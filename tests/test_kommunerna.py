"""Kommunernas evenemangskalendrar: Säffle och Kil, som visas som gruppen Kommunerna (#79)."""

import asyncio
import json
from datetime import date, timedelta

import httpx

from sources import kommunerna
from sources.kommunerna import Kil, Saffle, kil_state, saffle_dates

MONTHS = list(kommunerna.MONTHS)
D1 = date.today() + timedelta(days=5)
D2 = D1 + timedelta(days=7)


def sv(d: date) -> str:
    return f"{d.day:02d} {MONTHS[d.month - 1]}"


def run(coro):
    return asyncio.run(coro)


def test_group_is_kommunerna():
    assert Saffle.group == Kil.group == "Kommunerna"
    assert Saffle.key == "saffle" and Kil.key == "kil"


def test_saffle_dates_infer_the_year(monkeypatch):
    monkeypatch.setattr(kommunerna, "today", lambda: date(2026, 9, 29))
    assert saffle_dates("30 september", "30 september") == (date(2026, 9, 30), date(2026, 9, 30))
    assert saffle_dates("05 mars", "05 mars") == (date(2027, 3, 5), date(2027, 3, 5))        # våren: nästa år
    assert saffle_dates("19 september", "10 november") == (date(2026, 9, 19), date(2026, 11, 10))   # pågår
    assert saffle_dates("29 september", None) == (date(2026, 9, 29), date(2026, 9, 29))
    assert saffle_dates("31 februari", None) is None and saffle_dates("", None) is None
    # Adressen ger året när datumet stämmer, annars räknas det fram
    assert saffle_dates("05 mars", "05 mars", "/medis/2028-03-05-tribute.html")[0] == date(2028, 3, 5)
    assert saffle_dates("05 mars", "05 mars", "/medis/2026-09-03-babytorsdag.html")[0] == date(2027, 3, 5)

    monkeypatch.setattr(kommunerna, "today", lambda: date(2027, 1, 2))
    assert saffle_dates("28 december", "03 januari") == (date(2026, 12, 28), date(2027, 1, 3))   # över nyår


def hit(title, d, location="Medis stora scen", **kw):
    h = {"title": title, "startDate": sv(d), "endDate": sv(d), "startTime": "19:00", "endTime": "21:30",
         "location": location, "categories": ["Teater"], "description": "SäffleOperans musikal",
         "uri": f"/uppleva-och-gora/medis/{d.isoformat()}-{kommunerna._slug(title)}.html", "id": f"5.{title}",
         "image": {"alt": "", "uri": "/images/18.abc/1/%C3%84nglag%C3%A5rd%20960x540.jpg"}, "ticket": ""}
    h.update(kw)
    return h


def test_saffle_normalize_groups_recurring_occasions():
    events = Saffle().normalize({"hits": [
        hit("Änglagård", D1, ticket="https://secure.tickster.com/sv/egv24/selectevent"),
        hit("Änglagård", D2),
        hit("Gåfotboll", D1, location="Bollhallen, Sporthälla", categories=["Sport & motion"], startTime="10:00",
            endTime="", image=None),
        hit("Bio: Verity", D1, location="Sagabiografen", categories=["Film", "Okänd"]),
        hit("Mogendans", D1, endDate=sv(D1 + timedelta(days=2)), startTime="19:00", endTime="18:00"),
        hit("", D1),                                                    # utan titel
        hit("Ogiltigt datum", D1, startDate="99 smarch"),
    ]})
    by_title = {e["title"]: e for e in events}
    assert set(by_title) == {"Änglagård", "Gåfotboll", "Bio: Verity", "Mogendans"}
    run_ = by_title["Mogendans"]["next"]                                # över flera dagar: ingen sluttid
    assert (run_["date_end"], run_["time_start"], run_["time_end"]) == (
        (D1 + timedelta(days=2)).isoformat(), "19:00", None)

    a = by_title["Änglagård"]
    assert [o["date_start"] for o in a["occasions"]] == [D1.isoformat(), D2.isoformat()]
    assert a["next"]["time_start"] == "19:00" and a["next"]["time_end"] == "21:30"
    assert a["municipality"] == "Säffle" and a["place"]["title"] == "Medis stora scen"
    assert [c["title"] for c in a["categories"]] == ["Teater och underhållning"]
    assert a["booking_link"] == "https://secure.tickster.com/sv/egv24/selectevent"
    assert a["url"] == f"https://saffle.se/uppleva-och-gora/medis/{D1.isoformat()}-anglagard.html"
    assert a["images"][0]["large"] == "https://saffle.se/images/18.abc/1/%C3%84nglag%C3%A5rd%20960x540.jpg"
    assert a["id"] == "saffle-anglagard-medis-stora-scen" and a["summary"] == "SäffleOperans musikal"

    g = by_title["Gåfotboll"]
    assert [c["title"] for c in g["categories"]] == ["Sport, motion och hälsa"]
    assert g["next"]["time_end"] is None and g["images"] == [] and g["booking_link"] is None
    assert [c["title"] for c in by_title["Bio: Verity"]["categories"]] == ["Film"]   # okänd kategori blir Övrigt,
    # som försvinner när det finns en riktig kategori


def test_saffle_fetch_asks_for_all_paths_and_pages(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        start = int(request.url.params["start"])
        hits = [hit("Änglagård", D1)] if start == 0 else [hit("Gåfotboll", D1)]
        return httpx.Response(200, json={"hits": hits, "hitCount": 2})

    monkeypatch.setattr(kommunerna, "SAFFLE_PAGE_SIZE", 1)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    payload = run(Saffle().fetch(client, None))
    assert [h["title"] for h in payload["hits"]] == ["Änglagård", "Gåfotboll"]
    assert len(seen) == 2
    first = seen[0]
    assert first.url.params.get_list("paths[]") == kommunerna.SAFFLE_PATHS
    assert first.url.params["num"] == "1" and first.headers["x-requested-with"] == "XMLHttpRequest"


def test_saffle_fetch_rejects_unexpected_answer():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"message": "x"})))
    try:
        run(Saffle().fetch(client, None))
    except kommunerna.SourceError as exc:
        assert "Säffle kommun" in str(exc)
    else:
        raise AssertionError("inget fel")


def kil_item(title, d, end=None, time="10:30", end_time="11:00", desc=""):
    return {"id": f"4.{title}", "title": title, "desc": desc, "uri": f"/arkiv/evenemang/evenemang/{d}-x",
            "start": {"date": d.isoformat(), "time": time},
            "end": {"date": (end or d).isoformat(), "time": end_time}}


def kil_page(items, count):
    state = {"items": items, "count": count, "config": {"num": 25}}
    return ("<html><div data-cid='12.1'><p>Visar …</p></div>"
            "<script>AppRegistry.registerInitialState('12.9',{\"other\":1});</script>"
            f"<script nonce='x'>AppRegistry.registerInitialState('12.1',{json.dumps(state, ensure_ascii=False)});"
            "</script></html>")


def test_kil_state_and_normalize():
    page = kil_page([
        kil_item("Babytorsdag", D1, desc="För dig med barn 5–12 månader."),
        kil_item("Babytorsdag", D2),
        kil_item("KörenKörens höstkonsert", D1, time="17:30", end_time="18:30"),
        kil_item("Ungdomsgårdens konstutställning", D1, end=D2, time="00:00", end_time="23:59",
                 desc="Kom och läs om böckerna"),                    # heldag, och beskrivningen styr inte
        {"title": "Utan datum", "start": {}},
    ], 5)
    state = kil_state(page)
    assert state["count"] == 5 and len(state["items"]) == 5
    events = {e["title"]: e for e in Kil().normalize({"items": state["items"]})}
    assert set(events) == {"Babytorsdag", "KörenKörens höstkonsert", "Ungdomsgårdens konstutställning"}

    baby = events["Babytorsdag"]
    assert len(baby["occasions"]) == 2 and baby["municipality"] == "Kil" and baby["place"] is None
    assert [c["title"] for c in baby["categories"]] == ["Barn"]
    assert baby["url"] == f"https://kil.se/arkiv/evenemang/evenemang/{D1}-x" and baby["id"] == "kil-babytorsdag"
    assert "Musik" in [c["title"] for c in events["KörenKörens höstkonsert"]["categories"]]   # ordregeln konsert
    show = events["Ungdomsgårdens konstutställning"]
    assert (show["next"]["date_start"], show["next"]["date_end"], show["next"]["time_start"],
            show["next"]["time_end"]) == (D1.isoformat(), D2.isoformat(), None, None)
    assert [c["title"] for c in show["categories"]] == ["Utställning"]
    assert kil_state("<html>ingen lista</html>") is None


def test_kil_fetch_follows_pages():
    urls = []

    def handler(request):
        urls.append(str(request.url))
        if "start=" not in str(request.url):
            return httpx.Response(200, text=kil_page([kil_item(f"A{i}", D1) for i in range(25)], 27))
        return httpx.Response(200, text=kil_page([kil_item("B", D1), kil_item("C", D1)], 27))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    payload = run(Kil().fetch(client, None))
    assert len(payload["items"]) == 27
    assert urls == ["https://kil.se/arkiv/evenemang", "https://kil.se/arkiv/evenemang?start=25"]


def test_merge_fills_in_the_municipality():
    """Visit Värmland saknar ibland kommun (Gospelfestival i Fagerås), och Kil vet var evenemanget hålls."""
    from merge import merge
    vv = {"id": "vv-1", "source": "Visit Värmland", "title": "Gospelfestival i Fagerås", "summary": "", "description": "",
          "categories": [], "municipality": None, "place": None, "organizer": None, "url": "https://vv", "images": [],
          "booking_link": None, "website_link": None,
          "occasions": [{"date_start": D1.isoformat(), "date_end": D1.isoformat(), "time_start": None, "time_end": None}]}
    vv["sources"] = [{"name": "Visit Värmland", "url": "https://vv"}]
    kil = Kil().normalize({"items": [kil_item("Gospelfestival i Fagerås", D1, time="12:00", end_time="21:30")]})
    merged = merge([[vv], kil])
    assert len(merged) == 1 and merged[0]["municipality"] == "Kil"
    assert [s["name"] for s in merged[0]["sources"]] == ["Visit Värmland", "Kils kommun"]
