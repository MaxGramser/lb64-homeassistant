"""Wake-up light, wind-down and schedule on/off."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LB64ConfigEntry, LB64Coordinator
from .entity import LB64Entity
from .timers import sleep_command, wake_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LB64SwitchDescription(SwitchEntityDescription):
    """A switch on the lamp."""

    is_on_fn: Callable[[dict[str, Any]], bool]
    command_fn: Callable[[dict[str, Any], bool], str]


SWITCHES = (
    # A sunrise that ends at the wake-up time (time entity "Wake-up time").
    LB64SwitchDescription(
        key="wake",
        translation_key="wake",
        is_on_fn=lambda lamp: lamp["wake"]["on"],
        command_fn=lambda lamp, on: wake_command(lamp, on=on),
    ),
    # The lamp dims to off, ending at the wind-down time.
    LB64SwitchDescription(
        key="sleep",
        translation_key="sleep",
        is_on_fn=lambda lamp: lamp["sleep"]["on"],
        command_fn=lambda lamp, on: sleep_command(lamp, on=on),
    ),
    # The weekly on/off schedule made in the app.
    LB64SwitchDescription(
        key="schedule",
        translation_key="schedule",
        is_on_fn=lambda lamp: lamp["schedule"],
        command_fn=lambda lamp, on: f"CONFIG:SCHED:{int(on)}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: LB64ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the switches."""
    async_add_entities(LB64Switch(entry.runtime_data, description) for description in SWITCHES)


class LB64Switch(LB64Entity, SwitchEntity):
    """A switch on the lamp."""

    entity_description: LB64SwitchDescription

    def __init__(self, coordinator: LB64Coordinator, description: LB64SwitchDescription) -> None:
        """Initialize."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return bool(self.entity_description.is_on_fn(self.lamp))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch on."""
        await self.coordinator.async_command(self.entity_description.command_fn(self.lamp, True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch off."""
        await self.coordinator.async_command(self.entity_description.command_fn(self.lamp, False))
