"""Die Vorlage fuer neue Experimente laeuft durch.

Schuetzt davor, dass das Framework still wieder vom Beispiel-Experiment
abhaengt: andere Aufgabennamen, drei statt vier Stufen, zwei Varianten. Die
Schritte laufen als eigene Prozesse mit EXPERIMENT=vorlage, genau wie bei
einer Person, die ein eigenes Experiment anlegt.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lauf(args, tmp_path):
    env = {**os.environ, "EXPERIMENT": "vorlage"}
    env.pop("PERSONAS", None)
    r = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True,
                       capture_output=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_vorlage_von_plan_bis_auswertung(tmp_path):
    out = tmp_path / "lauf.jsonl"
    plan = _lauf(["src/design.py"], tmp_path)
    assert "Zellen gesamt: 10" in plan                  # 2 x (1 + 2 x 2)
    _lauf(["src/runner.py", "--provider", "mock", "--model", "mock", "--n", "40",
           "--out", str(out)], tmp_path)
    _lauf(["src/parse.py", str(out)], tmp_path)
    bericht = _lauf(["src/analyze.py", str(out.with_suffix(".parsed.csv")),
                     "--ziel", str(tmp_path / "ergebnisse")], tmp_path)
    assert "Aufgabe: aufgabe_1" in bericht
    assert "Baseline S0" in bericht
    assert (tmp_path / "ergebnisse" / "stufen_aufgabe_1.csv").exists()
