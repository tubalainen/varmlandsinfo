"""Bilderna via appen (#60): ingen öppen proxy, inga anrop in i det lokala nätverket, bara riktiga bilder."""

import asyncio

import httpx
from fastapi.testclient import TestClient

import events
import images
import main

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100
URL = "https://img.example.se/large/bild.jpg"


def event(*urls):
    return {"id": "e", "title": "T", "images": [{"small": u, "medium": u, "large": u, "alt": "", "copyright": ""}
                                                for u in urls]}


def proxy(tmp_path, handler, public=True, clock=None):
    calls = []

    def wrapped(request):
        calls.append(str(request.url))
        return handler(request)

    async def check(url):
        return public if isinstance(public, bool) else public(url)
    p = images.ImageProxy(tmp_path / "images", check_host=check, clock=clock or (lambda: 0),
                          client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(wrapped)))
    return p, calls


def get(p, k):
    return asyncio.run(p.get(k))


def test_media_type():
    assert images.media_type(JPEG) == "image/jpeg" and images.media_type(PNG) == "image/png"
    assert images.media_type(b"GIF89a...") == "image/gif"
    assert images.media_type(b"RIFF\0\0\0\0WEBPVP8 ") == "image/webp"
    assert images.media_type(b"\0\0\0\x1cftypavif") == "image/avif"
    assert images.media_type(b"<svg xmlns=...>") is None and images.media_type(b"<html>") is None


def test_rewrite_and_unknown_keys(tmp_path):
    p, calls = proxy(tmp_path, lambda r: httpx.Response(200, content=JPEG))
    evs = [event(URL), {"id": "x", "title": "Utan bild", "images": []}]
    p.register(evs)
    out = p.rewrite(evs)
    k = images.key(URL)
    assert out[0]["images"][0]["large"] == f"/img/{k}" and evs[0]["images"][0]["large"] == URL   # originalet orört
    assert get(p, "0" * 32) is None and calls == []            # okänd nyckel: ingen hämtning (ingen öppen proxy)
    assert get(p, k) == (JPEG, "image/jpeg") and len(calls) == 1
    assert get(p, k) == (JPEG, "image/jpeg") and len(calls) == 1   # andra gången från disk
    assert (tmp_path / "images" / k).read_bytes() == JPEG


def test_only_real_images_are_passed_through(tmp_path):
    for content in (b"<svg onload=alert(1)>", b"<html>hej</html>"):
        p, _ = proxy(tmp_path, lambda r, c=content: httpx.Response(200, content=c, headers={"content-type": "image/svg+xml"}))
        p.register([event(URL)])
        assert get(p, images.key(URL)) is None


def test_private_hosts_are_never_fetched(tmp_path):
    p, calls = proxy(tmp_path, lambda r: httpx.Response(200, content=JPEG), public=False)
    p.register([event("http://192.168.1.1/admin.jpg")])
    assert get(p, images.key("http://192.168.1.1/admin.jpg")) is None and calls == []


def test_redirects_are_checked(tmp_path):
    def handler(r):
        if r.url.host == "img.example.se":
            return httpx.Response(302, headers={"location": "http://intern.lan/bild.jpg"})
        return httpx.Response(200, content=JPEG)
    p, calls = proxy(tmp_path, handler, public=lambda url: "intern.lan" not in url)
    p.register([event(URL)])
    assert get(p, images.key(URL)) is None and calls == [URL]    # omdirigeringen till det lokala nätverket följs inte

    ok, calls = proxy(tmp_path, lambda r: httpx.Response(301, headers={"location": "/ny.jpg"}) if r.url.path != "/ny.jpg"
                      else httpx.Response(200, content=PNG))
    ok.register([event(URL)])
    assert get(ok, images.key(URL)) == (PNG, "image/png") and calls[-1] == "https://img.example.se/ny.jpg"


def test_too_large_and_failed_images_wait_before_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "MAX_BYTES", 50)
    now = [0.0]
    p, calls = proxy(tmp_path, lambda r: httpx.Response(200, content=JPEG), clock=lambda: now[0])
    p.register([event(URL)])
    k = images.key(URL)
    assert get(p, k) is None and get(p, k) is None and len(calls) == 1    # försöks inte igen direkt
    now[0] = images.RETRY_FAILED_AFTER + 1
    monkeypatch.setattr(images, "MAX_BYTES", 10_000)
    assert get(p, k) == (JPEG, "image/jpeg") and len(calls) == 2


def test_prune_removes_images_no_longer_used(tmp_path):
    p, _ = proxy(tmp_path, lambda r: httpx.Response(200, content=JPEG))
    other = "https://img.example.se/annan.jpg"
    p.register([event(URL, other)])
    get(p, images.key(URL)), get(p, images.key(other))
    assert p.prune([event(URL)]) == 1
    assert sorted(f.name for f in (tmp_path / "images").iterdir()) == [images.key(URL)]
    assert images.key(other) not in p.urls


def test_endpoint(tmp_path, monkeypatch):
    p, _ = proxy(tmp_path, lambda r: httpx.Response(200, content=JPEG))
    monkeypatch.setattr(main, "image_proxy", p)
    monkeypatch.setattr(events, "state", {**events.state, "events": [event(URL)]})
    client = TestClient(main.app)
    r = client.get(f"/img/{images.key(URL)}")
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-content-type-options"] == "nosniff" and "max-age=86400" in r.headers["cache-control"]
    assert client.get("/img/" + "0" * 32).status_code == 404
    assert client.get("/img/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert "img-src 'self' data:" in client.get("/").headers["content-security-policy"]


def test_public_host_check():
    assert not asyncio.run(images.is_public("file:///etc/passwd"))
    assert not asyncio.run(images.is_public("http://127.0.0.1/x.jpg"))
    assert not asyncio.run(images.is_public("http://192.168.1.1/x.jpg"))
    assert not asyncio.run(images.is_public("http://[::1]/x.jpg"))
    assert not asyncio.run(images.is_public("http://169.254.169.254/latest/meta-data"))
    assert asyncio.run(images.is_public("https://93.184.216.34/x.jpg"))
