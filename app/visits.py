"""Besöksstatistik för den dolda sidan /besoksinfo (#66). Bara påslagen när BESOKSINFO_PASSWORD är satt.

Sidvisningar av appen (GET /) räknas. Unika besökare räknas anonymt per dygn, utan cookies: en hash av IP-adress och
webbläsare med ett slumpvärde som byts varje dygn. Dagens besökare sparas med IP-adress, plats, enhet och hänvisning
till städningen efter dygnets slut. Då summeras dygnet och IP-adresserna tas bort. Den summerade statistiken per dag
sparas i 13 månader. Allt ligger i /data/besoksinfo.json.
"""

import hashlib
import ipaddress
import json
import logging
import os
import re
import secrets
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("varmlandsinfo")

PASSWORD = os.getenv("BESOKSINFO_PASSWORD", "")
RETENTION_DAYS = 396              # 13 månader summerad statistik
SAVE_INTERVAL = 60                # sekunder mellan sparningarna
DIMENSIONS = ("country", "city", "device", "browser", "os", "referrer")

BOT_RE = re.compile(
    r"bot\b|bot/|crawl|spider|slurp|curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|headless|lighthouse"
    r"|preview|facebookexternalhit|embedly|monitor|uptime|pingdom|scan|feedfetcher", re.I)


def enabled() -> bool:
    return bool(PASSWORD)


def parse_user_agent(ua: str) -> dict:
    """Enhet, webbläsare och operativsystem utifrån User-Agent (grovt, räcker för statistik)."""
    ua = ua or ""
    if re.search(r"iPad|Tablet|Android(?!.*Mobile)", ua):
        device = "Surfplatta"
    elif re.search(r"Mobi|iPhone|Android", ua):
        device = "Mobil"
    else:
        device = "Dator"
    for name, pattern in (("Edge", r"Edg(e|A|iOS)?/"), ("Opera", r"OPR/|Opera"), ("Samsung Internet", r"SamsungBrowser"),
                          ("Firefox", r"Firefox|FxiOS"), ("Chrome", r"Chrome|CriOS"), ("Safari", r"Safari")):
        if re.search(pattern, ua):
            browser = name
            break
    else:
        browser = "Annan"
    for name, pattern in (("Windows", r"Windows"), ("iOS", r"iPhone|iPad|iPod"), ("Android", r"Android"),
                          ("ChromeOS", r"CrOS"), ("macOS", r"Mac OS X|Macintosh"), ("Linux", r"Linux")):
        if re.search(pattern, ua):
            os_name = name
            break
    else:
        os_name = "Annat"
    return {"device": device, "browser": browser, "os": os_name}


def referrer_domain(referer: str | None, own_host: str | None) -> str:
    """Webbplatsen besökaren kom från (bara domänen), eller "Direkt"."""
    host = (urlsplit(referer or "").hostname or "").removeprefix("www.")
    own = (own_host or "").split(":")[0].removeprefix("www.")
    return host if host and host != own else "Direkt"


def _place(ip: str, geo) -> dict:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return {"country": "Okänt", "city": "Okänd"}
    if not addr.is_global:
        return {"country": "Lokalt nätverk", "city": "Lokalt nätverk"}
    found = geo.lookup(ip) if geo else {}
    country = found.get("country") or "Okänt"
    region = found.get("region") if found.get("region") != found.get("city") else None      # "Örebro, Örebro"
    city = ", ".join(x for x in (found.get("city"), region) if x) or "Okänd"
    return {"country": country, "city": f"{city} ({country})" if found.get("city") else city}


class VisitStats:
    def __init__(self, path: Path, geo=None, clock=time.time):
        self.path = path
        self.geo = geo
        self.clock = clock
        self.days: dict[str, dict] = {}     # dygn med besökare (och IP-adresser) som inte summerats än
        self.daily: dict[str, dict] = {}    # summerad statistik per dag
        self._lock = threading.Lock()
        self._saved = 0.0

    # ------------------------------------------------------------ lagring

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            log.warning("Kunde inte läsa besöksstatistiken: %s", exc)
            return
        self.days = data.get("days") or {}
        self.daily = data.get("daily") or {}

    def save(self) -> None:
        with self._lock:
            payload = json.dumps({"version": 1, "days": self.days, "daily": self.daily}, ensure_ascii=False)
        tmp = self.path.with_suffix(".json.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self.path)
            self._saved = self.clock()
        except OSError as exc:
            log.warning("Kunde inte spara besöksstatistiken: %s", exc)

    # ------------------------------------------------------------ räkning

    def record(self, ip: str, user_agent: str, referer: str | None, host: str | None, now: datetime) -> bool:
        """Räknar en sidvisning. Robotar räknas inte. Returnerar True om besöket räknades."""
        if not user_agent or BOT_RE.search(user_agent):
            return False
        day = now.date().isoformat()
        with self._lock:
            d = self.days.setdefault(day, {"salt": secrets.token_hex(16), "visits": 0, "visitors": {}})
            d["visits"] += 1
            key = hashlib.sha256(f"{d['salt']}|{ip}|{user_agent}".encode()).hexdigest()[:20]
            visitor = d["visitors"].get(key)
            if visitor is None:
                d["visitors"][key] = {"ip": ip, "first": now.strftime("%H:%M"), "last": now.strftime("%H:%M"), "hits": 1,
                                      **_place(ip, self.geo), **parse_user_agent(user_agent),
                                      "referrer": referrer_domain(referer, host)}
            else:
                visitor["hits"] += 1
                visitor["last"] = now.strftime("%H:%M")
        if self.clock() - self._saved > SAVE_INTERVAL:     # högst en gång i minuten (och vid städning och avslut)
            self.save()
        return True

    @staticmethod
    def summarize(detail: dict) -> dict:
        """Summerad statistik för ett dygn, utan IP-adresser."""
        visitors = list((detail.get("visitors") or {}).values())
        out = {"visits": detail.get("visits", 0), "unique": len(visitors)}
        for dim in DIMENSIONS:
            out[dim] = dict(Counter(v.get(dim) or "Okänd" for v in visitors))
        return out

    def cleanup(self, today: date) -> tuple[int, int]:
        """Summerar dygn före i dag och tar bort deras IP-adresser, och rensar dagar äldre än 13 månader.
        Körs efter hämtningarna från källorna och vid start. Returnerar (summerade dygn, rensade dagar)."""
        first = (today - timedelta(days=RETENTION_DAYS)).isoformat()
        with self._lock:
            done = [d for d in self.days if d < today.isoformat()]
            for d in done:
                self.daily[d] = self.summarize(self.days.pop(d))
            old = [d for d in self.daily if d < first]
            for d in old:
                del self.daily[d]
        if done or old:
            self.save()
        return len(done), len(old)

    # ------------------------------------------------------------ rapport

    def report(self, today: date, period: int) -> dict:
        """Underlaget till /besoksinfo för de senaste `period` dagarna (i dag inräknad)."""
        with self._lock:
            live = {d: self.summarize(v) for d, v in self.days.items()}
            per_day = {**self.daily, **live}
            visitors = sorted((dict(v) for v in (self.days.get(today.isoformat()) or {}).get("visitors", {}).values()),
                              key=lambda v: v["last"], reverse=True)
        days = [(today - timedelta(days=i)).isoformat() for i in range(period - 1, -1, -1)]
        series = [{"date": d, "unique": per_day.get(d, {}).get("unique", 0), "visits": per_day.get(d, {}).get("visits", 0)}
                  for d in days]
        top = {dim: Counter() for dim in DIMENSIONS}
        for d in days:
            for dim in DIMENSIONS:
                top[dim].update(per_day.get(d, {}).get(dim) or {})
        t = per_day.get(today.isoformat(), {})
        return {
            "today": {"unique": t.get("unique", 0), "visits": t.get("visits", 0)},
            "period": {"days": period, "unique": sum(s["unique"] for s in series), "visits": sum(s["visits"] for s in series)},
            "series": series,
            "top": {dim: c.most_common() for dim, c in top.items()},
            "visitors": visitors,
            "first_day": min(per_day) if per_day else None,
        }


store: VisitStats | None = None     # sätts vid start i main.py när funktionen är påslagen
