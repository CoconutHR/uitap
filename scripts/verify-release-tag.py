"""Verify that a release tag matches the project version and release metadata."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from version_sync import check, project_version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args()

    version = project_version(args.pyproject)
    expected = f"v{version}"
    if args.tag != expected:
        parser.error(f"tag {args.tag!r} does not match package version {version!r}")

    problems = check(args.pyproject.resolve().parent)
    if problems:
        for problem in problems:
            print(f"[版本不一致] {problem}", file=sys.stderr)
        parser.error("release metadata is out of sync; fix pyproject.toml, docs/变更说明.md and docs/API使用参考.md before tagging")

    print(f"verified {args.tag} for package version {version} with synchronized release metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
