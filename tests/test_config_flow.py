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


async def test_user_no_devices_found_shows_no_devices_error(hass, monkeypatch):
    """Cloud reached but returned no devices -> clear error, not a dead picker."""
    async def empty_discover(hass_, creds):
        return ([], {})

    monkeypatch.setattr(config_flow, "discover", empty_discover)
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "a", "access_secret": "s", "manual": False}
    )
    assert r["type"] == FlowResultType.FORM
    assert r["step_id"] == "user"
    assert r["errors"] == {"base": "no_devices"}


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


async def test_cloud_discovery_pump_only_keeps_credentials(hass, mock_tinytuya, monkeypatch):
    """Pump-only discovery must retain cloud auth for ``skdl_filter`` schedules."""
    devices = [
        {"id": "pumpid", "name": "Intex SX2100", "key": "pumpkey", "category": "sp"}
    ]

    async def fake_discover(hass_, creds):
        assert creds["access_id"] == "aid"
        return devices, {"pumpid": ("1.2.3.5", 3.5)}

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await _start(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"region": "eu", "access_id": "aid", "access_secret": "sec", "manual": False},
    )
    assert r["step_id"] == "discover"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"pump_tuya": "pumpid"}
    )

    assert r["type"] == FlowResultType.CREATE_ENTRY
    assert r["data"]["cloud"] == {
        "region": "eu",
        "access_id": "aid",
        "access_secret": "sec",
    }
    assert r["data"]["pump"]["pump_on_dp"] == "104"


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


async def test_reauth_updates_standalone_cloud_secret(hass, monkeypatch):
    """Pump/salt-only schedule credentials can be repaired without a sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "cloud": {"region": "eu", "access_id": "a", "access_secret": "old"},
            "pump": {
                "pump_mode": "tuya",
                "device_id": "pumpdev",
                "local_key": "k",
                "host": "1.2.3.5",
                "version": 3.5,
                "pump_on_dp": "104",
            },
        },
        unique_id="cloud-only",
        version=2,
    )
    entry.add_to_hass(hass)
    validated = []

    async def ok(hass_, creds):
        validated.append(creds)

    monkeypatch.setattr(config_flow, "validate_cloud", ok, raising=False)
    r = await entry.start_reauth_flow(hass)
    assert r["step_id"] == "reauth_confirm"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"access_secret": "new"}
    )

    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reauth_successful"
    assert entry.data["cloud"]["access_secret"] == "new"
    assert validated[-1]["access_secret"] == "new"


async def test_reauth_requires_at_least_one_new_credential(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={"salt": SALT_INPUT}, unique_id="saltdev", version=2
    )
    entry.add_to_hass(hass)
    r = await entry.start_reauth_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {})

    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"base": "need_reauth_value"}


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


async def test_reconfigure_repoints_sensor(hass, mock_tinytuya, monkeypatch):
    """Reconfigure re-runs discovery (reusing stored creds) and repoints the
    sensor to a replaced device — same entry, no removal."""
    entry = MockConfigEntry(domain=DOMAIN, data={"sensor": SENSOR_INPUT}, unique_id="sdev", version=2)
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        # stored creds are reused; the new analyzer shows up in discovery
        assert creds["access_id"] == "a"
        return ([{"id": "newsensor", "name": "New Sensor", "key": "k", "category": "rs"}], {})

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)
    assert r["step_id"] == "discover"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"sensor": "newsensor"})
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reconfigure_successful"
    assert entry.data["sensor"]["device_id"] == "newsensor"  # repointed
    assert entry.data["sensor"]["access_id"] == "a"  # creds preserved


async def test_reconfigure_unchanged_salt_not_rescanned(hass, mock_tinytuya, monkeypatch):
    """An unchanged salt id keeps its stored host/key even with an empty LAN scan."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"salt": SALT_INPUT, "sensor": SENSOR_INPUT},
        unique_id="saltdev", version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        devices = [
            {"id": "saltdev", "name": "AGP Salt", "key": "ignored", "category": "rs"},
            {"id": "newsensor", "name": "New Sensor", "key": "k", "category": "rs"},
        ]
        return (devices, {})  # empty scan map -> salt MUST be reused, not rescanned

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"saltwater": "saltdev", "sensor": "newsensor"}
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reconfigure_successful"
    assert entry.data["salt"] == SALT_INPUT  # unchanged, kept verbatim (no rescan)
    assert entry.data["sensor"]["device_id"] == "newsensor"


async def test_reconfigure_without_stored_creds_prompts(hass):
    """A local-only entry (no stored cloud creds) asks for creds first."""
    entry = MockConfigEntry(domain=DOMAIN, data={"salt": SALT_INPUT}, unique_id="saltdev", version=2)
    entry.add_to_hass(hass)
    r = await entry.start_reconfigure_flow(hass)
    assert r["step_id"] == "reconfigure_user"


async def test_reconfigure_pump_only_reuses_stored_cloud_creds(hass, monkeypatch):
    """Pump-only cloud auth must reopen discovery without asking for creds again."""
    pump = {
        "pump_mode": "tuya",
        "device_id": "pumpdev",
        "local_key": "k",
        "host": "1.2.3.5",
        "version": 3.5,
        "pump_on_dp": "104",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "cloud": {"region": "eu", "access_id": "a", "access_secret": "s"},
            "pump": pump,
        },
        unique_id="pumpdev",
        version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        assert creds == {"region": "eu", "access_id": "a", "access_secret": "s"}
        return ([{"id": "pumpdev", "name": "SX2100", "key": "k"}], {})

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)

    assert r["step_id"] == "discover"


async def test_reconfigure_linked_pump_drops_unused_cloud_secret(
    hass, mock_tinytuya, monkeypatch
):
    """Replacing the last Tuya device with an HA switch must remove cloud auth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
        unique_id="pumpdev",
        version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        return ([{"id": "pumpdev", "name": "SX2100", "key": "k"}], {})

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"manual": True})
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": False, "has_salt": False, "has_pump": True}
    )
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"pump_mode": "entity"}
    )
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"pump_switch": "switch.pool_pump"}
    )

    assert r["reason"] == "reconfigure_successful"
    assert "cloud" not in entry.data


async def test_removing_sensor_moves_cloud_creds_to_retained_tuya_pump(
    hass, mock_tinytuya, monkeypatch
):
    """Removing the credential-owning sensor must not disable pump schedules."""
    pump = {
        "pump_mode": "tuya",
        "device_id": "pumpdev",
        "local_key": "k",
        "host": "1.2.3.5",
        "version": 3.5,
        "pump_on_dp": "104",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sensor": SENSOR_INPUT, "pump": pump},
        unique_id="sensor-pump",
        version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        return ([{"id": "pumpdev", "name": "SX2100", "key": "k"}], {})

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"manual": True})
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {
            "has_sensor": False,
            "has_salt": False,
            "has_pump": False,
            "remove_sensor": True,
        },
    )
    await hass.async_block_till_done()

    assert r["reason"] == "reconfigure_successful"
    assert entry.data["cloud"] == {
        "region": "eu",
        "access_id": "a",
        "access_secret": "s",
    }
    assert entry.data["pump"] == pump


async def test_reconfigure_empty_discovery_reprompts_creds(hass, mock_tinytuya, monkeypatch):
    """Reconfigure with stored creds but no discovered devices -> re-prompt creds,
    not a dead empty picker."""
    entry = MockConfigEntry(domain=DOMAIN, data={"sensor": SENSOR_INPUT}, unique_id="sdev", version=2)
    entry.add_to_hass(hass)

    async def empty_discover(hass_, creds):
        return ([], {})

    monkeypatch.setattr(config_flow, "discover", empty_discover)
    r = await entry.start_reconfigure_flow(hass)
    assert r["step_id"] == "reconfigure_user"


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


# --- reconfigure: stale-IP healing + manual escape (v0.16.0) ---

async def test_reconfigure_scan_refreshes_stale_ip(hass, mock_tinytuya, monkeypatch):
    """A LAN-scan hit updates host/key/version even when the device id is unchanged."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"salt": SALT_INPUT, "sensor": SENSOR_INPUT},
        unique_id="saltdev", version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        devices = [
            {"id": "saltdev", "name": "AGP Salt", "key": "freshkey", "category": "rs"},
            {"id": "sdev", "name": "Sensor", "key": "k", "category": "rs"},
        ]
        return (devices, {"saltdev": ("10.0.0.42", 3.5)})

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)
    assert r["step_id"] == "discover"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"saltwater": "saltdev", "sensor": "sdev"}
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reconfigure_successful"
    assert entry.data["salt"]["host"] == "10.0.0.42"      # stale IP healed
    assert entry.data["salt"]["local_key"] == "freshkey"  # rotated key healed


async def test_reconfigure_discover_manual_escape(hass, mock_tinytuya, monkeypatch):
    """The discover step's manual checkbox routes to the manual chain, and a
    manual reconfigure updates the entry in place (same entry, new host)."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"salt": SALT_INPUT, "sensor": SENSOR_INPUT},
        unique_id="saltdev", version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        return ([{"id": "saltdev", "name": "AGP Salt", "key": "k", "category": "rs"}], {})

    async def ok(hass_, ui):
        return None

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    monkeypatch.setattr(config_flow, "validate_local", ok)
    r = await entry.start_reconfigure_flow(hass)
    assert r["step_id"] == "discover"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"manual": True})
    assert r["step_id"] == "manual"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": False, "has_salt": True, "has_pump": False}
    )
    assert r["step_id"] == "salt"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"device_id": "saltdev", "local_key": "k", "host": "192.168.44.67", "version": "3.5"},
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reconfigure_successful"
    assert entry.data["salt"]["host"] == "192.168.44.67"
    # The unticked sensor was NOT re-entered — it must be preserved (merge),
    # never silently dropped by the wholesale data replacement.
    assert entry.data["sensor"] == SENSOR_INPUT


async def test_reconfigure_user_manual_escape(hass, mock_tinytuya, monkeypatch):
    """Without stored cloud creds, the creds prompt offers the manual escape."""
    entry = MockConfigEntry(domain=DOMAIN, data={"salt": SALT_INPUT}, unique_id="saltdev", version=2)
    entry.add_to_hass(hass)

    async def ok(hass_, ui):
        return None

    monkeypatch.setattr(config_flow, "validate_local", ok)
    r = await entry.start_reconfigure_flow(hass)
    assert r["step_id"] == "reconfigure_user"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"region": "eu", "access_id": "", "access_secret": "", "manual": True}
    )
    assert r["step_id"] == "manual"


async def test_reconfigure_manual_remove_flag_drops_device(hass, mock_tinytuya, monkeypatch):
    """Manual reconfigure keeps unticked devices, but an explicit remove flag
    deletes one — the only removal path for cloud-credential-less setups."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"salt": SALT_INPUT, "sensor": SENSOR_INPUT},
        unique_id="saltdev", version=2,
    )
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        return ([{"id": "saltdev", "name": "AGP Salt", "key": "k", "category": "rs"}], {})

    async def ok(hass_, ui):
        return None

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    monkeypatch.setattr(config_flow, "validate_local", ok)
    r = await entry.start_reconfigure_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"manual": True})
    assert r["step_id"] == "manual"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"has_sensor": False, "has_salt": True, "has_pump": False, "remove_sensor": True},
    )
    assert r["step_id"] == "salt"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"device_id": "saltdev", "local_key": "k", "host": "10.0.0.9", "version": "3.5"},
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reconfigure_successful"
    assert entry.data["salt"]["host"] == "10.0.0.9"
    assert "sensor" not in entry.data  # eksplicit fjernet


async def test_reconfigure_sensor_step_accepts_model(hass, mock_tinytuya, monkeypatch):
    """Regression: the sensor step's reconfigure prefill must keep the extended
    schema (incl. the optional model field), not fall back to the base schema."""
    entry = MockConfigEntry(domain=DOMAIN, data={"sensor": SENSOR_INPUT}, unique_id="sdev", version=2)
    entry.add_to_hass(hass)

    async def fake_discover(hass_, creds):
        return ([{"id": "sdev", "name": "Sensor", "key": "k", "category": "rs"}], {})

    monkeypatch.setattr(config_flow, "discover", fake_discover)
    r = await entry.start_reconfigure_flow(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"manual": True})
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"has_sensor": True, "has_salt": False, "has_pump": False}
    )
    assert r["step_id"] == "sensor"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"region": "eu", "access_id": "a", "access_secret": "s",
         "device_id": "sdev", "model": "WA510 Water Analyzer"},
    )
    assert r["type"] == FlowResultType.ABORT
    assert r["reason"] == "reconfigure_successful"
    assert entry.data["sensor"]["model"] == "WA510 Water Analyzer"
