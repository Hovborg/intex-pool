"""Diagnostics support — credentials are redacted, raw device data included.

``entry.data`` carries the Tuya ``local_key`` and developer-cloud
``access_id``/``access_secret``; those must never leave the system in a
diagnostics download (they routinely end up attached to GitHub issues).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_ID, CONF_ACCESS_SECRET, CONF_LOCAL_KEY
from .models import IntexPoolConfigEntry

TO_REDACT = {CONF_LOCAL_KEY, CONF_ACCESS_ID, CONF_ACCESS_SECRET}


def _coordinator_snapshot(coordinator) -> dict[str, Any] | None:
    if coordinator is None:
        return None
    return {
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
        "data": coordinator.data,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IntexPoolConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    data = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
            "version": entry.version,
        },
        "coordinators": {
            "salt": _coordinator_snapshot(data.salt),
            "sensor": _coordinator_snapshot(data.sensor),
            "pump": _coordinator_snapshot(data.pump),
            "schedule": _coordinator_snapshot(data.schedule),
            "analyzer_schedule": _coordinator_snapshot(data.analyzer_schedule),
            "pump_schedule": _coordinator_snapshot(data.pump_schedule),
        },
    }
