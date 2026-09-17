"""控件选择器与匹配判定。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Selector:
    """不可变控件选择器。"""

    attributes: tuple[tuple[str, Any, int], ...] = ()
    mode: str = "smart"
    point: tuple[float, float] | None = None
    max_depth: int = 0
    max_children: int = 30

    EQUAL = 0
    CONTAINS = 1
    MATCHES = 2
    _FIELDS = frozenset({"name", "label", "value", "title", "type", "enabled", "selected", "focused", "visible", "index", "traits", "childCount"})

    def with_attr(self, key: str, value: Any, *, match: int = EQUAL) -> "Selector":
        if key not in self._FIELDS:
            raise ValueError(f"unsupported selector attribute: {key}")
        return Selector(self.attributes + ((key, value, match),), self.mode, self.point, self.max_depth, self.max_children)

    def name(self, value: str, *, contains: bool = False) -> "Selector": return self.with_attr("name", value, match=self.CONTAINS if contains else self.EQUAL)
    def label(self, value: str, *, contains: bool = False) -> "Selector": return self.with_attr("label", value, match=self.CONTAINS if contains else self.EQUAL)
    def text(self, value: str, *, contains: bool = False) -> "Selector": return self.label(value, contains=contains)
    def value(self, value: str, *, contains: bool = False) -> "Selector": return self.with_attr("value", value, match=self.CONTAINS if contains else self.EQUAL)
    def type(self, value: str) -> "Selector": return self.with_attr("type", value)
    def title(self, value: str, *, contains: bool = False) -> "Selector": return self.with_attr("title", value, match=self.CONTAINS if contains else self.EQUAL)
    def enabled(self, value: bool = True) -> "Selector": return self.with_attr("enabled", value)
    def visible(self, value: bool = True) -> "Selector": return self.with_attr("visible", value)
    def selected(self, value: bool = True) -> "Selector": return self.with_attr("selected", value)
    def focused(self, value: bool = True) -> "Selector": return self.with_attr("focused", value)
    def traits(self, value: int) -> "Selector": return self.with_attr("traits", value)
    def child_count(self, value: int) -> "Selector": return self.with_attr("childCount", value)
    def index(self, value: int) -> "Selector": return self.with_attr("index", value)
    def at(self, x: float, y: float) -> "Selector": return Selector(self.attributes, "point", (x, y), self.max_depth, self.max_children)
    def at_relative(self, x_ratio: float, y_ratio: float) -> "Selector": return Selector(self.attributes, "point_relative", (x_ratio, y_ratio), self.max_depth, self.max_children)
    def full(self) -> "Selector": return Selector(self.attributes, "full", self.point, self.max_depth, self.max_children)
    def with_limits(self, *, max_depth: int = 0, max_children: int = 30) -> "Selector":
        if max_depth < 0 or max_children < 0: raise ValueError("selector limits cannot be negative")
        return Selector(self.attributes, self.mode, self.point, max_depth, max_children)

    def payload(self, *, find: int = 99999) -> dict[str, Any]:
        conditions = []
        for key, value, match in self.attributes:
            if isinstance(value, bool): value = "true" if value else "false"
            conditions.append({"key": key, "params": [value, match] if match else value})
        result: dict[str, Any] = {"sel": conditions, "find": find}
        if self.max_depth: result["depth"] = self.max_depth
        if self.max_children != 30: result["children"] = self.max_children
        return result

    def code(self) -> str:
        calls = []
        for key, value, match in self.attributes:
            suffix = ", contains=True" if match == self.CONTAINS else ""
            calls.append(f".{key}({value!r}{suffix})")
        head = "device.selector()"
        if self.mode == "full": head = "device.selector(mode='full')"
        if self.point: head += f".at({self.point[0]!r}, {self.point[1]!r})"
        return head + "".join(calls)

def _matches(info: Mapping[str, Any], selector: Selector) -> bool:
    for key, expected, match in selector.attributes:
        actual = info.get(key)
        if match == Selector.CONTAINS:
            if str(expected) not in str(actual or ""):
                return False
        elif actual != expected:
            return False
    return True
