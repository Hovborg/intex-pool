"""Repair flows: user-fixable issues from the Repairs dashboard.

Currently one fixable issue: stale sensor data. The coordinator routes the
measurement request to the matching device's local re-test or cloud property.
"""
from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .models import IntexPoolData
from .tuya import TuyaError


class StaleSensorRepairFlow(RepairsFlow):
    """Confirm-to-fix: trigger a forced measurement on the water sensor."""

    def __init__(self, entry_id: str | None) -> None:
        self._entry_id = entry_id

    async def async_step_init(self, user_input=None) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> data_entry_flow.FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="confirm")
        entry = (
            self.hass.config_entries.async_get_entry(self._entry_id)
            if self._entry_id
            else None
        )
        if entry is not None and entry.state is ConfigEntryState.LOADED:
            data: IntexPoolData = entry.runtime_data
            if data.sensor is not None:
                try:
                    await data.sensor.async_refresh_measure()
                except (TuyaError, OSError, TimeoutError):
                    return self.async_show_form(
                        step_id="confirm", errors={"base": "cannot_refresh"}
                    )
        # Creating the entry closes the flow and removes the issue; it will be
        # re-raised by the listener if the measurement never arrives.
        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict | None
) -> RepairsFlow:
    """Return the fix flow for an issue (only sensor_stale_* is fixable)."""
    return StaleSensorRepairFlow((data or {}).get("entry_id"))
