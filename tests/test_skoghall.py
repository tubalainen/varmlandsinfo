"""Skoghalls Folkets Hus (#96): allt utom film och sändningar på bioduken."""

from datetime import date, timedelta

from merge import merge
from sources import skoghall
from sources.visitvarmland import normalize_event

DAY = (date.today() + timedelta(days=20)).isoformat()
D, M = DAY[8:], DAY[5:7]


def prod(id_, title, categories=(), content="<p>Text.</p>"):
    return {"id": id_, "title": title, "link": f"https://skoghallsfolketshus.se/produktion/p{id_}/",
            "categories": list(categories), "content": content}


def page(time="19:00", salong="1", price="195", ticket=True, poster=True):
    link = (f'<a href="https://sfh.internetbokningen.com/chap/api/tomovie@salongnr={salong}&amp;tid={time}&amp;'
            f'datum={DAY}" target="_blank" class="event-button tickets-button">Boka/köp biljetter</a>') if ticket else ""
    img = ('<img width="180" height="320" src="https://skoghallsfolketshus.se/wp-content/uploads/p-180x320.jpg" '
           'class="attachment-medium-poster size-medium-poster wp-post-image" alt="" srcset="'
           'https://skoghallsfolketshus.se/wp-content/uploads/p-180x320.jpg 180w, '
           'https://skoghallsfolketshus.se/wp-content/uploads/p-522x928.jpg 522w, '
           'https://skoghallsfolketshus.se/wp-content/uploads/p.jpg 1080w" />') if poster else ""
    return (f'<html>{img}<div class="x"><table class="event-table"><tbody><tr class="event-row">'
            f'<td>lördag <strong>{D}/{M}</strong> kl. {time}</td><td></td><td>{price} kr</td><td>{link}</td></tr>'
            f'</tbody></table></div><div id="footer">Telefon 054-51 55 00</div></html>')


def normalize(*items):
    return skoghall.SkoghallsFolketsHus().normalize(
        {"productions": [p for p, _ in items], "pages": {p["link"]: skoghall.trim(pg) for p, pg in items}})


def test_only_live_events():
    live = [prod(1, "Pubkväll med Green Road Band"),                                   # ingen kategori, men titeln
            prod(2, "Teater: 123 Schtunk", ["Teater"]),
            prod(3, "Konsert: The Hebbe Family &#038; Hammarö manskör", ["konsert", "Musik"]),
            prod(4, "Svenshult: En sagolik jul (Wermland Opera)", ["Julkonsert", "Svenshult"])]
    screen = [prod(5, "Verity", ["Crime", "Drama", "Thriller"]),                      # film
              prod(6, "Vi är Metal Dragon", ["Komedi", "Musik"]),                     # film om ett band
              prod(7, "Arkipelag (Även som Seniorbio)"),
              prod(8, "Opera på Bio: Otello", content="<p>Otello livesänds till biografer världen över.</p>"),
              prod(9, "Musikal på Bio: Top Hat &#8211; the Musical", ["Musikal"]),
              prod(10, "André Rieus 2026 Christmas Concert", ["konsert", "Musik"],
                   "<p>Ett exklusivt festligt evenemang på bio.</p>"),
              prod(11, "Knattebio: Alfons Åberg", ["Animerad film", "Barnfilm"])]
    assert [p["id"] for p in live + screen if skoghall.is_live(p)] == [1, 2, 3, 4]


def test_normalize_production():
    e, = normalize((prod(1, "Rockpub &#8211; Trash til Death", ["Live på Scen", "Metal", "Rockpub"],
                         "<p>Thrash metal från Skoghall.</p>"), page("19:00", salong="6", price="100")))
    assert e["title"] == "Rockpub – Trash til Death"
    assert e["occasions"][0]["date_start"] == DAY and e["occasions"][0]["time_start"] == "19:00"
    assert e["municipality"] == "Hammarö" and e["place"]["title"] == "Skoghalls Folkets Hus, restaurangen"
    assert [c["title"] for c in e["categories"]][0] == "Musik"
    assert e["summary"].endswith("Pris 100 kr.")
    assert e["booking_link"].endswith(f"salongnr=6&tid=19:00&datum={DAY}")
    assert e["images"][0]["small"].endswith("p-180x320.jpg") and e["images"][0]["medium"].endswith("p-522x928.jpg")
    assert e["images"][0]["large"].endswith("/p.jpg")


def test_other_places_and_row_fallback():
    kajsa, svenshult = normalize(
        (prod(1, "Kajsas Röda Hjärta (Tingvallakyrkan Karlstad)", ["Teater"]), page(ticket=False, poster=False)),
        (prod(2, "Svenshult: En sagolik jul (Wermland Opera)", ["Julkonsert"], "<p>Bygdegården Svenshult</p>"),
         page("16:00", salong="5")))
    assert kajsa["place"]["title"] == "Tingvallakyrkan" and kajsa["municipality"] == "Karlstad"
    assert kajsa["occasions"][0] == {"date_start": DAY, "date_end": DAY, "time_start": "19:00", "time_end": None}
    assert kajsa["booking_link"] is None and kajsa["images"] == []
    assert svenshult["place"]["title"] == "Bygdegården Svenshult" and svenshult["municipality"] == "Hammarö"


def test_merges_with_visit_varmland_by_time_and_place():
    """Samma konsert med helt olika titlar: samma dag, tid och lokal, och Hebbe nämns i Visit Värmlands ingress."""
    vv = normalize_event({"id": 9, "title": "Säg det med ett leende", "slug": "e/9",
                          "sales_text": "Följ med systrarna i The Hebbe Sisters och Hammarö Manskör.",
                          "categories": [{"title": "Musik"}],
                          "places": [{"title": "Skoghalls Folkets hus",
                                      "address": {"street_1": "Skogåsvägen 3", "zip_code": "663 30"}}],
                          "occasions": [{"date_start": DAY, "date_end": DAY, "time_start": "19:00:00"}]}, {})
    hebbe, other = normalize((prod(1, "Konsert: The Hebbe Family &#038; Hammarö manskör", ["konsert"]), page()),
                             (prod(2, "Pubkväll med Anders Djup", ["Pubkväll"]), page(salong="6")))
    merged = merge([[vv], [hebbe, other]])
    assert [e["title"] for e in merged] == ["Säg det med ett leende", "Pubkväll med Anders Djup"]
    assert [s["name"] for s in merged[0]["sources"]] == ["Visit Värmland", "Skoghalls Folkets Hus"]
