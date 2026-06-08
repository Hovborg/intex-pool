"""Schedule coordinator + sensor tests (fake cloud, no network)."""
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import schedule
from custom_components.intex_pool.const import DOMAIN
from custom_components.intex_pool.coordinator import ScheduleCoordinator
from custom_components.intex_pool.sensor import IntexScheduleSensor

REAL = "BgYJADAAAAAGCAMAA/8BAAYICgAC/wEABggOAAL/AQAGCRYAAgABAAAAAAAAAAAAAAAAAAAAAAA="


class FakeCloudSched:
    def __init__(self, raw):
        self.raw = raw
        self.issued = []

    def properties(self, device_id):
        return {"skdl_salt": self.raw, "PH_Number": 740}

    def issue(self, device_id, code, value):
        self.issued.append((device_id, code, value))


def _coord(hass, raw):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    return ScheduleCoordinator(hass, entry, FakeCloudSched(raw), "saltid", 600), entry


async def test_schedule_coordinator_decodes_blob(hass):
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    assert coord.last_update_success is True
    assert len(coord.data["slots"]) == 7
    assert len(schedule.active_schedules(coord.data["slots"])) == 5
    assert coord.data["raw"] == REAL


async def test_schedule_sensor_state_and_attributes(hass):
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    sensor = IntexScheduleSensor(coord, "saltid")
    assert sensor.native_value == 5
    attrs = sensor.extra_state_attributes
    assert len(attrs["schedules"]) == 5
    assert any("Daily" in s for s in attrs["schedules"])
    assert attrs["raw"] == REAL
    assert sensor.unique_id == "saltid_schedules"


async def test_schedule_write_round_trips(hass):
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    new = schedule.set_slot(coord.data["slots"], 4, on=True, hour=23, minute=30, duration=4)
    await coord.async_write_slots(new)
    did, code, blob = coord._client.issued[-1]
    assert (did, code) == ("saltid", "skdl_salt")
    decoded = schedule.decode_schedules(blob)
    assert (decoded[4]["hour"], decoded[4]["minute"], decoded[4]["duration"]) == (23, 30, 4)


async def test_schedule_slot_sensors(hass):
    from custom_components.intex_pool.sensor import IntexScheduleSlotSensor
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    slot1 = IntexScheduleSlotSensor(coord, "saltid", 1)   # active (Daily 03:00)
    assert "Daily 03:00" in slot1.native_value
    assert slot1.extra_state_attributes["active"] is True
    assert slot1.unique_id == "saltid_schedule_2"
    empty = IntexScheduleSlotSensor(coord, "saltid", 6)   # empty slot
    assert empty.native_value == "—"
    assert empty.extra_state_attributes["active"] is False


async def test_schedule_write_identical_is_noop_blob(hass):
    """Writing the current slots back yields the exact same blob (safe no-op)."""
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    await coord.async_write_slots(coord.data["slots"])
    assert coord._client.issued[-1][2] == REAL
