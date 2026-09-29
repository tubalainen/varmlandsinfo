"""Land, region och ort för en IP-adress, för besöksstatistiken (#66).

Uppslagningen görs lokalt i DB-IP:s fria databas IP to City Lite (CC BY 4.0, https://db-ip.com). Databasen hämtas
från db-ip.com när den saknas och sedan en gång i månaden. Inga uppgifter om besökarna skickas ut.
"""

import logging
import os
import time
import zlib
from datetime import date, timedelta
from pathlib import Path

import httpx

from common import USER_AGENT

log = logging.getLogger("varmlandsinfo")

URL = "https://download.db-ip.com/free/dbip-city-lite-{month}.mmdb.gz"
MAX_AGE = 32 * 86400              # sekunder innan databasen hämtas på nytt (den uppdateras varje månad)
MAX_BYTES = 400 * 1024 * 1024     # största tillåtna databas (uppackad)
ATTRIBUTION = "IP-geolokalisering av DB-IP"
ATTRIBUTION_URL = "https://db-ip.com"

# Länder på svenska (övriga visas med sitt engelska namn)
COUNTRIES_SV = {
    "SE": "Sverige", "NO": "Norge", "DK": "Danmark", "FI": "Finland", "IS": "Island", "DE": "Tyskland",
    "NL": "Nederländerna", "GB": "Storbritannien", "US": "USA", "FR": "Frankrike", "PL": "Polen", "ES": "Spanien",
    "IT": "Italien", "EE": "Estland", "LV": "Lettland", "LT": "Litauen", "IE": "Irland", "BE": "Belgien",
    "CH": "Schweiz", "AT": "Österrike", "CA": "Kanada", "CN": "Kina", "RU": "Ryssland", "UA": "Ukraina",
}


class GeoIP:
    def __init__(self, path: Path, client_factory=None, clock=time.time):
        self.path = path
        self.clock = clock
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(
            timeout=httpx.Timeout(30, read=120), headers={"User-Agent": USER_AGENT}, follow_redirects=True))
        self._reader = None
        self._mtime = None

    def available(self) -> bool:
        return self.path.is_file()

    def _open(self):
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return None
        if self._reader is None or mtime != self._mtime:
            import maxminddb
            if self._reader is not None:
                self._reader.close()
            self._reader = maxminddb.open_database(str(self.path))
            self._mtime = mtime
        return self._reader

    def lookup(self, ip: str) -> dict:
        """{"country", "region", "city"} för IP-adressen. Tomt om databasen saknas eller adressen är okänd."""
        try:
            reader = self._open()
            record = reader.get(ip) if reader else None
        except (ValueError, OSError) as exc:
            log.warning("Uppslagning i geodatabasen misslyckades: %s", type(exc).__name__)
            return {}
        if not record:
            return {}
        name = lambda part: ((part or {}).get("names") or {}).get("en")
        country = record.get("country") or {}
        region = name((record.get("subdivisions") or [None])[0])
        return {k: v for k, v in {
            "country": COUNTRIES_SV.get(country.get("iso_code"), name(country)),
            "region": region.removesuffix(" County") if region else None,
            "city": name(record.get("city")),
        }.items() if v}

    def stale(self) -> bool:
        try:
            return self.clock() - self.path.stat().st_mtime > MAX_AGE
        except OSError:
            return True

    async def ensure(self, today: date) -> bool:
        """Hämtar databasen om den saknas eller är äldre än en månad. True om en ny databas hämtades."""
        if not self.stale():
            return False
        first = today.replace(day=1)
        for month in (first, (first - timedelta(days=1)).replace(day=1)):   # månadens fil kan dröja en dag
            url = URL.format(month=month.strftime("%Y-%m"))
            try:
                if await self._download(url):
                    log.info("Hämtade geodatabasen från DB-IP (%s)", month.strftime("%Y-%m"))
                    return True
            except (httpx.HTTPError, OSError, zlib.error) as exc:
                log.warning("Kunde inte hämta geodatabasen från DB-IP: %s", type(exc).__name__)
                return False
        return False

    async def _download(self, url: str) -> bool:
        tmp = self.path.with_suffix(".tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        inflate = zlib.decompressobj(16 + zlib.MAX_WBITS)      # gzip
        size = 0
        try:
            async with self._client_factory() as client, client.stream("GET", url) as r:
                if r.status_code == 404:
                    return False
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        data = inflate.decompress(chunk)
                        size += len(data)
                        if size > MAX_BYTES:
                            raise OSError("geodatabasen är för stor")
                        f.write(data)
                    f.write(inflate.flush())
            import maxminddb
            maxminddb.open_database(str(tmp)).close()          # en trasig fil ersätter aldrig en fungerande
            os.replace(tmp, self.path)
            return True
        finally:
            tmp.unlink(missing_ok=True)
