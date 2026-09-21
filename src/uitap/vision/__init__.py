"""本机取色与模板匹配。"""
from __future__ import annotations

from .frame import ScreenFrame, relative_point, resolve_region
from .pixels import PixelColor


__all__ = ["PixelColor", "ScreenFrame", "relative_point", "resolve_region"]
