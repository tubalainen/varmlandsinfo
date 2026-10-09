"""Dagens slumpade hämtschema (#104)."""

from datetime import date, datetime, time, timedelta

import timetable
from common import TZ

DAY = date(2026, 10, 9)


def at(hour, minute=0, day=DAY):
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def test_parse_window():
    assert timetable.parse_window("08:00-13:00") == (time(8), time(13))
    assert timetable.parse_window("09:30–12:00") == (time(9, 30), time(12))
    for bad in ("", "8", "13:00-08:00", "10:00-10:20", "abc-def"):          # baklänges eller för kort
        assert timetable.parse_window(bad) == (time(8), time(13)), bad


def test_slots_are_random_within_the_window_and_change_every_day():
    keys = [f"k{i}" for i in range(40)]
    plan = timetable.Timetable()
    plan.plan(at(0, 1), keys)
    first = {k: plan.slot(k) for k in keys}
    assert all(at(8) <= t <= at(12, 30) for t in first.values())          # plats för två nya försök före 13
    assert len({t.time() for t in first.values()}) > 30                   # inte alla på samma klockslag
    plan.plan(at(10), keys)                                               # samma dag: samma tider
    assert {k: plan.slot(k) for k in keys} == first
    tomorrow = DAY + timedelta(days=1)
    plan.plan(at(0, 1, tomorrow), keys)
    second = {k: plan.slot(k) for k in keys}
    assert all(t.date() == tomorrow for t in second.values())
    assert sum(first[k].time() == second[k].time() for k in keys) < 5      # nya klockslag varje dag


def test_retries_stay_within_the_window():
    for _ in range(200):
        first = timetable.random_time(at(8), timetable.latest_first_attempt(DAY))
        second = timetable.retry_time(first, 1)
        third = timetable.retry_time(second, 0)
        assert first + timedelta(minutes=15) <= second <= first + timedelta(minutes=25)
        assert second + timedelta(minutes=15) <= third <= at(13)
    late = timetable.retry_time(at(20), 0)                                # hämtning vid start på kvällen
    assert at(20, 15) <= late <= at(20, 25)


def test_jobs_at_start():
    plan = timetable.Timetable()
    now = at(10)
    plan.plan(now, ["new", "old", "later", "missed", "fetched", "done"])
    plan.slots.update(later=at(11).isoformat(), missed=at(9).isoformat(), fetched=at(9).isoformat(),
                      old=at(9).isoformat())
    plan.mark_done("done", at(9, 5))
    yesterday = at(10, day=DAY - timedelta(days=1)).isoformat()
    jobs = plan.jobs_at_start(now, {
        "new": None,                                                      # saknar data: direkt
        "old": at(10, day=DAY - timedelta(days=2)).isoformat(),           # från i förrgår: direkt
        "later": yesterday,                                               # väntar på sin tid
        "missed": yesterday,                                              # appen var avstängd vid tiden
        "fetched": at(9, 30).isoformat(),                                 # redan hämtad efter sin tid
        "done": yesterday,
    })
    by_key = {key: when for when, key, attempt in jobs}
    assert set(by_key) == {"new", "old", "later", "missed"}
    assert by_key["new"] == by_key["old"] == now and by_key["later"] == at(11)
    assert now <= by_key["missed"] <= at(12, 30) and plan.slot("missed") == by_key["missed"]
    assert plan.done_today("fetched", now) and plan.done_today("done", now)
    after = timetable.Timetable()
    after.plan(at(15), ["missed"])
    after.slots["missed"] = at(9).isoformat()
    assert after.jobs_at_start(at(15), {"missed": yesterday}) == [(at(15), "missed", 0)]   # fönstret har passerat


def test_cutoff():
    plan = timetable.Timetable()
    plan.plan(at(10), ["a", "b"])
    plan.mark_done("a", at(9))
    assert plan.cutoff("a", at(10)) == at(0)                              # klar: bara dagens data
    assert plan.cutoff("b", at(10)) == at(0, day=DAY - timedelta(days=1))  # inte klar: gårdagens data får visas


def test_saved_and_loaded(tmp_path):
    plan = timetable.Timetable(tmp_path / "schema.json")
    plan.plan(at(7), ["a", "b"])
    plan.mark_done("a", at(9))
    plan.complete(at(12, 40))
    again = timetable.Timetable(tmp_path / "schema.json")
    again.load()
    assert (again.day, again.slots, again.done, again.completed) == (DAY, plan.slots, plan.done, plan.completed)
    (tmp_path / "schema.json").write_text("trasig")
    broken = timetable.Timetable(tmp_path / "schema.json")
    broken.load()
    assert broken.day is None


def test_schedule_only_shown_locally(monkeypatch):
    """Besökarna ser när allt senast uppdaterades, men aldrig hämtschemat (bara i /api/health, lokalt)."""
    import main
    plan = timetable.Timetable()
    plan.plan(at(7), ["visitvarmland"])
    plan.complete(at(12, 40))
    monkeypatch.setattr(main, "plan", plan)
    public, local = main.status(), main.status(detail=True)
    assert public["completed"] == local["completed"] == at(12, 40).isoformat()
    assert "schedule" not in public and "next_refresh" not in public
    assert local["schedule"]["window"] == "08:00–13:00" and "visitvarmland" in local["schedule"]["slots"]


def test_refresh_waits_for_a_fetch_that_does_not_cover_the_sources(monkeypatch):
    """En hämtning av en källa räcker inte för en begäran om alla källor: den görs efteråt."""
    import asyncio
    import events
    calls = []

    async def fake(keys, include_paused=False):
        calls.append(keys)
        await asyncio.sleep(0.01)

    async def both():
        await asyncio.gather(events.refresh(["scala"]), events.refresh(None), events.refresh(["ccc"]))

    monkeypatch.setattr(events, "_refresh", fake)
    monkeypatch.setattr(events, "_refresh_task", None)
    asyncio.run(both())
    assert calls == [["scala"], None]                                      # CCC ingick i hämtningen av alla
