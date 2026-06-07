"""Tests that the descriptor tables faithfully encode the verified device spec."""
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.intex_pool import const, decode


def test_salt_switch_sources_match_verified_rw_dps():
    src = {d.key: d.source for d in const.SWITCHES if d.device == const.DEVICE_SALT}
    assert src["power"] == "104"
    assert src["chlorination"] == "103"


def test_sensor_scaling_ph_and_fc_only():
    s = {d.key: d for d in const.SENSORS}
    assert s["ph"].scale == 0.01
    assert s["free_chlorine"].scale == 0.01
    assert s["orp"].scale is None  # ORP is raw mV


def test_unique_keys_per_table():
    for table in (const.SENSORS, const.BINARY_SENSORS, const.SWITCHES,
                  const.SELECTS, const.NUMBERS, const.BUTTONS):
        keys = [d.key for d in table]
        assert len(keys) == len(set(keys)), keys


def test_enum_sensors_have_options_and_value_fn():
    for d in const.SENSORS:
        if d.device_class == SensorDeviceClass.ENUM:
            assert d.options, f"{d.key} missing options"
            assert d.value_fn is not None, f"{d.key} missing value_fn"
            assert d.state_class is None, f"{d.key} enum must not have state_class"


def test_device_translation_key_pairs_unique_per_platform():
    for table in (const.SENSORS, const.BINARY_SENSORS, const.SWITCHES,
                  const.SELECTS, const.NUMBERS, const.BUTTONS):
        pairs = [(d.device, d.translation_key) for d in table]
        assert len(pairs) == len(set(pairs)), pairs


def test_self_clean_value_map_matches_manual():
    sc = next(d for d in const.SELECTS if d.key == "self_clean")
    assert set(sc.value_map.values()) == {"2", "4", "6", "10"}


def test_number_targets_sources_and_scale():
    n = {d.key: d for d in const.NUMBERS}
    assert n["ph_target"].source == "ph_set" and n["ph_target"].scale == 0.01
    assert n["orp_target"].source == "orp_set" and n["orp_target"].scale is None


def test_error_options_consistent_with_decode():
    err = next(d for d in const.SENSORS if d.key == "salt_error")
    assert err.options == decode.ERROR_OPTIONS
    assert err.value_fn(190) == "e90"


def test_every_descriptor_has_known_device():
    known = {const.DEVICE_SALT, const.DEVICE_SENSOR, const.DEVICE_PUMP}
    for table in (const.SENSORS, const.BINARY_SENSORS, const.SWITCHES,
                  const.SELECTS, const.NUMBERS, const.BUTTONS):
        for d in table:
            assert d.device in known, d.key
