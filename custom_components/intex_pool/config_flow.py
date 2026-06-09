"""Config + options flow for Intex Pool.

Two setup paths:
* **Cloud auto-discovery (easy, default):** the user enters their Tuya IoT
  cloud credentials once; the integration lists their devices (with local keys)
  and LAN-scans for IPs, so the user just picks which devices are the pool gear
  — no manual key extraction, no IP typing.
* **Manual (fallback):** enter device id / local key / host by hand.

The pump can always be linked to an existing HA switch (any brand).
"""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import tuya
from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_CLOUD_INTERVAL,
    CONF_DEVICE_ID,
    CONF_HAS_PUMP,
    CONF_HAS_SALT,
    CONF_HAS_SENSOR,
    CONF_HOST,
    CONF_LOCAL_INTERVAL,
    CONF_LOCAL_KEY,
    CONF_PUMP_ENERGY,
    CONF_PUMP_MODE,
    CONF_PUMP_ON_DP,
    CONF_PUMP_POWER,
    CONF_PUMP_SWITCH,
    CONF_REGION,
    CONF_VERSION,
    DEFAULT_CLOUD_INTERVAL,
    DEFAULT_LOCAL_INTERVAL,
    DEFAULT_PUMP_ON_DP,
    DEFAULT_REGION,
    DEVICE_PUMP,
    DEVICE_SALT,
    DEVICE_SENSOR,
    DOMAIN,
    PUMP_MODE_ENTITY,
    PUMP_MODE_TUYA,
    VERSION_CANDIDATES,
)

_VERSION_OPTIONS = ["auto", "3.1", "3.3", "3.4", "3.5"]
_REGION_OPTIONS = ["eu", "us", "cn", "in"]
CONF_MANUAL = "manual"

STEP_USER = vol.Schema(
    {
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_REGION_OPTIONS)
        ),
        vol.Optional(CONF_ACCESS_ID, default=""): str,
        vol.Optional(CONF_ACCESS_SECRET, default=""): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_MANUAL, default=False): bool,
    }
)

STEP_MANUAL = vol.Schema(
    {
        vol.Required(CONF_HAS_SENSOR, default=False): bool,
        vol.Required(CONF_HAS_SALT, default=False): bool,
        vol.Required(CONF_HAS_PUMP, default=False): bool,
    }
)

STEP_SENSOR = vol.Schema(
    {
        vol.Required(CONF_REGION, default=DEFAULT_REGION): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_REGION_OPTIONS)
        ),
        vol.Required(CONF_ACCESS_ID): str,
        vol.Required(CONF_ACCESS_SECRET): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_DEVICE_ID): str,
    }
)


def _local_schema(include_on_dp: bool = False) -> vol.Schema:
    schema = {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_LOCAL_KEY): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_VERSION, default="auto"): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_VERSION_OPTIONS)
        ),
    }
    if include_on_dp:
        schema[vol.Required(CONF_PUMP_ON_DP, default=DEFAULT_PUMP_ON_DP)] = str
    return vol.Schema(schema)


STEP_PUMP_MODE = vol.Schema(
    {
        vol.Required(CONF_PUMP_MODE, default=PUMP_MODE_ENTITY): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[PUMP_MODE_ENTITY, PUMP_MODE_TUYA], translation_key="pump_mode"
            )
        )
    }
)

STEP_PUMP_ENTITY = vol.Schema(
    {
        vol.Required(CONF_PUMP_SWITCH): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(CONF_PUMP_POWER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_PUMP_ENERGY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)


def _version_value(raw: str | None) -> float | None:
    if not raw or raw == "auto":
        return None
    return float(raw)


async def validate_local(hass, ui: dict) -> None:
    """Open a local Tuya connection, retrying past transient contention."""
    version = _version_value(ui.get(CONF_VERSION))
    client = tuya.LocalClient(
        ui[CONF_DEVICE_ID], ui[CONF_LOCAL_KEY], ui[CONF_HOST],
        version if version else VERSION_CANDIDATES[0],
    )
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            await hass.async_add_executor_job(client.status)
            return
        except Exception as err:  # noqa: BLE001
            last_err = err
            if attempt < 3:
                await asyncio.sleep(2)
    raise last_err  # type: ignore[misc]


async def validate_sensor(hass, ui: dict) -> None:
    """Fetch cloud properties to validate cloud creds + device id."""
    cloud = await hass.async_add_executor_job(
        tuya.CloudClient, ui[CONF_REGION], ui[CONF_ACCESS_ID], ui[CONF_ACCESS_SECRET]
    )
    await hass.async_add_executor_job(cloud.properties, ui[CONF_DEVICE_ID])


async def discover(hass, creds: dict) -> tuple[list[dict], dict]:
    """Return (cloud device list with keys, LAN scan map) for auto-discovery."""
    cloud = await hass.async_add_executor_job(
        tuya.CloudClient, creds[CONF_REGION], creds[CONF_ACCESS_ID], creds[CONF_ACCESS_SECRET]
    )
    devices = await hass.async_add_executor_job(cloud.list_devices)
    scan = await hass.async_add_executor_job(tuya.scan_lan)
    return devices, scan


class IntexPoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup (cloud auto-discovery, or manual fallback)."""

    VERSION = 1

    def __init__(self) -> None:
        self._flags: dict[str, bool] = {}
        self._data: dict[str, Any] = {}
        self._creds: dict[str, str] = {}
        self._devices: list[dict] = []
        self._scan: dict = {}

    # ---- entry point ----
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_MANUAL):
                return await self.async_step_manual()
            if not user_input.get(CONF_ACCESS_ID) or not user_input.get(CONF_ACCESS_SECRET):
                errors["base"] = "need_creds"
            else:
                self._creds = {
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
                    CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
                }
                try:
                    self._devices, self._scan = await discover(self.hass, self._creds)
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_discover()
        return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

    # ---- cloud auto-discovery ----
    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        by_id = {d["id"]: d for d in self._devices}
        errors: dict[str, str] = {}
        if user_input is not None:
            data: dict[str, Any] = {}
            if (sid := user_input.get("sensor")):
                data[DEVICE_SENSOR] = {**self._creds, CONF_DEVICE_ID: sid}
            if (stid := user_input.get("saltwater")):
                ip, ver = self._scan.get(stid, (None, None))
                if not ip:
                    errors["base"] = "device_offline"
                else:
                    data[DEVICE_SALT] = {
                        CONF_DEVICE_ID: stid, CONF_LOCAL_KEY: by_id[stid]["key"],
                        CONF_HOST: ip, CONF_VERSION: ver,
                    }
            ptid = user_input.get("pump_tuya")
            psw = user_input.get(CONF_PUMP_SWITCH)
            if ptid and not errors:
                ip, ver = self._scan.get(ptid, (None, None))
                if not ip:
                    errors["base"] = "device_offline"
                else:
                    data[DEVICE_PUMP] = {
                        CONF_PUMP_MODE: PUMP_MODE_TUYA, CONF_DEVICE_ID: ptid,
                        CONF_LOCAL_KEY: by_id[ptid]["key"], CONF_HOST: ip, CONF_VERSION: ver,
                        CONF_PUMP_ON_DP: DEFAULT_PUMP_ON_DP,
                    }
            elif psw:
                pump = {CONF_PUMP_MODE: PUMP_MODE_ENTITY, CONF_PUMP_SWITCH: psw}
                if user_input.get(CONF_PUMP_POWER):
                    pump[CONF_PUMP_POWER] = user_input[CONF_PUMP_POWER]
                if user_input.get(CONF_PUMP_ENERGY):
                    pump[CONF_PUMP_ENERGY] = user_input[CONF_PUMP_ENERGY]
                data[DEVICE_PUMP] = pump
            if not errors:
                if not any(k in data for k in (DEVICE_SALT, DEVICE_SENSOR, DEVICE_PUMP)):
                    errors["base"] = "no_device"
                else:
                    self._data = data
                    return await self._async_finish()
        options = [
            {"value": d["id"], "label": d.get("name") or d["id"]} for d in self._devices
        ]
        dev_sel = selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
        )
        schema = vol.Schema(
            {
                vol.Optional("sensor"): dev_sel,
                vol.Optional("saltwater"): dev_sel,
                vol.Optional("pump_tuya"): dev_sel,
                vol.Optional(CONF_PUMP_SWITCH): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(CONF_PUMP_POWER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_PUMP_ENERGY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )
        return self.async_show_form(step_id="discover", data_schema=schema, errors=errors)

    # ---- manual fallback ----
    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if not any(user_input.values()):
                return self.async_show_form(
                    step_id="manual", data_schema=STEP_MANUAL, errors={"base": "no_device"}
                )
            self._flags = user_input
            self._data = {}
            return await self._async_next()
        return self.async_show_form(step_id="manual", data_schema=STEP_MANUAL)

    async def _async_next(self) -> ConfigFlowResult:
        if self._flags.get(CONF_HAS_SENSOR) and DEVICE_SENSOR not in self._data:
            return await self.async_step_sensor()
        if self._flags.get(CONF_HAS_SALT) and DEVICE_SALT not in self._data:
            return await self.async_step_salt()
        if self._flags.get(CONF_HAS_PUMP) and DEVICE_PUMP not in self._data:
            return await self.async_step_pump()
        return await self._async_finish()

    async def _async_finish(self) -> ConfigFlowResult:
        await self.async_set_unique_id(self._compute_uid())
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Intex Pool", data=self._data)

    def _compute_uid(self) -> str:
        parts = [
            (self._data.get(DEVICE_SALT) or {}).get(CONF_DEVICE_ID),
            (self._data.get(DEVICE_SENSOR) or {}).get(CONF_DEVICE_ID),
            (self._data.get(DEVICE_PUMP) or {}).get(CONF_DEVICE_ID),
            (self._data.get(DEVICE_PUMP) or {}).get(CONF_PUMP_SWITCH),
        ]
        return "-".join(p for p in parts if p) or DOMAIN

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_sensor(self.hass, user_input)
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._data[DEVICE_SENSOR] = {
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
                    CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                }
                return await self._async_next()
        return self.async_show_form(step_id="sensor", data_schema=STEP_SENSOR, errors=errors)

    async def async_step_salt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_local(self.hass, user_input)
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._data[DEVICE_SALT] = {
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    CONF_LOCAL_KEY: user_input[CONF_LOCAL_KEY],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_VERSION: _version_value(user_input.get(CONF_VERSION)),
                }
                return await self._async_next()
        return self.async_show_form(step_id="salt", data_schema=_local_schema(), errors=errors)

    async def async_step_pump(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_PUMP_MODE] == PUMP_MODE_TUYA:
                return await self.async_step_pump_tuya()
            return await self.async_step_pump_entity()
        return self.async_show_form(step_id="pump", data_schema=STEP_PUMP_MODE)

    async def async_step_pump_tuya(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_local(self.hass, user_input)
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._data[DEVICE_PUMP] = {
                    CONF_PUMP_MODE: PUMP_MODE_TUYA,
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    CONF_LOCAL_KEY: user_input[CONF_LOCAL_KEY],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_VERSION: _version_value(user_input.get(CONF_VERSION)),
                    CONF_PUMP_ON_DP: user_input.get(CONF_PUMP_ON_DP, DEFAULT_PUMP_ON_DP),
                }
                return await self._async_next()
        return self.async_show_form(
            step_id="pump_tuya", data_schema=_local_schema(include_on_dp=True), errors=errors
        )

    async def async_step_pump_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data[DEVICE_PUMP] = {CONF_PUMP_MODE: PUMP_MODE_ENTITY, **user_input}
            return await self._async_next()
        return self.async_show_form(step_id="pump_entity", data_schema=STEP_PUMP_ENTITY)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "IntexPoolOptionsFlow":
        return IntexPoolOptionsFlow()


class IntexPoolOptionsFlow(OptionsFlowWithReload):
    """Adjust polling intervals + the linked pump (auto-reloads on save)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        pump = entry.data.get(DEVICE_PUMP) or {}
        is_entity_pump = pump.get(CONF_PUMP_MODE) == PUMP_MODE_ENTITY

        if user_input is not None:
            if is_entity_pump:
                new_pump = {CONF_PUMP_MODE: PUMP_MODE_ENTITY, CONF_PUMP_SWITCH: user_input[CONF_PUMP_SWITCH]}
                for key in (CONF_PUMP_POWER, CONF_PUMP_ENERGY):
                    if user_input.get(key):
                        new_pump[key] = user_input[key]
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, DEVICE_PUMP: new_pump}
                )
            return self.async_create_entry(
                data={
                    CONF_LOCAL_INTERVAL: user_input[CONF_LOCAL_INTERVAL],
                    CONF_CLOUD_INTERVAL: user_input[CONF_CLOUD_INTERVAL],
                }
            )

        fields: dict = {
            vol.Required(CONF_LOCAL_INTERVAL, default=DEFAULT_LOCAL_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=600)
            ),
            vol.Required(CONF_CLOUD_INTERVAL, default=DEFAULT_CLOUD_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=3600)
            ),
        }
        if is_entity_pump:
            sw = selector.EntitySelector(selector.EntitySelectorConfig(domain="switch"))
            sen = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
            fields[vol.Required(CONF_PUMP_SWITCH, default=pump.get(CONF_PUMP_SWITCH))] = sw
            power_key = (vol.Optional(CONF_PUMP_POWER, default=pump[CONF_PUMP_POWER])
                         if pump.get(CONF_PUMP_POWER) else vol.Optional(CONF_PUMP_POWER))
            energy_key = (vol.Optional(CONF_PUMP_ENERGY, default=pump[CONF_PUMP_ENERGY])
                          if pump.get(CONF_PUMP_ENERGY) else vol.Optional(CONF_PUMP_ENERGY))
            fields[power_key] = sen
            fields[energy_key] = sen
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), entry.options),
        )
