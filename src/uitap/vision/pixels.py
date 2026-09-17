"""PixelColor 与其解析/比较。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PixelColor:
    """RGBA color sampled from a physical screenshot pixel."""
    r: int
    g: int
    b: int
    a: int = 255
    @classmethod
    def parse(cls, value: "PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str") -> "PixelColor":
        if isinstance(value, cls): return value
        if isinstance(value, str):
            text = value.removeprefix("#")
            if len(text) not in {6, 8} or any(char not in "0123456789abcdefABCDEF" for char in text):
                raise ValueError("hex color must be #RRGGBB or #RRGGBBAA")
            values = tuple(int(text[index:index + 2], 16) for index in range(0, len(text), 2))
            return cls(*values) if len(values) == 4 else cls(*values, 255)
        if not isinstance(value, tuple) or len(value) not in {3, 4} or any(not isinstance(channel, int) or isinstance(channel, bool) or not 0 <= channel <= 255 for channel in value):
            raise ValueError("color must be PixelColor, RGB/RGBA tuple, or #RRGGBB/#RRGGBBAA")
        return cls(*value) if len(value) == 4 else cls(*value, 255)

    def matches(self, value: "PixelColor | tuple[int, int, int] | tuple[int, int, int, int] | str", *, tolerance: int = 0, include_alpha: bool = False) -> bool:
        expected = self.parse(value)
        if not isinstance(tolerance, int) or isinstance(tolerance, bool) or tolerance < 0: raise ValueError("tolerance must be a non-negative integer")
        actual, target = self.rgba if include_alpha else self.rgb, expected.rgba if include_alpha else expected.rgb
        return all(abs(one - two) <= tolerance for one, two in zip(actual, target))

    @property
    def rgb(self) -> tuple[int, int, int]: return self.r, self.g, self.b
    @property
    def rgba(self) -> tuple[int, int, int, int]: return self.r, self.g, self.b, self.a
    @property
    def hex(self) -> str: return f"#{self.r:02X}{self.g:02X}{self.b:02X}"
