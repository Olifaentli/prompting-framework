# Prompting-Framework für Verhaltensexperimente mit Sprachmodellen

Ein Werkzeug, um zu messen, wie gut ein Sprachmodell einen bekannten
menschlichen Verhaltenseffekt wiedergibt — und wie sich das ändert, wenn man
dem Modell mehr oder weniger über die Person sagt, die es spielen soll.

Das Framework nimmt eine Entscheidungsaufgabe im Originalwortlaut, erzeugt
daraus einen vollständig balancierten Versuchsplan, schickt jeden Prompt an
ein oder mehrere Modelle, speichert die Antworten unverändert und vergleicht
die Antwortverteilung mit erhobenen menschlichen Daten. Jeder Schritt ist
wiederholbar, jeder Lauf weiss, mit welchem Material und welchem Code er
entstanden ist.

Mögliche Einsätze: eine Studie mit Menschen vorab simulieren (Pilot), prüfen,
ob ein Effekt bei Modellen überhaupt auftritt, oder Prompting-Strategien gegen
einen echten Massstab vergleichen statt nach Gefühl.

Mitgeliefert ist ein vollständiges Beispiel: der **Framing-Effekt**
(Tversky & Kahneman, 1981) gegen die Replikationsdaten aus Many Labs 1 und
Ruggeri et al. (2020), mit vier Stufen von Personendetail.

## Schnellstart

Voraussetzung: Python 3.12 oder neuer (die festgelegten Versionen von numpy und
scipy verlangen es).

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q        # Testsuite
./run_pipeline.sh                            # Generalprobe ohne API-Schlüssel
```

Die Generalprobe zieht zwei vollständige Läufe aus einem Mock-Modell mit
bekannten Parametern und führt sie durch die gesamte Kette bis zu Tabellen und
Abbildungen unter `experiments/framing/ergebnisse/mock/`. Sie braucht weder
Schlüssel noch Netz.

Für echte Läufe: `.env.example` nach `.env` kopieren und die Schlüssel
eintragen. Die Datei bleibt ausserhalb der Versionsverwaltung.

## Aufbau

```
src/                    Das Framework
  experiment.py         welches Experiment aktiv ist und wo seine Dateien liegen
  design.py             Versuchsplan: Zellen, Durchläufe, Optionsreihenfolge, Prompts
  generate_personas.py  erzeugt und prüft Personenbeschreibungen mit einem Modell
  runner.py             Einzelaufrufe (Anthropic, OpenAI, Mock), fortsetzbar
  runner_batch.py       Stapelverarbeitung über die Batch-API von Anthropic
  models.py             Modellregister mit Preisen und Temperatursteuerung
  laufinfo.py           was jeder Lauf über sich festhält
  parse.py              Rohantwort → Wahl (getrennt von der Erhebung)
  analyze.py            Anteile, Effekt, Abstand zum Menschen, Kontrollen
  compare.py            zwei Modelle auf demselben Plan vergleichen
  referenz.py           menschliche Vergleichswerte im Standardformat
  statutils.py          Wilson- und Newcombe-Intervalle
  power.py              Stichprobenumfang aus der Zielgenauigkeit
  tabellen.py           Referenzwerte und Versuchsplan als Tabelle
  abbildungen.py        zwei druckfeste Standardabbildungen
  material.py           das gesamte Material als lesbare Dokumentation
experiments/framing/    das Beispiel-Experiment
experiments/vorlage/    Vorlage für ein eigenes Experiment (Platzhalter, läuft durch)
tests/                  Testsuite
docs/                   Aufbau im Detail, eigenes Experiment anlegen
run_pipeline.sh         Auswertung mit einem Befehl
```

Ausführlich: [docs/AUFBAU.md](docs/AUFBAU.md).
Ein eigenes Experiment anlegen: [docs/EIGENES_EXPERIMENT.md](docs/EIGENES_EXPERIMENT.md).

## Ablauf eines Experiments

| Schritt | Befehl |
|---|---|
| Versuchsplan prüfen | `.venv/bin/python src/design.py` |
| Stichprobenumfang | `.venv/bin/python src/power.py` |
| Kosten schätzen | `.venv/bin/python src/runner.py --model haiku-4.5 --n 910 --dry-run` |
| Lauf, Einzelaufrufe | `.venv/bin/python src/runner.py --provider openai --model luna --n 910 --temperature 1.0` |
| Lauf, Batch-API | `.venv/bin/python src/runner_batch.py submit --model haiku-4.5 --n 910` |
| Batch abholen | `.venv/bin/python src/runner_batch.py fetch --manifest <manifest>.json` |
| Fehlgeschlagene nachreichen | `.venv/bin/python src/runner_batch.py nachreichen --manifest <manifest>.json` |
| Alles auswerten | `./run_pipeline.sh daten <lauf_a>.jsonl <lauf_b>.jsonl "Modell A" "Modell B"` |

Ein anderes Experiment wählt die Umgebungsvariable `EXPERIMENT`
(etwa `EXPERIMENT=mein_experiment ./run_pipeline.sh`).

## Grundsätze

**Rohdaten bleiben roh.** Der Runner parst nichts, sondern schreibt die
unveränderte Antwort als JSON Lines. Jede Auslegung ist später revidierbar,
ohne den Lauf zu wiederholen.

**Material wird eingefroren.** Aufgaben und Personenbeschreibungen sind
Material, keine Programmlogik. Ihre Prüfsummen stehen im Experiment; ein
bezahlter Lauf startet nur, wenn das Material unverändert und der Code
gespeichert ist.

**Jeder Lauf weiss, woher er kommt.** Die erste Zeile jeder Rohdatei hält
Material mit Prüfsumme, Code-Stand, Bibliotheksversionen und Einstellungen
fest; jede Antwort die tatsächlich ausgelieferte Modellversion.

**Optionsreihenfolge exakt balanciert.** Die Zieloption steht in genau der
Hälfte der Durchläufe vorn. Das hält den bei Sprachmodellen belegten
Positionsbias aus den Mittelwerten heraus und macht ihn messbar.

**Allein der Detailgrad variiert.** Die Personenbeschreibungen einer Stufe
unterscheiden sich nur darin, wie viel sie über eine Person sagen, nie darin,
welche Neigung sie nahelegen. Der Generator prüft das maschinell; dieselbe
Variante beschreibt auf allen Stufen dieselbe Person.

**Statistik so einfach wie möglich.** Anteile, deren Differenzen und
95-%-Intervalle (Wilson, Newcombe), dazu eine vorab festgelegte
Relevanzgrenze. Die Frage „wie nah am Menschen?“ ist eine Abstandsfrage; ein
Abstand mit Intervall beantwortet sie direkter als ein Test.

## Modelle

Das Register in `src/models.py` führt Anthropic- und OpenAI-Modelle mit
Preisen. Für Verteilungsexperimente braucht es einstellbare Temperatur; die
jeweils neuesten Spitzenmodelle bieten sie teils nicht mehr an und sind
entsprechend markiert. Wo möglich wird eine datierte Modellkennung angefordert,
sonst die ausgelieferte Version je Antwort protokolliert.

## Beispiel-Experiment: Framing

`experiments/framing/` ist ein vollständiges, lauffähiges Experiment:

- **Material:** zwei Entscheidungsaufgaben im Originalwortlaut und zwölf
  erzeugte, geprüfte und eingefrorene Personenbeschreibungen (vier Personen
  auf drei Detailstufen), dazu das Protokoll ihrer Erzeugung. Alles lesbar in
  [experiments/framing/MATERIAL.md](experiments/framing/MATERIAL.md).
- **Vergleichswerte:** die aufbereiteten menschlichen Kennzahlen je Aufgabe
  (Anteile, Differenz, Standardfehler) mit Quellenangabe.
- **Skripte:** wie die Vergleichswerte aus den Rohdaten der Studien entstehen,
  und eine Prüfung, ob ein Modell eher Lehrbuchwerte wiedergibt als entscheidet.

**Nicht enthalten** sind die Rohdaten der Vergleichsstudien und die
Modellantworten oder Ergebnisse der ursprünglichen Untersuchung. Wer das
Experiment wiederholen will, lädt die Rohdaten bei den Quellen (die Skripte
nennen die Adressen) und fragt die Modelle mit eigenem API-Schlüssel; ein
vollständiger Lauf mit zwei Modellen kostete rund 1,80 US-Dollar.

| Datensatz | Quelle | Lizenz | im Repository |
|---|---|---|---|
| Many Labs 1 (Klein et al., 2014) | [osf.io/wx7ck](https://osf.io/wx7ck/) | CC0 1.0 | nur aufbereitete Kennzahlen |
| Ruggeri et al. (2020) | [osf.io/esxc4](https://osf.io/esxc4/) | keine Angabe | nur aufbereitete Kennzahlen, mit Quellenangabe |

```bash
REFERENZ_NEU=1 ./run_pipeline.sh     # Vergleichswerte aus den geladenen Rohdaten neu berechnen
```

## Grenzen der aktuellen Fassung

Das Framework ist um Entscheidungsaufgaben mit zwei Optionen und zwei
Bedingungen gebaut (im Schema `gain`/`loss` und `sure`/`risky`). Andere
Aufgabenformen und die Generatorregeln als Konfiguration statt als Code sind
als nächste Schritte vorgesehen; siehe [docs/EIGENES_EXPERIMENT.md](docs/EIGENES_EXPERIMENT.md#grenzen).

## Lizenz

Der Code steht unter der [MIT-Lizenz](LICENSE): Nutzen, Verändern und
Weitergeben sind erlaubt, solange der Urheberrechtshinweis erhalten bleibt.
Für die Daten der Vergleichsstudien gelten deren eigene Bedingungen (siehe
Tabelle oben).
