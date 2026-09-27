"""Motorsport: SBF (LoTS) och Svemo TA som en källa, och kategorin Motorsport (#49)."""

import asyncio
from datetime import date, timedelta
from urllib.parse import parse_qs

import httpx

import chat
from categories import split_motorsport
from common import category, finalize
from merge import merge
from sources import motorsport
from sources.motorsport import SBF, Svemo, municipality, parse_rows

D1 = date.today() + timedelta(days=10)
D2 = D1 + timedelta(days=1)
LONG = D1 + timedelta(days=200)


def row(frm, to, organizer, branch, status, name, arena, cid, alt=False):
    return f'''<tr class="rg{'Alt' if alt else ''}Row" id="ctl00_x_{cid}">
      <td>{frm}</td><td>{to}</td><td>{organizer}</td><td>{branch}</td><td>{status}</td><td>{name}</td><td>{arena}</td>
      <td><a href="/Public/Pages/CompetitionInformation/CompetitionInformation.aspx?CompetitionId={cid}">Visa</a></td></tr>'''


def page(rows, current=1, total=1, viewstate="VS1"):
    pager = f'''<tr class="rgPager"><td>
      <input type="button" name="grid$first" value=" " title="First Page" />
      <input type="button" name="grid$prev" value=" " title="Previous Page" />
      <a class="rgCurrentPage"><span>{current}</span></a>
      <input type="button" name="grid$next" value=" " title="Next Page" />
      <input type="button" name="grid$last" value=" " title="Last Page" />
      <div class="rgWrap rgInfoPart">&nbsp;{len(rows) * total} items in <strong>{total}</strong> pages</div></td></tr>'''
    return f'''<html><form><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="{viewstate}" />
      <input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="G" />
      <table>{pager}{"".join(rows)}</table></form></html>'''


SBF_ROWS = [
    row(D1, D2, "Karlstads Motor-club Bil", "Folkrace", "D) Distriktstävling (SDF)", "NGK MASTERS", "Kalvholmens Motorstadion", 1),
    row(D1, D1, "Hällefors Motorklubb", "Folkrace", "D) Distriktstävling (SDF)", "Snacksracet", "Hagforsvallen", 2, alt=True),
    row(D1, D1, "Säffle Motor Club", "Rally", "3. B-besiktning (Rally), D) Distriktstävling (SDF), Prova Bilsport (SDF)",
        "AP-Rundan", "Tillfällig", 3),
    row(D1, D1, "Storfors Motorklubb", "Folkrace", "Prova Bilsport (SDF), Uppvisning (SDF)", "Familjedag", "Nya Storfors Ring", 4),
    row(D1, D1, "Finnskoga Motorklubb", "Folkrace", "E) Lokaltävling (SDF)", "Klubbtävling", "Finnskoga Motorstadion", 5),
    # Ska sållas bort:
    row(D1, LONG, "Säffle Motor Club", "Folkrace", "Prova Bilsport (SDF), Träning (SDF)", "Träning", "Krokstabanan", 6),
    row(D1, D1, "Munkfors Motor Club", "Folkrace", "Träning (SDF)", "Träning", "Tomtfallets Motorstadion", 7),
    row(D1, D1, "Eskilstuna Motorklubb", "Folkrace", "D) Distriktstävling (SDF)", "Höstrusket", "Ekebybanan", 8),
    row(D1, D1, "Karlstad Miniracing MHF/Ungdom", "Radiostyrd Bilsport", "E) Lokaltävling (SDF)", "Msec 1", "Ankargatan", 9),
    row(D1, D1, "Arvika Motorklubb", "Folkrace", "D2) Distriktstävling utan publik (SDF)", "Internt", "Arvika", 10),
    row(D1, D2, "Årjängs Motorklubb", "Folkrace", "D2) Distriktstävling utan publik (SDF), Prova Bilsport (SDF)",
        "Prova på", "Nordmarkens Motorstadion", 11),
]


def test_parse_rows_and_filter():
    rows = parse_rows(page(SBF_ROWS))
    assert len(rows) == len(SBF_ROWS) and rows[0]["id"] == "1" and rows[1]["arena"] == "Hagforsvallen"
    events = {e["title"]: e for e in SBF().normalize({"rows": rows})}
    assert set(events) == {"NGK MASTERS", "Snacksracet", "AP-Rundan", "Familjedag", "Folkrace – Klubbtävling", "Prova på"}

    ngk = events["NGK MASTERS"]
    assert ngk["municipality"] == "Karlstad" and ngk["place"]["title"] == "Kalvholmens Motorstadion"
    assert ngk["occasions"][0]["date_start"] == D1.isoformat() and ngk["occasions"][0]["date_end"] == D2.isoformat()
    assert ngk["summary"] == "Folkrace på Kalvholmens Motorstadion. Distriktstävling."
    assert ngk["url"].endswith("CompetitionId=1") and ngk["url"].startswith("https://lots.sbf.se/")
    assert [c["title"] for c in ngk["categories"]] == ["Motorsport"]
    assert events["Snacksracet"]["municipality"] == "Hagfors"                # Örebroklubb på värmländsk bana
    assert events["AP-Rundan"]["municipality"] == "Säffle"                   # tillfällig bana: klubbens ort
    assert events["AP-Rundan"]["place"]["title"] == "Säffle"
    assert "Prova på" in events["Familjedag"]["summary"]
    assert "Prova på" in events["Prova på"]["summary"]                       # utan publik, men prova på


def test_municipality_from_track_or_club():
    assert municipality("Kalvholmens Motorstadion", "X") == "Karlstad"
    assert municipality("Gelleråsen Arena Karting", "Karlskoga MF") == "Karlskoga"
    assert municipality("Skogen", "Kristinehamns MK") == "Kristinehamn"
    assert municipality("Lökenebanan", "Kils MK Motorcykel") == "Kil"
    assert municipality("Ekebybanan", "Eskilstuna Motorklubb") is None     # "kil" i Eskilstuna räknas inte
    assert municipality("Eds-banan", "Eds-Skottbacka MX") is None
    assert municipality("Grudziadz", "Polen") is None


def test_rally_villages():
    """Rallyn utgår ofta från en by, och klubbnamnet saknar kommun (#51)."""
    assert municipality("Vitsand", "Motorklubben Ratten") == "Torsby"       # Finnskogsvalen
    assert municipality("Tillfällig", "Töcksfors MK") == "Årjäng"
    assert municipality("Uddeholm", "X") == "Hagfors"
    assert municipality("Nordmarkens Motorstadion", "Årjängs Motorklubb") == "Årjäng"
    assert municipality("Sångens motorstadion", "Hällefors Motorklubb") is None
    assert municipality("Tillfällig", "Motorklubben Ratten") is None        # klubben säger inget om orten


def run(source, handler):
    requests = []

    def record(request):
        requests.append(request)
        return handler(request, len(requests))

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(record)) as client:
            return await source.fetch(client, None)
    return asyncio.run(go()), requests


def test_sbf_reads_all_pages_with_postback(monkeypatch):
    monkeypatch.setattr(motorsport, "PAGE_DELAY", 0)
    pages = [page([SBF_ROWS[i]], current=i + 1, total=3, viewstate=f"VS{i + 1}") for i in range(3)]

    def handler(request, n):
        return httpx.Response(200, text=pages[n - 1])
    payload, requests = run(SBF(), handler)
    assert [r["id"] for r in payload["rows"]] == ["1", "2", "3"]
    assert [r.method for r in requests] == ["GET", "POST", "POST"]
    form = parse_qs(requests[1].content.decode())
    assert form["__EVENTTARGET"] == ["grid$next"] and form["__VIEWSTATE"] == ["VS1"]


def test_svemo_reads_last_pages_backwards(monkeypatch):
    monkeypatch.setattr(motorsport, "PAGE_DELAY", 0)
    old = row("2012-05-05", "2012-05-05", "FMCK Gotland", "Motocross", "Nationell", "Stockholmscrossen", "Motorgropen", 90)
    past = row((date.today() - timedelta(days=30)).isoformat(), (date.today() - timedelta(days=30)).isoformat(),
               "Kils MK Motorcykel", "Enduro", "Enklare tävling", "Wermlandsenduron 8", "Lökenebanan", 91)
    future = [row(D1, D1, "Kils MK Motorcykel", "Enduro", "Enklare tävling", "Wermlandsenduron 10 Skoj på Hoj", "Lökenebanan", 92),
              row(D1, D1, "Hagfors Motor Cykel Klubb", "Speedway", "Träning", "Träning", "Tallhult", 93),
              row(D2, D2, "Karlstad Speedway Klubb", "Speedway", "Nationell/Internationell", "Valsarna - Vargarna",
                  "Emtbjörks AB Arena", 94)]
    responses = {"GET": page([old], current=1, total=260),
                 "grid$last": page(future, current=260, total=260, viewstate="VSL"),
                 "grid$prev": page([past], current=259, total=260, viewstate="VSP")}

    def handler(request, n):
        if request.method == "GET":
            return httpx.Response(200, text=responses["GET"])
        return httpx.Response(200, text=responses[parse_qs(request.content.decode())["__EVENTTARGET"][0]])
    payload, requests = run(Svemo(), handler)
    assert len(requests) == 3                                              # första, sista och en bakåt
    events = {e["title"]: e for e in Svemo().normalize(payload)}
    assert set(events) == {"Wermlandsenduron 10 Skoj på Hoj", "Valsarna - Vargarna"}   # inte träning
    assert events["Valsarna - Vargarna"]["municipality"] == "Hagfors"
    assert events["Valsarna - Vargarna"]["summary"].startswith("Speedway på Emtbjörks AB Arena. Nationell tävling")


def test_changed_page_is_an_error():
    import pytest
    from common import SourceError

    with pytest.raises(SourceError):
        run(SBF(), lambda request, n: httpx.Response(200, text="<html>Underhåll</html>"))


def test_motorsport_category_split():
    def titles(title, cats, summary=""):
        return [c["title"] for c in split_motorsport([category(c) for c in cats], title, summary)]
    assert titles("Folkrace", ["Motor"]) == ["Motorsport"]
    assert titles("Wermlandsenduron - deltävling: Skoj på hoj", ["Motor"]) == ["Motorsport"]
    assert titles("Prins Carl Philips Racing Pokal med Barnens Motordag", ["Evenemang", "Motor", "Barn"]) == \
        ["Motorsport", "Evenemang", "Motor", "Barn"]                         # motordag: behåller Motor
    assert titles("Veteranfordonsträff & våffelkväll", ["Övriga evenemang", "Motor"]) == ["Övriga evenemang", "Motor"]
    assert titles("Lunnedets Motorträff", ["Evenemang", "Motor"]) == ["Evenemang", "Motor"]


def vv_event(title, day, muni, cats=("Motor",)):
    return finalize({"id": f"vv-{title}", "source": "Visit Värmland", "title": title, "summary": "", "description": "",
                     "categories": [category(c) for c in cats], "municipality": muni, "place": None, "organizer": None,
                     "url": "https://visitvarmland.com/x", "booking_link": None, "website_link": None, "images": [],
                     "occasions": [{"date_start": day.isoformat(), "date_end": day.isoformat(),
                                    "time_start": "10:00", "time_end": None}]})


def test_duplicates_with_visit_varmland_are_merged():
    sbf = SBF().normalize({"rows": parse_rows(page([
        row(D1, D1, "Munkfors Motor Club", "Folkrace", "D) Distriktstävling (SDF)", "Höstracet", "Tomtfallets Motorstadion", 20),
        row(D1, D1, "Säffle Motor Club", "Folkrace", "D) Distriktstävling (SDF)", "Vårracet", "Krokstabanan", 21)]))})
    vv = [vv_event("Folkrace", D1, "Munkfors"), vv_event("Loppis i Munkfors", D1, "Munkfors", ("Loppis",))]
    merged = merge([vv, sbf])
    titles = sorted(e["title"] for e in merged)
    assert titles == ["Folkrace", "Loppis i Munkfors", "Vårracet"]
    folkrace = next(e for e in merged if e["title"] == "Folkrace")
    assert [s["name"] for s in folkrace["sources"]] == ["Visit Värmland", "Svensk Bilsport (SBF)"]


def test_chat_understands_motorsport():
    assert chat.find_categories("Finns det något folkrace i helgen?") == {"Motorsport"}
    assert chat.find_categories("Vilka rallyn går i oktober?") == {"Motorsport"}
    assert chat.find_categories("Finns det någon motorträff?") == {"Motor"}
    assert chat.classify("När är nästa folkrace?") == "search"
    evs = [{"title": "NGK MASTERS", "summary": "Folkrace på Kalvholmens Motorstadion.", "description": "",
            "organizer": "Karlstads Motor-club Bil", "place": {"title": "Kalvholmens Motorstadion"},
            "municipality": "Karlstad", "url": "https://x", "categories": [{"title": "Motorsport"}],
            "occasions": [{"date_start": D1.isoformat(), "date_end": D1.isoformat(), "time_start": None, "time_end": None}]}]
    ok = chat.scope_check("Är NGK Masters på Kalvholmen värt att se för en 10-åring?", evs, date.today())
    assert ok["ok"] and "Kalvholmen" in " ".join(ok["entities"])
    assert not chat.scope_check("När går Rally Sweden i Umeå?", evs, date.today())["ok"]
    text, _ = chat.search_answer("När är nästa folkrace?", evs, date.today())
    assert "NGK MASTERS" in text


def test_multi_day_race_merges_with_single_day_listing():
    sbf = SBF().normalize({"rows": parse_rows(page([
        row(D1, D2, "Karlskoga Motorförening", "Karting", "D) Distriktstävling (SDF)", "Prins Carl-Philips Racing Pokal / Nobelracet",
            "Gelleråsen Arena Karting", 30)]))})
    vv = [vv_event("Prins Carl Philips Racing Pokal med Barnens Motordag", D2, "Karlskoga", ("Evenemang", "Motor", "Barn"))]
    merged = merge([vv, sbf])
    assert len(merged) == 1 and [s["name"] for s in merged[0]["sources"]] == ["Visit Värmland", "Svensk Bilsport (SBF)"]
