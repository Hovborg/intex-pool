"""Config + options flow tests (cloud auto-discovery + manual fallback)."""
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import config_flow
from custom_components.intex_pool.const import DOMAIN
from custom_components.intex_pool.tuya import TuyaError

SENSOR_INPUT = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}
SALT_INPUT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": "3.5"}


async def _start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def _to_manual(hass):
    """Advance the cloud entry step into the manual device-selection step."""
    r = await _start(hass)
    return await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "", "access_secret": "", "manual": True}
    )


# --- entry / cloud step ---

async def test_user_needs_creds_or_manual(hass):
    r = await _start(hass)
    assert r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "", "access_secret": "", "manual": False}
    )
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "need_creds"}


async def test_cloud_discovery_flow(hass, mock_tinytuya, monkeypatch):
    devices = [
        {"id": "saltid", "name": "AGP Salt", "key": "saltkey", "category": "rs"},
        {"id": "senid", "name": "AGP Sensor", "key": "senkey", "category": "rs"},
    ]
    scan = {"saltid": ("1.2.3.4", 3.5)}

    async def fake_discover(hass_, creds):
        assert creds["access_id"] == "aid"
        return devices, scan

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "aid", "access_secret": "sec", "manual": False}
    )
    assert r["step_id"] == "discover"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"sensor": "senid", "saltwater": "saltid"}
    )
    assert r["type"] == FlowResultType.CREATE_ENTRY
    assert r["data"]["salt"]["local_key"] == "saltkey"   # key auto-filled from cloud
    assert r["data"]["salt"]["host"] == "1.2.3.4"        # ip auto-filled from LAN scan
    assert r["data"]["salt"]["version"] == 3.5
    assert r["data"]["sensor"]["device_id"] == "senid"
    assert r["data"]["sensor"]["access_id"] == "aid"


async def test_cloud_discovery_device_offline(hass, monkeypatch):
    async def fake_discover(hass_, creds):
        return [{"id": "saltid", "name": "AGP Salt", "key": "k", "category": "rs"}], {}  # empty scan

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "aid", "access_secret": "sec", "manual": False}
    )
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"saltwater": "saltid"})
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "device_offline"}


async def test_cloud_discovery_bad_creds(hass, monkeypatch):
    async def boom(hass_, creds):
        raise TuyaError("bad creds")

    monkeypatch.setattr(config_flow, "discover", boom)
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "aid", "access_secret": "sec", "manual": False}
    )
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "cannot_connect"}


# --- manual fallback ---

async def test_manual_requires_at_least_one_device(hass):
    r = await _to_manual(hass)
    assert r["step_id"] == "manual"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": False, "has_salt": False, "has_pump": False}
    )
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "no_device"}


async def test_manual_sensor_only(hass, mock_tinytuya):
    r = await _to_manual(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    assert r["step_id"] == "sensor"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], SENSOR_INPUT)
    assert r["type"] == FlowResultType.CREATE_ENTRY
    assert r["data"]["sensor"]["device_id"] == "sdev"


async def test_manual_pump_entity_mode(hass, mock_tinytuya):
    r = await _to_manual(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": False, "has_salt": False, "has_pump": True}
    )
    assert r["step_id"] == "pump"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"pump_mode": "entity"})
    assert r["step_id"] == "pump_entity"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"pump_switch": "switch.my_pump"})
    assert r["type"] == FlowResultType.CREATE_ENTRY
    assert r["data"]["pump"]["pump_mode"] == "entity"
    assert r["data"]["pump"]["pump_switch"] == "switch.my_pump"


async def test_manual_cannot_connect(hass, monkeypatch):
    async def boom(hass_, ui):
        raise TuyaError("nope")

    monkeypatch.setattr(config_flow, "validate_sensor", boom)
    r = await _to_manual(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    r = await hass.config_entries.flow.async_configure(r["flow_id"], SENSOR_INPUT)
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "cannot_connect"}


async def test_duplicate_aborts(hass, mock_tinytuya):
    existing = MockConfigEntry(domain=DOMAIN, data={"sensor": SENSOR_INPUT}, unique_id="sdev")
    existing.add_to_hass(hass)
    r = await _to_manual(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    r = await hass.config_entries.flow.async_configure(r["flow_id"], SENSOR_INPUT)
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "already_configured"


async def test_reauth_updates_local_key(hass, monkeypatch):
    """A rotated local key: reauth form -> new key validated -> entry updated."""
    entry = MockConfigEntry(domain=DOMAIN, data={"salt": SALT_INPUT}, unique_id="saltdev", version=2)
    entry.add_to_hass(hass)

    async def ok(hass_, ui):
        return None

    monkeypatch.setattr(config_flow, "validate_local", ok)
    r = await entry.start_reauth_flow(hass)
    assert r["step_id"] == "reauth_confirm"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"local_key": "NEWKEY"})
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reauth_successful"
    assert entry.data["salt"]["local_key"] == "NEWKEY"


async def test_reauth_invalid_auth_shows_error(hass, monkeypatch):
    from custom_components.intex_pool.tuya import TuyaAuthError

    entry = MockConfigEntry(domain=DOMAIN, data={"salt": SALT_INPUT}, unique_id="saltdev", version=2)
    entry.add_to_hass(hass)

    async def bad(hass_, ui):
        raise TuyaAuthError("still bad")

    monkeypatch.setattr(config_flow, "validate_local", bad)
    r = await entry.start_reauth_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"local_key": "WRONG"})
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "invalid_auth"}


async def test_reauth_salt_and_pump_tuya_use_separate_keys(hass, monkeypatch):
    """With both a salt system and a Tuya pump, each gets its own key field."""
    pump_tuya = {
        "pump_mode": "tuya", "device_id": "pumpdev", "local_key": "oldp",
        "host": "1.2.3.5", "version": "3.5", "on_dp": "1",
    }
    entry = MockConfigEntry(
        domain=DOMAIN, data={"salt": SALT_INPUT, "pump": pump_tuya},
        unique_id="saltdev-pumpdev", version=2,
    )
    entry.add_to_hass(hass)

    async def ok(hass_, ui):
        return None

    monkeypatch.setattr(config_flow, "validate_local", ok)
    r = await entry.start_reauth_flow(hass)
    assert r["step_id"] == "reauth_confirm"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"local_key": "NEWSALT", "pump_local_key": "NEWPUMP"}
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reauth_successful"
    assert entry.data["salt"]["local_key"] == "NEWSALT"
    assert entry.data["pump"]["local_key"] == "NEWPUMP"  # pump key updated independently


async def test_options_flow(hass, mock_tinytuya):
    entry = MockConfigEntry(domain=DOMAIN, data={"has_sensor": True, "sensor": SENSOR_INPUT}, unique_id="sdev")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["step_id"] == "init"
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"local_interval": 30, "cloud_interval": 300}
    )
    assert r["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["local_interval"] == 30
