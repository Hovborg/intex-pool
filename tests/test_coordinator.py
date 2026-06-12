"""Coordinator tests with fake clients (no tinytuya, no network)."""
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool.const import DOMAIN, VERSION_CANDIDATES
from custom_components.intex_pool.coordinator import (
    AUTH_FAILURES_BEFORE_REAUTH,
    PumpCoordinator,
    SaltCoordinator,
    SensorCoordinator,
)
from custom_components.intex_pool.tuya import TuyaAuthError, TuyaError


class FakeLocal:
    def __init__(self):
        self.version = 3.5
        self.calls = []
        self.fail = False
        self.auth_fail = False

    def status(self):
        if self.auth_fail:
            raise TuyaAuthError("bad key")
        if self.fail:
            raise TuyaError("boom")
        return {"104": True, "109": 1490, "125": "working"}

    def set_value(self, dp, val):
        self.calls.append((dp, val))

    def set_version(self, v):
        self.version = v


class FakeCloud:
    def __init__(self):
        self.issued = []
        self.fail = False
        self.auth_fail = False

    def properties(self, device_id):
        if self.auth_fail:
            raise TuyaAuthError("bad secret")
        if self.fail:
            raise TuyaError("cloud down")
        return {"PH_Number": 740, "battery_capacity": 97}

    def issue(self, device_id, code, value):
        self.issued.append((device_id, code, value))


def _entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    return entry


async def test_salt_update_returns_dps(hass):
    client = FakeLocal()
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=False)
    await coord.async_refresh()
    assert coord.last_update_success is True
    assert coord.data["109"] == 1490


async def test_salt_update_failed_marks_unavailable(hass):
    client = FakeLocal()
    client.fail = True
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=False)
    await coord.async_refresh()
    assert coord.last_update_success is False


async def test_salt_auto_version_rotates_on_failure(hass):
    client = FakeLocal()
    client.fail = True
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=True)
    await coord.async_refresh()
    assert client.version == VERSION_CANDIDATES[1]


async def test_salt_set_dp_calls_client(hass):
    client = FakeLocal()
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=False)
    await coord.async_refresh()
    await coord.async_set_dp(104, False)
    assert client.calls == [(104, False)]


async def test_pump_is_local_coordinator(hass):
    client = FakeLocal()
    coord = PumpCoordinator(hass, _entry(hass), client, "pump", 15, auto_version=False)
    await coord.async_refresh()
    assert coord.data["104"] is True


async def test_sensor_update_and_issue(hass):
    cloud = FakeCloud()
    coord = SensorCoordinator(hass, _entry(hass), cloud, "devid", 120)
    await coord.async_refresh()
    assert coord.data["PH_Number"] == 740
    await coord.async_issue("ph_set", 750)
    assert cloud.issued == [("devid", "ph_set", 750)]


async def test_sensor_refresh_measure_presses_refresh_switch(hass):
    cloud = FakeCloud()
    coord = SensorCoordinator(hass, _entry(hass), cloud, "devid", 120)
    await coord.async_refresh()
    await coord.async_refresh_measure()
    assert cloud.issued[-1] == ("devid", "refresh_switch", True)


async def test_sensor_failure(hass):
    cloud = FakeCloud()
    cloud.fail = True
    coord = SensorCoordinator(hass, _entry(hass), cloud, "devid", 120)
    await coord.async_refresh()
    assert coord.last_update_success is False


async def test_salt_bad_key_known_version_raises_auth(hass):
    """Repeated key rejects on a known protocol version -> ConfigEntryAuthFailed.

    The first rejects are treated as transient (weak Wi-Fi garbles replies into
    auth errors); only AUTH_FAILURES_BEFORE_REAUTH consecutive rejects escalate.
    """
    client = FakeLocal()
    client.auth_fail = True
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=False)
    for _ in range(AUTH_FAILURES_BEFORE_REAUTH - 1):
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_salt_transient_auth_error_recovers_without_reauth(hass):
    """An isolated auth reject followed by a good poll never reaches reauth."""
    client = FakeLocal()
    client.auth_fail = True
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=False)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    client.auth_fail = False
    assert await coord._async_update_data()  # succeeds, resets the counter
    client.auth_fail = True
    for _ in range(AUTH_FAILURES_BEFORE_REAUTH - 1):
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


async def test_salt_bad_key_auto_version_retries_versions_first(hass):
    """While auto-detecting the version, a key/version reject rotates instead of reauth."""
    client = FakeLocal()
    client.auth_fail = True
    coord = SaltCoordinator(hass, _entry(hass), client, "salt", 15, auto_version=True)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert client.version == VERSION_CANDIDATES[1]  # rotated, not reauth


async def test_sensor_bad_secret_raises_auth(hass):
    cloud = FakeCloud()
    cloud.auth_fail = True
    coord = SensorCoordinator(hass, _entry(hass), cloud, "devid", 120)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()
