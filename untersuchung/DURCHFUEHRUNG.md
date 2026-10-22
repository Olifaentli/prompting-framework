# Durchführungsprotokoll

Was bei der Erhebung tatsächlich geschah, in zeitlicher Reihenfolge. Alle
Zeiten in UTC. Die Meta-Zeile jeder Rohdatei hält Material, Code-Stand und
Bibliotheksversionen zusätzlich maschinenlesbar fest.

## Vor der Erhebung

| Datum | Ereignis |
|---|---|
| 03.10.2026 | Erster Satz Personenbeschreibungen erzeugt (gpt-6-luna). Beim Lesen verworfen: Alle vier S3-Episoden zeigten Prüfen und Aufschreiben (Hinweis auf Gewissenhaftigkeit), eine S1-Beschreibung enthielt den Haushalt. |
| 09.10.2026 | Generator um zwei Prüfungen ergänzt, Satz neu erzeugt (11 Versuche, 2 wegen der Länge verworfen), gelesen und eingefroren. |
| 09.10.2026 | Analyseplan festgeschrieben (`ANALYSEPLAN.md`), bevor echte Daten erhoben wurden. |

## Vorabprüfung, 09.10.2026

| Zeit | Prüfung | Ergebnis |
|---|---|---|
| 11:19 | Luna, je ein Aufruf Gewinn/Verlust auf S0 | Temperatur angenommen, Reasoning abgeschaltet, Antwort im Format, ausgeliefert `gpt-6-luna`, kein `system_fingerprint` |
| 11:19 | Haiku, dasselbe | **Fehlgeschlagen** in der Bibliothek: `anthropic` 1.8.0 kennt `temperature` nicht mehr als Argument. Die Sperre für vollständig fehlgeschlagene Läufe brach ohne Kosten ab. Behoben: Temperatur über den Anfrageinhalt (`extra_body`); ein Test prüft seither den gesendeten Inhalt. In der Stapelverarbeitung kam sie bereits an. |
| 11:21 | Haiku, erneut | Antwort im Format, ausgeliefert `claude-haiku-4-5-20251001` |
| 11:22 | Modellliste OpenAI | Keine datierte Kennung für Luna (`gpt-6-luna`, `gpt-5.6-luna`). Die ausgelieferte Version wird je Antwort protokolliert. |
| 11:22 | Mini-Stapel Haiku, 8 Anfragen aus 8 Zellen | Eingereicht, `custom_id`-Format angenommen. Beim Abfragen fiel auf, dass `status` und `fetch` die `.env` nicht lasen; behoben. Danach abgeholt: 8 von 8 erfolgreich, jede Antwort der richtigen Zelle und Optionsreihenfolge zugeordnet, ausgeliefert `claude-haiku-4-5-20251001`. |

## Pilot, 09.10.2026

50 Durchläufe je Stufe und Rahmung, beide Aufgaben, 800 Aufrufe je Modell.
Beurteilt nur nach den vorab festgelegten technischen Kriterien; die
Pilotdaten gehen nicht in die Auswertung ein.

| | Haiku | Luna | Kriterium |
|---|---|---|---|
| Beginn | 11:22 | 11:23 | |
| API-Fehler | 0 % | 0 % | < 1 % |
| Auswertbare Antworten | 100 % | 100 % | ≥ 95 % |
| Abbruchgrund | 800 × `end_turn` | 800 × `stop` | unauffällig |
| Eingabetoken je Aufruf | 170 | 155 | geschätzt 167 |
| Kosten | 0,15 $ | 0,01 $ | |
| Vollständigkeit | vollständig | vollständig | |

Alle Kriterien erfüllt; Hauptlauf ohne Änderung freigegeben.

## Hauptlauf

| | Haiku | Luna |
|---|---|---|
| Weg | Stapelverarbeitung | Einzelaufrufe |
| Beginn | 09.10.2026, 11:27 (Batch `msgbatch_01KZRz4ziTGoBhcx2F9WXFEt`) | 09.10.2026, 11:25 |
| Ende | 09.10.2026, 11:44 (abgeholt) | 09.10.2026, 11:56 (1.885 s) |
| Aufrufe | 14.560 von 14.560 erfolgreich | 14.558 von 14.560 erfolgreich |
| Fehlversuche, nachgereicht | 0 | 2, nicht nachgefragt (siehe unten) |
| Ausgelieferte Version | durchgehend `claude-haiku-4-5-20251001` | durchgehend `gpt-6-luna`, kein `system_fingerprint` |
| Kosten | 1,38 $ (2.475.196 Token ein, 58.240 aus, Batch-Preis) | 0,26 $ (2.259.132 Token ein, 58.232 aus) |
| Vollständigkeit | vollständig; 0 % nicht auswertbar | 2 Durchläufe ohne Antwort, sonst vollständig; 0 % nicht auswertbar |

Code-Stand: Luna lief auf `92014b1`, Haiku auf `e1493b8`. Dazwischen änderten
sich nur die Abfrage des Stapelstands und eine neue Prüfung, nicht der Weg
eines Prompts zum Modell.

### Zwei Luna-Antworten über der Längengrenze

`asian_disease|gain|S2|a`, Durchläufe 27 und 190 (11:29). OpenAI meldete
`400: Could not finish the message because max_tokens or model output limit
was reached`. Luna wollte also länger antworten als die erlaubten 8 Token —
mehr als den einen verlangten Buchstaben. Anthropic liefert in so einem Fall
eine abgeschnittene Antwort, OpenAI einen Fehler.

Inhaltlich ist das keine Verbindungsstörung, sondern eine Antwort, die das
Format nicht einhält. Die beiden Durchläufe wurden deshalb **nicht erneut
gefragt**: Eine Wiederholung ersetzte zwei formwidrige Antworten durch neue
Ziehungen. Nach der Erhebung entschieden (09.10.2026): Sie zählen als nicht
auswertbar, nicht als API-Fehler (Regel in `src/parse.py`). In den Anteilen
fehlen sie so oder so; die Vollständigkeitsprüfung führt sie als beantwortet.

## Sicherung

Rohdaten, Manifest, Pilot und Vorabprüfung als `laeufe/rohdaten_hauptlauf.zip`
(0,27 MB), Prüfsummen in `ROHDATEN.sha256`; nach dem Packen gegengeprüft.
