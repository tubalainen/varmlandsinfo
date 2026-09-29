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
    "SHL": {
        "icon": "🏒", "color": "#1d4ed8",
        "description": "Hemmamatcher i SHL, herrarnas högsta serie i ishockey (Färjestad BK i Löfbergs Arena).",
    },
    "Bandy": {
        "icon": "⛸️", "color": "#0e7490",
        "description": "Bandymatcher i Värmland: seriematcher, cuper och träningsmatcher.",
    },
    "Motorsport": {
        "icon": "🏁", "color": "#dc2626",
        "description": "Folkrace, rally, rallycross, crosskart, karting, motocross, enduro, speedway och annan motorsport.",
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
    "Motorträffar": {
        "icon": "🏎️", "color": "#475569",
        "description": "Bil- och MC-träffar, veteranfordon och fordonsutställningar.",
    },
    "På vatten": {
        "icon": "🛶", "color": "#0284c7",
        "description": "Aktiviteter och evenemang på sjöar och älvar.",
    },
    "Film": {
        "icon": "🎬", "color": "#4f46e5",
        "description": "Bio, filmvisningar och filmkvällar.",
    },
    "Spel och quiz": {
        "icon": "🎲", "color": "#65a30d",
        "description": "Bingo, quiz, korsord, brädspel och spelkvällar.",
    },
    "Träffar och caféer": {
        "icon": "☕", "color": "#a16207",
        "description": "Caféträffar, fika, handarbete, språkcafé och andra öppna träffar.",
    },
    "Böcker och litteratur": {
        "icon": "📚", "color": "#9333ea",
        "description": "Bokcirklar, författarbesök, sagostunder och läsning.",
    },
    "Gratis": {
        "icon": "🆓", "color": "#0e9f6e",
        "description": "Fri entré – evenemanget kostar ingenting.",
    },
    "Övrigt": {
        "icon": "✨", "color": "#6b7280",
        "description": "Evenemang som inte passar in i någon annan kategori.",
    },
}

DEFAULT = {"icon": "📌", "color": "#6b7280", "description": "Evenemang i Värmland."}


def describe_category(title: str | None) -> dict:
    return dict(CATEGORIES.get(title or "", DEFAULT))


SHL = "SHL"
BANDY = "Bandy"
# Kategorier som bara en källa eller ordregel sätter och som följer med när evenemanget slås ihop med samma evenemang
# från en annan källa (Visit Värmland och Ticketmaster listar också Färjestads matcher)
SOURCE_ONLY = (SHL, BANDY)


# ---------------------------------------------------------------- loppisar

MARKET = "Marknad, mässa och auktion"
LOPPIS = "Loppis"
OTHER = "Övrigt"
MOTOR_MEET = "Motorträffar"
FREE = "Gratis"
# Källornas namn -> appens: Visit Värmlands marknadskategori (där loppisar ingår), paraplyetiketterna
# Evenemang och Övriga evenemang (som inte säger något) och Motor (förväxlas lätt med Motorsport)
SOURCE_NAMES = {"Marknad, mässa, auktion och loppis": MARKET, "Evenemang": OTHER, "Övriga evenemang": OTHER,
                "Motor": MOTOR_MEET}
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


# ---------------------------------------------------------------- motorsport

MOTORSPORT = "Motorsport"
MOTORSPORT_RE = re.compile(
    r"folkrace|rallycross|crosskart|\brally|\bsprinten\b|karting|gokart|go-kart|motocross|enduro|speedway"
    r"|supermoto|\btrial\b|roadracing|dragracing|drifting|bilcross|bilsport|motorsport|isracing|skoterrace"
    r"|snöskotercross|racing pokal|\bmx\b", re.I)
MEET_RE = re.compile(r"träff|utställning|mässa|veteran|kortege|cruising|motordag", re.I)


def split_motorsport(categories: list[dict], title: str, summary: str) -> list[dict]:
    """Tävlingar får kategorin Motorsport. Motorträffar behålls bara för träffar och fordonsutställningar."""
    titles = [c["title"] for c in categories]
    if MOTORSPORT not in titles and not MOTORSPORT_RE.search(title or ""):
        return categories
    text = f"{title} {summary or ''}"
    result = [c for c in categories if SOURCE_NAMES.get(c["title"], c["title"]) != MOTOR_MEET or MEET_RE.search(text)]
    if MOTORSPORT not in titles:
        result.insert(0, {"title": MOTORSPORT, **describe_category(MOTORSPORT)})
    return result


# ---------------------------------------------------------------- ordregler

# Kategorier ur titeln (och ingressen när källan inte angett någon egen kategori). Mest för Visit Värmlands
# evenemang som bara har paraplyetiketterna, t.ex. bio, caféträffar, bokcirklar och bingo.
KEYWORD_RULES = [
    # Bara ordet bandy (och bandymatch, bandycup …): inte innebandy eller åkning på bandyplanen
    ("Bandy", re.compile(r"\bbandy(match|matchen|matcher|cup|cupen|turnering|en)?\b", re.I)),
    ("Musik", re.compile(
        r"konsert|gospel|\bjazz|\bkör(en|er|erna|sång)?\b|\bsånger (i|om|för|från|till|av|med)\b|allsång|visafton"
        r"|trubadur|orkester|symfoni|\bopera\b|livemusik|live music|musikafton|musikkväll", re.I)),
    ("Film", re.compile(r"\bbio\b|\bbion\b|biograf|\bfilm(en|er|erna)?\b|filmkväll|filmvisning|filmklubb|matiné", re.I)),
    ("Spel och quiz", re.compile(
        r"bingo|quiz|korsord|melodikryss|brädspel|sällskapsspel|spelkväll|spelkafé|rollspel|tipspromenad", re.I)),
    ("Träffar och caféer", re.compile(
        r"caf[eé]|kafé|fika\b|frukost|träffpunkt|\bhäng\b|queerhäng|pratcafé|it-hjälp|handarbet|stickcafé"
        r"|stickträff", re.I)),
    ("Böcker och litteratur", re.compile(
        r"\bbok(cirkel|släpp|prat|caf[eé]|tips|klubb|samtal|en|ens)?\b|bokprat|bokfrukost|\bböcker|litteratur"
        r"|författar|läsklubb|läscirkel|läscafé|sagostund|godnattsaga|shared reading|läsa, lyssna|poesi", re.I)),
]


def refine(categories: list[dict], title: str, summary: str) -> list[dict]:
    """Källornas namn blir appens, ordregler lägger till kategorier, och Övrigt blir kvar bara när inget annat passar."""
    titles = []
    for c in categories:
        t = SOURCE_NAMES.get(c["title"], c["title"])
        if t not in titles:
            titles.append(t)
    vague = all(t in (OTHER, FREE) for t in titles)
    # Loppisar och motorsport har egna källor och regler (loppisar.com har t.ex. "… restaurang & cafe" som namn)
    rules = [] if LOPPIS in titles or MOTORSPORT in titles else KEYWORD_RULES
    for name, pattern in rules:
        if name not in titles and (pattern.search(title or "") or (vague and pattern.search(summary or ""))):
            titles.append(name)
    if any(t not in (OTHER, FREE) for t in titles):
        titles = [t for t in titles if t != OTHER]
    elif OTHER not in titles:
        titles.insert(0, OTHER)
    by_title = {c["title"]: c for c in categories}
    return [by_title[t] if t in by_title else {"title": t, **describe_category(t)} for t in titles]
