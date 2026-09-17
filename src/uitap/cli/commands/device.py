"""Device, app and system command handlers."""
from __future__ import annotations

import argparse

from ...i18n import t
from ..helpers import _confirm, _out


def cmd_ping(args: argparse.Namespace, client) -> None:
    _out({"platform": client.ping(), "device": str(client.address)})


def cmd_status(args: argparse.Namespace, client) -> None:
    _out(client.status())


def cmd_pkgs(args: argparse.Namespace, client) -> None:
    _out(client.packages())


def cmd_app(args: argparse.Namespace, client) -> None:
    _out(client.current_app())


def cmd_app_start(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_app_start", bundle_id=args.bundle_id))
    _out(client.app_start(args.bundle_id))


def cmd_app_stop(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_app_stop", bundle_id=args.bundle_id))
    client.app_stop(args.bundle_id)


def cmd_app_state(args: argparse.Namespace, client) -> None:
    _out(client.app_state(args.bundle_id))


def cmd_lock(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_lock"))
    client.lock_screen()


def cmd_unlock(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_unlock"))
    client.unlock_screen()


def cmd_clipboard(args: argparse.Namespace, client) -> None:
    if args.text is None:
        _out(client.get_clipboard())
    else:
        _confirm(args, client, t("action_clipboard_set"))
        client.set_clipboard(args.text)


def cmd_orientation(args: argparse.Namespace, client) -> None:
    _out(client.orientation())


def cmd_openurl(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_open_url", url=args.url))
    client.open_url(args.url)


def cmd_key(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_key", key=args.key_name))
    client.press_key(args.key_name)


def cmd_device_info(args: argparse.Namespace, client) -> None:
    _out(client.device_info())


def cmd_battery(args: argparse.Namespace, client) -> None:
    _out(client.battery_info())


def cmd_notification(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_notification"))
    client.open_notification()


COMMANDS = {
    "ping": cmd_ping,
    "status": cmd_status,
    "pkgs": cmd_pkgs,
    "app": cmd_app,
    "app-start": cmd_app_start,
    "app-stop": cmd_app_stop,
    "app-state": cmd_app_state,
    "lock": cmd_lock,
    "unlock": cmd_unlock,
    "clipboard": cmd_clipboard,
    "orientation": cmd_orientation,
    "openurl": cmd_openurl,
    "key": cmd_key,
    "device-info": cmd_device_info,
    "battery": cmd_battery,
    "notification": cmd_notification,
}