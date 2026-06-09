"""Time platform: editable start time per saltwater schedule slot."""
from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import schedule
from .const import DEVICE_META, DEVICE_SALT, DOMAIN, MANUFACTURER
from .entity import device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    salt_id = device_id_for(entry, DEVICE_SALT)
    if data.schedule is not None and salt_id is not None:
        async_add_entities(
            IntexScheduleStartTime(data.schedule, salt_id, i)
            for i in range(schedule.SLOT_COUNT)
        )


class IntexScheduleStartTime(CoordinatorEntity, TimeEntity):
    """Editable start time for one schedule slot."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule_start"
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, device_id: str, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_unique_id = f"{device_id}_schedule_{index + 1}_start"
        meta = DEVICE_META[DEVICE_SALT]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=meta["name"],
            manufacturer=MANUFACTURER,
            model=meta["model"],
        )

    def _slot(self) -> dict | None:
        slots = (self.coordinator.data or {}).get("slots") or []
        return slots[self._index] if self._index < len(slots) else None

    @property
    def native_value(self) -> dt_time | None:
        slot = self._slot()
        if not slot or not slot.get("active"):
            return None
        return dt_time(hour=int(slot.get("hour", 0)) % 24, minute=int(slot.get("minute", 0)) % 60)

    async def async_set_value(self, value: dt_time) -> None:
        slots = (self.coordinator.data or {}).get("slots") or schedule.decode_schedules("")
        new = schedule.set_slot(slots, self._index, hour=value.hour, minute=value.minute)
        await self.coordinator.async_write_slots(new)
