"""Kennzahlen und Aufbereitung einer Lösung für Anzeige/Export."""

import numpy as np

from shift_constants import T


def overstaffing_hours(coverage, demand):
    return float(np.maximum(coverage - demand, 0).sum())


GAP_TOLERANCE = 0.01  # € - darunter gelten LP- und ILP-Kosten als gleich


def classify_tu_check(tu_holds, gap, lp_is_integral, tol=GAP_TOLERANCE):
    """Ordnet das Live-Ergebnis des TU-Checks einer von vier Aussagen zu:

    - "tu": TU ist garantiert (kein Wraparound, keine Fixkosten).
    - "gap": LP-Kosten liegen unter den ILP-Kosten - eine echte Ganzzahligkeits-
      lücke. Maßgeblich sind die KOSTEN, nicht `lp_is_integral`: bei Fixkosten
      kann die Schichtanzahl x ganzzahlig sein, während die Aktivierungs-
      variable y fraktional ist und die LP trotzdem billiger bleibt.
    - "no_gap_integral": keine Lücke, LP-Lösung ganzzahlig.
    - "no_gap_fractional": keine Lücke, aber die LP-Lösung enthält fraktionale
      Werte (alternative Optima: eine gleich teure ganzzahlige Lösung existiert).
    """
    if tu_holds:
        return "tu"
    if gap > tol:
        return "gap"
    return "no_gap_integral" if lp_is_integral else "no_gap_fractional"


def total_shifts(counts):
    return float(sum(counts))


def used_shift_types(shifts, counts, eps=1e-6):
    """Sortierte Liste der Schichtlängen, die tatsächlich (auch nur
    fraktional) genutzt werden - relevant, um sichtbar zu machen, wie viele
    unterschiedliche Schichttypen aktiviert wurden (z. B. bei Fixkosten pro
    Typ)."""
    return sorted({s["length"] for s, c in zip(shifts, counts) if c > eps})


def active_shift_instances(shifts, counts, round_counts=True):
    """Baut eine flache Liste einzelner Schicht-Instanzen (für Tabellen/Gantt).

    Bei fraktionalen LP-Anzahlen wird aufgerundet und ein Hinweis mitgegeben -
    ein Gantt-Balken für 0.5 Personen ergibt keinen Sinn; die Fraktionalität
    selbst wird an anderer Stelle (Balkendiagramm der x_j) sichtbar gemacht.
    """
    rows = []
    for s, c in zip(shifts, counts):
        n = int(round(c)) if round_counts else c
        if n <= 0:
            continue
        rows.append({
            "start": s["start"],
            "length": s["length"],
            "wraps": s["wraps"],
            "count": n,
            "raw_count": c,
        })
    rows.sort(key=lambda r: r["start"])
    return rows


def fractional_shift_rows(shifts, counts):
    """Nur die Schichten mit einer echt fraktionalen Anzahl - für die
    Visualisierung des LP-Relaxierungsergebnisses."""
    rows = []
    for s, c in zip(shifts, counts):
        if abs(c - round(c)) > 1e-6:
            rows.append({"start": s["start"], "length": s["length"], "wraps": s["wraps"], "count": c})
    rows.sort(key=lambda r: r["start"])
    return rows
