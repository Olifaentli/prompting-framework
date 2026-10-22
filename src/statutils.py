"""Gemeinsame statistische Hilfsfunktionen.

Bewusst schmal gehalten: Die Auswertung dieser Arbeit kommt mit Anteilen,
Differenzen von Anteilen und deren Konfidenzintervallen aus. Auf
Inferenzverfahren wird verzichtet, wo ein Intervall dieselbe Aussage
verständlicher trägt.

Warum Wilson und Newcombe statt der Normalapproximation:
Die einfache Formel p +/- 1.96 * sqrt(p(1-p)/n) wird bei Anteilen nahe 0 oder 1
unbrauchbar und kann Intervallgrenzen ausserhalb von [0, 1] liefern. Bei
Persona-Bedingungen, die das Modell stark in eine Richtung schieben, ist genau
das zu erwarten.
"""

from __future__ import annotations

import math

from scipy import stats

Z95 = 1.959963984540054


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson-Score-Intervall fuer einen Anteil k/n."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half, centre + half)


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int, z: float = Z95) -> tuple[float, float]:
    """Newcombe-Intervall fuer die Differenz zweier unabhaengiger Anteile."""
    l1, u1 = wilson_ci(k1, n1, z)
    l2, u2 = wilson_ci(k2, n2, z)
    d = k1 / n1 - k2 / n2
    lower = d - math.sqrt((k1 / n1 - l1) ** 2 + (u2 - k2 / n2) ** 2)
    upper = d + math.sqrt((u1 - k1 / n1) ** 2 + (k2 / n2 - l2) ** 2)
    return (lower, upper)


def se_diff(p1: float, n1: int, p2: float, n2: int) -> float:
    """Standardfehler der Differenz zweier unabhaengiger Anteile."""
    return math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)


def cohens_h(p1: float, p2: float) -> float:
    """Effektstaerke fuer die Differenz zweier Anteile."""
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def chi2_2x2(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Chi-Quadrat-Test fuer eine Vierfeldertafel. Gibt (chi2, p) zurueck."""
    table = [[k1, n1 - k1], [k2, n2 - k2]]
    if any(cell < 0 for row in table for cell in row):
        raise ValueError("Negative Zellhaeufigkeit.")
    chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
    return float(chi2), float(p)


def ci_halfwidth(p1: float, p2: float, n_per_group: int, extra_var: float = 0.0,
                 z: float = Z95) -> float:
    """Halbe Breite des Konfidenzintervalls einer Anteilsdifferenz.

    `extra_var` nimmt die Varianz eines zusaetzlichen Terms auf, etwa die
    Unsicherheit des menschlichen Referenzwerts.
    """
    var = p1 * (1 - p1) / n_per_group + p2 * (1 - p2) / n_per_group + extra_var
    return z * math.sqrt(var)
