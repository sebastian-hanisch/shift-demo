"""Unabhängiges Orakel für die Schichtplanung: LP/ILP mit scipy (HiGHS) statt OR-Tools, Fixkosten-ILP ohne
Big-M über Aufzählung der erlaubten Schichtlängen-Teilmengen, Greedy und Nachfragekurve unabhängig nachgebaut."""

import itertools
import math
import random

import numpy as np
import pytest

from shift_model import demand_curve, shift_catalog
from shift_solver import solve_all

optimize = pytest.importorskip("scipy.optimize")

T = 24


def _columns(lengths, wrap):
    return [
        (length, s, [(s + k) % T for k in range(length)])
        for length in lengths
        for s in (range(T) if wrap else range(T - length + 1))
    ]


def _matrix(cols):
    a = np.zeros((T, len(cols)))
    for j, (_length, _s, hours) in enumerate(cols):
        a[hours, j] = 1
    return a


def _oracle_lp(lengths, wrap, d, cph, fixed):
    cols = _columns(lengths, wrap)
    a = _matrix(cols)
    n, types = len(cols), sorted(set(lengths))
    if fixed > 0:
        c = np.concatenate([[cph * length for length, _, _ in cols], [fixed] * len(types)])
        a_ub = np.zeros((T + n, n + len(types)))
        b_ub = np.zeros(T + n)
        a_ub[:T, :n], b_ub[:T] = -a, -d
        for j, (length, _s, hours) in enumerate(cols):
            a_ub[T + j, j] = 1
            a_ub[T + j, n + types.index(length)] = -max(d[h] for h in hours)
        bounds = [(0, None)] * n + [(0, 1)] * len(types)
        return optimize.linprog(c, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs").fun
    c = np.array([cph * length for length, _, _ in cols])
    return optimize.linprog(c, A_ub=-a, b_ub=-d, bounds=(0, None), method="highs").fun


def _oracle_ilp(lengths, wrap, d, cph, fixed):
    if (d <= 0).all():
        return 0.0
    best = float("inf")
    types = sorted(set(lengths))
    for r in range(1, len(types) + 1):
        for subset in itertools.combinations(types, r):
            cols = _columns(subset, wrap)
            res = optimize.milp(
                np.array([cph * length for length, _, _ in cols]),
                constraints=optimize.LinearConstraint(_matrix(cols), d.astype(float), np.inf),
                integrality=np.ones(len(cols)), bounds=optimize.Bounds(0, np.inf), options={"mip_rel_gap": 0},
            )
            if res.status == 0:
                best = min(best, res.fun + fixed * len(subset))
    return best


def _oracle_greedy_cost(lengths, wrap, d, cph, fixed):
    cols = sorted(_columns(lengths, wrap), key=lambda c: (c[0], c[1]))
    rem = d.astype(float).copy()
    active, total = set(), 0.0
    while rem.max() > 1e-6:
        best, best_score = None, -1.0
        for length, s, hours in cols:
            marginal = cph * length + (fixed if fixed > 0 and length not in active else 0.0)
            score = sum(rem[h] for h in hours) / marginal
            if score > best_score:
                best, best_score = (length, hours), score
        length, hours = best
        rem[hours] = np.maximum(rem[hours] - 1, 0)
        active.add(length)
        total += cph * length
    return total + fixed * len(active)


def _oracle_demand(n_peaks, conc, seed, base, height):
    rng = np.random.default_rng(seed)
    centers = rng.uniform(0, T, size=n_peaks)
    spread = 1 + (1 - conc) * 4
    return np.array([
        int(round(base + sum(height * math.exp(-((t - (c + k * T)) ** 2) / (2 * spread ** 2))
                             for c in centers for k in (-1, 0, 1))))
        for t in range(T)
    ])


def test_demand_curve_matches_direct_formula():
    rng = random.Random(1)
    for _ in range(100):
        args = (rng.randint(1, 3), rng.random(), rng.randint(0, 10 ** 6), rng.randint(0, 10), rng.randint(2, 20))
        assert np.array_equal(demand_curve(*args), _oracle_demand(*args))


def test_lp_ilp_and_greedy_against_scipy_oracle():
    rng = random.Random(2024)
    for _ in range(40):
        lengths = sorted(rng.sample(range(3, 13), rng.choice([1, 1, 2])))
        wrap = rng.random() < 0.6
        fixed = rng.choice([0.0, 0.0, 200.0, 600.0, 1500.0])
        cph = rng.choice([5.0, 30.0, 100.0])
        d = demand_curve(rng.randint(1, 3), rng.random(), rng.randint(0, 10 ** 6), rng.randint(0, 10), rng.randint(2, 20))
        res = solve_all(shift_catalog(lengths, wrap), d, cph, fixed)

        tol = 1e-4 * max(1.0, _oracle_ilp(lengths, wrap, d, cph, fixed))
        assert res["lp"].objective == pytest.approx(_oracle_lp(lengths, wrap, d, cph, fixed), abs=tol)
        assert res["ilp"].objective == pytest.approx(_oracle_ilp(lengths, wrap, d, cph, fixed), abs=tol)
        assert res["greedy"].objective == pytest.approx(_oracle_greedy_cost(lengths, wrap, d, cph, fixed), abs=1e-6)
        assert (res["ilp"].coverage >= d - 1e-6).all() and (res["greedy"].coverage >= d - 1e-6).all()
        if not wrap and fixed == 0:
            assert res["lp"].objective == pytest.approx(res["ilp"].objective, abs=1e-4)
