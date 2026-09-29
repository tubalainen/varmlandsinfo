"""Besöksstatistiken och den dolda sidan /besoksinfo (#66)."""

import asyncio
import base64
import gzip
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

import access
import events
import geoip
import main
import visits

TZ = events.TZ
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/18.0 Mobile/15E148 Safari/604.1")
DAY = datetime(2026, 9, 29, 10, 15, tzinfo=TZ)


class FakeGeo:
    def lookup(self, ip):
        return {"81.230.12.4": {"country": "Sverige", "region": "Värmland", "city": "Karlstad"}}.get(ip, {})

    def available(self):
        return True


def store(tmp_path, clock=None):
    s = visits.VisitStats(tmp_path / "besoksinfo.json", geo=FakeGeo(), clock=clock or (lambda: 0))
    return s


def test_user_agent_and_referrer():
    assert visits.parse_user_agent(CHROME) == {"device": "Dator", "browser": "Chrome", "os": "Windows"}
    assert visits.parse_user_agent(IPHONE) == {"device": "Mobil", "browser": "Safari", "os": "iOS"}
    tablet = "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    assert visits.parse_user_agent(tablet)["device"] == "Surfplatta"
    assert visits.parse_user_agent(CHROME + " Edg/140.0")["browser"] == "Edge"
    assert visits.referrer_domain("https://www.google.com/search?q=x", "varmland.example") == "google.com"
    assert visits.referrer_domain("https://varmland.example/#/lista", "varmland.example:7799") == "Direkt"
    assert visits.referrer_domain(None, "x") == "Direkt"


def test_unique_per_day_and_bots(tmp_path):
    s = store(tmp_path)
    assert s.record("81.230.12.4", CHROME, "https://www.google.com/", "app", DAY)
    assert s.record("81.230.12.4", CHROME, None, "app", DAY.replace(hour=11))
    assert s.record("81.230.12.4", IPHONE, None, "app", DAY)                    # annan webbläsare = annan besökare
    assert s.record("192.168.1.20", CHROME, None, "app", DAY)
    assert not s.record("66.249.66.1", "Mozilla/5.0 (compatible; Googlebot/2.1)", None, "app", DAY)
    assert not s.record("1.2.3.4", "curl/8.5.0", None, "app", DAY)
    assert not s.record("1.2.3.4", "", None, "app", DAY)
    r = s.report(DAY.date(), 7)
    assert r["today"] == {"unique": 3, "visits": 4}
    first = next(v for v in r["visitors"] if v["browser"] == "Chrome" and v["ip"] == "81.230.12.4")
    assert first["hits"] == 2 and first["first"] == "10:15" and first["last"] == "11:15"
    assert first["city"] == "Karlstad, Värmland (Sverige)" and first["referrer"] == "google.com"
    assert dict(r["top"]["country"]) == {"Sverige": 2, "Lokalt nätverk": 1}
    assert dict(r["top"]["device"]) == {"Dator": 2, "Mobil": 1}


def test_cleanup_removes_ip_addresses_and_old_days(tmp_path):
    s = store(tmp_path)
    s.record("81.230.12.4", CHROME, None, "app", DAY)
    s.daily["2025-08-01"] = {"visits": 1, "unique": 1}                          # äldre än 13 månader
    s.daily["2025-09-01"] = {"visits": 2, "unique": 2}
    assert s.cleanup(date(2026, 9, 29)) == (0, 1)                               # dagens besökare finns kvar
    assert "2026-09-29" in s.days
    assert s.cleanup(date(2026, 9, 30)) == (1, 0)                               # dygnet är slut
    assert s.days == {} and s.daily["2026-09-29"]["unique"] == 1
    saved = (tmp_path / "besoksinfo.json").read_text()
    assert "81.230.12.4" not in saved and "salt" not in saved                   # inga IP-adresser efter städningen
    again = store(tmp_path)
    again.load()
    assert again.report(date(2026, 9, 30), 7)["period"] == {"days": 7, "unique": 1, "visits": 1}


def test_saved_at_most_once_a_minute(tmp_path):
    now = [100.0]
    s = store(tmp_path, clock=lambda: now[0])
    s.record("81.230.12.4", CHROME, None, "app", DAY)
    assert (tmp_path / "besoksinfo.json").exists()
    s.record("81.230.12.5", CHROME, None, "app", DAY)
    assert "81.230.12.5" not in (tmp_path / "besoksinfo.json").read_text()
    now[0] += 61
    s.record("81.230.12.6", CHROME, None, "app", DAY)
    assert "81.230.12.6" in (tmp_path / "besoksinfo.json").read_text()


def test_geoip_lookup_and_download(tmp_path, monkeypatch):
    g = geoip.GeoIP(tmp_path / "geo.mmdb", clock=lambda: 0)

    class Reader:
        def get(self, ip):
            return {"country": {"iso_code": "SE", "names": {"en": "Sweden"}},
                    "subdivisions": [{"names": {"en": "Värmland County"}}], "city": {"names": {"en": "Arvika"}}}
    monkeypatch.setattr(g, "_open", lambda: Reader())
    assert g.lookup("81.230.12.4") == {"country": "Sverige", "region": "Värmland", "city": "Arvika"}

    calls = []

    def handler(request):
        calls.append(str(request.url))
        if "2026-10" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, content=gzip.compress(b"MMDB"))
    real = httpx.AsyncClient
    d = geoip.GeoIP(tmp_path / "geoip" / "db.mmdb", clock=lambda: 10**10,
                    client_factory=lambda: real(transport=httpx.MockTransport(handler)))
    import maxminddb
    monkeypatch.setattr(maxminddb, "open_database", lambda path: type("R", (), {"close": lambda self: None})())
    assert asyncio.run(d.ensure(date(2026, 10, 1)))                            # månadens fil saknas än: förra månaden
    assert calls[-1].endswith("dbip-city-lite-2026-09.mmdb.gz") and d.path.read_bytes() == b"MMDB"
    fresh = geoip.GeoIP(d.path)                                                 # nyss hämtad: inget nytt anrop
    assert not asyncio.run(fresh.ensure(date(2026, 10, 1)))


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(visits, "PASSWORD", "hemligt")
    monkeypatch.setattr(visits, "store", store(tmp_path))
    monkeypatch.setattr(main, "login_limiter", access.IpLimiter(limit=3, window=900))
    monkeypatch.setattr(events, "current_events", lambda: [])
    return TestClient(main.app, headers={"User-Agent": CHROME})


def auth(password, user="admin"):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_page_needs_the_password(app):
    app.get("/")                                                                # en sidvisning
    r = app.get("/besoksinfo")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    assert app.get("/besoksinfo", headers=auth("fel")).status_code == 401
    ok = app.get("/besoksinfo?dagar=7", headers=auth("hemligt", user="vemsomhelst"))
    assert ok.status_code == 200 and "Besöksinfo" in ok.text and "noindex" in ok.headers["x-robots-tag"]
    assert "Unika besökare i dag" in ok.text and "db-ip.com" in ok.text
    assert ok.headers["cache-control"] == "no-store"
    assert app.get("/besoksinfo?dagar=abc", headers=auth("hemligt")).status_code == 200   # ogiltig period: 30 dagar
    assert visits.store.report(events.today(), 1)["today"]["visits"] == 1       # /besoksinfo räknas inte


def test_too_many_wrong_passwords(app):
    for _ in range(3):
        assert app.get("/besoksinfo", headers=auth("fel")).status_code == 401
    assert app.get("/besoksinfo", headers=auth("hemligt")).status_code == 429   # spärrad även med rätt lösenord
    assert app.get("/besoksinfo").status_code == 429


def test_off_without_password(tmp_path, monkeypatch):
    monkeypatch.setattr(visits, "PASSWORD", "")
    monkeypatch.setattr(visits, "store", None)
    monkeypatch.setattr(events, "current_events", lambda: [])
    client = TestClient(main.app, headers={"User-Agent": CHROME})
    assert client.get("/").status_code == 200
    assert client.get("/besoksinfo", headers=auth("")).status_code == 404
    assert client.get("/besoksinfo?dagar=abc").status_code == 404                # avslöjar inte att sidan finns
    assert client.get("/api/events").json()["visit_stats"] is False


def test_render_empty_and_year(tmp_path):
    s = store(tmp_path)
    import besoksinfo
    html = besoksinfo.render(s.report(date(2026, 9, 29), 365), 365, False)
    assert "Inga besök i dag än." in html and "per månad" in html and "Geodatabasen är inte hämtad" in html
    report = s.report(date(2026, 9, 29), 7)
    report["visitors"] = [{"ip": "1.2.3.4", "first": "10:00", "last": "10:00", "hits": 1, "city": "<script>x</script>",
                           "device": "Dator", "browser": "Chrome", "os": "Windows", "referrer": "Direkt"}]
    assert "<script>" not in besoksinfo.render(report, 7, True)                 # allt från besökarna escapas
