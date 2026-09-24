"""Ticketmaster Discovery API v2. Kräver en API-nyckel (TICKETMASTER_API_KEY).

Nyckeln skickas bara som parameter till Ticketmaster. Den loggas aldrig och syns aldrig i felmeddelanden
(common.get_json tar bort frågesträngen, och httpx-loggningen är avstängd i main.py).
"""

import asyncio
import os
from datetime import datetime, timezone

import httpx

from common import category, finalize, get_json, https_url

API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
API_KEY = os.getenv("TICKETMASTER_API_KEY", "").strip()
RADIUS_KM = int(os.getenv("TICKETMASTER_RADIUS_KM") or 150)
CENTER = (59.55, 13.30)        # ungefär mitt i Värmland
PAGE_SIZE = 200                # max per sida
MAX_RESULTS = 1000             # Ticketmaster ger max 1000 träffar per sökning (size * page)

# Orter i Värmland (samt Karlskoga och Degerfors, som Visit Värmland räknar in) -> kommun
LOCALITIES = {
    "karlstad": "Karlstad", "molkom": "Karlstad", "vålberg": "Karlstad", "skattkärr": "Karlstad",
    "hammarö": "Hammarö", "skoghall": "Hammarö",
    "arvika": "Arvika", "årjäng": "Årjäng", "eda": "Eda", "charlottenberg": "Eda", "åmotfors": "Eda",
    "säffle": "Säffle", "grums": "Grums", "kil": "Kil", "forshaga": "Forshaga", "deje": "Forshaga",
    "sunne": "Sunne", "torsby": "Torsby", "hagfors": "Hagfors", "ekshärad": "Hagfors",
    "munkfors": "Munkfors", "filipstad": "Filipstad", "storfors": "Storfors",
    "kristinehamn": "Kristinehamn", "karlskoga": "Karlskoga", "degerfors": "Degerfors",
}
# Postnummerprefix i Värmland (662 = Åmål i Västra Götaland tas inte med)
POSTCODE_PREFIXES = ("65", "660", "661", "663", "664", "665", "666", "667", "668", "669",
                     "67", "68", "691", "693")

# Ticketmasters segment och genrer -> appens kategorier
SEGMENTS = {
    "music": "Musik", "musik": "Musik",
    "sports": "Sport, motion och hälsa", "sport": "Sport, motion och hälsa",
    "arts & theatre": "Teater och underhållning", "konst & teater": "Teater och underhållning",
    "kultur & teater": "Teater och underhållning", "film": "Teater och underhållning",
    "family": "Barn", "familj": "Barn",
    "miscellaneous": "Övriga evenemang", "övrigt": "Övriga evenemang",
}
GENRES = {"dance": "Dans", "dans": "Dans", "children's theatre": "Barn", "comedy": "Teater och underhållning"}


def geohash(lat: float, lon: float, precision: int = 6) -> str:
    """Geohash för Ticketmasters geoPoint-parameter."""
    chars = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_rng, lon_rng = [-90.0, 90.0], [-180.0, 180.0]
    out, bits, ch, even = [], 0, 0, True
    while len(out) < precision:
        rng, val = (lon_rng, lon) if even else (lat_rng, lat)
        mid = (rng[0] + rng[1]) / 2
        if val >= mid:
            ch |= 1 << (4 - bits)
            rng[0] = mid
        else:
            rng[1] = mid
        even = not even
        bits += 1
        if bits == 5:
            out.append(chars[ch])
            bits, ch = 0, 0
    return "".join(out)


def municipality_for(venue: dict) -> str | None:
    """Kommun för en arena i Värmland, annars None (arenan ligger utanför Värmland)."""
    city = ((venue.get("city") or {}).get("name") or "").strip().lower()
    if city in LOCALITIES:
        return LOCALITIES[city]
    postcode = (venue.get("postalCode") or "").replace(" ", "")
    if postcode.startswith(POSTCODE_PREFIXES):
        return (venue.get("city") or {}).get("name") or None
    return None


class Ticketmaster:
    key = "ticketmaster"
    title = "Ticketmaster"
    homepage = "https://www.ticketmaster.se"

    def config_error(self) -> str | None:
        return None if API_KEY else "Ingen API-nyckel (sätt TICKETMASTER_API_KEY i .env)"

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        events: dict[str, dict] = {}
        page, total_pages = 0, 1
        while page < total_pages and (page + 1) * PAGE_SIZE <= MAX_RESULTS:
            data = await get_json(
                client, API_URL, self.title,
                apikey=API_KEY, countryCode="SE", geoPoint=geohash(*CENTER), radius=RADIUS_KM, unit="km",
                startDateTime=start, sort="date,asc", size=PAGE_SIZE, page=page, locale="*",
            )
            for ev in (data.get("_embedded") or {}).get("events") or []:
                venue = ((ev.get("_embedded") or {}).get("venues") or [{}])[0]
                if municipality_for(venue):
                    events[ev["id"]] = ev
            total_pages = int((data.get("page") or {}).get("totalPages") or 0)
            page += 1
            await asyncio.sleep(0.25)   # max 5 anrop per sekund
        return {"events": list(events.values())}

    def normalize(self, payload: dict) -> list[dict]:
        return [e for e in (normalize_event(ev) for ev in payload.get("events") or []) if e]


def _pick_images(ev: dict) -> list[dict]:
    imgs = [i for i in ev.get("images") or [] if https_url(i.get("url"))]
    if not imgs:
        return []
    wide = sorted((i for i in imgs if i.get("ratio") == "16_9"), key=lambda i: i.get("width") or 0) or \
        sorted(imgs, key=lambda i: i.get("width") or 0)
    small = next((i for i in wide if (i.get("width") or 0) >= 300), wide[0])
    medium = next((i for i in wide if (i.get("width") or 0) >= 600), wide[-1])
    return [{"small": small["url"], "medium": medium["url"], "large": wide[-1]["url"],
             "alt": ev.get("name") or "", "copyright": ""}]


def _categories(ev: dict) -> list[dict]:
    titles = []
    for c in ev.get("classifications") or []:
        genre = ((c.get("genre") or {}).get("name") or "").lower()
        segment = ((c.get("segment") or {}).get("name") or "").lower()
        title = GENRES.get(genre) or SEGMENTS.get(segment)
        if title and title not in titles:
            titles.append(title)
    return [category(t) for t in titles or ["Övriga evenemang"]]


def normalize_event(ev: dict) -> dict | None:
    dates = ev.get("dates") or {}
    if ((dates.get("status") or {}).get("code") or "").lower() in ("cancelled", "canceled"):
        return None
    start = dates.get("start") or {}
    day = start.get("localDate")
    if not day:
        return None
    venue = ((ev.get("_embedded") or {}).get("venues") or [{}])[0]
    municipality = municipality_for(venue)
    if not municipality:
        return None

    genres = []
    for c in ev.get("classifications") or []:
        for part in ("genre", "subGenre"):
            name = (c.get(part) or {}).get("name")
            if name and name.lower() != "undefined" and name not in genres:
                genres.append(name)
    info = ev.get("info") or ev.get("pleaseNote") or ""
    summary = info[:300] if info else (f"{', '.join(genres)} på {venue.get('name')}." if genres else "")
    prices = ev.get("priceRanges") or []
    if prices and prices[0].get("min") is not None:
        p = prices[0]
        summary = (summary + " " if summary else "") + \
            f"Pris från {p['min']:.0f} {p.get('currency', 'SEK')}".replace("SEK", "kr") + "."

    loc = venue.get("location") or {}
    address = ", ".join(x for x in ((venue.get("address") or {}).get("line1"), venue.get("postalCode"),
                                    (venue.get("city") or {}).get("name")) if x)
    url = https_url(ev.get("url"))
    return finalize({
        "id": f"tm-{ev.get('id')}",
        "source": Ticketmaster.title,
        "title": ev.get("name") or "(utan titel)",
        "summary": summary,
        "description": info,
        "categories": _categories(ev) + ([category("Gratis")] if prices and all(
            (p.get("min") or 0) == 0 and (p.get("max") or 0) == 0 for p in prices) else []),
        "municipality": municipality,
        "place": {"title": venue.get("name"), "address": address,
                  "lat": loc.get("latitude"), "lon": loc.get("longitude")} if venue.get("name") else None,
        "organizer": (ev.get("promoter") or {}).get("name"),
        "url": url,
        "booking_link": url,
        "website_link": None,
        "images": _pick_images(ev),
        "occasions": [{"date_start": day, "date_end": day,
                       "time_start": (start.get("localTime") or "")[:5] or None, "time_end": None}],
    })
