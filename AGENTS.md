# AGENTS.md

本文件供各类编码代理（Claude Code、Codex、Cursor、DSH 等）在本仓库工作时参考；`CLAUDE.md` 通过一行 `@AGENTS.md` 导入本文件，内容只在此处维护。

## 项目概况

uitap 是一个 **uiautomator2 式 iOS 设备自动化客户端**（PyPI 包名 `uitap`，命令行 `ut`）。它通过手机端已有的 9096 HTTP 服务与 10102 日志 WebSocket 工作；运行时零依赖（模板匹配所需的 Pillow / OpenCV 为可选 `[vision]` extra）。

## 常用命令

```bat
python -m pip install -e ".[dev,vision]"  # 本地开发安装（含 pyflakes / build 与视觉依赖）
python -m unittest discover -s tests -v   # 全部单元测试；真机集成测试默认禁用
python -m pyflakes src/uitap              # 静态检查（未定义名/未用导入）
python scripts/version_sync.py            # 发布元数据三处版本一致性（测试也会强制）
python scripts/api_docs_sync.py           # 公开 API 文档覆盖 + API 面快照一致性（测试也会强制）
python scripts/smoke.py                   # 真机只读冒烟（需 tests/integration.json 且 enabled: true）
ut help                                   # CLI 速查（python -m uitap 完全等价）
```

真机验收需要 `tests/integration.json`（`enabled: true`）与已开启设备服务的 iPhone。

## 代码结构与约定

- 标准 src 布局，包位于 `src/uitap/`：
  - `core/` 传输层（transport / address / models / png / websocket）与 `client.py` 装配
  - `api/` 按领域拆分的 mixin —— **新增设备能力 = 新模块 + 加入 `client.py` 继承列表**
  - `ui/` uiautomator2 风格对象层；`vision/` 本机图像处理；`inspector/` 浏览器检查器（页面是 `page.html` 资源）
  - `cli/` 命令行 —— **新增命令 = `commands/` 写 handler + `parser.py` 加参数与 `_HELP` 文案 + 注册表登记**
- 中文优先：文档、docstring、**提交信息都用中文**；公开 API 带类型注解。
- 保持现有紧凑风格（如单行 `if ...: return` 是刻意写法），不要大规模重排格式。
- 依赖边界：除可选视觉依赖外只用 Python 标准库，新增依赖前先讨论。
- 真实 `uitap.json` 含密码 / UDID / 内网地址，禁止入库（已在 `.gitignore` 排除）。

## 不可改动（设备端协议契约）

Cookie `airscript=<password>`、`eval_python` 中执行的设备端模块 `ascript.ios.*`、`/api/*` 路由、9096 / 10102 端口——这些是服务端契约，改名或"去品牌化"会导致连接失败。品牌清理只作用于文档与 Python 侧命名。

## 命名规范

包 / 模块 / 命令：`uitap` / `ut`；核心类：`Client`、`UitapError`、`Tunnel`。不要重新引入 `asclient`、`AScriptClient`、`AScriptError`、`AScriptTunnel`、`asc` 命令等旧名。

## 发布流程

1. 更新 `pyproject.toml` 版本、`docs/变更说明.md`，并同步 `docs/API使用参考.md` 首行版本；三处必须一致，`python scripts/version_sync.py` 与 `tests/test_release_metadata.py` 会强制校验
2. `python -m unittest discover -s tests -v` 全绿后提交、推送 `main`
3. `git tag -a vX.Y.Z -m "uitap X.Y.Z" && git push origin vX.Y.Z`（tag 必须与包版本一致）
4. `release.yml` 自动执行：8 矩阵验证（含 tag 与三处版本校验）→ 构建并创建 GitHub Release → Trusted Publishing 发布到 PyPI（无需 token）

## 本机上下文（仅本机开发时参考）

- 本地进度与发布记录：`.ignore/项目进度与发布记录.md`（`.ignore/` 已 gitignore，不入库）
- 本机 pip 走华为云镜像，新发布同步有延迟；立即安装最新版用 `--index-url https://pypi.org/simple`
