"""Number platform (writable cloud targets: pH / ORP)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode, schedule
from .const import DEVICE_META, DEVICE_SALT, DOMAIN, MANUFACTURER, NUMBERS
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[NumberEntity] = []
    for desc in NUMBERS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexNumber(coordinator, desc, device_id))

    salt_id = device_id_for(entry, DEVICE_SALT)
    if data.schedule is not None and salt_id is not None:
        entities.extend(
            IntexScheduleDuration(data.schedule, salt_id, i)
            for i in range(schedule.SLOT_COUNT)
        )

    async_add_entities(entities)


class IntexScheduleDuration(CoordinatorEntity, NumberEntity):
    """Editable duration (hours) for one schedule slot."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule_duration"
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 72
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, device_id: str, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_unique_id = f"{device_id}_schedule_{index + 1}_duration"
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
    def available(self) -> bool:
        slot = self._slot()
        return super().available and bool(slot and slot.get("active"))

    @property
    def native_value(self) -> float | None:
        slot = self._slot()
        if not slot or not slot.get("active"):
            return None
        return float(slot.get("duration", 0))

    async def async_set_native_value(self, value: float) -> None:
        slots = (self.coordinator.data or {}).get("slots") or schedule.decode_schedules("")
        new = schedule.set_slot(slots, self._index, duration=int(value))
        await self.coordinator.async_write_slots(new)


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
