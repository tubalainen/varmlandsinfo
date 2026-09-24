"""Värmlandsinfo – samlar evenemang i Värmland och visar dem i ett webbgränssnitt."""

import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import chat
import events
from common import TZ, stats
from version import RELEASE_URL, REPO_URL, __version__

DAILY_REFRESH_TIME = os.getenv("DAILY_REFRESH_TIME", "05:00")
MIN_REFRESH_MINUTES = 30
RETRY_AFTER_FAILURE = timedelta(minutes=30)
STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# httpx loggar hela URL:en inklusive frågesträngen, där API-nycklar kan finnas
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("varmlandsinfo")


def _refresh_minutes() -> int:
    """REFRESH_MINUTES: 0 (eller tomt) = bara daglig körning, annars minst 30 minuter."""
    try:
        value = int(os.getenv("REFRESH_MINUTES") or 0)
    except ValueError:
        log.warning("Ogiltigt REFRESH_MINUTES=%r, använder 0 (av)", os.getenv("REFRESH_MINUTES"))
        return 0
    if 0 < value < MIN_REFRESH_MINUTES:
        log.warning("REFRESH_MINUTES=%d är för tätt för API:et, använder %d", value, MIN_REFRESH_MINUTES)
        return MIN_REFRESH_MINUTES
    return max(value, 0)


REFRESH_MINUTES = _refresh_minutes()

schedule: dict = {"next_refresh": None}


def _daily_at(now: datetime) -> datetime:
    h, m = (int(x) for x in DAILY_REFRESH_TIME.split(":"))
    return datetime.combine(now.date(), time(h, m), tzinfo=TZ)


def needs_refresh(updated: str | None, now: datetime) -> bool:
    """Sparad data räcker om den hämtats efter den senaste schemalagda uppdateringen."""
    if not updated:
        return True
    try:
        fetched = datetime.fromisoformat(updated)
    except ValueError:
        return True
    last_daily = _daily_at(now)
    if last_daily > now:
        last_daily -= timedelta(days=1)
    if fetched < last_daily:
        return True
    return REFRESH_MINUTES > 0 and now - fetched >= timedelta(minutes=REFRESH_MINUTES)


def next_run(now: datetime) -> datetime:
    """Nästa schemalagda uppdatering: dagligen vid DAILY_REFRESH_TIME, eventuellt tätare."""
    daily = _daily_at(now)
    if daily <= now:
        daily += timedelta(days=1)
    if REFRESH_MINUTES > 0:
        return min(daily, now + timedelta(minutes=REFRESH_MINUTES))
    return daily


async def scheduler() -> None:
    await asyncio.to_thread(events.load_cache)
    now = datetime.now(TZ)
    stale = events.stale_sources(lambda updated: needs_refresh(updated, now))
    if stale:
        log.info("Hämtar vid start: %s", ", ".join(stale))
        await events.refresh(stale)
    else:
        log.info("Sparad data är aktuell, ingen hämtning vid start")
    while True:
        now = datetime.now(TZ)
        target = next_run(now)
        failed = [k for k, v in events.state["sources"].items() if v["enabled"] and v["error"]]
        retry = bool(failed) and now + RETRY_AFTER_FAILURE < target
        if retry:
            # Misslyckad hämtning: försök igen om en stund med bara de källor som fallerade
            target = now + RETRY_AFTER_FAILURE
        schedule["next_refresh"] = target.isoformat(timespec="minutes")
        log.info("Nästa schemalagda uppdatering: %s%s", schedule["next_refresh"],
                 f" (nytt försök: {', '.join(failed)})" if retry else "")
        await asyncio.sleep(max(1, (target - datetime.now(TZ)).total_seconds()))
        await events.refresh(failed if retry else None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for line in (
        "=" * 60,
        f"  Värmlandsinfo v{__version__}",
        f"  Release: {RELEASE_URL}",
        f"  Källkod: {REPO_URL}",
        f"  AI-chatt: {chat.OLLAMA_MODEL if chat.OLLAMA_URL else 'avstängd'}",
        "=" * 60,
    ):
        log.info(line)
    task = asyncio.create_task(scheduler())
    yield
    task.cancel()


app = FastAPI(title="Värmlandsinfo", version=__version__, lifespan=lifespan)


def status() -> dict:
    s = events.state
    return {
        "version": __version__,
        "release_url": RELEASE_URL,
        "events": len(s["events"]),
        "updated": s["updated"],
        "refreshing": s["refreshing"],
        "next_refresh": schedule["next_refresh"],
        "error": s["error"],
        "api_calls": stats["api_calls"],
        "sources": s["sources"],
        "storage": {"dir": str(events.DATA_DIR), "error": s["storage_error"]},
        "chat": chat.chat_config(),
    }


@app.get("/api/events")
async def get_events():
    return {**status(), "today": events.today().isoformat(), "events": events.current_events()}


@app.get("/api/health")
async def health():
    return {"ok": True, **status()}


@app.post("/api/refresh")
async def refresh():
    message = await events.manual_refresh()
    return {**status(), "message": message}


class ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(max_length=50)


@app.get("/api/chat/status")
async def chat_status():
    return await chat.ollama_status()


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    stream = chat.chat_stream([m.model_dump() for m in req.messages], events.current_events(), events.today())
    return StreamingResponse(stream, media_type="application/x-ndjson")


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """Filer med version i adressen cachas länge. Allt annat kontrolleras mot servern varje gång."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/static/") and request.query_params.get("v") == __version__:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


def _render_index() -> str:
    """index.html med versionen i adresserna till stil, skript och ikoner, så att en uppgradering
    alltid ger nya filer i webbläsaren."""
    page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return re.sub(r'((?:href|src)="/(?:static/[^"?]+|manifest\.webmanifest))"', rf'\1?v={__version__}"', page)


INDEX_HTML = _render_index()


@app.get("/")
async def index():
    return HTMLResponse(INDEX_HTML, headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(STATIC_DIR / "icons" / "favicon-32.png", media_type="image/png")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
