"""CLI 命令注册表一致性：parser / handler / _HELP / API 参考四处必须同步。

新增命令的约定见 ``AGENTS.md``：``commands/`` 写 handler + ``parser.py`` 加参数
与 ``_HELP`` 文案 + 注册表登记，并写进 API 参考。这个测试把"漏登记"从人工记忆
变成 CI 失败。
"""
from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from uitap.cli.commands import COMMANDS
from uitap.cli.parser import _HELP, _parser


ROOT = Path(__file__).resolve().parent.parent
API_DOC = ROOT / "docs" / "API使用参考.md"
# 这些命令由 cli/app.py 直接分发，不经过 COMMANDS 注册表。
DIRECT_COMMANDS = {"help", "init", "doctor", "inspect", "tunnel"}


def subcommands() -> set[str]:
    action = next(item for item in _parser()._actions if isinstance(item, argparse._SubParsersAction))
    return set(action.choices)


class CliRegistryTests(unittest.TestCase):
    def test_every_command_has_a_handler_and_help_text(self):
        commands = subcommands()
        self.assertTrue(commands, "parser 未注册任何命令")
        self.assertEqual(sorted(commands - DIRECT_COMMANDS - set(COMMANDS)), [], "命令缺少 COMMANDS handler（或未登记到 DIRECT_COMMANDS）")
        self.assertEqual(sorted(commands - set(_HELP)), [], "命令缺少 _HELP 文案")
        self.assertEqual(sorted(set(_HELP) - commands), [], "_HELP 中存在 parser 已删除的命令")

    def test_every_command_is_documented(self):
        documented = API_DOC.read_text(encoding="utf-8")
        self.assertEqual(sorted(name for name in subcommands() if name not in documented), [], "命令未写入 docs/API使用参考.md")

    def test_direct_commands_are_dispatched_in_app(self):
        import uitap.cli.app as app

        source = Path(app.__file__).read_text(encoding="utf-8")
        for name in sorted(DIRECT_COMMANDS):
            self.assertIn(f'"{name}"', source, f"{name} 在 cli/app.py 中没有分发分支")


if __name__ == "__main__":
    unittest.main()
