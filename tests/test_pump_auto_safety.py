"""Unknown chlorination state must not be turned into a pump-off command."""
from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.intex_pool import switch as switch_module
from custom_components.intex_pool.switch import PUMP_AFTERRUN_S, IntexPumpAutoSwitch


def auto_switch(hass, data, available=True):
    entry = MockConfigEntry(domain="intex_pool", data={})
    coordinator = SimpleNamespace(data=data, last_update_success=available)
    switch = IntexPumpAutoSwitch(coordinator, "test-salt", "switch.test_pump", entry)
    switch.hass = hass
    switch.entity_id = "switch.test_auto"
    switch._attr_is_on = True
    return switch


@pytest.mark.parametrize("data,available", [({}, True), ({"103": None}, True), ({"103": False}, False)])
async def test_unknown_production_does_not_stop_pump(hass, data, available):
    calls = async_mock_service(hass, "switch", "turn_off")
    switch = auto_switch(hass, data, available)
    await switch._sync()
    assert not calls


async def test_unknown_production_cancels_pending_stop(hass):
    switch = auto_switch(hass, {})
    cancelled = []
    switch._last_prod = True
    switch._off_unsub = lambda: cancelled.append(True)
    await switch._sync()
    assert cancelled == [True]
    assert switch._last_prod is True


async def test_auto_switch_cannot_call_itself(hass):
    calls = async_mock_service(hass, "switch", "turn_on")
    switch = auto_switch(hass, {"103": True})
    switch._pump_switch = switch.entity_id
    await switch._sync()
    assert not calls


async def test_disabled_auto_does_not_run_queued_sync(hass):
    calls = async_mock_service(hass, "switch", "turn_on")
    switch = auto_switch(hass, {"103": True})
    switch._attr_is_on = False
    await switch._sync()
    assert not calls


async def test_poll_during_queued_stop_does_not_restart_afterrun(hass, monkeypatch):
    calls = async_mock_service(hass, "switch", "turn_off")
    timers = record_timers(monkeypatch)
    switch = auto_switch(hass, {"103": True})
    await switch._sync()
    switch.coordinator.data = {"103": False}
    await switch._sync()
    queued = []
    # Control the interleaving: HA otherwise eagerly finishes the service before
    # the following poll, which is a different (ordinary steady-state) case.
    with monkeypatch.context() as patch:
        patch.setattr(hass, "async_create_task", lambda coroutine: queued.append(coroutine))
        timers[0]["callback"](None)
        await switch._sync()
    assert len(timers) == 1
    assert len(queued) == 1
    await queued[0]
    assert len(calls) == 1
    assert switch._off_unsub is None


@pytest.mark.parametrize("value", ["unknown", "unavailable", "bad", 2, -1, [], {}])
async def test_invalid_production_never_controls_pump(hass, value):
    on_calls = async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    switch = auto_switch(hass, {"103": value})
    await switch._sync()
    assert not on_calls and not off_calls


@pytest.mark.parametrize("value,producing", [
    (True, True), (False, False), (1, True), (0, False),
    ("true", True), ("false", False), ("on", True), ("off", False),
    ("1", True), ("0", False),
])
async def test_known_production_representations(hass, value, producing):
    on_calls = async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    switch = auto_switch(hass, {"103": value})
    await switch._sync()
    assert len(on_calls) == int(producing)
    assert len(off_calls) == int(not producing)


def record_timers(monkeypatch):
    timers = []

    def schedule(hass, delay, callback):
        timer = {"delay": delay, "callback": callback, "cancelled": False}
        timers.append(timer)

        def cancel():
            timer["cancelled"] = True

        return cancel

    monkeypatch.setattr(switch_module, "async_call_later", schedule)
    return timers


async def test_interrupted_afterrun_resumes_full_hour_when_false_recovers(hass, monkeypatch):
    on_calls = async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    timers = record_timers(monkeypatch)
    switch = auto_switch(hass, {"103": True})
    await switch._sync()
    assert on_calls
    switch.coordinator.data = {"103": False}
    await switch._sync()
    assert len(timers) == 1
    assert switch._last_prod is False
    switch.coordinator.data = {}
    await switch._sync()
    assert timers[0]["cancelled"]
    assert not off_calls
    switch.coordinator.data = {"103": False}
    await switch._sync()
    assert len(timers) == 2
    assert timers[1]["delay"] == PUMP_AFTERRUN_S == 3600
    assert not off_calls
    # A cancelled callback may already have been queued: it must not consume
    # the newly started full after-run window.
    timers[0]["callback"](None)
    await hass.async_block_till_done()
    assert not off_calls
    timers[1]["callback"](None)
    await hass.async_block_till_done()
    assert len(off_calls) == 1


async def test_repeated_enable_preserves_pending_afterrun(hass, monkeypatch):
    async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    timers = record_timers(monkeypatch)
    switch = auto_switch(hass, {"103": True})
    await switch._sync()
    switch.coordinator.data = {"103": False}
    await switch._sync()
    monkeypatch.setattr(switch, "async_write_ha_state", lambda: None)
    await switch.async_turn_on()
    assert not off_calls
    assert len(timers) == 1
    assert not timers[0]["cancelled"]


@pytest.mark.parametrize("data", [{}, {"103": True}])
async def test_timer_callback_rechecks_current_production(hass, monkeypatch, data):
    async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    timers = record_timers(monkeypatch)
    switch = auto_switch(hass, {"103": True})
    await switch._sync()
    switch.coordinator.data = {"103": False}
    await switch._sync()
    switch.coordinator.data = data
    timers[0]["callback"](None)
    await hass.async_block_till_done()
    assert not off_calls


@pytest.mark.parametrize("data", [{}, {"103": True}])
async def test_queued_timer_stop_rechecks_production_before_service(hass, monkeypatch, data):
    async_mock_service(hass, "switch", "turn_on")
    off_calls = async_mock_service(hass, "switch", "turn_off")
    timers = record_timers(monkeypatch)
    switch = auto_switch(hass, {"103": True})
    await switch._sync()
    switch.coordinator.data = {"103": False}
    await switch._sync()
    queued = []
    with monkeypatch.context() as patch:
        patch.setattr(hass, "async_create_task", lambda coroutine: queued.append(coroutine))
        timers[0]["callback"](None)
    assert len(queued) == 1
    switch.coordinator.data = data
    await queued[0]
    assert not off_calls
