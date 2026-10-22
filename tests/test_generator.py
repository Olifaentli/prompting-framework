"""Tests fuer die Pruefung der erzeugten Personenbeschreibungen.

Die Pruefung ist die operationale Fassung der Designbedingung: Die Stufen
duerfen sich nur in der Menge an Detail unterscheiden, nicht in einer
mitgelieferten Disposition. Die Faelle unten stammen aus dem ersten echten
Lauf, bei dem genau das durchgerutscht war.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from generate_personas import MockGenerator, STUFEN, pruefe


# Aus dem ersten Lauf (03.10.2026): Die Episode zeigt Nachtesten und Festhalten.
S3_MIT_SORGFALT = (
    "You are 60 and work as a marine biologist at a coastal research center in a city, "
    "living with your two children, who are both in their twenties. Your day includes "
    "checking water samples, entering observations, and meeting colleagues to discuss "
    "results. At home, you make breakfast for everyone when schedules overlap and tend a "
    "few pots of herbs on the windowsill. You hold a doctorate in marine biology and "
    "sometimes help university students learn laboratory methods. You speak with your "
    "sister most weekends and attend a monthly neighborhood book group. Yesterday, a "
    "sample showed an unexpected change in color, so you repeated the test and added the "
    "result to your team's shared record."
)

# Aus dem ersten Lauf: S1 mit Haushalt statt nur Alter und Beruf.
S1_MIT_HAUSHALT = ("You are 60 and work as a marine biologist, living with your two "
                   "children in their twenties.")


def test_sorgfalt_in_der_episode_wird_abgelehnt():
    fehler = pruefe(S3_MIT_SORGFALT, "S3")
    assert any(f.startswith("Hinweis auf Sorgfalt") for f in fehler), fehler


def test_s1_mit_haushalt_wird_abgelehnt():
    fehler = pruefe(S1_MIT_HAUSHALT, "S1")
    assert any(f.startswith("mehr als Alter und Beruf") for f in fehler), fehler


def test_s1_mit_alter_und_beruf_besteht():
    assert pruefe("You are 27 and work as a baker in a small-town bakery.", "S1") == []


def test_haushalt_ist_ab_s2_erlaubt():
    """Die S1-Sperre gilt nur fuer S1; ab S2 gehoert der Haushalt dazu."""
    text = ("You are 39 and work as a primary school teacher in a city. You live with "
            "your partner in an apartment and cycle to school each morning. In the "
            "evening you share dinner with your partner and sometimes talk with "
            "neighbors in the courtyard.")
    assert not any(f.startswith("mehr als Alter und Beruf") for f in pruefe(text, "S2"))


def test_wortgrenze_vermeidet_fehlalarme():
    """'test' darf nicht in 'contest', 'list' nicht in 'listen' anschlagen."""
    text = ("You are 39 and work as a primary school teacher in a city. You listen to "
            "the radio, and last week your class watched a singing contest in the hall.")
    assert not any(f.startswith("Hinweis auf Sorgfalt") for f in pruefe(text, "S2"))


def test_mock_generator_besteht_die_pruefung():
    """Der Mock muss die Kette durchlaufen, sonst ist sie ohne API nicht testbar."""
    gen = MockGenerator()
    for s3 in gen.personen(4):
        assert pruefe(s3, "S3") == []
        for stufe in ("S2", "S1"):
            assert pruefe(gen.kuerzen(s3, stufe), stufe) == [], stufe


def test_jede_stufe_hat_einen_zusatz_eintrag():
    """Der Kuerzungsauftrag setzt {zusatz} ein; fehlt der Eintrag, bricht er ab."""
    for stufe, spec in STUFEN.items():
        assert "zusatz" in spec, stufe
