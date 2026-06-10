"""Base entity + platform helpers for Intex Pool."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DEVICE_META, DEVICE_PUMP, DEVICE_SALT, DEVICE_SENSOR, DOMAIN, MANUFACTURER
from .models import IntexPoolConfigEntry, IntexPoolData

if TYPE_CHECKING:
    from .coordinator import ScheduleCoordinator


def device_info_for(device: str, device_id: str) -> DeviceInfo:
    """DeviceInfo for a Tuya device id (salt / sensor / Tuya pump)."""
    meta = DEVICE_META[device]
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=meta["name"], manufacturer=MANUFACTURER, model=meta["model"],
    )


def pump_device_info(entry: IntexPoolConfigEntry) -> DeviceInfo:
    """A virtual 'Sand filter pump' device for an entity-linked pump's controls."""
    meta = DEVICE_META[DEVICE_PUMP]
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_pump")},
        name=meta["name"], manufacturer=MANUFACTURER, model="Linked pump",
    )


def coordinator_for(data: IntexPoolData, device: str) -> DataUpdateCoordinator | None:
    """Return the active coordinator for a device type, or None."""
    mapping = {DEVICE_SALT: data.salt, DEVICE_SENSOR: data.sensor, DEVICE_PUMP: data.pump}
    if device not in mapping:
        raise ValueError(f"Unknown Intex Pool device type: {device!r}")
    return mapping[device]


async def write_slots_guarded(
    coordinator: ScheduleCoordinator, slots: list[dict[str, Any]], what: str
) -> None:
    """Write schedule slots, converting any failure into a HomeAssistantError.

    Shared by every schedule-editing entity (slot switches, duration numbers,
    start times) so cloud-write failures surface to the user consistently
    instead of as raw platform exceptions.
    """
    try:
        await coordinator.async_write_slots(slots)
    except HomeAssistantError:
        raise
    except Exception as err:  # noqa: BLE001
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="schedule_write_failed",
            translation_placeholders={"name": what, "error": str(err)},
        ) from err


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
