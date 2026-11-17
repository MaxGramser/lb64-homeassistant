"""Client for the LB-64 network API (described in the README).

Three calls: the state as JSON, the lamp's text commands, and the push stream
(Server-Sent Events) that reports every change the moment it happens.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any

import aiohttp

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=8, sock_connect=4)
# The lamp sends an event at least every 5 seconds. Nothing for 20: the connection is dead.
STREAM_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_connect=4, sock_read=20)


class LB64Error(Exception):
    """The lamp refused a command."""


class LB64ConnectionError(LB64Error):
    """The lamp could not be reached."""


class LB64Client:
    """Talks to one lamp."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int = 80) -> None:
        """Initialize."""
        self._session = session
        self.host = host
        self.port = port
        self.url = f"http://{host}" if port == 80 else f"http://{host}:{port}"

    async def state(self) -> dict[str, Any]:
        """Return the full state."""
        try:
            async with self._session.get(f"{self.url}/api/state", timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                return _decode(await resp.read())
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise LB64ConnectionError(f"Cannot reach the lamp at {self.host}: {err}") from err

    async def command(self, *commands: str) -> list[str]:
        """Send one or more text commands; return the reply lines.

        Raises LB64Error if the lamp answers any of them with ERR.
        """
        try:
            async with self._session.post(
                f"{self.url}/api/command", data="\n".join(commands).encode(), timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                text = (await resp.read()).decode("utf-8", "replace")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LB64ConnectionError(f"Cannot reach the lamp at {self.host}: {err}") from err
        lines = [line for line in text.splitlines() if line]
        for line in lines:
            if line.startswith(("ERR:", "UNKNOWN:")):
                raise LB64Error(line)
        return lines

    async def events(self) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yield (event, document) from the push stream until it ends.

        Always ends with LB64ConnectionError: a stream that stops is a lost connection.
        """
        try:
            async with self._session.get(f"{self.url}/api/events", timeout=STREAM_TIMEOUT) as resp:
                resp.raise_for_status()
                event = "message"
                data: list[bytes] = []
                async for raw in resp.content:
                    line = raw.rstrip(b"\r\n")
                    if not line:
                        if data:
                            yield event, _decode(b"\n".join(data))
                        event, data = "message", []
                    elif line.startswith(b"event:"):
                        event = line[6:].strip().decode("ascii", "replace")
                    elif line.startswith(b"data:"):
                        data.append(line[5:].lstrip(b" "))
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise LB64ConnectionError(f"Lost the connection to the lamp at {self.host}: {err}") from err
        raise LB64ConnectionError(f"The lamp at {self.host} closed the connection")


def _decode(payload: bytes) -> dict[str, Any]:
    """Parse a JSON document. A preset name cut in the middle of a character must not break it."""
    document = json.loads(payload.decode("utf-8", "replace"))
    if not isinstance(document, dict):
        raise ValueError("unexpected answer from the lamp")
    return document
