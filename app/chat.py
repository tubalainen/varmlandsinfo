"""AI-chatt: väljer ut relevanta evenemang för en fråga och låter Ollama svara."""

import json
import logging
import os
import re
from collections.abc import AsyncIterator
from datetime import date, timedelta

import httpx

from chat_cache import AnswerCache
from chat_cache import normalize as normalize_question

log = logging.getLogger("varmlandsinfo.chat")



def base_url(url: str) -> str:
    """Tillåter både http://värd:11434 och fullständiga endpoint-URL:er (t.ex. /v1/chat/completions)."""
    url = url.strip().rstrip("/")
    return re.sub(r"(/v1(/chat/completions|/completions)?|/api(/chat|/generate)?)$", "", url)


OLLAMA_URL = base_url(os.getenv("OLLAMA_URL", ""))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
CHAT_MAX_EVENTS = int(os.getenv("CHAT_MAX_EVENTS", "40"))
MAX_HISTORY = 10

# Fördefinierade frågor i Fråga AI. Svaren på dem sparas alltid (se chat_cache.py).
SUGGESTIONS = [
    {"title": "I helgen", "tag": "Helg", "q": "Vad händer i Värmland i helgen? Ge mig de bästa tipsen."},
    {"title": "Barn & familj", "tag": "Barn", "q": "Finns det några barnaktiviteter i Karlstad nästa vecka?"},
    {"title": "Konserter", "tag": "Musik", "q": "Vilka konserter finns i Värmland den här månaden?"},
    {"title": "Färjestad BK", "tag": "Sport", "q": "När spelar Färjestad hemma nästa gång?"},
    {"title": "Teater & humor", "tag": "Scen", "q": "Vilka föreställningar går på Scalateatern och Karlstad CCC framöver?"},
    {"title": "Gratis", "tag": "Gratis", "q": "Vilka gratisevenemang finns i Värmland i helgen?"},
]
QUICK = [
    {"label": "Idag", "q": "Vad händer idag?"},
    {"label": "I helgen", "q": "Vad händer i helgen?"},
    {"label": "Nästa vecka", "q": "Vad händer nästa vecka?"},
    {"label": "Gratis", "q": "Vilka gratisevenemang finns i helgen?"},
    {"label": "Barn", "q": "Vilka barnaktiviteter finns i helgen?"},
    {"label": "Musik", "q": "Vilka konserter finns nästa vecka?"},
    {"label": "Sport", "q": "Vilka sportevenemang finns i helgen?"},
    {"label": "Karlstad", "q": "Vad händer i Karlstad i helgen?"},
    {"label": "Arvika", "q": "Vad händer i Arvika den här månaden?"},
]

cache: AnswerCache | None = None   # sätts vid start i main.py


def presets() -> dict:
    return {"suggestions": SUGGESTIONS, "quick": QUICK}


def is_preset(question: str) -> bool:
    key = normalize_question(question)
    return any(normalize_question(p["q"]) == key for p in SUGGESTIONS + QUICK)

WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli",
          "augusti", "september", "oktober", "november", "december"]

# Ordstammar som pekar ut en evenemangstyp
CATEGORY_WORDS = {
    "Musik": ["musik", "konsert", "spelning", "band", "kör", "jazz", "rock", "opera", "sång", "artist"],
    "Teater och underhållning": ["teater", "revy", "standup", "stand-up", "komik", "show", "föreställning", "underhållning", "musikal", "film", "bio"],
    "Dans": ["dans"],
    "Utställning": ["utställning", "konst", "museum", "museer", "galleri", "vernissage"],
    "Föreläsning och workshop": ["föreläsning", "föredrag", "workshop", "kurs", "seminarium", "prova på"],
    "Sport, motion och hälsa": ["sport", "idrott", "hockey", "fotboll", "match", "lopp", "motion", "hälsa", "yoga", "löpning", "skid", "cykel", "träning"],
    "Barn": ["barn", "familj", "unga", "ungdom", "kids", "lov"],
    "Marknad, mässa, auktion och loppis": ["marknad", "mässa", "auktion", "loppis", "julmarknad", "hantverk"],
    "Mat och dryck": ["mat", "dryck", "middag", "lunch", "provning", "vin", "öl", "restaurang", "brunch", "fika"],
    "Guidning": ["guid", "visning", "rundtur", "vandring"],
    "Motor": ["motor", "bil", "veteranbil", "mc", "motorcykel", "traktor"],
    "På vatten": ["båt", "vatten", "paddl", "kanot", "segl"],
    "Gratis": ["gratis", "fri entré", "fritt inträde", "gratisevenemang", "kostnadsfri"],
}

STOPWORDS = set("""
alla allt att av bara blir de dem den denna deras det detta dig din du där efter eller en ett fanns finns
för från följande gå går ha har hej hur i idag imorgon inte ja jag kan kanske kommer man med men mig mitt
mot mycket någon något några när nästa och om oss på sig ska skulle som så tack till tips under upp ut
vad var vi vilka vilken vilket vill visa värmland värmlands år är åt över evenemang evenemanget händer
hända hänt helgen helg vecka veckan veckor dag dagar kväll ikväll morgon månad månaden gärna ge någon
något ngt finns några blir kul roligt göra gör hittar hitta rekommendera förslag the and what where when
""".split())


def chat_config() -> dict:
    return {"enabled": bool(OLLAMA_URL), "model": OLLAMA_MODEL if OLLAMA_URL else None}


# ---------------------------------------------------------------- tolkning av frågan

def _weekend(d: date, weeks_ahead: int = 0) -> tuple[date, date]:
    """Kommande helg (fredag–söndag från fredag, annars lördag–söndag)."""
    sunday = d + timedelta(days=6 - d.weekday() + 7 * weeks_ahead)
    saturday = sunday - timedelta(days=1)
    if weeks_ahead == 0:
        return (min(d, saturday) if d.weekday() >= 4 else saturday), sunday
    return saturday, sunday


def parse_date_range(text: str, today: date) -> tuple[date, date] | None:
    """Tolkar svenska tidsuttryck (idag, i helgen, nästa vecka, 3 oktober …) till ett datumintervall."""
    t = text.lower()

    if m := re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", t):
        try:
            d = date(int(m[1]), int(m[2]), int(m[3]))
            return d, d
        except ValueError:
            pass

    month_re = "|".join(MONTHS)
    if m := re.search(rf"\b(\d{{1,2}})(?:e|:e)?\s+({month_re}|jan|feb|mar|apr|jun|jul|aug|sep|sept|okt|nov|dec)\b", t):
        month = next(i for i, name in enumerate(MONTHS, 1) if name.startswith(m[2][:3]))
        year = today.year + (1 if month < today.month else 0)
        try:
            d = date(year, month, int(m[1]))
            return d, d
        except ValueError:
            pass
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})\b", t):
        day, month = int(m[1]), int(m[2])
        if 1 <= month <= 12:
            year = today.year + (1 if month < today.month else 0)
            try:
                d = date(year, month, day)
                return d, d
            except ValueError:
                pass

    if re.search(r"\b(idag|i dag|ikväll|i kväll|ikväl|just nu)\b", t):
        return today, today
    if re.search(r"\b(i övermorgon|övermorgon)\b", t):
        d = today + timedelta(days=2)
        return d, d
    if re.search(r"\b(imorgon|i morgon|imorn|i morn)\b", t):
        d = today + timedelta(days=1)
        return d, d
    if re.search(r"\bnästa helg\b", t):
        return _weekend(today, 1)
    if re.search(r"\b(i helgen|helgen|denna helg|den här helgen|till helgen)\b", t):
        return _weekend(today)
    if re.search(r"\bnästa vecka\b", t):
        monday = today + timedelta(days=7 - today.weekday())
        return monday, monday + timedelta(days=6)
    if re.search(r"\b(i veckan|denna vecka|den här veckan|veckan)\b", t):
        return today, today + timedelta(days=6 - today.weekday())
    if re.search(r"\bnästa månad\b", t):
        first = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        return first, (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    if re.search(r"\b(i månaden|denna månad|den här månaden)\b", t):
        return today, (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    for i, name in enumerate(WEEKDAYS):
        if re.search(rf"\b(på |nu på |i )?{name}(en|s)?\b", t):
            d = today + timedelta(days=(i - today.weekday()) % 7)
            if re.search(rf"\bnästa {name}", t) and d == today:
                d += timedelta(days=7)
            return d, d

    if m := re.search(rf"\b({month_re})\b", t):
        month = MONTHS.index(m[1]) + 1
        year = today.year + (1 if month < today.month else 0)
        first = date(year, month, 1)
        last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return max(first, today), last
    return None


def find_municipalities(text: str, municipalities: list[str]) -> set[str]:
    t = text.lower()
    return {m for m in municipalities if re.search(rf"\b{re.escape(m.lower())}s?\b", t)}


def find_categories(text: str) -> set[str]:
    words = re.findall(r"[a-zåäöé\-]+", text.lower())
    found = set()
    for cat, stems in CATEGORY_WORDS.items():
        for stem in stems:
            if " " in stem:
                if stem in text.lower():
                    found.add(cat)
            elif any(w.startswith(stem) for w in words):
                found.add(cat)
    return found


def keywords(text: str) -> list[str]:
    words = re.findall(r"[0-9a-zåäöéü]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS and w not in WEEKDAYS and w not in MONTHS]


def _stem(w: str) -> str:
    return w[:6] if len(w) > 6 else w


# ---------------------------------------------------------------- urval av evenemang

def select_events(question: str, events: list[dict], today: date, limit: int = CHAT_MAX_EVENTS,
                  context: str = "") -> dict:
    """Väljer ut de evenemang som är mest relevanta för frågan.

    `context` är tidigare frågor i samtalet. Därifrån ärvs datum, kommun och typ
    när följdfrågan inte själv anger dem ("och på söndag då?").
    """
    municipalities = sorted({e["municipality"] for e in events if e.get("municipality")})
    date_range = parse_date_range(question, today) or (parse_date_range(context, today) if context else None)
    munis = find_municipalities(question, municipalities) or find_municipalities(context, municipalities)
    cats = find_categories(question) or (find_categories(context) if context else set())
    kws = [_stem(w) for w in keywords(question)
           if not any(w.startswith(m.lower()) for m in munis)]

    def in_range(e):
        if not date_range:
            return e["occasions"]
        lo, hi = date_range[0].isoformat(), date_range[1].isoformat()
        return [o for o in e["occasions"] if o["date_end"] >= lo and o["date_start"] <= hi]

    candidates = []
    for e in events:
        occ = in_range(e)
        if not occ:
            continue
        if munis and e.get("municipality") not in munis:
            continue
        candidates.append((e, occ))

    if cats:
        # Gratis är ett krav ("gratis konserter" = gratis OCH musik), övriga typer räcker det att en matchar
        def ok(e):
            titles = {c["title"] for c in e["categories"]}
            if "Gratis" in cats and "Gratis" not in titles:
                return False
            others = cats - {"Gratis"}
            return not others or bool(titles & others)
        with_cat = [(e, o) for e, o in candidates if ok(e)]
        if with_cat:
            candidates = with_cat

    def score(e):
        if not kws:
            return 0
        title = e["title"].lower()
        rest = " ".join(filter(None, [
            e.get("summary"), e.get("description"), e.get("organizer"),
            (e.get("place") or {}).get("title"), " ".join(c["title"] for c in e["categories"]),
        ])).lower()
        return sum(3 * (k in title) + (k in rest) for k in kws)

    scored = [(score(e), e, occ) for e, occ in candidates]
    if kws and any(s for s, _, _ in scored) and not (cats or munis or date_range):
        scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[2][0]["date_start"], x[2][0]["time_start"] or ""))
    chosen = scored[:limit]
    chosen.sort(key=lambda x: (x[2][0]["date_start"], x[2][0]["time_start"] or ""))

    return {
        "date_range": date_range,
        "municipalities": sorted(munis),
        "categories": sorted(cats),
        "total_matches": len(scored),
        "events": [(e, occ) for _, e, occ in chosen],
    }


def _fmt_occ(o: dict) -> str:
    d = date.fromisoformat(o["date_start"])
    s = f"{WEEKDAYS[d.weekday()]} {d.isoformat()}"
    if o.get("time_start"):
        s += f" kl. {o['time_start']}" + (f"–{o['time_end']}" if o.get("time_end") else "")
    return s


def format_event(e: dict, occ: list[dict]) -> str:
    dates = "; ".join(_fmt_occ(o) for o in occ[:6])
    if len(occ) > 6:
        dates += f" (+{len(occ) - 6} fler tillfällen, sista {occ[-1]['date_start']})"
    lines = [
        f"### {e['title']}",
        f"- Datum: {dates}",
        f"- Typ: {', '.join(c['title'] for c in e['categories'])}",
    ]
    where = ", ".join(x for x in [(e.get("place") or {}).get("title"), e.get("municipality")] if x)
    if where:
        lines.append(f"- Plats: {where}")
    if e.get("organizer"):
        lines.append(f"- Arrangör: {e['organizer']}")
    desc = e.get("summary") or (e.get("description") or "")[:300]
    if desc:
        lines.append(f"- Beskrivning: {desc}")
    if e.get("url"):
        lines.append(f"- Länk: {e['url']}")
    others = [s for s in e.get("sources") or [] if s.get("url") and s.get("url") != e.get("url")]
    for s in others:
        lines.append(f"- Även hos {s['name']}: {s['url']}")
    if e.get("booking_link"):
        lines.append(f"- Biljetter: {e['booking_link']}")
    return "\n".join(lines)


def build_system_prompt(selection: dict, today: date, total_events: int) -> str:
    parts = [
        "Du är en hjälpsam och kunnig guide till evenemang i Värmland.",
        f"Dagens datum är {WEEKDAYS[today.weekday()]} {today.isoformat()}.",
        "Svara på samma språk som frågan (normalt svenska), kortfattat och tydligt.",
        "Använd ENDAST evenemangen i listan nedan som källa. Hitta aldrig på evenemang, datum, tider eller platser.",
        "Om inget i listan passar frågan, säg det ärligt och föreslå gärna hur frågan kan formuleras om.",
        "Ange datum, tid och plats för evenemang du nämner, och länka dem i markdown-format: [Titel](länk).",
        "",
        f"Databasen innehåller totalt {total_events} aktuella evenemang.",
    ]
    filt = []
    if selection["date_range"]:
        lo, hi = selection["date_range"]
        filt.append(f"datum {lo.isoformat()}" + (f" till {hi.isoformat()}" if hi != lo else ""))
    if selection["municipalities"]:
        filt.append("kommun: " + ", ".join(selection["municipalities"]))
    if selection["categories"]:
        filt.append("typ: " + ", ".join(selection["categories"]))
    if filt:
        parts.append("Urvalet nedan är filtrerat på " + "; ".join(filt) + ".")
    shown = len(selection["events"])
    parts.append(f"{selection['total_matches']} evenemang matchar urvalet, {shown} visas nedan"
                 + (" (de mest relevanta)." if selection["total_matches"] > shown else "."))
    parts.append("")
    parts.append("## Evenemang")
    parts.extend(format_event(e, occ) for e, occ in selection["events"])
    if not selection["events"]:
        parts.append("(Inga evenemang matchade frågan.)")
    return "\n".join(parts)


# ---------------------------------------------------------------- Ollama

async def ollama_status() -> dict:
    cfg = chat_config()
    if not cfg["enabled"]:
        return {**cfg, "reachable": False, "error": "OLLAMA_URL är inte satt"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            models = [m.get("name") for m in r.json().get("models", [])]
        err = None
        if OLLAMA_MODEL not in models and f"{OLLAMA_MODEL}:latest" not in models:
            err = f"Modellen {OLLAMA_MODEL} finns inte i Ollama. Kör: ollama pull {OLLAMA_MODEL}"
        return {**cfg, "reachable": True, "models": models, "error": err}
    except Exception as exc:
        return {**cfg, "reachable": False, "error": f"Kan inte nå Ollama på {OLLAMA_URL}: {exc}"}


def _ndjson(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


async def chat_stream(messages: list[dict], events: list[dict], today: date,
                      data_version: str | None = None) -> AsyncIterator[str]:
    """Strömmar svaret som NDJSON: sources, delta …, done eller error.

    Fristående frågor (utan samtalshistorik) besvaras från sparade svar när frågan, dagen, datan och
    modellen är desamma. Annars ställs frågan till Ollama och svaret sparas."""
    if not OLLAMA_URL:
        yield _ndjson({"type": "error", "error": "AI-chatten är inte konfigurerad. Sätt OLLAMA_URL i docker-compose.yaml."})
        return

    history = [
        {"role": m["role"], "content": str(m.get("content", ""))[:4000]}
        for m in messages if m.get("role") in ("user", "assistant") and m.get("content")
    ][-MAX_HISTORY:]
    if not history or history[-1]["role"] != "user":
        yield _ndjson({"type": "error", "error": "Ingen fråga att besvara."})
        return

    question = history[-1]["content"]
    standalone = len(history) == 1
    ctx = {"day": today.isoformat(), "data": data_version, "model": OLLAMA_MODEL}
    if standalone and cache:
        hit = cache.get(question, ctx)
        if hit:
            yield _ndjson({"type": "sources", "events": hit["sources"]})
            yield _ndjson({"type": "delta", "text": hit["answer"]})
            yield _ndjson({"type": "done", "cached": True, "saved": hit.get("saved")})
            return

    # Följdfrågor ("och på söndag då?") saknar ofta sammanhang, så tidigare frågor tas med i sökningen
    user_turns = [m["content"] for m in history if m["role"] == "user"]
    selection = select_events(user_turns[-1], events, today, context=" ".join(user_turns[-3:-1]))
    sources = [{"title": e["title"], "url": e.get("url"), "date": occ[0]["date_start"]}
               for e, occ in selection["events"]]
    yield _ndjson({"type": "sources", "events": sources})

    payload = {
        "model": OLLAMA_MODEL,
        "stream": True,
        "messages": [{"role": "system", "content": build_system_prompt(selection, today, len(events))}, *history],
        "options": {"num_ctx": OLLAMA_NUM_CTX, "temperature": 0.2},
    }
    answer, complete = "", False
    try:
        timeout = httpx.Timeout(10, read=300)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    body = (await r.aread()).decode(errors="replace")[:300]
                    yield _ndjson({"type": "error", "error": f"Ollama svarade {r.status_code}: {body}"})
                    return
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        yield _ndjson({"type": "error", "error": data["error"]})
                        return
                    text = (data.get("message") or {}).get("content")
                    if text:
                        answer += text
                        yield _ndjson({"type": "delta", "text": text})
                    if data.get("done"):
                        complete = True
                        break
        yield _ndjson({"type": "done"})
    except Exception as exc:
        log.warning("Ollama-anrop misslyckades: %s", exc)
        yield _ndjson({"type": "error", "error": f"Kunde inte prata med Ollama ({OLLAMA_URL}): {exc}"})
        return
    # Bara kompletta svar på fristående frågor sparas
    if standalone and cache and complete and answer.strip():
        cache.put(question, ctx, answer, sources, preset=is_preset(question))
