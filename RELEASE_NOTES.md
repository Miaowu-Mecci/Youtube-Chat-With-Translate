# v0.1.0 — 首个版本

本地运行的 YouTube OBS 双语弹幕工具，提供中文设置页、实时预览和透明 OBS 浏览器源。

- 接入 YouTube 官方直播聊天接口，支持直播链接、视频 ID 或 liveChatId。
- 接入 Azure Translator F0 免费档，原文立即显示，译文完成后在同一条消息上方显示；需要自行配置 API Key 和区域。
- 支持字号、颜色、头像、消息数量及自定义 CSS，复用 blivechat 普通消息渲染组件。
- 内置无需密钥的双语演示模式。
- 提供 Windows x64 单文件 EXE；无需另装 Python 或 Node.js。

## 下载与启动

推荐下载 `YouTubeOBSChat-Windows-x64.zip`，解压后双击 `YouTubeOBSChat.exe`。程序启动后打开设置页；将 `http://127.0.0.1:12450/overlay` 添加到 OBS 浏览器源。关闭程序窗口或按 Ctrl+C 可停止服务。

配置保存在 `%LOCALAPPDATA%\YouTubeOBSChat\config.json`。发布文件不包含 API Key 或用户配置。`SHA256SUMS.txt` 提供 EXE 和 ZIP 的 SHA-256 校验值。

## 验证与首版边界

发布流程在 GitHub Windows runner 上执行 Python 自动测试、前端生产构建和生成 EXE 的实际启动验证，覆盖静态资源、本地配置与 WebSocket 双语演示。详细验证记录见压缩包中的 `VALIDATION.md`。

真实 YouTube / Azure 账号接入和 Windows OBS 人工验收仍未完成。首版仅支持单个公开直播间的普通文本及 Unicode 表情，暂不支持付费消息卡片、会员事件或自定义表情图片。官方 tombstone 接口不提供即时单条删除通知。

翻译需要自行开通 Azure Translator **F0 免费档**，受账号免费额度限制；程序不会自动切换付费服务。运行时需要能够访问 YouTube 与 Azure API。
