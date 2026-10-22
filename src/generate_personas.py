"""Erzeugt die Personenbeschreibungen mit einem Sprachmodell.

Sechste Komponente des Frameworks. Sie loest ein konkretes Problem: Werden die
Beschreibungen von Hand geschrieben, laesst sich einwenden, das Ergebnis haenge
an diesen besonderen Formulierungen. Mit einem Generator sind viele Varianten je
Stufe moeglich, und das Ergebnis kann als Spannweite ueber Formulierungen
berichtet werden, wie Sclar et al. (2024) es fordern.

Drei Vorkehrungen gegen die naheliegenden Einwaende:

  1. KREUZWEISE ERZEUGUNG
     Das erzeugende Modell gehoert einer anderen Anbieterfamilie als das
     getestete. Sonst koennte ein Modell seine eigene Ausdrucksweise besser
     verstehen als eine fremde.

  2. EINFRIEREN
     Die Beschreibungen werden einmal erzeugt und als Datei festgeschrieben,
     nicht waehrend des Experiments erzeugt. Sie sind Material, nicht
     Programmlogik, und werden vollstaendig dokumentiert (src/material.py).

  3. PRUEFUNG
     Jede Beschreibung wird gegen die Vorgaben geprueft: Wortzahl im Rahmen,
     keine risikobezogenen Begriffe, geforderte Inhalte vorhanden. Was durchfaellt,
     wird verworfen und neu erzeugt.

Aufruf:
    python src/generate_personas.py --provider mock --n 8
    python src/generate_personas.py --provider openai --model luna --n 8
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zugang
import models as model_registry

import experiment

ROOT = Path(__file__).resolve().parent.parent

# Begriffe, die keine Beschreibung enthalten darf. Dieselbe Liste prueft die
# Testsuite; sie ist die operationale Fassung der Designbedingung.
VERBOTEN = re.compile(
    # Wortgrenze an BEIDEN Enden. Ohne die hintere Grenze schlug "bet" in
    # "between" an und "invest" in "investigate" - gueltige Beschreibungen
    # waeren verworfen und als Regelverstoss des Modells berichtet worden.
    r"\b("
    r"risk|risks|risky|riskier|riskiest|"
    r"cautious|cautiously|caution|careful|carefully|"
    r"bold|boldly|boldness|adventurous|adventure|adventures|"
    r"gamble|gambles|gambling|gambler|"
    r"insurance|insure|insured|"
    r"invest|invests|investing|invested|investment|investments|"
    r"lottery|lotteries|bet|bets|betting|stake|stakes|"
    r"danger|dangers|dangerous|thrill|thrills|thrilling|"
    r"safe|safely|safety|unsafe|secure|securely|security|hazard|hazardous|"
    r"timid|daring|reckless|prudent|prudence|"
    # Eigenschaftswoerter, die mit Risikoneigung zusammenhaengen
    r"tidy|tidily|meticulous|orderly|spontaneous|impulsive|"
    r"punctual|reliable|conscientious|methodical|thorough|disciplined"
    r")\b", re.I)

# Angaben zur Wortzahl, die Modelle in die Ausgabe schreiben, wenn man sie zum
# Zaehlen auffordert. Sie muessen verworfen werden, und zwar aus zwei Gruenden:
# Sie landeten sonst im Prompt des Experiments, und sie blaehen die gemessene
# Wortzahl auf, sodass zu kurze Beschreibungen die Pruefung bestehen.
ZAEHLANGABE = re.compile(
    r"\(?\s*(?:word count\s*[:=]?\s*\d+|\d+\s*words?)\s*\)?\.?\s*$|"
    r"\(\s*\d+\s*words?\s*\)|word count\s*[:=]\s*\d+", re.I)

# Wendungen, mit denen Eigenschaften zugeschrieben werden. Sie sind das
# eigentliche Einfallstor: "You tend to keep your desk tidy" ist eine
# Eigenschaft, "you organize appointments" eine Taetigkeit. Verboten sind
# daher die Wendungen, nicht das Berufsvokabular.
DISPOSITION = re.compile(
    r"\byou (?:tend to|always|never|usually prefer|prefer|like to|enjoy|"
    r"are the (?:kind|sort) of)", re.I)

# Handlungen, die Sorgfalt zeigen, ohne sie zu benennen. Der erste erzeugte Satz
# enthielt in allen vier S3-Episoden Pruefen, Nachtesten und Aufschreiben. Das
# legt Gewissenhaftigkeit nahe, und Gewissenhaftigkeit haengt mit Risikoscheu
# zusammen. S3 haette dann neben mehr Detail auch eine Disposition
# mitgeliefert - genau die Vermischung, die das Design ausschliesst.
SORGFALT = re.compile(
    r"\b("
    r"check|checks|checked|checking|double-check|double-checks|double-checked|"
    r"verify|verifies|verified|verifying|"
    r"test|tests|tested|testing|retest|retests|retested|retesting|"
    r"repeat|repeats|repeated|repeating|"
    r"record|records|recorded|recording|log|logs|logged|logging|logbook|"
    r"notebook|notebooks|notes|checklist|checklists|list|lists|"
    r"calendar|calendars|planner|plan|plans|planned|planning|"
    r"schedule|schedules|scheduled|"
    r"organize|organizes|organized|organizing|organise|organises|organised|organising|"
    r"correct|corrects|corrected|correcting|mistake|mistakes|error|errors|"
    r"fix|fixes|fixed|fixing|repair|repairs|repaired|repairing|"
    r"solve|solves|solved|solving|problem|problems|"
    r"precise|precisely|exact|exactly|accurate|accurately|"
    r"write down|writes down|wrote down|writing down|jot|jots|jotted"
    r")\b", re.I)

# S1 heisst "Alter und Beruf". Im ersten Satz trug S1d zusaetzlich den
# Haushalt - mehr Detail als die Stufe vorsieht.
UEBER_S1 = re.compile(
    r"\b(live|lives|living|lived|home|house|flat|apartment|cottage|room|"
    r"partner|husband|wife|child|children|son|daughter|sister|brother|"
    r"parent|parents|family|alone|married|single|neighbor|neighbors|"
    r"neighbour|neighbours|friend|friends)\b", re.I)

# Vorgaben je Stufe: Zielwortzahl, erlaubte Abweichung, geforderte Inhalte.
STUFEN = {
    "S1": dict(ziel=14, toleranz=4,
               inhalte="age and occupation",
               # Zum Beruf gehoert die Art der Arbeitsstaette, wie in den von
               # Hand geschriebenen S1 ("teach geography at a secondary school").
               # Ohne sie kuerzt das Modell auf sieben Woerter und verfehlt die
               # Stufe.
               zusatz=("Keep ONLY the age, the occupation and the kind of workplace. "
                       "Nothing about household, family, where the person lives or "
                       "their daily routine.")),
    "S2": dict(ziel=50, toleranz=8,
               inhalte="age, occupation, living situation, daily routine and social contacts",
               zusatz=""),
    "S3": dict(ziel=110, toleranz=15,
               inhalte=("age, occupation, living situation, daily routine, social contacts, "
                        "educational background, personal habits and one concrete recent episode"),
               zusatz=""),
}

AUFTRAG_PERSONEN = """Write {anzahl} descriptions of {anzahl} clearly DIFFERENT adult people,
for use in a psychology experiment. Address each person as "You".

Make them differ from one another in all of these:
- age (spread them across the range 25 to 60)
- field of work (use {anzahl} unrelated fields, not all office or clerical work)
- household (living alone, with a partner, with children, sharing a flat)
- kind of place (city, small town, village)

Each description: between {unten} and {oben} words.
Include for each: {inhalte}.

Write plain prose, one paragraph per person. No lists inside a description,
no headings, no quotation marks.

Do not mention or imply anything about risk, caution, courage, boldness, money,
savings, investments, insurance, gambling, betting, lotteries, safety or danger,
and no sport or hobby involving physical risk.

Do not attribute character traits. Write what the person does, not what kind of
person they are. Never write "You tend to", "You always", "You prefer" or
"You are the kind of person who".

Do not show carefulness or diligence through actions either. The recent episode
must be an ordinary event that simply happened, such as a visit, a conversation,
a change in the weather or something seen on the way. It must not show the
person checking, testing, verifying, correcting, repairing, planning, organizing,
solving a problem or writing something down. Habits must not involve notes,
lists, logs, records, notebooks or calendars. Describe the work by its field and
setting, not by routines of checking or recording.

Separate the {anzahl} descriptions with a line containing only ---
Do not state the word count anywhere. Return only the descriptions."""

AUFTRAG_KUERZEN = """Here is a description of a person:

{text}

Rewrite it as a SHORTER description of the SAME person,
between {unten} and {oben} words.
Keep: {inhalte}.
Leave out everything else. {zusatz}

Keep every fact you keep identical - same age, same occupation, same household.
Do not introduce anything new. Address the person as "You".
Write plain prose. Do not attribute character traits.

Do not state the word count. Return only the shortened description."""


def normiert(text: str) -> str:
    """Fuer den Vergleich auf Doppelungen: Grossschreibung und Leerraum egal."""
    return re.sub(r"[^a-z0-9 ]", "", " ".join(text.lower().split()))


def pruefe(text: str, stufe: str) -> list[str]:
    """Gibt die Liste der Regelverstoesse zurueck; leer heisst bestanden."""
    spec = STUFEN[stufe]
    fehler = []
    # Die Laenge wird am Text ohne etwaige Zaehlangabe gemessen, damit eine
    # solche Angabe die Pruefung nicht unterlaeuft.
    n = len(ZAEHLANGABE.sub("", text).split())
    if abs(n - spec["ziel"]) > spec["toleranz"]:
        fehler.append(f"Wortzahl {n}, erwartet {spec['ziel']} +/- {spec['toleranz']}")
    treffer = sorted(set(w.lower() for w in VERBOTEN.findall(text)))
    if treffer:
        fehler.append(f"verbotene Begriffe: {', '.join(treffer)}")
    disp = sorted(set(w.lower() for w in DISPOSITION.findall(text)))
    if disp:
        fehler.append(f"Eigenschaftszuschreibung: {', '.join(disp)}")
    sorgfalt = sorted(set(w.lower() for w in SORGFALT.findall(text)))
    if sorgfalt:
        fehler.append(f"Hinweis auf Sorgfalt: {', '.join(sorgfalt)}")
    if stufe == "S1":
        mehr = sorted(set(w.lower() for w in UEBER_S1.findall(text)))
        if mehr:
            fehler.append(f"mehr als Alter und Beruf: {', '.join(mehr)}")
    if ZAEHLANGABE.search(text):
        fehler.append("enthaelt eine Angabe zur Wortzahl")
    if not text.strip().lower().startswith("you"):
        fehler.append("beginnt nicht mit 'You'")
    if any(z in text for z in ('"', "\n-", "•")):
        fehler.append("enthaelt Aufzaehlung oder Anfuehrungszeichen")
    return fehler


class MockGenerator:
    """Erzeugt Beschreibungen ohne API, damit die Pruefkette testbar bleibt."""

    BERUFE = ["works in university administration", "teaches geography at a secondary school",
              "works as a translator for technical manuals", "is a pharmacist in a small clinic",
              "works in the archive of a regional museum", "coordinates deliveries for a bakery chain",
              "is a sound technician at a theatre", "works as a landscape surveyor",
              "teaches music at a community college", "manages a plant nursery"]
    ORTE = ["a mid-sized town", "the edge of a large city", "a village near the coast",
            "a suburb with allotment gardens", "an old quarter near the river"]
    ALLTAG = ["take the bus to work and read on the way",
              "drive to work and listen to podcasts",
              "cycle along the canal to work",
              "walk twenty minutes to work past the market"]
    EPISODEN = ["Last month you spent a weekend repainting the kitchen.",
                "Last week the lift in your building was out of order for three days.",
                "Last month you helped your neighbour move a wardrobe up two flights of stairs.",
                "Last week you finally replaced the broken handle on the garden gate."]

    def __init__(self, seed: int = 11):
        self.rng = random.Random(seed)

    def personen(self, anzahl: int) -> list[str]:
        out = []
        for i in range(anzahl):
            alter = 27 + i * 8
            beruf = self.BERUFE[i % len(self.BERUFE)]
            ort = self.ORTE[i % len(self.ORTE)]
            alltag = self.ALLTAG[i % len(self.ALLTAG)]
            out.append(
                f"You are {alter} years old and {beruf} in {ort}. You rent a flat "
                f"with a balcony on the third floor of an older building and "
                f"{alltag}. You studied at a technical college in a neighbouring "
                f"region and came into this work after a temporary contract became "
                f"permanent six years ago. Most evenings you cook at home with "
                f"the window open, and every other week you meet "
                f"two friends for dinner at the same restaurant near the station. "
                f"You water the plants on the balcony before breakfast and listen "
                f"to the radio while doing so. On Sunday afternoons you visit your "
                f"sister and her two children on the other side of town. "
                f"{self.EPISODEN[i % len(self.EPISODEN)]}")
        # Auf die Zielwortzahl trimmen. Der Mock soll die Kette durchlaufen,
        # nicht die Pruefung erproben.
        ziel = STUFEN["S3"]["ziel"]
        return [self._trimmen(t, ziel) for t in out]

    @staticmethod
    def _trimmen(text: str, ziel: int) -> str:
        w = text.split()
        if len(w) <= ziel:
            return text
        kurz = " ".join(w[:ziel]).rstrip(",.;")
        return kurz + "."

    def _kuerzen_auf(self, text: str, ziel: int) -> str:
        return self._trimmen(text, ziel)

    def kuerzen(self, text: str, stufe: str, bitte: int | None = None) -> str:
        return self._trimmen(text, STUFEN[stufe]["ziel"])


class ApiGenerator:
    """Erzeugt erst alle Personen auf der hoechsten Stufe, dann die Kuerzungen.

    So ist sichergestellt, dass Variante a auf allen Stufen dieselbe Person
    beschreibt. Wuerde je Stufe neu erzeugt, variierten Detailgrad und Person
    gemeinsam - und die unabhaengige Variable waere nicht mehr der Detailgrad.
    """

    def __init__(self, provider: str, spec, temperature: float = 1.0):
        self.spec, self.provider, self.temperature = spec, provider, temperature
        if provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic()
        else:
            from openai import OpenAI
            self.client = OpenAI()

    def _frage(self, prompt: str, max_tokens: int) -> str:
        if self.provider == "anthropic":
            # temperature ueber extra_body, siehe AnthropicProvider in runner.py.
            msg = self.client.messages.create(
                model=self.spec.model_id, max_tokens=max_tokens,
                extra_body={"temperature": self.temperature},
                messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in msg.content if b.type == "text").strip()
        kw = dict(model=self.spec.model_id, max_completion_tokens=max_tokens,
                  messages=[{"role": "user", "content": prompt}])
        if self.spec.supports_temperature:
            kw["reasoning_effort"] = "none"
            kw["temperature"] = self.temperature
        r = self.client.chat.completions.create(**kw)
        return (r.choices[0].message.content or "").strip()

    def personen(self, anzahl: int) -> list[str]:
        """Die vollstaendigen Beschreibungen, in einem Aufruf erzeugt."""
        spec = STUFEN["S3"]
        prompt = AUFTRAG_PERSONEN.format(
            anzahl=anzahl, inhalte=spec["inhalte"],
            unten=spec["ziel"] - spec["toleranz"] + 3,
            oben=spec["ziel"] + spec["toleranz"] - 3)
        roh = self._frage(prompt, 220 * anzahl + 400)
        return self._zerlegen(roh, anzahl)

    @staticmethod
    def _zerlegen(roh: str, anzahl: int) -> list[str]:
        """Zerlegt die Antwort in die einzelnen Beschreibungen.

        Modelle halten den vorgegebenen Trenner nicht zuverlaessig ein. Daher
        drei Wege in abnehmender Verlaesslichkeit: der Trenner, numerierte
        Absaetze, schliesslich Leerzeilen.
        """
        def putzen(t: str) -> str:
            t = re.sub(r"^\s*(?:\*\*)?(?:Person\s*)?\d+[.):\]]?\s*(?:\*\*)?\s*", "", t.strip())
            return re.sub(r"\s+", " ", t).strip()

        for kandidat in (
            [t for t in re.split(r"\n\s*-{3,}\s*\n", roh) if t.strip()],
            [t for t in re.split(r"\n(?=\s*(?:\*\*)?(?:Person\s*)?\d+[.):\]])", roh) if t.strip()],
            [t for t in re.split(r"\n\s*\n", roh) if t.strip()],
        ):
            teile = [putzen(t) for t in kandidat]
            teile = [t for t in teile if len(t.split()) > 20]
            if len(teile) == anzahl:
                return teile
        return [putzen(t) for t in re.split(r"\n\s*-{3,}\s*\n", roh) if t.strip()]

    def kuerzen(self, text: str, stufe: str, bitte: int | None = None) -> str:
        """Kuerzt auf die Stufe. `bitte` ueberschreibt die erbetene Wortzahl.

        Modelle ueberschreiten erbetene Laengen verlaesslich. Die aufrufende
        Schleife justiert daher nach, statt die Pruefung aufzuweichen.
        """
        spec = STUFEN[stufe]
        ziel = bitte if bitte is not None else spec["ziel"]
        prompt = AUFTRAG_KUERZEN.format(
            text=text, inhalte=spec["inhalte"], zusatz=spec["zusatz"],
            unten=max(3, ziel - 3), oben=ziel + 3)
        return self._frage(prompt, 400)



def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic", "openai"])
    ap.add_argument("--model", default="mock", help="Alias aus src/models.py")
    ap.add_argument("--n", type=int, default=8, help="Varianten je Stufe")
    ap.add_argument("--max-versuche", type=int, default=6,
                    help="Versuche je Variante, bevor abgebrochen wird")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    spec = model_registry.get(args.model)
    if args.provider != "mock":
        zugang.pruefen(args.provider)
    gen = (MockGenerator() if args.provider == "mock"
           else ApiGenerator(args.provider, spec))

    out = Path(args.out).resolve() if args.out else experiment.material() / "personas_generated.yaml"
    protokoll = []
    try:
        ergebnis = erzeugen(gen, args.n, args.max_versuche, protokoll)
    finally:
        # Auch bei Abbruch schreiben: Die Ablehnungsgruende sind ein Befund
        # ueber die Steuerbarkeit des erzeugenden Modells und gehen sonst verloren.
        (out.with_suffix(".log.json")).write_text(
            json.dumps(protokoll, ensure_ascii=False, indent=1), encoding="utf-8")
    schreiben(out, args, spec, ergebnis, protokoll)
    if out.parent == experiment.material() and out.name != experiment.personen_datei():
        # Sonst friert man leicht die alte Datei ein, auf die die Konfiguration
        # noch zeigt, und das Experiment laeuft still mit fremden Beschreibungen.
        print(f"\nHinweis: Die experiment.yaml nennt unter material.personen noch "
              f"'{experiment.personen_datei()}'. Fuer die neuen Beschreibungen dort "
              f"'{out.name}' eintragen, bevor eingefroren wird.")


def erzeugen(gen, n: int, max_versuche: int, protokoll: list) -> dict[str, dict[str, str]]:
    """Erzeugt S3 in einem Aufruf und leitet S2 und S1 daraus ab."""
    ergebnis: dict[str, dict[str, str]] = {s_: {} for s_ in STUFEN}
    kennungen = [chr(ord("a") + i) for i in range(n)]

    # Schritt 1: die vollstaendigen Beschreibungen, alle in einem Aufruf.
    # Dadurch kann das Modell die Personen voneinander unterscheiden.
    for versuch in range(1, max_versuche + 1):
        personen = gen.personen(n)
        fehler_liste = [pruefe(t, "S3") for t in personen]
        doppelt = len({normiert(t) for t in personen}) < len(personen)
        protokoll.append(dict(schritt="personen", versuch=versuch,
                              anzahl=len(personen), doppelt=doppelt,
                              fehler=[f for f in fehler_liste if f],
                              texte=personen))
        if len(personen) == n and not doppelt and not any(fehler_liste):
            break
        print(f"  Versuch {versuch} verworfen: "
              f"{len(personen)} Beschreibungen, doppelt={doppelt}, "
              f"Fehler={[f for f in fehler_liste if f]}")
    else:
        raise SystemExit(
            f"Nach {max_versuche} Versuchen kein brauchbarer Satz von "
            f"{n} verschiedenen Beschreibungen.")

    for k, text in zip(kennungen, personen):
        ergebnis["S3"][k] = text

    # Schritt 2: die kuerzeren Stufen aus derselben Person ableiten.
    for stufe in ("S2", "S1"):
        for k in kennungen:
            bitte = STUFEN[stufe]["ziel"]
            for versuch in range(1, max_versuche + 1):
                text = gen.kuerzen(ergebnis["S3"][k], stufe, bitte)
                fehler = pruefe(text, stufe)
                # Nachjustieren: Weicht die Laenge ab, wird beim naechsten
                # Versuch entsprechend weniger oder mehr erbeten.
                ist = len(text.split())
                if abs(ist - STUFEN[stufe]["ziel"]) > STUFEN[stufe]["toleranz"]:
                    bitte = max(3, round(bitte * STUFEN[stufe]["ziel"] / max(1, ist)))
                vorhanden = {normiert(t) for t in ergebnis[stufe].values()}
                if normiert(text) in vorhanden:
                    fehler = fehler + ["Doppelung zu einer anderen Variante"]
                protokoll.append(dict(schritt=f"{stufe}{k}", versuch=versuch,
                                      woerter=len(text.split()), fehler=fehler,
                                      text=text))
                if not fehler:
                    ergebnis[stufe][k] = text
                    break
            else:
                raise SystemExit(
                    f"{stufe}{k}: nach {max_versuche} Versuchen keine "
                    f"gueltige Kuerzung. Letzte Fehler: {fehler}")

    return ergebnis


def schreiben(out: Path, args, spec, ergebnis: dict, protokoll: list) -> None:
    kopf = {
        "_meta": {
            "erzeugt_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provider": args.provider,
            "modell": spec.model_id,
            "varianten_je_stufe": args.n,
            "hinweis": ("Maschinell erzeugt und gegen die Vorgaben geprueft. Einmal "
                        "erzeugt und eingefroren; nicht zur Laufzeit generieren."),
        },
        "active_variants": [chr(ord("a") + i) for i in range(args.n)],
        "levels": {
            "S0": {"label": "Baseline ohne Personenbeschreibung",
                   "has_variants": False, "template": None},
            **{s: {"label": f"Detailgrad {s}", "has_variants": True,
                   "variants": ergebnis[s]} for s in STUFEN},
        },
        "response_instruction": ("Answer with exactly one letter, either A or B, "
                                 "and nothing else."),
    }
    out.write_text(yaml.dump(kopf, allow_unicode=True, sort_keys=False, width=88),
                   encoding="utf-8")

    versuche = len(protokoll)
    abgelehnt = sum(1 for e in protokoll if e.get("fehler") or e.get("doppelt"))
    print(f"Erzeugt mit {spec.model_id}: {args.n} Varianten je Stufe")
    print(f"Versuche insgesamt {versuche}, davon abgelehnt {abgelehnt} "
          f"({abgelehnt/versuche:.0%})")
    if abgelehnt:
        def flach(x):
            if isinstance(x, str):
                yield x
            elif isinstance(x, (list, tuple)):
                for y in x:
                    yield from flach(y)
        gruende: dict[str, int] = {}
        for e in protokoll:
            for f in flach(e.get("fehler", [])):
                schluessel = f.split(":")[0].split(",")[0]
                gruende[schluessel] = gruende.get(schluessel, 0) + 1
        print("Ablehnungsgruende:")
        for g, n in sorted(gruende.items(), key=lambda x: -x[1]):
            print(f"  {n:>3}x  {g}")
    print("\nWortzahlen je Stufe:")
    for s in STUFEN:
        w = [len(t.split()) for t in ergebnis[s].values()]
        print(f"  {s}: {min(w)}-{max(w)} (Ziel {STUFEN[s]['ziel']})")
    print(f"\nGeschrieben: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    print(f"Protokoll: {out.with_suffix('.log.json').name}")


if __name__ == "__main__":
    main()
