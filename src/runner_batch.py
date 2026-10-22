"""Fuehrt den Hauptlauf ueber die Message Batches API von Anthropic aus.

Gegenueber src/runner.py (Einzelaufrufe) halbiert die Batch-API die Kosten und
umgeht die Rate-Limits der Einzelaufrufe. Fuer den Hauptlauf mit Haiku
(14.560 Aufrufe) ist das der vorgesehene Weg. Luna laeuft ueber src/runner.py:
Dort ist der Lauf fortsetzbar, und die Kosten liegen ohnehin bei rund 0,25 $.

Ablauf:
    python src/runner_batch.py submit      --model haiku-4.5 --n 910 --temperature 1.0
    python src/runner_batch.py status      --manifest experiments/<name>/laeufe/manifest_....json
    python src/runner_batch.py fetch       --manifest experiments/<name>/laeufe/manifest_....json
    python src/runner_batch.py nachreichen --manifest experiments/<name>/laeufe/manifest_....json

`nachreichen` reicht alle Anfragen erneut ein, die fehlgeschlagen oder
abgelaufen sind, und traegt die neuen Batches ins Manifest ein. `fetch` fuehrt
danach alle Batches zusammen. So bleiben die Zellen exakt besetzt.

Fuer die Vorabpruefung reicht `submit --nur 8` je eine Anfrage aus acht
verschiedenen Zellen ein.

Grenzen der API: 100.000 Anfragen bzw. 256 MB je Batch. Bei groesseren Laeufen
teilt `submit` automatisch in mehrere Batches und legt die IDs in einer
Manifestdatei ab.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zugang
import laufinfo
import models as model_registry
from design import generate_trials

import experiment

ROOT = Path(__file__).resolve().parent.parent

MAX_TOKENS = 8
MAX_PER_BATCH = 90_000          # Sicherheitsabstand zum Limit von 100.000

# Erlaubte Zeichen der custom_id. Eine fruehere Fassung trennte mit "~"; die
# API haette den gesamten Batch beim Einreichen abgelehnt.
CUSTOM_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def trial_key(t) -> str:
    """custom_id, ueber das die Antwort spaeter wieder zugeordnet wird.

    Die Batch-API liefert die Ergebnisse in beliebiger Reihenfolge; die
    Zuordnung darf daher nie ueber die Position erfolgen. Getrennt wird mit
    "-", weil die Aufgabennamen Unterstriche enthalten.
    """
    rt = t.variant or "none"
    key = f"{t.item}-{t.frame}-{t.spec_level}-{rt}-{t.replicate}"
    if not CUSTOM_ID.fullmatch(key):
        raise ValueError(f"Unzulaessige custom_id: {key!r}")
    return key


def parse_key(key: str) -> dict:
    item, frame, spec, rt, rep = key.split("-")
    return {
        "item": item, "frame": frame, "spec_level": spec,
        "variant": None if rt == "none" else rt, "replicate": int(rep),
    }


def _rel(pfad: Path) -> Path:
    """Pfad relativ zum Framework, falls er darin liegt; sonst unveraendert."""
    return pfad.relative_to(ROOT) if pfad.is_relative_to(ROOT) else pfad


def je_zelle_eine(trials: list, anzahl: int) -> list:
    """Je eine Anfrage aus `anzahl` verschiedenen Zellen, fuer die Vorabpruefung."""
    out, gesehen = [], set()
    for t in trials:
        if t.cell_id not in gesehen:
            gesehen.add(t.cell_id)
            out.append(t)
        if len(out) == anzahl:
            break
    return out


def _client():
    """Der Anthropic-Client, nachdem der Zugang aus der .env geladen ist.

    Jeder Befehl holt sich den Client hier. Vorher erzeugten status und fetch
    ihn direkt, ohne die .env zu lesen, und fanden keinen Schluessel.
    """
    import anthropic
    zugang.pruefen("anthropic")
    return anthropic.Anthropic()


def _einreichen(client, spec, trials: list, temperature: float | None) -> list[str]:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    batch_ids = []
    for start in range(0, len(trials), MAX_PER_BATCH):
        chunk = trials[start:start + MAX_PER_BATCH]
        requests = []
        for t in chunk:
            params = dict(
                model=spec.model_id,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": t.prompt}],
            )
            if temperature is not None:
                params["temperature"] = temperature
            requests.append(
                Request(custom_id=trial_key(t), params=MessageCreateParamsNonStreaming(**params))
            )
        batch = client.messages.batches.create(requests=requests)
        batch_ids.append(batch.id)
        print(f"Batch {batch.id}: {len(chunk)} Anfragen, {batch.processing_status}")
    return batch_ids


def cmd_submit(args) -> None:
    spec = model_registry.get(args.model)
    if spec.provider != "anthropic":
        raise SystemExit("Die Batch-API wird hier nur fuer Anthropic-Modelle unterstuetzt. "
                         "Luna laeuft ueber src/runner.py.")
    if args.temperature is not None and not spec.supports_temperature:
        raise SystemExit(
            f"{spec.model_id} akzeptiert keinen temperature-Parameter (siehe src/models.py)."
        )
    info = laufinfo.erfassen()
    laufinfo.pruefen_vor_echtem_lauf(info)

    trials = list(generate_trials(args.n, seed=args.seed, only_item=args.item))
    if args.nur:
        trials = je_zelle_eine(trials, args.nur)
    # Die Optionsreihenfolge steckt im custom_id nicht drin, wird aber gebraucht.
    order = {trial_key(t): t.sure_option for t in trials}

    client = _client()
    runs = experiment.laeufe()
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_ids = _einreichen(client, spec, trials, args.temperature)

    praefix = "vorab" if args.nur else "manifest"
    manifest = runs / f"{praefix}_{args.model}_{stamp}.json"
    manifest.write_text(json.dumps({
        "model_alias": args.model,
        "model_id": spec.model_id,
        "temperature": args.temperature,
        "n_per_cell": args.n,
        "n_gilt_je": "Stufe und Rahmung",
        "seed": args.seed,
        "item": args.item,
        "nur": args.nur,
        "submitted_utc": stamp,
        "batch_ids": batch_ids,
        "nachgereicht": [],
        "sure_option": order,
        **info,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nManifest: {_rel(manifest)}")
    print(f"Insgesamt {len(trials)} Anfragen in {len(batch_ids)} Batch(es).")
    print(f"Status pruefen: python src/runner_batch.py status --manifest {_rel(manifest)}")


def _load_manifest(args) -> tuple[Path, dict]:
    pfad = Path(args.manifest).resolve()
    return pfad, json.loads(pfad.read_text(encoding="utf-8"))


def cmd_status(args) -> None:
    client = _client()
    _, man = _load_manifest(args)
    all_done = True
    for bid in man["batch_ids"]:
        b = client.messages.batches.retrieve(bid)
        c = b.request_counts
        print(f"{bid}: {b.processing_status} | fertig {c.succeeded} | Fehler {c.errored} "
              f"| laufend {c.processing} | abgelaufen {c.expired}")
        if b.processing_status != "ended":
            all_done = False
    print("\nAlle Batches abgeschlossen." if all_done else "\nNoch nicht fertig.")


def _ergebnisse(client, man: dict) -> dict:
    """Alle Ergebnisse aller Batches, je custom_id genau eines.

    Nach `nachreichen` kann eine Anfrage in zwei Batches vorkommen: einmal
    fehlgeschlagen, einmal erfolgreich. Das erfolgreiche Ergebnis gewinnt.
    """
    alle: dict = {}
    for bid in man["batch_ids"]:
        b = client.messages.batches.retrieve(bid)
        if b.processing_status != "ended":
            raise SystemExit(f"Batch {bid} ist noch nicht abgeschlossen.")
        for result in client.messages.batches.results(bid):
            bisher = alle.get(result.custom_id)
            if bisher is None or bisher.result.type != "succeeded":
                alle[result.custom_id] = result
    return alle


def cmd_fetch(args) -> None:
    client = _client()
    pfad, man = _load_manifest(args)
    order = man["sure_option"]
    alle = _ergebnisse(client, man)

    out = Path(args.out).resolve() if args.out else experiment.laeufe() / f"{man['model_alias']}_{man['submitted_utc']}.jsonl"
    n_ok = n_err = 0
    tok_in = tok_out = 0
    abgeholt = datetime.now(timezone.utc).isoformat()

    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_meta": {
            "provider": "anthropic",
            "model_alias": man["model_alias"],
            "model_id": man["model_id"],
            "temperature": man["temperature"],
            "supports_temperature": True,
            "n_per_cell": man["n_per_cell"],
            "n_gilt_je": man.get("n_gilt_je"),
            "seed": man["seed"],
            "started_utc": man["submitted_utc"],
            "via": "batch_api",
            "batch_ids": man["batch_ids"],
            "nachgereicht": man.get("nachgereicht", []),
            "material": man.get("material"),
            "git": man.get("git"),
            "pakete": man.get("pakete"),
        }}, ensure_ascii=False) + "\n")

        for key in order:
            result = alle.get(key)
            rec = parse_key(key)
            rec.update({
                "cell_id": f"{rec['item']}|{rec['frame']}|{rec['spec_level']}|{rec['variant'] or 'none'}",
                "sure_option": order[key],
                "model_id": man["model_id"],
                "temperature": man["temperature"],
                # Die Batch-API liefert keinen Zeitpunkt je Anfrage; festgehalten
                # wird der Zeitpunkt des Abholens.
                "ts_utc": abgeholt,
                "error": None,
            })
            if result is not None and result.result.type == "succeeded":
                msg = result.result.message
                rec["raw_text"] = "".join(b.text for b in msg.content if b.type == "text")
                rec["stop_reason"] = msg.stop_reason
                rec["input_tokens"] = msg.usage.input_tokens
                rec["output_tokens"] = msg.usage.output_tokens
                rec["served_model"] = msg.model
                tok_in += msg.usage.input_tokens
                tok_out += msg.usage.output_tokens
                n_ok += 1
            else:
                rec["error"] = result.result.type if result is not None else "fehlt"
                n_err += 1
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    spec = model_registry.get(man["model_alias"])
    # Batch-API: 50 % des Listenpreises.
    cost = (tok_in / 1e6 * spec.usd_per_mtok_in + tok_out / 1e6 * spec.usd_per_mtok_out) * 0.5
    print(f"Erfolgreich: {n_ok} | Fehlgeschlagen oder fehlend: {n_err}")
    print(f"Token in/out: {tok_in}/{tok_out} | Kosten (Batch, 50 %): ${cost:.2f}")
    print(f"Geschrieben: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    if n_err:
        print(f"\nOffene Anfragen nachreichen: python src/runner_batch.py nachreichen "
              f"--manifest {pfad.relative_to(ROOT) if pfad.is_relative_to(ROOT) else pfad}")
    else:
        print(f"\nWeiter: python src/parse.py {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


def cmd_nachreichen(args) -> None:
    client = _client()
    pfad, man = _load_manifest(args)

    # Nachgereicht wird nur auf demselben Material; sonst waeren die Prompts
    # der zweiten Runde andere als die der ersten.
    info = laufinfo.erfassen()
    laufinfo.pruefen_vor_echtem_lauf(info)
    if info["material"] != man.get("material"):
        raise SystemExit("Das Material weicht vom Manifest ab. Nachreichen nicht moeglich.")

    alle = _ergebnisse(client, man)
    offen = {k for k in man["sure_option"]
             if k not in alle or alle[k].result.type != "succeeded"}
    if not offen:
        print("Keine offenen Anfragen.")
        return

    trials = [t for t in generate_trials(man["n_per_cell"], seed=man["seed"],
                                         only_item=man["item"])
              if trial_key(t) in offen]
    if len(trials) != len(offen):
        raise SystemExit(f"{len(offen)} offen, aber {len(trials)} wiederhergestellt.")
    for t in trials:
        assert t.sure_option == man["sure_option"][trial_key(t)]

    spec = model_registry.get(man["model_alias"])
    neue = _einreichen(client, spec, trials, man["temperature"])
    man["batch_ids"].extend(neue)
    man.setdefault("nachgereicht", []).append({
        "utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "anzahl": len(trials), "batch_ids": neue,
    })
    pfad.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(trials)} Anfragen nachgereicht, Manifest aktualisiert.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit", help="Batch einreichen")
    s.add_argument("--model", default="haiku-4.5")
    s.add_argument("--n", type=int, default=910,
                   help="Durchlaeufe je Stufe und Rahmung; auf die Varianten verteilt")
    s.add_argument("--temperature", type=float, default=1.0)
    s.add_argument("--item", default=None)
    s.add_argument("--seed", type=int, default=20260828)
    s.add_argument("--nur", type=int, default=None,
                   help="nur je eine Anfrage aus so vielen Zellen (Vorabpruefung)")
    s.set_defaults(func=cmd_submit)

    s = sub.add_parser("status", help="Verarbeitungsstand abfragen")
    s.add_argument("--manifest", required=True)
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("fetch", help="Ergebnisse abholen")
    s.add_argument("--manifest", required=True)
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("nachreichen", help="Fehlgeschlagene Anfragen erneut einreichen")
    s.add_argument("--manifest", required=True)
    s.set_defaults(func=cmd_nachreichen)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
