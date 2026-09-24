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


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(events, "CACHE_FILE", tmp_path / "data" / "visitvarmland.json")
    events.save_cache([raw_event()], {9: "Karlstad"}, "2026-09-24T05:00:00+02:00")
    assert events.CACHE_FILE.exists()
    assert not list((tmp_path / "data").glob("*.tmp"))

    events.state.update(events=[], municipalities={}, updated=None)
    assert events.load_cache() is True
    assert events.state["updated"] == "2026-09-24T05:00:00+02:00"
    assert events.state["municipalities"] == {9: "Karlstad"}
    assert events.state["events"][0]["municipality"] == "Karlstad"


def test_load_cache_handles_missing_and_broken_file(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "CACHE_FILE", tmp_path / "visitvarmland.json")
    assert events.load_cache() is False
    events.CACHE_FILE.write_text("{trasig")
    assert events.load_cache() is False


def test_save_cache_survives_unwritable_dir(tmp_path, monkeypatch):
    blocker = tmp_path / "fil"
    blocker.write_text("")
    monkeypatch.setattr(events, "DATA_DIR", blocker / "data")  # kan inte skapas
    monkeypatch.setattr(events, "CACHE_FILE", blocker / "data" / "visitvarmland.json")
    events.save_cache([], {}, "2026-09-24T05:00:00+02:00")
    assert events.state["storage_error"]
    events.state["storage_error"] = None


def test_needs_refresh():
    tz = events.TZ
    now = datetime(2026, 9, 24, 14, 0, tzinfo=tz)
    assert main.needs_refresh(None, now)
    assert not main.needs_refresh("2026-09-24T06:00:00+02:00", now)  # efter dagens 05:00
    assert main.needs_refresh("2026-09-24T04:00:00+02:00", now)      # före dagens 05:00
    early = datetime(2026, 9, 24, 3, 0, tzinfo=tz)
    assert not main.needs_refresh("2026-09-23T06:00:00+02:00", early)  # efter gårdagens 05:00
