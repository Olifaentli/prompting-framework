"""Angaben, die jeder Lauf ueber sich selbst festhaelt.

Ein Rohprotokoll ist nur so viel wert wie das Wissen, unter welchen
Bedingungen es entstanden ist. Festgehalten werden daher das verwendete
Material mit Pruefsumme, der Stand des Codes und die Versionen der
Bibliotheken. Damit laesst sich jeder Lauf eindeutig dem eingefrorenen
Material zuordnen - oder zeigen, dass er es nicht war.
"""

from __future__ import annotations

import hashlib
import subprocess
from importlib import metadata
from pathlib import Path

import experiment

ROOT = Path(__file__).resolve().parent.parent

PAKETE = ("anthropic", "openai", "pandas", "numpy", "scipy", "PyYAML")


def sha256(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def git_stand() -> dict:
    """Commit und ob es ungespeicherte Aenderungen gab."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                capture_output=True, check=True).stdout.strip()
        offen = subprocess.run(["git", "status", "--porcelain", "--",
                                str(ROOT / "src"), str(experiment.material())],
                               cwd=ROOT, text=True, capture_output=True,
                               check=True).stdout.strip()
        return {"commit": commit, "aenderungen_offen": bool(offen)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "aenderungen_offen": None}


def material() -> dict:
    """Name und Pruefsumme der Dateien, aus denen die Prompts entstehen."""
    ordner = experiment.material()
    personas = experiment.personen_datei()
    eingefroren = {}
    liste = ordner / "eingefroren.sha256"
    if liste.exists():
        for zeile in liste.read_text(encoding="utf-8").splitlines():
            soll, name = zeile.split()
            eingefroren[name] = soll
    info = {}
    for name in (personas, experiment.aufgaben_datei()):
        ist = sha256(ordner / name)
        info[name] = {"sha256": ist, "eingefroren": eingefroren.get(name) == ist}
    return {"experiment": experiment.verzeichnis().name,
            "personas_datei": personas, "dateien": info}


def versionen() -> dict:
    out = {}
    for p in PAKETE:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = None
    return out


def erfassen() -> dict:
    return {"material": material(), "git": git_stand(), "pakete": versionen()}


def pruefen_vor_echtem_lauf(info: dict) -> None:
    """Bricht ab, wenn ein bezahlter Lauf nicht auf dem eingefrorenen Material beruht.

    Ein Mock-Lauf darf alles; ein Lauf gegen eine API kostet Geld und landet
    in der Auswertung. Er soll nur mit eingefrorenem Material und
    gespeichertem Code moeglich sein.
    """
    nicht = [n for n, d in info["material"]["dateien"].items() if not d["eingefroren"]]
    if nicht:
        raise SystemExit(
            f"Nicht eingefrorenes Material: {', '.join(nicht)}. "
            "Ein echter Lauf ist nur mit den Dateien aus material/eingefroren.sha256 "
            "des Experiments moeglich.")
    if info["git"]["aenderungen_offen"]:
        raise SystemExit(
            "Ungespeicherte Aenderungen in src/ oder im Material. Erst committen, damit der "
            "Lauf einem Code-Stand zugeordnet werden kann.")
