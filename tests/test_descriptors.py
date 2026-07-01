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
    assert set(sc.value_map.values()) == {"2", "4", "6", "8", "10"}


def test_number_targets_sources_and_scale():
    n = {d.key: d for d in const.NUMBERS}
    assert n["ph_target"].source == "ph_set" and n["ph_target"].scale == 0.01
    assert n["orp_target"].source == "orp_set" and n["orp_target"].scale is None


def test_error_options_consistent_with_decode():
    err = next(d for d in const.SENSORS if d.key == "salt_error")
    assert err.options == decode.ERROR_OPTIONS
    assert err.value_fn(190) == "e90"


def test_report_cadence_value_map_matches_thing_model():
    rc = next(d for d in const.SELECTS if d.key == "report_cadence")
    assert rc.device == const.DEVICE_SENSOR
    assert rc.source == "report_number"
    assert rc.value_map == {
        "ORP_byweek": "orp_weekly",
        "ORP_bymonth": "orp_monthly",
        "PH_byweek": "ph_weekly",
        "PH_bymonth": "ph_monthly",
        "FC_byweek": "fc_weekly",
        "FC_bymonth": "fc_monthly",
    }


def test_sensor_temp_unit_reuses_salt_polarity():
    salt = next(d for d in const.SELECTS if d.key == "temp_unit")
    sensor = next(d for d in const.SELECTS if d.key == "sensor_temp_unit")
    assert sensor.device == const.DEVICE_SENSOR
    assert sensor.source == "fc_unit_change_switch"
    assert sensor.translation_key == "temp_unit"
    # Same polarity tokens as the verified salt select.
    assert sensor.value_map == salt.value_map == {True: "c", False: "f"}


def test_retest_button_is_salt_local_dp():
    rt = next(d for d in const.BUTTONS if d.key == "retest")
    assert rt.device == const.DEVICE_SALT
    # retest_switch is DP 107 (local); salt writes address DPs numerically.
    assert rt.source == "107"
    assert rt.translation_key == "retest"


def test_every_descriptor_has_known_device():
    known = {const.DEVICE_SALT, const.DEVICE_SENSOR, const.DEVICE_PUMP}
    for table in (const.SENSORS, const.BINARY_SENSORS, const.SWITCHES,
                  const.SELECTS, const.NUMBERS, const.BUTTONS):
        for d in table:
            assert d.device in known, d.key
