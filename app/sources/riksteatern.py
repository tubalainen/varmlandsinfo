"""Riksteatern: föreställningarna i Värmlands län (#98).

Riksteaterföreningarna turnerar till Folkets Hus, bygdegårdar och teatrar, och deras föreställningar finns ofta
inte hos andra källor (t.ex. i Oleby Folkets Hus). Riksteaterns sida använder ett öppet JSON-API, och ett anrop ger
alla föreställningar i länet. Slutna föreställningar (skolföreställningar och liknande), inställda och flyttade tas
inte med, och inte heller bio eller sändningar på bioduken.
"""

import asyncio
import re

import httpx

from common import SourceError, category, clean_text, finalize, get_json, https_url

BASE = "https://www.riksteatern.se"
API = f"{BASE}/api/performance/filter/all"
REGION = "17"           # Värmlands län i Riksteaterns filter (/api/performance/filteritems/all)
PER_PAGE = 200
MAX_PAGES = 3
SCREEN = re.compile(r"på bio\b|\bbio:|livesänds till biograf|sänds på bio", re.I)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


class Riksteatern:
    key = "riksteatern"
    title = "Riksteatern"
    homepage = f"{BASE}/forestallningar/"

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        performances = []
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                await asyncio.sleep(1)
            items = await get_json(client, API, self.title, onlyNationalProductions="false",
                                   showSubscribedPerformances="true", region=REGION, page=page, itemsPerPage=PER_PAGE)
            if not isinstance(items, list):
                raise SourceError(f"{self.title} svarade inte med föreställningar, API:t kan ha ändrats")
            performances += items
            if len(items) < PER_PAGE:
                break
        return {"performances": performances}

    def normalize(self, payload: dict) -> list[dict]:
        events, seen = [], set()
        for p in payload.get("performances") or []:
            if isinstance(p, dict) and is_public(p) and (e := normalize_performance(p)) and e["id"] not in seen:
                seen.add(e["id"])
                events.append(e)
        return events


def is_public(p: dict) -> bool:
    """Öppen för alla och blir av som planerat, och inte bio."""
    if p.get("isPrivate") or p.get("isCanceled") or p.get("isPostponed"):
        return False
    return not SCREEN.search(clean_text(p.get("title")))


def normalize_performance(p: dict) -> dict | None:
    title = clean_text(p.get("title"))
    day = DATE_RE.match(p.get("date") or "")
    if not title or not day:
        return None
    time = (p.get("startTime") or "").strip()
    time = time.zfill(5) if TIME_RE.match(time) else None
    path = p.get("url") or ""
    url = https_url(BASE + path) if path.startswith("/") else BASE + "/forestallningar/"
    place = clean_text(p.get("locationInfo")) or clean_text(p.get("location"))
    organizer = clean_text(p.get("orgName"))
    image = https_url(p.get("imageUrl"))
    return finalize({
        "id": f"riksteatern-{path.rstrip('/').rsplit('/', 1)[-1] or day.group(0)}",
        "source": Riksteatern.title,
        "title": title,
        "summary": f"Riksteatern, arrangör {organizer}." if organizer else "Riksteatern.",
        "description": "",
        "categories": [category("Teater och underhållning")],
        "municipality": clean_text(p.get("municipality")) or None,
        "place": {"title": place, "address": "", "lat": None, "lon": None},
        "organizer": organizer,
        "url": url,
        "booking_link": url,
        "website_link": None,
        "images": [{"small": image, "medium": image, "large": image, "alt": title, "copyright": ""}] if image else [],
        "occasions": [{"date_start": day.group(0), "date_end": day.group(0), "time_start": time, "time_end": None}],
    })
