"""Menschliche Vergleichswerte je Aufgabe.

Das Framework erwartet sie in einem einheitlichen Format, gleich aus welcher
Studie sie stammen: eine Zeile je Aufgabe mit Anteil der Zieloption unter
beiden Bedingungen, deren Differenz und dem Standardfehler der Differenz.

    aufgabe, quelle, design, n, p_gain, p_loss, delta, se

Wie diese Werte aus den Rohdaten einer Studie entstehen, ist Sache des
Experiments (experiments/<name>/skripte/). Wo die Datei liegt, steht in der
experiment.yaml.
"""

from __future__ import annotations

import pandas as pd

import experiment
from statutils import Z95

SPALTEN = ("aufgabe", "quelle", "design", "n", "p_gain", "p_loss", "delta", "se")


def alle() -> pd.DataFrame:
    tabelle = pd.read_csv(experiment.referenzwerte())
    fehlend = [s for s in SPALTEN if s not in tabelle.columns]
    if fehlend:
        raise SystemExit(f"Referenzwerte unvollstaendig, es fehlen: {', '.join(fehlend)}")
    return tabelle


def fuer_aufgabe(aufgabe: str) -> dict:
    """Die Referenz einer Aufgabe, ergaenzt um das 95-%-Intervall von delta."""
    tabelle = alle()
    zeile = tabelle[tabelle["aufgabe"] == aufgabe]
    if zeile.empty:
        raise SystemExit(f"Keine Referenzwerte fuer Aufgabe '{aufgabe}'.")
    ref = zeile.iloc[0].to_dict()
    ref["n"] = int(ref["n"])
    ref["ci"] = (ref["delta"] - Z95 * ref["se"], ref["delta"] + Z95 * ref["se"])
    return ref
