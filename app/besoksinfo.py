"""Den dolda sidan /besoksinfo: besöksstatistik som HTML, utan skript (#66)."""

from datetime import date
from html import escape

import geoip
from version import __version__

PERIODS = (7, 30, 90, 365)
LABELS = {"country": "Länder", "city": "Orter", "device": "Enheter", "browser": "Webbläsare", "os": "Operativsystem",
          "referrer": "Hänvisningar"}
MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
TOP = 10

STYLE = """
.page { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
.head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 12px; }
.head h1 { margin: 0; font-size: 1.5rem; }
.periods { display: flex; gap: 6px; flex-wrap: wrap; }
.periods a { padding: 5px 11px; border-radius: 9px; border: 1px solid var(--line); background: var(--card); color: var(--text);
             text-decoration: none; font-size: .85rem; font-weight: 600; }
.periods a[aria-current] { background: var(--accent); border-color: transparent; color: var(--on-accent); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }
.tile, .panel { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.tile { padding: 14px 16px; }
.tile .label { color: var(--muted); font-size: .82rem; }
.tile .value { font-size: 1.9rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.2; }
.tile .note { color: var(--muted); font-size: .76rem; }
.panel { padding: 16px 18px; margin-bottom: 14px; }
.panel h2 { margin: 0 0 10px; font-size: 1.05rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
.grid .panel { margin: 0; }
.chart { display: flex; align-items: flex-end; gap: 2px; height: 160px; padding-top: 6px; border-bottom: 1px solid var(--line); }
.chart .col { flex: 1 1 0; display: flex; align-items: flex-end; height: 100%; min-width: 2px; }
.chart .bar { width: 100%; background: var(--accent); border-radius: 4px 4px 0 0; min-height: 1px; }
.chart .col:hover .bar { background: var(--accent-text); }
.axis { display: flex; justify-content: space-between; color: var(--muted); font-size: .75rem; margin-top: 4px; }
.rows { list-style: none; margin: 0; padding: 0; }
.rows li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 10px; padding: 5px 0; font-size: .88rem; }
.rows .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rows .n { font-variant-numeric: tabular-nums; color: var(--muted); }
.rows .track { grid-column: 1 / -1; height: 6px; border-radius: 4px; background: var(--surface-2); }
.rows .fill { height: 100%; border-radius: 4px; background: var(--accent); }
table { width: 100%; border-collapse: collapse; font-size: .86rem; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-size: .76rem; text-transform: uppercase; letter-spacing: .04em; }
td.num { font-variant-numeric: tabular-nums; text-align: right; }
.scroll { overflow-x: auto; }
details summary { cursor: pointer; color: var(--accent-text); font-size: .88rem; margin-top: 10px; }
.foot { color: var(--muted); font-size: .8rem; margin-top: 20px; }
.empty { color: var(--muted); font-size: .88rem; }
"""


def _fmt_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]}"


def _chart(series: list[dict]) -> str:
    """Unika besökare per dag som staplar (per månad för ett år)."""
    if len(series) > 90:
        months: dict[str, dict] = {}
        for s in series:
            m = months.setdefault(s["date"][:7], {"date": s["date"][:7] + "-01", "unique": 0, "visits": 0, "label": ""})
            m["unique"] += s["unique"]
            m["visits"] += s["visits"]
        points = [{**m, "label": f"{MONTHS[int(k[5:]) - 1]} {k[:4]}"} for k, m in months.items()]
    else:
        points = [{**s, "label": _fmt_day(s["date"])} for s in series]
    top = max((p["unique"] for p in points), default=0) or 1
    cols = "".join(
        f'<div class="col" title="{escape(p["label"])}: {p["unique"]} unika, {p["visits"]} sidvisningar">'
        f'<div class="bar" style="height:{max(p["unique"] / top * 100, 0.5 if p["unique"] else 0):.1f}%"></div></div>'
        for p in points)
    rows = "".join(f'<tr><td>{escape(p["label"])}</td><td class="num">{p["unique"]}</td><td class="num">{p["visits"]}</td></tr>'
                   for p in reversed(points))
    return (f'<div class="chart" role="img" aria-label="Unika besökare per {"månad" if len(series) > 90 else "dag"}">{cols}</div>'
            f'<div class="axis"><span>{escape(points[0]["label"])}</span><span>{escape(points[-1]["label"])}</span></div>'
            f'<details><summary>Visa som tabell</summary><div class="scroll"><table><thead><tr><th>Period</th>'
            f'<th class="num">Unika</th><th class="num">Sidvisningar</th></tr></thead><tbody>{rows}</tbody></table></div></details>')


def _top(title: str, items: list) -> str:
    total = sum(n for _, n in items) or 1
    best = items[0][1] if items else 1
    rows = "".join(
        f'<li><span class="name" title="{escape(str(name))}">{escape(str(name))}</span>'
        f'<span class="n">{n} ({n / total:.0%})</span>'
        f'<span class="track"><span class="fill" style="display:block;width:{n / best * 100:.1f}%"></span></span></li>'
        for name, n in items[:TOP])
    more = f'<p class="empty">+ {len(items) - TOP} till</p>' if len(items) > TOP else ""
    return f'<section class="panel"><h2>{escape(title)}</h2>' + (
        f'<ul class="rows">{rows}</ul>{more}' if items else '<p class="empty">Inga besök under perioden.</p>') + "</section>"


def _visitors(visitors: list[dict]) -> str:
    if not visitors:
        return '<p class="empty">Inga besök i dag än.</p>'
    rows = "".join(
        f'<tr><td>{escape(v.get("ip", ""))}</td>'
        f'<td>{escape(v["first"])}–{escape(v["last"])}</td><td class="num">{v["hits"]}</td>'
        f'<td>{escape(v.get("city", ""))}</td><td>{escape(v.get("device", ""))}</td>'
        f'<td>{escape(v.get("browser", ""))} · {escape(v.get("os", ""))}</td><td>{escape(v.get("referrer", ""))}</td></tr>'
        for v in visitors)
    return ('<div class="scroll"><table><thead><tr><th>IP-adress</th><th>Tid</th><th class="num">Visningar</th><th>Plats</th>'
            f'<th>Enhet</th><th>Webbläsare</th><th>Hänvisning</th></tr></thead><tbody>{rows}</tbody></table></div>')


def render(report: dict, period: int, geo_available: bool) -> str:
    current = ' aria-current="page"'
    periods = "".join(f'<a href="?dagar={p}"{current if p == period else ""}>{"1 år" if p == 365 else f"{p} dagar"}</a>'
                      for p in PERIODS)
    t, pr = report["today"], report["period"]
    since = f" Statistik finns sedan {_fmt_day(report['first_day'])}." if report.get("first_day") else ""
    geo_note = "" if geo_available else " Geodatabasen är inte hämtad än, så platserna visas som okända."
    tiles = (
        f'<div class="tile"><div class="label">Unika besökare i dag</div><div class="value">{t["unique"]}</div></div>'
        f'<div class="tile"><div class="label">Sidvisningar i dag</div><div class="value">{t["visits"]}</div></div>'
        f'<div class="tile"><div class="label">Unika besökare, {period} dagar</div><div class="value">{pr["unique"]}</div>'
        f'<div class="note">summa av unika per dygn</div></div>'
        f'<div class="tile"><div class="label">Sidvisningar, {period} dagar</div><div class="value">{pr["visits"]}</div></div>')
    tops = "".join(_top(LABELS[dim], report["top"][dim]) for dim in LABELS)
    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<title>Besöksinfo – Värmlandsinfo</title>
<link rel="icon" href="/static/icons/icon.svg?v={__version__}" type="image/svg+xml">
<link rel="stylesheet" href="/static/style.css?v={__version__}">
<style>{STYLE}</style>
</head>
<body>
<main class="page">
  <div class="head">
    <h1>Besöksinfo</h1>
    <nav class="periods" aria-label="Period">{periods}</nav>
  </div>
  <div class="tiles">{tiles}</div>
  <section class="panel"><h2>Unika besökare per {"månad" if period > 90 else "dag"}</h2>{_chart(report["series"])}</section>
  <div class="grid">{tops}</div>
  <section class="panel" style="margin-top:14px"><h2>Dagens besökare</h2>{_visitors(report["visitors"])}</section>
  <p class="foot">Unika besökare räknas per dygn utan cookies. Dagens besökare visas med IP-adress till städningen efter
  dygnets slut, därefter finns bara summerad statistik kvar i 13 månader. Robotar räknas inte.{since}{geo_note}
  <a href="{geoip.ATTRIBUTION_URL}">{geoip.ATTRIBUTION}</a>.</p>
</main>
</body>
</html>"""
