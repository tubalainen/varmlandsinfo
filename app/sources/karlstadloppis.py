"""Karlstad Loppis: bakluckeloppisen på I2 Norra Fältet i Karlstad (karlstadloppis.se, inget API).

Startsidan visar bara nästa datum ("Nästa loppis Söndag 27 september"). Tider och plats är fasta enligt
arrangörens besöksinformation: söndagar 10–15 på Norra Fältet, Infanterigatan 14. Utanför säsongen står
inget datum, och då ger källan inga evenemang.
"""

import html
import re
from datetime import date

import httpx

from common import SourceError, category, finalize, get_text, today

URL = "https://karlstadloppis.se/"
INFO_URL = "https://karlstadloppis.se/bakluckeloppis-norra-f%C3%A4ltet-karlstad/bes%C3%B6kare-info-36071161"
TITLE = "Bakluckeloppis I2 Norra Fältet"
TIME_START, TIME_END = "10:00", "15:00"

MONTHS = {name: i for i, name in enumerate(
    ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
     "november", "december"], start=1)}
NEXT = re.compile(r"Nästa loppis\s*(?:(?:mån|tis|ons|tors|fre|lör|sön)\w*\s+)?(\d{1,2})\s+(" + "|".join(MONTHS)
                  + r")(?:\s+(\d{4}))?", re.I)


class KarlstadLoppis:
    key = "karlstadloppis"
    title = "Karlstad Loppis"
    homepage = URL

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        page = await get_text(client, URL, self.title)
        if "loppis" not in page.lower():
            raise SourceError(f"{self.title} svarade med en oväntad sida, dess struktur kan ha ändrats")
        return {"html": page}

    def normalize(self, payload: dict) -> list[dict]:
        day = next_date(payload.get("html") or "")
        return [e for e in [event(day)] if e] if day else []


def _text(page: str) -> str:
    page = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))


def next_date(page: str) -> date | None:
    """Datumet efter "Nästa loppis". Utan årtal: i år, eller nästa år om datumet redan har passerat."""
    m = NEXT.search(_text(page))
    if not m:
        return None
    day, month = int(m.group(1)), MONTHS[m.group(2).lower()]
    t = today()
    year = int(m.group(3)) if m.group(3) else t.year + (1 if (month, day) < (t.month, t.day) else 0)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def event(day: date) -> dict | None:
    return finalize({
        "id": "karlstadloppis-bakluckeloppis",
        "source": KarlstadLoppis.title,
        "title": TITLE,
        "summary": "Värmlands största bakluckeloppis på Norra Fältet i Karlstad. Fri entré och fri parkering, "
                   "och på området finns en kiosk.",
        "description": "Drive-in för säljare: ingen förbokning, kom mellan kl. 8 och 10 och betala vid incheckningen. "
                       "Mer information och priser för säljare finns hos Karlstad Loppis.",
        "categories": [category("Marknad, mässa, auktion och loppis"), category("Gratis")],
        "municipality": "Karlstad",
        "place": {"title": "I2 Norra Fältet", "address": "Infanterigatan 14, 653 40 Karlstad",
                  "lat": 59.3937, "lon": 13.4923},
        "organizer": "Karlstad Loppis AB",
        "url": URL,
        "booking_link": None,
        "website_link": INFO_URL,
        "images": [],
        "occasions": [{"date_start": day.isoformat(), "date_end": day.isoformat(),
                       "time_start": TIME_START, "time_end": TIME_END}],
    })
