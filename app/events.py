"""Hämtning, normalisering och lagring av evenemang från Visit Värmland."""

import asyncio
import html
import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from categories import describe_category
from version import __version__

API_BASE = os.getenv("VISITVARMLAND_API", "https://turid.visitvarmland.com/api/v8")
SITE_BASE = "https://visitvarmland.com"
PAGE_SIZE = 50  # API:ets maxgräns per sida
TZ = ZoneInfo(os.getenv("TZ", "Europe/Stockholm"))
USER_AGENT = f"varmlandsinfo/{__version__} (+https://github.com/tubalainen/varmlandsinfo)"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_FILE = DATA_DIR / "visitvarmland.json"
CACHE_FORMAT = 1

log = logging.getLogger("varmlandsinfo")

state: dict = {"events": [], "updated": None, "error": None, "municipalities": {}, "refreshing": False,
               "storage_error": None}
_refresh_task: asyncio.Task | None = None


def today() -> date:
    return datetime.now(TZ).date()


def strip_html(text: str | None, limit: int = 700) -> str:
    if not text:
        return ""
    text = re.sub(r"<\s*(br|/p|/h\d|/li)\s*/?>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " …"
    return text


def https_url(url: str | None) -> str | None:
    if url and isinstance(url, str) and url.startswith(("https://", "http://")):
        return url
    return None


def normalize(ev: dict, municipalities: dict[int, str]) -> dict | None:
    first_day = today().isoformat()
    occasions = sorted(
        (
            {
                "date_start": o.get("date_start"),
                "date_end": o.get("date_end") or o.get("date_start"),
                "time_start": (o.get("time_start") or "")[:5] or None,
                "time_end": (o.get("time_end") or "")[:5] or None,
            }
            for o in ev.get("occasions") or []
            if o.get("date_start")
        ),
        key=lambda o: (o["date_start"], o["time_start"] or ""),
    )
    for o in occasions:
        # 00:00 utan sluttid betyder i praktiken "tid ej angiven"
        if o["time_start"] == "00:00" and o["time_end"] in (None, "00:00", "23:59"):
            o["time_start"] = o["time_end"] = None
    occasions = [o for o in occasions if o["date_end"] >= first_day]
    if not occasions:
        return None

    categories = [
        {"title": c.get("title"), **describe_category(c.get("title"))}
        for c in ev.get("categories") or []
    ] or [{"title": "Övriga evenemang", **describe_category("Övriga evenemang")}]

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
            "address": ", ".join(
                x for x in (addr.get("street_1"), addr.get("zip_code"), addr.get("city")) if x
            ),
            "lat": p.get("latitude"),
            "lon": p.get("longitude"),
        }

    images = []
    for img in ev.get("images") or []:
        large = https_url(img.get("large"))
        if large:
            images.append(
                {
                    "small": https_url(img.get("small")) or large,
                    "medium": https_url(img.get("medium")) or large,
                    "large": large,
                    "alt": img.get("alt_text") or ev.get("title") or "",
                    "copyright": img.get("copyright") or "",
                }
            )

    slug = ev.get("slug") or ""
    return {
        "id": ev.get("id"),
        "source": "Visit Värmland",
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
        "next": occasions[0],
    }


async def get_json(client: httpx.AsyncClient, path: str, **params) -> dict:
    for attempt in range(5):
        r = await client.get(f"{API_BASE}/{path}", params=params)
        if r.status_code == 429:
            wait = int(r.headers.get("retry-after", 10))
            log.warning("Rate limit, väntar %ss", wait)
            await asyncio.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Gav upp efter upprepade 429 för {path}")


async def fetch_visitvarmland() -> tuple[list[dict], dict[int, str]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        try:
            mdata = await get_json(client, "municipalities")
            municipalities = {m["id"]: m["title"] for m in mdata.get("data", [])}
        except Exception as exc:  # kommunlistan är inte kritisk
            log.warning("Kunde inte hämta kommuner: %s", exc)
            municipalities = state["municipalities"]

        raw: list[dict] = []
        page, total_pages = 1, 1
        while page <= total_pages:
            data = await get_json(client, "events", limit=PAGE_SIZE, page=page)
            raw.extend(data.get("data", []))
            total_pages = int(data.get("total_pages") or 1)
            page += 1
            await asyncio.sleep(0.3)
    return raw, municipalities


def apply(raw: list[dict], municipalities: dict[int, str], updated: str) -> int:
    """Normaliserar rådata och gör den till aktuell data. Returnerar antal aktuella evenemang."""
    events = [e for e in (normalize(ev, municipalities) for ev in raw) if e]
    events.sort(key=lambda e: (e["next"]["date_start"], e["next"]["time_start"] or "", e["title"]))
    state.update(events=events, municipalities=municipalities, updated=updated)
    return len(events)


def save_cache(raw: list[dict], municipalities: dict[int, str], updated: str) -> None:
    """Sparar rådata atomärt (skriv till temporär fil, byt sedan namn)."""
    payload = {
        "format": CACHE_FORMAT,
        "source": API_BASE,
        "updated": updated,
        "app_version": __version__,
        "municipalities": municipalities,
        "events": raw,
    }
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CACHE_FILE)
        state["storage_error"] = None
        log.info("Sparade %d evenemang i %s", len(raw), CACHE_FILE)
    except OSError as exc:
        state["storage_error"] = f"Kan inte spara till {CACHE_FILE}: {exc}"
        log.warning("%s (data finns bara i minnet)", state["storage_error"])


def load_cache() -> bool:
    """Läser in sparad data vid start. Returnerar True om det fanns giltig data."""
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("format") != CACHE_FORMAT or not isinstance(payload.get("events"), list):
            log.warning("Okänt format i %s, ignorerar filen", CACHE_FILE)
            return False
        municipalities = {int(k): v for k, v in (payload.get("municipalities") or {}).items()}
        n = apply(payload["events"], municipalities, payload.get("updated"))
        log.info("Läste in %d evenemang (%d aktuella) från %s, hämtade %s",
                 len(payload["events"]), n, CACHE_FILE, payload.get("updated"))
        return True
    except FileNotFoundError:
        log.info("Ingen sparad data i %s ännu", CACHE_FILE)
    except (OSError, ValueError) as exc:
        log.warning("Kunde inte läsa %s: %s", CACHE_FILE, exc)
    return False


async def _refresh() -> None:
    state["refreshing"] = True
    try:
        raw, municipalities = await fetch_visitvarmland()
        updated = datetime.now(TZ).isoformat(timespec="seconds")
        n = apply(raw, municipalities, updated)
        state["error"] = None
        log.info("Hämtade %d evenemang (%d aktuella)", len(raw), n)
        await asyncio.to_thread(save_cache, raw, municipalities, updated)
    except Exception as exc:
        # Senast hämtade (eller sparade) data ligger kvar
        log.exception("Uppdatering misslyckades")
        state["error"] = str(exc)
    finally:
        state["refreshing"] = False


async def refresh() -> None:
    """Startar en uppdatering, eller väntar in den som redan pågår."""
    global _refresh_task
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = asyncio.create_task(_refresh())
    # shield: en klient som kopplar ner ska inte avbryta hämtningen
    await asyncio.shield(_refresh_task)


def current_events() -> list[dict]:
    """Evenemang med tillfällen som inte passerat, sorterade på nästa tillfälle."""
    first_day = today().isoformat()
    result = []
    for e in state["events"]:
        occ = [o for o in e["occasions"] if o["date_end"] >= first_day]
        if occ:
            result.append({**e, "occasions": occ, "next": occ[0]})
    result.sort(key=lambda e: (e["next"]["date_start"], e["next"]["time_start"] or "", e["title"]))
    return result
