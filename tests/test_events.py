import json
from datetime import datetime

import events
import main
from sources.visitvarmland import normalize_event


def raw_event(**kw):
    base = {
        "id": 1, "title": "Test", "sales_text": "<p>Kul &amp; bra</p>", "slug": "evenemang/musik/test",
        "categories": [{"title": "Musik"}], "organizers": [{"title": "Arr", "municipality_id": 9}],
        "places": [], "images": [{"large": "https://img/x.jpg", "alt_text": ""}],
        "occasions": [{"date_start": "2099-01-01", "date_end": "2099-01-01", "time_start": "00:00:00", "time_end": None}],
    }
    return {**base, **kw}


def test_normalize():
    e = normalize_event(raw_event(), {9: "Karlstad"})
    assert e["id"] == "vv-1"
    assert e["summary"] == "Kul & bra"
    assert e["municipality"] == "Karlstad"
    assert e["url"] == "https://visitvarmland.com/evenemang/musik/test"
    assert e["next"]["time_start"] is None  # 00:00 utan sluttid = tid ej angiven
    assert e["images"][0]["medium"] == "https://img/x.jpg"
    assert e["sources"] == [{"name": "Visit Värmland", "url": e["url"]}]


def test_normalize_drops_past_events_and_unsafe_links():
    past = raw_event(occasions=[{"date_start": "2000-01-01", "date_end": "2000-01-01"}])
    assert normalize_event(past, {}) is None
    e = normalize_event(raw_event(booking_link="javascript:alert(1)"), {})
    assert e["booking_link"] is None


def use_tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(events, "_payloads", {})
    for info in events.state["sources"].values():
        monkeypatch.setitem(info, "updated", None)


def test_cache_roundtrip(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    payload = {"municipalities": {9: "Karlstad"}, "municipalities_updated": None, "events": [raw_event()]}
    events.save_cache("visitvarmland", payload, "2026-09-24T05:00:00+02:00")
    assert events.cache_file("visitvarmland").exists()
    assert not list((tmp_path / "data").glob("*.tmp"))

    assert events.load_cache() is True
    assert events.state["sources"]["visitvarmland"]["updated"] == "2026-09-24T05:00:00+02:00"
    assert events.state["sources"]["visitvarmland"]["count"] == 1
    assert events.state["events"][0]["municipality"] == "Karlstad"


def test_load_cache_reads_format_from_0_0_1(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    (tmp_path / "data").mkdir()
    old = {"format": 1, "updated": "2026-09-24T05:00:00+02:00", "municipalities": {"9": "Karlstad"},
           "municipalities_updated": "2026-09-24T05:00:00+02:00", "events": [raw_event()]}
    events.cache_file("visitvarmland").write_text(json.dumps(old))
    assert events.load_cache() is True
    assert events.state["events"][0]["municipality"] == "Karlstad"


def test_load_cache_handles_missing_and_broken_file(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    assert events.load_cache() is False
    (tmp_path / "data").mkdir()
    events.cache_file("visitvarmland").write_text("{trasig")
    assert events.load_cache() is False


def test_save_cache_survives_unwritable_dir(tmp_path, monkeypatch):
    blocker = tmp_path / "fil"
    blocker.write_text("")
    monkeypatch.setattr(events, "DATA_DIR", blocker / "data")  # kan inte skapas
    events.save_cache("visitvarmland", {}, "2026-09-24T05:00:00+02:00")
    assert events.state["storage_error"]
    events.state["storage_error"] = None


def test_stale_sources_only_enabled(monkeypatch):
    for key, info in events.state["sources"].items():
        monkeypatch.setitem(info, "updated", "2026-09-24T06:00:00+02:00" if key == "shl" else None)
    monkeypatch.setitem(events.state["sources"]["ticketmaster"], "enabled", False)
    stale = events.stale_sources(lambda updated: updated is None)
    assert stale == ["visitvarmland", "ccc", "scala"]   # SHL är aktuell, Ticketmaster avstängd


def test_needs_refresh():
    tz = events.TZ
    now = datetime(2026, 9, 24, 14, 0, tzinfo=tz)
    assert main.needs_refresh(None, now)
    assert not main.needs_refresh("2026-09-24T06:00:00+02:00", now)  # efter dagens 05:00
    assert main.needs_refresh("2026-09-24T04:00:00+02:00", now)      # före dagens 05:00
    early = datetime(2026, 9, 24, 3, 0, tzinfo=tz)
    assert not main.needs_refresh("2026-09-23T06:00:00+02:00", early)  # efter gårdagens 05:00


def test_next_run_daily():
    tz = events.TZ
    assert main.next_run(datetime(2026, 9, 24, 4, 0, tzinfo=tz)) == datetime(2026, 9, 24, 5, 0, tzinfo=tz)
    assert main.next_run(datetime(2026, 9, 24, 6, 0, tzinfo=tz)) == datetime(2026, 9, 25, 5, 0, tzinfo=tz)
