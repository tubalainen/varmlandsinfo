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
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from common import USER_AGENT

log = logging.getLogger("varmlandsinfo")

MAX_BYTES = 10 * 1024 * 1024      # största bild som hämtas
MAX_REDIRECTS = 3
CONCURRENCY = 4                   # samtidiga hämtningar från källorna
RETRY_FAILED_AFTER = 3600         # sekunder innan en bild som inte gick att hämta försöks igen
# Nya hämtningar från källorna (sparade bilder räknas inte), så att ingen kan få appen att hämta alla bilder på en
# gång och riskera att källorna spärrar appen (#89): högst BURST direkt, sedan en per sekund.
DOWNLOAD_BURST = 60
DOWNLOADS_PER_SECOND = 1.0
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


class Busy(Exception):
    """För många nya hämtningar från källorna just nu. Bilden hämtas vid ett senare besök."""


def key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


async def host_problem(url: str) -> str | None:
    """Varför bilder inte får hämtas från adressens värd, eller None om den är en http(s)-adress vars värd bara
    pekar på publika IP-adresser. Orsaken hamnar i loggen, så att den som driftar appen kan felsöka (#111)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "ogiltig adress"
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443)
    except OSError as exc:
        return f"DNS-uppslaget misslyckades: {exc.strerror or type(exc).__name__}"
    addrs = sorted({i[4][0].split("%")[0] for i in infos})
    if not addrs:
        return "DNS gav ingen adress"
    try:
        private = [a for a in addrs if not ipaddress.ip_address(a).is_global]
    except ValueError:
        return "DNS gav en ogiltig adress"
    if not private:
        return None
    if all(ipaddress.ip_address(a).is_unspecified for a in private):    # 0.0.0.0 och :: är spärrsvar från DNS
        return f"pekar på {', '.join(private)}, troligen spärrad i DNS, t.ex. av Pi-hole eller AdGuard Home"
    return f"pekar på {', '.join(private)}, som inte är publik"


async def is_public(url: str) -> bool:
    """http(s)-adress vars värd bara pekar på publika IP-adresser."""
    return await host_problem(url) is None


def _proxied(url: str) -> bool:
    """Hämtningen går via en utgående proxy (HTTPS_PROXY m.fl.), som httpx använder."""
    parts = urlsplit(url)
    return bool(urllib.request.getproxies().get(parts.scheme)) and not urllib.request.proxy_bypass(parts.hostname or "")


def peer_is_public(r: httpx.Response, url: str) -> bool:
    """Adressen som anslutningen faktiskt gick till är publik. Skyddar mot DNS-rebinding, där värdnamnet pekar på en
    publik adress när det kontrolleras och på en adress i det lokala nätverket när httpx ansluter (#90). Via en
    utgående proxy är anslutningen proxyns, och då gäller kontrollen av värdnamnet."""
    stream = r.extensions.get("network_stream")
    addr = stream.get_extra_info("server_addr") if stream else None
    if not addr or _proxied(url):
        return True
    try:
        ip = ipaddress.ip_address(str(addr[0]).split("%")[0])
    except ValueError:
        return False
    return (getattr(ip, "ipv4_mapped", None) or ip).is_global


class ImageProxy:
    def __init__(self, directory: Path, client_factory=None, clock=time.monotonic, check_host=host_problem):
        self.dir = directory
        self.urls: dict[str, str] = {}          # nyckel -> bildens adress hos källan
        self.failed: dict[str, float] = {}      # nyckel -> när hämtningen misslyckades
        self.warned: dict[str, float] = {}      # värd -> när den senast varnades för (#111)
        self.clock = clock
        self.check_host = check_host
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(
            timeout=httpx.Timeout(10, read=20), headers={"User-Agent": USER_AGENT}))
        self._sem = asyncio.Semaphore(CONCURRENCY)
        self._locks: dict[str, asyncio.Lock] = {}
        self._tokens, self._refilled = float(DOWNLOAD_BURST), clock()
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
        self.warned = {h: t for h, t in self.warned.items() if now - t < RETRY_FAILED_AFTER}
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

    def _refused(self, url: str, reason: str) -> None:
        """Varnar att bilder inte hämtas från värden, högst en gång per värd och RETRY_FAILED_AFTER (#111): annars
        blir det en rad per bild, ett 70-tal för en sidvisning."""
        host, now = urlsplit(url).hostname or "?", self.clock()
        if host in self.warned and now - self.warned[host] < RETRY_FAILED_AFTER:
            return
        self.warned[host] = now
        log.warning("Bilder hämtas inte från %s (%s). Nästa varning om värden tidigast om %d minuter.",
                    host, reason, RETRY_FAILED_AFTER // 60)

    def _take(self) -> bool:
        """En ny hämtning från källorna ryms i takten (DOWNLOAD_BURST, sedan DOWNLOADS_PER_SECOND)."""
        now = self.clock()
        self._tokens = min(DOWNLOAD_BURST, self._tokens + (now - self._refilled) * DOWNLOADS_PER_SECOND)
        self._refilled = now
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True

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
        """Bilden för nyckeln: från disk, annars från källan. None om den inte finns eller inte går att hämta.
        Busy om för många bilder har hämtats från källorna nyss."""
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
                if not self._take():
                    raise Busy
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
                    if problem := await self.check_host(url):
                        self._refused(url, problem)
                        return None
                    async with client.stream("GET", url, headers={"Accept": "image/*"}) as r:
                        if not peer_is_public(r, url):
                            self._refused(url, "servern som anslutningen gick till är inte publik")
                            return None
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
