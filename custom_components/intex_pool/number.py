"""Number platform (writable cloud targets: pH / ORP, pool volume)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
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
    CONF_CALCIUM_HARDNESS,
    CONF_CYA,
    CONF_POOL_VOLUME,
    CONF_QUICK_RUN_HOURS,
    CONF_TDS,
    CONF_TOTAL_ALKALINITY,
    CONF_VOLUME_UNIT,
    DEFAULT_QUICK_RUN_HOURS,
    DEVICE_META,
    DEVICE_PUMP,
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
    pump_id = device_id_for(entry, DEVICE_PUMP)
    if data.pump_schedule is not None and pump_id is not None:
        # Slot 0 excluded (unlike salt) — reserved for the Quick Run button;
        # see the matching note in switch.py's pump loop.
        entities.extend(
            IntexScheduleDuration(data.pump_schedule, pump_id, i, device=DEVICE_PUMP)
            for i in range(1, schedule.SLOT_COUNT)
        )
        # Paired with the Quick Run button (button.py) — holds how many hours
        # the next press should request. Independent of any slot's "active"
        # state (unlike IntexScheduleDuration above), so it's always settable.
        entities.append(IntexPumpQuickRunHoursNumber(entry, pump_id))

    # Pool volume for the salt advisor — editable right on the device page.
    if data.salt is not None and salt_id is not None:
        entities.append(IntexPoolVolumeNumber(entry, salt_id))

    # Software calibration offsets (drift bridge between app calibrations).
    sensor_id = device_id_for(entry, DEVICE_SENSOR)
    if data.sensor is not None and sensor_id is not None:
        entities.append(IntexCalibrationOffsetNumber(entry, sensor_id, "ph"))
        entities.append(IntexCalibrationOffsetNumber(entry, sensor_id, "orp"))
        # Manual water-test inputs feeding the LSI / water-balance sensors.
        for parameter, maximum, step in _CHEMISTRY_INPUTS:
            entities.append(
                IntexChemistryInputNumber(entry, sensor_id, parameter, maximum, step)
            )

    async_add_entities(entities)


# (options key, max ppm, step) — TA/CH are required for LSI; CYA/TDS optional.
_CHEMISTRY_INPUTS = (
    (CONF_TOTAL_ALKALINITY, 400, 5),
    (CONF_CALCIUM_HARDNESS, 1000, 5),
    (CONF_CYA, 300, 5),
    (CONF_TDS, 6000, 50),
)


class IntexChemistryInputNumber(NumberEntity):
    """A manual water-test result (ppm) feeding the LSI calculation.

    Update these after each strip/drop test; the LSI sensor recomputes live.
    Stored in the entry options (0 = not measured/unknown).
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_should_poll = False

    def __init__(
        self, entry: IntexPoolConfigEntry, device_id: str, parameter: str,
        maximum: int, step: int,
    ) -> None:
        self._entry = entry
        self._parameter = parameter
        self._attr_translation_key = parameter
        self._attr_unique_id = f"{device_id}_{parameter}"
        self._attr_device_info = device_info_for(DEVICE_SENSOR, device_id)
        self._attr_native_max_value = maximum
        self._attr_native_step = step

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
        try:
            return float(self._entry.options.get(self._parameter, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    async def async_set_native_value(self, value: float) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, self._parameter: int(value)},
        )
        async_dispatcher_send(
            self.hass, SIGNAL_OPTIONS_UPDATED.format(self._entry.entry_id)
        )
        self.async_write_ha_state()


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


class IntexPumpQuickRunHoursNumber(NumberEntity):
    """Desired duration (hours) for the pump's next Quick Run.

    Read by ``IntexPumpQuickRunButton`` (button.py) when pressed. Stored in
    entry options (same pattern as ``IntexPoolVolumeNumber`` above) rather
    than slot-bound like ``IntexScheduleDuration``, so it's settable at any
    time — not only while a run happens to be active.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "quick_run_hours"
    # No entity_category (unlike the other Config-style numbers in this file):
    # this is the parameter you set right before pressing Quick Run, part of
    # the primary interaction, not a background setting — it needs to show up
    # in the device page's main Controls section next to the button, not get
    # split off into a separate Configuration section.
    # 1, not 0: a 0-hour run isn't a meaningful request (there's nothing for
    # Quick Run to do), so it's excluded from the range entirely rather than
    # accepted and silently coerced to the default (see native_value below —
    # `stored or DEFAULT` used to turn an explicit, legal 0 into 2 the moment
    # this min allowed it).
    _attr_native_min_value = 1
    _attr_native_max_value = 72
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(self, entry: IntexPoolConfigEntry, device_id: str) -> None:
        self._entry = entry
        self._attr_unique_id = f"{device_id}_quick_run_hours"
        self._attr_device_info = device_info_for(DEVICE_PUMP, device_id)

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
        # Explicit None-check, NOT `stored or DEFAULT` — with min now 1, a
        # stored 0 can't happen via this entity, but options are plain dict
        # values or (rare) an old/hand-edited entry could still hold one;
        # falling back to the default only when truly unset (None/missing)
        # keeps any real stored value, including one a future range change
        # might legally set to 0, from being silently overridden.
        raw = self._entry.options.get(CONF_QUICK_RUN_HOURS)
        if raw is None:
            return float(DEFAULT_QUICK_RUN_HOURS)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(DEFAULT_QUICK_RUN_HOURS)

    async def async_set_native_value(self, value: float) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_QUICK_RUN_HOURS: value},
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

    def __init__(self, coordinator, device_id: str, index: int, device: str = DEVICE_SALT) -> None:
        super().__init__(coordinator)
        self._index = index
        # Slot 0 is the Boost cycle ON THE CHLORINATOR only — the pump's slot 0
        # is a regular timed slot (its app writes one-shots into any slot).
        if index == 0 and device == DEVICE_SALT:
            self._attr_translation_key = "boost_duration"
        else:
            self._attr_translation_key = "schedule_duration"
            self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_unique_id = f"{device_id}_schedule_{index + 1}_duration"
        meta = DEVICE_META[device]
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
