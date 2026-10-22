"""Berechnet die menschlichen Referenzkennzahlen zum Gewinn/Verlust-Framing.

Quelle: Many Labs 1 (Klein et al., 2014), OSF-Projekt wx7ck, Komponente "Data".
Lizenz der Daten: CC0.

Relevante Variablen (laut Data/Codebook.xlsx):
    gainlossgroup    0 = "People will die" (Verlustrahmung)
                     1 = "People will be saved" (Gewinnrahmung)
    gainlossDV       1 = sichere Option ("chose program with exact outcome")
                     2 = riskante Option ("chose program with probability outcome")
    diseaseforder    Anzeigeposition des Experiments innerhalb der Session

Ausgabe: referenz/ml1_framing_reference.csv (im Experimentordner)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat
from scipy import stats

# Framework-Module (statutils) liegen drei Ebenen hoeher unter src/.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from statutils import newcombe_diff_ci, wilson_ci

ROOT = Path(__file__).resolve().parent.parent
SAV = ROOT / "referenz" / "rohdaten" / "ml1" / "Data" / "CleanedDataset.sav"
OUT = ROOT / "referenz" / "ml1_framing_reference.csv"

COLS = ["gainlossgroup", "gainlossDV", "diseaseforder", "referrer", "sample"]

# Publizierte Originalwerte aus Tversky & Kahneman (1981), Asian-Disease-Problem.
TK1981 = {"gain_p_sure": 0.72, "loss_p_sure": 0.22, "n_gain": 152, "n_loss": 155}


def load() -> pd.DataFrame:
    if not SAV.exists():
        raise SystemExit(
            f"Datensatz fehlt: {SAV}\n"
            "Bitte ML1_Datasets.zip von https://osf.io/download/nqg97/ nach "
            "referenz/rohdaten/ml1/ laden und Data/CleanedDataset.sav entpacken."
        )
    df, _ = pyreadstat.read_sav(str(SAV), usecols=COLS)
    # Nur Faelle mit gueltiger Bedingung und gueltiger Antwort.
    df = df.dropna(subset=["gainlossgroup", "gainlossDV"]).copy()
    df["frame"] = df["gainlossgroup"].map({1.0: "gain", 0.0: "loss"})
    df["chose_sure"] = (df["gainlossDV"] == 1.0).astype(int)
    return df


def summarise(df: pd.DataFrame, label: str) -> dict:
    g = df[df["frame"] == "gain"]
    l = df[df["frame"] == "loss"]
    k_g, n_g = int(g["chose_sure"].sum()), len(g)
    k_l, n_l = int(l["chose_sure"].sum()), len(l)
    p_g, p_l = k_g / n_g, k_l / n_l

    lo, hi = newcombe_diff_ci(k_g, n_g, k_l, n_l)
    g_lo, g_hi = wilson_ci(k_g, n_g)
    l_lo, l_hi = wilson_ci(k_l, n_l)

    return {
        "subset": label,
        "n_total": n_g + n_l,
        "n_gain": n_g,
        "n_loss": n_l,
        "p_sure_gain": round(p_g, 4),
        "p_sure_gain_ci_low": round(g_lo, 4),
        "p_sure_gain_ci_high": round(g_hi, 4),
        "p_sure_loss": round(p_l, 4),
        "p_sure_loss_ci_low": round(l_lo, 4),
        "p_sure_loss_ci_high": round(l_hi, 4),
        "framing_delta": round(p_g - p_l, 4),
        "framing_delta_ci_low": round(lo, 4),
        "framing_delta_ci_high": round(hi, 4),
    }


def main() -> None:
    df = load()
    rows = [summarise(df, "ML1_all")]

    # Robustheit: getrennt nach Erhebungsmodus (Labor vs. online).
    if "referrer" in df.columns:
        for ref, sub in df.groupby("referrer"):
            if len(sub) >= 200 and sub["frame"].nunique() == 2:
                rows.append(summarise(sub, f"ML1_referrer_{str(ref).strip()}"))

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    main_row = rows[0]
    tk_delta = TK1981["gain_p_sure"] - TK1981["loss_p_sure"]

    print(f"Geschrieben: {OUT.relative_to(ROOT)}  ({len(out)} Zeilen)\n")
    print("=== Many Labs 1 — Gewinn/Verlust-Framing (Asian Disease) ===")
    print(f"  N gesamt              {main_row['n_total']}")
    print(
        f"  p(sicher | Gewinn)    {main_row['p_sure_gain']:.3f}  "
        f"[{main_row['p_sure_gain_ci_low']:.3f}, {main_row['p_sure_gain_ci_high']:.3f}]  n={main_row['n_gain']}"
    )
    print(
        f"  p(sicher | Verlust)   {main_row['p_sure_loss']:.3f}  "
        f"[{main_row['p_sure_loss_ci_low']:.3f}, {main_row['p_sure_loss_ci_high']:.3f}]  n={main_row['n_loss']}"
    )
    print(
        f"  Framing-Delta         {main_row['framing_delta']:.3f}  "
        f"[{main_row['framing_delta_ci_low']:.3f}, {main_row['framing_delta_ci_high']:.3f}]"
    )
    print("\n=== Vergleich Tversky & Kahneman (1981) ===")
    print(f"  Original-Delta        {tk_delta:.3f}")
    print(f"  ML1-Delta             {main_row['framing_delta']:.3f}")
    print(f"  Verhaeltnis           {main_row['framing_delta'] / tk_delta:.2f}x des Originaleffekts")


if __name__ == "__main__":
    main()
