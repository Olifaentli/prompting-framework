"""Tests fuer die Versuchsplanung.

Diese Tests sichern die Eigenschaften ab, von denen die Auswertung abhaengt.
Ein Fehler im Design faellt sonst erst auf, wenn die Daten bereits erhoben und
bezahlt sind.
"""

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from design import (active_variants, build_prompt, enumerate_cells,
                    generate_trials, load_config)


@pytest.fixture(scope="module")
def config():
    return load_config()


def test_zellzahl_folgt_der_konfiguration(config):
    """Die Zellzahl ergibt sich aus 2 Rahmungen x (1 Baseline + 3 Stufen x Varianten).

    Der Test rechnet gegen die Konfiguration statt gegen eine feste Zahl, damit
    das Hinzunehmen einer Variante nicht faelschlich als Fehler gilt.
    """
    items, personas = config
    n_v = len(active_variants(personas))
    erwartet = 2 * (1 + 3 * n_v)
    for item in items:
        cells = enumerate_cells(items, personas, only_item=item)
        assert len(cells) == erwartet, f"{item}: {len(cells)} statt {erwartet} Zellen"


def test_aktive_varianten_sind_definiert(config):
    """Jede aktive Variante muss in allen Stufen mit Beschreibung hinterlegt sein."""
    items, personas = config
    for v in active_variants(personas):
        for level, spec in personas["levels"].items():
            if spec["has_variants"]:
                assert v in spec["variants"], f"{level}: Variante '{v}' fehlt"


def test_beschreibungen_ohne_risikobezug(config):
    """Keine Personenbeschreibung darf eine Risikoneigung mitliefern.

    Das ist die Kernbedingung des Designs: Variiert wird allein die Menge an
    Detail, nicht die Disposition der beschriebenen Person.
    """
    import re as _re
    items, personas = config
    verboten = _re.compile(
        r"\b(risk|cautious|careful|bold|adventur|gambl|insur|invest|"
        r"danger|thrill|safe|timid|daring|reckless)", _re.I)
    for level, spec in personas["levels"].items():
        if not spec["has_variants"]:
            continue
        for v, txt in spec["variants"].items():
            treffer = verboten.findall(txt)
            assert not treffer, f"{level}{v}: risikobezogene Woerter {treffer}"


def test_detailgrad_steigt(config):
    """Die Stufen muessen tatsaechlich mehr Text enthalten, sonst ist die
    unabhaengige Variable nicht umgesetzt."""
    items, personas = config
    for v in active_variants(personas):
        laengen = [len(personas["levels"][s]["variants"][v].split())
                   for s in ("S1", "S2", "S3")]
        assert laengen == sorted(laengen), f"Variante {v}: {laengen} nicht steigend"
        assert laengen[0] < laengen[-1], f"Variante {v}: S1 und S3 gleich lang"


def test_varianten_innerhalb_einer_stufe_aehnlich_lang(config):
    """Die Varianten einer Stufe sollen vergleichbar lang sein, damit der
    Variantenvergleich nicht zum Laengenvergleich wird."""
    items, personas = config
    for level, spec in personas["levels"].items():
        if not spec["has_variants"]:
            continue
        laengen = [len(t.split()) for t in spec["variants"].values()]
        assert max(laengen) <= 1.3 * min(laengen), f"{level}: {laengen}"


def test_baseline_ohne_variante(config):
    """S0 darf keine Variante tragen, da es keine Beschreibung enthaelt."""
    items, personas = config
    for cell in enumerate_cells(items, personas):
        if cell.spec_level == "S0":
            assert cell.variant is None
        else:
            assert cell.variant in active_variants(personas)


def test_jede_zelle_einmal(config):
    """Keine Zelle darf doppelt auftreten."""
    items, personas = config
    ids = [c.cell_id for c in enumerate_cells(items, personas)]
    assert len(ids) == len(set(ids))


def test_optionsreihenfolge_balanciert():
    """Die sichere Option steht in genau der Haelfte der Durchlaeufe zuerst.

    Das ist die Kontrolle gegen Positionsbias. Waere sie nur zufaellig statt
    exakt balanciert, entstuende in kleinen Zellen eine Schieflage.
    """
    trials = list(generate_trials(100, only_item="asian_disease", je_stufe=False))
    per_cell = {}
    for t in trials:
        per_cell.setdefault(t.cell_id, []).append(t.sure_option)
    for cell_id, orders in per_cell.items():
        counts = Counter(orders)
        assert counts["A"] == counts["B"] == 50, f"{cell_id}: {dict(counts)}"


def test_reproduzierbar():
    """Gleicher Seed erzeugt identische Trials."""
    a = list(generate_trials(20, seed=42, only_item="asian_disease"))
    b = list(generate_trials(20, seed=42, only_item="asian_disease"))
    assert [t.prompt for t in a] == [t.prompt for t in b]
    assert [t.sure_option for t in a] == [t.sure_option for t in b]


def test_verschiedene_seeds_verschiedene_reihenfolge():
    a = list(generate_trials(100, seed=1, only_item="asian_disease"))
    b = list(generate_trials(100, seed=2, only_item="asian_disease"))
    assert [t.sure_option for t in a] != [t.sure_option for t in b]


def test_prompt_enthaelt_beide_optionen(config):
    """Jeder Prompt muss genau ein A und ein B anbieten."""
    items, personas = config
    for cell in enumerate_cells(items, personas):
        for sure in ("A", "B"):
            p = build_prompt(items, personas, cell, sure)
            assert "\nA: " in p or p.startswith("A: ")
            assert "\nB: " in p


def test_baseline_prompt_ohne_persona(config):
    """Die Baseline darf keine Personenbeschreibung enthalten."""
    items, personas = config
    cell = next(c for c in enumerate_cells(items, personas)
                if c.spec_level == "S0" and c.item == "asian_disease")
    p = build_prompt(items, personas, cell, "A")
    assert "You are" not in p
    assert "You spend" not in p


def test_persona_steht_vor_der_aufgabe(config):
    """Die Persona muss vor der Aufgabe stehen, sonst wirkt sie nicht als Rahmen."""
    items, personas = config
    cell = next(c for c in enumerate_cells(items, personas)
                if c.spec_level == "S2" and c.variant == "a"
                and c.item == "asian_disease")
    p = build_prompt(items, personas, cell, "A")
    assert p.index("You are") < p.index("Imagine that")


@pytest.mark.parametrize("frame,begriff", [("gain", "saved"), ("loss", "die")])
def test_rahmung_verwendet_originalwortlaut(config, frame, begriff):
    """Gewinnrahmung spricht von Geretteten, Verlustrahmung von Toten."""
    items, personas = config
    cell = next(c for c in enumerate_cells(items, personas)
                if c.item == "asian_disease" and c.frame == frame and c.spec_level == "S0")
    p = build_prompt(items, personas, cell, "A")
    assert begriff in p


def test_sichere_option_wechselt_die_position(config):
    """Bei sure_option='B' steht die sichere Option hinten."""
    items, personas = config
    cell = next(c for c in enumerate_cells(items, personas)
                if c.item == "asian_disease" and c.frame == "gain" and c.spec_level == "S0")
    pa = build_prompt(items, personas, cell, "A")
    pb = build_prompt(items, personas, cell, "B")
    assert "A: If this program is adopted, 200 people will be saved." in pa
    assert "B: If this program is adopted, 200 people will be saved." in pb


def test_mock_provider_deckt_alle_zellen(config):
    """Der Mock-Provider muss jede Zelle des Versuchsplans bedienen koennen.

    Ohne diesen Test bleibt eine Umstellung des Designs unbemerkt, bis ein
    ganzer Probelauf fehlschlaegt.
    """
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "src"))
    from runner import MockProvider

    anbieter = MockProvider()
    for t in generate_trials(2, only_item="asian_disease", je_stufe=False):
        antwort = anbieter(t)
        assert antwort["text"], f"leere Antwort fuer {t.cell_id}"


def test_durchlaeufe_werden_je_stufe_verteilt(config):
    """n gilt je Stufe und Rahmung, nicht je Variante.

    Die Auswertung aggregiert je Stufe. Wuerde n je Zelle gelten, erhielte die
    Baseline mit ihrer einzigen Variante nur einen Bruchteil der Durchlaeufe
    der uebrigen Stufen - und zwar bei der Stufe, die den wichtigsten
    Vergleichswert liefert.
    """
    from collections import Counter
    items, personas = config
    n_var = len(active_variants(personas))
    ziel = 40 * n_var                      # teilbar, damit kein Rundungsrest
    trials = list(generate_trials(ziel, only_item="asian_disease"))
    je_stufe = Counter((t.spec_level, t.frame) for t in trials)
    assert je_stufe, "keine Trials erzeugt"
    for (stufe, rahmung), anzahl in je_stufe.items():
        assert anzahl == ziel, f"{stufe}/{rahmung}: {anzahl} statt {ziel}"


def test_je_zelle_modus_bleibt_verfuegbar(config):
    """Fuer Pilotlaeufe muss n weiterhin je Zelle deutbar sein."""
    from collections import Counter
    trials = list(generate_trials(10, only_item="asian_disease", je_stufe=False))
    pro_zelle = Counter(t.cell_id for t in trials)
    assert set(pro_zelle.values()) == {10}


def test_verteilung_ist_exakt(config):
    """Die Summe je Stufe muss genau n ergeben, auch wenn n nicht teilbar ist.

    Eine Rundung je Variante liesse die Stufen um wenige Durchlaeufe
    auseinanderlaufen; das waere harmlos, aber eine unnoetige Frage im Text.
    """
    from collections import Counter
    for n in (910, 907, 101, 13):
        trials = list(generate_trials(n, only_item="asian_disease"))
        je_stufe = Counter((t.spec_level, t.frame) for t in trials)
        for schluessel, anzahl in je_stufe.items():
            assert anzahl == n, f"n={n}, {schluessel}: {anzahl}"
