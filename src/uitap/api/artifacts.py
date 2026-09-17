"""Failure evidence capture."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import UitapError


class ArtifactsMixin:
    """失败证据捕获。"""


    def capture_artifacts(self, destination: str | Path, *, prefix: str = "failure", mode: str = "smart") -> dict[str, Path]:
        """Save as much diagnostic evidence as a partially healthy device permits."""
        directory = Path(destination); directory.mkdir(parents=True, exist_ok=True)
        result: dict[str, Path] = {}
        errors: dict[str, str] = {}
        try: result["screenshot"] = self.save_screenshot(directory / f"{prefix}.png")
        except (UitapError, OSError) as exc: errors["screenshot"] = str(exc)
        xml = directory / f"{prefix}.xml"
        try:
            xml.write_text(self.ui_xml(mode=mode), encoding="utf-8")
            result["xml"] = xml.resolve()
        except (UitapError, OSError) as exc: errors["xml"] = str(exc)
        context = directory / f"{prefix}.json"
        payload: dict[str, Any] = {"errors": errors}
        for key, action in (("status", self.status), ("current_app", self.current_app)):
            try: payload[key] = action()
            except UitapError as exc: errors[key] = str(exc)
        context.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result["context"] = context.resolve()
        return result
