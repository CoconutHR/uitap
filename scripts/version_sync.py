"""发布元数据一致性守卫：``pyproject.toml`` / 变更说明 / API 文档首部版本。

三处必须指向同一个 ``X.Y.Z``：

1. ``pyproject.toml`` 的 ``project.version``（打包与 PyPI 的权威版本）；
2. ``docs/变更说明.md`` 中必须存在 ``## X.Y.Z`` 小节；
3. ``docs/API使用参考.md`` 首部必须声明形如 ``uitap `X.Y.Z``` 的版本。

用法::

    python scripts/version_sync.py            # 校验，不一致时返回码 1
    python scripts/version_sync.py --root .   # 指定仓库根目录

该检查同时被 ``scripts/verify-release-tag.py``（发布工作流）与
``tests/test_release_metadata.py``（每次 CI 与 PR）调用，因此漏改任何一处
都会在合并前和打 tag 时被拦下。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 release runners install tomli.
    import tomli as tomllib


VERSION_PATTERN = r"\d+\.\d+\.\d+"
API_DOC_SCAN_LINES = 12

_API_DOC_VERSION = re.compile(rf"uitap\s*`({VERSION_PATTERN})`")
_CHANGELOG_VERSION = re.compile(rf"^##\s+({VERSION_PATTERN})", re.MULTILINE)


def project_version(path: Path) -> str:
    """Return ``project.version`` from a pyproject file."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def api_doc_version(path: Path) -> str:
    """Return the version declared in the first lines of the API reference."""
    for line in path.read_text(encoding="utf-8").splitlines()[:API_DOC_SCAN_LINES]:
        match = _API_DOC_VERSION.search(line)
        if match:
            return match.group(1)
    raise ValueError(f"{path} 前 {API_DOC_SCAN_LINES} 行内未找到形如 uitap `X.Y.Z` 的版本声明")


def changelog_versions(path: Path) -> list[str]:
    """Return every ``## X.Y.Z`` section version in the changelog."""
    return _CHANGELOG_VERSION.findall(path.read_text(encoding="utf-8"))


def check(root: Path) -> list[str]:
    """Return one message per inconsistency; an empty list means synchronized."""
    pyproject = root / "pyproject.toml"
    changelog = root / "docs" / "变更说明.md"
    api_doc = root / "docs" / "API使用参考.md"
    problems: list[str] = []
    try:
        version = project_version(pyproject)
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        return [f"{pyproject}: 无法读取 project.version（{exc}）"]
    if not re.fullmatch(VERSION_PATTERN, version):
        problems.append(f"{pyproject}: 版本 {version!r} 不是 X.Y.Z 形式")

    try:
        declared = api_doc_version(api_doc)
    except (OSError, ValueError) as exc:
        problems.append(str(exc))
    else:
        if declared != version:
            problems.append(f"{api_doc}: 首部版本 {declared} 与 {pyproject} 的 {version} 不一致")

    try:
        versions = changelog_versions(changelog)
    except OSError as exc:
        problems.append(f"{changelog}: 无法读取（{exc}）")
    else:
        if version not in versions:
            existing = "、".join(versions) or "无"
            problems.append(f"{changelog}: 缺少 `## {version}` 版本小节（现有：{existing}）")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="仓库根目录；默认脚本所在仓库")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    problems = check(root)
    if problems:
        for problem in problems:
            print(f"[版本不一致] {problem}", file=sys.stderr)
        print("请同步 pyproject.toml、docs/变更说明.md 与 docs/API使用参考.md 后重试。", file=sys.stderr)
        return 1
    print(f"版本三处一致：{project_version(root / 'pyproject.toml')}（pyproject / 变更说明 / API 文档）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
