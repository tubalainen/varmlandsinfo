"""Städning av gammal data vid morgonkörningen (#42)."""

import asyncio
import json
from datetime import date, datetime

import chat
import events
import main
import sessions
from chat_cache import AnswerCache
from test_events import raw_event
from test_events import use_tmp_data as _use_tmp_data

TZ = events.TZ
MORNING = datetime(2026, 9, 25, 5, 0, tzinfo=TZ)
YESTERDAY = "2026-09-24T05:10:00+02:00"
TODAY = "2026-09-25T05:01:00+02:00"


def use_tmp_data(tmp_path, monkeypatch):
    """Tom datakatalog, och källornas status återställs efter testet."""
    _use_tmp_data(tmp_path, monkeypatch)
    for info in events.state["sources"].values():
        for key in ("error", "enabled", "count"):
            monkeypatch.setitem(info, key, info[key])
        monkeypatch.setitem(info, "error", None)
    monkeypatch.setitem(events.state, "events", [])


def vv_payload():
    return {"municipalities": {9: "Karlstad"}, "municipalities_updated": None, "events": [raw_event()]}


def test_last_daily_run():
    assert main.last_daily_run(datetime(2026, 9, 25, 14, 0, tzinfo=TZ)) == MORNING
    assert main.last_daily_run(datetime(2026, 9, 25, 3, 0, tzinfo=TZ)) == datetime(2026, 9, 24, 5, 0, tzinfo=TZ)


def test_purge_removes_data_older_than_the_morning_run(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    events.save_cache("visitvarmland", vv_payload(), TODAY)
    events.save_cache("scala", {"pages": []}, YESTERDAY)
    (tmp_path / "data" / "ccc.json.tmp").write_text("halvskriven")
    (tmp_path / "data" / "annat.json").write_text("{}")                   # andra filer rörs inte
    events.load_cache()
    monkeypatch.setitem(events.state["sources"]["scala"], "error", "Kunde inte nå Scalateatern")

    assert events.purge_old(MORNING) == ["scala"]
    files = sorted(p.name for p in (tmp_path / "data").iterdir())
    assert files == ["annat.json", "visitvarmland.json"]
    assert "scala" not in events._payloads and events.state["sources"]["scala"]["updated"] is None
    assert events.state["sources"]["scala"]["error"] == "Kunde inte nå Scalateatern"
    assert events.state["sources"]["visitvarmland"]["count"] == 1
    assert events.purge_old(MORNING) == []                                # inget kvar att städa


def test_purge_sets_error_so_the_source_is_retried(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    events.save_cache("ccc", {"html": ""}, YESTERDAY)
    events.load_cache()
    events.purge_old(MORNING)
    assert events.state["sources"]["ccc"]["error"].startswith("Ingen aktuell data")
    assert "ccc" in main.failed_sources()


def test_disabled_source_is_neither_loaded_nor_kept(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    monkeypatch.setitem(events.state["sources"]["visitvarmland"], "enabled", False)
    events.save_cache("visitvarmland", vv_payload(), TODAY)
    events.load_cache()
    assert events.state["sources"]["visitvarmland"]["count"] == 0          # visas inte
    assert events.purge_old(MORNING) == ["visitvarmland"]
    assert not events.cache_file("visitvarmland").exists()


def test_answer_cache_keeps_only_valid_answers(tmp_path):
    c = AnswerCache(tmp_path / "c.json")
    old = {"day": "2026-09-24", "data": YESTERDAY, "model": "m"}
    new = {"day": "2026-09-25", "data": TODAY, "model": "m"}
    c.put("Vad händer idag?", old, "gammalt", [], preset=True)
    c.put("Egen fråga", old, "gammalt", [], preset=False)
    c.put("Vad händer i helgen?", new, "nytt", [], preset=True)
    assert c.prune(new) == 2
    saved = json.loads((tmp_path / "c.json").read_text())
    assert list(saved["presets"]) == ["vad händer i helgen"] and saved["recent"] == []
    assert c.prune(new) == 0


def test_clear_sessions_keeps_the_one_answering():
    store = sessions.SessionStore()
    a, _ = store.get_or_create(None)
    b, _ = store.get_or_create(None)
    store.begin(b)
    assert store.clear() == 1
    assert store.get(a.id) is None and store.get(b.id) is b


def test_morning_run_retries_then_cleans_up(monkeypatch, tmp_path):
    calls = []

    async def fake_refresh(keys=None):
        calls.append(keys)
        # Scalateatern svarar först på tredje försöket, CCC aldrig
        for key, info in events.state["sources"].items():
            if keys is None or key in keys:
                ok = key != "ccc" and not (key == "scala" and len(calls) < 3)
                info["error"] = None if ok else "fel"

    cleaned = []
    monkeypatch.setattr(main, "MORNING_RETRY_DELAY", main.timedelta(0))
    monkeypatch.setattr(main.events, "refresh", fake_refresh)
    monkeypatch.setattr(main, "cleanup", lambda now, conversations=False: cleaned.append(conversations))
    use_tmp_data(tmp_path, monkeypatch)
    asyncio.run(main.morning_run())
    assert calls == [None, ["ccc", "scala"], ["ccc", "scala"]]
    assert cleaned == [True]                                               # städning och rensade samtal efteråt


def test_cleanup_prunes_everything(monkeypatch, tmp_path):
    use_tmp_data(tmp_path, monkeypatch)
    c = AnswerCache(tmp_path / "c.json")
    c.put("Vad händer idag?", {"day": "2026-09-24", "data": YESTERDAY, "model": chat.OLLAMA_MODEL}, "gammalt", [], True)
    monkeypatch.setattr(chat, "cache", c)
    monkeypatch.setattr(sessions, "store", sessions.SessionStore())
    sessions.store.get_or_create(None)
    monkeypatch.setattr(events, "today", lambda: date(2026, 9, 25))
    monkeypatch.setitem(events.state, "updated", TODAY)
    main.cleanup(datetime(2026, 9, 25, 5, 3, tzinfo=TZ), conversations=True)
    assert c.presets == {} and len(sessions.store) == 0
