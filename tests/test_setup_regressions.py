"""Setup regressions using only isolated, mocked Home Assistant flows."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import config_flow
from custom_components.intex_pool.const import DOMAIN

SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sensor"}
SALT = {"device_id": "salt", "local_key": "k", "host": "192.0.2.1", "version": 3.5}
PUMP = {"pump_mode": "entity", "pump_switch": "switch.pool_pump"}


@pytest.mark.parametrize("removed", ["sensor", "salt", "pump"])
async def test_remove_wins_over_existing_device_edit_checkbox(hass, monkeypatch, removed):
    """The form preselects existing devices; Remove must override that checkbox."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"sensor": SENSOR, "salt": SALT, "pump": PUMP},
        unique_id="pool", version=2,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(config_flow, "discover", AsyncMock(return_value=([], {})))
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"manual": True},
    )
    assert result["step_id"] == "manual"
    flags = {"has_sensor": False, "has_salt": False, "has_pump": False}
    flags[f"has_{removed}"] = True
    flags[f"remove_{removed}"] = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], flags)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert removed not in entry.data
    for kept in {"sensor", "salt", "pump"} - {removed}:
        assert entry.data[kept] == {"sensor": SENSOR, "salt": SALT, "pump": PUMP}[kept]


async def test_discovery_keeps_models_of_unchanged_devices_with_fresh_scan(hass, monkeypatch):
    """Re-discovery may heal LAN details without erasing the chosen model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "sensor": {**SENSOR, "model": "WA510 Water Analyzer"},
            "salt": {**SALT, "model": "QS1600 Plus"},
            "pump": {
                **SALT, "device_id": "pump", "pump_mode": "tuya",
                "pump_on_dp": "104", "model": "SX2100",
            },
        },
        unique_id="pool", version=2,
    )
    entry.add_to_hass(hass)
    devices = [{"id": key, "name": key, "key": "fresh"} for key in ("sensor", "salt", "pump")]
    scan = {"salt": ("192.0.2.2", 3.5), "pump": ("192.0.2.3", 3.4)}
    monkeypatch.setattr(config_flow, "discover", AsyncMock(return_value=(devices, scan)))
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sensor": "sensor", "saltwater": "salt", "pump_tuya": "pump"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert entry.data["sensor"]["model"] == "WA510 Water Analyzer"
    assert entry.data["salt"]["model"] == "QS1600 Plus"
    assert entry.data["pump"]["model"] == "SX2100"
    assert entry.data["salt"]["host"] == "192.0.2.2"
    assert entry.data["salt"]["local_key"] == "fresh"
    assert entry.data["pump"]["host"] == "192.0.2.3"
    assert entry.data["pump"]["version"] == 3.4
    assert entry.data["pump"]["pump_on_dp"] == "104"


async def test_replacement_does_not_inherit_previous_devices_model(hass, monkeypatch):
    """A model belongs to a physical device, not to its replaceable role."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"sensor": {**SENSOR, "model": "Old analyzer"}},
        unique_id="pool", version=2,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(
        config_flow, "discover",
        AsyncMock(return_value=([{"id": "new", "name": "New analyzer", "key": "k"}], {})),
    )
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"sensor": "new"})
    assert result["type"] == FlowResultType.ABORT
    assert entry.data["sensor"]["device_id"] == "new"
    assert "model" not in entry.data["sensor"]


async def test_reconfigure_updates_duplicate_identity_for_old_and_new_sensor(
    hass, monkeypatch, mock_tinytuya,
):
    entry = MockConfigEntry(
        domain=DOMAIN, data={"sensor": SENSOR}, unique_id="sensor", version=2,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(
        config_flow, "discover",
        AsyncMock(return_value=([{"id": "new", "name": "Replacement", "key": "k"}], {})),
    )
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"sensor": "new"})
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "new"

    for device_id, expected in (("new", FlowResultType.ABORT), ("sensor", FlowResultType.CREATE_ENTRY)):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"manual": True})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**SENSOR, "device_id": device_id},
        )
        assert result["type"] == expected
        if expected == FlowResultType.ABORT:
            assert result["reason"] == "already_configured"


async def test_reconfigure_collision_does_not_change_either_entry(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN, data={"sensor": SENSOR}, unique_id="sensor", version=2,
    )
    other_data = {"sensor": {**SENSOR, "device_id": "occupied"}}
    other = MockConfigEntry(domain=DOMAIN, data=other_data, unique_id="occupied", version=2)
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    monkeypatch.setattr(
        config_flow, "discover",
        AsyncMock(return_value=([{"id": "occupied", "name": "Other", "key": "k"}], {})),
    )
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sensor": "occupied"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "sensor"
    assert entry.data == {"sensor": SENSOR}
    assert other.unique_id == "occupied"
    assert other.data == other_data
    reload.assert_not_called()


async def test_manual_reconfigure_identity_includes_untouched_devices(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN, data={"sensor": SENSOR, "salt": SALT},
        unique_id="salt-sensor", version=2,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(config_flow, "discover", AsyncMock(return_value=([], {})))
    monkeypatch.setattr(config_flow, "validate_sensor", AsyncMock())
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"manual": True})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SENSOR, "device_id": "new"},
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "salt-new"
    assert entry.data["salt"] == SALT
