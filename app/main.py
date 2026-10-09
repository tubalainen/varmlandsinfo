"""Värmlandsinfo – samlar evenemang i Värmland och visar dem i ett webbgränssnitt."""

import asyncio
import base64
import binascii
import logging
import math
import json
import re
import secrets
from contextlib import aclosing, asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import access
import besoksinfo
import chat
import events
import geoip
import images
import sessions
import timetable
import visits
from common import TZ, stats
from version import RELEASE_URL, REPO_URL, __version__

STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# httpx loggar hela URL:en inklusive frågesträngen, där API-nycklar kan finnas
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("varmlandsinfo")


plan = timetable.Timetable()   # dagens slumpade hämtschema (#104), sparas när schemaläggaren startat
schedule: dict = {"next_refresh": None}


def cleanup(now: datetime, conversations: bool = False) -> None:
    """Städar bort inaktuell data. Körs efter varje hämtning från källorna och vid start:
    källdata som är äldre än dagens hämtning av källan (och från avstängda källor), inaktuella AI-svar, bilder som
    inte hör till något evenemang, samtal som inte använts på 2 timmar, IP-adresser som inte längre räknas i spärren
    för Fråga AI och, när dagens hämtningar är klara, alla chattsamtal."""
    events.purge_old(lambda key: plan.cutoff(key, now))
    chat.prune_cache(events.today(), events.state["updated"])
    if n := image_proxy.prune(events.state["events"]):
        log.info("Rensade %d bilder som inte hör till något evenemang", n)
    sessions.store.expire()
    access.chat_limiter.prune()
    login_limiter.prune()
    if visits.store and any(n := visits.store.cleanup(events.today())):
        log.info("Besöksstatistik: summerade %d dygn (IP-adresserna togs bort) och rensade %d gamla dagar", *n)
    if conversations and (n := sessions.store.clear()):
        log.info("Rensade %d chattsamtal", n)


async def update_geoip() -> None:
    """Hämtar DB-IP:s geodatabas till besöksstatistiken när den saknas eller är äldre än en månad."""
    if visits.store and visits.store.geo:
        await visits.store.geo.ensure(events.today())


def enabled_sources() -> list[str]:
    return [k for k, v in events.state["sources"].items() if v["enabled"]]


async def fetch(key: str, attempt: int) -> tuple[datetime, str, int] | None:
    """Dagens hämtning av en källa. Första försöket även när källan är pausad (nekade åtkomst), och högst två nya
    försök när den fallerar (inte när den är pausad). Returnerar nästa försök, eller None när källan är klar för
    dagen. När alla källor är klara städas även chattsamtalen bort."""
    await events.refresh([key], include_paused=attempt == 0)
    now = datetime.now(TZ)
    info = events.state["sources"][key]
    if info["error"] and not info["paused"] and attempt < timetable.RETRIES:
        when = timetable.retry_time(now, timetable.RETRIES - attempt - 1)
        log.info("Nytt försök %d av %d med %s kl. %s", attempt + 1, timetable.RETRIES, info["title"],
                 when.strftime("%H.%M"))
        cleanup(now)
        return when, key, attempt + 1
    plan.mark_done(key, now)
    if plan.all_done(enabled_sources(), now):
        plan.complete(now)
        log.info("Dagens hämtningar är klara")
        cleanup(now, conversations=True)
        await update_geoip()
    else:
        cleanup(now)
    return None


async def scheduler() -> None:
    """Hämtar varje källa en gång per dag vid dess slumpade tid (timetable), med nya försök. Vid midnatt dras
    nya tider."""
    await asyncio.to_thread(events.load_cache)
    plan.path = events.DATA_DIR / "schema.json"
    plan.load()
    if not plan.completed:     # före #104: den senaste hämtningen
        plan.completed = events.state["updated"]
    now = datetime.now(TZ)
    jobs = plan.jobs_at_start(now, {k: events.state["sources"][k]["updated"] for k in enabled_sources()})
    if due := [key for when, key, _ in jobs if when <= now]:
        log.info("Hämtar vid start: %s", ", ".join(due))
    else:
        log.info("Sparad data är aktuell, ingen hämtning vid start")
        cleanup(now)
        await update_geoip()
    while True:
        now = datetime.now(TZ)
        if plan.day != now.date():     # nytt dygn: nya slumpade tider
            jobs = plan.jobs_at_start(now, {k: events.state["sources"][k]["updated"] for k in enabled_sources()})
        jobs.sort()
        schedule["next_refresh"] = jobs[0][0].isoformat(timespec="minutes") if jobs else None
        if jobs and jobs[0][0] <= now:
            _, key, attempt = jobs.pop(0)
            if not plan.done_today(key, now) and (retry := await fetch(key, attempt)):
                jobs.append(retry)
            continue
        tomorrow = timetable.midnight(now.date() + timedelta(days=1)) + timedelta(seconds=1)
        wake = min(jobs[0][0], tomorrow) if jobs else tomorrow
        await asyncio.sleep(max(1.0, (wake - datetime.now(TZ)).total_seconds()))


@asynccontextmanager
async def lifespan(_: FastAPI):
    for line in (
        "=" * 60,
        f"  Värmlandsinfo v{__version__}",
        f"  Release: {RELEASE_URL}",
        f"  Källkod: {REPO_URL}",
        f"  Fråga AI: {'dold (CHAT_ENABLED=false)' if not chat.CHAT_ENABLED else chat.OLLAMA_MODEL if chat.OLLAMA_URL else 'bara sökfrågor (ingen OLLAMA_URL)'}",
        "=" * 60,
    ):
        log.info(line)
    chat.cache = chat.AnswerCache(events.DATA_DIR / "chat_cache.json")
    chat.cache.load()
    if visits.enabled():
        visits.store = visits.VisitStats(events.DATA_DIR / "besoksinfo.json",
                                         geo=geoip.GeoIP(events.DATA_DIR / "geoip" / "dbip-city-lite.mmdb"))
        visits.store.load()
        log.info("  Besöksstatistik: på (/besoksinfo)")
    task = asyncio.create_task(scheduler())
    yield
    task.cancel()
    if visits.store:
        visits.store.save()


# Ingen automatisk API-dokumentation (/docs, /redoc, /openapi.json): API:t är till för appens eget gränssnitt
app = FastAPI(title="Värmlandsinfo", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None,
              openapi_url=None)


STORAGE_ERROR = "Appen kan inte spara hämtad data, så den finns bara i minnet. Se loggen."


def status(detail: bool = False) -> dict:
    """Appens status. Datakatalogen och fullständiga lagringsfel bara med `detail` (/api/health, bara lokalt, #87)."""
    s = events.state
    storage = ({"dir": str(events.DATA_DIR), "error": s["storage_error"]} if detail
               else {"error": STORAGE_ERROR if s["storage_error"] else None})
    return {
        "version": __version__,
        "release_url": RELEASE_URL,
        "events": len(s["events"]),
        "updated": s["updated"],             # senaste hämtningen av någon källa
        "completed": plan.completed,         # när alla källor senast var hämtade (visas i appen, #104)
        "refreshing": s["refreshing"],
        "error": s["error"],
        "api_calls": stats["api_calls"],
        "sources": s["sources"],
        "storage": storage,
        "chat": chat.chat_config(),
        "visit_stats": visits.enabled(),
        # Hämtschemat visas bara lokalt, aldrig för besökarna (#104)
        **({"schedule": {"window": "–".join(t.strftime("%H:%M") for t in timetable.WINDOW),
                         "next_refresh": schedule["next_refresh"], "day": plan.day and plan.day.isoformat(),
                         "slots": plan.slots, "done": plan.done}} if detail else {}),
    }


# Bilderna visas via appen (/img/<nyckel>), så att källornas bildservrar aldrig ser besökarna
image_proxy = images.ImageProxy(events.DATA_DIR / "images")
IMAGE_KEY = re.compile(r"[0-9a-f]{32}")


@app.get("/api/events")
async def get_events():
    image_proxy.register(events.state["events"])
    return {**status(), "today": events.today().isoformat(),
            "events": image_proxy.rewrite(events.current_events())}


@app.get("/img/{key}", include_in_schema=False)
async def image(key: str):
    """En evenemangsbild. Bara bilder som finns i appens evenemang kan hämtas."""
    if not IMAGE_KEY.fullmatch(key):
        return Response(status_code=404)
    image_proxy.register(events.state["events"])
    try:
        hit = await image_proxy.get(key)
    except images.Busy:
        return Response(status_code=503, headers={"Cache-Control": "no-store", "Retry-After": "60"})
    if not hit:
        return Response(status_code=404, headers={"Cache-Control": "no-store"})
    data, kind = hit
    return Response(data, media_type=kind,
                    headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})


@app.get("/api/health", dependencies=[Depends(access.require_local)])
async def health():
    return {"ok": True, **status(detail=True)}


@app.post("/api/refresh", dependencies=[Depends(access.require_local)])
async def refresh():
    message = await events.manual_refresh()
    if not message:
        # Källorna som hämtades räknas som dagens hämtning, och städningen görs efter varje hämtning
        now = datetime.now(TZ)
        for key in enabled_sources():
            if not events.state["sources"][key]["error"]:
                plan.mark_done(key, now)
        plan.complete(now)
        cleanup(now)
    return {**status(detail=True), "message": message}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


SessionHeader = Header(default=None, alias="X-Chat-Session", max_length=100)


def require_chat() -> None:
    """Fråga AI finns inte när funktionen är avstängd (CHAT_ENABLED=false)."""
    if not chat.CHAT_ENABLED:
        raise HTTPException(status_code=404)


@app.get("/api/chat/presets", dependencies=[Depends(require_chat)])
async def chat_presets():
    return chat.presets()


@app.get("/api/chat/status", dependencies=[Depends(require_chat)])
async def chat_status():
    return await chat.ollama_status()


SEARCH_STILL_WORKS = "Enkla sökfrågor som \"Vad händer i helgen?\" fungerar som vanligt."


def _minutes(seconds: float) -> str:
    n = max(1, math.ceil(seconds / 60))
    return "1 minut" if n == 1 else f"{n} minuter"


@app.post("/api/chat", dependencies=[Depends(require_chat)])
async def chat_endpoint(req: ChatRequest, request: Request, session_id: str | None = SessionHeader):
    """Ny fråga i ett samtal. Samtalet (sessionen) och dess historik finns på servern, klienten skickar
    bara frågan och sitt sessions-id. Okänt eller utgånget id ger ett nytt samtal."""
    session, created = sessions.store.get_or_create(session_id)
    if sessions.store.begin(session) == "busy":
        return JSONResponse({"error": "Vänta tills svaret på förra frågan är klart."}, status_code=409)
    ip = access.client_ip(request)

    def admit() -> str | None:
        """Spärrarna gäller bara frågor som går till AI:n: per session, och per IP-adress för den som skapar
        nya sessioner för att komma runt spärren per session."""
        if wait := sessions.store.ai_wait(session):
            return (f"Du har ställt {sessions.RATE_LIMIT} frågor till AI:n på {sessions.RATE_WINDOW // 60} minuter. "
                    f"Nästa fråga till AI:n går att ställa om {_minutes(wait)}. {SEARCH_STILL_WORKS}")
        if wait := access.chat_limiter.wait(ip):
            return (f"Många frågor till AI:n har ställts från din adress den senaste halvtimmen. "
                    f"Nästa fråga till AI:n går att ställa om {_minutes(wait)}. {SEARCH_STILL_WORKS}")
        access.chat_limiter.allow(ip)
        sessions.store.count_ai(session)
        return None

    return StreamingResponse(_session_stream(session, created and bool(session_id), req.question, admit),
                             media_type="application/x-ndjson")


async def _session_stream(session: sessions.Session, expired: bool, question: str, admit=None):
    """Svaret strömmas vidare och sparas i samtalet när det är komplett."""
    answer, sources, web, meta, ok = "", [], [], {}, False
    try:
        yield json.dumps({"type": "session", "id": session.id, "expired": expired}) + "\n"
        messages = [*session.model_history(), {"role": "user", "content": question}]
        async with aclosing(chat.chat_stream(messages, events.current_events(), events.today(),
                                             data_version=events.state["updated"], admit=admit,
                                             previous_sources=session.previous_sources())) as stream:
            async for line in stream:
                ev = json.loads(line)
                if ev["type"] == "delta":
                    answer += ev["text"]
                elif ev["type"] == "sources":
                    sources = ev["events"]
                elif ev["type"] == "web":
                    web = ev["results"]
                elif ev["type"] == "done":
                    ok = not ev.get("refused")
                    meta = {k: ev[k] for k in ("mode", "cached", "saved") if k in ev}
                yield line
    finally:
        # Vägrade, avbrutna och misslyckade svar sparas inte i samtalet
        turns = [{"role": "user", "content": question},
                 {"role": "assistant", "content": answer, "sources": sources, "web": web, **meta}] if ok and answer else None
        sessions.store.end(session, turns)


@app.get("/api/chat/session", dependencies=[Depends(require_chat)])
async def chat_session(session_id: str | None = SessionHeader):
    """Samtalet för att visa det igen efter omladdning av sidan."""
    session = sessions.store.get(session_id)
    return {"messages": session.view() if session else [], "busy": bool(session and session.is_busy())}


@app.delete("/api/chat/session", dependencies=[Depends(require_chat)])
async def chat_session_reset(session_id: str | None = SessionHeader):
    """Nytt samtal: historiken på servern tas bort."""
    return {"reset": sessions.store.reset(session_id)}


MAX_BODY = 32 * 1024     # största kropp i ett anrop (en fråga i Fråga AI är högst 4000 tecken)


class BodyLimit:
    """Avvisar kroppar större än MAX_BODY med 413, både enligt Content-Length och medan kroppen tas emot, så att
    ingen kan fylla minnet med stora anrop (#89)."""

    def __init__(self, app, limit: int = MAX_BODY):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > self.limit):
            return await JSONResponse({"error": "Anropet är för stort."}, status_code=413)(scope, receive, send)
        received = 0

        async def limited():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    raise HTTPException(status_code=413, detail="Anropet är för stort.")
            return message
        await self.app(scope, limited, send)


app.add_middleware(BodyLimit)


# Säkerhetshuvuden på alla svar (#88). Sidan får dessutom en strikt CSP (PAGE_CSP).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
# Bara appens egna skript, stilar, bilder och anrop. Webbläsaren hämtar aldrig något från källorna (bilderna visas via
# appen), och sidan kan inte bäddas in i andra sidor.
PAGE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


@app.middleware("http")
async def response_headers(request: Request, call_next):
    """Säkerhetshuvuden på alla svar. Filer med version i adressen cachas länge, allt annat kontrolleras mot servern
    varje gång."""
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    # Den råa sökvägen, inte request.url.path, som byggs av Host-huvudet (jfr CVE-2026-48710, #85)
    path = request.scope["path"]
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/static/") and request.query_params.get("v") == __version__:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


def _render_index(chat_enabled: bool) -> str:
    """index.html med versionen i adresserna till stil, skript och ikoner, så att en uppgradering
    alltid ger nya filer i webbläsaren. Utan Fråga AI tas menyvalet och chattens skript bort."""
    page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    if not chat_enabled:
        page = re.sub(r'\s*<a href="#/fraga".*?</a>', "", page)
        page = page.replace('\n<script src="/static/chat.js"></script>', "")
        page = page.replace("<body>", '<body data-chat="off">', 1)
    return re.sub(r'((?:href|src)="/(?:static/[^"?]+|manifest\.webmanifest))"', rf'\1?v={__version__}"', page)


INDEX_HTML = {on: _render_index(on) for on in (True, False)}


@app.get("/")
async def index(request: Request):
    if visits.store and request.method == "GET" and "prefetch" not in request.headers.get("sec-purpose", ""):
        visits.store.record(access.client_ip(request), request.headers.get("user-agent", ""),
                            request.headers.get("referer"), request.headers.get("host"), datetime.now(TZ))
    return HTMLResponse(INDEX_HTML[chat.CHAT_ENABLED], headers={"Cache-Control": "no-cache",
                                                                 "Content-Security-Policy": PAGE_CSP})


# ---------------------------------------------------------------- besöksstatistik (dold sida)

login_limiter = access.IpLimiter(limit=10, window=15 * 60)    # felaktiga lösenord per IP-adress
PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer",
                   "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                                              "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"}


def _password_ok(authorization: str | None) -> bool | None:
    """True/False för ett angivet lösenord (HTTP Basic, valfritt användarnamn), None om inget angavs."""
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.lower() != "basic" or not value:
        return None
    try:
        _, _, password = base64.b64decode(value, validate=True).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return secrets.compare_digest(password.encode(), visits.PASSWORD.encode())


@app.get("/besoksinfo", include_in_schema=False)
async def besoksinfo_page(request: Request):
    """Besöksstatistiken. Bara när BESOKSINFO_PASSWORD är satt, och bara med lösenordet."""
    if not visits.store:
        return Response(status_code=404)
    ip = access.client_ip(request)
    if wait := login_limiter.wait(ip):
        return Response(f"För många felaktiga försök. Försök igen om {_minutes(wait)}.", status_code=429,
                        media_type="text/plain; charset=utf-8", headers=PRIVATE_HEADERS)
    ok = _password_ok(request.headers.get("authorization"))
    if not ok:
        if ok is False:
            login_limiter.allow(ip)                             # räknar det felaktiga försöket
            log.warning("Felaktigt lösenord till /besoksinfo")
        return Response("Lösenord krävs.", status_code=401, media_type="text/plain; charset=utf-8",
                        headers={**PRIVATE_HEADERS, "WWW-Authenticate": 'Basic realm="Besoksinfo", charset="UTF-8"'})
    # Perioden tolkas först här, så att inget svar avslöjar sidan innan lösenordet är kontrollerat
    dagar = request.query_params.get("dagar", "")
    period = int(dagar) if dagar.isdigit() and int(dagar) in besoksinfo.PERIODS else 30
    report = visits.store.report(events.today(), period)
    return HTMLResponse(besoksinfo.render(report, period, bool(visits.store.geo and visits.store.geo.available())),
                        headers=PRIVATE_HEADERS)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(STATIC_DIR / "icons" / "favicon-32.png", media_type="image/png")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
