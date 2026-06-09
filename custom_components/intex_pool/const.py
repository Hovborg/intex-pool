"""Constants and entity descriptor tables for the Intex Pool integration.

Descriptor tables are the single source of truth for every entity. Each
platform module builds its entities by filtering these tables by the active
device type. DP numbers / property codes, units, scaling and decoders are
ported from ``01-drift/13-pool-kontrol`` (config.json + manuals/REFERENCE.md),
live-verified 2026-06-07.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)

from . import decode

DOMAIN = "intex_pool"

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.TIME,
]

# --- device types ---
DEVICE_SALT = "salt"
DEVICE_SENSOR = "sensor"
DEVICE_PUMP = "pump"

# --- config-entry keys ---
CONF_HAS_SALT = "has_salt"
CONF_HAS_SENSOR = "has_sensor"
CONF_HAS_PUMP = "has_pump"
CONF_REGION = "region"
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DEVICE_ID = "device_id"
CONF_LOCAL_KEY = "local_key"
CONF_HOST = "host"
CONF_VERSION = "version"
CONF_PUMP_MODE = "pump_mode"          # "tuya" | "entity"
CONF_PUMP_SWITCH = "pump_switch"      # entity_id (entity mode)
CONF_PUMP_POWER = "pump_power"        # entity_id or DP (optional)
CONF_PUMP_ENERGY = "pump_energy"
CONF_PUMP_ON_DP = "pump_on_dp"        # DP string for tuya pump on/off
CONF_LOCAL_INTERVAL = "local_interval"
CONF_CLOUD_INTERVAL = "cloud_interval"

PUMP_MODE_TUYA = "tuya"
PUMP_MODE_ENTITY = "entity"

DEFAULT_REGION = "eu"
DEFAULT_LOCAL_INTERVAL = 15
DEFAULT_CLOUD_INTERVAL = 120
DEFAULT_SCHEDULE_INTERVAL = 600  # schedules change rarely; poll the cloud blob slowly
DEFAULT_PUMP_ON_DP = "1"

VERSION_CANDIDATES = [3.4, 3.5, 3.3, 3.1]

MANUFACTURER = "Intex / AGP"
DEVICE_META: dict[str, dict[str, str]] = {
    DEVICE_SALT: {"name": "Saltwater system", "model": "QS-series chlorinator"},
    DEVICE_SENSOR: {"name": "Water sensor", "model": "Water analyzer (WA510)"},
    DEVICE_PUMP: {"name": "Sand filter pump", "model": "Pump"},
}


# --------------------------------------------------------------------------
# Descriptor dataclasses (each adds device + source to the HA description)
# --------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class IntexSensorDescription(SensorEntityDescription):
    device: str
    source: str
    scale: float | None = None
    value_fn: Callable[[Any], Any] | None = None


@dataclass(frozen=True, kw_only=True)
class IntexBinaryDescription(BinarySensorEntityDescription):
    device: str
    source: str


@dataclass(frozen=True, kw_only=True)
class IntexSwitchDescription(SwitchEntityDescription):
    device: str
    source: str


@dataclass(frozen=True, kw_only=True)
class IntexSelectDescription(SelectEntityDescription):
    device: str
    source: str
    value_map: dict[Any, str] = field(default_factory=dict)  # raw DP value -> option token


@dataclass(frozen=True, kw_only=True)
class IntexNumberDescription(NumberEntityDescription):
    device: str
    source: str
    scale: float | None = None  # display = raw * scale ; raw = round(value / scale)


@dataclass(frozen=True, kw_only=True)
class IntexButtonDescription(ButtonEntityDescription):
    device: str
    source: str


# --------------------------------------------------------------------------
# SENSORS
# --------------------------------------------------------------------------
SENSORS: tuple[IntexSensorDescription, ...] = (
    # Saltwater (local DPs)
    IntexSensorDescription(
        key="salinity", translation_key="salinity", device=DEVICE_SALT, source="109",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:shaker-outline",
    ),
    IntexSensorDescription(
        key="salt_water_temp", translation_key="water_temp", device=DEVICE_SALT, source="111",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
    ),
    IntexSensorDescription(
        key="cell_runtime", translation_key="cell_runtime", device=DEVICE_SALT, source="105",
        native_unit_of_measurement=UnitOfTime.HOURS, state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:timer-cog-outline",
    ),
    IntexSensorDescription(
        key="time_remaining", translation_key="time_remaining", device=DEVICE_SALT, source="110",
        native_unit_of_measurement=UnitOfTime.HOURS, state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-sand",
    ),
    IntexSensorDescription(
        key="status", translation_key="status", device=DEVICE_SALT, source="125",
        device_class=SensorDeviceClass.ENUM, options=decode.STATUS_OPTIONS,
        value_fn=decode.normalize_status, icon="mdi:state-machine",
    ),
    IntexSensorDescription(
        key="alarm", translation_key="alarm", device=DEVICE_SALT, source="127",
        device_class=SensorDeviceClass.ENUM, options=decode.ALARM_OPTIONS,
        value_fn=decode.normalize_alarm, icon="mdi:alert-circle-outline",
    ),
    IntexSensorDescription(
        key="salt_error", translation_key="error_code", device=DEVICE_SALT, source="114",
        device_class=SensorDeviceClass.ENUM, options=decode.ERROR_OPTIONS,
        value_fn=decode.normalize_error, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-octagon-outline",
    ),
    # Water sensor (cloud properties)
    IntexSensorDescription(
        key="ph", translation_key="ph", device=DEVICE_SENSOR, source="PH_Number",
        scale=0.01, state_class=SensorStateClass.MEASUREMENT, icon="mdi:ph",
    ),
    IntexSensorDescription(
        key="orp", translation_key="orp", device=DEVICE_SENSOR, source="ORP_Number",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:flash",
    ),
    IntexSensorDescription(
        key="free_chlorine", translation_key="free_chlorine", device=DEVICE_SENSOR, source="fc_number",
        scale=0.01, native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:test-tube",
    ),
    IntexSensorDescription(
        key="sensor_water_temp", translation_key="water_temp", device=DEVICE_SENSOR, source="water_tempture_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
    ),
    IntexSensorDescription(
        key="battery", translation_key="battery", device=DEVICE_SENSOR, source="battery_capacity",
        native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="ph_indicator", translation_key="ph_indicator", device=DEVICE_SENSOR, source="ph_indcator",
        device_class=SensorDeviceClass.ENUM, options=decode.PH_INDICATOR_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.PH_INDICATOR_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:alpha-p-circle",
    ),
    IntexSensorDescription(
        key="orp_indicator", translation_key="orp_indicator", device=DEVICE_SENSOR, source="orp_indicator",
        device_class=SensorDeviceClass.ENUM, options=decode.ORP_INDICATOR_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.ORP_INDICATOR_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:flash-alert",
    ),
    IntexSensorDescription(
        key="chlorine_indicator", translation_key="chlorine_indicator", device=DEVICE_SENSOR, source="fc_indicator",
        device_class=SensorDeviceClass.ENUM, options=decode.FC_INDICATOR_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.FC_INDICATOR_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:test-tube",
    ),
    IntexSensorDescription(
        key="maintenance", translation_key="maintenance", device=DEVICE_SENSOR, source="maintenance_indicator",
        device_class=SensorDeviceClass.ENUM, options=decode.MAINTENANCE_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.MAINTENANCE_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:wrench",
    ),
    IntexSensorDescription(
        key="sensor_error", translation_key="error_code", device=DEVICE_SENSOR, source="error_code",
        device_class=SensorDeviceClass.ENUM, options=decode.ERROR_OPTIONS,
        value_fn=decode.normalize_error, entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-octagon-outline",
    ),
    # NOTE: a Tuya pump only exposes the on/off switch + connectivity here.
    # Pump power/energy/temperature come from the user's *existing* HA entities
    # (Shelly, Zigbee relay, any brand) linked in pump "entity" mode and shown
    # by the dashboard card — so non-Intex pumps work alongside the rest.
)

# --------------------------------------------------------------------------
# BINARY SENSORS  (connectivity is added programmatically per device)
# --------------------------------------------------------------------------
BINARY_SENSORS: tuple[IntexBinaryDescription, ...] = (
    IntexBinaryDescription(
        key="mesh", translation_key="mesh", device=DEVICE_SALT, source="119",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:access-point-network",
    ),
    IntexBinaryDescription(
        key="pump_mesh", translation_key="pump_mesh", device=DEVICE_SALT, source="126",
        entity_category=EntityCategory.DIAGNOSTIC, icon="mdi:water-pump",
    ),
)

# --------------------------------------------------------------------------
# SWITCHES
# --------------------------------------------------------------------------
SWITCHES: tuple[IntexSwitchDescription, ...] = (
    IntexSwitchDescription(
        key="power", translation_key="power", device=DEVICE_SALT, source="104", icon="mdi:power",
    ),
    IntexSwitchDescription(
        key="chlorination", translation_key="chlorination", device=DEVICE_SALT, source="103", icon="mdi:flash",
    ),
    IntexSwitchDescription(
        key="pump", translation_key="pump", device=DEVICE_PUMP, source=CONF_PUMP_ON_DP, icon="mdi:water-pump",
    ),
)

# --------------------------------------------------------------------------
# SELECTS  (native upgrade over raw bridge sensors)
# --------------------------------------------------------------------------
SELECTS: tuple[IntexSelectDescription, ...] = (
    IntexSelectDescription(
        key="self_clean", translation_key="self_clean", device=DEVICE_SALT, source="108",
        value_map={2: "2", 4: "4", 6: "6", 10: "10"}, icon="mdi:broom",
        entity_category=EntityCategory.CONFIG,
    ),
    IntexSelectDescription(
        key="temp_unit", translation_key="temp_unit", device=DEVICE_SALT, source="124",
        value_map={False: "c", True: "f"}, icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
    ),
)

# --------------------------------------------------------------------------
# NUMBERS (writable cloud targets)
# --------------------------------------------------------------------------
NUMBERS: tuple[IntexNumberDescription, ...] = (
    IntexNumberDescription(
        key="ph_target", translation_key="ph_target", device=DEVICE_SENSOR, source="ph_set",
        scale=0.01, native_min_value=7.2, native_max_value=7.8, native_step=0.1,
        mode=NumberMode.SLIDER, icon="mdi:ph", entity_category=EntityCategory.CONFIG,
    ),
    IntexNumberDescription(
        key="orp_target", translation_key="orp_target", device=DEVICE_SENSOR, source="orp_set",
        native_min_value=650, native_max_value=750, native_step=10,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        mode=NumberMode.SLIDER, icon="mdi:flash", entity_category=EntityCategory.CONFIG,
    ),
)

# --------------------------------------------------------------------------
# BUTTONS
# --------------------------------------------------------------------------
BUTTONS: tuple[IntexButtonDescription, ...] = (
    IntexButtonDescription(
        key="refresh", translation_key="refresh", device=DEVICE_SENSOR, source="refresh_switch",
        icon="mdi:refresh",
    ),
)
