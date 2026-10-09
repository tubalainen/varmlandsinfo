"""Ritar platshållarbilderna per kategori (#101): app/static/placeholders/<kategori>.svg.

Varje bild är ett värmländskt landskap (himmel, åsar, granskog och sjö) i kategorins färg med kategorins motiv i en
cirkel. Bilderna har ett eget mörkt läge (prefers-color-scheme), som resten av gränssnittet.

Kör: python tools/placeholders.py
"""

import random
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from categories import CATEGORIES  # noqa: E402

OUT = ROOT / "app" / "static" / "placeholders"
W, H = 416, 296
WHITE, DARK_BG = "#ffffff", "#0b1220"


def slug(title: str) -> str:
    """Filnamnet: gemener utan accenter (å, ä, ö -> a, a, o), annat än bokstäver och siffror blir bindestreck.
    Samma regel som placeholder() i app.js."""
    s = "".join(c for c in unicodedata.normalize("NFD", title.lower()) if not unicodedata.combining(c))
    return "-".join("".join(c if c.isalnum() else " " for c in s).split())


def mix(a: str, b: str, t: float) -> str:
    """Blandar färgen a med b, där t är andelen b."""
    x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(p + (q - p) * t):02x}" for p, q in zip(x, y))


def star(cx, cy, r_out, r_in, points=5, rot=-90):
    import math
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / points)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return f'<polygon class="f" points="{" ".join(pts)}"/>'


def star_c(*args, **kw):
    """Stjärna i kategorins färg (på vit botten)."""
    return star(*args, **kw).replace('class="f"', 'class="c"')


# Motiven ritas kring (0, 0) inom cirka ±48. Klasser: s = vit kontur, f = vit fyllning, c = kategorins färg,
# cs = kontur i kategorins färg
MOTIFS = {
    "Musik": """
        <ellipse class="f" cx="-22" cy="28" rx="14" ry="10" transform="rotate(-20 -22 28)"/>
        <ellipse class="f" cx="24" cy="20" rx="14" ry="10" transform="rotate(-20 24 20)"/>
        <path class="s" d="M-9 25V-28M37 17V-38"/>
        <polygon class="f" points="-12,-30 40,-40 40,-26 -12,-16"/>""",
    "Teater och underhållning": """
        <g transform="rotate(14 14 -4) translate(14 -6)" opacity=".75">
          <path class="f" d="M-30-30Q0-40 30-30Q32 8 0 36Q-32 8-30-30Z"/>
          <ellipse class="c" cx="-12" cy="-10" rx="7" ry="4"/><ellipse class="c" cx="12" cy="-10" rx="7" ry="4"/>
          <path class="cs" d="M-13 18Q0 6 13 18"/>
        </g>
        <g transform="rotate(-12 -14 4) translate(-14 6)">
          <path class="f cs2" d="M-30-30Q0-40 30-30Q32 8 0 36Q-32 8-30-30Z"/>
          <ellipse class="c" cx="-12" cy="-10" rx="7" ry="4"/><ellipse class="c" cx="12" cy="-10" rx="7" ry="4"/>
          <path class="cs" d="M-14 8Q0 22 14 8"/>
        </g>""",
    "Dans": """
        <path class="s" d="M0-50V-30"/>
        <circle class="f" cx="0" cy="4" r="34"/>
        <ellipse class="cs" cx="0" cy="4" rx="34" ry="11"/>
        <ellipse class="cs" cx="0" cy="4" rx="34" ry="24"/>
        <ellipse class="cs" cx="0" cy="4" rx="12" ry="34"/>
        <path class="cs" d="M0-30V38"/>
        """ + star(-46, -26, 9, 3, 4, 0) + star(44, 34, 7, 2, 4, 0),
    "Utställning": """
        <rect class="s" x="-44" y="-34" width="88" height="66" rx="4"/>
        <path class="f" d="M-34 24L-12-6L2 10L14-2L34 24Z"/>
        <circle class="f" cx="20" cy="-18" r="7"/>
        <path class="s" d="M-24 32L-34 50M24 32L34 50"/>""",
    "Föreläsning och workshop": """
        <path class="f" d="M-26-4V20Q0 34 26 20V-4L0 8Z"/>
        <polygon class="f cs3" points="0,-34 50,-12 0,10 -50,-12"/>
        <path class="s s4" d="M44-10V22"/>
        <circle class="f" cx="44" cy="26" r="6"/>""",
    "Sport, motion och hälsa": """
        <path class="s s10" d="M-22-48L-2-6M22-48L2-6"/>
        <circle class="f" cx="0" cy="20" r="26"/>
        """ + star_c(0, 21, 15, 6.5),
    "Barn": """
        <path class="s s3" d="M-24 14Q-14 30 0 46M24 8Q14 30 0 46M0-6V46"/>
        <ellipse class="f cs3" cx="0" cy="-28" rx="17" ry="21"/>
        <ellipse class="f cs3" cx="-24" cy="-8" rx="17" ry="21"/>
        <ellipse class="f cs3" cx="24" cy="-14" rx="17" ry="21"/>""",
    "Marknad, mässa och auktion": """
        <path class="s" d="M-40-14V44M40-14V44"/>
        <rect class="f" x="-48" y="12" width="96" height="10" rx="2"/>
        <circle class="f" cx="-24" cy="4" r="7"/><circle class="f" cx="-8" cy="4" r="7"/>
        <circle class="f" cx="10" cy="4" r="7"/><circle class="f" cx="26" cy="4" r="7"/>
        <path class="f" d="M-48-40H48V-20Q40-10 32-20Q24-10 16-20Q8-10 0-20Q-8-10-16-20Q-24-10-32-20Q-40-10-48-20Z"/>
        <path class="c" d="M-32-40H-16V-20Q-24-10-32-20ZM0-40H16V-20Q8-10 0-20ZM32-40H48V-20Q40-10 32-20Z"/>""",
    "SHL": """
        <path class="s s8" d="M-34-46L16 34H36M34-46L-16 34H-36"/>
        <ellipse class="f" cx="0" cy="44" rx="14" ry="6"/>""",
    "Bandy": """
        <path class="s s8" d="M-32-46L12 22Q22 40 40 32"/>
        <circle class="ball" cx="-18" cy="30" r="11"/>""",
    "Handboll": """
        <circle class="f" cx="0" cy="0" r="40"/>
        <path class="cs" d="M-40 0Q0-16 40 0M-6-40Q-20 0-6 40M14-37Q30-6 18 36"/>""",
    "Motorsport": """
        <path class="s" d="M-40-46V48"/>
        <g transform="translate(-38 -42)">
          <rect class="f" width="80" height="54"/>
          <path class="c" d="M20 0h20v18h-20zM60 0h20v18h-20zM0 18h20v18h-20zM40 18h20v18h-20zM20 36h20v18h-20z
            M60 36h20v18h-20z"/>
        </g>""",
    "Loppis": """
        <path class="s" d="M0-16V-24Q0-38 12-38Q22-38 22-28"/>
        <path class="s" d="M0-16L-46 16Q-50 24-40 24H40Q50 24 46 16Z"/>
        <path class="s s4" d="M26 24L34 40"/>
        <rect class="f" x="24" y="38" width="22" height="14" rx="3" transform="rotate(-20 35 45)"/>""",
    "Mat och dryck": """
        <circle class="s" cx="0" cy="2" r="32"/>
        <circle class="s s3" cx="0" cy="2" r="20"/>
        <path class="s s4" d="M-50-30V36M-56-30V-14M-44-30V-14M-56-14Q-50-6-44-14"/>
        <path class="f" d="M48 36V-30Q62-20 56 6H48Z"/>
        <path class="s s4" d="M48 4V36"/>""",
    "Guidning": """
        <circle class="s" cx="0" cy="0" r="42"/>
        <polygon class="f" points="0,-32 10,0 -10,0"/>
        <polygon class="s s3" points="0,32 10,0 -10,0"/>
        <circle class="c" cx="0" cy="0" r="4"/>
        <path class="s s3" d="M0-42V-34M0 42V34M-42 0H-34M42 0H34"/>""",
    "Motorträffar": """
        <path class="f" d="M-52 16V2Q-50-6-38-8L-24-10L-14-28H18L30-10L46-8Q54-6 54 4V16Z"/>
        <polygon class="c" points="-10,-23 0,-23 0,-12 -17,-12"/>
        <polygon class="c" points="5,-23 15,-23 23,-12 5,-12"/>
        <circle class="c ws" cx="-30" cy="18" r="11"/><circle class="c ws" cx="32" cy="18" r="11"/>""",
    "På vatten": """
        <path class="s s5" d="M-18-44L18 22"/>
        <ellipse class="f" cx="20" cy="26" rx="6" ry="12" transform="rotate(-29 20 26)"/>
        <path class="f" d="M-56 0Q-40 22 0 22Q40 22 56 0Q0 12-56 0Z"/>
        <path class="s s4" d="M-48 40q10-7 20 0t20 0t20 0t20 0t20 0"/>""",
    "Film": """
        <rect class="f" x="-42" y="-10" width="84" height="54" rx="4"/>
        <path class="c" d="M-30-10h14l-10 12h-14zM-2-10h14l-10 12h-14zM26-10h14l-10 12h-14z"/>
        <g transform="rotate(-16 -42 -12)">
          <rect class="f" x="-42" y="-30" width="84" height="14" rx="3"/>
          <path class="c" d="M-30-30h14l-10 14h-14zM-2-30h14l-10 14h-14zM26-30h14l-10 14h-14z"/>
        </g>""",
    "Spel och quiz": """
        <g transform="rotate(-14 -20 -6)">
          <rect class="f" x="-46" y="-32" width="52" height="52" rx="10"/>
          <circle class="c" cx="-32" cy="-18" r="5"/><circle class="c" cx="-20" cy="-6" r="5"/>
          <circle class="c" cx="-8" cy="6" r="5"/>
        </g>
        <g transform="rotate(16 24 16)">
          <rect class="f cs3" x="0" y="-8" width="48" height="48" rx="9"/>
          <circle class="c" cx="12" cy="4" r="4.5"/><circle class="c" cx="36" cy="4" r="4.5"/>
          <circle class="c" cx="12" cy="28" r="4.5"/><circle class="c" cx="36" cy="28" r="4.5"/>
        </g>""",
    "Träffar och caféer": """
        <path class="s s4" d="M-12-14q-8-10 0-18t0-18M10-14q-8-10 0-18t0-18"/>
        <path class="f" d="M-34-4H34L28 30Q26 38 18 38H-18Q-26 38-28 30Z"/>
        <path class="s" d="M32 4Q50 2 48 15Q46 27 28 25"/>
        <ellipse class="f" cx="0" cy="43" rx="48" ry="6"/>""",
    "Böcker och litteratur": """
        <path class="f" d="M-2-20Q-26-36-50-28V30Q-26 22-2 36Z"/>
        <path class="f" d="M2-20Q26-36 50-28V30Q26 22 2 36Z"/>
        <path class="cs" d="M-40-14Q-26-20-12-12M-40 0Q-26-6-12 2M-40 14Q-26 8-12 16
          M40-14Q26-20 12-12M40 0Q26-6 12 2M40 14Q26 8 12 16"/>""",
    "Gratis": """
        <path class="f" d="M-50-28H50V-10A10 10 0 0 0 50 10V28H-50V10A10 10 0 0 0-50-10Z"/>
        <path class="cs" stroke-dasharray="5 6" d="M22-24V24"/>
        <path class="c" d="M-14 16L-32-2Q-40-12-30-18Q-22-22-14-12Q-6-22 2-18Q12-12 4-2Z"/>""",
    "Övrigt": star(0, 0, 42, 10, 4, -90) + star(34, -30, 15, 4, 4, -90) + star(-32, 28, 12, 3, 4, -90),
}


def forest(rng: random.Random, y0: float, height: float, step: float) -> str:
    """Granskog: en rad trianglar längs en svagt böljande linje, sedan rakt ned till y = 230."""
    pts = [f"{-W},230"]
    x = -W - 6.0
    while x < 2 * W + 6:
        h = height * rng.uniform(0.55, 1.0)
        base = y0 + 6 * rng.uniform(-1, 1)
        w = step * rng.uniform(0.8, 1.2)
        pts += [f"{x:.0f},{base:.0f}", f"{x + w / 2:.0f},{base - h:.0f}", f"{x + w:.0f},{base:.0f}"]
        x += w * 0.8
    pts.append(f"{2 * W},230")
    return " ".join(pts)


def svg(title: str) -> str:
    c = CATEGORIES[title]["color"]
    rng = random.Random(7)  # samma skog i alla bilder
    far = forest(rng, 190, 34, 22)
    near = forest(rng, 214, 46, 28)
    light = {"sky1": mix(c, WHITE, .9), "sky2": mix(c, WHITE, .74), "sun": mix(c, WHITE, .96),
             "hill": mix(c, WHITE, .6), "far": mix(c, WHITE, .3), "near": mix(c, "#0f172a", .35),
             "lake": mix(c, WHITE, .68), "glint": mix(c, WHITE, .88), "halo": mix(c, WHITE, .82)}
    dark = {"sky1": mix(c, DARK_BG, .88), "sky2": mix(c, DARK_BG, .7), "sun": mix(c, WHITE, .75),
            "hill": mix(c, DARK_BG, .5), "far": mix(c, "#03060c", .62), "near": mix(c, "#03060c", .8),
            "lake": mix(c, DARK_BG, .72), "glint": mix(c, DARK_BG, .45), "halo": mix(c, DARK_BG, .5)}

    def rules(p):
        return (f".sky1{{stop-color:{p['sky1']}}}.sky2{{stop-color:{p['sky2']}}}.sun{{fill:{p['sun']}}}"
                f".hill{{fill:{p['hill']}}}.far{{fill:{p['far']}}}.near{{fill:{p['near']}}}"
                f".lake{{fill:{p['lake']}}}.glint{{stroke:{p['glint']}}}.halo{{fill:{p['halo']}}}")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<style>
{rules(light)}
@media (prefers-color-scheme: dark) {{ {rules(dark)} }}
.s{{fill:none;stroke:#fff;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}}
.s3{{stroke-width:3}}.s4{{stroke-width:4}}.s5{{stroke-width:5}}.s8{{stroke-width:8}}.s10{{stroke-width:10}}
.f{{fill:#fff}}.c{{fill:{c}}}.ball{{fill:#fb923c;stroke:#fff;stroke-width:4}}.ws{{stroke:#fff;stroke-width:5}}
.cs{{fill:none;stroke:{c};stroke-width:4;stroke-linecap:round}}.cs2{{stroke:{c};stroke-width:3}}
.cs3{{stroke:{c};stroke-width:3;stroke-linejoin:round}}
.glint{{fill:none;stroke-width:3;stroke-linecap:round}}
</style>
<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" class="sky1"/><stop offset="1" class="sky2"/></linearGradient></defs>
<rect x="{-W}" width="{3 * W}" height="{H}" fill="url(#sky)"/>
<circle class="sun" cx="346" cy="58" r="24"/>
<path class="hill" d="M{-W} 180Q-200 150-100 186Q-40 160 0 196Q70 150 150 178Q230 140 300 170Q360 150 416 172Q500 140 600 184Q700 150 {2 * W} 176V230H{-W}Z"/>
<polygon class="far" points="{far}"/>
<polygon class="near" points="{near}"/>
<rect class="lake" x="{-W}" y="228" width="{3 * W}" height="{H - 228}"/>
<path class="glint" d="M-300 256h70M-160 270h90M-120 246h50M40 250h60M140 262h90M290 248h70M70 278h50M250 282h80
M450 252h80M560 272h60M690 248h90"/>
<circle class="halo" cx="208" cy="134" r="84" opacity=".55"/>
<circle class="c" cx="208" cy="134" r="72"/>
<g transform="translate(208 134)">{MOTIFS[title]}
</g>
</svg>
"""


def main():
    OUT.mkdir(exist_ok=True)
    missing = set(CATEGORIES) - set(MOTIFS)
    if missing:
        raise SystemExit(f"Motiv saknas för: {', '.join(sorted(missing))}")
    for title in CATEGORIES:
        (OUT / f"{slug(title)}.svg").write_text(svg(title), encoding="utf-8")
    print(f"{len(CATEGORIES)} platshållare i {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
