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
    sensor = IntexScheduleSensor(coord, "salt", "saltid", "schedules")
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


async def test_schedule_slot_switches(hass):
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    slot1 = IntexScheduleSlotSwitch(coord, "saltid", 1)   # active (Daily 03:00)
    assert slot1.is_on is True
    assert "Daily 03:00" in slot1.extra_state_attributes["summary"]
    assert slot1.unique_id == "saltid_schedule_2"
    empty = IntexScheduleSlotSwitch(coord, "saltid", 6)   # empty slot
    assert empty.is_on is False
    assert empty.extra_state_attributes["summary"] is None


async def test_schedule_slot_toggle_off_remembers_and_clears(hass):
    from custom_components.intex_pool import schedule
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    sw = IntexScheduleSlotSwitch(coord, "saltid", 1)
    # exercise the write logic directly (avoids the propagation sleep in turn_off)
    slots = coord.data["slots"]
    sw._remembered = {f: int(slots[1].get(f, 0)) for f in schedule.FIELDS}
    new = schedule.set_slot(slots, 1, clear=True)
    assert new[1]["active"] is False
    # and restoring from remembered brings it back
    r = sw._remembered
    restored = schedule.set_slot(new, 1, on=bool(r["on"]), hour=r["hour"], duration=r["duration"], days=r["days"])
    assert restored[1]["hour"] == 3 and restored[1]["active"] is True


async def test_schedule_write_identical_is_noop_blob(hass):
    """Writing the current slots back yields the exact same blob (safe no-op)."""
    coord, _ = _coord(hass, REAL)
    await coord.async_refresh()
    await coord.async_write_slots(coord.data["slots"])
    assert coord._client.issued[-1][2] == REAL


async def test_boost_on_suspends_timed_schedules(hass, monkeypatch):
    """Turning Boost (slot 0) on engages boost AND clears every timed slot,
    remembering the active ones so they can be restored later."""
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch
    coord, _ = _coord(hass, REAL)  # slot0=boost, slots1-4 active timed
    await coord.async_refresh()
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep",
        lambda *a, **k: _noop_async(),
    )
    boost = IntexScheduleSlotSwitch(coord, "saltid", 0)
    monkeypatch.setattr(boost, "async_write_ha_state", lambda: None)

    await boost.async_turn_on()

    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    assert decoded[0]["active"] is True and decoded[0]["on"] == 0   # boost engaged
    assert all(not decoded[i]["active"] for i in range(1, 7))       # timed all off
    assert set(boost._suspended) == {"1", "2", "3", "4"}            # remembered


async def test_boost_off_restores_suspended_schedules(hass, monkeypatch):
    """Turning Boost off clears the boost slot and restores the suspended timed
    schedules to their original slots."""
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch
    only_boost = schedule.set_slot(schedule.decode_schedules(""), 0, on=False, duration=48)
    coord, _ = _coord(hass, schedule.encode_schedules(only_boost))
    await coord.async_refresh()
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep",
        lambda *a, **k: _noop_async(),
    )
    boost = IntexScheduleSlotSwitch(coord, "saltid", 0)
    monkeypatch.setattr(boost, "async_write_ha_state", lambda: None)
    boost._suspended = {
        "1": {"month": 6, "date": 8, "hour": 3, "minute": 0,
              "duration": 3, "days": 255, "on": 1, "pad": 0}
    }

    await boost.async_turn_off()

    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    assert decoded[0]["active"] is False                       # boost cleared
    assert decoded[1]["active"] is True and decoded[1]["hour"] == 3  # restored
    assert boost._suspended == {}


async def test_boost_double_on_keeps_suspended(hass, monkeypatch):
    """A second Boost turn-on (timed slots already cleared) must NOT wipe the
    previously suspended schedules with an empty snapshot."""
    from custom_components.intex_pool.switch import IntexScheduleSlotSwitch
    only_boost = schedule.set_slot(schedule.decode_schedules(""), 0, on=False, duration=48)
    coord, _ = _coord(hass, schedule.encode_schedules(only_boost))  # no active timed slots
    await coord.async_refresh()
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep",
        lambda *a, **k: _noop_async(),
    )
    boost = IntexScheduleSlotSwitch(coord, "saltid", 0)
    monkeypatch.setattr(boost, "async_write_ha_state", lambda: None)
    kept = {"1": {"month": 6, "date": 8, "hour": 3, "minute": 0,
                  "duration": 3, "days": 255, "on": 1, "pad": 0}}
    boost._suspended = {k: dict(v) for k, v in kept.items()}

    await boost.async_turn_on()  # second turn-on; nothing to snapshot

    assert boost._suspended == kept  # preserved, not overwritten


async def _noop_async():
    return None
