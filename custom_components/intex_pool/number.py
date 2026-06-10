"""Number platform (writable cloud targets: pH / ORP, pool volume)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import calibration, decode, schedule
from .const import (
    CONF_POOL_VOLUME,
    CONF_VOLUME_UNIT,
    DEVICE_META,
    DEVICE_SALT,
    DEVICE_SENSOR,
    DOMAIN,
    MANUFACTURER,
    NUMBERS,
    SIGNAL_OPTIONS_UPDATED,
    VOLUME_UNIT_GALLON,
)
from .entity import (
    IntexPoolEntity,
    coordinator_for,
    device_id_for,
    device_info_for,
    write_slots_guarded,
)
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

    # Pool volume for the salt advisor — editable right on the device page.
    if data.salt is not None and salt_id is not None:
        entities.append(IntexPoolVolumeNumber(entry, salt_id))

    # Software calibration offsets (drift bridge between app calibrations).
    sensor_id = device_id_for(entry, DEVICE_SENSOR)
    if data.sensor is not None and sensor_id is not None:
        entities.append(IntexCalibrationOffsetNumber(entry, sensor_id, "ph"))
        entities.append(IntexCalibrationOffsetNumber(entry, sensor_id, "orp"))

    async_add_entities(entities)


class IntexCalibrationOffsetNumber(NumberEntity):
    """User calibration offset applied to the pH/ORP reading.

    Usually set via the ``intex_pool.calibrate`` service (which computes the
    offset from a reference test), but directly editable too. The ORP offset
    is advanced/disabled by default: there is no sound home reference for ORP
    (strips measure FC, not ORP) — a low ORP is usually chemistry (CYA) or
    fouling, which an offset would dangerously hide.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(self, entry: IntexPoolConfigEntry, device_id: str, parameter: str) -> None:
        self._entry = entry
        self._parameter = parameter
        self._attr_translation_key = f"{parameter}_offset"
        self._attr_unique_id = f"{device_id}_{parameter}_offset"
        self._attr_device_info = device_info_for(DEVICE_SENSOR, device_id)
        if parameter == "ph":
            self._attr_native_min_value = -calibration.PH_MAX_OFFSET
            self._attr_native_max_value = calibration.PH_MAX_OFFSET
            self._attr_native_step = 0.05
        else:
            self._attr_native_min_value = -calibration.ORP_MAX_OFFSET
            self._attr_native_max_value = calibration.ORP_MAX_OFFSET
            self._attr_native_step = 1
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
            self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_OPTIONS_UPDATED.format(self._entry.entry_id),
                self._refresh,
            )
        )

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        return calibration.offset_for(self._entry, self._parameter)

    async def async_set_native_value(self, value: float) -> None:
        calibration.async_store_calibration(
            self.hass, self._entry, {f"{self._parameter}_offset": round(value, 2)}
        )
        self.async_write_ha_state()


class IntexPoolVolumeNumber(NumberEntity):
    """Pool volume (in the chosen unit) — stored in the entry options.

    Updates apply immediately (the advisor reads the options live); no entry
    reload is needed. The displayed unit follows the Volume unit select.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "pool_volume"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 200_000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(self, entry: IntexPoolConfigEntry, device_id: str) -> None:
        self._entry = entry
        self._attr_unique_id = f"{device_id}_pool_volume"
        self._attr_device_info = device_info_for(DEVICE_SALT, device_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_OPTIONS_UPDATED.format(self._entry.entry_id),
                self._refresh,
            )
        )

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self) -> str:
        if self._entry.options.get(CONF_VOLUME_UNIT) == VOLUME_UNIT_GALLON:
            return UnitOfVolume.GALLONS
        return UnitOfVolume.LITERS

    @property
    def native_value(self) -> float | None:
        try:
            return float(self._entry.options.get(CONF_POOL_VOLUME, 0) or 0)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_POOL_VOLUME: int(value)},
        )
        async_dispatcher_send(
            self.hass, SIGNAL_OPTIONS_UPDATED.format(self._entry.entry_id)
        )
        self.async_write_ha_state()


class IntexScheduleDuration(CoordinatorEntity, NumberEntity):
    """Editable duration (hours) for one schedule slot."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 72
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, device_id: str, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        # Slot 0 is the Boost cycle: only a duration, labelled "Boost duration".
        if index == 0:
            self._attr_translation_key = "boost_duration"
        else:
            self._attr_translation_key = "schedule_duration"
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
        await write_slots_guarded(self.coordinator, new, self.entity_id)


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
