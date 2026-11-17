"""Restart the lamp."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LB64ConfigEntry, LB64Coordinator
from .entity import LB64Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: LB64ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the button."""
    async_add_entities([LB64RestartButton(entry.runtime_data)])


class LB64RestartButton(LB64Entity, ButtonEntity):
    """Restarts the lamp."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: LB64Coordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "restart")

    async def async_press(self) -> None:
        """Restart."""
        await self.coordinator.async_command("CONFIG:REBOOT")
