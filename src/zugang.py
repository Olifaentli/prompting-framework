"""Laedt die Zugangsdaten aus der Datei .env, falls vorhanden.

Im Quellcode steht nie ein Schluessel. Die Skripte lesen ausschliesslich
Umgebungsvariablen; diese Datei sorgt lediglich dafuer, dass eine lokale
.env-Datei als Quelle dafuer dient. Sie ist in .gitignore eingetragen und
gelangt nicht in die Versionsverwaltung.

Bereits gesetzte Umgebungsvariablen haben Vorrang. Wer die Schluessel im
Terminal exportiert, ueberschreibt damit die Datei - nuetzlich, um einen
Lauf einmalig mit einem anderen Zugang zu fahren.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"


def laden() -> list[str]:
    """Laedt .env und gibt die Namen der gefundenen Zugaenge zurueck."""
    if ENV.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV, override=False)
        except ImportError:
            # Rückfall ohne Zusatzpaket: einfache Zeilen der Form NAME=WERT.
            for zeile in ENV.read_text(encoding="utf-8").splitlines():
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                name, _, wert = zeile.partition("=")
                os.environ.setdefault(name.strip(), wert.strip())
    return [n for n in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") if os.environ.get(n)]


def pruefen(provider: str) -> None:
    """Bricht mit einer verstaendlichen Meldung ab, wenn der Zugang fehlt."""
    gefunden = laden()
    noetig = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    if noetig and noetig not in gefunden:
        raise SystemExit(
            f"{noetig} ist nicht gesetzt.\n"
            f"Entweder im Terminal exportieren oder in die Datei .env eintragen.\n"
            f"Vorlage: .env.example — bezogen wird der Schluessel bei "
            f"{'console.anthropic.com' if provider == 'anthropic' else 'platform.openai.com'}."
        )


if __name__ == "__main__":
    gefunden = laden()
    print(f".env vorhanden: {'ja' if ENV.exists() else 'nein'}")
    for n in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        wert = os.environ.get(n)
        print(f"  {n:<20} {'gesetzt (' + wert[:7] + '…)' if wert else 'fehlt'}")
