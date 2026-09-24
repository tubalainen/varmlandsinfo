"""Karlstad CCC: evenemangskalendern på karlstadccc.se (serverrenderad HTML, inget API)."""

import re
from urllib.parse import urljoin

import httpx

from common import SourceError, category, clean_text, finalize, get_text, https_url

BASE = "https://www.karlstadccc.se"
CALENDAR_URL = f"{BASE}/17/38/program-biljetter/"

TAGS = {
    "konsert": "Musik",
    "teater": "Teater och underhållning",
    "show": "Teater och underhållning",
    "ovrigt": "Övriga evenemang",
}


class CCC:
    key = "ccc"
    title = "Karlstad CCC"
    homepage = CALENDAR_URL

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        page = await get_text(client, CALENDAR_URL, self.title)
        if not parse(page):
            raise SourceError(f"Hittade inga evenemang hos {self.title}, sidans struktur kan ha ändrats")
        return {"html": page}

    def normalize(self, payload: dict) -> list[dict]:
        return [e for e in (normalize_item(i) for i in parse(payload.get("html") or "")) if e]


def _time(text: str) -> tuple[str | None, str | None]:
    """'19:30' -> ('19:30', None), '18.00-01.00' -> ('18:00', '01:00')."""
    times = [f"{int(h):02d}:{m}" for h, m in re.findall(r"(\d{1,2})[:.](\d{2})", text or "")]
    return (times[0] if times else None), (times[1] if len(times) > 1 else None)


def parse(page: str) -> list[dict]:
    """Ett kort per evenemang: <div class="card-item ... js-filter-item" data-tags="...">."""
    items = []
    chunks = re.split(r'<div class="card-item[^"]*js-filter-item"', page)[1:]
    for chunk in chunks:
        tags = re.match(r'\s*data-tags="([^"]*)"', chunk)
        chunk = chunk.split('<div class="card-item', 1)[0]
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", (re.search(r'fa-calendar-alt"></i>(.*?)</p>', chunk, re.S)
                                                  or [None, ""])[1])
        if not dates:
            continue
        time_text = (re.search(r'fa-clock"></i>(.*?)</p>', chunk, re.S) or [None, ""])[1]
        img = re.search(r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"', chunk)
        # Rubriken stängs ibland med fel tagg (</p>), därför tolerant matchning och alt-texten som reserv
        heading = re.search(r"<h[1-6][^>]*>(.*?)</(?:h[1-6]|p)>", chunk, re.S)
        title = clean_text(heading.group(1)) if heading else ""
        if not title and img:
            title = clean_text(img.group(2))
        if not title:
            continue
        body = chunk.split("</h3>", 1)[1] if "</h3>" in chunk else ""
        text = clean_text((re.search(r"<p>(.*?)</p>", body, re.S) or [None, ""])[1])
        footer = chunk.split('class="card-footer"', 1)[1] if 'class="card-footer"' in chunk else ""
        links = re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', footer, re.S)
        booking = next((urljoin(BASE, h) for h, label in links if "boka" in clean_text(label).lower()), None)
        more = next((urljoin(BASE, h) for h, label in links if "läs mer" in clean_text(label).lower()), None)
        items.append({
            "title": title, "dates": dates, "time": _time(time_text), "tag": tags.group(1) if tags else "",
            "text": text, "image": urljoin(BASE, img.group(1)) if img else None,
            "booking": booking, "url": more,
        })
    return items


def normalize_item(item: dict) -> dict | None:
    start, end = item["time"]
    url = https_url(item.get("url")) or CALENDAR_URL
    image = https_url(item.get("image"))
    key = re.sub(r"[^a-z0-9]+", "-", (item.get("url") or item["title"]).lower()).strip("-")
    return finalize({
        "id": f"ccc-{key}",
        "source": CCC.title,
        "title": item["title"],
        "summary": item.get("text") or "",
        "description": item.get("text") or "",
        "categories": [category(TAGS.get(item.get("tag"), "Övriga evenemang"))],
        "municipality": "Karlstad",
        "place": {"title": "Karlstad CCC", "address": "", "lat": None, "lon": None},
        "organizer": None,
        "url": url,
        "booking_link": https_url(item.get("booking")),
        "website_link": None,
        "images": [{"small": image, "medium": image, "large": image, "alt": item["title"], "copyright": ""}]
        if image else [],
        "occasions": [{"date_start": d, "date_end": d, "time_start": start, "time_end": end}
                      for d in item["dates"]],
    })
