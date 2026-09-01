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
from shift_evaluation import (
    active_shift_instances,
    fractional_shift_rows,
    overstaffing_hours,
    total_shifts,
    used_shift_types,
)
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


def test_shift_catalog_multiple_lengths_combines_all():
    lengths = [4, 6, 8]
    shifts = shift_catalog(lengths, allow_wrap=False)
    assert len(shifts) == sum(T - l + 1 for l in lengths)
    found_lengths = {s["length"] for s in shifts}
    assert found_lengths == set(lengths)
    for s in shifts:
        assert s["coverage"].sum() == s["length"]


def test_shift_catalog_single_int_equals_single_element_list():
    from_int = shift_catalog(8, allow_wrap=False)
    from_list = shift_catalog([8], allow_wrap=False)
    assert len(from_int) == len(from_list)
    for a, b in zip(from_int, from_list):
        assert a["start"] == b["start"] and a["length"] == b["length"]
        assert (a["coverage"] == b["coverage"]).all()


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
    result = solve_greedy(shifts, demand, cost_per_hour=100.0)
    assert (result.coverage >= demand - 1e-6).all()
    assert result.is_integral


def test_ilp_covers_demand_and_is_integral(small_instance):
    demand, shifts = small_instance
    result = solve_lp_or_ilp(shifts, demand, cost_per_hour=100.0, integer=True)
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


def test_no_wrap_lp_equals_ilp_with_mixed_lengths():
    """TU hängt an der Intervallform jeder einzelnen Schicht, nicht an einer
    einheitlichen Länge - mehrere gemischte Schichtlängen ohne Wraparound
    müssen also weiterhin eine ganzzahlige LP-Lösung liefern."""
    for seed in range(5):
        demand = demand_curve(2, 0.5, seed, 2, 8)
        shifts = shift_catalog([4, 6, 8, 10], allow_wrap=False)
        lp = solve_lp_or_ilp(shifts, demand, 30.0, integer=False)
        ilp = solve_lp_or_ilp(shifts, demand, 30.0, integer=True)
        assert lp.is_integral, f"LP sollte ganzzahlig sein (seed={seed}, gemischte Längen)"
        assert abs(lp.objective - ilp.objective) < 1e-4


def test_fixed_cost_zero_matches_no_fixed_cost_baseline():
    """fixed_cost_per_type=0.0 (Default) darf sich nicht vom alten,
    reinen linearen Modell unterscheiden - keine Binärvariablen/Big-M
    aktiv, wenn das Feature aus ist."""
    demand = demand_curve(2, 0.5, 42, 2, 8)
    shifts = shift_catalog([4, 6, 8], allow_wrap=False)
    ilp_default = solve_lp_or_ilp(shifts, demand, 30.0, integer=True)
    ilp_explicit = solve_lp_or_ilp(shifts, demand, 30.0, integer=True, fixed_cost_per_type=0.0)
    assert ilp_default.objective == pytest.approx(ilp_explicit.objective)


def test_fixed_cost_adds_binary_activation_cost_to_ilp_objective():
    """Das ILP-Ziel muss dem linearen Stundenanteil plus Fixkosten je
    tatsächlich genutztem Schichttyp entsprechen."""
    demand = demand_curve(1, 0.5, 1, 2, 8)
    shifts = shift_catalog([4, 6, 8], allow_wrap=False)
    fixed_cost = 200.0
    ilp = solve_lp_or_ilp(shifts, demand, 30.0, integer=True, fixed_cost_per_type=fixed_cost)
    used = used_shift_types(shifts, ilp.counts)
    hourly_component = sum(c * s["length"] * 30.0 for c, s in zip(ilp.counts, shifts))
    assert ilp.objective == pytest.approx(hourly_component + fixed_cost * len(used))


def test_fixed_cost_can_break_tu_even_without_wrap():
    """Anders als reine Stundenkosten koppeln Fixkosten pro Schichttyp die
    Anzahlen x_j über Big-M an Binärvariablen - diese Fixed-Charge-Struktur
    ist i. A. nicht total unimodular, eine Ganzzahligkeitslücke kann also
    auch ganz ohne Wraparound auftreten. Regressionsschutz für eine konkret
    geprüfte Kombination."""
    demand = demand_curve(1, 0.5, 1, 2, 8)
    shifts = shift_catalog([4, 6, 8], allow_wrap=False)
    lp = solve_lp_or_ilp(shifts, demand, 30.0, integer=False, fixed_cost_per_type=200.0)
    ilp = solve_lp_or_ilp(shifts, demand, 30.0, integer=True, fixed_cost_per_type=200.0)
    assert ilp.objective - lp.objective > 1.0


def test_greedy_amortizes_fixed_cost_onto_first_use():
    """Solange eine Schichtlänge noch nicht aktiviert wurde, muss Greedy
    ihre Fixkosten in die Bewertung der ersten Instanz einpreisen - das
    Greedy-Ziel muss daher exakt Stundenkosten plus Fixkosten je
    tatsächlich genutztem Typ ergeben (keine "vergessenen" Fixkosten)."""
    demand = demand_curve(2, 0.5, 42, 2, 8)
    shifts = shift_catalog([4, 6, 8], allow_wrap=False)
    fixed_cost = 300.0
    result = solve_greedy(shifts, demand, 30.0, fixed_cost_per_type=fixed_cost)
    used = used_shift_types(shifts, result.counts)
    hourly_component = sum(c * s["length"] * 30.0 for c, s in zip(result.counts, shifts))
    assert result.objective == pytest.approx(hourly_component + fixed_cost * len(used))
    assert (result.coverage >= demand - 1e-6).all()


def test_high_fixed_cost_pushes_greedy_towards_fewer_shift_types():
    """Bei sehr hohen Fixkosten pro Typ sollte Greedy sich auf möglichst
    wenige Schichtlängen beschränken, statt naiv nach reiner Deckung pro
    Stunde zu wählen."""
    demand = demand_curve(2, 0.5, 42, 2, 8)
    shifts = shift_catalog([4, 6, 8, 10], allow_wrap=False)
    cheap = solve_greedy(shifts, demand, 30.0, fixed_cost_per_type=0.0)
    expensive = solve_greedy(shifts, demand, 30.0, fixed_cost_per_type=5000.0)
    n_types_cheap = len(used_shift_types(shifts, cheap.counts))
    n_types_expensive = len(used_shift_types(shifts, expensive.counts))
    assert n_types_expensive <= n_types_cheap


def test_gap_example_actually_shows_a_gap():
    """Regressionsschutz für die in shift_constants.GAP_EXAMPLE hinterlegte
    Parameterkombination: sie muss zuverlässig eine echte
    Ganzzahligkeitslücke zwischen LP und ILP erzeugen, sonst verfehlt das
    zugehörige Demo-Preset seinen didaktischen Zweck."""
    g = GAP_EXAMPLE
    demand = demand_curve(g["n_peaks"], g["peak_conc"], g["seed"], g["base_demand"], g["peak_height"])
    shifts = shift_catalog(g["shift_lengths"], allow_wrap=True)
    lp = solve_lp_or_ilp(shifts, demand, 100.0, integer=False)
    ilp = solve_lp_or_ilp(shifts, demand, 100.0, integer=True)
    assert not lp.is_integral
    assert ilp.objective - lp.objective > 0.01


def test_cost_scales_with_shift_length():
    """Kosten sind pro Stunde definiert, nicht pro Schicht - eine 4h-Schicht
    muss halb so viel kosten wie eine ansonsten gleiche 8h-Schicht."""
    demand = np.full(T, 1)
    short = shift_catalog(4, allow_wrap=False)
    long = shift_catalog(8, allow_wrap=False)
    ilp_short = solve_lp_or_ilp(short, demand, cost_per_hour=10.0, integer=True)
    ilp_long = solve_lp_or_ilp(long, demand, cost_per_hour=10.0, integer=True)
    assert ilp_short.objective == pytest.approx(4 * 10.0 * sum(ilp_short.counts))
    assert ilp_long.objective == pytest.approx(8 * 10.0 * sum(ilp_long.counts))


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


def test_used_shift_types_only_counts_nonzero():
    shifts = shift_catalog([4, 6, 8], allow_wrap=False)
    counts = [0.0] * len(shifts)
    lengths = [s["length"] for s in shifts]
    counts[lengths.index(6)] = 2.0
    assert used_shift_types(shifts, counts) == [6]


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
    shifts = shift_catalog(GAP_EXAMPLE["shift_lengths"], allow_wrap=True)
    lp = solve_lp_or_ilp(shifts, demand, 100.0, integer=False)
    pdf_bytes = generate_shift_plan_pdf("Test", shifts, lp, demand, 100.0)
    assert pdf_bytes[:4] == b"%PDF"


def test_pdf_export_with_fixed_cost_returns_bytes(small_instance):
    demand, shifts = small_instance
    result = solve_lp_or_ilp(shifts, demand, 100.0, integer=True, fixed_cost_per_type=200.0)
    pdf_bytes = generate_shift_plan_pdf("Test", shifts, result, demand, 100.0, fixed_cost_per_type=200.0)
    assert pdf_bytes[:4] == b"%PDF"
