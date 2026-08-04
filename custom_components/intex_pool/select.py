"""Select platform (self-clean cycle, temperature unit, volume unit)."""
from __future__ import annotations

from typing import ClassVar

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_PUMP_MODE,
    CONF_PUMP_SWITCH,
    CONF_VOLUME_UNIT,
    DEVICE_PUMP,
    DEVICE_SALT,
    PUMP_MODE_ENTITY,
    SELECTS,
    SIGNAL_OPTIONS_UPDATED,
    VOLUME_UNIT_GALLON,
    VOLUME_UNIT_LITER,
)
from .entity import (
    IntexPoolEntity,
    coordinator_for,
    device_id_for,
    device_info_for,
    pump_device_info,
)
from .models import IntexPoolConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntexPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: list[SelectEntity] = []
    for desc in SELECTS:
        coordinator = coordinator_for(data, desc.device)
        if coordinator is None:
            continue
        device_id = device_id_for(entry, desc.device)
        if device_id is None:
            continue
        entities.append(IntexSelect(coordinator, desc, device_id))

    # Pick the linked pump's switch right on the (virtual) pump device page.
    if (entry.data.get(DEVICE_PUMP) or {}).get(CONF_PUMP_MODE) == PUMP_MODE_ENTITY:
        entities.append(IntexPumpSwitchSelect(entry))

    # Volume unit for the pool-volume entity + salt advisor.
    salt_id = device_id_for(entry, DEVICE_SALT)
    if data.salt is not None and salt_id is not None:
        entities.append(IntexVolumeUnitSelect(entry, salt_id))

    async_add_entities(entities)


class IntexVolumeUnitSelect(SelectEntity):
    """Unit for the pool volume (litres or US gallons) — stored in options.

    Changing the unit does NOT convert the stored number: the Pool volume
    value is interpreted in whichever unit is selected here.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "volume_unit"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options: ClassVar[list[str]] = [VOLUME_UNIT_LITER, VOLUME_UNIT_GALLON]
    _attr_should_poll = False

    def __init__(self, entry: IntexPoolConfigEntry, device_id: str) -> None:
        self._entry = entry
        self._attr_unique_id = f"{device_id}_volume_unit"
        self._attr_device_info = device_info_for(DEVICE_SALT, device_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_OPTIONS_UPDATED.format(self._entry.entry_id),
                self._refresh,
            )
        )

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        return self._entry.options.get(CONF_VOLUME_UNIT, VOLUME_UNIT_LITER)

    async def async_select_option(self, option: str) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, CONF_VOLUME_UNIT: option}
        )
        # Nudge siblings (the Pool volume number shows this unit).
        async_dispatcher_send(
            self.hass, SIGNAL_OPTIONS_UPDATED.format(self._entry.entry_id)
        )
        self.async_write_ha_state()


class IntexPumpSwitchSelect(SelectEntity):
    """Choose which switch drives the linked sand-filter pump (changes + reloads)."""

    _attr_has_entity_name = True
    _attr_translation_key = "pump_switch_select"

    def __init__(self, entry: IntexPoolConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_pump_switch_select"
        self._attr_device_info = pump_device_info(entry)

    @property
    def options(self) -> list[str]:
        return sorted(self.hass.states.async_entity_ids("switch"))

    @property
    def current_option(self) -> str | None:
        cur = (self._entry.data.get(DEVICE_PUMP) or {}).get(CONF_PUMP_SWITCH)
        # O(1) existence check — don't rebuild the full options list here.
        return cur if cur and self.hass.states.get(cur) is not None else None

    async def async_select_option(self, option: str) -> None:
        pump = {**(self._entry.data.get(DEVICE_PUMP) or {}), CONF_PUMP_SWITCH: option}
        self.hass.config_entries.async_update_entry(
            self._entry, data={**self._entry.data, DEVICE_PUMP: pump}
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._entry.entry_id)
        )


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
        # Device-aware write: local coordinators (salt) write the DP over the LAN
        # (async_set_dp); cloud coordinators (sensor) issue a property (async_issue).
        source = self.entity_description.source
        raw = self._reverse[option]
        try:
            if hasattr(self.coordinator, "async_set_dp"):
                await self.coordinator.async_set_dp(source, raw)
            else:
                await self.coordinator.async_issue(source, raw)
        except Exception as err:
            raise HomeAssistantError(f"Failed to set {self.entity_id}: {err}") from err
