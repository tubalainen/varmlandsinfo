"""Säkerhetsåtgärder efter säkerhetsanalysen (#85–#92)."""

import asyncio
import json
import time
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

import chat
import events
import images
import main
import visits
from test_followups import CONVERSATION, EVENTS, SOURCES, THU
from version import __version__

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100


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


# ---------------------------------------------------------------- gränser (#89)

def test_large_bodies_are_rejected():
    client = TestClient(main.app)
    big = json.dumps({"question": "x" * (main.MAX_BODY + 1)})
    r = client.post("/api/chat", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413

    def chunks():                        # utan Content-Length: räknas medan kroppen tas emot
        for _ in range(10):
            yield b"x" * (main.MAX_BODY // 4)
    r = client.post("/api/chat", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert client.post("/api/chat", headers={"Content-Length": "abc"}).status_code == 413
    r = client.post("/api/chat", json={"question": "å" * 4000})        # största tillåtna frågan går igenom
    assert r.status_code != 413


def test_image_downloads_are_paced(tmp_path, monkeypatch):
    now = [0.0]
    urls = [f"https://img.example.se/{i}.jpg" for i in range(images.DOWNLOAD_BURST + 5)]
    p = images.ImageProxy(tmp_path / "images", check_host=lambda url: asyncio.sleep(0, True), clock=lambda: now[0],
                          client_factory=lambda: httpx.AsyncClient(
                              transport=httpx.MockTransport(lambda r: httpx.Response(200, content=JPEG))))
    p.register([{"id": "e", "title": "T", "images": [{"large": u} for u in urls]}])
    for u in urls[:images.DOWNLOAD_BURST]:
        assert asyncio.run(p.get(images.key(u)))
    with pytest.raises(images.Busy):
        asyncio.run(p.get(images.key(urls[-1])))
    assert asyncio.run(p.get(images.key(urls[0])))               # sparade bilder räknas inte
    now[0] = 2
    assert asyncio.run(p.get(images.key(urls[-1])))               # en ny per sekund


def test_busy_image_gives_503(monkeypatch):
    async def busy(key):
        raise images.Busy
    monkeypatch.setattr(main.image_proxy, "get", busy)
    r = TestClient(main.app).get("/img/" + "a" * 32)
    assert r.status_code == 503 and r.headers["retry-after"] == "60"


def test_visit_stats_are_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(visits, "MAX_VISITORS_PER_DAY", 3)
    monkeypatch.setattr(visits, "MAX_PER_DIMENSION", 2)
    s = visits.VisitStats(tmp_path / "b.json")
    day = datetime(2026, 9, 30, 10, 0)
    for i in range(6):
        s.record(f"81.230.12.{i}", "Mozilla/5.0 Chrome/140", f"https://site{i}.example/", "app", day)
    d = s.days["2026-09-30"]
    assert len(d["visitors"]) == 3 and d["visits"] == 6
    summary = visits.VisitStats.summarize(d)
    assert summary["referrer"] == {"site0.example": 1, "site1.example": 1, "Övriga": 1}


# ---------------------------------------------------------------- säkerhetshuvuden (#88)

def test_security_headers_on_all_responses():
    client = TestClient(main.app)
    for path in ("/", "/api/events", "/static/app.js", "/img/" + "0" * 32, "/finns-inte"):
        r = client.get(path)
        for name, value in main.SECURITY_HEADERS.items():
            assert r.headers[name] == value, (path, name)


def test_strict_csp_on_the_page():
    csp = TestClient(main.app).get("/").headers["content-security-policy"]
    for part in ("default-src 'self'", "script-src 'self'", "object-src 'none'", "base-uri 'none'",
                 "frame-ancestors 'none'", "img-src 'self' data:"):
        assert part in csp
    assert "unsafe" not in csp


# ---------------------------------------------------------------- länkar i AI-svar och bildproxyns server (#90)

def test_event_links_and_allowed_links():
    e = {"url": "https://visitvarmland.com/a", "booking_link": "https://tickster.com/a",
         "sources": [{"name": "VV", "url": "https://visitvarmland.com/a"}, {"name": "CCC", "url": "https://ccc.se/a"}]}
    assert chat.event_links(e) == ["https://visitvarmland.com/a", "https://ccc.se/a", "https://tickster.com/a"]
    allowed = chat.allowed_links([{"url": "https://visitvarmland.com/a", "links": chat.event_links(e)}],
                                 [{"url": "https://sv.wikipedia.org/wiki/Karlstad"}])
    answer = ("Gå på [A](https://visitvarmland.com/a), biljetter på https://tickster.com/a. "
              "Läs mer: https://sv.wikipedia.org/wiki/Karlstad och [logga in](https://evil.example/login)")
    assert chat.answer_links(answer) - allowed == {"https://evil.example/login"}


def ai_answer(text, tmp_path, monkeypatch):
    body = json.dumps({"message": {"content": text}, "done": True})
    ollama(monkeypatch, lambda request: httpx.Response(200, text=body))
    monkeypatch.setattr(chat, "cache", chat.AnswerCache(tmp_path / "c.json"))
    q = chat.SUGGESTIONS[0]["q"]

    async def go():
        return [json.loads(x) async for x in chat.chat_stream([{"role": "user", "content": q}], EVENTS, THU, "v")]
    return asyncio.run(go()), chat.normalize_question(q)


def test_answers_with_links_outside_the_material_are_not_cached(tmp_path, monkeypatch):
    konsert = next(e for e in EVENTS if e["title"] == "Höstkonsert")          # i helgen, alltså i underlaget
    out, key = ai_answer(f"Gå på [{konsert['title']}]({konsert['url']}).", tmp_path, monkeypatch)
    sources = next(x for x in out if x["type"] == "sources")["events"]
    assert all("links" in s for s in sources)
    assert key in chat.cache.presets                                   # länken finns i underlaget: sparas
    out, key = ai_answer("Vinn biljetter på [tävlingen](https://evil.example/vinn)!", tmp_path, monkeypatch)
    assert out[-1] == {"type": "done"} and key not in chat.cache.presets     # visas, men sparas inte


class Stream:
    def __init__(self, ip):
        self.ip = ip

    def get_extra_info(self, name):
        return (self.ip, 443) if name == "server_addr" else None


def test_image_proxy_checks_the_connected_server(tmp_path, monkeypatch):
    monkeypatch.setattr(images.urllib.request, "getproxies", lambda: {})
    for ip, ok in (("93.184.216.34", True), ("10.0.0.1", False), ("127.0.0.1", False), ("::ffff:192.168.1.1", False)):
        p = images.ImageProxy(tmp_path / ip, check_host=lambda url: asyncio.sleep(0, True), clock=lambda: 0,
                              client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(
                                  lambda r: httpx.Response(200, content=JPEG, extensions={"network_stream": Stream(ip)}))))
        url = "https://rebind.example/x.jpg"
        p.register([{"id": "e", "title": "T", "images": [{"large": url}]}])
        assert bool(asyncio.run(p.get(images.key(url)))) is ok, ip
    # Via en utgående proxy är anslutningen proxyns (ofta en lokal adress), och då gäller kontrollen av värdnamnet
    monkeypatch.setattr(images.urllib.request, "getproxies", lambda: {"https": "http://10.0.0.9:3128"})
    r = httpx.Response(200, extensions={"network_stream": Stream("10.0.0.9")})
    assert images.peer_is_public(r, "https://rebind.example/x.jpg")
