"""Tests fuer die Auswertungsschicht.

Fehler in der Auswertung erzeugen keine Fehlermeldung, sondern still Zahlen,
die plausibel aussehen. Deshalb wird hier gegen Werte geprueft, die von aussen
bekannt sind: publizierte Referenzwerte, die wahren Parameter des Mocks und
synthetische Daten mit eingebauter Differenz.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import referenz
from analyze import grenzen_bei_ungueltigen, je_stufe, saettigung, ungueltige
from compare import vergleichen
from design import generate_trials, load_config
from parse import extract_letter
from runner import MockProvider
from tabellen import tabelle_versuchsplan


@pytest.fixture(scope="module")
def items():
    return load_config()[0]


# ---------------------------------------------------------------- Referenzen

def test_jede_aufgabe_hat_ihre_referenz(items):
    assert referenz.fuer_aufgabe("asian_disease")["delta"] == pytest.approx(0.2868, abs=1e-4)
    assert referenz.fuer_aufgabe("monetary_endowment")["delta"] == pytest.approx(0.3587, abs=1e-4)


def test_ruggeri_gespiegelt_auf_sichere_option(items):
    """Bei Ruggeri ist Option A riskant; unter Gewinnrahmung waehlt die Mehrheit sicher."""
    r = referenz.fuer_aufgabe("monetary_endowment")
    assert r["p_gain"] == pytest.approx(1 - 0.2559, abs=1e-4)
    assert r["p_gain"] > 0.5 > r["p_loss"]


def test_gepaarter_standardfehler_von_hand():
    from referenzwerte import ruggeri
    r = ruggeri()
    b, c, n = 300, 1615, 3666
    assert r["se"] == pytest.approx(((b + c) - (b - c) ** 2 / n) ** 0.5 / n)


# ---------------------------------------------------------------- Mock

def _mocklauf(n: int, seed: int = 7) -> pd.DataFrame:
    anbieter = MockProvider(seed=seed)
    rows = []
    for t in generate_trials(n, only_item="asian_disease"):
        letter = extract_letter(anbieter(t)["text"])
        if letter is None:
            continue
        rows.append({"item": t.item, "frame": t.frame, "spec_level": t.spec_level,
                     "variant": t.variant or "none", "sure_option": t.sure_option,
                     "chose_sure": int(letter == t.sure_option), "choice": "x",
                     "error": None})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def mock910():
    return _mocklauf(910)


def test_mock_parameter_werden_zurueckgewonnen(mock910, items):
    """Der Mock schiebt mit jeder Stufe zur sicheren Option. Unter Gewinnrahmung
    muss der Anteil sicherer Wahlen daher von S0 nach S3 steigen."""
    ref = referenz.fuer_aufgabe("asian_disease")
    s = je_stufe(mock910, ref["delta"], ref["se"]).set_index("Stufe")
    assert s.loc["S3", "p_Gewinn"] > s.loc["S0", "p_Gewinn"]


def test_wahrer_framing_effekt_im_mittel_getroffen(items):
    """Wahrer Framing-Effekt auf S0, gemittelt ueber beide Optionspositionen:
    Gewinn (sig(1,22) + sig(0,98)) / 2 = 0,750, Verlust (sig(0,02) + sig(-0,22)) / 2
    = 0,475, Differenz 0,2745.

    Ein einzelner Lauf verfehlt ihn in rund einem von zwanzig Faellen mit
    seinem 95-%-Intervall - das ist die Definition des Intervalls. Geprueft
    wird daher der Mittelwert ueber zehn Startwerte; dessen Standardfehler
    liegt bei etwa 0,008.
    """
    deltas = []
    for seed in range(1, 11):
        s0 = _mocklauf(910, seed=seed).query("spec_level == 'S0'")
        deltas.append(s0[s0.frame == "gain"].chose_sure.mean()
                      - s0[s0.frame == "loss"].chose_sure.mean())
    assert sum(deltas) / len(deltas) == pytest.approx(0.2745, abs=0.025)


# ---------------------------------------------------------------- Vergleich

def _synthetisch(p_gain: float, p_loss: float, n: int = 1000) -> pd.DataFrame:
    rows = []
    for stufe in ("S0", "S1"):
        for frame, p in (("gain", p_gain), ("loss", p_loss)):
            k = round(p * n)
            rows += [{"spec_level": stufe, "frame": frame, "chose_sure": int(i < k),
                      "sure_option": "A" if i % 2 else "B"} for i in range(n)]
    return pd.DataFrame(rows)


def test_vergleich_findet_eingebaute_differenz(items):
    ref = referenz.fuer_aufgabe("asian_disease")
    a = _synthetisch(0.70, 0.30)        # Delta 0,40
    b = _synthetisch(0.60, 0.40)        # Delta 0,20
    v = vergleichen(a, b, ref).set_index("Stufe")
    assert v.loc["S0", "Differenz"] == pytest.approx(0.20)
    assert v.loc["S0", "Differenz_lo"] < 0.20 < v.loc["S0", "Differenz_hi"]
    assert v.loc["S0", "Differenz_lo"] > 0


def test_gleiche_modelle_ohne_differenz(items):
    ref = referenz.fuer_aufgabe("asian_disease")
    v = vergleichen(_synthetisch(0.6, 0.4), _synthetisch(0.6, 0.4), ref)
    assert (v["Differenz"] == 0).all()
    assert (v["Differenz_lo"] < 0).all() and (v["Differenz_hi"] > 0).all()


# ---------------------------------------------------------------- Saettigung

def _stufen(abstaende):
    return pd.DataFrame({"Stufe": ["S0", "S1", "S2", "S3"], "Abstand": abstaende})


def test_saettigung_nach_grossem_schritt():
    assert saettigung(_stufen([-0.30, -0.10, -0.08, -0.07])) == "S1"


def test_saettigung_ohne_relevante_aenderung_ab_beginn():
    assert saettigung(_stufen([-0.05, -0.04, -0.06, -0.05])) == "S0"


def test_saettigung_letzte_stufe_wenn_es_bis_zum_ende_springt():
    assert saettigung(_stufen([-0.40, -0.25, -0.10, 0.05])) == "S3"


# ---------------------------------------------------------------- Ungueltige

def _roh_mit_ungueltigen():
    rows = []
    for frame in ("gain", "loss"):
        for i in range(100):
            if i < 10:
                rows.append({"spec_level": "S1", "frame": frame, "choice": "invalid",
                             "chose_sure": None, "error": None})
            else:
                rows.append({"spec_level": "S1", "frame": frame, "choice": "sure",
                             "chose_sure": int(i < (70 if frame == "gain" else 40)),
                             "error": None})
    rows.append({"spec_level": "S1", "frame": "gain", "choice": "invalid",
                 "chose_sure": None, "error": "overloaded"})
    return pd.DataFrame(rows)


def test_api_fehler_getrennt_von_ungueltigen():
    u = ungueltige(_roh_mit_ungueltigen()).set_index("Rahmung")
    assert u.loc["gain", "API_Fehler"] == 1
    assert u.loc["gain", "nicht_auswertbar"] == 10
    assert u.loc["gain", "Anteil_nicht_auswertbar"] == pytest.approx(0.10)


def test_grenzen_umschliessen_den_beobachteten_effekt():
    roh = _roh_mit_ungueltigen()
    tief, hoch = grenzen_bei_ungueltigen(roh, "S1")
    # Beobachtet ohne Ungueltige: 60/90 - 30/90 = 0,333
    assert tief < 0.333 < hoch
    assert hoch == pytest.approx(0.70 - 0.30)        # Gewinn alle sicher, Verlust alle riskant
    assert tief == pytest.approx(0.60 - 0.40)        # umgekehrt


# ---------------------------------------------------------------- Ausgabe

def test_versuchsplan_tabelle_stimmt_mit_text_ueberein(items):
    plan = tabelle_versuchsplan(items, load_config()[1], 910)
    assert plan.attrs["aufrufe_je_aufgabe_und_modell"] == 7_280
    assert plan.attrs["aufrufe_je_modell"] == 14_560


def test_abbildungen_werden_erzeugt(tmp_path, mock910, items):
    from abbildungen import abbildung_stufen, abbildung_varianten
    from analyze import streuung_der_varianten
    ref = referenz.fuer_aufgabe("asian_disease")
    laeufe = []
    for name, df in (("a", mock910), ("b", _mocklauf(400, seed=3))):
        ordner = tmp_path / name
        ordner.mkdir()
        je_stufe(df, ref["delta"], ref["se"]).to_csv(ordner / "stufen_asian_disease.csv", index=False)
        streuung_der_varianten(df).to_csv(ordner / "varianten_asian_disease.csv", index=False)
        laeufe.append(ordner)
    for fn in (abbildung_stufen, abbildung_varianten):
        png = fn(laeufe, ["A", "B"], items, tmp_path / "abb", ["S0", "S1", "S2", "S3"])
        assert png.exists() and png.with_suffix(".svg").exists()


def test_vergleich_folgt_der_reihenfolge_der_konfiguration(items):
    """Stufen stehen in der Reihenfolge der Personendatei, nicht alphabetisch."""
    ref = referenz.fuer_aufgabe("asian_disease")
    a = _synthetisch(0.7, 0.3).replace({"spec_level": {"S0": "basis", "S1": "viel"}})
    v = vergleichen(a, a, ref, ["basis", "viel"])
    assert list(v["Stufe"]) == ["basis", "viel"]
    v = vergleichen(a, a, ref, ["viel", "basis"])
    assert list(v["Stufe"]) == ["viel", "basis"]
