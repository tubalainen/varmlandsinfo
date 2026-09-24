"""Scalateatern: föreställningslistan på scalateatern.se (WordPress, föreställningarna finns inte i REST-API:et)."""

import asyncio
import re

import httpx

from common import SourceError, category, clean_text, finalize, get_text, https_url, today

BASE = "https://www.scalateatern.se"
LIST_URL = f"{BASE}/forestallningar/"
MAX_PAGES = 15

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}

GENRES = {
    "musik": "Musik",
    "teater": "Teater och underhållning", "revy": "Teater och underhållning",
    "musikal": "Teater och underhållning", "kabaré": "Teater och underhållning",
    "show": "Teater och underhållning", "magi": "Teater och underhållning",
    "humor": "Teater och underhållning", "stand up": "Teater och underhållning",
    "talkshow": "Teater och underhållning",
    "dans": "Dans",
    "barn": "Barn",
    "föreläsning": "Föreläsning och workshop", "litteratur": "Föreläsning och workshop",
    "samhälle": "Föreläsning och workshop", "politik": "Föreläsning och workshop",
    "historia": "Föreläsning och workshop", "poesi": "Föreläsning och workshop",
    "pod": "Föreläsning och workshop", "podcast": "Föreläsning och workshop",
    "konferans": "Föreläsning och workshop",
    "mat": "Mat och dryck", "mingel": "Mat och dryck",
    "träning": "Sport, motion och hälsa",
}


class Scala:
    key = "scala"
    title = "Scalateatern"
    homepage = LIST_URL

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        pages = []
        for n in range(1, MAX_PAGES + 1):
            url = LIST_URL if n == 1 else f"{LIST_URL}page/{n}/"
            try:
                page = await get_text(client, url, self.title)
            except SourceError:
                if n == 1:
                    raise
                break   # sidan finns inte (404): slutet på listan
            if not _items(page):
                break
            pages.append(page)
            if f"/forestallningar/page/{n + 1}" not in page:
                break
            await asyncio.sleep(1)
        if not pages:
            raise SourceError(f"Hittade inga föreställningar hos {self.title}, sidans struktur kan ha ändrats")
        return {"pages": pages}

    def normalize(self, payload: dict) -> list[dict]:
        # Samma föreställning flera dagar blir ett evenemang med flera tillfällen
        groups: dict[str, list[dict]] = {}
        for item in parse(payload.get("pages") or []):
            groups.setdefault(item.get("url") or f"{item['title']}|{item['date']}", []).append(item)
        return [e for e in (normalize_group(g) for g in groups.values()) if e]


def _items(page: str) -> list[str]:
    chunks = page.split('<div class="post-list--item')[1:]
    # Sista posten följs av sidnumrering och sidfot, som inte hör till posten
    if chunks:
        chunks[-1] = re.split(r'load-more|page-numbers|<footer', chunks[-1], 1)[0]
    return chunks


def parse(pages: list[str]) -> list[dict]:
    items = []
    year = today().year
    prev_month = None
    for page in pages:
        for chunk in _items(page):
            day = re.search(r'class="day[^"]*">\s*(\d{1,2})', chunk)
            month = re.search(r'class="month[^"]*">\s*([a-zåäö]+)', chunk, re.I)
            title = re.search(r'class="title[^"]*">\s*<span>(.*?)</span>', chunk, re.S)
            if not (day and month and title) or month.group(1).lower()[:3] not in MONTHS:
                continue
            m = MONTHS[month.group(1).lower()[:3]]
            # Listan är kronologisk utan årtal: nytt år när månaden minskar
            if prev_month is None and m < today().month - 1:
                year += 1
            elif prev_month is not None and m < prev_month:
                year += 1
            prev_month = m
            meta_block = (re.search(r'<div class="meta">(.*?)</div>', chunk, re.S) or [None, ""])[1]
            meta = [clean_text(x) for x in re.findall(r'<span class="d-inline-block[^"]*">(.*?)</span>', meta_block, re.S)]
            time = next((x for x in meta if re.fullmatch(r"\d{1,2}[:.]\d{2}", x)), None)
            terms = [x for x in meta if x != time]
            links = re.findall(r'href="([^"]+)"', chunk)
            url = next((h for h in links if "/forestallning/" in h), None)
            booking = next((h for h in links if h.startswith("http") and "/forestallning" not in h
                            and "scalateatern.se/forestallningar" not in h), None)
            img = re.search(r'<img[^>]*src="([^"]+)"', chunk)
            thumb = image = None
            if img:
                thumb = img.group(1) if img.group(1).startswith("http") else BASE + img.group(1)
                image = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", thumb)   # originalbilden (stor) för förstoring
            items.append({
                "title": clean_text(title.group(1)),
                "date": f"{year}-{m:02d}-{int(day.group(1)):02d}",
                "time": time.replace(".", ":").zfill(5) if time else None,
                "stage": terms[0] if terms else None,
                "genres": [g.strip() for t in terms[1:] for g in t.split(",") if g.strip()],
                "badges": [clean_text(b) for b in re.findall(r'<span class="badge[^"]*">(.*?)</span>', chunk, re.S)],
                "url": url, "booking": booking, "thumb": thumb, "image": image,
            })
    return items


def normalize_group(items: list[dict]) -> dict | None:
    item = items[0]
    cats = []
    for g in item.get("genres") or []:
        title = GENRES.get(g.lower())
        if title and title not in cats:
            cats.append(title)
    stage = item.get("stage")
    genres = ", ".join(item.get("genres") or []).lower()
    summary = f"{genres.capitalize() or 'Föreställning'} på Scalateatern" + (f", {stage}" if stage else "") + "."
    if item.get("badges"):
        summary += " " + ". ".join(item["badges"]) + "."
    url = https_url(item.get("url")) or LIST_URL
    image, thumb = https_url(item.get("image")), https_url(item.get("thumb"))
    key = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")
    return finalize({
        "id": f"scala-{key}",
        "source": Scala.title,
        "title": item["title"],
        "summary": summary,
        "description": "",
        "categories": [category(c) for c in cats or ["Teater och underhållning"]],
        "municipality": "Karlstad",
        "place": {"title": f"Scalateatern{', ' + stage if stage else ''}", "address": "", "lat": None, "lon": None},
        "organizer": None,
        "url": url,
        "booking_link": https_url(item.get("booking")),
        "website_link": None,
        # Miniatyren (160 px) i listan, originalet (ofta runt 1 MB) bara vid förstoring
        "images": [{"small": thumb or image, "medium": thumb or image, "large": image or thumb,
                    "alt": item["title"], "copyright": ""}] if image or thumb else [],
        "occasions": [{"date_start": i["date"], "date_end": i["date"], "time_start": i.get("time"), "time_end": None}
                      for i in items],
    })
