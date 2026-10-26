"""Tickster (#116): Event Dump API, evenemangen i Värmland, Karlskoga och Degerfors."""

import asyncio
import gzip
import json
from datetime import date, timedelta

import httpx
import pytest

from common import SourceError
from sources import tickster
from sources.tickster import Tickster

D1 = date.today() + timedelta(days=5)
D2 = D1 + timedelta(days=2)
VENUES = [
    {"id": "v1", "name": "Wermland Opera Stora Scen", "address": "Malmtorgsgatan 2", "zipCode": "65340",
     "city": "Karlstad", "country": "SE", "geo": {"latitude": 59.38, "longitude": 13.5}},
    {"id": "v2", "name": "Stora konsertsalen, Musikhögskolan Ingesund", "address": "Musikhögskolan Ingesund",
     "zipCode": "67191", "city": "Arvika", "country": "SE", "geo": {"latitude": 59.6, "longitude": 12.6}},
    {"id": "v3", "name": "Strandhallen", "address": "Strandvägen 2", "zipCode": "67151", "city": "Arvika", "country": "SE"},
    {"id": "v4", "name": "Bio Monitor", "address": "Viktoriagatan 8", "zipCode": "68230", "city": "Filipstad", "country": "SE"},
    {"id": "v5", "name": "Salongen / Landskrona Teater", "address": "Östergatan 18", "zipCode": "261 31",
     "city": "Landskrona", "country": "SE"},
    {"id": "v6", "name": "Konserthuset", "address": "Gate 1", "zipCode": "0150", "city": "Oslo", "country": "NO"},
]
ORGANIZERS = [{"id": "o1", "name": "Wermland Opera"}, {"id": "o2", "name": "MH Ingesund"},
              {"id": "o3", "name": "Dotteviks IF"}, {"id": "o9", "name": "Landskrona stad"}]


def ev(eid, name, venue, day=D1, start="19:00", end="21:00", end_day=None, **extra):
    end_day = end_day or day
    return {"id": eid, "published": True, "name": name, "start": f"{day.isoformat()}T{start}:00+01:00",
            "end": f"{end_day.isoformat()}T{end}:00+01:00", "eventState": "ReleasedForSale", "hierarchyType": "event",
            "productionParentId": None, "infoUri": f"https://www.tickster.com/se/sv/events/{eid}/x",
            "shopUri": f"https://secure.tickster.com/{eid}", "description": "<p>Välkommen!</p><p>Biljetter.</p>",
            "imageUrl": f"https://static.tickster.com/{eid}", "isCollectionEvent": False, "tags": [], "links": [],
            "venueId": venue, "organizerId": "o1", "childEvents": [], **extra}


def dump(*events):
    return {"created": "2026-10-26T02:00:01+00:00", "events": list(events), "venues": VENUES, "organizers": ORGANIZERS}


def normalize(*events):
    payload = {"dump_id": "x", **tickster.area_dump(dump(*events))}
    return {e["title"]: e for e in Tickster().normalize(payload)}


def test_only_events_in_the_area_are_kept():
    payload = tickster.area_dump(dump(ev("a", "Kulmen", "v2"), ev("b", "Revy", "v5"), ev("c", "Konsert", "v6")))
    assert [e["id"] for e in payload["events"]] == ["a"]
    assert {v["id"] for v in payload["venues"]} == {"v1", "v2", "v3", "v4"}
    assert [o["id"] for o in payload["organizers"]] == ["o1"]                 # bara arrangörerna som används


def test_event_fields():
    e = normalize(ev("a1", "Ingesunds symfoniorkester - Kulmen blir Finlandia", "v2", organizerId="o2",
                     links=[{"text": "Läs mer", "uri": "https://ingesund.se"}]))[
        "Ingesunds symfoniorkester - Kulmen blir Finlandia"]
    assert e["id"] == "tickster-a1" and e["source"] == "Tickster"
    assert e["url"] == "https://www.tickster.com/se/sv/events/a1/x" and e["booking_link"] == "https://secure.tickster.com/a1"
    assert e["municipality"] == "Arvika" and e["organizer"] == "MH Ingesund"
    assert e["place"] == {"title": "Stora konsertsalen, Musikhögskolan Ingesund",
                          "address": "Musikhögskolan Ingesund, 67191 Arvika", "lat": 59.6, "lon": 12.6}
    assert e["occasions"] == [{"date_start": D1.isoformat(), "date_end": D1.isoformat(),
                               "time_start": "19:00", "time_end": "21:00"}]
    assert e["description"] == "Välkommen!\nBiljetter." and e["website_link"] == "https://ingesund.se"
    assert e["images"][0]["large"] == "https://static.tickster.com/a1"
    assert [c["title"] for c in e["categories"]] == ["Musik"]


def test_not_events_are_skipped():
    events = normalize(
        ev("p", "Presentkort", "v1", day=date(2025, 12, 1), end_day=date(2027, 12, 31)),
        ev("s", "Dotteviks IF Säsongskort 2026/2027", "v3", end_day=D1 + timedelta(days=150)),
        ev("m", "Medlemsskap Föreningen Ransätersstämman", "v1"),
        ev("b", "Bortglömda ön  (Tal: Sve(dubb)(Text: Sve)", "v4", tags=["bio"]),
        ev("l", "Simson och Delila (Live på bio)", "v4"),
        ev("x", "Clayface", "v4", tags=["bio"]),
        ev("c", "Halloween 16+", "v1", eventState="Cancelled"),
        ev("k", "Alla konserter på Ingesund", "v2", hierarchyType="collection", childEvents=[{"id": "a"}]),
        ev("f", "Mat & Dryck - En döing på drömsemester", "v1"),
        ev("u", "Opublicerad", "v1", published=False),
        ev("ok", "Kejsaren av Portugallien", "v1", eventState="SaleEnded"),            # slutsåld blir av ändå
    )
    assert set(events) == {"Kejsaren av Portugallien"}


def test_performances_with_the_same_title_and_place_are_one_event():
    payload = {"dump_id": "x", **tickster.area_dump(dump(
        ev("p2", "En döing på drömsemester", "v1", day=D2, start="18:00", end="20:05",
           hierarchyType="production-child", productionParentId="PROD"),
        ev("p1", "En döing på drömsemester", "v1", hierarchyType="production-child", productionParentId="PROD"),
        ev("p3", "En döing på drömsemester", "v2"),                                    # annan plats
    ))}
    same, other = sorted(Tickster().normalize(payload), key=lambda e: len(e["occasions"]), reverse=True)
    assert same["id"] == "tickster-PROD" and same["place"]["title"] == "Wermland Opera Stora Scen"
    assert [(o["date_start"], o["time_start"]) for o in same["occasions"]] == [(D1.isoformat(), "19:00"),
                                                                               (D2.isoformat(), "18:00")]
    assert other["id"] == "tickster-p3" and other["municipality"] == "Arvika"


def test_times_and_multi_day_events():
    events = normalize(
        ev("n", "Halloweenfesten", "v1", start="21:00", end="02:00", end_day=D1 + timedelta(days=1)),
        ev("f", "Indoor Rockin' Roots Festival", "v1", start="18:00", end="23:00", end_day=D1 + timedelta(days=2)),
    )
    night = events["Halloweenfesten"]["occasions"][0]
    assert (night["date_start"], night["date_end"], night["time_start"], night["time_end"]) == \
        (D1.isoformat(), D1.isoformat(), "21:00", None)                        # slutar efter midnatt: ingen sluttid
    fest = events["Indoor Rockin' Roots Festival"]["occasions"][0]
    assert (fest["date_start"], fest["date_end"]) == (D1.isoformat(), (D1 + timedelta(days=2)).isoformat())


def test_categories():
    def cats(name, venue="v1", **extra):
        [e] = normalize(ev("a", name, venue, **extra)).values()
        return [c["title"] for c in e["categories"]]
    assert cats("Dotteviks IF Herr U - Åsmyra IBK", "v3", tags=["Innebandy"]) == ["Sport, motion och hälsa"]
    assert cats("BIK Karlskoga - Nybro Vikings", "v3") == ["Sport, motion och hälsa"]
    assert cats("Vinprovning Franska frestelser", "v3") == ["Mat och dryck"]
    assert cats("Mogendans på Medis", "v3") == ["Dans"]
    assert cats("Kvinnor och äppelträd", "v1") == ["Teater och underhållning"]         # platsens namn
    assert cats("Höstglöd", "v2") == ["Musik"]
    assert cats("Stadsvandring 10 november", "v3") == ["Guidning"]
    assert cats("Drömresan", "v3") == ["Övrigt"]
    assert "Bandy" not in cats("Dotteviks IF Dam - Skoghalls IBK", "v3", tags=["Innebandy"])


def test_config_error_without_key(monkeypatch):
    monkeypatch.setattr(tickster, "API_KEY", "")
    assert "TICKSTER_API_KEY" in Tickster().config_error()
    monkeypatch.setattr(tickster, "API_KEY", "nyckel")
    assert Tickster().config_error() is None


def run(coro):
    return asyncio.run(coro)


def client_for(handler):
    calls = []

    def record(request):
        calls.append(request)
        return handler(request)
    return httpx.AsyncClient(transport=httpx.MockTransport(record)), calls


def test_fetch_downloads_the_dump_and_keeps_the_area(monkeypatch):
    monkeypatch.setattr(tickster, "API_KEY", "HEMLIG")
    body = gzip.compress(json.dumps(dump(ev("a", "Kulmen", "v2"), ev("b", "Revy", "v5"))).encode())

    def handler(request):
        if request.url.host == "api.tickster.com":
            return httpx.Response(200, json={"id": "sv-upcoming-1", "created": "2026-10-26T03:17:10+00:00",
                                             "uri": "http://dumps.s3.example.com/sv/upcoming/1?X-Amz-Signature=s"})
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    client, calls = client_for(handler)
    payload = run(Tickster().fetch(client, None))
    assert payload["dump_id"] == "sv-upcoming-1" and [e["id"] for e in payload["events"]] == ["a"]
    assert calls[0].url.params["key"] == "HEMLIG" and str(calls[0].url.path) == "/sv/api/1.0/events/dump/upcoming"
    assert calls[1].url.scheme == "https"                                        # filen hämtas över https

    client, calls = client_for(handler)
    assert run(Tickster().fetch(client, payload)) is payload                     # samma fil: ingen ny hämtning
    assert len(calls) == 1


def test_fetch_errors_never_show_the_key(monkeypatch):
    monkeypatch.setattr(tickster, "API_KEY", "HEMLIG")
    for status in (401, 404):
        client, _ = client_for(lambda request, s=status: httpx.Response(s))
        with pytest.raises(SourceError) as exc:
            run(Tickster().fetch(client, None))
        assert "HEMLIG" not in str(exc.value) and "key=" not in str(exc.value)
    client, _ = client_for(lambda request: httpx.Response(200, json={"id": "x"}))
    with pytest.raises(SourceError, match="adress"):
        run(Tickster().fetch(client, None))

    def broken(request):
        if request.url.host == "api.tickster.com":
            return httpx.Response(200, json={"id": "y", "uri": "https://dumps.example.com/y?sig=HEMLIG2"})
        return httpx.Response(200, content=b"\x1f\x8btrasig")
    client, _ = client_for(broken)
    with pytest.raises(SourceError) as exc:
        run(Tickster().fetch(client, None))
    assert "HEMLIG2" not in str(exc.value)
