"""Städning av gammal data efter hämtningarna (#42, #104)."""

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
MIDNIGHT = datetime(2026, 9, 25, 0, 0, tzinfo=TZ)
YESTERDAY = "2026-09-24T09:10:00+02:00"
TODAY = "2026-09-25T09:01:00+02:00"


def before_today(key):
    return MIDNIGHT


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


def test_purge_removes_data_older_than_the_cutoff(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    events.save_cache("visitvarmland", vv_payload(), TODAY)
    events.save_cache("scala", {"pages": []}, YESTERDAY)
    (tmp_path / "data" / "ccc.json.tmp").write_text("halvskriven")
    (tmp_path / "data" / "annat.json").write_text("{}")                   # andra filer rörs inte
    events.load_cache()
    monkeypatch.setitem(events.state["sources"]["scala"], "error", "Kunde inte nå Scalateatern")

    assert events.purge_old(before_today) == ["scala"]
    files = sorted(p.name for p in (tmp_path / "data").iterdir())
    assert files == ["annat.json", "visitvarmland.json"]
    assert "scala" not in events._payloads and events.state["sources"]["scala"]["updated"] is None
    assert events.state["sources"]["scala"]["error"] == "Kunde inte nå Scalateatern"
    assert events.state["sources"]["visitvarmland"]["count"] == 1
    assert events.purge_old(before_today) == []                                # inget kvar att städa


def test_purge_sets_error_so_the_source_is_retried(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    events.save_cache("ccc", {"html": ""}, YESTERDAY)
    events.load_cache()
    events.purge_old(before_today)
    assert events.state["sources"]["ccc"]["error"] == "Ingen aktuell data: källan kunde inte hämtas i dag"


def test_disabled_source_is_neither_loaded_nor_kept(tmp_path, monkeypatch):
    use_tmp_data(tmp_path, monkeypatch)
    monkeypatch.setitem(events.state["sources"]["visitvarmland"], "enabled", False)
    events.save_cache("visitvarmland", vv_payload(), TODAY)
    events.load_cache()
    assert events.state["sources"]["visitvarmland"]["count"] == 0          # visas inte
    assert events.purge_old(before_today) == ["visitvarmland"]
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


def test_cleanup_keeps_yesterdays_data_until_todays_fetch_is_done(monkeypatch, tmp_path):
    """Gårdagens data visas tills källan hämtats i dag. Misslyckas dagens hämtning tas den bort (#104)."""
    use_tmp_data(tmp_path, monkeypatch)
    plan = main.timetable.Timetable()
    monkeypatch.setattr(main, "plan", plan)
    events.save_cache("ccc", {"html": ""}, YESTERDAY)
    events.save_cache("scala", {"pages": []}, "2026-09-23T09:00:00+02:00")   # från i förrgår
    events.load_cache()
    now = datetime(2026, 9, 25, 9, 30, tzinfo=TZ)
    plan.plan(now, ["ccc", "scala"])
    main.cleanup(now)
    assert events.cache_file("ccc").exists() and not events.cache_file("scala").exists()
    plan.mark_done("ccc", now)                                          # dagens hämtning misslyckades
    main.cleanup(now)
    assert not events.cache_file("ccc").exists()


def test_fetch_retries_then_cleans_up(monkeypatch, tmp_path):
    """Högst två nya försök per källa och dag, inga när källan är pausad. När alla källor är klara är
    informationen uppdaterad i sin helhet och chattsamtalen städas bort."""
    calls = []

    async def fake_refresh(keys=None, include_paused=False):
        calls.append((keys, include_paused))
        info = events.state["sources"][keys[0]]
        info["error"] = None if keys == ["scala"] and len(calls) >= 3 else "fel"
        info["paused"] = keys == ["sbf"]

    async def no_geoip():
        pass

    cleaned = []
    use_tmp_data(tmp_path, monkeypatch)
    for key, info in events.state["sources"].items():
        monkeypatch.setitem(info, "paused", False)
        monkeypatch.setitem(info, "enabled", key in ("scala", "sbf"))
    plan = main.timetable.Timetable()
    monkeypatch.setattr(main, "plan", plan)
    monkeypatch.setattr(main.events, "refresh", fake_refresh)
    monkeypatch.setattr(main, "update_geoip", no_geoip)
    monkeypatch.setattr(main, "cleanup", lambda now, conversations=False: cleaned.append(conversations))
    now = datetime.now(TZ)
    plan.plan(now, ["scala", "sbf"])

    first = asyncio.run(main.fetch("scala", 0))
    assert first[1:] == ("scala", 1) and first[0] >= now + main.timetable.RETRY_DELAY
    assert asyncio.run(main.fetch("scala", 1))[1:] == ("scala", 2)
    assert asyncio.run(main.fetch("scala", 2)) is None                  # lyckades på tredje försöket
    assert asyncio.run(main.fetch("sbf", 0)) is None                    # pausad: inga nya försök
    assert calls == [(["scala"], True), (["scala"], False), (["scala"], False), (["sbf"], True)]
    assert cleaned == [False, False, False, True]                       # samtalen städas när allt är klart
    assert plan.completed and plan.all_done(["scala", "sbf"], datetime.now(TZ))


def test_cleanup_prunes_everything(monkeypatch, tmp_path):
    use_tmp_data(tmp_path, monkeypatch)
    c = AnswerCache(tmp_path / "c.json")
    c.put("Vad händer idag?", {"day": "2026-09-24", "data": YESTERDAY, "model": chat.OLLAMA_MODEL}, "gammalt", [], True)
    monkeypatch.setattr(chat, "cache", c)
    monkeypatch.setattr(sessions, "store", sessions.SessionStore())
    sessions.store.get_or_create(None)
    monkeypatch.setattr(events, "today", lambda: date(2026, 9, 25))
    monkeypatch.setitem(events.state, "updated", TODAY)
    main.cleanup(datetime(2026, 9, 25, 9, 3, tzinfo=TZ), conversations=True)
    assert c.presets == {} and len(sessions.store) == 0


def test_cleanup_after_each_fetch_removes_stale_data(monkeypatch, tmp_path):
    """Efter varje hämtning (inte bara morgonkörningen) rensas utgångna samtal, IP-adresser som inte längre räknas
    i spärren, bilder utan evenemang och halvfärdiga bildfiler (#62)."""
    import access
    import images
    use_tmp_data(tmp_path, monkeypatch)
    clock = [0.0]
    store = sessions.SessionStore(ttl=100, clock=lambda: clock[0])
    old, _ = store.get_or_create(None)
    monkeypatch.setattr(sessions, "store", store)
    limiter = access.IpLimiter(window=60, clock=lambda: clock[0])
    limiter.allow("81.230.12.4")
    monkeypatch.setattr(access, "chat_limiter", limiter)
    proxy = images.ImageProxy(tmp_path / "images")
    (tmp_path / "images").mkdir()
    for name in ("a" * 32, "b" * 32 + ".tmp"):
        (tmp_path / "images" / name).write_bytes(b"x")
    monkeypatch.setattr(main, "image_proxy", proxy)

    clock[0] = 50
    fresh, _ = store.get_or_create(None)
    main.cleanup(datetime(2026, 9, 25, 12, 0, tzinfo=TZ))                # t.ex. efter en extra uppdatering
    assert len(limiter) == 1 and len(store) == 2                         # inget har hunnit bli inaktuellt
    assert list((tmp_path / "images").iterdir()) == []                   # bilder utan evenemang och .tmp-filer

    clock[0] = 120
    main.cleanup(datetime(2026, 9, 25, 12, 30, tzinfo=TZ))
    assert len(limiter) == 0                                             # IP-adressen räknas inte längre
    assert store.get(old.id) is None and store.get(fresh.id) is not None  # bara det utgångna samtalet


def test_manual_refresh_cleans_up(monkeypatch):
    calls = []
    async def refresh():
        return None
    monkeypatch.setattr(events, "manual_refresh", refresh)
    monkeypatch.setattr(main, "cleanup", lambda now, conversations=False: calls.append(now))
    monkeypatch.setattr(main.access, "is_local", lambda r: True)
    monkeypatch.setattr(main, "plan", main.timetable.Timetable())
    from fastapi.testclient import TestClient
    data = TestClient(main.app).post("/api/refresh").json()
    assert len(calls) == 1
    assert data["completed"] == main.plan.completed is not None              # allt hämtades nyss
