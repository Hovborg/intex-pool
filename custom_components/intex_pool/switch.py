"""Switch platform (saltwater power/chlorination, Tuya pump on/off)."""
from __future__ import annotations

from dataclasses import replace

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import decode
from .const import (
    DEFAULT_PUMP_ON_DP,
    DEVICE_PUMP,
    PUMP_MODE_TUYA,
    SWITCHES,
)
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    pump_cfg = entry.data.get("pump") or {}
    entities: list[IntexSwitch] = []
    for desc in SWITCHES:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        if desc.device == DEVICE_PUMP:
            if pump_cfg.get("mode") != PUMP_MODE_TUYA:
                continue
            # resolve the configured on/off DP for the Tuya pump
            desc = replace(desc, source=str(pump_cfg.get("on_dp", DEFAULT_PUMP_ON_DP)))
        entities.append(IntexSwitch(coordinator, desc, device_id))
    async_add_entities(entities)


class IntexSwitch(IntexPoolEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return decode.as_bool(self._raw)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        try:
            await self.coordinator.async_set_dp(self.entity_description.source, value)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to set {self.entity_id}: {err}") from err
