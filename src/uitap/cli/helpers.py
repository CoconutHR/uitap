"""Shared CLI helpers: client/tunnel construction, output and confirmation."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ..config import device_options, load_config, tunnel_options
from ..core import Client
from ..i18n import t
from ..tunnel import Tunnel


def _client(args: argparse.Namespace) -> Client:
    options = device_options(load_config(args.config))
    address = args.device or options.get("address", "127.0.0.1:9096")
    password = args.password if args.password is not None else options.get("password", "")
    timeout = args.timeout if args.timeout is not None else options.get("timeout", 15.0)
    retries = options.get("retries", 1)
    return Client(address, password=password, timeout=timeout, retries=retries)


def _tunnel(args: argparse.Namespace) -> Tunnel:
    options = tunnel_options(load_config(args.config))
    return Tunnel(
        local_port=int(args.local_port if args.local_port is not None else options.get("local_port", 9096)),
        remote_port=int(args.remote_port if args.remote_port is not None else options.get("remote_port", 9096)),
        local_log_port=int(args.local_log_port if args.local_log_port is not None else options.get("local_log_port", 10102)),
        remote_log_port=int(args.remote_log_port if args.remote_log_port is not None else options.get("remote_log_port", 10102)),
        forward_logs=False if args.no_logs else bool(options.get("forward_logs", True)),
        udid=args.udid if args.udid is not None else str(options.get("udid", "")),
        executable=args.iproxy if args.iproxy is not None else str(options.get("iproxy", "iproxy")),
        local_host=str(options.get("local_host", "127.0.0.1")),
        startup_timeout=float(options.get("startup_timeout", 8)),
    )


def _out(value: Any) -> None:
    if isinstance(value, bytes):
        sys.stdout.buffer.write(value)
    elif value is not None:
        print(json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else value)


def _confirm(args: argparse.Namespace, client: Client, action: str) -> None:
    """Require an explicit acknowledgement for a state-changing CLI operation."""
    if not args.yes:
        raise ValueError(t("confirmation_required", device=client.address, action=action))
    print(t("confirmed", device=client.address, action=action), file=sys.stderr)