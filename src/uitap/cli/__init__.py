"""uitap 命令行包：``ut`` / ``uitap`` / ``python -m uitap`` 三个等价入口。"""
from __future__ import annotations

from .app import _stop_tunnel_on_sigterm, main
from .parser import _HELP, _parser

__all__ = ["main", "_stop_tunnel_on_sigterm", "_HELP", "_parser"]