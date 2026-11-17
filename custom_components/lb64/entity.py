"""Base entity for the LB-64."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LB64Coordinator


class LB64Entity(CoordinatorEntity[LB64Coordinator]):
    """An entity of one lamp."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LB64Coordinator, key: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        data = coordinator.data
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            connections={(CONNECTION_NETWORK_MAC, format_mac(data["mac"]))} if data.get("mac") else set(),
            name=data.get("name"),
            manufacturer=MANUFACTURER,
            model=data.get("model", "LB-64"),
            sw_version=data.get("fw"),
            configuration_url=coordinator.client.url,
        )

    @property
    def lamp(self) -> dict[str, Any]:
        """The lamp's state."""
        return self.coordinator.data
