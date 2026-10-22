#!/usr/bin/env bash
# Reproduziert die gesamte Auswertung eines Experiments.
#
#   ./run_pipeline.sh [n]                       Generalprobe: zwei Mock-Läufe, ohne API
#   ./run_pipeline.sh daten A.jsonl B.jsonl     Auswertung aus vorhandenen Rohdaten
#                       [Name A] [Name B]
#
# Welches Experiment gilt, steuert die Umgebungsvariable EXPERIMENT
# (Standard: framing). Mit REFERENZ_NEU=1 werden die Referenzwerte vorher aus
# den Rohdaten der Vergleichsstudien neu berechnet; sonst gelten die
# versionierten Werte unter referenz/.
#
# Die Erhebung selbst läuft bewusst nicht über dieses Skript: Sie kostet Geld
# und geschieht einmal. Wiederholbar mit einem Befehl ist alles, was danach
# kommt.
set -euo pipefail

cd "$(dirname "$0")"
if [ -n "${PYTHON:-}" ]; then PY="$PYTHON"
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=python3; fi

EXP=$("$PY" src/experiment.py verzeichnis)
echo "Experiment: $EXP"

if [ "${1:-}" = "daten" ]; then
  A="$2"; B="$3"
  NAME_A="${4:-Modell A}"; NAME_B="${5:-Modell B}"
  ERG="$EXP/ergebnisse"
else
  # Ohne Angabe der geplante Umfang aus der experiment.yaml, sonst 200.
  N="${1:-$("$PY" -c 'import sys; sys.path.insert(0, "src"); import experiment; print(experiment.geplantes_n() or 200)')}"
  A="$EXP/laeufe/mock_a.jsonl"; B="$EXP/laeufe/mock_b.jsonl"
  NAME_A="Mock A"; NAME_B="Mock B"
  ERG="$EXP/ergebnisse/mock"
fi

echo
echo "== 1/6  Referenzwerte =="
if [ "${REFERENZ_NEU:-0}" = "1" ]; then
  # Zeilenweise lesen, damit Pfade mit Leerzeichen heil bleiben.
  while IFS= read -r SKRIPT; do
    "$PY" "$SKRIPT"
    echo
  done < <("$PY" src/experiment.py skripte referenz_erstellen)
else
  echo "Versionierte Werte: $("$PY" -c 'import sys; sys.path.insert(0, "src"); import experiment; print(experiment.referenzwerte())')"
  echo "(neu berechnen mit REFERENZ_NEU=1)"
fi

echo
echo "== 2/6  Tests =="
"$PY" -m pytest tests/ -q

echo
echo "== 3/6  Stichprobenplanung, Versuchsplan, Material =="
"$PY" src/power.py
echo
"$PY" src/tabellen.py
echo
"$PY" src/material.py

if [ "${1:-}" != "daten" ]; then
  echo
  echo "== Mock-Läufe (n=$N je Stufe und Bedingung) =="
  rm -f "$A" "$B"
  "$PY" src/runner.py --provider mock --model mock --n "$N" --seed 20260828 --out "$A"
  "$PY" src/runner.py --provider mock --model mock --n "$N" --seed 11 --out "$B"
fi

echo
echo "== 4/6  Auswertung je Modell =="
for LAUF in "$A" "$B"; do
  "$PY" src/parse.py "$LAUF"
  echo
  "$PY" src/analyze.py "${LAUF%.jsonl}.parsed.csv" --ziel "$ERG/$(basename "${LAUF%.jsonl}")"
done

echo
echo "== 5/6  Modellvergleich und Zusatzprüfungen des Experiments =="
"$PY" src/compare.py "${A%.jsonl}.parsed.csv" "${B%.jsonl}.parsed.csv" --ziel "$ERG/vergleich"
while IFS= read -r SKRIPT; do
  for LAUF in "$A" "$B"; do
    "$PY" "$SKRIPT" "${LAUF%.jsonl}.parsed.csv"
  done
done < <("$PY" src/experiment.py skripte pruefungen)

echo
echo "== 6/6  Abbildungen =="
"$PY" src/abbildungen.py "$ERG/$(basename "${A%.jsonl}")" "$ERG/$(basename "${B%.jsonl}")" \
    --namen "$NAME_A" "$NAME_B" --ziel "$ERG/abbildungen"
