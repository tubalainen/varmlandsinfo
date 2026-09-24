"""SHL: hemmamatcher för ett lag (standard Färjestad BK) från SHL:s öppna spelschema-API."""

import asyncio
import os

import httpx

from common import category, finalize, get_json

API_BASE = "https://www.shl.se/api/sports-v2"
TEAM_CODE = os.getenv("SHL_TEAM_CODE", "FBK").strip().upper()
# Kommun för lagets hemmaarena (Färjestad spelar i Löfbergs Arena, Karlstad)
TEAM_MUNICIPALITY = os.getenv("SHL_TEAM_MUNICIPALITY", "Karlstad")


class SHL:
    key = "shl"
    title = "SHL"
    homepage = "https://www.shl.se/game-schedule"

    def config_error(self) -> str | None:
        return None if TEAM_CODE else "SHL_TEAM_CODE är tomt"

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        filters = await get_json(client, f"{API_BASE}/season-series-game-types-filter", self.title)
        default = filters.get("defaultSsgtFilter") or {}
        season = default.get("season")
        series = next((s["uuid"] for s in filters.get("series", []) if s.get("code") == "SHL"),
                      default.get("series"))
        game_types = [g["uuid"] for g in filters.get("gameType", []) if g.get("uuid")] \
            or [default.get("gameType")]
        if not (season and series and all(game_types)):
            raise RuntimeError("SHL:s API gav ingen aktuell säsong")

        games: dict[str, dict] = {}
        for game_type in game_types:
            data = await get_json(client, f"{API_BASE}/game-schedule", self.title, seasonUuid=season,
                                  seriesUuid=series, gameTypeUuid=game_type, gamePlace="all", played="all")
            for g in data.get("gameInfo") or []:
                if (g.get("homeTeamInfo") or {}).get("code", "").upper() == TEAM_CODE:
                    games[g["uuid"]] = g
            await asyncio.sleep(0.5)
        return {"team": TEAM_CODE, "season": season, "games": list(games.values())}

    def normalize(self, payload: dict) -> list[dict]:
        return [e for e in (normalize_game(g) for g in payload.get("games") or []) if e]


def _team_name(info: dict) -> str:
    names = info.get("names") or {}
    return names.get("long") or names.get("full") or info.get("code") or "?"


def normalize_game(g: dict) -> dict | None:
    if g.get("state") == "post-game":
        return None
    start = g.get("startDateTime") or ""   # lokal tid, t.ex. "2026-09-24 19:00:00"
    if len(start) < 10:
        return None
    home, away = g.get("homeTeamInfo") or {}, g.get("awayTeamInfo") or {}
    home_name, away_name = _team_name(home), _team_name(away)
    venue = (g.get("venueInfo") or {}).get("name")
    series = (g.get("seriesInfo") or {}).get("displayName") or "SHL"
    rnd = g.get("roundNumber")
    summary = f"{series}-match{f', omgång {rnd}' if rnd else ''}: {home_name} tar emot {away_name}" \
              + (f" i {venue}." if venue else ".")
    url = f"https://www.shl.se/game/{g['uuid']}"
    return finalize({
        "id": f"shl-{g['uuid']}",
        "source": SHL.title,
        "title": f"{home_name} - {away_name}",
        "summary": summary,
        "description": "",
        "categories": [category("Sport, motion och hälsa")],
        "municipality": TEAM_MUNICIPALITY,
        "place": {"title": venue, "address": "", "lat": None, "lon": None} if venue else None,
        "organizer": home_name,
        "url": url,
        "booking_link": None,
        "website_link": None,
        "images": [],
        "occasions": [{"date_start": start[:10], "date_end": start[:10],
                       "time_start": start[11:16] or None, "time_end": None}],
    })
