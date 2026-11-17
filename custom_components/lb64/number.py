"""Speed of the showing preset, and the boost."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SPEED_MAX
from .coordinator import LB64ConfigEntry, LB64Coordinator
from .entity import LB64Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LB64NumberDescription(NumberEntityDescription):
    """A number on the lamp."""

    value_fn: Callable[[dict[str, Any]], int]
    command: str


NUMBERS = (
    # Animation speed of the preset that is showing; the lamp remembers it per preset.
    # 0 = frozen, 50 = normal, 100 = about 6x, 200 = about 24x.
    LB64NumberDescription(
        key="speed",
        translation_key="speed",
        native_min_value=0,
        native_max_value=SPEED_MAX,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda lamp: lamp["speed"],
        command="PRESET:SPEED",
    ),
    # Boost past full colour: brighter, paler. 0 = off.
    LB64NumberDescription(
        key="gain",
        translation_key="gain",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        value_fn=lambda lamp: lamp["gain"],
        command="GAIN",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: LB64ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the numbers."""
    async_add_entities(LB64Number(entry.runtime_data, description) for description in NUMBERS)


class LB64Number(LB64Entity, NumberEntity):
    """A number on the lamp."""

    entity_description: LB64NumberDescription

    def __init__(self, coordinator: LB64Coordinator, description: LB64NumberDescription) -> None:
        """Initialize."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        """Return the value."""
        return self.entity_description.value_fn(self.lamp)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.coordinator.async_command(f"{self.entity_description.command}:{round(value)}")
