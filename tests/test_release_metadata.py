"""发布元数据三处版本必须同步：pyproject / 变更说明 / API 文档首部。

该测试在 CI 与 PR 上运行，与打 tag 时执行的 ``scripts/verify-release-tag.py``
一起构成"强制同步"：漏改任何一处都会在合并前和发布前失败。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_version_sync():
    spec = importlib.util.spec_from_file_location("uitap_version_sync", ROOT / "scripts" / "version_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


version_sync = _load_version_sync()


class ReleaseMetadataTests(unittest.TestCase):
    def test_repository_release_metadata_is_synchronized(self):
        self.assertEqual(version_sync.check(ROOT), [], "pyproject、docs/变更说明.md 与 docs/API使用参考.md 的版本必须一致")

    def test_check_reports_api_doc_and_changelog_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "pyproject.toml").write_text('[project]\nname = "uitap"\nversion = "0.1.1"\n', encoding="utf-8")
            (root / "docs" / "变更说明.md").write_text("# 变更说明\n\n## 0.1.0 — 旧版本\n", encoding="utf-8")
            (root / "docs" / "API使用参考.md").write_text("本文对应当前主分支 uitap `0.1.0`；\n", encoding="utf-8")
            problems = version_sync.check(root)
            self.assertTrue(any("首部版本" in problem for problem in problems), problems)
            self.assertTrue(any("缺少" in problem for problem in problems), problems)

    def test_check_reports_missing_api_doc_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "pyproject.toml").write_text('[project]\nname = "uitap"\nversion = "0.1.1"\n', encoding="utf-8")
            (root / "docs" / "变更说明.md").write_text("## 0.1.1 — 示例\n", encoding="utf-8")
            (root / "docs" / "API使用参考.md").write_text("# uitap API 使用参考\n\n没有版本声明。\n", encoding="utf-8")
            problems = version_sync.check(root)
            self.assertTrue(any("未找到" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
