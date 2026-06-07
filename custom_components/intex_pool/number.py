"""Number platform (writable cloud targets: pH / ORP)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import decode
from .const import NUMBERS
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[IntexNumber] = []
    for desc in NUMBERS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexNumber(coordinator, desc, device_id))
    async_add_entities(entities)


class IntexNumber(IntexPoolEntity, NumberEntity):
    @property
    def native_value(self) -> float | None:
        raw = self._raw
        desc = self.entity_description
        if desc.scale is not None:
            return decode.scaled(raw, desc.scale)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        desc = self.entity_description
        if desc.scale is not None:
            raw = int(round(value / desc.scale))
        else:
            raw = int(value) if float(value).is_integer() else value
        try:
            await self.coordinator.async_issue(desc.source, raw)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to set {self.entity_id}: {err}") from err
