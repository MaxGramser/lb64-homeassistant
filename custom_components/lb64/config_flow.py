"""Config flow for the LB-64: found on the network (zeroconf), or added by address."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .client import LB64Client, LB64ConnectionError
from .const import DEFAULT_PORT, DOMAIN


class LB64ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a lamp."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host = ""
        self._port = DEFAULT_PORT
        self._name = "LB-64"

    async def _lamp(self, host: str, port: int) -> dict[str, Any]:
        return await LB64Client(async_get_clientsession(self.hass), host, port).state()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a lamp by its address (name.local or IP, optionally with :port)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host, _, port_text = user_input[CONF_HOST].strip().removeprefix("http://").rstrip("/").partition(":")
            port = int(port_text) if port_text.isdigit() else DEFAULT_PORT
            try:
                lamp = await self._lamp(host, port)
            except LB64ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(lamp["id"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
                return self.async_create_entry(title=lamp.get("name", self._name), data={CONF_HOST: host, CONF_PORT: port})
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str}), errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """A lamp announced itself on the network.

        Everything needed is in the announcement, so the lamp is offered even if it does
        not answer at this very moment (it may just be starting up).
        """
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        properties = discovery_info.properties
        if not (lamp_id := properties.get("id")):
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(lamp_id)
        # Already set up: follow the lamp to its new address (and reload if it changed).
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._port})
        self._name = properties.get("name") or self._name
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm adding the discovered lamp."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                lamp = await self._lamp(self._host, self._port)
            except LB64ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=lamp.get("name") or self._name, data={CONF_HOST: self._host, CONF_PORT: self._port}
                )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._name, "host": self._host},
            errors=errors,
        )
