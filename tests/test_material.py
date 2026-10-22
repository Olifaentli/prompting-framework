"""Tests fuer das eingefrorene Material des Experiments.

Eingefroren sind drei Dinge: die Personenbeschreibungen, die
Aufgabentexte und der Zusammenbau des Prompts. Aendert sich eines davon, sind
Laeufe vorher und nachher nicht mehr vergleichbar. Diese Tests schlagen dann
an, statt dass die Aenderung erst in den Daten auffaellt.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import experiment
from design import active_variants, build_prompt, enumerate_cells, load_config


def test_pruefsummen_unveraendert():
    ordner = experiment.material()
    for zeile in (ordner / "eingefroren.sha256").read_text(encoding="utf-8").splitlines():
        soll, name = zeile.split()
        ist = hashlib.sha256((ordner / name).read_bytes()).hexdigest()
        assert ist == soll, f"{name} wurde nach dem Einfrieren veraendert"


def test_standard_ist_der_eingefrorene_satz(monkeypatch):
    monkeypatch.delenv("PERSONAS", raising=False)
    _, personas = load_config()
    assert experiment.personen_datei() == "personas_generated.yaml"
    assert active_variants(personas) == ("a", "b", "c", "d")


def test_zusammenbau_wortgleich(monkeypatch):
    """Der vollstaendige Prompt einer Zelle, Zeichen fuer Zeichen.

    Haelt fest, was das Modell tatsaechlich liest: Beschreibung, Aufgabe im
    Originalwortlaut, Optionen, Frage, Antwortanweisung - ohne zusaetzliche
    Rollenanweisung, die es nur auf S1 bis S3 gaebe.
    """
    monkeypatch.delenv("PERSONAS", raising=False)
    items, personas = load_config()
    zelle = next(c for c in enumerate_cells(items, personas)
                 if c.item == "asian_disease" and c.frame == "loss"
                 and c.spec_level == "S1" and c.variant == "b")
    erwartet = (
        "You are 39 and work as a marine biologist at a coastal research center.\n\n"
        "Imagine that the United States is preparing for the outbreak of an unusual "
        "disease, which is expected to kill 600 people. Two alternative programs to "
        "fight the disease have been proposed. Assume that the exact scientific "
        "estimate of the consequences of the program are as follows:\n\n"
        "A: If this program is adopted, there is 1/3 probability that no people will "
        "die and 2/3 probability that 600 people will die.\n"
        "B: If this program is adopted, 400 people will die.\n\n"
        "Which program would you choose?\n\n"
        "Answer with exactly one letter, either A or B, and nothing else."
    )
    assert build_prompt(items, personas, zelle, "B") == erwartet
