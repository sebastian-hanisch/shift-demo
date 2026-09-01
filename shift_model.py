"""
Nachfragegenerierung und Schichtkatalog für die Schichtplanung-Demo.

Der Bedarf wird als (im Kreis geglättete) Überlagerung von Nachfragespitzen
über einen 24h-Horizont erzeugt - analog zum Muster in den anderen
Demos (z. B. Tor-Zuordnung, LKW-Terminvergabe: Seed, Anzahl Peaks,
Peak-Konzentration).
"""

import numpy as np

from shift_constants import T


def demand_curve(n_peaks, peak_conc, seed, base_demand, peak_height):
    """Erzeugt einen stündlichen Mindestpersonalbedarf über T Stunden.

    peak_conc in [0,1]: hohe Werte = schmale, ausgeprägte Spitzen (z. B.
    Stoßzeiten im Einzelhandel), niedrige Werte = breite, flache Verläufe.
    Peaks werden zyklisch gespiegelt (t-T, t, t+T), damit die Kurve am
    Tagesrand (0h/24h) glatt anschließt - unabhängig davon, ob später
    Schichten über Mitternacht hinweg erlaubt werden.
    """
    rng = np.random.default_rng(int(seed))
    centers = rng.uniform(0, T, size=int(n_peaks))
    spread = 1.0 + (1.0 - float(peak_conc)) * 4.0
    t = np.arange(T)
    d = np.full(T, float(base_demand))
    for c in centers:
        for k in (-1, 0, 1):
            dist = t - (c + k * T)
            d += float(peak_height) * np.exp(-(dist ** 2) / (2 * spread ** 2))
    return np.round(d).astype(int)


def shift_catalog(length, allow_wrap):
    """Liste möglicher Schichten als (Start, Deckungs-Bitmaske über T Stunden).

    Ohne Wraparound deckt jede Schicht einen zusammenhängenden Block ohne
    Lücke innerhalb [0,T) ab (Intervallstruktur -> Nebenbedingungsmatrix
    ist total unimodular). Mit Wraparound dürfen Schichten über Mitternacht
    hinweg laufen (z. B. 22-6 Uhr) - das Deckungsmuster ist dann im linearen
    Stundenraster nicht mehr zusammenhängend, die Intervalleigenschaft und
    damit die TU-Garantie entfällt.
    """
    length = int(length)
    shifts = []
    starts = range(T) if allow_wrap else range(T - length + 1)
    for s in starts:
        cov = np.zeros(T, dtype=bool)
        for k in range(length):
            cov[(s + k) % T] = True
        shifts.append({"start": s, "length": length, "wraps": (s + length) > T, "coverage": cov})
    return shifts


def shift_label(start, length):
    """ASCII-only Label - wird auch im PDF-Export verwendet, dessen
    Core-Font (Helvetica) keine Sonderzeichen wie Halbgeviertstrich oder
    Umlaute darstellen kann (siehe pack_pdf_export.py-Konvention: 'EUR'
    statt Euro-Zeichen, 'ae/oe/ue' statt Umlaute, Bindestrich statt Gedankenstrich)."""
    end = (start + length) % T
    wraps = (start + length) > T
    suffix = " (ueber Mitternacht)" if wraps else ""
    return f"{start:02d}:00-{end:02d}:00{suffix}"
