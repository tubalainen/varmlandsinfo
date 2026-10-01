"""Bara kommuner i filtret Kommun, inte orter som Väse och Brunskog eller orter utanför området (#81)."""

from datetime import date, timedelta

import chat
from common import finalize
from kommuner import KOMMUNER, kommun, orter_i
from sources import ticketmaster
from sources.visitvarmland import normalize_event as vv_event

FUTURE = (date.today() + timedelta(days=20)).isoformat()


def test_kommun_from_names_places_and_postcodes():
    assert len(KOMMUNER) == 18 and {"Karlskoga", "Degerfors"} <= set(KOMMUNER)
    assert kommun("Karlstad") == "Karlstad" and kommun("karlstad") == "Karlstad"
    assert kommun("Karlstads kommun") == "Karlstad" and kommun("Hammarö kommun") == "Hammarö"
    assert kommun("Väse") == "Karlstad" and kommun("Brunskog") == "Arvika" and kommun("SKOGHALL") == "Hammarö"
    assert kommun("Kungsgatan 54, 681 31") == "Kristinehamn" and kommun("Görsjövägen, 68395") == "Hagfors"
    assert kommun("Visnums-Kil") == "Kristinehamn" and kommun("Stora Kil") == "Kil"   # inte kommunen Kil
    assert kommun("Stockholm") is None and kommun("Oslo", "0188") is None and kommun(None, "") is None
    assert kommun("Kilsbacken") is None and kommun("Edane") == "Arvika"                 # hela ord, inte Kil eller Eda
    assert kommun("Stockholm", "Torget 1, 69131") == "Karlskoga"                        # första texten som ger en
    assert kommun("660 57") is None                                                     # delat prefix: orten avgör
    assert orter_i("Vad händer i Skoghall och Väse?") == {"skoghall": "Hammarö", "väse": "Karlstad"}


def event(**kw):
    e = {"id": "x", "source": "Test", "title": "Konsert", "summary": "", "description": "", "categories": [],
         "municipality": None, "place": None, "organizer": None, "url": None, "images": [],
         "booking_link": None, "website_link": None,
         "occasions": [{"date_start": FUTURE, "date_end": FUTURE, "time_start": None, "time_end": None}]}
    e.update(kw)
    return e


def test_finalize_sets_only_municipalities():
    assert finalize(event(municipality="Väse"))["municipality"] == "Karlstad"
    assert finalize(event(municipality="Stockholm"))["municipality"] is None
    assert finalize(event(place={"title": "Christinateatern", "address": "Kungsgatan 54, 681 31"}))[
        "municipality"] == "Kristinehamn"
    assert finalize(event(municipality="Sunne", place={"title": "X", "address": "652 25"}))["municipality"] == "Sunne"


def venue(city, postcode):
    return {"_embedded": {"venues": [{"name": "Bygdegården", "postalCode": postcode, "city": {"name": city}}]},
            "dates": {"start": {"localDate": FUTURE, "localTime": "19:00:00"}}, "id": "Z9", "name": "Dans"}


def test_ticketmaster_gives_municipalities_not_places():
    assert ticketmaster.normalize_event(venue("Väse", "66057"))["municipality"] == "Karlstad"
    assert ticketmaster.normalize_event(venue("Brunskog", "67194"))["municipality"] == "Arvika"
    # Okänd by med värmländskt postnummer: med, men utan kommun när prefixet delas av flera kommuner
    unknown = ticketmaster.normalize_event(venue("Okändby", "68092"))
    assert unknown is not None and unknown["municipality"] is None
    assert ticketmaster.normalize_event(venue("Stockholm", "11122")) is None


def test_visitvarmland_uses_the_place_before_the_organizers_city():
    municipalities = {9: "Karlstad", 11: "Kristinehamn"}
    base = {"id": 1, "title": "Matmilen Kristinehamn", "slug": "matmilen",
            "occasions": [{"date_start": FUTURE}], "categories": [{"title": "Mat och dryck"}]}
    matmilen = vv_event({**base, "organizers": [{"title": "Matmilen AB", "city": "Stockholm"}],
                         "places": [{"title": "Kristinehamns centrum",
                                     "address": {"street_1": "Kungsgatan", "zip_code": "681 31", "city": ""}}]},
                        municipalities)
    assert matmilen["municipality"] == "Kristinehamn"
    abroad = vv_event({**base, "organizers": [{"title": "X", "city": "Stockholm"}], "places": []}, municipalities)
    assert abroad["municipality"] is None
    by_id = vv_event({**base, "organizers": [{"title": "X", "municipality_id": 9, "city": "Stockholm"}]},
                     municipalities)
    assert by_id["municipality"] == "Karlstad"
    # Platsen går före arrangörens kommun: Karlstads Riksteaterförening arrangerar i Skoghall (#95)
    skoghall = vv_event({**base, "title": "Rent Hus",
                         "organizers": [{"title": "Karlstads riksteaterförening", "municipality_id": 9, "city": "Karlstad"}],
                         "places": [{"title": "Skoghall Folkets hus",
                                     "address": {"street_1": "Skogåsvägen 3", "zip_code": "66330", "city": ""}}]},
                        municipalities)
    assert skoghall["municipality"] == "Hammarö"


def test_chat_understands_places():
    assert chat.find_municipalities("Vad händer i Skoghall i helgen?", ["Hammarö", "Karlstad"]) == {"Hammarö"}
    assert chat.find_municipalities("Vad händer i Väse?", ["Hammarö"]) == set()          # kommunen saknas i appen
    events = [finalize(event(title="Säg det med ett leende", municipality="Hammarö",
                             place={"title": "Skoghalls Folkets hus", "address": "663 30"}))]
    today = date.today()
    assert chat.scope_check("Vad händer i Skoghall?", events, today)["ok"]
    _, sources = chat.search_answer("Vad händer i Skoghall?", events, today)
    assert [s["title"] for s in sources] == ["Säg det med ett leende"]
