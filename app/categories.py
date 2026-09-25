"""Klassificering och beskrivning av evenemangstyper (Visit Värmlands kategorier)."""

import re

CATEGORIES: dict[str, dict] = {
    "Musik": {
        "icon": "🎵", "color": "#7c3aed",
        "description": "Konserter, spelningar och andra musikupplevelser – från klassiskt till rock och visor.",
    },
    "Teater och underhållning": {
        "icon": "🎭", "color": "#db2777",
        "description": "Teater, revy, standup, show och annan scenunderhållning.",
    },
    "Dans": {
        "icon": "💃", "color": "#e11d48",
        "description": "Dansföreställningar, dansbanor, danskvällar och kurser.",
    },
    "Utställning": {
        "icon": "🖼️", "color": "#0891b2",
        "description": "Konst-, museums- och andra utställningar att besöka under en period.",
    },
    "Föreläsning och workshop": {
        "icon": "🎓", "color": "#2563eb",
        "description": "Föredrag, kurser, workshops och andra lärande träffar.",
    },
    "Sport, motion och hälsa": {
        "icon": "🏅", "color": "#16a34a",
        "description": "Idrottsevenemang, matcher, lopp och aktiviteter för motion och hälsa.",
    },
    "Barn": {
        "icon": "🧸", "color": "#f59e0b",
        "description": "Aktiviteter och föreställningar särskilt för barn och familjer.",
    },
    "Marknad, mässa och auktion": {
        "icon": "🛍️", "color": "#ea580c",
        "description": "Marknader, mässor, auktioner och försäljning.",
    },
    "Loppis": {
        "icon": "🧺", "color": "#c026d3",
        "description": "Loppisar, loppmarknader och second hand – fynda begagnat.",
    },
    "Mat och dryck": {
        "icon": "🍽️", "color": "#b45309",
        "description": "Matupplevelser, provningar, middagar och food-evenemang.",
    },
    "Guidning": {
        "icon": "🧭", "color": "#0d9488",
        "description": "Guidade turer och visningar av platser, byggnader och natur.",
    },
    "Motor": {
        "icon": "🏎️", "color": "#475569",
        "description": "Motorträffar, tävlingar och fordonsutställningar.",
    },
    "På vatten": {
        "icon": "🛶", "color": "#0284c7",
        "description": "Aktiviteter och evenemang på sjöar och älvar.",
    },
    "Gratis": {
        "icon": "🆓", "color": "#0e9f6e",
        "description": "Fri entré – evenemanget kostar ingenting.",
    },
    "Evenemang": {
        "icon": "📅", "color": "#64748b",
        "description": "Allmänna evenemang och festligheter.",
    },
    "Övriga evenemang": {
        "icon": "✨", "color": "#6b7280",
        "description": "Evenemang som inte passar in i någon annan kategori.",
    },
}

DEFAULT = {"icon": "📌", "color": "#6b7280", "description": "Evenemang i Värmland."}


def describe_category(title: str | None) -> dict:
    return dict(CATEGORIES.get(title or "", DEFAULT))


# ---------------------------------------------------------------- loppisar

MARKET = "Marknad, mässa och auktion"
LOPPIS = "Loppis"
# Visit Värmlands namn på marknadskategorin, där loppisar ingår
SOURCE_NAMES = {"Marknad, mässa, auktion och loppis": MARKET}
LOPPIS_RE = re.compile(r"loppis|loppmarknad|second[ -]?hand", re.I)
MARKET_RE = re.compile(r"(?<!lopp)marknad|mässa|mässan|auktion", re.I)


def split_loppis(categories: list[dict], title: str, summary: str) -> list[dict]:
    """Bryter ut loppisar ur marknadskategorin till en egen kategori.

    Loppis: titeln nämner loppis (eller loppmarknad, second hand), eller marknadskategorin och ingressen nämner loppis.
    Marknadskategorin behålls bara om texten också nämner marknad, mässa eller auktion.
    """
    titles = [SOURCE_NAMES.get(c["title"], c["title"]) for c in categories]
    text = f"{title} {summary or ''}"
    loppis = LOPPIS in titles or bool(LOPPIS_RE.search(title or "")) or (
        MARKET in titles and bool(LOPPIS_RE.search(summary or "")))
    result = []
    for t in titles:
        if t == MARKET and loppis and not MARKET_RE.search(text):
            continue
        if t not in result:
            result.append(t)
    if loppis and LOPPIS not in result:
        result.insert(0, LOPPIS)
    by_title = {c["title"]: c for c in categories}
    return [by_title[t] if t in by_title else {"title": t, **describe_category(t)} for t in result]
