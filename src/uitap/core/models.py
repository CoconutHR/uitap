"""Public value objects returned by device APIs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class LogEntry:
    message: str
    kind: str = "o"
    timestamp: str = ""

@dataclass(frozen=True)
class ImageMatch:
    """A visual-template match in physical screen pixels."""
    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2

@dataclass(frozen=True)
class OcrItem:
    text: str
    rect: tuple[int, int, int, int] | None
    confidence: float | None
    raw: Mapping[str, Any]

@dataclass(frozen=True)
class OcrResult:
    items: tuple[OcrItem, ...]
    raw: Any
