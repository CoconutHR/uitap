"""公开 API 文档覆盖检查与 API 面快照守卫。

两个目标：

1. ``docs/API使用参考.md`` 必须覆盖 ``Client`` / ``Device`` / ``Selector`` /
   ``Run`` / ``Tunnel`` 的每一个公开成员，避免"加了方法忘了写文档"。
2. ``tests/api_surface.json`` 记录当前公开 API 面；任何增删都会让
   ``tests/test_api_docs_sync.py`` 失败，迫使改动者显式更新快照。移除成员会被
   ``--update-surface`` 拦下，除非同时提升 minor/major 版本（对应
   ``docs/发布与验收流程.md`` 的版本策略）。

用法::

    python scripts/api_docs_sync.py                   # 校验，不一致时返回码 1
    python scripts/api_docs_sync.py --update-surface  # 更新快照（仅新增时）
    python scripts/api_docs_sync.py --update-surface --allow-removals  # 已升 minor/major 时确认移除
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
API_DOC = Path("docs/API使用参考.md")
SNAPSHOT = Path("tests/api_surface.json")
PUBLIC_TYPES = ("Client", "Device", "Selector", "Run", "Tunnel")


def _load_package(root: Path):
    """导入已安装的 uitap；源码检出未安装时退回 ``src/``。"""
    try:
        import uitap
    except ModuleNotFoundError:
        sys.path.insert(0, str(root / "src"))
        import uitap
    return uitap


def public_members(cls) -> list[str]:
    """Return the sorted callable public members of a class (properties excluded)."""
    return sorted(name for name in dir(cls) if not name.startswith("_") and callable(getattr(cls, name, None)))


def current_surface(root: Path = ROOT) -> dict[str, list[str]]:
    package = _load_package(root)
    return {name: public_members(getattr(package, name)) for name in PUBLIC_TYPES}


def docs_gaps(text: str, surface: dict[str, list[str]]) -> list[str]:
    """Return one message per public type that has members missing from the doc text."""
    gaps = []
    for cls, members in surface.items():
        missing = [member for member in members if member not in text]
        if missing:
            gaps.append(f"{cls} 缺少文档成员: {', '.join(missing)}")
    return gaps


def load_snapshot(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def surface_diff(old: dict[str, list[str]], new: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Return ``(added, removed)`` fully-qualified member names between two surfaces."""
    added: list[str] = []
    removed: list[str] = []
    for cls in sorted(set(old) | set(new)):
        before, after = set(old.get(cls, [])), set(new.get(cls, []))
        added += [f"{cls}.{name}" for name in sorted(after - before)]
        removed += [f"{cls}.{name}" for name in sorted(before - after)]
    return added, removed


def snapshot_problems(snapshot: dict, surface: dict[str, list[str]]) -> list[str]:
    if not snapshot:
        return [f"{SNAPSHOT} 不存在；运行 python scripts/api_docs_sync.py --update-surface 生成"]
    added, removed = surface_diff(snapshot.get("surface", {}), surface)
    if not added and not removed:
        return []
    detail = []
    if added:
        detail.append(f"新增 {len(added)}: {', '.join(added)}")
    if removed:
        detail.append(f"移除 {len(removed)}: {', '.join(removed)}")
    return [f"公开 API 面与 {SNAPSHOT} 不一致（{'；'.join(detail)}）；确认后运行 python scripts/api_docs_sync.py --update-surface"]


def _version_parts(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0


def removal_needs_minor_or_major(old_version: str, new_version: str) -> bool:
    """True when the new version already raised the minor or major component."""
    try:
        old, new = _version_parts(old_version), _version_parts(new_version)
    except (ValueError, IndexError):
        return False
    return new[:2] > old[:2]


def project_version(path: Path) -> str:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib
    return str(tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"])


def check(root: Path = ROOT) -> list[str]:
    """Return every docs-coverage and snapshot problem; empty means healthy."""
    surface = current_surface(root)
    problems = [f"{API_DOC}: {gap}" for gap in docs_gaps((root / API_DOC).read_text(encoding="utf-8"), surface)]
    problems += snapshot_problems(load_snapshot(root / SNAPSHOT), surface)
    return problems


def update_surface(root: Path = ROOT, *, allow_removals: bool = False) -> str:
    surface = current_surface(root)
    snapshot = load_snapshot(root / SNAPSHOT)
    added, removed = surface_diff(snapshot.get("surface", {}), surface)
    version = project_version(root / "pyproject.toml")
    if removed:
        if not allow_removals:
            raise SystemExit(f"拒绝更新：将移除公开 API {', '.join(removed)}。确认是有意为之后追加 --allow-removals。")
        if not removal_needs_minor_or_major(str(snapshot.get("version", "0.0.0")), version):
            raise SystemExit(f"拒绝更新：{snapshot.get('version')} -> {version} 未提升 minor/major，但存在公开 API 移除（{', '.join(removed)}）。")
    target = root / SNAPSHOT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"version": version, "surface": surface}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return f"已写入 {target}（版本 {version}）：新增 {len(added)}、移除 {len(removed)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录；默认脚本所在仓库")
    parser.add_argument("--update-surface", action="store_true", help="用当前公开 API 面重写 tests/api_surface.json")
    parser.add_argument("--allow-removals", action="store_true", help="确认移除公开成员且版本已提升 minor/major")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.update_surface:
        print(update_surface(root, allow_removals=args.allow_removals))
        return 0
    problems = check(root)
    if problems:
        for problem in problems:
            print(f"[API 不一致] {problem}", file=sys.stderr)
        return 1
    print("公开 API 文档覆盖完整，且与 tests/api_surface.json 一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
