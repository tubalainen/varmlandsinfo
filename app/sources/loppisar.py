"""loppisar.com: loppisar i Värmland med öppettider per dag (sökningen, serverrenderad HTML, inget API).

Sökresultatet har en rubrik per dag ("Fredagen den 25 september 2026:") och en rad per loppis med länk,
öppettider, typ och plats. En loppis blir ett evenemang med ett tillfälle per dag den har öppet.
Bilderna ligger under /images/, som robots.txt inte tillåter, så de tas inte med.
"""

import re
from datetime import date
from urllib.parse import urlencode

import httpx

from common import SourceError, category, clean_text, finalize, get_text, today

BASE = "https://www.loppisar.com"
LAN_VARMLAND = 15
DAYS = 30                                    # så många dagar framåt som hämtas (ett anrop)
HOMEPAGE = f"{BASE}/sokning.html"

MONTHS = {name: i for i, name in enumerate(
    ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
     "november", "december"], start=1)}
DAY_HEADER = re.compile(r"<h4[^>]*>\s*\w+ den (\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4}):?\s*</h4>", re.I)
ROW = re.compile(
    r'<a href="(l(\d+)/[^"]+)"><strong>(.*?)</strong></a>\s*-\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
    r'\s*(?:\(([^)]*)\))?.*?<strong>Plats:</strong>\s*(.*?)</span>', re.S)
# Kommunnamn som slutar på s även utan genitiv ("Hagfors kommun")
S_NAMES = {"Hagfors", "Munkfors", "Storfors"}


def search_url(first_day: date) -> str:
    return f"{HOMEPAGE}?" + urlencode({"sokning": 1, "do_search": 1, "slanID": LAN_VARMLAND, "skommunID": "alla",
                                        "sdatum": first_day.isoformat(), "srange": "framat", "srangetime": DAYS})


class Loppisar:
    key = "loppisar"
    title = "loppisar.com"
    homepage = HOMEPAGE

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        page = await get_text(client, search_url(today()), self.title)
        if "Sökresultat" not in page:
            raise SourceError(f"Hittade inget sökresultat hos {self.title}, sidans struktur kan ha ändrats")
        return {"html": page}

    def normalize(self, payload: dict) -> list[dict]:
        groups: dict[str, list[dict]] = {}
        for row in parse(payload.get("html") or ""):
            groups.setdefault(row["id"], []).append(row)
        return [e for e in (normalize_group(g) for g in groups.values()) if e]


def municipality(place: str) -> tuple[str, str | None]:
    """'Zakrisdalsslingan 2, 653 42 Karlstad, Karlstads kommun' -> ('Zakrisdalsslingan 2, 653 42 Karlstad', 'Karlstad')."""
    m = re.search(r",?\s*([A-ZÅÄÖ][\wåäöé]+) kommun\s*$", place)
    if not m:
        return place, None
    name = m.group(1)
    if name.endswith("s") and name not in S_NAMES:
        name = name[:-1]
    address = re.sub(r"\s+,", ",", place[:m.start()]).strip(" ,")
    return address, name


def parse(page: str) -> list[dict]:
    """Rader i sökresultatet i dokumentordning, var och en med sitt datum."""
    rows = []
    marks = sorted([(m.start(), "day", m) for m in DAY_HEADER.finditer(page)]
                   + [(m.start(), "row", m) for m in ROW.finditer(page)], key=lambda x: x[0])
    day = None
    for _, kind, m in marks:
        if kind == "day":
            try:
                day = date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
            except ValueError:
                day = None
            continue
        if day is None:
            continue
        href, lid, name, start, end, kind_text, place = m.groups()
        address, muni = municipality(clean_text(place))
        start, end = start.zfill(5), end.zfill(5)
        rows.append({
            "id": lid, "url": f"{BASE}/{href}", "title": clean_text(name), "date": day,
            "time_start": start, "time_end": end if end != start else None,
            "kind": clean_text(kind_text or ""), "address": address, "municipality": muni,
        })
    return rows


def normalize_group(rows: list[dict]) -> dict | None:
    first = rows[0]
    kind = first["kind"].lower() or "loppis"
    return finalize({
        "id": f"loppisar-{first['id']}",
        "source": Loppisar.title,
        "title": first["title"],
        "summary": f"{kind.capitalize()} med öppettider enligt loppisar.com. Kontakta gärna loppisen innan du åker långt.",
        "description": "",
        "categories": [category("Marknad, mässa, auktion och loppis")],
        "municipality": first["municipality"],
        "place": {"title": first["title"], "address": first["address"], "lat": None, "lon": None},
        "organizer": None,
        "url": first["url"],
        "booking_link": None,
        "website_link": None,
        "images": [],
        "occasions": [{"date_start": r["date"].isoformat(), "date_end": r["date"].isoformat(),
                       "time_start": r["time_start"], "time_end": r["time_end"]} for r in rows],
    })
