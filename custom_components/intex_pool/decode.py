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
