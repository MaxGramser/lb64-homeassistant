"""What the lamp is doing, and its diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LB64ConfigEntry, LB64Coordinator
from .entity import LB64Entity

PARALLEL_UPDATES = 0

MODES = ["off", "on", "preview", "wake", "sleep"]
SUPPLY_VOLTS = 5.0


@dataclass(frozen=True, kw_only=True)
class LB64SensorDescription(SensorEntityDescription):
    """A sensor of the lamp."""

    value_fn: Callable[[dict[str, Any]], Any]


def _stat(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda lamp: lamp.get("stats", {}).get(key)


SENSORS = (
    # off | on | preview (the app is trying an unsaved preset) | wake (sunrise) | sleep (wind-down)
    LB64SensorDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=MODES,
        value_fn=lambda lamp: mode if (mode := str(lamp.get("mode", "")).lower()) in MODES else None,
    ),
    # Estimated from the picture: the firmware adds up every LED of every frame.
    LB64SensorDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=_stat("amps"),
    ),
    LB64SensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda lamp: round(amps * SUPPLY_VOLTS, 1) if (amps := _stat("amps")(lamp)) is not None else None,
    ),
    # Share of "every LED full white" that the panel is showing.
    LB64SensorDescription(
        key="load",
        translation_key="load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_stat("load"),
    ),
    LB64SensorDescription(
        key="fps",
        translation_key="fps",
        native_unit_of_measurement="fps",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=_stat("fps"),
    ),
    LB64SensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_stat("rssi"),
    ),
    LB64SensorDescription(
        key="heap",
        translation_key="heap",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=_stat("heap"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: LB64ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the sensors."""
    async_add_entities(LB64Sensor(entry.runtime_data, description) for description in SENSORS)


class LB64Sensor(LB64Entity, SensorEntity):
    """A sensor of the lamp."""

    entity_description: LB64SensorDescription

    def __init__(self, coordinator: LB64Coordinator, description: LB64SensorDescription) -> None:
        """Initialize."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the value."""
        return self.entity_description.value_fn(self.lamp)
