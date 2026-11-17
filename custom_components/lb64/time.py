"""Wake-up time and wind-down time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LB64ConfigEntry, LB64Coordinator
from .entity import LB64Entity
from .timers import sleep_command, wake_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LB64TimeDescription(TimeEntityDescription):
    """A time of day on the lamp."""

    value_fn: Callable[[dict[str, Any]], str]
    command_fn: Callable[[dict[str, Any], str], str]


TIMES = (
    # The moment the sunrise is complete.
    LB64TimeDescription(
        key="wake_time",
        translation_key="wake_time",
        value_fn=lambda lamp: lamp["wake"]["time"],
        command_fn=lambda lamp, value: wake_command(lamp, time=value),
    ),
    # The moment the lamp is off.
    LB64TimeDescription(
        key="sleep_time",
        translation_key="sleep_time",
        value_fn=lambda lamp: lamp["sleep"]["time"],
        command_fn=lambda lamp, value: sleep_command(lamp, time=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: LB64ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the times."""
    async_add_entities(LB64Time(entry.runtime_data, description) for description in TIMES)


class LB64Time(LB64Entity, TimeEntity):
    """A time of day on the lamp (the lamp's local time)."""

    entity_description: LB64TimeDescription

    def __init__(self, coordinator: LB64Coordinator, description: LB64TimeDescription) -> None:
        """Initialize."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> time:
        """Return the time."""
        hours, minutes = self.entity_description.value_fn(self.lamp).split(":")
        return time(int(hours), int(minutes))

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        await self.coordinator.async_command(self.entity_description.command_fn(self.lamp, f"{value.hour:02d}:{value.minute:02d}"))
