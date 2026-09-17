"""Project, file and log command handlers."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from ...i18n import t
from ..helpers import _confirm, _out


def cmd_cat(args: argparse.Namespace, client) -> None:
    data = client.read_file(args.path)
    if args.output:
        Path(args.output).write_bytes(data)
        print(Path(args.output).resolve())
    else:
        sys.stdout.buffer.write(data)


def cmd_mv(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_mv", path=args.path, new_name=args.new_name))
    client.rename_remote(args.path, args.new_name)


def cmd_ls(args: argparse.Namespace, client) -> None:
    _out(client.projects())


def cmd_create(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_create", project=args.project))
    client.create_project(args.project)


def cmd_rename(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_rename", project=args.project, new_name=args.new_name))
    client.rename_project(args.project, args.new_name)


def cmd_remove(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_remove", project=args.project))
    client.remove_project(args.project)


def cmd_files(args: argparse.Namespace, client) -> None:
    _out(client.project_files(args.project))


def cmd_push(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_upload", project=args.project))
    source = Path(args.source)
    count = client.upload_tree(args.project, source) if source.is_dir() else (client.upload_file(args.project, source, args.remote) or 1)
    print(t("uploaded_count", count=count))


def cmd_pull(args: argparse.Namespace, client) -> None:
    for target in client.download_project(args.project, args.output):
        print(target)


def cmd_run(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_run", project=args.project))
    client.run_project(args.project)


def cmd_stop(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_stop"))
    client.stop_project()


def cmd_log(args: argparse.Namespace, client) -> None:
    output = Path(args.output).open("w", encoding="utf-8") if args.output else None
    try:
        for entry in client.logs(duration=args.seconds, reconnects=args.reconnects):
            if args.contains and args.contains not in entry.message:
                continue
            print(f"[{entry.kind}] {entry.timestamp} {entry.message}")
            if output:
                output.write(json.dumps({"message": entry.message, "kind": entry.kind, "timestamp": entry.timestamp}, ensure_ascii=False) + "\n")
    finally:
        if output:
            output.close()


def cmd_deploy(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_deploy", project=args.project))
    logs, image = client.deploy(args.project, args.entry, log_seconds=args.logs)
    for entry in logs:
        print(f"[{entry.kind}] {entry.timestamp} {entry.message}")
    path = Path(args.screenshot or f"deploy_{time.strftime('%Y%m%d_%H%M%S')}.png")
    path.write_bytes(image)
    print(path.resolve())


COMMANDS = {
    "cat": cmd_cat,
    "mv": cmd_mv,
    "ls": cmd_ls,
    "create": cmd_create,
    "rename": cmd_rename,
    "remove": cmd_remove,
    "files": cmd_files,
    "push": cmd_push,
    "pull": cmd_pull,
    "run": cmd_run,
    "stop": cmd_stop,
    "log": cmd_log,
    "deploy": cmd_deploy,
}