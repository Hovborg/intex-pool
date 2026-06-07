"""Sensor/binary_sensor entity tests (real coordinator + fake client)."""
from homeassistant.const import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import const
from custom_components.intex_pool.binary_sensor import IntexBinarySensor, IntexConnectivity
from custom_components.intex_pool.coordinator import SaltCoordinator, SensorCoordinator
from custom_components.intex_pool.sensor import IntexSensor


class FakeLocal:
    def __init__(self, dps):
        self._dps = dps
        self.fail = False

    def status(self):
        if self.fail:
            from custom_components.intex_pool.tuya import TuyaError
            raise TuyaError("down")
        return self._dps

    def set_value(self, dp, v):
        pass

    def set_version(self, v):
        pass


class FakeCloud:
    def __init__(self, props):
        self._p = props

    def properties(self, did):
        return self._p

    def issue(self, did, code, val):
        pass


def _sensor_desc(key):
    return next(d for d in const.SENSORS if d.key == key)


async def _salt(hass, dps):
    entry = MockConfigEntry(domain=const.DOMAIN, data={})
    entry.add_to_hass(hass)
    client = FakeLocal(dps)
    coord = SaltCoordinator(hass, entry, client, "salt", 15, auto_version=False)
    await coord.async_refresh()
    return coord, client


async def _sensor(hass, props):
    entry = MockConfigEntry(domain=const.DOMAIN, data={})
    entry.add_to_hass(hass)
    coord = SensorCoordinator(hass, entry, FakeCloud(props), "sid", 120)
    await coord.async_refresh()
    return coord


async def test_salinity_value_and_identity(hass):
    coord, _ = await _salt(hass, {"109": 1490})
    s = IntexSensor(coord, _sensor_desc("salinity"), "saltid")
    assert s.native_value == 1490
    assert s.unique_id == "saltid_salinity"
    assert s.device_info["identifiers"] == {(const.DOMAIN, "saltid")}
    assert s.has_entity_name is True


async def test_status_and_error_decoded(hass):
    coord, _ = await _salt(hass, {"125": "working", "114": 190})
    assert IntexSensor(coord, _sensor_desc("status"), "x").native_value == "working"
    assert IntexSensor(coord, _sensor_desc("salt_error"), "x").native_value == "e90"


async def test_ph_and_battery(hass):
    coord = await _sensor(hass, {"PH_Number": 740, "battery_capacity": 97})
    assert IntexSensor(coord, _sensor_desc("ph"), "sid").native_value == 7.4
    battery = IntexSensor(coord, _sensor_desc("battery"), "sid")
    assert battery.native_value == 97
    assert battery.entity_category == EntityCategory.DIAGNOSTIC


async def test_orp_indicator_enum_normalizes(hass):
    coord = await _sensor(hass, {"orp_indicator": "saltwater_abnormal"})
    assert IntexSensor(coord, _sensor_desc("orp_indicator"), "sid").native_value == "saltwater_abnormal"


async def test_binary_flag_and_connectivity(hass):
    coord, client = await _salt(hass, {"119": True, "126": False})
    mesh_desc = next(d for d in const.BINARY_SENSORS if d.key == "mesh")
    assert IntexBinarySensor(coord, mesh_desc, "saltid").is_on is True

    conn = IntexConnectivity(coord, "salt", "saltid")
    assert conn.is_on is True
    assert conn.available is True
    # When the device drops, connectivity reports off but stays available
    client.fail = True
    await coord.async_refresh()
    assert conn.is_on is False
    assert conn.available is True
