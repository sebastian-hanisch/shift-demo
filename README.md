# 🗓️ Schichtplanung (Personalbedarfsdeckung)

Interaktive Demo zur Schichtplanung: Ein stündlicher Personalmindestbedarf über 24 Stunden muss durch eine Auswahl an Schichten gedeckt werden — mit möglichst wenigen/günstigen Schichten.

**[→ Demo live ausprobieren](https://sebastianhanisch-shift-demo.streamlit.app/)**

## Worum geht's?

Ein klassisches Mengenüberdeckungsproblem (Set Cover), hier mit einer besonderen mathematischen Eigenschaft im Fokus: **totale Unimodularität (TU)**. Wenn jede Schicht einen zusammenhängenden Zeitblock abdeckt (kein Wraparound über Mitternacht) und keine Fixkosten pro Schichttyp aktiv sind, liefert die LP-Relaxierung automatisch eine ganzzahlige Lösung — ein ILP-Solver ist dafür streng genommen nicht nötig. Die Demo macht live sichtbar, wann diese Garantie gilt und wann nicht.

## Methodik

- Drei Lösungsverfahren im direkten Vergleich: **Greedy-Heuristik**, **LP-Relaxierung** und **exaktes ILP** (Google OR-Tools)
- Mehrere Schichtlängen gleichzeitig wählbar, optionale Fixkosten pro Schichttyp (Fixed-Charge-/Big-M-Struktur, bricht die TU-Garantie unabhängig vom Wraparound)
- Mathematische Herleitung der TU-Eigenschaft (inkl. klassischem Odd-Cycle-Lehrbuchbeispiel) im Expander „Mathematische Formulierung“
- PDF-Export, Permalink

## Wie ist das entstanden?

Angeregt durch ein Gespräch über eine Bachelorarbeit zur Schichtplanung und totaler Unimodularität — die Demo sollte genau diesen Effekt direkt erlebbar machen, nicht nur behaupten.

**Erst die Mathematik geprüft, dann die Oberfläche gebaut.** Vor der ersten Zeile UI-Code stand ein Prototyp, der per Zufallssuche über Schichtlängen/Seeds/Nachfragemuster prüfte, wie oft eine Wraparound-Konfiguration tatsächlich eine Ganzzahligkeitslücke zwischen LP-Relaxierung und ILP erzeugt: rund 22 % der Zufallskombinationen zeigten eine Lücke. Eine der stärksten davon ist als Preset „Beispiel mit Ganzzahligkeitslücke“ fest hinterlegt — kein Zufallstreffer, sondern eine geprüfte Garantie, dass der Effekt beim Klick auch wirklich sichtbar wird.

**Zwei echte Bugs beim Bauen gefunden:**
- Der PDF-Export stürzte bei jedem Schichtplan mit mindestens einer besetzten Schicht ab — die Kernschrift von FPDF (Helvetica) kann den Halbgeviertstrich (–) in den Zeitangaben („06:00–14:00“) nicht darstellen. Behoben durch reine ASCII-Beschriftung („06:00-14:00“), analog zur bereits an anderer Stelle im Portfolio etablierten Konvention.
- Die Stunden-Achsenbeschriftung eines Charts nutzte `tickformat="02d:00"` — das ist Python-Formatsyntax, kein gültiges Plotly-D3-Format. Die Achse brach dadurch beim Rendern (stille SVG-Fehler), behoben durch explizite `tickvals`/`ticktext`.

**Später erweitert** um mehrere gleichzeitig wählbare Schichtlängen und optionale Fixkosten pro Schichttyp — ein zweiter, vom Wraparound unabhängiger Weg, die TU-Garantie zu brechen (die Kopplung `x_j ≤ M_j · y_L` zwischen einer kontinuierlichen und einer binären Variable ist eine klassische Big-M-/Fixed-Charge-Struktur, die die Intervalleigenschaft der reinen Deckungsmatrix zerstört). Dazu die formale Herleitung im Expander „Mathematische Formulierung“ sowie eine Neustrukturierung nach dem Muster der übrigen Demos: Ergebnis zuerst, vollständiger Methodenvergleich sekundär im Expander.

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `pytest tests/ -v`

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von [Sebastian Hanisch](https://sebastianhanisch.net) — Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
