"""Loppiskartan: loppisar i Värmland med öppettider (#115, ersätter loppisar.com som lades ned i oktober 2026).

Sidan för Värmland (/loppis-lan-varmland) har alla ställen i länet i sidans data (Next.js, `self.__next_f`), med
kommun, adress, koordinater och öppettider: fasta datum (`hours_type` "specific") eller ett veckoschema ("weekly").
Ett anrop ger hela länet. Bara loppisar tas med, inte second hand-butiker och antikaffärer (användarens val), och
inte ställen utan öppettider. Ett veckoschema blir ett tillfälle per öppen dag, 30 dagar framåt. robots.txt spärrar
/api/, där bilderna ligger, så de tas inte med.
"""

import json
import re
from datetime import date, timedelta

import httpx

from common import SourceError, category, finalize, get_text, https_url, strip_html, today

BASE = "https://loppiskartan.se"
URL = f"{BASE}/loppis-lan-varmland"
DAYS = 30                                    # så många dagar framåt som veckoschemat ger tillfällen
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PUSH = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
MARKETS = re.compile(r'\{"markets":\s*\[')
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
# Loppisar har ordet i namnet. Second hand-butiker, kedjor och antikaffärer (Myrorna, Röda Korset, Fyndboa …) tas
# inte med, och inte heller Karlstad Loppis, som är en egen källa med säsongens datum
LOPPIS_NAME = re.compile(r"loppis|loppmarknad", re.I)
OWN_SOURCE = re.compile(r"karlstad loppis", re.I)
# "öppet fredagar och lördagar under sommaren": veckoschemat gäller bara juni–augusti
SUMMER = re.compile(r"\bsommar(en|tid)?\b|sommarloppis", re.I)
SUMMER_MONTHS = (6, 7, 8)


class Loppiskartan:
    key = "loppiskartan"
    title = "Loppiskartan"
    group = "Loppisar"          # visas som en källa i gränssnittet, tillsammans med Karlstad Loppis
    homepage = URL

    def config_error(self) -> str | None:
        return None

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        return {"markets": markets(await get_text(client, URL, self.title))}

    def normalize(self, payload: dict) -> list[dict]:
        first = today()
        return [e for e in (normalize_market(m, first) for m in payload.get("markets") or [] if is_loppis(m)) if e]


def markets(page: str) -> list[dict]:
    """Ställena i sidans data. Next.js delar upp datan i flera skript, som sätts ihop innan listan tolkas."""
    try:
        data = "".join(json.loads(f'"{chunk}"') for chunk in PUSH.findall(page))
        found, _ = json.JSONDecoder().raw_decode(data, MARKETS.search(data).start())
    except (AttributeError, ValueError):
        raise SourceError("Hittade inga loppisar hos Loppiskartan, sidans struktur kan ha ändrats") from None
    return [m for m in found.get("markets") or [] if isinstance(m, dict)]


def is_loppis(m: dict) -> bool:
    name = m.get("name") or ""
    return bool(LOPPIS_NAME.search(name)) and not OWN_SOURCE.search(name)


def _parsed(value):
    """Öppettiderna kan vara JSON som text eller redan tolkade."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _time(value) -> str | None:
    value = (value or "").strip() if isinstance(value, str) else ""
    return value.zfill(5) if TIME_RE.match(value) else None


def occasions(m: dict, first: date) -> list[dict]:
    out = []
    if m.get("hours_type") == "specific":
        for d in _parsed(m.get("specific_dates")) or []:
            try:
                day = date.fromisoformat(d.get("date") or "")
            except (AttributeError, TypeError, ValueError):
                continue
            out.append((day, d.get("start"), d.get("end")))
    elif m.get("hours_type") == "weekly":
        schedule = _parsed(m.get("weekly_schedule")) or {}
        summer = SUMMER.search(f"{m.get('description') or ''} {m.get('hours_note') or ''}")
        for i in range(DAYS):
            day = first + timedelta(days=i)
            hours = schedule.get(WEEKDAYS[day.weekday()]) if isinstance(schedule, dict) else None
            if isinstance(hours, dict) and hours.get("isOpen") and (not summer or day.month in SUMMER_MONTHS):
                out.append((day, hours.get("start"), hours.get("end")))
    return [{"date_start": day.isoformat(), "date_end": day.isoformat(), "time_start": _time(start),
             "time_end": _time(end) if _time(end) != _time(start) else None} for day, start, end in out]


def address(text: str | None) -> str:
    """'Vickersrudstorp där oppe , SE-661 94 Säffle, Sverige' -> 'Vickersrudstorp där oppe, 661 94 Säffle'."""
    text = re.sub(r",\s*Sverige\s*$", "", text or "")
    return re.sub(r"\s+,", ",", re.sub(r"\bSE-(?=\d{3}\s?\d{2})", "", text)).strip(" ,")


def normalize_market(m: dict, first: date) -> dict | None:
    name = (m.get("name") or "").strip()
    slug = m.get("slug") or ""
    occ = occasions(m, first)
    if not name or not slug or not occ:
        return None
    note = (m.get("hours_note") or "").strip()
    summary = strip_html(m.get("description"), 300)
    link = next((u for u in (m.get(k) for k in ("website", "facebook", "instagram")) if isinstance(u, str) and u), None)
    if link and not link.startswith(("http://", "https://")):
        link = f"https://{link}"
    return finalize({
        "id": f"loppiskartan-{m.get('id') or slug}",
        "source": Loppiskartan.title,
        "title": name,
        "summary": summary or "Loppis med öppettider enligt Loppiskartan.",
        "description": "\n\n".join(x for x in (strip_html(m.get("description"), 2000), note,
                                                "Kontakta gärna loppisen innan du åker långt.") if x),
        "categories": [category("Loppis")],
        "municipality": m.get("kommun") or m.get("municipality"),
        "place": {"title": name, "address": address(m.get("address")),
                  "lat": m.get("latitude"), "lon": m.get("longitude")},
        "organizer": None,
        "url": f"{BASE}/markets/{slug}",
        "booking_link": None,
        "website_link": https_url(link),
        "images": [],
        "occasions": occ,
    })
