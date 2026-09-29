"""Bandy i Värmland från Svenska Bandyförbundets matcher i Profixio."""

import asyncio
import html
import json
from datetime import date, datetime, timedelta

import httpx

import chat
from common import TZ
from sources import bandy
from sources.bandy import Bandy, municipality, normalize_match, parse_leagues, parse_matches, parse_teams, youth

DAY = date.today() + timedelta(days=10)


def kickoff(day: date, hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return int(datetime(day.year, day.month, day.day, h, m, tzinfo=TZ).timestamp())


def match(mid, day, hhmm, home, away, arena="Tingvalla Isstadion", rnd="1"):
    """Ett matchblock som på Profixios publika sidor (förenklat men med samma struktur)."""
    facility = f'<a class="text-blue-950" href="https://www.profixio.com/app/lx/SBF/facility/5766">\n {arena}\n</a>' if arena else ""
    return f'''<div x-data="{{ init() {{ $store.matches.registerMatch(
      {mid},
      'SBF.SE.BA',
      {{ homegoals: '', awaygoals: '', hasLivescore: false, winner: null, gamestate: null, setup: null, kickoff: {kickoff(day, hhmm)}, }}
    ); }} }}" class="flex flex-col h-full"
     wire:key="mc_mini_{mid}"
    >
      <div>Runde {rnd}</div><div>•</div><div class="hidden">Bandyallsvenskan He</div>
      {facility}
      <div class="flex">{day.strftime("%b")} {day.day} • {hhmm}</div>
      <div>{home}</div><div>-</div><div>{hhmm}</div><div>{away}</div>
      <div>Finished</div><a href="https://www.profixio.com/app/lx/match/{mid}">Matchinfo</a>
    </div>'''


def snapshot(name):
    data = {"data": [], "memo": {"id": "x", "name": name}, "checksum": "c"}
    return html.escape(json.dumps(data), quote=True)


def schedule_page(matches, teams=(), next_param=None):
    links = "".join(f'<a href="https://www.profixio.com/app/lx/competition/leagueid1/teams/{i}">\n{t}\n</a>'
                    for i, t in enumerate(teams))
    lazy = (f'<div wire:snapshot="{snapshot("infinite-scroll-next-page")}" wire:id="n" '
            f'x-intersect="$wire.__lazyLoad(&#039;{next_param}&#039;)"></div>') if next_param else ""
    return f'''<html><head><meta name="csrf-token" content="TOKEN"></head>
      <body><script data-update-uri="https://www.profixio.com/app/livewire/update"></script>
      <div wire:snapshot="{snapshot("lx.competition.schedule")}">{links}{"".join(matches)}{lazy}</div></body></html>'''


LISTING = '''<a href="https://www.profixio.com/app/lx/competition/leagueid28502">Bandyallsvenskan Herr</a>
  <a href="https://www.profixio.com/app/lx/competition/leagueid28500">Elitserien Herr</a>
  <a href="https://www.profixio.com/app/lx/competition/leagueid28603">Träningsmatcher Mellansverige</a>
  <a href="https://www.profixio.com/app/lx/competition/leagueid28517">Division 2 Stockholm</a>
  <a href="https://www.profixio.com/app/lx/competition/leagueid28509">U19 Nationell</a>
  <a href="https://www.profixio.com/app/lx/competition/leagueid28583">Karlstad tjejbandycup</a>'''


def test_league_selection():
    names = [x["name"] for x in parse_leagues(LISTING) if bandy.senior_league(x["name"])]
    assert names == ["Bandyallsvenskan Herr", "Elitserien Herr", "Träningsmatcher Mellansverige"]


def test_youth_and_place():
    assert youth("IK Sirius BK U17N") and youth("Derby/Linköping U17") and youth("Västerås SK Flick Elit")
    assert not youth("Katrineholm Bandy U") and not youth("IF Boltic")          # U = utvecklingslag (seniorer)
    assert municipality("Tingvalla Isstadion", "Djurgårdens IF Bandy") == "Karlstad"
    assert municipality(None, "Slottsbron IF") == "Grums"
    assert municipality("Behrn Arena", "Örebro SK Bandy") is None
    assert municipality("Stinsen Arena", "Nässjö IF") is None


def test_parse_matches_and_teams():
    page = schedule_page([match(1, DAY, "19:00", "IF Boltic", "Djurgårdens IF Bandy"),
                          match(2, DAY, "15:00", "Nässjö IF", "IF Boltic", arena="Stinsen Arena", rnd="2")],
                         teams=["IF Boltic", "Nässjö IF"])
    ms = parse_matches(page)
    assert [(m["id"], m["arena"], m["home"], m["away"], m["round"]) for m in ms] == [
        ("1", "Tingvalla Isstadion", "IF Boltic", "Djurgårdens IF Bandy", "1"),
        ("2", "Stinsen Arena", "Nässjö IF", "IF Boltic", "2")]
    assert parse_teams(page) == ["IF Boltic", "Nässjö IF"]


def test_normalize_home_games_in_varmland_only():
    home, away = parse_matches(schedule_page([match(1, DAY, "19:00", "IF Boltic", "Djurgårdens IF Bandy"),
                                              match(2, DAY, "15:00", "Nässjö IF", "IF Boltic", arena="Stinsen Arena")]))
    e = normalize_match({**home, "league": "Bandyallsvenskan Herr"})
    assert e["title"] == "IF Boltic - Djurgårdens IF Bandy"
    assert e["municipality"] == "Karlstad" and e["place"]["title"] == "Tingvalla Isstadion"
    assert e["next"]["date_start"] == DAY.isoformat() and e["next"]["time_start"] == "19:00"
    assert [c["title"] for c in e["categories"]] == ["Sport, motion och hälsa", "Bandy"]
    assert e["summary"] == "Bandyallsvenskan Herr, omgång 1: IF Boltic tar emot Djurgårdens IF Bandy på Tingvalla Isstadion."
    assert e["url"] == "https://www.profixio.com/app/lx/match/1"
    assert normalize_match({**away, "league": "Bandyallsvenskan Herr"}) is None     # bortamatch i Nässjö


def test_training_and_youth_matches():
    ms = parse_matches(schedule_page([match(1, DAY, "13:30", "Slottsbron IF", "Ready"),
                                      match(2, DAY, "10:00", "IK Sirius BK U17N", "Slottsbron IF U17")]))
    e = normalize_match({**ms[0], "league": "Träningsmatcher Mellansverige"})
    assert e["summary"] == "Träningsmatch i bandy: Slottsbron IF möter Ready på Tingvalla Isstadion."
    assert normalize_match({**ms[1], "league": "Träningsmatcher Mellansverige"}) is None     # ungdom


def run(handler, previous=None):
    requests = []

    def record(request):
        requests.append(request)
        return handler(request)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(record)) as client:
            return await Bandy().fetch(client, previous)
    return asyncio.run(go()), requests


def test_fetch_discovers_leagues_and_reads_next_pages(monkeypatch):
    monkeypatch.setattr(bandy, "PAGE_DELAY", 0)
    allsvenskan = schedule_page([match(1, DAY, "19:00", "IF Boltic", "Djurgårdens IF Bandy")],
                                teams=["IF Boltic", "Nässjö IF"], next_param="P2")
    page2 = schedule_page([match(2, DAY + timedelta(days=7), "13:15", "IF Boltic", "Tranås BoIS")])
    elit = schedule_page([match(3, DAY, "19:00", "Villa-Lidköping BK", "Västerås SK", arena="Sparbanken Lidköping Arena")],
                         teams=["Villa-Lidköping BK", "Västerås SK"])
    training = schedule_page([], teams=["IK Sirius BK U17N"])

    def handler(request):
        url = str(request.url)
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["_token"] == "TOKEN" and request.headers["X-Livewire"] == "1"
            assert body["components"][0]["calls"][0] == {"path": "", "method": "__lazyLoad", "params": ["P2"]}
            return httpx.Response(200, json={"components": [{"effects": {"html": page2}}]})
        if "t=competitions" in url:
            return httpx.Response(200, text=LISTING)
        if "leagueid28502" in url:
            return httpx.Response(200, text=allsvenskan)
        if "leagueid28500" in url:
            return httpx.Response(200, text=elit)
        return httpx.Response(200, text=training)

    payload, requests = run(handler)
    assert [x["name"] for x in payload["leagues"]] == ["Bandyallsvenskan Herr"]       # bara serier med lag från Värmland
    assert payload["discovered"] == date.today().isoformat()
    assert [m["id"] for m in payload["matches"]] == ["1", "2"]
    # tävlingslistan, första sidan av de tre seniorserierna (Allsvenskans återanvänds) och nästa sida
    assert [r.method for r in requests] == ["GET", "GET", "GET", "GET", "POST"]
    events = Bandy().normalize(payload)
    assert [e["title"] for e in events] == ["IF Boltic - Djurgårdens IF Bandy", "IF Boltic - Tranås BoIS"]

    # Nästa hämtning inom en vecka: bara Allsvenskan, utan tävlingslistan
    payload2, requests2 = run(handler, previous=payload)
    assert [r.method for r in requests2] == ["GET", "POST"] and "leagueid28502" in str(requests2[0].url)
    assert payload2["discovered"] == payload["discovered"]


def test_rediscovers_after_a_week(monkeypatch):
    monkeypatch.setattr(bandy, "PAGE_DELAY", 0)
    old = {"discovered": (date.today() - timedelta(days=8)).isoformat(),
           "leagues": [{"id": "1", "name": "Gammal serie", "teams": []}], "matches": []}
    _, requests = run(lambda r: httpx.Response(200, text=LISTING if "competitions" in str(r.url) else schedule_page([])),
                      previous=old)
    assert "t=competitions" in str(requests[0].url)


def test_fetch_fails_clearly_when_structure_changes(monkeypatch):
    monkeypatch.setattr(bandy, "PAGE_DELAY", 0)
    try:
        run(lambda r: httpx.Response(200, text="<html>ny layout</html>"))
    except Exception as exc:
        assert "struktur" in str(exc)
    else:
        raise AssertionError("inget fel")


def test_bandy_matches_in_chat():
    ms = parse_matches(schedule_page([match(1, DAY, "19:00", "IF Boltic", "Djurgårdens IF Bandy")]))
    e = normalize_match({**ms[0], "league": "Bandyallsvenskan Herr"})
    inne = {"title": "Innebandy: Damer", "summary": "", "description": "", "organizer": None, "place": None,
            "municipality": "Karlstad", "url": "https://x", "categories": [{"title": "Sport, motion och hälsa"}],
            "occasions": [{"date_start": DAY.isoformat(), "date_end": DAY.isoformat(), "time_start": "19:00",
                           "time_end": None}]}
    _, sources = chat.search_answer("När spelar Boltic nästa gång?", [e, inne], date.today())
    assert [s["title"] for s in sources] == ["IF Boltic - Djurgårdens IF Bandy"]
    _, sources = chat.search_answer("Vilka bandymatcher finns?", [e, inne], date.today())
    assert [s["title"] for s in sources] == ["IF Boltic - Djurgårdens IF Bandy"]
    assert chat.scope_check("När spelar Boltic på Tingvalla?", [e, inne], date.today())["ok"]
