"""Kommunerna som appen täcker, och hur orter, adresser och postnummer knyts till dem (#81).

Filtret Kommun ska bara innehålla kommuner, inte orter (Väse, Brunskog) eller orter utanför området (Stockholm).
`common.finalize` sätter därför varje evenemangs kommun med `kommun()`, så att alla källor följer samma regler.
"""

import re

# Värmlands 16 kommuner plus Karlskoga och Degerfors, samma som i Visit Värmlands kommunlista
KOMMUNER = ["Arvika", "Degerfors", "Eda", "Filipstad", "Forshaga", "Grums", "Hagfors", "Hammarö", "Karlskoga",
            "Karlstad", "Kil", "Kristinehamn", "Munkfors", "Storfors", "Sunne", "Säffle", "Torsby", "Årjäng"]

# Tätorter och byar -> kommun. Korta eller tvetydiga namn (Ed, Nor, Kila, Brattfors) finns inte med.
ORTER = {
    # Karlstad
    "molkom": "Karlstad", "vålberg": "Karlstad", "skattkärr": "Karlstad", "väse": "Karlstad", "edsvalla": "Karlstad",
    "blombacka": "Karlstad", "ulvsby": "Karlstad", "vallargärdet": "Karlstad", "östra fågelvik": "Karlstad",
    "ilanda": "Karlstad", "alster": "Karlstad", "nyed": "Karlstad", "skåre": "Karlstad",
    # Hammarö
    "skoghall": "Hammarö", "hallersrud": "Hammarö", "mörmon": "Hammarö",
    # Arvika
    "brunskog": "Arvika", "gunnarskog": "Arvika", "glava": "Arvika", "edane": "Arvika", "klässbol": "Arvika",
    "jössefors": "Arvika", "stavnäs": "Arvika", "högerud": "Arvika", "älgå": "Arvika", "taserud": "Arvika",
    "sulvik": "Arvika", "ottebol": "Arvika", "rackstad": "Arvika",
    # Eda
    "charlottenberg": "Eda", "åmotfors": "Eda", "koppom": "Eda", "eda glasbruk": "Eda", "skillingmark": "Eda",
    "köla": "Eda", "järnskog": "Eda", "hökedal": "Eda",
    # Filipstad
    "lesjöfors": "Filipstad", "nykroppa": "Filipstad", "storbrohyttan": "Filipstad", "persberg": "Filipstad",
    "nordmark": "Filipstad", "rämmen": "Filipstad",
    # Forshaga
    "deje": "Forshaga", "mölnbacka": "Forshaga", "ullerud": "Forshaga",
    # Grums
    "slottsbron": "Grums", "borgvik": "Grums", "värmskog": "Grums",
    # Hagfors
    "ekshärad": "Hagfors", "råda": "Hagfors", "uddeholm": "Hagfors", "sunnemo": "Hagfors", "mjönäs": "Hagfors",
    "gustav adolf": "Hagfors", "bergsäng": "Hagfors",
    # Kil
    "fagerås": "Kil", "högboda": "Kil", "frykerud": "Kil", "apertin": "Kil", "stora kil": "Kil", "nilsby": "Kil",
    # Kristinehamn
    "björneborg": "Kristinehamn", "ölme": "Kristinehamn", "rudskoga": "Kristinehamn", "visnum": "Kristinehamn",
    "visnums-kil": "Kristinehamn", "bäckhammar": "Kristinehamn", "nässundet": "Kristinehamn",
    # Munkfors
    "ransäter": "Munkfors",
    # Storfors
    "lungsund": "Storfors", "bjurtjärn": "Storfors", "kyrksten": "Storfors",
    # Sunne
    "rottneros": "Sunne", "gräsmark": "Sunne", "lysvik": "Sunne", "östra ämtervik": "Sunne",
    "västra ämtervik": "Sunne", "östra emtervik": "Sunne", "västra emtervik": "Sunne", "uddheden": "Sunne",
    "gettjärn": "Sunne", "mårbacka": "Sunne",
    # Säffle
    "värmlandsbro": "Säffle", "svanskog": "Säffle", "nysäter": "Säffle", "långserud": "Säffle", "tveta": "Säffle",
    "millesvik": "Säffle", "ölserud": "Säffle", "bränn-ekeby": "Säffle", "gillberga": "Säffle",
    # Torsby
    "sysslebäck": "Torsby", "likenäs": "Torsby", "stöllet": "Torsby", "östmark": "Torsby", "lekvattnet": "Torsby",
    "vitsand": "Torsby", "höljes": "Torsby", "bograngen": "Torsby", "branäs": "Torsby", "ambjörby": "Torsby",
    "finnskoga": "Torsby", "oleby": "Torsby", "fensbol": "Torsby",
    # Årjäng
    "töcksfors": "Årjäng", "sillerud": "Årjäng", "holmedal": "Årjäng", "silbodal": "Årjäng", "trankil": "Årjäng",
    "vågsäter": "Årjäng", "västra fågelvik": "Årjäng", "blomskog": "Årjäng",
    # Degerfors
    "svartå": "Degerfors", "åtorp": "Degerfors",
}

# Postnummerprefix (tre siffror) som bara används i en kommun. Delade prefix (660, 670, 680 …) avgörs av orten.
POSTNUMMER = {
    "651": "Karlstad", "652": "Karlstad", "653": "Karlstad", "654": "Karlstad", "655": "Karlstad", "656": "Karlstad",
    "661": "Säffle", "663": "Hammarö", "664": "Grums", "665": "Kil", "667": "Forshaga", "669": "Forshaga",
    "671": "Arvika", "672": "Årjäng", "673": "Eda", "681": "Kristinehamn", "682": "Filipstad", "683": "Hagfors",
    "684": "Munkfors", "685": "Torsby", "686": "Sunne", "688": "Storfors", "691": "Karlskoga", "693": "Degerfors",
}

_B, _E = r"(?<![\wåäöé-])", r"(?![\wåäöé-])"
_EXACT = {k.lower(): k for k in KOMMUNER}
# Längst först, så att "Visnums-Kil" och "Stora Kil" hittas före kommunen Kil
_ORT_RE = re.compile(_B + "(" + "|".join(re.escape(o) for o in sorted(ORTER, key=len, reverse=True)) + ")" + _E,
                     re.I)
_KOMMUN_RE = re.compile(_B + "(" + "|".join(re.escape(k) for k in KOMMUNER) + r")s?(?:\s+kommun)?" + _E, re.I)
_POSTNUMMER_RE = re.compile(r"(?<!\d)(\d{3})\s?\d{2}(?!\d)")


def kommun(*texts: str | None) -> str | None:
    """Kommunen för den första texten som går att knyta till en: en kommun ("Karlstad", "Karlstads kommun"), en ort
    ("Väse" -> Karlstad) eller ett postnummer ("681 31" -> Kristinehamn). None om ingen text ger en kommun."""
    for text in texts:
        t = (text or "").strip()
        if not t:
            continue
        if t.lower() in _EXACT:
            return _EXACT[t.lower()]
        if m := _ORT_RE.search(t):
            return ORTER[m.group(1).lower()]
        if m := _KOMMUN_RE.search(t):
            return _EXACT[m.group(1).lower()]
        for prefix in _POSTNUMMER_RE.findall(t):
            if prefix in POSTNUMMER:
                return POSTNUMMER[prefix]
    return None


def orter_i(text: str | None) -> dict[str, str]:
    """Orter som nämns i en text (t.ex. en fråga), med sin kommun: {"skoghall": "Hammarö"}."""
    return {m.group(1).lower(): ORTER[m.group(1).lower()] for m in _ORT_RE.finditer(text or "")}
