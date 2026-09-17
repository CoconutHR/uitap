"""Device status probing and compatibility fallbacks."""
from __future__ import annotations

import json
from typing import Any

from ..errors import DeviceConnectionError, DeviceOperationError, DeviceResponseError
from ..i18n import t


class StatusMixin:
    """设备状态探测与兼容降级。"""


    def ping(self) -> str:
        raw = self.request("POST", "/api/model/pip", data=b"{}", headers={"Content-Type": "application/json"}, timeout=5)
        return "iOS" if not raw.strip() else ("Android" if json.loads(raw.decode("utf-8")).get("code") == 1 else "iOS")

    def status(self) -> dict[str, Any]:
        """读取设备状态并在 iOS 4001 状态接口异常时降级。

        ``screen`` 为实际物理分辨率；``logical_screen`` 仅用于协议诊断。
        """
        try:
            result = self._ok(self.json("GET", "/api/status")).get("data", {})
            if not isinstance(result, dict):
                raise DeviceResponseError("invalid status returned by device", body=repr(result))
            self._attach_status_screen(result)
            return result
        except DeviceOperationError as exc:
            issue = "ios_objc_property_callable" if "ObjCStrInstance" in str(exc) and "callable" in str(exc) else "device_status_error"
            result: dict[str, Any] = {
                "available": True,
                "health": "degraded",
                "status_api_error": str(exc),
                "compatibility": {
                    "status_api": {"state": "degraded", "issue": issue, "message": t("status_fallback_summary")},
                    "capabilities": {},
                },
                "platform": self.ping(),
            }
            self._attach_status_screen(result, result["compatibility"]["capabilities"])
            try:
                result["current_app"] = self.current_app()
                result["compatibility"]["capabilities"]["current_app"] = "available"
            except (DeviceOperationError, DeviceResponseError, DeviceConnectionError):
                result["compatibility"]["capabilities"]["current_app"] = "unavailable"
            self._backfill_status_fields(result)
            return result

    def _attach_status_screen(self, result: dict[str, Any], capabilities: dict[str, Any] | None = None) -> None:
        try:
            result["logical_screen"] = self._logical_screen()
        except (DeviceOperationError, DeviceResponseError, DeviceConnectionError):
            pass
        try:
            result["screen"] = self.screen_size()
            if capabilities is not None: capabilities["screen"] = "available"
        except (DeviceOperationError, DeviceResponseError, DeviceConnectionError):
            if capabilities is not None: capabilities["screen"] = "unavailable"

    def _backfill_status_fields(self, result: dict[str, Any]) -> None:
        """iOS 4001 服务端 ``/api/status`` 崩溃时，用一次 ``eval`` 回填等价的只读字段。

        设备端 ``api_status`` 把 ``languageCode`` 属性当方法调用导致整个接口报错
        （根因记录见 docs/生产使用指南.md 的兼容性章节）。这里只回填不改变设备
        状态的 ``device``/``system``/``app``/``python`` 字段；battery 等需要打开
        设备监控开关的字段保持缺失。补偿失败时静默跳过，不影响降级返回。
        """
        code = (
            "import json\n"
            "def _g(v):\n"
            "    try: return v() if callable(v) else v\n"
            "    except Exception: return v\n"
            "_o = {}\n"
            "try:\n"
            "    from rubicon.objc import ObjCClass\n"
            "    _d = _g(ObjCClass('UIDevice').currentDevice)\n"
            "    _o['device'] = {'brand': 'Apple', 'manufacturer': 'Apple', 'abi': 'arm64',"
            " 'model': str(_g(_d.model) or ''), 'full_name': str(_g(_d.name) or ''),"
            " 'product': str(_g(_d.systemName) or '')}\n"
            "    _o['system'] = {'os_name': 'iOS', 'ios_version': str(_g(_d.systemVersion) or ''),"
            " 'language': str(_g(_g(ObjCClass('NSLocale').currentLocale).languageCode) or ''),"
            " 'timezone': str(_g(_g(ObjCClass('NSTimeZone').localTimeZone).name) or '')}\n"
            "    _b = _g(ObjCClass('NSBundle').mainBundle)\n"
            "    _o['app'] = {'version': str(_b.objectForInfoDictionaryKey_('CFBundleShortVersionString') or ''),"
            " 'build': str(_b.objectForInfoDictionaryKey_('CFBundleVersion') or ''),"
            " 'package': str(_g(_b.bundleIdentifier) or '')}\n"
            "    import platform as _p\n"
            "    _o['python'] = {'version': _p.python_version()}\n"
            "except Exception:\n"
            "    pass\n"
            "_result = json.dumps(_o)\n"
        )
        try:
            value = self.eval_python(code)
        except (DeviceOperationError, DeviceResponseError, DeviceConnectionError):
            return
        if not isinstance(value, dict) or not value: return
        fields = sorted(str(key) for key in value)
        result.update(value)
        result["compatibility"]["status_api"]["compensated_fields"] = fields
        result["compatibility"]["status_api"]["message"] = (
            t("status_fallback_summary") + " " + t("status_compensated_fields", fields=", ".join(fields))
        )

    def packages(self) -> list[Any]:
        """返回设备端 Python 包列表，元素通常为 ``[名称, 版本]``。"""
        status = self.status()
        packages = status.get("python", {}).get("packages")
        if packages is not None:
            return packages
        value = self.eval_python(
            "import importlib.metadata as md, json\n"
            "_packages = {d.metadata['Name']: d.version for d in md.distributions() if d.metadata.get('Name')}\n"
            "_result = json.dumps(sorted(_packages.items()))"
        )
        return value if isinstance(value, list) else []
