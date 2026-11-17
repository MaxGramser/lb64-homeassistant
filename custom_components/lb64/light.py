"""The lamp itself: on/off, brightness, the stored presets as effects, and a plain colour."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LB64ConfigEntry, LB64Coordinator
from .entity import LB64Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: LB64ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the light."""
    async_add_entities([LB64Light(entry.runtime_data)])


def preset_labels(presets: list[dict[str, Any]]) -> dict[int, str]:
    """Slot -> the name shown in the effect list.

    Names on the lamp need not be unique; a repeated one gets its slot number added.
    """
    counts: dict[str, int] = {}
    for preset in presets:
        counts[preset["name"]] = counts.get(preset["name"], 0) + 1
    return {
        preset["slot"]: preset["name"] if counts[preset["name"]] == 1 else f"{preset['name']} ({preset['slot'] + 1})"
        for preset in presets
    }


class LB64Light(LB64Entity, LightEntity):
    """The lamp.

    Effects are the presets stored on the lamp, by name. The list follows the lamp:
    a preset made, renamed or deleted in the app shows up here at once.

    Colour: picking a colour gives one plain colour. If the lamp is showing a `solid`
    preset, that one is recoloured; otherwise the lamp goes to its stored solid preset
    ("lamp" on a fresh device) and recolours that. Animated presets are never changed.
    For an animated preset the colour shown here is the first one of its palette.
    """

    _attr_name = None
    _attr_translation_key = "lamp"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator: LB64Coordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "light")

    @property
    def is_on(self) -> bool:
        """Return whether the lamp is on."""
        return bool(self.lamp["on"])

    @property
    def brightness(self) -> int:
        """Return the master brightness (lamp: 0-100)."""
        return round(self.lamp["brightness"] * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the colour of a plain preset, or the first colour of an animated one."""
        colors = self.lamp.get("colors") or []
        if not colors:
            return None
        value = int(colors[0], 16)
        return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF

    @property
    def effect_list(self) -> list[str]:
        """Return the presets stored on the lamp."""
        return list(preset_labels(self.lamp["presets"]).values())

    @property
    def effect(self) -> str | None:
        """Return the preset that is showing (none while the app previews an unsaved one)."""
        if self.lamp.get("preview"):
            return None
        return preset_labels(self.lamp["presets"]).get(self.lamp["preset"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return what the lamp is doing: on, off, preview, wake (sunrise) or sleep (wind-down)."""
        return {"mode": str(self.lamp.get("mode", "")).lower()}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, and/or change brightness, preset or colour, in one request to the lamp."""
        commands: list[str] = []
        if ATTR_BRIGHTNESS in kwargs:
            commands.append(f"BRIGHTNESS:{max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))}")
        if ATTR_EFFECT in kwargs:
            slots = {label: slot for slot, label in preset_labels(self.lamp["presets"]).items()}
            if kwargs[ATTR_EFFECT] not in slots:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_preset",
                    translation_placeholders={"preset": str(kwargs[ATTR_EFFECT])},
                )
            commands.append(f"PRESET:USE:{slots[kwargs[ATTR_EFFECT]]}")
        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            commands.append(f"COLOR:{red:02X}{green:02X}{blue:02X}")
        # POWER:1 also ends a running sunrise or wind-down, so it is only sent when the
        # lamp is off or when turning on is all that was asked.
        if not self.is_on or not commands:
            commands.append("POWER:1")
        await self.coordinator.async_command(*commands)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (the lamp fades out)."""
        await self.coordinator.async_command("POWER:0")
