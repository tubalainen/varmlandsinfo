from datetime import date, timedelta

from merge import merge
from sources import ccc, scala

D1 = date.today() + timedelta(days=20)
D2 = D1 + timedelta(days=1)


def ccc_card(tag, dates, time, heading, img_alt="Alt-titel", booking="https://www.ticketmaster.se/event/1"):
    return f'''
  <div class="card-item bg-primary js-filter-item" data-tags="{tag}">
    <div class="image-wrapper"><img src="/assets/images/kalendarium/x-850px.jpg" alt="{img_alt}"></div>
    <div class="card-body badge-wrapper p-2">
      <div class="badge">
        <p class="pb-0"><i class="fas fa-calendar-alt"></i> {dates}</p>
        <p class="pb-0"><i class="fas fa-clock"></i> {time}</p>
      </div>
      {heading}
      <p>Kort   beskrivning &amp; mer.</p>
    </div>
    <div class="card-footer">
      <a href="{booking}" target="_blank" class="btn">Boka biljett &amp; mat</a>
      <a href="/17/180/x/" class="arrow-link">Läs mer</a>
    </div>
  </div>'''


def test_ccc_parse_variants():
    page = "<html>" + ccc_card("konsert", D1.isoformat(), "19:30", '<h3 class="small-title">Konsert A</h3>') \
        + ccc_card("show", f"{D1} &amp; {D2}", "18.00-01.00", '<h3 class="small-title">Show B</h3>') \
        + ccc_card("konsert", D1.isoformat(), "16:00", '<h3 class="small-title">Trasig rubrik</p>') \
        + ccc_card("ovrigt", D1.isoformat(), "", "", img_alt="Från alt-texten") + "</html>"
    events = ccc.CCC().normalize({"html": page})
    by_title = {e["title"]: e for e in events}
    assert set(by_title) == {"Konsert A", "Show B", "Trasig rubrik", "Från alt-texten"}
    a = by_title["Konsert A"]
    assert a["next"]["time_start"] == "19:30"
    assert a["categories"][0]["title"] == "Musik"
    assert a["summary"] == "Kort beskrivning & mer."
    assert a["url"] == "https://www.karlstadccc.se/17/180/x/"
    assert a["booking_link"] == "https://www.ticketmaster.se/event/1"
    assert a["images"][0]["large"] == "https://www.karlstadccc.se/assets/images/kalendarium/x-850px.jpg"
    b = by_title["Show B"]
    assert [o["date_start"] for o in b["occasions"]] == [D1.isoformat(), D2.isoformat()]
    assert (b["next"]["time_start"], b["next"]["time_end"]) == ("18:00", "01:00")
    assert by_title["Från alt-texten"]["next"]["time_start"] is None


def scala_item(day, month, time, stage, genre, title, slug, extra=""):
    return f'''
<div class="post-list--item d-flex">
  <div class="col date"><div>
    <span class="day text-uppercase">
      {day}   </span>
    <span class="month text-uppercase">
      {month}   </span>
  </div></div>
  <figure class="thumbnail"><img width="160" height="160" src="/wp-content/uploads/2026/09/{slug}-160x160.png" alt=""></figure>
  <div class="col content"><div>
    <a href="https://www.scalateatern.se/forestallning/{slug}/">
      <div class="meta">
        <span class="d-inline-block">
          {time}    </span>
        <span class="d-inline-block text-uppercase term">
          {stage}    </span>
        <span class="d-inline-block text-uppercase term">
          {genre}    </span>
      </div>
      <div class="title d-block"><span>{title}</span></div>
    </a>
  </div></div>
  <div class="col actions">
    <a href="https://www.scalateatern.se/forestallning/{slug}/" class="btn read-more">Läs mer</a>
    {extra}
  </div>
</div>'''


MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def test_scala_parse_groups_and_year_rollover(monkeypatch):
    monkeypatch.setattr(scala, "today", lambda: date(2026, 11, 20))
    page = "<div class='post-list'>" \
        + scala_item(26, "nov", "14:00", "Stora scen", "Teater", "BRITT-MARIE", "britt-marie",
                     '<a href="https://biljett.scalateatern.se/sv/buyingflow/tickets/1/2/" class="btn">Köp</a>') \
        + scala_item(27, "nov", "14:00", "Stora scen", "Teater", "BRITT-MARIE", "britt-marie") \
        + scala_item(30, "dec", "20:30", "Källaren", "Musik, Humor", "Nyårsjazz", "nyarsjazz",
                     '<span class="badge bg-x">\n  Slutsåld  </span>') \
        + scala_item(3, "jan", "19.00", "Foajén", "Stand up", "Januarikomik", "komik") \
        + "</div><a class='load-more' href='/forestallningar/page/2/'>Fler</a><footer>x</footer>"
    events = {e["title"]: e for e in scala.Scala().normalize({"pages": [page]})}
    assert len(events) == 3
    bm = events["BRITT-MARIE"]
    assert [o["date_start"] for o in bm["occasions"]] == ["2026-11-26", "2026-11-27"]
    assert bm["booking_link"] == "https://biljett.scalateatern.se/sv/buyingflow/tickets/1/2/"
    assert bm["place"]["title"] == "Scalateatern, Stora scen"
    assert bm["images"][0]["small"].endswith("britt-marie-160x160.png")
    assert bm["images"][0]["large"].endswith("britt-marie.png")
    jazz = events["Nyårsjazz"]
    assert [c["title"] for c in jazz["categories"]] == ["Musik", "Teater och underhållning"]
    assert "Slutsåld" in jazz["summary"]
    komik = events["Januarikomik"]
    assert komik["next"]["date_start"] == "2027-01-03"     # årsskifte
    assert komik["next"]["time_start"] == "19:00"


def test_ccc_merges_with_visit_varmland_duplicate():
    page = ccc_card("konsert", D1.isoformat(), "19:30", '<h3 class="small-title">Bowie in Berlin</h3>')
    c = ccc.CCC().normalize({"html": page})
    vv = dict(c[0], id="vv-1", source="Visit Värmland", url="https://visitvarmland.com/x",
              sources=[{"name": "Visit Värmland", "url": "https://visitvarmland.com/x"}], booking_link=None)
    merged = merge([[vv], [c[0]]])
    assert len(merged) == 1
    assert [s["name"] for s in merged[0]["sources"]] == ["Visit Värmland", "Karlstad CCC"]
    assert merged[0]["booking_link"] == "https://www.ticketmaster.se/event/1"


def test_scala_free_entry_badge(monkeypatch):
    monkeypatch.setattr(scala, "today", lambda: date(2026, 11, 20))
    page = scala_item(26, "nov", "20:00", "Källaren", "Musik", "Jam", "jam", '<span class="badge x">Fri entré</span>')
    e = scala.Scala().normalize({"pages": [page]})[0]
    assert [c["title"] for c in e["categories"]] == ["Musik", "Gratis"]
