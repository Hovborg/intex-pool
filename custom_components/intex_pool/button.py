"""Button platform (force a fresh sensor measurement; pump Quick Run)."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import schedule
from .const import (
    BUTTONS,
    CONF_QUICK_RUN_HOURS,
    DEFAULT_QUICK_RUN_HOURS,
    DEVICE_PUMP,
    QUICK_RUN_SLOT,
)
from .entity import (
    IntexPoolEntity,
    coordinator_for,
    device_id_for,
    device_info_for,
    write_slots_guarded,
)
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[ButtonEntity] = []
    for desc in BUTTONS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexButton(coordinator, desc, device_id))

    pump_id = device_id_for(entry, DEVICE_PUMP)
    if data.pump_schedule is not None and pump_id is not None:
        entities.append(IntexPumpQuickRunButton(data.pump_schedule, entry, pump_id))

    async_add_entities(entities)


class IntexButton(IntexPoolEntity, ButtonEntity):
    async def async_press(self) -> None:
        # Device-aware write: a local coordinator (salt/pump) writes the DP over
        # the LAN (async_set_dp), a cloud coordinator (sensor) issues a property
        # (async_issue). This keeps the sensor refresh button on the cloud path
        # while the salt re-test button hits the local device.
        source = self.entity_description.source
        try:
            if hasattr(self.coordinator, "async_set_dp"):
                await self.coordinator.async_set_dp(source, True)
            else:
                await self.coordinator.async_issue(source, True)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to press {self.entity_id}: {err}") from err


class IntexPumpQuickRunButton(CoordinatorEntity, ButtonEntity):
    """Run the sand-filter pump right now for the configured Quick Run duration.

    Writes a genuine one-time entry (``days=0`` + today's date) into
    ``QUICK_RUN_SLOT``, matching the encoding the pump's own app uses for a
    one-off run (``on=1`` + a specific date) — NOT the saltwater
    chlorinator's ``on=0``/"Boost" encoding, which the Tuya thing-model ties
    specifically to chlorinator hardware (see ``IntexScheduleSlotSwitch``'s
    ``_is_boost`` docstring) and does not apply to the pump.

    A plain manual on/off (the ``pump``/``pump_filter`` switches) has no
    duration parameter at all and always falls back to the device's own
    fixed default run time — this button is the only way from Home Assistant
    to make the pump run for a specific, arbitrary duration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "quick_run"

    def __init__(self, coordinator, entry: IntexPoolConfigEntry, device_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{device_id}_quick_run"
        self._attr_device_info = device_info_for(DEVICE_PUMP, device_id)

    async def async_press(self) -> None:
        # Explicit None-check, NOT `stored or DEFAULT` — see the matching
        # note on IntexPumpQuickRunHoursNumber.native_value in number.py.
        raw = self._entry.options.get(CONF_QUICK_RUN_HOURS)
        if raw is None:
            hours = DEFAULT_QUICK_RUN_HOURS
        else:
            try:
                hours = float(raw)
            except (TypeError, ValueError):
                hours = DEFAULT_QUICK_RUN_HOURS
        # Local wall-clock time, NOT UTC — the schedule blob stores hour/
        # minute as the device's own local time, and dt_util.now() is HA's
        # canonical timezone-aware "now" (unlike a naive datetime.utcnow()).
        #
        # Rounded up (not "now") because the write itself isn't instant:
        # ScheduleCoordinator.async_write_slots() waits 5s for the cloud write
        # to settle before returning, on top of normal network latency. A
        # start time already in the past by the time Tuya applies it simply
        # never runs — silently. A naive "+1 minute, truncate to :00" is NOT
        # enough: pressed at :59, that only buys ~1s. Add 2 minutes BEFORE
        # truncating instead — pressed at :00 gives the full 2-minute buffer;
        # pressed at :59 (the worst case) still gives just over 1 full
        # minute, comfortably covering the write's real-world latency.
        target = (dt_util.now() + timedelta(minutes=2)).replace(second=0, microsecond=0)
        slots = (self.coordinator.data or {}).get("slots") or schedule.decode_schedules("")
        new = schedule.set_slot(
            slots, QUICK_RUN_SLOT,
            on=True, hour=target.hour, minute=target.minute,
            month=target.month, date=target.day,
            duration=round(hours), days=0,
        )
        await write_slots_guarded(self.coordinator, new, self.entity_id)
