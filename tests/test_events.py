from datetime import datetime

import events
import main


def raw_event(**kw):
    base = {
        "id": 1, "title": "Test", "sales_text": "<p>Kul &amp; bra</p>", "slug": "evenemang/musik/test",
        "categories": [{"title": "Musik"}], "organizers": [{"title": "Arr", "municipality_id": 9}],
        "places": [], "images": [{"large": "https://img/x.jpg", "alt_text": ""}],
        "occasions": [{"date_start": "2099-01-01", "date_end": "2099-01-01", "time_start": "00:00:00", "time_end": None}],
    }
    return {**base, **kw}


def test_normalize():
    e = events.normalize(raw_event(), {9: "Karlstad"})
    assert e["summary"] == "Kul & bra"
    assert e["municipality"] == "Karlstad"
    assert e["url"] == "https://visitvarmland.com/evenemang/musik/test"
    assert e["next"]["time_start"] is None  # 00:00 utan sluttid = tid ej angiven
    assert e["images"][0]["medium"] == "https://img/x.jpg"


def test_normalize_drops_past_events_and_unsafe_links():
    past = raw_event(occasions=[{"date_start": "2000-01-01", "date_end": "2000-01-01"}])
    assert events.normalize(past, {}) is None
    e = events.normalize(raw_event(booking_link="javascript:alert(1)"), {})
    assert e["booking_link"] is None


def test_next_run_daily():
    tz = events.TZ
    assert main.next_run(datetime(2026, 9, 24, 4, 0, tzinfo=tz)) == datetime(2026, 9, 24, 5, 0, tzinfo=tz)
    assert main.next_run(datetime(2026, 9, 24, 6, 0, tzinfo=tz)) == datetime(2026, 9, 25, 5, 0, tzinfo=tz)
