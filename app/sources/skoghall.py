"""Skoghalls Folkets Hus (Hammarö): allt utom film och sändningar på bioduken (#96).

Sajten är WordPress med tillägget Theater. Produktionerna och deras kategorier finns i REST-API:t, och varje
produktionssida har en tabell med visningarna, där biljettlänken har exakt datum och tid
(`…tomovie@salongnr=6&tid=19:00&datum=2026-11-06`). De flesta produktionerna är filmer, så bara de som säkert inte är
film tas med (`is_live`), och bara deras sidor hämtas.
"""

import asyncio
import html
import re

import httpx

from common import SourceError, category, clean_text, finalize, get_json, get_text, https_url, log, strip_html, today

BASE = "https://skoghallsfolketshus.se"
API = f"{BASE}/wp-json/wp/v2"
ADDRESS = "Skogåsvägen 3, 663 21 Skoghall"

# Kategorier hos sajten som betyder att produktionen inte är film. Filmerna har genrer (Drama, Komedi, Action …)
# eller ingen kategori alls, och sajtens kategori Bio används inte konsekvent.
LIVE_CATEGORIES = {"föreläsning", "teater", "musikteater", "pubkväll", "rockpub", "blues", "blueskväll", "live på scen",
                   "livemusik", "konsert", "julkonsert", "standup", "gala", "svenshult", "bussresa", "evenemang"}
LIVE_TITLE = re.compile(r"^(pubkväll|rockpub|blueskväll|teater|musikteater|konsert|författarbesök|föreläsning|"
                        r"stand-?up|bussresa)\b", re.I)
# Sändningar på bioduken (Opera på Bio, Musikal på Bio, André Rieus julkonsert) räknas som bio
SCREEN = re.compile(r"på bio\b|\bbio:|seniorbio|knattebio|livesänds till biograf|sänds på bio", re.I)

CATEGORIES = {
    "föreläsning": "Föreläsning och workshop", "författarbesök": "Föreläsning och workshop",
    "teater": "Teater och underhållning", "musikteater": "Teater och underhållning",
    "standup": "Teater och underhållning", "stand-up": "Teater och underhållning", "gala": "Teater och underhållning",
    "pubkväll": "Musik", "rockpub": "Musik", "blues": "Musik", "blueskväll": "Musik", "konsert": "Musik",
    "julkonsert": "Musik", "livemusik": "Musik", "live på scen": "Musik",
}
# Andra platser än huset: (ord i titeln eller texten, plats, kommun)
PLACES = [("tingvallakyrkan", "Tingvallakyrkan", "Karlstad"),
          ("svenshult", "Bygdegården Svenshult", "Hammarö")]
RESTAURANT = "6"        # salongen i biljettlänken för restaurangen (pubkvällar)

TICKET_RE = re.compile(r"tomovie@salongnr=(\d+)&(?:amp;)?tid=(\d{1,2}:\d{2})&(?:amp;)?datum=(\d{4}-\d{2}-\d{2})")
ROW_RE = re.compile(r'<tr class="event-row">(.*?)</tr>', re.S)


class SkoghallsFolketsHus:
    key = "skoghall"
    title = "Skoghalls Folkets Hus"
    homepage = BASE

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        prods = await get_json(client, f"{API}/wp_theatre_prod", self.title, per_page=100,
                               _fields="id,title,link,categories,content")
        await asyncio.sleep(1)
        cats = await get_json(client, f"{API}/categories", self.title, per_page=100, _fields="id,name")
        if not isinstance(prods, list) or not isinstance(cats, list):
            raise SourceError(f"{self.title} svarade inte med produktioner, API:t kan ha ändrats")
        names = {c.get("id"): (c.get("name") or "") for c in cats}
        productions = [{"id": p.get("id"), "title": (p.get("title") or {}).get("rendered") or "",
                        "link": p.get("link") or "", "categories": [names.get(c, "") for c in p.get("categories") or []],
                        "content": (p.get("content") or {}).get("rendered") or ""} for p in prods]
        # Bara produktionerna som inte är film sparas, och bara deras sidor hämtas
        live = [p for p in productions if is_live(p) and p["link"].startswith(BASE)]
        pages = {}
        for p in live:
            await asyncio.sleep(1)
            try:
                pages[p["link"]] = trim(await get_text(client, p["link"], self.title))
            except SourceError as exc:
                log.warning("%s: %s", self.title, exc)    # t.ex. en produktion som just tagits bort
        if live and not pages:
            raise SourceError(f"Kunde inte läsa några produktionssidor hos {self.title}")
        return {"productions": live, "pages": pages}

    def normalize(self, payload: dict) -> list[dict]:
        pages = payload.get("pages") or {}
        events = []
        for p in payload.get("productions") or []:
            if is_live(p) and p.get("link") in pages:
                if e := normalize_production(p, pages[p["link"]]):
                    events.append(e)
        return events


def is_live(p: dict) -> bool:
    """Inte film och inte en sändning på bioduken: en levande kategori eller titel, och inget som säger bio."""
    title = clean_text(p.get("title"))
    if SCREEN.search(f"{title} {strip_html(p.get('content'), 2000)}"):
        return False
    return bool(LIVE_TITLE.match(title)) or any((c or "").lower() in LIVE_CATEGORIES for c in p.get("categories") or [])


def trim(page: str) -> str:
    """Bara affischen och visningstabellen ur produktionssidan, så att den sparade datan blir liten."""
    poster = re.search(r"<img[^>]*wp-post-image[^>]*>", page)
    start = page.find('class="event-table"')
    table = page[start:page.find("</table>", start) + 8] if start >= 0 else ""
    return (poster.group(0) if poster else "") + table


def occasions(page: str) -> tuple[list[dict], dict]:
    """Visningarna ur tabellen: datum och tid ur biljettlänken, annars ur raden (dd/mm kl. HH:MM, året räknas
    fram). Returnerar också pris, biljettlänk och salong för den första visningen."""
    occ, first = [], {}
    for row in ROW_RE.findall(page):
        ticket = TICKET_RE.search(row)
        if ticket:
            salong, time, day = ticket.groups()
        else:
            m = re.search(r"(\d{1,2})/(\d{1,2})</strong>\s*kl\.\s*(\d{1,2})[:.](\d{2})", row)
            if not m:
                continue
            d, mon, h, mi = (int(x) for x in m.groups())
            year = today().year + (1 if mon < today().month - 1 else 0)
            salong, time, day = None, f"{h:02d}:{mi:02d}", f"{year}-{mon:02d}-{d:02d}"
        occ.append({"date_start": day, "date_end": day, "time_start": time.zfill(5), "time_end": None})
        if not first:
            price = re.search(r"(?<![\d:/])(\d+)\s*kr\b", clean_text(row))
            link = re.search(r'href="([^"]+)"[^>]*tickets-button', row)
            first = {"price": price.group(1).replace(" ", "") if price else None, "salong": salong,
                     "booking": html.unescape(link.group(1)) if link else None}
    return occ, first


def _images(page: str, title: str) -> list[dict]:
    poster = re.search(r"<img[^>]*wp-post-image[^>]*>", page)
    if not poster:
        return []
    tag = poster.group(0)
    src = re.search(r'src="([^"]+)"', tag)
    sizes = sorted(((int(w), u) for u, w in re.findall(r"(https://\S+?)\s+(\d+)w", tag)), key=lambda x: x[0])
    small = https_url(src.group(1)) if src else None
    medium = next((u for w, u in sizes if w >= 500), small)
    large = sizes[-1][1] if sizes else small
    if not small and not large:
        return []
    return [{"small": small or large, "medium": https_url(medium) or small or large, "large": https_url(large) or small,
             "alt": title, "copyright": ""}]


def normalize_production(p: dict, page: str) -> dict | None:
    occ, first = occasions(page)
    if not occ:
        return None
    title = clean_text(p.get("title"))
    description = strip_html(p.get("content"))
    text = f"{title} {description}".lower()
    place, kommun = "Skoghalls Folkets Hus", "Hammarö"
    address = ADDRESS
    for word, other, other_kommun in PLACES:
        if word in text:
            place, kommun, address = other, other_kommun, ""
            break
    else:
        if first.get("salong") == RESTAURANT:
            place = "Skoghalls Folkets Hus, restaurangen"
    cats = []
    for c in [*(p.get("categories") or []), (LIVE_TITLE.match(title) or [None, None])[1]]:
        if (name := CATEGORIES.get((c or "").lower())) and name not in cats:
            cats.append(name)
    summary = strip_html(p.get("content"), 300)
    if first.get("price"):
        summary = f"{summary} Pris {first['price']} kr.".strip()
    url = https_url(p.get("link")) or BASE
    return finalize({
        "id": f"skoghall-{p.get('id')}",
        "source": SkoghallsFolketsHus.title,
        "title": title,
        "summary": summary,
        "description": description,
        "categories": [category(c) for c in cats or ["Övrigt"]],
        "municipality": kommun,
        "place": {"title": place, "address": address, "lat": None, "lon": None},
        "organizer": "Skoghalls Folkets Hus",
        "url": url,
        "booking_link": https_url(first.get("booking")),
        "website_link": None,
        "images": _images(page, title),
        "occasions": occ,
    })
