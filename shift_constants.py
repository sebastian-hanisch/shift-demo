"""
Zentrale Konstanten für die Schichtplanung-Demo
(Sebastian Hanisch - Operations Research und Machine Learning).
"""

T = 24  # Stunden pro Tag - fester Horizont, um die Demo einfach zu halten

AVAILABLE_SHIFT_LENGTHS = list(range(3, 13))  # 3-12h, wählbar per Multiselect
DEFAULT_SHIFT_LENGTHS = [6, 8, 10]
DEFAULT_COST_PER_HOUR = 30.0
DEFAULT_FIXED_COST_PER_TYPE = 0.0  # aus: reine lineare Stundenkosten wie bisher
DEFAULT_BASE_DEMAND = 2
DEFAULT_PEAK_HEIGHT = 8

# Feste, geprüfte Kombination, die unter Wraparound zuverlässig eine
# Ganzzahligkeitslücke zwischen LP-Relaxierung und ILP erzeugt (siehe
# Prototyp-Suche: ~22% der Zufallskombinationen zeigen eine Lücke, diese
# hier ist eine der stärksten und daher als Beispiel-Preset hinterlegt).
# Bewusst eine einzelne Schichtlänge, damit die Ganzzahligkeitslücke
# eindeutig auf den Wraparound zurückzuführen ist und nicht auf das
# Zusammenspiel mehrerer Schichtlängen.
GAP_EXAMPLE = {
    "shift_lengths": [5],
    "n_peaks": 1,
    "peak_conc": 0.2,
    "seed": 1,
    "base_demand": DEFAULT_BASE_DEMAND,
    "peak_height": DEFAULT_PEAK_HEIGHT,
}

GREEDY_MAX_ITER = 5_000
