import json

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
    assert stale == ["visitvarmland", "ccc", "scala", "bandy", "handboll", "greatevent", "karlstadloppis", "loppisar",
                     "sbf", "svemo", "saffle", "kil", "skoghall", "riksteatern"]   # SHL är aktuell, Ticketmaster avstängd


def test_index_references_versioned_assets():
    from version import __version__
    html = main.INDEX_HTML[True]
    assert f'/static/style.css?v={__version__}"' in html
    assert f'/static/app.js?v={__version__}"' in html
    assert f'/manifest.webmanifest?v={__version__}"' in html
    assert 'href="/static/style.css"' not in html


def test_cache_headers():
    from fastapi.testclient import TestClient
    from version import __version__
    client = TestClient(main.app)   # utan "with": startar inte schemaläggaren
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert "immutable" in client.get(f"/static/style.css?v={__version__}").headers["cache-control"]
    assert client.get("/static/style.css").headers["cache-control"] == "no-cache"
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_refresh_pauses_sources_that_deny_access(monkeypatch):
    """401/403 kan betyda att appen är spärrad: källan hämtas inte igen förrän vid nästa dags hämtning (#76)."""
    import asyncio
    from common import AccessDenied

    class Denied:
        key, title, homepage = "fake", "Fejk", "https://x"
        calls = 0

        async def fetch(self, client, previous):
            Denied.calls += 1
            if Denied.calls == 1:
                raise AccessDenied("Fejk nekade åtkomst (HTTP 403). Källan pausas till nästa dags hämtning.")
            return {"events": []}

        def normalize(self, payload):
            return []

    info = {"title": "Fejk", "group": "Fejk", "homepage": "https://x", "enabled": True, "config_error": None,
            "count": 0, "updated": None, "error": None, "paused": False}
    monkeypatch.setattr(events, "SOURCES", [Denied()])
    monkeypatch.setitem(events.state, "sources", {"fake": info})
    monkeypatch.setattr(events, "save_cache", lambda *a: None)
    monkeypatch.setattr(events, "rebuild", lambda: None)

    asyncio.run(events._refresh(None))
    assert info["paused"] and "pausas" in info["error"] and Denied.calls == 1
    asyncio.run(events._refresh(None))                       # manuell eller schemalagd uppdatering: hoppas över
    assert Denied.calls == 1
    asyncio.run(events._refresh(None, include_paused=True))  # dagens första försök
    assert Denied.calls == 2 and not info["paused"] and info["error"] is None
