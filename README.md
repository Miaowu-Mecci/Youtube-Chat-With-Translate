# YouTube OBS 双语弹幕

本地运行的 YouTube 直播评论栏：输入直播链接，将透明网页加入 OBS 浏览器源；弹幕先显示原文，翻译完成后在同一条消息上方补充译文。

前端复用 [blivechat](https://github.com/xfgryujk/blivechat) 的渲染组件、基础 DOM 和滚动效果，支持普通弹幕的既有 CSS 选择器。外部翻译采用 Azure Translator **F0 免费档**。

## Windows 快速开始

1. 安装 **Python 3.11 或更新版本**，以及 **Node.js 22 LTS 或更新版本**。安装 Python 时勾选添加到 PATH；安装后重新打开终端。
2. 下载或复制完整项目，双击 `install.cmd`。它创建 `.venv`、安装固定的 Python 运行依赖、执行 `npm ci`，并构建前端。首次安装需要联网。
3. 双击 `start.cmd`，保持终端窗口打开；浏览器访问 **http://127.0.0.1:12450**。
4. 无需凭据即可点击「体验演示」，确认原文、译文、样式和预览正常。
5. 填写 YouTube 参数；需要机器翻译时，再填写 Azure 参数并开启翻译。
6. 点击「连接直播间」。在 OBS 添加「浏览器」源，粘贴 **http://127.0.0.1:12450/overlay**，建议尺寸 **480 × 720**。

源码部署使用 `start.cmd`；也可以按下方流程生成独立 EXE。前端只在安装或代码更新后需要重新构建。

## Windows 单文件 EXE

已提供 PyInstaller 打包配置和 Windows 一键构建脚本，目标为 **Windows x64**。构建者需要 Python、Node.js 和联网环境；拿到成品的使用者无需安装 Python、Node.js 或项目依赖。

**本机打包**：在 Windows 上双击 `build-exe.cmd`。脚本安装依赖、构建前端、生成单文件并进行实际启动冒烟测试；成功后产物为 `dist/YouTubeOBSChat.exe`。

**下载已发布版本**：在仓库的 Releases 页面下载 `YouTubeOBSChat-Windows-x64.zip`，解压后运行其中的 `YouTubeOBSChat.exe`；压缩包包含使用文档和第三方许可证。也提供单独的 EXE 和 `SHA256SUMS.txt` 校验文件。

**GitHub 构建**：在 Actions 中选择 **Build Windows EXE → Run workflow**，构建通过后下载 `YouTubeOBSChat-Windows-x64` artifact。推送 `v*` 版本标签时，CI 在 Windows x64 上运行自动测试、生成 EXE 并实际启动验证，全部通过后自动创建 Release 并上传 EXE、发行压缩包及 SHA-256 校验文件；手动构建仅生成 artifact。

EXE 的使用方式：

1. 双击 `YouTubeOBSChat.exe`；服务启动成功后自动打开设置页。
2. 保持控制台窗口打开，关闭窗口或按 Ctrl+C 会停止服务。浏览器标签页关闭不会停止服务。
3. OBS 地址仍为 `http://127.0.0.1:12450/overlay`。应用不会自动连接直播间，需要在设置页点击连接。
4. 配置默认保存到 **`%LOCALAPPDATA%\YouTubeOBSChat\config.json`**，不会放进单文件解压的临时目录；替换 EXE 后配置仍然保留。源码版原有 `data/config.json` 不自动迁移；需要时将它复制到新目录，切勿将真实配置随 EXE 分发。

可在命令行运行 `YouTubeOBSChat.exe --port 12460` 或 `YouTubeOBSChat.exe --no-browser`。也支持 `YTCHAT_DATA_DIR` 指定数据目录。端口被占用时程序提示失败，保留控制台供查看，不自动改端口以免 OBS 地址失效。

仅将前端构建结果、默认头像、许可证和程序依赖加入 EXE，**不包含真实 API Key 或用户数据目录**。分发时请附上 `LICENSE`、`THIRD_PARTY_NOTICES.md` 与 `licenses/`。

Windows EXE 必须由 Windows 本机构建或 Actions Windows runner 生成；当前 Linux 环境不能直接生成 Windows EXE。[PyInstaller 平台说明](https://pyinstaller.org/en/stable/operating-mode.html)

## YouTube API 配置

1. 在 [Google Cloud Console](https://console.cloud.google.com/) 创建项目。
2. 启用 **YouTube Data API v3**，创建 API Key。建议将 Key 的 API 使用范围限制为 YouTube Data API；此工具在后端请求，不适用浏览器 HTTP Referer 限制。
3. 设置页输入正在直播的 `watch?v=…`、`youtu.be/…`、`youtube.com/live/…` 链接或 11 位视频 ID。也可以选择 `liveChatId` 类型并直接输入聊天 ID。
4. 本工具通过 `videos.list(part=liveStreamingDetails)` 解析 `activeLiveChatId`，再使用官方 `liveChatMessages.streamList` 接收推送。[官方指南](https://developers.google.com/youtube/v3/live/streaming-live-chat)

自动识别时，11 位 ID 视为视频 ID；若聊天 ID 恰好也是 11 位，请显式选择 `liveChatId`。频道主页和 `@频道/live` 自动寻找直播暂不支持。默认使用 API Key 访问公开直播，不提供 OAuth 私有直播登录或发送弹幕功能。

YouTube API 有项目配额；`streamList` 每次调用的官方配额成本为 5 单位。程序共享上游连接、带续传令牌重连，不按浏览器数量重复拉取。不承诺免费配额能覆盖任意直播时长；配额耗尽、凭据无效或聊天关闭时停止自动重试并提示。[官方接口](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/streamList)

## Azure 免费翻译

1. 注册 Azure，在 [Azure Portal](https://portal.azure.com/) 创建 **Translator** 资源。
2. **定价层必须选择 F0 免费档**，不要选择 S1、付费多服务资源或自动升级套餐。
3. 在资源的「Keys and Endpoint」页面复制 Key 和区域，填入本工具。例如区域为 `eastasia`，使用资源实际显示值。
4. 开启翻译，选择主播语言，点击「保存设置」；若尚未连接，再点击「连接直播间」。

截至 2026-10-09，Azure F0 标准翻译每月提供 **200 万字符免费额度**；实际限制以账号和官方页面为准。本工具只调用标准文本翻译接口，不自动升级资源或切换到付费服务。[官方价格](https://azure.microsoft.com/en-us/pricing/details/translator/)

程序省略 `from` 参数，让 Azure 自动识别源语言；目标语言列表从官方 `/languages` 接口读取。如果列表暂不可用，显示内置常用语言并提示。配置源语言相同或译文与原文相同的消息只显示一份。短句、混合语言、俚语和人名的识别与翻译可能不准确。[翻译接口](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/v3/translate)

默认 4 个翻译 worker、200 个排队任务、每次调用最多等待 5 秒。重复文本共享请求，完成结果保存在最多 1000 条的内存缓存中；纯表情、数字、链接或空文本跳过翻译。限流退避 2 秒，当前消息保留原文；超时或服务失败也保留原文。鉴权或额度错误暂停翻译，修改翻译配置或断开后重新连接可恢复。

开启翻译后，消息文本会发送给 Azure；作者名称、头像和 API Key 不包含在翻译正文中。Azure 资源是否为 F0 无法从翻译接口可靠判断，必须由用户创建资源时确认。本工具不显示账号实际剩余额度。

## 演示与样式

演示使用固定的日语、英语、中文、西班牙语和韩语样例；译文在原文到达约 0.7 秒后加入。不访问 YouTube 或翻译 API，不需要 Key。固定译文仅适用于简体中文目标；选择其他语言的演示只展示原文。真实翻译使用 Azure API。

样式面板支持字号、原文颜色、译文颜色、头像显示、保留消息数量和任意自定义 CSS。修改样式即时影响预览；保存后同步所有 OBS 页面。「复制 CSS」可以将完整样式粘贴到 OBS 自定义 CSS。

保留的常用选择器包括：

```css
yt-live-chat-renderer { background: transparent; }
yt-live-chat-text-message-renderer { padding: 10px 16px; }
yt-live-chat-author-chip #author-name { font-weight: bold; }
yt-live-chat-text-message-renderer #message { color: white; }
.translation { color: #8de1cb; font-weight: 600; }
```

`#message` 仍然仅含原文，`.translation` 为新增的译文元素。同一条消息用 `data-message-id` 标识。默认样式放在 CSS layer 中，用户提供的普通 CSS 可以覆盖它。OBS 浏览器源自身的自定义 CSS 优先于默认 layer；来自 OBS 和项目配置的自定义 CSS 若相互冲突，仍遵循浏览器常规层叠规则。

首版实测普通消息、头像和用户名样式；B 站舰队等级、礼物卡片及其他平台专有选择器不在兼容承诺内。要求使用支持 CSS `@layer` 和 `:has()` 的较新版 OBS 浏览器源。

## 本地配置与运行

源码版配置保存于 `data/config.json`，EXE 版保存于 `%LOCALAPPDATA%\YouTubeOBSChat\config.json`，首次保存时创建。`config.example.json` 为格式示例，不自动加载；通过设置页保存最方便。API Key 在本地文件中以明文保存，勿上传、截图或分享该文件；`data/` 已加入 `.gitignore`。配置查询仅返回 `youtube_key_set` / `azure_key_set` 标记，不返回 Key。

默认只监听回环地址；跨站浏览器请求及外部 Host 被拒绝，没有启用宽松 CORS。OBS 地址不包含任何 Key。需要调整端口时：

```bat
start.cmd --port 12460
```

非 Windows 环境或手动安装：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python main.py
```

Windows 手动运行时，将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。Python 启动命令不要求项目以 editable package 安装。

可设置 `YTCHAT_DATA_DIR` 指定独立数据目录。不会在服务启动时自动连接；打开设置页后手动连接，避免后台意外消耗额度。

YouTube 和 Azure API 必须能从本机访问。HTTP 请求遵循 httpx 的标准代理环境变量；gRPC 使用其自身的 HTTP CONNECT 代理配置。代理需要支持 TLS 和 HTTP/2。访问失败时查看设置页的状态信息，不要通过分享配置文件排查密钥问题。

## API 与数据流

| 接口 | 用途 |
| --- | --- |
| `GET /api/config` | 读取公开配置及密钥存在标记 |
| `PUT /api/config` | 保存部分配置；省略 Key 表示保留，Key 传空字符串表示清除；`style` 对象整体替换 |
| `POST /api/connect` | 连接当前直播间；同模式运行时重复调用不创建额外连接 |
| `POST /api/disconnect` | 停止上游与翻译，保留已显示消息 |
| `POST /api/demo` | 启动固定样例演示 |
| `GET /api/status` | 读取连接、翻译状态和浏览器连接数 |
| `GET /api/languages` | 返回官方支持语言列表或内置回退列表 |
| `WS /ws` | 推送当前快照与后续事件 |

WebSocket 事件含会话 `session`，类型为 `snapshot`、`message`、`translation`、`delete`、`status`。新增消息字段为 `id`、`author_id`、`author`、`avatar`、`role`、`time`、`original`、`translation`、`source_language` 和 `translation_status`。译文事件按 ID 原地更新，不重排或重新插入消息。

换直播源或 YouTube Key 后连接停止并清空消息，需要重新连接；换目标语言或翻译凭据会取消旧任务，清除旧译文并重新翻译当前保留的消息，不重启 YouTube 连接。保存纯样式修改也不会重启上游连接。

保留消息最多 500 条，去重与删除 ID 各最多 10000 条。新浏览器连接获得当前快照；慢客户端积压时以最新快照替换队列。消息历史不落盘，服务重启后不会恢复旧聊天内容。

**删除同步限制**：官方 `tombstone` 只表示消息已删除，官方明确说明它并不是即时删除推送。本工具会处理收到的 tombstone 和封禁事件，删除当前缓存中相关消息，并忽略迟到的翻译回调；不能保证已展示单条消息的删除实时同步。封禁事件用于清除当前该作者消息，不额外永久屏蔽其日后被解禁的正常发言。[官方消息定义](https://developers.google.com/youtube/v3/live/docs/liveChatMessages)

## 开发与验证

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/generate_proto.py
.venv/bin/python -m pytest -q
cd frontend
npm run build
npx playwright install chromium
npm test
```

官方 protobuf 和生成绑定已随项目保存，运行时无需安装 `grpcio-tools`。重新生成会覆盖两份绑定文件。Python 测试包含本地 gRPC wire contract 和模拟 HTTP 翻译服务；浏览器测试启动独立数据目录与本地服务器，不读取用户配置，也不消耗真实 API 额度。

验收记录见 [VALIDATION.md](VALIDATION.md)。当前没有真实用户凭据，未完成真实 YouTube / Azure 调用与 Windows OBS 人工验证；这些不能用演示或模拟测试替代。

## 首版边界与许可

支持单个公开直播间、普通文字、Unicode 表情、作者头像与角色、双语翻译、样式自定义及独立 EXE 打包。暂不支持发送弹幕、付费卡片、会员事件卡片、自定义表情图片、多直播间或 OBS 原生插件。

本项目新增代码使用 MIT。上游复用版本、修改范围及许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 `licenses/`。
