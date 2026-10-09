# v0.1.1 — Google 免 Key 双语翻译

新增 Google 翻译免 Key 模式，保留 Azure F0；用户无需创建翻译账号或配置翻译密钥即可尝试 Google 双语弹幕。

- 新增「Google 翻译 · 免 Key（实验性）」服务选项，支持中简、中繁、英、日、韩、西、法、德八种目标语言。
- 新增「保存并测试翻译」和「恢复翻译」按钮；无需连接 YouTube 即可测试翻译服务。
- Google 请求单并发、至少间隔 1 秒、超时 5 秒；429 后等待 60 秒，连续三次限流暂停，失败保留原文，不自动切换付费服务。
- 翻译测试与直播共享限流状态；切换服务或语言取消旧任务并重译当前保留消息。
- 兼容 v0.1.0 配置，保留 Azure 密钥与目标语言；语言列表暂不可用时保留原设置。

## 下载与升级

推荐下载 `YouTubeOBSChat-Windows-x64.zip`，解压后运行 `YouTubeOBSChat.exe`，无需安装 Python 或 Node.js。已有用户请先退出旧程序，再替换 EXE；配置仍保存在 `%LOCALAPPDATA%\YouTubeOBSChat\config.json`。

打开 `http://127.0.0.1:12450`，在「双语翻译」选择 Google、设置目标语言并点击「保存并测试翻译」。旧配置默认保留 Azure，需要手动切换 Google。测试成功后开启翻译并连接直播间；YouTube 接入仍需 YouTube API Key。OBS 浏览器源地址不变：`http://127.0.0.1:12450/overlay`。

同时提供独立 EXE 和 `SHA256SUMS.txt`。ZIP 包含中文使用说明、验证记录与第三方许可证，不包含用户配置或 API Key。

## 验证与限制

后端 87 项自动测试、Chromium 8 项浏览器测试通过。发布 CI 在 Windows x64 上重新运行后端测试、前端构建，并实际启动 EXE 验证静态资源、Google 默认配置和语言列表、本地配置及 WebSocket 双语演示。

Google 模式使用非官方网页接口，没有固定免费额度或稳定性保证，可能被限流或因接口变化失效。此前探测曾返回 429，用户随后反馈命令行请求可返回 200；请在自己的网络中使用测试按钮确认。演示和模拟测试不代表真实翻译服务成功。

真实 YouTube / Azure 接入以及 Windows OBS 人工验收仍未完成。Azure F0 需要自行配置凭据，弹幕正文会发送给所选择的 Google 或 Azure 服务。
