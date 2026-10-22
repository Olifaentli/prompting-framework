"""Vergleicht zwei Modelle auf demselben Versuchsplan.

Je Aufgabe und Detailstufe stehen der Framing-Effekt beider Modelle
nebeneinander und ihre Differenz mit Konfidenzintervall. Dasselbe Werkzeug wie
in analyze.py: Die Differenz zweier unabhaengiger Framing-Effekte bekommt den
Standardfehler sqrt(se_1^2 + se_2^2), so wie der Abstand zum Menschen.

Aufruf: python src/compare.py <lauf_a>.parsed.csv <lauf_b>.parsed.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment
import referenz
from analyze import RELEVANZGRENZE, je_stufe
from design import load_config, stufen
from statutils import Z95

ROOT = Path(__file__).resolve().parent.parent


def laden(pfad: Path) -> tuple[str, pd.DataFrame]:
    roh = pd.read_csv(pfad)
    df = roh[roh["choice"] != "invalid"].copy()
    df["chose_sure"] = df["chose_sure"].astype(int)
    return str(roh["model_id"].iloc[0]), df


def vergleichen(a: pd.DataFrame, b: pd.DataFrame, ref: dict,
                ordnung: list[str] | None = None) -> pd.DataFrame:
    sa = je_stufe(a, ref["delta"], ref["se"]).set_index("Stufe")
    sb = je_stufe(b, ref["delta"], ref["se"]).set_index("Stufe")
    rows = []
    gemeinsam = set(sa.index) & set(sb.index)
    for stufe in [x for x in (ordnung or sorted(gemeinsam)) if x in gemeinsam]:
        d = sa.loc[stufe, "Delta"] - sb.loc[stufe, "Delta"]
        se = (sa.loc[stufe, "Delta_se"] ** 2 + sb.loc[stufe, "Delta_se"] ** 2) ** 0.5
        rows.append({
            "Stufe": stufe,
            "Delta_A": sa.loc[stufe, "Delta"], "Delta_B": sb.loc[stufe, "Delta"],
            "Abstand_A": sa.loc[stufe, "Abstand"], "Abstand_B": sb.loc[stufe, "Abstand"],
            "Differenz": d, "Differenz_lo": d - Z95 * se, "Differenz_hi": d + Z95 * se,
        })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lauf_a")
    ap.add_argument("lauf_b")
    ap.add_argument("--ziel", default=None)
    args = ap.parse_args()

    pa, pb = Path(args.lauf_a).resolve(), Path(args.lauf_b).resolve()
    name_a, a = laden(pa)
    name_b, b = laden(pb)
    items, personas = load_config()
    ziel = Path(args.ziel).resolve() if args.ziel else experiment.ergebnisse() / "vergleich"
    ziel.mkdir(parents=True, exist_ok=True)

    print(f"A = {name_a}\nB = {name_b}\n")
    for aufgabe in items:
        if aufgabe not in set(a["item"]) or aufgabe not in set(b["item"]):
            continue
        ref = referenz.fuer_aufgabe(aufgabe)
        v = vergleichen(a[a["item"] == aufgabe], b[b["item"] == aufgabe], ref, stufen(personas))
        print(f"=== {aufgabe} (Mensch: {ref['delta']:.3f}) ===")
        print(f"{'Stufe':<7}{'Delta A':>9}{'Delta B':>9}{'A - B':>9}{'95%-Intervall':>20}")
        print("-" * 54)
        for _, r in v.iterrows():
            iv = f"[{r['Differenz_lo']:.3f}, {r['Differenz_hi']:.3f}]"
            print(f"{r['Stufe']:<7}{r['Delta_A']:>9.3f}{r['Delta_B']:>9.3f}"
                  f"{r['Differenz']:>+9.3f}{iv:>20}")
        klein = ((v["Differenz_lo"] > -RELEVANZGRENZE) & (v["Differenz_hi"] < RELEVANZGRENZE))
        print(f"Unterschied auf allen Stufen innerhalb +/-{RELEVANZGRENZE:.2f}: "
              f"{'ja' if klein.all() else 'nein'}\n")
        v.assign(Aufgabe=aufgabe, Modell_A=name_a, Modell_B=name_b).to_csv(
            ziel / f"vergleich_{aufgabe}.csv", index=False)
    print(f"Tabellen: {ziel.relative_to(ROOT) if ziel.is_relative_to(ROOT) else ziel}")


if __name__ == "__main__":
    main()
