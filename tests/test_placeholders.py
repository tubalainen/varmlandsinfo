"""Platshållarbilderna per kategori (#101)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import placeholders  # noqa: E402
from categories import CATEGORIES  # noqa: E402

STATIC = ROOT / "app" / "static"


def test_slug():
    assert placeholders.slug("Sport, motion och hälsa") == "sport-motion-och-halsa"
    assert placeholders.slug("Böcker och litteratur") == "bocker-och-litteratur"
    assert placeholders.slug("På vatten") == "pa-vatten"
    assert placeholders.slug("SHL") == "shl"


def test_every_category_has_a_placeholder():
    for title in CATEGORIES:
        path = STATIC / "placeholders" / f"{placeholders.slug(title)}.svg"
        assert path.exists(), title
        # Incheckade filer ska vara verktygets aktuella utdata
        assert path.read_text(encoding="utf-8") == placeholders.svg(title), f"Kör python tools/placeholders.py ({title})"


def test_app_js_knows_every_placeholder():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    listed = set(re.findall(r'"([a-z0-9-]+)"', re.search(r"const PLACEHOLDERS = new Set\(\[(.*?)\]\)", js, re.S)[1]))
    assert listed == {placeholders.slug(t) for t in CATEGORIES}
    assert "ovrigt" in listed


def test_placeholders_are_self_contained():
    """Inga externa resurser, skript eller länkar (CSP img-src 'self', #88)."""
    for path in (STATIC / "placeholders").glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "href" not in text and "http://" not in text.replace(
            'xmlns="http://www.w3.org/2000/svg"', ""), path.name
