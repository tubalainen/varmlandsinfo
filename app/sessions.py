"""Samtal i Fråga AI: en session per webbläsarflik, med historiken på servern.

Klienten skickar bara sin nya fråga och sitt sessions-id. Servern äger historiken, så den kan inte
förfalskas. Varje session får ställa en fråga i taget och ett begränsat antal frågor per minut.

Sessionerna finns bara i minnet (appen körs som en process) och försvinner vid omstart.
"""

import re
import secrets
import threading
import time
from dataclasses import dataclass, field

SESSION_TTL = 2 * 3600          # sekunder utan aktivitet innan sessionen tas bort
MAX_SESSIONS = 1000
MAX_TURNS = 20                  # meddelanden som sparas per session (frågor och svar)
RATE_LIMIT = 10                 # frågor per session …
RATE_WINDOW = 60                # … och tidsfönster i sekunder
BUSY_TIMEOUT = 20 * 60          # en fråga som aldrig avslutades spärrar inte sessionen längre än så

ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


@dataclass
class Session:
    id: str
    history: list[dict] = field(default_factory=list)   # {"role", "content", + visningsdata}
    last_seen: float = field(default_factory=time.monotonic)
    busy_since: float | None = None                      # när pågående fråga ställdes
    asked: list[float] = field(default_factory=list)     # tidpunkter för de senaste frågorna

    def is_busy(self, now: float | None = None) -> bool:
        if self.busy_since is None:
            return False
        return (time.monotonic() if now is None else now) - self.busy_since < BUSY_TIMEOUT

    def model_history(self) -> list[dict]:
        """Historiken som skickas till modellen: bara roll och text."""
        return [{"role": m["role"], "content": m["content"]} for m in self.history]

    def view(self) -> list[dict]:
        """Historiken för att visa samtalet igen i webbläsaren."""
        return [dict(m) for m in self.history]


class SessionStore:
    def __init__(self, ttl: float = SESSION_TTL, max_sessions: int = MAX_SESSIONS,
                 rate_limit: int = RATE_LIMIT, rate_window: float = RATE_WINDOW, clock=time.monotonic):
        self.ttl, self.max_sessions = ttl, max_sessions
        self.rate_limit, self.rate_window = rate_limit, rate_window
        self.clock = clock
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._sessions)

    def _expire(self, now: float) -> None:
        for sid in [sid for sid, s in self._sessions.items() if now - s.last_seen > self.ttl and not s.is_busy(now)]:
            del self._sessions[sid]
        # För många sessioner: de som varit inaktiva längst tas bort först
        if len(self._sessions) >= self.max_sessions:
            idle = sorted((s for s in self._sessions.values() if not s.is_busy(now)), key=lambda s: s.last_seen)
            for s in idle[:len(self._sessions) - self.max_sessions + 1]:
                del self._sessions[s.id]

    def get(self, sid: str | None) -> Session | None:
        """Befintlig session, eller None om id:t är ogiltigt, okänt eller har gått ut."""
        if not sid or not ID_RE.match(sid):
            return None
        with self._lock:
            now = self.clock()
            s = self._sessions.get(sid)
            if s and now - s.last_seen > self.ttl and not s.is_busy(now):
                del self._sessions[sid]
                return None
            if s:
                s.last_seen = now
            return s

    def get_or_create(self, sid: str | None) -> tuple[Session, bool]:
        """Sessionen för id:t. Finns den inte skapas en ny med nytt id (klienten väljer aldrig id)."""
        s = self.get(sid)
        if s:
            return s, False
        with self._lock:
            now = self.clock()
            self._expire(now)
            s = Session(id=secrets.token_urlsafe(32), last_seen=now)
            self._sessions[s.id] = s
            return s, True

    def clear(self) -> int:
        """Tar bort alla samtal som inte besvarar en fråga just nu. Returnerar antalet."""
        with self._lock:
            now = self.clock()
            idle = [sid for sid, s in self._sessions.items() if not s.is_busy(now)]
            for sid in idle:
                del self._sessions[sid]
            return len(idle)

    def reset(self, sid: str | None) -> bool:
        with self._lock:
            return self._sessions.pop(sid, None) is not None if sid else False

    def begin(self, s: Session) -> str | None:
        """Markerar att sessionen ställer en fråga. Returnerar ett felmeddelande om det inte går."""
        with self._lock:
            now = self.clock()
            if s.is_busy(now):
                return "busy"
            s.asked = [t for t in s.asked if now - t < self.rate_window]
            if len(s.asked) >= self.rate_limit:
                return "rate"
            s.asked.append(now)
            s.busy_since = now
            s.last_seen = now
            return None

    def end(self, s: Session, turns: list[dict] | None = None) -> None:
        """Frågan är klar. `turns` (fråga och svar) läggs till i historiken om svaret blev komplett."""
        with self._lock:
            if turns:
                s.history.extend(turns)
                del s.history[:-MAX_TURNS]
            s.busy_since = None
            s.last_seen = self.clock()


store = SessionStore()
