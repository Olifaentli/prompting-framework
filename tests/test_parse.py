"""Tests fuer die Antwortextraktion.

Der Parser entscheidet, welche Modellantwort als Wahl zaehlt. Zu grosszuegiges
Parsen erfindet Daten, zu strenges verwirft gueltige Antworten. Beide Fehler
verzerren das Ergebnis, daher sind die Grenzfaelle hier festgeschrieben.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from parse import extract_letter


@pytest.mark.parametrize("text,erwartet", [
    ("A", "A"),
    ("B", "B"),
    ("a", "A"),
    (" A ", "A"),
    ("A.", "A"),
    ("A)", "A"),
    ("(B)", "B"),
    ("Program A", "A"),
    ("Option B", "B"),
    ("Answer: A", "A"),
    ("Choice: B", "B"),
])
def test_gueltige_antworten(text, erwartet):
    assert extract_letter(text) == erwartet


@pytest.mark.parametrize("text", [
    None,
    "",
    "   ",
    "I'm not able to choose.",
    "It depends on your risk preference.",
])
def test_ungueltige_antworten(text):
    assert extract_letter(text) is None


def test_beide_buchstaben_genannt_ist_ungueltig():
    """Nennt die Antwort beide Optionen, ist keine Wahl erkennbar.

    Diese Antworten als Wahl zu zaehlen waere eine Erfindung von Daten.
    """
    assert extract_letter("Either A or B could be justified.") is None
    assert extract_letter("A and B have the same expected value.") is None


def test_einzelner_buchstabe_im_fliesstext():
    """Kommt nur ein Buchstabe isoliert vor, gilt er als Wahl."""
    assert extract_letter("I would choose A in this case.") == "A"


def test_buchstabe_in_wort_zaehlt_nicht():
    """'a' als Artikel darf nicht als Wahl gelesen werden."""
    assert extract_letter("This is a difficult decision without more context.") is None


def test_grossschreibung_egal():
    assert extract_letter("program b") == "B"


@pytest.mark.parametrize("text,erwartet", [
    ("```A```", "A"),
    ("```\nB\n```", "B"),
    ("```text\nA\n```", "A"),
    ("`B`", "B"),
    ("**A**", "A"),
    ("*B*", "B"),
    ("``` A ```", "A"),
])
def test_formatierungsreste_werden_entfernt(text, erwartet):
    """Modelle verpacken kurze Antworten mitunter in Codeblock-Markierungen.

    Diese Reste sind kein Teil der Antwort. Wuerden sie eine gueltige Wahl
    unauswertbar machen, entstuenden kuenstliche Ausfaelle.
    """
    assert extract_letter(text) == erwartet


def _schreiben(tmp_path, saetze):
    import json
    pfad = tmp_path / "lauf.jsonl"
    with pfad.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_meta": {"model_id": "m"}}) + "\n")
        for s in saetze:
            fh.write(json.dumps(s) + "\n")
    return pfad


def _satz(rep, **extra):
    s = {"cell_id": "a|gain|S0|none", "item": "a", "frame": "gain", "spec_level": "S0",
         "variant": None, "replicate": rep, "sure_option": "A", "raw_text": "A", "error": None}
    s.update(extra)
    return s


def test_zu_lange_antwort_ist_nicht_auswertbar_kein_api_fehler(tmp_path):
    from parse import parse_file
    fehler = "BadRequestError: Error code: 400 - Could not finish the message because max_tokens or model output limit was reached."
    df, _ = parse_file(_schreiben(tmp_path, [_satz(0), _satz(1, raw_text=None, error=fehler)]))
    zeile = df[df["replicate"] == 1].iloc[0]
    assert zeile["choice"] == "invalid"
    assert zeile["error"] is None or zeile["error"] != zeile["error"]   # None oder NaN
    assert zeile["hinweis"] == "Ausgabe ueber der Laengengrenze"


def test_fortgesetzter_lauf_zaehlt_jeden_durchlauf_einmal(tmp_path):
    from parse import parse_file
    saetze = [_satz(0, raw_text=None, error="RateLimitError: 429"), _satz(0), _satz(1)]
    df, _ = parse_file(_schreiben(tmp_path, saetze))
    assert len(df) == 2
    assert (df["choice"] == "sure").all()
