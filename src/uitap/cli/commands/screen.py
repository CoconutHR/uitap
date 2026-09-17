"""Screen, tree and recognition command handlers."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..helpers import _out


def cmd_shot(args: argparse.Namespace, client) -> None:
    print(client.save_screenshot_crop_relative(args.output, *args.crop_rel) if args.crop_rel else client.save_screenshot(args.output))


def cmd_dump(args: argparse.Namespace, client) -> None:
    Path(args.output).write_text(client.ui_xml(mode=args.mode), encoding="utf-8")
    print(Path(args.output).resolve())


def cmd_observe(args: argparse.Namespace, client) -> None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    image, xml = Path(f"{args.prefix}_{stamp}.png"), Path(f"{args.prefix}_{stamp}.xml")
    print(client.save_screenshot(image))
    xml.write_text(client.ui_xml(), encoding="utf-8")
    print(xml.resolve())


def cmd_ocr(args: argparse.Namespace, client) -> None:
    result = client.ocr(region=tuple(int(value) for value in args.rect.split("|")) if args.rect else None)
    _out({"items": [{"text": item.text, "rect": item.rect, "confidence": item.confidence} for item in result.items], "raw": result.raw})


def cmd_findcolor(args: argparse.Namespace, client) -> None:
    _out(client.find_colors(args.colors, diff=args.diff or 0.98))


def cmd_compare(args: argparse.Namespace, client) -> None:
    _out(client.compare_colors(args.colors, diff=args.diff or 0.9))


COMMANDS = {
    "shot": cmd_shot,
    "dump": cmd_dump,
    "observe": cmd_observe,
    "ocr": cmd_ocr,
    "findcolor": cmd_findcolor,
    "compare": cmd_compare,
}