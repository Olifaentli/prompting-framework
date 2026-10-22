"""Tests fuer die statistischen Hilfsfunktionen.

Geprueft wird gegen von Hand nachrechenbare Faelle und gegen die publizierten
Werte der Referenzstudien. Damit ist ausgeschlossen, dass ein Vorzeichen- oder
Formelfehler unbemerkt in die Ergebnisse laeuft.
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from statutils import (chi2_2x2, ci_halfwidth, cohens_h, newcombe_diff_ci,
                       se_diff, wilson_ci)


class TestWilson:
    def test_intervall_umschliesst_den_anteil(self):
        lo, hi = wilson_ci(50, 100)
        assert lo < 0.5 < hi

    def test_bleibt_in_null_bis_eins(self):
        """Der Vorteil gegenueber der Normalapproximation: keine Grenzen ausserhalb [0,1]."""
        for k, n in [(0, 30), (30, 30), (1, 200), (199, 200)]:
            lo, hi = wilson_ci(k, n)
            assert 0.0 <= lo <= hi <= 1.0, f"k={k}, n={n}: [{lo}, {hi}]"

    def test_schmaler_bei_groesserem_n(self):
        schmal = wilson_ci(500, 1000)
        breit = wilson_ci(50, 100)
        assert (schmal[1] - schmal[0]) < (breit[1] - breit[0])

    def test_leere_stichprobe(self):
        lo, hi = wilson_ci(0, 0)
        assert math.isnan(lo) and math.isnan(hi)


class TestNewcombe:
    def test_symmetrie(self):
        """Vertauschen der Gruppen spiegelt das Intervall am Nullpunkt."""
        a = newcombe_diff_ci(60, 100, 40, 100)
        b = newcombe_diff_ci(40, 100, 60, 100)
        assert a[0] == pytest.approx(-b[1], abs=1e-9)
        assert a[1] == pytest.approx(-b[0], abs=1e-9)

    def test_gleiche_anteile_schliessen_null_ein(self):
        lo, hi = newcombe_diff_ci(50, 100, 50, 100)
        assert lo < 0 < hi

    def test_deutlicher_unterschied_schliesst_null_aus(self):
        lo, hi = newcombe_diff_ci(90, 100, 10, 100)
        assert lo > 0


class TestCohensH:
    def test_null_bei_gleichheit(self):
        assert cohens_h(0.5, 0.5) == pytest.approx(0.0)

    def test_vorzeichen(self):
        assert cohens_h(0.7, 0.3) > 0
        assert cohens_h(0.3, 0.7) < 0

    def test_originalwert_tversky_kahneman_1981(self):
        """Asian-Disease-Problem: 72 % gegen 22 % ergibt h = 1.05."""
        assert cohens_h(0.72, 0.22) == pytest.approx(1.05, abs=0.01)

    def test_many_labs_replikation(self):
        """Many Labs 1: .622 gegen .335 ergibt h = 0.58, rund halb so gross."""
        h = cohens_h(0.622, 0.335)
        assert h == pytest.approx(0.58, abs=0.01)
        assert h / cohens_h(0.72, 0.22) == pytest.approx(0.55, abs=0.02)


class TestChi2:
    def test_kein_unterschied_gibt_grosses_p(self):
        _, p = chi2_2x2(50, 100, 50, 100)
        assert p > 0.9

    def test_grosser_unterschied_gibt_kleines_p(self):
        chi2, p = chi2_2x2(90, 100, 10, 100)
        assert p < 0.001 and chi2 > 100

    def test_negative_haeufigkeit_wird_abgelehnt(self):
        with pytest.raises(ValueError):
            chi2_2x2(150, 100, 50, 100)


class TestStichprobenplanung:
    def test_intervall_schrumpft_mit_n(self):
        assert ci_halfwidth(0.62, 0.34, 1000) < ci_halfwidth(0.62, 0.34, 100)

    def test_referenzunsicherheit_setzt_untergrenze(self):
        """Auch bei sehr grossem n bleibt das Intervall mindestens so breit
        wie die Unsicherheit der menschlichen Referenzdaten."""
        ref_se = 0.0121
        hw = ci_halfwidth(0.62, 0.34, 10_000_000, extra_var=ref_se ** 2)
        assert hw > 1.95 * ref_se

    def test_se_diff_stimmt_mit_handrechnung(self):
        erwartet = math.sqrt(0.25 / 100 + 0.25 / 100)
        assert se_diff(0.5, 100, 0.5, 100) == pytest.approx(erwartet)
