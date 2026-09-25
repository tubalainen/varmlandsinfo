"""Great Event of Karlstad: sidan Kommande evenemang på greateventofkarlstad.se (WordPress med Elementor, inget API).

Varje evenemang är ett eget block med en datumrad ("Fre 23 oktober 2026 | Löfbergs Arena, Karlstad"), en rubrik,
en ingress, en "Läs mer"-text, en bild och knappar som "Köp biljetter".
"""

import re
from datetime import date

import httpx

from common import SourceError, category, clean_text, finalize, get_text, https_url, strip_html, today

BASE = "https://www.greateventofkarlstad.se"
LIST_URL = f"{BASE}/kommande-evenemang/"

MONTHS = {name: i for i, name in enumerate(
    ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
     "november", "december"], start=1)}
WEEKDAY = r"(?:mån|tis|ons|tors|fre|lör|sön)\w*"

# "Fre 23 oktober", "19-20 februari", "6/11": dag (eller dagar) och månad
DATE_TOKEN = re.compile(r"(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?(?:\s+(" + "|".join(MONTHS) + r")|/(\d{1,2}))", re.I)
YEAR = re.compile(r"\b(20\d{2})\b")
# Datumraden: "<datum> <år> | <plats>, <ort>"
DATE_LINE = re.compile(r"<p[^>]*>\s*([^<|]{0,120}?\b20\d{2})\s*\|\s*([^<]+?)\s*</p>")
# Egen rad per datum i Läs mer-texten: "Fredag 6/11, Daniel Lemma" följd av ett stycke om artisten
SUB_ITEM = re.compile(r"<p[^>]*>\s*<strong>\s*" + WEEKDAY + r"\s+(\d{1,2})/(\d{1,2}),\s*([^<]+?)\s*</strong>\s*</p>\s*<p[^>]*>(.*?)</p>",
                      re.I | re.S)

# Evenemangstyp utifrån ord i titel (väger tre gånger) och text
TYPES = [
    ("Musik", r"konsert|spelning|turné|musik|album|låtar|orchestra|orkester|sång|live music|band\b"),
    ("Teater och underhållning", r"föreställning|show\b|humor|skratt|stand-?up|komik|revy|teater|musikal"),
    ("Mat och dryck", r"\bvin\b|vinfest|\bdeli\b|middag|provning|bbq|barbecue|\bmat\b"),
    ("Marknad, mässa och auktion", r"\bmässa|marknad"),
]


class GreatEvent:
    key = "greatevent"
    title = "Great Event"
    homepage = LIST_URL

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        page = await get_text(client, LIST_URL, self.title)
        if not parse(page):
            raise SourceError(f"Hittade inga evenemang hos {self.title}, sidans struktur kan ha ändrats")
        return {"html": page}

    def normalize(self, payload: dict) -> list[dict]:
        return [e for e in (normalize_item(i) for i in parse(payload.get("html") or "")) if e]


def _year_for(month: int, day: int, year: int | None) -> int:
    """Årtalet när det saknas: i år, eller nästa år om datumet redan har passerat."""
    if year:
        return year
    t = today()
    return t.year + (1 if (month, day) < (t.month, t.day) else 0)


def parse_dates(text: str) -> list[tuple[date, date]]:
    """Datumdelen av datumraden som tillfällen (från, till).

    "Fre 23 oktober 2026" -> en dag, "Fre-lör 19-20 februari 2027" -> två dagar i följd,
    "6/11, 20/11, 8/12 2026" -> tre dagar, "30 januari – 2 februari 2027" -> fyra dagar i följd.
    """
    years = [(m.start(), int(m.group(1))) for m in YEAR.finditer(text)]
    tokens = []
    for m in DATE_TOKEN.finditer(text):
        if YEAR.fullmatch(m.group(0)):
            continue
        month = MONTHS[m.group(3).lower()] if m.group(3) else int(m.group(4))
        if not 1 <= month <= 12:
            continue
        year = next((y for pos, y in years if pos >= m.end()), years[-1][1] if years else None)
        d1, d2 = int(m.group(1)), int(m.group(2) or m.group(1))
        try:
            y = _year_for(month, d1, year)
            tokens.append((m.start(), m.end(), date(y, month, d1), date(y, month, d2)))
        except ValueError:
            continue
    result = []
    i = 0
    while i < len(tokens):
        start, end_pos, lo, hi = tokens[i]
        # "30 januari – 2 februari": två datum med bindestreck emellan är en period
        if i + 1 < len(tokens) and re.fullmatch(r"\s*[-–]\s*", text[end_pos:tokens[i + 1][0]]):
            hi = tokens[i + 1][3]
            i += 1
        if hi >= lo:
            result.append((lo, hi))
        i += 1
    return result


def _blocks(page: str) -> list[str]:
    """Varje evenemang är en egen Elementor-behållare på översta nivån."""
    blocks = page.split('e-con-boxed e-con e-parent"')[1:]
    if blocks:
        blocks[-1] = re.split(r"<footer", blocks[-1], 1)[0]   # sidfoten hör inte till sista evenemanget
    return blocks


def _text(fragment: str | None) -> str:
    """Text ur HTML, utan blanksteg före skiljetecken ("<em>Bara vi</em>." ska inte bli "Bara vi .")."""
    return re.sub(r"\s+([.,!?:;])", r"\1", clean_text(fragment))


def _guess_type(title: str, text: str) -> str:
    best, score = "Övriga evenemang", 0
    for name, pattern in TYPES:
        s = 3 * len(re.findall(pattern, title, re.I)) + len(re.findall(pattern, text, re.I))
        if s > score:
            best, score = name, s
    return best


def parse(page: str) -> list[dict]:
    items = []
    for block in _blocks(page):
        line = DATE_LINE.search(block)
        heading = re.search(r"<h[1-6][^>]*elementor-heading-title[^>]*>(.*?)</h[1-6]>", block, re.S)
        if not line or not heading:
            continue
        title = clean_text(heading.group(1))
        dates = parse_dates(clean_text(line.group(1)))
        if not title or not dates:
            continue
        where = [p.strip() for p in clean_text(line.group(2)).split(",") if p.strip()]
        after = block[heading.end():]
        intro = re.split(r"elementor-toggle|elementor-button", after, 1)[0]   # ingressen står före Läs mer och knapparna
        summary = _text((re.search(r"<p[^>]*>(.*?)</p>", intro, re.S) or [None, ""])[1])
        more = (re.search(r'class="elementor-tab-content[^"]*"[^>]*>(.*?)</div>', after, re.S) or [None, ""])[1]
        buttons = [(h.replace("&#038;", "&"), clean_text(label)) for h, label in
                   re.findall(r'<a class="elementor-button[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)]
        booking = next((h for h, label in buttons if "biljett" in label.lower()), buttons[0][0] if buttons else None)
        img = re.search(r'<img[^>]*src="([^"]+/wp-content/uploads/[^"]+)"[^>]*?(?:alt="([^"]*)")?', block)
        item = {
            "title": title, "dates": dates, "place": ", ".join(where[:-1]) or (where[0] if where else ""),
            "municipality": where[-1] if len(where) > 1 else "Karlstad",
            "summary": summary, "description": strip_html(more), "booking": booking,
            "image": img.group(1) if img else None,
        }

        # Ett evenemang per datum och artist när Läs mer-texten har egna rader per datum
        subs = []
        year = dates[0][0].year
        for d, m, artist, text in SUB_ITEM.findall(more):
            try:
                y = year + 1 if int(m) < dates[0][0].month else year
                day = date(y, int(m), int(d))
            except ValueError:
                continue
            subs.append({**item, "title": f"{title}: {clean_text(artist)}", "dates": [(day, day)],
                         "summary": _text(text), "description": _text(text) + ("\n\n" + summary if summary else "")})
        if subs:
            covered = {s["dates"][0][0] for s in subs}
            rest = [(lo, hi) for lo, hi in dates if lo not in covered]
            items.extend(subs)
            if rest:
                items.append({**item, "dates": rest})
        else:
            items.append(item)
    return items


def normalize_item(item: dict) -> dict | None:
    image = https_url(item.get("image"))
    first = item["dates"][0][0].isoformat()
    key = re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")
    return finalize({
        "id": f"greatevent-{key}-{first}",
        "source": GreatEvent.title,
        "title": item["title"],
        "summary": item.get("summary") or "",
        "description": item.get("description") or item.get("summary") or "",
        "categories": [category(_guess_type(item["title"], f"{item.get('summary')} {item.get('description')}"))],
        "municipality": item.get("municipality") or "Karlstad",
        "place": {"title": item.get("place") or "", "address": "", "lat": None, "lon": None},
        "organizer": "Great Event",
        "url": LIST_URL,
        "booking_link": https_url(item.get("booking")),
        "website_link": None,
        "images": [{"small": image, "medium": image, "large": image, "alt": item["title"], "copyright": ""}]
        if image else [],
        "occasions": [{"date_start": lo.isoformat(), "date_end": hi.isoformat(), "time_start": None, "time_end": None}
                      for lo, hi in item["dates"]],
    })
