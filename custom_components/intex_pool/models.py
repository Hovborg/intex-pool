"""Runtime data container stored on the config entry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import (
        PumpCoordinator,
        SaltCoordinator,
        ScheduleCoordinator,
        SensorCoordinator,
    )


@dataclass
class IntexPoolData:
    """Active coordinators for a config entry (any subset may be present)."""

    salt: SaltCoordinator | None = None
    sensor: SensorCoordinator | None = None
    pump: PumpCoordinator | None = None
    schedule: ScheduleCoordinator | None = None
    # The analyzer's own measurement-window schedule (skdl_orpph, read-only).
    analyzer_schedule: ScheduleCoordinator | None = None
    pump_schedule: ScheduleCoordinator | None = None


type IntexPoolConfigEntry = ConfigEntry[IntexPoolData]
