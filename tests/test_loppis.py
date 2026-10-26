"""Källorna Loppiskartan (#115, ersätter loppisar.com) och Karlstad Loppis (#43)."""

import json
from datetime import date, timedelta

from merge import merge, similar
from sources import karlstadloppis, loppiskartan
from sources.karlstadloppis import KarlstadLoppis
from sources.loppiskartan import Loppiskartan

MONTHS = list(karlstadloppis.MONTHS)
D1 = date.today() + timedelta(days=3)
CLOSED = {"isOpen": False, "start": "", "end": ""}


def week(**days):
    """Veckoschemat som Loppiskartan har det (JSON som text), t.ex. week(sunday=("12:00", "17:00"))."""
    return json.dumps({d: {"isOpen": True, "start": t[0], "end": t[1]} if (t := days.get(d)) else CLOSED
                       for d in loppiskartan.WEEKDAYS})


def market(mid, name, hours_type=None, weekly=None, dates=None, kommun="Karlstad", **extra):
    return {"id": mid, "slug": f"m-{mid}", "name": name, "description": extra.pop("description", ""),
            "latitude": 59.4, "longitude": 13.5, "address": "Östanås 610, SE-655 98 Molkom, Sverige",
            "hours_type": hours_type, "weekly_schedule": weekly,
            "specific_dates": json.dumps([{"date": d, "start": "11:00", "end": "16:00"} for d in dates or []]),
            "hours_note": extra.pop("hours_note", None), "website": extra.pop("website", ""), "facebook": None,
            "instagram": None, "kommun": kommun, **extra}


def page(markets: list[dict]) -> str:
    """Sidan som Next.js skickar den: datan uppdelad i flera skript."""
    data = '1:["$","div"]\n27:["$","$L2c",null,' + json.dumps({"markets": markets, "areaName": "Värmland"}) + "]\n"
    parts = [data[:40], data[40:300], data[300:]]
    return "<html>" + "".join(f"<script>self.__next_f.push([1,{json.dumps(p)}])</script>" for p in parts) + "</html>"


def test_loppiskartan_reads_the_page_data():
    ms = [market(1, "Loppisen där oppe", "specific", dates=[D1.isoformat()]), market(2, "Myrorna")]
    assert [m["name"] for m in loppiskartan.markets(page(ms))] == ["Loppisen där oppe", "Myrorna"]
    try:
        loppiskartan.markets("<html>Ny sida</html>")
        raise AssertionError("borde ge ett fel")
    except loppiskartan.SourceError as exc:
        assert "Loppiskartan" in str(exc)


def test_loppiskartan_only_flea_markets_with_hours(monkeypatch):
    first = date(2026, 10, 26)                                          # en måndag
    monkeypatch.setattr(loppiskartan, "today", lambda: first)
    monkeypatch.setattr("common.today", lambda: first)
    ms = [
        market(1, "Loppisen där oppe", "specific", dates=["2026-10-31", "2026-08-08"], kommun="Säffle",
               hours_note="Även öppet efter överenskommelse", website="www.example.se"),
        market(2, "Bäverland Loppis & Secondhand", "weekly", week(sunday=("12:00", "17:00"))),
        market(3, "Myrorna", "weekly", week(monday=("10:00", "18:00"))),                  # butik
        market(4, "Röda Korset Second hand Karlstad", "weekly", week(monday=("10:00", "18:00"))),
        market(5, "Lions Loppmarknad"),                                                     # utan öppettider
        market(6, "Loppis Gustav Adolf 44", "weekly", week(friday=("12:00", "16:00")),
               description="Loppis vid Värmlandsgården, öppet fredagar under sommaren."),
        market(7, "Karlstad Loppis AB Bakluckeloppis", "weekly", week(sunday=("10:00", "15:00"))),   # egen källa
    ]
    events = {e["title"]: e for e in Loppiskartan().normalize({"markets": ms})}
    assert set(events) == {"Loppisen där oppe", "Bäverland Loppis & Secondhand"}

    oppe = events["Loppisen där oppe"]
    assert oppe["id"] == "loppiskartan-1" and oppe["url"] == "https://loppiskartan.se/markets/m-1"
    assert oppe["occasions"] == [{"date_start": "2026-10-31", "date_end": "2026-10-31",
                                  "time_start": "11:00", "time_end": "16:00"}]        # passerade datum tas bort
    assert oppe["municipality"] == "Säffle" and oppe["website_link"] == "https://www.example.se"
    assert "Även öppet efter överenskommelse" in oppe["description"]
    assert oppe["categories"][0]["title"] == "Loppis" and oppe["images"] == []

    bv = events["Bäverland Loppis & Secondhand"]
    assert [o["date_start"] for o in bv["occasions"]] == ["2026-11-01", "2026-11-08", "2026-11-15", "2026-11-22"]
    assert bv["next"]["time_start"] == "12:00" and bv["next"]["time_end"] == "17:00"
    assert bv["place"]["address"] == "Östanås 610, 655 98 Molkom" and bv["municipality"] == "Karlstad"


def test_loppiskartan_summer_schedule_only_in_summer(monkeypatch):
    monkeypatch.setattr("common.today", lambda: date(2027, 6, 1))
    m = market(6, "Loppis Gustav Adolf 44", "weekly", week(friday=("12:00", "16:00")),
               description="Öppet fredagar under sommaren.")
    [e] = [x for x in [loppiskartan.normalize_market(m, date(2027, 6, 1))] if x]
    assert [o["date_start"] for o in e["occasions"]][:2] == ["2027-06-04", "2027-06-11"]
    assert loppiskartan.normalize_market(m, date(2026, 10, 26)) is None


def test_loppis_word_does_not_merge_different_flea_markets():
    assert not similar("Z loppis", "Equmenia-scouternas extra-loppis")
    assert not similar("Loppis i Torsby", "Loppis i Sysslebäck")
    assert similar("Hånsfors Bruk, Loppis & Antikt", "Hånsfors Bruk Loppis")


def test_karlstadloppis_next_date(monkeypatch):
    monkeypatch.setattr(karlstadloppis, "today", lambda: date(2026, 9, 25))
    page = ('<div><span><b>Nästa loppis<br>Söndag 27 september.<br></b></span>'
            '<b>Norra fältet infanterigatan 14,65340&nbsp;</b></div>')
    assert karlstadloppis.next_date(page) == date(2026, 9, 27)
    assert karlstadloppis.next_date("Nästa loppis 3 maj") == date(2027, 5, 3)            # passerat i år: nästa år
    assert karlstadloppis.next_date("Nästa loppis Söndag 26 april 2026") == date(2026, 4, 26)
    assert karlstadloppis.next_date("Sommarens första datum kommer nån gång i April") is None
    assert karlstadloppis.next_date("Nästa loppis Söndag 31 september") is None


def test_karlstadloppis_event():
    d = date.today() + timedelta(days=2)
    page = f"<b>Nästa loppis<br>Söndag {d.day} {MONTHS[d.month - 1]} {d.year}.</b>"
    [e] = KarlstadLoppis().normalize({"html": page})
    assert e["title"] == "Bakluckeloppis I2 Norra Fältet" and e["municipality"] == "Karlstad"
    assert e["occasions"] == [{"date_start": d.isoformat(), "date_end": d.isoformat(),
                               "time_start": "10:00", "time_end": "15:00"}]
    assert {c["title"] for c in e["categories"]} == {"Loppis", "Gratis"}
    assert KarlstadLoppis().normalize({"html": "<p>Säsongen är slut</p>"}) == []             # inget fel utanför säsong


def test_flea_markets_from_both_sources_stay_apart():
    d = date.today() + timedelta(days=2)
    kl = KarlstadLoppis().normalize({"html": f"Nästa loppis {d.day} {MONTHS[d.month - 1]} {d.year}"})
    lc = Loppiskartan().normalize({"markets": [market(9, "Z loppis", "specific", dates=[d.isoformat()])]})
    assert len(merge([kl, lc])) == 2


# ---------------------------------------------------------------- Loppis som egen kategori (#44)

def cats(*titles):
    from common import category
    return [category(t) for t in titles]


def titles_after(categories, title, summary=""):
    from categories import split_loppis
    return [c["title"] for c in split_loppis(categories, title, summary)]


def test_loppis_is_split_out_of_the_market_category():
    vv = "Marknad, mässa, auktion och loppis"            # Visit Värmlands namn
    assert titles_after(cats(vv), "Höstloppis i Arenan") == ["Loppis"]
    assert titles_after(cats(vv), "Höstmarknad i Gunnarskog") == ["Marknad, mässa och auktion"]
    assert titles_after(cats(vv), "Höstmarknad", "Marknad med loppis och hantverk") == \
        ["Loppis", "Marknad, mässa och auktion"]                      # båda
    assert titles_after(cats(vv), "Stor barnloppis i Munkfors", "Allt för barn") == ["Loppis"]
    assert titles_after(cats(vv, "Gratis"), "Loppis och skördebord") == ["Loppis", "Gratis"]
    assert titles_after(cats("Övriga evenemang"), "Nördloppis på Ritz") == ["Loppis", "Övrigt"]
    assert titles_after(cats("Musik"), "Konsert", "Efteråt finns en loppis i foajén") == ["Musik"]   # bara ingressen räcker inte
    assert titles_after(cats("Mat och dryck"), "Second hand-mässa") == \
        ["Loppis", "Mat och dryck"]


def test_chat_understands_loppis():
    from chat import find_categories
    assert find_categories("Vilka loppisar finns i helgen?") == {"Loppis"}
    assert find_categories("Finns det någon julmarknad?") == {"Marknad, mässa och auktion"}


# ---------------------------------------------------------------- en källa i gränssnittet (#45)

def test_flea_market_sources_are_shown_as_one(tmp_path, monkeypatch):
    import events
    from test_cleanup import use_tmp_data
    use_tmp_data(tmp_path, monkeypatch)
    d = date.today() + timedelta(days=2)
    monkeypatch.setitem(events._payloads, "karlstadloppis", {"html": f"Nästa loppis {d.day} {MONTHS[d.month - 1]} {d.year}"})
    monkeypatch.setitem(events._payloads, "loppiskartan", {"markets": [market(9, "Z loppis", "specific",
                                                                              dates=[d.isoformat()])]})
    events.rebuild()
    names = {s["name"] for e in events.state["events"] for s in e["sources"]}
    assert names == {"Loppisar"}                                           # ett namn i gränssnittet
    info = events.state["sources"]
    assert info["karlstadloppis"]["group"] == info["loppiskartan"]["group"] == "Loppisar"
    assert info["karlstadloppis"]["count"] == 1 and info["loppiskartan"]["count"] == 1   # status per källa finns kvar
    assert info["visitvarmland"]["group"] == "Visit Värmland"
