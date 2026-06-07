"""Base entity + platform helpers for Intex Pool."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_META, DEVICE_PUMP, DEVICE_SALT, DEVICE_SENSOR, DOMAIN, MANUFACTURER
from .models import IntexPoolConfigEntry, IntexPoolData


def coordinator_for(data: IntexPoolData, device: str):
    """Return the active coordinator for a device type, or None."""
    return {DEVICE_SALT: data.salt, DEVICE_SENSOR: data.sensor, DEVICE_PUMP: data.pump}[device]


def device_id_for(entry: IntexPoolConfigEntry, device: str) -> str | None:
    """Return the Tuya device id stored for a device type (None if not applicable)."""
    section = entry.data.get(device) or {}
    return section.get("device_id")


class IntexPoolEntity(CoordinatorEntity):
    """Common base: device grouping, stable unique id, coordinator-driven."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description, device_id: str) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        meta = DEVICE_META[description.device]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=meta["name"],
            manufacturer=MANUFACTURER,
            model=meta["model"],
        )

    @property
    def _raw(self) -> Any:
        """The raw value for this entity's DP/property from coordinator data."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get(self.entity_description.source)
