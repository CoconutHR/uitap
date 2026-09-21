"""视觉引擎：纯 Pillow 降级路径与 OpenCV 路径必须都能定位同一模板。

``find_image`` 会先用无损精确匹配短路，因此这里刻意使用"非完全相同"的模板，
强制进入模糊匹配，才能覆盖 ``_find_pillow`` / ``_find_opencv``。0.1.1 的
``screenshot_crop_relative`` / ``ocr_raw(region_relative=)`` 回归说明：
未被执行的分支就是未经验证的承诺。
"""
from __future__ import annotations

import importlib
import unittest
from io import BytesIO

import uitap.vision.frame as frame_module
from uitap import ScreenFrame


def _dump(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _source_and_template():
    from PIL import Image

    source = Image.new("RGB", (40, 30), (30, 30, 30))
    template = Image.new("RGB", (8, 6), (0, 0, 0))
    for y in range(6):
        for x in range(8):
            template.putpixel((x, y), (40 + x * 20, 60 + y * 25, 200 - x * 8))
    source.paste(template, (17, 11))
    # 轻改三个像素：精确匹配必然失败，两个模糊引擎都会被真正执行。
    for x, y in ((0, 0), (7, 5), (3, 2)):
        red, green, blue = template.getpixel((x, y))
        template.putpixel((x, y), (red + 6, green - 4, blue + 5))
    return _dump(source), _dump(template)


class VisionEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.template = _source_and_template()

    def setUp(self):
        self._opencv_state = frame_module._OPENCV_AVAILABLE

    def tearDown(self):
        frame_module._OPENCV_AVAILABLE = self._opencv_state

    def test_pillow_and_opencv_find_the_same_location(self):
        frame_module._OPENCV_AVAILABLE = False
        pillow = ScreenFrame(self.source).find_image(self.template, confidence=0.9)
        frame_module._OPENCV_AVAILABLE = True
        opencv = ScreenFrame(self.source).find_image(self.template, confidence=0.9)
        self.assertIsNotNone(pillow, "纯 Pillow 降级路径未能定位模板")
        self.assertIsNotNone(opencv, "OpenCV 路径未能定位模板")
        self.assertEqual((pillow.x, pillow.y), (17, 11))
        self.assertEqual((opencv.x, opencv.y), (17, 11))

    def test_pillow_engine_is_used_when_opencv_is_unavailable(self):
        original = frame_module._opencv_available
        frame_module._opencv_available = lambda: False
        try:
            match = ScreenFrame(self.source).find_image(self.template, confidence=0.9)
        finally:
            frame_module._opencv_available = original
        self.assertIsNotNone(match)
        self.assertEqual((match.x, match.y), (17, 11))

    def test_pillow_engine_returns_none_for_an_absent_template(self):
        from PIL import Image

        frame_module._OPENCV_AVAILABLE = False
        absent = _dump(Image.new("RGB", (8, 6), (250, 10, 10)))
        self.assertIsNone(ScreenFrame(self.source).find_image(absent, confidence=0.95))

    def test_probe_reports_unavailable_when_cv2_cannot_be_imported(self):
        original_import = importlib.import_module

        def blocked(name, *args, **kwargs):
            raise ImportError(name)

        frame_module._OPENCV_AVAILABLE = None
        importlib.import_module = blocked
        try:
            self.assertFalse(frame_module._opencv_available())
        finally:
            importlib.import_module = original_import

    def test_exact_match_still_short_circuits_both_engines(self):
        from PIL import Image

        source = Image.new("RGB", (20, 20), (10, 20, 30))
        template = Image.new("RGB", (3, 3), (200, 100, 50))
        source.paste(template, (8, 9))
        frame_module._OPENCV_AVAILABLE = False  # 禁用引擎也必须能命中：走的是无损精确路径
        match = ScreenFrame(_dump(source)).find_image(_dump(template), confidence=1)
        self.assertEqual((match.x, match.y, match.confidence), (8, 9, 1.0))


if __name__ == "__main__":
    unittest.main()
