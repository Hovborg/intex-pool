"""Langelier Saturation Index (LSI) — pool water balance.

Pure functions, no Home Assistant imports. The math reproduces the
industry-standard chart (CDC MAHC 2024 Annex Table 5.7.4.6 / Taylor / CPO)
to +/-0.01 at every published breakpoint, computed continuously via the
closed forms behind the tables:

    LSI = pH + TF + CF + AF - TDS_constant

* AF = log10(carbonate alkalinity), CarbAlk = TA - CYA x F(pH) where
  F(pH) = 0.388 / (1 + 10^(6.78 - pH)) (Wojtowicz/PHTA; ~CYA/3 at pH 7.6)
* CF = log10(0.4 x CH)  -- the classic-chart factor; using log10(CH) with
  the 12.1 constant is the canonical implementation bug (+0.40 error)
* TF = -0.56 + 0.01827 x degF - 0.000041 x degF^2 (Wojtowicz fit of the
  Van Waters & Rogers table; valid 32-105 degF, clamped)
* TDS constant per CDC MAHC: 12.1 below 1000 ppm TDS, 12.2 above.

Sources: CDC MAHC 2024 Annex 5.7.4.6; APSP/PHTA Water Balance Indexes
(2017); PHTA Alkalinity fact sheet (2021); Wojtowicz, JSPSI 1(1) & 3(1);
Taylor Watergram; Orenda LSI methodology.
"""
from __future__ import annotations

import math

# Interpretation bands: balanced -0.3..+0.3 (CDC MAHC / Orenda); APSP and
# Taylor tolerate up to +0.5 -> a "slightly scaling" watch zone in between.
BALANCED_BAND = 0.3
SEVERE_BAND = 0.5

WATER_BALANCE_OPTIONS = [
    "severely_corrosive",
    "slightly_corrosive",
    "balanced",
    "slightly_scaling",
    "scale_forming",
]


def cya_correction_factor(ph: float) -> float:
    """pH-dependent cyanurate fraction (Wojtowicz; PHTA Table 1, +/-0.01)."""
    return 0.388 / (1.0 + 10.0 ** (6.78 - ph))


def carbonate_alkalinity(ta: float, cya: float, ph: float) -> float:
    """Carbonate alkalinity: measured TA minus the cyanurate contribution."""
    return ta - cya * cya_correction_factor(ph)


def lsi(
    ph: float,
    temp_c: float,
    ta: float,
    ch: float,
    cya: float = 0.0,
    tds: float = 0.0,
) -> float | None:
    """Pool-chart LSI, or None when the inputs can't produce one.

    *ta*/*ch* in ppm as CaCO3 (standard test-kit output); *cya*/*tds* in ppm,
    0 = none/unknown (TDS 0 -> the classic 12.1 constant, correct for
    non-salt fills; SWG owners should pass ~their salt ppm).
    """
    if ta <= 0 or ch <= 0:
        return None
    carb_alk = carbonate_alkalinity(ta, cya, ph)
    if carb_alk <= 0:
        return None
    temp_f = min(max(temp_c * 1.8 + 32.0, 32.0), 105.0)  # table validity range
    tf = -0.56 + 0.01827 * temp_f - 0.000041 * temp_f**2
    cf = math.log10(0.4 * ch)
    af = math.log10(carb_alk)
    tds_const = 12.1 if (tds or 0) < 1000 else 12.2
    return round(ph + tf + cf + af - tds_const, 2)


def classify(value: float | None) -> str | None:
    """Interpretation token for an LSI value (see WATER_BALANCE_OPTIONS)."""
    if value is None:
        return None
    if value < -SEVERE_BAND:
        return "severely_corrosive"
    if value < -BALANCED_BAND:
        return "slightly_corrosive"
    if value <= BALANCED_BAND:
        return "balanced"
    if value <= SEVERE_BAND:
        return "slightly_scaling"
    return "scale_forming"
