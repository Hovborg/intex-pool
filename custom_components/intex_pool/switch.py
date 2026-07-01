"""Switch platform (saltwater power/chlorination, Tuya pump on/off)."""
from __future__ import annotations

import logging
from dataclasses import replace

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode, schedule
from .const import (
    CONF_PUMP_MODE,
    CONF_PUMP_ON_DP,
    CONF_PUMP_SWITCH,
    DEFAULT_PUMP_ON_DP,
    DEVICE_META,
    DEVICE_PUMP,
    DEVICE_SALT,
    DOMAIN,
    MANUFACTURER,
    PUMP_MODE_ENTITY,
    PUMP_MODE_TUYA,
    SWITCHES,
)
from .entity import (
    IntexPoolEntity,
    coordinator_for,
    device_id_for,
    pump_device_info,
    write_slots_guarded,
)
from .models import IntexPoolConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
# The pump interlock keys on DP103 (chlorine PRODUCTION), not DP104 (master
# power): power routinely stays on 24/7 while production cycles, so keying on
# power would run the pump constantly. The manual also requires the filter
# pump to keep circulating a while after chlorination stops.
SALT_PROD_DP = "103"
PUMP_AFTERRUN_S = 3600


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    pump_cfg = entry.data.get("pump") or {}
    entities: list[SwitchEntity] = []
    for desc in SWITCHES:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        if desc.device == DEVICE_PUMP:
            if pump_cfg.get(CONF_PUMP_MODE) != PUMP_MODE_TUYA:
                continue
            # resolve the configured on/off DP for the Tuya pump
            desc = replace(desc, source=str(pump_cfg.get(CONF_PUMP_ON_DP, DEFAULT_PUMP_ON_DP)))
        entities.append(IntexSwitch(coordinator, desc, device_id))

    # Pump auto mode: drive a linked (entity-mode) pump from the saltwater state,
    # so the pump runs only while the saltwater system is on.
    if (
        data.salt is not None
        and pump_cfg.get(CONF_PUMP_MODE) == PUMP_MODE_ENTITY
        and pump_cfg.get(CONF_PUMP_SWITCH)
    ):
        salt_id = device_id_for(entry, DEVICE_SALT)
        if salt_id is not None:
            entities.append(
                IntexPumpAutoSwitch(data.salt, salt_id, pump_cfg[CONF_PUMP_SWITCH], entry)
            )

    # One toggle switch per schedule slot (turn each schedule on/off).
    if data.schedule is not None:
        sched_salt_id = device_id_for(entry, DEVICE_SALT)
        if sched_salt_id is not None:
            entities.extend(
                IntexScheduleSlotSwitch(data.schedule, sched_salt_id, i)
                for i in range(schedule.SLOT_COUNT)
            )

    async_add_entities(entities)


class IntexSwitch(IntexPoolEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return decode.as_bool(self._raw)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        # Device-aware write: local coordinators (salt/Tuya pump) set the DP
        # over the LAN; cloud coordinators (water sensor) issue a property.
        source = self.entity_description.source
        try:
            if hasattr(self.coordinator, "async_set_dp"):
                await self.coordinator.async_set_dp(source, value)
            else:
                await self.coordinator.async_issue(source, value)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to set {self.entity_id}: {err}") from err


class IntexPumpAutoSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Auto mode: run the linked pump while chlorine is being produced.

    Driven by the saltwater coordinator (DP103 = chlorine production). While
    this switch is on, the configured pump switch is turned on whenever
    production runs, and turned off PUMP_AFTERRUN_S after production stops so
    the last chlorine batch still gets circulated. When off, the pump is left
    under manual control.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "pump_auto"

    def __init__(self, salt_coordinator, salt_device_id: str, pump_switch: str, entry) -> None:
        super().__init__(salt_coordinator)
        self._pump_switch = pump_switch
        self._attr_unique_id = f"{salt_device_id}_pump_auto"
        self._attr_is_on = False
        self._attr_device_info = pump_device_info(entry)
        self._sync_task = None
        self._off_unsub = None          # pending after-run timer
        self._last_prod: bool | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == "on"
        if not self._attr_is_on:
            return
        # The initial sync calls the switch service of ANOTHER integration —
        # during startup that platform may not be loaded yet, so defer until HA
        # is fully started. On a plain integration reload HA is already running.
        if self.hass.is_running:
            self.hass.async_create_task(self._sync())
        else:
            async def _on_started(_event) -> None:
                await self._sync()

            self.async_on_remove(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        # One sync at a time: rapid coordinator updates (poll + an explicit
        # refresh) must not stack concurrent service calls to the pump.
        if self._attr_is_on and (self._sync_task is None or self._sync_task.done()):
            self._sync_task = self.hass.async_create_task(self._sync())
        super()._handle_coordinator_update()

    async def _sync(self) -> None:
        if not self._pump_switch:
            return
        prod_on = bool(self.coordinator.data and self.coordinator.data.get(SALT_PROD_DP))
        was_on, self._last_prod = self._last_prod, prod_on
        if prod_on:
            self._cancel_afterrun()
            await self._pump_call(True)
        elif was_on:
            # Production just stopped: keep circulating, then stop the pump.
            if self._off_unsub is None:
                self._off_unsub = async_call_later(
                    self.hass, PUMP_AFTERRUN_S, self._afterrun_done
                )
        elif self._off_unsub is None:
            # Steady not-producing state with no after-run owed.
            await self._pump_call(False)

    @callback
    def _afterrun_done(self, _now) -> None:
        self._off_unsub = None
        if self._attr_is_on:
            self.hass.async_create_task(self._pump_call(False))

    def _cancel_afterrun(self) -> None:
        if self._off_unsub is not None:
            self._off_unsub()
            self._off_unsub = None

    async def _pump_call(self, on: bool) -> None:
        try:
            await self.hass.services.async_call(
                "switch", "turn_on" if on else "turn_off",
                {"entity_id": self._pump_switch}, blocking=True,
            )
        except Exception as err:  # noqa: BLE001 - auto-mode must never crash the update loop
            _LOGGER.warning(
                "Pump auto mode could not switch %s %s: %s",
                self._pump_switch, "on" if on else "off", err,
            )

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self._last_prod = None  # evaluate afresh (no stale after-run owed)
        self.async_write_ha_state()
        await self._sync()

    async def async_turn_off(self, **kwargs) -> None:
        self._cancel_afterrun()
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_afterrun()
        await super().async_will_remove_from_hass()


def _slot_fields(slot: dict) -> dict:
    """Snapshot a slot's writable fields as plain ints (for remember/restore)."""
    return {f: int(slot.get(f, 0)) for f in schedule.FIELDS}


def _apply(slots: list[dict], index: int, rec: dict) -> list[dict]:
    """Write a remembered/default record into slot *index*."""
    return schedule.set_slot(
        slots, index,
        on=bool(rec.get("on")), hour=rec.get("hour"), minute=rec.get("minute"),
        duration=rec.get("duration"), month=rec.get("month"),
        date=rec.get("date"), days=rec.get("days"),
    )


class IntexScheduleSlotSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """One toggle per saltwater schedule slot.

    On = the slot has an active schedule. Turning it off remembers the schedule
    and clears the slot; turning it back on restores the remembered schedule.
    The schedule details are exposed as attributes (and shown on the card).

    Slot 0 is the device's **Boost** cycle. Turning Boost on additionally
    *suspends* (remembers + clears) the timed schedules so they don't fight the
    boost run; turning Boost off restores them — mirroring how the unit itself
    reverts to its normal schedule after a boost completes.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id: str, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._is_boost = index == 0
        self._remembered: dict | None = None
        # Timed schedules suspended while Boost is on: {slot_index_str: fields}.
        self._suspended: dict[str, dict] = {}
        if self._is_boost:
            self._attr_translation_key = "boost_slot"
        else:
            self._attr_translation_key = "schedule_slot"
            self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_unique_id = f"{device_id}_schedule_{index + 1}"
        meta = DEVICE_META[DEVICE_SALT]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=meta["name"],
            manufacturer=MANUFACTURER,
            model=meta["model"],
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if not last:
            return
        if isinstance(last.attributes.get("remembered"), dict):
            self._remembered = dict(last.attributes["remembered"])
        if self._is_boost and isinstance(last.attributes.get("suspended"), dict):
            self._suspended = {k: dict(v) for k, v in last.attributes["suspended"].items()}

    def _slot(self) -> dict | None:
        slots = (self.coordinator.data or {}).get("slots") or []
        return slots[self._index] if self._index < len(slots) else None

    @property
    def is_on(self) -> bool:
        slot = self._slot()
        return bool(slot and slot.get("active"))

    @property
    def extra_state_attributes(self) -> dict:
        slot = self._slot() or {}
        active = bool(slot.get("active"))
        attrs = {
            **{k: slot.get(k) for k in schedule.FIELDS[:7]},
            "summary": schedule.summarize(slot) if active else None,
            "mode": schedule.mode_of(slot) if active else None,
            "remembered": self._remembered,
        }
        if self._is_boost:
            attrs["suspended"] = self._suspended
        return attrs

    def _slots(self) -> list[dict]:
        return (self.coordinator.data or {}).get("slots") or schedule.decode_schedules("")

    async def async_turn_off(self, **kwargs) -> None:
        slots = self._slots()
        slot = slots[self._index]
        remembered = _slot_fields(slot) if slot.get("active") else self._remembered
        new = schedule.set_slot(slots, self._index, clear=True)
        restoring = self._is_boost and bool(self._suspended)
        if restoring:
            # Boost released: bring the suspended timed schedules back.
            for idx, rec in self._suspended.items():
                new = _apply(new, int(idx), rec)
        # Write FIRST — only commit the remembered/suspended bookkeeping once
        # the cloud write succeeded, so a failed write can't leave the entity
        # believing the slot was cleared/restored.
        await write_slots_guarded(self.coordinator, new, self.entity_id)
        self._remembered = remembered
        if restoring:
            self._suspended = {}
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        # Restore the remembered schedule, or create a sensible default the user
        # can then edit. Slot 0 defaults to a Boost cycle (on=0, long duration,
        # no start time); the timed slots default to a daily run.
        slots = self._slots()
        if self._is_boost:
            default = {"on": 0, "hour": 0, "minute": 0, "duration": 48, "days": 0}
        else:
            default = {"on": 1, "hour": 12, "minute": 0, "duration": 2, "days": 0xFF}
        new = _apply(slots, self._index, self._remembered or default)
        snapshot: dict[str, dict] | None = None
        if self._is_boost:
            # Suspend (remember + clear) every active timed schedule so the UI
            # shows them off and they don't run against the boost cycle. Only
            # overwrite the remembered set when there is actually something to
            # remember, so a second turn-on (timed slots already cleared) can't
            # wipe the suspended schedules.
            snapshot = {
                str(i): _slot_fields(slots[i])
                for i in range(1, schedule.SLOT_COUNT)
                if slots[i].get("active")
            }
            for i in range(1, schedule.SLOT_COUNT):
                new = schedule.set_slot(new, i, clear=True)
        # Write FIRST — commit the suspended snapshot only on success.
        await write_slots_guarded(self.coordinator, new, self.entity_id)
        if self._is_boost and snapshot:
            self._suspended = snapshot
        self.async_write_ha_state()
