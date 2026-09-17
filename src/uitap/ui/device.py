"""高层设备入口 Device 与延迟查询集合 UiCollection。"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from ..api.coordinates import swipe_gesture
from ..i18n import t
from .objects import UiObject
from .selector import Selector
from .snapshot import SnapshotCollection, UiSnapshot
from .watch import WatchRule, Watcher

if TYPE_CHECKING:
    from ..core import Client


@dataclass
class Device:
    """类似 uiautomator2 的高层设备入口。"""

    client: "Client"

    def selector(self, *, mode: str = "smart", **attributes: Any) -> Selector:
        selector = Selector(mode=mode)
        aliases = {"text": "label", "resource_id": "name", "description": "name", "class_name": "type"}
        for key, value in attributes.items(): selector = selector.with_attr(aliases.get(key, key), value)
        return selector
    def __call__(self, **attributes: Any) -> "UiCollection": return UiCollection(self, self.selector(**attributes))
    def snapshot(self, *, mode: str = "full") -> UiSnapshot: return UiSnapshot(self, self.client.ui_tree(mode=mode), mode=mode)
    def find_all(self, selector: Selector, *, normalize: bool = True) -> list[UiObject]:
        """查询 selector 匹配的全部元素。

        ``normalize=False`` 只需一次树请求，节点坐标为设备端逻辑点；
        适合存在性检查，但此时不能对返回元素执行点击。
        """
        if not normalize and selector.point is not None: raise ValueError("point selectors require normalized queries")
        data = self.client.ui_tree(selector=selector.payload(), mode=selector.mode, x=(selector.point or (0, 0))[0], y=(selector.point or (0, 0))[1], normalize=normalize)
        views = data.get("views") or []
        if not isinstance(views, list): raise ValueError("invalid element list returned by device")
        return [UiObject(self, dict(item), selector) for item in views if isinstance(item, Mapping)]
    def find(self, selector: Selector, *, timeout: float = 0, interval: float = 0.3, log: bool = False) -> UiObject | None: return UiCollection(self, selector).get(timeout=timeout, interval=interval, log=log)
    def wait(self, selector: Selector, *, timeout: float = 10.0, interval: float = 0.3, log: bool = False) -> UiObject:
        result = self.find(selector, timeout=timeout, interval=interval, log=log)
        if result is None: raise LookupError(f"element did not appear within {timeout}s: {selector.code()}")
        return result
    def wait_any(self, selectors: Mapping[str, Selector], *, timeout: float = 10.0, interval: float = 0.3, log: bool = False) -> tuple[str, UiObject]:
        if not selectors: raise ValueError("selectors must not be empty")
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout
        while True:
            snapshot = self.snapshot(mode="full")
            for name, selector in selectors.items():
                found = snapshot.select(selector).get()
                if found: return name, found.object
            if time.monotonic() >= deadline: raise LookupError(f"none of the elements appeared within {timeout}s: {', '.join(selectors)}")
            time.sleep(min(interval, deadline - time.monotonic()))
    def wait_gone(self, selector: Selector, *, timeout: float = 10.0, interval: float = 0.3, log: bool = False) -> bool: return UiCollection(self, selector).wait_gone(timeout=timeout, interval=interval, log=log)
    def scroll_until_element(self, selectors: Selector | Mapping[str, Selector], *, direction: str = "down", swipe_relative: tuple[float, float, float, float] | None = None, x1_ratio: float | None = None, y1_ratio: float | None = None, x2_ratio: float | None = None, y2_ratio: float | None = None, timeout: float = 20.0, interval: float = 0.5, max_swipes: int = 10, duration: float | None = None, duration_ms: int | None = None, log: bool = False, initial_delay: bool = True) -> "UiObject | tuple[str, UiObject]":
        """沿 ``direction`` 滑动，直到语义控件出现。

        每轮只读取一次完整控件树并在本地匹配全部候选 selector；传入单个
        ``Selector`` 返回 ``UiObject``，传入 ``{名称: Selector}`` 映射返回
        ``(命中名称, UiObject)``。``timeout``/``interval`` 单位秒，
        ``duration`` 为每次滑动的秒数；超时或滑动次数用尽抛 ``LookupError``。
        """
        if timeout < 0 or interval <= 0 or max_swipes < 0:
            raise ValueError("timeout must be non-negative, interval positive, and max_swipes non-negative")
        single = isinstance(selectors, Selector)
        mapping = {"element": selectors} if single else dict(selectors)
        if not mapping: raise ValueError("selectors must not be empty")
        x1, y1, x2, y2 = swipe_gesture(direction, swipe_relative, x1_ratio, y1_ratio, x2_ratio, y2_ratio)
        deadline = time.monotonic() + timeout
        if initial_delay: time.sleep(min(interval, timeout))
        for swipe_number in range(max_swipes + 1):
            snapshot = self.snapshot(mode="full")
            for name, selector in mapping.items():
                found = snapshot.select(selector).get()
                if found is not None:
                    if log: print(t("element_scroll_match", attempt=swipe_number + 1, name=name))
                    return found.object if single else (name, found.object)
            if log: print(t("element_scroll_next", attempt=swipe_number + 1))
            if swipe_number == max_swipes or time.monotonic() >= deadline: break
            self.swipe_relative(x1, y1, x2, y2, duration=duration, duration_ms=duration_ms)
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
        if log: print(t("element_scroll_stop", attempt=swipe_number + 1))
        raise LookupError(f"none of the elements appeared after {max_swipes} {direction} swipes or before timeout: {', '.join(mapping)}")
    def watch(self, *rules: Selector | WatchRule, interval: float = 2.0, log: bool = False) -> Watcher:
        """启动后台规则监控；直接传 ``Selector`` 等价于命中即点击。

        返回的 ``Watcher`` 支持上下文管理器（退出自动停止），``.triggered``
        记录触发顺序，``.errors`` 记录轮询异常。监控线程与主线程的动作
        共用设备锁，不会交叉执行点击。
        """
        normalized: list[WatchRule] = []
        for index, rule in enumerate(rules):
            if isinstance(rule, Selector): normalized.append(WatchRule(selector=rule, name=f"rule_{index}"))
            elif isinstance(rule, WatchRule): normalized.append(rule)
            else: raise ValueError("watch rules must be Selector or WatchRule instances")
        if not normalized: raise ValueError("watch requires at least one rule")
        return Watcher(self, normalized, interval=interval, log=log)
    def wait_current_app(self, expected: Any, *, timeout: float = 10.0, interval: float = 0.3) -> Mapping[str, Any]: return self.client.wait_current_app(expected, timeout=timeout, interval=interval)
    def app_start(self, bundle_id: str, *, timeout: float = 15.0, wait: bool = True) -> Any: return self.client.app_start(bundle_id, timeout=timeout, wait=wait)
    def app_stop(self, bundle_id: str) -> Any: return self.client.app_stop(bundle_id)
    def app_state(self, bundle_id: str) -> Any: return self.client.app_state(bundle_id)
    def lock_screen(self) -> Any: return self.client.lock_screen()
    def unlock_screen(self) -> Any: return self.client.unlock_screen()
    def get_clipboard(self) -> Any: return self.client.get_clipboard()
    def set_clipboard(self, content: str) -> Any: return self.client.set_clipboard(content)
    def orientation(self) -> Any: return self.client.orientation()
    def open_url(self, url: str) -> Any: return self.client.open_url(url)
    def dismiss_keyboard(self) -> Any: return self.client.dismiss_keyboard()
    def press_key(self, key: str) -> Any: return self.client.press_key(key)
    def device_info(self) -> Any: return self.client.device_info()
    def battery_info(self) -> Any: return self.client.battery_info()
    def open_notification(self) -> Any: return self.client.open_notification()
    def screen_cache(self, enabled: bool) -> Any: return self.client.screen_cache(enabled)
    def notify(self, msg: str, title: str | None = None, *, notification_id: str = "9096") -> Any: return self.client.notify(msg, title, notification_id=notification_id)
    def find_sift(self, templates: Any, **kwargs: Any) -> Any: return self.client.find_sift(templates, **kwargs)
    def scan_code(self, **kwargs: Any) -> Any: return self.client.scan_code(**kwargs)
    def yolov_load(self, param_path: str, bin_path: str, yaml_path: str | None = None, *, use_gpu: bool = False) -> Any: return self.client.yolov_load(param_path, bin_path, yaml_path, use_gpu=use_gpu)
    def yolov_detect(self, **kwargs: Any) -> Any: return self.client.yolov_detect(**kwargs)
    def yolov_free(self) -> Any: return self.client.yolov_free()
    def yolov_nc(self) -> Any: return self.client.yolov_nc()
    def click_if_unique(self, selector: Selector, *, timeout: float = 0, interval: float = 0.3, duration: float | None = None, duration_ms: int | None = None) -> UiObject:
        deadline = time.monotonic() + timeout
        with self.client.locked():
            while True:
                matches = self.find_all(selector)
                if len(matches) == 1:
                    matches[0].click(duration=duration, duration_ms=duration_ms)
                    return matches[0]
                if time.monotonic() >= deadline:
                    raise LookupError(f"selector matched {len(matches)} elements within {timeout}s: {selector.code()}")
                time.sleep(min(interval, deadline - time.monotonic()))
    def dump_hierarchy(self, *, mode: str = "smart") -> str: return self.client.ui_xml(mode=mode)
    def screenshot(self, destination: str | None = None) -> bytes | Any: return self.client.save_screenshot(destination) if destination else self.client.screenshot()
    def screenshot_crop(self, left: int, top: int, right: int, bottom: int) -> bytes: return self.client.screenshot_crop(left, top, right, bottom)
    def screenshot_crop_relative(self, left: float, top: float, right: float, bottom: float) -> bytes: return self.client.screenshot_crop_relative(left, top, right, bottom)
    def save_screenshot_crop(self, destination: str | Path, left: int, top: int, right: int, bottom: int) -> Path: return self.client.save_screenshot_crop(destination, left, top, right, bottom)
    def save_screenshot_crop_relative(self, destination: str | Path, left: float, top: float, right: float, bottom: float) -> Path: return self.client.save_screenshot_crop_relative(destination, left, top, right, bottom)
    def tap(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None, jitter: int = 0) -> Any: return self.client.tap(x, y, duration=duration, duration_ms=duration_ms, jitter=jitter)
    def click_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None, jitter: int = 0) -> Any: return self.client.tap_relative(x_ratio, y_ratio, duration=duration, duration_ms=duration_ms, jitter=jitter)
    def click_rel(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None, jitter: int = 0) -> Any: return self.click_relative(x_ratio, y_ratio, duration=duration, duration_ms=duration_ms, jitter=jitter)
    def click_random(self, x1: float, y1: float, x2: float, y2: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.click_random(x1, y1, x2, y2, duration=duration, duration_ms=duration_ms)
    def click_random_relative(self, x1_ratio: float, y1_ratio: float, x2_ratio: float, y2_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.click_random_relative(x1_ratio, y1_ratio, x2_ratio, y2_ratio, duration=duration, duration_ms=duration_ms)
    def slide_path(self, points: Any, *, durations: Any = None, duration: int = 800, touch_down_duration: int = 0, touch_up_duration: int = 0) -> Any: return self.client.slide_path(points, durations=durations, duration=duration, touch_down_duration=touch_down_duration, touch_up_duration=touch_up_duration)
    def slide_path_relative(self, points: Any, *, durations: Any = None, duration: int = 800, touch_down_duration: int = 0, touch_up_duration: int = 0) -> Any: return self.client.slide_path_relative(points, durations=durations, duration=duration, touch_down_duration=touch_down_duration, touch_up_duration=touch_up_duration)
    def touch_and_slide(self, from_x: float, from_y: float, to_x: float, to_y: float, *, touch_down_duration: int = 500, touch_move_duration: int = 1000, touch_up_duration: int = 500) -> Any: return self.client.touch_and_slide(from_x, from_y, to_x, to_y, touch_down_duration=touch_down_duration, touch_move_duration=touch_move_duration, touch_up_duration=touch_up_duration)
    def touch_and_slide_relative(self, from_x_ratio: float, from_y_ratio: float, to_x_ratio: float, to_y_ratio: float, *, touch_down_duration: int = 500, touch_move_duration: int = 1000, touch_up_duration: int = 500) -> Any: return self.client.touch_and_slide_relative(from_x_ratio, from_y_ratio, to_x_ratio, to_y_ratio, touch_down_duration=touch_down_duration, touch_move_duration=touch_move_duration, touch_up_duration=touch_up_duration)
    def long_press(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.long_press(x, y, duration=duration, duration_ms=duration_ms)
    def long_press_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.long_press_relative(x_ratio, y_ratio, duration=duration, duration_ms=duration_ms)
    def double_tap(self, x: float, y: float, *, duration: float | None = None, duration_ms: int | None = None, interval: float = 0.08) -> Any: return self.client.double_tap(x, y, duration=duration, duration_ms=duration_ms, interval=interval)
    def double_tap_relative(self, x_ratio: float, y_ratio: float, *, duration: float | None = None, duration_ms: int | None = None, interval: float = 0.08) -> Any: return self.client.double_tap_relative(x_ratio, y_ratio, duration=duration, duration_ms=duration_ms, interval=interval)
    def swipe(self, x1: float, y1: float, x2: float, y2: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.swipe(x1, y1, x2, y2, duration=duration, duration_ms=duration_ms)
    def swipe_relative(self, x1_ratio: float, y1_ratio: float, x2_ratio: float, y2_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.swipe_relative(x1_ratio, y1_ratio, x2_ratio, y2_ratio, duration=duration, duration_ms=duration_ms)
    def drag(self, x1: float, y1: float, x2: float, y2: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.drag(x1, y1, x2, y2, duration=duration, duration_ms=duration_ms)
    def drag_relative(self, x1_ratio: float, y1_ratio: float, x2_ratio: float, y2_ratio: float, *, duration: float | None = None, duration_ms: int | None = None) -> Any: return self.client.drag_relative(x1_ratio, y1_ratio, x2_ratio, y2_ratio, duration=duration, duration_ms=duration_ms)
    def capture_frame(self) -> Any: return self.client.capture_frame()
    def pixel(self, x: int, y: int) -> Any: return self.client.pixel(x, y)
    def pixel_relative(self, x_ratio: float, y_ratio: float) -> Any: return self.client.pixel_relative(x_ratio, y_ratio)
    def pixels(self, points: Any) -> Any: return self.client.pixels(points)
    def pixels_relative(self, points: Any) -> Any: return self.client.pixels_relative(points)
    def ocr(self, **kwargs: Any) -> Any: return self.client.ocr(**kwargs)
    def ocr_raw(self, **kwargs: Any) -> Any: return self.client.ocr_raw(**kwargs)
    def find_ocr_text(self, text: str, **kwargs: Any) -> Any: return self.client.find_ocr_text(text, **kwargs)
    def wait_ocr_text(self, text: str, **kwargs: Any) -> Any: return self.client.wait_ocr_text(text, **kwargs)
    def color_matches(self, x: int, y: int, expected: Any, **kwargs: Any) -> bool: return self.client.color_matches(x, y, expected, **kwargs)
    def color_matches_relative(self, x_ratio: float, y_ratio: float, expected: Any, **kwargs: Any) -> bool: return self.client.color_matches_relative(x_ratio, y_ratio, expected, **kwargs)
    def find_color(self, expected: Any, **kwargs: Any) -> Any: return self.client.find_color(expected, **kwargs)
    def count_color(self, expected: Any, **kwargs: Any) -> int: return self.client.count_color(expected, **kwargs)
    def assert_color(self, x: int, y: int, expected: Any, **kwargs: Any) -> Any: return self.client.assert_color(x, y, expected, **kwargs)
    def assert_color_relative(self, x_ratio: float, y_ratio: float, expected: Any, **kwargs: Any) -> Any: return self.client.assert_color_relative(x_ratio, y_ratio, expected, **kwargs)
    def scroll_until_image(self, template: str | Path | bytes, **kwargs: Any) -> Any: return self.client.scroll_until_image(template, **kwargs)
    def find_image(self, template: str | Path | bytes, **kwargs: Any) -> Any: return self.client.find_image(template, **kwargs)
    def find_images(self, templates: Mapping[str, str | Path | bytes], **kwargs: Any) -> Any: return self.client.find_images(templates, **kwargs)
    def find_any_image(self, templates: Mapping[str, str | Path | bytes], **kwargs: Any) -> Any: return self.client.find_any_image(templates, **kwargs)
    def wait_image(self, template: str | Path | bytes, **kwargs: Any) -> Any: return self.client.wait_image(template, **kwargs)
    def wait_any_image(self, templates: Mapping[str, str | Path | bytes], **kwargs: Any) -> Any: return self.client.wait_any_image(templates, **kwargs)
    def wait_image_gone(self, template: str | Path | bytes, **kwargs: Any) -> bool: return self.client.wait_image_gone(template, **kwargs)
    def tap_image(self, template: str | Path | bytes, **kwargs: Any) -> Any: return self.client.tap_image(template, **kwargs)

@dataclass
class UiCollection:
    """一个选择器对应的延迟查询控件集合。"""
    device: Device
    selector: Selector
    @property
    def exists(self) -> bool: return self.exists_fast()
    @property
    def count(self) -> int: return len(self.all(normalize=False))
    @property
    def info(self) -> Mapping[str, Any]:
        item = self.get()
        if item is None: raise LookupError(f"element not found: {self.selector.code()}")
        return item.info
    def all(self, *, normalize: bool = True) -> list[UiObject]: return self.device.find_all(self.selector, normalize=normalize)
    def exists_fast(self) -> bool: return bool(self.all(normalize=False))
    def snapshot(self, *, mode: str = "full") -> SnapshotCollection: return self.device.snapshot(mode=mode).select(self.selector)
    def get(self, *, timeout: float = 0, interval: float = 0.3, log: bool = False) -> UiObject | None:
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout; attempt = 0
        while True:
            attempt += 1; found = self.all()
            if found:
                if log: print(t("selector_wait_found", attempt=attempt, selector=self.selector.code()))
                return found[0]
            if log: print(t("selector_wait_missing", attempt=attempt, selector=self.selector.code()))
            if time.monotonic() >= deadline: return None
            time.sleep(min(interval, deadline - time.monotonic()))
    def wait_gone(self, *, timeout: float = 10.0, interval: float = 0.3, log: bool = False) -> bool:
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        deadline = time.monotonic() + timeout; attempt = 0
        while True:
            attempt += 1
            if not self.exists:
                if log: print(t("selector_wait_gone", attempt=attempt, selector=self.selector.code()))
                return True
            if log: print(t("selector_wait_present", attempt=attempt, selector=self.selector.code()))
            if time.monotonic() >= deadline: return False
            time.sleep(min(interval, deadline - time.monotonic()))
    def click(self, *, duration: float | None = None, duration_ms: int | None = None) -> Any:
        item = self.get()
        if item is None: raise LookupError(f"element not found: {self.selector.code()}")
        return item.click(duration=duration, duration_ms=duration_ms)
    def click_exists(self, *, timeout: float = 0) -> bool:
        item = self.get(timeout=timeout)
        if item is None: return False
        item.click(); return True
    def set_text(self, text: str, *, interval_ms: int = 120) -> Any:
        item = self.get()
        if item is None: raise LookupError(f"element not found: {self.selector.code()}")
        return item.set_text(text, interval_ms=interval_ms)
    def get_text(self) -> str:
        item = self.get()
        if item is None: raise LookupError(f"element not found: {self.selector.code()}")
        return item.get_text()
    def scroll(self, direction: str = "down", distance: float = 1.0) -> Any:
        item = self.get()
        if item is None: raise LookupError(f"element not found: {self.selector.code()}")
        return item.scroll(direction, distance)
    def scroll_to(self, selector: "Selector | dict[str, Any]", **kwargs: Any) -> Any:
        item = self.get()
        if item is None: raise LookupError(f"element not found: {self.selector.code()}")
        return item.scroll_to(selector, **kwargs)
