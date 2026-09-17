"""Command handler registry, grouped by domain.

Adding a command means: define a ``cmd_*`` handler in one of the domain
modules below, register it here, and add its parser/help entries in
``uitap.cli.parser``.
"""
from __future__ import annotations

from typing import Callable

from .device import COMMANDS as _DEVICE
from .files import COMMANDS as _FILES
from .input import COMMANDS as _INPUT
from .screen import COMMANDS as _SCREEN

COMMANDS: dict[str, Callable] = {**_DEVICE, **_SCREEN, **_INPUT, **_FILES}

__all__ = ["COMMANDS"]