"""Tests fuer die Vollstaendigkeitspruefung eines Laufs."""

import copy

import pytest

from design import generate_trials
from vollstaendigkeit import pruefen

META = {"n_per_cell": 20, "seed": 20260828, "n_gilt_je": "Stufe und Rahmung",
        "material": {"dateien": {"personas_generated.yaml": {"eingefroren": True},
                                 "items.yaml": {"eingefroren": True}}},
        "git": {"aenderungen_offen": False}}


@pytest.fixture
def lauf():
    return [{"cell_id": t.cell_id, "replicate": t.replicate, "sure_option": t.sure_option,
             "error": None, "raw_text": "A", "served_model": "m-1"}
            for t in generate_trials(META["n_per_cell"], seed=META["seed"])]


def test_vollstaendiger_lauf(lauf):
    assert pruefen(META, lauf) == []


def test_fehlender_durchlauf(lauf):
    assert any("fehlen" in b for b in pruefen(META, lauf[1:]))


def test_wiederholter_fehlversuch_ist_kein_befund(lauf):
    fehl = dict(lauf[0], error="overloaded", raw_text=None)
    assert pruefen(META, [fehl] + lauf) == []


def test_doppelte_antwort(lauf):
    assert any("mehrfach" in b for b in pruefen(META, lauf + [lauf[0]]))


def test_vertauschte_reihenfolge(lauf):
    lauf[0]["sure_option"] = "B" if lauf[0]["sure_option"] == "A" else "A"
    assert any("Optionsreihenfolge" in b for b in pruefen(META, lauf))


def test_nicht_eingefrorenes_material(lauf):
    meta = copy.deepcopy(META)
    meta["material"]["dateien"]["items.yaml"]["eingefroren"] = False
    assert any("nicht eingefroren" in b for b in pruefen(meta, lauf))


def test_wechselnde_modellversion(lauf):
    lauf[0]["served_model"] = "m-2"
    assert any("wechselte" in b for b in pruefen(META, lauf))


def test_antwort_ueber_laengengrenze_fehlt_nicht(lauf):
    lauf[0].update(raw_text=None, served_model=None,
                   error="BadRequestError: 400 - max_tokens or model output limit was reached")
    assert pruefen(META, lauf) == []
    assert pruefen.statistik["ueber_laengengrenze"] == 1
