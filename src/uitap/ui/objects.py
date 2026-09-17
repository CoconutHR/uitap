"""控件对象（UiObject）。"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .selector import Selector

if TYPE_CHECKING:
    from .device import Device


@dataclass
class UiObject:
    """A resolved UI element whose coordinates are physical screenshot pixels."""

    device: "Device"
    info: Mapping[str, Any]
    selector: Selector

    @property
    def rect(self) -> dict[str, float]:
        return {"x": float(self.info.get("x") or 0), "y": float(self.info.get("y") or 0), "width": float(self.info.get("width") or 0), "height": float(self.info.get("height") or 0)}

    @property
    def center(self) -> tuple[float, float]:
        rect = self.rect
        return rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2

    @property
    def exists(self) -> bool: return True

    def click(self, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        rect = self.rect
        if rect["width"] <= 0 or rect["height"] <= 0: raise ValueError("element has an empty rectangle")
        return self.device.client.tap(*self.center, duration=duration, duration_ms=duration_ms)
    def long_click(self, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.device.client.long_press(*self.center, duration=duration, duration_ms=duration_ms)
    def double_click(self, *, duration: float | None = None, duration_ms: int | None = None, interval: float = 0.08) -> Any: return self.device.client.double_tap(*self.center, duration=duration, duration_ms=duration_ms, interval=interval)
    def click_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        try: x_ratio, y_ratio = float(x_ratio), float(y_ratio)
        except (TypeError, ValueError) as exc: raise ValueError("element relative coordinates must be finite numbers between 0 and 1") from exc
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in (x_ratio, y_ratio)):
            raise ValueError("element relative coordinates must be finite numbers between 0 and 1")
        rect = self.rect
        if rect["width"] <= 0 or rect["height"] <= 0: raise ValueError("element has an empty rectangle")
        x = min(rect["x"] + rect["width"] - 1, rect["x"] + rect["width"] * x_ratio)
        y = min(rect["y"] + rect["height"] - 1, rect["y"] + rect["height"] * y_ratio)
        return self.device.client.tap(x, y, duration=duration, duration_ms=duration_ms)
    def drag_to(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        return self.device.client.drag(*self.center, x, y, duration=duration, duration_ms=duration_ms)
    def drag_to_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        return self.device.client.drag(*self.center, *self.device.client.relative_point(x_ratio, y_ratio), duration=duration, duration_ms=duration_ms)
    def set_text(self, text: str, *, interval_ms: int = 120) -> Any:
        self.click()
        return self.device.client.input_text(text, interval_ms=interval_ms)
    def get_text(self) -> str:
        """读取元素文本（`value`/`label` 的设备端权威值，而非本地树快照）。"""
        node_id = self.info.get("id")
        if not node_id: raise ValueError("element has no node id; re-query the element before reading text")
        return self.device.client.element_text(str(node_id))
    def scroll(self, direction: str = "down", distance: float = 1.0) -> Any:
        """在可滚动元素内滚动；``direction``：up/down/left/right，``distance`` 为元素宽高倍数。"""
        node_id = self.info.get("id")
        if not node_id: raise ValueError("element has no node id; re-query the element before scrolling")
        return self.device.client.element_scroll(str(node_id), direction, distance)
    def scroll_to(self, selector: "Selector | dict[str, Any]", *, direction: str = "down", max_swipes: int = 8, distance: float = 0.8, interval: float = 0.3) -> "UiObject | None":
        """在当前可滚动元素内滚动查找目标；找到返回元素，``max_swipes`` 次后未找到返回 ``None``。"""
        target_selector = selector if isinstance(selector, Selector) else self.device.selector(**selector)
        for attempt in range(max_swipes + 1):
            found = self.device.find(target_selector, timeout=0)
            if found is not None: return found
            if attempt >= max_swipes: return None
            self.scroll(direction, distance)
            time.sleep(max(0, interval))
        return None
    def screenshot(self, destination: str | Path | None = None) -> bytes | Path:
        frame = self.device.client.capture_frame()
        rect = self.rect
        left, top = max(0, int(rect["x"])), max(0, int(rect["y"]))
        right, bottom = min(frame.width, int(rect["x"] + rect["width"])), min(frame.height, int(rect["y"] + rect["height"]))
        if left >= right or top >= bottom: raise ValueError("element has an empty rectangle")
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(frame.png)) as image:
            output = BytesIO(); image.crop((left, top, right, bottom)).save(output, "PNG")
        data = output.getvalue()
        if destination is None: return data
        target = Path(destination); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        return target.resolve()
