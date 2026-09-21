"""Device-side graphics engine and OCR."""
from __future__ import annotations

import json
import time
from typing import Any, Mapping, Optional

from ..core.models import OcrItem, OcrResult
from ..errors import DeviceOperationError


class OcrMixin:
    """设备端图色引擎与 OCR。"""


    def _device_screenshot_path(self) -> str:
        items = self._ok(self.json("GET", "/api/screen/capture/list", params={"capture": "true"})).get("data") or []
        if not items:
            raise DeviceOperationError("device did not return a screenshot path")
        return str(items[0]["path"])

    def gp(self, class_id: str, params: str, *, image: Optional[str] = None, name: str = "uitap") -> Any:
        track = [{"id": class_id, "type": "图色工具", "data": {"params": params}}]
        return self._ok(self.json("POST", "/api/screen/gp", form={"strack": json.dumps(track, ensure_ascii=False), "image": image or self._device_screenshot_path(), "gp": name}, timeout=60)).get("data")

    def ocr_raw(self, *, region: tuple[int, int, int, int] | None = None, region_relative: tuple[float, float, float, float] | None = None) -> Any:
        if region is not None and region_relative is not None: raise ValueError("region and region_relative cannot be combined")
        if region_relative is not None:
            frame = self.capture_frame(); left, top, right, bottom = frame.resolve_region(region_relative=region_relative); region = (left, top, right, bottom)
        rect = "|".join(str(value) for value in region) if region else None
        return self.gp("ascript.ios.screen.Ocr", "mode=5, confidence=0.1" + (f", rect=[{rect}]" if rect else ""))

    def ocr(self, *, region: tuple[int, int, int, int] | None = None, region_relative: tuple[float, float, float, float] | None = None) -> OcrResult:
        raw = self.ocr_raw(region=region, region_relative=region_relative)
        try: payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError: payload = raw
        entries = payload.get("data", []) if isinstance(payload, Mapping) else payload if isinstance(payload, list) else []
        items: list[OcrItem] = []
        for entry in entries:
            if not isinstance(entry, Mapping): continue
            rect_value = entry.get("rect")
            rect = tuple(int(value) for value in rect_value) if isinstance(rect_value, list) and len(rect_value) == 4 else None
            confidence = float(entry["confidence"]) if isinstance(entry.get("confidence"), (int, float)) else None
            items.append(OcrItem(str(entry.get("text") or ""), rect, confidence, dict(entry)))
        return OcrResult(tuple(items), payload)

    def find_ocr_text(self, text: str, *, contains: bool = True, region: tuple[int, int, int, int] | None = None, region_relative: tuple[float, float, float, float] | None = None) -> list[OcrItem]:
        result = self.ocr(region=region, region_relative=region_relative)
        return [item for item in result.items if text in item.text] if contains else [item for item in result.items if item.text == text]

    def wait_ocr_text(self, text: str, *, contains: bool = True, timeout: float = 10.0, interval: float = 0.5, region: tuple[int, int, int, int] | None = None, region_relative: tuple[float, float, float, float] | None = None) -> OcrItem:
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout
        while True:
            found = self.find_ocr_text(text, contains=contains, region=region, region_relative=region_relative)
            if found: return found[0]
            if time.monotonic() >= deadline: raise LookupError(f"OCR text did not appear within {timeout}s: {text}")
            time.sleep(min(interval, deadline - time.monotonic()))
