"""Referenzkennzahlen aus der Prospect-Theory-Replikation von Ruggeri et al. (2020).

Quelle: OSF-Projekt esxc4, Analysis/data/preregistered_exclusions.
Publikation: Nature Human Behaviour, 4, 622-633. https://doi.org/10.1038/s41562-020-0886-x

Anders als Many Labs 1 ist dieser Datensatz *within-subject*: jede Person beantwortet
alle 17 Items in randomisierter Reihenfolge (Spalte Presentation_Order). Die Framing-
Kontraste sind daher gepaart und werden mit McNemar getestet.

Spalten 1-17 entsprechen den Items aus Kahneman & Tversky (1979), Econometrica.
Kodierung: 1 = Option A gewaehlt, 0 = Option B.

Ausgabe: referenz/ruggeri_contrasts.csv (im Experimentordner)
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "referenz" / "rohdaten" / "ruggeri" / "pt_replication_data.csv"
ORIG = ROOT / "referenz" / "rohdaten" / "ruggeri" / "original_study_values.xlsx"
OUT = ROOT / "referenz" / "ruggeri_contrasts.csv"

# Spalte -> Item-Bezeichnung in Kahneman & Tversky (1979).
COL_TO_KT = {
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "7", "6": "8",
    "7": "3'", "8": "4'", "9": "7'", "10": "8'", "11": "10",
    "12": "11", "13": "12", "14": "13", "15": "13'", "16": "14", "17": "14'",
}

# Theoretische Kontraste. Der Framing-Kontrast (11 vs. 12) ist der fuer diese
# Arbeit zentrale: identische Endzustaende, unterschiedlicher Referenzpunkt.
CONTRASTS = [
    ("framing_outcomes", "12", "13", "K&T 11 vs 12 — Framing identischer Endzustaende"),
    ("reflection_3", "3", "7", "K&T 3 vs 3' — Reflexionseffekt (hohe Wsk.)"),
    ("reflection_4", "4", "8", "K&T 4 vs 4' — Reflexionseffekt (niedrige Wsk.)"),
    ("reflection_7", "5", "9", "K&T 7 vs 7' — Reflexionseffekt"),
    ("reflection_8", "6", "10", "K&T 8 vs 8' — Reflexionseffekt"),
    ("reflection_13", "14", "15", "K&T 13 vs 13' — Reflexionseffekt"),
    ("reflection_14", "16", "17", "K&T 14 vs 14' — Reflexionseffekt"),
]


def cohens_g(p1: float, p2: float) -> float:
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def paired_contrast(df: pd.DataFrame, c1: str, c2: str) -> dict:
    sub = df[[c1, c2]].dropna()
    n = len(sub)
    a, b = sub[c1].astype(int), sub[c2].astype(int)
    p1, p2 = a.mean(), b.mean()

    # McNemar auf den diskordanten Paaren.
    n01 = int(((a == 0) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum())
    if n01 + n10 > 0:
        res = stats.binomtest(n10, n01 + n10, 0.5)
        p_val = res.pvalue
    else:
        p_val = float("nan")

    return {
        "n_pairs": n,
        "p_A_item1": round(p1, 4),
        "p_A_item2": round(p2, 4),
        "delta": round(p1 - p2, 4),
        "cohens_g": round(cohens_g(p1, p2), 4),
        "discordant_10": n10,
        "discordant_01": n01,
        "mcnemar_p": f"{p_val:.3e}",
    }


def main() -> None:
    if not CSV.exists():
        raise SystemExit(
            f"Datensatz fehlt: {CSV}\n"
            "Bitte von https://osf.io/download/tg54x/ nach referenz/rohdaten/ruggeri/ laden."
        )
    df = pd.read_csv(CSV)
    orig = pd.read_excel(ORIG).set_index(pd.read_excel(ORIG).columns[0])

    rows = []
    for name, c1, c2, desc in CONTRASTS:
        r = paired_contrast(df, c1, c2)
        # Originalwerte aus Kahneman & Tversky (1979) zum Vergleich.
        o1 = orig.loc[int(c1), "Reported Proportion A"]
        o2 = orig.loc[int(c2), "Reported Proportion A"]
        rows.append({
            "contrast": name,
            "description": desc,
            "kt_item_1": COL_TO_KT[c1],
            "kt_item_2": COL_TO_KT[c2],
            **r,
            "original_p_A_item1": o1,
            "original_p_A_item2": o2,
            "original_delta": round(o1 - o2, 4),
            "attenuation": round(r["delta"] / (o1 - o2), 3) if (o1 - o2) != 0 else None,
        })

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print(f"Geschrieben: {OUT.relative_to(ROOT)}")
    print(f"N Teilnehmende: {len(df)} | Laender: {df['Country'].nunique()} | Sprachen: {df['Language'].nunique()}\n")
    cols = ["contrast", "n_pairs", "p_A_item1", "p_A_item2", "delta",
            "original_delta", "attenuation", "cohens_g", "mcnemar_p"]
    print(out[cols].to_string(index=False))
    print("\nHinweis: 'attenuation' < 1 bedeutet abgeschwaechter Effekt gegenueber dem Original.")


if __name__ == "__main__":
    main()
