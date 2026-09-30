"""Säkerhetsåtgärder efter säkerhetsanalysen (#85–#92)."""

import time

from fastapi.testclient import TestClient

import main
from version import __version__


def test_many_ranges_are_answered_quickly():
    """CVE-2025-62727: ett Range-huvud med många intervall fick Starlette att räkna i kvadratisk tid (#85)."""
    client = TestClient(main.app)
    ranges = ",".join(f"{i}-{i}" for i in range(0, 20000, 2))
    start = time.monotonic()
    r = client.get("/static/app.js", headers={"Range": f"bytes={ranges}"})
    assert time.monotonic() - start < 2
    assert r.status_code in (200, 206, 416)


def test_api_is_never_cached_whatever_the_host():
    """Cache-Control väljs efter den råa sökvägen, inte efter en adress som byggs av Host-huvudet (CVE-2026-48710, #85)."""
    client = TestClient(main.app)
    for host in ("x/static", "evil.example/static/", "a b"):
        r = client.get(f"/api/events?v={__version__}", headers={"host": host})
        assert r.headers["cache-control"] == "no-store", host
    r = client.get(f"/static/app.js?v={__version__}")
    assert "immutable" in r.headers["cache-control"]
