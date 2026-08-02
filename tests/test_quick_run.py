"""Pump Quick Run button + duration number (fake cloud, no network)."""
from datetime import UTC, datetime

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intex_pool import schedule
from custom_components.intex_pool.button import IntexPumpQuickRunButton
from custom_components.intex_pool.const import (
    CONF_QUICK_RUN_HOURS,
    DEFAULT_QUICK_RUN_HOURS,
    DOMAIN,
    QUICK_RUN_SLOT,
)
from custom_components.intex_pool.coordinator import ScheduleCoordinator
from custom_components.intex_pool.number import IntexPumpQuickRunHoursNumber

SENSOR = {"region": "eu", "access_id": "a", "access_secret": "s", "device_id": "sdev"}
PUMP_TUYA = {"pump_mode": "tuya", "device_id": "pumpdev", "local_key": "k",
             "host": "1.2.3.5", "version": 3.5, "pump_on_dp": "1"}


class FakeCloudSched:
    def __init__(self, raw=""):
        self.raw = raw
        self.issued = []

    def properties(self, device_id):
        return {"skdl_filter": self.raw}

    def issue(self, device_id, code, value):
        self.issued.append((device_id, code, value))
        self.raw = value


async def _pump_coord(hass, raw=""):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    client = FakeCloudSched(raw)
    coord = ScheduleCoordinator(hass, entry, client, "pumpid", 600, code="skdl_filter")
    await coord.async_refresh()
    return coord, entry


async def _noop_sleep(*a, **k):
    return None


async def test_quick_run_button_writes_one_time_slot(hass, monkeypatch):
    """Pressing Quick Run writes today's date + now+2min into the reserved
    slot, on=1, days=0 — a genuine one-shot, not a recurring program. The
    buffer (not "now") guards against the write itself taking >0s to land —
    see the docstring on IntexPumpQuickRunButton.async_press."""
    coord, entry = await _pump_coord(hass)
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep", _noop_sleep
    )
    fixed_now = datetime(2026, 8, 15, 14, 30, tzinfo=UTC)
    monkeypatch.setattr(
        "custom_components.intex_pool.button.dt_util.now", lambda: fixed_now
    )
    hass.config_entries.async_update_entry(entry, options={CONF_QUICK_RUN_HOURS: 3})

    button = IntexPumpQuickRunButton(coord, entry, "pumpid")
    await button.async_press()

    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    slot = decoded[QUICK_RUN_SLOT]
    assert slot["active"] is True
    assert slot["on"] == 1
    assert (slot["hour"], slot["minute"]) == (14, 32)
    assert (slot["month"], slot["date"]) == (8, 15)
    assert slot["duration"] == 3
    assert slot["days"] == 0  # one-time, not a recurring daily program


async def test_quick_run_button_worst_case_still_leaves_a_full_minute(hass, monkeypatch):
    """Pressed in the last second of a minute (the tightest case): the
    written start time must still be more than one full minute in the
    future, not just "the next minute boundary" (which could be ~1s away —
    the exact gap codex flagged as too tight for the write's real latency)."""
    coord, entry = await _pump_coord(hass)
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep", _noop_sleep
    )
    now = datetime(2026, 8, 15, 14, 30, 59, tzinfo=UTC)
    monkeypatch.setattr("custom_components.intex_pool.button.dt_util.now", lambda: now)

    button = IntexPumpQuickRunButton(coord, entry, "pumpid")
    await button.async_press()

    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    slot = decoded[QUICK_RUN_SLOT]
    written = datetime(2026, 8, 15, slot["hour"], slot["minute"], tzinfo=UTC)
    assert (written - now).total_seconds() > 60


async def test_quick_run_button_rounds_up_across_hour_boundary(hass, monkeypatch):
    """The buffer must correctly roll over hour/date/month, not just wrap the
    minute field in isolation (a naive `minute + N` would break at :59 and
    again at midnight/month-end)."""
    coord, entry = await _pump_coord(hass)
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep", _noop_sleep
    )
    monkeypatch.setattr(
        "custom_components.intex_pool.button.dt_util.now",
        lambda: datetime(2026, 1, 31, 23, 59, tzinfo=UTC),
    )

    button = IntexPumpQuickRunButton(coord, entry, "pumpid")
    await button.async_press()

    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    slot = decoded[QUICK_RUN_SLOT]
    assert (slot["hour"], slot["minute"]) == (0, 1)
    assert (slot["month"], slot["date"]) == (2, 1)


async def test_quick_run_button_uses_default_hours_when_unset(hass, monkeypatch):
    coord, entry = await _pump_coord(hass)
    monkeypatch.setattr(
        "custom_components.intex_pool.coordinator.asyncio.sleep", _noop_sleep
    )
    monkeypatch.setattr(
        "custom_components.intex_pool.button.dt_util.now",
        lambda: datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )

    button = IntexPumpQuickRunButton(coord, entry, "pumpid")
    await button.async_press()

    decoded = schedule.decode_schedules(coord._client.issued[-1][2])
    assert decoded[QUICK_RUN_SLOT]["duration"] == DEFAULT_QUICK_RUN_HOURS


async def test_quick_run_hours_number_defaults_and_persists(hass, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    num = IntexPumpQuickRunHoursNumber(entry, "pumpid")
    num.hass = hass
    monkeypatch.setattr(num, "async_write_ha_state", lambda: None)
    assert num.native_value == DEFAULT_QUICK_RUN_HOURS
    assert num.unique_id == "pumpid_quick_run_hours"

    await num.async_set_native_value(5)

    assert entry.options[CONF_QUICK_RUN_HOURS] == 5
    assert num.native_value == 5.0


async def test_quick_run_slot_excluded_from_generic_pump_editors(hass, mock_tinytuya):
    """Slot 0 must not be double-exposed: a user's own recurring program in
    that slot (set via the generic "Schedule 1" switch/number/time entities,
    or the Tuya app) must not be silently overwritten the next time Quick Run
    fires. The fix is that the generic pump schedule editors skip index 0
    entirely — only the dedicated Quick Run button/number own that slot."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"has_sensor": True, "has_pump": True, "sensor": SENSOR, "pump": PUMP_TUYA},
        unique_id="uid-quick-run-reservation",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.pump_schedule is not None

    registry = er.async_get(hass)
    unique_ids = {
        reg.unique_id
        for reg in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    # Slot 0 ("schedule_1") must NOT get generic editors for the pump.
    assert "pumpdev_schedule_1" not in unique_ids
    assert "pumpdev_schedule_1_duration" not in unique_ids
    assert "pumpdev_schedule_1_start" not in unique_ids
    # Slots 1-6 ("schedule_2".."schedule_7") still do.
    for n in range(2, 8):
        assert f"pumpdev_schedule_{n}" in unique_ids
        assert f"pumpdev_schedule_{n}_duration" in unique_ids
        assert f"pumpdev_schedule_{n}_start" in unique_ids
    # Only the dedicated Quick Run entities own slot 0.
    assert "pumpdev_quick_run" in unique_ids
    assert "pumpdev_quick_run_hours" in unique_ids

    assert await hass.config_entries.async_unload(entry.entry_id)
