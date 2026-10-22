# Untersuchung: Framing-Effekt und Detailgrad der Personenbeschreibung

Die Ergebnisse des Hauptlaufs vom 9. Oktober 2026, erhoben mit dem Framework
in diesem Repository und dem Experiment `experiments/framing/`. Dieser Ordner
ist dafür da, dass sich die Ergebnisse nachprüfen lassen.

## Was erhoben wurde

| | Claude Haiku 4.5 | GPT-6 Luna |
|---|---|---|
| Modellkennung | `claude-haiku-4-5-20251001` | `gpt-6-luna` |
| Weg | Stapelverarbeitung (Batch-API) | Einzelaufrufe |
| Temperatur | 1,0 | 1,0, Reasoning abgeschaltet |
| Aufrufe | 14.560 | 14.560 |
| Nicht auswertbar | 0 | 2 (Antwort über der Längengrenze) |
| Kosten | 1,38 US-Dollar | 0,26 US-Dollar |

Zwei Aufgaben (Asian-Disease-Problem, Geldbeträge) × zwei Rahmungen × vier
Detailstufen, 910 Durchläufe je Stufe und Rahmung, auf vier Personen verteilt.

## Inhalt

| Datei | Was es ist |
|---|---|
| `rohdaten/rohdaten_hauptlauf.zip` | Alle Rohantworten der Modelle, unverändert, dazu Pilot und Vorabprüfung |
| `ROHDATEN.sha256` | Prüfsummen der Rohdateien |
| `ergebnisse/haupt_haiku/`, `ergebnisse/haupt_luna/` | Ergebnistabellen je Modell: Effekt je Stufe, Varianten, Positionsbias, nicht auswertbare Antworten |
| `ergebnisse/vergleich/` | Modellvergleich je Aufgabe |
| `ergebnisse/tabellen/` | Vergleichswerte und Versuchsplan |
| `ergebnisse/abbildungen/` | Die zwei Abbildungen (SVG und PNG) |
| `ergebnisse/auswertung_protokoll.txt` | Vollständige Ausgabe der Auswertung |
| `ANALYSEPLAN.md` | Was vor der Erhebung festgelegt wurde |
| `DURCHFUEHRUNG.md` | Was bei der Erhebung geschah, mit allen Vorkommnissen |
| `pruefen.py` | Rechnet die Ergebnisse aus den Rohdaten neu und vergleicht sie |

## Nachprüfen

Voraussetzung ist Python 3.12 oder neuer. Im Hauptordner des Repositorys:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python untersuchung/pruefen.py
```

Unter Windows heisst der Interpreter `.venv\Scripts\python`.

Das Skript prüft drei Dinge:

1. Die Rohantworten sind unverändert (Prüfsummen).
2. Parser, Auswertung je Modell und Modellvergleich laufen mit dem Code dieses
   Repositorys durch.
3. Jede neu berechnete Ergebnistabelle stimmt Zahl für Zahl mit der hier
   veröffentlichten überein.

Am Ende steht „Alle … Tabellen stimmen überein“ oder eine Liste der
abweichenden Tabellen.

## Was sich darüber hinaus prüfen lässt

- **Die Prompts:** Sie werden nicht gespeichert, weil sie aus dem Material und
  dem Startwert exakt entstehen. `src/design.py` zeigt Beispiele; jede Zeile der
  Rohdaten nennt Zelle, Durchlauf und Position der sicheren Option.
- **Die Vergleichswerte:** Die Rohdaten von Many Labs 1 und Ruggeri et al. sind
  nicht enthalten. Wer sie bei den Quellen lädt (Adressen in den Skripten unter
  `experiments/framing/skripte/`), kann die Vergleichswerte mit
  `REFERENZ_NEU=1 ./run_pipeline.sh` neu berechnen.
- **Die Erhebung selbst** lässt sich nicht Antwort für Antwort wiederholen:
  Die Modelle antworten bei Temperatur 1,0 zufällig. Ein neuer Lauf ergibt neue
  Stichproben; die Auswertung lässt sich darauf genauso anwenden.

## Abweichungen vom Analyseplan

Zwei, beide in `DURCHFUEHRUNG.md` beschrieben:

1. Zwei Luna-Antworten waren länger als erlaubt; OpenAI meldet das als Fehler.
   Sie zählen als nicht auswertbar und wurden nicht neu gezogen.
2. Die Prüfung „Original oder Replikation?“ meldet kein Signal, wenn ein Modell
   von beiden Vergleichswerten mehr als 0,10 entfernt liegt. Das wurde nach
   Ansicht der Daten ergänzt; die berechneten Abstände sind unverändert.
