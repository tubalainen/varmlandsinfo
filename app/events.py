"""Hämtning, lagring och sammanslagning av evenemang från alla källor."""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from common import TZ, USER_AGENT, log, now_iso, stats, today
from merge import merge
from sources import SOURCES
from version import __version__

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_FORMAT = 2
MIN_MANUAL_REFRESH = timedelta(minutes=5)     # knappen hämtar inte oftare än så

state: dict = {
    "events": [],
    "updated": None,          # senaste genomförda hämtning (alla källor)
    "error": None,            # sammanfattning av fel i senaste hämtningen
    "refreshing": False,
    "storage_error": None,
    # per källa: {"title", "enabled", "count", "updated", "error"}
    "sources": {s.key: {"title": s.title, "homepage": s.homepage, "enabled": s.config_error() is None,
                        "config_error": s.config_error(), "count": 0, "updated": None, "error": None}
                for s in SOURCES},
}
_payloads: dict[str, dict] = {}
_refresh_task: asyncio.Task | None = None


def cache_file(key: str) -> Path:
    return DATA_DIR / f"{key}.json"


def rebuild() -> None:
    """Normaliserar alla källors rådata och slår ihop dem."""
    per_source = []
    for s in SOURCES:
        payload = _payloads.get(s.key)
        events = []
        if payload is not None:
            try:
                events = s.normalize(payload)
            except Exception as exc:
                log.exception("Kunde inte tolka data från %s", s.title)
                state["sources"][s.key]["error"] = f"Kunde inte tolka data: {exc}"
        state["sources"][s.key]["count"] = len(events)
        per_source.append(events)
    merged = merge(per_source)
    merged.sort(key=lambda e: (e["next"]["date_start"], e["next"]["time_start"] or "", e["title"]))
    state["events"] = merged


def save_cache(key: str, payload: dict, updated: str) -> None:
    """Sparar en källas rådata atomärt (skriv till temporär fil, byt sedan namn)."""
    path = cache_file(key)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"format": CACHE_FORMAT, "source": key, "updated": updated,
                       "app_version": __version__, "payload": payload}, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        state["storage_error"] = None
    except OSError as exc:
        state["storage_error"] = f"Kan inte spara till {path}: {exc}"
        log.warning("%s (data finns bara i minnet)", state["storage_error"])


def _read_cache(key: str) -> tuple[dict, str | None] | None:
    path = cache_file(key)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("Kunde inte läsa %s: %s", path, exc)
        return None
    if data.get("format") == CACHE_FORMAT and isinstance(data.get("payload"), dict):
        return data["payload"], data.get("updated")
    if data.get("format") == 1 and isinstance(data.get("events"), list):   # från version 0.0.1
        return {"municipalities": data.get("municipalities") or {},
                "municipalities_updated": data.get("municipalities_updated") or data.get("updated"),
                "events": data["events"]}, data.get("updated")
    log.warning("Okänt format i %s, ignorerar filen", path)
    return None


def load_cache() -> bool:
    """Läser in sparad data för alla källor vid start. True om någon källa hade data."""
    found = False
    for s in SOURCES:
        if not state["sources"][s.key]["enabled"]:
            continue   # avstängda källors filer raderas vid städningen (purge_old)
        cached = _read_cache(s.key)
        if cached:
            _payloads[s.key], state["sources"][s.key]["updated"] = cached
            found = True
    if found:
        rebuild()
        state["updated"] = max((v["updated"] for v in state["sources"].values() if v["updated"]), default=None)
        log.info("Läste in sparad data: %s", ", ".join(
            f"{v['title']} {v['count']}" for v in state["sources"].values() if v["updated"]))
    return found


def stale_sources(is_stale) -> list[str]:
    """Aktiverade källor som saknar data eller vars data är inaktuell enligt is_stale(updated)."""
    return [s.key for s in SOURCES
            if state["sources"][s.key]["enabled"] and is_stale(state["sources"][s.key]["updated"])]


async def _refresh(keys: list[str] | None) -> None:
    state["refreshing"] = True
    calls_before = stats["api_calls"]
    try:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        async with httpx.AsyncClient(headers=headers, timeout=60) as client:
            for s in SOURCES:
                info = state["sources"][s.key]
                if not info["enabled"] or (keys is not None and s.key not in keys):
                    continue
                try:
                    payload = await s.fetch(client, _payloads.get(s.key))
                    updated = now_iso()
                    _payloads[s.key] = payload
                    info.update(updated=updated, error=None)
                    await asyncio.to_thread(save_cache, s.key, payload, updated)
                except Exception as exc:
                    # Senast hämtade (eller sparade) data för källan ligger kvar
                    log.warning("Hämtning från %s misslyckades: %s", s.title, exc)
                    info["error"] = str(exc)
        rebuild()
        errors = [f"{v['title']}: {v['error']}" for v in state["sources"].values() if v["enabled"] and v["error"]]
        state["error"] = "; ".join(errors) or None
        state["updated"] = now_iso()
        log.info("Hämtade evenemang (%s) med %d API-anrop, %d evenemang efter sammanslagning",
                 ", ".join(f"{v['title']} {v['count']}" for v in state["sources"].values() if v["enabled"]),
                 stats["api_calls"] - calls_before, len(state["events"]))
    except Exception as exc:
        log.exception("Uppdatering misslyckades")
        state["error"] = str(exc)
    finally:
        state["refreshing"] = False


async def refresh(keys: list[str] | None = None) -> None:
    """Hämtar angivna källor (alla om None), eller väntar in en hämtning som redan pågår."""
    global _refresh_task
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = asyncio.create_task(_refresh(keys))
    # shield: en klient som kopplar ner ska inte avbryta hämtningen
    await asyncio.shield(_refresh_task)


def _older_than(iso: str | None, age: timedelta) -> bool:
    if not iso:
        return True
    try:
        return datetime.now(TZ) - datetime.fromisoformat(iso) > age
    except ValueError:
        return True


async def manual_refresh() -> str | None:
    """Uppdatering från knappen. Returnerar ett meddelande om den hoppades över."""
    if not state["refreshing"] and state["updated"] and not _older_than(state["updated"], MIN_MANUAL_REFRESH):
        return "Evenemangen hämtades för mindre än 5 minuter sedan, så de hämtades inte igen."
    await refresh()
    return None


def _fetched_before(iso: str | None, cutoff: datetime) -> bool:
    try:
        return datetime.fromisoformat(iso) < cutoff
    except (TypeError, ValueError):
        return True


def purge_old(cutoff: datetime) -> list[str]:
    """Tar bort data som hämtats före `cutoff` (den senaste morgonkörningen) och data från avstängda källor,
    både ur minnet och från disken. Kvarglömda temporära filer raderas också. Returnerar källorna som städades."""
    purged = []
    for s in SOURCES:
        info = state["sources"][s.key]
        path = cache_file(s.key)
        try:
            path.with_suffix(".json.tmp").unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Kunde inte radera %s: %s", path.with_suffix(".json.tmp"), exc)
        if info["enabled"] and not _fetched_before(info["updated"], cutoff):
            continue
        had_data = _payloads.pop(s.key, None) is not None or path.exists()
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Kunde inte radera %s: %s", path, exc)
        if info["updated"] or had_data:
            purged.append(s.key)
        info["updated"] = None
        if info["enabled"] and not info["error"]:
            info["error"] = "Ingen aktuell data: källan kunde inte hämtas vid morgonkörningen"
    if purged:
        rebuild()
        log.info("Städade bort gammal data: %s", ", ".join(state["sources"][k]["title"] for k in purged))
    return purged


def current_events() -> list[dict]:
    """Evenemang med tillfällen som inte passerat, sorterade på nästa tillfälle."""
    first_day = today().isoformat()
    result = []
    for e in state["events"]:
        occ = [o for o in e["occasions"] if o["date_end"] >= first_day]
        if occ:
            result.append({**e, "occasions": occ, "next": occ[0]})
    result.sort(key=lambda e: (e["next"]["date_start"], e["next"]["time_start"] or "", e["title"]))
    return result
