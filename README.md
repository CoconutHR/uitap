# uitap

[![CI](https://github.com/CoconutHR/uitap/actions/workflows/ci.yml/badge.svg)](https://github.com/CoconutHR/uitap/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/uitap.svg)](https://pypi.org/project/uitap/)
[![Python](https://img.shields.io/pypi/pyversions/uitap.svg)](https://pypi.org/project/uitap/)
[![License](https://img.shields.io/pypi/l/uitap.svg)](LICENSE)

**uiautomator2 式 iOS 设备自动化客户端。** `pip install uitap`，零运行时依赖（模板匹配的 Pillow 可选），通过设备端已有的 `9096` HTTP 服务与 `10102` 日志 WebSocket 提供截图、控件树、坐标操作、工程管理、OCR、日志与自动化能力。

完整中文文档：[从零开始使用教程](docs/从零开始使用教程.md)、[API 使用参考](docs/API使用参考.md)、[生产使用指南](docs/生产使用指南.md)、[USB 隧道运维指南](docs/USB隧道运维指南.md)、[发布与验收流程](docs/发布与验收流程.md)、[变更说明](docs/变更说明.md)。

## 前置条件

- 手机上已安装并开启设备服务（AScript 应用中的开发者服务），电脑与手机同一网络；USB 场景见下文。
- Python 3.10+。命令行默认缩写为 `ut`（`uitap` 为全名，二者等价；`python -m uitap` 不依赖 PATH）。

## 最短上手

```bat
pip install uitap
ut init
edit uitap.json
ut status
```

`init` 在当前目录生成一份包含全部配置键的 `uitap.json`，并自动填入已安装的 `iproxy` 路径；它不连接设备，可在手机就绪前先执行。已存在同名文件时拒绝覆盖，确需重建加 `--force`。把 `device.address` 改为手机页面显示的地址（例如 `192.168.1.100:9096`；USB 场景保持默认 `127.0.0.1:9096`），然后 `ut status` 输出的 `"available": true` 即连接成功。接着用五行 Python 完成第一次自动化：

```python
from uitap import connect

device = connect("192.168.1.100:9096")   # 与 uitap.json 中一致
print(device(text="登录").count)         # 先确认恰好命中一个控件
device(text="登录").click()              # 确认无误后再点击
```

## 任务速查

`device` 指 `connect()` 返回的对象，`client` 指低层 `Client`（可从 `device.client` 取得）；`timeout`、`interval` 单位为秒，只有带 `_ms` 后缀的参数才使用毫秒。完整参数见 [API 使用参考](docs/API使用参考.md)。

| 我想… | 写法 |
| --- | --- |
| 截图留证 | `device.screenshot("evidence/step.png")` |
| 点击文本为“登录”的按钮 | `device(text="登录").click()` |
| 按控件名（accessibility name）定位 | `device(name="login_button")` |
| 确认控件存在 / 数量 | `device(text="登录").exists` / `.count` |
| 等控件出现（最多 10 秒） | `device(text="首页").get(timeout=10)` |
| 等控件出现，超时直接报错 | `device.wait(device.selector().text("首页"), timeout=10)` |
| 等控件消失 | `device(text="弹窗").wait_gone(timeout=10)` |
| 找到才点击，找不到不报错 | `device(text="同意").click_exists(timeout=5)` |
| 输入文本（自动先点击控件取得焦点） | `device(resource_id="username").set_text("hello")` |
| 等图片出现并返回坐标 | `client.wait_image("assets/login.png", confidence=0.95)` |
| 等图片出现后点击中心 | `client.tap_image("assets/继续.png", timeout=10)` |
| 等 loading 图片消失再继续 | `client.wait_image_gone("assets/loading.png", timeout=20)` |
| 滚动列表直到目标图片出现 | `client.scroll_until_image("assets/target.png", direction="up")` |
| 滚动列表直到目标控件出现 | `device.scroll_until_element(device.selector().name("提交"), direction="up")` |
| 弹窗出现自动点击（后台监控） | `with device.watch(device.selector().text("允许"), interval=1.5): ...` |
| 按屏幕比例点击（底部中央） | `device.click_rel(0.5, 0.92)` |
| 按屏幕比例滑动 | `client.swipe_relative(0.5, 0.8, 0.5, 0.2)` |
| 识别屏幕文字 | `client.ocr()` |
| 找含“登录”二字的 OCR 文本（含坐标） | `client.find_ocr_text("登录")` |
| 等屏幕出现指定文字 | `client.wait_ocr_text("登录成功", timeout=10)` |
| 读取一个像素的 RGB/HEX | `client.pixel(100, 200).rgb` / `.hex` |
| 按比例读取像素颜色 | `client.pixel_relative(0.5, 0.92)` |
| 断言某点是某颜色（带容差） | `client.assert_color(100, 200, "#FFFFFF", tolerance=3)` |
| 区域内找/数某种颜色 | `client.find_color("#FF0000", region=(0, 1800, 1179, 2556))` / `client.count_color(...)` |
| 长按 / 双击（绝对坐标） | `client.long_press(600, 1200, duration=0.8)` / `client.double_tap(600, 1200)` |
| 按比例长按 / 双击 | `client.long_press_relative(0.5, 0.5, duration=0.8)` |
| 拖拽（绝对 / 比例） | `client.drag(200, 1000, 900, 1000, duration=0.5)` / `client.drag_relative(0.2, 0.5, 0.8, 0.5)` |
| 元素长按 / 双击 / 拖到某点 | `element.long_click()` / `element.double_click()` / `element.drag_to(800, 1200)` |
| 等目标 App 成为前台 | `client.wait_current_app("com.example.app", timeout=10)` |
| 启动 / 停止 App | `client.app_start("com.example.app")` / `client.app_stop("com.example.app")` |
| 查 App 运行状态 | `client.app_state("com.example.app")["state"]` |
| 锁屏 / 解锁 | `client.lock_screen()` / `client.unlock_screen()` |
| 读写设备剪贴板 | `client.set_clipboard("code")` / `client.get_clipboard()` |
| 查当前屏幕方向 | `client.orientation()` |
| 打开 URL / 深链 | `client.open_url("myapp://page")` |
| 发送按键（home/音量/电源） | `client.press_key("home")` |
| 读取元素文本 | `device(label="标题").get_text()` |
| 清空元素文本 | 暂不可用（设备端限制，见 API 参考 `get_text` 行） |
| 多段轨迹滑动 | `client.slide_path([(1800, 1300), (600, 1300)], durations=[150, 150])` |
| 长按拖拽（三段停留） | `client.touch_and_slide(600, 1300, 1800, 1300)` |
| 矩形内随机点击 | `client.click_random(300, 500, 900, 1000)` |
| 拟人抖动点击 | `client.tap(600, 1300, jitter=5)` |
| SIFT 特征匹配 | `client.find_sift(["~/res/img/x.png"], threshold=0.7)` |
| 二维码/条码识别 | `client.scan_code()` |
| YOLO 目标检测 | `client.yolov_load(p, b, yaml)` → `client.yolov_detect(threshold=0.5)` |
| 设备端整帧缓存 | `client.screen_cache(True)`（批量找色/OCR 前开） |
| 系统通知 | `client.notify("跑完了", title="uitap")` |
| 元素内滚动 / 滚动查找 | `element.scroll("down", 0.8)` / `element.scroll_to(device.selector().name("目标"))` |
| 查电池 / 设备信息 | `client.battery_info()` / `client.device_info()` |
| 查到唯一元素才点击（锁内原子） | `device.click_if_unique(device.selector().name("提交"))` |
| 一帧中找多个模板 | `client.find_images({"成功": "success.png", "失败": "failure.png"})` |
| 等待任意页面结果（可各给区域） | `name, match = client.wait_any_image({...}, regions={...}, timeout=20)` |
| 本地快照关系查询 | `device.snapshot()(name="表单").child(device.selector().text("提交"))` |
| 读取控件树 XML 字符串 | `device.dump_hierarchy()` |
| 每步自动留证据的可靠执行 | `run.step("登录", login.click, capture_after=True)` |
| 等待日志出现标记 | `client.wait_for_log("READY", timeout=10)` |
| 在 Python 中管理 USB 隧道（读配置） | `with Tunnel.from_config() as tunnel:` |

## IDE 提示

包内置类型注解、中文 docstring 和 `py.typed` 标记。安装后在 PyCharm 或 VS Code/Pylance 中输入 `client.`、`device.` 或将鼠标悬停在方法上，可看到参数类型、中文单位说明、默认值与返回类型。参数名保持英文以兼容 Python 生态。

```python
from uitap import Client

device = Client("192.168.1.100:9096")
device.save_screenshot("screen.png")
# tap/swipe 使用截图的物理像素坐标；先用 action_size() 确认尺寸。
device.tap(600, 1800)
device.upload_file("demo", "__init__.py")
device.run_project("demo")
```

## 安装与配置

```bat
pip install uitap
ut init
edit uitap.json
ut doctor
```

从 PyPI 安装（推荐）：`pip install uitap`；升级用 `pip install --upgrade uitap`。`pip` 未加入 `PATH` 时改用 `python -m pip install uitap`（系统只有 `python3` 时替换为 `python3 -m pip`；Windows 也可用 `py -m pip`）。

源码仓库安装（开发场景）：`python -m pip install --user --upgrade .`，改用 `python -m uitap` 调用（Windows 可等价写 `py -m uitap`，不依赖 `Scripts` 目录是否加入 `PATH`）。真实 `uitap.json` 已被 Git 忽略，其中的密码、UDID 与内网地址不得提交；`init` 在检测到配置未被忽略时会主动警告。

需要模板匹配、找图等视觉功能时，改用 `pip install "uitap[vision]"` 一并安装 Pillow 与 OpenCV（`opencv-python-headless`）；OpenCV 用于模糊匹配加速，未安装时自动降级到纯 Pillow 实现，功能不受影响。

常用配置项：

- `language`：`auto`、`zh-CN` 或 `en`。`auto` 时中文系统输出中文，其他系统输出英文。
- `device.address`：Wi-Fi 场景填写手机服务地址，例如 `192.168.1.100:9096`；USB 场景填写 `127.0.0.1:9096`。
- `device.password`：设备服务密码；留空表示不发送密码 Cookie。
- `tunnel`：USB `iproxy` 的可执行文件、UDID 和端口配置。

单次命令可使用 `--device`、`--password`、`--timeout` 与 `--lang` 覆盖配置文件。这些都是全局参数，必须写在子命令之前（例如 `ut --device 127.0.0.1:9096 status`）；只有 `--yes` 允许写在子命令之后。优先级统一为“命令行参数 > 配置文件 > 内置默认值”。

## 快速诊断与 USB 连接

`ut help` 查看中文命令速查。`ut doctor` 会只读检查 `iproxy`、隧道端口、控制服务、日志服务和 `status` 兼容性；默认不修改电脑或手机。

电脑与手机不在同一网络时，安装受信任来源的 `iproxy` 后执行：

```bat
ut doctor
ut tunnel
```

`tunnel` 会同时映射 `127.0.0.1:9096 -> 手机:9096` 与 `127.0.0.1:10102 -> 手机:10102`。保持该终端运行，再打开第二个终端执行：

```bat
ut status
ut log 10
ut inspect
```

USB 场景下 `device.address` 必须是 `127.0.0.1:9096`。端口冲突时可用 `tunnel --local-port` / `--local-log-port` 改用其他本地端口，但 `tunnel` 不会自动改写配置，业务命令需同步用 `--device 127.0.0.1:<新端口>` 指向新端口；多设备并行时再用 `--udid` 固定目标手机。完整参数表见 [USB 隧道运维指南](docs/USB隧道运维指南.md)。若已安装 `iproxy.exe` 但未加入 `PATH`，可执行 `ut doctor --fix-iproxy "D:\\tools\\libimobiledevice\\iproxy.exe"`；工具会显示修改计划，并在确认后才写入本地配置。

## 自动化对象 API

```python
from uitap import connect

device = connect("192.168.1.100:9096")
confirm = device(text="Confirm", class_name="XCUIElementTypeButton")
if confirm.exists:
    print(confirm.info)
    confirm.click()

# 也支持稳定的显式选择器和坐标点探测。
device.selector().name("login_button")
device.selector().at(200, 600)              # 绝对物理像素
device.selector().at_relative(0.5, 0.5)     # 屏幕比例坐标
```

坐标规则统一如下：**无后缀方法一律使用截图物理像素绝对坐标**，例如 `tap(x, y)`、`swipe(...)`、`Selector.at(x, y)`、`pixel(x, y)`、`screenshot_crop(left, top, right, bottom)`；**`*_relative` 一律使用 `0..1` 比例坐标**。所有矩形均为 `left, top, right, bottom`，左上包含、右下排除。控件树、截图、OCR 与 `tap`/`swipe` 使用物理像素，坐标始终跟随当前屏幕方向（竖屏如 `1179 x 2556`，横屏自动变为 `2556 x 1179`，已在真机横屏验证）；只有 `status()["logical_screen"]` 保留移动端原始逻辑点，供协议诊断使用。

```python
# 保存屏幕下半部分（比例裁剪）。
device.save_screenshot_crop_relative("artifacts/bottom.png", 0, 0.5, 1, 1)
```

本机模板可等待图标出现/消失，也可指定置信度。容差匹配（`confidence < 1.0`）会优先读取设备已存在的 HID JPEG 帧；HID 不可用时自动回退 PNG，无需为 USB 场景引入另一套 API。精确匹配（`confidence=1.0`）、截图留证与取色仍使用无损 PNG。

```python
match = device.wait_image("assets/login-icon.png", confidence=0.95, timeout=15, log=True)
device.tap(*match.center)
device.wait_image_gone("assets/loading.png", confidence=0.90, timeout=20, log=True)

# 自定义比例手势与每次滑动时长。
match = device.scroll_until_image("assets/target.png", swipe_relative=(0.7, 0.75, 0.35, 0.25), duration=0.65)
```

生产工作流建议使用 `Run`。它会将同一设备的动作串行化，并为每一步写入独立证据目录：

```python
from uitap import Run, connect

device = connect("192.168.1.100:9096")
with Run(device) as run:
    login = run.assert_unique(device.selector().name("login_button"))
    run.step("open_login", login.click, capture_after=True)
```

完整可运行的带注释示例见 [examples/完整流程示例.py](examples/完整流程示例.py) 与[从零开始使用教程](docs/从零开始使用教程.md)第 10 节。

## Inspector 与真机验收

`ut inspect` 会启动仅监听本机回环地址的浏览器 Inspector。界面展示当前截图、控件树、前台 App、控件属性、可复制选择器和真机坐标；“框选区域”会冻结一张原始 PNG 并暂停实时刷新，确认后保存无损裁剪图及同名 JSON 元数据。

| 我要改的 | 参数 | 默认值 |
| --- | --- | --- |
| 连接哪台手机 | 全局 `--device HOST[:PORT]`，或配置文件 `device.address` | 配置文件 / `127.0.0.1:9096` |
| Inspector 自己监听在哪 | `inspect --host HOST` | `127.0.0.1` |
| Inspector 监听端口 | `inspect --port PORT`（`0` 表示随机端口） | `0` |
| 不自动打开浏览器 | `inspect --no-browser` | 自动打开 |

**不要使用 `--host 0.0.0.0`。** Inspector 的 `/api/*` 接口没有任何鉴权，能读取设备截图与控件树；绑定到非回环地址等于把手机屏幕内容暴露给同网段所有主机。

部分 App 或页面不暴露无障碍控件树，此时 Inspector 会正确显示没有语义节点；仍可单独使用截图、OCR、图色与坐标操作。

真机冒烟测试使用独立配置文件，避免环境变量和误操作。跨平台脚本 `scripts/smoke.py` 会先确认 `enabled: true`，再运行只读集成套件（Windows 也可用 `scripts\windows-smoke.ps1` 包装脚本）：

```bat
copy tests\integration.example.json tests\integration.json
edit tests\integration.json
python scripts/smoke.py --install
```

等价的直接调用是 `python -m unittest discover -s tests -p test_integration.py -v`。将 `tests\integration.json` 的 `enabled` 显式设为 `true` 后才会连接真机。该套件默认只读取状态、截图、控件树、日志端口和可选选择器，不执行点击、输入、上传、删除或部署。

## 运行方式与边界

CLI 有三种等价调用：`ut`（默认缩写）、`uitap`（全名）、`python -m uitap`（不依赖 PATH，Windows 推荐）。除模板匹配所需的 Pillow（以及可选的 OpenCV 加速）外，该库只依赖 Python 标准库。生产发布前应在目标 App、目标 iOS 版本和目标设备上执行集成验收；已知的设备端兼容降级见[生产使用指南](docs/生产使用指南.md)。