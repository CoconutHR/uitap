"""The uitap device-service client, assembled from per-domain API mixins."""
from __future__ import annotations

from ..api.app import AppMixin
from ..api.artifacts import ArtifactsMixin
from ..api.colors import ColorsMixin
from ..api.coordinates import CoordinatesMixin
from ..api.detect import DetectMixin
from ..api.files import FilesMixin
from ..api.images import ImagesMixin
from ..api.input import InputMixin
from ..api.logs import LogsMixin
from ..api.ocr import OcrMixin
from ..api.screen import ScreenMixin
from ..api.status import StatusMixin
from ..api.system import SystemMixin
from ..api.tree import TreeMixin
from .transport import Transport


class Client(Transport, StatusMixin, ScreenMixin, CoordinatesMixin, InputMixin, AppMixin, SystemMixin, TreeMixin, ImagesMixin, DetectMixin, OcrMixin, ColorsMixin, FilesMixin, LogsMixin, ArtifactsMixin):
    """uitap 单台设备服务客户端。

    参数 ``address`` 为 ``HOST[:PORT]``；``password`` 为可选服务密码；
    ``timeout`` 单位为秒。所有公开坐标均使用截图物理像素。
    """
