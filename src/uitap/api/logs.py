"""Log WebSocket streaming and waiting."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Iterator, Mapping, Optional

from ..core.models import LogEntry
from ..core.transport import LOG_PORT
from ..core.websocket import WebSocket
from ..errors import DeviceConnectionError, ProtocolError
from ..i18n import t


class LogsMixin:
    """日志 WebSocket 读取与等待。"""


    def logs(self, *, duration: Optional[float] = None, stop_event: Optional[threading.Event] = None, reconnects: int = 0, reconnect_delay: float = 1.0) -> Iterator[LogEntry]:
        """Yield device stdout/stderr events from port 10102.

        ``reconnects`` is the number of unexpected disconnects to retry. The
        duration is a total deadline across every connection attempt.
        """
        deadline = time.monotonic() + duration if duration is not None else None
        remaining = max(0, int(reconnects))
        if deadline is not None and time.monotonic() >= deadline:
            return
        while not stop_event or not stop_event.is_set():
            try:
                complete = yield from self._logs_once(deadline=deadline, stop_event=stop_event)
                if complete or remaining <= 0:
                    return
                remaining -= 1
                if not self._wait_to_reconnect(reconnect_delay, deadline, stop_event):
                    return
            except (DeviceConnectionError, ProtocolError, OSError):
                if remaining <= 0:
                    raise
                remaining -= 1
                if not self._wait_to_reconnect(reconnect_delay, deadline, stop_event):
                    return

    @staticmethod
    def _wait_to_reconnect(delay: float, deadline: Optional[float], stop_event: Optional[threading.Event]) -> bool:
        wait = max(0.0, delay)
        if deadline is not None:
            wait = min(wait, max(0.0, deadline - time.monotonic()))
            if wait <= 0:
                return False
        if stop_event is not None:
            return not stop_event.wait(wait)
        time.sleep(wait)
        return deadline is None or time.monotonic() < deadline

    def _logs_once(self, *, deadline: Optional[float], stop_event: Optional[threading.Event]) -> Iterator[LogEntry]:
        headers = {"Cookie": f"airscript={self.password}"} if self.password else None
        connect_timeout = self.timeout
        if deadline is not None:
            connect_timeout = min(connect_timeout, max(0.001, deadline - time.monotonic()))
        try:
            websocket = WebSocket.connect(self.address.host, LOG_PORT, "/log/", timeout=connect_timeout, headers=headers, deadline=deadline, stop_event=stop_event)
        except TimeoutError:
            if (deadline is not None and time.monotonic() >= deadline) or (stop_event is not None and stop_event.is_set()):
                return True
            raise
        except OSError as exc:
            raise DeviceConnectionError(t("cannot_reach_logs", host=self.address.host, port=LOG_PORT, detail=exc)) from exc
        try:
            while not stop_event or not stop_event.is_set():
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return True
                    websocket.settimeout(min(0.5, remaining))
                try:
                    message = websocket.receive()
                except TimeoutError:
                    continue
                if message is None:
                    return websocket.close_code in {None, 1000, 1001}
                opcode, payload = message
                if opcode != 0x1:
                    continue
                text = payload.decode("utf-8")
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    event = None
                if isinstance(event, Mapping):
                    yield LogEntry(str(event.get("msg", "")), str(event.get("type", "o")), str(event.get("time", "")))
                else:
                    yield LogEntry(text)
            return True
        finally:
            websocket.close()

    def save_logs(self, destination: str | Path, *, duration: Optional[float] = None, reconnects: int = 0) -> int:
        """Write log events as UTF-8 JSON Lines and return the event count."""
        destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with destination.open("w", encoding="utf-8") as stream:
            for entry in self.logs(duration=duration, reconnects=reconnects):
                stream.write(json.dumps({"message": entry.message, "kind": entry.kind, "timestamp": entry.timestamp}, ensure_ascii=False) + "\n")
                count += 1
        return count

    def wait_for_log(self, pattern: str, *, timeout: float = 10.0, regex: bool = False, reconnects: int = 1) -> LogEntry | None:
        """Wait for a log line containing ``pattern`` (or matching its regex)."""
        matcher = re.compile(pattern).search if regex else lambda value: pattern in value
        for entry in self.logs(duration=timeout, reconnects=reconnects):
            if matcher(entry.message): return entry
        return None
