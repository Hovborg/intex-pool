"""Sensor platform."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import calibration, chemistry, decode, schedule
from .const import (
    CONF_CALCIUM_HARDNESS,
    CONF_CYA,
    CONF_SALT_TARGET,
    CONF_TDS,
    CONF_TOTAL_ALKALINITY,
    DEFAULT_SALT_TARGET,
    DEVICE_PUMP,
    DEVICE_SALT,
    DEVICE_SENSOR,
    SALT_MAX_PPM,
    SENSORS,
    SIGNAL_OPTIONS_UPDATED,
)
from .entity import (
    IntexPoolEntity,
    coordinator_for,
    device_id_for,
    device_info_for,
    pool_volume_liters,
)
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 0

# E92 dilution table from the QS-series manual (§6): salinity -> drain+refill %.
_DILUTE_TABLE = ((2200, 40), (2600, 50), (3200, 60), (4000, 70))


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
        entities.append(IntexScheduleSensor(data.schedule, DEVICE_SALT, salt_id, "schedules"))

    sensor_id = device_id_for(entry, DEVICE_SENSOR)
    if data.analyzer_schedule is not None and sensor_id is not None:
        entities.append(
            IntexScheduleSensor(
                data.analyzer_schedule, DEVICE_SENSOR, sensor_id, "analyzer_schedules"
            )
        )

    pump_id = device_id_for(entry, DEVICE_PUMP)
    if data.pump_schedule is not None and pump_id is not None:
        entities.append(
            IntexScheduleSensor(data.pump_schedule, DEVICE_PUMP, pump_id, "schedules")
        )

    # Salt dose advisor — always created with the salt device; it reads the
    # pool volume/target live from the entry options, so adjusting them (via
    # the Pool volume entity or ⋮ → Configure) needs no reload.
    if data.salt is not None and salt_id is not None:
        entities.append(IntexSaltDoseSensor(data.salt, salt_id, entry))

    # LSI / water balance — needs the analyzer (live pH + temp) plus the
    # manual test-input entities (TA/CH, optionally CYA/TDS).
    if data.sensor is not None and sensor_id is not None:
        entities.append(IntexLsiSensor(entry, data, sensor_id))
        entities.append(IntexWaterBalanceSensor(entry, data, sensor_id))

    async_add_entities(entities)


class _LsiBase(SensorEntity):
    """Shared wiring for the LSI-derived sensors.

    Recomputes on analyzer updates (pH/temp), on salt updates (live salinity
    is the TDS fallback for SWG pools) and on option changes (test inputs,
    calibration offsets).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: IntexPoolConfigEntry, data, device_id: str) -> None:
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{device_id}_{self._attr_translation_key}"
        self._attr_device_info = device_info_for(DEVICE_SENSOR, device_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for coordinator in (self._data.sensor, self._data.salt):
            if coordinator is not None:
                self.async_on_remove(coordinator.async_add_listener(self._refresh))
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

    def _option(self, key: str) -> float:
        try:
            return float(self._entry.options.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def _inputs(self) -> dict | None:
        """Collect the LSI inputs, or None when they can't produce an LSI."""
        sensor = self._data.sensor
        if sensor is None or not sensor.last_update_success:
            return None
        props = sensor.data or {}
        ph = decode.scaled(props.get("PH_Number"), 0.01)
        try:
            temp_c = float(props.get("water_tempture_c"))
        except (TypeError, ValueError):
            return None
        if ph is None:
            return None
        ph += calibration.ph_offset(self._entry)  # judge the corrected value
        ta = self._option(CONF_TOTAL_ALKALINITY)
        ch = self._option(CONF_CALCIUM_HARDNESS)
        cya = self._option(CONF_CYA)
        tds = self._option(CONF_TDS)
        tds_source = "manual"
        if not tds and self._data.salt is not None and self._data.salt.last_update_success:
            # SWG pools: salt dominates TDS — use the live salinity reading.
            try:
                tds = float((self._data.salt.data or {}).get("109") or 0)
                tds_source = "salinity"
            except (TypeError, ValueError):
                tds = 0.0
        return {
            "ph": round(ph, 2), "temp_c": temp_c, "ta": ta, "ch": ch,
            "cya": cya, "tds": tds, "tds_source": tds_source if tds else None,
        }

    def _lsi(self) -> tuple[float | None, dict]:
        inputs = self._inputs()
        if inputs is None:
            return None, {}
        value = chemistry.lsi(
            inputs["ph"], inputs["temp_c"], inputs["ta"], inputs["ch"],
            cya=inputs["cya"], tds=inputs["tds"],
        )
        return value, inputs


class IntexLsiSensor(_LsiBase):
    """Langelier Saturation Index from live pH/temp + manual test inputs."""

    _attr_translation_key = "lsi"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        return self._lsi()[0]

    @property
    def extra_state_attributes(self) -> dict:
        value, inputs = self._lsi()
        attrs = {"water_balance": chemistry.classify(value), **inputs}
        if not inputs.get("ta") or not inputs.get("ch"):
            attrs["status"] = "set_test_inputs"  # TA + CH entities must be set
        return attrs


class IntexWaterBalanceSensor(_LsiBase):
    """Interpretation of the LSI (corrosive / balanced / scale-forming)."""

    _attr_translation_key = "water_balance"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = chemistry.WATER_BALANCE_OPTIONS

    @property
    def native_value(self) -> str | None:
        return chemistry.classify(self._lsi()[0])


class IntexScheduleSensor(CoordinatorEntity, SensorEntity):
    """Read-only view of a device's schedule slots (count + details)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device: str, device_id: str, translation_key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{device_id}_{translation_key}"
        self._attr_device_info = device_info_for(device, device_id)

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


class IntexSensor(IntexPoolEntity, SensorEntity):
    """A read-only sensor backed by a DP / cloud property.

    pH/ORP apply the user's software calibration offset (see calibration.py);
    the uncorrected reading stays available as the ``raw_value`` attribute.
    """

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.entity_description.calibration:
            # Refresh immediately when offsets change (service / number entity).
            entry = self.coordinator.config_entry
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_OPTIONS_UPDATED.format(entry.entry_id),
                    self._on_options_updated,
                )
            )

    @callback
    def _on_options_updated(self) -> None:
        self.async_write_ha_state()

    def _uncalibrated(self) -> StateType | datetime:
        raw = self._raw
        desc = self.entity_description
        if desc.value_fn is not None:
            return desc.value_fn(raw)
        if desc.scale is not None:
            return decode.scaled(raw, desc.scale)
        return raw

    @property
    def native_value(self) -> StateType | datetime:
        value = self._uncalibrated()
        param = self.entity_description.calibration
        if param and isinstance(value, (int, float)):
            offset = calibration.offset_for(self.coordinator.config_entry, param)
            if offset:
                return round(value + offset, 2)
        return value

    @property
    def extra_state_attributes(self) -> dict | None:
        param = self.entity_description.calibration
        if not param:
            return None
        entry = self.coordinator.config_entry
        offset = calibration.offset_for(entry, param)
        return {
            "raw_value": self._uncalibrated(),
            "calibration_offset": offset or 0,
            "calibrated_at": calibration.get_calibration(entry).get("calibrated_at"),
        }


class IntexSaltDoseSensor(CoordinatorEntity, SensorEntity):
    """Advisory: kg of salt to add to reach the target salinity.

    kg = litres x (target ppm - current ppm) / 1e6 — the standard pool formula
    (1 ppm = 1 mg/L), matching the QS-series manual's own dosing examples.
    Above the manual's 1800 ppm max the advice flips to dilution (drain %
    straight from the manual's E92 table). Advisory only — never actuates.

    Pool volume/unit/target are read live from the entry options (set them via
    the Pool volume / Volume unit / target entities or ⋮ → Configure).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "salt_to_add"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, device_id: str, entry: IntexPoolConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{device_id}_salt_to_add"
        self._attr_device_info = device_info_for(DEVICE_SALT, device_id)

    def _salinity(self) -> float | None:
        raw = (self.coordinator.data or {}).get("109")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _target(self) -> int:
        return int(self._entry.options.get(CONF_SALT_TARGET, DEFAULT_SALT_TARGET))

    @property
    def native_value(self) -> float | None:
        salinity = self._salinity()
        volume_l = pool_volume_liters(self._entry)
        if salinity is None or volume_l <= 0:
            return None
        return round(max(0.0, volume_l * (self._target() - salinity) / 1_000_000), 2)

    @property
    def extra_state_attributes(self) -> dict:
        salinity = self._salinity()
        volume_l = pool_volume_liters(self._entry)
        attrs: dict = {
            "salinity_ppm": salinity,
            "target_ppm": self._target(),
            "pool_volume_l": round(volume_l) if volume_l else 0,
            "status": None,
            "drain_refill_pct": None,
        }
        if volume_l <= 0:
            attrs["status"] = "set_pool_volume"
            return attrs
        if salinity is None:
            return attrs
        if salinity > SALT_MAX_PPM:
            attrs["status"] = "dilute"
            attrs["drain_refill_pct"] = next(
                (pct for limit, pct in _DILUTE_TABLE if salinity <= limit), 70
            )
        elif salinity < self._target():
            attrs["status"] = "add_salt"
        else:
            attrs["status"] = "ok"
        return attrs
