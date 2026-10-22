# Aufbau des Frameworks

Dieses Dokument beschreibt, wie das Framework arbeitet: welche Komponenten es
gibt, wie die Daten von der Konfiguration bis zur Abbildung fliessen, in
welchen Formaten sie gespeichert werden und wie gerechnet wird.

## Überblick

```
 experiment.yaml ─┐
 items.yaml ──────┤                                   referenzwerte.csv
 personas.yaml ───┤                                          │
                  ▼                                          ▼
           ┌────────────┐   Prompts   ┌──────────┐  JSONL  ┌───────┐  CSV  ┌──────────┐
           │ Versuchs-  │ ──────────▶ │ Ausfüh-  │ ──────▶ │ Parser│ ────▶ │ Auswer-  │ ──▶ Tabellen
           │ plan       │             │ rung     │  roh    │       │       │ tung     │ ──▶ Abbildungen
           │ design.py  │             │ runner*  │         │parse  │       │ analyze  │
           └────────────┘             └──────────┘         └───────┘       │ compare  │
                  ▲                         │                              └──────────┘
                  │                         ▼
     generate_personas.py            laufinfo.py: Material-Prüfsummen,
     (einmalig, dann eingefroren)    Code-Stand, Versionen in jeder Rohdatei
```

Fünf Schichten mit klaren Übergaben:

1. **Spezifikation** — Aufgaben und Personenbeschreibungen als Dateien, nicht
   als Code. Einmal erzeugt, geprüft und eingefroren.
2. **Versuchsplan** — leitet aus der Spezifikation alle Zellen und Durchläufe
   ab, deterministisch aus einem Startwert.
3. **Ausführung** — schickt jeden Prompt an ein Modell und speichert die
   Antwort unverändert, mit allem, was zur Einordnung nötig ist.
4. **Auslegung** — übersetzt Rohantworten in Wahlen, getrennt von der
   Erhebung und daher jederzeit neu anwendbar.
5. **Auswertung** — Anteile, Effekt, Abstand zum Menschen, Kontrollen,
   Modellvergleich, Tabellen und Abbildungen.

## Das Experiment als Ordner

Das Framework kennt keine festen Pfade. Alles, was ein Experiment ausmacht,
liegt in einem Ordner unter `experiments/`; `src/experiment.py` löst die Pfade
auf. Welches Experiment gilt, steuert die Umgebungsvariable `EXPERIMENT`
(Standard `framing`).

```
experiments/<name>/
  experiment.yaml        Name, Material, Referenzwerte, Auswertungsparameter,
                         Bezeichnungen, experimentspezifische Skripte
  ANALYSEPLAN.md         was vor der Erhebung festgelegt wurde
  MATERIAL.md            das Material in lesbarer Form (erzeugt)
  material/
    items.yaml           Aufgaben im Originalwortlaut
    personas*.yaml       Personenbeschreibungen je Stufe und Variante
                         (welche Datei gilt, steht in experiment.yaml)
    eingefroren.sha256   Prüfsummen des eingefrorenen Materials
  referenz/
    referenzwerte.csv    menschliche Vergleichswerte im Standardformat
    rohdaten/            Rohdaten der Vergleichsstudien (nicht versioniert)
  skripte/               Aufbereitung der Referenzdaten, Zusatzprüfungen
  laeufe/                Rohprotokolle und Manifeste (nicht versioniert)
  ergebnisse/            Tabellen und Abbildungen je Lauf
```

## 1 · Spezifikation

### Aufgaben (`items.yaml`)

Je Aufgabe ein Eintrag mit Quelle, optionalem Einleitungstext, Frage und den
beiden Bedingungen. Jede Bedingung nennt die beiden Optionen und kann einen
eigenen Vorspann haben.

```yaml
asian_disease:
  source: "Many Labs 1 (Klein et al., 2014)"
  intro: "Imagine that the United States is preparing ..."
  question: "Which program would you choose?"
  frames:
    gain:
      sure:  "If this program is adopted, 200 people will be saved."
      risky: "If this program is adopted, there is 1/3 probability ..."
    loss:
      sure:  "If this program is adopted, 400 people will die."
      risky: "..."
```

Gemessen wird der Anteil der Wahlen der Option `sure` in jeder Bedingung.

### Personenbeschreibungen

Detailstufen mit je mehreren Formulierungsvarianten. Die Stufe ohne
Beschreibung (`has_variants: false`) ist die Baseline.

```yaml
active_variants: [a, b, c, d]
levels:
  S0: {label: "...", has_variants: false, template: null}
  S1: {label: "...", has_variants: true, variants: {a: "You are 27 and ...", ...}}
  ...
response_instruction: "Answer with exactly one letter, either A or B, and nothing else."
```

Die Varianten einer Stufe sind keine eigene Bedingung, sondern eine Kontrolle:
Streut das Ergebnis zwischen ihnen, hängt es am Wortlaut, nicht am Detailgrad.
Stufen und Varianten sind frei benennbar; die Reihenfolge in der Datei ist die
Reihenfolge von wenig zu viel Detail.

### Erzeugung der Beschreibungen (`generate_personas.py`)

Die Beschreibungen können von Hand geschrieben oder von einem Modell erzeugt
werden. Der Generator arbeitet verschachtelt: Er erzeugt zuerst die
ausführlichste Stufe für alle Personen in einem Aufruf und leitet die kürzeren
Stufen daraus ab. So beschreibt eine Variante auf allen Stufen dieselbe Person,
und es variiert allein die Menge an Detail.

Jeder Entwurf wird maschinell geprüft und bei einem Verstoss verworfen:
Wortzahl im Rahmen der Stufe, keine verbotenen Begriffe (Risiko, Geld,
Sicherheit …), keine Eigenschaftszuschreibungen („You tend to …“), keine
Handlungen, die Sorgfalt zeigen (Prüfen, Aufschreiben …), auf der niedrigsten
Stufe nichts ausser Alter, Beruf und Art der Arbeitsstätte. Jeder Versuch
wird samt Text und Ablehnungsgrund protokolliert (`personas_generated.log.json`).
Danach wird die Datei gelesen und eingefroren; zur Laufzeit wird nichts
erzeugt.

### Einfrieren

`material/eingefroren.sha256` enthält die Prüfsummen von Aufgaben- und
Personendatei. Die Testsuite prüft sie, und `laufinfo.py` lässt einen
bezahlten Lauf nur zu, wenn sie stimmen und in `src/` und im Material keine
ungespeicherten Änderungen liegen.

## 2 · Versuchsplan (`design.py`)

Eine **Zelle** ist eine Kombination aus Aufgabe × Bedingung × Stufe ×
Variante. Bei zwei Bedingungen, einer Baseline und drei Stufen mit vier
Varianten sind das 2 × (1 + 3 × 4) = 26 Zellen je Aufgabe.

Der Umfang `n` gilt **je Stufe und Bedingung** und wird auf die Varianten der
Stufe verteilt (bei 910 und vier Varianten: 228, 228, 227, 227). Die Baseline
erhält damit denselben Umfang wie jede andere Stufe. Mit `--je-zelle` gilt
`n` stattdessen je Zelle, was für Pilotläufe handlich ist.

Innerhalb jeder Zelle steht die Zieloption in genau der Hälfte der
Durchläufe an erster Stelle; die Reihenfolge wird mit einem festen Startwert
gemischt. Derselbe Startwert ergibt denselben Plan.

**Ein Prompt** ist eine einzige Nachricht aus: Personenbeschreibung (entfällt
bei der Baseline), Einleitung, Vorspann, den Optionen A und B, Frage,
Antwortanweisung — durch Leerzeilen getrennt. Eine Rollenanweisung wie
„Stell dir vor, du bist diese Person“ fehlt bewusst: Es gäbe sie nur auf den
Stufen mit Beschreibung, und Baseline und erste Stufe unterschieden sich dann
in zwei Dingen.

## 3 · Ausführung

### Einzelaufrufe (`runner.py`)

Parallel über einen Thread-Pool, mit Wiederholung bei Ratenbegrenzung und
Überlastung (exponentielles Warten). Ein Fehlschlag stoppt den Lauf nicht,
sondern wird als Fehler protokolliert. **Fortsetzbar:** Wird derselbe Befehl
mit derselben Ausgabedatei erneut gestartet, überspringt er alle bereits
erfolgreich beantworteten Durchläufe.

Anbieter: Anthropic, OpenAI (Reasoning abgeschaltet, damit Temperatur gilt),
Mock (zieht Antworten aus einem logistischen Modell mit bekannten Parametern,
damit sich prüfen lässt, ob die Auswertung sie zurückgewinnt).

### Stapelverarbeitung (`runner_batch.py`)

Für grosse Läufe bei Anthropic, zum halben Preis und ohne Ratenbegrenzung.

```
submit       Versuchsplan erzeugen, Anfragen einreichen, Manifest schreiben
status       Verarbeitungsstand aller Batches
fetch        Ergebnisse abholen, über custom_id den Durchläufen zuordnen
nachreichen  fehlgeschlagene oder abgelaufene Anfragen erneut einreichen
```

Die Ergebnisse kommen in beliebiger Reihenfolge; zugeordnet wird über die
`custom_id` (`<aufgabe>-<bedingung>-<stufe>-<variante>-<durchlauf>`, nur
`[A-Za-z0-9_-]`, höchstens 64 Zeichen). Das Manifest hält die
Optionsreihenfolge jedes Durchlaufs fest. Nach `nachreichen` führt `fetch`
alle Batches zusammen; ein erfolgreiches Ergebnis hat Vorrang.
`submit --nur 8` reicht je eine Anfrage aus acht Zellen ein, als Vorabprüfung.

### Rohdatenformat (JSON Lines)

Erste Zeile: Meta-Angaben des Laufs.

```json
{"_meta": {"provider": "anthropic", "model_id": "claude-haiku-4-5-20251001",
  "temperature": 1.0, "n_per_cell": 910, "n_gilt_je": "Stufe und Rahmung",
  "seed": 20260828, "started_utc": "...",
  "material": {"experiment": "framing", "personas_datei": "personas_generated.yaml",
               "dateien": {"personas_generated.yaml": {"sha256": "...", "eingefroren": true}, ...}},
  "git": {"commit": "...", "aenderungen_offen": false},
  "pakete": {"anthropic": "1.8.0", ...}}}
```

Danach eine Zeile je Durchlauf:

```json
{"cell_id": "asian_disease|loss|S1|b", "item": "asian_disease", "frame": "loss",
 "spec_level": "S1", "variant": "b", "replicate": 17, "sure_option": "B",
 "model_id": "...", "temperature": 1.0, "ts_utc": "...", "error": null,
 "raw_text": "B", "stop_reason": "end_turn", "input_tokens": 168, "output_tokens": 1,
 "served_model": "claude-haiku-4-5-20251001"}
```

Der Prompt selbst wird nicht gespeichert; er ist aus Material und Startwert
exakt reproduzierbar.

## 4 · Auslegung (`parse.py`)

Jede Rohantwort fällt in eine von drei Klassen: Zieloption, andere Option,
nicht auswertbar. Formatierungsreste (Codeblöcke, Sternchen, „Option A“)
werden toleriert. Nennt eine Antwort beide Buchstaben, ist sie nicht
auswertbar. Im Fliesstext zählt nur ein grossgeschriebenes, freistehendes A
oder B, weil der Artikel „a“ sonst als Wahl gelesen würde: Eine verworfene
gültige Antwort ist der harmlosere Fehler als eine erfundene Wahl.

Ausgabe: `<lauf>.parsed.csv` mit einer Zeile je Durchlauf.

## 5 · Auswertung

Ein Werkzeug für alles: Anteile, deren Differenzen und 95-%-Intervalle. Keine
Signifikanztests, keine Effektstärken, keine Modelle. Ein Intervall, das die
Null nicht einschliesst, sagt dasselbe wie ein Test; einen Abstand beschreibt
eine Zahl mit Intervall direkter.

| Grösse | Rechnung |
|---|---|
| Anteil p | Wahlen der Zieloption / auswertbare Antworten, je Stufe und Bedingung; Intervall nach Wilson |
| Effekt Δ | p(gain) − p(loss); Intervall nach Newcombe |
| Abstand | Δ(Modell) − Δ(Mensch); Standardfehler √(se²(Modell) + se²(Mensch)) |
| klein | Intervall des Abstands liegt ganz innerhalb ± Relevanzgrenze |
| Sättigung | erste Stufe, ab der sich der Abstand von Stufe zu Stufe um weniger als die Relevanzgrenze ändert |
| Modellvergleich | Δ(A) − Δ(B) je Stufe; Standardfehler √(se²(A) + se²(B)) |

Wilson und Newcombe statt der Normalapproximation, weil Personenbedingungen
Anteile nahe 0 oder 1 erzeugen können, wo die einfache Formel versagt.

Kontrollen (`analyze.py`):

- **Positionsbias** — Anteil der Zieloption vorn gegen hinten.
- **Formulierungen** — Spannweite von Δ über die Varianten einer Stufe.
- **Nicht auswertbare Antworten** — Anteil je Stufe und Bedingung, API-Fehler
  getrennt. Über der Schwelle aus `experiment.yaml` zusätzlich die Grenzen von
  Δ, wenn alle ungültigen sicher bzw. riskant gewesen wären.

Experimentspezifische Prüfungen stehen in `skripte/` des Experiments und
werden in `experiment.yaml` unter `pruefungen` eingetragen.

### Referenzwerte (`referenz.py`)

Das Framework liest eine Zeile je Aufgabe:

```
aufgabe, quelle, design, n, p_gain, p_loss, delta, se
```

Wie diese Werte aus den Rohdaten einer Studie entstehen (Spiegelung von
Optionen, gepaarte oder unabhängige Stichproben), regeln die Skripte des
Experiments.

### Stichprobenumfang (`power.py`)

`n` folgt aus der gewünschten Genauigkeit des Abstands, nicht aus einem Test.
Die Unsicherheit der menschlichen Referenz setzt eine Untergrenze, die sich
durch mehr Modellaufrufe nicht unterschreiten lässt.

### Ausgabe

`analyze.py` schreibt je Lauf nach `ergebnisse/<lauf>/`: `stufen_*.csv`,
`varianten_*.csv`, `ungueltig_*.csv`, `positionsbias_*.csv`.
`compare.py` schreibt `vergleich_*.csv`, `abbildungen.py` zwei Abbildungen
als SVG und PNG (300 dpi), `tabellen.py` die Referenzwerte und den
Versuchsplan.

## Qualitätssicherung

Fehler in der Auswertung erzeugen keine Fehlermeldung, sondern plausibel
aussehende Zahlen. Die Testsuite prüft deshalb gegen Werte, die von aussen
bekannt sind:

- **Design** — Zellzahl folgt der Konfiguration, Baseline ohne Beschreibung,
  Position exakt hälftig, Umfang je Stufe exakt, Plan reproduzierbar.
- **Material** — Prüfsummen unverändert, ein vollständiger Prompt Zeichen für
  Zeichen.
- **Generator** — die Prüfregeln fangen bekannte Verstösse ab und lassen
  zulässige Texte durch.
- **Parser** — gültige und ungültige Antwortformen.
- **Statistik** — Intervalle gegen publizierte Werte (Tversky & Kahneman,
  1981; Many Labs 1).
- **Auswertung** — Mock-Parameter werden zurückgewonnen, eine eingebaute
  Differenz wird gefunden, Sättigungsregel, Grenzen bei ungültigen Antworten.
- **Stapelverarbeitung** — `custom_id` gültig, eindeutig und umkehrbar;
  nachgereichte Ergebnisse haben Vorrang.

Die Suite prüft das Framework immer am Beispiel `framing`, unabhängig vom
aktiven Experiment; ein eigener Test lässt zusätzlich die Vorlage
`experiments/vorlage` mit drei Stufen und zwei Varianten durchlaufen. Die
mitgelieferte GitHub-Konfiguration (`.github/workflows/tests.yml`) führt die
Suite bei jedem Push aus, mit zwei verschiedenen Personendateien.

## Reproduktion

```bash
./run_pipeline.sh                                  # Generalprobe, ohne API
./run_pipeline.sh daten <a>.jsonl <b>.jsonl        # aus vorhandenen Rohdaten
REFERENZ_NEU=1 ./run_pipeline.sh ...               # Referenzwerte neu berechnen
```

Aus den Rohdaten, dem Material und dem Code-Stand in der Meta-Zeile lässt sich
jede Zahl und jede Abbildung neu erzeugen.
