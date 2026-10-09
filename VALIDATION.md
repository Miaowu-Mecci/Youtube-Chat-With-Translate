# 首版验收记录

验证日期：2026-10-09。环境：Linux、Python 3.12、Node.js 24、Playwright Chromium 145。

## 已完成

- 前端生产构建：`npm run build` 成功。
- Python 自动测试：**60 项通过**，覆盖直播 URL / ID 解析、官方 protobuf 消息映射、本地 gRPC 服务的请求与响应、续传令牌、多个浏览器共享连接、去重、删除与封禁、错误停止重试、本地演示、内存边界和 API 密钥脱敏。
- 翻译测试：模拟 Azure HTTP 响应，覆盖自动识别参数、重复请求合并、缓存、队列满、超时、限流、鉴权 / 额度错误暂停、任务取消与目标语言切换。
- 浏览器测试：5 项通过，覆盖预览与独立 OBS 页面共享演示、译文原位更新、双语上下顺序、删除后迟到译文、纯文本安全呈现、透明背景、自定义 CSS 覆盖、头像隐藏、保存后同步，以及手机布局和滚动。
- 代表性 CSS：实测 `yt-live-chat-text-message-renderer` 边框、`yt-live-chat-author-chip #author-name` 颜色及 `.translation` 颜色 / 字重。
- 人工截图检查：设置页和演示评论栏布局正常。
- 前端依赖：已升级 Vite / lodash 的有修复版本依赖；剩余 Vue 2 模板解析器的两个关联低风险报告，详情见 `THIRD_PARTY_NOTICES.md`。

## 尚未验证

- **真实 YouTube 直播**：未提供 API Key 和可用于验收的正在直播视频；模拟 gRPC 服务仅验证客户端 wire contract、消息映射与恢复逻辑。
- **真实 Azure F0 翻译**：未提供 Azure Key 与区域；模拟服务不代表真实翻译质量、账号额度或外部网络时延。
- **Windows 安装脚本和 OBS**：当前环境没有 Windows 或 OBS。脚本已按 Windows CMD 语法编写；透明背景和滚动在 Chromium 浏览器中验证，尚未在 Windows OBS 人工确认。
- **完整 CSS 生态兼容性**：实测常用普通消息选择器，不保证所有 blivechat 第三方 CSS 及 B 站专属效果兼容。

## 真实环境验收步骤

1. 在 Windows 安装 Python ≥3.11 和 Node.js ≥22，运行 `install.cmd`、`start.cmd`。
2. 先启动演示，OBS 浏览器源打开 `http://127.0.0.1:12450/overlay`，设置 480 × 720，确认透明背景、持续滚动和上下双语展示。
3. 填入有效 YouTube API Key 和正在直播的公开视频，确认页面显示「已连接」，由观众发送可识别测试文字。
4. 开启 Azure F0 翻译，选择简体中文，分别发送英语、日语和中文；确认先显示原文，再原位增加译文，中文消息不会重复展示。
5. 打开第二个 OBS 浏览器源或独立预览，确认消息一致。关闭再打开页面，应恢复当前缓存消息，不重新建立 YouTube 上游连接。
6. 设置页切换目标语言并保存，确认保留原文、清除旧译文并应用新语言；更换直播源后确认需要手动重新连接。
7. 断开网络后恢复，确认自动重连；对无效 Key、聊天关闭等场景确认可读错误且无无限重试。

删除能力受官方接口限制：`tombstone` 不是即时删除通知，不以即时单条删除同步作为可承诺的验收项。

## EXE 打包增补验证（2026-10-09）

- 已添加 `YouTubeOBSChat.spec`、`build-exe.cmd` 和手动触发的 Windows x64 GitHub Actions 构建流程。
- 当前平台为 Linux，分别实际构建并启动 PyInstaller 的 onedir 和 onefile 版本；二者均通过 `scripts/smoke_bundle.py` 验证：前端 HTML / JS / CSS 资源、默认头像、本地配置文件写入、WebSocket 双语演示及断开连接。
- 单文件 Linux 验证产物约 25 MB；不代表 Windows EXE 的最终大小，Linux 二进制不能当作 Windows EXE 分发。
- 后端回归与新增测试共 **65 项通过**；新增测试验证冻结资源与持久化配置目录分离、数据目录覆盖、服务启动成功后打开浏览器及启动失败时不打开浏览器。
- **尚未生成或验证 Windows EXE**：需要在 Windows 运行 `build-exe.cmd`，或在 GitHub 手动触发已提供的 workflow。流程包含对生成的 EXE 进行实际启动冒烟测试，通过后才上传 artifact。
- Windows 默认使用 `%LOCALAPPDATA%\YouTubeOBSChat\config.json`；构建明确排除真实配置目录。源码配置不自动迁移，更新 EXE 不更改该用户数据目录。


## Google 免 Key 模式增补验证（2026-10-09）

- Google 网页翻译适配器独立编写，复用已有异步 HTTP 客户端；无需翻译账号、Key、浏览器扩展或浏览器登录。服务属于实验性非官方接口。
- 前端生产构建成功；Python 自动测试 **87 项通过**，包含 Azure 回归，以及新增的分段响应、中文代码映射、旧配置迁移、异常 JSON / HTML、超时、三次限流暂停、手动恢复保留冷却、测试与直播共享锁、配置变更取消旧任务。
- Chromium 浏览器测试 **8 项通过**，包含免 Key 配置、保存后测试、限流提示、Azure 凭据保留、服务切换与语言回退、Azure 列表故障时保留旧目标语言，并保留原位译文、删除后迟到译文、透明背景、自定义 CSS、滚动和手机布局验证。
- 后端服务测试使用模拟 Google / Azure 响应；浏览器中的翻译测试结果使用模拟本地接口响应，不代表真实服务成功。
- Google 网页接口的真实网络探测返回 **HTTP 429**，未取得真实译文。请在用户电脑上使用「保存并测试翻译」验证可达性。程序处理限流并保留原文，不自动切换付费服务。
- Windows CI 会对新 EXE 实际启动，额外检查 Google 默认配置与八种目标语言；真实 YouTube / Azure 接入及 Windows OBS 人工验收仍待完成。
- 本次更新仅生成手动 CI artifact，不新建 Release，不修改既有 `v0.1.0` 标签及附件。
