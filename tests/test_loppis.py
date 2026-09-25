"""Källorna loppisar.com och Karlstad Loppis (#43)."""

from datetime import date, timedelta

from merge import merge, similar
from sources import karlstadloppis, loppisar
from sources.karlstadloppis import KarlstadLoppis
from sources.loppisar import Loppisar

MONTHS = list(loppisar.MONTHS)
WEEKDAYS = ["Måndagen", "Tisdagen", "Onsdagen", "Torsdagen", "Fredagen", "Lördagen", "Söndagen"]
D1 = date.today() + timedelta(days=3)
D2 = D1 + timedelta(days=1)


def header(d: date) -> str:
    return (f"<tr><td><h4 style='margin:0px; margin-top:5px;'>{WEEKDAYS[d.weekday()]} den {d.day} "
            f"{MONTHS[d.month - 1]} {d.year}:</h4></td></tr>")


def row(lid, slug, name, times, place, kind="Säsongsloppis"):
    return f'''<tr> <td class="sokrow"> <img src="images/loppisar/thumbnail-x.jpg" align="left" />
      <a href="l{lid}/{slug}.html"><strong>{name}</strong></a> - {times} ({kind}) <br />
      <span style="font-size:11px"><strong>Plats:</strong> {place}</span> </td> </tr>'''


def search_page(*parts):
    return "<html><h2>Sökresultat</h2><table>" + "".join(parts) + "</table></html>"


def test_loppisar_groups_days_per_loppis():
    page = search_page(
        header(D1),
        row(4124, "z-loppis", "Z loppis", "11:00-11:00", "Zakrisdalsslingan 2, 653 42 Karlstad, Karlstads kommun"),
        row(3630, "johans", "Johans Diversehandel", "11:00-18:00", "Arvika Maskingränd 2 67141 Arvika , Arvika kommun"),
        header(D2),
        row(4124, "z-loppis", "Z loppis", "9:00-18:00", "Zakrisdalsslingan 2, 653 42 Karlstad, Karlstads kommun"),
        row(1, "hagfors", "Loppis i Hagfors", "10:00-14:00", "Storgatan 1, Hagfors kommun", kind="Engångsloppis"),
        '<tr><td><h4>Söndagen den 99 september 2026:</h4></td></tr>',   # ogiltigt datum
        row(2, "x", "Utan giltigt datum", "10:00-14:00", "Någonstans, Kils kommun"),
    )
    events = {e["title"]: e for e in Loppisar().normalize({"html": page})}
    assert set(events) == {"Z loppis", "Johans Diversehandel", "Loppis i Hagfors"}

    z = events["Z loppis"]
    assert z["id"] == "loppisar-4124" and z["url"] == "https://www.loppisar.com/l4124/z-loppis.html"
    assert [(o["date_start"], o["time_start"], o["time_end"]) for o in z["occasions"]] == [
        (D1.isoformat(), "11:00", None),                               # samma start- och sluttid = ingen sluttid
        (D2.isoformat(), "09:00", "18:00")]
    assert z["municipality"] == "Karlstad" and z["place"]["address"] == "Zakrisdalsslingan 2, 653 42 Karlstad"
    assert z["categories"][0]["title"] == "Marknad, mässa, auktion och loppis"
    assert z["images"] == []                                           # /images/ är spärrad i robots.txt
    assert events["Johans Diversehandel"]["place"]["address"] == "Arvika Maskingränd 2 67141 Arvika"
    assert events["Loppis i Hagfors"]["municipality"] == "Hagfors"     # inte "Hagfor"
    assert events["Loppis i Hagfors"]["summary"].startswith("Engångsloppis")


def test_loppisar_search_url_asks_for_varmland():
    url = loppisar.search_url(date(2026, 9, 25))
    assert "slanID=15" in url and "sdatum=2026-09-25" in url and "srangetime=30" in url


def test_loppis_word_does_not_merge_different_flea_markets():
    assert not similar("Z loppis", "Equmenia-scouternas extra-loppis")
    assert not similar("Loppis i Torsby", "Loppis i Sysslebäck")
    assert similar("Hånsfors Bruk, Loppis & Antikt", "Hånsfors Bruk Loppis")


def test_karlstadloppis_next_date(monkeypatch):
    monkeypatch.setattr(karlstadloppis, "today", lambda: date(2026, 9, 25))
    page = ('<div><span><b>Nästa loppis<br>Söndag 27 september.<br></b></span>'
            '<b>Norra fältet infanterigatan 14,65340&nbsp;</b></div>')
    assert karlstadloppis.next_date(page) == date(2026, 9, 27)
    assert karlstadloppis.next_date("Nästa loppis 3 maj") == date(2027, 5, 3)            # passerat i år: nästa år
    assert karlstadloppis.next_date("Nästa loppis Söndag 26 april 2026") == date(2026, 4, 26)
    assert karlstadloppis.next_date("Sommarens första datum kommer nån gång i April") is None
    assert karlstadloppis.next_date("Nästa loppis Söndag 31 september") is None


def test_karlstadloppis_event():
    d = date.today() + timedelta(days=2)
    page = f"<b>Nästa loppis<br>Söndag {d.day} {MONTHS[d.month - 1]} {d.year}.</b>"
    [e] = KarlstadLoppis().normalize({"html": page})
    assert e["title"] == "Bakluckeloppis I2 Norra Fältet" and e["municipality"] == "Karlstad"
    assert e["occasions"] == [{"date_start": d.isoformat(), "date_end": d.isoformat(),
                               "time_start": "10:00", "time_end": "15:00"}]
    assert {c["title"] for c in e["categories"]} == {"Marknad, mässa, auktion och loppis", "Gratis"}
    assert KarlstadLoppis().normalize({"html": "<p>Säsongen är slut</p>"}) == []             # inget fel utanför säsong


def test_flea_markets_from_both_sources_stay_apart():
    d = date.today() + timedelta(days=2)
    kl = KarlstadLoppis().normalize({"html": f"Nästa loppis {d.day} {MONTHS[d.month - 1]} {d.year}"})
    lc = Loppisar().normalize({"html": search_page(header(d), row(4124, "z", "Z loppis", "11:00-16:00",
                                                                  "Zakrisdalsslingan 2, Karlstads kommun"))})
    assert len(merge([kl, lc])) == 2
