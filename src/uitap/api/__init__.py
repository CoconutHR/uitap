"""Per-domain API mixins that compose uitap.core.client.Client."""
from __future__ import annotations

from .app import AppMixin
from .artifacts import ArtifactsMixin
from .colors import ColorsMixin
from .coordinates import CoordinatesMixin
from .detect import DetectMixin
from .files import FilesMixin
from .images import ImagesMixin
from .input import InputMixin
from .logs import LogsMixin
from .ocr import OcrMixin
from .screen import ScreenMixin
from .status import StatusMixin
from .system import SystemMixin
from .tree import TreeMixin


__all__ = ["AppMixin", "ArtifactsMixin", "ColorsMixin", "CoordinatesMixin", "DetectMixin", "FilesMixin", "ImagesMixin", "InputMixin", "LogsMixin", "OcrMixin", "ScreenMixin", "StatusMixin", "SystemMixin", "TreeMixin"]
