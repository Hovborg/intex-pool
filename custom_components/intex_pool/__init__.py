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
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

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
    PumpCoordinator,
    SaltCoordinator,
    ScheduleCoordinator,
    SensorCoordinator,
)
from .issues import async_setup_issue_listeners
from .models import IntexPoolConfigEntry, IntexPoolData

SERVICE_SET_SCHEDULE = "set_schedule"
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
        cloud = await hass.async_add_executor_job(
            tuya.CloudClient, sensor["region"], sensor["access_id"], sensor["access_secret"]
        )
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
        c for c in (data.salt, data.sensor, data.pump, data.schedule) if c is not None
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


def _schedule_coordinator_for_call(hass: HomeAssistant, call: ServiceCall):
    """Resolve the target ScheduleCoordinator for a set_schedule call."""
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
        if data and data.schedule is not None:
            return data.schedule
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="no_schedule"
    )


def _register_services(hass: HomeAssistant) -> None:
    """Register the schedule-editing service once."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        return

    async def _set_schedule(call: ServiceCall) -> None:
        coordinator = _schedule_coordinator_for_call(hass, call)
        slots = (coordinator.data or {}).get("slots") or schedule_mod.decode_schedules("")
        new = schedule_mod.set_slot(
            slots, call.data["slot"],
            on=call.data.get("enable"), hour=call.data.get("hour"),
            minute=call.data.get("minute"), duration=call.data.get("duration"),
            month=call.data.get("month"), date=call.data.get("date"),
            days=call.data.get("days"), clear=call.data.get("clear", False),
        )
        await coordinator.async_write_slots(new)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULE, _set_schedule, schema=SET_SCHEDULE_SCHEMA
    )


async def async_unload_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> bool:
    """Unload a config entry. The service stays registered (it validates entries)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
