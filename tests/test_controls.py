"""Switch/number/button/select command tests."""
import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import const
from custom_components.intex_pool.button import IntexButton
from custom_components.intex_pool.coordinator import SaltCoordinator, SensorCoordinator
from custom_components.intex_pool.number import IntexNumber
from custom_components.intex_pool.select import IntexSelect
from custom_components.intex_pool.switch import IntexSwitch


class RecordingLocal:
    def __init__(self, dps):
        self._dps = dps
        self.calls = []
        self.fail = False

    def status(self):
        return self._dps

    def set_value(self, dp, v):
        if self.fail:
            from custom_components.intex_pool.tuya import TuyaError
            raise TuyaError("nope")
        self.calls.append((dp, v))

    def set_version(self, v):
        pass


class RecordingCloud:
    def __init__(self, props):
        self._p = props
        self.issued = []

    def properties(self, did):
        return self._p

    def issue(self, did, code, val):
        self.issued.append((code, val))


async def _salt(hass, dps):
    entry = MockConfigEntry(domain=const.DOMAIN, data={})
    entry.add_to_hass(hass)
    client = RecordingLocal(dps)
    coord = SaltCoordinator(hass, entry, client, "salt", 15, auto_version=False)
    await coord.async_refresh()
    return coord, client


async def _sensor(hass, props):
    entry = MockConfigEntry(domain=const.DOMAIN, data={})
    entry.add_to_hass(hass)
    client = RecordingCloud(props)
    coord = SensorCoordinator(hass, entry, client, "sid", 120)
    await coord.async_refresh()
    return coord, client


def _d(table, key):
    return next(d for d in table if d.key == key)


async def test_switch_power_toggle(hass):
    coord, client = await _salt(hass, {"104": True, "103": False})
    sw = IntexSwitch(coord, _d(const.SWITCHES, "power"), "saltid")
    assert sw.is_on is True
    await sw.async_turn_off()
    assert client.calls[0] == ("104", False)


async def test_switch_command_error_raises(hass):
    coord, client = await _salt(hass, {"104": True})
    client.fail = True
    sw = IntexSwitch(coord, _d(const.SWITCHES, "power"), "saltid")
    with pytest.raises(HomeAssistantError):
        await sw.async_turn_on()


async def test_select_self_clean(hass):
    coord, client = await _salt(hass, {"108": 4})
    sel = IntexSelect(coord, _d(const.SELECTS, "self_clean"), "saltid")
    assert sel.current_option == "4"
    assert sel.options == ["2", "4", "6", "10"]
    await sel.async_select_option("6")
    assert client.calls[0] == ("108", 6)


async def test_select_temp_unit_sets_bool(hass):
    # DP124 True == °C, False == °F (inverse of the doc; verified on hardware)
    coord, client = await _salt(hass, {"124": True})
    sel = IntexSelect(coord, _d(const.SELECTS, "temp_unit"), "saltid")
    assert sel.current_option == "c"
    assert set(sel.options) == {"c", "f"}
    await sel.async_select_option("f")
    assert client.calls[0] == ("124", False)


async def test_number_ph_target_scaled(hass):
    coord, client = await _sensor(hass, {"ph_set": 750})
    num = IntexNumber(coord, _d(const.NUMBERS, "ph_target"), "sid")
    assert num.native_value == 7.5
    await num.async_set_native_value(7.6)
    assert client.issued[0] == ("ph_set", 760)


async def test_number_orp_target_raw(hass):
    coord, client = await _sensor(hass, {"orp_set": 700})
    num = IntexNumber(coord, _d(const.NUMBERS, "orp_target"), "sid")
    assert num.native_value == 700.0
    await num.async_set_native_value(720)
    assert client.issued[0] == ("orp_set", 720)


async def test_pump_auto_mode_follows_saltwater(hass):
    from pytest_homeassistant_custom_component.common import async_mock_service
    from custom_components.intex_pool.switch import IntexPumpAutoSwitch
    entry = MockConfigEntry(domain=const.DOMAIN, data={})
    entry.add_to_hass(hass)
    client = RecordingLocal({"104": True})
    coord = SaltCoordinator(hass, entry, client, "salt", 15, auto_version=False)
    await coord.async_refresh()
    on_calls = async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    sw = IntexPumpAutoSwitch(coord, "saltid", "switch.shelly_pump", entry)
    sw.hass = hass
    assert sw.unique_id == "saltid_pump_auto"
    # salt power on -> pump on
    await sw._sync()
    await hass.async_block_till_done()
    assert on_calls[-1].data == {"entity_id": "switch.shelly_pump"}
    # salt power off -> pump off
    client._dps = {"104": False}
    await coord.async_refresh()
    await sw._sync()
    await hass.async_block_till_done()
    assert off_calls[-1].data == {"entity_id": "switch.shelly_pump"}


async def test_button_refresh(hass):
    coord, client = await _sensor(hass, {"PH_Number": 740})
    btn = IntexButton(coord, _d(const.BUTTONS, "refresh"), "sid")
    await btn.async_press()
    assert client.issued[-1] == ("refresh_switch", True)


async def test_select_report_cadence(hass):
    coord, client = await _sensor(hass, {"report_number": "PH_byweek"})
    sel = IntexSelect(coord, _d(const.SELECTS, "report_cadence"), "sid")
    # value_map decodes the raw thing-model enum to a friendly token
    assert sel.current_option == "ph_weekly"
    assert set(sel.options) == {
        "orp_weekly", "orp_monthly", "ph_weekly", "ph_monthly", "fc_weekly", "fc_monthly",
    }
    # round-trip: selecting a token writes the raw enum back via the cloud issue path
    await sel.async_select_option("fc_monthly")
    assert client.issued[0] == ("report_number", "FC_bymonth")


async def test_select_sensor_temp_unit_sets_bool(hass):
    # Reuses the salt temp_unit polarity (True == °C, False == °F).
    coord, client = await _sensor(hass, {"fc_unit_change_switch": True})
    sel = IntexSelect(coord, _d(const.SELECTS, "sensor_temp_unit"), "sid")
    assert sel.current_option == "c"
    assert set(sel.options) == {"c", "f"}
    await sel.async_select_option("f")
    assert client.issued[0] == ("fc_unit_change_switch", False)


async def test_button_retest_uses_local_write(hass):
    # The salt "re-test" button must use the LOCAL coordinator write path
    # (async_set_dp -> set_value), not the cloud async_issue.
    coord, client = await _salt(hass, {"104": True})
    btn = IntexButton(coord, _d(const.BUTTONS, "retest"), "saltid")
    await btn.async_press()
    assert client.calls[-1] == ("107", True)


async def test_button_refresh_still_uses_cloud_write(hass):
    # The existing sensor refresh button must keep using the cloud issue path.
    coord, client = await _sensor(hass, {"PH_Number": 740})
    btn = IntexButton(coord, _d(const.BUTTONS, "refresh"), "sid")
    await btn.async_press()
    assert client.issued[-1] == ("refresh_switch", True)
