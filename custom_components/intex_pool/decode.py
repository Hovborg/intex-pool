"""Pure value decoders / normalizers for Intex Pool Tuya data.

No Home Assistant imports — these are plain functions so they can be unit
tested in isolation. Raw Tuya enum/bitmap values are normalized into stable
lowercase tokens; the human-readable text for each token lives in the entity
state translations (``strings.json`` / ``translations/*.json``), so the
integration stays translatable instead of hard-coding one language.

All mappings are ported from ``01-drift/13-pool-kontrol/manuals/REFERENCE.md``
(§2 saltwater DP spec, §3 sensor property spec, §5 error codes), which was
distilled live from the Tuya thing-model on 2026-06-07.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# --- DP114 (saltwater) / sensor "error_code": integer code -> token (REF §2/§5) ---
SALT_ERROR_CODES: dict[int, str] = {
    0: "none",
    101: "e1", 102: "e2", 103: "e3", 104: "e4", 105: "e5",
    180: "e80", 181: "e81",
    190: "e90", 191: "e91", 192: "e92", 193: "e93", 194: "e94",
    195: "e95", 196: "e96", 197: "e97", 199: "e99", 200: "end",
}
ERROR_OPTIONS: list[str] = list(dict.fromkeys(SALT_ERROR_CODES.values()))

# --- DP125 working_indicator (REF §2) ---
STATUS_OPTIONS: list[str] = ["working", "fp_mode", "sleep", "boost"]

# --- DP127 warntype_indicator (REF §2) ---
ALARM_OPTIONS: list[str] = [
    "normal", "e93", "e90", "e01e02", "e03e04",
    "e91e92", "e05", "e94", "e95", "e96", "e97", "e99",
]

# --- sensor indicators (REF §3) ---
PH_INDICATOR_OPTIONS: list[str] = ["off", "red", "green"]
ORP_INDICATOR_OPTIONS: list[str] = ["off", "red", "green", "saltwater_abnormal"]
FC_INDICATOR_OPTIONS: list[str] = ["off", "red", "green"]
MAINTENANCE_OPTIONS: list[str] = ["off", "red"]

# --- sensor ORP_dif_Number trend enum (REF §3): raw no/red/green/blue ---
# Raw colour tokens map to semantic levels (0=no, 1=low, 2=mid, 3=high).
ORP_TREND_RAW_TO_TOKEN: dict[str, str] = {
    "no": "none", "red": "low", "green": "mid", "blue": "high",
}
ORP_TREND_OPTIONS: list[str] = list(dict.fromkeys(ORP_TREND_RAW_TO_TOKEN.values()))

# Cloud measurement properties whose report time feeds "Last measurement".
MEASUREMENT_CODES: tuple[str, ...] = (
    "PH_Number", "ORP_Number", "fc_number", "water_tempture_c", "battery_capacity",
)


def normalize_error(raw: Any) -> str | None:
    """Map a raw error_code value to a token, or None if unknown/blank."""
    try:
        return SALT_ERROR_CODES.get(int(raw))
    except (TypeError, ValueError):
        return None


def _enum_token(raw: Any, options: list[str]) -> str | None:
    """Lowercase a raw enum value and return it only if it's a known option."""
    if raw is None:
        return None
    token = str(raw).strip().lower()
    return token if token in options else None


def normalize_status(raw: Any) -> str | None:
    """DP125 working_indicator -> token."""
    return _enum_token(raw, STATUS_OPTIONS)


def normalize_alarm(raw: Any) -> str | None:
    """DP127 warntype_indicator -> token."""
    return _enum_token(raw, ALARM_OPTIONS)


def normalize_indicator(raw: Any, options: list[str]) -> str | None:
    """Generic indicator enum -> token (pass the relevant *_OPTIONS list)."""
    return _enum_token(raw, options)


def normalize_orp_trend(raw: Any) -> str | None:
    """ORP_dif_Number colour enum -> semantic trend token (none/low/mid/high)."""
    if raw is None:
        return None
    return ORP_TREND_RAW_TO_TOKEN.get(str(raw).strip().lower())


def last_measurement(times: Any) -> datetime | None:
    """Newest report time (epoch ms) across the measurement properties -> datetime.

    *times* is the ``{code: epoch_ms}`` dict the cloud client stashes under the
    reserved ``_times`` key. Falls back to the newest time of any property if
    none of the known measurement codes are present.
    """
    if not isinstance(times, dict) or not times:
        return None
    stamps = [
        t for code in MEASUREMENT_CODES
        if isinstance((t := times.get(code)), (int, float)) and t > 0
    ]
    if not stamps:
        stamps = [t for t in times.values() if isinstance(t, (int, float)) and t > 0]
    if not stamps:
        return None
    return datetime.fromtimestamp(max(stamps) / 1000, tz=UTC)


def scaled(raw: Any, factor: float, digits: int = 2) -> float | None:
    """Multiply a raw numeric value by *factor* (e.g. pH 740 -> 7.4), or None."""
    if raw is None:
        return None
    try:
        return round(float(raw) * factor, digits)
    except (TypeError, ValueError):
        return None


def as_bool(raw: Any) -> bool | None:
    """Coerce a Tuya bool-ish value to bool, or None if absent."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in ("true", "on", "1")
