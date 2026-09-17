"""Projects (modules) and file management."""
from __future__ import annotations

import secrets
import threading
import time
import urllib.parse
from pathlib import Path, PurePosixPath
from typing import Any, Optional

from ..core.models import LogEntry
from ..errors import DeviceOperationError

def _validate_name(name: str) -> str:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("project name must be one non-empty directory name")
    return name


def _validate_relative(path: str) -> str:
    path = str(PurePosixPath(path.replace("\\", "/")))
    if not path or path == "." or path.startswith("/") or ".." in PurePosixPath(path).parts:
        raise ValueError("remote path must be relative and cannot contain '..'")
    return path


def _project_file_paths(tree: Any) -> list[str]:
    """Normalize Android-style and iOS-4001 project file trees."""
    paths: list[str] = []

    def walk(node: Any, parent: str | None) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, parent)
            return
        if not isinstance(node, dict):
            return
        name = str(node.get("name") or node.get("fileName") or "")
        children = node.get("childs") or node.get("children") or node.get("files") or []
        if children:
            # The root returned by iOS has the project name. It is not part
            # of the remote path below ~/modules/<project>/.
            child_parent = "" if parent is None else "/".join(part for part in (parent, name) if part)
            walk(children, child_parent)
        elif name and (node.get("isFile") is True or (not node.get("dir") and not node.get("isDir") and parent is not None)):
            paths.append(_validate_relative("/".join(part for part in (parent or "", name) if part)))

    walk(tree, None)
    return sorted(set(paths))



class FilesMixin:
    """工程（模块）与文件管理。"""


    def projects(self) -> list[dict[str, Any]]:
        return self._ok(self.json("POST", "/api/module/list")).get("data", [])

    def create_project(self, name: str) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/module/create", params={"name": _validate_name(name)}))

    def rename_project(self, name: str, new_name: str) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/module/rname", params={"name": _validate_name(name), "rename": _validate_name(new_name)}))

    def remove_project(self, name: str) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/module/remove", params={"name": _validate_name(name)}))

    def project_files(self, name: str) -> Any:
        return self._ok(self.json("GET", "/api/module/files", params={"name": _validate_name(name)})).get("data", [])

    def download_project(self, project: str, destination: str | Path) -> list[Path]:
        """Download all project files, preserving their relative directories."""
        project = _validate_name(project)
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        result: list[Path] = []
        for relative in _project_file_paths(self.project_files(project)):
            target = destination.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read_file(f"~/modules/{project}/{relative}"))
            result.append(target)
        return result

    def run_project(self, name: str) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/module/run", params={"name": _validate_name(name)}))

    def stop_project(self) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/module/stop"))

    def read_file(self, remote_path: str) -> bytes:
        return self.request("GET", "/api/file/get", params={"path": remote_path}, timeout=30)

    def save_text(self, remote_path: str, content: str) -> None:
        with self.locked(): self._ok(self.json("POST", "/api/file/save", form={"path": remote_path, "content": content}))

    def create_remote(self, parent: str, name: str, *, directory: bool = False) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/file/create", params={"path": parent, "name": name, "type": "floder" if directory else "file"}))

    def remove_remote(self, path: str) -> None:
        with self.locked(): self._ok(self.json("GET", "/api/file/remove", params={"path": path}))

    def rename_remote(self, path: str, new_name: str) -> None:
        """重命名设备端文件或目录（同目录内）。

        ``path`` 为完整远程路径（支持 ``~/`` 前缀）；``new_name`` 只是新名字，
        不能包含路径分隔符，设备端会在原目录下完成改名。
        """
        if not new_name or "/" in new_name or "\\" in new_name: raise ValueError("new_name must be a bare file name without path separators")
        with self.locked(): self._ok(self.json("GET", "/api/file/rename", params={"path": path, "name": new_name}))

    def upload_file(self, project: str, local_path: str | Path, remote_path: Optional[str] = None) -> None:
        project, local_path = _validate_name(project), Path(local_path)
        if not local_path.is_file():
            raise FileNotFoundError(local_path)
        relative = _validate_relative(remote_path or local_path.name)
        with self.locked():
            try:
                self.create_project(project)
            except DeviceOperationError:
                pass
            boundary = "----uitap" + secrets.token_hex(16)
            filename = urllib.parse.quote(local_path.name, safe="")
            prefix = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
            body = prefix + local_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            result = self.json("POST", "/api/file/upload", params={"path": f"~/modules/{project}/{relative}", "overwrite": "true"}, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=60)
            self._ok(result)

    def upload_tree(self, project: str, directory: str | Path) -> int:
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(directory)
        files = sorted(item for item in directory.rglob("*") if item.is_file())
        for item in files:
            self.upload_file(project, item, item.relative_to(directory).as_posix())
        return len(files)

    def deploy(self, project: str, entry_file: str | Path, *, log_seconds: float = 5.0) -> tuple[list[LogEntry], bytes]:
        with self.locked():
            self.upload_file(project, entry_file, "__init__.py")
            logs: list[LogEntry] = []
            stop = threading.Event()
            thread = threading.Thread(target=lambda: logs.extend(self.logs(duration=log_seconds, stop_event=stop)), daemon=True)
            thread.start(); time.sleep(0.2); self.run_project(project); thread.join(log_seconds + 3); stop.set()
            return logs, self.screenshot()
