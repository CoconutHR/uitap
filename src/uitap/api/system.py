"""Clipboard, orientation, keys, battery and notifications."""
from __future__ import annotations

from typing import Any

from ..errors import DeviceResponseError


class SystemMixin:
    """系统操作：剪贴板、方向、按键、电池与通知。"""


    def lock_screen(self) -> None:
        """锁定屏幕。

        设备端不提供可靠的锁屏状态查询：WDA ``/wda/locked`` 在实测设备上
        恒为 False（锁屏前后均如此，已真机确认）。需要判断时可对截图做
        全黑检测。
        """
        with self.locked(): self.eval_python("from ascript.ios import system\nsystem.lock()\n_result=True")

    def unlock_screen(self) -> None:
        """解锁屏幕；已设锁屏密码的设备无法用本方法解锁，需真机输入密码。"""
        with self.locked(): self.eval_python("from ascript.ios import system\nsystem.unlock()\n_result=True")

    def get_clipboard(self) -> str:
        """读取设备剪贴板文本。"""
        value = self.eval_python("from ascript.ios import system\n_result=str(system.get_clipboard() or '')")
        return value if isinstance(value, str) else str(value)

    def set_clipboard(self, content: str) -> None:
        """写入文本到设备剪贴板。"""
        if not isinstance(content, str): raise ValueError("content must be a string")
        with self.locked(): self.eval_python("from ascript.ios import system\nsystem.set_clipboard(%r)\n_result=True" % content)

    def orientation(self) -> str:
        """返回当前屏幕方向：``"portrait"`` 或 ``"landscape"``。

        设备端 WDA 客户端未提供设置方向的接口，程序化旋转暂不可用；
        方向跟随设备物理旋转实时变化（已真机验证）。
        """
        value = self.eval_python("from ascript.ios import system\n_result=str(system.screen_orientation()).split('.')[-1].lower()")
        if not isinstance(value, str) or value not in ("portrait", "landscape"): raise DeviceResponseError("invalid orientation returned by device", body=repr(value))
        return value

    def open_url(self, url: str) -> None:
        """通过系统 open 打开 URL 或 App 深链。"""
        if not isinstance(url, str) or not url.strip(): raise ValueError("url must be a non-empty string")
        with self.locked(): self.eval_python("from ascript.ios import system\nsystem.open_url(%r)\n_result=True" % url)

    def dismiss_keyboard(self) -> None:
        """尝试收起当前软键盘。"""
        with self.locked(): self.eval_python("from ascript.ios.system import client\nclient.keyboard_dismiss()\n_result=True")

    # 友好名 -> 设备端 wdapy.Keycode 枚举成员名
    _KEY_CODES = {"home": "HOME", "volume_up": "VOLUME_UP", "volume_down": "VOLUME_DOWN", "power": "POWER", "power_plus_home": "POWER_PLUS_HOME", "snapshot": "SNAPSHOT"}

    def press_key(self, key: str) -> None:
        """发送按键事件。``key``：home、volume_up、volume_down、power、power_plus_home、snapshot。"""
        try: member = self._KEY_CODES[key]
        except KeyError: raise ValueError(f"key must be one of {sorted(self._KEY_CODES)}") from None
        with self.locked(): self.eval_python("from ascript.ios.system import client\nfrom ascript.ios.wdapy import Keycode\nclient.press(Keycode.%s)\n_result=True" % member)

    def device_info(self) -> dict[str, Any]:
        """返回设备信息字典；字段缺失时为 ``None``（如 model、name、uuid、locale、界面风格）。"""
        value = self.eval_python(
            "import json\n"
            "from ascript.ios.system import client\n"
            "di = client.device_info()\n"
            "_result = json.dumps({'model': di.model, 'name': di.name, 'uuid': di.uuid,"
            " 'time_zone': di.time_zone, 'current_locale': di.current_locale,"
            " 'user_interface_idiom': di.user_interface_idiom, 'user_interface_style': di.user_interface_style,"
            " 'is_simulator': di.is_simulator})\n"
        )
        return value if isinstance(value, dict) else {}

    def battery_info(self) -> dict[str, Any]:
        """返回电池信息：``{"level": 0.0-1.0, "state": "unplugged|charging|full|unknown"}``。"""
        value = self.eval_python(
            "import json\n"
            "from ascript.ios.system import client\n"
            "bi = client.battery_info()\n"
            "_result = json.dumps({'level': bi.level, 'state': str(bi.state).split('.')[-1].split(':')[0].strip().lower()})\n"
        )
        if not isinstance(value, dict): raise DeviceResponseError("invalid battery info returned by device", body=repr(value))
        try: value["level"] = float(value.get("level"))
        except (TypeError, ValueError): value["level"] = None
        state = str(value.get("state") or "").split(".")[-1].split(":")[0].strip().lower()
        battery_states = {"0": "unknown", "1": "unplugged", "2": "charging", "3": "full"}
        value["state"] = battery_states.get(state, state) or None
        return value

    def open_notification(self) -> None:
        """下拉打开通知中心；收起可再上滑或按 home。"""
        size = self.action_size()
        w, h = float(size["width"]), float(size["height"])
        self.swipe(w / 2, 3, w / 2, h * 0.5, duration_ms=400)

    def notify(self, msg: str, title: str | None = None, *, notification_id: str = "9096") -> None:
        """发送系统通知（脚本完成/告警提醒）。"""
        if not msg or not isinstance(msg, str): raise ValueError("msg must be a non-empty string")
        with self.locked(): self.eval_python("from ascript.ios.developer.api import oc\noc.notify(%r, %r, %r)\n_result=True" % (msg, title, notification_id))
