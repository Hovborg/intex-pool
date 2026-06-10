"""Event platform: discrete alarm/error transitions for logbook + automations.

The enum sensors (alarm / error code) show the *current* state; these event
entities fire once per *transition* so users get a logbook trail and can
trigger automations on "alarm changed" without templating against the enums.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import decode
from .const import DEVICE_SALT, DEVICE_SENSOR
from .entity import device_info_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 0

# Sentinel meaning "no value observed yet" (None is a real observation).
_UNSEEN = object()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[IntexTransitionEvent] = []

    salt_id = device_id_for(entry, DEVICE_SALT)
    if data.salt is not None and salt_id is not None:
        entities.append(
            IntexTransitionEvent(
                data.salt, DEVICE_SALT, salt_id, "alarm_event", "127",
                decode.normalize_alarm, decode.ALARM_OPTIONS,
            )
        )

    sensor_id = device_id_for(entry, DEVICE_SENSOR)
    if data.sensor is not None and sensor_id is not None:
        entities.append(
            IntexTransitionEvent(
                data.sensor, DEVICE_SENSOR, sensor_id, "error_event", "error_code",
                decode.normalize_error, decode.ERROR_OPTIONS,
            )
        )

    async_add_entities(entities)


class IntexTransitionEvent(CoordinatorEntity, EventEntity):
    """Fires an event whenever the watched enum value changes.

    The first observation after (re)start only seeds the baseline — an ongoing
    alarm doesn't re-fire on every restart; only real transitions do.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        device: str,
        device_id: str,
        translation_key: str,
        source: str,
        normalize: Callable[[Any], str | None],
        options: list[str],
    ) -> None:
        super().__init__(coordinator)
        self._source = source
        self._normalize = normalize
        self._last: Any = _UNSEEN
        self._attr_translation_key = translation_key
        self._attr_event_types = list(options)
        self._attr_unique_id = f"{device_id}_{translation_key}"
        self._attr_device_info = device_info_for(device, device_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Seed the baseline from current data so an ongoing state doesn't fire.
        self._last = self._current()

    def _current(self) -> str | None:
        data = self.coordinator.data or {}
        return self._normalize(data.get(self._source))

    @callback
    def _handle_coordinator_update(self) -> None:
        current = self._current()
        if self._last is _UNSEEN or self._last is None:
            # No real value observed yet. A None baseline happens when the
            # source property is absent from the first poll (the cloud only
            # reports properties the device has ever emitted) — the first
            # value to appear is an ongoing state, not a transition, so it
            # must seed silently instead of firing a spurious event.
            self._last = current
        elif current is not None and current != self._last:
            self._last = current
            self._trigger_event(current)
            self.async_write_ha_state()
        super()._handle_coordinator_update()
