"""
Lösungsverfahren für die Schichtplanung: Greedy-Heuristik, LP-Relaxierung
und exaktes ILP - alle über dasselbe Deckungsmodell:

    minimiere   Σ_j cost_j * x_j + Σ_L fixed_cost * y_L
                mit cost_j = cost_per_hour * length_j
    unter       Σ_j (Schicht j deckt Stunde t) * x_j  >=  demand[t]   für alle t
                x_j <= M_j * y_L(j)                    für jede Schicht j
                x_j >= 0 (ganzzahlig bei Greedy/ILP, kontinuierlich bei LP)
                y_L in {0,1} (kontinuierlich [0,1] bei LP) - "Schichtlänge L wird
                überhaupt genutzt"

Kosten skalieren mit der Schichtlänge, damit bei mehreren gleichzeitig
wählbaren Schichttypen ein echter Trade-off entsteht (mehr kurze Schichten
vs. weniger lange Schichten mit mehr Überdeckung). Optional kommt pro
genutzter Schichtlänge eine Fixkosten-Komponente hinzu (z. B. Einrichtung/
Schulung für ein neues Schichtmuster) - das koppelt die Anzahl x_j über eine
Big-M-Nebenbedingung an eine Aktivierungs-Variable y_L und macht die Wahl
zwischen Schichttypen zu einer echten kombinatorischen Entscheidung
(Fixed-Charge-Struktur), nicht mehr nur zu einer linearen Kostenabwägung.
M_j ist dabei die maximale Stundennachfrage, die Schicht j überhaupt
abdeckt - eine beweisbar sichere (und recht enge) obere Schranke für x_j,
da mehr Instanzen einer Schicht als die Bedarfsspitze, die sie abdeckt,
nie nötig sind.

Die LP-Relaxierung und das ILP verwenden dieselbe Nebenbedingungsmatrix -
nur die Variablenart unterscheidet sich. Ist die Matrix total unimodular
(zusammenhängende Schichten, kein Wraparound - unabhängig davon, ob ein
oder mehrere Schichtlängen im Katalog stehen), fallen LP- und ILP-Optimum
zwangsläufig zusammen. Mit Wraparound ist das nicht mehr garantiert; ob
im Einzelfall tatsächlich eine Lücke auftritt, hängt von der konkreten
Bedarfskurve und Schichtlänge ab - deshalb wird das Ergebnis live geprüft
und nicht nur behauptet. Fixkosten pro Schichttyp brechen die TU-Garantie
ebenfalls (und zwar unabhängig vom Wraparound): Big-M-Kopplungen zwischen
x_j und y_L sind i. A. nicht total unimodular, die LP-Relaxierung ist bei
aktiven Fixkosten typischerweise "locker" (klassische Schwäche von
Big-M-Formulierungen) - auch das wird live geprüft, nicht behauptet.
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


def _shift_costs(shifts, cost_per_hour):
    return [float(cost_per_hour) * s["length"] for s in shifts]


def solve_lp_or_ilp(shifts, demand, cost_per_hour, integer, fixed_cost_per_type=0.0):
    solver_name = "CBC" if integer else "GLOP"
    solver = pywraplp.Solver.CreateSolver(solver_name)
    n = len(shifts)
    costs = _shift_costs(shifts, cost_per_hour)
    if integer:
        x = [solver.IntVar(0, solver.infinity(), f"x{j}") for j in range(n)]
    else:
        x = [solver.NumVar(0, solver.infinity(), f"x{j}") for j in range(n)]

    for t in range(T):
        covering = [x[j] for j, s in enumerate(shifts) if s["coverage"][t]]
        solver.Add(solver.Sum(covering) >= float(demand[t]))

    objective_terms = [costs[j] * x[j] for j in range(n)]

    if fixed_cost_per_type > 0:
        lengths = sorted({s["length"] for s in shifts})
        if integer:
            y = {length: solver.IntVar(0, 1, f"y{length}") for length in lengths}
        else:
            y = {length: solver.NumVar(0, 1, f"y{length}") for length in lengths}
        for j, s in enumerate(shifts):
            m_j = float(np.max(demand[s["coverage"]]))
            solver.Add(x[j] <= m_j * y[s["length"]])
        objective_terms += [float(fixed_cost_per_type) * y[length] for length in lengths]

    solver.Minimize(solver.Sum(objective_terms))
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


def solve_greedy(shifts, demand, cost_per_hour, fixed_cost_per_type=0.0):
    """Klassischer gewichteter Greedy-Set-Cover: wiederholt die Schicht mit
    dem besten Verhältnis aus abgedecktem Bedarfsüberhang zu Kosten wählen
    ("bester Gegenwert je Euro"), bis überall gedeckt ist. Bei einer
    einzelnen Schichtlänge (alle Kosten gleich) ist das identisch zum
    einfachen Greedy nach reiner Deckung. Liefert immer eine ganzzahlige,
    zulässige Lösung - aber ohne Optimalitätsgarantie (bekannter
    Log-Approximationsfaktor für Set-Cover-artige Probleme).

    Fixkosten pro Schichttyp werden auf die erste Nutzung einer Länge
    umgelegt: Solange eine Länge noch nicht aktiviert wurde, zählt ihre
    Fixkosten-Komponente zu den Grenzkosten der ersten Instanz dazu - das
    bestraft das Eröffnen eines neuen Schichttyps genau dann, wenn er sich
    (noch) nicht lohnt."""
    remaining = demand.astype(float).copy()
    n = len(shifts)
    costs = _shift_costs(shifts, cost_per_hour)
    counts = [0] * n
    activated_lengths = set()
    guard = 0
    while remaining.max() > FRACTIONAL_EPS and guard < GREEDY_MAX_ITER:
        guard += 1
        best_j, best_score = -1, -1.0
        for j, s in enumerate(shifts):
            cov = s["coverage"]
            covered = np.minimum(remaining, np.where(cov, remaining, 0.0)).sum()
            marginal_cost = costs[j]
            if fixed_cost_per_type > 0 and s["length"] not in activated_lengths:
                marginal_cost += fixed_cost_per_type
            score = covered / marginal_cost
            if score > best_score:
                best_score, best_j = score, j
        if best_j < 0 or best_score <= FRACTIONAL_EPS:
            break
        cov = shifts[best_j]["coverage"]
        remaining = np.where(cov, np.maximum(remaining - 1.0, 0.0), remaining)
        counts[best_j] += 1
        activated_lengths.add(shifts[best_j]["length"])

    objective = sum(c * cost for c, cost in zip(counts, costs)) + fixed_cost_per_type * len(activated_lengths)
    return SolveResult(
        method="Greedy-Heuristik",
        status="feasible" if remaining.max() <= FRACTIONAL_EPS else "infeasible (Iterationslimit)",
        objective=objective,
        counts=counts,
        is_integral=True,
        coverage=_coverage_from_counts(shifts, counts),
    )


def solve_all(shifts, demand, cost_per_hour, fixed_cost_per_type=0.0):
    return {
        "greedy": solve_greedy(shifts, demand, cost_per_hour, fixed_cost_per_type),
        "lp": solve_lp_or_ilp(shifts, demand, cost_per_hour, integer=False, fixed_cost_per_type=fixed_cost_per_type),
        "ilp": solve_lp_or_ilp(shifts, demand, cost_per_hour, integer=True, fixed_cost_per_type=fixed_cost_per_type),
    }
