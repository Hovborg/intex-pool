"""Tests for the saltwater schedule codec (pure, no HA)."""
import importlib.util
import pathlib

_P = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "intex_pool" / "schedule.py"
_spec = importlib.util.spec_from_file_location("intex_schedule", _P)
sched = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sched)

# The live device's actual blob (captured 2026-06-09).
REAL = "BgYJADAAAAAGCAMAA/8BAAYICgAC/wEABggOAAL/AQAGCRYAAgABAAAAAAAAAAAAAAAAAAAAAAA="


def test_round_trip_exact():
    slots = sched.decode_schedules(REAL)
    assert sched.encode_schedules(slots) == REAL


def test_decode_counts():
    slots = sched.decode_schedules(REAL)
    assert len(slots) == 7
    assert len(sched.active_schedules(slots)) == 5


def test_decode_fields_of_a_known_slot():
    slots = sched.decode_schedules(REAL)
    # slot index 1: month6 date8 03:00 dur3 days255 on
    s = slots[1]
    assert (s["month"], s["date"], s["hour"], s["minute"], s["duration"], s["days"], s["on"]) == (6, 8, 3, 0, 3, 255, 1)
    assert s["active"] is True


def test_boost_slot_mode():
    slots = sched.decode_schedules(REAL)
    boost = slots[0]  # on=0, duration 48 -> boost (per app)
    assert boost["on"] == 0 and boost["duration"] == 48
    assert sched.mode_of(boost) == "boost"


def test_summarize_daily_vs_onetime():
    slots = sched.decode_schedules(REAL)
    assert sched.summarize(slots[1]).startswith("Daily 03:00")   # days=255
    assert sched.summarize(slots[4]).startswith("06-09 22:00")   # days=0 one-time


def test_empty_blob():
    slots = sched.decode_schedules("")
    assert len(slots) == 7 and sched.active_schedules(slots) == []
    assert sched.encode_schedules(slots) == sched.encode_schedules([])


def test_set_slot_updates_only_target_and_round_trips_others():
    slots = sched.decode_schedules(REAL)
    updated = sched.set_slot(slots, 4, on=True, hour=23, minute=30, duration=4)
    assert (updated[4]["hour"], updated[4]["minute"], updated[4]["duration"], updated[4]["on"]) == (23, 30, 4, 1)
    # other slots unchanged
    assert sched.encode_schedules(updated[:4]) == sched.encode_schedules(slots[:4])


def test_set_slot_clear():
    slots = sched.decode_schedules(REAL)
    updated = sched.set_slot(slots, 1, clear=True)
    assert updated[1]["active"] is False
    assert all(updated[1][f] == 0 for f in ("month", "date", "hour", "duration", "on"))


def test_set_slot_index_bounds():
    import pytest
    with pytest.raises(ValueError):
        sched.set_slot([], 7)
