import asyncio
from datetime import datetime, timedelta

import httpx

import events
import main


def run(coro):
    return asyncio.run(coro)


def client_with(responses):
    calls = []

    def handler(request):
        calls.append(request.url)
        return responses.pop(0)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


def test_get_json_retries_after_429(monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    monkeypatch.setattr(events.asyncio, "sleep", fake_sleep)
    client, calls = client_with([
        httpx.Response(429, headers={"retry-after": "7"}),
        httpx.Response(200, json={"data": []}, headers={"x-ratelimit-remaining": "50"}),
    ])
    assert run(events.get_json(client, "events")) == {"data": []}
    assert len(calls) == 2
    assert slept == [7]


def test_get_json_pauses_when_quota_low(monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    monkeypatch.setattr(events.asyncio, "sleep", fake_sleep)
    client, _ = client_with([httpx.Response(200, json={}, headers={"x-ratelimit-remaining": "2"})])
    run(events.get_json(client, "events"))
    assert slept == [60]


def test_get_json_gives_up(monkeypatch):
    async def fake_sleep(s):
        pass

    monkeypatch.setattr(events.asyncio, "sleep", fake_sleep)
    client, calls = client_with([httpx.Response(429) for _ in range(events.MAX_RETRIES + 1)])
    try:
        run(events.get_json(client, "events"))
        assert False, "borde ha gett upp"
    except RuntimeError:
        pass
    assert len(calls) == events.MAX_RETRIES + 1


def test_manual_refresh_is_throttled(monkeypatch):
    called = []

    async def fake_refresh():
        called.append(1)

    monkeypatch.setattr(events, "refresh", fake_refresh)
    recent = (datetime.now(events.TZ) - timedelta(minutes=1)).isoformat()
    monkeypatch.setitem(events.state, "updated", recent)
    monkeypatch.setitem(events.state, "error", None)
    assert run(events.manual_refresh())  # hoppas över
    assert called == []

    old = (datetime.now(events.TZ) - timedelta(minutes=10)).isoformat()
    monkeypatch.setitem(events.state, "updated", old)
    assert run(events.manual_refresh()) is None
    assert called == [1]


def test_refresh_minutes_has_floor(monkeypatch):
    for raw, expected in [("0", 0), ("", 0), ("abc", 0), ("5", 30), ("45", 45), ("-3", 0)]:
        monkeypatch.setenv("REFRESH_MINUTES", raw)
        assert main._refresh_minutes() == expected, raw
