"""View-tree queries with coordinate normalization."""
from __future__ import annotations

import copy
import json
import math
from typing import Any, Mapping, Optional

from ..errors import DeviceResponseError


class TreeMixin:
    """控件树查询与坐标归一化。"""


    def ui_xml(self, *, mode: str = "smart", depth: int = 0, x: float = 0, y: float = 0) -> str:
        """获取物理像素坐标已归一化的 XML 控件树。"""
        logical, action = self._coordinate_spaces()
        raw = self.request("GET", "/api/node/dump", params={"mode": mode, "depth": depth, "x": x * logical["width"] / action["width"], "y": y * logical["height"] / action["height"]}, timeout=30).decode("utf-8")
        return self._scale_xml_coordinates(raw, action["width"] / logical["width"], action["height"] / logical["height"])

    def ui_tree(self, *, mode: str = "smart", selector: Optional[Mapping[str, Any]] = None, x: float = 0, y: float = 0, normalize: bool = True) -> dict[str, Any]:
        """获取结构化控件树；``x/y`` 为物理像素点探测坐标。

        ``normalize=False`` 跳过坐标空间探测和坐标归一化：整个查询只需
        一次树请求，适合只判断元素存在性或读取非坐标字段的场景；此时
        返回节点坐标为设备端逻辑点，且不能使用点探测 selector。
        """
        params: dict[str, Any] = {"mode": mode}
        if selector is not None:
            params["selector"] = json.dumps(selector, ensure_ascii=False)
        if not normalize:
            if x or y: raise ValueError("point probing requires normalized queries")
            data = self._ok(self.json("GET", "/api/tool/view/dump", params=params)).get("data", {})
            if not isinstance(data, Mapping):
                raise DeviceResponseError("invalid UI tree returned by device", body=repr(data))
            return dict(data)
        logical, action = self._coordinate_spaces()
        params["x"] = x * logical["width"] / action["width"]
        params["y"] = y * logical["height"] / action["height"]
        data = self._ok(self.json("GET", "/api/tool/view/dump", params=params)).get("data", {})
        if not isinstance(data, Mapping):
            raise DeviceResponseError("invalid UI tree returned by device", body=repr(data))
        config = data.get("config") if isinstance(data.get("config"), Mapping) else {}
        scale = config.get("scale")
        try:
            protocol_scale = float(scale)
        except (TypeError, ValueError):
            protocol_scale = 0.0
        derived_x, derived_y = action["width"] / logical["width"], action["height"] / logical["height"]
        if protocol_scale > 0 and math.isclose(protocol_scale, derived_x, rel_tol=0.01) and math.isclose(protocol_scale, derived_y, rel_tol=0.01):
            x_scale = y_scale = protocol_scale
        else:
            x_scale, y_scale = derived_x, derived_y
        return self._scale_tree_coordinates(dict(data), x_scale, y_scale, action)

    def find_elements(self, selector: Mapping[str, Any], *, mode: str = "smart", x: float = 0, y: float = 0, normalize: bool = True) -> list[dict[str, Any]]:
        """Resolve a device-side selector and return its matching element metadata.

        ``selector`` follows the documented view-tree contract reported by the device, for
        example ``{"sel": [{"key": "label", "params": "OK"}], "find": 99999}``.
        ``normalize=False`` 只发一次树请求，返回的坐标为设备端逻辑点。
        """
        data = self.ui_tree(mode=mode, selector=selector, x=x, y=y, normalize=normalize)
        views = data.get("views") or []
        if not isinstance(views, list):
            raise DeviceResponseError("invalid element list returned by device", body=repr(views))
        return [dict(view) for view in views if isinstance(view, Mapping)]

    def element_text(self, node_id: str) -> str:
        """读取元素文本（等价设备端 WDA ``element/text``）；``node_id`` 取自元素属性的 ``id``。"""
        value = self.eval_python("from ascript.ios.node import Node\nfrom ascript.ios.system import client as sc\n_result=str(Node(sc, %r).text)" % node_id)
        return value if isinstance(value, str) else str(value)

    def element_scroll(self, node_id: str, direction: str = "down", distance: float = 1.0) -> None:
        """在可滚动元素内滚动；``direction``：up/down/left/right，``distance`` 为元素宽高的倍数（0..1+）。"""
        if direction not in ("up", "down", "left", "right"): raise ValueError("direction must be one of up/down/left/right")
        if not isinstance(distance, (int, float)) or not 0 < distance <= 5: raise ValueError("distance must be within (0, 5]")
        with self.locked(): self.eval_python("from ascript.ios.node import Node\nfrom ascript.ios.system import client as sc\nNode(sc, %r).scroll(%r, %r)\n_result=True" % (node_id, direction, float(distance)))

    @staticmethod
    def _scale_tree_coordinates(tree: dict[str, Any], x_scale: float, y_scale: float, action: Mapping[str, float]) -> dict[str, Any]:
        x_keys, y_keys = {"x", "left", "right", "center_x"}, {"y", "top", "bottom", "center_y"}
        width_keys, height_keys = {"width", "widthPixels", "noncompatWidthPixels"}, {"height", "heightPixels", "noncompatHeightPixels"}
        value = copy.deepcopy(tree)
        def visit(item: Any) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if isinstance(child, (int, float)) and not isinstance(child, bool):
                        if key in x_keys or key in width_keys: item[key] = child * x_scale
                        elif key in y_keys or key in height_keys: item[key] = child * y_scale
                    else: visit(child)
            elif isinstance(item, list):
                for child in item: visit(child)
        visit(value)
        display = value.setdefault("config", {}).setdefault("display", {})
        display["widthPixels"], display["heightPixels"] = action["width"], action["height"]
        return value

    @staticmethod
    def _scale_xml_coordinates(xml: str, x_scale: float, y_scale: float) -> str:
        import xml.etree.ElementTree as ET
        if x_scale == 1 and y_scale == 1:
            return xml
        try: root = ET.fromstring(xml)
        except ET.ParseError: return xml
        for element in root.iter():
            for key, scale in (("x", x_scale), ("width", x_scale), ("y", y_scale), ("height", y_scale)):
                if key in element.attrib:
                    try: element.attrib[key] = str(int(round(float(element.attrib[key]) * scale)))
                    except ValueError: pass
        return ET.tostring(root, encoding="unicode")
