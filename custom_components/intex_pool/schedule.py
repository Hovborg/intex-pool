"""Decode / encode the saltwater system's schedule blob (``skdl_salt`` / DP116).

The schedule is a base64-encoded raw value made of **7 fixed 8-byte slots**.
Field order is confirmed by the device's Tuya thing-model (DP116 ``skdl_salt``,
description: "month date hour minute worktime week control(0/1) Null"):

* ``duration`` = *worktime* in hours
* ``days``     = *week* bitmask — bit7 (0x80) set = weekly repeat; bits6-0 pick
  the weekday for a one-time entry. ``0xFF`` = repeat every day.
* ``on``       = *control* (1 = timed run; 0 with a long worktime = Boost cycle,
  reported back by the device as ``working_indicator == "boost"``)

Decode→encode round-trips byte-for-byte (verified against the live QS1600 Plus
2026-06-09), so the format is reliable.

No Home Assistant imports — pure functions, unit-testable in isolation.
"""
from __future__ import annotations

import base64
from typing import Any

SLOT_COUNT = 7
SLOT_SIZE = 8
FIELDS = ("month", "date", "hour", "minute", "duration", "days", "on", "pad")


def decode_schedules(b64: str | None) -> list[dict[str, Any]]:
    """Decode the base64 blob into 7 slot dicts (always returns 7)."""
    data = base64.b64decode(b64) if b64 else b""
    slots: list[dict[str, Any]] = []
    for i in range(SLOT_COUNT):
        chunk = data[i * SLOT_SIZE : i * SLOT_SIZE + SLOT_SIZE]
        chunk = chunk + bytes(SLOT_SIZE - len(chunk))  # pad short/empty
        rec = {f: chunk[j] for j, f in enumerate(FIELDS)}
        rec["active"] = any(chunk[:7])
        slots.append(rec)
    return slots


def encode_schedules(slots: list[dict[str, Any]]) -> str:
    """Encode up to 7 slot dicts back into the base64 blob (always 56 bytes)."""
    out = bytearray()
    for i in range(SLOT_COUNT):
        rec = slots[i] if i < len(slots) else {}
        out += bytes([int(rec.get(f, 0)) & 0xFF for f in FIELDS])
    return base64.b64encode(bytes(out)).decode()


def active_schedules(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in slots if s.get("active")]


DAYS_EVERY = 0xFF  # days mask = every day


def mode_of(slot: dict[str, Any]) -> str:
    """Best-effort mode label. The ``on`` byte = 1 for a timed run; = 0 with a
    long duration is the device's **Boost** cycle (per the app). Inferred."""
    return "on" if slot.get("on") else "boost"


def summarize(slot: dict[str, Any]) -> str:
    """Human-readable one-liner, e.g. ``Daily 03:00 · 3h · on`` / ``06-09 22:00 · 2h · on``."""
    h, m = int(slot.get("hour", 0)), int(slot.get("minute", 0))
    when = (
        f"Daily {h:02d}:{m:02d}"
        if slot.get("days") == DAYS_EVERY
        else f"{int(slot.get('month', 0)):02d}-{int(slot.get('date', 0)):02d} {h:02d}:{m:02d}"
    )
    return f"{when} · {int(slot.get('duration', 0))}h · {mode_of(slot)}"


def set_slot(
    slots: list[dict[str, Any]],
    index: int,
    *,
    on: bool | None = None,
    hour: int | None = None,
    minute: int | None = None,
    duration: int | None = None,
    month: int | None = None,
    date: int | None = None,
    days: int | None = None,
    clear: bool = False,
) -> list[dict[str, Any]]:
    """Return a new slot list with slot *index* updated (or cleared)."""
    if not 0 <= index < SLOT_COUNT:
        raise ValueError(f"slot index must be 0-{SLOT_COUNT - 1}")
    out = [dict(s) for s in decode_schedules(encode_schedules(slots))]  # normalize to 7
    if clear:
        out[index] = {f: 0 for f in FIELDS} | {"active": False}
        return out
    rec = out[index]
    for key, val in (
        ("on", 1 if on else 0 if on is not None else None),
        ("hour", hour), ("minute", minute), ("duration", duration),
        ("month", month), ("date", date), ("days", days),
    ):
        if val is not None:
            rec[key] = int(val) & 0xFF
    rec["active"] = any(rec.get(f, 0) for f in FIELDS[:7])
    return out
