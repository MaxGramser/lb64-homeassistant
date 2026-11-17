"""The LB-64 integration: a square ambient lamp, controlled over the local network."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import LB64Client
from .const import DEFAULT_PORT
from .coordinator import LB64ConfigEntry, LB64Coordinator

PLATFORMS = [Platform.BUTTON, Platform.LIGHT, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH, Platform.TIME]


async def async_setup_entry(hass: HomeAssistant, entry: LB64ConfigEntry) -> bool:
    """Set up a lamp."""
    client = LB64Client(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data.get(CONF_PORT, DEFAULT_PORT))
    coordinator = LB64Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LB64ConfigEntry) -> bool:
    """Unload a lamp."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
