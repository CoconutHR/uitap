"""uiautomator2 风格的高层对象 API。"""
from __future__ import annotations

from .device import Device, UiCollection
from .objects import UiObject
from .run import Run
from .selector import Selector
from .snapshot import SnapshotCollection, SnapshotNode, UiSnapshot
from .watch import Watcher, WatchRule


__all__ = ["Device", "Selector", "UiCollection", "UiObject", "UiSnapshot", "SnapshotNode", "SnapshotCollection", "WatchRule", "Watcher", "Run"]
