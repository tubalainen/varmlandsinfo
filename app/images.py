"""Evenemangens bilder via appen, så att källornas bildservrar aldrig ser besökarna.

`/api/events` ger adresser som `/img/<nyckel>`, där nyckeln är en hash av bildens adress hos källan. Appen hämtar
bilden på serversidan första gången någon visar den och sparar den på disk (`/data/images/`).

Ingen öppen proxy: bara bilder som finns i appens evenemang kan hämtas. Värdar som pekar på andra än publika
adresser (t.ex. det lokala nätverket) hämtas aldrig, inte heller efter en omdirigering, och bara riktiga bilder
(JPEG, PNG, GIF, WebP, AVIF) släpps igenom.
"""

import asyncio
import hashlib
import ipaddress
import logging
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from common import USER_AGENT

log = logging.getLogger("varmlandsinfo")

MAX_BYTES = 10 * 1024 * 1024      # största bild som hämtas
MAX_REDIRECTS = 3
CONCURRENCY = 4                   # samtidiga hämtningar från källorna
RETRY_FAILED_AFTER = 3600         # sekunder innan en bild som inte gick att hämta försöks igen
SIZES = ("small", "medium", "large")

TYPES = {                         # filsignatur -> mediatyp
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}


def media_type(data: bytes) -> str | None:
    """Bildens typ utifrån innehållet (inte utifrån vad servern påstår). None om det inte är en tillåten bild."""
    for sig, kind in TYPES.items():
        if data.startswith(sig):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return "image/avif"
    return None


def key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


async def is_public(url: str) -> bool:
    """http(s)-adress vars värd bara pekar på publika IP-adresser."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443)
    except OSError:
        return False
    try:
        return bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)
    except ValueError:
        return False


class ImageProxy:
    def __init__(self, directory: Path, client_factory=None, clock=time.monotonic, check_host=is_public):
        self.dir = directory
        self.urls: dict[str, str] = {}          # nyckel -> bildens adress hos källan
        self.failed: dict[str, float] = {}      # nyckel -> när hämtningen misslyckades
        self.clock = clock
        self.check_host = check_host
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(
            timeout=httpx.Timeout(10, read=20), headers={"User-Agent": USER_AGENT}))
        self._sem = asyncio.Semaphore(CONCURRENCY)
        self._locks: dict[str, asyncio.Lock] = {}
        self._source = None                     # evenemangslistan som adresserna senast lästes från

    # ------------------------------------------------------------ adresser

    def register(self, events: list[dict]) -> None:
        """Lär in bildadresserna i evenemangen (görs om bara när listan byts ut)."""
        if events is self._source:
            return
        for e in events:
            for img in e.get("images") or []:
                for size in SIZES:
                    if url := img.get(size):
                        self.urls[key(url)] = url
        self._source = events

    def rewrite(self, events: list[dict]) -> list[dict]:
        """Evenemangen med bildadresser via appen."""
        def local(img: dict) -> dict:
            return {**img, **{size: f"/img/{key(img[size])}" for size in SIZES if img.get(size)}}
        return [{**e, "images": [local(i) for i in e["images"]]} if e.get("images") else e for e in events]

    def prune(self, events: list[dict]) -> int:
        """Glömmer adresser och raderar sparade bilder som inte hör till något evenemang längre, liksom
        halvfärdiga filer (*.tmp) från en avbruten hämtning."""
        self._source = None
        self.urls = {}
        self.register(events)
        now = self.clock()
        self.failed = {k: t for k, t in self.failed.items() if k in self.urls and now - t < RETRY_FAILED_AFTER}
        removed = 0
        if self.dir.is_dir():
            for f in self.dir.iterdir():
                if f.suffix == ".tmp" or f.name not in self.urls:
                    try:
                        f.unlink()
                        removed += 1
                    except OSError as exc:
                        log.warning("Kunde inte radera %s: %s", f, exc)
        return removed

    # ------------------------------------------------------------ hämtning

    def _path(self, k: str) -> Path:
        return self.dir / k

    def cached(self, k: str) -> tuple[bytes, str] | None:
        try:
            data = self._path(k).read_bytes()
        except OSError:
            return None
        kind = media_type(data)
        return (data, kind) if kind else None

    async def get(self, k: str) -> tuple[bytes, str] | None:
        """Bilden för nyckeln: från disk, annars från källan. None om den inte finns eller inte går att hämta."""
        if k not in self.urls:
            return None
        if hit := self.cached(k):
            return hit
        if (t := self.failed.get(k)) is not None and self.clock() - t < RETRY_FAILED_AFTER:
            return None
        lock = self._locks.setdefault(k, asyncio.Lock())
        async with lock:
            if hit := self.cached(k):           # någon annan hann hämta den medan vi väntade
                return hit
            try:
                async with self._sem:
                    data = await self._download(self.urls[k])
            finally:
                self._locks.pop(k, None)
            kind = media_type(data) if data else None
            if not kind:
                self.failed[k] = self.clock()
                return None
            self.failed.pop(k, None)
            self._save(k, data)
            return data, kind

    def _save(self, k: str, data: bytes) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self._path(k).with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, self._path(k))
        except OSError as exc:
            log.warning("Kunde inte spara bilden %s: %s", k, exc)

    async def _download(self, url: str) -> bytes | None:
        try:
            async with self._client_factory() as client:
                for _ in range(MAX_REDIRECTS + 1):
                    if not await self.check_host(url):
                        log.warning("Bilden hämtades inte (värden är inte publik): %s", urlsplit(url).hostname)
                        return None
                    async with client.stream("GET", url, headers={"Accept": "image/*"}) as r:
                        if r.is_redirect and (location := r.headers.get("location")):
                            url = urljoin(url, location)
                            continue
                        if r.status_code != 200:
                            log.info("Bilden kunde inte hämtas från %s: HTTP %s", urlsplit(url).hostname, r.status_code)
                            return None
                        data = bytearray()
                        async for chunk in r.aiter_bytes():
                            data += chunk
                            if len(data) > MAX_BYTES:
                                return None
                        return bytes(data)
        except httpx.HTTPError as exc:
            log.info("Bilden kunde inte hämtas från %s: %s", urlsplit(url).hostname, type(exc).__name__)
        return None
