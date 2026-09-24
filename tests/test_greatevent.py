from datetime import date, timedelta

from merge import merge
from sources import greatevent
from sources.greatevent import GreatEvent, parse_dates

MONTHS = list(greatevent.MONTHS)
D1 = date.today() + timedelta(days=40)
D2 = D1 + timedelta(days=1)
NEXT_YEAR = date.today().year + 1


def textual(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def block(date_line, title, intro="Ingress.", more="", buttons=(("https://tickets.example/1", "Köp biljetter"),)):
    btns = "".join(f'''<div class="elementor-button-wrapper"> <a class="elementor-button elementor-button-link elementor-size-sm"
      href="{href}" target="_blank"> <span class="elementor-button-text">{label}</span> </a></div>''' for href, label in buttons)
    toggle = f'''<div class="elementor-toggle"><div class="elementor-toggle-item">
      <div class="elementor-tab-title"><a class="elementor-toggle-title">Läs mer</a></div>
      <div id="elementor-tab-content-1" class="elementor-tab-content elementor-clearfix" data-tab="1">{more}</div>
      </div></div>''' if more else ""
    return f'''<div class="elementor-element e-flex e-con-boxed e-con e-parent" data-id="x"><div class="e-con-inner">
      <a href="https://example.com/"><img src="https://www.greateventofkarlstad.se/wp-content/uploads/2026/09/bild.jpg" alt=""></a>
      <div class="elementor-widget-container"><p>{date_line}</p></div>
      <div class="elementor-widget-container"><h2 class="elementor-heading-title elementor-size-default">{title}</h2></div>
      <div class="elementor-widget-container"><p class="p1">{intro}</p></div>
      {toggle}{btns}
    </div></div>'''


def page(*blocks):
    head = '<html><head><meta property="og:description" content="1/1 2030 | Fel, Fel"></head><body>'
    return head + "".join(blocks) + "<footer><p>©2026 Great Event</p></footer></body></html>"


def test_parse_dates_formats():
    assert parse_dates("Fre 23 oktober 2026") == [(date(2026, 10, 23),) * 2]
    assert parse_dates("Fre-lör 19-20 februari 2027") == [(date(2027, 2, 19), date(2027, 2, 20))]
    assert parse_dates("6/11, 20/11, 8/12 2026") == [(date(2026, 11, 6),) * 2, (date(2026, 11, 20),) * 2,
                                                     (date(2026, 12, 8),) * 2]
    assert parse_dates("30 januari – 2 februari 2027") == [(date(2027, 1, 30), date(2027, 2, 2))]
    assert parse_dates("Lör 5 december 2026 och sön 10 januari 2027") == [(date(2026, 12, 5),) * 2,
                                                                          (date(2027, 1, 10),) * 2]
    assert parse_dates("31/2 2027") == []
    assert parse_dates("Kommer snart") == []


def test_normalize_events_from_page():
    html = page(
        block(f"Fre {textual(D1)} | Löfbergs Arena, Karlstad", "Stor konsert",
              intro="En arenaturné med <em>nya låtar</em> .", more="<p>Mer om konserten.</p>",
              buttons=(("https://tickets.example/1", "Köp biljetter"), ("https://food.example", "Mat innan konsert"))),
        block(f"Fre-lör 19-20 februari {NEXT_YEAR} | Nöjesfabriken, Karlstad",
              "Karlstad Vin &amp; Deli", intro="Vinmässa med provning.",
              buttons=(("https://tickets.example/2", "Få 20% rabatt på biljetten"),)),
        block(f"{textual(D2)} | Scen", "Humorkväll", intro="En föreställning med mycket skratt."),
        block("Datum kommer | Löfbergs Arena, Karlstad", "Utan datum"),
    )
    events = {e["title"]: e for e in GreatEvent().normalize({"html": html})}
    assert set(events) == {"Stor konsert", "Karlstad Vin & Deli", "Humorkväll"}

    c = events["Stor konsert"]
    assert c["occasions"] == [{"date_start": D1.isoformat(), "date_end": D1.isoformat(), "time_start": None, "time_end": None}]
    assert c["place"]["title"] == "Löfbergs Arena" and c["municipality"] == "Karlstad"
    assert c["categories"][0]["title"] == "Musik"
    assert c["summary"] == "En arenaturné med nya låtar."                 # utan blanksteg före punkt
    assert c["description"] == "Mer om konserten."
    assert c["booking_link"] == "https://tickets.example/1"
    assert c["images"][0]["large"].endswith("/bild.jpg")
    assert c["url"] == greatevent.LIST_URL and c["source"] == "Great Event"

    vin = events["Karlstad Vin & Deli"]
    assert [(o["date_start"], o["date_end"]) for o in vin["occasions"]] == [(f"{NEXT_YEAR}-02-19", f"{NEXT_YEAR}-02-20")]
    assert vin["categories"][0]["title"] == "Mat och dryck"
    assert events["Karlstad Vin & Deli"]["booking_link"] == "https://tickets.example/2"
    assert events["Humorkväll"]["categories"][0]["title"] == "Teater och underhållning"
    assert events["Humorkväll"]["municipality"] == "Karlstad"                # bara plats angiven


def test_one_event_per_artist_and_date():
    d3 = D1 + timedelta(days=14)
    more = (f"<p><strong>Fredag {D1.day}/{D1.month}, Artist Ett</strong></p><p>Om artist ett.</p>"
            f"<p><strong>Tisdag {D2.day}/{D2.month}, Artist Två</strong></p><p>Om <em>artist två</em> .</p>"
            "<p><strong>🔥 Gör kvällen komplett med middag</strong></p><p>BBQ.</p>")
    line = f"{D1.day}/{D1.month}, {D2.day}/{D2.month}, {d3.day}/{d3.month} {d3.year} | Julins Backyard BBQ, Karlstad"
    events = GreatEvent().normalize({"html": page(block(line, "Backyard Live Music", intro="Intima spelningar.", more=more))})
    by_title = {e["title"]: e for e in events}
    assert set(by_title) == {"Backyard Live Music: Artist Ett", "Backyard Live Music: Artist Två", "Backyard Live Music"}
    one = by_title["Backyard Live Music: Artist Ett"]
    assert one["next"]["date_start"] == D1.isoformat() and one["summary"] == "Om artist ett."
    assert by_title["Backyard Live Music: Artist Två"]["summary"] == "Om artist två."
    assert [o["date_start"] for o in by_title["Backyard Live Music"]["occasions"]] == [d3.isoformat()]   # datum utan artist
    assert all(e["categories"][0]["title"] == "Musik" for e in events)


def test_page_without_events_is_an_error():
    assert greatevent.parse(page()) == []


def test_merges_with_ticketmaster_duplicate():
    tm = {"id": "tm-1", "source": "Ticketmaster", "title": "Benjamin Ingrosso – What Happens Next?", "summary": "",
          "description": "", "categories": [], "municipality": "Karlstad", "place": None, "organizer": None,
          "url": "https://www.ticketmaster.se/event/1", "booking_link": None, "website_link": None, "images": [],
          "occasions": [{"date_start": D1.isoformat(), "date_end": D1.isoformat(), "time_start": "19:00", "time_end": None}]}
    ge = GreatEvent().normalize({"html": page(block(f"Fre {textual(D1)} | Löfbergs Arena, Karlstad", "Benjamin Ingrosso"))})
    merged = merge([[tm], ge])
    assert len(merged) == 1 and [s["name"] for s in merged[0]["sources"]] == ["Ticketmaster", "Great Event"]
