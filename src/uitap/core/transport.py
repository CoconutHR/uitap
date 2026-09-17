"""Transport core: HTTP session, retries, device locking and device-side eval."""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Optional

from ..errors import DeviceConnectionError, DeviceOperationError, DeviceResponseError
from ..i18n import t
from ..runtime import device_lock
from .address import DeviceAddress


LOG_PORT = 10102
"""Device-side log WebSocket port; the device service does not make it configurable."""

_DEFAULT_LOCK_TIMEOUT = object()

class Transport:
    """Shared base for :class:`~uitap.core.client.Client`."""


    def __init__(self, address: str | DeviceAddress, *, password: str = "", timeout: float = 15.0, retries: int = 1, coordinate_cache_ttl: float = 1.0, lock_id: str | None = None, lock_timeout: float | None = None):
        self.address = DeviceAddress.parse(address)
        self.lock_id = lock_id
        self.password, self.timeout, self.retries = password, float(timeout), max(0, int(retries))
        if lock_timeout is not None:
            try:
                lock_timeout = float(lock_timeout)
            except (TypeError, ValueError) as exc:
                raise ValueError("lock_timeout must be a finite non-negative number of seconds") from exc
            if not math.isfinite(lock_timeout) or lock_timeout < 0 or lock_timeout > threading.TIMEOUT_MAX:
                raise ValueError("lock_timeout must be a finite non-negative number of seconds")
        self.lock_timeout = lock_timeout
        if not math.isfinite(coordinate_cache_ttl) or coordinate_cache_ttl < 0: raise ValueError("coordinate_cache_ttl must be a finite non-negative number of seconds")
        self.coordinate_cache_ttl = float(coordinate_cache_ttl)
        self._space_cache: tuple[float, dict[str, float], dict[str, float]] | None = None
        self._hid_vision_available: bool | None = None
        self._vision_action_dimensions: dict[str, float] | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.address}"

    def locked(self, *, timeout: float | None | object = _DEFAULT_LOCK_TIMEOUT):
        """Return the reentrant cross-process mutex for actions against this device."""
        return device_lock(self.address, lock_id=self.lock_id, timeout=self.lock_timeout if timeout is _DEFAULT_LOCK_TIMEOUT else timeout)

    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> dict[str, str]:
        result = dict(extra or {})
        if self.password:
            result["Cookie"] = f"airscript={self.password}"
        return result

    def request(self, method: str, path: str, *, params: Optional[Mapping[str, Any]] = None, form: Optional[Mapping[str, Any]] = None, data: Optional[bytes] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> bytes:
        """调用已确认的原始 HTTP 接口并返回字节。

        ``path`` 必须以 ``/`` 开头；``timeout`` 单位秒。仅在高层 API
        尚未覆盖的稳定设备端接口中使用。
        """
        if not path.startswith("/"):
            raise ValueError(t("path_must_start"))
        if form is not None and data is not None:
            raise ValueError(t("form_data_exclusive"))
        if params:
            path += ("&" if "?" in path else "?") + urllib.parse.urlencode(params, doseq=True)
        if form is not None:
            data = urllib.parse.urlencode(form, doseq=True).encode("utf-8")
            headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
        req = urllib.request.Request(self.base_url + path, data=data, method=method.upper(), headers=self._headers(headers))
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout or self.timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                raise DeviceResponseError(f"HTTP {exc.code} for {path}", status=exc.code, body=exc.read().decode("utf-8", "replace")[:2000]) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.2 * (2 ** attempt))
        raise DeviceConnectionError(t("cannot_reach_device", address=self.address, detail=last_error)) from last_error

    def json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        raw = self.request(method, path, **kwargs)
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeviceResponseError(t("invalid_json", path=path), body=raw[:1000].decode("utf-8", "replace")) from exc
        if not isinstance(value, dict):
            raise DeviceResponseError(t("expected_object", path=path), body=repr(value))
        return value

    @staticmethod
    def _ok(value: Mapping[str, Any]) -> dict[str, Any]:
        if value.get("code") not in (None, 1, True):
            raise DeviceOperationError(str(value.get("msg") or value))
        return dict(value)

    def eval_python(self, code: str, *, image: str = "") -> Any:
        if not code.strip():
            raise ValueError("code is empty")
        with self.locked(): value = self._ok(self.json("POST", "/api/gp/eval", form={"code": code, "image": image}, timeout=60)).get("data")
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
