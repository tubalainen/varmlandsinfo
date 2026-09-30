"""Säkerhetsåtgärder efter säkerhetsanalysen (#85–#92)."""

import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import chat
import events
import main
from test_followups import CONVERSATION, EVENTS, SOURCES, THU
from version import __version__


def test_many_ranges_are_answered_quickly():
    """CVE-2025-62727: ett Range-huvud med många intervall fick Starlette att räkna i kvadratisk tid (#85)."""
    client = TestClient(main.app)
    ranges = ",".join(f"{i}-{i}" for i in range(0, 20000, 2))
    start = time.monotonic()
    r = client.get("/static/app.js", headers={"Range": f"bytes={ranges}"})
    assert time.monotonic() - start < 2
    assert r.status_code in (200, 206, 416)


def test_api_is_never_cached_whatever_the_host():
    """Cache-Control väljs efter den råa sökvägen, inte efter en adress som byggs av Host-huvudet (CVE-2026-48710, #85)."""
    client = TestClient(main.app)
    for host in ("x/static", "evil.example/static/", "a b"):
        r = client.get(f"/api/events?v={__version__}", headers={"host": host})
        assert r.headers["cache-control"] == "no-store", host
    r = client.get(f"/static/app.js?v={__version__}")
    assert "immutable" in r.headers["cache-control"]


# ---------------------------------------------------------------- inga interna detaljer till besökarna (#87)

PRIVATE = "http://10.0.0.5:11434"
REAL_CLIENT = httpx.AsyncClient


def ollama(monkeypatch, handler):
    monkeypatch.setattr(chat.httpx, "AsyncClient",
                        lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(chat, "OLLAMA_URL", PRIVATE)
    monkeypatch.setattr(chat, "cache", None)
    monkeypatch.setattr(chat.websearch, "enabled", lambda: False)


def ask(handler, monkeypatch):
    ollama(monkeypatch, handler)

    async def go():
        return [json.loads(x) async for x in chat.chat_stream(CONVERSATION, EVENTS, THU, "v", previous_sources=SOURCES)]
    return asyncio.run(go())


def unreachable(request):
    raise httpx.ConnectError(f"All connection attempts failed ({PRIVATE})")


@pytest.mark.parametrize("handler", [
    unreachable,
    lambda request: httpx.Response(500, text="model runner crashed at /usr/share/ollama/models/blobs/sha256-abc"),
    lambda request: httpx.Response(200, text=json.dumps({"error": "out of memory on 10.0.0.5"})),
])
def test_ollama_errors_are_not_shown_to_visitors(handler, monkeypatch, caplog):
    out = ask(handler, monkeypatch)
    assert out[-1] == {"type": "error", "error": chat.AI_FAILED}
    text = json.dumps(out)
    assert "10.0.0.5" not in text and "/usr/share" not in text and "ConnectError" not in text
    assert caplog.records    # detaljerna finns i loggen


def test_ollama_status_hides_address(monkeypatch):
    ollama(monkeypatch, unreachable)
    st = asyncio.run(chat.ollama_status())
    assert st["error"] == chat.UNREACHABLE and "10.0.0.5" not in json.dumps(st)
    ollama(monkeypatch, lambda request: httpx.Response(200, json={"models": [{"name": "privat-modell:7b"}]}))
    st = asyncio.run(chat.ollama_status())
    assert st["reachable"] and "models" not in st
    assert st["error"] == f"Modellen {chat.OLLAMA_MODEL} finns inte i Ollama. Kör: ollama pull {chat.OLLAMA_MODEL}"


def test_storage_details_only_locally(monkeypatch):
    monkeypatch.setitem(events.state, "storage_error", "Kan inte spara till /data/visitvarmland.json: [Errno 13]")
    public = TestClient(main.app).get("/api/events").json()
    assert public["storage"] == {"error": main.STORAGE_ERROR}
    assert "/data" not in json.dumps(public["storage"])
    local = TestClient(main.app, client=("127.0.0.1", 50000)).get("/api/health").json()
    assert local["storage"]["dir"] and "Errno 13" in local["storage"]["error"]
