"""Prueft, ob ein Lauf vollstaendig und sauber ist, bevor er ausgewertet wird.

Aus Umfang und Startwert in der Meta-Zeile laesst sich exakt nachrechnen,
welche Durchlaeufe es geben muss. Geprueft wird:

  - jeder geplante Durchlauf ist genau einmal erfolgreich beantwortet
  - die Optionsreihenfolge jedes Durchlaufs stimmt mit dem Plan ueberein
  - in jeder Zelle steht die Zieloption genau zur Haelfte vorn
  - das Material war eingefroren, der Code gespeichert
  - die ausgelieferte Modellversion ist ueber den Lauf gleich geblieben

Fehlgeschlagene Versuche, die spaeter erfolgreich wiederholt wurden (Fortsetzen
bei Einzelaufrufen, Nachreichen bei der Stapelverarbeitung), zaehlen nicht als
Fehler.

Aufruf: python src/vollstaendigkeit.py experiments/<name>/laeufe/<lauf>.jsonl
Endet mit Code 1, wenn etwas nicht stimmt.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from design import generate_trials
from parse import ist_antwort, laengengrenze


def lesen(pfad: Path) -> tuple[dict, list[dict]]:
    meta, saetze = {}, []
    with pfad.open(encoding="utf-8") as fh:
        for zeile in fh:
            r = json.loads(zeile)
            if "_meta" in r:
                meta = r["_meta"]          # bei Fortsetzungen gilt die letzte
            else:
                saetze.append(r)
    return meta, saetze


def pruefen(meta: dict, saetze: list[dict], item: str | None = None) -> list[str]:
    """Gibt die Liste der Befunde zurueck; leer heisst vollstaendig."""
    befunde = []
    je_stufe = meta.get("n_gilt_je", "Stufe und Rahmung") != "Zelle"
    plan = {(t.cell_id, t.replicate): t.sure_option
            for t in generate_trials(meta["n_per_cell"], seed=meta["seed"],
                                     only_item=item, je_stufe=je_stufe)}

    # Als beantwortet gilt auch eine Antwort ueber der Laengengrenze: Das Modell
    # hat geantwortet, nur nicht im Format. Sie ist nicht auswertbar, fehlt aber nicht.
    erfolgreich: dict = defaultdict(list)
    fehlversuche = zu_lang = 0
    for r in saetze:
        schluessel = (r["cell_id"], r["replicate"])
        if ist_antwort(r):
            erfolgreich[schluessel].append(r)
            zu_lang += laengengrenze(r.get("error"))
        else:
            fehlversuche += 1

    fehlend = [k for k in plan if k not in erfolgreich]
    doppelt = [k for k, v in erfolgreich.items() if len(v) > 1]
    fremd = [k for k in erfolgreich if k not in plan]
    falsche_position = [k for k, v in erfolgreich.items()
                        if k in plan and v[0]["sure_option"] != plan[k]]
    if fehlend:
        befunde.append(f"{len(fehlend)} geplante Durchlaeufe fehlen, z. B. {fehlend[:3]}")
    if doppelt:
        befunde.append(f"{len(doppelt)} Durchlaeufe mehrfach beantwortet, z. B. {doppelt[:3]}")
    if fremd:
        befunde.append(f"{len(fremd)} Durchlaeufe nicht im Plan, z. B. {fremd[:3]}")
    if falsche_position:
        befunde.append(f"{len(falsche_position)} Durchlaeufe mit anderer Optionsreihenfolge als geplant")

    # Exakte Haelftigkeit je Zelle, gemessen an den tatsaechlich vorhandenen Antworten.
    position: dict = defaultdict(Counter)
    for (zelle, _), v in erfolgreich.items():
        position[zelle][v[0]["sure_option"]] += 1
    schief = [z for z, c in position.items() if abs(c["A"] - c["B"]) > 1]
    if schief:
        befunde.append(f"{len(schief)} Zellen nicht haelftig balanciert, z. B. {schief[:3]}")

    material = meta.get("material") or {}
    nicht_eingefroren = [n for n, d in (material.get("dateien") or {}).items()
                         if not d.get("eingefroren")]
    if not material:
        befunde.append("Meta-Zeile ohne Angaben zum Material")
    elif nicht_eingefroren:
        befunde.append(f"Material nicht eingefroren: {', '.join(nicht_eingefroren)}")
    if (meta.get("git") or {}).get("aenderungen_offen"):
        befunde.append("Lauf mit ungespeicherten Aenderungen am Code oder Material")

    versionen = Counter(v[0].get("served_model") for v in erfolgreich.values()
                        if v[0].get("served_model") is not None)
    if len(versionen) > 1:
        befunde.append(f"Ausgelieferte Modellversion wechselte im Lauf: {dict(versionen)}")

    pruefen.statistik = {
        "geplant": len(plan), "erfolgreich": len(erfolgreich),
        "fehlversuche_wiederholt": fehlversuche, "zellen": len(position),
        "ueber_laengengrenze": zu_lang,
        "versionen": dict(versionen),
    }
    return befunde


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--item", default=None, help="falls der Lauf nur eine Aufgabe umfasste")
    args = ap.parse_args()

    pfad = Path(args.jsonl).resolve()
    meta, saetze = lesen(pfad)
    if not meta:
        raise SystemExit(f"{pfad.name}: keine Meta-Zeile.")
    befunde = pruefen(meta, saetze, args.item)
    s = pruefen.statistik
    print(f"Lauf: {pfad.name} | Modell: {meta.get('model_id')} | Temperatur: {meta.get('temperature')}")
    print(f"Geplant {s['geplant']:,}, erfolgreich beantwortet {s['erfolgreich']:,} "
          f"in {s['zellen']} Zellen; wiederholte Fehlversuche: {s['fehlversuche_wiederholt']}")
    print(f"Ausgelieferte Version: {s['versionen']}")
    if s["ueber_laengengrenze"]:
        print(f"Antworten ueber der Laengengrenze (nicht auswertbar, nicht fehlend): "
              f"{s['ueber_laengengrenze']}")
    if befunde:
        print("\nNICHT VOLLSTAENDIG:")
        for b in befunde:
            print(f"  - {b}")
        raise SystemExit(1)
    print("\nVollstaendig: jeder geplante Durchlauf genau einmal, Reihenfolge wie geplant,")
    print("jede Zelle haelftig balanciert, Material eingefroren, Code gespeichert.")


if __name__ == "__main__":
    main()
