"""Tickster: biljettsläppta evenemang i Värmland via Event Dump API (#116). Kräver en API-nyckel (TICKSTER_API_KEY).

Tickster publicerar varje natt en fil med alla kommande evenemang (cirka 8 MB gzip, 50 MB JSON). Två anrop per dag:
metadata med en signerad adress till filen, sedan filen. Bara evenemang på platser i Värmland, Karlskoga och
Degerfors sparas. Nyckeln skickas bara som parameter till Tickster. Den loggas aldrig och syns aldrig i fel
(common.get_json tar bort frågesträngen, och httpx-loggningen är avstängd i main.py).

Tas inte med: inställda, bio och sändningar på bioduken, presentkort, årskort och liknande som inte är evenemang,
samlingar och produktioner med egna föreställningar (föreställningarna finns som egna poster) och poster som
sträcker sig över mer än en vecka. Föreställningar med samma titel på samma plats blir ett evenemang.
"""

import gzip
import json
import os
import re
from datetime import datetime

import httpx

from common import SourceError, category, clean_text, finalize, get_bytes, get_json, https_url, strip_html
from kommuner import kommun
from sources.ticketmaster import POSTCODE_PREFIXES

API_URL = "https://api.tickster.com/sv/api/1.0/events/dump/upcoming"
API_KEY = os.getenv("TICKSTER_API_KEY", "").strip()
HOMEPAGE = "https://www.tickster.com/se/sv"
MAX_DAYS = 7                    # längre poster är säsongskort, presentkort och produktioner över hela säsongen
SKIP_STATES = {"cancelled", "canceled", "postponed"}
NOT_EVENTS = re.compile(r"presentkort|gåvokort|årskort|säsongskort|medlemskap|medlemsskap|bordsbokning|abonnemang"
                        r"|^mat & dryck\b", re.I)
SCREEN = re.compile(r"\(tal:|på bio\b|\bbio:|livesänds|sänds på bio|direktsänd", re.I)
# Kategorier ur titel, taggar och arrangör, annars ur platsens namn. Ordreglerna i categories.py lägger till fler
SPORT = "Sport, motion och hälsa"
RULES = [
    (SPORT, re.compile(r"innebandy|hockey|säsongen 20|\bmatch\b|hyrox|\btrav\b|travet\b", re.I)),
    ("Teater och underhållning", re.compile(
        r"teater|revy|revyn|standup|stand-up|komedi|comedy|\bshow\b|dinnershow|föreställning|musikal|trolleri|magic",
        re.I)),
    ("Musik", re.compile(r"konsert|\blive\b|festival|\bband\b|tribute|kvartett|kvintett|\btrio\b|afton\b|orkester"
                         r"|symfoni|#rock|#pop|#punk|#metal|\bjazz|rocken|sessions", re.I)),
    ("Dans", re.compile(r"\bdans(en|kväll|band)?\b|dansen\b|socialdans|mogendans|danskväll", re.I)),
    ("Mat och dryck", re.compile(r"vinprovning|\bvin\b|wine|julbord|julsupé|middag|dinner|my table|bubblor", re.I)),
    ("Föreläsning och workshop", re.compile(r"workshop|föreläsning|föredrag|kurs\b", re.I)),
    ("Guidning", re.compile(r"stadsvandring|guidad|guidning|visning", re.I)),
]
# Matcher: klubbarnas förkortningar i titeln ("BIK Karlskoga - Nybro Vikings", "Dotteviks IF Herr - Åsmyra IBK")
CLUB = re.compile(r"\b(IF|IK|BK|IBK|IBF|HK|HC|BIK|FF|SK)\b")
VENUE_RULES = [
    ("Musik", re.compile(r"konsertsal|konserthall", re.I)),
    ("Teater och underhållning", re.compile(r"teater|stora scen", re.I)),
]


def in_area(venue: dict) -> bool:
    """Platsen ligger i Värmland, Karlskoga eller Degerfors: känd ort eller kommun, eller värmländskt postnummer."""
    if (venue.get("country") or "SE") != "SE":
        return False
    postcode = (venue.get("zipCode") or "").replace(" ", "")
    return bool(kommun(venue.get("city"), venue.get("zipCode"))) or postcode.startswith(POSTCODE_PREFIXES)


def area_dump(dump: dict) -> dict:
    """Bara evenemangen på platser i området, med deras platser och arrangörer."""
    venues = {v["id"]: v for v in dump.get("venues") or [] if isinstance(v, dict) and v.get("id") and in_area(v)}
    events = [e for e in dump.get("events") or [] if isinstance(e, dict) and e.get("venueId") in venues]
    used = {e.get("organizerId") for e in events}
    return {"created": dump.get("created"), "events": events, "venues": list(venues.values()),
            "organizers": [o for o in dump.get("organizers") or [] if isinstance(o, dict) and o.get("id") in used]}


class Tickster:
    key = "tickster"
    title = "Tickster"
    homepage = HOMEPAGE

    def config_error(self) -> str | None:
        return None if API_KEY else "Ingen API-nyckel (sätt TICKSTER_API_KEY i .env)"

    async def fetch(self, client: httpx.AsyncClient, previous: dict | None) -> dict:
        meta = await get_json(client, API_URL, self.title, key=API_KEY)
        uri = https_url(meta.get("uri")) if isinstance(meta, dict) else None
        if not uri:
            raise SourceError(f"{self.title} svarade utan adress till dagens fil, API:t kan ha ändrats")
        if previous and meta.get("id") and previous.get("dump_id") == meta.get("id"):
            return previous                                   # samma fil som förra gången: ingen ny hämtning
        raw = await get_bytes(client, uri.replace("http://", "https://", 1), self.title)
        try:
            dump = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        except (EOFError, OSError, ValueError):
            raise SourceError(f"{self.title}s fil gick inte att läsa") from None
        del raw
        if not isinstance(dump, dict) or not isinstance(dump.get("events"), list):
            raise SourceError(f"{self.title}s fil saknar evenemang, formatet kan ha ändrats")
        return {"dump_id": meta.get("id"), **area_dump(dump)}

    def normalize(self, payload: dict) -> list[dict]:
        venues = {v["id"]: v for v in payload.get("venues") or []}
        organizers = {o["id"]: o.get("name") for o in payload.get("organizers") or []}
        groups: dict[tuple, list[dict]] = {}
        for e in payload.get("events") or []:
            if is_event(e) and (venue := venues.get(e.get("venueId"))) and in_area(venue):
                groups.setdefault((clean_text(e.get("name")).lower(), e["venueId"]), []).append(e)
        out = []
        for group in groups.values():
            group.sort(key=lambda e: e.get("start") or "")
            if event := normalize_group(group, venues[group[0]["venueId"]], organizers):
                out.append(event)
        return out


def _dt(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def is_event(e: dict) -> bool:
    """Ett publicerat evenemang som blir av, med en egen tid, och inte bio eller något annat än ett evenemang."""
    name = clean_text(e.get("name"))
    start, end = _dt(e.get("start")), _dt(e.get("end"))
    if not name or not start or e.get("published") is False:
        return False
    if (e.get("eventState") or "").lower() in SKIP_STATES:
        return False
    if e.get("hierarchyType") == "collection" or e.get("childEvents") or e.get("isCollectionEvent"):
        return False
    if end and (end - start).days > MAX_DAYS:
        return False
    tags = " ".join(t for t in e.get("tags") or [] if isinstance(t, str)).lower()
    return not (NOT_EVENTS.search(name) or SCREEN.search(name) or re.search(r"(^|\s)#?bio\b", tags))


def categories(e: dict, venue: dict, organizer: str | None) -> list[dict]:
    text = " ".join([clean_text(e.get("name")), *[t for t in e.get("tags") or [] if isinstance(t, str)], organizer or ""])
    titles = [t for t, rule in RULES if rule.search(text)]
    if CLUB.search(clean_text(e.get("name"))) and SPORT not in titles:
        titles.insert(0, SPORT)
    titles = titles or [t for t, rule in VENUE_RULES if rule.search(venue.get("name") or "")]
    return [category(t) for t in titles or ["Övrigt"]]


def occasion(e: dict) -> dict:
    start, end = _dt(e.get("start")), _dt(e.get("end"))
    # Sluttiden bara när evenemanget slutar samma dag (Tickster sätter ofta slutet till nästa natt)
    same_day = end and end.date() == start.date() and end > start
    multi = end and (end.date() - start.date()).days >= 1 and (end - start).total_seconds() > 24 * 3600
    return {"date_start": start.date().isoformat(), "date_end": (end if multi else start).date().isoformat(),
            "time_start": start.strftime("%H:%M"), "time_end": end.strftime("%H:%M") if same_day else None}


def normalize_group(group: list[dict], venue: dict, organizers: dict) -> dict | None:
    first = group[0]
    title = clean_text(first.get("name"))
    organizer = organizers.get(first.get("organizerId"))
    description = strip_html(first.get("description"), 3000)
    url = https_url(first.get("infoUri")) or https_url(first.get("shopUri"))
    image = https_url(first.get("imageUrl"))
    geo = venue.get("geo") or {}
    address = ", ".join(x for x in (clean_text(venue.get("address")), " ".join(
        x for x in (clean_text(venue.get("zipCode")), clean_text(venue.get("city"))) if x)) if x)
    links = [https_url(link.get("uri")) for link in first.get("links") or [] if isinstance(link, dict)]
    return finalize({
        "id": f"tickster-{first.get('productionParentId') or first.get('id')}",
        "source": Tickster.title,
        "title": title,
        "summary": strip_html(first.get("description"), 300),
        "description": description,
        "categories": categories(first, venue, organizer),
        "municipality": kommun(venue.get("city"), venue.get("zipCode")),
        "place": {"title": clean_text(venue.get("name")), "address": address,
                  "lat": geo.get("latitude"), "lon": geo.get("longitude")},
        "organizer": organizer,
        "url": url,
        "booking_link": https_url(first.get("shopUri")) or url,
        "website_link": next((x for x in links if x), None),
        "images": [{"small": image, "medium": image, "large": image, "alt": title, "copyright": ""}] if image else [],
        "occasions": [occasion(e) for e in group],
    })
