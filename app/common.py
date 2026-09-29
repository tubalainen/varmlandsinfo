"""Gemensamma hjälpfunktioner för evenemangskällorna."""

import asyncio
import email.utils
import html
import logging
import os
import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from categories import describe_category, refine, split_loppis, split_motorsport
from version import __version__

TZ = ZoneInfo(os.getenv("TZ", "Europe/Stockholm"))
USER_AGENT = f"varmlandsinfo/{__version__} (+https://github.com/tubalainen/varmlandsinfo)"
RATE_LIMIT_LOW = 5   # pausa när så här få anrop återstår i kvoten
# Nya försök är mycket försiktiga (#76), så att appen aldrig riskerar att bli spärrad av en källa:
# högst ett nytt försök per anrop, bara vid 429 och 5xx, och aldrig tidigare än källan ber om (Retry-After).
SERVER_ERROR_RETRY_DELAY = 60   # sekunder före det nya försöket vid ett serverfel (HTTP 5xx) utan Retry-After
RATE_LIMIT_WAIT = 60            # sekunder före det nya försöket vid 429 utan Retry-After
MAX_RETRY_WAIT = 60             # ber källan om längre väntan görs inget nytt försök förrän nästa hämtning

log = logging.getLogger("varmlandsinfo")

stats = {"api_calls": 0}


def today() -> date:
    return datetime.now(TZ).date()


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def strip_html(text: str | None, limit: int = 700) -> str:
    if not text:
        return ""
    text = re.sub(r"<\s*(br|/p|/h\d|/li)\s*/?>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " …"
    return text


def https_url(url: str | None) -> str | None:
    if url and isinstance(url, str) and url.startswith(("https://", "http://")):
        return url
    return None


def category(title: str) -> dict:
    return {"title": title, **describe_category(title)}


FREE_RE = re.compile(r"\b(fri entré|fritt inträde|fri inträde|gratis|kostnadsfri\w*|free)\b", re.I)
PAID_RE = re.compile(r"\d+\s*(kr|sek|:-)", re.I)


def price_is_free(prices: list[dict]) -> bool:
    """True om prisuppgifterna anger fri entré (eller pris 0) och inget pris över 0 finns.

    "Vuxen 50 kr, 0–19 år fri entré" räknas alltså inte som gratis."""
    free = False
    for p in prices or []:
        if not isinstance(p, dict):
            continue
        text = f"{p.get('price_type') or ''} {p.get('description') or ''}"
        raw = str(p.get("price") or "").replace(",", ".")
        amount = re.search(r"\d+(\.\d+)?", raw)
        if amount and float(amount.group()) > 0:
            return False
        if PAID_RE.search(text):
            return False
        if amount or FREE_RE.search(text):
            free = True
    return free


class SourceError(RuntimeError):
    """Fel från en källa. Meddelandet innehåller aldrig frågesträngen (där API-nycklar kan finnas)."""


class AccessDenied(SourceError):
    """HTTP 401/403: nyckeln är fel eller appen är spärrad. Källan pausas till nästa morgonkörning (events)."""


PAUSED = "Källan pausas till nästa morgonkörning."


def retry_after(r: httpx.Response, default: float) -> float | None:
    """Sekunder enligt Retry-After (sekunder eller datum). `default` utan huvud, None om det inte går att tolka."""
    value = (r.headers.get("retry-after") or "").strip()
    if not value:
        return default
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        return None
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


async def _request(send, unreachable: str, where: str) -> httpx.Response:
    """Ett anrop till en källa, med högst ett nytt försök: vid 429 och serverfel (5xx), och bara om källan inte ber
    om längre väntan än MAX_RETRY_WAIT. `where` (källa och sökväg, aldrig frågesträngen) används i loggen,
    `unreachable` i felmeddelandet."""
    for attempt in range(2):
        try:
            r = await send()
        except httpx.HTTPError as exc:
            raise SourceError(f"Kunde inte nå {unreachable}: {type(exc).__name__}") from None
        stats["api_calls"] += 1
        if attempt or not (r.status_code == 429 or r.status_code >= 500):
            return r
        wait = retry_after(r, RATE_LIMIT_WAIT if r.status_code == 429 else SERVER_ERROR_RETRY_DELAY)
        if wait is None or wait > MAX_RETRY_WAIT:
            log.warning("HTTP %s från %s. Källan ber appen vänta längre än %ss, så inget nytt försök förrän nästa "
                        "hämtning", r.status_code, where, MAX_RETRY_WAIT)
            return r
        if r.status_code >= 500:
            wait = max(wait, SERVER_ERROR_RETRY_DELAY)
        log.warning("HTTP %s från %s, ett nytt försök om %ss", r.status_code, where, round(wait))
        await asyncio.sleep(wait)
    return r


def _check(r: httpx.Response, source: str, where: str, key_hint: bool = False) -> None:
    """Felet för ett misslyckat svar. 401/403 pausar källan, 429 väntar till nästa hämtning."""
    if r.status_code in (401, 403):
        hint = ", kontrollera API-nyckeln" if key_hint else ""
        raise AccessDenied(f"{source} nekade åtkomst (HTTP {r.status_code}){hint}. {PAUSED}")
    if r.status_code == 429:
        raise SourceError(f"{source} ber appen vänta (HTTP 429 Too Many Requests). Nytt försök vid nästa hämtning.")
    if r.status_code >= 400:
        raise SourceError(f"{where} svarade HTTP {r.status_code}")


async def get_json(client: httpx.AsyncClient, url: str, source: str, **params) -> dict:
    """GET som respekterar källans rate limit och aldrig läcker frågesträngen i felmeddelanden."""
    where = f"{source} ({urlsplit(url).path})"
    r = await _request(lambda: client.get(url, params=params), where, where)
    _check(r, source, where, key_hint=True)
    remaining = r.headers.get("x-ratelimit-remaining") or r.headers.get("rate-limit-available")
    if remaining is not None and remaining.isdigit() and int(remaining) < RATE_LIMIT_LOW:
        log.info("Bara %s anrop kvar i kvoten hos %s, pausar 60s", remaining, source)
        await asyncio.sleep(60)
    try:
        return r.json()
    except ValueError:
        raise SourceError(f"{where} svarade inte med JSON") from None


async def get_text(client: httpx.AsyncClient, url: str, source: str, headers: dict | None = None) -> str:
    """GET av en HTML-sida (för källor utan API)."""
    r = await _request(lambda: client.get(url, headers={"Accept": "text/html", **(headers or {})}, follow_redirects=True),
                       source, f"{source} ({urlsplit(url).path})")
    _check(r, source, f"{source} ({urlsplit(url).path})")
    return r.text


async def post_form(client: httpx.AsyncClient, url: str, data: dict, source: str) -> str:
    """POST av ett formulär (t.ex. en ASP.NET-postback för att byta sida i en lista)."""
    r = await _request(lambda: client.post(url, data=data, headers={"Accept": "text/html"}, follow_redirects=True),
                       source, f"{source} ({urlsplit(url).path})")
    _check(r, source, f"{source} ({urlsplit(url).path})")
    return r.text


async def post_json(client: httpx.AsyncClient, url: str, data: dict, source: str, headers: dict | None = None) -> dict:
    """POST med JSON (t.ex. när en sida laddar fler rader med ett Livewire-anrop, som i webbläsaren)."""
    r = await _request(lambda: client.post(url, json=data, headers={"Accept": "application/json", **(headers or {})}),
                       source, f"{source} ({urlsplit(url).path})")
    _check(r, source, f"{source} ({urlsplit(url).path})")
    try:
        return r.json()
    except ValueError:
        raise SourceError(f"{source} ({urlsplit(url).path}) svarade inte med JSON") from None


def clean_text(fragment: str | None) -> str:
    """Text ur ett HTML-fragment, med blanksteg ihopslagna."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))).strip()


def finalize(event: dict) -> dict | None:
    """Sorterar tillfällen, tar bort passerade och sätter `next`. None om inget tillfälle återstår."""
    first_day = today().isoformat()
    occ = sorted(
        (o for o in event["occasions"] if o.get("date_start")),
        key=lambda o: (o["date_start"], o.get("time_start") or ""),
    )
    occ = [o for o in occ if (o.get("date_end") or o["date_start"]) >= first_day]
    if not occ:
        return None
    for o in occ:
        o.setdefault("date_end", o["date_start"])
        o.setdefault("time_start", None)
        o.setdefault("time_end", None)
    event["occasions"] = occ
    event["next"] = occ[0]
    title, summary = event.get("title") or "", event.get("summary") or ""
    event["categories"] = refine(
        split_motorsport(split_loppis(event.get("categories") or [], title, summary), title, summary), title, summary)
    event.setdefault("sources", [{"name": event["source"], "url": event.get("url")}])
    return event
