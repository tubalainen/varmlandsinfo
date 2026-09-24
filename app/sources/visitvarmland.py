"""Visit Värmland (Turid API v8). Omfattar även Karlstads och Hammarö kommuns evenemangskalendrar,
som visar ett urval ur samma API."""

import asyncio
import os
from datetime import datetime, timedelta

import httpx

from common import TZ, category, finalize, get_json, https_url, log, now_iso, strip_html

API_BASE = os.getenv("VISITVARMLAND_API", "https://turid.visitvarmland.com/api/v8")
SITE_BASE = "https://visitvarmland.com"
PAGE_SIZE = 50                                  # API:ets maxgräns per sida
MUNICIPALITIES_MAX_AGE = timedelta(days=7)      # kommunlistan ändras sällan


def _older_than(iso: str | None, age: timedelta) -> bool:
    if not iso:
        return True
    try:
        return datetime.now(TZ) - datetime.fromisoformat(iso) > age
    except ValueError:
        return True


class VisitVarmland:
    key = "visitvarmland"
    title = "Visit Värmland"
    homepage = "https://visitvarmland.com/evenemang"

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        previous = previous or {}
        municipalities = previous.get("municipalities") or {}
        municipalities_updated = previous.get("municipalities_updated")
        if not municipalities or _older_than(municipalities_updated, MUNICIPALITIES_MAX_AGE):
            try:
                data = await get_json(client, f"{API_BASE}/municipalities", self.title)
                municipalities = {m["id"]: m["title"] for m in data.get("data", [])}
                municipalities_updated = now_iso()
            except Exception as exc:  # kommunlistan är inte kritisk
                log.warning("Kunde inte hämta kommuner: %s", exc)

        raw: list[dict] = []
        page, total_pages = 1, 1
        while page <= total_pages:
            data = await get_json(client, f"{API_BASE}/events", self.title, limit=PAGE_SIZE, page=page)
            raw.extend(data.get("data", []))
            total_pages = int(data.get("total_pages") or 1)
            page += 1
            await asyncio.sleep(0.5)
        return {"municipalities": municipalities, "municipalities_updated": municipalities_updated, "events": raw}

    def normalize(self, payload: dict) -> list[dict]:
        municipalities = {int(k): v for k, v in (payload.get("municipalities") or {}).items()}
        return [e for e in (normalize_event(ev, municipalities) for ev in payload.get("events") or []) if e]


def normalize_event(ev: dict, municipalities: dict[int, str]) -> dict | None:
    occasions = []
    for o in ev.get("occasions") or []:
        if not o.get("date_start"):
            continue
        occ = {
            "date_start": o["date_start"],
            "date_end": o.get("date_end") or o["date_start"],
            "time_start": (o.get("time_start") or "")[:5] or None,
            "time_end": (o.get("time_end") or "")[:5] or None,
        }
        # 00:00 utan sluttid betyder i praktiken "tid ej angiven"
        if occ["time_start"] == "00:00" and occ["time_end"] in (None, "00:00", "23:59"):
            occ["time_start"] = occ["time_end"] = None
        occasions.append(occ)

    categories = [category(c.get("title")) for c in ev.get("categories") or [] if c.get("title")] \
        or [category("Övriga evenemang")]

    municipality = None
    for org in ev.get("organizers") or []:
        municipality = municipalities.get(org.get("municipality_id")) or org.get("city")
        if municipality:
            break

    place = None
    places = ev.get("places") or []
    if places:
        p = places[0]
        addr = p.get("address") or {}
        place = {
            "title": p.get("title"),
            "address": ", ".join(x for x in (addr.get("street_1"), addr.get("zip_code"), addr.get("city")) if x),
            "lat": p.get("latitude"),
            "lon": p.get("longitude"),
        }

    images = []
    for img in ev.get("images") or []:
        large = https_url(img.get("large"))
        if large:
            images.append({
                "small": https_url(img.get("small")) or large,
                "medium": https_url(img.get("medium")) or large,
                "large": large,
                "alt": img.get("alt_text") or ev.get("title") or "",
                "copyright": img.get("copyright") or "",
            })

    slug = ev.get("slug") or ""
    return finalize({
        "id": f"vv-{ev.get('id')}",
        "source": VisitVarmland.title,
        "title": ev.get("title") or "(utan titel)",
        "summary": strip_html(ev.get("sales_text") or ev.get("description"), 300),
        "description": strip_html(ev.get("presentation") or ev.get("description")),
        "categories": categories,
        "municipality": municipality,
        "place": place,
        "organizer": (ev.get("organizers") or [{}])[0].get("title"),
        "url": f"{SITE_BASE}/{slug}" if slug else None,
        "booking_link": https_url(ev.get("booking_link")),
        "website_link": https_url(ev.get("website_link")),
        "images": images,
        "occasions": occasions,
    })
