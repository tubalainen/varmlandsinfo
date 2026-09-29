"""Gemensamt för källorna i Profixio (bandy och handboll): tolkning av de publika sidorna och Livewire-anrop.

Profixio har ett API, men det kräver en nyckel. De publika sidorna är serverrenderade (Laravel Livewire):
- Tävlingslistan (/lx/<förbund>?t=competitions) har säsongens alla serier med namn och id.
- En series spelschema (/lx/competition/leagueid<id>?t=schedule) visar 25 kommande matcher och seriens lag.
- Delar av en sida laddas med ett Livewire-anrop (__lazyLoad), precis som i webbläsaren: nästa 25 matcher i en
  serie (komponenten infinite-scroll-next-page) och ett lags kommande matcher (lx.team.schedule).
"""

import html
import json
import re

import httpx

from common import SourceError, post_json

BASE = "https://www.profixio.com/app"
# Profixio väljer språk efter besökaren (svenska från Sverige, annars ofta engelska). Svenska begärs alltid, och
# tolkningen klarar båda.
HEADERS = {"Accept-Language": "sv"}


def _lines(fragment: str) -> list[str]:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", fragment, flags=re.S)
    return [x for x in (re.sub(r"\s+", " ", html.unescape(s)).strip() for s in re.split(r"<[^>]+>", text)) if x]


def parse_leagues(page: str) -> list[dict]:
    """Serierna i tävlingslistan: id och namn."""
    leagues, seen = [], set()
    for lid, name in re.findall(r'href="[^"]*/lx/competition/leagueid(\d+)[^"]*"[^>]*>(.*?)</a>', page, re.S):
        name = " ".join(_lines(name))
        if lid not in seen and name:
            seen.add(lid)
            leagues.append({"id": lid, "name": name})
    return leagues


def parse_teams(page: str) -> list[str]:
    """Seriens lag (länkarna till lagens sidor)."""
    names = {" ".join(_lines(n)) for n in re.findall(r'/teams/\d+"[^>]*>(.*?)</a>', page, re.S)}
    return sorted(n for n in names if n)


def parse_team_links(page: str) -> list[dict]:
    """Seriens lag med id: [{"id": "1577172", "name": "IFK Hammarö"}]."""
    teams, seen = [], set()
    for tid, name in re.findall(r'/teams/(\d+)"[^>]*>(.*?)</a>', page, re.S):
        name = " ".join(_lines(name))
        if tid not in seen and name:
            seen.add(tid)
            teams.append({"id": tid, "name": name})
    return teams


# Raden med datum och tid: "16 okt • 19:00" (svenska) eller "Oct 16 • 19:00" (engelska). Tiden tas ur tidsstämpeln.
DATE_LINE = re.compile(r"•\s*\d{1,2}[:.]\d{2}$")
ROUND_RE = re.compile(r"^(?:Omgång|Runde|Round)\s+(\d+)$", re.I)


def parse_matches(page: str) -> list[dict]:
    """Matcherna på en sida: id, avspark (Unix-tid), arena, lag och omgång."""
    matches = []
    parts = re.split(r"\$store\.matches\.registerMatch\(", page)
    for part in parts[1:]:
        head = re.match(r"\s*(\d+),\s*'[^']*',\s*\{(.*?)\}\s*\)", part, re.S)
        if not head:
            continue
        kickoff = re.search(r"kickoff:\s*(\d+)", head.group(2))
        block = part[part.find("mc_mini_"):] if "mc_mini_" in part else part
        arena = re.search(r'/facility/\d+"\s*>\s*(.*?)\s*</a>', block, re.S)
        lines = _lines(block[block.find(">") + 1:])
        i = next((n for n, x in enumerate(lines) if DATE_LINE.search(x)), None)
        if not kickoff or i is None or len(lines) < i + 5 or lines[i + 2] != "-":
            continue
        rnd = next((m.group(1) for m in map(ROUND_RE.match, lines[:i]) if m), None)
        matches.append({"id": head.group(1), "kickoff": int(kickoff.group(1)),
                        "arena": " ".join(_lines(arena.group(1))) if arena else None,
                        "home": lines[i + 1], "away": lines[i + 4], "round": rnd})
    return matches


def parse_checked(page: str, source: str) -> list[dict]:
    """parse_matches, men ett tydligt fel när sidan har matcher som inte går att tolka (i stället för 0 matcher)."""
    matches = parse_matches(page)
    if not matches and "registerMatch(" in page:
        raise SourceError(f"Kunde inte tolka matcherna hos {source}, sidans struktur kan ha ändrats")
    return matches


def lazy_component(page: str, name: str) -> tuple[str, str] | None:
    """Livewire-komponenten `name` som laddas i efterhand: dess snapshot och parametern till __lazyLoad."""
    for m in re.finditer(r'wire:snapshot="([^"]*)"', page):
        snapshot = html.unescape(m.group(1))
        try:
            if json.loads(snapshot)["memo"]["name"] != name:
                continue
        except (ValueError, KeyError):
            continue
        lazy = re.search(r"__lazyLoad\(&#039;([A-Za-z0-9+/=]+)&#039;\)", page[m.end():m.end() + 20000])
        if lazy:
            return snapshot, lazy.group(1)
    return None


def next_page(page: str) -> tuple[str, str] | None:
    """Komponenten som laddar nästa sida i en series spelschema."""
    return lazy_component(page, "infinite-scroll-next-page")


async def load_lazy(client: httpx.AsyncClient, page: str, url: str, component: tuple[str, str], source: str) -> str:
    """HTML:en för en komponent som laddas i efterhand (samma anrop som webbläsaren gör, med sidans csrf-token)."""
    token = re.search(r'name="csrf-token" content="([^"]+)"', page)
    update = re.search(r'data-update-uri="([^"]+)"', page)
    if not (token and update):
        raise SourceError(f"Hittade inte Livewire-uppgifterna hos {source}, sidans struktur kan ha ändrats")
    snapshot, param = component
    data = await post_json(client, update.group(1), {"_token": token.group(1), "components": [
        {"snapshot": snapshot, "updates": {}, "calls": [{"path": "", "method": "__lazyLoad", "params": [param]}]}]},
        source, headers={"X-Livewire": "1", "Referer": url, **HEADERS})
    try:
        return data["components"][0]["effects"]["html"]
    except (KeyError, IndexError, TypeError):
        raise SourceError(f"Oväntat svar från {source} vid ett Livewire-anrop, sidans struktur kan ha ändrats")
