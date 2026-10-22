# Analyseplan

Festgelegt am 09.10.2026, vor der Erhebung der echten Daten. Jede spätere
Änderung wird bei den Ergebnissen als Abweichung ausgewiesen.

## Material und Durchführung

- **Material eingefroren** (Prüfsummen in `material/eingefroren.sha256`):
  Personenbeschreibungen, Aufgabentexte und der Zusammenbau des Prompts. Ein bezahlter Lauf bricht ab, wenn eines davon
  abweicht.
- **Versuchsplan:** 2 Aufgaben × 2 Rahmungen × 4 Detailstufen (S0–S3). Ab S1 je
  vier Formulierungsvarianten als Kontrolle, nicht als Bedingung.
  910 Durchläufe je Stufe und Rahmung, auf die Varianten verteilt;
  Optionsposition genau zur Hälfte vertauscht. 14.560 Aufrufe je Modell.
- **Modelle:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, Batch-API) und
  GPT-6 Luna (`gpt-6-luna`, `reasoning_effort="none"`, Einzelaufrufe).
  Temperatur 1,0, höchstens 8 Ausgabetoken.

## Kennzahlen

Ein Werkzeug für alles: Anteile, deren Differenzen und 95-%-Intervalle
(Wilson für Anteile, Newcombe für Differenzen). Keine Signifikanztests, keine
Effektstärken, keine Modelle.

- **Anteil sicher:** Anteil der Wahlen der sicheren Option, je Stufe und
  Rahmung, über alle Varianten der Stufe.
- **Framing-Effekt Δ:** Anteil sicher unter Gewinn minus unter Verlust.
- **Abstand:** Δ des Modells minus Δ der menschlichen Referenz. Many Labs 1
  (0,287) für das Asian-Disease-Problem, Ruggeri et al. (0,359) für die
  Geldbeträge. Das Intervall des Abstands berücksichtigt die Unsicherheit
  beider Seiten.
- **Relevanzgrenze 0,10.** Ein Abstand gilt als *klein*, wenn sein
  Intervall vollständig innerhalb von ±0,10 liegt.

## Unterfragen

- **UF1 — Framing-Effekt in Richtung und Stärke, auch bei der weniger
  bekannten Aufgabe:** Δ auf S0 je Aufgabe und Modell. Schliesst das
  Intervall die Null nicht ein und ist Δ positiv, zeigt das Modell den Effekt
  in menschlicher Richtung. Die Stärke beschreibt der Abstand.
- **UF2 — Verbessert mehr Detail die Übereinstimmung, gibt es eine
  Sättigung?** Abstand je Stufe. Mehr Detail verbessert die Übereinstimmung,
  wenn der Betrag des Abstands mit der Stufe sinkt.
  *Sättigung:* die erste Stufe, ab der sich der Abstand von Stufe zu Stufe
  um weniger als 0,10 ändert, abgelesen an den Punktwerten. Ohne eigene
  Kennzahl; ob die Änderungen belastbar sind, zeigen die Intervalle der
  einzelnen Stufen.
- **UF3 — Unterscheiden sich die Modellfamilien?** Δ_Haiku − Δ_Luna je Stufe
  und Aufgabe mit Intervall. Liegt das Intervall innerhalb von ±0,10, gilt der
  Unterschied als nicht relevant.

## Kontrollen

- **Positionsbias:** Anteil sicher bei sicherer Option vorn gegen hinten, als
  Differenz mit Intervall.
- **Formulierungen:** Spannweite von Δ über die vier Varianten einer Stufe.
  Eine grosse Spannweite heisst: Das Ergebnis hängt am Wortlaut.
- **Nicht auswertbare Antworten:** Anteil je Stufe und Rahmung, API-Fehler
  getrennt. Sie gehen nicht in die Anteile ein. Liegt ihr Anteil in einer
  Zelle über 5 %, wird zusätzlich gezeigt, zwischen welchen Werten Δ läge,
  wenn alle sicher bzw. riskant gewesen wären.
- **Kontamination:** Liegt das Modell auf S0 näher an den Originalwerten
  (Tversky & Kahneman, 1981) oder an der Replikation (Many Labs 1)? Und tritt
  der Effekt auch bei der weniger bekannten Aufgabe auf? Beides sind Hinweise,
  keine Beweise.

## Pilot und Abweichungen

- **Pilot:** 50 Durchläufe je Stufe und Rahmung, beide Modelle, beide
  Aufgaben. Rein technische Kriterien: API-Fehler unter 1 %, mindestens 95 %
  auswertbare Antworten, Token wie geschätzt. Effektgrössen werden nicht
  angesehen; Pilotdaten gehen nicht in die Auswertung ein. Sind die Kriterien
  erfüllt, folgt der Hauptlauf ohne weitere Änderung.
- **Parser:** Muss die Auslegung der Antworten nach der Erhebung angepasst
  werden, geschieht das auf den unveränderten Rohdaten und wird als
  Abweichung berichtet. Die Kriterien oben bleiben unverändert.
- **Explorativ:** Alles, was hier nicht steht, wird im Text als explorativ
  gekennzeichnet.

## Umsetzung

`./run_pipeline.sh daten <haiku>.jsonl <luna>.jsonl` (im Ordner `framework/`)
erzeugt aus den Rohdaten alle Kennzahlen, Tabellen und Abbildungen. Code:
`src/analyze.py` (UF1, UF2, Kontrollen), `src/compare.py` (UF3),
`skripte/kontamination.py` (dieses Experiment), `src/abbildungen.py`,
`src/tabellen.py`.
