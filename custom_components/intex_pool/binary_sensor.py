"""Binary sensor platform (DP flags + per-device connectivity)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode
from .const import BINARY_SENSORS, DEVICE_META, DOMAIN, MANUFACTURER
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 0

_DEVICES = ("salt", "sensor", "pump")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[BinarySensorEntity] = []

    # DP-flag binary sensors
    for desc in BINARY_SENSORS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexBinarySensor(coordinator, desc, device_id))

    # One connectivity sensor per active (Tuya) device
    for device in _DEVICES:
        coordinator = coordinator_for(data, device)
        device_id = device_id_for(entry, device)
        if coordinator is None or device_id is None:
            continue
        entities.append(IntexConnectivity(coordinator, device, device_id))

    async_add_entities(entities)


class IntexBinarySensor(IntexPoolEntity, BinarySensorEntity):
    """A read-only boolean DP flag."""

    @property
    def is_on(self) -> bool | None:
        return decode.as_bool(self._raw)


class IntexConnectivity(CoordinatorEntity, BinarySensorEntity):
    """Per-device reachability — stays available, reports on/off."""

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device: str, device_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_connectivity"
        meta = DEVICE_META[device]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=meta["name"],
            manufacturer=MANUFACTURER,
            model=meta["model"],
        )

    @property
    def available(self) -> bool:
        return True  # the connectivity sensor itself is always available

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
