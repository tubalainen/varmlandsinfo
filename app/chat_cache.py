"""Sparade AI-svar, så att samma fråga inte behöver ställas till AI-modellen igen.

Ett svar återanvänds bara om frågan, dagens datum, evenemangsdatans version och modellen är desamma.
Fördefinierade frågor sparas alltid, egna frågor bara de senaste MAX_RECENT.
"""

import json
import logging
import os
import re
import threading
from pathlib import Path

from common import now_iso

log = logging.getLogger("varmlandsinfo.chat")

MAX_RECENT = 10
FORMAT = 1


def normalize(question: str) -> str:
    """Gemener och ihopslagna blanksteg, utan skiljetecken i slutet."""
    return re.sub(r"\s+", " ", question or "").strip().lower().rstrip("?!. ")


class AnswerCache:
    def __init__(self, path: Path, max_recent: int = MAX_RECENT):
        self.path = Path(path)
        self.max_recent = max_recent
        self.presets: dict[str, dict] = {}
        self.recent: list[dict] = []   # äldst först
        self._lock = threading.Lock()

    # ---- lagring
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("format") == FORMAT:
                self.presets = dict(data.get("presets") or {})
                self.recent = list(data.get("recent") or [])[-self.max_recent:]
                log.info("Läste in %d sparade AI-svar", len(self.presets) + len(self.recent))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            log.warning("Kunde inte läsa sparade AI-svar (%s): %s", self.path, exc)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"format": FORMAT, "presets": self.presets, "recent": self.recent}, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("Kunde inte spara AI-svar (%s): %s", self.path, exc)

    # ---- användning
    @staticmethod
    def _valid(entry: dict, ctx: dict) -> bool:
        return all(entry.get(k) == v for k, v in ctx.items())

    def get(self, question: str, ctx: dict) -> dict | None:
        """Sparat svar för frågan om det gäller samma dag, samma data och samma modell."""
        key = normalize(question)
        with self._lock:
            entry = self.presets.get(key)
            if entry and self._valid(entry, ctx):
                return entry
            for i, entry in enumerate(self.recent):
                if entry["key"] == key and self._valid(entry, ctx):
                    self.recent.append(self.recent.pop(i))   # senast använd sist
                    return entry
        return None

    def prune(self, ctx: dict) -> int:
        """Tar bort svar som inte gäller `ctx` (dagens datum, aktuell data och modell). Returnerar antalet."""
        with self._lock:
            before = len(self.presets) + len(self.recent)
            self.presets = {k: e for k, e in self.presets.items() if self._valid(e, ctx)}
            self.recent = [e for e in self.recent if self._valid(e, ctx)]
            removed = before - len(self.presets) - len(self.recent)
        if removed:
            self.save()
            log.info("Tog bort %d inaktuella AI-svar", removed)
        return removed

    def put(self, question: str, ctx: dict, answer: str, sources: list[dict], preset: bool) -> None:
        key = normalize(question)
        entry = {"key": key, "question": question, "answer": answer, "sources": sources,
                 "saved": now_iso(), **ctx}
        with self._lock:
            if preset:
                self.presets[key] = entry
            else:
                self.recent = [e for e in self.recent if e["key"] != key]
                self.recent.append(entry)
                del self.recent[:-self.max_recent]
        self.save()
