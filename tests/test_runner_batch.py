"""Tests fuer die Stapelverarbeitung, ohne API-Zugriff.

Ein Fehler hier faellt sonst erst auf, wenn der Batch eingereicht und bezahlt
ist - oder gar nicht, wenn Antworten falschen Zellen zugeordnet werden.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from design import generate_trials
from runner_batch import CUSTOM_ID, _ergebnisse, je_zelle_eine, parse_key, trial_key


@pytest.fixture(scope="module")
def hauptlauf():
    return list(generate_trials(910))


def test_custom_id_erlaubt_und_eindeutig(hauptlauf):
    keys = [trial_key(t) for t in hauptlauf]
    assert len(keys) == 14_560
    assert len(set(keys)) == len(keys), "doppelte custom_id"
    for k in keys:
        assert CUSTOM_ID.fullmatch(k), k


def test_custom_id_hin_und_zurueck(hauptlauf):
    for t in hauptlauf:
        r = parse_key(trial_key(t))
        assert (r["item"], r["frame"], r["spec_level"], r["variant"], r["replicate"]) == \
               (t.item, t.frame, t.spec_level, t.variant, t.replicate)


def test_vorabpruefung_streut_ueber_zellen(hauptlauf):
    auswahl = je_zelle_eine(hauptlauf, 8)
    assert len(auswahl) == 8
    assert len({t.cell_id for t in auswahl}) == 8


def _ergebnis(key, typ):
    return SimpleNamespace(custom_id=key, result=SimpleNamespace(type=typ))


class _Client:
    """Ersatz fuer den API-Client: zwei Batches, der zweite reicht nach."""

    def __init__(self, batches):
        self._b = batches
        self.messages = SimpleNamespace(batches=self)

    def retrieve(self, bid):
        return SimpleNamespace(processing_status="ended")

    def results(self, bid):
        return iter(self._b[bid])


def test_nachgereichtes_ergebnis_gewinnt():
    client = _Client({
        "b1": [_ergebnis("k1", "succeeded"), _ergebnis("k2", "errored")],
        "b2": [_ergebnis("k2", "succeeded")],
    })
    alle = _ergebnisse(client, {"batch_ids": ["b1", "b2"]})
    assert alle["k1"].result.type == "succeeded"
    assert alle["k2"].result.type == "succeeded"


def test_erfolg_wird_nicht_ueberschrieben():
    client = _Client({
        "b1": [_ergebnis("k1", "succeeded")],
        "b2": [_ergebnis("k1", "expired")],
    })
    assert _ergebnisse(client, {"batch_ids": ["b1", "b2"]})["k1"].result.type == "succeeded"


def test_jeder_befehl_laedt_den_zugang():
    """Der Client entsteht nur in _client(), das vorher die .env liest.

    Frueher erzeugten status und fetch ihn direkt und fanden keinen Schluessel.
    """
    quelle = (Path(__file__).resolve().parent.parent / "src" / "runner_batch.py").read_text(encoding="utf-8")
    assert quelle.count("anthropic.Anthropic(") == 1
    rumpf = quelle.split("def _client():", 1)[1].split("\ndef ", 1)[0]
    assert "zugang.pruefen" in rumpf
