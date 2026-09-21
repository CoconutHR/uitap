"""跨平台真机只读冒烟测试入口（Windows / macOS / Linux 通用）。

用法::

    python scripts/smoke.py             # 校验配置后运行真机集成测试
    python scripts/smoke.py --install   # 先安装当前仓库再运行
    python scripts/smoke.py --config tests/integration.json

脚本只负责"校验配置 -> （可选）安装 -> 运行 tests/test_integration.py"，
不做点击、输入、上传、删除、运行项目或 ``eval``。每一步都会回显实际执行的
命令，便于在 CI 或发布记录中留证。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "tests" / "integration.json"
EXAMPLE_CONFIG = ROOT / "tests" / "integration.example.json"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path)


def load_enabled_config(path: Path) -> dict:
    """Return the integration config only when it explicitly opts in."""
    if not path.is_file():
        raise SystemExit(
            f"缺少配置文件 {path}；请先复制 {EXAMPLE_CONFIG} 为 {path} 并填写设备信息与选择器。"
        )
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} 不是合法 JSON：{exc}") from exc
    if not isinstance(config, dict):
        raise SystemExit(f"{path} 必须是 JSON 对象。")
    if config.get("enabled") is not True:
        raise SystemExit(f"{path} 的 enabled 不是 true；确认目标设备与选择器后再显式开启。")
    return config


def run(command: list[str]) -> int:
    print("+ " + " ".join(command), flush=True)
    return subprocess.call(command, cwd=str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="真机集成配置路径；默认 tests/integration.json")
    parser.add_argument("--install", action="store_true", help="运行前先执行 python -m pip install --user --upgrade .")
    args = parser.parse_args(argv)

    config_path = _resolve(args.config)
    load_enabled_config(config_path)
    print(f"配置就绪：{config_path}")

    if args.install:
        code = run([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "."])
        if code:
            return code

    return run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_integration.py", "-v"])


if __name__ == "__main__":
    raise SystemExit(main())
