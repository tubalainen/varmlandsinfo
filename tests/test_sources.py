from datetime import date, timedelta

from merge import merge, similar
from sources import shl, ticketmaster
from sources.visitvarmland import normalize_event

FUTURE = (date.today() + timedelta(days=30)).isoformat()


def shl_game(**kw):
    g = {
        "uuid": "abc123", "startDateTime": f"{FUTURE} 19:00:00", "state": "pre-game", "roundNumber": 5,
        "homeTeamInfo": {"code": "FBK", "names": {"long": "Färjestad BK"}},
        "awayTeamInfo": {"code": "RBK", "names": {"long": "Rögle BK"}},
        "venueInfo": {"name": "Löfbergs Arena"}, "seriesInfo": {"displayName": "SHL"},
    }
    g.update(kw)
    return g


def test_shl_normalize():
    e = shl.normalize_game(shl_game())
    assert e["id"] == "shl-abc123"
    assert e["title"] == "Färjestad BK - Rögle BK"
    assert e["next"] == {"date_start": FUTURE, "date_end": FUTURE, "time_start": "19:00", "time_end": None}
    assert e["municipality"] == "Karlstad"
    assert e["url"] == "https://www.shl.se/game/abc123"
    assert e["categories"][0]["title"] == "Sport, motion och hälsa"
    assert shl.normalize_game(shl_game(state="post-game")) is None


def tm_event(**kw):
    ev = {
        "id": "Z1", "name": "Håkan Hellström", "url": "https://www.ticketmaster.se/event/Z1",
        "dates": {"start": {"localDate": FUTURE, "localTime": "20:00:00"}, "status": {"code": "onsale"}},
        "classifications": [{"segment": {"name": "Music"}, "genre": {"name": "Rock"}}],
        "images": [{"url": "https://s1.ticketm.net/a_640.jpg", "ratio": "16_9", "width": 640},
                   {"url": "https://s1.ticketm.net/a_1024.jpg", "ratio": "16_9", "width": 1024},
                   {"url": "https://s1.ticketm.net/a_305.jpg", "ratio": "3_2", "width": 305}],
        "priceRanges": [{"min": 495.0, "max": 895.0, "currency": "SEK"}],
        "_embedded": {"venues": [{"name": "Löfbergs Arena", "postalCode": "65465", "city": {"name": "Karlstad"},
                                  "address": {"line1": "Norra infarten 79"},
                                  "location": {"latitude": "59.4", "longitude": "13.5"}}]},
    }
    ev.update(kw)
    return ev


def test_ticketmaster_normalize():
    e = ticketmaster.normalize_event(tm_event())
    assert e["id"] == "tm-Z1"
    assert e["municipality"] == "Karlstad"
    assert e["categories"][0]["title"] == "Musik"
    assert e["next"]["time_start"] == "20:00"
    assert e["booking_link"] == "https://www.ticketmaster.se/event/Z1"
    assert e["images"][0]["large"].endswith("a_1024.jpg")
    assert "495 kr" in e["summary"]


def test_ticketmaster_filters_outside_varmland_and_cancelled():
    oslo = tm_event(_embedded={"venues": [{"name": "Spektrum", "postalCode": "0188", "city": {"name": "Oslo"}}]})
    assert ticketmaster.normalize_event(oslo) is None
    amal = tm_event(_embedded={"venues": [{"name": "X", "postalCode": "66231", "city": {"name": "Åmål"}}]})
    assert ticketmaster.normalize_event(amal) is None
    cancelled = tm_event(dates={"start": {"localDate": FUTURE}, "status": {"code": "cancelled"}})
    assert ticketmaster.normalize_event(cancelled) is None
    skoghall = tm_event(_embedded={"venues": [{"name": "Folkets hus", "city": {"name": "Skoghall"}}]})
    assert ticketmaster.normalize_event(skoghall)["municipality"] == "Hammarö"


def test_ticketmaster_disabled_without_key(monkeypatch):
    monkeypatch.setattr(ticketmaster, "API_KEY", "")
    assert "API-nyckel" in ticketmaster.Ticketmaster().config_error()


def test_geohash():
    assert ticketmaster.geohash(57.64911, 10.40744, 11) == "u4pruydqqvj"   # känt referensvärde


def test_similar_titles():
    assert similar("Färjestad BK - Rögle BK", "Färjestad BK – Rögle BK")
    assert similar("Håkan Hellström", "Håkan Hellström – Turné 2026")
    assert not similar("Jazzkväll", "Hockey: Färjestad BK - HV71")


def test_merge_shl_into_visit_varmland():
    vv = normalize_event({
        "id": 5, "title": "Färjestad BK - Rögle BK", "slug": "evenemang/sport/fbk-rbk",
        "categories": [{"title": "Sport, motion och hälsa"}], "organizers": [{"municipality_id": 9}],
        "images": [{"large": "https://img/fbk.jpg"}], "booking_link": "https://tickster/x",
        "occasions": [{"date_start": FUTURE, "date_end": FUTURE, "time_start": "00:00:00"}],
    }, {9: "Karlstad"})
    game = shl.normalize_game(shl_game())
    other = shl.normalize_game(shl_game(uuid="zzz", awayTeamInfo={"code": "HV", "names": {"long": "HV71"}}))
    merged = merge([[vv], [], [game, other]])
    assert len(merged) == 2
    fbk = merged[0]
    assert fbk["source"] == "Visit Värmland"
    assert [s["name"] for s in fbk["sources"]] == ["Visit Värmland", "SHL"]
    assert fbk["next"]["time_start"] == "19:00"     # tiden kommer från SHL
    assert merged[1]["title"] == "Färjestad BK - HV71"


def test_merge_keeps_different_municipalities_apart():
    a = shl.normalize_game(shl_game())
    b = dict(ticketmaster.normalize_event(tm_event(name="Färjestad BK - Rögle BK")))
    b["municipality"] = "Arvika"
    assert len(merge([[a], [b]])) == 2
