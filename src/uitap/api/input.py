"""Taps, swipes, drags and text input."""
from __future__ import annotations

import json
import math
import time
from typing import Any


class InputMixin:
    """点击、滑动、拖拽与文本输入。"""


    @staticmethod
    def _duration_ms(duration: float | None, duration_ms: int | None, *, default_ms: int) -> int:
        if duration is not None and duration_ms is not None: raise ValueError("duration and duration_ms cannot be combined")
        if duration is not None:
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0: raise ValueError("duration must be a finite non-negative number of seconds")
            return int(round(duration * 1000))
        if duration_ms is not None:
            if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms < 0: raise ValueError("duration_ms must be a non-negative integer")
            return duration_ms
        return default_ms

    def tap(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None, jitter: int = 0) -> Any:
        """点击物理像素 ``x/y``；``duration`` 单位秒；``jitter`` 为随机抖动像素数(拟人)。"""
        milliseconds = self._duration_ms(duration, duration_ms, default_ms=20)
        jitter = int(jitter or 0)
        if jitter < 0: raise ValueError("jitter must be a non-negative integer")
        with self.locked(): return self.eval_python("from ascript.ios.action import click\nclick(%r, %r, %r, %r)\n_result=True" % (x, y, milliseconds, jitter))

    def click_random(self, x1: float, y1: float, x2: float, y2: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        """在矩形 ``(x1,y1)-(x2,y2)`` 内随机点击一个点(物理像素,两角顺序不限)。"""
        milliseconds = self._duration_ms(duration, duration_ms, default_ms=20)
        corners = (int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)), milliseconds)
        with self.locked(): return self.eval_python("from ascript.ios.action import click_random\nclick_random(%r, %r, %r, %r, %r)\n_result=True" % corners)

    def click_random_relative(self, x1_ratio: float, y1_ratio: float, x2_ratio: float, y2_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        """``click_random`` 的比例坐标版本。"""
        a = self.relative_point(x1_ratio, y1_ratio)
        b = self.relative_point(x2_ratio, y2_ratio)
        return self.click_random(a[0], a[1], b[0], b[1], duration=duration, duration_ms=duration_ms)

    def slide_path(self, points: Any, *, durations: Any = None, duration: int = 800, touch_down_duration: int = 0, touch_up_duration: int = 0) -> Any:
        """沿多段轨迹滑动(物理像素点序列,至少两个点)。

        ``durations`` 为每段移动耗时(毫秒)列表,长度须为点数减一;
        缺省时把 ``duration`` 均分到各段。``touch_down_duration``/``touch_up_duration``
        为按下后/松开前的额外停留毫秒数。
        """
        pts = [[float(point[0]), float(point[1])] for point in points]
        if len(pts) < 2: raise ValueError("slide_path requires at least two points")
        durations_json = json.dumps([int(item) for item in durations]) if durations is not None else "None"
        with self.locked(): return self.eval_python("import json\nfrom ascript.ios.action import slide_path\nslide_path(json.loads(%r), duration=%d, durations=%s, touch_down_duration=%d, touch_up_duration=%d)\n_result=True" % (json.dumps(pts), int(duration), durations_json, int(touch_down_duration), int(touch_up_duration)))

    def slide_path_relative(self, points: Any, *, durations: Any = None, duration: int = 800, touch_down_duration: int = 0, touch_up_duration: int = 0) -> Any:
        """``slide_path`` 的比例坐标版本;``points`` 为 0..1 比例点序列。"""
        absolute = [self.relative_point(point[0], point[1]) for point in points]
        return self.slide_path(absolute, durations=durations, duration=duration, touch_down_duration=touch_down_duration, touch_up_duration=touch_up_duration)

    def touch_and_slide(self, from_x: float, from_y: float, to_x: float, to_y: float, *, touch_down_duration: int = 500, touch_move_duration: int = 1000, touch_up_duration: int = 500) -> Any:
        """带停留的拖拽:按下停 ``touch_down_duration`` 毫秒 → 移动 ``touch_move_duration`` 毫秒 → 松开前停 ``touch_up_duration`` 毫秒。"""
        with self.locked(): return self.eval_python("from ascript.ios.action import touch_and_slide\ntouch_and_slide(%r, %r, %r, %r, %r, %r, %r)\n_result=True" % (from_x, from_y, to_x, to_y, touch_down_duration / 1000.0, touch_move_duration / 1000.0, touch_up_duration / 1000.0))

    def touch_and_slide_relative(self, from_x_ratio: float, from_y_ratio: float, to_x_ratio: float, to_y_ratio: float, *, touch_down_duration: int = 500, touch_move_duration: int = 1000, touch_up_duration: int = 500) -> Any:
        """``touch_and_slide`` 的比例坐标版本。"""
        start = self.relative_point(from_x_ratio, from_y_ratio)
        end = self.relative_point(to_x_ratio, to_y_ratio)
        return self.touch_and_slide(start[0], start[1], end[0], end[1], touch_down_duration=touch_down_duration, touch_move_duration=touch_move_duration, touch_up_duration=touch_up_duration)

    def long_press(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        """在物理像素 ``x/y`` 长按；默认 0.8 秒。"""
        milliseconds = self._duration_ms(duration, duration_ms, default_ms=800)
        return self.tap(x, y, duration_ms=milliseconds)

    def double_tap(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None, interval: float = 0.08) -> Any:
        """在物理像素 ``x/y`` 连续点击两次。"""
        milliseconds = self._duration_ms(duration, duration_ms, default_ms=20)
        if not math.isfinite(interval) or interval < 0: raise ValueError("interval must be a finite non-negative number of seconds")
        self.tap(x, y, duration_ms=milliseconds); time.sleep(interval)
        return self.tap(x, y, duration_ms=milliseconds)

    def tap_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None, jitter: int = 0) -> Any:
        """按屏幕比例点击；``duration`` 单位秒；``jitter`` 为随机抖动像素数。"""
        return self.tap(*self.relative_point(x_ratio, y_ratio), **({"duration": duration} if duration is not None else {"duration_ms": duration_ms} if duration_ms is not None else {}), jitter=jitter)

    def long_press_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        return self.long_press(*self.relative_point(x_ratio, y_ratio), duration=duration, duration_ms=duration_ms)

    def double_tap_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None, interval: float = 0.08) -> Any:
        return self.double_tap(*self.relative_point(x_ratio, y_ratio), duration=duration, duration_ms=duration_ms, interval=interval)

    def swipe(self, x1: float, y1: float, x2: float, y2: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        milliseconds = self._duration_ms(duration, duration_ms, default_ms=200)
        with self.locked(): return self.eval_python("from ascript.ios.action import slide\nslide(%r, %r, %r, %r, %r)\n_result=True" % (x1, y1, x2, y2, milliseconds))

    def drag(self, x1: float, y1: float, x2: float, y2: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        """从一个物理像素点拖拽到另一个点；默认 0.5 秒。"""
        milliseconds = self._duration_ms(duration, duration_ms, default_ms=500)
        return self.swipe(x1, y1, x2, y2, duration_ms=milliseconds)

    def swipe_relative(self, x1_ratio: float, y1_ratio: float, x2_ratio: float, y2_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        """按屏幕比例滑动；``duration`` 单位秒。"""
        return self.swipe(*self.relative_point(x1_ratio, y1_ratio), *self.relative_point(x2_ratio, y2_ratio), duration=duration, duration_ms=duration_ms)

    def drag_relative(self, x1_ratio: float, y1_ratio: float, x2_ratio: float, y2_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        return self.drag(*self.relative_point(x1_ratio, y1_ratio), *self.relative_point(x2_ratio, y2_ratio), duration=duration, duration_ms=duration_ms)

    def input_text(self, text: str, *, interval_ms: int = 120) -> Any:
        """向当前焦点输入文本；``interval_ms`` 为字符间隔毫秒数。"""
        with self.locked(): return self.eval_python("from ascript.ios.action import input\ninput(%s, %r)\n_result=True" % (json.dumps(text, ensure_ascii=False), interval_ms))

    def home(self) -> Any:
        with self.locked(): return self.eval_python("from ascript.ios.action import home\nhome()\n_result=True")
