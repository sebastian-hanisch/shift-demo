"""
Lösungsverfahren für die Schichtplanung: Greedy-Heuristik, LP-Relaxierung
und exaktes ILP - alle über dasselbe Deckungsmodell:

    minimiere   Σ_j cost * x_j
    unter       Σ_j (Schicht j deckt Stunde t) * x_j  >=  demand[t]   für alle t
                x_j >= 0 (ganzzahlig bei Greedy/ILP, kontinuierlich bei LP)

Die LP-Relaxierung und das ILP verwenden dieselbe Nebenbedingungsmatrix -
nur die Variablenart unterscheidet sich. Ist die Matrix total unimodular
(zusammenhängende Schichten, kein Wraparound), fallen LP- und ILP-Optimum
zwangsläufig zusammen. Mit Wraparound ist das nicht mehr garantiert; ob
im Einzelfall tatsächlich eine Lücke auftritt, hängt von der konkreten
Bedarfskurve und Schichtlänge ab - deshalb wird das Ergebnis live geprüft
und nicht nur behauptet.
"""

from dataclasses import dataclass, field

import numpy as np
from ortools.linear_solver import pywraplp

from shift_constants import GREEDY_MAX_ITER, T

FRACTIONAL_EPS = 1e-6


@dataclass
class SolveResult:
    method: str
    status: str
    objective: float
    counts: list  # Anzahl Instanzen je Schichttyp (kann fraktional sein bei LP)
    is_integral: bool
    coverage: np.ndarray = field(default_factory=lambda: np.zeros(T))


def _coverage_from_counts(shifts, counts):
    cov = np.zeros(T)
    for c, s in zip(counts, shifts):
        if c:
            cov += c * s["coverage"]
    return cov


def solve_lp_or_ilp(shifts, demand, cost_per_shift, integer):
    solver_name = "CBC" if integer else "GLOP"
    solver = pywraplp.Solver.CreateSolver(solver_name)
    n = len(shifts)
    if integer:
        x = [solver.IntVar(0, solver.infinity(), f"x{j}") for j in range(n)]
    else:
        x = [solver.NumVar(0, solver.infinity(), f"x{j}") for j in range(n)]

    for t in range(T):
        covering = [x[j] for j, s in enumerate(shifts) if s["coverage"][t]]
        solver.Add(solver.Sum(covering) >= float(demand[t]))

    solver.Minimize(solver.Sum(float(cost_per_shift) * x[j] for j in range(n)))
    status_code = solver.Solve()

    ok = status_code in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)
    status = "optimal" if status_code == pywraplp.Solver.OPTIMAL else ("infeasible" if not ok else "feasible")
    counts = [v.solution_value() for v in x] if ok else [0.0] * n
    objective = solver.Objective().Value() if ok else float("nan")
    is_integral = all(abs(c - round(c)) < FRACTIONAL_EPS for c in counts)

    return SolveResult(
        method="LP-Relaxierung" if not integer else "Exaktes ILP",
        status=status,
        objective=objective,
        counts=counts,
        is_integral=is_integral,
        coverage=_coverage_from_counts(shifts, counts),
    )


def solve_greedy(shifts, demand, cost_per_shift):
    """Klassischer Greedy-Set-Cover: wiederholt die Schicht wählen, die den
    aktuell größten Bedarfsüberhang abdeckt, bis überall gedeckt ist. Liefert
    immer eine ganzzahlige, zulässige Lösung - aber ohne Optimalitätsgarantie
    (bekannter Log-Approximationsfaktor für Set-Cover-artige Probleme)."""
    remaining = demand.astype(float).copy()
    n = len(shifts)
    counts = [0] * n
    guard = 0
    while remaining.max() > FRACTIONAL_EPS and guard < GREEDY_MAX_ITER:
        guard += 1
        best_j, best_score = -1, -1.0
        for j, s in enumerate(shifts):
            cov = s["coverage"]
            score = np.minimum(remaining, np.where(cov, remaining, 0.0)).sum()
            if score > best_score:
                best_score, best_j = score, j
        if best_j < 0 or best_score <= FRACTIONAL_EPS:
            break
        cov = shifts[best_j]["coverage"]
        remaining = np.where(cov, np.maximum(remaining - 1.0, 0.0), remaining)
        counts[best_j] += 1

    objective = sum(counts) * float(cost_per_shift)
    return SolveResult(
        method="Greedy-Heuristik",
        status="feasible" if remaining.max() <= FRACTIONAL_EPS else "infeasible (Iterationslimit)",
        objective=objective,
        counts=counts,
        is_integral=True,
        coverage=_coverage_from_counts(shifts, counts),
    )


def solve_all(shifts, demand, cost_per_shift):
    return {
        "greedy": solve_greedy(shifts, demand, cost_per_shift),
        "lp": solve_lp_or_ilp(shifts, demand, cost_per_shift, integer=False),
        "ilp": solve_lp_or_ilp(shifts, demand, cost_per_shift, integer=True),
    }
