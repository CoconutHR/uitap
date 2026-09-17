"""Screenshots, pixels and screen caching."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ..core.png import crop_png, crop_png_relative, png_size
from ..errors import DeviceResponseError
from ..vision import PixelColor, ScreenFrame


class ScreenMixin:
    """截图、像素读取与屏幕缓存。"""
    crop_png = staticmethod(crop_png)
    crop_png_relative = staticmethod(crop_png_relative)


    def screenshot(self) -> bytes:
        """获取当前屏幕 PNG 字节，坐标尺寸与 ``tap`` 一致。"""
        return self.request("GET", "/api/screen/capture", timeout=30)

    def action_size(self) -> dict[str, float]:
        """返回 ``tap``、``swipe``、OCR 使用的截图物理像素尺寸。"""
        size = png_size(self.screenshot())
        if size is None:
            raise DeviceResponseError("invalid PNG returned by screenshot endpoint")
        return {"width": size[0], "height": size[1]}

    def screen_size(self) -> dict[str, float]:
        """返回当前真实物理屏幕分辨率。

        与截图、OCR、``tap``、``swipe`` 使用同一物理像素坐标系；
        设备端 ``/api/screen/size`` 的逻辑点尺寸由内部 ``_logical_screen`` 使用。
        """
        return self.action_size()

    def capture_frame(self) -> ScreenFrame:
        """抓取一张物理像素截图，供取色和多个视觉查询共享。"""
        return ScreenFrame(self.screenshot())

    def pixel(self, x: int, y: int) -> PixelColor:
        """读取物理像素坐标 ``x/y`` 的 RGBA 颜色。"""
        return self.capture_frame().pixel(x, y)

    def pixel_relative(self, x_ratio: float, y_ratio: float) -> PixelColor:
        """按屏幕宽高比例读取一个像素颜色。"""
        return self.capture_frame().pixel_relative(x_ratio, y_ratio)

    def pixels(self, points: Iterator[tuple[int, int]] | list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> list[PixelColor]:
        """在同一张截图中读取多个物理像素坐标。"""
        return self.capture_frame().pixels(points)

    def pixels_relative(self, points: Iterator[tuple[float, float]] | list[tuple[float, float]] | tuple[tuple[float, float], ...]) -> list[PixelColor]:
        """在同一张截图中读取多个比例坐标。"""
        return self.capture_frame().pixels_relative(points)

    def save_screenshot(self, destination: str | Path) -> Path:
        """保存完整 PNG 截图到 ``destination``，返回绝对路径。"""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.screenshot())
        return destination.resolve()

    def screenshot_crop_relative(self, left: float, top: float, right: float, bottom: float) -> bytes:
        """抓取并按比例裁剪 PNG。"""
        return self.capture_frame().crop_relative(left, top, right, bottom)

    def screenshot_crop(self, left: int, top: int, right: int, bottom: int) -> bytes:
        """抓取并按物理像素矩形裁剪 PNG。"""
        return self.capture_frame().crop_pixels(left, top, right, bottom)

    def save_screenshot_crop_relative(self, destination: str | Path, left: float, top: float, right: float, bottom: float) -> Path:
        """Capture a relative crop and save it as PNG."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.screenshot_crop_relative(left, top, right, bottom))
        return destination.resolve()

    def save_screenshot_crop(self, destination: str | Path, left: int, top: int, right: int, bottom: int) -> Path:
        """Capture a physical-pixel crop and save it as PNG."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.screenshot_crop(left, top, right, bottom))
        return destination.resolve()

    def screen_cache(self, enabled: bool) -> None:
        """开关设备端整帧缓存：开启后首次截图复用同一帧，批量 find_color/OCR 提速；
        画面会变化时务必关闭。等价设备端 ``screen.cache``。"""
        with self.locked(): self.eval_python("from ascript.ios.screen import cache\ncache(%r)\n_result=True" % bool(enabled))
