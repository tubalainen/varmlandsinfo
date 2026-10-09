"""Handboll i Värmland: Svenska Handbollförbundets matcher i Profixio (seniorer, herr och dam, #82).

Värmland hör till Handbollförbundet Väst. Med kommer de nationella seniorserierna (Handbollsligan, Allsvenskan,
Dam/Herr 1, Svenska cupen) och Väst-serierna Dam/Herr 2–4, men inte ungdom, motion, para eller landslag.

De flesta serierna har bara något enstaka lag från Värmland (t.ex. IFK Hammarö bland 23 lag i Herr 3 Väst), så i
stället för hela seriers spelscheman hämtas lagens egna sidor:
- En gång i veckan: tävlingslistan och första sidan av varje seniorserie, för att hitta lagen från Värmland (ort i
  lagnamnet eller en känd klubb). Lagen sparas i källans data.
- Varje gång: lagsidan och lagets kommande matcher (Livewire-komponenten lx.team.schedule, 15 matcher), 2 anrop per
  lag med paus emellan.

Bara matcher som spelas i Värmland (eller Karlskoga) tas med: arenan avgör kommunen, och i andra hand hemmalaget.
"""

import re
from datetime import date, datetime, timedelta

import httpx

from common import TZ, SourceError, category, finalize, get_text, pause, today
from kommuner import KOMMUNER, kommun
from sources.profixio import (BASE, HEADERS, lazy_component, load_lazy, parse_checked, parse_leagues,
                              parse_team_links)

COMPETITIONS_URL = f"{BASE}/lx/SHF?t=competitions"
PAGE_DELAY = 2                   # sekunder mellan anropen
DISCOVER_DAYS = 7                # så ofta serierna och deras lag gås igenom

# Seniorserier: nationella serier och cuper, och Handbollförbundet Västs serier (dit Värmland hör)
SENIOR_RE = re.compile(r"^(Damer|Herrar) - (Handbollsligan (dam|herr)|Damallsvenskan|Herrallsvenskan|Dam 1|Herr 1"
                       r"|Svenska cupen \d{4}-\d{4}|(Dam|Herr) [234] Väst)$", re.I)
YOUTH_RE = re.compile(r"(?<![\wåäö])[UFPJ]\d{1,2}(?!\d)|flick|pojk|junior|ungdom|akademi", re.I)
# Klubbar i Värmland utan ort i namnet (början av ett ord) → kommun
CLUBS = {"hellton": "Karlstad", "brukspôjkera": "Forshaga", "brukspöjkera": "Forshaga"}
CLUB_RE = re.compile(r"(?<![\wåäö])(" + "|".join(CLUBS) + r")", re.I)


def senior_league(name: str) -> bool:
    return bool(SENIOR_RE.search(name or ""))


def youth(team: str) -> bool:
    return bool(YOUTH_RE.search(team or ""))


def team_municipality(team: str | None) -> str | None:
    """Kommunen för ett lag från Värmland: en känd klubb eller en ort i lagnamnet ("IFK Hammarö")."""
    if m := CLUB_RE.search(team or ""):
        return CLUBS[m.group(1).lower()]
    return kommun(team)


def municipality(arena: str | None, home: str | None) -> str | None:
    """Kommunen för en match: arenan i första hand ("Hammarhallen A, Hammarö"), annars hemmalaget."""
    return kommun(arena) or team_municipality(home)


def league_name(name: str) -> str:
    """"Herrar - Herr 3 Väst" -> "Herr 3 Väst", "Damer - Svenska cupen 2026-2027" -> "Svenska cupen (damer)"."""
    group, _, rest = (name or "").partition(" - ")
    if rest.lower().startswith("svenska cupen"):
        return f"Svenska cupen ({group.lower()})"
    return rest or name


class Handboll:
    key = "handboll"
    title = "Handboll"
    homepage = f"{BASE}/lx/SHF"

    def config_error(self) -> str | None:
        return None

    async def _discover(self, client: httpx.AsyncClient) -> list[dict]:
        """Lagen från Värmland i seniorserierna (seriens första sida har alla lag)."""
        listing = await get_text(client, COMPETITIONS_URL, self.title, HEADERS)
        leagues = [x for x in parse_leagues(listing) if senior_league(x["name"])]
        if not leagues:
            raise SourceError(f"Hittade inga serier hos {self.title}, sidans struktur kan ha ändrats")
        teams = []
        for league in leagues:
            await pause(PAGE_DELAY)
            page = await get_text(client, f"{BASE}/lx/competition/leagueid{league['id']}?t=schedule", self.title,
                                  HEADERS)
            for t in parse_team_links(page):
                if not youth(t["name"]) and team_municipality(t["name"]):
                    teams.append({**t, "league_id": league["id"], "league": league["name"]})
        return teams

    async def _team_matches(self, client: httpx.AsyncClient, team: dict) -> list[dict]:
        """Lagets kommande matcher: lagsidan och sedan komponenten med schemat."""
        url = f"{BASE}/lx/competition/leagueid{team['league_id']}/teams/{team['id']}"
        await pause(PAGE_DELAY)
        page = await get_text(client, url, self.title, HEADERS)
        component = lazy_component(page, "lx.team.schedule")
        if not component:
            raise SourceError(f"Hittade inte lagets matcher hos {self.title}, sidans struktur kan ha ändrats")
        await pause(PAGE_DELAY)
        return parse_checked(await load_lazy(client, page, url, component, self.title), self.title)

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        prev = previous or {}
        checked = prev.get("discovered")
        fresh = checked and today() - date.fromisoformat(checked) < timedelta(days=DISCOVER_DAYS)
        if fresh and "teams" in prev:
            teams, discovered = prev["teams"], checked
        else:
            teams, discovered = await self._discover(client), today().isoformat()
        matches = []
        for team in teams:
            for m in await self._team_matches(client, team):
                matches.append({**m, "league": team["league"]})
        return {"discovered": discovered, "teams": teams, "matches": matches}

    def normalize(self, payload: dict) -> list[dict]:
        events, seen = [], set()
        for m in payload.get("matches") or []:
            if m["id"] in seen:              # två värmländska lag möts: matchen finns hos båda
                continue
            seen.add(m["id"])
            if e := normalize_match(m):
                events.append(e)
        return events


def normalize_match(m: dict) -> dict | None:
    if youth(m["home"]) or youth(m["away"]):
        return None
    muni = municipality(m.get("arena"), m["home"])
    if muni not in KOMMUNER:
        return None                          # bortamatch utanför Värmland
    start = datetime.fromtimestamp(m["kickoff"], TZ)
    arena = m.get("arena")
    where = f" i {arena}" if arena else ""
    rnd = f", omgång {m['round']}" if m.get("round") else ""
    return finalize({
        "id": f"handboll-{m['id']}",
        "source": Handboll.title,
        "title": f"{m['home']} - {m['away']}",
        "summary": f"Handboll, {league_name(m.get('league') or '')}{rnd}: {m['home']} tar emot {m['away']}{where}.",
        "description": "",
        "categories": [category("Sport, motion och hälsa"), category("Handboll")],
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
