"""Följdfrågor i Fråga AI: samtalets sammanhang (#73)."""

import asyncio
import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

import access
import chat
import events
import main
import sessions
from chat import previous_events, refers_back, select_events
from sessions import Session, SessionStore

THU = date(2026, 9, 24)


def ev(title, day, municipality="Karlstad", cat="Sport, motion och hälsa", place=None):
    return {"title": title, "summary": "", "description": "", "organizer": None,
            "place": {"title": place} if place else None, "municipality": municipality,
            "url": f"https://x/{title.replace(' ', '-')}", "categories": [{"title": cat}],
            "occasions": [{"date_start": day, "date_end": day, "time_start": "19:00", "time_end": None}]}


BOLTIC = [ev("IF Boltic - Djurgårdens IF Bandy", "2026-10-16", place="Tingvalla Isstadion"),
          ev("IF Boltic - Tranås BoIS", "2026-10-24", place="Tingvalla Isstadion")]
OTHER = [ev("Bokcirkel", "2026-09-26", municipality="Torsby", cat="Böcker och litteratur"),
         ev("Höstkonsert", "2026-09-26", cat="Musik")]
EVENTS = BOLTIC + OTHER
SOURCES = [{"title": e["title"], "url": e["url"], "date": e["occasions"][0]["date_start"]} for e in BOLTIC]


def test_refers_back():
    for q in ["Vilken tid börjar den?", "Hur tar jag mig dit?", "Och matchen efter det?", "Var ligger arenan?",
              "Vad kostar det?", "Berätta mer om det första förslaget", "Vilken av dem passar bäst?"]:
        assert refers_back(q, EVENTS, THU), q
    for q in ["Finns det något gratis?", "Vad händer i Karlstad den här veckan?", "Vad händer i helgen?",
              "Och på söndag då?", "När spelar Färjestad?", "Var ligger arenan i Torsby?",
              "Är det något för barn?", "Vilka konserter finns det här månaden?"]:
        assert not refers_back(q, EVENTS, THU), q


def test_previous_events_are_first_in_the_selection():
    pinned = previous_events(SOURCES, EVENTS)
    assert [e["title"] for e in pinned] == [e["title"] for e in BOLTIC]
    sel = select_events("Mot vilket lag?", EVENTS, THU, pinned=pinned)
    assert [e["title"] for e, _ in sel["events"]][:2] == [e["title"] for e in BOLTIC]
    assert sel["pinned"] == 2 and len(sel["events"]) == len(EVENTS)          # inga dubbletter
    prompt = chat.build_system_prompt(sel, THU, len(EVENTS))
    assert "De 2 första evenemangen nedan är de som samtalets tidigare svar handlade om." in prompt
    assert prompt.index("IF Boltic - Djurgårdens") < prompt.index("Bokcirkel")


def test_session_previous_sources_prefer_what_the_answer_mentioned():
    s = Session(id="x")
    s.history = [
        {"role": "user", "content": "Tips i helgen?"},
        {"role": "assistant", "content": f"Gå på [Höstkonsert]({OTHER[1]['url']})!",
         "sources": [{"title": e["title"], "url": e["url"]} for e in EVENTS]},     # underlaget: 4 evenemang
        {"role": "user", "content": "När spelar Boltic?"},
        {"role": "assistant", "content": "Lista", "sources": SOURCES},           # inga länkar i texten
    ]
    assert [x["title"] for x in s.previous_sources()] == [e["title"] for e in BOLTIC] + ["Höstkonsert"]


def run(messages, monkeypatch, ollama="http://ollama", previous=None):
    seen = {}

    async def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text=json.dumps({"message": {"content": "Kl. 19:00."}, "done": True}))

    real = httpx.AsyncClient
    monkeypatch.setattr(chat.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(chat, "OLLAMA_URL", ollama)
    monkeypatch.setattr(chat, "cache", None)
    monkeypatch.setattr(chat.websearch, "enabled", lambda: False)

    async def go():
        return [json.loads(x) async for x in chat.chat_stream(messages, EVENTS, THU, "v", previous_sources=previous)]
    return asyncio.run(go()), seen


CONVERSATION = [{"role": "user", "content": "När spelar Boltic nästa gång?"},
                {"role": "assistant", "content": "**Nästa tillfälle:** IF Boltic - Djurgårdens IF Bandy"},
                {"role": "user", "content": "Vilken tid börjar den?"}]


def test_followup_goes_to_ai_with_history_and_previous_events(monkeypatch):
    assert chat.classify("Vilken tid börjar den?") == "search"            # utan samtal vore det en sökning
    out, seen = run(CONVERSATION, monkeypatch, previous=SOURCES)
    assert out[-1] == {"type": "done"} and {"type": "delta", "text": "Kl. 19:00."} in out
    msgs = seen["body"]["messages"]
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]   # hela samtalet
    system = msgs[0]["content"]
    assert system.index("### IF Boltic - Djurgårdens IF Bandy") < system.index("### Bokcirkel")
    sources = next(x for x in out if x["type"] == "sources")["events"]
    assert [s["title"] for s in sources][:2] == [e["title"] for e in BOLTIC]


def test_followup_without_ollama_shows_previous_events(monkeypatch):
    out, _ = run(CONVERSATION, monkeypatch, ollama="", previous=SOURCES)
    text = "".join(x["text"] for x in out if x["type"] == "delta")
    assert text.startswith(chat.FOLLOWUP_NOTE)
    assert [s["title"] for s in next(x for x in out if x["type"] == "sources")["events"]] == [e["title"] for e in BOLTIC]
    assert out[-1] == {"type": "done", "mode": "search"}


def test_followup_with_own_criteria_is_still_a_search(monkeypatch):
    conv = CONVERSATION[:2] + [{"role": "user", "content": "Vilka konserter finns i helgen?"}]
    out, seen = run(conv, monkeypatch, previous=SOURCES)
    assert out[-1]["mode"] == "search" and "body" not in seen
    assert [s["title"] for s in next(x for x in out if x["type"] == "sources")["events"]] == ["Höstkonsert"]


def test_first_question_is_unchanged(monkeypatch):
    out, seen = run([{"role": "user", "content": "Vilken tid börjar den?"}], monkeypatch, previous=SOURCES)
    assert out[-1].get("mode") == "search" and "body" not in seen            # inget samtal, ingen följdfråga


# ---------------------------------------------------------------- via API:t

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(sessions, "store", SessionStore())
    monkeypatch.setattr(access, "chat_limiter", access.IpLimiter())
    monkeypatch.setattr(events, "current_events", lambda: EVENTS)
    return TestClient(main.app)


def test_api_passes_previous_answer_to_followups(client, monkeypatch):
    seen = {}

    async def stream(messages, evs, today, *a, previous_sources=None, **kw):
        seen.setdefault("previous", []).append(previous_sources)
        yield json.dumps({"type": "sources", "events": SOURCES}) + "\n"
        yield json.dumps({"type": "delta", "text": f"[{BOLTIC[0]['title']}]({BOLTIC[0]['url']})"}) + "\n"
        yield json.dumps({"type": "done", "mode": "search"}) + "\n"
    monkeypatch.setattr(chat, "chat_stream", stream)
    first = client.post("/api/chat", json={"question": "När spelar Boltic?"})
    sid = json.loads(first.text.splitlines()[0])["id"]
    client.post("/api/chat", json={"question": "Vilken tid börjar den?"}, headers={"X-Chat-Session": sid})
    assert seen["previous"][0] == []
    assert [s["title"] for s in seen["previous"][1]] == [BOLTIC[0]["title"]]     # det svaret länkade

    # Nytt samtal (och när man lämnar sidan): historiken tas bort på servern
    assert client.delete("/api/chat/session", headers={"X-Chat-Session": sid}).json() == {"reset": True}
    assert client.get("/api/chat/session", headers={"X-Chat-Session": sid}).json()["messages"] == []
