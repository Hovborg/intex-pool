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

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import tuya
from .const import (
    CONF_CLOUD_INTERVAL,
    CONF_LOCAL_INTERVAL,
    CONF_PUMP_MODE,
    DEFAULT_CLOUD_INTERVAL,
    DEFAULT_LOCAL_INTERVAL,
    DEVICE_PUMP,
    DEVICE_SALT,
    DEVICE_SENSOR,
    DOMAIN,
    PLATFORMS,
    PUMP_MODE_TUYA,
    VERSION_CANDIDATES,
)
from .coordinator import PumpCoordinator, SaltCoordinator, SensorCoordinator
from .models import IntexPoolConfigEntry, IntexPoolData

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/intex_pool"
CARD_FILENAME = "intex-pool-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled dashboard card once per HA start (if built)."""
    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    if not card.is_file():
        _LOGGER.debug("Dashboard card not bundled (%s) — skipping registration", card)
        return True
    url = f"{URL_BASE}/{CARD_FILENAME}"
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(url, str(card), False)]
        )
    except RuntimeError:
        # Already registered (e.g. integration reloaded) — harmless.
        pass
    # add_extra_js_url needs the frontend component to be set up first.
    if "frontend" in hass.config.components:
        add_extra_js_url(hass, url)
        _LOGGER.debug("Registered Intex Pool card at %s", url)
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

    return data


async def async_setup_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> bool:
    """Set up Intex Pool from a config entry."""
    data = await _build_data(hass, entry)
    entry.runtime_data = data

    for coordinator in (data.salt, data.sensor, data.pump):
        if coordinator is not None:
            await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IntexPoolConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
