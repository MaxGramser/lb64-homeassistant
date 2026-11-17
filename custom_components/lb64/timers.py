"""The wake-up light and the wind-down: reading them and composing their commands.

The lamp takes each of them as one command with all its fields, so changing one field
means sending the others back as they are.
"""

from __future__ import annotations

from typing import Any


def wake_command(lamp: dict[str, Any], **changes: Any) -> str:
    """WAKE:SET:<on>|HH:MM|<days>|<duration>|<hold>|<level> with `changes` applied."""
    wake = {**lamp["wake"], **changes}
    return (
        f"WAKE:SET:{int(bool(wake['on']))}|{wake['time']}|{wake['days']}|"
        f"{wake['duration']}|{wake['hold']}|{wake['level']}"
    )


def sleep_command(lamp: dict[str, Any], **changes: Any) -> str:
    """SLEEP:SET:<on>|HH:MM|<days>|<duration> with `changes` applied."""
    sleep = {**lamp["sleep"], **changes}
    return f"SLEEP:SET:{int(bool(sleep['on']))}|{sleep['time']}|{sleep['days']}|{sleep['duration']}"
