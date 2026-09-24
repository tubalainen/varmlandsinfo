import asyncio
from datetime import datetime, timedelta

import httpx

import common
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

    monkeypatch.setattr(common.asyncio, "sleep", fake_sleep)
    client, calls = client_with([
        httpx.Response(429, headers={"retry-after": "7"}),
        httpx.Response(200, json={"data": []}, headers={"x-ratelimit-remaining": "50"}),
    ])
    assert run(common.get_json(client, "https://api.test/events", "Test")) == {"data": []}
    assert len(calls) == 2
    assert slept == [7]


def test_get_json_pauses_when_quota_low(monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    monkeypatch.setattr(common.asyncio, "sleep", fake_sleep)
    client, _ = client_with([httpx.Response(200, json={}, headers={"x-ratelimit-remaining": "2"})])
    run(common.get_json(client, "https://api.test/events", "Test"))
    assert slept == [60]


def test_get_json_gives_up(monkeypatch):
    async def fake_sleep(s):
        pass

    monkeypatch.setattr(common.asyncio, "sleep", fake_sleep)
    client, calls = client_with([httpx.Response(429) for _ in range(common.MAX_RETRIES + 1)])
    try:
        run(common.get_json(client, "https://api.test/events", "Test"))
        assert False, "borde ha gett upp"
    except common.SourceError:
        pass
    assert len(calls) == common.MAX_RETRIES + 1


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


def test_errors_never_contain_query_string():
    client, _ = client_with([httpx.Response(401), httpx.Response(500)])
    for _ in range(2):
        try:
            run(common.get_json(client, "https://api.test/events", "Test", apikey="HEMLIG"))
            assert False
        except common.SourceError as exc:
            assert "HEMLIG" not in str(exc)
            assert "apikey" not in str(exc)
