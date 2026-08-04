"""Tests closing the remaining audit gaps (F40-F42).

F40: card/static-path registration in async_setup.
F41: the cloud-secret branch of the reauth flow.
F42: pump-auto restore-on-restart (RestoreEntity + initial sync).
"""
from types import SimpleNamespace

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.core import State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
    mock_restore_cache,
)

import custom_components.intex_pool as integration
from custom_components.intex_pool import config_flow
from custom_components.intex_pool.const import DOMAIN

SALT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": 3.5}
SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}


def test_integration_declares_config_entry_only_schema() -> None:
    """Hassfest requires async_setup integrations to declare YAML semantics."""
    assert hasattr(integration, "CONFIG_SCHEMA")
    assert integration.CONFIG_SCHEMA({}) == {}


# ------------------------------------------------ F40: card registration ---

async def test_async_setup_registers_card_and_services(hass, monkeypatch):
    from custom_components.intex_pool import async_setup

    registered: list = []

    async def fake_register(paths):
        registered.extend(paths)

    hass.http = SimpleNamespace(async_register_static_paths=fake_register)
    hass.config.components.add("frontend")
    js_urls: list[str] = []
    monkeypatch.setattr(
        "custom_components.intex_pool.add_extra_js_url",
        lambda _hass, url: js_urls.append(url),
    )

    assert await async_setup(hass, {})

    paths = [p.url_path for p in registered]
    assert "/intex_pool/intex-pool-card.js" in paths
    assert "/intex_pool/intex-pool-card.js.map" in paths  # sourcemap served too
    assert len(js_urls) == 1
    assert js_urls[0].startswith("/intex_pool/intex-pool-card.js?v=")  # cache-bust
    # services are registered at component setup (action-setup rule)
    for service in ("set_schedule", "get_schedule", "calibrate", "clear_calibration"):
        assert hass.services.has_service(DOMAIN, service)


async def test_async_setup_registers_card_with_real_frontend_loader(hass):
    """The bundled module is visible through HA's real frontend URL manager."""
    from custom_components.intex_pool import async_setup

    async def fake_register(paths):
        return None

    hass.http = SimpleNamespace(async_register_static_paths=fake_register)
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *args: None, [])
    hass.config.components.add("frontend")
    assert await async_setup(hass, {})

    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert any(url.startswith("/intex_pool/intex-pool-card.js?v=") for url in urls)


# ----------------------------------------- F41: cloud-secret reauth branch ---

async def test_reauth_updates_cloud_secret(hass, monkeypatch):
    """The water sensor's access_secret can be reauthed (sensor-only entry)."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"sensor": SENSOR}, unique_id="sdev", version=2
    )
    entry.add_to_hass(hass)

    validated: list[dict] = []

    async def ok(hass_, ui):
        validated.append(ui)

    monkeypatch.setattr(config_flow, "validate_sensor", ok)
    r = await entry.start_reauth_flow(hass)
    assert r["step_id"] == "reauth_confirm"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"access_secret": "NEWSECRET"}
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reauth_successful"
    assert entry.data["sensor"]["access_secret"] == "NEWSECRET"
    # the candidate config (with the new secret) was actually validated
    assert validated and validated[0]["access_secret"] == "NEWSECRET"


# ------------------------------------- F42: pump-auto restore-on-restart ---

async def _setup_pump_auto(hass, restored: str, uid: str):
    entity_id = "switch.sand_filter_pump_pump_auto_mode"
    mock_restore_cache(hass, [State(entity_id, restored)])
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "has_salt": True, "has_pump": True, "salt": SALT,
            "pump": {"pump_mode": "entity", "pump_switch": "switch.shelly_pump"},
        },
        unique_id=uid, version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entity_id


async def test_pump_auto_restores_on_and_syncs(hass, mock_tinytuya):
    """A restored ON state survives restart, and the auto mode keeps driving
    the linked pump (conftest data has DP103 production OFF -> pump turned off;
    the interlock keys on chlorine production, not master power).

    The mock service is registered AFTER setup: loading the entry sets up the
    real switch component, which would otherwise clobber a pre-registered mock.
    """
    entry, entity_id = await _setup_pump_auto(hass, "on", "uid-restore")

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("switch", DOMAIN, "saltdev_pump_auto") == entity_id
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "on"  # restored across restart

    off_calls = async_mock_service(hass, "switch", "turn_off")
    await entry.runtime_data.salt.async_refresh()
    await hass.async_block_till_done()
    assert off_calls and off_calls[-1].data == {"entity_id": "switch.shelly_pump"}


async def test_pump_auto_restores_off_without_sync(hass, mock_tinytuya):
    entry, entity_id = await _setup_pump_auto(hass, "off", "uid-restore-off")

    state = hass.states.get(entity_id)
    assert state is not None and state.state == "off"

    on_calls = async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    await entry.runtime_data.salt.async_refresh()
    await hass.async_block_till_done()
    assert not on_calls and not off_calls  # auto mode off -> hands off the pump
