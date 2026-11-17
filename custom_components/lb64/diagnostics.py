"""Diagnostics: the lamp's state as the integration last saw it."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import LB64ConfigEntry

TO_REDACT = {"id", "mac", "ip", "host"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: LB64ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a lamp."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "connected": coordinator.last_update_success,
        "lamp": async_redact_data(coordinator.data, TO_REDACT),
    }
