"""Wertet einen Lauf aus und vergleicht ihn mit den menschlichen Referenzdaten.

Die Auswertung verwendet ein einziges statistisches Mittel: Anteile, deren
Differenzen und Konfidenzintervalle. Keine Signifikanztests, keine
Effektstaerken, keine Modelle.

Der Grund ist nicht Bequemlichkeit. Ein Konfidenzintervall, das die Null nicht
einschliesst, sagt dasselbe wie ein Signifikanztest auf demselben Niveau -
beides zu berichten waere doppelt. Und die Fragestellung zielt auf einen
Abstand, nicht auf ein Ja oder Nein; einen Abstand beschreibt eine Zahl mit
Unsicherheitsbereich unmittelbar.

Ausgewertet wird je Aufgabe und Detailstufe. Die Formulierungsvarianten einer
Stufe werden zusammengefasst; ihre Streuung wird getrennt als Spannweite
ausgewiesen. Jede Aufgabe wird mit ihrer eigenen Referenz verglichen
(src/referenz.py).

Aufruf: python src/analyze.py experiments/<name>/laeufe/<datei>.parsed.csv [--item <aufgabe>]
Die Tabellen landen in experiments/<name>/ergebnisse/<lauf>/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment
import referenz
from design import baseline, load_config, stufen as stufen_der_konfiguration
from statutils import newcombe_diff_ci, se_diff

ROOT = Path(__file__).resolve().parent.parent

# Beide Grenzen gehoeren zum Analyseplan des Experiments und stehen in
# dessen experiment.yaml, nicht im Code.
#
# Relevanzgrenze: Abweichungen darunter gelten als praktisch bedeutungslos.
RELEVANZGRENZE = experiment.auswertung("relevanzgrenze")

# Ab diesem Anteil nicht auswertbarer Antworten in einer Zelle wird gezeigt,
# wie weit sich der Framing-Effekt verschieben koennte, wenn alle ungueltigen
# Antworten sicher bzw. riskant gewesen waeren.
SCHWELLE_UNGUELTIG = experiment.auswertung("schwelle_ungueltig")


def je_stufe(df: pd.DataFrame, ref_delta: float, ref_se: float) -> pd.DataFrame:
    """Eine Zeile je Detailstufe: Anteile, Framing-Effekt, Abstand zum Menschen."""
    rows = []
    for stufe, grp in df.groupby("spec_level"):
        g, l = grp[grp["frame"] == "gain"], grp[grp["frame"] == "loss"]
        if g.empty or l.empty:
            continue
        k_g, n_g = int(g["chose_sure"].sum()), len(g)
        k_l, n_l = int(l["chose_sure"].sum()), len(l)
        p_g, p_l = k_g / n_g, k_l / n_l
        lo, hi = newcombe_diff_ci(k_g, n_g, k_l, n_l)
        se_d = se_diff(p_g, n_g, p_l, n_l)
        abstand = (p_g - p_l) - ref_delta
        se_a = (se_d ** 2 + ref_se ** 2) ** 0.5
        rows.append({
            "Stufe": stufe, "n": n_g + n_l,
            "p_Gewinn": p_g, "p_Verlust": p_l,
            "Delta": p_g - p_l, "Delta_lo": lo, "Delta_hi": hi, "Delta_se": se_d,
            "Abstand": abstand,
            "Abstand_lo": abstand - 1.96 * se_a,
            "Abstand_hi": abstand + 1.96 * se_a,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["klein"] = (out["Abstand_lo"] > -RELEVANZGRENZE) & (out["Abstand_hi"] < RELEVANZGRENZE)
    return out


def saettigung(stufen: pd.DataFrame, reihe: list[str] | None = None) -> str | None:
    """Erste Stufe, ab der sich der Abstand nicht mehr relevant aendert.

    Variante (a) des Analyseplans, ohne neue Kennzahl: Saettigung liegt bei
    Stufe k, wenn sich der Abstand von jeder folgenden Stufe zur vorigen um
    weniger als die Relevanzgrenze aendert. Abgelesen an den Punktwerten;
    ob die Aenderungen belastbar sind, zeigen die Intervalle der Tabelle.
    """
    s = stufen.set_index("Stufe")
    reihe = [x for x in (reihe or list(stufen["Stufe"])) if x in s.index]
    for i, k in enumerate(reihe):
        danach = reihe[i:]
        aenderungen = [abs(s.loc[b, "Abstand"] - s.loc[a, "Abstand"])
                       for a, b in zip(danach, danach[1:])]
        if all(a < RELEVANZGRENZE for a in aenderungen):
            return k
    return None


def streuung_der_varianten(df: pd.DataFrame) -> pd.DataFrame:
    """Framing-Effekt je Formulierungsvariante, als Spannweite innerhalb der Stufe."""
    rows = []
    for (stufe, variante), grp in df.groupby(["spec_level", "variant"]):
        g, l = grp[grp["frame"] == "gain"], grp[grp["frame"] == "loss"]
        if len(g) < 20 or len(l) < 20:
            continue
        rows.append({"Stufe": stufe, "Variante": variante,
                     "Delta": g["chose_sure"].mean() - l["chose_sure"].mean()})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def spannweite(varianten: pd.DataFrame) -> pd.DataFrame:
    if varianten.empty:
        return varianten
    return (varianten.groupby("Stufe")["Delta"]
            .agg(Varianten="count", kleinster="min", groesster="max")
            .assign(Spannweite=lambda x: x["groesster"] - x["kleinster"])
            .reset_index())


def ungueltige(roh: pd.DataFrame) -> pd.DataFrame:
    """Anteil nicht auswertbarer Antworten je Stufe und Rahmung.

    API-Fehler werden getrennt gezaehlt: Sie sagen etwas ueber die Verbindung,
    nicht ueber das Modell.
    """
    rows = []
    for (stufe, rahmung), grp in roh.groupby(["spec_level", "frame"]):
        api = grp["error"].notna()
        antworten = grp[~api]
        n_ungueltig = int((antworten["choice"] == "invalid").sum())
        rows.append({
            "Stufe": stufe, "Rahmung": rahmung, "n": len(grp),
            "API_Fehler": int(api.sum()),
            "nicht_auswertbar": n_ungueltig,
            "Anteil_nicht_auswertbar": n_ungueltig / len(antworten) if len(antworten) else float("nan"),
        })
    return pd.DataFrame(rows)


def grenzen_bei_ungueltigen(roh: pd.DataFrame, stufe: str) -> tuple[float, float]:
    """Framing-Effekt einer Stufe, wenn alle ungueltigen Antworten sicher bzw. riskant waeren."""
    grp = roh[(roh["spec_level"] == stufe) & roh["error"].isna()]
    # Am staerksten verschieben die Faelle "Gewinn ungueltig = sicher,
    # Verlust ungueltig = riskant" und umgekehrt.
    hoch = _delta_mit(grp, gain=1, loss=0)
    tief = _delta_mit(grp, gain=0, loss=1)
    return tief, hoch


def _delta_mit(grp: pd.DataFrame, gain: int, loss: int) -> float:
    g = grp[grp["frame"] == "gain"]
    l = grp[grp["frame"] == "loss"]
    p_g = g["chose_sure"].where(g["choice"] != "invalid", gain).astype(int).mean()
    p_l = l["chose_sure"].where(l["choice"] != "invalid", loss).astype(int).mean()
    return p_g - p_l


def positionsbias(df: pd.DataFrame) -> dict | None:
    t = df.groupby("sure_option")["chose_sure"].agg(n="count", k="sum")
    if len(t) != 2:
        return None
    (n1, k1), (n2, k2) = [(int(r["n"]), int(r["k"])) for _, r in t.iterrows()]
    lo, hi = newcombe_diff_ci(k1, n1, k2, n2)
    return {"p_vorn": k1 / n1, "n_vorn": n1, "p_hinten": k2 / n2, "n_hinten": n2,
            "Differenz": k1 / n1 - k2 / n2, "lo": lo, "hi": hi}


def f(v: float, nd: int = 3) -> str:
    return f"{v:.{nd}f}"


def auswerten(roh: pd.DataFrame, aufgabe: str, ziel: Path, ordnung: list[str], base: str) -> pd.DataFrame:
    item_rows = roh[roh["item"] == aufgabe]
    n_item = len(item_rows)
    df = item_rows[item_rows["choice"] != "invalid"].copy()
    df["chose_sure"] = df["chose_sure"].astype(int)
    ref = referenz.fuer_aufgabe(aufgabe)

    print("=" * 75)
    print(f"Aufgabe: {aufgabe}")
    print(f"Auswertbar: {len(df)} von {n_item} ({len(df)/n_item:.1%})")
    print(f"Menschlicher Vergleichswert: {f(ref['delta'])} "
          f"[{f(ref['ci'][0])}, {f(ref['ci'][1])}], {ref['quelle']}, {ref['design']}\n")

    stufen = je_stufe(df, ref["delta"], ref["se"])
    # groupby sortiert alphabetisch; massgeblich ist die Reihenfolge der Konfiguration.
    stufen = stufen.set_index("Stufe").reindex(
        [x for x in ordnung if x in set(stufen["Stufe"])]).reset_index()

    print("=== Framing-Effekt je Detailstufe ===")
    print(f"{'Stufe':<7}{'n':>7}{'Gewinn':>9}{'Verlust':>9}{'Delta':>8}"
          f"{'95%-Intervall':>18}{'Abstand':>9}{'klein':>7}")
    print("-" * 75)
    for _, r in stufen.iterrows():
        iv = f"[{f(r['Delta_lo'])}, {f(r['Delta_hi'])}]"
        print(f"{r['Stufe']:<7}{int(r['n']):>7}{f(r['p_Gewinn']):>9}{f(r['p_Verlust']):>9}"
              f"{f(r['Delta']):>8}{iv:>18}{r['Abstand']:>+9.3f}"
              f"{'ja' if r['klein'] else 'nein':>7}")
    print(f"\n'klein' heisst: Der Unsicherheitsbereich des Abstands liegt vollstaendig")
    print(f"innerhalb von +/-{RELEVANZGRENZE:.2f}.")

    print("\n=== Zeigt das Modell den Effekt ohne Personenbeschreibung? ===")
    zeile = stufen[stufen["Stufe"] == base]
    if not zeile.empty:
        r = zeile.iloc[0]
        print(f"Baseline {base}: Delta = {f(r['Delta'])}, "
              f"Intervall [{f(r['Delta_lo'])}, {f(r['Delta_hi'])}], "
              f"Abstand zum Menschen {r['Abstand']:+.3f}")
        if r["Delta_lo"] > 0:
            print("  -> Ja, in derselben Richtung wie beim Menschen.")
        elif r["Delta_hi"] < 0:
            print("  -> Ein Effekt ist vorhanden, aber ENTGEGEN der menschlichen Richtung.")
        else:
            print("  -> Nein. Das Intervall schliesst die Null ein.")

    print("\n=== Abstand zum Menschen nach Detailstufe ===")
    s = stufen.set_index("Stufe")
    reihe = [x for x in ordnung if x in s.index]
    for stufe in reihe:
        bal = abs(s.loc[stufe, "Abstand"])
        print(f"  {stufe}  {s.loc[stufe, 'Abstand']:+.3f}   {'#' * max(1, round(bal * 120))}")
    sat = saettigung(stufen, ordnung)
    print(f"  Saettigung (Variante a): ab {sat}" if sat else
          "  Saettigung (Variante a): keine Stufe erfuellt das Kriterium")

    varianten = streuung_der_varianten(df)
    span = spannweite(varianten)
    if not span.empty:
        print("\n=== Kontrolle: Streuung zwischen den Formulierungen ===")
        print(f"{'Stufe':<7}{'Varianten':>11}{'kleinstes':>11}{'groesstes':>11}{'Spannweite':>12}")
        print("-" * 52)
        for _, r in span.iterrows():
            print(f"{r['Stufe']:<7}{int(r['Varianten']):>11}{f(r['kleinster']):>11}"
                  f"{f(r['groesster']):>11}{f(r['Spannweite']):>12}")

    print("\n=== Kontrolle: nicht auswertbare Antworten ===")
    ung = ungueltige(item_rows)
    for _, r in ung.iterrows():
        print(f"  {r['Stufe']} {r['Rahmung']:<5} {r['Anteil_nicht_auswertbar']:6.1%} "
              f"nicht auswertbar, {int(r['API_Fehler'])} API-Fehler")
    auffaellig = sorted(set(ung.loc[ung["Anteil_nicht_auswertbar"] > SCHWELLE_UNGUELTIG, "Stufe"]))
    grenzen = []
    for stufe in auffaellig:
        tief, hoch = grenzen_bei_ungueltigen(item_rows, stufe)
        grenzen.append({"Stufe": stufe, "Delta_tiefst": tief, "Delta_hoechst": hoch})
        print(f"  {stufe}: ueber {SCHWELLE_UNGUELTIG:.0%} ungueltig. Framing-Effekt laege "
              f"zwischen {f(tief)} und {f(hoch)}, je nachdem, wie die ungueltigen ausgefallen waeren.")

    print("\n=== Kontrolle: Positionsbias ===")
    pb = positionsbias(df)
    if pb:
        print(f"  sichere Option vorn:   {f(pb['p_vorn'])}  (n = {pb['n_vorn']})")
        print(f"  sichere Option hinten: {f(pb['p_hinten'])}  (n = {pb['n_hinten']})")
        print(f"  Differenz {pb['Differenz']:+.3f}, Intervall [{f(pb['lo'])}, {f(pb['hi'])}]")

    ziel.mkdir(parents=True, exist_ok=True)
    stufen.assign(Aufgabe=aufgabe, Referenz=ref["delta"]).to_csv(
        ziel / f"stufen_{aufgabe}.csv", index=False)
    if not varianten.empty:
        varianten.assign(Aufgabe=aufgabe).to_csv(ziel / f"varianten_{aufgabe}.csv", index=False)
    ung.assign(Aufgabe=aufgabe).to_csv(ziel / f"ungueltig_{aufgabe}.csv", index=False)
    if grenzen:
        pd.DataFrame(grenzen).assign(Aufgabe=aufgabe).to_csv(
            ziel / f"grenzen_ungueltig_{aufgabe}.csv", index=False)
    if pb:
        pd.DataFrame([pb]).assign(Aufgabe=aufgabe).to_csv(
            ziel / f"positionsbias_{aufgabe}.csv", index=False)
    print()
    return stufen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parsed_csv")
    ap.add_argument("--item", default=None, help="nur diese Aufgabe; sonst alle im Lauf")
    ap.add_argument("--ziel", default=None, help="Ordner fuer die Tabellen")
    args = ap.parse_args()

    quelle = Path(args.parsed_csv).resolve()
    roh = pd.read_csv(quelle)
    items, personas = load_config()
    lauf = quelle.name.removesuffix(".parsed.csv")
    ziel = Path(args.ziel).resolve() if args.ziel else experiment.ergebnisse() / lauf

    aufgaben = [args.item] if args.item else [a for a in items if a in set(roh["item"])]
    if not aufgaben or (args.item and args.item not in set(roh["item"])):
        raise SystemExit(f"Keine Daten fuer Aufgabe '{args.item}'.")
    print(f"Lauf: {lauf} | Modell: {roh['model_id'].iloc[0]}\n")
    for aufgabe in aufgaben:
        auswerten(roh, aufgabe, ziel, stufen_der_konfiguration(personas), baseline(personas))
    print(f"Tabellen: {ziel.relative_to(ROOT) if ziel.is_relative_to(ROOT) else ziel}")


if __name__ == "__main__":
    main()
