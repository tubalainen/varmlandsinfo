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


def test_errors_never_contain_query_string(monkeypatch):
    async def no_sleep(s):
        pass
    monkeypatch.setattr(common.asyncio, "sleep", no_sleep)
    client, _ = client_with([httpx.Response(401), httpx.Response(500), httpx.Response(500)])   # 5xx: ett nytt försök
    for _ in range(2):
        try:
            run(common.get_json(client, "https://api.test/events", "Test", apikey="HEMLIG"))
            assert False
        except common.SourceError as exc:
            assert "HEMLIG" not in str(exc)
            assert "apikey" not in str(exc)


def test_server_errors_are_retried_once(monkeypatch):
    """Serverfel (HTTP 5xx) är ofta tillfälliga: ett nytt försök efter en kort paus (#75)."""
    slept = []

    async def fake_sleep(s):
        slept.append(s)
    monkeypatch.setattr(common.asyncio, "sleep", fake_sleep)
    before = common.stats["api_calls"]

    client, calls = client_with([httpx.Response(500), httpx.Response(200, json={"ok": True})])
    assert run(common.get_json(client, "https://api.test/events?apikey=HEMLIG", "Test")) == {"ok": True}
    assert len(calls) == 2 and slept == [common.SERVER_ERROR_RETRY_DELAY]
    assert common.stats["api_calls"] - before == 2

    client, calls = client_with([httpx.Response(503), httpx.Response(502)])
    try:
        run(common.get_json(client, "https://api.test/events?apikey=HEMLIG", "Test"))
    except common.SourceError as exc:
        assert "HTTP 502" in str(exc) and "HEMLIG" not in str(exc)
    else:
        raise AssertionError("inget fel")
    assert len(calls) == 2                                          # bara ett nytt försök

    for call in (lambda c: common.get_text(c, "https://x.test/sida", "Test"),
                 lambda c: common.post_form(c, "https://x.test/sida", {"a": "1"}, "Test"),
                 lambda c: common.post_json(c, "https://x.test/sida", {"a": 1}, "Test")):
        client, calls = client_with([httpx.Response(500), httpx.Response(200, json={"ok": 1}, text=None)])
        run(call(client))
        assert len(calls) == 2


def test_client_errors_are_not_retried(monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)
    monkeypatch.setattr(common.asyncio, "sleep", fake_sleep)
    client, calls = client_with([httpx.Response(404), httpx.Response(200, text="ok")])
    try:
        run(common.get_text(client, "https://x.test/sida", "Test"))
    except common.SourceError as exc:
        assert "HTTP 404" in str(exc)
    else:
        raise AssertionError("inget fel")
    assert len(calls) == 1 and slept == []
