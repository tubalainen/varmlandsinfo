import asyncio
import json
from datetime import date

import httpx

import chat
from chat_cache import AnswerCache, normalize

CTX = {"day": "2026-09-24", "data": "2026-09-24T05:00:00+02:00", "model": "m"}


def test_normalize():
    assert normalize("  Vad händer   IDAG? ") == "vad händer idag"


def test_cache_validity_and_limits(tmp_path):
    c = AnswerCache(tmp_path / "c.json", max_recent=3)
    c.put("Fråga 1", CTX, "svar 1", [], preset=False)
    assert c.get("fråga 1?", CTX)["answer"] == "svar 1"
    assert c.get("Fråga 1", {**CTX, "data": "ny"}) is None       # evenemangen har uppdaterats
    assert c.get("Fråga 1", {**CTX, "day": "2026-09-25"}) is None  # ny dag
    assert c.get("Fråga 1", {**CTX, "model": "annan"}) is None
    for i in range(2, 6):
        c.put(f"Fråga {i}", CTX, f"svar {i}", [], preset=False)
    assert [e["key"] for e in c.recent] == ["fråga 3", "fråga 4", "fråga 5"]   # bara de senaste
    for i in range(10):
        c.put(f"Förval {i}", CTX, "x", [], preset=True)
    assert len(c.presets) == 10 and len(c.recent) == 3            # förval räknas inte in i gränsen

    fresh = AnswerCache(tmp_path / "c.json", max_recent=3)
    fresh.load()
    assert fresh.get("Fråga 5", CTX)["answer"] == "svar 5"         # överlever omstart


def collect(gen):
    async def run():
        return [json.loads(x) async for x in gen]
    return asyncio.run(run())


def test_chat_stream_uses_cache(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        body = "\n".join(json.dumps(x) for x in [{"message": {"content": "Hej "}}, {"message": {"content": "där"}, "done": True}])
        return httpx.Response(200, text=body)

    real = httpx.AsyncClient
    monkeypatch.setattr(chat.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(chat, "OLLAMA_URL", "http://ollama")
    monkeypatch.setattr(chat, "OLLAMA_MODEL", "m")
    monkeypatch.setattr(chat, "cache", AnswerCache(tmp_path / "c.json"))

    q = chat.QUICK[0]["q"]
    first = collect(chat.chat_stream([{"role": "user", "content": q}], [], date(2026, 9, 24), "v1"))
    assert "".join(e.get("text", "") for e in first) == "Hej där" and len(calls) == 1
    assert chat.normalize_question(q) in chat.cache.presets        # förval sparas alltid

    again = collect(chat.chat_stream([{"role": "user", "content": q}], [], date(2026, 9, 24), "v1"))
    assert again[-1] == {"type": "done", "cached": True, "saved": again[-1]["saved"]}
    assert "".join(e.get("text", "") for e in again) == "Hej där" and len(calls) == 1   # ingen ny förfrågan

    collect(chat.chat_stream([{"role": "user", "content": q}], [], date(2026, 9, 24), "v2"))   # ny data
    assert len(calls) == 2

    follow = [{"role": "user", "content": q}, {"role": "assistant", "content": "Hej där"},
              {"role": "user", "content": "och imorgon?"}]
    collect(chat.chat_stream(follow, [], date(2026, 9, 24), "v2"))
    collect(chat.chat_stream(follow, [], date(2026, 9, 24), "v2"))
    assert len(calls) == 4                                          # följdfrågor sparas inte
    assert chat.cache.recent == []
