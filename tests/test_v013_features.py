"""Tests for the v0.13.0 features.

Covers: salt dose advisor, cell wear, cold-water guard, action-required
roll-up, analyzer measurement schedules, get_schedule response service and
the fixable stale-sensor repair.
"""
import pytest
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import const
from custom_components.intex_pool.const import DOMAIN

SALT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": 3.5}
SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}


async def _setup(hass, data, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, options=options or {},
        unique_id="uid-" + "-".join(sorted(data)), version=2,
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


# ------------------------------------------------------- salt dose advisor ---

async def test_salt_advisor_disabled_without_volume(hass, mock_tinytuya):
    await _setup(hass, {"has_salt": True, "salt": SALT})
    assert "saltdev_salt_to_add" not in _entities(hass)


async def test_salt_advisor_math_and_status(hass, mock_tinytuya):
    # conftest salinity is 1490 ppm -> above the 950 target -> nothing to add
    entry = await _setup(
        hass, {"has_salt": True, "salt": SALT},
        options={"pool_volume": 9150, "salt_target": 950},
    )
    advisor = _entities(hass)["saltdev_salt_to_add"]
    assert advisor.native_value == 0.0
    assert advisor.extra_state_attributes["status"] == "ok"

    # low salinity -> kg = L x delta_ppm / 1e6 (manual-verified formula)
    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "109": 700}}
    await entry.runtime_data.salt.async_refresh()
    assert advisor.native_value == pytest.approx(9150 * 250 / 1_000_000, abs=0.01)
    assert advisor.extra_state_attributes["status"] == "add_salt"

    # too salty -> dilution advice from the manual's E92 table
    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "109": 2400}}
    await entry.runtime_data.salt.async_refresh()
    assert advisor.native_value == 0.0
    attrs = advisor.extra_state_attributes
    assert attrs["status"] == "dilute"
    assert attrs["drain_refill_pct"] == 50  # 2200-2600 band


# ----------------------------------------------------- cell wear descriptor ---

async def test_cell_wear_percentage(hass, mock_tinytuya):
    await _setup(hass, {"has_salt": True, "salt": SALT})
    wear = _entities(hass)["saltdev_cell_wear"]
    # conftest runtime is 10 h of the 5000 h counter range -> 0.2 %
    assert wear.native_value == pytest.approx(0.2)


# ------------------------------------------------------- cold water guard ---

def test_cold_water_value_fn():
    desc = next(d for d in const.BINARY_SENSORS if d.key == "cold_water")
    assert desc.value_fn(10) is True
    assert desc.value_fn(19) is False
    assert desc.value_fn(None) is None


async def test_cold_water_entity(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_salt": True, "salt": SALT})
    cold = _entities(hass)["saltdev_cold_water"]
    assert cold.is_on is False  # conftest water temp = 19 degC
    mock_tinytuya.tinytuya.Device.status = lambda self: {"dps": {"104": True, "111": 9}}
    await entry.runtime_data.salt.async_refresh()
    assert cold.is_on is True


# --------------------------------------------------- action required rollup ---

async def test_action_required_rollup(hass, mock_tinytuya):
    entry = await _setup(
        hass, {"has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR}
    )
    rollup = _entities(hass)["saltdev_action_required"]
    # conftest data is healthy: alarm normal, salinity 1490, pH 7.4, ORP 680
    assert rollup.is_on is False
    assert rollup.extra_state_attributes["reasons"] == []

    # degrade water chemistry: pH 8.0 (high) + ORP 600 (below 650 floor)
    mock_tinytuya.tinytuya.Cloud.cloudrequest = lambda self, path, post=None: {
        "success": True,
        "result": {"properties": [
            {"code": "PH_Number", "value": 800},
            {"code": "ORP_Number", "value": 600},
            {"code": "maintenance_indicator", "value": "off"},
        ]},
    }
    await entry.runtime_data.sensor.async_refresh()
    reasons = rollup.extra_state_attributes["reasons"]
    assert rollup.is_on is True
    assert "ph_high" in reasons and "orp_low" in reasons

    # degrade the salt side too: alarm E90 + salinity below 800
    mock_tinytuya.tinytuya.Device.status = lambda self: {
        "dps": {"104": True, "109": 500, "127": "E90"}
    }
    await entry.runtime_data.salt.async_refresh()
    reasons = rollup.extra_state_attributes["reasons"]
    assert "salt_alarm_e90" in reasons and "salinity_low" in reasons


# ------------------------------------------------- analyzer schedule sensor ---

async def test_analyzer_schedule_sensor(hass, mock_tinytuya):
    await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    sched = _entities(hass)["sdev_analyzer_schedules"]
    assert sched.native_value == 0  # no skdl_orpph in conftest -> empty slots


# ------------------------------------------------------ get_schedule service ---

async def test_get_schedule_returns_decoded_slots(hass, mock_tinytuya):
    await _setup(
        hass, {"has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR}
    )
    response = await hass.services.async_call(
        DOMAIN, "get_schedule", {}, blocking=True, return_response=True
    )
    assert set(response) == {"saltwater", "analyzer"}
    assert len(response["saltwater"]["slots"]) == 7
    assert len(response["analyzer"]["slots"]) == 7
    assert all("active" in s for s in response["saltwater"]["slots"])


# ------------------------------------------------- fixable stale repair flow ---

async def test_stale_issue_is_fixable_with_entry_data(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    old_ms = 1_600_000_000_000  # 2020 — far past the 3 h threshold
    mock_tinytuya.tinytuya.Cloud.cloudrequest = lambda self, path, post=None: {
        "success": True,
        "result": {"properties": [{"code": "PH_Number", "value": 700, "time": old_ms}]},
    }
    await entry.runtime_data.sensor.async_refresh()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"sensor_stale_{entry.entry_id}")
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.data == {"entry_id": entry.entry_id}


async def test_stale_repair_flow_triggers_refresh(hass, mock_tinytuya, monkeypatch):
    from custom_components.intex_pool.repairs import async_create_fix_flow

    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    refreshes = []

    async def _fake_refresh():
        refreshes.append(1)

    monkeypatch.setattr(
        entry.runtime_data.sensor, "async_refresh_measure", _fake_refresh
    )
    flow = await async_create_fix_flow(
        hass, f"sensor_stale_{entry.entry_id}", {"entry_id": entry.entry_id}
    )
    flow.hass = hass
    # first call shows the confirm form; confirming triggers the measurement
    form = await flow.async_step_init(None)
    assert form["type"] == "form" and form["step_id"] == "confirm"
    result = await flow.async_step_confirm({})
    assert result["type"] == "create_entry"
    assert refreshes == [1]
