"""Device-side SIFT / QR / YOLO detection."""
from __future__ import annotations

import json
from typing import Any

from ..vision import resolve_region


class DetectMixin:
    """设备端 SIFT / 二维码 / YOLO 识别。"""


    def _capture_rect(self, region: Any, region_relative: Any) -> tuple[int, int, int, int]:
        """解析设备端 ``capture(rect=...)`` 的矩形。

        与 :meth:`uitap.vision.ScreenFrame.resolve_region` 共用同一套校验；
        只有比例输入才需要先在本机抓一帧量屏幕尺寸，纯物理像素 ``region``
        不再额外抓屏。
        """
        if region is not None and region_relative is not None: raise ValueError("region and region_relative cannot be combined")
        if region is not None: return resolve_region(None, None, region=region)
        size = self.action_size()
        return resolve_region(int(size["width"]), int(size["height"]), region_relative=region_relative)


    def find_sift(self, templates: Any, *, threshold: float = 0.5, rgb: bool = False, max_res: int = 0, region: Any = None, region_relative: Any = None) -> list[dict[str, Any]]:
        """SIFT 特征匹配：比模板匹配更抗尺度/光照变化；在设备端原生 OpenCV 上执行。

        ``templates`` 为**设备端**小图路径列表（如 ``~/res/img/x.png``）；本机模板请先
        上传到设备。返回 ``[{"result": (x, y), "rect": (l, t, r, b), "center_x", "center_y",
        "confidence"}]``，坐标为截图像素并已叠加 ``region`` 偏移。``max_res=0`` 返回全部命中。
        """
        if not templates: raise ValueError("templates must be a non-empty sequence of device-side paths")
        paths = [str(item) for item in templates]
        if not 0 < float(threshold) <= 1: raise ValueError("threshold must be within (0, 1]")
        left, top, right, bottom = self._capture_rect(region, region_relative)
        code = (
            "import json\n"
            "from ascript.ios.screen import capture\n"
            "from ascript.ios.developer.api import oc\n"
            "img = capture(rect=(%d, %d, %d, %d))\n"
            "res = oc.find_sift(img, %r, threshold=%r, rgb=%r, max_res=%d, offset_xy=(%d, %d))\n"
            "_result = json.dumps(res)\n" % (left, top, right, bottom, paths, float(threshold), bool(rgb), int(max_res), left, top)
        )
        value = self.eval_python(code)
        return value if isinstance(value, list) else []

    def scan_code(self, *, region: Any = None, region_relative: Any = None) -> list[dict[str, Any]]:
        """二维码/条码识别（设备端原生 MLKitx）。返回 ``[{"result": (x, y), "rect",
        "center_x", "center_y", "value", "type", "format"}]``，坐标为截图像素。"""
        left, top, right, bottom = self._capture_rect(region, region_relative)
        code = (
            "import json\n"
            "from ascript.ios.screen import capture\n"
            "from ascript.ios.developer.api import oc\n"
            "img = capture(rect=(%d, %d, %d, %d))\n"
            "res = oc.code_scanner(img, offset_x=%d, offset_y=%d)\n"
            "_result = json.dumps(res)\n" % (left, top, right, bottom, left, top)
        )
        value = self.eval_python(code)
        return value if isinstance(value, list) else []

    def yolov_load(self, param_path: str, bin_path: str, yaml_path: str | None = None, *, use_gpu: bool = False) -> bool:
        """加载 YOLOv8/v11 ncnn 模型（加载一次后可反复 ``yolov_detect``）。

        三个路径均为**设备端**路径（``.param``/``.bin`` 为 ncnn 权重，``yaml_path``
        可选，用于解析类别名）。返回加载是否成功。
        """
        if not param_path or not bin_path: raise ValueError("param_path and bin_path are required device-side paths")
        code = (
            "from ascript.ios.screen import yolov11\n"
            "_result = bool(yolov11.load(%r, %r, %r, use_gpu=%r))\n" % (str(param_path), str(bin_path), str(yaml_path) if yaml_path else None, bool(use_gpu))
        )
        return bool(self.eval_python(code))

    def yolov_detect(self, *, target_size: int = 640, threshold: float = 0.4, nms_threshold: float = 0.5, region: Any = None, region_relative: Any = None) -> list[dict[str, Any]]:
        """YOLO 目标检测：自动截取当前屏幕（或 ``region``/``region_relative`` 区域）推理。

        返回 ``[{"class_id", "confidence", "rect": [l, t, r, b], "tag"}]``，坐标为
        截图像素（区域检测结果已自动加回偏移）。``tag`` 来自加载时 yaml 的类别名。
        需先 ``yolov_load``。
        """
        if not 0 < float(threshold) <= 1: raise ValueError("threshold must be within (0, 1]")
        if not 0 <= float(nms_threshold) <= 1: raise ValueError("nms_threshold must be within 0..1")
        rect = "None"
        if region is not None or region_relative is not None:
            left, top, right, bottom = self._capture_rect(region, region_relative)
            rect = json.dumps([left, top, right, bottom])
        code = (
            "import json\n"
            "from ascript.ios.screen import yolov11\n"
            "_result = json.dumps(yolov11.detect(target_size=%d, threshold=%r, nms_threshold=%r, rect=%s))\n" % (int(target_size), float(threshold), float(nms_threshold), rect)
        )
        value = self.eval_python(code)
        return value if isinstance(value, list) else []

    def yolov_free(self) -> None:
        """释放已加载的 YOLO 模型。"""
        with self.locked(): self.eval_python("from ascript.ios.screen import yolov11\nyolov11.free()\n_result=True")

    def yolov_nc(self) -> int:
        """返回已加载模型的类别数；未加载时为 0。"""
        return int(self.eval_python("from ascript.ios.screen import yolov11\n_result=int(yolov11.nc())"))
