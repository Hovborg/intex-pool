"""Sensor platform."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode, schedule
from .const import DEVICE_META, DEVICE_SALT, DOMAIN, MANUFACTURER, SENSORS
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[SensorEntity] = []
    for desc in SENSORS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexSensor(coordinator, desc, device_id))

    salt_id = device_id_for(entry, DEVICE_SALT)
    if data.schedule is not None and salt_id is not None:
        entities.append(IntexScheduleSensor(data.schedule, salt_id))
        entities.extend(
            IntexScheduleSlotSensor(data.schedule, salt_id, i)
            for i in range(schedule.SLOT_COUNT)
        )

    async_add_entities(entities)


class IntexScheduleSensor(CoordinatorEntity, SensorEntity):
    """Read-only view of the saltwater system's schedules (count + details)."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedules"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_schedules"
        meta = DEVICE_META[DEVICE_SALT]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=meta["name"],
            manufacturer=MANUFACTURER,
            model=meta["model"],
        )

    @property
    def native_value(self) -> int:
        slots = (self.coordinator.data or {}).get("slots") or []
        return len(schedule.active_schedules(slots))

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        active = schedule.active_schedules(data.get("slots") or [])
        return {
            "schedules": [schedule.summarize(s) for s in active],
            "details": [
                {**{k: s[k] for k in schedule.FIELDS[:7]},
                 "mode": schedule.mode_of(s), "summary": schedule.summarize(s)}
                for s in active
            ],
            "raw": data.get("raw"),
        }


class IntexScheduleSlotSensor(CoordinatorEntity, SensorEntity):
    """One sensor per schedule slot, so each schedule shows under the device."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule_slot"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, device_id: str, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_unique_id = f"{device_id}_schedule_{index + 1}"
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
    def native_value(self) -> str:
        slot = self._slot()
        if not slot or not slot.get("active"):
            return "—"
        return schedule.summarize(slot)

    @property
    def extra_state_attributes(self) -> dict:
        slot = self._slot() or {}
        active = bool(slot.get("active"))
        return {
            **{k: slot.get(k) for k in schedule.FIELDS[:7]},
            "active": active,
            "mode": schedule.mode_of(slot) if active else None,
        }


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
