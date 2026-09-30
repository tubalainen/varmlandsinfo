"""Åtkomst till API:t: vad som bara får anropas lokalt, och spärren per IP-adress i Fråga AI.

Appen har ingen proxykonfiguration. En omvänd proxy framför appen hanteras utanför den. Anrop via en
proxy känns igen på huvudena som proxyn lägger till, och räknas aldrig som lokala.
"""

import ipaddress
import threading
import time

from fastapi import HTTPException, Request

IP_RATE_LIMIT = 20              # frågor till AI:n per IP-adress …
IP_RATE_WINDOW = 30 * 60        # … och tidsfönster i sekunder (rullande)
MAX_TRACKED_IPS = 5000

# Huvuden som omvända proxyer (nginx, Traefik, Caddy, Nginx Proxy Manager, Cloudflare …) lägger till
FORWARD_HEADERS = ("forwarded", "x-forwarded-for", "x-real-ip", "cf-connecting-ip", "true-client-ip")


def _ip(host: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        ip = ipaddress.ip_address(host or "")
    except ValueError:
        return None
    return getattr(ip, "ipv4_mapped", None) or ip


def _is_lan(ip) -> bool:
    return bool(ip) and (ip.is_loopback or ip.is_private) and not ip.is_unspecified


def is_local(request: Request) -> bool:
    """Anropet kommer direkt från samma dator eller det lokala nätverket, och inte via en omvänd proxy."""
    if any(h in request.headers for h in FORWARD_HEADERS):
        return False
    return _is_lan(_ip(request.client.host if request.client else None))


def require_local(request: Request) -> None:
    """Beroende för adresser som bara är till för den som driftar appen (t.ex. /api/refresh)."""
    if not is_local(request):
        raise HTTPException(status_code=403, detail="Bara tillgängligt från det lokala nätverket.")


def client_ip(request: Request) -> str:
    """Adressen som spärren per IP gäller. Kommer anropet från en lokal proxy används adressen som proxyn
    lade till sist i X-Forwarded-For (tidigare adresser kan klienten själv ha skickat). Annars anslutningens adress."""
    host = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _is_lan(_ip(host)):
        last = forwarded.split(",")[-1].strip()
        if _ip(last):
            return last
    return host


class IpLimiter:
    """Högst `limit` anrop per `window` sekunder och nyckel (IP-adress)."""

    def __init__(self, limit: int = IP_RATE_LIMIT, window: float = IP_RATE_WINDOW, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._hits)

    def prune(self) -> int:
        """Glömmer adresser vars anrop alla är äldre än fönstret (IP-adresser sparas inte längre än så)."""
        with self._lock:
            now = self.clock()
            old = [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]
            for k in old:
                del self._hits[k]
            return len(old)

    def wait(self, key: str) -> float:
        """Sekunder tills nyckeln får göra nästa anrop (0 = nu). Räknar inte anropet."""
        with self._lock:
            now = self.clock()
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            return 0 if len(hits) < self.limit else hits[0] + self.window - now

    def allow(self, key: str) -> bool:
        """Räknar anropet och svarar om det ryms inom gränsen."""
        with self._lock:
            now = self.clock()
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            full = len(self._hits) > MAX_TRACKED_IPS
        if full:
            self.prune()
        return True


chat_limiter = IpLimiter()
