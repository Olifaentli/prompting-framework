"""Tests fuer die Kontaminationspruefung.

Geprueft wird die Rechenlogik, nicht die inhaltliche Deutung: Landet ein
kuenstlich erzeugtes Ergebnis naeher am Original oder naeher an der
Replikation, muss die Pruefung das korrekt zuordnen.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kontamination import TK_GAIN, TK_LOSS, framing


def mach_daten(p_gain: float, p_loss: float, n: int = 1000,
               item: str = "asian_disease") -> pd.DataFrame:
    """Erzeugt einen Datensatz mit exakt vorgegebenen Anteilen."""
    zeilen = []
    for frame, p in (("gain", p_gain), ("loss", p_loss)):
        k = round(p * n)
        for i in range(n):
            zeilen.append({"item": item, "frame": frame, "spec_level": "S0",
                           "chose_sure": 1 if i < k else 0})
    return pd.DataFrame(zeilen)


def test_framing_rechnet_die_differenz():
    m = framing(mach_daten(0.70, 0.30))
    assert m["p_gain"] == pytest.approx(0.70, abs=1e-6)
    assert m["p_loss"] == pytest.approx(0.30, abs=1e-6)
    assert m["delta"] == pytest.approx(0.40, abs=1e-6)
    assert m["n"] == 2000


def test_framing_ohne_eine_rahmung():
    """Fehlt eine Rahmung, gibt es keinen Effekt zu berechnen."""
    df = mach_daten(0.7, 0.3)
    assert framing(df[df["frame"] == "gain"]) is None


def test_intervall_umschliesst_die_differenz():
    m = framing(mach_daten(0.62, 0.34))
    assert m["ci"][0] < m["delta"] < m["ci"][1]


def test_originalwerte_werden_als_original_erkannt():
    """Ein Ergebnis exakt auf den Originalwerten liegt naeher am Original."""
    m = framing(mach_daten(TK_GAIN, TK_LOSS))
    tk_delta = TK_GAIN - TK_LOSS
    ml1_delta = 0.287
    assert abs(m["delta"] - tk_delta) < abs(m["delta"] - ml1_delta)


def test_replikationswerte_werden_als_replikation_erkannt():
    """Ein Ergebnis auf den Many-Labs-Werten liegt naeher an der Replikation."""
    m = framing(mach_daten(0.622, 0.335))
    tk_delta = TK_GAIN - TK_LOSS
    ml1_delta = 0.287
    assert abs(m["delta"] - ml1_delta) < abs(m["delta"] - tk_delta)


def test_kein_effekt_schliesst_null_ein():
    m = framing(mach_daten(0.5, 0.5))
    assert m["ci"][0] < 0 < m["ci"][1]


def test_weit_von_beiden_werten_gibt_kein_signal(capsys):
    """Liegt das Modell weit unter Original und Replikation, sagt Pruefung 1 nichts.

    Rechnerisch waere es dann immer 'naeher an der Replikation', weil diese
    kleiner ist - ein Scheinbefund. Ergaenzt nach dem Hauptlauf (Haiku: 0,048).
    """
    from kontamination import pruefung_original_oder_replikation
    df = mach_daten(0.99, 0.95).assign(item="asian_disease", spec_level="S0")
    pruefung_original_oder_replikation(df, {"delta": 0.287})
    ausgabe = capsys.readouterr().out
    assert "Signal: keines" in ausgabe
    assert "REPLIKATION" not in ausgabe
