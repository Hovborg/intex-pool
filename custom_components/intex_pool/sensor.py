"""Sensor platform."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import decode
from .const import SENSORS
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[IntexSensor] = []
    for desc in SENSORS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexSensor(coordinator, desc, device_id))
    async_add_entities(entities)


class IntexSensor(IntexPoolEntity, SensorEntity):
    """A read-only sensor backed by a DP / cloud property."""

    @property
    def native_value(self):
        raw = self._raw
        desc = self.entity_description
        if desc.value_fn is not None:
            return desc.value_fn(raw)
        if desc.scale is not None:
            return decode.scaled(raw, desc.scale)
        return raw
