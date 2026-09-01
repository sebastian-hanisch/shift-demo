"""Plotly-Visualisierungen für die Schichtplanung-Demo."""

import plotly.graph_objects as go

from shift_constants import T

_LENGTH_PALETTE = ["#3E8E86", "#D68A2E", "#6C5CE7", "#E4572E", "#2E86AB", "#8AA24A", "#B23A48", "#4C6663"]


def _length_color_map(lengths):
    uniq = sorted(set(lengths))
    return {length: _LENGTH_PALETTE[i % len(_LENGTH_PALETTE)] for i, length in enumerate(uniq)}


def coverage_figure(demand, coverage, title):
    hours = list(range(T))
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hours, y=demand, name="Bedarf", marker_color="#94a3b8", opacity=0.55,
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=coverage, name="Deckung", mode="lines+markers",
        line=dict(color="#14233B", width=3, shape="hv"),
    ))
    tick_hours = list(range(0, T + 1, 2))
    fig.update_layout(
        title=title, xaxis_title="Uhrzeit", yaxis_title="Personen",
        height=320, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickmode="array", tickvals=tick_hours, ticktext=[f"{h:02d}:00" for h in tick_hours]),
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def shift_gantt_figure(rows, title):
    """Gantt-Ansicht der besetzten Schichten, nach Schichtlänge eingefärbt -
    macht bei mehreren gleichzeitig gewählten Schichttypen sichtbar, welche
    Länge wo zum Einsatz kommt. Das Label enthält die Länge, damit zwei
    unterschiedlich lange Schichten mit demselben Start nicht in dieselbe
    Gantt-Zeile fallen."""
    color_map = _length_color_map(r["length"] for r in rows)
    fig = go.Figure()
    y_labels = []
    for i, r in enumerate(rows):
        color = color_map[r["length"]]
        y = f"{r['start']:02d}:00 · {r['length']}h · {r['count']}×"
        y_labels.append(y)
        if r["wraps"]:
            end_of_day = T - r["start"]
            fig.add_trace(go.Bar(
                x=[end_of_day], y=[y], base=[r["start"]], orientation="h",
                marker_color=color, showlegend=False,
                hovertemplate=f"{r['start']:02d}:00–24:00, {r['count']}× besetzt<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=[r["length"] - end_of_day], y=[y], base=[0], orientation="h",
                marker_color=color, showlegend=False,
                hovertemplate=f"00:00–{(r['start']+r['length'])%T:02d}:00 (Fortsetzung), {r['count']}× besetzt<extra></extra>",
            ))
        else:
            fig.add_trace(go.Bar(
                x=[r["length"]], y=[y], base=[r["start"]], orientation="h",
                marker_color=color, showlegend=False,
                hovertemplate=f"{r['start']:02d}:00–{r['start']+r['length']:02d}:00, {r['count']}× besetzt<extra></extra>",
            ))
    for length, color in color_map.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", marker=dict(size=10, color=color, symbol="square"),
            name=f"{length}h-Schicht",
        ))
    fig.update_layout(
        title=title, barmode="stack", height=max(160, 34 * len(rows) + 60),
        xaxis=dict(title="Uhrzeit", range=[0, T], dtick=2),
        yaxis=dict(title=None, categoryorder="array", categoryarray=y_labels[::-1]),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def fractional_bars_figure(rows, title):
    fig = go.Figure()
    labels = [f"{r['start']:02d}:00 (+{r['length']}h)" for r in rows]
    values = [r["count"] for r in rows]
    colors = ["#dc2626" if abs(v - round(v)) > 1e-6 else "#16a34a" for v in values]
    fig.add_trace(go.Bar(x=labels, y=values, marker_color=colors))
    for v in sorted(set(round(v) for v in values)):
        fig.add_hline(y=v, line_dash="dot", line_color="#94a3b8", opacity=0.6)
    fig.update_layout(
        title=title, yaxis_title="x_j (Anzahl Personen, LP-Relaxierung)",
        height=320, margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig
