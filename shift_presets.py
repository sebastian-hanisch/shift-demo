"""
Ein-Klick-Beispielszenarien und Permalink-Logik - dasselbe SETTING_SPECS-
Muster wie in den anderen Demos (z. B. pack_presets.py): eine Wahrheitsquelle
für Wertebereiche, aus der sowohl die Slider als auch die Permalink-
Begrenzung lesen.
"""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

from shift_constants import (
    AVAILABLE_SHIFT_LENGTHS,
    DEFAULT_BASE_DEMAND,
    DEFAULT_COST_PER_HOUR,
    DEFAULT_FIXED_COST_PER_TYPE,
    DEFAULT_PEAK_HEIGHT,
    DEFAULT_SHIFT_LENGTHS,
    GAP_EXAMPLE,
)


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


def _parse_lengths(v):
    return sorted({int(x) for x in v.split(",") if x.strip()})


def _format_lengths(lengths):
    return ",".join(str(int(l)) for l in sorted(set(lengths)))


SETTING_SPECS = {
    "shift_lengths_multiselect": SettingSpec("len", _parse_lengths, DEFAULT_SHIFT_LENGTHS),
    "n_peaks_slider": SettingSpec("peaks", int, 2, 1, 3),
    "peak_conc_slider": SettingSpec("conc", float, 0.5, 0.0, 1.0),
    "seed_input": SettingSpec("seed", int, 42, 0, 2_000_000_000),
    "base_demand_slider": SettingSpec("base", int, DEFAULT_BASE_DEMAND, 0, 10),
    "peak_height_slider": SettingSpec("peak_h", int, DEFAULT_PEAK_HEIGHT, 2, 20),
    "cost_slider": SettingSpec("cost", float, DEFAULT_COST_PER_HOUR, 5.0, 100.0),
    "fixed_cost_slider": SettingSpec("fixed", float, DEFAULT_FIXED_COST_PER_TYPE, 0.0, 1500.0),
    "wrap_checkbox": SettingSpec("wrap", lambda v: v == "1", False),
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def apply_preset(shift_lengths, n_peaks, peak_conc, seed, base_demand, peak_height, wrap):
    st.session_state["shift_lengths_multiselect"] = list(shift_lengths)
    st.session_state["n_peaks_slider"] = n_peaks
    st.session_state["peak_conc_slider"] = peak_conc
    st.session_state["seed_input"] = seed
    st.session_state["base_demand_slider"] = base_demand
    st.session_state["peak_height_slider"] = peak_height
    st.session_state["wrap_checkbox"] = wrap


def apply_gap_example():
    apply_preset(
        GAP_EXAMPLE["shift_lengths"], GAP_EXAMPLE["n_peaks"], GAP_EXAMPLE["peak_conc"],
        GAP_EXAMPLE["seed"], GAP_EXAMPLE["base_demand"], GAP_EXAMPLE["peak_height"], wrap=True,
    )


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, 2_000_000_000)


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                if isinstance(value, list):
                    value = [v for v in value if v in AVAILABLE_SHIFT_LENGTHS]
                    if not value:
                        continue
                else:
                    if spec.lo is not None:
                        value = max(spec.lo, value)
                    if spec.hi is not None:
                        value = min(spec.hi, value)
                st.session_state[state_key] = value
            except (ValueError, TypeError):
                pass
    st.session_state["permalink_loaded"] = True


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def sync_query_params(shift_lengths, n_peaks, peak_conc, seed, base_demand, peak_height, cost, fixed_cost, wrap):
    try:
        st.query_params["len"] = _format_lengths(shift_lengths)
        st.query_params["peaks"] = str(n_peaks)
        st.query_params["conc"] = str(peak_conc)
        st.query_params["seed"] = str(int(seed))
        st.query_params["base"] = str(base_demand)
        st.query_params["peak_h"] = str(peak_height)
        st.query_params["cost"] = str(cost)
        st.query_params["fixed"] = str(fixed_cost)
        st.query_params["wrap"] = "1" if wrap else "0"
    except Exception:
        pass
