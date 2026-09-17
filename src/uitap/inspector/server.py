"""Local browser inspector for the connected iOS device.

It intentionally has no runtime dependency: the browser speaks only to this
loopback server, which speaks to the configured device.
"""
from __future__ import annotations

import base64
import json
import secrets
import threading
import webbrowser
from collections import OrderedDict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from ..core.png import png_size

if TYPE_CHECKING:
    from ..core import Client




_PAGE = (Path(__file__).with_name("page.html")).read_text(encoding="utf-8")


_MAX_SNAPSHOTS = 6
_SNAPSHOT_TTL_SECONDS = 300.0
_MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024
_MAX_SNAPSHOT_CACHE_BYTES = 48 * 1024 * 1024
_MAX_CROP_REQUEST_BYTES = 16 * 1024


def serve(client: "Client", *, host: str = "127.0.0.1", port: int = 0, open_browser: bool = True, output_dir: str | Path | None = None) -> ThreadingHTTPServer:
    """Start the local Inspector; selected screenshot crops save into ``output_dir``.

    Every Inspector snapshot is briefly retained in memory. Crop requests refer
    to this frozen, original PNG by ID, so the saved image and reported physical
    coordinates always describe the same frame.
    """
    crop_directory = Path(output_dir or Path.cwd()).resolve()
    crop_directory.mkdir(parents=True, exist_ok=True)
    snapshots: OrderedDict[str, dict[str, Any]] = OrderedDict()
    snapshots_lock = threading.RLock()
    crop_lock = threading.Lock()

    def now_iso() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def discard_expired_snapshots() -> None:
        cutoff = datetime.now().timestamp() - _SNAPSHOT_TTL_SECONDS
        for snapshot_id, item in list(snapshots.items()):
            if float(item["created_at_epoch"]) < cutoff:
                snapshots.pop(snapshot_id, None)

    def remembered_snapshot_bytes() -> int:
        return sum(len(item["image"]) for item in snapshots.values())

    def remember_snapshot(image: bytes, *, width: int, height: int, metadata: dict[str, Any]) -> str:
        if len(image) > _MAX_SNAPSHOT_BYTES:
            raise ValueError("Inspector screenshot is too large to retain for region cropping")
        with snapshots_lock:
            discard_expired_snapshots()
            snapshot_id = secrets.token_urlsafe(18)
            snapshots[snapshot_id] = {
                "image": image,
                "width": width,
                "height": height,
                "created_at_epoch": datetime.now().timestamp(),
                "metadata": metadata,
            }
            while len(snapshots) > _MAX_SNAPSHOTS or remembered_snapshot_bytes() > _MAX_SNAPSHOT_CACHE_BYTES:
                snapshots.popitem(last=False)
            return snapshot_id

    def frozen_snapshot(snapshot_id: object) -> dict[str, Any] | None:
        if not isinstance(snapshot_id, str) or not snapshot_id:
            return None
        with snapshots_lock:
            discard_expired_snapshots()
            item = snapshots.get(snapshot_id)
            if item is not None:
                snapshots.move_to_end(snapshot_id)
            return item

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None: pass

        def _send(self, status: int, body: bytes, content_type: str) -> bool:
            """Return false when a browser abandons an in-flight response."""
            try:
                self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return False
            return True

        def do_GET(self) -> None:
            parsed = urlparse(self.path); path, query = parsed.path, parse_qs(parsed.query)
            if path == "/":
                self._send(200, _PAGE.encode(), "text/html; charset=utf-8")
                return
            if path == "/api/snapshot":
                try:
                    mode = query.get("mode", ["smart"])[0]
                    with client.locked():
                        image = client.screenshot()
                        tree = client.ui_tree(mode=mode)
                        app, app_error = {}, ""
                        try:
                            app = client.current_app()
                        except Exception as exc:
                            app_error = str(exc)
                    display = tree.get("config", {}).get("display", {}) if isinstance(tree, dict) else {}
                    tree_width = int(display.get("widthPixels") or 0)
                    tree_height = int(display.get("heightPixels") or 0)
                    size = png_size(image)
                    width, height = (int(size[0]), int(size[1])) if size is not None else (tree_width or 1, tree_height or 1)
                    captured_at = now_iso()
                    metadata = {"captured_at": captured_at, "mode": mode, "app": app, "app_error": app_error}
                    snapshot_id = remember_snapshot(image, width=width, height=height, metadata=metadata)
                    data = json.dumps({"snapshot_id": snapshot_id, "captured_at": captured_at, "tree": tree, "app": app, "app_error": app_error, "coordinate_space": {"width": width, "height": height}, "tree_coordinate_space": {"width": tree_width or width, "height": tree_height or height}, "image": base64.b64encode(image).decode("ascii")}, ensure_ascii=False).encode()
                    self._send(200, data, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(502, str(exc).encode(), "text/plain; charset=utf-8")
                return
            if path == "/api/selector":
                try:
                    mode = query.get("mode", ["smart"])[0]
                    selector = json.loads(query.get("selector", [""])[0])
                    if not isinstance(selector, dict):
                        raise ValueError("selector must be a JSON object")
                    elements = client.find_elements(selector, mode=mode)
                    self._send(200, json.dumps({"count": len(elements), "elements": elements}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(502, str(exc).encode(), "text/plain; charset=utf-8")
                return
            self._send(404, b"Not found", "text/plain")

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/crop":
                self._send(404, b"Not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= _MAX_CROP_REQUEST_BYTES:
                    raise ValueError("crop request is empty or too large")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("crop request must be a JSON object")
                source = frozen_snapshot(payload.get("snapshot_id"))
                if source is None:
                    self._send(404, b"frozen Inspector screenshot was not found or has expired", "text/plain; charset=utf-8")
                    return
                rect = payload.get("rect")
                if not isinstance(rect, dict):
                    raise ValueError("crop request must include a rect object")
                values = tuple(rect.get(name) for name in ("left", "top", "right", "bottom"))
                if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
                    raise ValueError("crop rectangle must use integer physical pixels")
                left, top, right, bottom = values
                # Cropping decodes the whole PNG. Serialize this memory-intensive
                # path so concurrent browser tabs cannot multiply peak memory use.
                with crop_lock:
                    image = client.crop_png(source["image"], left, top, right, bottom)
                    width, height = right - left, bottom - top
                    source_width, source_height = int(source["width"]), int(source["height"])
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    stem = f"inspect_crop_{stamp}_x{left}_y{top}_w{width}_h{height}"
                    destination = crop_directory / f"{stem}.png"
                    metadata_destination = crop_directory / f"{stem}.json"
                    metadata = {
                        "source_snapshot_id": str(payload["snapshot_id"]),
                        "source_size": {"width": source_width, "height": source_height},
                        "region": {"left": left, "top": top, "right": right, "bottom": bottom, "width": width, "height": height, "center": {"x": left + width / 2, "y": top + height / 2}},
                        "region_relative": {"left": left / source_width, "top": top / source_height, "right": right / source_width, "bottom": bottom / source_height},
                        "snapshot": source["metadata"],
                        "created_at": now_iso(),
                    }
                    destination.write_bytes(image)
                    metadata_destination.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._send(200, json.dumps({"path": str(destination), "metadata_path": str(metadata_destination), "metadata": metadata}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            except Exception as exc:
                self._send(400, str(exc).encode(), "text/plain; charset=utf-8")

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{server.server_port}/"
    if open_browser:
        webbrowser.open(url)
    return server


def run_forever(client: "Client", *, host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> str:
    server = serve(client, host=host, port=port, open_browser=open_browser)
    url = f"http://{host}:{server.server_port}/"
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return url
