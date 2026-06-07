"""Integration setup/unload tests (offline fakes via mock_tinytuya)."""
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool.const import DOMAIN

SALT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": 3.5}
SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}
PUMP_TUYA = {"pump_mode": "tuya", "device_id": "pumpdev", "local_key": "k",
             "host": "1.2.3.5", "version": 3.5, "on_dp": "1"}


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
    # no saltwater switches when only the sensor is configured
    assert not any(i.startswith("switch.") for i in ids)


async def test_setup_pump_entity_mode_creates_no_coordinator(hass, mock_tinytuya):
    entry = await _setup(hass, {
        "has_pump": True,
        "pump": {"pump_mode": "entity", "pump_switch": "switch.my_pump"},
    })
    assert entry.state is ConfigEntryState.LOADED
    # entity-mode pump => no Tuya coordinator, no integration-created pump entity
    assert entry.runtime_data.pump is None
    assert not any(i.startswith("switch.") for i in hass.states.async_entity_ids())
