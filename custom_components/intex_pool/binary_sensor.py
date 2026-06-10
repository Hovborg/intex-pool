"""Binary sensor platform (DP flags, connectivity, advisory roll-ups)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import decode
from .const import (
    BINARY_SENSORS,
    DEVICE_META,
    DEVICE_SALT,
    DEVICE_SENSOR,
    DOMAIN,
    MANUFACTURER,
    ORP_MIN_MV,
    PH_MAX,
    PH_MIN,
    SALT_MAX_PPM,
    SALT_MIN_PPM,
    STALE_AFTER_HOURS,
)
from .entity import IntexPoolEntity, coordinator_for, device_id_for, device_info_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 0

_DEVICES = ("salt", "sensor", "pump")

# Salt alarm tokens that do NOT need attention.
_ALARM_OK = {None, "normal", "e93"}


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

    # "Action required" roll-up: one problem flag spanning whatever exists.
    anchor = (
        (DEVICE_SALT, device_id_for(entry, DEVICE_SALT))
        if data.salt is not None and device_id_for(entry, DEVICE_SALT)
        else (DEVICE_SENSOR, device_id_for(entry, DEVICE_SENSOR))
        if data.sensor is not None and device_id_for(entry, DEVICE_SENSOR)
        else None
    )
    if anchor is not None:
        entities.append(IntexActionRequired(data, anchor[0], anchor[1]))

    async_add_entities(entities)


class IntexBinarySensor(IntexPoolEntity, BinarySensorEntity):
    """A read-only boolean DP flag (or value_fn-derived condition)."""

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self._raw)
        return decode.as_bool(self._raw)


class IntexActionRequired(BinarySensorEntity):
    """One PROBLEM flag rolling up everything that needs the owner's attention.

    Checks (only against data that actually exists): active salt alarm,
    maintenance indicator, pH outside the manual's 7.2-7.8 band, ORP below the
    650 mV sanitation floor, salinity outside the QS-series' 800-1800 ppm
    operating range, and stale analyzer data. The triggering reasons are
    exposed as the ``reasons`` attribute for automations/notifications.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "action_required"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, data, device: str, device_id: str) -> None:
        self._data = data
        self._attr_unique_id = f"{device_id}_action_required"
        self._attr_device_info = device_info_for(device, device_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for coordinator in (self._data.salt, self._data.sensor):
            if coordinator is not None:
                self.async_on_remove(
                    coordinator.async_add_listener(self._handle_update)
                )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    def _reasons(self) -> list[str]:
        reasons: list[str] = []
        salt = self._data.salt
        if salt is not None and salt.last_update_success:
            dps = salt.data or {}
            alarm = decode.normalize_alarm(dps.get("127"))
            if alarm not in _ALARM_OK:
                reasons.append(f"salt_alarm_{alarm}")
            salinity = _as_float(dps.get("109"))
            if salinity is not None and not SALT_MIN_PPM <= salinity <= SALT_MAX_PPM:
                reasons.append("salinity_low" if salinity < SALT_MIN_PPM else "salinity_high")
        sensor = self._data.sensor
        if sensor is not None and sensor.last_update_success:
            props = sensor.data or {}
            maint = decode.normalize_indicator(
                props.get("maintenance_indicator"), decode.MAINTENANCE_OPTIONS
            )
            if maint == "red":
                reasons.append("maintenance")
            ph = decode.scaled(props.get("PH_Number"), 0.01)
            if ph is not None and not PH_MIN <= ph <= PH_MAX:
                reasons.append("ph_low" if ph < PH_MIN else "ph_high")
            orp = _as_float(props.get("ORP_Number"))
            if orp is not None and orp < ORP_MIN_MV:
                reasons.append("orp_low")
            last = decode.last_measurement(props.get("_times"))
            if (
                last is not None
                and (dt_util.utcnow() - last).total_seconds() > STALE_AFTER_HOURS * 3600
            ):
                reasons.append("stale_measurement")
        return reasons

    @property
    def is_on(self) -> bool:
        return bool(self._reasons())

    @property
    def extra_state_attributes(self) -> dict:
        return {"reasons": self._reasons()}


def _as_float(raw) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


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
