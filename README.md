# 🗓️ Schichtplanung (Personalbedarfsdeckung)

Interaktive Demo zur Schichtplanung: Ein stündlicher Personalmindestbedarf über 24 Stunden muss durch eine Auswahl an Schichten gedeckt werden — mit möglichst wenigen/günstigen Schichten.

**[→ Demo live ausprobieren](https://sebastianhanisch-shift-demo.streamlit.app/)**

## Worum geht's?

Ein klassisches Mengenüberdeckungsproblem (Set Cover), hier mit einer besonderen mathematischen Eigenschaft im Fokus: **totale Unimodularität (TU)**. Wenn jede Schicht einen zusammenhängenden Zeitblock abdeckt (kein Wraparound über Mitternacht) und keine Fixkosten pro Schichttyp aktiv sind, liefert die LP-Relaxierung automatisch eine ganzzahlige Lösung — ein ILP-Solver ist dafür streng genommen nicht nötig. Die Demo macht live sichtbar, wann diese Garantie gilt und wann nicht.

## Methodik

- Drei Lösungsverfahren im direkten Vergleich: **Greedy-Heuristik**, **LP-Relaxierung** und **exaktes ILP** (Google OR-Tools)
- Zusätzlich: **Genetischer Algorithmus** und **Ant-Colony-Optimization** als Metaheuristik-Vergleich
- Mehrere Schichtlängen gleichzeitig wählbar, optionale Fixkosten pro Schichttyp (Fixed-Charge-Struktur, bricht die TU-Garantie unabhängig vom Wraparound)
- Mathematische Herleitung der TU-Eigenschaft (inkl. klassischem Odd-Cycle-Lehrbuchbeispiel) im Expander „Mathematische Formulierung“
- PDF-Export, Permalink

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `pytest tests/ -v`

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von [Sebastian Hanisch](https://sebastianhanisch.net) — Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
