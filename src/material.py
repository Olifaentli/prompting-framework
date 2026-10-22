"""Dokumentiert das Material eines Experiments in einer lesbaren Datei.

Abgedruckt werden der Aufbau des Prompts an einem vollstaendigen Beispiel,
die Aufgabentexte im Originalwortlaut, alle Personenbeschreibungen und die
Pruefsummen. Erzeugt statt abgetippt: Was dort steht, ist nachweislich das,
was die Modelle gelesen haben. Geeignet als Anhang eines Berichts.

Aufruf: python src/material.py   ->  experiments/<name>/MATERIAL.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment
import laufinfo
from design import active_variants, baseline, build_prompt, enumerate_cells, load_config
RAHMUNG = {"gain": "Gewinnrahmung", "loss": "Verlustrahmung"}


def zitat(text: str) -> str:
    return "\n".join(f"> {z}" if z else ">" for z in text.strip().splitlines())


def main() -> None:
    items, personas = load_config()
    info = laufinfo.material()
    zeilen = [f"# Material: {experiment.name()}", "",
              "Automatisch erzeugt aus dem eingefrorenen Material (`src/material.py`).", ""]

    # Beispiel: die erste Zelle mit Personenbeschreibung.
    zelle = next(c for c in enumerate_cells(items, personas) if c.variant is not None)
    zeilen += ["## Aufbau des Prompts", "",
               "Jeder Aufruf besteht aus einer einzigen Nachricht in dieser Reihenfolge: "
               f"Personenbeschreibung (entfällt auf {baseline(personas)}), Aufgabentext, die beiden Optionen, "
               "Frage, Antwortanweisung. Die sichere Option steht in der Hälfte der "
               f"Durchläufe an erster Stelle. Beispiel: {experiment.titel(zelle.item)}, "
               f"{RAHMUNG.get(zelle.frame, zelle.frame)}, Detailstufe {zelle.spec_level}, "
               f"Variante {zelle.variant}, sichere Option als B.", ""]
    zeilen += ["```", build_prompt(items, personas, zelle, "B"), "```", ""]

    zeilen += ["## Aufgabentexte im Originalwortlaut", ""]
    for name, item in items.items():
        zeilen += [f"### {experiment.titel(name)}", "", f"Quelle: {item['source'].strip()}", ""]
        for rahmung, frame in item["frames"].items():
            teile = [t.strip() for t in (item.get("intro"), frame.get("preamble")) if t]
            teile += [f"Sichere Option: {frame['sure'].strip()}",
                      f"Riskante Option: {frame['risky'].strip()}",
                      item["question"].strip()]
            zeilen += [f"**{RAHMUNG.get(rahmung, rahmung)}**", "", zitat("\n\n".join(teile)), ""]

    zeilen += ["## Antwortanweisung", "", zitat(personas["response_instruction"]), ""]

    anzahl = len(active_variants(personas))
    erzeuger = personas.get("_meta", {}).get("modell")
    herkunft = (f"Erzeugt mit {erzeuger}, maschinell geprüft, gelesen und eingefroren."
                if erzeuger else "Von Hand geschrieben und eingefroren.")
    zeilen += ["## Personenbeschreibungen", "",
               f"Je Detailstufe {anzahl} Variante{'n' if anzahl != 1 else ''}; dieselbe "
               f"Variante beschreibt auf allen Stufen dieselbe Person. {herkunft}", ""]
    for v in active_variants(personas):
        zeilen += [f"### Variante {v}", ""]
        for stufe, spec in personas["levels"].items():
            if not spec["has_variants"]:
                continue
            text = spec["variants"][v].strip()
            zeilen += [f"**{stufe}** ({len(text.split())} Wörter)", "", zitat(text), ""]

    zeilen += ["## Prüfsummen", "", "| Datei | SHA-256 |", "|---|---|"]
    for name, d in info["dateien"].items():
        zeilen.append(f"| `{name}` | `{d['sha256']}` |")
    zeilen.append("")

    out = experiment.verzeichnis() / "MATERIAL.md"
    out.write_text("\n".join(zeilen), encoding="utf-8")
    print(f"Geschrieben: {out}")


if __name__ == "__main__":
    main()
