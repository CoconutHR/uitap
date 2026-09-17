"""后台规则监控（Watcher / WatchRule）。"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from ..i18n import t
from .objects import UiObject
from .selector import Selector

if TYPE_CHECKING:
    from .device import Device


@dataclass(frozen=True)
class WatchRule:
    """一条后台监控规则：selector 命中时执行动作。

    ``action`` 为 ``"click"``（点击命中元素）或接收 ``UiObject`` 的可调用
    对象。``max_triggers`` 限制该规则的触发次数，``0`` 表示不限。
    """

    selector: Selector
    action: Callable[[UiObject], Any] | str = "click"
    max_triggers: int = 0
    name: str = ""

class Watcher:
    """轮询式规则监控器；命中后自动执行动作，可用上下文管理器取消。"""

    def __init__(self, device: "Device", rules: list[WatchRule], *, interval: float = 2.0, log: bool = False):
        self.device, self.rules, self.interval, self.log = device, rules, interval, log
        self.triggered: list[str] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool: return bool(self._thread and self._thread.is_alive())
    @property
    def trigger_count(self) -> int: return len(self.triggered)

    def start(self) -> "Watcher":
        if self.is_running: return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None: self._thread.join(timeout=max(2.0, self.interval + 1.0))
        self._thread = None

    def __enter__(self) -> "Watcher": return self.start()
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.stop()
        return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as exc:  # 后台线程不向主流程抛异常，记录后继续轮询。
                self.errors.append(f"{type(exc).__name__}: {exc}")
            self._stop.wait(self.interval)

    def _poll(self) -> None:
        snapshot = self.device.snapshot(mode="full")
        for rule in self.rules:
            name = rule.name or rule.selector.code()
            if rule.max_triggers and self.triggered.count(name) >= rule.max_triggers: continue
            found = snapshot.select(rule.selector).get()
            if found is None: continue
            with self.device.client.locked():
                if callable(rule.action): rule.action(found.object)
                elif rule.action == "click": found.object.click()
                else: raise ValueError(f"unsupported watcher action: {rule.action!r}")
            self.triggered.append(name)
            if self.log: print(t("watcher_triggered", name=name, count=len(self.triggered)))
