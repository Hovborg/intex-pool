"""Config + options flow tests."""
import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import config_flow
from custom_components.intex_pool.const import DOMAIN
from custom_components.intex_pool.tuya import TuyaError

SENSOR_INPUT = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}
SALT_INPUT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": "3.5"}


async def _start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def test_user_requires_at_least_one_device(hass):
    result = await _start(hass)
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": False, "has_salt": False, "has_pump": False}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_device"}


async def test_flow_sensor_only(hass, mock_tinytuya):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    assert result["step_id"] == "sensor"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SENSOR_INPUT)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["sensor"]["device_id"] == "sdev"
    assert "salt" not in result["data"]


async def test_flow_salt_only(hass, mock_tinytuya):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": False, "has_salt": True, "has_pump": False}
    )
    assert result["step_id"] == "salt"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SALT_INPUT)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["salt"]["version"] == 3.5  # "3.5" -> float


async def test_flow_pump_entity_mode(hass, mock_tinytuya):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": False, "has_salt": False, "has_pump": True}
    )
    assert result["step_id"] == "pump"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pump_mode": "entity"}
    )
    assert result["step_id"] == "pump_entity"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pump_switch": "switch.my_pump"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["pump"]["pump_mode"] == "entity"
    assert result["data"]["pump"]["pump_switch"] == "switch.my_pump"


async def test_flow_all_three_routes_in_order(hass, mock_tinytuya):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": True, "has_salt": True, "has_pump": True}
    )
    assert result["step_id"] == "sensor"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SENSOR_INPUT)
    assert result["step_id"] == "salt"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SALT_INPUT)
    assert result["step_id"] == "pump"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pump_mode": "entity"})
    assert result["step_id"] == "pump_entity"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pump_switch": "switch.my_pump"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert set(result["data"]).issuperset({"sensor", "salt", "pump"})


async def test_flow_cannot_connect(hass, monkeypatch):
    async def boom(hass, ui):
        raise TuyaError("nope")

    monkeypatch.setattr(config_flow, "validate_sensor", boom)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SENSOR_INPUT)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_aborts(hass, mock_tinytuya):
    existing = MockConfigEntry(domain=DOMAIN, data={"sensor": SENSOR_INPUT}, unique_id="sdev")
    existing.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SENSOR_INPUT)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass, mock_tinytuya):
    entry = MockConfigEntry(domain=DOMAIN, data={"has_sensor": True, "sensor": SENSOR_INPUT}, unique_id="sdev")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"local_interval": 30, "cloud_interval": 300}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["local_interval"] == 30
