"""Button platform (force a fresh sensor measurement)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BUTTONS
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[IntexButton] = []
    for desc in BUTTONS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexButton(coordinator, desc, device_id))
    async_add_entities(entities)


class IntexButton(IntexPoolEntity, ButtonEntity):
    async def async_press(self) -> None:
        # Measurement requests share the repair flow's device-aware routing.
        source = self.entity_description.source
        try:
            if self.entity_description.key == "refresh":
                await self.coordinator.async_refresh_measure()
            elif hasattr(self.coordinator, "async_set_dp"):
                await self.coordinator.async_set_dp(source, True)
            else:
                await self.coordinator.async_issue(source, True)
        except Exception as err:
            raise HomeAssistantError(f"Failed to press {self.entity_id}: {err}") from err
