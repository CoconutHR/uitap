"""本地控件树快照与查询集合。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from .objects import UiObject
from .selector import Selector, _matches

if TYPE_CHECKING:
    from .device import Device


@dataclass(frozen=True)
class SnapshotNode:
    snapshot: "UiSnapshot"
    index: int

    @property
    def info(self) -> Mapping[str, Any]: return self.snapshot._nodes[self.index]
    @property
    def object(self) -> UiObject: return UiObject(self.snapshot.device, self.info, Selector(mode=self.snapshot.mode))
    @property
    def rect(self) -> dict[str, float]: return self.object.rect
    @property
    def center(self) -> tuple[float, float]: return self.object.center
    def click(self, **kwargs: Any) -> Any: return self.object.click(**kwargs)
    def long_click(self, **kwargs: Any) -> Any: return self.object.long_click(**kwargs)
    def double_click(self, **kwargs: Any) -> Any: return self.object.double_click(**kwargs)
    def drag_to(self, x: float, y: float, **kwargs: Any) -> Any: return self.object.drag_to(x, y, **kwargs)
    def drag_to_relative(self, x_ratio: float, y_ratio: float, **kwargs: Any) -> Any: return self.object.drag_to_relative(x_ratio, y_ratio, **kwargs)
    def set_text(self, text: str, *, interval_ms: int = 120) -> Any: return self.object.set_text(text, interval_ms=interval_ms)
    def get_text(self) -> str: return self.object.get_text()
    def scroll(self, direction: str = "down", distance: float = 1.0) -> Any: return self.object.scroll(direction, distance)
    def scroll_to(self, selector: "Selector | dict[str, Any]", **kwargs: Any) -> Any: return self.object.scroll_to(selector, **kwargs)

class SnapshotCollection:
    """Locally queried nodes from one immutable ``UiSnapshot``."""

    def __init__(self, snapshot: "UiSnapshot", indices: tuple[int, ...]):
        self.snapshot, self.indices = snapshot, indices

    @property
    def exists(self) -> bool: return bool(self.indices)
    @property
    def count(self) -> int: return len(self.indices)
    @property
    def info(self) -> Mapping[str, Any]:
        if not self.indices: raise LookupError("element not found in snapshot")
        return self.snapshot._nodes[self.indices[0]]
    def all(self) -> list[SnapshotNode]: return [SnapshotNode(self.snapshot, index) for index in self.indices]
    def get(self) -> SnapshotNode | None: return self.all()[0] if self.indices else None
    def where_regex(self, field: str, pattern: str) -> "SnapshotCollection":
        if field not in {"name", "label", "value", "title", "type", "enabled", "selected", "focused", "visible", "index", "traits", "childCount"}:
            raise ValueError(f"unsupported selector attribute: {field}")
        matcher = re.compile(pattern).search
        return SnapshotCollection(self.snapshot, tuple(index for index in self.indices if matcher(str(self.snapshot._nodes[index].get(field) or ""))))
    def child(self, selector: Selector | None = None) -> "SnapshotCollection":
        indices = tuple(child for index in self.indices for child in self.snapshot._children[index])
        return self.snapshot._filter(indices, selector)
    def descendant(self, selector: Selector | None = None) -> "SnapshotCollection":
        result: list[int] = []
        def walk(index: int) -> None:
            for child in self.snapshot._children[index]:
                result.append(child); walk(child)
        for index in self.indices: walk(index)
        return self.snapshot._filter(tuple(result), selector)
    def parent(self, selector: Selector | None = None) -> "SnapshotCollection":
        return self.snapshot._filter(tuple(index for item in self.indices if (index := self.snapshot._parents[item]) is not None), selector)
    def sibling(self, selector: Selector | None = None) -> "SnapshotCollection":
        result: list[int] = []
        for index in self.indices:
            parent = self.snapshot._parents[index]
            if parent is not None: result.extend(item for item in self.snapshot._children[parent] if item != index)
        return self.snapshot._filter(tuple(dict.fromkeys(result)), selector)

class UiSnapshot:
    """One full UI tree queried locally without further device requests."""

    def __init__(self, device: "Device", tree: Mapping[str, Any], *, mode: str):
        self.device, self.tree, self.mode = device, dict(tree), mode
        self._nodes: list[dict[str, Any]] = []
        self._parents: list[int | None] = []
        self._children: list[tuple[int, ...]] = []
        self._exact_index: dict[str, dict[Any, tuple[int, ...]]] = {}
        def visit(node: Mapping[str, Any], parent: int | None) -> int:
            index = len(self._nodes); info = {key: value for key, value in node.items() if key != "childs"}
            self._nodes.append(info); self._parents.append(parent); self._children.append(())
            children = tuple(visit(child, index) for child in (node.get("childs") or []) if isinstance(child, Mapping))
            self._children[index] = children
            return index
        for root in self.tree.get("views") or []:
            if isinstance(root, Mapping): visit(root, None)
        mutable_index: dict[str, dict[Any, list[int]]] = {}
        for index, node in enumerate(self._nodes):
            for field, value in node.items():
                if field not in Selector._FIELDS or not isinstance(value, (str, int, float, bool)):
                    continue
                mutable_index.setdefault(field, {}).setdefault(value, []).append(index)
        self._exact_index = {field: {value: tuple(indices) for value, indices in values.items()} for field, values in mutable_index.items()}

    def _filter(self, indices: tuple[int, ...], selector: Selector | None) -> SnapshotCollection:
        return SnapshotCollection(self, tuple(index for index in indices if selector is None or _matches(self._nodes[index], selector)))
    def __call__(self, **attributes: Any) -> SnapshotCollection: return self.select(self.device.selector(**attributes))
    def select(self, selector: Selector) -> SnapshotCollection:
        if selector.point is not None:
            if selector.mode == "point_relative":
                x, y = self.device.client.relative_point(*selector.point)
            else:
                x, y = selector.point
            candidates = tuple(sorted((index for index, node in enumerate(self._nodes) if float(node.get("width") or 0) > 0 and float(node.get("height") or 0) > 0 and float(node.get("x") or 0) <= x < float(node.get("x") or 0) + float(node.get("width") or 0) and float(node.get("y") or 0) <= y < float(node.get("y") or 0) + float(node.get("height") or 0)), key=lambda index: (float(self._nodes[index].get("width") or 0) * float(self._nodes[index].get("height") or 0), index)))
        else:
            exact_lists = [self._exact_index.get(field, {}).get(value, ()) for field, value, match in selector.attributes if match == Selector.EQUAL]
            if exact_lists and any(not values for values in exact_lists):
                candidates = ()
            elif exact_lists:
                allowed = set(min(exact_lists, key=len))
                for values in exact_lists:
                    allowed.intersection_update(values)
                candidates = tuple(index for index in range(len(self._nodes)) if index in allowed)
            else:
                candidates = tuple(range(len(self._nodes)))
        return self._filter(candidates, selector)
    def roots(self) -> SnapshotCollection: return SnapshotCollection(self, tuple(index for index, parent in enumerate(self._parents) if parent is None))
