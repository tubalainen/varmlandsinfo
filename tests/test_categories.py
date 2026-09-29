"""Kategorierna efter finalize: källornas namn, ordregler och Övrigt (#53)."""

from datetime import date, timedelta

import chat
from common import category, finalize

DAY = (date.today() + timedelta(days=3)).isoformat()


def titles(title, cats, summary=""):
    event = finalize({"id": "x", "source": "Visit Värmland", "title": title, "summary": summary,
                      "categories": [category(c) for c in cats],
                      "occasions": [{"date_start": DAY, "date_end": DAY}]})
    return [c["title"] for c in event["categories"]]


def test_vague_source_categories_become_other():
    assert titles("Öppet hus", ["Evenemang"]) == ["Övrigt"]
    assert titles("Öppet hus", ["Evenemang", "Övriga evenemang"]) == ["Övrigt"]
    assert titles("Inspirationsdag", ["Övriga evenemang", "Gratis"]) == ["Övrigt", "Gratis"]
    assert titles("Anhörigdagen", ["Gratis"]) == ["Övrigt", "Gratis"]     # Gratis är ingen typ


def test_other_only_when_nothing_else_fits():
    assert titles("Familjesöndag: Lego", ["Evenemang", "Barn"]) == ["Barn"]
    assert titles("Konstutställning", ["Övriga evenemang", "Utställning"]) == ["Utställning"]


def test_motor_is_renamed():
    assert titles("Lunnedets Motorträff", ["Evenemang", "Motor"]) == ["Motorträffar"]
    assert titles("MC-Café", ["Övriga evenemang", "Motor"]) == ["Motorträffar", "Träffar och caféer"]
    assert titles("Folkrace", ["Motor"]) == ["Motorsport"]


def test_keyword_categories():
    assert titles("Bio Kontrast: Swear", ["Övriga evenemang"]) == ["Film"]
    assert titles("Filmkväll med Skimra Filmklubb", ["Övriga evenemang"]) == ["Film"]
    assert titles("Bingo på Rämmens Bygdegård", ["Evenemang"]) == ["Spel och quiz"]
    assert titles("Korsordscafé", ["Övriga evenemang"]) == ["Spel och quiz", "Träffar och caféer"]
    assert titles("Handarbetscafé", ["Övriga evenemang"]) == ["Träffar och caféer"]
    assert titles("Bokcirkel Forshaga bibliotek", ["Övriga evenemang"]) == ["Böcker och litteratur"]
    assert titles("Babybokprat", ["Övriga evenemang", "Barn"]) == ["Barn", "Böcker och litteratur"]
    assert titles("Gospelfestival i Fagerås", ["Evenemang"]) == ["Musik"]
    assert titles("Sånger i adventstid", ["Övriga evenemang"]) == ["Musik"]


def test_keyword_rules_do_not_overreach():
    assert titles("Tipspromenad: Djur i sånger", ["Sport, motion och hälsa"]) == \
        ["Sport, motion och hälsa", "Spel och quiz"]                             # inte Musik
    assert titles("Brott och vardag i domböckernas värld", ["Föreläsning och workshop"]) == ["Föreläsning och workshop"]
    assert titles("Boka bord", ["Mat och dryck"]) == ["Mat och dryck"]
    assert titles("IQF Värmland Iris restaurang & cafe", ["Loppis"]) == ["Loppis"]     # namnet på en loppis
    # Ingressen räknas bara när källan inte angett någon egen typ
    assert titles("Lunchkonsert", ["Musik"], "Fika finns att köpa") == ["Musik"]
    assert titles("Äntligen onsdag!", ["Evenemang"], "Författaren berättar om sin skrivresa") == ["Böcker och litteratur"]


def test_chat_understands_new_categories():
    assert chat.find_categories("Går det någon bra film på bio i helgen?") == {"Film"}
    assert chat.find_categories("Finns det något bingo nära Karlstad?") == {"Spel och quiz"}
    assert chat.find_categories("Var finns det språkcafé?") == {"Träffar och caféer"}
    assert chat.find_categories("Något författarbesök i oktober?") == {"Böcker och litteratur"}
    assert chat.find_categories("Kan jag boka biljetter?") == set()


def test_bandy_keyword_rule():
    assert titles("Bandy: IF Boltic - Djurgården", ["Sport, motion och hälsa"]) == ["Sport, motion och hälsa", "Bandy"]
    assert titles("Bandymatch på Tingvalla", ["Evenemang"]) == ["Bandy"]
    assert titles("Innebandy: Damer", ["Sport, motion och hälsa"]) == ["Sport, motion och hälsa"]
    assert titles("Allmänhetens åkning på bandyplanen", ["Sport, motion och hälsa"]) == ["Sport, motion och hälsa"]
