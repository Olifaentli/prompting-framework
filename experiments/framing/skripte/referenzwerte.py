"""Fuehrt die beiden Referenzstudien im Standardformat des Frameworks zusammen.

Many Labs 1 (Asian Disease): zwei unabhaengige Gruppen. Der Standardfehler
folgt aus dem Newcombe-Intervall, das referenz_ml1.py berechnet hat.

Ruggeri et al. (2020) (Geldbetraege): Dieselben Personen beantworten beide
Rahmungen. Fuer gepaarte Anteile ist der Standardfehler der Differenz
sqrt((b + c) - (b - c)^2 / n) / n, mit b und c den diskordanten Paaren.
Option A ist dort die riskante Option; fuer den Anteil der sicheren Option
wird gespiegelt.

Aufruf: python experiments/framing/skripte/referenzwerte.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

HIER = Path(__file__).resolve().parent
EXPERIMENT = HIER.parent
sys.path.insert(0, str(EXPERIMENT.parent.parent / "src"))

from statutils import Z95  # noqa: E402

REF_ML1 = EXPERIMENT / "referenz" / "ml1_framing_reference.csv"
REF_RUG = EXPERIMENT / "referenz" / "ruggeri_contrasts.csv"
OUT = EXPERIMENT / "referenz" / "referenzwerte.csv"


def ml1() -> dict:
    r = pd.read_csv(REF_ML1)
    r = r[r["subset"] == "ML1_all"].iloc[0]
    return {
        "aufgabe": "asian_disease",
        "quelle": "Many Labs 1 (Klein et al., 2014)",
        "design": "zwei Gruppen",
        "n": int(r["n_total"]),
        "p_gain": float(r["p_sure_gain"]),
        "p_loss": float(r["p_sure_loss"]),
        "delta": float(r["framing_delta"]),
        "se": (float(r["framing_delta_ci_high"]) - float(r["framing_delta_ci_low"])) / (2 * Z95),
    }


def ruggeri() -> dict:
    rug = pd.read_csv(REF_RUG)
    r = rug[rug["contrast"] == "framing_outcomes"].iloc[0]
    n = int(r["n_pairs"])
    b, c = int(r["discordant_10"]), int(r["discordant_01"])
    p_gain = 1 - float(r["p_A_item1"])
    p_loss = 1 - float(r["p_A_item2"])
    return {
        "aufgabe": "monetary_endowment",
        "quelle": "Ruggeri et al. (2020)",
        "design": "gepaart",
        "n": n,
        "p_gain": p_gain,
        "p_loss": p_loss,
        "delta": p_gain - p_loss,
        "se": math.sqrt((b + c) - (b - c) ** 2 / n) / n,
    }


def main() -> None:
    tabelle = pd.DataFrame([ml1(), ruggeri()])
    tabelle.to_csv(OUT, index=False)
    print(tabelle.to_string(index=False))
    print(f"\nGeschrieben: {OUT}")


if __name__ == "__main__":
    main()
