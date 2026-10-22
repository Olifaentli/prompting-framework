"""Das aktive Experiment: wo Material, Referenzwerte, Laeufe und Ergebnisse liegen.

Das Framework selbst kennt keine festen Pfade. Jedes Experiment ist ein Ordner
unter experiments/ mit einer experiment.yaml, die Material, Referenzwerte,
Auswertungsparameter und experimentspezifische Skripte benennt:

    experiments/<name>/
        experiment.yaml     Beschreibung des Experiments
        material/           Aufgaben, Personenbeschreibungen, Pruefsummen
        referenz/           menschliche Vergleichswerte (referenzwerte.csv)
        skripte/            Aufbereitung der Referenzdaten, Zusatzpruefungen
        laeufe/             Rohprotokolle der Modelllaeufe (nicht versioniert)
        ergebnisse/         Tabellen und Abbildungen

Welches Experiment gilt, steuert die Umgebungsvariable EXPERIMENT (Name unter
experiments/ oder Pfad). Ohne Angabe gilt das Beispiel-Experiment "framing".

Aufruf von der Kommandozeile, etwa aus run_pipeline.sh:
    python src/experiment.py verzeichnis
    python src/experiment.py skripte referenz_erstellen
    python src/experiment.py skripte pruefungen
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STANDARD = "framing"


def verzeichnis() -> Path:
    wert = os.environ.get("EXPERIMENT", STANDARD)
    unter_experiments = ROOT / "experiments" / wert
    pfad = unter_experiments if unter_experiments.is_dir() else Path(wert).resolve()
    if not (pfad / "experiment.yaml").exists():
        raise SystemExit(f"Kein Experiment unter '{pfad}' (experiment.yaml fehlt).")
    return pfad


def konfiguration() -> dict:
    return yaml.safe_load((verzeichnis() / "experiment.yaml").read_text(encoding="utf-8"))


def name() -> str:
    return konfiguration().get("name", verzeichnis().name)


def material() -> Path:
    return verzeichnis() / "material"


def aufgaben_datei() -> str:
    return konfiguration()["material"]["aufgaben"]


def personen_datei() -> str:
    """Die Personendatei: aus der Umgebungsvariablen PERSONAS oder der Konfiguration."""
    return os.environ.get("PERSONAS", konfiguration()["material"]["personen"])


def referenzwerte() -> Path:
    return verzeichnis() / konfiguration()["referenzwerte"]


def laeufe() -> Path:
    return verzeichnis() / "laeufe"


def ergebnisse() -> Path:
    return verzeichnis() / "ergebnisse"


def geplantes_n() -> int | None:
    """Geplante Durchlaeufe je Stufe und Bedingung, falls angegeben."""
    return konfiguration().get("versuchsplan", {}).get("n")


def auswertung(schluessel: str):
    return konfiguration()["auswertung"][schluessel]


def titel(aufgabe: str) -> str:
    return konfiguration().get("darstellung", {}).get("aufgaben", {}).get(aufgabe, aufgabe)


def stufentext(stufe: str) -> str:
    return konfiguration().get("darstellung", {}).get("stufen", {}).get(stufe, "")


def skripte(art: str) -> list[Path]:
    """Experimentspezifische Skripte einer Art, etwa 'referenz_erstellen' oder 'pruefungen'."""
    return [verzeichnis() / s for s in konfiguration().get(art, [])]


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verzeichnis":
        print(verzeichnis())
    elif len(sys.argv) == 3 and sys.argv[1] == "skripte":
        for s in skripte(sys.argv[2]):
            print(s)
    else:
        raise SystemExit(__doc__)
