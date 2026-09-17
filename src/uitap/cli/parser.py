"""Argument parser and per-command help text for the ``ut`` CLI."""
from __future__ import annotations

import argparse

from ..i18n import current_language


_HELP: dict[str, tuple[str, str]] = {
    "ping": ("ping\n探测设备服务并返回平台（iOS/Android）。", "ping\nProbe the device service and report its platform (iOS/Android)."),
    "help": ("help [命令]\n显示全部命令速查或单个命令的详细说明。", "help [COMMAND]\nShow the command overview or details for one command."),
    "init": ("init [--device 地址] [--force] [--print]\n在当前目录生成完整的 uitap.json，默认 device.address 为 127.0.0.1:9096 并自动填入已安装的 iproxy 路径。已存在时不覆盖，除非加 --force；--print 只输出内容不落盘。", "init [--device ADDRESS] [--force] [--print]\nCreate a complete uitap.json in the current directory, defaulting device.address to 127.0.0.1:9096 and filling in a detected iproxy path. Existing files are never overwritten without --force; --print writes to stdout only."),
    "doctor": ("doctor [--report FILE] [--fix-iproxy PATH] [--yes]\n诊断本地工具、端口、设备服务和日志服务；仅在 --yes 确认后写入安全配置修复。", "doctor [--report FILE] [--fix-iproxy PATH] [--yes]\nDiagnose local tools, ports, device service, and logs; write safe fixes only after --yes confirmation."),
    "status": ("status\n查看设备可用性、屏幕尺寸和当前前台应用。", "status\nShow availability, screen size, and foreground app."),
    "pkgs": ("pkgs\n列出设备端 Python 包。", "pkgs\nList device-side Python packages."),
    "app": ("app\n显示当前前台应用信息。", "app\nShow the foreground app."),
    "app-start": ("app-start BUNDLE_ID\n启动 App 并等待其进入前台。需要 --yes。", "app-start BUNDLE_ID\nLaunch an app and wait for it to reach the foreground. Requires --yes."),
    "app-stop": ("app-stop BUNDLE_ID\n停止 App（等价于上划杀掉）。需要 --yes。", "app-stop BUNDLE_ID\nStop an app (same as swiping it away). Requires --yes."),
    "app-state": ("app-state BUNDLE_ID\n查询 App 运行状态（foreground/background/not_running）。", "app-state BUNDLE_ID\nShow an app's run state (foreground/background/not_running)."),
    "lock": ("lock\n锁定屏幕。需要 --yes。", "lock\nLock the screen. Requires --yes."),
    "unlock": ("unlock\n解锁屏幕（无密码设备）。需要 --yes。", "unlock\nUnlock the screen (passcode-free devices). Requires --yes."),
    "clipboard": ("clipboard [TEXT]\n读取剪贴板；传入 TEXT 则写入。写入需要 --yes。", "clipboard [TEXT]\nRead the clipboard; pass TEXT to write it. Writing requires --yes."),
    "orientation": ("orientation\n显示当前屏幕方向（portrait/landscape）。", "orientation\nShow the current screen orientation (portrait/landscape)."),
    "openurl": ("openurl URL\n通过系统打开 URL 或 App 深链。需要 --yes。", "openurl URL\nOpen a URL or app deep link via the system. Requires --yes."),
    "key": ("key {home,volume_up,volume_down,power,power_plus_home,snapshot}\n发送按键事件。需要 --yes。", "key {home,volume_up,volume_down,power,power_plus_home,snapshot}\nSend a key event. Requires --yes."),
    "device-info": ("device-info\n显示设备信息（型号、名称、locale 等）。", "device-info\nShow device info (model, name, locale, etc.)."),
    "battery": ("battery\n显示电池电量与状态。", "battery\nShow battery level and state."),
    "notification": ("notification\n下拉打开通知中心。需要 --yes。", "notification\nOpen the notification center. Requires --yes."),
    "shot": ("shot [输出.png] [--crop-rel 左 上 右 下]\n保存真机截图，可按屏幕比例裁剪。", "shot [OUTPUT.png] [--crop-rel LEFT TOP RIGHT BOTTOM]\nSave a device screenshot with an optional relative crop."),
    "dump": ("dump [输出.xml] [--mode MODE]\n保存 XML 控件树；mode 可为 smart/full/point。", "dump [OUTPUT.xml] [--mode MODE]\nSave the XML control tree; mode can be smart/full/point."),
    "observe": ("observe [--prefix 前缀]\n同时保存截图与 XML 控件树。", "observe [--prefix PREFIX]\nSave a screenshot and the XML control tree together."),
    "inspect": ("inspect [--host HOST] [--port PORT] [--no-browser]\n启动本机 Inspector，查看截图、控件树、前台应用和坐标。", "inspect [--host HOST] [--port PORT] [--no-browser]\nStart the local Inspector for screenshots, trees, foreground app, and coordinates."),
    "tunnel": ("tunnel [--local-port PORT] [--remote-port PORT] [--local-log-port PORT] [--remote-log-port PORT] [--no-logs] [--udid UDID] [--iproxy PATH]\n通过 USB 同时转发控制端口 9096 和日志端口 10102。", "tunnel [--local-port PORT] [--remote-port PORT] [--local-log-port PORT] [--remote-log-port PORT] [--no-logs] [--udid UDID] [--iproxy PATH]\nForward USB control port 9096 and log port 10102."),
    "eval": ("eval CODE\n执行受信任的设备端 Python。需要 --yes。", "eval CODE\nRun trusted device-side Python. Requires --yes."),
    "cat": ("cat 远程路径 [输出文件]\n打印或保存设备端文件。", "cat REMOTE_PATH [OUTPUT]\nPrint or save a device-side file."),
    "mv": ("mv 远程路径 新名字\n在同目录内重命名设备端文件或目录。需要 --yes。", "mv REMOTE_PATH NEW_NAME\nRename a device-side file or directory within its parent. Requires --yes."),
    "ocr": ("ocr [rect]\n识别屏幕文字（设备端 OCR）。", "ocr [rect]\nRecognize on-screen text with device OCR."),
    "findcolor": ("findcolor COLORS [--diff FLOAT]\n查找颜色组合。", "findcolor COLORS [--diff FLOAT]\nFind a color combination on screen."),
    "compare": ("compare COLORS [--diff FLOAT]\n比对指定颜色组合。", "compare COLORS [--diff FLOAT]\nCompare the given color combination."),
    "ls": ("ls\n列出设备项目。", "ls\nList device projects."),
    "create": ("create PROJECT\n创建项目。需要 --yes。", "create PROJECT\nCreate a project. Requires --yes."),
    "rename": ("rename PROJECT NEW_NAME\n重命名项目。需要 --yes。", "rename PROJECT NEW_NAME\nRename a project. Requires --yes."),
    "remove": ("remove PROJECT\n删除项目（破坏性）。需要 --yes。", "remove PROJECT\nDelete a project (destructive). Requires --yes."),
    "files": ("files PROJECT\n查看项目文件树。", "files PROJECT\nShow a project's file tree."),
    "push": ("push PROJECT SOURCE [REMOTE]\n上传单个文件或整个目录到项目。需要 --yes。", "push PROJECT SOURCE [REMOTE]\nUpload one file or a directory into a project. Requires --yes."),
    "pull": ("pull PROJECT [OUTPUT]\n下载项目文件到本机。", "pull PROJECT [OUTPUT]\nDownload project files to this machine."),
    "run": ("run PROJECT\n运行项目的 __init__.py。需要 --yes。", "run PROJECT\nRun a project's __init__.py. Requires --yes."),
    "stop": ("stop\n停止当前项目。需要 --yes。", "stop\nStop the current project. Requires --yes."),
    "log": ("log [SECONDS] [--reconnects N] [--output FILE] [--contains TEXT]\n读取设备日志回显；不传秒数时默认读取 3 秒。USB 模式需要 tunnel 同时映射 10102。", "log [SECONDS] [--reconnects N] [--output FILE] [--contains TEXT]\nRead device log output for the given seconds (default 3). USB mode requires tunnel to forward 10102."),
    "deploy": ("deploy PROJECT ENTRY [--logs SECONDS] [--screenshot FILE]\n上传入口文件、运行项目、收集日志（默认 5 秒）并保存截图。需要 --yes。", "deploy PROJECT ENTRY [--logs SECONDS] [--screenshot FILE]\nUpload an entry file, run the project, collect logs (default 5 seconds), and save a screenshot. Requires --yes."),
    "tap": ("tap X Y [--duration MS | --duration-ms MS | --duration-s SECONDS]\n在真机坐标点击。旧 --duration 保持毫秒。需要 --yes。", "tap X Y [--duration MS | --duration-ms MS | --duration-s SECONDS]\nTap a device coordinate. Legacy --duration remains milliseconds. Requires --yes."),
    "tap-rel": ("tap-rel X_RATIO Y_RATIO [--duration MS | --duration-ms MS | --duration-s SECONDS]\n按屏幕宽高比例点击，例如 0.5 0.92。需要 --yes。", "tap-rel X_RATIO Y_RATIO [--duration MS | --duration-ms MS | --duration-s SECONDS]\nTap using screen ratios, for example 0.5 0.92. Requires --yes."),
    "swipe": ("swipe X1 Y1 X2 Y2 [--duration MS | --duration-ms MS | --duration-s SECONDS]\n从起点滑动到终点。需要 --yes。", "swipe X1 Y1 X2 Y2 [--duration MS | --duration-ms MS | --duration-s SECONDS]\nSwipe from one point to another. Requires --yes."),
    "swipe-rel": ("swipe-rel X1_RATIO Y1_RATIO X2_RATIO Y2_RATIO [--duration MS | --duration-ms MS | --duration-s SECONDS]\n按屏幕宽高比例滑动，例如 0.5 0.8 0.5 0.2。需要 --yes。", "swipe-rel X1_RATIO Y1_RATIO X2_RATIO Y2_RATIO [--duration MS | --duration-ms MS | --duration-s SECONDS]\nSwipe using screen ratios, for example 0.5 0.8 0.5 0.2. Requires --yes."),
    "input": ("input TEXT [--interval MS]\n向当前焦点输入文本。需要 --yes。", "input TEXT [--interval MS]\nType text into the focused control. Requires --yes."),
    "home": ("home\n执行 Home 操作。需要 --yes。", "home\nPress Home on the device. Requires --yes."),
    "api": ("api METHOD PATH [--params JSON] [--form JSON]\n调用已确认但未封装的原始端点。需要 --yes。", "api METHOD PATH [--params JSON] [--form JSON]\nCall a confirmed but unwrapped API endpoint. Requires --yes."),
}
"""命令速查表：命令名 -> （中文说明，英文说明）。"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ut", description="uitap：uiautomator2 式本地 iOS 设备自动化客户端" if current_language() == "zh" else "uitap: local iOS device automation client with a uiautomator2-style API")
    parser.add_argument("--config", help="JSON config path; defaults to ./uitap.json when present")
    parser.add_argument("--device", help="HOST[:PORT]; overrides device.address in config")
    parser.add_argument("--password", help="overrides device.password in config")
    parser.add_argument("--timeout", type=float, help="seconds; overrides device.timeout in config")
    parser.add_argument("--lang", choices=("auto", "zh-CN", "en"), help="output language; defaults to the OS language or config language")
    parser.add_argument("--yes", action="store_true", help="confirm a state-changing operation")
    commands = parser.add_subparsers(dest="command", required=True)
    help_command = commands.add_parser("help", help="show concise usage help")
    help_command.add_argument("topic", nargs="?")
    initialize = commands.add_parser("init", help="create a complete uitap.json in the current directory")
    initialize.add_argument("--device", dest="init_device", metavar="ADDRESS", help="device address to write; defaults to 127.0.0.1:9096")
    initialize.add_argument("--force", action="store_true", help="overwrite an existing configuration file")
    initialize.add_argument("--print", dest="print_only", action="store_true", help="print the configuration without writing it")
    doctor = commands.add_parser("doctor", help="diagnose local tools and device connectivity")
    doctor.add_argument("--fix-iproxy", metavar="PATH", help="save a validated absolute iproxy path after confirmation")
    doctor.add_argument("--report", metavar="FILE", help="write a password-free JSON diagnostic report")
    for name in ("ping", "status", "ls", "stop", "home", "app", "pkgs"):
        commands.add_parser(name)
    shot = commands.add_parser("shot"); shot.add_argument("output", nargs="?", default="screenshot.png"); shot.add_argument("--crop-rel", nargs=4, type=float, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    dump = commands.add_parser("dump"); dump.add_argument("output", nargs="?", default="dump.xml"); dump.add_argument("--mode", default="smart")
    observe = commands.add_parser("observe"); observe.add_argument("--prefix", default="observe")
    inspect = commands.add_parser("inspect", help="start the local browser UI inspector")
    inspect.add_argument("--host", default="127.0.0.1"); inspect.add_argument("--port", type=int, default=0); inspect.add_argument("--no-browser", action="store_true")
    tunnel = commands.add_parser("tunnel", help="run an iproxy USB tunnel until Ctrl+C")
    tunnel.add_argument("--local-port", type=int); tunnel.add_argument("--remote-port", type=int)
    tunnel.add_argument("--local-log-port", type=int); tunnel.add_argument("--remote-log-port", type=int)
    tunnel.add_argument("--no-logs", action="store_true", help="forward only the HTTP service port")
    tunnel.add_argument("--udid"); tunnel.add_argument("--iproxy")
    ev = commands.add_parser("eval"); ev.add_argument("code")
    cat = commands.add_parser("cat"); cat.add_argument("path"); cat.add_argument("output", nargs="?")
    mv = commands.add_parser("mv"); mv.add_argument("path"); mv.add_argument("new_name")
    for name in ("app-start", "app-stop", "app-state"):
        item = commands.add_parser(name); item.add_argument("bundle_id")
    for name in ("lock", "unlock", "orientation"):
        commands.add_parser(name)
    clip = commands.add_parser("clipboard"); clip.add_argument("text", nargs="?")
    ourl = commands.add_parser("openurl"); ourl.add_argument("url")
    keyp = commands.add_parser("key"); keyp.add_argument("key_name")
    for name in ("device-info", "battery"):
        commands.add_parser(name)
    commands.add_parser("notification")
    ocr = commands.add_parser("ocr"); ocr.add_argument("rect", nargs="?")
    for name in ("findcolor", "compare"):
        item = commands.add_parser(name); item.add_argument("colors"); item.add_argument("--diff", type=float)
    for name in ("create", "run", "files", "remove"):
        item = commands.add_parser(name); item.add_argument("project")
    ren = commands.add_parser("rename"); ren.add_argument("project"); ren.add_argument("new_name")
    push = commands.add_parser("push"); push.add_argument("project"); push.add_argument("source"); push.add_argument("remote", nargs="?")
    pull = commands.add_parser("pull"); pull.add_argument("project"); pull.add_argument("output", nargs="?", default=".")
    deploy = commands.add_parser("deploy"); deploy.add_argument("project"); deploy.add_argument("entry"); deploy.add_argument("--logs", type=float, default=5.0); deploy.add_argument("--screenshot")
    log = commands.add_parser("log"); log.add_argument("seconds", nargs="?", type=float, default=3.0); log.add_argument("--reconnects", type=int, default=0); log.add_argument("--output"); log.add_argument("--contains")
    for name in ("tap", "swipe"):
        item = commands.add_parser(name); item.add_argument("coordinates", nargs="+", type=float)
        durations = item.add_mutually_exclusive_group()
        durations.add_argument("--duration", type=int, default=None, help="milliseconds (legacy default unit)")
        durations.add_argument("--duration-ms", "--duration_ms", dest="duration_ms", type=int, default=None)
        durations.add_argument("--duration-s", "--duration_s", dest="duration_s", type=float, default=None)
        if name == "tap": item.add_argument("--jitter", type=int, default=0)
    for name in ("tap-rel", "swipe-rel"):
        item = commands.add_parser(name); item.add_argument("coordinates", nargs="+", type=float)
        durations = item.add_mutually_exclusive_group()
        durations.add_argument("--duration", type=int, default=None, help="milliseconds (legacy default unit)")
        durations.add_argument("--duration-ms", "--duration_ms", dest="duration_ms", type=int, default=None)
        durations.add_argument("--duration-s", "--duration_s", dest="duration_s", type=float, default=None)
        if name == "tap-rel": item.add_argument("--jitter", type=int, default=0)
    inp = commands.add_parser("input"); inp.add_argument("text"); inp.add_argument("--interval", type=int, default=120)
    raw = commands.add_parser("api", help="call a confirmed but unwrapped API endpoint")
    raw.add_argument("method"); raw.add_argument("path"); raw.add_argument("--params", default="{}"); raw.add_argument("--form", default="{}")
    # 允许 --yes 写在子命令之后，等价于写在全局位置；SUPPRESS 避免覆盖全局值。
    for command in commands.choices.values():
        command.add_argument("--yes", action="store_true", default=argparse.SUPPRESS, help="confirm a state-changing operation (same as the global --yes)")
    return parser