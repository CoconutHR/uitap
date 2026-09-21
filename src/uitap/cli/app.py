"""CLI entry point: argument dispatch, help output and special command flows."""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any

from ..config import language_option, load_config
from ..doctor import diagnose, planned_iproxy_fix, save_report, set_iproxy_path
from ..errors import TunnelError, UitapError
from ..i18n import current_language, set_language, t
from .commands import COMMANDS
from .helpers import _client, _tunnel
from .parser import _HELP, _parser


def _stop_tunnel_on_sigterm(signum: int, frame: object) -> None:
    """Route process termination through the tunnel command's cleanup block."""
    raise KeyboardInterrupt


def _print_help(topic: str | None = None) -> None:
    language = current_language()
    if topic:
        item = _HELP.get(topic)
        if item is None:
            print(t("help_unknown", command=topic), file=sys.stderr)
            return
        print(item[0 if language == "zh" else 1])
        return
    if language == "zh":
        print("""uitap 使用帮助

用法：python -m uitap [--config 文件] [--device 地址] [--lang zh-CN|en] <命令>

配置文件：默认读取当前目录的 uitap.json。可设置顶层 language 为 auto、zh-CN 或 en。

常用命令：
  init       生成 uitap.json 配置文件（不连接设备）
  doctor     诊断本机、USB 隧道、设备服务和日志服务
  status     查看设备状态与当前前台应用
  tunnel     通过 USB 转发 9096 控制端口及 10102 日志端口
  inspect    打开可视化控件检查器
  shot       保存真机截图
  dump       保存 XML 控件树
  deploy     上传并运行项目，收集日志和截图（需要 --yes）
  log        查看日志回显
  tap/tap-rel/swipe/input/home  执行设备操作（需要 --yes）

查看某个命令的详细参数：python -m uitap help <命令>""")
    else:
        print("""uitap usage

Usage: python -m uitap [--config FILE] [--device ADDRESS] [--lang zh-CN|en] <command>

Configuration: reads uitap.json from the current directory by default. The top-level language can be auto, zh-CN, or en.

Common commands:
  init       Create an uitap.json configuration file (no device needed)
  doctor     Diagnose local tools, USB tunnel, device service, and log service
  status     Show device status and foreground app
  tunnel     Forward USB control port 9096 and log port 10102
  inspect    Open the visual control inspector
  shot       Save a device screenshot
  dump       Save the XML control tree
  deploy     Upload/run a project and collect logs/screenshots (requires --yes)
  log        Read log output
  tap/tap-rel/swipe/input/home  Perform device actions (requires --yes)

View command details: python -m uitap help <command>""")


def _print_doctor(checks: list[Any]) -> None:
    labels = {"ok": t("doctor_ok"), "warning": t("doctor_warning"), "error": t("doctor_error")}
    print(t("doctor_title"))
    for check in checks:
        print(f"[{labels[check.status]}] {check.message}")


def _confirm_repair(args: argparse.Namespace) -> bool:
    if args.yes:
        return True
    if not sys.stdin.isatty():
        print(t("doctor_fix_declined"), file=sys.stderr)
        return False
    try:
        return input(t("doctor_fix_confirm")).strip().lower() in {"y", "yes"}
    except (EOFError, OSError):
        return False


def _run_init(args: argparse.Namespace) -> int:
    """Create a full configuration file; the only command that writes one."""
    from ..initializer import LOOPBACK_ADDRESS, build_config, detect_iproxy, is_git_ignored, render_config, write_config

    address = args.init_device or LOOPBACK_ADDRESS
    iproxy = detect_iproxy()
    config = build_config(address=address, iproxy=iproxy)
    if args.print_only:
        sys.stdout.write(render_config(config))
        return 0
    try:
        target = write_config(config, args.config, force=args.force)
    except FileExistsError as exc:
        print(t("init_exists", path=Path(str(exc)).resolve()), file=sys.stderr)
        return 1
    print(t("init_written", path=target))
    print(t("init_iproxy_found", path=iproxy) if iproxy else t("init_iproxy_missing"))
    if address == LOOPBACK_ADDRESS:
        print(t("init_loopback_hint", address=address))
    if is_git_ignored(target) is False:
        print(t("init_gitignore_warning", path=target), file=sys.stderr)
    print(t("init_next_steps"))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        set_language(args.lang or language_option(config))
        if args.command == "help":
            _print_help(args.topic)
            return 0 if not args.topic or args.topic in _HELP else 1
        if args.command == "init":
            return _run_init(args)
        client = _client(args)
        cmd = args.command
        if cmd == "doctor":
            checks = diagnose(client, config)
            _print_doctor(checks)
            if args.report:
                print(t("doctor_report_saved", path=save_report(checks, args.report, client=client)))
            if args.fix_iproxy:
                if not Path(args.fix_iproxy).expanduser().is_file():
                    raise ValueError(t("doctor_fix_invalid", path=Path(args.fix_iproxy).expanduser()))
                print(planned_iproxy_fix(args.config, args.fix_iproxy))
                if _confirm_repair(args):
                    print(t("doctor_fix_done", path=set_iproxy_path(config, args.fix_iproxy, path=args.config)))
            return 1 if any(check.status == "error" for check in checks) else 0
        if cmd == "inspect":
            from ..inspector import serve
            server = serve(client, host=args.host, port=args.port, open_browser=not args.no_browser)
            print(t("inspector_running", url=f"http://{args.host}:{server.server_port}/"))
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        if cmd == "tunnel":
            tunnel = _tunnel(args).start()
            routes = f"service={tunnel.address} -> device:{tunnel.remote_port}"
            if tunnel.log_address:
                routes += f"; logs={tunnel.log_address} -> device:{tunnel.remote_log_port}"
            print(t("tunnel_running", routes=routes, address=tunnel.address))
            previous_sigterm = signal.signal(signal.SIGTERM, _stop_tunnel_on_sigterm)
            try:
                while tunnel.is_running:
                    time.sleep(0.25)
                raise TunnelError(t("tunnel_exited", detail=tunnel.exit_summary()))
            except KeyboardInterrupt:
                pass
            finally:
                signal.signal(signal.SIGTERM, previous_sigterm)
                tunnel.stop()
            return 0
        handler = COMMANDS.get(cmd)
        if handler is None:
            raise ValueError(f"unhandled command: {cmd}")
        handler(args, client)
    except (UitapError, ValueError, OSError) as exc:
        print(f"{t('error_prefix')}: {exc}", file=sys.stderr)
        return 1
    return 0