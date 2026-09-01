"""
Unit-Tests der reinen Modell-/Solver-/Bewertungslogik (kein Streamlit-UI-Code).

Ausführen mit: pytest tests/ -v
"""

import os
import sys

import numpy as np
import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.abspath(APP_DIR))

from shift_constants import GAP_EXAMPLE, T
from shift_evaluation import active_shift_instances, fractional_shift_rows, overstaffing_hours, total_shifts
from shift_model import demand_curve, shift_catalog, shift_label
from shift_pdf_export import generate_shift_plan_pdf
from shift_solver import solve_all, solve_greedy, solve_lp_or_ilp


# ==========================================================================
# Nachfragekurve
# ==========================================================================

def test_demand_curve_shape_and_nonnegative():
    d = demand_curve(n_peaks=2, peak_conc=0.5, seed=42, base_demand=2, peak_height=8)
    assert d.shape == (T,)
    assert (d >= 0).all()


def test_demand_curve_deterministic():
    d1 = demand_curve(2, 0.5, 42, 2, 8)
    d2 = demand_curve(2, 0.5, 42, 2, 8)
    assert (d1 == d2).all()


def test_demand_curve_different_seed_differs():
    d1 = demand_curve(2, 0.5, 42, 2, 8)
    d2 = demand_curve(2, 0.5, 43, 2, 8)
    assert not (d1 == d2).all()


# ==========================================================================
# Schichtkatalog
# ==========================================================================

def test_shift_catalog_no_wrap_count_and_length():
    length = 8
    shifts = shift_catalog(length, allow_wrap=False)
    assert len(shifts) == T - length + 1
    for s in shifts:
        assert s["coverage"].sum() == length
        assert not s["wraps"]


def test_shift_catalog_no_wrap_is_contiguous():
    """Kernvoraussetzung für TU: die Deckung jeder Schicht ist ein
    zusammenhängender Block ohne Lücke."""
    for s in shift_catalog(7, allow_wrap=False):
        idx = np.where(s["coverage"])[0]
        assert (idx == np.arange(idx[0], idx[0] + len(idx))).all()


def test_shift_catalog_wrap_count_and_length():
    length = 8
    shifts = shift_catalog(length, allow_wrap=True)
    assert len(shifts) == T
    for s in shifts:
        assert s["coverage"].sum() == length
    assert any(s["wraps"] for s in shifts)


def test_shift_label_formats_wraparound():
    label = shift_label(22, 8)
    assert "22:00" in label
    assert "ueber Mitternacht" in label


# ==========================================================================
# Solver: Machbarkeit, Ganzzahligkeit, TU-Verhalten
# ==========================================================================

@pytest.fixture
def small_instance():
    demand = demand_curve(2, 0.5, 42, 2, 8)
    shifts = shift_catalog(8, allow_wrap=False)
    return demand, shifts


def test_greedy_covers_demand(small_instance):
    demand, shifts = small_instance
    result = solve_greedy(shifts, demand, cost_per_shift=100.0)
    assert (result.coverage >= demand - 1e-6).all()
    assert result.is_integral


def test_ilp_covers_demand_and_is_integral(small_instance):
    demand, shifts = small_instance
    result = solve_lp_or_ilp(shifts, demand, cost_per_shift=100.0, integer=True)
    assert result.status in ("optimal", "feasible")
    assert (result.coverage >= demand - 1e-6).all()
    assert result.is_integral


def test_lp_objective_never_exceeds_ilp_objective(small_instance):
    """LP-Relaxierung ist eine Lockerung des ILP - ihr Optimum kann nie
    schlechter (teurer) sein als das ganzzahlige Optimum."""
    demand, shifts = small_instance
    lp = solve_lp_or_ilp(shifts, demand, 100.0, integer=False)
    ilp = solve_lp_or_ilp(shifts, demand, 100.0, integer=True)
    assert lp.objective <= ilp.objective + 1e-6


def test_no_wrap_lp_equals_ilp_across_instances():
    """Ohne Wraparound ist die Matrix eine Intervallmatrix -> total
    unimodular -> LP-Relaxierung und ILP müssen exakt übereinstimmen."""
    for seed in range(5):
        for length in (5, 6, 8, 10):
            demand = demand_curve(2, 0.5, seed, 2, 8)
            shifts = shift_catalog(length, allow_wrap=False)
            lp = solve_lp_or_ilp(shifts, demand, 100.0, integer=False)
            ilp = solve_lp_or_ilp(shifts, demand, 100.0, integer=True)
            assert lp.is_integral, f"LP sollte ganzzahlig sein (seed={seed}, length={length})"
            assert abs(lp.objective - ilp.objective) < 1e-4


def test_gap_example_actually_shows_a_gap():
    """Regressionsschutz für die in shift_constants.GAP_EXAMPLE hinterlegte
    Parameterkombination: sie muss zuverlässig eine echte
    Ganzzahligkeitslücke zwischen LP und ILP erzeugen, sonst verfehlt das
    zugehörige Demo-Preset seinen didaktischen Zweck."""
    g = GAP_EXAMPLE
    demand = demand_curve(g["n_peaks"], g["peak_conc"], g["seed"], g["base_demand"], g["peak_height"])
    shifts = shift_catalog(g["shift_length"], allow_wrap=True)
    lp = solve_lp_or_ilp(shifts, demand, 100.0, integer=False)
    ilp = solve_lp_or_ilp(shifts, demand, 100.0, integer=True)
    assert not lp.is_integral
    assert ilp.objective - lp.objective > 0.01


def test_solve_all_keys():
    demand = demand_curve(2, 0.5, 42, 2, 8)
    shifts = shift_catalog(8, allow_wrap=False)
    results = solve_all(shifts, demand, 100.0)
    assert set(results.keys()) == {"greedy", "lp", "ilp"}


# ==========================================================================
# Kennzahlen
# ==========================================================================

def test_overstaffing_hours_simple():
    demand = np.array([1.0, 2.0, 3.0])
    coverage = np.array([2.0, 2.0, 2.0])
    assert overstaffing_hours(coverage, demand) == pytest.approx(1.0)  # nur Stunde 0: 2-1=1


def test_active_shift_instances_rounds_and_skips_zero():
    shifts = shift_catalog(4, allow_wrap=False)
    counts = [0.0] * len(shifts)
    counts[0] = 2.4
    rows = active_shift_instances(shifts, counts)
    assert len(rows) == 1
    assert rows[0]["count"] == 2


def test_fractional_shift_rows_detects_only_fractional():
    shifts = shift_catalog(4, allow_wrap=False)
    counts = [0.0] * len(shifts)
    counts[0] = 1.0
    counts[1] = 1.5
    rows = fractional_shift_rows(shifts, counts)
    assert len(rows) == 1
    assert rows[0]["start"] == shifts[1]["start"]


def test_total_shifts():
    assert total_shifts([1, 2.5, 0]) == pytest.approx(3.5)


# ==========================================================================
# PDF-Export
# ==========================================================================

def test_pdf_export_returns_bytes(small_instance):
    demand, shifts = small_instance
    result = solve_lp_or_ilp(shifts, demand, 100.0, integer=True)
    pdf_bytes = generate_shift_plan_pdf("Test", shifts, result, demand, 100.0)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"


def test_pdf_export_handles_fractional_lp_result(small_instance):
    """Der PDF-Export muss auch mit einer fraktionalen LP-Lösung
    klarkommen (z. B. wenn man ihn versehentlich auf lp statt ilp anwendet)."""
    demand = demand_curve(GAP_EXAMPLE["n_peaks"], GAP_EXAMPLE["peak_conc"], GAP_EXAMPLE["seed"], GAP_EXAMPLE["base_demand"], GAP_EXAMPLE["peak_height"])
    shifts = shift_catalog(GAP_EXAMPLE["shift_length"], allow_wrap=True)
    lp = solve_lp_or_ilp(shifts, demand, 100.0, integer=False)
    pdf_bytes = generate_shift_plan_pdf("Test", shifts, lp, demand, 100.0)
    assert pdf_bytes[:4] == b"%PDF"
