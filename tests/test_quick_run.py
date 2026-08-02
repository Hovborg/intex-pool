"""Pump Quick Run button + duration number (fake cloud, no network)."""
from datetime import UTC, datetime

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
    """Pressing Quick Run writes today's date + now's time into the reserved
    slot, on=1, days=0 — a genuine one-shot, not a recurring program."""
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
    assert (slot["hour"], slot["minute"]) == (14, 30)
    assert (slot["month"], slot["date"]) == (8, 15)
    assert slot["duration"] == 3
    assert slot["days"] == 0  # one-time, not a recurring daily program


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
