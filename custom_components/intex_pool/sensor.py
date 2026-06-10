"""Sensor platform."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode, schedule
from .const import (
    CONF_POOL_VOLUME,
    CONF_SALT_TARGET,
    DEFAULT_SALT_TARGET,
    DEVICE_SALT,
    DEVICE_SENSOR,
    SALT_MAX_PPM,
    SENSORS,
)
from .entity import IntexPoolEntity, coordinator_for, device_id_for, device_info_for
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

    # Salt dose advisor — needs the salt device + a configured pool volume.
    volume = entry.options.get(CONF_POOL_VOLUME, 0)
    if data.salt is not None and salt_id is not None and volume:
        target = entry.options.get(CONF_SALT_TARGET, DEFAULT_SALT_TARGET)
        entities.append(IntexSaltDoseSensor(data.salt, salt_id, int(volume), int(target)))

    async_add_entities(entities)


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
    """A read-only sensor backed by a DP / cloud property."""

    @property
    def native_value(self) -> StateType | datetime:
        raw = self._raw
        desc = self.entity_description
        if desc.value_fn is not None:
            return desc.value_fn(raw)
        if desc.scale is not None:
            return decode.scaled(raw, desc.scale)
        return raw


class IntexSaltDoseSensor(CoordinatorEntity, SensorEntity):
    """Advisory: kg of salt to add to reach the target salinity.

    kg = litres x (target ppm - current ppm) / 1e6 — the standard pool formula
    (1 ppm = 1 mg/L), matching the QS-series manual's own dosing examples.
    Above the manual's 1800 ppm max the advice flips to dilution (drain %
    straight from the manual's E92 table). Advisory only — never actuates.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "salt_to_add"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, device_id: str, volume_l: int, target_ppm: int) -> None:
        super().__init__(coordinator)
        self._volume = volume_l
        self._target = target_ppm
        self._attr_unique_id = f"{device_id}_salt_to_add"
        self._attr_device_info = device_info_for(DEVICE_SALT, device_id)

    def _salinity(self) -> float | None:
        raw = (self.coordinator.data or {}).get("109")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def native_value(self) -> float | None:
        salinity = self._salinity()
        if salinity is None:
            return None
        return round(max(0.0, self._volume * (self._target - salinity) / 1_000_000), 2)

    @property
    def extra_state_attributes(self) -> dict:
        salinity = self._salinity()
        attrs: dict = {
            "salinity_ppm": salinity,
            "target_ppm": self._target,
            "pool_volume_l": self._volume,
            "status": None,
            "drain_refill_pct": None,
        }
        if salinity is None:
            return attrs
        if salinity > SALT_MAX_PPM:
            attrs["status"] = "dilute"
            attrs["drain_refill_pct"] = next(
                (pct for limit, pct in _DILUTE_TABLE if salinity <= limit), 70
            )
        elif salinity < self._target:
            attrs["status"] = "add_salt"
        else:
            attrs["status"] = "ok"
        return attrs
