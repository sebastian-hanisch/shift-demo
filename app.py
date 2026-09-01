"""
Schichtplanung (Personalbedarfsdeckung) – interaktive Demo
Sebastian Hanisch - Operations Research und Machine Learning

Features:
- Stündlicher Personalbedarf über 24h, synthetisch erzeugt (Seed, Anzahl
  Nachfragespitzen, Konzentration).
- Mehrere Schichtlängen gleichzeitig wählbar (z. B. Teilzeit 4h + Vollzeit 8h);
  Kosten skalieren mit der Schichtlänge, sodass ein echter Mix-Trade-off
  entsteht.
- Optionale Fixkosten pro genutztem Schichttyp (z. B. Einrichtung/Schulung
  für ein neues Schichtmuster) - macht die Typwahl zu einer echten
  kombinatorischen Entscheidung (Fixed-Charge-Struktur) und vergrößert
  typischerweise sowohl die Greedy-Suboptimalität als auch die
  LP/ILP-Ganzzahligkeitslücke, auch ohne Wraparound.
- Drei Lösungsverfahren im Vergleich: Greedy-Heuristik (immer ganzzahlig),
  LP-Relaxierung (kontinuierlich) und exaktes ILP (Google OR-Tools).
- Kernthema: totale Unimodularität. Solange Schichten zusammenhängende
  Zeitblöcke ohne Lücke abdecken (keine Nachtschicht über Mitternacht
  hinweg) und keine Fixkosten pro Schichttyp aktiv sind, ist die
  Nebenbedingungsmatrix eine Intervallmatrix und damit total unimodular -
  die LP-Relaxierung liefert automatisch eine ganzzahlige Lösung, ein
  ILP-Solver ist dafür streng genommen nicht nötig. Wraparound und
  Fixkosten brechen diese Garantie unabhängig voneinander; ob im
  Einzelfall tatsächlich eine Ganzzahligkeitslücke auftritt, wird live
  geprüft und nicht nur behauptet.
- Schichtplan-Gantt-Ansicht, PDF-Export, Permalink.

Selbe Struktur wie bei den anderen Demos in diesem Workspace: Ergebnis
zuerst ("Ihr optimierter Schichtplan"), vollständiger Methodenvergleich
sekundär im Expander, dazu "Wie funktioniert diese Demo?" und "Mathematische
Formulierung" als eigene Expander.

Lauffähig mit: streamlit run app.py

Code-Struktur: Die eigentliche Logik (Modell, Solver, Kennzahlen, PDF-Export,
Visualisierung) liegt in den Modulen shift_*.py neben dieser Datei,
analog zu den anderen Demos in diesem Workspace.
"""

import pandas as pd
import streamlit as st

from shift_constants import AVAILABLE_SHIFT_LENGTHS
from shift_evaluation import (
    active_shift_instances,
    fractional_shift_rows,
    overstaffing_hours,
    total_shifts,
    used_shift_types,
)
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
def _compute(shift_lengths, n_peaks, peak_conc, seed, base_demand, peak_height, cost_per_hour, fixed_cost_per_type, wrap, cache_key):
    demand = demand_curve(n_peaks, peak_conc, seed, base_demand, peak_height)
    shifts = shift_catalog(shift_lengths, allow_wrap=wrap)
    results = solve_all(shifts, demand, cost_per_hour, fixed_cost_per_type)
    return demand, shifts, results


def _comparison_row(label, shifts, demand, result):
    types = used_shift_types(shifts, result.counts)
    types_str = ", ".join(f"{l}h" for l in types) if types else "-"
    count_fmt = f"{total_shifts(result.counts):.0f}" if result.is_integral else f"{total_shifts(result.counts):.1f}"
    cost_fmt = f"{result.objective:,.0f}" if result.is_integral else f"{result.objective:,.1f}"
    return {
        "Methode": label,
        "Anzahl Schichten": count_fmt,
        "Kosten (€)": cost_fmt,
        "Überdeckung (Personenstd.)": f"{overstaffing_hours(result.coverage, demand):.0f}",
        "Genutzte Schichttypen": f"{len(types)} ({types_str})",
        "Ganzzahlig?": "Ja" if result.is_integral else "Nein",
    }


st.set_page_config(page_title="Schichtplanung – Sebastian Hanisch", layout="wide")

st.title("🗓️ Schichtplanung (Personalbedarfsdeckung)")
st.markdown(
    """
Interaktive Demo zur Schichtplanung: Ein stündlicher **Personalmindestbedarf** über
24 Stunden muss durch eine Auswahl an **Schichten** gedeckt werden - mit möglichst
wenigen/günstigen Schichten. Drei selbst implementierte bzw. über Google OR-Tools gelöste
Verfahren - eine **Greedy-Heuristik**, eine **LP-Relaxierung** und ein **exaktes ILP** - werden
direkt verglichen. Kernthema der Demo ist **totale Unimodularität**: wann garantiert die
LP-Relaxierung bereits eine ganzzahlige Lösung, und wann nicht mehr? Hintergrund dazu im
Expander "Wie funktioniert diese Demo?" unten sowie formal hergeleitet im Expander
"📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_col1, preset_col2, preset_col3 = st.columns(3)
with preset_col1:
    st.button(
        "🏬 Einzelhandel (1 Spitze)", use_container_width=True,
        on_click=apply_preset, args=([4, 8], 1, 0.5, 42, 2, 8, False),
        help="Ein Nachmittags-/Abend-Peak, Mix aus 4h-Teilzeit- und 8h-Vollzeitschichten, "
             "keine Wraparound-Schichten.",
    )
with preset_col2:
    st.button(
        "☎️ Callcenter (2 Spitzen)", use_container_width=True,
        on_click=apply_preset, args=([4, 6], 2, 0.6, 7, 2, 6, False),
        help="Vormittags- und Abend-Peak, Mix aus kürzeren 4h- und 6h-Schichten.",
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
    shift_lengths = st.multiselect(
        "Schichtlängen (Stunden)", options=AVAILABLE_SHIFT_LENGTHS, key="shift_lengths_multiselect",
        help="Mehrere Längen gleichzeitig wählbar - der Solver kombiniert sie frei, um den Bedarf "
             "möglichst günstig zu decken. Totale Unimodularität bleibt dabei erhalten (siehe unten).",
    )
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
    cost_per_hour = st.slider("Kosten pro Stunde (€)", *bounds("cost_slider"), step=5.0, key="cost_slider")
    fixed_cost_per_type = st.slider(
        "Fixkosten pro Schichttyp (€)", *bounds("fixed_cost_slider"), step=50.0, key="fixed_cost_slider",
        help="Einmalige Kosten, sobald eine Schichtlänge überhaupt genutzt wird (z. B. Einrichtung/"
             "Schulung für ein neues Schichtmuster) - zusätzlich zu den linearen Stundenkosten. "
             "Macht die Wahl zwischen Schichttypen zu einer echten kombinatorischen Entscheidung "
             "und bricht auch die TU-Garantie der reinen Deckungsmatrix (siehe Abschnitt weiter unten).",
    )

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

if not shift_lengths:
    st.warning("Bitte mindestens eine Schichtlänge in der Seitenleiste wählen.")
    st.stop()

sync_query_params(shift_lengths, n_peaks, peak_conc, seed, base_demand, peak_height, cost_per_hour, fixed_cost_per_type, wrap)

shift_lengths_key = tuple(sorted(shift_lengths))
cache_key = (shift_lengths_key, n_peaks, peak_conc, int(seed), base_demand, peak_height, cost_per_hour, fixed_cost_per_type, wrap)
demand, shifts, results = _compute(
    shift_lengths_key, n_peaks, peak_conc, int(seed), base_demand, peak_height, cost_per_hour, fixed_cost_per_type, wrap, cache_key,
)
greedy, lp, ilp = results["greedy"], results["lp"], results["ilp"]

st.markdown("## 🎯 Ihr optimierter Schichtplan")

cost_savings_pct = 0.0
if greedy.objective > 0:
    cost_savings_pct = (greedy.objective - ilp.objective) / greedy.objective * 100

m1, m2 = st.columns(2)
m1.metric(
    "Anzahl Schichten (ILP)", f"{total_shifts(ilp.counts):.0f}",
    delta=f"{total_shifts(ilp.counts) - total_shifts(greedy.counts):+.0f} ggü. Greedy", delta_color="inverse",
)
m2.metric(
    "Kosten (ILP)", f"{ilp.objective:,.0f} €",
    delta=f"{-cost_savings_pct:+.1f}% ggü. Greedy", delta_color="inverse",
)

if cost_savings_pct > 0.5:
    st.success(
        f"💡 Das exakte ILP ist **{cost_savings_pct:.1f}%** günstiger als die Greedy-Heuristik "
        f"({ilp.objective:,.0f} € statt {greedy.objective:,.0f} €) - nachweislich optimal für "
        "dieses Szenario, siehe Methodenvergleich unten."
    )

rows = active_shift_instances(shifts, ilp.counts)
if rows:
    st.plotly_chart(shift_gantt_figure(rows, "Besetzte Schichten über den Tag (ILP-Lösung)"), use_container_width=True)

if fixed_cost_per_type > 0:
    greedy_types = used_shift_types(shifts, greedy.counts)
    ilp_types = used_shift_types(shifts, ilp.counts)
    st.caption(
        f"Genutzte Schichttypen - Greedy: {len(greedy_types)} ({', '.join(f'{l}h' for l in greedy_types)}) · "
        f"ILP: {len(ilp_types)} ({', '.join(f'{l}h' for l in ilp_types)}) · "
        f"je {fixed_cost_per_type:.0f} € Fixkosten pro aktiviertem Typ."
    )

pdf_bytes = generate_shift_plan_pdf("Schichtplanung", shifts, ilp, demand, cost_per_hour, fixed_cost_per_type)
st.download_button(
    "📄 Schichtplan als PDF herunterladen", data=pdf_bytes,
    file_name="schichtplan.pdf", mime="application/pdf",
)

st.caption(
    "Ermittelt mit dem exakten ILP (Google OR-Tools) - nachweislich optimal für dieses Szenario. "
    "Details im Methodenvergleich unten."
)

st.markdown("---")
st.subheader("📐 Totale Unimodularität: Wann reicht die LP-Relaxierung?")
st.markdown(
    """
Kernthema dieser Demo: Wann liefert die **LP-Relaxierung** automatisch eine ganzzahlige Lösung,
sodass ein ILP-Solver eigentlich nicht nötig wäre - und wann nicht mehr? Die Bedingung dafür
(**totale Unimodularität**, TU) und warum Wraparound-Schichten sowie Fixkosten pro Schichttyp sie
unabhängig voneinander brechen können, ist im Expander "📐 Mathematische Formulierung" unten
formal hergeleitet. Hier wird das Ergebnis für Ihre aktuelle Konfiguration live geprüft - nicht
nur behauptet.
"""
)

gap = ilp.objective - lp.objective if (lp.status != "infeasible" and ilp.status != "infeasible") else 0.0
tu_col1, tu_col2, tu_col3 = st.columns(3)
tu_col1.metric("LP-Relaxierung (Kosten)", f"{lp.objective:,.1f} €")
tu_col2.metric("ILP (Kosten)", f"{ilp.objective:,.0f} €")
tu_col3.metric("Ganzzahligkeitslücke", f"{gap:,.1f} €", delta=None if gap < 0.01 else "LP fraktional!", delta_color="inverse")

tu_holds = not wrap and fixed_cost_per_type == 0
if tu_holds:
    st.success(
        "Ohne Wraparound und ohne Fixkosten pro Schichttyp ist die Matrix total unimodular: "
        f"LP-Relaxierung und ILP stimmen exakt überein ({lp.objective:,.0f} € = {ilp.objective:,.0f} €). "
        "Die LP-Lösung ist bereits ganzzahlig - kein Branch & Bound nötig."
    )
elif lp.is_integral:
    reasons = []
    if wrap:
        reasons.append("Wraparound")
    if fixed_cost_per_type > 0:
        reasons.append("Fixkosten pro Schichttyp")
    reason_text = " und ".join(reasons)
    st.info(
        f"{reason_text} aktiv - TU ist nicht mehr garantiert, für diese konkrete Konfiguration ist "
        "die LP-Lösung aber trotzdem ganzzahlig ausgefallen. Das ist kein Widerspruch: TU (bzw. eine "
        "ganzzahlige LP-Lösung) ist eine hinreichende, keine notwendige Eigenschaft. Probieren Sie "
        "andere Schichtlängen/Seeds oder das Preset „Beispiel mit Ganzzahligkeitslücke“."
    )
else:
    reasons = []
    if wrap:
        reasons.append("Wraparound")
    if fixed_cost_per_type > 0:
        reasons.append("Fixkosten pro Schichttyp")
    reason_text = " und ".join(reasons)
    st.warning(
        f"Ganzzahligkeitslücke gefunden ({reason_text} aktiv): Die LP-Relaxierung ({lp.objective:,.1f} €) "
        f"unterschätzt das tatsächliche Optimum ({ilp.objective:,.0f} €) - {gap:,.1f} € Differenz. Die "
        "LP-Lösung enthält fraktionale Werte (z. B. „0,5 Personen“ oder eine „halb aktivierte“ "
        "Schichtlänge), die real nicht umsetzbar sind."
    )
    frac_rows = fractional_shift_rows(shifts, lp.counts)
    if frac_rows:
        st.plotly_chart(fractional_bars_figure(frac_rows, "LP-Relaxierung: fraktionale Schicht-Anzahlen"), use_container_width=True)

st.markdown("---")

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich", expanded=False):
    tabs = st.tabs(["🏃 Greedy-Heuristik", "🧮 LP-Relaxierung", "✅ Exaktes ILP", "📊 Vergleich"])

    with tabs[0]:
        st.caption(
            "Wiederholt die Schicht mit dem besten Verhältnis aus abgedecktem Bedarfsüberhang zu "
            "Grenzkosten wählen, bis überall gedeckt ist - liefert immer eine gültige, ganzzahlige "
            "Lösung, aber ohne Optimalitätsgarantie."
        )
        g1, g2 = st.columns(2)
        g1.metric("Anzahl Schichten", f"{total_shifts(greedy.counts):.0f}")
        g2.metric("Kosten", f"{greedy.objective:,.0f} €")
        st.caption(f"Überdeckung: {overstaffing_hours(greedy.coverage, demand):.0f} Personenstunden.")
        st.plotly_chart(coverage_figure(demand, greedy.coverage, "Greedy: Bedarf vs. Deckung"), use_container_width=True)

    with tabs[1]:
        st.caption(
            "Dieselbe Nebenbedingungsmatrix wie das ILP, aber mit kontinuierlichen statt "
            "ganzzahligen Schicht-Anzahlen - eine Lockerung, die nie teurer als das ILP sein kann "
            "und damit eine untere Schranke für die tatsächlichen Kosten liefert."
        )
        l1, l2 = st.columns(2)
        l1.metric("Kosten", f"{lp.objective:,.1f} €")
        l2.metric("Ganzzahlig?", "Ja" if lp.is_integral else "Nein")
        st.plotly_chart(coverage_figure(demand, lp.coverage, "LP-Relaxierung: Bedarf vs. Deckung"), use_container_width=True)

    with tabs[2]:
        st.caption(
            "Exakte Lösung über Google OR-Tools (CBC, Branch & Bound) - nachweislich optimal, aber "
            "im Worst Case mit exponentiellem Aufwand."
        )
        i1, i2 = st.columns(2)
        i1.metric("Anzahl Schichten", f"{total_shifts(ilp.counts):.0f}")
        i2.metric("Kosten", f"{ilp.objective:,.0f} €")
        st.caption(f"Überdeckung: {overstaffing_hours(ilp.coverage, demand):.0f} Personenstunden.")
        st.plotly_chart(coverage_figure(demand, ilp.coverage, "ILP: Bedarf vs. Deckung"), use_container_width=True)

    with tabs[3]:
        st.markdown("### Methodenvergleich")
        comp_rows = [
            _comparison_row("Greedy-Heuristik", shifts, demand, greedy),
            _comparison_row("LP-Relaxierung", shifts, demand, lp),
            _comparison_row("Exaktes ILP", shifts, demand, ilp),
        ]
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Alle drei Verfahren lösen dieselbe Nebenbedingungsmatrix - fair vergleichbar, auch wenn "
            "die Lösungsstrategien sehr unterschiedlich sind."
        )
        vis_cols = st.columns(3)
        for col, (label, result) in zip(vis_cols, [("Greedy", greedy), ("LP-Relaxierung", lp), ("ILP", ilp)]):
            with col:
                st.markdown(f"**{label}**")
                st.plotly_chart(coverage_figure(demand, result.coverage, label), use_container_width=True)

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Die Problemstellung:** Ein stündlicher Personalmindestbedarf über 24 Stunden muss durch eine
Auswahl an Schichten gedeckt werden, mit möglichst geringen Kosten - ein klassisches
**Mengenüberdeckungsproblem** (Set Cover), hier mit der Zusatzstruktur, dass jede Schicht einen
zusammenhängenden Zeitblock abdeckt (bzw. bei Wraparound einen über Mitternacht umlaufenden). Set
Cover ist im Allgemeinen NP-schwer; die Intervallstruktur macht den Fall ohne Wraparound und ohne
Fixkosten aber besonders gutartig (siehe Abschnitt zur totalen Unimodularität oben sowie den
Expander "📐 Mathematische Formulierung").

**Bedarfskurve:** Wird synthetisch erzeugt: ein Grundbedarf plus eine wählbare Anzahl
Nachfragespitzen (zufällige Uhrzeiten, gesteuert über den Zufalls-Seed), deren Breite über die
"Konzentration" eingestellt wird - hohe Konzentration ergibt schmale, ausgeprägte Spitzen (z. B.
ein scharfer Feierabend-Peak im Einzelhandel), niedrige Konzentration einen breiten, flachen
Verlauf.

**Greedy-Heuristik (Baseline):** Wählt wiederholt die Schicht mit dem besten Verhältnis aus
abgedecktem Bedarfsüberhang zu Grenzkosten ("bester Gegenwert je Euro"), bis der gesamte Bedarf
gedeckt ist. Liefert immer eine gültige, ganzzahlige Lösung in linearer Zeit - aber ohne
Optimalitätsgarantie (bekannter logarithmischer Approximationsfaktor für Set-Cover-artige
Probleme). Sind Fixkosten pro Schichttyp aktiv, rechnet Greedy sie der jeweils ersten Instanz
einer noch nicht genutzten Schichtlänge zu - das bestraft das unnötige Eröffnen eines neuen
Schichttyps.

**LP-Relaxierung:** Dieselbe Nebenbedingungsmatrix wie das ILP, aber mit kontinuierlichen statt
ganzzahligen Schicht-Anzahlen. Da sie eine Lockerung des ILP ist, kann ihr Optimum nie teurer
sein - sie liefert also stets eine untere Schranke für die tatsächlichen Kosten. Ob sie zufällig
schon ganzzahlig ausfällt, hängt von der TU-Eigenschaft der aktuellen Konfiguration ab (siehe
oben).

**Exaktes ILP:** Löst dieselbe Formulierung mit ganzzahligen (bzw. bei Fixkosten zusätzlich
binären) Variablen über Google OR-Tools (CBC-Solver, Branch & Bound) - garantiert optimal, im
Worst Case aber mit exponentiellem Aufwand. Für die Größenordnungen dieser Demo (ein Tag, wenige
Schichttypen) ist das in der Praxis kein Problem.

**Fixkosten pro Schichttyp:** Optionale einmalige Kosten, sobald eine Schichtlänge überhaupt
genutzt wird (z. B. Einrichtung oder Schulung für ein neues Schichtmuster). Technisch über eine
Binärvariable je Schichtlänge umgesetzt, die per Big-M-Nebenbedingung an die zugehörigen
Schicht-Anzahlen gekoppelt ist - macht aus der reinen Kostenabwägung eine echte kombinatorische
Entscheidung (lohnt sich ein zusätzlicher Schichttyp?) und lässt Greedy spürbar seltener das
exakte Optimum treffen.

**Totale Unimodularität:** Der eigentliche Kern der Demo. Wenn jede Schicht einen
zusammenhängenden Zeitblock abdeckt (kein Wraparound) und keine Fixkosten aktiv sind, ist die
Nebenbedingungsmatrix nachweislich total unimodular - die LP-Relaxierung liefert dann immer
automatisch eine ganzzahlige Lösung, ein ILP-Solver ist streng genommen nicht nötig. Wraparound
und Fixkosten pro Schichttyp brechen diese Garantie unabhängig voneinander (siehe Abschnitt oben
und die formale Herleitung im Expander "📐 Mathematische Formulierung") - ob im Einzelfall
wirklich eine Lücke entsteht, wird für Ihre aktuelle Konfiguration live geprüft, statt nur
behauptet.

**In echten Projekten** kämen meist weitere Nebenbedingungen dazu (Qualifikationen, Ruhezeiten
zwischen Schichten, Fairness-Regeln über mehrere Tage, ein mehrtägiger statt eines festen
24h-Horizonts) - das Grundprinzip aus Deckungsmodell und den drei Lösungsverfahren bleibt aber
dasselbe.
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
Formal ist die Personalbedarfsdeckung ein **(gewichtetes) Mengenüberdeckungsproblem** (Set
Cover) mit einer zusätzlichen Intervallstruktur. Gegeben:

- ein Zeithorizont $T = \{0, \ldots, 23\}$ (Stunden eines Tages)
- ein stündlicher Mindestbedarf $d_t \geq 0$ für jede Stunde $t \in T$ (`demand` in
  `shift_model.py`)
- ein Schichtkatalog $J$: jede Schicht $j \in J$ hat eine Startzeit, eine Länge und deckt eine
  Menge $C_j \subseteq T$ von Stunden ab (`shift_catalog()` in `shift_model.py`) - ohne
  Wraparound ist $C_j$ stets ein **zusammenhängendes Intervall**, mit Wraparound kann es über
  Mitternacht "umlaufen"
- Stundenkosten $c_j = \text{cost\_per\_hour} \cdot \text{length}_j$ je Instanz von Schicht $j$
- optional Fixkosten $f \geq 0$ je genutzter Schichtlänge $L$ (`fixed_cost_per_type`)

Gesucht sind Anzahlen $x_j \geq 0$ (wie oft Schicht $j$ eingesetzt wird) und - nur bei aktiven
Fixkosten - Aktivierungsvariablen $y_L \in \{0,1\}$ ("Schichtlänge $L$ wird überhaupt genutzt"),
die den Bedarf zu minimalen Kosten decken:
"""
    )
    st.latex(r"\min \; \sum_{j \in J} c_j\, x_j \;+\; \sum_{L} f \cdot y_L")
    st.latex(r"\text{u. d. N.} \quad \sum_{j:\, t \in C_j} x_j \;\geq\; d_t \quad \forall t \in T")
    st.latex(r"x_j \;\leq\; M_j \cdot y_{L(j)} \quad \forall j \in J \qquad (\text{nur bei } f > 0)")
    st.latex(r"x_j \geq 0 \;(\text{ganzzahlig bei Greedy/ILP}), \qquad y_L \in \{0,1\}\;(\text{bzw. } [0,1] \text{ bei LP})")
    st.markdown(
        r"""
$M_j$ ist dabei die Bedarfsspitze, die Schicht $j$ überhaupt abdeckt ($M_j = \max_{t \in C_j}
d_t$) - eine beweisbar sichere und recht enge obere Schranke, denn mehr Instanzen einer Schicht
als die Spitze, die sie abdeckt, sind nie nötig (siehe `solve_lp_or_ilp()` in `shift_solver.py`).

**Totale Unimodularität (TU).** Eine Matrix ist TU, wenn jede quadratische Teilmatrix
Determinante $0$, $+1$ oder $-1$ hat. Für reine Deckungsprobleme reicht dafür die
**Intervalleigenschaft**: Besteht jede Spalte (= Schicht) der Nebenbedingungsmatrix aus
**aufeinanderfolgenden Einsen** (d. h. ist $C_j$ ein zusammenhängendes Intervall), ist die Matrix
eine Intervallmatrix und damit total unimodular - ein Standardresultat der ganzzahligen
Optimierung (siehe z. B. Nemhauser & Wolsey, *Integer and Combinatorial Optimization*, 1988,
Kap. I.2 zu Intervallmatrizen). Für TU-Matrizen sind bei ganzzahliger rechter Seite ($d_t \in
\mathbb{Z}$) **alle Ecken des LP-Polyeders bereits ganzzahlig** - die LP-Relaxierung liefert also
automatisch eine ganzzahlige Lösung, Branch & Bound ist streng genommen überflüssig.

**Warum Wraparound die Garantie bricht:** Erlaubt man Schichten über Mitternacht hinweg, ist
$C_j$ im linearen 24-Stunden-Raster kein zusammenhängendes Intervall mehr (es "umläuft" den Rand
$t=23 \to t=0$) - die Intervalleigenschaft und damit die TU-Garantie entfällt. Ob das im
Einzelfall tatsächlich zu einer fraktionalen LP-Lösung führt, hängt von der konkreten
Bedarfskurve ab (siehe Textbeispiel unten) und wird in der Demo live geprüft.

**Warum Fixkosten pro Schichttyp die Garantie brechen:** Die Kopplung $x_j \leq M_j \cdot
y_{L(j)}$ zwischen einer kontinuierlichen und einer binären Variable ist eine klassische
**Big-M-/Fixed-Charge-Struktur** - solche gemischt-ganzzahligen Kopplungen sind im Allgemeinen
nicht total unimodular, unabhängig vom Wraparound (siehe z. B. Nemhauser & Wolsey 1988, Kap. zu
Fixed-Charge-Problemen). Ein zusätzlicher Effekt kommt hinzu: Big-M-Formulierungen haben
typischerweise eine "lockere" LP-Relaxierung, weil $y_L$ kontinuierlich fast beliebig klein
gewählt werden kann, solange $x_j \leq M_j \cdot y_L$ noch erfüllt ist - die Fixkosten werden in
der Relaxierung dadurch künstlich klein gerechnet. Beides zusammen führt dazu, dass bei aktiven
Fixkosten in der Praxis fast immer eine Ganzzahligkeitslücke auftritt, auch ganz ohne Wraparound.

**Kleines Lehrbuchbeispiel (Odd Cycle):** Drei Zeiteinheiten im Kreis, Bedarf 1 in jeder,
Schichten decken je zwei aufeinanderfolgende (zyklische) Einheiten ab, Kosten 1 je Schicht -
dieselbe Struktur wie beim Wraparound-Fall oben, nur auf drei Einheiten verkleinert:
"""
    )
    st.latex(r"\text{LP-Relaxierung: } x = (0.5,\, 0.5,\, 0.5) \;\to\; \text{Kosten } 1.5")
    st.latex(r"\text{ILP: } x = (1,\, 1,\, 0) \;\to\; \text{Kosten } 2.0")
    st.markdown(
        r"""
Die zyklische Struktur (kein Anfang, kein Ende - wie bei Wraparound-Schichten) erzwingt eine
fraktionale LP-Lösung, weil sich der Bedarf nicht mit halbzahligen Schichten in der Realität
decken lässt.

**Bezug zum Code:** `shift_catalog()` in `shift_model.py` baut $C_j$ für jede Schicht auf und
markiert Wraparound-Schichten (`wraps`). `solve_lp_or_ilp()` in `shift_solver.py` setzt
Zielfunktion und Nebenbedingungen von oben 1:1 um (inklusive der optionalen Big-M-Kopplung),
`solve_greedy()` löst dieselbe Struktur approximativ über eine Bang-per-Buck-Regel. Ob die
LP-Lösung für die aktuelle Konfiguration ganzzahlig ist, wird nicht angenommen, sondern über
`SolveResult.is_integral` nach jedem Solver-Aufruf tatsächlich geprüft.
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
