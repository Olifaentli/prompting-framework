"""Erzeugt die Versuchszellen und die zugehoerigen Prompts.

Das Design variiert zwei Faktoren:
    Rahmung       gain / loss              (= der Framing-Effekt)
    Detailgrad    S0 / S1 / S2 / S3        (wie viel ueber die Person gesagt wird)

Je Stufe ab S1 gibt es mehrere Formulierungsvarianten mit verschiedenen
Personen, derzeit vier. Sie sind keine eigene Versuchsbedingung, sondern eine
Kontrolle: Faellt das Ergebnis je Variante unterschiedlich aus, haengt es an
der Formulierung und nicht am Detailgrad (vgl. Sclar et al., 2024).

Da S0 keine Beschreibung enthaelt, ergeben sich bei vier Varianten
2 x (1 + 3 x 4) = 26 Zellen je Item.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import Iterator

import yaml

import experiment




@dataclass(frozen=True)
class Cell:
    """Eine Versuchsbedingung ohne Replikation."""
    item: str
    frame: str
    spec_level: str
    variant: str | None

    @property
    def cell_id(self) -> str:
        v = self.variant or "none"
        return f"{self.item}|{self.frame}|{self.spec_level}|{v}"


@dataclass
class Trial:
    """Ein einzelner Modellaufruf: Zelle plus Replikationsindex und Optionsreihenfolge."""
    cell_id: str
    item: str
    frame: str
    spec_level: str
    variant: str | None
    replicate: int
    sure_option: str      # "A" oder "B" - welcher Buchstabe die sichere Option traegt
    prompt: str

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(personas_datei: str | None = None) -> tuple[dict, dict]:
    """Laedt Aufgaben und Personenbeschreibungen.

    Beide Dateien liegen im Materialordner des aktiven Experiments; welche
    gelten, steht in dessen experiment.yaml. Eine andere Personendatei laesst
    sich uebergeben oder ueber die Umgebungsvariable PERSONAS waehlen, etwa um
    die Pipeline mit anderen Beschreibungen zu pruefen. Welche Datei ein Lauf
    verwendet hat, haelt der Runner in der Meta-Zeile fest.
    """
    ordner = experiment.material()
    name = personas_datei or experiment.personen_datei()
    items = yaml.safe_load((ordner / experiment.aufgaben_datei()).read_text(encoding="utf-8"))
    personas = yaml.safe_load((ordner / name).read_text(encoding="utf-8"))
    return items, personas


def active_variants(personas: dict) -> tuple[str, ...]:
    """Formulierungsvarianten, die im Versuchsplan eingesetzt werden.

    Steht in der Konfiguration, nicht im Code: Der Umfang des Versuchsplans ist
    eine inhaltliche Entscheidung und soll ohne Codeaenderung revidierbar sein.
    Fehlt die Angabe, gelten alle Varianten der ersten Stufe mit Beschreibung.
    """
    if personas.get("active_variants"):
        return tuple(personas["active_variants"])
    erste = next(s for s in personas["levels"].values() if s["has_variants"])
    return tuple(erste["variants"])


def stufen(personas: dict) -> list[str]:
    """Die Detailstufen in der Reihenfolge der Konfiguration, von wenig zu viel."""
    return list(personas["levels"])


def baseline(personas: dict) -> str:
    """Die Stufe ohne Personenbeschreibung, gegen die der Effekt zuerst geprueft wird."""
    ohne = [s for s, spec in personas["levels"].items() if not spec["has_variants"]]
    return ohne[0] if ohne else stufen(personas)[0]


def enumerate_cells(items: dict, personas: dict, only_item: str | None = None) -> list[Cell]:
    variants = active_variants(personas)
    cells: list[Cell] = []
    for item_name, item in items.items():
        if only_item and item_name != only_item:
            continue
        for frame in item["frames"]:
            for level, spec in personas["levels"].items():
                if spec["has_variants"]:
                    for v in variants:
                        cells.append(Cell(item_name, frame, level, v))
                else:
                    cells.append(Cell(item_name, frame, level, None))
    return cells


def build_persona_block(personas: dict, level: str, variant: str | None) -> str:
    """Die Personenbeschreibung der gegebenen Stufe und Variante.

    Die Varianten enthalten den vollstaendigen Text; es gibt keine Platzhalter.
    S0 liefert eine leere Beschreibung.
    """
    spec = personas["levels"][level]
    if not spec["has_variants"]:
        return ""
    return spec["variants"][variant].strip()


def build_prompt(items: dict, personas: dict, cell: Cell, sure_option: str) -> str:
    item = items[cell.item]
    frame = item["frames"][cell.frame]

    parts: list[str] = []

    persona = build_persona_block(personas, cell.spec_level, cell.variant)
    if persona:
        parts.append(persona)

    if item.get("intro"):
        parts.append(item["intro"].strip())
    if frame.get("preamble"):
        parts.append(frame["preamble"].strip())

    # Optionsreihenfolge randomisiert, um Positionsbias zu kontrollieren.
    if sure_option == "A":
        options = [("A", frame["sure"]), ("B", frame["risky"])]
    else:
        options = [("A", frame["risky"]), ("B", frame["sure"])]
    parts.append("\n".join(f"{letter}: {text.strip()}" for letter, text in options))

    parts.append(item["question"].strip())
    parts.append(personas["response_instruction"].strip())

    return "\n\n".join(parts)


def generate_trials(
    n: int,
    seed: int = 20260828,
    only_item: str | None = None,
    only_level: str | None = None,
    je_stufe: bool = True,
) -> Iterator[Trial]:
    """Erzeugt alle Trials in deterministischer Reihenfolge.

    `je_stufe=True` (Standard) deutet n als Zahl der Durchlaeufe **je Stufe und
    Rahmung** und verteilt sie gleichmaessig auf die Formulierungsvarianten
    dieser Stufe. Das entspricht der Auswertung, die je Stufe aggregiert: Die
    Varianten teilen sich die Durchlaeufe und liefern die Streuung.

    Ohne diese Verteilung erhielte die Baseline, die nur eine Variante hat,
    denselben Umfang wie eine einzelne Variante der hoeheren Stufen - also ein
    Achtel des Noetigen, und das ausgerechnet bei der Stufe mit dem wichtigsten
    Vergleichswert.

    `je_stufe=False` deutet n als Zahl je Zelle, was fuer Pilotlaeufe handlich ist.
    """
    items, personas = load_config()
    rng = random.Random(seed)
    varianten = active_variants(personas)
    n_varianten = len(varianten)

    for cell in enumerate_cells(items, personas, only_item):
        if only_level and cell.spec_level != only_level:
            continue
        if je_stufe:
            if cell.variant is None:
                n_per_cell = n
            else:
                # Exakte Aufteilung: Der Rest wird auf die ersten Varianten
                # verteilt, damit die Summe je Stufe genau n ergibt.
                i = varianten.index(cell.variant)
                n_per_cell = n // n_varianten + (1 if i < n % n_varianten else 0)
            n_per_cell = max(1, n_per_cell)
        else:
            n_per_cell = n
        # Exakt balancierte Zuordnung, danach gemischt.
        order = ["A"] * (n_per_cell // 2) + ["B"] * (n_per_cell - n_per_cell // 2)
        rng.shuffle(order)
        for i, sure_option in enumerate(order):
            yield Trial(
                cell_id=cell.cell_id,
                item=cell.item,
                frame=cell.frame,
                spec_level=cell.spec_level,
                variant=cell.variant,
                replicate=i,
                sure_option=sure_option,
                prompt=build_prompt(items, personas, cell, sure_option),
            )


if __name__ == "__main__":
    items, personas = load_config()
    cells = enumerate_cells(items, personas)
    vs = active_variants(personas)
    print(f"Aktive Formulierungsvarianten: {', '.join(vs)}")
    print(f"Zellen gesamt: {len(cells)}")
    for it in items:
        print(f"  {it}: {sum(1 for c in cells if c.item == it)}")

    # Zwei Beispiele: die Baseline der ersten Aufgabe und die ausfuehrlichste
    # Stufe derselben Aufgabe in der anderen Bedingung.
    erste = next(iter(items))
    b = next(c for c in cells if c.item == erste and c.spec_level == baseline(personas))
    print(f"\n--- Beispiel {b.spec_level} (Baseline), {b.item}, {b.frame}, sichere Option als A ---")
    print(build_prompt(items, personas, b, "A"))

    letzte = stufen(personas)[-1]
    c = next(c for c in cells if c.item == erste and c.spec_level == letzte and c.frame != b.frame)
    print(f"\n--- Beispiel {c.spec_level} Variante {c.variant}, {c.item}, {c.frame}, sichere Option als B ---")
    print(build_prompt(items, personas, c, "B"))
