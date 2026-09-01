"""
Erzeugt einen einsatzfähigen Schichtplan als downloadbares PDF (in-memory) -
Zusammenfassung + Liste der besetzten Schichten je Stunde.
"""

import time

from shift_evaluation import active_shift_instances, overstaffing_hours, total_shifts, used_shift_types
from shift_model import shift_label


def generate_shift_plan_pdf(label, shifts, result, demand, cost_per_hour, fixed_cost_per_type=0.0):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    rows = active_shift_instances(shifts, result.counts)
    n_shifts = total_shifts(result.counts) if result.is_integral else round(total_shifts(result.counts))
    overstaff = overstaffing_hours(result.coverage, demand)
    active_types = used_shift_types(shifts, result.counts)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Schichtplan - {label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')} Uhr", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Zusammenfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Verfahren: {result.method}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Anzahl Schichten: {n_shifts:.0f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Kosten: {result.objective:.0f} EUR (bei {cost_per_hour:.0f} EUR je Stunde)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if fixed_cost_per_type > 0:
        types_str = ", ".join(f"{l}h" for l in active_types)
        pdf.cell(
            0, 6,
            f"Davon Fixkosten: {fixed_cost_per_type * len(active_types):.0f} EUR fuer {len(active_types)} "
            f"genutzte Schichttypen ({types_str}), je {fixed_cost_per_type:.0f} EUR",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
    pdf.cell(0, 6, f"Ueberdeckung: {overstaff:.0f} Personenstunden", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if not result.is_integral:
        pdf.cell(0, 6, "Hinweis: LP-Relaxierung, Werte teils fraktional (siehe Detailtabelle unten)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Besetzte Schichten", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    headers = ["Schicht", "Zeitraum", "Anzahl Personen", "Kosten/Schicht (EUR)"]
    widths = [15, 75, 40, 45]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 235)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    for i, r in enumerate(rows):
        count_str = f"{r['raw_count']:.2f}" if abs(r["raw_count"] - round(r["raw_count"])) > 1e-6 else f"{r['count']}"
        shift_cost = r["length"] * cost_per_hour
        row = [str(i + 1), shift_label(r["start"], r["length"]), count_str, f"{shift_cost:.0f}"]
        for val, w in zip(row, widths):
            pdf.cell(w, 6, val, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(6)

    return bytes(pdf.output())
