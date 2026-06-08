"""Data update coordinators for the Intex Pool integration.

One coordinator per active device. All blocking tinytuya work is dispatched to
the executor so the event loop is never blocked. The coordinator serializes
polling (one request at a time) and shares parsed data with every entity.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import schedule
from .const import VERSION_CANDIDATES
from .tuya import CloudClient, LocalClient, TuyaError

_LOGGER = logging.getLogger(__name__)


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

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self._client.status)
        except TuyaError as err:
            self._rotate_version()
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 - surface any transport failure
            self._rotate_version()
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err

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
    """Read/write the saltwater system's schedule blob (``skdl_salt``) via cloud.

    The schedule is cloud-only (the device never reports it locally), so this
    polls the salt device's thing-model properties and decodes the blob.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CloudClient,
        device_id: str,
        interval: int,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name="Intex salt schedule", config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self._client = client
        self.device_id = device_id

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            props = await self.hass.async_add_executor_job(
                self._client.properties, self.device_id
            )
        except TuyaError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        raw = props.get("skdl_salt")
        return {"raw": raw, "slots": schedule.decode_schedules(raw)}

    async def async_write_slots(self, slots: list[dict[str, Any]]) -> None:
        """Encode + write the schedule slots back, then refresh."""
        b64 = schedule.encode_schedules(slots)
        await self.hass.async_add_executor_job(
            self._client.issue, self.device_id, "skdl_salt", b64
        )
        await self.async_request_refresh()
