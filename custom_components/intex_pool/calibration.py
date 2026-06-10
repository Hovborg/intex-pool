"""Software calibration offsets for the water analyzer.

Research-grounded model (see README): the Intex app's buffer-powder
calibration is the authoritative baseline (two-point pH, one-point ORP at
256 mV); the offsets here are a *drift bridge* between those calibrations,
anchored to the user's own reference test (drop kit preferred, strips are
coarse). Offset-only on purpose — over the pool's narrow 7.0-7.8 band the
residual slope error after an offset anchor is far below the device's
+/-0.2 pH spec, and pretending to fit a slope from strip readings would be
false precision. FC is never calibrated: it is a derived "reference only"
value computed device-side from its own (uncorrected) pH/ORP.

Stored in the config entry options under ``calibration``:
``{"ph_offset": float, "orp_offset": float, "calibrated_at": iso,
"device_coeffs": {"ph": raw, "orp": raw}}``. The device_coeffs snapshot of
the (read-only!) ``ph_caliberate``/``orp_caliberate`` cloud coefficients
lets us detect that the device was recalibrated in the app — the software
offsets are then obsolete and get reset (see issues.py).
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import CONF_CALIBRATION, SIGNAL_OPTIONS_UPDATED
from .models import IntexPoolConfigEntry

# Guardrails (industry figures, see research notes in the README):
# 30 mV electrode asymmetry ~ 0.5 pH is the "clean/recalibrate/replace"
# threshold -> clamp there; below the device's 0.1 resolution a correction
# is noise -> deadband to zero.
PH_MAX_OFFSET = 0.5
PH_DEADBAND = 0.1
ORP_MAX_OFFSET = 100  # mV
ORP_DEADBAND = 10  # mV
# Matches the manual's own 4-month recalibration cadence.
STALE_AFTER_DAYS = 120


def get_calibration(entry: IntexPoolConfigEntry) -> dict[str, Any]:
    """The stored calibration record ({} when never calibrated)."""
    return entry.options.get(CONF_CALIBRATION) or {}


def ph_offset(entry: IntexPoolConfigEntry) -> float:
    try:
        return float(get_calibration(entry).get("ph_offset") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def orp_offset(entry: IntexPoolConfigEntry) -> float:
    try:
        return float(get_calibration(entry).get("orp_offset") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def offset_for(entry: IntexPoolConfigEntry, parameter: str) -> float:
    return ph_offset(entry) if parameter == "ph" else orp_offset(entry)


def async_store_calibration(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    updates: dict[str, Any] | None,
    device_coeffs: dict[str, Any] | None = None,
) -> None:
    """Persist calibration updates in the entry options (no reload needed).

    ``updates=None`` clears the whole calibration record.
    """
    if updates is None:
        options = {k: v for k, v in entry.options.items() if k != CONF_CALIBRATION}
    else:
        record = {**get_calibration(entry), **updates}
        record["calibrated_at"] = dt_util.utcnow().isoformat(timespec="seconds")
        if device_coeffs is not None:
            record["device_coeffs"] = device_coeffs
        options = {**entry.options, CONF_CALIBRATION: record}
    hass.config_entries.async_update_entry(entry, options=options)
    async_dispatcher_send(hass, SIGNAL_OPTIONS_UPDATED.format(entry.entry_id))
