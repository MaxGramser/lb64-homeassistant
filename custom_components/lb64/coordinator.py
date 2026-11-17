"""Keeps the state of one lamp, fed by the lamp's push stream."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import LB64Client, LB64ConnectionError, LB64Error
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type LB64ConfigEntry = ConfigEntry[LB64Coordinator]

# The lamp reports its diagnostics (current, frame rate, signal) every 5 seconds; that is
# more than a history needs.
STATS_INTERVAL = 15
RECONNECT_MAX = 15


class LB64Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """State of one lamp. No polling: the lamp pushes every change."""

    config_entry: LB64ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LB64ConfigEntry, client: LB64Client) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {client.host}", update_interval=None)
        self.client = client
        self._stats_at = 0.0
        self._time_sent_at = 0.0

    @property
    def device_id(self) -> str:
        """The lamp's own id (stable; the unique id of the config entry)."""
        return self.config_entry.unique_id or self.data["id"]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the state once (at setup; afterwards the stream delivers it)."""
        try:
            return await self.client.state()
        except LB64ConnectionError as err:
            raise UpdateFailed(str(err)) from err

    def start(self) -> None:
        """Start listening to the lamp."""
        self.config_entry.async_create_background_task(self.hass, self._listen(), f"{DOMAIN} events {self.client.host}")

    async def _listen(self) -> None:
        """Follow the push stream for as long as the entry is loaded; reconnect when it drops."""
        failures = 0
        while True:
            try:
                async for event, document in self.client.events():
                    failures = 0
                    self._handle(event, document)
            except LB64ConnectionError as err:
                failures += 1
                # One short hiccup (the lamp roaming to another access point) is retried
                # at once and never shows; after that the entities become unavailable.
                if failures > 1 and self.last_update_success:
                    self.async_set_update_error(err)
            await asyncio.sleep(0.5 if failures <= 1 else min(2 ** (failures - 1), RECONNECT_MAX))

    @callback
    def _handle(self, event: str, document: dict[str, Any]) -> None:
        if event == "state":
            self._stats_at = time.monotonic()
            self._device_changed(document)
            self.async_set_updated_data(document)
            if not document.get("time_valid", True):
                self._send_time()
        elif event == "stats" and self.data is not None:
            now = time.monotonic()
            if self.last_update_success and now - self._stats_at < STATS_INTERVAL:
                return
            self._stats_at = now
            self.async_set_updated_data({**self.data, "stats": document})

    @callback
    def _device_changed(self, document: dict[str, Any]) -> None:
        """Keep the device page right after a firmware update or a rename in the app."""
        old = self.data or {}
        if old.get("fw") == document.get("fw") and old.get("name") == document.get("name"):
            return
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(registry, self.config_entry.entry_id):
            registry.async_update_device(device.id, sw_version=document.get("fw"), name=document.get("name"))

    @callback
    def _send_time(self) -> None:
        """The lamp has no clock battery: after a power cut, tell it what time it is.

        (It also asks an NTP server itself; this covers networks where that is blocked.)
        """
        now = time.monotonic()
        if now - self._time_sent_at < 60:
            return
        self._time_sent_at = now

        async def send() -> None:
            try:
                await self.client.command(f"TIME:SET:{int(dt_util.utcnow().timestamp())}")
            except LB64Error as err:
                _LOGGER.debug("Could not set the lamp's clock: %s", err)

        self.config_entry.async_create_background_task(self.hass, send(), f"{DOMAIN} clock")

    async def async_command(self, *commands: str) -> list[str]:
        """Send commands to the lamp. The new state follows over the push stream."""
        try:
            return await self.client.command(*commands)
        except LB64ConnectionError as err:
            raise HomeAssistantError(str(err)) from err
        except LB64Error as err:
            raise HomeAssistantError(f"The lamp refused {', '.join(commands)}: {err}") from err
