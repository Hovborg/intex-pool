"""Select platform (self-clean cycle, temperature unit)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SELECTS
from .entity import IntexPoolEntity, coordinator_for, device_id_for
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[IntexSelect] = []
    for desc in SELECTS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexSelect(coordinator, desc, device_id))
    async_add_entities(entities)


class IntexSelect(IntexPoolEntity, SelectEntity):
    def __init__(self, coordinator, description, device_id: str) -> None:
        super().__init__(coordinator, description, device_id)
        # de-duplicate while preserving order
        self._attr_options = list(dict.fromkeys(description.value_map.values()))
        # option -> raw DP value (last raw wins, so bool overrides int 0/1)
        self._reverse = {opt: raw for raw, opt in description.value_map.items()}

    @property
    def current_option(self) -> str | None:
        return self.entity_description.value_map.get(self._raw)

    async def async_select_option(self, option: str) -> None:
        if option not in self._reverse:
            raise HomeAssistantError(f"Unknown option {option!r} for {self.entity_id}")
        try:
            await self.coordinator.async_set_dp(
                self.entity_description.source, self._reverse[option]
            )
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to set {self.entity_id}: {err}") from err
