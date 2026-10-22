"""Erzeugt zwei Tabellen, die jeder Bericht ueber ein Experiment braucht.

Referenzwerte: die menschlichen Vergleichswerte je Aufgabe.
Versuchsplan: Stufen, Inhalt, Varianten und Durchlaeufe je Bedingung.

Beide Tabellen werden aus denselben Quellen berechnet, aus denen auch das
Experiment und die Auswertung schoepfen. Abtippen entfaellt, und die Zahlen
im Text koennen nicht von denen im Code abweichen.

Aufruf: python src/tabellen.py [--n <durchlaeufe je stufe und bedingung>]
Ohne --n gilt der geplante Umfang aus der experiment.yaml.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment
import referenz
from design import active_variants, generate_trials, load_config


def tabelle_referenz(items: dict) -> pd.DataFrame:
    rows = []
    for aufgabe in items:
        r = referenz.fuer_aufgabe(aufgabe)
        rows.append({
            "Aufgabe": aufgabe, "Quelle": r["quelle"], "Design": r["design"], "n": r["n"],
            "p_sicher_Gewinn": round(r["p_gain"], 3), "p_sicher_Verlust": round(r["p_loss"], 3),
            "Framing_Effekt": round(r["delta"], 3),
            "CI_unten": round(r["ci"][0], 3), "CI_oben": round(r["ci"][1], 3),
        })
    return pd.DataFrame(rows)


def tabelle_versuchsplan(items: dict, personas: dict, n: int) -> pd.DataFrame:
    trials = list(generate_trials(n))
    je = Counter((t.item, t.spec_level, t.frame) for t in trials)
    erste = next(iter(items))
    rows = []
    for stufe, spec in personas["levels"].items():
        varianten = len(active_variants(personas)) if spec["has_variants"] else 1
        woerter = ([len(t.split()) for t in spec["variants"].values()]
                   if spec["has_variants"] else [0])
        rows.append({
            "Stufe": stufe, "Inhalt": experiment.stufentext(stufe),
            "Woerter": f"{min(woerter)}-{max(woerter)}" if spec["has_variants"] else "0",
            "Varianten": varianten,
            "Durchlaeufe_Gewinn": je[(erste, stufe, "gain")],
            "Durchlaeufe_Verlust": je[(erste, stufe, "loss")],
        })
    plan = pd.DataFrame(rows)
    plan.attrs["aufrufe_je_aufgabe_und_modell"] = sum(v for (i, _, _), v in je.items() if i == erste)
    plan.attrs["aufrufe_je_modell"] = len(trials)
    return plan


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    args = ap.parse_args()

    items, personas = load_config()
    n = args.n or experiment.geplantes_n()
    if n is None:
        raise SystemExit("Kein Umfang: --n angeben oder versuchsplan.n in der experiment.yaml eintragen.")
    ziel = experiment.ergebnisse() / "tabellen"
    ziel.mkdir(parents=True, exist_ok=True)

    t2 = tabelle_referenz(items)
    t2.to_csv(ziel / "referenzwerte.csv", index=False)
    print("Referenzwerte aus den menschlichen Daten")
    print(t2.to_string(index=False), "\n")

    t3 = tabelle_versuchsplan(items, personas, n)
    t3.to_csv(ziel / "versuchsplan.csv", index=False)
    print(f"Versuchsplan je Aufgabe und Modell (geplant: n = {n} je Stufe und Bedingung)")
    print(t3.to_string(index=False))
    print(f"\nAufrufe je Aufgabe und Modell: {t3.attrs['aufrufe_je_aufgabe_und_modell']:,}")
    print(f"Aufrufe je Modell ({len(items)} Aufgabe(n)): {t3.attrs['aufrufe_je_modell']:,}")
    print(f"\nGeschrieben: {ziel}")


if __name__ == "__main__":
    main()
