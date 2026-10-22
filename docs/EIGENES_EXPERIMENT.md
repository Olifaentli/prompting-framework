# Ein eigenes Experiment anlegen

Ein Experiment ist ein Ordner unter `experiments/`. Der Code bleibt
unverändert; alles Experimentspezifische steht in Dateien.

## 1 · Ordner anlegen

Von der Vorlage aus, nicht vom Beispiel: Die Vorlage enthält nur Platzhalter
und läuft so, wie sie ist, gegen das Mock-Modell durch. Wer vom Beispiel
kopiert, schleppt dessen Beschreibungen, Referenzdaten und Skripte mit und
friert sie womöglich unbemerkt ein.

```bash
cp -r experiments/vorlage experiments/mein_experiment
export EXPERIMENT=mein_experiment
./run_pipeline.sh 100            # einmal mit den Platzhaltern durchlaufen lassen
```

Die Probe hinterlässt Ergebnisse zu den Platzhaltern. Bevor die eigenen Daten
kommen, diese Ordner leeren:

```bash
rm -rf experiments/mein_experiment/{laeufe,ergebnisse} experiments/mein_experiment/MATERIAL.md
```

Alle Befehle wirken jetzt auf `experiments/mein_experiment/`. Die Testsuite
prüft weiterhin das Framework am Beispiel `framing`, unabhängig davon,
welches Experiment aktiv ist.

## 2 · `experiment.yaml` anpassen

```yaml
name: Mein Experiment
material:
  aufgaben: items.yaml
  personen: personas.yaml        # beim Generator: personas_generated.yaml
referenzwerte: referenz/referenzwerte.csv
versuchsplan:
  n: 910                         # Durchläufe je Stufe und Bedingung, aus src/power.py
auswertung:
  relevanzgrenze: 0.10
  schwelle_ungueltig: 0.05
darstellung:
  aufgaben: {meine_aufgabe: Lesbarer Titel}
  stufen: {S0: keine Beschreibung, S1: ..., S2: ..., S3: ...}
referenz_erstellen: []          # Skripte, die referenzwerte.csv erzeugen
pruefungen: []                  # Zusatzprüfungen je Lauf
```

Relevanzgrenze und Schwelle gehören zum Analyseplan: vor der Erhebung
festlegen, nicht danach.

## 3 · Aufgaben schreiben (`material/items.yaml`)

Im Originalwortlaut der Studie, deren menschliche Daten als Massstab dienen.
Jede Aufgabe braucht zwei Bedingungen (`gain`, `loss`) mit je einer Zieloption
(`sure`) und einer Alternative (`risky`), dazu eine Frage. Gemessen wird der
Anteil der Zieloption je Bedingung; der Effekt ist dessen Differenz.

## 4 · Personenbeschreibungen

Von Hand in einer YAML-Datei nach dem Schema in [AUFBAU.md](AUFBAU.md), oder
mit dem Generator:

```bash
.venv/bin/python src/generate_personas.py --provider openai --model luna --n 4
```

Der Generator schreibt `material/personas_generated.yaml` und ein Protokoll
aller Versuche. Danach in der `experiment.yaml` unter `material.personen`
`personas_generated.yaml` eintragen; der Generator weist darauf hin, wenn das
fehlt. **Lesen, bevor eingefroren wird:** Die maschinelle Prüfung
fängt Stichwörter, aber nicht jede unausgesprochene Neigung. Die Prüfregeln
(verbotene Begriffe, Zielwortzahlen je Stufe) stehen derzeit in
`src/generate_personas.py` und sind auf das Framing-Beispiel zugeschnitten;
für ein anderes Thema dort anpassen.

Wenn möglich, ein Modell einer anderen Anbieterfamilie als die getesteten
verwenden. Sonst liest ein Modell womöglich seine eigene Ausdrucksweise
besser als eine fremde.

## 5 · Referenzwerte

`referenz/referenzwerte.csv` mit einer Zeile je Aufgabe:

| Spalte | Bedeutung |
|---|---|
| `aufgabe` | Schlüssel aus `items.yaml` |
| `quelle`, `design` | Studie; „zwei Gruppen“ oder „gepaart“ |
| `n` | Stichprobenumfang |
| `p_gain`, `p_loss` | Anteil der Zieloption je Bedingung |
| `delta` | `p_gain − p_loss` |
| `se` | Standardfehler von `delta` |

Für unabhängige Gruppen: se aus den beiden Anteilen oder aus einem
publizierten Intervall. Für gepaarte Daten (dieselben Personen in beiden
Bedingungen): √((b + c) − (b − c)²/n) / n mit b, c den diskordanten Paaren.
Ein Skript, das diese Datei aus Rohdaten erzeugt, gehört nach `skripte/` und
unter `referenz_erstellen` in die `experiment.yaml`.

## 6 · Einfrieren

```bash
(cd experiments/mein_experiment/material && sha256sum personas.yaml items.yaml > eingefroren.sha256)
```

Die Dateinamen müssen die sein, die in der `experiment.yaml` stehen.

Danach committen. Ab jetzt startet ein bezahlter Lauf nur mit genau diesem
Material. `ANALYSEPLAN.md` schreiben und ebenfalls committen, bevor echte
Daten erhoben werden.

## 7 · Planen, Pilot, Lauf

```bash
.venv/bin/python src/design.py                       # Zellen und Beispielprompts
.venv/bin/python src/power.py                        # Umfang für die Zielgenauigkeit
.venv/bin/python src/runner.py --model <alias> --n <n> --dry-run   # Kosten
.venv/bin/python src/runner.py --provider <anbieter> --model <alias> --n 50 \
    --temperature 1.0 --out experiments/mein_experiment/laeufe/pilot.jsonl
.venv/bin/python src/parse.py experiments/mein_experiment/laeufe/pilot.jsonl
```

Den Pilot nur technisch beurteilen (Fehlerquote, auswertbare Antworten,
Token), nicht nach Effektgrössen; sonst wird das Design an die Daten angepasst.
Dann der Hauptlauf über `runner.py` oder `runner_batch.py`.

## 8 · Auswerten

```bash
./run_pipeline.sh daten experiments/mein_experiment/laeufe/a.jsonl \
                        experiments/mein_experiment/laeufe/b.jsonl "Modell A" "Modell B"
```

## Neues Modell

Ein Eintrag in `src/models.py` mit Anbieter, Kennung (möglichst datiert),
Temperatursteuerung und Preisen. Ein neuer Anbieter braucht eine Klasse in
`src/runner.py` mit derselben Schnittstelle wie `AnthropicProvider`: Aufruf
mit einem Durchlauf, Rückgabe von Text, Token, Stoppgrund und ausgelieferter
Modellversion. Dazu ein Eintrag in `build_provider` und in den Auswahlwerten
von `--provider`; den Schlüssel liest `src/zugang.py` aus der `.env`.

## Grenzen

Die aktuelle Fassung ist um Entscheidungsaufgaben mit **zwei Optionen** und
**zwei Bedingungen** gebaut, mit den Schlüsseln `gain`/`loss` und
`sure`/`risky`. Detailstufen und Varianten sind frei benennbar und in ihrer
Zahl frei; die Reihenfolge in der Personendatei gilt als Reihenfolge von wenig
zu viel Detail, und die Stufe ohne Beschreibung ist die Baseline. Die
Prüfregeln des Generators sind auf die Stufen `S1` bis `S3` des Beispiels
zugeschnitten. Als nächste Schritte vorgesehen:

- beliebig benannte Bedingungen und Optionen, mehr als zwei Optionen
- die Prüfregeln des Generators als Teil der Experimentkonfiguration
- weitere Anbieter, Stapelverarbeitung auch für OpenAI
