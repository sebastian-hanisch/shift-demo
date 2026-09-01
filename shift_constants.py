"""
Zentrale Konstanten für die Schichtplanung-Demo
(Sebastian Hanisch - Operations Research und Machine Learning).
"""

T = 24  # Stunden pro Tag - fester Horizont, um die Demo einfach zu halten

DEFAULT_SHIFT_LENGTH = 8
DEFAULT_COST_PER_SHIFT = 250.0
DEFAULT_BASE_DEMAND = 2
DEFAULT_PEAK_HEIGHT = 8

# Feste, geprüfte Kombination, die unter Wraparound zuverlässig eine
# Ganzzahligkeitslücke zwischen LP-Relaxierung und ILP erzeugt (siehe
# Prototyp-Suche: ~22% der Zufallskombinationen zeigen eine Lücke, diese
# hier ist eine der stärksten und daher als Beispiel-Preset hinterlegt).
GAP_EXAMPLE = {
    "shift_length": 5,
    "n_peaks": 1,
    "peak_conc": 0.2,
    "seed": 1,
    "base_demand": DEFAULT_BASE_DEMAND,
    "peak_height": DEFAULT_PEAK_HEIGHT,
}

GREEDY_MAX_ITER = 5_000
FEEDBACK_FILE = "feedback_log.csv"
