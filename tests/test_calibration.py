"""Tests for the software calibration (v0.14.0).

Model under test (research-grounded): offset-only drift bridge between the
Intex app's buffer calibrations; deadband below device resolution; clamp at
the clean/recalibrate threshold; auto-reset when the device's own caliberate
coefficients move (app recalibration).
"""
import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

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


def _props(self, path, post=None, *, ph=740, orp=680, coeff_ph=None, coeff_orp=None):
    props = [
        {"code": "PH_Number", "value": ph},
        {"code": "ORP_Number", "value": orp},
        {"code": "maintenance_indicator", "value": "off"},
    ]
    if coeff_ph is not None:
        props.append({"code": "ph_caliberate", "value": coeff_ph})
    if coeff_orp is not None:
        props.append({"code": "orp_caliberate", "value": coeff_orp})
    return {"success": True, "result": {"properties": props}}


async def test_calibrate_ph_applies_offset(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    ph = _entities(hass)["sdev_ph"]
    assert ph.native_value == 7.4  # conftest raw 740

    response = await hass.services.async_call(
        DOMAIN, "calibrate",
        {"parameter": "ph", "reference_value": 7.6},
        blocking=True, return_response=True,
    )
    assert response == {
        "parameter": "ph", "device_value": 7.4,
        "reference_value": 7.6, "offset": 0.2,
    }
    assert entry.options["calibration"]["ph_offset"] == 0.2
    assert ph.native_value == 7.6
    attrs = ph.extra_state_attributes
    assert attrs["raw_value"] == 7.4
    assert attrs["calibration_offset"] == 0.2
    assert attrs["calibrated_at"] is not None


async def test_calibrate_deadband_clears_offset(hass, mock_tinytuya):
    """A correction below the device's 0.1 resolution is noise -> offset 0."""
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    await hass.services.async_call(
        DOMAIN, "calibrate", {"parameter": "ph", "reference_value": 7.45},
        blocking=True,
    )
    assert entry.options["calibration"]["ph_offset"] == 0.0
    assert _entities(hass)["sdev_ph"].native_value == 7.4


async def test_calibrate_rejects_oversized_offset(hass, mock_tinytuya):
    """> +/-0.5 pH is clean/recalibrate territory — refuse to mask it."""
    await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "calibrate", {"parameter": "ph", "reference_value": 8.5},
            blocking=True,
        )


async def test_calibrate_orp(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    await hass.services.async_call(
        DOMAIN, "calibrate", {"parameter": "orp", "reference_value": 700},
        blocking=True,
    )
    assert entry.options["calibration"]["orp_offset"] == 20
    assert _entities(hass)["sdev_orp"].native_value == 700


async def test_clear_calibration(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    await hass.services.async_call(
        DOMAIN, "calibrate", {"parameter": "ph", "reference_value": 7.6},
        blocking=True,
    )
    assert _entities(hass)["sdev_ph"].native_value == 7.6
    await hass.services.async_call(DOMAIN, "clear_calibration", {}, blocking=True)
    assert "calibration" not in entry.options
    assert _entities(hass)["sdev_ph"].native_value == 7.4


async def test_offset_number_entity_applies_live(hass, mock_tinytuya):
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    ents = _entities(hass)
    offset = ents["sdev_ph_offset"]
    assert offset.native_value == 0.0
    await offset.async_set_native_value(-0.2)
    assert entry.options["calibration"]["ph_offset"] == -0.2
    assert ents["sdev_ph"].native_value == pytest.approx(7.2)
    # ORP offset entity is advanced -> registered but disabled by default
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("number", DOMAIN, "sdev_orp_offset")
    assert entity_id is not None
    assert registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_app_recalibration_resets_offsets(hass, mock_tinytuya):
    """When the device's own caliberate coefficients move (app recalibration),
    the software offsets are obsolete: reset to 0 + repair issue raised."""
    mock_tinytuya.tinytuya.Cloud.cloudrequest = lambda self, path, post=None: _props(
        self, path, coeff_ph=1, coeff_orp=0
    )
    entry = await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    await hass.services.async_call(
        DOMAIN, "calibrate", {"parameter": "ph", "reference_value": 7.6},
        blocking=True,
    )
    assert entry.options["calibration"]["device_coeffs"] == {"ph": 1, "orp": 0}
    assert _entities(hass)["sdev_ph"].native_value == 7.6

    # the app recalibrates -> coefficient changes -> next poll resets offsets
    mock_tinytuya.tinytuya.Cloud.cloudrequest = lambda self, path, post=None: _props(
        self, path, coeff_ph=5, coeff_orp=0
    )
    await entry.runtime_data.sensor.async_refresh()
    assert entry.options["calibration"]["ph_offset"] == 0.0
    assert _entities(hass)["sdev_ph"].native_value == 7.4
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"calibration_reset_{entry.entry_id}"
    )
    assert issue is not None


async def test_action_required_uses_calibrated_ph(hass, mock_tinytuya):
    """The roll-up judges the corrected value, not the raw one."""
    mock_tinytuya.tinytuya.Cloud.cloudrequest = lambda self, path, post=None: _props(
        self, path, ph=800  # raw 8.0 -> ph_high
    )
    await _setup(
        hass, {"has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR}
    )
    rollup = _entities(hass)["saltdev_action_required"]
    assert "ph_high" in rollup.extra_state_attributes["reasons"]

    # a -0.3 offset (reference test said 7.7) brings it back into the band
    await hass.services.async_call(
        DOMAIN, "calibrate", {"parameter": "ph", "reference_value": 7.7},
        blocking=True,
    )
    assert "ph_high" not in rollup.extra_state_attributes["reasons"]
