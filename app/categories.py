"""Klassificering och beskrivning av evenemangstyper (Visit Värmlands kategorier)."""

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
    "Marknad, mässa, auktion och loppis": {
        "icon": "🛍️", "color": "#ea580c",
        "description": "Marknader, mässor, auktioner, loppisar och försäljning.",
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
