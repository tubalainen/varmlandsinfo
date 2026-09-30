"""Åtkomst till API:t: lokala adresser, omvända proxyer och spärren per IP i Fråga AI (#56)."""

import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import access
import chat
import events
import main
import sessions
from sessions import SessionStore


def request(host, headers=None):
    return Request({"type": "http", "method": "GET", "path": "/", "client": (host, 50000) if host else None,
                    "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]})


def test_local_addresses():
    for host in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        assert access.is_local(request(host)), host
    # Det lokala nätverket och Dockers bryggnät räknas inte som lokala (#86)
    for host in ("192.168.1.20", "10.0.0.5", "172.17.0.1", "::ffff:192.168.1.20", "fd00::1",
                 "81.230.12.4", "2a00:1450::1", "testclient", None, "0.0.0.0"):
        assert not access.is_local(request(host)), host


def test_reverse_proxy_is_never_local():
    for header in ("X-Forwarded-For", "Forwarded", "X-Real-IP", "CF-Connecting-IP"):
        assert not access.is_local(request("172.18.0.2", {header: "81.230.12.4"})), header


def test_client_ip():
    assert access.client_ip(request("81.230.12.4")) == "81.230.12.4"
    # Via en lokal proxy: adressen som proxyn lade till sist, inte den som klienten själv skickat
    assert access.client_ip(request("172.18.0.2", {"X-Forwarded-For": "1.2.3.4, 81.230.12.4"})) == "81.230.12.4"
    # Direkt från internet kan huvudet förfalskas och räknas inte
    assert access.client_ip(request("81.230.12.4", {"X-Forwarded-For": "1.2.3.4"})) == "81.230.12.4"
    assert access.client_ip(request("172.18.0.2", {"X-Forwarded-For": "skräp"})) == "172.18.0.2"


def test_ip_limiter():
    now = [0.0]
    limiter = access.IpLimiter(limit=2, window=60, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")
    now[0] = 20
    assert limiter.wait("a") == 40 and limiter.wait("b") == 0
    now[0] = 61
    assert limiter.wait("a") == 0 and limiter.allow("a")
    assert (access.IP_RATE_LIMIT, access.IP_RATE_WINDOW) == (20, 30 * 60)


def test_docs_are_closed():
    client = TestClient(main.app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_admin_endpoints_only_locally(monkeypatch):
    client = TestClient(main.app)   # klientens adress är "testclient", alltså inte lokal
    assert client.get("/api/health").status_code == 403
    assert client.post("/api/refresh").status_code == 403
    monkeypatch.setattr(access, "is_local", lambda r: True)
    assert client.get("/api/health").json()["ok"]
    assert client.get("/api/events").status_code == 200    # gränssnittets data är alltid öppen


def test_admin_endpoints_only_from_inside_the_container():
    """Bara loopback (healthcheck och docker exec), inte det lokala nätverket eller Dockers bryggnät (#86)."""
    for host in ("192.168.1.20", "172.17.0.1", "fd00::1"):
        client = TestClient(main.app, client=(host, 50000))
        assert client.get("/api/health").status_code == 403, host
        assert client.post("/api/refresh").status_code == 403, host
    local = TestClient(main.app, client=("127.0.0.1", 50000))
    assert local.get("/api/health").json()["ok"]
    assert local.get("/api/health", headers={"X-Forwarded-For": "81.230.12.4"}).status_code == 403


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(sessions, "store", SessionStore())
    monkeypatch.setattr(access, "chat_limiter", access.IpLimiter(limit=3))
    monkeypatch.setattr(chat, "cache", None)
    monkeypatch.setattr(events, "current_events", lambda: [])
    return TestClient(main.app)


def test_chat_is_limited_per_ip_even_with_new_sessions(client, monkeypatch):
    from test_sessions import fake_ai
    fake_ai(monkeypatch)
    last = [client.post("/api/chat", json={"question": "Vad passar en 8-åring?"}).text.splitlines()[-1]
            for _ in range(4)]
    assert ["error" in x for x in last] == [False, False, False, True]
    assert "från din adress" in json.loads(last[-1])["error"]


def test_questions_without_ai_are_not_limited_per_ip(client):
    for _ in range(6):
        r = client.post("/api/chat", json={"question": "Vad händer idag?"})
        assert r.status_code == 200 and '"mode": "search"' in r.text.splitlines()[-1]


def test_chat_can_be_turned_off(client, monkeypatch):
    """CHAT_ENABLED=false: Fråga AI syns inte i gränssnittet och API:t för chatten finns inte."""
    page = client.get("/").text
    assert 'href="#/fraga"' in page and "/static/chat.js" in page
    assert client.get("/api/events").json()["chat"]["visible"] is True

    monkeypatch.setattr(chat, "CHAT_ENABLED", False)
    page = client.get("/").text
    assert 'href="#/fraga"' not in page and "/static/chat.js" not in page and 'data-chat="off"' in page
    assert 'href="#/kalender"' in page and "/static/app.js" in page
    assert client.get("/api/events").json()["chat"] == {"visible": False, "enabled": False, "model": None,
                                                         "websearch": False}
    for method, path in (("get", "/api/chat/presets"), ("get", "/api/chat/status"), ("get", "/api/chat/session"),
                         ("delete", "/api/chat/session")):
        assert getattr(client, method)(path).status_code == 404, path
    assert client.post("/api/chat", json={"question": "Vad händer idag?"}).status_code == 404


def test_chat_flag(monkeypatch):
    for value, expected in (("", True), ("true", True), ("1", True), ("false", False), ("False", False), ("0", False),
                            ("nej", False), ("off", False)):
        monkeypatch.setenv("X_FLAG", value)
        assert chat.flag("X_FLAG") is expected, value
