"""Data update coordinators for the Intex Pool integration.

One coordinator per active device. All blocking tinytuya work is dispatched to
the executor so the event loop is never blocked. The coordinator serializes
polling (one request at a time) and shares parsed data with every entity.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import schedule
from .const import DOMAIN, VERSION_CANDIDATES
from .tuya import CloudClient, LocalClient, TuyaAuthError, TuyaError

_LOGGER = logging.getLogger(__name__)

# Consecutive bad-auth polls (after any version cycling) before the key is
# considered rotated and a reauth flow is started. >1 so a single corrupted
# reply on a marginal Wi-Fi link cannot kick the entry into reauth.
AUTH_FAILURES_BEFORE_REAUTH = 3
# Once a protocol version has polled successfully it is locked in — a transient
# Wi-Fi blip must not cycle a proven version away (that self-inflicts extra
# failed polls). Only an unbroken failure streak (device reflashed to a new
# protocol?) re-opens auto-detection — and the reauth threshold below leaves
# room for a full candidate cycle AFTER this unlock, so a version change never
# escalates into a reauth prompt for a key that was never wrong.
VERSION_UNLOCK_FAILURES = 5

_AUTH_STORE_KEY = f"{DOMAIN}_auth_failures"


class _AuthFailures:
    """Consecutive auth-failure counter that SURVIVES coordinator rebuilds.

    Every ConfigEntryNotReady retry rebuilds the coordinators from scratch; an
    instance attribute would restart at zero on each attempt, so permanently
    bad credentials could never accumulate enough consecutive rejects to reach
    the reauth threshold — the entry would loop "not ready" forever instead of
    surfacing a reauth prompt.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, key: str) -> None:
        self._store: dict[str, int] = hass.data.setdefault(_AUTH_STORE_KEY, {})
        self._key = f"{entry.entry_id}:{key}"

    @property
    def count(self) -> int:
        return self._store.get(self._key, 0)

    def bump(self) -> int:
        self._store[self._key] = self.count + 1
        return self._store[self._key]

    def reset(self) -> None:
        self._store.pop(self._key, None)


def clear_auth_failures(hass: HomeAssistant, entry_id: str) -> None:
    """Drop an entry's persisted auth counters (called on unload/removal)."""
    store: dict[str, int] = hass.data.setdefault(_AUTH_STORE_KEY, {})
    for key in [k for k in store if k.startswith(f"{entry_id}:")]:
        store.pop(key, None)


class CloudClientProvider:
    """Lazily construct and share an optional standalone cloud client.

    The sensor's cloud connection is required during config-entry setup. Pump-
    and salt-only cloud credentials are different: they provide optional
    schedules and must recover through normal coordinator polling without
    reloading otherwise healthy LAN coordinators.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: Mapping[str, str],
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._region = config["region"]
        self._access_id = config["access_id"]
        self._access_secret = config["access_secret"]
        self._client: CloudClient | None = None
        self._lock = asyncio.Lock()
        self._reauth_started = False

    async def async_get(self) -> CloudClient:
        """Return the cached client, retrying construction when unavailable."""
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is not None:
                return self._client
            try:
                client = await self._hass.async_add_executor_job(
                    CloudClient,
                    self._region,
                    self._access_id,
                    self._access_secret,
                )
            except TuyaAuthError:
                self.mark_auth_failed()
                raise
            self._client = client
            return client

    def mark_auth_failed(self) -> None:
        """Drop a rejected client and start at most one reauth flow."""
        self._client = None
        if not self._reauth_started:
            self._reauth_started = True
            self._entry.async_start_reauth(self._hass)


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
        self._auth_failures = _AuthFailures(hass, entry, name)
        self._fail_streak = 0
        self._ver_locked = False
        # Serialize LAN I/O: the periodic poll and a manual DP write each open
        # their own TCP session, and the device firmware only reliably serves
        # one at a time — an unserialized write racing a poll can be dropped.
        self._io_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self._io_lock:
                data = await self.hass.async_add_executor_job(self._client.status)
        except TuyaAuthError as err:
            # Bad key (or version). While auto-detecting the protocol version,
            # keep cycling versions first. A single auth reject is NOT proof
            # the key rotated: on a weak Wi-Fi link a truncated/garbled reply
            # decrypts to the same error (seen in the field as a spurious
            # "reauth required" while the key was still valid). Only escalate
            # to reauth after several consecutive rejects with no success in
            # between.
            failures = self._auth_failures.bump()
            self._fail_streak += 1
            extra = 0
            if self._auto_version:
                extra = len(VERSION_CANDIDATES)
                if self._ver_locked:
                    # A locked version only re-enters rotation after
                    # VERSION_UNLOCK_FAILURES — leave room for the full
                    # candidate cycle AFTER the unlock, so a firmware protocol
                    # change (decodes as auth errors) gets re-detected instead
                    # of escalating into reauth for a key that was never wrong.
                    extra += VERSION_UNLOCK_FAILURES
            if failures < AUTH_FAILURES_BEFORE_REAUTH + extra:
                self._rotate_version()
                raise UpdateFailed(str(err)) from err
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaError as err:
            self._fail_streak += 1
            self._rotate_version()
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 - surface any transport failure
            self._fail_streak += 1
            self._rotate_version()
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        self._auth_failures.reset()
        self._fail_streak = 0
        self._ver_locked = True  # proven good — stop cycling on transient blips
        return data

    def _rotate_version(self) -> None:
        """Advance to the next protocol-version candidate (auto-detect mode).

        A version that has successfully polled is locked in: transient
        transport failures must not cycle it away. Only a long unbroken
        failure streak re-opens auto-detection.
        """
        if not self._auto_version:
            return
        if self._ver_locked and self._fail_streak < VERSION_UNLOCK_FAILURES:
            return
        self._ver_idx = (self._ver_idx + 1) % len(VERSION_CANDIDATES)
        self._client.set_version(VERSION_CANDIDATES[self._ver_idx])

    async def async_set_dp(self, dp: str | int, value: Any) -> None:
        """Set a DP, then refresh so HA reflects the new state quickly."""
        async with self._io_lock:
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
        self._auth_failures = _AuthFailures(hass, entry, "sensor")

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.hass.async_add_executor_job(
                self._client.properties, self._device_id
            )
        except TuyaAuthError as err:
            # Same transient-tolerance as the local coordinators: one auth-coded
            # cloud reply (token-refresh race, gateway hiccup) must not force a
            # reauth prompt for still-valid credentials.
            if self._auth_failures.bump() < AUTH_FAILURES_BEFORE_REAUTH:
                raise UpdateFailed(str(err)) from err
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        self._auth_failures.reset()
        return data

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
        client: CloudClient | None,
        device_id: str,
        interval: int,
        code: str = "skdl_salt",
        *,
        provider: CloudClientProvider | None = None,
        optional_cloud: bool = False,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=f"Intex schedule {code}", config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self._client = client
        self._provider = provider
        self._optional_cloud = optional_cloud
        if client is None and provider is None:
            raise ValueError("ScheduleCoordinator needs a client or provider")
        self.device_id = device_id
        self.code = code
        self._write_lock = asyncio.Lock()
        self._auth_failures = _AuthFailures(hass, entry, f"schedule:{code}")

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            client = await self._async_client()
            props = await self.hass.async_add_executor_job(
                client.properties, self.device_id
            )
        except TuyaAuthError as err:
            if self._optional_cloud:
                if self._provider is not None:
                    self._provider.mark_auth_failed()
                raise UpdateFailed(str(err)) from err
            # Tolerate transient auth-coded cloud replies (see SensorCoordinator).
            if self._auth_failures.bump() < AUTH_FAILURES_BEFORE_REAUTH:
                raise UpdateFailed(str(err)) from err
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        self._auth_failures.reset()
        raw = props.get(self.code)
        return {"raw": raw, "slots": schedule.decode_schedules(raw)}

    async def _async_client(self) -> CloudClient:
        """Get the eager client or a lazily recovered standalone client."""
        if self._provider is not None:
            self._client = await self._provider.async_get()
        if self._client is None:  # constructor invariant; keeps type narrowing explicit
            raise TuyaError("cloud client unavailable")
        return self._client

    async def async_write_slots(self, slots: list[dict[str, Any]]) -> None:
        """Encode + write the schedule slots back, then refresh.

        Writes are serialized behind a lock, and the just-written slots are
        published optimistically right away: the Tuya cloud takes a few seconds
        to reflect a write, and a second edit inside that settle window used to
        read the stale blob and silently undo the first edit.
        """
        async with self._write_lock:
            b64 = schedule.encode_schedules(slots)
            client = await self._async_client()
            await self.hass.async_add_executor_job(
                client.issue, self.device_id, self.code, b64
            )
            self.async_set_updated_data({"raw": b64, "slots": slots})
            await asyncio.sleep(5)
        await self.async_request_refresh()
