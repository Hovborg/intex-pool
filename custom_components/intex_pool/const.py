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
    Platform.EVENT,
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
CONF_POOL_VOLUME = "pool_volume"      # in CONF_VOLUME_UNIT; 0/unset disables the advisor
CONF_SALT_TARGET = "salt_target"      # target salinity (ppm) for the advisor
CONF_VOLUME_UNIT = "volume_unit"      # "liter" | "gallon" (US)
CONF_CALIBRATION = "calibration"      # software offsets record (see calibration.py)
# Manual water-test inputs for the LSI / water-balance calculation (ppm).
CONF_TOTAL_ALKALINITY = "total_alkalinity"
CONF_CALCIUM_HARDNESS = "calcium_hardness"
CONF_CYA = "cya"
CONF_TDS = "tds"

VOLUME_UNIT_LITER = "liter"
VOLUME_UNIT_GALLON = "gallon"
GAL_TO_L = 3.785411784  # US liquid gallon

# Dispatcher signal (per entry) fired when options are updated programmatically
# by the config entities, so sibling entities refresh their displayed state.
SIGNAL_OPTIONS_UPDATED = "intex_pool_options_updated_{}"

PUMP_MODE_TUYA = "tuya"
PUMP_MODE_ENTITY = "entity"

DEFAULT_REGION = "eu"
DEFAULT_LOCAL_INTERVAL = 15
DEFAULT_CLOUD_INTERVAL = 120
DEFAULT_SCHEDULE_INTERVAL = 600  # schedules change rarely; poll the cloud blob slowly
DEFAULT_PUMP_ON_DP = "1"

# --- water-quality guidance (QS-series manual §6/§9 + industry ORP floor) ---
# Salinity: QS-series operating range 800-1800 ppm, optimum 950 ppm.
SALT_MIN_PPM = 800
SALT_MAX_PPM = 1800
DEFAULT_SALT_TARGET = 950
# pH ideal band per the Intex manual (7.2 min, 7.8 max).
PH_MIN = 7.2
PH_MAX = 7.8
# Industry sanitation floor for ORP (Pentair/chloramine guidance: >=650 mV).
ORP_MIN_MV = 650
# Below ~15 degC cold water stresses/wears the electrolysis cell (the device
# itself hard-errors at <10 degC with E03).
COLD_WATER_C = 15.0
# The electrolysis cell's runtime counter range in the thing model is
# 0-5000 h - treated as the rated cell life for the wear estimate
# (assumption: Intex does not document the cap's meaning).
CELL_RATED_HOURS = 5000
# The sleeping analyzer reports roughly hourly; older than this is stale.
STALE_AFTER_HOURS = 3

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
    # "ph" | "orp": user calibration offset is applied to this sensor's value.
    calibration: str | None = None


@dataclass(frozen=True, kw_only=True)
class IntexBinaryDescription(BinarySensorEntityDescription):
    device: str
    source: str
    value_fn: Callable[[Any], bool | None] | None = None  # raw -> is_on (default: as_bool)


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
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    IntexSensorDescription(
        key="salt_water_temp", translation_key="water_temp", device=DEVICE_SALT, source="111",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    IntexSensorDescription(
        key="cell_runtime", translation_key="cell_runtime", device=DEVICE_SALT, source="105",
        native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC, suggested_display_precision=0,
    ),
    # Electrolysis-cell wear estimate: runtime as % of the 0-5000 h counter
    # range (assumed rated life - see CELL_RATED_HOURS note above).
    IntexSensorDescription(
        key="cell_wear", translation_key="cell_wear", device=DEVICE_SALT, source="105",
        scale=100 / CELL_RATED_HOURS, native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC, suggested_display_precision=1,
    ),
    IntexSensorDescription(
        key="time_remaining", translation_key="time_remaining", device=DEVICE_SALT, source="110",
        native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
    ),
    IntexSensorDescription(
        key="status", translation_key="status", device=DEVICE_SALT, source="125",
        device_class=SensorDeviceClass.ENUM, options=decode.STATUS_OPTIONS,
        value_fn=decode.normalize_status,
    ),
    IntexSensorDescription(
        key="alarm", translation_key="alarm", device=DEVICE_SALT, source="127",
        device_class=SensorDeviceClass.ENUM, options=decode.ALARM_OPTIONS,
        value_fn=decode.normalize_alarm,
    ),
    IntexSensorDescription(
        key="salt_error", translation_key="error_code", device=DEVICE_SALT, source="114",
        device_class=SensorDeviceClass.ENUM, options=decode.ERROR_OPTIONS,
        value_fn=decode.normalize_error, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Water sensor (cloud properties)
    IntexSensorDescription(
        key="ph", translation_key="ph", device=DEVICE_SENSOR, source="PH_Number",
        scale=0.01, device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        calibration="ph",
    ),
    IntexSensorDescription(
        key="orp", translation_key="orp", device=DEVICE_SENSOR, source="ORP_Number",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
        calibration="orp",
    ),
    IntexSensorDescription(
        key="free_chlorine", translation_key="free_chlorine", device=DEVICE_SENSOR, source="fc_number",
        scale=0.01, native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
    ),
    IntexSensorDescription(
        key="sensor_water_temp", translation_key="water_temp", device=DEVICE_SENSOR, source="water_tempture_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    IntexSensorDescription(
        key="battery", translation_key="battery", device=DEVICE_SENSOR, source="battery_capacity",
        native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    IntexSensorDescription(
        key="ph_indicator", translation_key="ph_indicator", device=DEVICE_SENSOR, source="ph_indcator",
        device_class=SensorDeviceClass.ENUM, options=decode.PH_INDICATOR_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.PH_INDICATOR_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="orp_indicator", translation_key="orp_indicator", device=DEVICE_SENSOR, source="orp_indicator",
        device_class=SensorDeviceClass.ENUM, options=decode.ORP_INDICATOR_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.ORP_INDICATOR_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="orp_trend", translation_key="orp_trend", device=DEVICE_SENSOR, source="ORP_dif_Number",
        device_class=SensorDeviceClass.ENUM, options=decode.ORP_TREND_OPTIONS,
        value_fn=decode.normalize_orp_trend, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="chlorine_indicator", translation_key="chlorine_indicator", device=DEVICE_SENSOR, source="fc_indicator",
        device_class=SensorDeviceClass.ENUM, options=decode.FC_INDICATOR_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.FC_INDICATOR_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="maintenance", translation_key="maintenance", device=DEVICE_SENSOR, source="maintenance_indicator",
        device_class=SensorDeviceClass.ENUM, options=decode.MAINTENANCE_OPTIONS,
        value_fn=lambda r: decode.normalize_indicator(r, decode.MAINTENANCE_OPTIONS),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="sensor_error", translation_key="error_code", device=DEVICE_SENSOR, source="error_code",
        device_class=SensorDeviceClass.ENUM, options=decode.ERROR_OPTIONS,
        value_fn=decode.normalize_error, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexSensorDescription(
        key="last_measurement", translation_key="last_measurement", device=DEVICE_SENSOR,
        source="_times", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=decode.last_measurement, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Calibration coefficients (0-255). READ-ONLY on purpose: these are offset
    # coefficients the device manages itself during calibration — writing them
    # corrupts the user's calibration (live-verified in a pH-4.0 buffer). They
    # are diagnostics for support cases, disabled by default.
    IntexSensorDescription(
        key="ph_calibration", translation_key="ph_calibration", device=DEVICE_SENSOR,
        source="ph_caliberate", entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IntexSensorDescription(
        key="orp_calibration", translation_key="orp_calibration", device=DEVICE_SENSOR,
        source="orp_caliberate", entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IntexBinaryDescription(
        key="pump_mesh", translation_key="pump_mesh", device=DEVICE_SALT, source="126",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # The water sensor reports its own mesh/link flag. After re-pairing one
    # device the salt<->sensor link can dangle half-open — exactly here.
    IntexBinaryDescription(
        key="sensor_mesh", translation_key="mesh", device=DEVICE_SENSOR, source="mesh_indicator",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Cold-water guard: electrolysis below ~15 degC stresses the cell (the
    # device itself errors with E03 below 10 degC). Advisory only.
    IntexBinaryDescription(
        key="cold_water", translation_key="cold_water", device=DEVICE_SALT, source="111",
        device_class=BinarySensorDeviceClass.COLD,
        value_fn=lambda raw: None if raw is None else float(raw) < COLD_WATER_C,
    ),
)

# --------------------------------------------------------------------------
# SWITCHES
# --------------------------------------------------------------------------
SWITCHES: tuple[IntexSwitchDescription, ...] = (
    IntexSwitchDescription(
        key="power", translation_key="power", device=DEVICE_SALT, source="104",
    ),
    IntexSwitchDescription(
        key="chlorination", translation_key="chlorination", device=DEVICE_SALT, source="103",
    ),
    # DP102 "salt_switch2" (消毒#2) — the thing model's second disinfection
    # switch. Writable per the model, but its effect on the QS1600 Plus is
    # unverified on real hardware, so it ships disabled by default.
    IntexSwitchDescription(
        key="chlorination_2", translation_key="chlorination_2", device=DEVICE_SALT, source="102",
        entity_registry_enabled_default=False,
    ),
    # Cloud-written stabilizer (CYA) flag. Relevant because CYA skews ORP
    # readings (REFERENCE.md §9) — the device offers it as a writable bool.
    IntexSwitchDescription(
        key="stabilizer", translation_key="stabilizer", device=DEVICE_SENSOR, source="fc_sta_flg",
        entity_category=EntityCategory.CONFIG,
    ),
    # source placeholder is the SAFE default DP "1"; async_setup_entry replaces
    # it with the configured CONF_PUMP_ON_DP value for Tuya pumps.
    IntexSwitchDescription(
        key="pump", translation_key="pump", device=DEVICE_PUMP, source=DEFAULT_PUMP_ON_DP,
    ),
)

# --------------------------------------------------------------------------
# SELECTS  (native upgrade over raw bridge sensors)
# --------------------------------------------------------------------------
SELECTS: tuple[IntexSelectDescription, ...] = (
    IntexSelectDescription(
        key="self_clean", translation_key="self_clean", device=DEVICE_SALT, source="108",
        value_map={2: "2", 4: "4", 6: "6", 10: "10"},
        entity_category=EntityCategory.CONFIG,
    ),
    IntexSelectDescription(
        key="temp_unit", translation_key="temp_unit", device=DEVICE_SALT, source="124",
        # NOTE: on the real hardware DP124 is True for °C and False for °F
        # (inverse of the thing-model doc), verified against the live device.
        value_map={True: "c", False: "f"},
        entity_category=EntityCategory.CONFIG,
    ),
    # Water sensor (cloud properties, written via SensorCoordinator.async_issue)
    IntexSelectDescription(
        key="report_cadence", translation_key="report_cadence", device=DEVICE_SENSOR,
        source="report_number",
        # Thing-model enum (rw): {ORP,PH,FC}_{byweek,bymonth}.
        value_map={
            "ORP_byweek": "orp_weekly", "ORP_bymonth": "orp_monthly",
            "PH_byweek": "ph_weekly", "PH_bymonth": "ph_monthly",
            "FC_byweek": "fc_weekly", "FC_bymonth": "fc_monthly",
        },
        entity_category=EntityCategory.CONFIG,
    ),
    IntexSelectDescription(
        key="sensor_temp_unit", translation_key="temp_unit", device=DEVICE_SENSOR,
        source="fc_unit_change_switch",
        # Reuses the salt temp_unit polarity (True == °C, False == °F), which is
        # verified on the salt hardware. The thing-model doc lists 0=°C/1=°F for
        # this sensor property, so the sensor-side polarity could be inverted vs
        # salt — live-verify against the real sensor before trusting it.
        value_map={True: "c", False: "f"},
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
        mode=NumberMode.SLIDER, entity_category=EntityCategory.CONFIG,
    ),
    IntexNumberDescription(
        key="orp_target", translation_key="orp_target", device=DEVICE_SENSOR, source="orp_set",
        native_min_value=650, native_max_value=750, native_step=10,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        mode=NumberMode.SLIDER, entity_category=EntityCategory.CONFIG,
    ),
)

# --------------------------------------------------------------------------
# BUTTONS
# --------------------------------------------------------------------------
BUTTONS: tuple[IntexButtonDescription, ...] = (
    IntexButtonDescription(
        key="refresh", translation_key="refresh", device=DEVICE_SENSOR, source="refresh_switch",
    ),
    # Salt "re-test now": code `retest_switch` is local DP 107 (bool, wr) — forces
    # a fresh salt/temp measurement. Salt is a LOCAL device so the source is the
    # numeric DP (set_value addresses DPs by number), not the code name.
    IntexButtonDescription(
        key="retest", translation_key="retest", device=DEVICE_SALT, source="107",
    ),
)
