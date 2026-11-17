"""Fixtures: a fake lamp that speaks the network API (see the README) on a real local socket."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
import sys

from aiohttp import web
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

STATE = {
    "id": "A1B2C3D47684",
    "name": "LB-64 7684",
    "model": "LB-64",
    "fw": "0.2.0",
    "mac": "A1:B2:C3:D4:76:84",
    "host": "lb64-7684.local",
    "ip": "127.0.0.1",
    "on": True,
    "brightness": 60,
    "gain": 0,
    "mode": "ON",
    "preset": 0,
    "preview": False,
    "preset_name": "aura",
    "effect": "aura",
    "speed": 45,
    "colors": ["ff2e93", "9b30ff"],
    "presets": [
        {"slot": 0, "name": "aura", "effect": "aura"},
        {"slot": 1, "name": "orb", "effect": "orb"},
        {"slot": 15, "name": "lamp", "effect": "solid"},
    ],
    "schedule": False,
    "wake": {"on": False, "time": "07:00", "days": "1111100", "duration": 30, "hold": 30, "level": 100},
    "sleep": {"on": False, "time": "23:00", "days": "1111111", "duration": 30},
    "time_valid": True,
    "locked": False,
    "stats": {"load": 23, "amps": 0.73, "limited": False, "fps": 60, "render_ms": 6.1, "show_ms": 2.2,
              "rssi": -55, "heap": 30000, "min_heap": 25000, "uptime": 100, "time": 1794894293, "ble": False, "clients": 1},
}


class FakeLamp:
    """Enough of the lamp to test the integration: state, commands, push stream."""

    def __init__(self) -> None:
        self.state = copy.deepcopy(STATE)
        self.commands: list[str] = []
        self.streams: list[web.StreamResponse] = []
        self.refuse: str | None = None
        self.runner: web.AppRunner | None = None
        self.port = 0

    async def start(self, port: int = 0) -> None:
        app = web.Application()
        app.router.add_get("/api/state", self._state)
        app.router.add_get("/api/events", self._events)
        app.router.add_post("/api/command", self._command)
        self.runner = web.AppRunner(app, handler_cancellation=True, shutdown_timeout=0.1)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", port)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Go away, as when the lamp loses power."""
        for stream in self.streams:
            if stream._req is not None and stream._req.transport is not None:
                stream._req.transport.abort()
        self.streams.clear()
        if self.runner:
            await self.runner.cleanup()
            self.runner = None

    async def _state(self, request: web.Request) -> web.Response:
        return web.json_response(self.state)

    async def _events(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        await response.write(b"retry: 2000\n\n")
        self.streams.append(response)
        await self._send(response, "state", self.state)
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            if response in self.streams:
                self.streams.remove(response)
        return response

    async def _send(self, stream: web.StreamResponse, event: str, document: dict) -> None:
        await stream.write(f"event: {event}\ndata: {json.dumps(document)}\n\n".encode())

    async def push(self, event: str = "state") -> None:
        """Tell the listeners, as the lamp does when something changes."""
        document = self.state if event == "state" else self.state["stats"]
        for stream in list(self.streams):
            await self._send(stream, event, document)

    async def _command(self, request: web.Request) -> web.Response:
        replies = []
        for line in (await request.text()).splitlines():
            self.commands.append(line)
            replies.append(self.refuse or self._apply(line))
        await self.push()
        return web.Response(text="\n".join(replies) + "\n")

    def _apply(self, line: str) -> str:
        """The handful of commands the integration sends."""
        state = self.state
        name, _, value = line.partition(":")
        if name == "POWER":
            state["on"] = value == "1"
            state["mode"] = "ON" if state["on"] else "OFF"
        elif name == "BRIGHTNESS":
            state["brightness"] = int(value)
        elif name == "GAIN":
            state["gain"] = int(value)
        elif line.startswith("PRESET:USE:"):
            state["preset"] = int(line.rsplit(":", 1)[1])
        elif line.startswith("PRESET:SPEED:"):
            state["speed"] = int(line.rsplit(":", 1)[1])
        elif name == "COLOR":
            state["preset"], state["effect"], state["colors"] = 15, "solid", [value.lower()]
        elif line.startswith("CONFIG:SCHED:"):
            state["schedule"] = line.endswith("1")
        elif line.startswith("WAKE:SET:"):
            on, time, days, duration, hold, level = line[9:].split("|")
            state["wake"] = {"on": on == "1", "time": time, "days": days, "duration": int(duration), "hold": int(hold), "level": int(level)}
        elif line.startswith("SLEEP:SET:"):
            on, time, days, duration = line[10:].split("|")
            state["sleep"] = {"on": on == "1", "time": time, "days": days, "duration": int(duration)}
        return f"OK:{line}"


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations, socket_enabled):
    """Load the integration from this repository and allow the local socket of the fake lamp."""


@pytest.fixture
async def lamp():
    fake = FakeLamp()
    await fake.start()
    yield fake
    await fake.stop()
