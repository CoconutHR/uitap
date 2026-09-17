"""Logical/action coordinate conversion."""
from __future__ import annotations

import math
import time

from ..errors import DeviceResponseError
from ..i18n import t


_SWIPE_DIRECTIONS = {
    "down": (0.5, 0.2, 0.5, 0.8), "up": (0.5, 0.8, 0.5, 0.2),
    "left": (0.8, 0.5, 0.2, 0.5), "right": (0.2, 0.5, 0.8, 0.5),
    "下": (0.5, 0.2, 0.5, 0.8), "上": (0.5, 0.8, 0.5, 0.2),
    "左": (0.8, 0.5, 0.2, 0.5), "右": (0.2, 0.5, 0.8, 0.5),
}

def swipe_gesture(direction: str = "down", swipe_relative: tuple[float, float, float, float] | None = None, x1_ratio: float | None = None, y1_ratio: float | None = None, x2_ratio: float | None = None, y2_ratio: float | None = None) -> tuple[float, float, float, float]:
    """Validate direction/custom-swipe input and return screen ratio endpoints.

    ``direction`` 是手势移动方向，支持 down/up/left/right 及中文；提供
    ``swipe_relative`` 元组时覆盖方向轨迹，也兼容四个独立比例参数。
    """
    custom_swipe = (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
    if any(value is not None for value in custom_swipe) and not all(value is not None for value in custom_swipe):
        raise ValueError("x1_ratio, y1_ratio, x2_ratio, and y2_ratio must be supplied together")
    if swipe_relative is not None:
        if any(value is not None for value in custom_swipe):
            raise ValueError("swipe_relative cannot be combined with individual ratio parameters")
        try:
            if len(swipe_relative) != 4: raise ValueError
            custom_swipe = tuple(float(value) for value in swipe_relative)
        except (TypeError, ValueError) as exc:
            raise ValueError("swipe_relative must contain four ratios: x1, y1, x2, y2") from exc
    if all(value is not None for value in custom_swipe):
        return custom_swipe
    try:
        return _SWIPE_DIRECTIONS[direction.lower()]
    except (AttributeError, KeyError) as exc:
        raise ValueError("direction must be one of: down, up, left, right, 下, 上, 左, 右") from exc

class CoordinatesMixin:
    """逻辑点/动作坐标系换算。"""


    def _logical_screen(self) -> dict[str, float]:
        value = self._ok(self.json("GET", "/api/screen/size")).get("data", {})
        try:
            width, height = float(value["width"]), float(value["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DeviceResponseError(t("screen_size_invalid"), body=repr(value)) from exc
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            raise DeviceResponseError(t("screen_size_invalid"), body=repr(value))
        return {"width": width, "height": height}

    def _coordinate_spaces(self) -> tuple[dict[str, float], dict[str, float]]:
        """Return logical and action sizes, reusing a short-TTL cache.

        轮询类查询每轮都会读取坐标空间；缓存把 3 次设备往返降到 1 次。
        只缓存截图成功的结果；截屏失败时不缓存，下次重试。旋转屏幕会
        改变物理尺寸，旋转敏感的流程可设 ``coordinate_cache_ttl=0``。
        """
        now = time.monotonic()
        if self._space_cache is not None and now < self._space_cache[0]:
            return self._space_cache[1], self._space_cache[2]
        logical = self._logical_screen()
        try:
            action = self.screen_size()
        except DeviceResponseError:
            # A malformed screenshot must not make tree inspection unusable.
            return logical, logical
        if self.coordinate_cache_ttl > 0:
            self._space_cache = (now + self.coordinate_cache_ttl, logical, action)
        return logical, action

    def relative_point(self, x_ratio: float, y_ratio: float) -> tuple[float, float]:
        """Convert two 0..1 ratios into physical action coordinates.

        The result is directly suitable for :meth:`tap` and :meth:`swipe`.
        """
        try:
            x_ratio, y_ratio = float(x_ratio), float(y_ratio)
        except (TypeError, ValueError) as exc:
            raise ValueError(t("relative_ratio_invalid")) from exc
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in (x_ratio, y_ratio)):
            raise ValueError(t("relative_ratio_invalid"))
        size = self.action_size()
        # Keep 1.0 within the valid final coordinate while retaining fractional points elsewhere.
        return min(size["width"] - 1, size["width"] * x_ratio), min(size["height"] - 1, size["height"] * y_ratio)
