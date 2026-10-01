"""Riksteatern (#98): de publika föreställningarna i Värmlands län."""

from datetime import date, timedelta

import chat
from merge import merge
from sources import riksteatern, skoghall

DAY = (date.today() + timedelta(days=20)).isoformat()


def perf(title, place, municipality, time="19:00", org="Torsby Teaterförening – en del av Riksteatern", slug="p",
         **flags):
    """En föreställning som Riksteaterns API ger den (fälten som appen använder)."""
    return {"title": title, "date": f"{DAY}T{time}:00+02:00", "startTime": time, "municipality": municipality,
            "location": municipality, "locationInfo": place,
            "url": f"/forestallningar/{slug}/{DAY.replace('-', '')}{time.replace(':', '')}-139075G",
            "orgName": org, "imageUrl": f"https://www.riksteatern.se/globalassets/{slug}.jpg",
            "isPrivate": False, "isCanceled": False, "isPostponed": False, **flags}


def normalize(*items):
    return riksteatern.Riksteatern().normalize({"performances": list(items)})


def test_normalize_performance():
    e, = normalize(perf("Stina Ekblad och Strindbergs musikaliska värld", "Oleby Folkets Hus, Oleby, Torsby",
                        "Torsby", slug="stina-ekblad"))
    assert e["source"] == "Riksteatern" and e["id"].startswith("riksteatern-") and e["id"].endswith("-139075G")
    assert e["occasions"][0] == {"date_start": DAY, "date_end": DAY, "time_start": "19:00", "time_end": None}
    assert e["municipality"] == "Torsby" and e["place"]["title"] == "Oleby Folkets Hus, Oleby, Torsby"
    assert e["organizer"] == "Torsby Teaterförening – en del av Riksteatern"
    assert e["url"].startswith("https://www.riksteatern.se/forestallningar/stina-ekblad/")
    assert e["images"][0]["large"] == "https://www.riksteatern.se/globalassets/stina-ekblad.jpg"
    assert "Teater och underhållning" in [c["title"] for c in e["categories"]]
    assert e["summary"] == "Riksteatern, arrangör Torsby Teaterförening – en del av Riksteatern."


def test_only_public_performances():
    """Slutna (skolföreställningar, matiné för kommunen), inställda, flyttade och bio tas inte med."""
    public = [perf("Kvinnor och äppelträd", "Christinateatern, Kristinehamn", "Kristinehamn", slug="a"),
              perf("Vid Dneprs strand", "Muséet Kvarnen, Filipstad", "Filipstad", "18:00", slug="b")]
    other = [perf("Förstör den här pjäsen", "Grossbolsskolan, Grossbolshallen, Forshaga", "Forshaga", "10:30",
                  slug="c", isPrivate=True),
             perf("Åh Dorian!", "Christinateatern, Kristinehamn", "Kristinehamn", "13:00", slug="d", isPrivate=True),
             perf("Ett hjärta i dagens läge", "Christinateatern, Kristinehamn", "Kristinehamn", slug="e",
                  isCanceled=True),
             perf("Rent Hus", "Folkets Hus, Lunnasalen, Skoghall, Hammarö", "Hammarö", slug="f", isPostponed=True),
             perf("Opera på bio: Tosca", "Bio Roxy, Karlstad", "Karlstad", slug="g")]
    assert [e["title"] for e in normalize(*public, *other)] == ["Kvinnor och äppelträd", "Vid Dneprs strand"]
    assert normalize(public[0], public[0]) == normalize(public[0])           # samma föreställning en gång


def test_passed_and_broken_performances_are_skipped():
    old = perf("Gammal", "Ritz, Arvika", "Arvika", slug="h")
    old["date"] = "2020-01-01T19:00:00+01:00"
    broken = perf("Utan datum", "Ritz, Arvika", "Arvika", slug="i")
    broken["date"] = None
    assert normalize(old, broken, "inte en föreställning") == []


def test_merges_with_skoghall():
    """Rent Hus i Skoghalls Folkets Hus finns både hos huset och hos Riksteatern: ett evenemang, två länkar."""
    house = skoghall.SkoghallsFolketsHus().normalize({
        "productions": [{"id": 1, "title": "Musikteater: Rent Hus", "link": "https://skoghallsfolketshus.se/p/1/",
                         "categories": ["Musikteater"], "content": "<p>Karlstads Riksteaterförening.</p>"}],
        "pages": {"https://skoghallsfolketshus.se/p/1/":
                  f'<table class="event-table"><tr class="event-row"><td>'
                  f'<a href="https://x/tomovie@salongnr=1&amp;tid=14:00&amp;datum={DAY}" class="tickets-button">'
                  f'Boka</a></td></tr></table>'}})
    rt = normalize(perf("Rent Hus", "Folkets Hus, Lunnasalen, Skoghall, Hammarö", "Hammarö", "14:00", slug="rent",
                        org="Karlstads Riksteaterförening"))
    merged = merge([house, rt])
    assert len(merged) == 1
    assert [s["name"] for s in merged[0]["sources"]] == ["Skoghalls Folkets Hus", "Riksteatern"]


def test_ask_ai_knows_riksteatern():
    events = merge([normalize(perf("Kvinnor och äppelträd", "Christinateatern, Kristinehamn", "Kristinehamn",
                                   org="Kristinehamns Teaterförening – en del av Riksteatern"))])
    assert chat.scope_check("Vad spelar Riksteatern i Kristinehamn?", events, date.today())["ok"]
    assert not chat.scope_check("Vad spelar Dramaten i Kristinehamn?", events, date.today())["ok"]
