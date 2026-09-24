"""Värmlandsinfo – samlar evenemang i Värmland och visar dem i ett webbgränssnitt."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import chat
import events
from version import __version__

DAILY_REFRESH_TIME = os.getenv("DAILY_REFRESH_TIME", "05:00")
REFRESH_MINUTES = int(os.getenv("REFRESH_MINUTES", "0"))  # 0 = bara daglig körning
STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("varmlandsinfo")

schedule: dict = {"next_refresh": None}


def _daily_at(now: datetime) -> datetime:
    h, m = (int(x) for x in DAILY_REFRESH_TIME.split(":"))
    return datetime.combine(now.date(), time(h, m), tzinfo=events.TZ)


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
    loaded = await asyncio.to_thread(events.load_cache)
    if not loaded or needs_refresh(events.state["updated"], datetime.now(events.TZ)):
        await events.refresh()
    else:
        log.info("Sparad data är aktuell, ingen hämtning vid start")
    while True:
        target = next_run(datetime.now(events.TZ))
        schedule["next_refresh"] = target.isoformat(timespec="minutes")
        log.info("Nästa schemalagda uppdatering: %s", schedule["next_refresh"])
        await asyncio.sleep(max(1, (target - datetime.now(events.TZ)).total_seconds()))
        await events.refresh()


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("Värmlandsinfo %s startar (AI-chatt: %s)", __version__,
             chat.OLLAMA_MODEL if chat.OLLAMA_URL else "avstängd")
    task = asyncio.create_task(scheduler())
    yield
    task.cancel()


app = FastAPI(title="Värmlandsinfo", version=__version__, lifespan=lifespan)


def status() -> dict:
    s = events.state
    return {
        "version": __version__,
        "events": len(s["events"]),
        "updated": s["updated"],
        "refreshing": s["refreshing"],
        "next_refresh": schedule["next_refresh"],
        "error": s["error"],
        "storage": {"file": str(events.CACHE_FILE), "error": s["storage_error"]},
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
    await events.refresh()
    return status()


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


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
