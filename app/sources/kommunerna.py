"""Kommunernas egna evenemangskalendrar (Säffle och Kil), som inte finns hos Visit Värmland (#79).

Båda kommunerna använder Sitevision med moduler från Soleil IT, och de visas som en källa, *Kommunerna*, i
gränssnittet (som Loppisar och Motorsport):

- **Säffle** (modulen eventsList): sidan hämtar tillfällena som JSON från ett appresource-anrop med sidans
  sökvägar (`paths[]`). Ett tillfälle per rad, med plats, kategorier, bild och biljettlänk. Datumen står utan år
  ("30 september"), och listan innehåller bara tillfällen som inte är slut.
- **Kil** (modulen eventListing): serverrenderad lista, 25 per sida (`?start=25`). Sidan har listans data som JSON
  (`registerInitialState`) med datum och tider i ISO-format, men utan plats och kategori.

Återkommande tillfällen (samma titel och plats) blir ett evenemang med flera tillfällen.
"""

import json
import re
from datetime import date
from urllib.parse import quote, urljoin

import httpx

from common import SourceError, category, clean_text, finalize, get_json, get_text, today

GROUP = "Kommunerna"
MAX_PAGES = 4        # skydd mot oändliga sidbyten: Säffle ger allt i ett anrop och Kil har 25 per sida

MONTHS = {name: i for i, name in enumerate(
    ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
     "november", "december"], start=1)}
DAY_MONTH = re.compile(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")", re.I)
URI_DATE = re.compile(r"/(\d{4})-(\d{2})-(\d{2})-")
TIME = re.compile(r"^(\d{1,2})[:.](\d{2})")
# Kategorier för Kil, som saknar egna (Säffle har kategorier). Ur titeln, och Barn även ur beskrivningen.
# Utan träff tar ordreglerna i categories.refine vid.
KIL_RULES = [
    ("Utställning", re.compile(r"utställning", re.I)),
    ("Föreläsning och workshop", re.compile(r"föreläsning|föredrag|författarsamtal|workshop|kulturträff", re.I)),
    ("Teater och underhållning", re.compile(r"teater|\bshow\b|humor|revy", re.I)),
]
CHILD_RE = re.compile(r"\bbarn|\bbaby|bebis|småbarn|sagostund|förskola|\bbamse", re.I)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().translate(str.maketrans("åäöé", "aaoe"))).strip("-")


def _time(text: str | None) -> str | None:
    m = TIME.match((text or "").strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def _group(items: list[dict], key) -> list[list[dict]]:
    groups: dict = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return list(groups.values())


# ---------------------------------------------------------------- Säffle

SAFFLE_BASE = "https://saffle.se"
SAFFLE_PAGE = f"{SAFFLE_BASE}/uppleva-och-gora/visit-saffle/evenemang.html"
# Kalendermodulens anrop och sökvägar, ur sidans konfiguration (Soleil.webapps['EventsListing'].render)
SAFFLE_ITEMS = f"{SAFFLE_BASE}/appresource/4.5a6b7d4f18f9ed30d72b6177/12.5a6b7d4f18f9ed30d72b62d9/items"
SAFFLE_PATHS = ["3.66fab3816ed55d01b187", "3.6d8eeb2116ed543f18e225d4", "3.7b462ceb16f19853bb935d16",
                "3.7b462ceb16f19853bb935c72"]
SAFFLE_PAGE_SIZE = 200

SAFFLE_CATEGORIES = {
    "Barn": "Barn",
    "Dans": "Dans",
    "Entreprenörskap": "Föreläsning och workshop",
    "Film": "Film",
    "Föreläsning": "Föreläsning och workshop",
    "Hantverk & slöjd": "Föreläsning och workshop",
    "Humor": "Teater och underhållning",
    "Konst": "Utställning",
    "Kurs": "Föreläsning och workshop",
    "Litteratur": "Böcker och litteratur",
    "Loppis": "Loppis",
    "Marknad": "Marknad, mässa och auktion",
    "Musik": "Musik",
    "Mässa": "Marknad, mässa och auktion",
    "Opera": "Musik",
    "Show": "Teater och underhållning",
    "Sport & motion": "Sport, motion och hälsa",
    "Teater": "Teater och underhållning",
    "Utställning": "Utställning",
    "Övrigt": "Övrigt",
}


class Saffle:
    key = "saffle"
    title = "Säffle kommun"
    group = GROUP
    homepage = SAFFLE_PAGE

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        hits: list[dict] = []
        for _ in range(MAX_PAGES):
            data = await get_json(client, SAFFLE_ITEMS, self.title, headers={"X-Requested-With": "XMLHttpRequest"},
                                  start=len(hits), num=SAFFLE_PAGE_SIZE, **{"paths[]": SAFFLE_PATHS})
            page = data.get("hits") if isinstance(data, dict) else None
            if not isinstance(page, list):
                raise SourceError(f"{self.title} svarade inte med en evenemangslista, anropet kan ha ändrats")
            hits += page
            if not page or len(hits) >= int(data.get("hitCount") or 0):
                break
        return {"hits": hits}

    def normalize(self, payload: dict) -> list[dict]:
        items = [i for i in (parse_saffle(h) for h in payload.get("hits") or []) if i]
        groups = _group(items, lambda i: (i["title"].lower(), (i["location"] or "").lower()))
        return [e for e in (normalize_saffle(g) for g in groups) if e]


def _day_month(text: str | None) -> tuple[int, int] | None:
    m = DAY_MONTH.search(text or "")
    return (MONTHS[m.group(2).lower()], int(m.group(1))) if m else None


def saffle_dates(start_text: str, end_text: str | None, uri: str = "") -> tuple[date, date] | None:
    """Start och slut för '30 september' utan år. Listan har bara tillfällen som inte är slut, så slutet ligger i
    år eller nästa år, och starten före slutet. Adressen ('/2026-09-30-mogendans…') ger året när den stämmer."""
    start_md = _day_month(start_text)
    end_md = _day_month(end_text) or start_md
    if not start_md:
        return None
    t = today()
    try:
        m = URI_DATE.search(uri or "")
        if m and (int(m.group(2)), int(m.group(3))) == start_md:
            start = date(int(m.group(1)), *start_md)
        else:
            year = t.year + (1 if end_md < (t.month, t.day) else 0)
            start = date(year - (1 if start_md > end_md else 0), *start_md)
        end = date(start.year + (1 if end_md < start_md else 0), *end_md)
    except ValueError:
        return None
    return start, end


def parse_saffle(hit: dict) -> dict | None:
    if not isinstance(hit, dict):
        return None
    title = clean_text(hit.get("title"))
    dates = saffle_dates(hit.get("startDate") or "", hit.get("endDate"), hit.get("uri") or "")
    if not title or not dates:
        return None
    image = (hit.get("image") or {}).get("uri") if isinstance(hit.get("image"), dict) else None
    uri = hit.get("uri") or ""
    # Över flera dagar (t.ex. en föreställning 2–4 oktober) gäller sluttiden den sista dagen, så den tas inte med
    time_end = _time(hit.get("endTime")) if dates[0] == dates[1] else None
    return {
        "id": str(hit.get("id") or ""), "title": title, "summary": clean_text(hit.get("description")),
        "location": clean_text(hit.get("location")) or None, "start": dates[0], "end": dates[1],
        "time_start": _time(hit.get("startTime")), "time_end": time_end,
        "categories": [c for c in hit.get("categories") or [] if isinstance(c, str)],
        "url": urljoin(SAFFLE_BASE, quote(uri, safe="/%:.-_~")) if uri.startswith("/") else SAFFLE_PAGE,
        "image": urljoin(SAFFLE_BASE, image) if isinstance(image, str) and image.startswith("/") else None,
        "ticket": hit.get("ticket") if str(hit.get("ticket") or "").startswith("https://") else None,
    }


def normalize_saffle(items: list[dict]) -> dict | None:
    first = items[0]
    names = []
    for c in first["categories"]:
        name = SAFFLE_CATEGORIES.get(c, "Övrigt")
        if name not in names:
            names.append(name)
    image = first["image"]
    return finalize({
        "id": f"saffle-{_slug(first['title'])}-{_slug(first['location'] or '')}".rstrip("-"),
        "source": Saffle.title,
        "title": first["title"],
        "summary": first["summary"],
        "description": "",
        "categories": [category(n) for n in names],
        "municipality": "Säffle",
        "place": {"title": first["location"], "address": "", "lat": None, "lon": None} if first["location"] else None,
        "organizer": None,
        "url": first["url"],
        "booking_link": next((i["ticket"] for i in items if i["ticket"]), None),
        "website_link": None,
        "images": [{"small": image, "medium": image, "large": image, "alt": first["title"], "copyright": ""}]
        if image else [],
        "occasions": [{"date_start": i["start"].isoformat(), "date_end": i["end"].isoformat(),
                       "time_start": i["time_start"], "time_end": i["time_end"]} for i in items],
    })


# ---------------------------------------------------------------- Kil

KIL_BASE = "https://kil.se"
KIL_PAGE = f"{KIL_BASE}/arkiv/evenemang"
KIL_STATE = re.compile(r"registerInitialState\('[^']*',\s*(\{.*?\})\);\s*</script>", re.S)


class Kil:
    key = "kil"
    title = "Kils kommun"
    group = GROUP
    homepage = KIL_PAGE

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        items: list[dict] = []
        for _ in range(MAX_PAGES):
            url = KIL_PAGE if not items else f"{KIL_PAGE}?start={len(items)}"
            state = kil_state(await get_text(client, url, self.title))
            if state is None:
                raise SourceError(f"Hittade ingen evenemangslista hos {self.title}, sidans struktur kan ha ändrats")
            page = [i for i in state["items"] if isinstance(i, dict)]
            items += page
            if not page or len(items) >= int(state.get("count") or 0):
                break
        return {"items": items}

    def normalize(self, payload: dict) -> list[dict]:
        items = [i for i in (parse_kil(x) for x in payload.get("items") or []) if i]
        return [e for e in (normalize_kil(g) for g in _group(items, lambda i: i["title"].lower())) if e]


def kil_state(page: str) -> dict | None:
    """Listans data ur sidan (den första registerInitialState med items och count)."""
    for m in KIL_STATE.finditer(page):
        try:
            state = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(state, dict) and isinstance(state.get("items"), list) and "count" in state:
            return state
    return None


def parse_kil(item: dict) -> dict | None:
    start, end = item.get("start") or {}, item.get("end") or {}
    title = clean_text(item.get("title"))
    if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(start.get("date") or "")):
        return None
    end_date = end.get("date") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(end.get("date") or "")) else start["date"]
    uri = item.get("uri") or ""
    time_start, time_end = _time(start.get("time")), _time(end.get("time"))
    if time_start == "00:00" and time_end in (None, "00:00", "23:59"):   # heldag, t.ex. utställningar
        time_start = time_end = None
    if end_date != start["date"]:                                       # sluttiden gäller sista dagen
        time_end = None
    return {
        "title": title, "summary": clean_text(item.get("desc")),
        "start": start["date"], "end": max(end_date, start["date"]),
        "time_start": time_start, "time_end": time_end,
        "url": urljoin(KIL_BASE, uri) if uri.startswith("/") else KIL_PAGE,
    }


def normalize_kil(items: list[dict]) -> dict | None:
    first = items[0]
    names = [name for name, pattern in KIL_RULES if pattern.search(first["title"])]
    if CHILD_RE.search(f"{first['title']} {first['summary']}"):
        names.append("Barn")
    return finalize({
        "id": f"kil-{_slug(first['title'])}",
        "source": Kil.title,
        "title": first["title"],
        "summary": first["summary"],
        "description": "",
        "categories": [category(n) for n in names],
        "municipality": "Kil",
        "place": None,
        "organizer": None,
        "url": first["url"],
        "booking_link": None,
        "website_link": None,
        "images": [],
        "occasions": [{"date_start": i["start"], "date_end": i["end"],
                       "time_start": i["time_start"], "time_end": i["time_end"]} for i in items],
    })
