"""Prüft, ob die veröffentlichten Ergebnisse aus Rohdaten und Code entstehen.

1. Entpackt die Rohantworten der Modelle und vergleicht ihre Prüfsummen.
2. Wertet sie mit dem Code dieses Repositorys neu aus: Parser, Auswertung je
   Modell, Modellvergleich.
3. Vergleicht jede neu berechnete Ergebnistabelle mit der veröffentlichten,
   Zahl für Zahl.

Aufruf im Hauptordner des Repositorys, nach der Installation laut README:
    python untersuchung/pruefen.py
"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent
LAEUFE = ("haupt_haiku", "haupt_luna")
TOLERANZ = 1e-9


def ausfuehren(befehl: list[str]) -> None:
    env = {**os.environ, "EXPERIMENT": "framing"}
    env.pop("PERSONAS", None)
    r = subprocess.run(befehl, cwd=ROOT, env=env, text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        raise SystemExit(f"Schritt fehlgeschlagen: {' '.join(befehl)}")


def gleich(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) <= TOLERANZ
    except ValueError:
        return False


def tabellen_gleich(alt: Path, neu: Path) -> bool:
    if not neu.exists():
        return False
    with alt.open(encoding="utf-8") as fa, neu.open(encoding="utf-8") as fb:
        za, zb = list(csv.reader(fa)), list(csv.reader(fb))
    return len(za) == len(zb) and all(
        len(x) == len(y) and all(gleich(u, v) for u, v in zip(x, y)) for x, y in zip(za, zb))


def main() -> None:
    soll = dict(reversed(z.split()) for z in (HIER / "ROHDATEN.sha256").read_text().splitlines())
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        print("1 · Rohantworten")
        with zipfile.ZipFile(HIER / "rohdaten" / "rohdaten_hauptlauf.zip") as z:
            for lauf in LAEUFE:
                inhalt = z.read(f"{lauf}.jsonl")
                ok = hashlib.sha256(inhalt).hexdigest() == soll[f"{lauf}.jsonl"]
                print(f"  {lauf}.jsonl: Prüfsumme {'stimmt' if ok else 'WEICHT AB'}")
                if not ok:
                    raise SystemExit(1)
                (tmp / f"{lauf}.jsonl").write_bytes(inhalt)

        print("2 · Neu auswerten")
        py = sys.executable
        for lauf in LAEUFE:
            ausfuehren([py, "src/parse.py", str(tmp / f"{lauf}.jsonl")])
            ausfuehren([py, "src/analyze.py", str(tmp / f"{lauf}.parsed.csv"),
                        "--ziel", str(tmp / "ergebnisse" / lauf)])
        ausfuehren([py, "src/compare.py", str(tmp / "haupt_haiku.parsed.csv"),
                    str(tmp / "haupt_luna.parsed.csv"), "--ziel", str(tmp / "ergebnisse" / "vergleich")])
        print("  Parser, Auswertung je Modell und Modellvergleich gelaufen")

        print("3 · Mit den veröffentlichten Tabellen vergleichen")
        abweichend, geprueft = [], 0
        for veroeffentlicht in sorted((HIER / "ergebnisse").rglob("*.csv")):
            rel = veroeffentlicht.relative_to(HIER / "ergebnisse")
            if rel.parts[0] not in (*LAEUFE, "vergleich"):
                continue
            geprueft += 1
            if not tabellen_gleich(veroeffentlicht, tmp / "ergebnisse" / rel):
                abweichend.append(str(rel))
        if abweichend:
            print(f"  {len(abweichend)} von {geprueft} Tabellen weichen ab:")
            for a in abweichend:
                print(f"    - {a}")
            raise SystemExit(1)
        print(f"  Alle {geprueft} Tabellen stimmen überein.")


if __name__ == "__main__":
    main()
