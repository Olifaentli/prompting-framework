"""Bestimmt den noetigen Stichprobenumfang je Zelle.

Kriterium ist die Breite des Konfidenzintervalls, nicht ein Testverfahren.
Das passt zur Fragestellung: Gesucht ist die Distanz zwischen Modell und
Mensch, und die Guete dieser Aussage haengt daran, wie schmal ihr
Unsicherheitsbereich ist.

Die Rechnung beruecksichtigt beide Unsicherheitsquellen:
  - die Streuung der Modellantworten, die mit n sinkt
  - die Unsicherheit des menschlichen Referenzwerts, die fest ist

Letztere setzt eine Untergrenze: Auch bei unendlich vielen Modellaufrufen
bleibt das Intervall mindestens so breit wie die Referenz selbst.

Aufruf: python src/power.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment
import referenz
from design import load_config
from statutils import Z95, ci_halfwidth

COST_PER_MTOK_IN = 1.00     # Claude Haiku 4.5
TOKENS_PER_CALL = 130



def required_n(p_gain: float, p_loss: float, ref_se: float,
               target: float, cap: int = 50_000) -> int | None:
    """Kleinstes n je Zelle, bei dem die halbe Intervallbreite `target` erreicht."""
    for n in range(20, cap, 10):
        if ci_halfwidth(p_gain, p_loss, n, extra_var=ref_se ** 2) <= target:
            return n
    return None


def main() -> None:
    # Ausgewertet wird je Detailstufe und Rahmung, nicht je Formulierungsvariante.
    # Die Varianten teilen sich die Durchlaeufe einer Stufe und liefern die Streuung.
    items, personas = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--aufgabe", default=next(iter(items)),
                    help="Aufgabe, deren Referenz die Planung bestimmt (Standard: die erste)")
    args = ap.parse_args()
    n_stufen = len(personas["levels"])
    n_cells = n_stufen * 2

    r = referenz.fuer_aufgabe(args.aufgabe)
    p_gain, p_loss, ref_se = r["p_gain"], r["p_loss"], r["se"]

    print("=== Ausgangswerte ===")
    print(f"Aufgabe: {args.aufgabe}, Referenz: {r['quelle']}")
    print(f"Menschliche Referenz: Delta = {r['delta']:.3f}, "
          f"Standardfehler = {ref_se:.4f}")
    floor = Z95 * ref_se
    print(f"Untergrenze der Intervallbreite: +/-{floor:.3f}")
    print("Diese Grenze stammt allein aus der Unsicherheit der Referenzdaten und")
    print("laesst sich durch mehr Modellaufrufe nicht unterschreiten.\n")

    print("=== Benoetigte Durchlaeufe je Zelle ===")
    print(f"{'Zielgenauigkeit':<20}{'n je Zelle':>12}{'Aufrufe gesamt':>17}"
          f"{'Kosten':>10}{'mit Batch':>11}")
    print("-" * 70)

    rows = []
    for target in (0.10, 0.07, 0.05, 0.04, 0.03):
        n = required_n(p_gain, p_loss, ref_se, target)
        if n is None:
            print(f"{'+/-' + f'{target:.2f}':<20}{'nicht erreichbar':>12}")
            continue
        calls = n * n_cells
        cost = calls * TOKENS_PER_CALL / 1e6 * COST_PER_MTOK_IN
        print(f"{'+/-' + f'{target:.2f}':<20}{n:>12,}{calls:>17,}"
              f"{'$' + f'{cost:.2f}':>10}{'$' + f'{cost/2:.2f}':>11}")
        rows.append((target, n, calls, cost))

    print(f"\nAufrufe und Kosten gelten je Item und Modell, bei {n_cells} Auswertungs-")
    print(f"einheiten ({n_stufen} Detailstufen x 2 Rahmungen) und Claude Haiku 4.5.")

    grenze = experiment.auswertung("relevanzgrenze")
    n_rec = required_n(p_gain, p_loss, ref_se, 0.05)
    print(f"\n=== Empfehlung ===")
    if n_rec is None:
        print("Eine Genauigkeit von +/-0.05 ist nicht erreichbar: Schon die Unsicherheit")
        print(f"der menschlichen Referenz liegt bei +/-{floor:.3f}. Mehr Modellaufrufe helfen")
        print("hier nicht; die Tabelle oben zeigt, was erreichbar ist.")
    else:
        print(f"n = {n_rec} je Zelle. Damit ist die Distanz auf +/-0.05 genau bestimmt,")
        print(f"also deutlich schaerfer als die Relevanzgrenze von {grenze:.2f}.")
        print(f"Ein Modell und eine Aufgabe: {n_rec * n_cells:,} Aufrufe.")
        n_items = len(items)
        for mods in (1, 2):
            calls = n_rec * n_cells * n_items * mods
            cost = calls * TOKENS_PER_CALL / 1e6 * COST_PER_MTOK_IN
            print(f"  {n_items} Aufgabe(n), {mods} Modell(e): {calls:>7,} Aufrufe, "
                  f"${cost:.2f} bzw. ${cost/2:.2f} ueber die Batch-API")

    print("\n=== Was verschiedene Umfaenge leisten ===")
    print(f"{'n':>7}{'Intervall':>14}   Bewertung")
    print("-" * 56)
    for n in (100, 200, 400, 800, 1600):
        hw = ci_halfwidth(p_gain, p_loss, n, extra_var=ref_se ** 2)
        if hw > 0.10:
            note = "zu grob, sagt nichts aus"
        elif hw > 0.06:
            note = "grenzwertig"
        elif hw > 0.045:
            note = "brauchbar"
        else:
            note = "gut"
        print(f"{n:>7}{'+/-' + f'{hw:.3f}':>14}   {note}")


if __name__ == "__main__":
    main()
