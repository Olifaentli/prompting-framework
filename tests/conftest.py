"""Gemeinsame Einrichtung der Tests.

Die Tests pruefen das Framework anhand des mitgelieferten Beispiel-Experiments
und laufen deshalb immer gegen experiments/framing - auch wenn gerade ein
anderes Experiment aktiv ist (Umgebungsvariable EXPERIMENT). Sonst stuende
ein eigenes Experiment mit anderen Aufgaben und Zahlen staendig im
Widerspruch zu den erwarteten Werten.

Die Framework-Module liegen unter src/, die Skripte des Beispiel-Experiments
unter experiments/framing/skripte/. Beide werden importierbar gemacht.
"""

import os
import sys
from pathlib import Path

os.environ["EXPERIMENT"] = "framing"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "framing" / "skripte"))
