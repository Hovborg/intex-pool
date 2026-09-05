"""Repair issues: actionable problems surfaced in HA's Repairs dashboard.

Three conditions are watched via coordinator listeners:

* **Salt alarm** (DP127): flow loss, salt out of range, electrode faults, …
  The fix texts come straight from the Intex manual (REFERENCE.md §5).
* **Sensor maintenance** (``maintenance_indicator == red``): probes need
  cleaning/calibration.
* **Stale sensor data**: the sleeping water sensor normally reports about once
  an hour; if the newest measurement is much older than that, the readings on
  the dashboard are silently outdated (this is exactly how a dead/replaced
  device id presented in the field).
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from . import calibration, decode
from .const import DOMAIN, STALE_AFTER_HOURS
from .models import IntexPoolConfigEntry

# Alarm tokens that get their own translated repair text (manual fix steps).
_ALARM_ISSUE_KEYS = {"e90", "e91e92", "e01e02", "e03e04", "e97", "e99"}
# Tokens that mean "no problem" — clear the alarm issue.
_ALARM_OK = {None, "normal", "e93"}
# Hardware faults are errors; the rest are warnings.
_ALARM_SEVERE = {"e97", "e99"}

# The sensor reports ~1x/hour; treat anything older than this as stale.
STALE_AFTER = timedelta(hours=STALE_AFTER_HOURS)


def async_setup_issue_listeners(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> None:
    """Attach coordinator listeners that create/clear repair issues."""
    data = entry.runtime_data

    if data.salt is not None:
        salt = data.salt
        alarm_issue = f"salt_alarm_{entry.entry_id}"

        @callback
        def _check_alarm() -> None:
            if not salt.last_update_success:
                # Offline: we can't confirm the alarm cleared — leave any
                # existing issue intact instead of hiding a real problem.
                return
            token = decode.normalize_alarm((salt.data or {}).get("127"))
            if token in _ALARM_OK:
                ir.async_delete_issue(hass, DOMAIN, alarm_issue)
                return
            key = f"salt_alarm_{token}" if token in _ALARM_ISSUE_KEYS else "salt_alarm"
            ir.async_create_issue(
                hass, DOMAIN, alarm_issue,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR
                if token in _ALARM_SEVERE
                else ir.IssueSeverity.WARNING,
                translation_key=key,
                translation_placeholders={"code": token.upper()},
            )

        entry.async_on_unload(salt.async_add_listener(_check_alarm))

    if data.sensor is not None:
        sensor = data.sensor
        maint_issue = f"sensor_maintenance_{entry.entry_id}"
        stale_issue = f"sensor_stale_{entry.entry_id}"
        cal_reset_issue = f"calibration_reset_{entry.entry_id}"
        cal_stale_issue = f"calibration_stale_{entry.entry_id}"

        @callback
        def _check_calibration(props: dict) -> None:
            """Reset software offsets when the device was recalibrated in the
            app (its caliberate coefficients moved), and flag offsets older
            than the manual's own 4-month cadence."""
            cal = calibration.get_calibration(entry)
            if not cal:
                return
            has_offsets = bool(cal.get("ph_offset") or cal.get("orp_offset"))
            coeffs = cal.get("device_coeffs") or {}
            current = {
                "ph": props.get("ph_caliberate"),
                "orp": props.get("orp_caliberate"),
            }
            if (
                has_offsets
                and coeffs
                and any(
                    coeffs.get(k) is not None
                    and current.get(k) is not None
                    and coeffs[k] != current[k]
                    for k in ("ph", "orp")
                )
            ):
                # Device baseline moved -> our offsets are obsolete.
                calibration.async_store_calibration(
                    hass, entry,
                    {"ph_offset": 0.0, "orp_offset": 0.0},
                    device_coeffs=current,
                )
                ir.async_create_issue(
                    hass, DOMAIN, cal_reset_issue,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="calibration_reset",
                )
                return
            ir.async_delete_issue(hass, DOMAIN, cal_reset_issue)

            calibrated_at = dt_util.parse_datetime(cal.get("calibrated_at") or "")
            if (
                has_offsets
                and calibrated_at is not None
                and dt_util.utcnow() - calibrated_at
                > timedelta(days=calibration.STALE_AFTER_DAYS)
            ):
                ir.async_create_issue(
                    hass, DOMAIN, cal_stale_issue,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="calibration_stale",
                    translation_placeholders={
                        "days": str(calibration.STALE_AFTER_DAYS)
                    },
                )
            else:
                ir.async_delete_issue(hass, DOMAIN, cal_stale_issue)

        @callback
        def _check_sensor() -> None:
            if not sensor.last_update_success:
                # Offline: can't confirm anything cleared — keep existing issues.
                return
            props = sensor.data or {}
            _check_calibration(props)
            maint = decode.normalize_indicator(
                props.get("maintenance_indicator"), decode.MAINTENANCE_OPTIONS
            )
            if maint == "red":
                ir.async_create_issue(
                    hass, DOMAIN, maint_issue,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="sensor_maintenance",
                )
            else:
                ir.async_delete_issue(hass, DOMAIN, maint_issue)

            last = decode.last_measurement(props.get("_times"))
            if last is not None and dt_util.utcnow() - last > STALE_AFTER:
                ir.async_create_issue(
                    hass, DOMAIN, stale_issue,
                    # Fixable: the repair flow forces a fresh measurement
                    # through the device-aware coordinator — see repairs.py.
                    is_fixable=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="sensor_stale",
                    translation_placeholders={
                        "last": last.isoformat(timespec="minutes")
                    },
                    data={"entry_id": entry.entry_id},
                )
            else:
                ir.async_delete_issue(hass, DOMAIN, stale_issue)

        entry.async_on_unload(sensor.async_add_listener(_check_sensor))
