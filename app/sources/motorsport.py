"""Motorsport i Värmland och Karlskoga: SBF:s tävlingskalender (LoTS) och Svemo TA.

Båda är samma tävlingssystem (ASP.NET med en Telerik-lista, inget API). Listan visar 50 tävlingar per sida,
och sidbyten görs med postback (__VIEWSTATE + __EVENTTARGET), precis som i webbläsaren.

- SBF (bilsport): filtret för kommande tävlingar fungerar, så alla sidor läses (cirka 12 anrop).
- Svemo (MC och snöskoter): datumfiltret ignoreras och listan börjar 2012. Därför läses sista sidan och
  sidorna bakåt tills tävlingarna har passerat (cirka 3 anrop).

Listorna saknar län och kommun. Läget avgörs av banans namn (PLACES) och i andra hand arrangörens ort.
Källorna visas som en källa, Motorsport, i gränssnittet.
"""

import html
import re
from datetime import date, timedelta

import httpx

from common import SourceError, category, finalize, get_text, pause, post_form, today

GROUP = "Motorsport"
COLUMNS = "FromDateShort,ToDateShort,Arena,Organizer,Branch,Name,CompetitionStatus,CompetitionInfo"
PAGE_DELAY = 1.5                 # sekunder mellan sidorna
MAX_PAGES = 20
MAX_DAYS = 7                     # längre perioder är träningstillstånd, inte evenemang

# Kommuner som räknas (Värmland och Karlskoga, som Visit Värmland)
MUNICIPALITIES = ["Arvika", "Eda", "Filipstad", "Forshaga", "Grums", "Hagfors", "Hammarö", "Karlstad", "Kil",
                  "Kristinehamn", "Munkfors", "Storfors", "Sunne", "Säffle", "Torsby", "Årjäng", "Karlskoga"]
# Banor och orter (början av ett ord) → kommun
PLACES = {
    "kalvholmen": "Karlstad", "hynboholm": "Karlstad", "molkom": "Karlstad", "tomtfallet": "Munkfors",
    "krokstabanan": "Säffle", "nordmarkens motorstadion": "Årjäng", "hökedal": "Eda", "charlottenberg": "Eda",
    "åmotfors": "Eda", "koppom": "Eda", "finnskoga": "Torsby", "höljes": "Torsby", "östmark": "Torsby",
    "likenäs": "Torsby", "femtåbanan": "Torsby", "sysslebäck": "Torsby", "flottuvebanan": "Filipstad",
    "storfors ring": "Storfors", "hagforsvallen": "Hagfors", "tallhult": "Hagfors", "emtbjörks": "Hagfors",
    "valsarna": "Hagfors", "ekesberget": "Hagfors", "ekshärad": "Hagfors", "elofsrud": "Sunne",
    "tossebergsklätten": "Sunne", "fryksdalens": "Sunne", "lökenebanan": "Kil", "gelleråsen": "Karlskoga",
    "skoghall": "Hammarö", "deje": "Forshaga", "glava": "Arvika", "edane": "Arvika",
    # Byar och tätorter där rallyn och andra tävlingar utgår (rallyn har ofta "Tillfällig" som bana)
    "vitsand": "Torsby", "lekvattnet": "Torsby", "bograngen": "Torsby", "branäs": "Torsby", "stöllet": "Torsby",
    "gräsmark": "Sunne", "rottneros": "Sunne", "lysvik": "Sunne", "nysäter": "Säffle", "svanskog": "Säffle",
    "värmlandsbro": "Säffle", "brunskog": "Arvika", "klässbol": "Arvika", "töcksfors": "Årjäng",
    "vågsäter": "Årjäng", "lesjöfors": "Filipstad", "slottsbron": "Grums", "vålberg": "Karlstad",
    "ransäter": "Munkfors", "uddeholm": "Hagfors", "älvsbacka": "Hagfors", "bjurtjärn": "Storfors",
}
MUNI_RE = re.compile(r"(?<![\wåäö])(" + "|".join(MUNICIPALITIES) + r")s?(?![\wåäö])", re.I)
PLACE_RE = re.compile(r"(?<![\wåäö])(" + "|".join(re.escape(p) for p in PLACES) + r")", re.I)

BRANCH_TEXT = {"Karting": "Karting (gokart)", "Bilorientering": "Bilorientering"}


def municipality(arena: str, organizer: str) -> str | None:
    """Kommunen för en tävling: banan i första hand, annars arrangörens ort. None om den inte är i området."""
    for text in (arena, organizer):
        if m := PLACE_RE.search(text or ""):
            return PLACES[m.group(1).lower()]
        if m := MUNI_RE.search(text or ""):
            return next(x for x in MUNICIPALITIES if x.lower() == m.group(1).lower())
    return None


# ---------------------------------------------------------------- tävlingslistan (gemensam för SBF och Svemo)

def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_rows(page: str) -> list[dict]:
    """Raderna i listan: från, till, arrangör, gren, typ, namn, bana och tävlingens id."""
    rows = []
    for tr in re.findall(r'<tr[^>]*class="rg(?:Alt)?Row[^"]*"[^>]*>(.*?)</tr>', page, re.S):
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        cid = re.search(r"CompetitionId=(\d+)", tr)
        if len(cells) < 7 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
            continue
        rows.append({"from": cells[0], "to": cells[1] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[1]) else cells[0],
                     "organizer": cells[2], "branch": cells[3], "status": cells[4], "name": cells[5],
                     "arena": cells[6], "id": cid.group(1) if cid else ""})
    return rows


def _pages(page: str) -> int:
    m = re.search(r"(\d+) items in (\d+) pages", _text(page))
    return int(m.group(2)) if m else 1


def _postback(page: str, button_title: str) -> dict | None:
    """Formulärdata för att klicka på en knapp i listans sidväljare ("Next Page", "Last Page" …)."""
    button = re.search(r'name="([^"]+)"[^>]*title="' + re.escape(button_title) + '"', page)
    if not button:
        return None
    data = {n: html.unescape(v) for n, v in
            re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page)}
    data.update({"__EVENTTARGET": button.group(1), "__EVENTARGUMENT": ""})
    return data


class _Competitions:
    """Gemensam läsare för tävlingssystemet (LoTS och Svemo TA)."""
    key = title = homepage = base = ""
    group = GROUP
    backwards = False            # Svemo: sista sidan och bakåt

    def config_error(self) -> str | None:
        return None

    @property
    def list_url(self) -> str:
        return f"{self.base}/public/pages/competition/competitions.aspx?Columns={COLUMNS}&Datefilter=Future&pagesize=50"

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        url = self.list_url
        page = await get_text(client, url, self.title)
        if "rgInfoPart" not in page and not parse_rows(page):
            raise SourceError(f"Hittade ingen tävlingslista hos {self.title}, sidans struktur kan ha ändrats")
        rows, pages, total = [], 1, _pages(page)
        first = (today() - timedelta(days=MAX_DAYS)).isoformat()
        if self.backwards and total > 1:
            data = _postback(page, "Last Page")
            if not data:
                raise SourceError(f"Hittade inte sidväljaren hos {self.title}")
            await pause(PAGE_DELAY)
            page = await post_form(client, url, data, self.title)
            pages += 1
        rows += parse_rows(page)
        while pages < min(total, MAX_PAGES):
            if self.backwards and (not rows or min(r["from"] for r in rows) < first):
                break
            data = _postback(page, "Previous Page" if self.backwards else "Next Page")
            if not data:
                break
            await pause(PAGE_DELAY)
            page = await post_form(client, url, data, self.title)
            pages += 1
            rows += parse_rows(page)
        return {"rows": rows}

    # ---- urval och normalisering
    def include(self, row: dict) -> bool:
        return True

    def normalize(self, payload: dict) -> list[dict]:
        events, seen = [], set()
        for row in payload.get("rows") or []:
            key = row["id"] or f"{row['from']}|{row['name']}|{row['organizer']}"
            if key in seen or not self.include(row):
                continue
            seen.add(key)
            if e := self.event(row):
                events.append(e)
        return events

    def event(self, row: dict) -> dict | None:
        muni = municipality(row["arena"], row["organizer"])
        if not muni:
            return None
        try:
            start, end = date.fromisoformat(row["from"]), date.fromisoformat(row["to"])
        except ValueError:
            return None
        if end < start or (end - start).days > MAX_DAYS:
            return None
        branch = BRANCH_TEXT.get(row["branch"], row["branch"])
        kind = self.kind(row["status"])
        name = row["name"] if row["name"] and row["name"].lower() not in ("träning", "tävling") else ""
        # Allmänna namn ("Klubbtävling", "KM") får grenen framför sig
        generic = re.fullmatch(r"(klubb|lokal|distrikts)?tävling|km\s*\d*|klubbmästerskap\w*|deltävling\s*\d*", name, re.I)
        title = (f"{branch} – {name}" if generic else name) or f"{branch} – {row['organizer']}"
        arena = row["arena"] if row["arena"].lower() not in ("tillfällig", "skogen", "") else ""
        summary = f"{branch}" + (f" på {arena}" if arena else "") + (f". {kind}" if kind else "") + "."
        if self.try_it(row["status"]):
            summary += " Prova på: här kan du själv prova på motorsport."
        url = (f"{self.base}/Public/Pages/CompetitionInformation/CompetitionInformation.aspx?CompetitionId={row['id']}"
               if row["id"] else self.homepage)
        return finalize({
            "id": f"{self.key}-{row['id'] or re.sub(r'[^a-z0-9]+', '-', key_of(row))}",
            "source": self.title,
            "title": title,
            "summary": summary,
            "description": f"{summary} Arrangör: {row['organizer']}. Gren: {row['branch']}.",
            "categories": [category("Motorsport")],
            "municipality": muni,
            "place": {"title": arena or muni, "address": "", "lat": None, "lon": None},
            "organizer": row["organizer"],
            "url": url,
            "booking_link": None,
            "website_link": None,
            "images": [],
            "occasions": [{"date_start": start.isoformat(), "date_end": end.isoformat(),
                           "time_start": None, "time_end": None}],
        })

    def kind(self, status: str) -> str:
        return status

    def try_it(self, status: str) -> bool:
        return False


def key_of(row: dict) -> str:
    return f"{row['from']}-{row['name']}-{row['organizer']}".lower()


# ---------------------------------------------------------------- källorna

class SBF(_Competitions):
    """Svensk Bilsport: folkrace, rally, rallycross, crosskart, karting, bilcross, racing, drifting …"""
    key = "sbf"
    title = "Svensk Bilsport (SBF)"
    base = "https://lots.sbf.se"
    homepage = "https://www.sbf.se/tavlingar/tavlingskalender"
    SKIP_BRANCHES = {"Radiostyrd Bilsport", "Drivers Open", "Ticket to drive"}
    EVENT_RE = re.compile(r"tävling|uppvisning|prova bilsport", re.I)

    def include(self, row: dict) -> bool:
        status = row["status"]
        if row["branch"] in self.SKIP_BRANCHES or not self.EVENT_RE.search(status):
            return False
        # "Distriktstävling utan publik" visas bara om det också är prova på
        if re.search(r"utan publik", status, re.I) and not re.search(r"prova bilsport|uppvisning", status, re.I):
            return False
        return True

    def kind(self, status: str) -> str:
        """'D) Distriktstävling (SDF), Prova Bilsport (SDF)' -> 'Distriktstävling'."""
        m = re.search(r"[A-E]\d?\)\s*([^,(]+?)(?:\s*\(|,|$)", status)
        return m.group(1).strip() if m else ""

    def try_it(self, status: str) -> bool:
        return bool(re.search(r"prova bilsport", status, re.I))


class Svemo(_Competitions):
    """Svemo: motocross, enduro, speedway, trial, roadracing, snöskoter …"""
    key = "svemo"
    title = "Svemo"
    base = "https://ta.svemo.se"
    homepage = "https://www.svemo.se"
    backwards = True

    def include(self, row: dict) -> bool:
        return bool(row["status"]) and row["status"].lower() != "träning"

    def kind(self, status: str) -> str:
        return {"Nationell/Internationell": "Nationell tävling"}.get(status, status)
