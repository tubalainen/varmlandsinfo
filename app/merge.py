"""Slår ihop samma evenemang från flera källor."""

import re
import unicodedata

SIMILARITY = 0.6   # andel gemensamma ord i titlarna för att räknas som samma evenemang
STOP = {"och", "med", "i", "på", "the", "and", "live", "tour", "turné", "konsert", "presenterar", "feat"}


def _words(title: str) -> set[str]:
    t = unicodedata.normalize("NFKC", title or "").lower()
    t = re.sub(r"[^\wåäöéü]+", " ", t)
    return {w for w in t.split() if len(w) > 1 and w not in STOP}


def similar(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    if wa <= wb or wb <= wa:   # den ena titeln ingår helt i den andra
        return True
    return len(wa & wb) / len(wa | wb) >= SIMILARITY


def _same_place(a: dict, b: dict) -> bool:
    return not a.get("municipality") or not b.get("municipality") or a["municipality"] == b["municipality"]


def _absorb(primary: dict, other: dict) -> None:
    """Lägger till den andra källans länk och fyller i det som saknas hos den primära."""
    known = {s["name"] for s in primary["sources"]}
    for s in other["sources"]:
        if s["name"] not in known:
            primary["sources"].append(s)
    for key in ("booking_link", "website_link", "summary", "description", "place", "organizer"):
        if not primary.get(key) and other.get(key):
            primary[key] = other[key]
    if not primary["images"] and other["images"]:
        primary["images"] = other["images"]
    # Tid från en källa som har den, för tillfällen samma dag
    times = {o["date_start"]: o for o in other["occasions"] if o.get("time_start")}
    for o in primary["occasions"]:
        if not o.get("time_start") and o["date_start"] in times:
            o["time_start"] = times[o["date_start"]]["time_start"]
            o["time_end"] = times[o["date_start"]].get("time_end")


def merge(per_source: list[list[dict]]) -> list[dict]:
    """per_source i prioritetsordning (rikaste källan först). Returnerar sammanslagen lista."""
    result: list[dict] = []
    by_day: dict[str, list[dict]] = {}
    for events in per_source:
        for ev in events:
            ev["sources"] = [dict(s) for s in ev.get("sources") or [{"name": ev["source"], "url": ev.get("url")}]]
            match = None
            for o in ev["occasions"]:
                for cand in by_day.get(o["date_start"], []):
                    if cand["source"] != ev["source"] and _same_place(cand, ev) and similar(cand["title"], ev["title"]):
                        match = cand
                        break
                if match:
                    break
            if match:
                _absorb(match, ev)
                continue
            result.append(ev)
            for o in ev["occasions"]:
                by_day.setdefault(o["date_start"], []).append(ev)
    return result
