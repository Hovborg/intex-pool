"""The Intex Pool integration.

Sets up one coordinator per configured device (saltwater chlorinator over the
LAN, water sensor over the Tuya cloud, sand-filter pump over the LAN in Tuya
mode) and serves the bundled dashboard card so it auto-loads on install.
A non-Tuya pump (any brand) is handled in "entity" mode: it creates no
coordinator here — its existing HA entities are shown by the card.
"""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import calibration, decode
from . import schedule as schedule_mod
from . import tuya
from .const import (
    CONF_CLOUD_INTERVAL,
    CONF_LOCAL_INTERVAL,
    CONF_PUMP_MODE,
    DEFAULT_CLOUD_INTERVAL,
    DEFAULT_LOCAL_INTERVAL,
    DEFAULT_SCHEDULE_INTERVAL,
    DEVICE_PUMP,
    DEVICE_SALT,
    DEVICE_SENSOR,
    DOMAIN,
    PLATFORMS,
    PUMP_MODE_TUYA,
    VERSION_CANDIDATES,
)
from .coordinator import (
    clear_auth_failures,
    PumpCoordinator,
    SaltCoordinator,
    ScheduleCoordinator,
    SensorCoordinator,
)
from .issues import async_setup_issue_listeners
from .models import IntexPoolConfigEntry, IntexPoolData

SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_GET_SCHEDULE = "get_schedule"
SERVICE_CALIBRATE = "calibrate"
SERVICE_CLEAR_CALIBRATION = "clear_calibration"
GET_SCHEDULE_SCHEMA = vol.Schema({vol.Optional("config_entry_id"): str})
CALIBRATE_SCHEMA = vol.Schema(
    {
        vol.Required("parameter"): vol.In(["ph", "orp"]),
        vol.Required("reference_value"): vol.Coerce(float),
        vol.Optional("config_entry_id"): str,
    }
)
CLEAR_CALIBRATION_SCHEMA = vol.Schema({vol.Optional("config_entry_id"): str})
SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Optional("config_entry_id"): str,
        vol.Optional("clear"): bool,
        vol.Optional("enable"): bool,
        vol.Optional("hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Optional("minute"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
        # 72 h matches the schedule-duration number entity (and the longest
        # boost cycle in the manual); the raw byte could hold 255 but nothing
        # legitimate needs it.
        vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=0, max=72)),
        vol.Optional("month"): vol.All(vol.Coerce(int), vol.Range(min=0, max=12)),
        vol.Optional("date"): vol.All(vol.Coerce(int), vol.Range(min=0, max=31)),
        vol.Optional("days"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    }
)

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/intex_pool"
CARD_FILENAME = "intex-pool-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the service + the bundled dashboard card once per HA start."""
    # Registering in async_setup (not async_setup_entry) means a service call
    # without a loaded entry fails with a clear validation error instead of
    # "service not found" (quality-scale rule: action-setup).
    _register_services(hass)

    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    if not card.is_file():
        _LOGGER.debug("Dashboard card not bundled (%s) — skipping registration", card)
        return True
    path = f"{URL_BASE}/{CARD_FILENAME}"
    static_paths = [StaticPathConfig(path, str(card), False)]
    if (card_map := card.with_suffix(".js.map")).is_file():
        # Serve the source map next to the bundle so browser dev tools can
        # show readable stack traces from the minified card.
        static_paths.append(StaticPathConfig(f"{path}.map", str(card_map), False))
    try:
        await hass.http.async_register_static_paths(static_paths)
    except RuntimeError:
        # Already registered (e.g. integration reloaded) — harmless.
        pass
    # add_extra_js_url needs the frontend component to be set up first.
    if "frontend" in hass.config.components:
        # Cache-bust with the integration version so a HACS update serves the
        # new bundle instead of a stale cached one (no hard refresh needed).
        try:
            version = (await async_get_integration(hass, DOMAIN)).version
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not read integration version for cache-bust: %s", err)
            version = None
        url = f"{path}?v={version}" if version else path
        add_extra_js_url(hass, url)
        _LOGGER.debug("Registered Intex Pool card at %s", url)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> bool:
    """Migrate old config entries.

    v1 → v2: slot 0 is now the device's **Boost** cycle, which has no start time,
    so its ``time.…_schedule_1_start`` entity is no longer created. Remove any
    such orphan left behind by earlier versions so it doesn't linger forever as
    an "unavailable" entity.
    """
    if entry.version < 2:
        registry = er.async_get(hass)
        for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg.domain == "time" and reg.unique_id.endswith("_schedule_1_start"):
                registry.async_remove(reg.entity_id)
                _LOGGER.info("Removed orphaned boost start-time entity %s", reg.entity_id)
        hass.config_entries.async_update_entry(entry, version=2)
    return True


def _local_client(cfg: dict) -> tuple[tuya.LocalClient, bool]:
    """Build a LocalClient and whether protocol version must be auto-detected."""
    version = cfg.get("version")
    auto = not version
    client = tuya.LocalClient(
        cfg["device_id"], cfg["local_key"], cfg["host"],
        float(version) if version else VERSION_CANDIDATES[0],
    )
    return client, auto


async def _build_data(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> IntexPoolData:
    """Create the coordinators for whichever devices the entry configured."""
    data = IntexPoolData()
    local_interval = entry.options.get(CONF_LOCAL_INTERVAL, DEFAULT_LOCAL_INTERVAL)
    cloud_interval = entry.options.get(CONF_CLOUD_INTERVAL, DEFAULT_CLOUD_INTERVAL)

    if (salt := entry.data.get(DEVICE_SALT)):
        client, auto = _local_client(salt)
        data.salt = SaltCoordinator(hass, entry, client, "salt", local_interval, auto)

    cloud = None
    if (sensor := entry.data.get(DEVICE_SENSOR)):
        # The CloudClient constructor performs a blocking token fetch: a raw
        # network exception here must become not-ready (retry with backoff),
        # not an unhandled setup error that stays dead until a manual reload.
        try:
            cloud = await hass.async_add_executor_job(
                tuya.CloudClient, sensor["region"], sensor["access_id"], sensor["access_secret"]
            )
        except tuya.TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise ConfigEntryNotReady(
                f"Tuya cloud unreachable: {type(err).__name__}: {err}"
            ) from err
        data.sensor = SensorCoordinator(
            hass, entry, cloud, sensor["device_id"], cloud_interval
        )

    pump = entry.data.get(DEVICE_PUMP)
    if pump and pump.get(CONF_PUMP_MODE) == PUMP_MODE_TUYA:
        client, auto = _local_client(pump)
        data.pump = PumpCoordinator(hass, entry, client, "pump", local_interval, auto)

    # Saltwater schedule lives only in the cloud (skdl_salt). Needs the cloud
    # client (from the water sensor's creds) + a saltwater device.
    salt_cfg = entry.data.get(DEVICE_SALT)
    if data.salt is not None and cloud is not None and salt_cfg:
        data.schedule = ScheduleCoordinator(
            hass, entry, cloud, salt_cfg["device_id"], DEFAULT_SCHEDULE_INTERVAL
        )

    # The analyzer's own measurement-window schedule (skdl_orpph) — same
    # 7-slot blob format (live-verified), exposed read-only.
    if data.sensor is not None and cloud is not None and sensor:
        data.analyzer_schedule = ScheduleCoordinator(
            hass, entry, cloud, sensor["device_id"], DEFAULT_SCHEDULE_INTERVAL,
            code="skdl_orpph",
        )

    # The Tuya pump's internal timer program (skdl_filter) — same blob format
    # (live-verified via the shadow API 2026-07-02), exposed read-only for now.
    if data.pump is not None and cloud is not None and pump:
        data.pump_schedule = ScheduleCoordinator(
            hass, entry, cloud, pump["device_id"], DEFAULT_SCHEDULE_INTERVAL,
            code="skdl_filter",
        )

    return data


async def async_setup_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> bool:
    """Set up Intex Pool from a config entry."""
    data = await _build_data(hass, entry)
    entry.runtime_data = data

    # Independent devices: refresh each but don't let one flaky device (e.g. a
    # sleeping sensor or a chlorinator momentarily polled by another client)
    # block the whole entry. Each coordinator recovers on its own interval.
    # A bad key surfaces as ConfigEntryAuthFailed from the coordinator, which
    # auto-starts a reauth flow.
    coordinators = [
        c
        for c in (data.salt, data.sensor, data.pump, data.schedule,
                  data.analyzer_schedule, data.pump_schedule)
        if c is not None
    ]
    for coordinator in coordinators:
        await coordinator.async_refresh()
    # If every configured device failed its first poll, report not-ready so HA
    # retries setup with backoff (instead of loading with all entities dead).
    if coordinators and not any(c.last_update_success for c in coordinators):
        raise ConfigEntryNotReady("No Intex Pool device could be reached")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_issue_listeners(hass, entry)
    return True


def _entry_for_call(
    hass: HomeAssistant, call: ServiceCall, has_target, error_key: str
) -> IntexPoolConfigEntry:
    """Resolve the target loaded entry for a service call.

    *has_target* is a predicate on the entry's runtime data selecting entries
    that can actually serve the call (e.g. has a schedule / has the sensor).
    """
    entry_id = call.data.get("config_entry_id")
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_found"
            )
        entries = [entry]
    for entry in entries:
        if entry.state is not ConfigEntryState.LOADED:
            continue
        data: IntexPoolData | None = getattr(entry, "runtime_data", None)
        if data and has_target(data):
            return entry
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key=error_key)


def _data_for_call(
    hass: HomeAssistant, call: ServiceCall, *, writable: bool = False
) -> IntexPoolData:
    """Resolve the target entry's runtime data for a schedule service call.

    ``writable=True`` (set_schedule) requires the saltwater schedule — an entry
    with only the read-only analyzer schedule must not be selected, or a
    multi-entry setup gets a bogus "no_schedule" error while a writable entry
    exists further down the list.
    """
    def predicate(d: IntexPoolData) -> bool:
        if writable:
            return d.schedule is not None
        return (d.schedule is not None or d.analyzer_schedule is not None
                or d.pump_schedule is not None)

    entry = _entry_for_call(hass, call, predicate, "no_schedule")
    return entry.runtime_data


def _serialize_slots(coordinator) -> dict | None:
    """Decoded slot table for service responses (JSON-serializable)."""
    if coordinator is None:
        return None
    data = coordinator.data or {}
    slots = data.get("slots") or schedule_mod.decode_schedules("")
    return {
        "raw": data.get("raw"),
        "slots": [
            {
                **{k: s.get(k) for k in schedule_mod.FIELDS[:7]},
                "active": bool(s.get("active")),
                "mode": schedule_mod.mode_of(s) if s.get("active") else None,
                "summary": schedule_mod.summarize(s) if s.get("active") else None,
            }
            for s in slots
        ],
    }


def _register_services(hass: HomeAssistant) -> None:
    """Register the schedule services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        return

    async def _set_schedule(call: ServiceCall) -> ServiceResponse:
        data = _data_for_call(hass, call, writable=True)
        coordinator = data.schedule
        if coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_schedule"
            )
        slots = (coordinator.data or {}).get("slots") or schedule_mod.decode_schedules("")
        new = schedule_mod.set_slot(
            slots, call.data["slot"],
            on=call.data.get("enable"), hour=call.data.get("hour"),
            minute=call.data.get("minute"), duration=call.data.get("duration"),
            month=call.data.get("month"), date=call.data.get("date"),
            days=call.data.get("days"), clear=call.data.get("clear", False),
        )
        await coordinator.async_write_slots(new)
        if call.return_response:
            return _serialize_slots(coordinator)
        return None

    async def _get_schedule(call: ServiceCall) -> ServiceResponse:
        data = _data_for_call(hass, call)
        return {
            "saltwater": _serialize_slots(data.schedule),
            "analyzer": _serialize_slots(data.analyzer_schedule),
            "pump": _serialize_slots(data.pump_schedule),
        }

    async def _calibrate(call: ServiceCall) -> ServiceResponse:
        entry = _entry_for_call(
            hass, call, lambda d: d.sensor is not None, "no_sensor"
        )
        sensor = entry.runtime_data.sensor
        if not sensor.last_update_success:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="sensor_unavailable"
            )
        props = sensor.data or {}
        parameter = call.data["parameter"]
        reference = float(call.data["reference_value"])
        if parameter == "ph":
            current = decode.scaled(props.get("PH_Number"), 0.01)
            max_offset, deadband, digits = (
                calibration.PH_MAX_OFFSET, calibration.PH_DEADBAND, 2,
            )
        else:
            current = props.get("ORP_Number")
            max_offset, deadband, digits = (
                calibration.ORP_MAX_OFFSET, calibration.ORP_DEADBAND, 0,
            )
        try:
            current = float(current)
        except (TypeError, ValueError):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_reading"
            ) from None
        offset = round(reference - current, digits)
        if abs(offset) < deadband:
            # Below the device's resolving power — the probe agrees with the
            # reference; clear any stored offset instead of storing noise.
            offset = 0.0
        if abs(offset) > max_offset:
            # That much error is clean/recalibrate/replace territory — a
            # software offset would hide a real problem.
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="offset_too_large",
                translation_placeholders={
                    "offset": str(offset), "max": str(max_offset), "parameter": parameter,
                },
            )
        calibration.async_store_calibration(
            hass, entry, {f"{parameter}_offset": offset},
            device_coeffs={
                "ph": props.get("ph_caliberate"),
                "orp": props.get("orp_caliberate"),
            },
        )
        if call.return_response:
            return {
                "parameter": parameter,
                "device_value": current,
                "reference_value": reference,
                "offset": offset,
            }
        return None

    async def _clear_calibration(call: ServiceCall) -> None:
        entry = _entry_for_call(
            hass, call, lambda d: d.sensor is not None, "no_sensor"
        )
        calibration.async_store_calibration(hass, entry, None)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULE, _set_schedule, schema=SET_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_SCHEDULE, _get_schedule, schema=GET_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CALIBRATE, _calibrate, schema=CALIBRATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_CALIBRATION, _clear_calibration,
        schema=CLEAR_CALIBRATION_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> bool:
    """Unload a config entry. The service stays registered (it validates entries)."""
    clear_auth_failures(hass, entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> None:
    """Purge this entry's repair issues when the entry is deleted.

    HA does not clean the issue registry up automatically — without this, an
    alarm/maintenance/stale issue active at removal time would linger in the
    Repairs dashboard forever, pointing at a deleted integration.
    """
    for prefix in ("salt_alarm", "sensor_maintenance", "sensor_stale"):
        ir.async_delete_issue(hass, DOMAIN, f"{prefix}_{entry.entry_id}")


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: IntexPoolConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow deleting devices that the entry no longer references.

    After a reconfigure repoints the entry to a replaced device (new Tuya id),
    the old device-registry entry would otherwise linger forever.
    """
    current: set[str] = {f"{entry.entry_id}_pump"}
    for device in (DEVICE_SALT, DEVICE_SENSOR, DEVICE_PUMP):
        if device_id := (entry.data.get(device) or {}).get("device_id"):
            current.add(device_id)
    return not any(
        domain == DOMAIN and identifier in current
        for domain, identifier in device_entry.identifiers
    )
