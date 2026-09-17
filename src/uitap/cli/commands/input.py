"""Input gestures and raw debug command handlers."""
from __future__ import annotations

import argparse
import json
import sys

from ...i18n import t
from ..helpers import _confirm, _out


def cmd_tap(args: argparse.Namespace, client) -> None:
    if len(args.coordinates) != 2:
        raise ValueError(t("tap_requires"))
    _confirm(args, client, t("action_tap", coordinates=args.coordinates))
    _out(client.tap(*args.coordinates, duration=args.duration_s, duration_ms=args.duration_ms if args.duration_ms is not None else args.duration, jitter=args.jitter))


def cmd_tap_rel(args: argparse.Namespace, client) -> None:
    if len(args.coordinates) != 2:
        raise ValueError(t("tap_relative_requires"))
    _confirm(args, client, t("action_tap_relative", coordinates=args.coordinates))
    _out(client.tap_relative(*args.coordinates, duration=args.duration_s, duration_ms=args.duration_ms if args.duration_ms is not None else args.duration, jitter=args.jitter))


def cmd_swipe(args: argparse.Namespace, client) -> None:
    if len(args.coordinates) != 4:
        raise ValueError(t("swipe_requires"))
    _confirm(args, client, t("action_swipe", coordinates=args.coordinates))
    _out(client.swipe(*args.coordinates, duration=args.duration_s, duration_ms=args.duration_ms if args.duration_ms is not None else args.duration))


def cmd_swipe_rel(args: argparse.Namespace, client) -> None:
    if len(args.coordinates) != 4:
        raise ValueError(t("swipe_relative_requires"))
    _confirm(args, client, t("action_swipe_relative", coordinates=args.coordinates))
    _out(client.swipe_relative(*args.coordinates, duration=args.duration_s, duration_ms=args.duration_ms if args.duration_ms is not None else args.duration))


def cmd_input(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_input"))
    _out(client.input_text(args.text, interval_ms=args.interval))


def cmd_home(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_home"))
    _out(client.home())


def cmd_eval(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_eval"))
    _out(client.eval_python(args.code))


def cmd_api(args: argparse.Namespace, client) -> None:
    _confirm(args, client, t("action_api", method=args.method.upper(), path=args.path))
    params, form = json.loads(args.params), json.loads(args.form)
    raw = client.request(args.method, args.path, params=params or None, form=form or None)
    try:
        _out(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.stdout.buffer.write(raw)


COMMANDS = {
    "tap": cmd_tap,
    "tap-rel": cmd_tap_rel,
    "swipe": cmd_swipe,
    "swipe-rel": cmd_swipe_rel,
    "input": cmd_input,
    "home": cmd_home,
    "eval": cmd_eval,
    "api": cmd_api,
}