"""Data update coordinators for the Intex Pool integration.

One coordinator per active device. All blocking tinytuya work is dispatched to
the executor so the event loop is never blocked. The coordinator serializes
polling (one request at a time) and shares parsed data with every entity.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import schedule
from .const import VERSION_CANDIDATES
from .tuya import CloudClient, LocalClient, TuyaAuthError, TuyaError

_LOGGER = logging.getLogger(__name__)

# Consecutive bad-auth polls (after any version cycling) before the key is
# considered rotated and a reauth flow is started. >1 so a single corrupted
# reply on a marginal Wi-Fi link cannot kick the entry into reauth.
AUTH_FAILURES_BEFORE_REAUTH = 3


class _LocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Shared logic for local (LAN) Tuya devices, with protocol auto-detect."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: LocalClient,
        name: str,
        interval: int,
        auto_version: bool,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=name, config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self._client = client
        self._auto_version = auto_version
        self._ver_idx = 0
        self._auth_failures = 0

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.hass.async_add_executor_job(self._client.status)
        except TuyaAuthError as err:
            # Bad key (or version). While auto-detecting the protocol version,
            # keep cycling versions first. A single auth reject is NOT proof
            # the key rotated: on a weak Wi-Fi link a truncated/garbled reply
            # decrypts to the same error (seen in the field as a spurious
            # "reauth required" while the key was still valid). Only escalate
            # to reauth after several consecutive rejects with no success in
            # between.
            self._auth_failures += 1
            threshold = AUTH_FAILURES_BEFORE_REAUTH + (
                len(VERSION_CANDIDATES) if self._auto_version else 0
            )
            if self._auth_failures < threshold:
                self._rotate_version()
                raise UpdateFailed(str(err)) from err
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaError as err:
            self._rotate_version()
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 - surface any transport failure
            self._rotate_version()
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        self._auth_failures = 0
        return data

    def _rotate_version(self) -> None:
        """Advance to the next protocol-version candidate (auto-detect mode)."""
        if not self._auto_version:
            return
        self._ver_idx = (self._ver_idx + 1) % len(VERSION_CANDIDATES)
        self._client.set_version(VERSION_CANDIDATES[self._ver_idx])

    async def async_set_dp(self, dp: str | int, value: Any) -> None:
        """Set a DP, then refresh so HA reflects the new state quickly."""
        await self.hass.async_add_executor_job(self._client.set_value, dp, value)
        await self.async_request_refresh()


class SaltCoordinator(_LocalCoordinator):
    """Saltwater chlorinator (local)."""


class PumpCoordinator(_LocalCoordinator):
    """Sand-filter pump (local Tuya mode)."""


class SensorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Cloud-only water sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CloudClient,
        device_id: str,
        interval: int,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name="Intex water sensor", config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self._client = client
        self._device_id = device_id

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(
                self._client.properties, self._device_id
            )
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err

    async def async_issue(self, code: str, value: Any) -> None:
        """Write a cloud property, then refresh."""
        await self.hass.async_add_executor_job(
            self._client.issue, self._device_id, code, value
        )
        await self.async_request_refresh()

    async def async_refresh_measure(self) -> None:
        """Force the sleeping sensor to take a fresh measurement now."""
        await self.async_issue("refresh_switch", True)


class ScheduleCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read/write a device's schedule blob via the cloud.

    The schedule properties are cloud-only (never reported locally). The same
    7-slot codec covers both the chlorinator's ``skdl_salt`` and the analyzer's
    ``skdl_orpph`` measurement windows (byte-format live-verified 2026-06-10).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CloudClient,
        device_id: str,
        interval: int,
        code: str = "skdl_salt",
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=f"Intex schedule {code}", config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self._client = client
        self.device_id = device_id
        self.code = code
        self._write_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            props = await self.hass.async_add_executor_job(
                self._client.properties, self.device_id
            )
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        raw = props.get(self.code)
        return {"raw": raw, "slots": schedule.decode_schedules(raw)}

    async def async_write_slots(self, slots: list[dict[str, Any]]) -> None:
        """Encode + write the schedule slots back, then refresh.

        Writes are serialized behind a lock, and the just-written slots are
        published optimistically right away: the Tuya cloud takes a few seconds
        to reflect a write, and a second edit inside that settle window used to
        read the stale blob and silently undo the first edit.
        """
        async with self._write_lock:
            b64 = schedule.encode_schedules(slots)
            await self.hass.async_add_executor_job(
                self._client.issue, self.device_id, self.code, b64
            )
            self.async_set_updated_data({"raw": b64, "slots": slots})
            await asyncio.sleep(5)
        await self.async_request_refresh()
