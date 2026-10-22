"""Ueberfuehrt die Rohprotokolle in eine ausgewertete Tabelle.

Getrennt vom Runner, damit Parsing-Entscheidungen jederzeit revidiert und auf
die unveraenderten Rohdaten neu angewendet werden koennen.

Antworten werden in drei Kategorien eingeteilt:
    sure    / risky   gueltige Wahl
    invalid            nicht interpretierbar oder verweigert

Aufruf: python src/parse.py experiments/<name>/laeufe/<datei>.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Das Antwortformat verlangt einen einzelnen Buchstaben. Toleriert werden
# fuehrende Artefakte wie "A." oder "Program A", nicht aber Antworten, die
# beide Buchstaben nennen.
PATTERNS = [
    re.compile(r"^\s*\(?([AB])\)?[\.\)\s]*$", re.IGNORECASE),
    re.compile(r"^\s*(?:program|option|answer|choice)\s*:?\s*([AB])\b", re.IGNORECASE),
]


def saeubern(text: str) -> str:
    """Entfernt Formatierungsreste, die Modelle um die Antwort legen.

    Modelle verpacken kurze Antworten mitunter in Codeblock-Markierungen oder
    Sternchen. Diese Reste sind kein Teil der Antwort und wuerden eine gueltige
    Wahl als nicht interpretierbar verwerfen.
    """
    t = text.strip()
    # Vollstaendiger Codeblock: den Inhalt herausziehen. Die Sprachkennung wird
    # nur als solche erkannt, wenn ihr ein Leerraum folgt - sonst waere bei
    # "```A```" der Buchstabe selbst als Kennung gelesen worden.
    m = re.match(r"^```(?:[a-zA-Z]+\s)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t = m.group(1).strip()
    t = t.strip("`").strip()
    t = re.sub(r"^\*+|\*+$", "", t).strip()
    return t


def extract_letter(text: str | None) -> str | None:
    if not text:
        return None
    t = saeubern(text)
    for pat in PATTERNS:
        m = pat.match(t)
        if m:
            return m.group(1).upper()
    # Fallback: genau ein Buchstabe kommt isoliert vor, der andere nicht.
    #
    # Bewusst NUR Grossbuchstaben: Der unbestimmte Artikel "a" ist im Englischen
    # haeufig ("This is a difficult decision") und wuerde sonst als Wahl von
    # Option A gelesen. Eine verworfene gueltige Antwort ist der harmlosere
    # Fehler - eine erfundene Wahl verzerrt das Ergebnis.
    found = set(re.findall(r"\b([AB])\b", t))
    if len(found) == 1:
        return found.pop()
    return None


# Fehlermeldungen, mit denen ein Anbieter eine zu lange Antwort ablehnt, statt
# sie abzuschneiden (OpenAI: "max_tokens or model output limit was reached").
# Das ist keine Verbindungsstoerung, sondern eine Antwort, die das Format nicht
# einhaelt: Sie zaehlt als nicht auswertbar und wird nicht neu gezogen.
# Festgelegt nach dem Hauptlauf des Framing-Experiments (zwei Faelle bei Luna).
LAENGENGRENZE = re.compile(r"max_tokens|output limit", re.I)


def laengengrenze(fehler: str | None) -> bool:
    return bool(fehler) and bool(LAENGENGRENZE.search(fehler))


def ist_antwort(rec: dict) -> bool:
    """Hat das Modell geantwortet - gueltig, formwidrig oder zu lang?"""
    return rec.get("error") is None or laengengrenze(rec.get("error"))


def je_durchlauf(saetze: list[dict]) -> list[dict]:
    """Genau ein Datensatz je Durchlauf.

    Bei einem fortgesetzten Lauf stehen Fehlversuch und spaetere Antwort
    hintereinander in der Datei. Es zaehlt die Antwort; gibt es keine, der
    letzte Fehlversuch.
    """
    gewaehlt: dict = {}
    for r in saetze:
        schluessel = (r["cell_id"], r["replicate"])
        bisher = gewaehlt.get(schluessel)
        if bisher is None or not ist_antwort(bisher):
            gewaehlt[schluessel] = r
    return list(gewaehlt.values())


def parse_file(path: Path) -> tuple[pd.DataFrame, dict]:
    rows, meta, saetze = [], {}, []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if "_meta" in rec:
                meta = rec["_meta"]
            else:
                saetze.append(rec)
    for rec in je_durchlauf(saetze):
        zu_lang = laengengrenze(rec.get("error"))
        letter = extract_letter(rec.get("raw_text"))
        if letter is None:
            choice = "invalid"
            chose_sure = None
        else:
            chose_sure = int(letter == rec["sure_option"])
            choice = "sure" if chose_sure else "risky"
        rows.append({
            "item": rec["item"],
            "frame": rec["frame"],
            "spec_level": rec["spec_level"],
            "variant": rec["variant"] or "none",
            "replicate": rec["replicate"],
            "sure_option": rec["sure_option"],
            "raw_text": rec.get("raw_text"),
            "parsed_letter": letter,
            "choice": choice,
            "chose_sure": chose_sure,
            # Eine zu lange Antwort ist eine Antwort, kein API-Fehler.
            "error": None if zu_lang else rec.get("error"),
            "hinweis": "Ausgabe ueber der Laengengrenze" if zu_lang else None,
            "model_id": rec.get("model_id"),
            "temperature": rec.get("temperature"),
        })
    return pd.DataFrame(rows), meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.jsonl).resolve()
    df, meta = parse_file(src)
    out = Path(args.out).resolve() if args.out else src.with_suffix(".parsed.csv")
    df.to_csv(out, index=False)

    n = len(df)
    n_err = int(df["error"].notna().sum())
    n_inv = int((df["choice"] == "invalid").sum())
    print(f"Quelle: {src.name}")
    print(f"Modell: {meta.get('model_id')} | Temperatur: {meta.get('temperature')}")
    print(f"Trials: {n}")
    print(f"API-Fehler: {n_err} ({n_err/n:.2%})")
    n_lang = int(df["hinweis"].notna().sum())
    if n_lang:
        print(f"Davon nicht auswertbar, weil ueber der Laengengrenze: {n_lang}")
    print(f"Nicht parsebar: {n_inv} ({n_inv/n:.2%})")
    if n_inv:
        bad = df[df["choice"] == "invalid"]["raw_text"].value_counts().head(5)
        print("Haeufigste ungueltige Antworten:")
        for txt, c in bad.items():
            print(f"  {c:>5}x  {str(txt)[:70]!r}")
    print(f"\nGeschrieben: {out}")


if __name__ == "__main__":
    main()
