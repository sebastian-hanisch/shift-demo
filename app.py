"""
Schichtplanung (Personalbedarfsdeckung) – interaktive Demo
Sebastian Hanisch - Operations Research und Machine Learning

Features:
- Stündlicher Personalbedarf über 24h, synthetisch erzeugt (Seed, Anzahl
  Nachfragespitzen, Konzentration).
- Drei Lösungsverfahren im Vergleich: Greedy-Heuristik (immer ganzzahlig),
  LP-Relaxierung (kontinuierlich) und exaktes ILP (Google OR-Tools).
- Kernthema: totale Unimodularität. Solange Schichten zusammenhängende
  Zeitblöcke ohne Lücke abdecken (keine Nachtschicht über Mitternacht
  hinweg), ist die Nebenbedingungsmatrix eine Intervallmatrix und damit
  total unimodular - die LP-Relaxierung liefert automatisch eine
  ganzzahlige Lösung, ein ILP-Solver ist dafür streng genommen nicht
  nötig. Erlaubt man Schichten über Mitternacht hinweg (Wraparound),
  entfällt diese Garantie; ob im Einzelfall tatsächlich eine
  Ganzzahligkeitslücke zwischen LP und ILP auftritt, wird live geprüft
  und nicht nur behauptet.
- Schichtplan-Gantt-Ansicht, PDF-Export, Permalink, Feedback-Mechanismus.

Lauffähig mit: streamlit run app.py

Code-Struktur: Die eigentliche Logik (Modell, Solver, Kennzahlen, PDF-Export,
Visualisierung, Feedback) liegt in den Modulen shift_*.py neben dieser Datei,
analog zu den anderen Demos in diesem Workspace.
"""

import streamlit as st

from shift_constants import DEFAULT_BASE_DEMAND, DEFAULT_COST_PER_SHIFT, DEFAULT_PEAK_HEIGHT, DEFAULT_SHIFT_LENGTH, GAP_EXAMPLE, T
from shift_evaluation import active_shift_instances, fractional_shift_rows, overstaffing_hours, total_shifts
from shift_feedback import get_feedback_counts, log_feedback
from shift_model import demand_curve, shift_catalog
from shift_pdf_export import generate_shift_plan_pdf
from shift_presets import (
    apply_gap_example,
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sync_query_params,
)
from shift_solver import solve_all
from shift_visualization import coverage_figure, fractional_bars_figure, shift_gantt_figure


@st.cache_data(show_spinner=False)
def _compute(shift_length, n_peaks, peak_conc, seed, base_demand, peak_height, cost, wrap, cache_key):
    demand = demand_curve(n_peaks, peak_conc, seed, base_demand, peak_height)
    shifts = shift_catalog(shift_length, allow_wrap=wrap)
    results = solve_all(shifts, demand, cost)
    return demand, shifts, results


st.set_page_config(page_title="Schichtplanung – Sebastian Hanisch", layout="wide")

st.title("🗓️ Schichtplanung (Personalbedarfsdeckung)")
st.markdown(
    """
Interaktive Demo zur Schichtplanung: Ein stündlicher **Personalmindestbedarf** über
24 Stunden muss durch eine Auswahl an **Schichten** gedeckt werden - mit möglichst
wenigen/günstigen Schichten. Drei Verfahren im Vergleich: **Greedy-Heuristik**,
**LP-Relaxierung** und ein **exaktes ILP** (Google OR-Tools). Kernthema der Demo:
**totale Unimodularität** - wann garantiert die LP-Relaxierung bereits eine
ganzzahlige Lösung, und wann nicht mehr?
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_col1, preset_col2, preset_col3 = st.columns(3)
with preset_col1:
    st.button(
        "🏬 Einzelhandel (1 Spitze)", use_container_width=True,
        on_click=apply_preset, args=(8, 1, 0.5, 42, 2, 8, False),
        help="Ein Nachmittags-/Abend-Peak, Schichtlänge 8h, keine Wraparound-Schichten.",
    )
with preset_col2:
    st.button(
        "☎️ Callcenter (2 Spitzen)", use_container_width=True,
        on_click=apply_preset, args=(6, 2, 0.6, 7, 2, 6, False),
        help="Vormittags- und Abend-Peak, kürzere 6h-Schichten.",
    )
with preset_col3:
    st.button(
        "⚠️ Beispiel mit Ganzzahligkeitslücke", use_container_width=True,
        on_click=apply_gap_example,
        help="Wraparound aktiviert, Parameter so gewählt, dass LP-Relaxierung und ILP "
             "nachweislich auseinanderfallen - siehe Abschnitt weiter unten.",
    )

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    shift_length = st.slider("Schichtlänge (Stunden)", *bounds("shift_length_slider"), key="shift_length_slider")
    n_peaks = st.slider("Anzahl Nachfragespitzen", *bounds("n_peaks_slider"), key="n_peaks_slider")
    peak_conc = st.slider(
        "Konzentration der Spitzen", *bounds("peak_conc_slider"), step=0.05, key="peak_conc_slider",
        help="Hohe Werte = schmale, ausgeprägte Spitzen. Niedrige Werte = breiter, flacher Verlauf.",
    )
    base_demand = st.slider("Grundbedarf (Personen)", *bounds("base_demand_slider"), key="base_demand_slider")
    peak_height = st.slider("Spitzenhöhe (zusätzliche Personen)", *bounds("peak_height_slider"), key="peak_height_slider")
    seed_lo, seed_hi = bounds("seed_input")
    seed = st.number_input("Zufalls-Seed", min_value=seed_lo, max_value=seed_hi, step=1, key="seed_input")

    st.markdown("**Kosten**")
    cost_per_shift = st.slider("Kosten pro Schicht (€)", *bounds("cost_slider"), step=10.0, key="cost_slider")

    st.markdown("**Nebenbedingungen**")
    wrap = st.checkbox(
        "Schichten über Mitternacht hinweg erlauben (Wraparound)", key="wrap_checkbox",
        help="Ohne Wraparound deckt jede Schicht einen zusammenhängenden Block ohne Lücke ab - "
             "die Nebenbedingungsmatrix ist dann total unimodular. Mit Wraparound entfällt diese "
             "Garantie (siehe Abschnitt weiter unten).",
    )

    st.button(
        "🎲 Neuen Bedarf generieren", use_container_width=True, on_click=randomize_seed,
        help="Würfelt einen neuen Zufalls-Seed für die Nachfragekurve.",
    )

sync_query_params(shift_length, n_peaks, peak_conc, seed, base_demand, peak_height, cost_per_shift, wrap)

cache_key = (shift_length, n_peaks, peak_conc, int(seed), base_demand, peak_height, cost_per_shift, wrap)
demand, shifts, results = _compute(shift_length, n_peaks, peak_conc, int(seed), base_demand, peak_height, cost_per_shift, wrap, cache_key)
greedy, lp, ilp = results["greedy"], results["lp"], results["ilp"]

st.divider()
st.subheader("Vergleich: Greedy-Heuristik vs. exaktes ILP")
col1, col2 = st.columns(2)
with col1:
    st.metric("Greedy: Anzahl Schichten", f"{total_shifts(greedy.counts):.0f}", help=f"Kosten: {greedy.objective:,.0f} €")
    st.plotly_chart(coverage_figure(demand, greedy.coverage, "Greedy: Bedarf vs. Deckung"), use_container_width=True)
with col2:
    st.metric(
        "ILP: Anzahl Schichten", f"{total_shifts(ilp.counts):.0f}", help=f"Kosten: {ilp.objective:,.0f} €",
        delta=f"{total_shifts(ilp.counts) - total_shifts(greedy.counts):+.0f} ggü. Greedy", delta_color="inverse",
    )
    st.plotly_chart(coverage_figure(demand, ilp.coverage, "ILP: Bedarf vs. Deckung"), use_container_width=True)

st.caption(
    f"Greedy-Überdeckung: {overstaffing_hours(greedy.coverage, demand):.0f} Personenstunden · "
    f"ILP-Überdeckung: {overstaffing_hours(ilp.coverage, demand):.0f} Personenstunden. "
    "Der Greedy-Algorithmus liefert immer eine gültige, ganzzahlige Lösung - aber ohne "
    "Optimalitätsgarantie."
)

st.divider()
st.subheader("📐 Totale Unimodularität: Wann reicht die LP-Relaxierung?")
st.markdown(
    """
Formuliert man das Deckungsproblem als lineares Programm, ist die Nebenbedingungsmatrix
genau dann **total unimodular (TU)**, wenn jede Schicht einen **zusammenhängenden**
Zeitblock ohne Lücke abdeckt (*Intervallmatrix* / konsekutive-Einsen-Eigenschaft in
linearer Reihenfolge). In diesem Fall liefert die **LP-Relaxierung** bei ganzzahligem
Bedarf automatisch eine ganzzahlige Lösung - ein ILP-Solver ist dafür nicht zwingend
nötig. Erlaubt man **Schichten über Mitternacht hinweg**, ist diese Intervallstruktur
im linearen 24h-Raster durchbrochen, die TU-Garantie entfällt. Ob das im Einzelfall
tatsächlich zu einer **Ganzzahligkeitslücke** führt, hängt von der konkreten Bedarfskurve
und Schichtlänge ab - unten wird das für die aktuelle Konfiguration live geprüft.
"""
)

gap = ilp.objective - lp.objective if (lp.status != "infeasible" and ilp.status != "infeasible") else 0.0
tu_col1, tu_col2, tu_col3 = st.columns(3)
tu_col1.metric("LP-Relaxierung (Kosten)", f"{lp.objective:,.1f} €")
tu_col2.metric("ILP (Kosten)", f"{ilp.objective:,.0f} €")
tu_col3.metric("Ganzzahligkeitslücke", f"{gap:,.1f} €", delta=None if gap < 0.01 else "LP fraktional!", delta_color="inverse")

if not wrap:
    st.success(
        "Ohne Wraparound ist die Matrix total unimodular: LP-Relaxierung und ILP stimmen "
        f"exakt überein ({lp.objective:,.0f} € = {ilp.objective:,.0f} €). Die LP-Lösung ist "
        "bereits ganzzahlig - kein Branch & Bound nötig."
    )
elif lp.is_integral:
    st.info(
        "Wraparound ist aktiv, TU ist nicht mehr garantiert - für diese konkrete Bedarfskurve "
        "und Schichtlänge ist die LP-Lösung aber trotzdem ganzzahlig ausgefallen. Das ist kein "
        "Widerspruch: TU ist eine hinreichende, keine notwendige Bedingung. Probieren Sie das "
        "Preset „Beispiel mit Ganzzahligkeitslücke“ oder andere Schichtlängen/Seeds."
    )
else:
    st.warning(
        f"Ganzzahligkeitslücke gefunden: Die LP-Relaxierung ({lp.objective:,.1f} €) unterschätzt "
        f"das tatsächliche Optimum ({ilp.objective:,.0f} €) - {gap:,.1f} € Differenz. Die "
        "LP-Lösung enthält fraktionale Werte (z. B. „0,5 Personen“), die real nicht umsetzbar sind."
    )
    frac_rows = fractional_shift_rows(shifts, lp.counts)
    if frac_rows:
        st.plotly_chart(fractional_bars_figure(frac_rows, "LP-Relaxierung: fraktionale Schicht-Anzahlen"), use_container_width=True)

with st.expander("Kleines Lehrbuchbeispiel (T=3, zyklisch) - dieselbe Struktur, ganz klein"):
    st.markdown(
        """
Drei Zeiteinheiten im Kreis, Bedarf 1 in jeder, Schichten decken je zwei
aufeinanderfolgende (zyklische) Einheiten ab, Kosten 1 je Schicht:

- **LP-Relaxierung**: x = (0.5, 0.5, 0.5) → Kosten 1.5
- **ILP**: x = (1, 1, 0) → Kosten 2.0

Klassisches Beispiel für einen **Odd-Cycle**: Die zyklische Struktur erzwingt eine
fraktionale LP-Lösung, weil sich der Bedarf nicht mit halbzahligen Schichten in der
Realität decken lässt.
"""
    )

st.divider()
st.subheader("📋 Schichtplan (ILP-Lösung)")
rows = active_shift_instances(shifts, ilp.counts)
if rows:
    st.plotly_chart(shift_gantt_figure(rows, "Besetzte Schichten über den Tag"), use_container_width=True)

pdf_bytes = generate_shift_plan_pdf("Schichtplanung", shifts, ilp, demand, cost_per_shift)
st.download_button(
    "📄 Schichtplan als PDF herunterladen", data=pdf_bytes,
    file_name="schichtplan.pdf", mime="application/pdf",
)

st.divider()
st.caption("War diese Demo hilfreich?")
fb_col1, fb_col2, _ = st.columns([1, 1, 4])
with fb_col1:
    if st.button("👍 Ja"):
        log_feedback("up")
        st.toast("Danke für Ihr Feedback!")
with fb_col2:
    if st.button("👎 Nein"):
        log_feedback("down")
        st.toast("Danke für Ihr Feedback!")

st.markdown("---")
st.caption(
    "Diese Demo ist bewusst vereinfacht (fester 24h-Horizont, ein einheitlicher Schichttyp), "
    "um die Grundprinzipien - insbesondere die Rolle der totalen Unimodularität - greifbar zu "
    "machen. Reale Dienstplanungen enthalten meist mehrere Schichttypen, Qualifikationen, "
    "Ruhezeiten und Fairness-Regeln über mehrere Tage - die Methodik dahinter ist dieselbe."
)
st.caption("Entwickelt von [Sebastian Hanisch](https://sebastianhanisch.net) - Operations Research und Machine Learning.")
