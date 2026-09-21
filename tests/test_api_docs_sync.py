"""公开 API 文档覆盖与 API 面快照守卫的测试。

``test_repository_docs_and_surface_snapshot_are_in_sync`` 会在 CI 与 PR 上运行：
新增公开方法却没写进 ``docs/API使用参考.md``，或改动了公开 API 却没更新
``tests/api_surface.json``，都会在这里失败。
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_api_docs_sync():
    spec = importlib.util.spec_from_file_location("uitap_api_docs_sync", ROOT / "scripts" / "api_docs_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api_docs_sync = _load_api_docs_sync()


class ApiDocsSyncTests(unittest.TestCase):
    def test_repository_docs_and_surface_snapshot_are_in_sync(self):
        self.assertEqual(api_docs_sync.check(ROOT), [], "API 参考缺项或公开 API 面快照过期")

    def test_docs_gaps_reports_missing_members(self):
        surface = api_docs_sync.current_surface(ROOT)
        gaps = api_docs_sync.docs_gaps("", surface)
        self.assertTrue(gaps)
        self.assertTrue(any(gap.startswith("Client ") for gap in gaps), gaps)

    def test_docs_gaps_accepts_the_real_document(self):
        text = (ROOT / "docs" / "API使用参考.md").read_text(encoding="utf-8")
        self.assertEqual(api_docs_sync.docs_gaps(text, api_docs_sync.current_surface(ROOT)), [])

    def test_surface_diff_detects_additions_and_removals(self):
        added, removed = api_docs_sync.surface_diff({"Client": ["tap", "swipe"]}, {"Client": ["tap", "long_press"]})
        self.assertEqual(added, ["Client.long_press"])
        self.assertEqual(removed, ["Client.swipe"])

    def test_snapshot_problems_accepts_identical_and_rejects_changed_surfaces(self):
        surface = {"Client": ["tap"]}
        self.assertEqual(api_docs_sync.snapshot_problems({"version": "0.1.1", "surface": surface}, surface), [])
        problems = api_docs_sync.snapshot_problems({"version": "0.1.1", "surface": {"Client": ["tap", "swipe"]}}, surface)
        self.assertTrue(any("移除" in problem for problem in problems), problems)
        self.assertEqual(api_docs_sync.snapshot_problems({}, surface), [f"{api_docs_sync.SNAPSHOT} 不存在；运行 python scripts/api_docs_sync.py --update-surface 生成"])

    def test_removal_requires_a_minor_or_major_bump(self):
        self.assertFalse(api_docs_sync.removal_needs_minor_or_major("0.1.1", "0.1.2"))
        self.assertTrue(api_docs_sync.removal_needs_minor_or_major("0.1.1", "0.2.0"))
        self.assertTrue(api_docs_sync.removal_needs_minor_or_major("0.2.0", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
