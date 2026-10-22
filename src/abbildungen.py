"""Erzeugt die beiden Standardabbildungen eines Experiments.

Abbildung A: Framing-Effekt ueber die Detailstufen S0 bis S3, eine Linie je
Modell mit 95-%-Intervall, dahinter der menschliche Vergleichswert als Band.
Eine Tafel je Aufgabe.

Abbildung B: Framing-Effekt je Formulierungsvariante als Punkte je Stufe.
Zeigt, wie stark das Ergebnis am Wortlaut der Beschreibungen haengt.

Beide fuer den Druck gebaut: Die Modelle unterscheiden sich in Farbe, Marker
und Linienart, damit die Abbildungen auch schwarz-weiss lesbar bleiben.
Ausgabe als SVG (fuer Word, verlustfrei) und PNG mit 300 dpi.

Aufruf:
    python src/abbildungen.py experiments/<name>/ergebnisse/<lauf_a> \
        experiments/<name>/ergebnisse/<lauf_b> --namen "Modell A" "Modell B"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment
import referenz
from design import load_config, stufen

ROOT = Path(__file__).resolve().parent.parent


# Erste zwei Plaetze der geprueften Referenzpalette (dataviz), gegen
# Farbfehlsichtigkeit validiert. Marker und Linienart tragen die Zuordnung
# zusaetzlich, Farbe allein reicht im Druck nicht.
MODELLSTIL = [
    dict(color="#2a78d6", marker="o", linestyle="-"),
    dict(color="#eb6834", marker="s", linestyle="--"),
]
TINTE = "#0b0b0b"
TINTE_2 = "#52514e"
REFERENZ = "#8a8985"
RASTER = "#e4e3df"

plt.rcParams.update({
    # Liberation Sans hat dieselben Masse wie Arial, eine verbreitete Berichtsschrift.
    "font.family": ["Liberation Sans", "DejaVu Sans"],
    "font.size": 9,
    "axes.edgecolor": TINTE_2,
    "axes.labelcolor": TINTE,
    "xtick.color": TINTE_2,
    "ytick.color": TINTE_2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    # Text als Umrisse: Word zeigt die SVG dann ueberall gleich an, auch ohne
    # die Schrift.
    "svg.fonttype": "path",
})

BREITE_CM = 16


def _figur(n_tafeln: int, hoehe_cm: float = 7.5):
    zoll = 1 / 2.54
    fig, achsen = plt.subplots(1, n_tafeln, figsize=(BREITE_CM * zoll, hoehe_cm * zoll),
                               sharey=True, squeeze=False)
    return fig, achsen[0]


def komma(x: float, nd: int = 1) -> str:
    """Dezimalkomma, wie im deutschen Text."""
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


def _achse(ax, titel: str, reihe: list[str]) -> None:
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: komma(v)))
    ax.set_title(titel, fontsize=9, color=TINTE, loc="left")
    ax.set_xticks(range(len(reihe)), reihe)
    ax.set_xlim(-0.5, len(reihe) - 0.5)
    ax.axhline(0, color=TINTE_2, linewidth=0.8)
    ax.grid(axis="y", color=RASTER, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("Detailstufe")


def _referenzband(ax, ref: dict, breite: int) -> None:
    ax.axhspan(ref["ci"][0], ref["ci"][1], color=REFERENZ, alpha=0.18, linewidth=0)
    ax.axhline(ref["delta"], color=REFERENZ, linewidth=1.2, linestyle=":")
    # Links unter der Linie: Dort liegt bei der Baseline kaum je ein Datenpunkt,
    # rechts dagegen landen die ausfuehrlichen Stufen oft genau auf dem Band.
    ax.annotate(f"Mensch {komma(ref['delta'], 2)}", xy=(-0.5, ref["ci"][0]),
                xytext=(3, -2), textcoords="offset points", ha="left", va="top",
                fontsize=8, color=TINTE_2)


def abbildung_stufen(laeufe: list[Path], namen: list[str], items: dict, ziel: Path,
                     reihe: list[str]) -> Path:
    aufgaben = [a for a in items if all((l / f"stufen_{a}.csv").exists() for l in laeufe)]
    fig, achsen = _figur(len(aufgaben))
    versatz = [-0.08, 0.08]
    for ax, aufgabe in zip(achsen, aufgaben):
        _referenzband(ax, referenz.fuer_aufgabe(aufgabe), len(reihe))
        for i, (lauf, name) in enumerate(zip(laeufe, namen)):
            t = pd.read_csv(lauf / f"stufen_{aufgabe}.csv").set_index("Stufe").reindex(reihe)
            x = [j + versatz[i] for j in range(len(reihe))]
            stil = MODELLSTIL[i]
            ax.errorbar(x, t["Delta"],
                        yerr=[t["Delta"] - t["Delta_lo"], t["Delta_hi"] - t["Delta"]],
                        color=stil["color"], marker=stil["marker"], linestyle=stil["linestyle"],
                        linewidth=1.5, markersize=5.5, markeredgecolor="white",
                        markeredgewidth=0.8, elinewidth=1, capsize=0, label=name)
        _achse(ax, experiment.titel(aufgabe), reihe)
    achsen[0].set_ylabel("Framing-Effekt Δ\n(Anteil sicher: Gewinn − Verlust)")
    _legende(fig, achsen[0])
    return _speichern(fig, ziel, "abbildung_effekt_je_stufe")


def abbildung_varianten(laeufe: list[Path], namen: list[str], items: dict, ziel: Path,
                        reihe: list[str]) -> Path:
    aufgaben = [a for a in items if all((l / f"varianten_{a}.csv").exists() for l in laeufe)]
    fig, achsen = _figur(len(aufgaben))
    versatz = [-0.12, 0.12]
    for ax, aufgabe in zip(achsen, aufgaben):
        _referenzband(ax, referenz.fuer_aufgabe(aufgabe), len(reihe))
        for i, (lauf, name) in enumerate(zip(laeufe, namen)):
            v = pd.read_csv(lauf / f"varianten_{aufgabe}.csv")
            s = pd.read_csv(lauf / f"stufen_{aufgabe}.csv").set_index("Stufe")
            stil = MODELLSTIL[i]
            x = [reihe.index(st) + versatz[i] for st in v["Stufe"]]
            ax.scatter(x, v["Delta"], s=22, color=stil["color"], marker=stil["marker"],
                       edgecolors="white", linewidths=0.6, label=name, zorder=3)
            # Der Wert der Stufe als kurzer Strich, damit die Streuung der
            # Varianten gegen ihn lesbar ist.
            for st in reihe:
                if st in s.index:
                    xs = reihe.index(st) + versatz[i]
                    ax.plot([xs - 0.07, xs + 0.07], [s.loc[st, "Delta"]] * 2,
                            color=stil["color"], linewidth=1.5, zorder=2)
        _achse(ax, experiment.titel(aufgabe), reihe)
    achsen[0].set_ylabel("Framing-Effekt Δ je Variante")
    _legende(fig, achsen[0])
    return _speichern(fig, ziel, "abbildung_varianten")


def _legende(fig, ax) -> None:
    griffe, beschriftung = ax.get_legend_handles_labels()
    fig.legend(griffe, beschriftung, loc="upper right", ncol=len(griffe), frameon=False,
               fontsize=8, labelcolor=TINTE, bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.93))


def _speichern(fig, ziel: Path, name: str) -> Path:
    ziel.mkdir(parents=True, exist_ok=True)
    fig.savefig(ziel / f"{name}.svg")
    fig.savefig(ziel / f"{name}.png", dpi=300)
    plt.close(fig)
    return ziel / f"{name}.png"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("laeufe", nargs=2, help="zwei Ergebnisordner von analyze.py")
    ap.add_argument("--namen", nargs=2, default=None, help="Bezeichnung der beiden Modelle")
    ap.add_argument("--ziel", default=None)
    args = ap.parse_args()

    laeufe = [Path(l).resolve() for l in args.laeufe]
    namen = args.namen or [l.name for l in laeufe]
    ziel = Path(args.ziel).resolve() if args.ziel else experiment.ergebnisse() / "abbildungen"
    items, personas = load_config()
    reihe = stufen(personas)
    for pfad in (abbildung_stufen(laeufe, namen, items, ziel, reihe),
                 abbildung_varianten(laeufe, namen, items, ziel, reihe)):
        print(f"Geschrieben: {pfad.relative_to(ROOT) if pfad.is_relative_to(ROOT) else pfad} (+ .svg)")


if __name__ == "__main__":
    main()
