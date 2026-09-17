"""uitap — dependency-free iOS device automation with a uiautomator2-style API."""

from importlib.metadata import PackageNotFoundError, version as _package_version

from .core import Client, DeviceAddress, ImageMatch, LogEntry, OcrItem, OcrResult
from .ui import Device, Selector, UiCollection, UiObject, UiSnapshot, SnapshotNode, SnapshotCollection, WatchRule, Watcher
from .vision import PixelColor, ScreenFrame
from .ui import Run
from .tunnel import Tunnel, IProxyTunnel
from .errors import UitapError, DeviceConnectionError, DeviceLockTimeoutError, DeviceOperationError, DeviceResponseError, IProxyNotFoundError, ProtocolError, TunnelError

try:
    __version__ = _package_version("uitap")
except PackageNotFoundError:  # running from a source checkout without installation
    __version__ = "0.0.0+unknown"


def connect(address: str, *, password: str = "", timeout: float = 15.0, retries: int = 1, lock_id: str | None = None, lock_timeout: float | None = None) -> Device:
    """Connect to an iOS device using a uiautomator2-like entry point."""
    return Device(Client(address, password=password, timeout=timeout, retries=retries, lock_id=lock_id, lock_timeout=lock_timeout))

__all__ = ["Client", "DeviceAddress", "ImageMatch", "LogEntry", "OcrItem", "OcrResult", "PixelColor", "ScreenFrame", "Device", "Selector", "UiCollection", "UiObject", "UiSnapshot", "SnapshotNode", "SnapshotCollection", "WatchRule", "Watcher", "Run", "Tunnel", "IProxyTunnel", "connect", "UitapError", "DeviceConnectionError", "DeviceLockTimeoutError", "DeviceOperationError", "DeviceResponseError", "ProtocolError", "TunnelError", "IProxyNotFoundError"]
