"""Tests for the LB-64 integration against a fake lamp."""

from __future__ import annotations

import asyncio
from ipaddress import ip_address

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.lb64 import coordinator as coordinator_module
from custom_components.lb64.const import DOMAIN

LIGHT = "light.lb_64_7684"


async def wait_for(hass: HomeAssistant, condition, timeout: float = 5.0) -> None:
    """Wait until something that arrives over the push stream is true."""
    end = asyncio.get_running_loop().time() + timeout
    while not condition():
        assert asyncio.get_running_loop().time() < end, "timed out"
        await asyncio.sleep(0.02)
        await hass.async_block_till_done()


async def setup(hass: HomeAssistant, lamp) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=lamp.state["id"], data={CONF_HOST: "127.0.0.1", CONF_PORT: lamp.port})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await wait_for(hass, lambda: len(lamp.streams) == 1)
    return entry


def discovery(lamp) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address("127.0.0.1"),
        ip_addresses=[ip_address("127.0.0.1")],
        hostname="lb64-7684.local.",
        name="LB-64 7684._lb64._tcp.local.",
        port=lamp.port,
        type="_lb64._tcp.local.",
        properties={"id": lamp.state["id"], "name": "LB-64 7684", "model": "LB-64", "fw": "0.2.0"},
    )


async def test_zeroconf_flow(hass: HomeAssistant, lamp) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery(lamp))
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LB-64 7684"
    assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_PORT: lamp.port}
    assert result["result"].unique_id == "A1B2C3D47684"


async def test_zeroconf_while_the_lamp_is_starting(hass: HomeAssistant, lamp) -> None:
    """Found while it does not answer yet: still offered; adding works once it is up."""
    port = lamp.port
    info = discovery(lamp)
    await lamp.stop()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=info)
    assert result["step_id"] == "zeroconf_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    await lamp.start(port)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_follows_new_address(hass: HomeAssistant, lamp) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=lamp.state["id"], data={CONF_HOST: "192.0.2.9", CONF_PORT: 80})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery(lamp))
    assert result["type"] is FlowResultType.ABORT
    assert entry.data == {CONF_HOST: "127.0.0.1", CONF_PORT: lamp.port}
    await hass.async_block_till_done()


async def test_user_flow(hass: HomeAssistant, lamp) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "127.0.0.1:1"})
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: f"127.0.0.1:{lamp.port}"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "A1B2C3D47684"


async def test_entities(hass: HomeAssistant, lamp) -> None:
    entry = await setup(hass, lamp)
    light = hass.states.get(LIGHT)
    assert light.state == "on"
    assert light.attributes["brightness"] == 153
    assert light.attributes["effect"] == "aura"
    assert light.attributes["effect_list"] == ["aura", "orb", "lamp"]
    assert light.attributes["rgb_color"] == (255, 46, 147)
    assert hass.states.get("number.lb_64_7684_speed").state == "45"
    assert hass.states.get("number.lb_64_7684_boost").state == "0"
    assert hass.states.get("switch.lb_64_7684_wake_up_light").state == "off"
    assert hass.states.get("switch.lb_64_7684_wind_down").state == "off"
    assert hass.states.get("switch.lb_64_7684_schedule").state == "off"
    assert hass.states.get("time.lb_64_7684_wake_up_time").state == "07:00:00"
    assert hass.states.get("time.lb_64_7684_wind_down_time").state == "23:00:00"
    assert hass.states.get("sensor.lb_64_7684_mode").state == "on"
    assert hass.states.get("sensor.lb_64_7684_current").state == "0.73"
    assert hass.states.get("sensor.lb_64_7684_power").state == "3.6"
    assert hass.states.get("sensor.lb_64_7684_load").state == "23"
    assert hass.states.get("sensor.lb_64_7684_frame_rate").state == "60"
    assert hass.states.get("sensor.lb_64_7684_wifi_signal").state == "-55"
    assert hass.states.get("button.lb_64_7684_restart") is not None

    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.identifiers == {(DOMAIN, "A1B2C3D47684")}
    assert (device.name, device.model, device.sw_version, device.manufacturer) == ("LB-64 7684", "LB-64", "0.2.0", "Lichtblok")


async def test_light_commands(hass: HomeAssistant, lamp) -> None:
    await setup(hass, lamp)

    await hass.services.async_call("light", "turn_off", {"entity_id": LIGHT}, blocking=True)
    assert lamp.commands == ["POWER:0"]
    await wait_for(hass, lambda: hass.states.get(LIGHT).state == "off")

    lamp.commands.clear()
    await hass.services.async_call("light", "turn_on", {"entity_id": LIGHT, "brightness": 255, "effect": "orb"}, blocking=True)
    assert lamp.commands == ["BRIGHTNESS:100", "PRESET:USE:1", "POWER:1"]
    await wait_for(hass, lambda: hass.states.get(LIGHT).attributes.get("effect") == "orb")
    assert hass.states.get(LIGHT).attributes["brightness"] == 255

    # Already on: a colour does not send POWER (that would end a running sunrise).
    lamp.commands.clear()
    await hass.services.async_call("light", "turn_on", {"entity_id": LIGHT, "rgb_color": [0, 255, 128]}, blocking=True)
    assert lamp.commands == ["COLOR:00FF80"]
    await wait_for(hass, lambda: hass.states.get(LIGHT).attributes.get("rgb_color") == (0, 255, 128))
    assert hass.states.get(LIGHT).attributes["effect"] == "lamp"

    lamp.commands.clear()
    await hass.services.async_call("light", "turn_on", {"entity_id": LIGHT}, blocking=True)
    assert lamp.commands == ["POWER:1"]


async def test_other_commands(hass: HomeAssistant, lamp) -> None:
    await setup(hass, lamp)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.lb_64_7684_speed", "value": 120}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.lb_64_7684_boost", "value": 30}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.lb_64_7684_schedule"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.lb_64_7684_wake_up_light"}, blocking=True)
    await hass.services.async_call("time", "set_value", {"entity_id": "time.lb_64_7684_wake_up_time", "time": "06:45:00"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.lb_64_7684_wind_down"}, blocking=True)
    await hass.services.async_call("time", "set_value", {"entity_id": "time.lb_64_7684_wind_down_time", "time": "22:30:00"}, blocking=True)
    await hass.services.async_call("button", "press", {"entity_id": "button.lb_64_7684_restart"}, blocking=True)
    assert lamp.commands == [
        "PRESET:SPEED:120",
        "GAIN:30",
        "CONFIG:SCHED:1",
        "WAKE:SET:1|07:00|1111100|30|30|100",
        "WAKE:SET:1|06:45|1111100|30|30|100",
        "SLEEP:SET:1|23:00|1111111|30",
        "SLEEP:SET:1|22:30|1111111|30",
        "CONFIG:REBOOT",
    ]
    await wait_for(hass, lambda: hass.states.get("time.lb_64_7684_wind_down_time").state == "22:30:00")
    assert hass.states.get("number.lb_64_7684_speed").state == "120"
    assert hass.states.get("switch.lb_64_7684_wake_up_light").state == "on"


async def test_refused_command(hass: HomeAssistant, lamp) -> None:
    await setup(hass, lamp)
    lamp.refuse = "ERR:PRESET:SPEED:No stored preset showing"
    with pytest.raises(HomeAssistantError, match="No stored preset showing"):
        await hass.services.async_call("number", "set_value", {"entity_id": "number.lb_64_7684_speed", "value": 10}, blocking=True)


async def test_push_from_the_lamp(hass: HomeAssistant, lamp) -> None:
    """A change made in the app or with the buttons, and a preset renamed in the app."""
    await setup(hass, lamp)
    lamp.state.update(on=False, mode="OFF", brightness=20)
    lamp.state["presets"][1]["name"] = "ball"
    lamp.state["presets"].append({"slot": 16, "name": "aura", "effect": "glow"})
    await lamp.push()
    await wait_for(hass, lambda: hass.states.get(LIGHT).state == "off")
    assert hass.states.get(LIGHT).attributes["effect_list"] == ["aura (1)", "ball", "lamp", "aura (17)"]
    assert hass.states.get("sensor.lb_64_7684_mode").state == "off"

    # A firmware update and a rename in the app reach the device page.
    lamp.state.update(fw="0.3.0", name="Woonkamer")
    await lamp.push()
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    registry = dr.async_get(hass)
    await wait_for(hass, lambda: dr.async_entries_for_config_entry(registry, entry.entry_id)[0].sw_version == "0.3.0")
    assert dr.async_entries_for_config_entry(registry, entry.entry_id)[0].name == "Woonkamer"


async def test_lamp_restart(hass: HomeAssistant, lamp, monkeypatch) -> None:
    """The lamp goes away and comes back: unavailable, then right again, by itself."""
    monkeypatch.setattr(coordinator_module, "RECONNECT_MAX", 1)
    await setup(hass, lamp)
    port = lamp.port
    await lamp.stop()
    await wait_for(hass, lambda: hass.states.get(LIGHT).state == STATE_UNAVAILABLE)

    lamp.state.update(brightness=80, time_valid=False)     # after a power cut the lamp has no clock
    await lamp.start(port)
    await wait_for(hass, lambda: hass.states.get(LIGHT).state == "on", timeout=10)
    assert hass.states.get(LIGHT).attributes["brightness"] == 204
    await wait_for(hass, lambda: any(c.startswith("TIME:SET:") for c in lamp.commands))


async def test_unload(hass: HomeAssistant, lamp) -> None:
    entry = await setup(hass, lamp)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await wait_for(hass, lambda: not lamp.streams)
