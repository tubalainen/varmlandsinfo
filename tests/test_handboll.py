"""Handboll i Värmland: Svenska Handbollförbundets matcher i Profixio, seniorer herr och dam (#82)."""

import asyncio
import json
from datetime import date, timedelta

import httpx

import chat
from categories import refine
from sources import handboll
from sources.handboll import Handboll, league_name, municipality, normalize_match, senior_league, team_municipality
from sources.profixio import parse_matches
from test_bandy import DAY, match, snapshot

LISTING = "".join(f'<a href="https://www.profixio.com/app/lx/competition/leagueid{i}">{n}</a>' for i, n in [
    (28137, "Herrar - Handbollsligan herr"), (28140, "Damer - Dam 1"), (28690, "Herrar - Svenska cupen 2026-2027"),
    (28053, "Herrar - Herr 3 Väst"), (28037, "Damer - Dam 4 Väst"), (27990, "Herrar - Herr 3 Öst"),
    (28055, "Pojkar - P19 Väst"), (28065, "Motion Senior - Motion Väst Herrar"), (28721, "Herrar - EM-kval"),
    (28069, "Para Väst - Para Väst")])


def league_page(teams, matches=()):
    links = "".join(f'<a href="https://www.profixio.com/app/lx/competition/leagueid1/teams/{tid}">\n{name}\n</a>'
                    for tid, name in teams)
    return f"<html><body>{links}{''.join(matches)}</body></html>"


def team_page(param="T1"):
    return f'''<html><head><meta name="csrf-token" content="TOKEN"></head>
      <body><script data-update-uri="https://www.profixio.com/app/livewire/update"></script>
      <div wire:snapshot="{snapshot("lx.team-page")}"></div>
      <div wire:snapshot="{snapshot("lx.team.schedule")}" x-init="$wire.__lazyLoad(&#039;{param}&#039;)"></div>
      </body></html>'''


def test_league_selection():
    from sources.profixio import parse_leagues
    names = [x["name"] for x in parse_leagues(LISTING) if senior_league(x["name"])]
    assert names == ["Herrar - Handbollsligan herr", "Damer - Dam 1", "Herrar - Svenska cupen 2026-2027",
                     "Herrar - Herr 3 Väst", "Damer - Dam 4 Väst"]                  # inte Öst, ungdom, motion, para
    assert league_name("Herrar - Herr 3 Väst") == "Herr 3 Väst"
    assert league_name("Damer - Svenska cupen 2026-2027") == "Svenska cupen (damer)"


def test_teams_and_places():
    assert team_municipality("IFK Hammarö") == "Hammarö" and team_municipality("IF Hellton Karlstad") == "Karlstad"
    assert team_municipality("IF Hellton") == "Karlstad" and team_municipality("HK Brukspôjkera") == "Forshaga"
    assert team_municipality("Skåre HK") == "Karlstad" and team_municipality("Karlskoga HK") == "Karlskoga"
    assert team_municipality("Kils AIKs HF") == "Kil" and team_municipality("IK Nord") is None
    assert municipality("Hammarhallen A, Hammarö", "IFK Hammarö") == "Hammarö"
    assert municipality("Sundstahallen", "IF Hellton Karlstad") == "Karlstad"            # okänd arena: hemmalaget
    assert municipality("Rimnershallen A", "Uddevalla HK") is None


def test_normalize_home_games_in_varmland_only():
    home, away = parse_matches("".join([
        match(1, DAY, "12:00", "IFK Hammarö", "IF HV Tidaholm", arena="Hammarhallen A, Hammarö", rnd="3"),
        match(2, DAY, "10:00", "Uddevalla HK", "IFK Hammarö", arena="Rimnershallen A")]))
    e = normalize_match({**home, "league": "Herrar - Herr 3 Väst"})
    assert e["title"] == "IFK Hammarö - IF HV Tidaholm" and e["municipality"] == "Hammarö"
    assert [c["title"] for c in e["categories"]] == ["Sport, motion och hälsa", "Handboll"]
    assert e["summary"] == ("Handboll, Herr 3 Väst, omgång 3: IFK Hammarö tar emot IF HV Tidaholm "
                            "i Hammarhallen A, Hammarö.")
    assert e["next"]["date_start"] == DAY.isoformat() and e["next"]["time_start"] == "12:00"
    assert e["url"] == "https://www.profixio.com/app/lx/match/1" and e["id"] == "handboll-1"
    assert normalize_match({**away, "league": "Herrar - Herr 3 Väst"}) is None            # bortamatch i Uddevalla


def run(handler, previous=None):
    requests = []

    def record(request):
        requests.append(request)
        return handler(request)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(record)) as client:
            return await Handboll().fetch(client, previous)
    return asyncio.run(go()), requests


def handler_for(schedules):
    """Profixio i miniatyr: tävlingslistan, seriernas sidor, lagsidorna och lagens schema (Livewire)."""
    def handler(request):
        url = str(request.url)
        assert request.headers["Accept-Language"] == "sv"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["_token"] == "TOKEN" and request.headers["X-Livewire"] == "1"
            param = body["components"][0]["calls"][0]["params"][0]
            return httpx.Response(200, json={"components": [{"effects": {"html": schedules[param]}}]})
        if "t=competitions" in url:
            return httpx.Response(200, text=LISTING)
        if "/teams/" in url:
            return httpx.Response(200, text=team_page(url.rsplit("/", 1)[1]))
        if "leagueid28053" in url:
            return httpx.Response(200, text=league_page([(101, "IFK Hammarö"), (102, "Uddevalla HK"),
                                                         (103, "IFK Hammarö F16")]))
        if "leagueid28140" in url:
            return httpx.Response(200, text=league_page([(201, "IF Hellton Karlstad"), (202, "IK Cyrus")]))
        return httpx.Response(200, text=league_page([(301, "Ystads IF HF"), (302, "HK Aranäs F16")]))
    return handler


SCHEDULES = {
    "101": "".join([match(1, DAY, "12:00", "IFK Hammarö", "IF HV Tidaholm", arena="Hammarhallen A, Hammarö"),
                    match(2, DAY, "10:00", "Uddevalla HK", "IFK Hammarö", arena="Rimnershallen A")]),
    "201": match(3, DAY + timedelta(days=1), "15:00", "IF Hellton Karlstad", "IK Cyrus", arena="Sundstahallen"),
}


def test_fetch_finds_varmland_teams_and_reads_their_schedules(monkeypatch):
    monkeypatch.setattr(handboll, "PAGE_DELAY", 0)
    payload, requests = run(handler_for(SCHEDULES))
    assert [(t["name"], t["league"]) for t in payload["teams"]] == [
        ("IF Hellton Karlstad", "Damer - Dam 1"), ("IFK Hammarö", "Herrar - Herr 3 Väst")]
    assert payload["discovered"] == date.today().isoformat()
    # tävlingslistan och de fem seniorseriernas första sida, sedan lagsidan och schemat för de två lagen
    assert [r.method for r in requests] == ["GET"] * 6 + ["GET", "POST"] * 2
    events = Handboll().normalize(payload)
    assert [(e["title"], e["municipality"]) for e in events] == [                      # bortamatchen är borta
        ("IF Hellton Karlstad - IK Cyrus", "Karlstad"), ("IFK Hammarö - IF HV Tidaholm", "Hammarö")]

    # Nästa hämtning inom en vecka: bara lagen, utan tävlingslistan och serierna
    payload2, requests2 = run(handler_for(SCHEDULES), previous=payload)
    assert [r.method for r in requests2] == ["GET", "POST"] * 2 and "/teams/" in str(requests2[0].url)
    assert payload2["discovered"] == payload["discovered"]


def test_rediscovers_after_a_week(monkeypatch):
    monkeypatch.setattr(handboll, "PAGE_DELAY", 0)
    old = {"discovered": (date.today() - timedelta(days=8)).isoformat(), "teams": [], "matches": []}
    _, requests = run(handler_for(SCHEDULES), previous=old)
    assert "t=competitions" in str(requests[0].url)


def test_same_match_from_two_teams_once():
    m = parse_matches(match(9, DAY, "18:00", "IFK Kristinehamn", "Arvika HK", arena="Kristinehamns sporthall"))[0]
    events = Handboll().normalize({"matches": [{**m, "league": "Damer - Dam 3 Väst"}] * 2})
    assert [(e["title"], e["municipality"]) for e in events] == [("IFK Kristinehamn - Arvika HK", "Kristinehamn")]


def test_fetch_fails_clearly_when_structure_changes(monkeypatch):
    monkeypatch.setattr(handboll, "PAGE_DELAY", 0)
    try:
        run(lambda r: httpx.Response(200, text="<html>ny layout</html>"))
    except Exception as exc:
        assert "struktur" in str(exc)
    else:
        raise AssertionError("inget fel")


def test_category_and_chat():
    def titles(title, summary=""):
        return [c["title"] for c in refine([{"title": "Evenemang"}], title, summary)]
    assert "Handboll" in titles("Handbollsmatch: IFK Kristinehamn - Arvika HK")
    assert "Handboll" not in titles("Tipspromenad", "Karlskoga Handboll ordnar tipspromenad.")   # bara titeln
    assert "Handboll" not in titles("Handbollsskola för barn")
    assert chat.find_categories("Finns det några handbollsmatcher i helgen?") == {"Handboll"}
