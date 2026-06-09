"""Switch platform (saltwater power/chlorination, Tuya pump on/off)."""
from __future__ import annotations

from dataclasses import replace

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode, schedule
from .const import (
    CONF_PUMP_MODE,
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
)
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1
SALT_POWER_DP = "104"


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
            desc = replace(desc, source=str(pump_cfg.get("on_dp", DEFAULT_PUMP_ON_DP)))
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
        try:
            await self.coordinator.async_set_dp(self.entity_description.source, value)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to set {self.entity_id}: {err}") from err


class IntexPumpAutoSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Auto mode: run the linked pump only while the saltwater system is on.

    Driven by the saltwater coordinator (DP104 = power). When this switch is on,
    the configured pump switch is turned on whenever the saltwater system is on
    and off when it is off. When off, the pump is left under manual control.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "pump_auto"
    _attr_icon = "mdi:autorenew"

    def __init__(self, salt_coordinator, salt_device_id: str, pump_switch: str, entry) -> None:
        super().__init__(salt_coordinator)
        self._pump_switch = pump_switch
        self._attr_unique_id = f"{salt_device_id}_pump_auto"
        self._attr_is_on = False
        self._attr_device_info = pump_device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == "on"
        if self._attr_is_on:
            await self._sync()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._attr_is_on:
            self.hass.async_create_task(self._sync())
        super()._handle_coordinator_update()

    async def _sync(self) -> None:
        if not self._pump_switch:
            return
        salt_on = bool(self.coordinator.data and self.coordinator.data.get(SALT_POWER_DP))
        await self.hass.services.async_call(
            "switch", "turn_on" if salt_on else "turn_off",
            {"entity_id": self._pump_switch}, blocking=False,
        )

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()
        await self._sync()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()


class IntexScheduleSlotSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """One toggle per saltwater schedule slot.

    On = the slot has an active schedule. Turning it off remembers the schedule
    and clears the slot; turning it back on restores the remembered schedule.
    The schedule details are exposed as attributes (and shown on the card).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id: str, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._remembered: dict | None = None
        # Slot 0 is the device's Boost cycle (on=0, long duration, no start time).
        if index == 0:
            self._attr_translation_key = "boost_slot"
            self._attr_icon = "mdi:rocket-launch"
        else:
            self._attr_translation_key = "schedule_slot"
            self._attr_icon = "mdi:calendar-clock"
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
        if last and isinstance(last.attributes.get("remembered"), dict):
            self._remembered = dict(last.attributes["remembered"])

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
        return {
            **{k: slot.get(k) for k in schedule.FIELDS[:7]},
            "summary": schedule.summarize(slot) if active else None,
            "mode": schedule.mode_of(slot) if active else None,
            "remembered": self._remembered,
        }

    def _slots(self) -> list[dict]:
        return (self.coordinator.data or {}).get("slots") or schedule.decode_schedules("")

    async def async_turn_off(self, **kwargs) -> None:
        slots = self._slots()
        slot = slots[self._index]
        if slot.get("active"):
            self._remembered = {f: int(slot.get(f, 0)) for f in schedule.FIELDS}
        new = schedule.set_slot(slots, self._index, clear=True)
        await self.coordinator.async_write_slots(new)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        # Restore the remembered schedule, or create a sensible default the user
        # can then edit. Slot 0 defaults to a Boost cycle (on=0, long duration,
        # no start time); the timed slots default to a daily run.
        if self._index == 0:
            default = {"on": 0, "hour": 0, "minute": 0, "duration": 48, "days": 0}
        else:
            default = {"on": 1, "hour": 12, "minute": 0, "duration": 2, "days": 0xFF}
        r = self._remembered or default
        new = schedule.set_slot(
            self._slots(), self._index,
            on=bool(r.get("on")), hour=r.get("hour"), minute=r.get("minute"),
            duration=r.get("duration"), month=r.get("month"), date=r.get("date"),
            days=r.get("days"),
        )
        await self.coordinator.async_write_slots(new)
        self.async_write_ha_state()
