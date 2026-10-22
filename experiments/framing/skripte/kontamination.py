"""Prueft, ob das Modell entscheidet oder sich erinnert.

Das Asian-Disease-Problem steht in jedem Lehrbuch der Entscheidungspsychologie.
Das Modell hat es im Training gesehen - samt der beruehmten Originalzahlen von
72 % und 22 %. Antwortet es "richtig", sind zwei Erklaerungen moeglich: Es
simuliert eine Entscheidung, oder es gibt Auswendiggelerntes wieder. Fuer die
Frage, ob sich das Verfahren auf neue Fragestellungen uebertragen laesst, macht
das den entscheidenden Unterschied.

Zwei Pruefungen, die beide ohne zusaetzliche Modelllaeufe auskommen:

  1. ORIGINAL ODER REPLIKATION
     Die Originalwerte (72/22) sind massenhaft zitiert, die Replikationswerte
     aus Many Labs 1 (62/34) kaum. Landet das Modell naeher am Original,
     spricht das fuer Erinnerung; landet es naeher an der Replikation oder
     dazwischen, ist Erinnerung die schlechtere Erklaerung.

  2. BEKANNTE GEGEN UNBEKANNTE AUFGABE
     Die monetaeren Aufgaben aus Ruggeri et al. (2020) sind weit weniger
     verbreitet als das Krankheitsszenario. Zeigt sich der Effekt dort
     ebenfalls, ist Erinnerung als Erklaerung deutlich schwaecher.

Keine der beiden Pruefungen beweist etwas. Beide liefern ein berichtbares
Signal, und beides gehoert in die Limitationen.

Aufruf: python experiments/framing/skripte/kontamination.py <lauf>.parsed.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Framework-Module liegen drei Ebenen hoeher unter src/.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import referenz
from statutils import newcombe_diff_ci


# Publizierte Originalwerte, Tversky & Kahneman (1981), Asian-Disease-Problem.
TK_GAIN, TK_LOSS = 0.72, 0.22


def framing(df: pd.DataFrame) -> dict | None:
    """Anteil der sicheren Option je Rahmung und deren Differenz."""
    g = df[df["frame"] == "gain"]
    l = df[df["frame"] == "loss"]
    if g.empty or l.empty:
        return None
    k_g, n_g = int(g["chose_sure"].sum()), len(g)
    k_l, n_l = int(l["chose_sure"].sum()), len(l)
    lo, hi = newcombe_diff_ci(k_g, n_g, k_l, n_l)
    return {
        "p_gain": k_g / n_g, "p_loss": k_l / n_l,
        "delta": k_g / n_g - k_l / n_l,
        "ci": (lo, hi), "n": n_g + n_l,
    }


def pruefung_original_oder_replikation(df: pd.DataFrame, ml1: dict) -> None:
    print("=" * 66)
    print("PRUEFUNG 1 — Original oder Replikation?")
    print("=" * 66)

    sub = df[(df["item"] == "asian_disease") & (df["spec_level"] == "S0")]
    if sub.empty:
        print("Keine Baseline-Daten fuer das Asian-Disease-Problem.\n")
        return
    m = framing(sub)

    tk_delta = TK_GAIN - TK_LOSS
    d_tk = abs(m["delta"] - tk_delta)
    d_ml = abs(m["delta"] - ml1["delta"])

    print(f"\nModell (Baseline S0, n = {m['n']}):")
    print(f"  p(sicher | Gewinn)  {m['p_gain']:.3f}")
    print(f"  p(sicher | Verlust) {m['p_loss']:.3f}")
    print(f"  Framing-Effekt      {m['delta']:.3f}  [{m['ci'][0]:.3f}, {m['ci'][1]:.3f}]")

    print(f"\n{'Vergleichswert':<34}{'Delta':>8}{'Abstand':>10}")
    print("-" * 52)
    print(f"{'Tversky & Kahneman 1981 (beruehmt)':<34}{tk_delta:>8.3f}{d_tk:>10.3f}")
    print(f"{'Many Labs 1 (kaum zitiert)':<34}{ml1['delta']:>8.3f}{d_ml:>10.3f}")

    print()
    if min(d_tk, d_ml) > 0.10:
        print("  Signal: keines. Das Modell liegt von beiden Werten mehr als 0.10 entfernt;")
        print("  die Pruefung kann dann nicht zwischen Erinnerung und Entscheidung trennen.")
    elif d_tk < d_ml:
        print("  Signal: naeher am ORIGINAL.")
        print("  Erinnerung an die publizierten Werte ist eine ernstzunehmende")
        print("  Erklaerung und muss in den Limitationen benannt werden.")
    elif d_ml < d_tk:
        print("  Signal: naeher an der REPLIKATION.")
        print("  Erinnerung an die beruehmten Originalzahlen erklaert das Ergebnis")
        print("  schlecht, da gerade die weniger verbreiteten Werte getroffen werden.")
    else:
        print("  Signal: uneindeutig, beide Abstaende gleich gross.")

    if m["delta"] > tk_delta:
        print("\n  Hinweis: Der Effekt faellt staerker aus als im Original. Eine")
        print("  Ueberzeichnung des bekannten Musters spricht ebenfalls eher fuer")
        print("  Reproduktion von Gelerntem als fuer eine Entscheidung.")
    print()


def pruefung_bekannt_gegen_unbekannt(df: pd.DataFrame, ml1: dict, rug_delta: float | None) -> None:
    print("=" * 66)
    print("PRUEFUNG 2 — Bekannte gegen weniger bekannte Aufgabe")
    print("=" * 66)

    zeilen = []
    for item, label, human in [
        ("asian_disease", "Asian Disease (sehr bekannt)", ml1["delta"]),
        ("monetary_endowment", "Geldbetraege (kaum bekannt)", rug_delta),
    ]:
        sub = df[(df["item"] == item) & (df["spec_level"] == "S0")]
        if sub.empty:
            continue
        m = framing(sub)
        if m is None:
            continue
        zeilen.append((label, m, human))

    if not zeilen:
        print("Keine auswertbaren Daten.\n")
        return

    print(f"\n{'Aufgabe':<30}{'Modell':>9}{'Mensch':>9}{'Abstand':>10}")
    print("-" * 58)
    for label, m, human in zeilen:
        if human is None:
            print(f"{label:<30}{m['delta']:>9.3f}{'—':>9}{'—':>10}")
        else:
            print(f"{label:<30}{m['delta']:>9.3f}{human:>9.3f}{m['delta'] - human:>+10.3f}")

    print()
    if len(zeilen) < 2:
        print("  Nur eine Aufgabe ausgewertet — fuer die Pruefung werden beide benoetigt.")
        print("  Lauf ohne --item ausfuehren, damit beide Aufgaben enthalten sind.")
    else:
        (_, m_bekannt, _), (_, m_unbekannt, _) = zeilen[0], zeilen[1]
        if m_unbekannt["ci"][0] > 0:
            print("  Signal: Der Effekt tritt auch bei der weniger bekannten Aufgabe auf.")
            print("  Erinnerung erklaert das Ergebnis schlecht, da hier kaum publizierte")
            print("  Werte zum Abrufen bereitstehen.")
        else:
            print("  Signal: Bei der weniger bekannten Aufgabe ist kein Effekt gesichert.")
            print("  Das ist mit Erinnerung an das beruehmte Szenario vereinbar und")
            print("  schwaecht die Uebertragbarkeit auf neue Fragestellungen.")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parsed_csv")
    args = ap.parse_args()

    df = pd.read_csv(Path(args.parsed_csv).resolve())
    print(f"\nKontaminationspruefung: {Path(args.parsed_csv).name} "
          f"({df['model_id'].iloc[0]})")
    df = df[df["choice"] != "invalid"].copy()
    df["chose_sure"] = df["chose_sure"].astype(int)

    # Beide Vergleichswerte aus der Referenztabelle des Experiments
    # (referenz/referenzwerte.csv, erzeugt von skripte/referenzwerte.py).
    ml1 = referenz.fuer_aufgabe("asian_disease")
    rug_delta = referenz.fuer_aufgabe("monetary_endowment")["delta"]

    print()
    pruefung_original_oder_replikation(df, ml1)
    pruefung_bekannt_gegen_unbekannt(df, ml1, rug_delta)

    print("=" * 66)
    print("Beide Pruefungen liefern Hinweise, keine Beweise. Sie gehoeren in die")
    print("Limitationen und begrenzen, wie weit sich das Verfahren auf neue")
    print("Fragestellungen uebertragen laesst.")
    print("=" * 66)


if __name__ == "__main__":
    main()
