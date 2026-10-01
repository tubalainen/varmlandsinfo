"""Slår ihop samma evenemang från flera källor."""

import re
import unicodedata
from datetime import date, timedelta

from categories import SOURCE_ONLY

SIMILARITY = 0.6   # andel gemensamma ord i titlarna för att räknas som samma evenemang
# Vanliga ord som inte säger vilket evenemang det är ("Z loppis" ska inte bli samma som "Loppis i Oleby")
STOP = {"och", "med", "i", "på", "the", "and", "live", "tour", "turné", "konsert", "presenterar", "feat",
        "loppis", "loppmarknad"}


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


def _motorsport(e: dict) -> bool:
    return any(c["title"] == "Motorsport" for c in e.get("categories") or [])


def same_race(a: dict, b: dict) -> bool:
    """Samma motorsporttävling med olika titlar: Visit Värmlands "Folkrace" och SBF:s "Höstracet" (Folkrace på
    Tomtfallets Motorstadion). Den korta titelns ord finns i den andras titel och text, eller minst tre ord är gemensamma."""
    if not (_motorsport(a) and _motorsport(b)):
        return False
    for x, y in ((a, b), (b, a)):
        wx, wy = _words(x["title"]), _words(f"{y['title']} {y.get('summary') or ''}")
        if wx and (wx <= wy or len(wx & wy) >= 3):
            return True
    return False


def _same_place(a: dict, b: dict) -> bool:
    return not a.get("municipality") or not b.get("municipality") or a["municipality"] == b["municipality"]


def _norm(text: str | None) -> str:
    return re.sub(r"[^\wåäöéü]+", "", unicodedata.normalize("NFKC", text or "").lower())


def duplicate_listing(a: dict, b: dict) -> bool:
    """Samma evenemang två gånger hos samma källa: Visit Värmland har ibland en post från arrangören och en från
    lokalen ("Rent Hus" och "Musikteater: Rent Hus" i Skoghall). Kräver samma dag och starttid och samma plats
    (gatuadressen eller lokalens namn), så att olika evenemang med samma titel aldrig slås ihop (#95)."""
    times = {(o["date_start"], o["time_start"]) for o in a["occasions"] if o.get("time_start")}
    if not times & {(o["date_start"], o["time_start"]) for o in b["occasions"] if o.get("time_start")}:
        return False
    pa, pb = a.get("place") or {}, b.get("place") or {}
    street_a, street_b = (_norm((p.get("address") or "").split(",")[0]) for p in (pa, pb))
    name_a, name_b = _norm(pa.get("title")), _norm(pb.get("title"))
    return bool(street_a and street_a == street_b) or bool(name_a and name_a == name_b)


def _absorb(primary: dict, other: dict) -> None:
    """Lägger till den andra källans länk och fyller i det som saknas hos den primära."""
    known = {s["name"] for s in primary["sources"]}
    for s in other["sources"]:
        if s["name"] not in known:
            primary["sources"].append(s)
    for key in ("municipality", "booking_link", "website_link", "summary", "description", "place", "organizer"):
        if not primary.get(key) and other.get(key):
            primary[key] = other[key]
    have = {c["title"] for c in primary["categories"]}
    primary["categories"] += [c for c in other["categories"] if c["title"] in SOURCE_ONLY and c["title"] not in have]
    if not primary["images"] and other["images"]:
        primary["images"] = other["images"]
    # Tid från en källa som har den, för tillfällen samma dag
    times = {o["date_start"]: o for o in other["occasions"] if o.get("time_start")}
    for o in primary["occasions"]:
        if not o.get("time_start") and o["date_start"] in times:
            o["time_start"] = times[o["date_start"]]["time_start"]
            o["time_end"] = times[o["date_start"]].get("time_end")


def _days(o: dict) -> list[str]:
    """Dagarna ett tillfälle omfattar: varje dag i en kort period (t.ex. en tävlingshelg), annars startdagen."""
    start, end = o["date_start"], o.get("date_end") or o["date_start"]
    try:
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return [start]
    if not 0 < (d1 - d0).days <= 7:
        return [start]
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def merge(per_source: list[list[dict]]) -> list[dict]:
    """per_source i prioritetsordning (rikaste källan först). Returnerar sammanslagen lista."""
    result: list[dict] = []
    by_day: dict[str, list[dict]] = {}
    for events in per_source:
        for ev in events:
            ev["sources"] = [dict(s) for s in ev.get("sources") or [{"name": ev["source"], "url": ev.get("url")}]]
            match = None
            for day in (d for o in ev["occasions"] for d in _days(o)):
                for cand in by_day.get(day, []):
                    if (_same_place(cand, ev) and (similar(cand["title"], ev["title"]) or same_race(cand, ev))
                            and (cand["source"] != ev["source"] or duplicate_listing(cand, ev))):
                        match = cand
                        break
                if match:
                    break
            if match:
                _absorb(match, ev)
                continue
            result.append(ev)
            for day in {d for o in ev["occasions"] for d in _days(o)}:
                by_day.setdefault(day, []).append(ev)
    return result
