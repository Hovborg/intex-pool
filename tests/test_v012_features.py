"""Tests for the v0.12.0 fixes/features.

Covers: pump on/off-DP resolution, cloud-written switches, reauth escalation,
write-then-commit slot switches, schedule time/duration entities, the pump
switch selector, the set_schedule service, diagnostics redaction, repair
issues, event entities and the new decoders.
"""
from datetime import UTC, datetime

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import const, decode
from custom_components.intex_pool.const import DOMAIN, VERSION_CANDIDATES
from custom_components.intex_pool.coordinator import (
    AUTH_FAILURES_BEFORE_REAUTH,
    SaltCoordinator,
    ScheduleCoordinator,
)
from custom_components.intex_pool.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.intex_pool import schedule
from custom_components.intex_pool.tuya import TuyaAuthError

SALT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": 3.5}
SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}

REAL = "BgYJADAAAAAGCAMAA/8BAAYICgAC/wEABggOAAL/AQAGCRYAAgABAAAAAAAAAAAAAAAAAAAAAAA="


async def _setup(hass, data):
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, unique_id="uid-" + "-".join(sorted(data)), version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entities(hass):
    return {
        e.unique_id: e
        for p in ep.async_get_platforms(hass, DOMAIN)
        for e in p.entities.values()
    }


# ---------------------------------------------------------------- decoders ---

def test_normalize_orp_trend():
    assert decode.normalize_orp_trend("no") == "none"
    assert decode.normalize_orp_trend("Red") == "low"
    assert decode.normalize_orp_trend("green") == "mid"
    assert decode.normalize_orp_trend("blue") == "high"
    assert decode.normalize_orp_trend("bogus") is None
    assert decode.normalize_orp_trend(None) is None


def test_last_measurement_uses_newest_measurement_time():
    times = {"PH_Number": 1765000000000, "ORP_Number": 1765003600000, "ph_set": 1765999999999}
    # config props (ph_set) are ignored; newest MEASUREMENT time wins
    assert decode.last_measurement(times) == datetime.fromtimestamp(
        1765003600000 / 1000, tz=UTC
    )
    # fallback: no known measurement codes -> newest of anything
    assert decode.last_measurement({"ph_set": 1765000000000}) == datetime.fromtimestamp(
        1765000000000 / 1000, tz=UTC
    )
    assert decode.last_measurement({}) is None
    assert decode.last_measurement(None) is None


# ------------------------------------------------------- pump on/off DP fix ---

async def test_tuya_pump_switch_uses_configured_dp(hass, mock_tinytuya):
    """Regression: the configured pump_on_dp must reach the switch entity."""
    await _setup(hass, {
        "has_pump": True,
        "pump": {"pump_mode": "tuya", "device_id": "pumpdev", "local_key": "k",
                 "host": "1.2.3.5", "version": 3.5, "pump_on_dp": "20"},
    })
    pump_switch = _entities(hass)["pumpdev_pump"]
    assert pump_switch.entity_description.source == "20"


async def test_tuya_pump_legacy_dp_is_healed_from_live_data(hass, mock_tinytuya):
    """An old DP1 default auto-heals when the live SX2100 exposes only DP104."""
    mock_tinytuya.tinytuya.Device.status = lambda self: {
        "dps": {"104": True, "106": False, "125": "working", "127": "normal"}
    }
    entry = await _setup(
        hass,
        {
            "pump": {
                "pump_mode": "tuya",
                "device_id": "pumpdev",
                "local_key": "k",
                "host": "1.2.3.5",
                "version": 3.5,
                "pump_on_dp": "1",
            }
        },
    )

    assert entry.data["pump"]["pump_on_dp"] == "104"
    assert _entities(hass)["pumpdev_pump"].entity_description.source == "104"


# ------------------------------------------------- new switch descriptors ---

async def test_stabilizer_switch_writes_via_cloud(hass, mock_tinytuya):
    await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    issued = []
    mock_tinytuya.tinytuya.Cloud.cloudrequest = (
        lambda self, path, post=None: (issued.append((path, post)) or {"success": True, "result": {}})
        if post else {"success": True, "result": {"properties": []}}
    )
    sw = _entities(hass)["sdev_stabilizer"]
    await sw.async_turn_on()
    assert any("/shadow/properties/issue" in p for p, _ in issued)


def test_salt_switch2_disabled_by_default():
    desc = next(d for d in const.SWITCHES if d.key == "chlorination_2")
    assert desc.source == "102"
    assert desc.entity_registry_enabled_default is False


# ------------------------------------------------------- reauth escalation ---

async def test_auto_version_escalates_to_reauth_after_full_cycle(hass):
    class BadKeyClient:
        def status(self):
            raise TuyaAuthError("914")

        def set_version(self, v):
            pass

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coord = SaltCoordinator(hass, entry, BadKeyClient(), "salt", 15, auto_version=True)
    for _ in range(len(VERSION_CANDIDATES) + AUTH_FAILURES_BEFORE_REAUTH - 1):
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
    # every version candidate rejected as bad auth, repeatedly -> the key
    # itself rotated (single rejects are tolerated as Wi-Fi transients)
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


# ----------------------------------------- slot switch: write-then-commit ---

class FakeCloudSched:
    def __init__(self, raw, fail=False):
        self.raw = raw
        self.fail = fail
        self.issued = []

    def properties(self, device_id):
        return {"skdl_salt": self.raw}

    def issue(self, device_id, code, value):
        if self.fail:
            raise TuyaAuthError("nope")
        self.issued.append((device_id, code, value))


def _sched_coord(hass, raw, fail=False):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    return ScheduleCoordinator(hass, entry, FakeCloudSched(raw, fail), "saltid", 600)


async def test_slot_switch_failed_write_keeps_state(hass, monkeypatch):
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch

    coord = _sched_coord(hass, REAL)
    await coord.async_refresh()
    coord._client.fail = True
    sw = IntexScheduleSlotSwitch(coord, "saltid", 1)  # active timed slot
    monkeypatch.setattr(sw, "async_write_ha_state", lambda: None)
    assert sw._remembered is None
    with pytest.raises(HomeAssistantError):
        await sw.async_turn_off()
    # the failed clear must NOT have committed any bookkeeping
    assert sw._remembered is None


async def test_boost_failed_write_keeps_suspended_empty(hass, monkeypatch):
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch

    coord = _sched_coord(hass, REAL)
    await coord.async_refresh()
    coord._client.fail = True
    boost = IntexScheduleSlotSwitch(coord, "saltid", 0)
    monkeypatch.setattr(boost, "async_write_ha_state", lambda: None)
    with pytest.raises(HomeAssistantError):
        await boost.async_turn_on()
    assert boost._suspended == {}


# ----------------------------------------- schedule time/duration entities ---

@pytest.fixture
def no_sleep(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("custom_components.intex_pool.coordinator.asyncio.sleep", _noop)


async def test_schedule_duration_entity_writes(hass, no_sleep, monkeypatch):
    from custom_components.intex_pool.number import IntexScheduleDuration

    coord = _sched_coord(hass, REAL)
    await coord.async_refresh()
    num = IntexScheduleDuration(coord, "saltid", 1)
    monkeypatch.setattr(num, "async_write_ha_state", lambda: None)
    assert num.native_value == 3.0  # Daily 03:00 · 3h
    await num.async_set_native_value(5)
    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    assert decoded[1]["duration"] == 5


async def test_schedule_duration_unavailable_when_slot_empty(hass):
    from custom_components.intex_pool.number import IntexScheduleDuration

    coord = _sched_coord(hass, REAL)
    await coord.async_refresh()
    num = IntexScheduleDuration(coord, "saltid", 6)  # empty slot
    assert num.native_value is None
    assert num.available is False


async def test_schedule_start_time_entity_writes(hass, no_sleep, monkeypatch):
    from custom_components.intex_pool.time import IntexScheduleStartTime

    coord = _sched_coord(hass, REAL)
    await coord.async_refresh()
    t = IntexScheduleStartTime(coord, "saltid", 1)
    monkeypatch.setattr(t, "async_write_ha_state", lambda: None)
    assert (t.native_value.hour, t.native_value.minute) == (3, 0)
    from datetime import time as dt_time

    await t.async_set_value(dt_time(hour=21, minute=15))
    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    assert (decoded[1]["hour"], decoded[1]["minute"]) == (21, 15)


async def test_schedule_write_failure_raises_homeassistanterror(hass, no_sleep):
    from custom_components.intex_pool.number import IntexScheduleDuration

    coord = _sched_coord(hass, REAL, fail=True)
    await coord.async_refresh()  # read path doesn't use issue -> succeeds
    num = IntexScheduleDuration(coord, "saltid", 1)
    with pytest.raises(HomeAssistantError):
        await num.async_set_native_value(4)


# --------------------------------------------------- pump switch selector ---

async def test_pump_switch_select_updates_entry_and_reloads(hass, mock_tinytuya, monkeypatch):
    entry = await _setup(hass, {
        "has_pump": True,
        "pump": {"pump_mode": "entity", "pump_switch": "switch.shelly_pump"},
    })
    hass.states.async_set("switch.shelly_pump", "on")
    hass.states.async_set("switch.other_pump", "off")
    sel = _entities(hass)[f"{entry.entry_id}_pump_switch_select"]
    assert sel.current_option == "switch.shelly_pump"
    assert "switch.other_pump" in sel.options

    reloads = []

    async def _fake_reload(entry_id):
        reloads.append(entry_id)
        return True

    monkeypatch.setattr(hass.config_entries, "async_reload", _fake_reload)
    await sel.async_select_option("switch.other_pump")
    await hass.async_block_till_done()
    assert entry.data["pump"]["pump_switch"] == "switch.other_pump"
    assert reloads == [entry.entry_id]


# ------------------------------------------------------ set_schedule service ---

async def test_set_schedule_service_registered_without_entries(hass, mock_tinytuya):
    """action-setup rule: the service exists as soon as the component is set up,
    and a call with no usable entry fails with a clear validation error."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "set_schedule")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_schedule", {"slot": 1, "enable": True}, blocking=True
        )


async def test_set_schedule_service_writes(hass, mock_tinytuya, no_sleep):
    entry = await _setup(hass, {
        "has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR,
    })
    assert entry.state is ConfigEntryState.LOADED
    coord = entry.runtime_data.schedule
    assert coord is not None
    written = []
    monkeypatch_issue = coord._client.issue

    class _Recorder:
        def issue(self, did, code, value):
            written.append((did, code, value))

        def properties(self, did):
            return {"skdl_salt": None}

    coord._client = _Recorder()
    await hass.services.async_call(
        DOMAIN, "set_schedule",
        {"slot": 2, "enable": True, "hour": 7, "minute": 30, "duration": 2, "days": 255},
        blocking=True,
    )
    assert written, f"no write happened (orig issue: {monkeypatch_issue})"
    did, code, blob = written[-1]
    assert code == "skdl_salt"
    decoded = schedule.decode_schedules(blob)
    assert (decoded[2]["hour"], decoded[2]["minute"], decoded[2]["duration"]) == (7, 30, 2)
    assert decoded[2]["active"] is True


async def test_set_schedule_service_bad_entry_id(hass, mock_tinytuya):
    await _setup(hass, {"has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_schedule",
            {"slot": 1, "enable": True, "config_entry_id": "deadbeef"},
            blocking=True,
        )


# ------------------------------------------------------------- diagnostics ---

async def test_diagnostics_redacts_credentials(hass, mock_tinytuya):
    entry = await _setup(hass, {
        "has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR,
    })
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["data"]["salt"]["local_key"] == "**REDACTED**"
    assert diag["entry"]["data"]["sensor"]["access_secret"] == "**REDACTED**"
    assert diag["entry"]["data"]["sensor"]["access_id"] == "**REDACTED**"
    # non-secrets survive, raw data included
    assert diag["entry"]["data"]["salt"]["device_id"] == "saltdev"
    assert diag["coordinators"]["salt"]["last_update_success"] is True
    assert "104" in diag["coordinators"]["salt"]["data"]


# ------------------------------------------------------------ repair issues ---

async def test_salt_alarm_creates_and_clears_issue(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_salt": True, "salt": SALT})
    registry = ir.async_get(hass)
    issue_id = f"salt_alarm_{entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue_id) is None  # normal at start

    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "127": "E90"}}
    await entry.runtime_data.salt.async_refresh()
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "salt_alarm_e90"
    assert issue.severity == ir.IssueSeverity.WARNING

    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "127": "normal"}}
    await entry.runtime_data.salt.async_refresh()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_stale_sensor_creates_issue(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    registry = ir.async_get(hass)
    issue_id = f"sensor_stale_{entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue_id) is None  # no times -> no issue

    old_ms = 1_600_000_000_000  # 2020 — far older than the 3 h threshold
    mock_tinytuya.tinytuya.Cloud.cloudrequest = lambda self, path, post=None: {
        "success": True,
        "result": {"properties": [{"code": "PH_Number", "value": 700, "time": old_ms}]},
    }
    await entry.runtime_data.sensor.async_refresh()
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "sensor_stale"


# ------------------------------------------------------------ event entity ---

async def test_alarm_event_fires_on_transition_only(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_salt": True, "salt": SALT})
    eid = "event.saltwater_system_alarm"
    state = hass.states.get(eid)
    assert state is not None
    assert state.state == "unknown"  # baseline seeded, nothing fired

    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "127": "E90"}}
    await entry.runtime_data.salt.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(eid)
    assert state.attributes.get("event_type") == "e90"

    # unchanged value -> no new event timestamp
    last = state.state
    await entry.runtime_data.salt.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == last


# ------------------------------------------------- v0.12.1 regression fixes ---

async def test_error_event_absent_key_seeds_silently(hass, mock_tinytuya):
    """The cloud omits properties the device never emitted. When error_code
    appears for the first time it's an ongoing state, not a transition — no
    event may fire (v0.12.1 fix for the None-baseline bug)."""
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    eid = "event.water_sensor_error"
    assert hass.states.get(eid).state == "unknown"  # error_code absent in conftest

    def _props_with(error_code):
        return lambda self, path, post=None: {
            "success": True,
            "result": {"properties": [
                {"code": "PH_Number", "value": 740},
                {"code": "error_code", "value": error_code},
            ]},
        }

    # error_code appears for the first time (healthy: 0 -> "none") — must NOT fire
    mock_tinytuya.tinytuya.Cloud.cloudrequest = _props_with(0)
    await entry.runtime_data.sensor.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == "unknown"

    # a real transition afterwards MUST fire
    mock_tinytuya.tinytuya.Cloud.cloudrequest = _props_with(190)  # E90
    await entry.runtime_data.sensor.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(eid).attributes.get("event_type") == "e90"


async def test_alarm_issue_survives_device_offline(hass, mock_tinytuya):
    """An active alarm repair issue must NOT disappear just because the device
    went offline — only a confirmed clear deletes it (v0.12.1 fix)."""
    entry = await _setup(hass, {"has_salt": True, "salt": SALT})
    registry = ir.async_get(hass)
    issue_id = f"salt_alarm_{entry.entry_id}"

    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "127": "E90"}}
    await entry.runtime_data.salt.async_refresh()
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    # device goes offline -> poll fails -> issue must remain
    def _raise(self):
        raise OSError("offline")

    mock_tinytuya.tinytuya.Device.status = _raise
    await entry.runtime_data.salt.async_refresh()
    assert entry.runtime_data.salt.last_update_success is False
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    # back online and clear -> issue deleted
    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "127": "normal"}}
    await entry.runtime_data.salt.async_refresh()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_remove_entry_purges_issues(hass, mock_tinytuya):
    """Deleting the config entry must remove its repair issues (v0.12.1 fix)."""
    entry = await _setup(hass, {"has_salt": True, "salt": SALT})
    registry = ir.async_get(hass)
    issue_id = f"salt_alarm_{entry.entry_id}"

    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "127": "E90"}}
    await entry.runtime_data.salt.async_refresh()
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is None
