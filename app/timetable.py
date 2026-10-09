"""Dagens hämtschema (#104): varje källa hämtas en gång per dag, vid en egen slumpad tid i hämtfönstret
(`REFRESH_WINDOW`, standard 08:00–13:00). Tiderna dras på nytt varje dag, så att källorna inte anropas på samma
klockslag dag efter dag och inte alla på en gång. Schemat sparas i `data/schema.json`, så att en omstart varken
ger nya tider eller extra hämtningar samma dag."""

import json
import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from common import TZ, log

DEFAULT_WINDOW = "08:00-13:00"
# Var VÄLDIGT snäll mot källorna (#76): högst två nya försök per källa och dag, minst 15 minuter emellan
RETRIES = 2
RETRY_DELAY = timedelta(minutes=15)
RETRY_JITTER = timedelta(minutes=10)     # nya försök 15–25 minuter efter det förra
_random = random.SystemRandom()


def parse_window(raw: str | None) -> tuple[time, time]:
    """REFRESH_WINDOW, t.ex. "08:00-13:00". Fönstret måste rymma de nya försöken."""
    try:
        start, end = (time.fromisoformat(part.strip()) for part in (raw or "").replace("–", "-").split("-"))
        if datetime.combine(date.min, end) - datetime.combine(date.min, start) > RETRIES * RETRY_DELAY:
            return start, end
    except ValueError:
        pass
    log.warning("Ogiltigt REFRESH_WINDOW=%r (HH:MM-HH:MM, minst %d minuter), använder %s", raw,
                RETRIES * RETRY_DELAY.total_seconds() // 60 + 1, DEFAULT_WINDOW)
    return parse_window(DEFAULT_WINDOW)


WINDOW = parse_window(os.getenv("REFRESH_WINDOW") or DEFAULT_WINDOW)
for _old in ("DAILY_REFRESH_TIME", "REFRESH_MINUTES"):
    if os.getenv(_old):
        log.warning("%s används inte längre: källorna hämtas vid slumpade tider inom REFRESH_WINDOW (#104)", _old)


def midnight(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=TZ)


def window(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, WINDOW[0], tzinfo=TZ), datetime.combine(day, WINDOW[1], tzinfo=TZ)


def latest_first_attempt(day: date) -> datetime:
    """Senaste tiden för dagens första försök, så att de nya försöken också ryms i fönstret."""
    return window(day)[1] - RETRIES * RETRY_DELAY


def random_time(lo: datetime, hi: datetime) -> datetime:
    if hi <= lo:
        return lo
    return (lo + timedelta(seconds=_random.uniform(0, (hi - lo).total_seconds()))).replace(microsecond=0)


def retry_time(previous: datetime, retries_after: int) -> datetime:
    """Nästa försök: 15–25 minuter efter det förra, och i fönstret så att de återstående försöken också ryms."""
    lo = previous + RETRY_DELAY
    hi = lo + RETRY_JITTER
    start, end = window(previous.date())
    if start <= previous <= end:
        hi = max(lo, min(hi, end - retries_after * RETRY_DELAY))
    return random_time(lo, hi)


def _parse(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


class Timetable:
    """Dagens tider per källa (`slots`), källorna vars hämtning är klar för dagen (`done`, även när den
    misslyckades) och när alla källor senast var hämtade (`completed`)."""

    def __init__(self, path: Path | None = None):
        self.path = path            # None: sparas inte
        self.day: date | None = None
        self.slots: dict[str, str] = {}
        self.done: dict[str, str] = {}
        self.completed: str | None = None

    def load(self) -> None:
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            day = date.fromisoformat(data["day"])
            slots, done = dict(data["slots"]), dict(data.get("done") or {})
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            log.warning("Kunde inte läsa %s: %s", self.path, exc)
            return
        self.day, self.slots, self.done, self.completed = day, slots, done, data.get("completed")

    def save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"day": self.day.isoformat() if self.day else None, "slots": self.slots,
                                       "done": self.done, "completed": self.completed}), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("Kunde inte spara hämtschemat %s: %s", self.path, exc)

    def plan(self, now: datetime, keys: list[str]) -> None:
        """Drar dagens slumpade tider: en gång per dag, och för källor som saknar en tid (t.ex. nyss påslagna)."""
        if self.day != now.date():
            self.day, self.slots, self.done = now.date(), {}, {}
        missing = [k for k in keys if k not in self.slots]
        for key in missing:
            self.slots[key] = random_time(window(self.day)[0], latest_first_attempt(self.day)).isoformat()
        if missing:
            self.save()
            log.info("Dagens hämtschema: %s", ", ".join(
                f"{k} {self.slot(k):%H.%M}" for k in sorted(self.slots, key=self.slots.get)))

    def slot(self, key: str) -> datetime:
        return datetime.fromisoformat(self.slots[key])

    def move(self, key: str, when: datetime) -> None:
        self.slots[key] = when.isoformat()
        self.save()

    def done_today(self, key: str, now: datetime) -> bool:
        return self.day == now.date() and key in self.done

    def mark_done(self, key: str, now: datetime) -> None:
        if self.day == now.date():
            self.done[key] = now.isoformat(timespec="seconds")
            self.save()

    def all_done(self, keys: list[str], now: datetime) -> bool:
        return all(self.done_today(k, now) for k in keys)

    def complete(self, now: datetime) -> None:
        """Alla källor är hämtade: tidpunkten visas i appen som när informationen senast uppdaterades i sin helhet."""
        self.completed = now.isoformat(timespec="seconds")
        self.save()

    def cutoff(self, key: str, now: datetime) -> datetime:
        """Äldsta data som får användas för källan: i dag när dagens hämtning är klar (även om den misslyckades),
        annars i går. Gårdagens data visas alltså tills källan hämtats i dag, men aldrig data från före i går."""
        return midnight(now.date() - timedelta(days=0 if self.done_today(key, now) else 1))

    def jobs_at_start(self, now: datetime, updated: dict[str, str | None]) -> list[tuple[datetime, str, int]]:
        """Hämtningarna som återstår i dag, som (tid, källa, försök). `updated` är källornas senaste hämtning.
        Källor utan data (eller med data från före i går) hämtas direkt. En missad tid (appen var avstängd) dras
        om inom fönstret, eller hämtas direkt när fönstret har passerat."""
        self.plan(now, list(updated))
        jobs = []
        for key, iso in updated.items():
            if self.done_today(key, now):
                continue
            fetched, slot = _parse(iso), self.slot(key)
            if fetched is None or fetched < midnight(now.date() - timedelta(days=1)):
                jobs.append((now, key, 0))
            elif fetched >= slot:                       # redan hämtad efter dagens tid, t.ex. via /api/refresh
                self.mark_done(key, fetched)
            elif slot > now:
                jobs.append((slot, key, 0))
            else:
                start, end = window(now.date())
                when = random_time(max(now, start), latest_first_attempt(now.date())) if now < end else now
                self.move(key, when)
                jobs.append((when, key, 0))
        return sorted(jobs)
