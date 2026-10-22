"""Fuehrt die Modellaufrufe aus und protokolliert die Rohantworten.

Grundsatz: Dieses Skript parst nichts. Es schreibt die unveraenderte Antwort
des Modells als JSONL, damit jede spaetere Parsing-Entscheidung nachvollziehbar
und revidierbar bleibt. Das Parsen uebernimmt src/parse.py.

Aufrufbeispiele:
    python src/runner.py --provider mock --n 200
    python src/runner.py --provider anthropic --model haiku-4.5 --n 200 --temperature 1.0
    python src/runner.py --provider anthropic --model haiku-4.5 --n 200 --batch
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zugang
import laufinfo
import models as model_registry
from design import active_variants, generate_trials, load_config, stufen

import experiment

ROOT = Path(__file__).resolve().parent.parent

MAX_TOKENS = 8

# Wiederholversuche bei Ratenbegrenzung. Bei Laeufen in der Groessenordnung von
# zehntausenden Aufrufen antworten die Anbieter zeitweise mit HTTP 429. Ohne
# Wiederholung gingen diese Trials als Fehler verloren und die Zellen waeren
# unterschiedlich gross besetzt.
MAX_WIEDERHOLUNGEN = 4
GRUNDWARTEZEIT = 2.0        # Sekunden, danach Verdopplung


def mit_wiederholung(fn, *args):
    """Ruft fn auf und wiederholt bei Ratenbegrenzung mit wachsender Wartezeit."""
    letzter = None
    for versuch in range(MAX_WIEDERHOLUNGEN + 1):
        try:
            return fn(*args)
        except Exception as exc:
            letzter = exc
            text = f"{type(exc).__name__} {exc}".lower()
            vorruebergehend = any(k in text for k in
                                  ("rate", "429", "overload", "timeout", "503", "502"))
            if not vorruebergehend or versuch == MAX_WIEDERHOLUNGEN:
                raise
            time.sleep(GRUNDWARTEZEIT * (2 ** versuch) + random.random())
    raise letzter


# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------

class MockProvider:
    """Simuliert Antworten aus einem bekannten logistischen Modell.

    Dient ausschliesslich dem Test der Pipeline: Da die wahren Parameter hier
    bekannt sind, laesst sich pruefen, ob die Auswertung sie zurueckgewinnt.
    """

    # Wahre Parameter auf der Logit-Skala fuer p(sichere Option).
    BASE = 0.50                 # Grundneigung zur sicheren Option
    FRAME = {"gain": 0.60, "loss": -0.60}
    # Mehr Detail verschiebt die Antwort leicht, mit abnehmendem Zuwachs --
    # nachgebildet nach dem Befund von Bai et al. (2025). Je Position der Stufe
    # in der Konfiguration, damit der Mock beliebig benannte Stufen bedient.
    SPEC_SHIFT = (0.00, 0.18, 0.30, 0.35)
    POSITION_BIAS = 0.12        # leichte Praeferenz fuer die erstgenannte Option
    REFUSAL_RATE = 0.004

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        _, personas = load_config()
        self.stufen = stufen(personas)
        self.varianten = list(active_variants(personas))

    def spec_shift(self, stufe: str) -> float:
        i = self.stufen.index(stufe)
        if i < len(self.SPEC_SHIFT):
            return self.SPEC_SHIFT[i]
        return self.SPEC_SHIFT[-1] + 0.02 * (i - len(self.SPEC_SHIFT) + 1)

    def variant_shift(self, variant: str | None) -> float:
        """Kleiner Unterschied zwischen den Formulierungsvarianten.

        Damit laesst sich pruefen, ob die Auswertung ihn aufdeckt. Je Position
        der Variante, damit der Mock jede Zahl und Benennung bedient:
        erste +0.08, zweite -0.08, dritte +0.04, vierte -0.04, ...
        """
        if variant is None:
            return 0.0
        i = self.varianten.index(variant) if variant in self.varianten else 0
        return (1 if i % 2 == 0 else -1) * 0.08 / (1 + i // 2)

    def __call__(self, trial) -> dict:
        logit = (
            self.BASE
            + self.FRAME[trial.frame]
            + self.spec_shift(trial.spec_level)
            + self.variant_shift(trial.variant)
        )
        if trial.sure_option == "A":
            logit += self.POSITION_BIAS
        else:
            logit -= self.POSITION_BIAS

        p_sure = 1 / (1 + math.exp(-logit))
        if self.rng.random() < self.REFUSAL_RATE:
            text = "I'm not able to choose."
        else:
            chose_sure = self.rng.random() < p_sure
            text = trial.sure_option if chose_sure else ("B" if trial.sure_option == "A" else "A")
        return {"text": text, "input_tokens": 120, "output_tokens": 1,
                "stop_reason": "end_turn", "served_model": "mock-v1"}


class AnthropicProvider:
    def __init__(self, spec, temperature: float | None):
        import anthropic
        self.client = anthropic.Anthropic()
        self.spec = spec
        self.temperature = temperature

    def __call__(self, trial) -> dict:
        kwargs = dict(
            model=self.spec.model_id,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": trial.prompt}],
        )
        if self.temperature is not None:
            if not self.spec.supports_temperature:
                raise SystemExit(
                    f"Modell {self.spec.model_id} akzeptiert keinen temperature-Parameter. "
                    "Entweder --temperature weglassen oder ein Modell mit "
                    "Temperatursteuerung waehlen (siehe src/models.py)."
                )
            # Die Anthropic-Bibliothek ab 1.x kennt temperature nicht mehr als
            # Argument, weil die neuesten Modelle ihn ablehnen. Haiku 4.5 akzeptiert
            # ihn weiterhin; er wird daher direkt in den Anfrageinhalt gelegt.
            # tests/test_anbieter.py prueft, dass er dort tatsaechlich ankommt.
            kwargs["extra_body"] = {"temperature": self.temperature}

        msg = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in msg.content if b.type == "text")
        return {
            "text": text,
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
            "stop_reason": msg.stop_reason,
            # Die tatsaechlich ausgelieferte Version, nicht die angeforderte.
            "served_model": msg.model,
        }


class OpenAIProvider:
    def __init__(self, spec, temperature: float | None):
        from openai import OpenAI
        self.client = OpenAI()
        self.spec = spec
        self.temperature = temperature

    def __call__(self, trial) -> dict:
        kwargs = dict(
            model=self.spec.model_id,
            max_completion_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": trial.prompt}],
        )
        # Reasoning abschalten. Zwei Gruende: Die Temperatur ist nur ohne
        # Reasoning nutzbar, und ein rechnendes Modell zeigt keinen
        # Framing-Effekt mehr (Payne, 2025).
        if self.spec.supports_temperature:
            kwargs["reasoning_effort"] = "none"
        if self.temperature is not None:
            if not self.spec.supports_temperature:
                raise SystemExit(
                    f"Modell {self.spec.model_id} akzeptiert keinen "
                    "temperature-Parameter (siehe src/models.py)."
                )
            kwargs["temperature"] = self.temperature
        r = self.client.chat.completions.create(**kwargs)
        u = r.usage
        return {
            "text": r.choices[0].message.content or "",
            "input_tokens": u.prompt_tokens,
            "output_tokens": u.completion_tokens,
            "stop_reason": r.choices[0].finish_reason,
            # OpenAI bietet fuer luna keine datierte Kennung an. Festgehalten
            # wird daher, was ausgeliefert wurde, samt Kennung der Serverkonfiguration.
            "served_model": r.model,
            "system_fingerprint": getattr(r, "system_fingerprint", None),
        }


def build_provider(name: str, spec, temperature: float | None, seed: int = 7):
    if name == "mock":
        # Eigener Zufallsstrom je Lauf, sonst sind zwei Mock-Laeufe nur scheinbar
        # unabhaengig.
        return MockProvider(seed=seed)
    zugang.pruefen(name)
    if name == "anthropic":
        return AnthropicProvider(spec, temperature)
    if name == "openai":
        return OpenAIProvider(spec, temperature)
    raise SystemExit(f"Unbekannter Provider: {name}")


# --------------------------------------------------------------------------
# Lauf
# --------------------------------------------------------------------------

def load_done(path: Path) -> set[tuple[str, int]]:
    """Bereits erledigte Trials, damit ein abgebrochener Lauf fortgesetzt werden kann."""
    if not path.exists():
        return set()
    done = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("error") is None:
                done.add((r["cell_id"], r["replicate"]))
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic", "openai"])
    ap.add_argument("--model", default="mock", help="Alias aus src/models.py")
    ap.add_argument("--n", type=int, default=100,
                    help="Durchlaeufe je Stufe und Rahmung; auf die Varianten verteilt")
    ap.add_argument("--je-zelle", action="store_true",
                    help="n stattdessen je Zelle deuten (fuer Pilotlaeufe)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--item", default=None, help="nur ein Item, z.B. asian_disease")
    ap.add_argument("--level", default=None,
                    help="nur eine Detailstufe, z.B. S2 — für Läufe in Etappen")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260828)
    ap.add_argument("--dry-run", action="store_true", help="nur zaehlen und Kosten schaetzen")
    args = ap.parse_args()

    spec = model_registry.get(args.model)
    if args.provider != "mock" and spec.provider != args.provider:
        raise SystemExit(f"Modell '{args.model}' gehoert zu Provider '{spec.provider}', nicht '{args.provider}'.")

    trials = list(generate_trials(args.n, seed=args.seed, only_item=args.item,
                                  only_level=args.level,
                                  je_stufe=not args.je_zelle))

    if args.dry_run:
        # Grobe Schaetzung: rund vier Zeichen je Token. Eine feste Zahl je
        # Aufruf unterschaetzte die S3-Prompts, die mehr als doppelt so lang
        # sind wie die Baseline.
        est_in = sum(len(t.prompt) for t in trials) / 4
        cost = est_in / 1e6 * spec.usd_per_mtok_in + len(trials) * 1 / 1e6 * spec.usd_per_mtok_out
        zellen = len({t.cell_id for t in trials})
        print(f"Trials: {len(trials)} in {zellen} Zellen")
        print(f"Modell: {spec.model_id}  Temperatur steuerbar: {'ja' if spec.supports_temperature else 'NEIN'}")
        print(f"Geschaetzte Eingabetoken: {est_in:,.0f}")
        print(f"Geschaetzte Kosten: ${cost:.2f} (Batch API: ${cost/2:.2f})")
        return

    info = laufinfo.erfassen()
    if args.provider != "mock":
        laufinfo.pruefen_vor_echtem_lauf(info)

    runs = experiment.laeufe()
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out).resolve() if args.out else runs / f"{args.model}_{stamp}.jsonl"

    done = load_done(out)
    todo = [t for t in trials if (t.cell_id, t.replicate) not in done]
    print(f"{len(trials)} Trials, {len(done)} bereits vorhanden, {len(todo)} offen.")
    if not todo:
        print("Nichts zu tun.")
        return

    provider = build_provider(args.provider, spec, args.temperature, args.seed)
    meta = {
        "provider": args.provider,
        "model_alias": args.model,
        "model_id": spec.model_id,
        "temperature": args.temperature,
        "supports_temperature": spec.supports_temperature,
        "n_per_cell": args.n,
        "n_gilt_je": "Zelle" if args.je_zelle else "Stufe und Rahmung",
        "seed": args.seed,
        "started_utc": stamp,
        **info,
    }

    t0 = time.time()
    tok_in = tok_out = 0
    errors = 0

    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")

        def run_one(trial):
            try:
                return trial, mit_wiederholung(provider, trial), None
            except Exception as exc:  # bewusst breit: ein Fehlschlag darf den Lauf nicht stoppen
                return trial, None, f"{type(exc).__name__}: {exc}"

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_one, t) for t in todo]
            for i, fut in enumerate(as_completed(futures), 1):
                trial, resp, err = fut.result()
                rec = trial.to_dict()
                rec.pop("prompt")  # Prompt ist aus design.py reproduzierbar
                rec.update({
                    "model_id": spec.model_id,
                    "temperature": args.temperature,
                    "ts_utc": datetime.now(timezone.utc).isoformat(),
                    "error": err,
                })
                if resp:
                    rec["raw_text"] = resp["text"]
                    rec["stop_reason"] = resp["stop_reason"]
                    rec["input_tokens"] = resp["input_tokens"]
                    rec["output_tokens"] = resp["output_tokens"]
                    rec["served_model"] = resp.get("served_model")
                    if resp.get("system_fingerprint") is not None:
                        rec["system_fingerprint"] = resp["system_fingerprint"]
                    tok_in += resp["input_tokens"]
                    tok_out += resp["output_tokens"]
                else:
                    errors += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if i % 200 == 0:
                    fh.flush()
                    print(f"  {i}/{len(todo)} ({time.time()-t0:.0f}s)")

    cost = tok_in / 1e6 * spec.usd_per_mtok_in + tok_out / 1e6 * spec.usd_per_mtok_out
    print(f"\nFertig in {time.time()-t0:.0f}s. Fehler: {errors}")
    print(f"Token in/out: {tok_in}/{tok_out}  Kosten: ${cost:.4f}")
    rel = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"Geschrieben: {rel}")
    if errors == len(todo):
        # Ein Lauf, in dem jede Anfrage fehlschlug, ist kein Lauf. Sonst endet
        # etwa eine falsche Konfiguration still mit Erfolg.
        raise SystemExit(f"Alle {errors} Anfragen sind fehlgeschlagen. Erste Fehler stehen in {rel}.")


if __name__ == "__main__":
    main()
