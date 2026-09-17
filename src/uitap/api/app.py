"""App lifecycle and foreground state."""
from __future__ import annotations

import time
from typing import Any, Callable, Mapping

from ..errors import DeviceOperationError, DeviceResponseError


class AppMixin:
    """应用生命周期与前台状态。"""


    _APP_STATE_NAMES = {0: "not_running", 1: "not_running", 2: "background", 3: "foreground", 4: "foreground"}

    def current_app(self) -> dict[str, Any]:
        return self._ok(self.json("GET", "/api/node/package")).get("data", {})

    def wait_current_app(self, expected: str | Callable[[Mapping[str, Any]], bool], *, timeout: float = 10.0, interval: float = 0.3) -> dict[str, Any]:
        if timeout < 0 or interval <= 0: raise ValueError("timeout must be non-negative and interval must be positive")
        matcher = (lambda app: app.get("bundle_id") == expected) if isinstance(expected, str) else expected
        if not callable(matcher): raise ValueError("expected must be a bundle id or callable")
        deadline = time.monotonic() + timeout
        while True:
            app = self.current_app()
            if matcher(app): return app
            if time.monotonic() >= deadline: raise LookupError(f"foreground app did not match within {timeout}s")
            time.sleep(min(interval, deadline - time.monotonic()))

    def app_start(self, bundle_id: str, *, timeout: float = 15.0, wait: bool = True) -> dict[str, Any]:
        """启动指定 bundle id 的 App。

        ``wait=True`` 时等待其进入前台（最多 ``timeout`` 秒）；返回启动后的
        ``current_app`` 结果。部分 App 首次启动有隐私弹窗，建议配合 ``watch()``。
        """
        if not bundle_id or not isinstance(bundle_id, str): raise ValueError("bundle_id must be a non-empty string")
        code = "from ascript.ios import system\nsystem.app_start(%r)\n_result=True" % bundle_id
        with self.locked(): self.eval_python(code)
        if not wait: return self.current_app()
        try:
            return self.wait_current_app(bundle_id, timeout=timeout)
        except LookupError:
            raise DeviceOperationError(f"app {bundle_id!r} did not reach the foreground within {timeout}s") from None

    def app_stop(self, bundle_id: str) -> None:
        """停止指定 bundle id 的 App（等价于上划杀掉）。"""
        if not bundle_id or not isinstance(bundle_id, str): raise ValueError("bundle_id must be a non-empty string")
        code = "from ascript.ios import system\nsystem.app_stop(%r)\n_result=True" % bundle_id
        with self.locked(): self.eval_python(code)

    def app_state(self, bundle_id: str) -> dict[str, Any]:
        """返回 App 运行状态：``{"code": 0-4, "state": "not_running|background|foreground"}``。

        设备端 WDA 状态码为静态值（真机实测前台/后台/被杀均返回相同码，
        且不随状态变化），因此 ``"background"`` 与 ``"not_running"`` 在该
        实现上不可区分；客户端在同一帧内同时读取 ``app_current``，bundle
        一致时强制判定为 foreground，其余情况报 not_running。
        """
        if not bundle_id or not isinstance(bundle_id, str): raise ValueError("bundle_id must be a non-empty string")
        code = (
            "from ascript.ios import system as s\n"
            "import json\n"
            "_code = s.app_state(%r)\n"
            "_cur = ''\n"
            "try:\n"
            "    _cur = s.app_current().bundle_id or ''\n"
            "except Exception:\n"
            "    pass\n"
            "_result = json.dumps({'code': int(_code) if _code is not None else -1, 'current': _cur})\n" % bundle_id
        )
        value = self.eval_python(code)
        if not isinstance(value, dict): raise DeviceResponseError("invalid app state returned by device", body=repr(value))
        numeric = value.get("code", -1)
        state = self._APP_STATE_NAMES.get(numeric, "unknown")
        if value.get("current") == bundle_id and state != "foreground": state = "foreground"
        return {"code": numeric, "state": state}
