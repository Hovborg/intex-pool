"""Integration setup/unload tests (offline fakes via mock_tinytuya)."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import async_migrate_entry
from custom_components.intex_pool.const import DOMAIN
from custom_components.intex_pool.diagnostics import async_get_config_entry_diagnostics

SALT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": 3.5}
SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}
PUMP_TUYA = {"pump_mode": "tuya", "device_id": "pumpdev", "local_key": "k",
             "host": "1.2.3.5", "version": 3.5, "pump_on_dp": "1"}


async def _setup(hass, data):
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id="uid-" + "-".join(data))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_all_devices(hass, mock_tinytuya):
    entry = await _setup(hass, {
        "has_sensor": True, "has_salt": True, "has_pump": True,
        "sensor": SENSOR, "salt": SALT, "pump": PUMP_TUYA,
    })
    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.salt is not None and data.sensor is not None and data.pump is not None
    ids = hass.states.async_entity_ids()
    assert any(i.startswith("sensor.") for i in ids)
    assert any(i.startswith("switch.") for i in ids)
    assert any(i.startswith("number.") for i in ids)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_sensor_only(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.sensor is not None
    assert data.salt is None and data.pump is None
    ids = hass.states.async_entity_ids()
    assert any(i.startswith("sensor.") for i in ids)
    # no saltwater switches when only the sensor is configured (the sensor's
    # own stabilizer switch is expected)
    assert not any(i.startswith("switch.saltwater_system") for i in ids)
    assert "switch.water_sensor_stabilizer_cya_flag" in ids


async def test_setup_retries_when_all_devices_fail(hass, mock_tinytuya, monkeypatch):
    """If every configured device fails its first poll, setup -> SETUP_RETRY."""
    monkeypatch.setattr(
        mock_tinytuya.tinytuya.Cloud,
        "cloudrequest",
        lambda self, path, post=None: {"success": False},
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data={"has_sensor": True, "sensor": SENSOR}, version=2
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_v1_removes_orphan_boost_start_time(hass):
    """v1→v2 drops the slot-0 (Boost) start-time entity; the orphan is removed."""
    entry = MockConfigEntry(domain=DOMAIN, data={"salt": SALT}, version=1)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    orphan = registry.async_get_or_create(
        "time", DOMAIN, "saltdev_schedule_1_start", config_entry=entry
    )
    keep = registry.async_get_or_create(
        "time", DOMAIN, "saltdev_schedule_2_start", config_entry=entry
    )

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert registry.async_get(orphan.entity_id) is None  # boost start-time gone
    assert registry.async_get(keep.entity_id) is not None  # real slot kept


async def test_setup_pump_entity_mode_creates_no_coordinator(hass, mock_tinytuya):
    entry = await _setup(hass, {
        "has_pump": True,
        "pump": {"pump_mode": "entity", "pump_switch": "switch.my_pump"},
    })
    assert entry.state is ConfigEntryState.LOADED
    # entity-mode pump => no Tuya coordinator, no integration-created pump entity
    assert entry.runtime_data.pump is None
    assert not any(i.startswith("switch.") for i in hass.states.async_entity_ids())


async def test_setup_pump_only_cloud_creates_schedule_coordinator(hass, mock_tinytuya):
    """Stored pump-only cloud auth must make the pump timer available."""
    entry = await _setup(
        hass,
        {
            "cloud": {"region": "eu", "access_id": "a", "access_secret": "s"},
            "pump": {
                "pump_mode": "tuya",
                "device_id": "pumpdev",
                "local_key": "k",
                "host": "1.2.3.5",
                "version": 3.5,
                "pump_on_dp": "104",
            },
        },
    )

    assert entry.runtime_data.pump_schedule is not None
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["coordinators"]["pump_schedule"]["last_update_success"] is True
    assert diagnostics["entry"]["data"]["cloud"]["access_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["cloud"]["access_secret"] == "**REDACTED**"


async def test_pump_only_stays_loaded_when_standalone_cloud_is_down(hass, mock_tinytuya):
    """Cloud-only schedules must not take the local pump controls down with them."""

    class OfflineCloud:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Tuya cloud offline")

    mock_tinytuya.tinytuya.Cloud = OfflineCloud
    entry = await _setup(
        hass,
        {
            "cloud": {"region": "eu", "access_id": "a", "access_secret": "s"},
            "pump": {
                "pump_mode": "tuya",
                "device_id": "pumpdev",
                "local_key": "k",
                "host": "1.2.3.5",
                "version": 3.5,
                "pump_on_dp": "104",
            },
        },
    )

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.pump is not None
    assert entry.runtime_data.pump_schedule is None
