"""Kennzahlen und Aufbereitung einer Lösung für Anzeige/Export."""

import numpy as np

from shift_constants import T


def overstaffing_hours(coverage, demand):
    return float(np.maximum(coverage - demand, 0).sum())


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
