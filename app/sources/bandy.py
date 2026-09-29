"""Bandy i Värmland: Svenska Bandyförbundets matcher i Profixio (seniorer, även träningsmatcher).

Bandy spelas på is med skridskor och är inte innebandy. Källan har bara bandy.

Profixio har ett API, men det kräver en nyckel, så de publika sidorna läses (tolkningen finns i profixio.py):
- Tävlingslistan (/lx/SBF?t=competitions) har säsongens alla serier med namn och id.
- En series spelschema (/lx/competition/leagueid<id>?t=schedule) visar 25 kommande matcher och serien lag.
  Nästa 25 laddas med ett Livewire-anrop (__lazyLoad), precis som när man scrollar i webbläsaren.

För att vara snäll mot Profixio görs två sorters hämtning:
- En gång i veckan: tävlingslistan och första sidan av varje seniorserie, för att se vilka serier som har lag
  från Värmland (lagets ort). Resultatet sparas i källans data.
- Varje gång: bara de serierna, bara kommande matcher.

Matcherna har ingen kommun. Läget avgörs av arenan och i andra hand hemmalagets namn (PLACES och kommunerna, som
för motorsporten). Ungdomslag (U17, F15 …) räknas inte.
"""

import asyncio
import re
from datetime import date, datetime, timedelta

import httpx

from common import TZ, SourceError, category, finalize, get_text, today
from sources.motorsport import MUNICIPALITIES, municipality as motor_municipality
from sources.profixio import (BASE, HEADERS, load_lazy, next_page, parse_checked, parse_leagues,  # noqa: F401
                              parse_matches, parse_teams)

COMPETITIONS_URL = f"{BASE}/lx/SBF?t=competitions"
PAGE_DELAY = 2                   # sekunder mellan anropen
MAX_PAGES = 12                   # sidor à 25 matcher per serie
DISCOVER_DAYS = 7                # så ofta serierna och deras lag gås igenom

# Seniorserier: nationella serier och cuper, och distrikt Mellansveriges serier och träningsmatcher (Värmland hör
# till Mellansverige). Ungdom, junior och andra distrikt räknas inte.
SENIOR_RE = re.compile(r"^(Elitserien|Bandyallsvenskan|Division \d|Svenska Cupen (Herr|Dam)|(Allsvenska |Ettan )?Supercup"
                       r"|Träningsmatcher (Herr|Dam|Mellansverige))", re.I)
OTHER_DISTRICT_RE = re.compile(r"\b(Stockholm|Småland|Sydväst|Västergötland|Nord)\b", re.I)
YOUTH_RE = re.compile(r"(?<![\wåäö])[UFPJ]\d{1,2}(?!\d)|flick|pojk|junior|ungdom", re.I)

# Arenor och klubbar (början av ett ord) → kommun, utöver motorsportens orter och kommunerna
PLACES = {"tingvalla": "Karlstad", "boltic": "Karlstad", "västerstrand": "Karlstad", "slottsbron": "Grums"}
PLACE_RE = re.compile(r"(?<![\wåäö])(" + "|".join(PLACES) + r")", re.I)


def municipality(arena: str | None, home: str | None) -> str | None:
    """Kommunen för en match: arenan i första hand, annars hemmalagets namn. None om den inte är i Värmland."""
    for text in (arena, home):
        if m := PLACE_RE.search(text or ""):
            return PLACES[m.group(1).lower()]
        if muni := motor_municipality(text or "", ""):
            return muni
    return None


def senior_league(name: str) -> bool:
    return bool(SENIOR_RE.search(name)) and not OTHER_DISTRICT_RE.search(name)


def youth(team: str) -> bool:
    return bool(YOUTH_RE.search(team or ""))


# ---------------------------------------------------------------- källan

class Bandy:
    key = "bandy"
    title = "Bandy"
    homepage = "https://www.profixio.com/app/lx/SBF"

    def config_error(self) -> str | None:
        return None

    async def _schedule(self, client: httpx.AsyncClient, league: dict, page: str | None = None) -> list[dict]:
        """Alla kommande matcher i en serie: första sidan och sedan nästa sida tills listan är slut."""
        url = f"{BASE}/lx/competition/leagueid{league['id']}?t=schedule"
        if page is None:
            await asyncio.sleep(PAGE_DELAY)
            page = await get_text(client, url, self.title, HEADERS)
        matches = parse_checked(page, self.title)
        first = page                     # csrf-token och Livewire-adressen finns bara på första sidan
        for _ in range(MAX_PAGES - 1):
            nxt = next_page(page)
            if not nxt:
                break
            await asyncio.sleep(PAGE_DELAY)
            page = await load_lazy(client, first, url, nxt, self.title)
            found = parse_checked(page, self.title)
            if not found:
                break
            matches += found
        return matches

    async def _discover(self, client: httpx.AsyncClient) -> tuple[list[dict], dict[str, str]]:
        """Seniorserierna med lag från Värmland, och första sidan av deras spelschema (för att slippa hämta den igen)."""
        listing = await get_text(client, COMPETITIONS_URL, self.title, HEADERS)
        leagues = [x for x in parse_leagues(listing) if senior_league(x["name"])]
        if not leagues:
            raise SourceError(f"Hittade inga serier hos {self.title}, sidans struktur kan ha ändrats")
        found, first_pages = [], {}
        for league in leagues:
            await asyncio.sleep(PAGE_DELAY)
            page = await get_text(client, f"{BASE}/lx/competition/leagueid{league['id']}?t=schedule", self.title, HEADERS)
            teams = [t for t in parse_teams(page) if not youth(t) and municipality(None, t)]
            arenas = any(municipality(m["arena"], None) for m in parse_checked(page, self.title))
            if teams or arenas:
                found.append({**league, "teams": teams})
                first_pages[league["id"]] = page
        return found, first_pages

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        prev = previous or {}
        checked = prev.get("discovered")
        fresh = checked and today() - date.fromisoformat(checked) < timedelta(days=DISCOVER_DAYS)
        if fresh and "leagues" in prev:
            leagues, first_pages, discovered = prev["leagues"], {}, checked
        else:
            (leagues, first_pages), discovered = await self._discover(client), today().isoformat()
        matches = []
        for league in leagues:
            for m in await self._schedule(client, league, first_pages.get(league["id"])):
                matches.append({**m, "league": league["name"]})
        return {"discovered": discovered, "leagues": leagues, "matches": matches}

    def normalize(self, payload: dict) -> list[dict]:
        events, seen = [], set()
        for m in payload.get("matches") or []:
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            if e := normalize_match(m):
                events.append(e)
        return events


def normalize_match(m: dict) -> dict | None:
    if youth(m["home"]) or youth(m["away"]):
        return None
    muni = municipality(m.get("arena"), m["home"])
    if muni not in MUNICIPALITIES:
        return None
    start = datetime.fromtimestamp(m["kickoff"], TZ)
    league = m.get("league") or ""
    training = league.lower().startswith("träningsmatch")
    arena = m.get("arena")
    where = f" på {arena}" if arena else ""
    if training:
        summary = f"Träningsmatch i bandy: {m['home']} möter {m['away']}{where}."
    else:
        rnd = f", omgång {m['round']}" if m.get("round") else ""
        summary = f"{league}{rnd}: {m['home']} tar emot {m['away']}{where}."
    return finalize({
        "id": f"bandy-{m['id']}",
        "source": Bandy.title,
        "title": f"{m['home']} - {m['away']}",
        "summary": summary,
        "description": "",
        "categories": [category("Sport, motion och hälsa"), category("Bandy")],
        "municipality": muni,
        "place": {"title": arena or muni, "address": "", "lat": None, "lon": None},
        "organizer": m["home"],
        "url": f"{BASE}/lx/match/{m['id']}",
        "booking_link": None,
        "website_link": None,
        "images": [],
        "occasions": [{"date_start": start.date().isoformat(), "date_end": start.date().isoformat(),
                       "time_start": start.strftime("%H:%M"), "time_end": None}],
    })
