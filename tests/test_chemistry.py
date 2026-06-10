"""Tests for the LSI / water-balance math and entities (v0.15.0).

The pure-math tests pin the implementation to the published industry tables
(CDC MAHC 2024 Annex Table 5.7.4.6) at their exact breakpoints.
"""
import math

import pytest
from homeassistant.helpers import entity_platform as ep
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import chemistry
from custom_components.intex_pool.const import DOMAIN

SALT = {"device_id": "saltdev", "local_key": "k", "host": "1.2.3.4", "version": 3.5}
SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}


# ------------------------------------------------------------- pure math ---

def test_alkalinity_factor_matches_mahc_table():
    # AF = log10(TA): published rows 25->1.4, 100->2.0, 800->2.9
    for ta, af in ((25, 1.4), (100, 2.0), (800, 2.9)):
        assert round(math.log10(ta), 1) == af


def test_calcium_factor_matches_mahc_table():
    # CF = log10(0.4 x CH): published rows 25->1.0, 100->1.6, 800->2.5, 2500->3.0
    for ch, cf in ((25, 1.0), (100, 1.6), (800, 2.5), (2500, 3.0)):
        assert round(math.log10(0.4 * ch), 1) == cf


def test_temperature_factor_matches_mahc_breakpoints():
    # TF polynomial vs published table rows (deg F -> factor), +/-0.05
    for deg_f, tf in ((32, 0.0), (53, 0.3), (76, 0.6), (84, 0.7), (105, 0.9)):
        poly = -0.56 + 0.01827 * deg_f - 0.000041 * deg_f**2
        assert poly == pytest.approx(tf, abs=0.05)


def test_lsi_balanced_textbook_case():
    # pH 7.5, 84 degF (28.9 C), TA 100, CH 100, no CYA/TDS:
    # 7.5 + 0.7 + 1.6 + 2.0 - 12.1 = -0.3 (chart arithmetic)
    value = chemistry.lsi(7.5, 28.9, ta=100, ch=100)
    assert value == pytest.approx(-0.3, abs=0.03)


def test_lsi_cya_correction_lowers_alkalinity():
    # At pH 7.6 the cyanurate factor is ~1/3 (PHTA/Orenda)
    assert chemistry.cya_correction_factor(7.6) == pytest.approx(0.33, abs=0.01)
    with_cya = chemistry.lsi(7.6, 25, ta=100, ch=200, cya=60)
    without = chemistry.lsi(7.6, 25, ta=100, ch=200)
    assert with_cya < without  # 60 ppm CYA removes ~20 ppm carbonate alk


def test_lsi_tds_constant_switches_at_1000():
    low = chemistry.lsi(7.5, 25, ta=100, ch=200, tds=500)
    high = chemistry.lsi(7.5, 25, ta=100, ch=200, tds=1500)
    assert low - high == pytest.approx(0.1, abs=0.001)  # 12.1 vs 12.2


def test_lsi_invalid_inputs_return_none():
    assert chemistry.lsi(7.5, 25, ta=0, ch=200) is None
    assert chemistry.lsi(7.5, 25, ta=100, ch=0) is None
    # CYA so high it consumes all alkalinity -> no carbonate alk -> None
    assert chemistry.lsi(7.6, 25, ta=30, ch=200, cya=300) is None


def test_classify_bands():
    assert chemistry.classify(-0.6) == "severely_corrosive"
    assert chemistry.classify(-0.4) == "slightly_corrosive"
    assert chemistry.classify(0.0) == "balanced"
    assert chemistry.classify(0.3) == "balanced"
    assert chemistry.classify(0.4) == "slightly_scaling"
    assert chemistry.classify(0.6) == "scale_forming"
    assert chemistry.classify(None) is None


# ---------------------------------------------------------------- entities ---

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


async def test_lsi_unavailable_without_test_inputs(hass, mock_tinytuya):
    await _setup(hass, {"has_sensor": True, "sensor": SENSOR})
    ents = _entities(hass)
    assert ents["sdev_lsi"].native_value is None
    assert ents["sdev_lsi"].extra_state_attributes["status"] == "set_test_inputs"
    assert ents["sdev_water_balance"].native_value is None


async def test_lsi_computed_from_inputs_and_live_data(hass, mock_tinytuya):
    """Conftest: pH 7.4, temp 19 C. TA/CH from the test-input entities."""
    await _setup(
        hass, {"has_sensor": True, "sensor": SENSOR},
        options={"total_alkalinity": 100, "calcium_hardness": 250},
    )
    ents = _entities(hass)
    lsi = ents["sdev_lsi"]
    expected = chemistry.lsi(7.4, 19, ta=100, ch=250)
    assert lsi.native_value == expected
    assert ents["sdev_water_balance"].native_value == chemistry.classify(expected)
    # entity-driven update: a higher CH via the number entity shifts LSI up
    await ents["sdev_calcium_hardness"].async_set_native_value(400)
    assert lsi.native_value == chemistry.lsi(7.4, 19, ta=100, ch=400)


async def test_lsi_uses_calibrated_ph_and_salinity_tds(hass, mock_tinytuya):
    entry = await _setup(
        hass,
        {"has_salt": True, "has_sensor": True, "salt": SALT, "sensor": SENSOR},
        options={"total_alkalinity": 100, "calcium_hardness": 250},
    )
    ents = _entities(hass)
    lsi = ents["sdev_lsi"]
    attrs = lsi.extra_state_attributes
    # TDS fell back to the live salinity (conftest: 1490 ppm -> 12.2 constant)
    assert attrs["tds"] == 1490
    assert attrs["tds_source"] == "salinity"
    base = lsi.native_value

    # calibrating pH (+0.2) must shift the LSI by the same amount
    await hass.services.async_call(
        DOMAIN, "calibrate", {"parameter": "ph", "reference_value": 7.6},
        blocking=True,
    )
    assert lsi.native_value == pytest.approx(base + 0.2, abs=0.011)
    assert entry.options["calibration"]["ph_offset"] == 0.2
