"""Gemensamma hjälpfunktioner för evenemangskällorna."""

import asyncio
import html
import logging
import os
import re
from datetime import date, datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from categories import describe_category, split_loppis
from version import __version__

TZ = ZoneInfo(os.getenv("TZ", "Europe/Stockholm"))
USER_AGENT = f"varmlandsinfo/{__version__} (+https://github.com/tubalainen/varmlandsinfo)"
RATE_LIMIT_LOW = 5   # pausa när så här få anrop återstår i kvoten
MAX_RETRIES = 4

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


async def get_json(client: httpx.AsyncClient, url: str, source: str, **params) -> dict:
    """GET som respekterar källans rate limit och aldrig läcker frågesträngen i felmeddelanden."""
    where = f"{source} ({urlsplit(url).path})"
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceError(f"Kunde inte nå {where}: {type(exc).__name__}") from None
        stats["api_calls"] += 1
        if r.status_code == 429:
            if attempt == MAX_RETRIES:
                break
            try:
                wait = min(int(r.headers.get("retry-after", 60)), 120)
            except ValueError:
                wait = 60
            log.warning("Rate limit (429) från %s, väntar %ss", source, wait)
            await asyncio.sleep(wait)
            continue
        if r.status_code in (401, 403):
            raise SourceError(f"{source} nekade åtkomst (HTTP {r.status_code}), kontrollera API-nyckeln")
        if r.status_code >= 400:
            raise SourceError(f"{where} svarade HTTP {r.status_code}")
        remaining = r.headers.get("x-ratelimit-remaining") or r.headers.get("rate-limit-available")
        if remaining is not None and remaining.isdigit() and int(remaining) < RATE_LIMIT_LOW:
            log.info("Bara %s anrop kvar i kvoten hos %s, pausar 60s", remaining, source)
            await asyncio.sleep(60)
        try:
            return r.json()
        except ValueError:
            raise SourceError(f"{where} svarade inte med JSON") from None
    raise SourceError(f"{source} svarar fortsatt 429 (Too Many Requests)")


async def get_text(client: httpx.AsyncClient, url: str, source: str) -> str:
    """GET av en HTML-sida (för källor utan API)."""
    try:
        r = await client.get(url, headers={"Accept": "text/html"}, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise SourceError(f"Kunde inte nå {source}: {type(exc).__name__}") from None
    stats["api_calls"] += 1
    if r.status_code >= 400:
        raise SourceError(f"{source} ({urlsplit(url).path}) svarade HTTP {r.status_code}")
    return r.text


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
    event["categories"] = split_loppis(event.get("categories") or [], event.get("title") or "", event.get("summary") or "")
    event.setdefault("sources", [{"name": event["source"], "url": event.get("url")}])
    return event
