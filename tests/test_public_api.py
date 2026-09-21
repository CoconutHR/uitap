"""补齐未被任何测试触及的公开 API，防止再次出现"改了签名、漏改调用点"。

这些用例直接来自一次覆盖审计：``screenshot_crop_relative`` 与
``ocr_raw(region_relative=...)`` 曾在 0.1.1 因为 ``ScreenFrame._region``
的签名收窄而回归（调用点仍是旧的 3 参形式，TypeError），而当时没有任何
测试覆盖这两个入口。此文件把这类"相对坐标 / 裁剪 / 等待 / 选择器构造"
入口固定下来。
"""
from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from uitap import Client, Device, ImageMatch, Selector
from uitap import OcrItem, OcrResult
from uitap.core.png import png_size


def _png(size=(100, 200), color: str = "black", paste: tuple[int, int, int, str] | None = None) -> bytes:
    image = Image.new("RGB", size, color)
    if paste is not None:
        left, top, width, height, patch_color = paste
        image.paste(Image.new("RGB", (width, height), patch_color), (left, top))
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class _FakeScreen(unittest.TestCase):
    """一个截图被替换为固定 PNG 的 Client，不发起任何网络请求。"""

    def setUp(self):
        self.client = Client("127.0.0.1:9096")
        self.client.screenshot = lambda: _png()
        self.device = Device(self.client)


class CropTests(_FakeScreen):
    def test_relative_and_absolute_crops_return_expected_sizes(self):
        # 0.1.1 回归点：相对裁剪曾经因为内部签名收窄而 TypeError。
        self.assertEqual(png_size(self.client.screenshot_crop_relative(0, 0, 0.5, 0.5)), (50.0, 100.0))
        self.assertEqual(png_size(self.client.screenshot_crop(10, 20, 60, 120)), (50.0, 100.0))

    def test_crops_validate_their_bounds(self):
        with self.assertRaises(ValueError): self.client.screenshot_crop_relative(0.6, 0.1, 0.2, 0.9)
        with self.assertRaises(ValueError): self.client.screenshot_crop(0, 0, 500, 2000)

    def test_save_crop_helpers_write_real_png_files(self):
        with tempfile.TemporaryDirectory() as directory:
            relative = self.client.save_screenshot_crop_relative(Path(directory) / "relative.png", 0, 0, 0.5, 0.5)
            absolute = self.client.save_screenshot_crop(Path(directory) / "absolute.png", 0, 0, 50, 100)
            self.assertEqual(png_size(relative.read_bytes()), (50.0, 100.0))
            self.assertEqual(png_size(absolute.read_bytes()), (50.0, 100.0))


class RelativeScreenTests(_FakeScreen):
    def setUp(self):
        super().setUp()
        self.client.screenshot = lambda: _png((10, 10), "black", (4, 4, 2, 2, "red"))

    def test_relative_pixels_and_colors_resolve_against_the_frame(self):
        self.assertEqual(self.client.pixel_relative(0.5, 0.5).rgb, (255, 0, 0))
        self.assertEqual([color.rgb for color in self.client.pixels_relative([(0.5, 0.5), (0.0, 0.0)])], [(255, 0, 0), (0, 0, 0)])
        self.assertTrue(self.client.color_matches_relative(0.5, 0.5, "#FF0000"))
        self.assertEqual(self.client.assert_color_relative(0.5, 0.5, "#FF0000").hex, "#FF0000")
        with self.assertRaises(AssertionError): self.client.assert_color_relative(0.0, 0.0, "#FF0000")
        with self.assertRaises(ValueError): self.client.assert_color_relative(1.5, 0.5, "#FF0000")


class RelativeInputTests(_FakeScreen):
    def test_relative_wrappers_convert_to_physical_pixels(self):
        recorded: dict[str, object] = {}
        self.client.long_press = lambda x, y, **kwargs: recorded.setdefault("long", (x, y, kwargs))
        self.client.swipe = lambda *args, **kwargs: recorded.setdefault("swipe", (args, kwargs))
        taps: list[tuple[float, float]] = []
        self.client.tap = lambda x, y, **kwargs: taps.append((x, y))
        self.device.long_press_relative(0.5, 0.25, duration_ms=800)
        self.device.drag_relative(0.1, 0.2, 0.3, 0.4, duration=0.5)
        self.device.double_tap_relative(0.5, 0.5)
        self.assertEqual(recorded["long"], (50.0, 50.0, {"duration": None, "duration_ms": 800}))
        self.assertEqual(recorded["swipe"], ((10.0, 40.0, 30.0, 80.0), {"duration_ms": 500}))
        self.assertEqual(taps, [(50.0, 100.0), (50.0, 100.0)])  # double_tap 连续两次

    def test_relative_wrappers_reject_out_of_range_ratios(self):
        for call in (
            lambda: self.device.long_press_relative(1.5, 0.5),
            lambda: self.device.double_tap_relative(0.5, -0.1),
            lambda: self.device.drag_relative(0.1, 0.2, 1.2, 0.4),
        ):
            with self.assertRaises(ValueError): call()


class ImageWaitTests(_FakeScreen):
    def test_wait_image_gone_reports_disappearance_and_timeout(self):
        sequence = [ImageMatch(0, 0, 1, 1, 1.0), None]
        self.client.find_image = lambda *args, **kwargs: sequence.pop(0)
        self.assertTrue(self.client.wait_image_gone("template.png", timeout=1, interval=0.01, initial_delay=False))
        self.client.find_image = lambda *args, **kwargs: ImageMatch(0, 0, 1, 1, 1.0)
        self.assertFalse(self.client.wait_image_gone("template.png", timeout=0, interval=0.01, initial_delay=False))

    def test_tap_image_clicks_the_match_center(self):
        recorded: list[tuple[float, ...]] = []
        self.client.wait_image = lambda *args, **kwargs: ImageMatch(10, 20, 4, 6, 1.0)
        self.client.tap = lambda *args, **kwargs: recorded.append(args)
        match = self.device.tap_image("template.png")
        self.assertEqual(match.center, (12.0, 23.0))
        self.assertEqual(recorded, [(12.0, 23.0)])


class OcrRegionTests(_FakeScreen):
    def setUp(self):
        super().setUp()
        self.calls: list[str] = []
        self.client.gp = lambda class_id, params, **kwargs: self.calls.append(params) or "{}"

    def test_ocr_raw_converts_relative_region_to_pixel_rect(self):
        # 0.1.1 回归点：frame._region 收窄为 2 参后此处仍传 3 参。
        self.client.ocr_raw(region_relative=(0, 0, 0.5, 0.5))
        self.assertIn("rect=[0|0|50|100]", self.calls[-1])
        self.client.ocr_raw()
        self.assertNotIn("rect=", self.calls[-1])

    def test_ocr_parses_items_from_a_relative_region(self):
        payload = {"data": [{"text": "登录", "confidence": 0.9, "rect": [1, 2, 3, 4]}]}
        self.client.gp = lambda *args, **kwargs: payload
        result = self.client.ocr(region_relative=(0, 0, 0.5, 0.5))
        self.assertEqual([item.text for item in result.items], ["登录"])
        self.assertEqual(result.items[0].rect, (1, 2, 3, 4))

    def test_wait_ocr_text_returns_the_first_match_and_times_out(self):
        results = [OcrResult((), {}), OcrResult((OcrItem("登录成功", None, None, {}),), {})]
        self.client.ocr = lambda **kwargs: results.pop(0)
        self.assertEqual(self.client.wait_ocr_text("登录成功", timeout=1, interval=0.01).text, "登录成功")
        self.client.ocr = lambda **kwargs: OcrResult((), {})
        with self.assertRaises(LookupError): self.client.wait_ocr_text("不会出现", timeout=0, interval=0.01)
        with self.assertRaises(ValueError): self.client.wait_ocr_text("x", timeout=0, interval=0)
        with self.assertRaises(ValueError): self.client.wait_ocr_text("x", timeout=-1)


class TreeAndDetectTests(_FakeScreen):
    def test_dump_hierarchy_forwards_the_requested_mode(self):
        self.client.ui_xml = lambda **kwargs: kwargs.get("mode", "missing")
        self.assertEqual(self.device.dump_hierarchy(mode="full"), "full")
        self.assertEqual(self.device.dump_hierarchy(), "smart")

    def test_ocr_raw_facade_forwards_keyword_arguments(self):
        seen: list[dict] = []
        self.client.ocr_raw = lambda **kwargs: seen.append(kwargs)
        self.device.ocr_raw(region=(1, 2, 3, 4))
        self.assertEqual(seen, [{"region": (1, 2, 3, 4)}])


class DetectRegionTests(_FakeScreen):
    """设备端检测 API 的区域解析：与 ScreenFrame.resolve_region 共用一套语义。"""

    def setUp(self):
        super().setUp()
        self.captured: list[str] = []
        self.client.eval_python = lambda code: self.captured.append(code) or []
        self.size_calls = 0

    def _measure(self, width=1000.0, height=2000.0):
        def action_size():
            self.size_calls += 1
            return {"width": width, "height": height}
        self.client.action_size = action_size

    def _forbid_measure(self):
        def action_size():
            raise AssertionError("绝对像素 region 不应触发本机抓帧")
        self.client.action_size = action_size

    def test_absolute_region_skips_the_host_capture(self):
        self._forbid_measure()
        self.client.scan_code(region=(10, 20, 30, 40))
        self.assertIn("capture(rect=(10, 20, 30, 40))", self.captured[-1])
        self.client.yolov_detect(region=(1, 2, 3, 4))
        self.assertIn("rect=[1, 2, 3, 4]", self.captured[-1])

    def test_relative_and_full_screen_regions_measure_once(self):
        self._measure()
        self.client.scan_code(region_relative=(0, 0, 0.5, 0.5))
        self.assertIn("capture(rect=(0, 0, 500, 1000))", self.captured[-1])
        self.client.scan_code()
        self.assertIn("capture(rect=(0, 0, 1000, 2000))", self.captured[-1])
        self.assertEqual(self.size_calls, 2)

    def test_detect_and_vision_share_one_region_resolver(self):
        from uitap.vision import resolve_region

        self._measure()
        self.client.find_sift(["~/res/img/a.png"], region_relative=(0.1, 0.2, 0.5, 0.6))
        expected = resolve_region(1000, 2000, region_relative=(0.1, 0.2, 0.5, 0.6))
        self.assertIn(f"capture(rect={expected})", self.captured[-1])

    def test_detect_regions_reject_input_the_vision_resolver_rejects(self):
        self._measure()
        with self.assertRaises(ValueError): self.client.scan_code(region=(0, 0, 1, 1), region_relative=(0, 0, 1, 1))
        with self.assertRaises(ValueError): self.client.scan_code(region=(0, 0, 0.5, 0.5))          # 比例数值必须走 region_relative
        with self.assertRaises(ValueError): self.client.scan_code(region=(100, 200, 50, 60))          # left >= right
        with self.assertRaises(ValueError): self.client.scan_code(region_relative=(0.5, 0.5, 0.5, 0.5))  # 退化区域
        with self.assertRaises(ValueError): self.client.scan_code(region_relative=(0, 0, 1.5, 1))


class SelectorBuilderTests(unittest.TestCase):
    def test_state_and_limit_builders_encode_the_device_payload(self):
        selector = Selector().visible().selected(False).focused(True).traits(3).child_count(2).with_limits(max_depth=5, max_children=7)
        payload = selector.payload(find=3)
        self.assertEqual(payload["find"], 3)
        self.assertEqual(payload["depth"], 5)
        self.assertEqual(payload["children"], 7)
        self.assertEqual(payload["sel"], [
            {"key": "visible", "params": "true"},
            {"key": "selected", "params": "false"},
            {"key": "focused", "params": "true"},
            {"key": "traits", "params": 3},
            {"key": "childCount", "params": 2},
        ])

    def test_contains_match_encodes_a_params_pair(self):
        payload = Selector().name("login", contains=True).payload()
        self.assertEqual(payload["sel"], [{"key": "name", "params": ["login", 1]}])
        self.assertEqual(Selector().text("登录").code(), "device.selector().label('登录')")

    def test_builders_reject_invalid_inputs(self):
        with self.assertRaises(ValueError): Selector().with_attr("unknown", 1)
        with self.assertRaises(ValueError): Selector().with_limits(max_depth=-1)
        with self.assertRaises(ValueError): Selector().with_limits(max_children=-1)


if __name__ == "__main__":
    unittest.main()
