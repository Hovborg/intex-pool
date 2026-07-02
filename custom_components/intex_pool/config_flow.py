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
from homeassistant.core import HomeAssistant, callback
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
    CONF_MODEL,
    CONF_POOL_VOLUME,
    CONF_PUMP_ENERGY,
    CONF_PUMP_MODE,
    CONF_PUMP_ON_DP,
    CONF_PUMP_POWER,
    CONF_PUMP_SWITCH,
    CONF_REGION,
    CONF_SALT_TARGET,
    CONF_VERSION,
    CONF_VOLUME_UNIT,
    DEFAULT_CLOUD_INTERVAL,
    DEFAULT_LOCAL_INTERVAL,
    DEFAULT_PUMP_ON_DP,
    DEFAULT_REGION,
    DEFAULT_SALT_TARGET,
    DEVICE_PUMP,
    DEVICE_META,
    DEVICE_SALT,
    DEVICE_SENSOR,
    DOMAIN,
    MODEL_SUGGESTIONS,
    PUMP_MODE_ENTITY,
    PUMP_MODE_TUYA,
    SALT_MAX_PPM,
    SALT_MIN_PPM,
    VERSION_CANDIDATES,
    VOLUME_UNIT_GALLON,
    VOLUME_UNIT_LITER,
)

_VERSION_OPTIONS = ["auto", "3.1", "3.3", "3.4", "3.5"]
_REGION_OPTIONS = ["eu", "us", "cn", "in"]
CONF_MANUAL = "manual"
# Explicit device-removal flags for the manual reconfigure step: unticked boxes
# KEEP a device (merge), so manual-only setups (no cloud creds -> no discover
# picker) still need a way to delete one.
REMOVE_FLAGS = {"remove_sensor": DEVICE_SENSOR, "remove_salt": DEVICE_SALT, "remove_pump": DEVICE_PUMP}
CONF_PUMP_LOCAL_KEY = "pump_local_key"  # reauth: the Tuya pump's own key field

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

# Reconfigure entry point — cloud credentials for re-discovery, or the manual
# escape for devices the LAN scan cannot see (e.g. on another VLAN/subnet).
STEP_RECONFIGURE_USER = vol.Schema(
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


def _local_schema(include_on_dp: bool = False) -> vol.Schema:
    schema = {
        vol.Required(CONF_DEVICE_ID): str,
        # The local key is a device credential — mask it like access_secret.
        vol.Required(CONF_LOCAL_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
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


def _model_selector(device: str) -> selector.SelectSelector:
    """Model picker (suggestions + free text) — cosmetic, for the device page."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=MODEL_SUGGESTIONS.get(device, []),
            mode=selector.SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


def _version_value(raw: str | None) -> float | None:
    if not raw or raw == "auto":
        return None
    return float(raw)


async def validate_local(hass: HomeAssistant, ui: dict) -> None:
    """Open a local Tuya connection, retrying past transient contention.

    Only transport failures are retried — a rejected key (auth) will never
    succeed with the same credentials, so it surfaces immediately instead of
    making the user wait through the retry budget.
    """
    version = _version_value(ui.get(CONF_VERSION))
    client = tuya.LocalClient(
        ui[CONF_DEVICE_ID], ui[CONF_LOCAL_KEY], ui[CONF_HOST],
        version if version else VERSION_CANDIDATES[0],
    )
    for attempt in range(4):
        try:
            await hass.async_add_executor_job(client.status)
            return
        except tuya.TuyaAuthError:
            raise
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise  # re-raise the last failure with its traceback intact
            await asyncio.sleep(2)


async def validate_sensor(hass: HomeAssistant, ui: dict) -> None:
    """Fetch cloud properties to validate cloud creds + device id."""
    cloud = await hass.async_add_executor_job(
        tuya.CloudClient, ui[CONF_REGION], ui[CONF_ACCESS_ID], ui[CONF_ACCESS_SECRET]
    )
    await hass.async_add_executor_job(cloud.properties, ui[CONF_DEVICE_ID])


async def discover(hass: HomeAssistant, creds: dict) -> tuple[list[dict], dict]:
    """Return (cloud device list with keys, LAN scan map) for auto-discovery."""
    cloud = await hass.async_add_executor_job(
        tuya.CloudClient, creds[CONF_REGION], creds[CONF_ACCESS_ID], creds[CONF_ACCESS_SECRET]
    )
    devices = await hass.async_add_executor_job(cloud.list_devices)
    scan = await hass.async_add_executor_job(tuya.scan_lan)
    return devices, scan


class IntexPoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup (cloud auto-discovery, or manual fallback)."""

    VERSION = 2

    def __init__(self) -> None:
        self._flags: dict[str, bool] = {}
        self._data: dict[str, Any] = {}
        self._creds: dict[str, str] = {}
        self._devices: list[dict] = []
        self._scan: dict = {}
        self._reconfigure_entry = None

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
                    if not self._devices:
                        # Reached the cloud but it returned no devices — don't
                        # show a dead/empty picker. Tell the user to set up
                        # manually instead of leaving them stuck on a blank list.
                        errors["base"] = "no_devices"
                    else:
                        return await self.async_step_discover()
        return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

    # ---- reauth (e.g. the local_key rotated after re-pairing) ----
    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        salt = entry.data.get(DEVICE_SALT)
        sensor = entry.data.get(DEVICE_SENSOR)
        pump = entry.data.get(DEVICE_PUMP) or {}
        pump_tuya = pump if pump.get(CONF_PUMP_MODE) == PUMP_MODE_TUYA else None
        errors: dict[str, str] = {}
        # Each local device gets its OWN key field (salt and a Tuya pump have
        # separate keys), so reauth works for any combination of devices.
        if user_input is not None:
            new_data = {**entry.data}
            try:
                if salt and CONF_LOCAL_KEY in user_input:
                    cand = {**salt, CONF_LOCAL_KEY: user_input[CONF_LOCAL_KEY]}
                    await validate_local(self.hass, cand)
                    new_data[DEVICE_SALT] = cand
                if pump_tuya and CONF_PUMP_LOCAL_KEY in user_input:
                    cand = {**pump_tuya, CONF_LOCAL_KEY: user_input[CONF_PUMP_LOCAL_KEY]}
                    await validate_local(self.hass, cand)
                    new_data[DEVICE_PUMP] = cand
                if sensor and CONF_ACCESS_SECRET in user_input:
                    cand = {**sensor, CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET]}
                    await validate_sensor(self.hass, cand)
                    new_data[DEVICE_SENSOR] = cand
            except tuya.TuyaAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data=new_data)

        fields: dict = {}
        _pw = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
        if salt:
            fields[vol.Required(CONF_LOCAL_KEY)] = _pw
        if pump_tuya:
            fields[vol.Required(CONF_PUMP_LOCAL_KEY)] = _pw
        if sensor:
            fields[vol.Required(CONF_ACCESS_SECRET)] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema(fields), errors=errors
        )

    # ---- reconfigure (e.g. a device was replaced and got a new id) ----
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._reconfigure_entry = self._get_reconfigure_entry()
        # Re-run discovery with the stored cloud creds so the user can re-pick
        # devices (unchanged devices keep their existing IP/key, no scan needed).
        sensor = self._reconfigure_entry.data.get(DEVICE_SENSOR) or {}
        creds = {
            k: sensor[k]
            for k in (CONF_REGION, CONF_ACCESS_ID, CONF_ACCESS_SECRET)
            if sensor.get(k)
        }
        if len(creds) == 3:
            self._creds = creds
            try:
                self._devices, self._scan = await discover(self.hass, self._creds)
            except Exception:  # noqa: BLE001
                return await self.async_step_reconfigure_user()
            if not self._devices:
                # Stored creds reached the cloud but found nothing — re-prompt
                # (lets the user fix the region/creds) instead of an empty picker.
                return await self.async_step_reconfigure_user()
            return await self.async_step_discover()
        return await self.async_step_reconfigure_user()

    async def async_step_reconfigure_user(
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
                    if not self._devices:
                        errors["base"] = "no_devices"
                    else:
                        return await self.async_step_discover()
        schema = STEP_RECONFIGURE_USER
        if self._reconfigure_entry is not None and (
            sensor := self._reconfigure_entry.data.get(DEVICE_SENSOR)
        ):
            # Prefill the stored non-secret cloud fields — this step is reached
            # exactly when re-discovery failed, so don't force retyping them.
            schema = self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_USER,
                {k: sensor[k] for k in (CONF_REGION, CONF_ACCESS_ID) if sensor.get(k)},
            )
        return self.async_show_form(
            step_id="reconfigure_user", data_schema=schema, errors=errors
        )

    # ---- cloud auto-discovery ----
    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        by_id = {d["id"]: d for d in self._devices}
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_MANUAL):
                return await self.async_step_manual()
            data: dict[str, Any] = {}
            if (sid := user_input.get("sensor")):
                data[DEVICE_SENSOR] = {**self._creds, CONF_DEVICE_ID: sid}
            if (stid := user_input.get("saltwater")):
                # Prefer the live scan over the stored config: it heals a stale
                # IP (new lease / moved subnet) and a rotated key even when the
                # device id itself is unchanged.
                fresh = self._scanned_local(stid, by_id)
                kept = self._unchanged_local(DEVICE_SALT, stid)
                if fresh is not None:
                    data[DEVICE_SALT] = fresh
                elif kept is not None:
                    data[DEVICE_SALT] = kept
                else:
                    errors["base"] = "device_offline"
            ptid = user_input.get("pump_tuya")
            psw = user_input.get(CONF_PUMP_SWITCH)
            if ptid and not errors:
                fresh = self._scanned_local(ptid, by_id)
                kept = self._unchanged_local(DEVICE_PUMP, ptid)
                if fresh is not None:
                    data[DEVICE_PUMP] = {
                        CONF_PUMP_MODE: PUMP_MODE_TUYA,
                        **fresh,
                        CONF_PUMP_ON_DP: (kept or {}).get(CONF_PUMP_ON_DP, DEFAULT_PUMP_ON_DP),
                    }
                elif kept is not None:
                    data[DEVICE_PUMP] = kept
                else:
                    errors["base"] = "device_offline"
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
            selector.SelectSelectorConfig(
                options=options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                custom_value=True,  # allow typing/pasting a device id if the list is incomplete
            )
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
                vol.Optional(CONF_MANUAL, default=False): bool,
            }
        )
        if self._reconfigure_entry is not None:
            schema = self.add_suggested_values_to_schema(
                schema, self._reconfigure_suggested()
            )
        return self.async_show_form(step_id="discover", data_schema=schema, errors=errors)

    def _scanned_local(
        self, dev_id: str, by_id: dict[str, dict]
    ) -> dict[str, Any] | None:
        """Fresh local config from the LAN scan + the cloud key, or None when the
        scan did not see the device (e.g. it sits on another VLAN/subnet)."""
        ip, ver = self._scan.get(dev_id, (None, None))
        key = (by_id.get(dev_id) or {}).get("key")
        if not ip or not key:
            return None
        return {
            CONF_DEVICE_ID: dev_id, CONF_LOCAL_KEY: key,
            CONF_HOST: ip, CONF_VERSION: ver,
        }

    def _unchanged_local(self, device: str, dev_id: str) -> dict[str, Any] | None:
        """Reuse a local device's stored IP/key when reconfiguring and its id is
        unchanged — used when the LAN scan cannot see the (unchanged) device."""
        if self._reconfigure_entry is None:
            return None
        cur = self._reconfigure_entry.data.get(device) or {}
        if device == DEVICE_PUMP and cur.get(CONF_PUMP_MODE) != PUMP_MODE_TUYA:
            return None
        return cur if cur.get(CONF_DEVICE_ID) == dev_id else None

    def _reconfigure_suggested(self) -> dict[str, Any]:
        """Pre-fill the discover form with the entry's current selections."""
        d = self._reconfigure_entry.data
        pump = d.get(DEVICE_PUMP) or {}
        suggested: dict[str, Any] = {}
        if d.get(DEVICE_SENSOR):
            suggested["sensor"] = d[DEVICE_SENSOR].get(CONF_DEVICE_ID)
        if d.get(DEVICE_SALT):
            suggested["saltwater"] = d[DEVICE_SALT].get(CONF_DEVICE_ID)
        if pump.get(CONF_PUMP_MODE) == PUMP_MODE_TUYA:
            suggested["pump_tuya"] = pump.get(CONF_DEVICE_ID)
        elif pump.get(CONF_PUMP_SWITCH):
            suggested[CONF_PUMP_SWITCH] = pump.get(CONF_PUMP_SWITCH)
            if pump.get(CONF_PUMP_POWER):
                suggested[CONF_PUMP_POWER] = pump[CONF_PUMP_POWER]
            if pump.get(CONF_PUMP_ENERGY):
                suggested[CONF_PUMP_ENERGY] = pump[CONF_PUMP_ENERGY]
        return {k: v for k, v in suggested.items() if v}

    # ---- manual fallback ----
    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        schema = STEP_MANUAL
        if self._reconfigure_entry is not None:
            # Pre-tick the devices the entry already has. Ticked devices get
            # re-entered in the following steps; unticked ones are kept as-is
            # (merged back in _async_finish), never silently dropped. Existing
            # devices additionally get an explicit remove-checkbox.
            d = self._reconfigure_entry.data
            fields = dict(STEP_MANUAL.schema)
            for flag, dev in REMOVE_FLAGS.items():
                if dev in d:
                    fields[vol.Optional(flag, default=False)] = bool
            schema = self.add_suggested_values_to_schema(
                vol.Schema(fields),
                {
                    CONF_HAS_SENSOR: DEVICE_SENSOR in d,
                    CONF_HAS_SALT: DEVICE_SALT in d,
                    CONF_HAS_PUMP: DEVICE_PUMP in d,
                },
            )
        if user_input is not None:
            if not any(user_input.values()):
                return self.async_show_form(
                    step_id="manual", data_schema=schema, errors={"base": "no_device"}
                )
            self._flags = user_input
            self._data = {}
            return await self._async_next()
        return self.async_show_form(step_id="manual", data_schema=schema)

    async def _async_next(self) -> ConfigFlowResult:
        if self._flags.get(CONF_HAS_SENSOR) and DEVICE_SENSOR not in self._data:
            return await self.async_step_sensor()
        if self._flags.get(CONF_HAS_SALT) and DEVICE_SALT not in self._data:
            return await self.async_step_salt()
        if self._flags.get(CONF_HAS_PUMP) and DEVICE_PUMP not in self._data:
            return await self.async_step_pump()
        return await self._async_finish()

    async def _async_finish(self) -> ConfigFlowResult:
        if self._reconfigure_entry is not None:
            # Reconfigure: update the existing entry + reload (keep entity ids).
            data = self._data
            if self._flags:
                # Manual reconfigure edits only the ticked devices: an unticked
                # box means "leave that device as it is" — merge the untouched
                # devices back in instead of silently dropping them. Removal is
                # explicit via the remove_* checkboxes (manual-only setups
                # cannot reach the discover picker).
                removed = {dev for flag, dev in REMOVE_FLAGS.items() if self._flags.get(flag)}
                kept = {
                    k: v
                    for k, v in self._reconfigure_entry.data.items()
                    if k in DEVICE_META and k not in removed
                }
                data = {**kept, **data}
            return self.async_update_reload_and_abort(self._reconfigure_entry, data=data)
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
            except tuya.TuyaAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._data[DEVICE_SENSOR] = {
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
                    CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    **({CONF_MODEL: user_input[CONF_MODEL]} if user_input.get(CONF_MODEL) else {}),
                }
                return await self._async_next()
        schema = STEP_SENSOR.extend({vol.Optional(CONF_MODEL): _model_selector(DEVICE_SENSOR)})
        if self._reconfigure_entry is not None and (
            cur := self._reconfigure_entry.data.get(DEVICE_SENSOR)
        ):
            # Never embed the stored secret in the form payload sent to the
            # frontend — prefill only the non-secret fields.
            schema = self.add_suggested_values_to_schema(
                STEP_SENSOR, {k: v for k, v in cur.items() if k != CONF_ACCESS_SECRET}
            )
        return self.async_show_form(step_id="sensor", data_schema=schema, errors=errors)

    async def async_step_salt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_local(self.hass, user_input)
            except tuya.TuyaAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._data[DEVICE_SALT] = {
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    CONF_LOCAL_KEY: user_input[CONF_LOCAL_KEY],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_VERSION: _version_value(user_input.get(CONF_VERSION)),
                    **({CONF_MODEL: user_input[CONF_MODEL]} if user_input.get(CONF_MODEL) else {}),
                }
                return await self._async_next()
        schema = _local_schema().extend({vol.Optional(CONF_MODEL): _model_selector(DEVICE_SALT)})
        if self._reconfigure_entry is not None and (
            cur := self._reconfigure_entry.data.get(DEVICE_SALT)
        ):
            suggested = {k: v for k, v in cur.items() if k != CONF_LOCAL_KEY}
            schema = self.add_suggested_values_to_schema(
                schema, {**suggested, CONF_VERSION: str(cur.get(CONF_VERSION) or "auto")}
            )
        return self.async_show_form(step_id="salt", data_schema=schema, errors=errors)

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
            except tuya.TuyaAuthError:
                errors["base"] = "invalid_auth"
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
                    **({CONF_MODEL: user_input[CONF_MODEL]} if user_input.get(CONF_MODEL) else {}),
                }
                return await self._async_next()
        schema = _local_schema(include_on_dp=True).extend(
            {vol.Optional(CONF_MODEL): _model_selector(DEVICE_PUMP)}
        )
        if self._reconfigure_entry is not None:
            cur = self._reconfigure_entry.data.get(DEVICE_PUMP) or {}
            if cur.get(CONF_PUMP_MODE) == PUMP_MODE_TUYA:
                suggested = {k: v for k, v in cur.items() if k != CONF_LOCAL_KEY}
                schema = self.add_suggested_values_to_schema(
                    schema, {**suggested, CONF_VERSION: str(cur.get(CONF_VERSION) or "auto")}
                )
        return self.async_show_form(step_id="pump_tuya", data_schema=schema, errors=errors)

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
                    CONF_POOL_VOLUME: user_input.get(CONF_POOL_VOLUME, 0),
                    CONF_VOLUME_UNIT: user_input.get(CONF_VOLUME_UNIT, VOLUME_UNIT_LITER),
                    CONF_SALT_TARGET: user_input.get(CONF_SALT_TARGET, DEFAULT_SALT_TARGET),
                }
            )

        fields: dict = {
            vol.Required(CONF_LOCAL_INTERVAL, default=DEFAULT_LOCAL_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=600)
            ),
            vol.Required(CONF_CLOUD_INTERVAL, default=DEFAULT_CLOUD_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=3600)
            ),
            # Salt advisor: pool volume (0 = advisor off), its unit + target ppm.
            vol.Optional(CONF_POOL_VOLUME, default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=200_000)
            ),
            vol.Optional(CONF_VOLUME_UNIT, default=VOLUME_UNIT_LITER): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[VOLUME_UNIT_LITER, VOLUME_UNIT_GALLON],
                    translation_key="volume_unit",
                )
            ),
            vol.Optional(CONF_SALT_TARGET, default=DEFAULT_SALT_TARGET): vol.All(
                vol.Coerce(int), vol.Range(min=SALT_MIN_PPM, max=SALT_MAX_PPM)
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
