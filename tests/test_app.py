"""
UI-Tests über streamlit.testing.v1.AppTest - prüft, dass die App mit allen
Presets, Slider-Extremen und Umschaltern lädt, ohne abzustürzen.

Ausführen mit: pytest tests/ -v
"""

import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = os.path.join(os.path.dirname(__file__), "..")
APP_PATH = os.path.join(APP_DIR, "app.py")
TIMEOUT = 90

sys.path.insert(0, os.path.abspath(APP_DIR))


def fresh_app():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=TIMEOUT)
    return at


def assert_ok(at):
    assert not at.exception, f"Unerwartete Exception(s): {[e.message for e in at.exception]}"


def test_default_load():
    at = fresh_app()
    assert_ok(at)
    assert len(at.metric) >= 5  # Greedy/ILP-Anzahl + LP/ILP/Lücke-Kacheln


def test_structure_matches_sibling_demos():
    """Die Demo soll wie die anderen Portfolio-Demos strukturiert sein:
    Ergebnis zuerst, dann Methodenvergleich/Funktionsweise/Mathematik als
    eigene Expander mit den üblichen Übertiteln."""
    at = fresh_app()
    assert_ok(at)
    expander_labels = [e.label for e in at.expander]
    assert any("vollständiger Methodenvergleich" in label for label in expander_labels)
    assert any(label == "Wie funktioniert diese Demo?" for label in expander_labels)
    assert any("Mathematische Formulierung" in label for label in expander_labels)
    tab_labels = [t.label for t in at.tabs]
    assert any("Greedy" in label for label in tab_labels)
    assert any("LP-Relaxierung" in label for label in tab_labels)
    assert any("ILP" in label for label in tab_labels)
    assert any("Vergleich" in label for label in tab_labels)
    assert len(at.dataframe) >= 1  # Methodenvergleich-Tabelle
    assert any("optimierter Schichtplan" in md.value for md in at.markdown)


@pytest.mark.parametrize("label", ["Einzelhandel (1 Spitze)", "Callcenter (2 Spitzen)", "Beispiel mit Ganzzahligkeitslücke"])
def test_presets_apply_without_crash(label):
    at = fresh_app()
    btn = [b for b in at.button if label in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    assert_ok(at)


def test_gap_example_preset_enables_wrap_and_shows_warning():
    at = fresh_app()
    btn = [b for b in at.button if "Ganzzahligkeitslücke" in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    assert_ok(at)
    wrap_checkbox = [c for c in at.sidebar.checkbox if "Mitternacht" in c.label][0]
    assert wrap_checkbox.value is True
    assert any("Ganzzahligkeitslücke gefunden" in w.value for w in at.warning)


def test_wrap_checkbox_toggle():
    at = fresh_app()
    wrap_checkbox = [c for c in at.sidebar.checkbox if "Mitternacht" in c.label][0]
    wrap_checkbox.check().run(timeout=TIMEOUT)
    assert_ok(at)
    wrap_checkbox2 = [c for c in at.sidebar.checkbox if "Mitternacht" in c.label][0]
    assert wrap_checkbox2.value is True
    wrap_checkbox2.uncheck().run(timeout=TIMEOUT)
    assert_ok(at)
    assert any("total unimodular" in s.value for s in at.success)


def test_regenerate_seed_button_changes_seed():
    at = fresh_app()
    seed_before = at.sidebar.number_input(key="seed_input").value
    seed_btn = [b for b in at.sidebar.button if "Neuen Bedarf" in b.label][0]
    seed_btn.click().run(timeout=TIMEOUT)
    assert_ok(at)
    seed_after = at.sidebar.number_input(key="seed_input").value
    assert seed_after != seed_before


@pytest.mark.parametrize("shift_lengths", [[3], [12], [3, 6, 12]])
def test_shift_length_extremes(shift_lengths):
    at = fresh_app()
    ms = at.sidebar.multiselect(key="shift_lengths_multiselect")
    ms.set_value(shift_lengths).run(timeout=TIMEOUT)
    assert_ok(at)


def test_empty_shift_lengths_shows_warning_without_crash():
    at = fresh_app()
    ms = at.sidebar.multiselect(key="shift_lengths_multiselect")
    ms.set_value([]).run(timeout=TIMEOUT)
    assert_ok(at)
    assert any("mindestens eine Schichtlänge" in w.value for w in at.warning)


def test_fixed_cost_slider_default_zero_shows_tu_success():
    at = fresh_app()
    assert_ok(at)
    fixed_slider = [s for s in at.sidebar.slider if "Fixkosten" in s.label][0]
    assert fixed_slider.value == 0.0
    assert any("total unimodular" in s.value for s in at.success)


def test_fixed_cost_slider_nonzero_replaces_tu_success_with_live_check():
    at = fresh_app()
    fixed_slider = [s for s in at.sidebar.slider if "Fixkosten" in s.label][0]
    fixed_slider.set_value(500.0).run(timeout=TIMEOUT)
    assert_ok(at)
    assert not any("total unimodular" in s.value for s in at.success)
    assert any("Fixkosten pro Schichttyp" in i.value for i in at.info) or any(
        "Fixkosten pro Schichttyp" in w.value for w in at.warning
    )


def test_fixed_cost_shows_activated_shift_types_caption():
    at = fresh_app()
    fixed_slider = [s for s in at.sidebar.slider if "Fixkosten" in s.label][0]
    fixed_slider.set_value(500.0).run(timeout=TIMEOUT)
    assert_ok(at)
    assert any("Genutzte Schichttypen" in c.value for c in at.caption)


def test_no_peaks_and_no_base_demand_edge_case():
    """Grenzfall: minimaler Bedarf über den ganzen Tag - Solver muss auch
    dann noch eine sinnvolle (leere oder minimale) Lösung liefern."""
    at = fresh_app()
    base_slider = [s for s in at.sidebar.slider if "Grundbedarf" in s.label][0]
    peak_slider = [s for s in at.sidebar.slider if "Spitzenhöhe" in s.label][0]
    base_slider.set_value(0).run(timeout=TIMEOUT)
    peak_slider.set_value(0).run(timeout=TIMEOUT)
    assert_ok(at)


def test_pdf_download_button_present():
    at = fresh_app()
    assert_ok(at)
    assert any("PDF" in b.label for b in at.download_button)


