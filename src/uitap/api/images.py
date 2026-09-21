"""Host-side template matching (HID-accelerated, PNG fallback)."""
from __future__ import annotations

import base64
import binascii
import math
import time
from pathlib import Path
from typing import Any, Mapping

from ..core.models import ImageMatch
from ..errors import DeviceConnectionError, DeviceOperationError, DeviceResponseError, UitapError
from ..i18n import t
from ..vision import ScreenFrame
from .coordinates import swipe_gesture


def _resolved_region(name: str, *, regions: Mapping[str, Any] | None, regions_relative: Mapping[str, Any] | None, regions_pixels: Mapping[str, Any] | None, region: Any, region_relative: Any, region_pixels: Any) -> tuple[Any, Any, Any]:
    """Pick a template's search region: per-name mapping first, call-wide default second.

    A template that has an entry in any of the ``regions*`` mappings uses only the
    mapped trio (so a per-name entry never mixes with the default and trips the
    "regions cannot be combined" validation); everything else falls back to the
    call-wide ``region*`` defaults.
    """
    overridden = any(mapping is not None and name in mapping for mapping in (regions, regions_relative, regions_pixels))
    if overridden:
        return (regions or {}).get(name), (regions_relative or {}).get(name), (regions_pixels or {}).get(name)
    return region, region_relative, region_pixels


class ImagesMixin:
    """本机模板匹配（HID 加速，PNG 回退）。"""


    @staticmethod
    def _image_match(image: bytes, template: str | Path | bytes, *, confidence: float, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None) -> ImageMatch | None:
        return ScreenFrame(image).find_image(template, confidence=confidence, region=region, region_relative=region_relative, region_pixels=region_pixels)

    def _hid_vision_frame(self) -> ScreenFrame | None:
        """Return the existing HID recording JPEG frame, or ``None`` when unavailable.

        The endpoint is present only when the device-side broadcast extension is
        running. It is a best-effort optimization for host-side image matching;
        public screenshot and pixel APIs deliberately retain their PNG contract.
        """
        if self._hid_vision_available is False:
            return None
        try:
            value = self.json("GET", "/api/hid/screenshot", timeout=min(self.timeout, 10.0)).get("value")
            if not isinstance(value, str) or not value or value == "null":
                raise ValueError("HID screenshot response has no image")
            image = base64.b64decode(value, validate=True)
            frame = ScreenFrame(image)
        except (DeviceResponseError, DeviceOperationError, ValueError, binascii.Error, OSError):
            # A missing, malformed or incompatible endpoint should not make a
            # previously working vision workflow fail. Avoid retrying it in every
            # wait loop; the normal PNG endpoint remains the compatibility path.
            self._hid_vision_available = False
            return None
        except DeviceConnectionError:
            # Do not cache transient transport failures as an unavailable feature.
            return None
        self._hid_vision_available = True
        return frame

    def _vision_action_size(self, frame: ScreenFrame) -> dict[str, float]:
        """Return action-coordinate dimensions for a HID frame.

        HID JPEGs can differ by one pixel from the physical PNG action space.
        Calibrate once with the authoritative PNG endpoint, then refresh after
        a rotation. This keeps ImageMatch coordinates safe for ``tap()`` while
        leaving steady-state matching on the faster JPEG path.
        """
        cached = self._vision_action_dimensions
        if cached is not None and (cached["width"] > cached["height"]) == (frame.width > frame.height):
            return cached
        space = self._space_cache
        if space is not None and time.monotonic() < space[0]:
            action = dict(space[2])
            if (action["width"] > action["height"]) == (frame.width > frame.height):
                self._vision_action_dimensions = action
                return action
        action = self.action_size()
        self._vision_action_dimensions = action
        return action

    def _capture_vision_frame(self, *, exact: bool = False) -> tuple[ScreenFrame, dict[str, float]]:
        """Capture one frame for host-side template matching.

        Exact matching remains PNG-only because the HID source is a lossy JPEG.
        Other matching attempts use HID when present and automatically fall back
        to the regular PNG endpoint on unsupported devices.
        """
        if not exact:
            frame = self._hid_vision_frame()
            if frame is not None:
                try:
                    return frame, self._vision_action_size(frame)
                except UitapError:
                    # Coordinate calibration is not optional; preserve coordinate
                    # correctness by falling back rather than returning raw JPEG
                    # coordinates when the authoritative PNG size is unavailable.
                    pass
        frame = self.capture_frame()
        return frame, {"width": float(frame.width), "height": float(frame.height)}

    @staticmethod
    def _scale_vision_region(region: tuple[int, int, int, int] | tuple[float, float, float, float] | None, action: Mapping[str, float], frame: ScreenFrame) -> tuple[int, int, int, int] | tuple[float, float, float, float] | None:
        """Map an absolute action-space region into a HID frame's pixel space."""
        if region is None or not all(isinstance(value, int) for value in region):
            return region
        x_scale, y_scale = frame.width / action["width"], frame.height / action["height"]
        left, top, right, bottom = region
        return (
            max(0, min(frame.width - 1, math.floor(left * x_scale))),
            max(0, min(frame.height - 1, math.floor(top * y_scale))),
            max(1, min(frame.width, math.ceil(right * x_scale))),
            max(1, min(frame.height, math.ceil(bottom * y_scale))),
        )

    @staticmethod
    def _scale_vision_match(match: ImageMatch | None, action: Mapping[str, float], frame: ScreenFrame) -> ImageMatch | None:
        """Map HID-frame match coordinates back to public action coordinates."""
        if match is None or (action["width"] == frame.width and action["height"] == frame.height):
            return match
        x_scale, y_scale = action["width"] / frame.width, action["height"] / frame.height
        left, top = round(match.x * x_scale), round(match.y * y_scale)
        right, bottom = round((match.x + match.width) * x_scale), round((match.y + match.height) * y_scale)
        return ImageMatch(left, top, max(1, right - left), max(1, bottom - top), match.confidence)

    def _find_image_in_vision_frame(self, frame: ScreenFrame, action: Mapping[str, float], template: str | Path | bytes, *, confidence: float, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None) -> ImageMatch | None:
        match = frame.find_image(
            template,
            confidence=confidence,
            region=self._scale_vision_region(region, action, frame),
            region_relative=region_relative,
            region_pixels=self._scale_vision_region(region_pixels, action, frame),
        )
        return self._scale_vision_match(match, action, frame)

    def find_image(self, template: str | Path | bytes, *, confidence: float = 0.9, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None) -> ImageMatch | None:
        """在当前截图中匹配一个本机模板。

        ``confidence < 1`` 时优先读取设备已有的 HID 录屏 JPEG 帧；接口不可用
        时自动回退 PNG。精确匹配（``confidence == 1``）保持无损 PNG 语义。
        """
        frame, action = self._capture_vision_frame(exact=confidence == 1)
        return self._find_image_in_vision_frame(frame, action, template, confidence=confidence, region=region, region_relative=region_relative, region_pixels=region_pixels)

    def find_images(self, templates: Mapping[str, str | Path | bytes], *, confidence: float = 0.9, regions: Mapping[str, tuple[int, int, int, int] | tuple[float, float, float, float] | None] | None = None, regions_relative: Mapping[str, tuple[float, float, float, float] | None] | None = None, regions_pixels: Mapping[str, tuple[int, int, int, int] | None] | None = None, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None) -> dict[str, ImageMatch | None]:
        """在一张截图中匹配多个模板。

        ``regions`` / ``regions_relative`` / ``regions_pixels`` 按模板名称给出每张
        模板各自的搜索区域；``region`` / ``region_relative`` / ``region_pixels``
        是作用于全部模板的默认区域。同一模板两者都给时，按名称的映射优先。
        """
        frame, action = self._capture_vision_frame(exact=confidence == 1)
        matches: dict[str, ImageMatch | None] = {}
        for name, template in templates.items():
            specific, specific_relative, specific_pixels = _resolved_region(name, regions=regions, regions_relative=regions_relative, regions_pixels=regions_pixels, region=region, region_relative=region_relative, region_pixels=region_pixels)
            matches[name] = self._find_image_in_vision_frame(frame, action, template, confidence=confidence, region=specific, region_relative=specific_relative, region_pixels=specific_pixels)
        return matches

    def find_any_image(self, templates: Mapping[str, str | Path | bytes], *, confidence: float = 0.9, regions: Mapping[str, tuple[int, int, int, int] | tuple[float, float, float, float] | None] | None = None, regions_relative: Mapping[str, tuple[float, float, float, float] | None] | None = None, regions_pixels: Mapping[str, tuple[int, int, int, int] | None] | None = None, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None) -> tuple[str, ImageMatch] | None:
        """在一张截图中寻找任意模板，返回第一个命中的名称和结果。

        区域参数与 :meth:`find_images` 相同：``regions*`` 按模板名称给出各自区域，
        ``region*`` 是全部模板共用的默认区域，按名称的映射优先。
        """
        frame, action = self._capture_vision_frame(exact=confidence == 1)
        for name, template in templates.items():
            specific, specific_relative, specific_pixels = _resolved_region(name, regions=regions, regions_relative=regions_relative, regions_pixels=regions_pixels, region=region, region_relative=region_relative, region_pixels=region_pixels)
            match = self._find_image_in_vision_frame(frame, action, template, confidence=confidence, region=specific, region_relative=specific_relative, region_pixels=specific_pixels)
            if match is not None:
                return name, match
        return None

    def wait_image(self, template: str | Path | bytes, *, confidence: float = 0.9, timeout: float = 10.0, interval: float = 0.5, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None, log: bool = False, initial_delay: bool = True) -> ImageMatch:
        """等待本机模板出现并返回 ``ImageMatch``。"""
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout
        if initial_delay: time.sleep(min(interval, timeout))
        attempt = 0
        while True:
            attempt += 1
            match = self.find_image(template, confidence=confidence, region=region, region_relative=region_relative, region_pixels=region_pixels)
            if match is not None:
                if log: print(t("image_wait_found", attempt=attempt, x=match.x, y=match.y, confidence=match.confidence))
                return match
            if log: print(t("image_wait_missing", attempt=attempt))
            if time.monotonic() >= deadline: raise TimeoutError("image did not appear before timeout")
            time.sleep(min(interval, deadline - time.monotonic()))

    def wait_any_image(self, templates: Mapping[str, str | Path | bytes], *, confidence: float = 0.9, timeout: float = 10.0, interval: float = 0.5, regions: Mapping[str, tuple[int, int, int, int] | tuple[float, float, float, float] | None] | None = None, regions_relative: Mapping[str, tuple[float, float, float, float] | None] | None = None, regions_pixels: Mapping[str, tuple[int, int, int, int] | None] | None = None, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None, initial_delay: bool = True) -> tuple[str, ImageMatch]:
        """等待任意模板出现；每轮只抓取并解码一张截图。

        区域参数与 :meth:`find_any_image` 相同：``regions`` / ``regions_relative`` /
        ``regions_pixels`` 按模板名称给出每张模板各自的搜索区域（形如
        ``regions={"成功": (0, 0, 1179, 900)}``）；``region`` / ``region_relative`` /
        ``region_pixels`` 是全部模板共用的默认区域；同一模板两者都给时按名称的映射优先。
        """
        if not templates: raise ValueError("templates must not be empty")
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout
        if initial_delay: time.sleep(min(interval, timeout))
        while True:
            result = self.find_any_image(templates, confidence=confidence, regions=regions, regions_relative=regions_relative, regions_pixels=regions_pixels, region=region, region_relative=region_relative, region_pixels=region_pixels)
            if result is not None: return result
            if time.monotonic() >= deadline: raise TimeoutError(f"none of the images appeared before timeout: {', '.join(templates)}")
            time.sleep(min(interval, deadline - time.monotonic()))

    def wait_image_gone(self, template: str | Path | bytes, *, confidence: float = 0.9, timeout: float = 10.0, interval: float = 0.5, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None, log: bool = False, initial_delay: bool = True) -> bool:
        """等待模板消失，成功返回 ``True``，超时返回 ``False``。"""
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout
        if initial_delay: time.sleep(min(interval, timeout))
        attempt = 0
        while True:
            attempt += 1
            match = self.find_image(template, confidence=confidence, region=region, region_relative=region_relative, region_pixels=region_pixels)
            if match is None:
                if log: print(t("image_wait_gone", attempt=attempt))
                return True
            if log: print(t("image_wait_present", attempt=attempt, confidence=match.confidence))
            if time.monotonic() >= deadline: return False
            time.sleep(min(interval, deadline - time.monotonic()))

    def tap_image(self, template: str | Path | bytes, *, confidence: float = 0.9, timeout: float = 10.0, interval: float = 0.5, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None, duration: float | None = None, duration_ms: int | None = None) -> ImageMatch:
        """等待模板出现后点击中心，``duration_ms`` 为点击持续毫秒数。"""
        match = self.wait_image(template, confidence=confidence, timeout=timeout, interval=interval, region=region, region_relative=region_relative, region_pixels=region_pixels)
        self.tap(*match.center, duration=duration, duration_ms=duration_ms)
        return match

    def scroll_until_image(self, template: str | Path | bytes, *, direction: str = "down", swipe_relative: tuple[float, float, float, float] | None = None, x1_ratio: float | None = None, y1_ratio: float | None = None, x2_ratio: float | None = None, y2_ratio: float | None = None, confidence: float = 0.9, timeout: float = 20.0, interval: float = 0.5, max_swipes: int = 10, region: tuple[int, int, int, int] | tuple[float, float, float, float] | None = None, region_relative: tuple[float, float, float, float] | None = None, region_pixels: tuple[int, int, int, int] | None = None, duration: float | None = None, duration_ms: int | None = None, log: bool = False, initial_delay: bool = True) -> ImageMatch:
        """Swipe in ``direction`` until a template appears, then return its match."""
        if timeout < 0 or interval <= 0 or max_swipes < 0:
            raise ValueError("timeout must be non-negative, interval positive, and max_swipes non-negative")
        x1, y1, x2, y2 = swipe_gesture(direction, swipe_relative, x1_ratio, y1_ratio, x2_ratio, y2_ratio)
        # Validate a custom ratio gesture before the initial wait or any action.
        self.relative_point(x1, y1); self.relative_point(x2, y2)
        deadline = time.monotonic() + timeout
        if initial_delay: time.sleep(min(interval, timeout))
        for swipe_number in range(max_swipes + 1):
            match = self.find_image(template, confidence=confidence, region=region, region_relative=region_relative, region_pixels=region_pixels)
            attempt = swipe_number + 1
            if match is not None:
                if log: print(t("image_scroll_match", attempt=attempt, x=match.x, y=match.y, confidence=match.confidence))
                return match
            if swipe_number == max_swipes or time.monotonic() >= deadline:
                if log: print(t("image_scroll_stop", attempt=attempt))
                break
            if log: print(t("image_scroll_next", attempt=attempt))
            self.swipe_relative(x1, y1, x2, y2, **({"duration": duration} if duration is not None else {"duration_ms": duration_ms} if duration_ms is not None else {}))
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
        raise TimeoutError(f"image did not appear after {max_swipes} {direction} swipes or before timeout")
