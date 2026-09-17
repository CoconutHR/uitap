"""Screen color sampling, search and assertions."""
from __future__ import annotations

from typing import Any

from ..vision import PixelColor


class ColorsMixin:
    """屏幕取色、找色与比色。"""


    def color_matches(self, x: int, y: int, expected: PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str, *, tolerance: int = 0, include_alpha: bool = False) -> bool:
        return self.capture_frame().color_matches(x, y, expected, tolerance=tolerance, include_alpha=include_alpha)

    def color_matches_relative(self, x_ratio: float, y_ratio: float, expected: PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str, *, tolerance: int = 0, include_alpha: bool = False) -> bool:
        return self.capture_frame().color_matches_relative(x_ratio, y_ratio, expected, tolerance=tolerance, include_alpha=include_alpha)

    def find_color(self, expected: PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str, *, tolerance: int = 0, region: tuple[int, int, int, int] | None = None, region_relative: tuple[float, float, float, float] | None = None) -> tuple[int, int] | None:
        return self.capture_frame().find_color(expected, tolerance=tolerance, region=region, region_relative=region_relative)

    def count_color(self, expected: PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str, *, tolerance: int = 0, region: tuple[int, int, int, int] | None = None, region_relative: tuple[float, float, float, float] | None = None) -> int:
        return self.capture_frame().count_color(expected, tolerance=tolerance, region=region, region_relative=region_relative)

    def assert_color(self, x: int, y: int, expected: PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str, *, tolerance: int = 0, include_alpha: bool = False) -> PixelColor:
        return self.capture_frame().assert_color(x, y, expected, tolerance=tolerance, include_alpha=include_alpha)

    def assert_color_relative(self, x_ratio: float, y_ratio: float, expected: PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str, *, tolerance: int = 0, include_alpha: bool = False) -> PixelColor:
        frame = self.capture_frame(); x, y = frame.point_relative(x_ratio, y_ratio)
        return frame.assert_color(x, y, expected, tolerance=tolerance, include_alpha=include_alpha)

    def find_colors(self, colors: str, *, diff: float = 0.98) -> Any:
        return self.gp("ascript.ios.screen.FindColors", f"colors={colors!r}, diff={diff}")

    def compare_colors(self, colors: str, *, diff: float = 0.9) -> Any:
        return self.gp("ascript.ios.screen.CompareColors", f"colors={colors!r}, diff={diff}")
