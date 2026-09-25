"""Webbsökning via SearXNG för Fråga AI.

Bara frågor som går till AI:n söker på webben. Träffarna (titel, länk, utdrag) blir ett kompletterande
underlag till modellen. SearXNG måste ha JSON-formatet påslaget (search.formats: [html, json] i settings.yml).
Fel eller timeout stoppar aldrig svaret: då svarar AI:n utan webben.
"""

import html
import logging
import os
import re

import httpx

log = logging.getLogger("varmlandsinfo.websearch")

TIMEOUT = 8                       # sekunder
MAX_TITLE, MAX_SNIPPET = 150, 300


def _base(url: str) -> str:
    """Tillåter både http://värd:8080 och http://värd:8080/search."""
    return re.sub(r"/search/?$", "", url.strip().rstrip("/"))


def _int(name: str, default: int) -> int:
    try:
        return max(1, min(int(os.getenv(name) or default), 20))
    except ValueError:
        log.warning("Ogiltigt %s=%r, använder %d", name, os.getenv(name), default)
        return default


SEARXNG_URL = _base(os.getenv("SEARXNG_URL", ""))
SEARXNG_RESULTS = _int("SEARXNG_RESULTS", 5)
SEARXNG_LANGUAGE = (os.getenv("SEARXNG_LANGUAGE") or "sv").strip()


def enabled() -> bool:
    return bool(SEARXNG_URL)


def build_query(question: str, municipalities: list[str] | set[str] | None = None) -> str:
    """Frågan som sökord, med "Värmland" tillagt om varken Värmland eller en kommun nämns."""
    q = re.sub(r"\s+", " ", question).strip()
    if not municipalities and not re.search(r"värmland", q, re.I):
        q += " Värmland"
    return q


def _clean(text: str | None, limit: int) -> str:
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


async def search(query: str) -> list[dict]:
    """Webbträffar som [{title, url, content}]. Tom lista om sökningen är avstängd eller misslyckas."""
    if not enabled() or not query.strip():
        return []
    params = {"q": query, "format": "json", "language": SEARXNG_LANGUAGE, "safesearch": 1}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers={"Accept": "application/json"}) as client:
            r = await client.get(f"{SEARXNG_URL}/search", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        # Ingen frågetext i loggen, bara vad som gick fel
        log.warning("Webbsökningen via SearXNG misslyckades: %s", type(exc).__name__)
        return []
    results, seen = [], set()
    for item in data.get("results") or []:
        url = item.get("url") or ""
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        results.append({"title": _clean(item.get("title"), MAX_TITLE) or url, "url": url,
                        "content": _clean(item.get("content"), MAX_SNIPPET)})
        if len(results) >= SEARXNG_RESULTS:
            break
    return results


def config() -> dict:
    return {"enabled": enabled(), "results": SEARXNG_RESULTS if enabled() else 0}
