# YouTube OBS 多语言弹幕

本地运行的 YouTube 直播评论栏：免费抓取公开直播弹幕，无需 YouTube API Key；使用 Google 网页翻译同时翻译为多种语言，按自定义顺序显示在原文下方。透明网页可直接加入 OBS 浏览器源。

前端复用 [blivechat](https://github.com/xfgryujk/blivechat) 的渲染组件、基础 DOM 和滚动效果，支持普通弹幕的既有 CSS 选择器。支持 **Google 翻译免 Key（实验性）** 和 Azure Translator **F0 免费档**。

## Windows 快速开始

1. 安装 **Python 3.11 或更新版本**，以及 **Node.js 22 LTS 或更新版本**。安装 Python 时勾选添加到 PATH；安装后重新打开终端。
2. 下载或复制完整项目，双击 `install.cmd`。它创建 `.venv`、安装固定的 Python 运行依赖、执行 `npm ci`，并构建前端。首次安装需要联网。
3. 双击 `start.cmd`，保持终端窗口打开；浏览器访问 **http://127.0.0.1:12450**。
4. 无需凭据即可点击「体验演示」，确认原文、译文、样式和预览正常。
5. 粘贴 YouTube 直播视频链接，保留默认「免费网页抓取」；在「多语言翻译」选择 Google，添加目标语言并开启翻译，拖动语言卡片或使用 ↑ ↓ 排序，然后保存。两者均无需自己申请 API Key；也保留官方 YouTube API 和 Azure 翻译选项。
6. 点击「连接直播间」。在 OBS 添加「浏览器」源，粘贴 **http://127.0.0.1:12450/overlay**，建议尺寸 **480 × 720**。

源码部署使用 `start.cmd`；也可以按下方流程生成独立 EXE。前端只在安装或代码更新后需要重新构建。

## Windows 单文件 EXE

已提供 PyInstaller 打包配置和 Windows 一键构建脚本，目标为 **Windows x64**。构建者需要 Python、Node.js 和联网环境；拿到成品的使用者无需安装 Python、Node.js 或项目依赖。

**本机打包**：在 Windows 上双击 `build-exe.cmd`。脚本安装依赖、构建前端、生成单文件并进行实际启动冒烟测试；成功后产物为 `dist/YouTubeOBSChat.exe`。

**下载已发布版本**：在仓库的 Releases 页面下载 `YouTubeOBSChat-Windows-x64.zip`，解压后运行其中的 `YouTubeOBSChat.exe`；压缩包包含使用文档和第三方许可证。也提供单独的 EXE 和 `SHA256SUMS.txt` 校验文件。

**v0.3.0 表情支持版**：在 Releases 下载 `YouTubeOBSChat-Windows-x64.zip` 或 `YouTubeOBSChat.exe`。新增频道自定义表情、文字与表情混排、YouTube 贴纸图片展示及图片失败回退；保留此前演示、网页解析和多语言翻译修复。退出旧程序后替换 EXE，并刷新设置页与 OBS 浏览器源。

**GitHub 构建**：在 Actions 中选择 **Build Windows EXE → Run workflow**，构建通过后下载 `YouTubeOBSChat-Windows-x64` artifact。推送 `v*` 版本标签时，CI 在 Windows x64 上运行自动测试、生成 EXE 并实际启动验证，全部通过后自动创建 Release 并上传 EXE、发行压缩包及 SHA-256 校验文件；手动构建仅生成 artifact。

EXE 的使用方式：

1. 双击 `YouTubeOBSChat.exe`；服务启动成功后自动打开设置页。
2. 保持控制台窗口打开，关闭窗口或按 Ctrl+C 会停止服务。浏览器标签页关闭不会停止服务。
3. OBS 地址仍为 `http://127.0.0.1:12450/overlay`。应用不会自动连接直播间，需要在设置页点击连接。
4. 配置默认保存到 **`%LOCALAPPDATA%\YouTubeOBSChat\config.json`**，不会放进单文件解压的临时目录；替换 EXE 后配置仍然保留。源码版原有 `data/config.json` 不自动迁移；需要时将它复制到新目录，切勿将真实配置随 EXE 分发。

可在命令行运行 `YouTubeOBSChat.exe --port 12460` 或 `YouTubeOBSChat.exe --no-browser`。也支持 `YTCHAT_DATA_DIR` 指定数据目录。端口被占用时程序提示失败，保留控制台供查看，不自动改端口以免 OBS 地址失效。

仅将前端构建结果、默认头像、许可证和程序依赖加入 EXE，**不包含真实 API Key 或用户数据目录**。分发时请附上 `LICENSE`、`THIRD_PARTY_NOTICES.md` 与 `licenses/`。

Windows EXE 必须由 Windows 本机构建或 Actions Windows runner 生成；当前 Linux 环境不能直接生成 Windows EXE。[PyInstaller 平台说明](https://pyinstaller.org/en/stable/operating-mode.html)

## 免费抓取与多语言翻译

新增功能自 v0.2.0 起提供；推荐使用修复演示和网页解析的 v0.2.1 或更新版本，或运行本次源码；已有 v0.1.1 Release 二进制不包含这些更新。

默认使用 **免费网页抓取**，接受公开正在直播的视频链接或 11 位视频 ID。它读取 YouTube 网页的聊天续传接口，共享同一条上游连接、按网页给出的间隔轮询，保留消息去重、历史过滤、删除和作者封禁处理。无需用户账号或 API Key，不占用用户的 YouTube Data API 配额。

这是非官方网页协议，不保证持续可用。登录/年龄限制、隐私同意、验证码、限流、地区或网络限制、网页协议变化可能导致无法接入；界面会显示错误，不会自动切换到需要 Key 的官方接口。不支持私有直播、聊天回放、频道主页自动找直播或网页模式下的 `liveChatId`。需要官方接口时，在连接设置中选择「官方 API」并填写自己的 Key。

在「多语言翻译」选择 Google，开启翻译，从下拉框添加目标语言。当前支持简体中文、繁体中文、英语、日语、韩语、西班牙语、法语、德语，最多同时选择 8 种。拖动卡片或使用 ↑ ↓ 调整顺序，至少保留一种语言；点击「保存设置」后，预览及所有 OBS 页面同步。只调整顺序会复用已有译文，不重复发起翻译请求；增删语言或切换服务会取消旧翻译任务并重新翻译保留消息，不重连 YouTube。

例如选择「简体中文 → English」，观众 XXX 发送「你好」：

```text
XXX: 你好
  · zh-Hans  你好
  · en       Hello
```

每种语言都有独立的完成/等待/失败状态，完成后在原行更新，不重排消息。即使译文与原文相同，也保留该语言行。失败时保留原文与其他成功译文；「恢复翻译」只重新提交未完成语言。Google 请求共用单并发和至少一秒间隔，缓存按「正文 + 目标语言」区分，重复请求合并；选择更多语言会增加等待时间。Google 网页接口无需 Key，但可能限流或变化，不保证永久免费可用。

「保存并测试翻译」会逐一测试选中的所有语言。演示提供全部八种常用目标语言的固定译文，无需联网；Azure 额外提供的其他语言显示「演示暂无该语言样例」。演示不能证明真实服务可用。

配置新增 `youtube_provider`（`web` / `api`）和有序 `target_languages` 数组。旧的单语言 `target_language` 仍作为第一目标语言兼容；旧配置已有 YouTube Key 时保留官方 API 模式，旧配置和 API 客户端的单语言设置会迁移为单元素列表。`translations` 数组中的每项包含 `language`、`text`、`status`，通过快照和 translation WebSocket 事件同步。`.translation` 仍可用于自定义所有译文样式，单个语言可用 `.translation-row[data-language="en"]` 选取。

联网要求：免费弹幕需要 `www.youtube.com`，Google 翻译需要 `translate.googleapis.com`，头像通常来自 `yt3.ggpht.com` 或 `yt3.googleusercontent.com`。云环境启用了域名白名单时，需要允许上述目的域名。

### 网页连接错误排查

免费网页模式先读取独立聊天页，无法取得聊天数据时尝试观看页。程序识别常见初始数据赋值和嵌套聊天结构；遇到明确的登录、年龄验证、验证码或隐私同意页面时停止并提示，不会自动完成验证。

若同一电脑的浏览器未登录也能正常看到聊天，但程序仍报解析失败，请记录错误中的「聊天页 / 观看页 HTTP、响应类型、初始标记、解析与令牌」诊断信息。这些信息不包含 Cookie、密钥或网页正文。浏览器可能使用与程序不同的代理配置；请检查程序可使用的 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量。不要分享账号 Cookie 或真实配置文件。

## YouTube API 配置

1. 在 [Google Cloud Console](https://console.cloud.google.com/) 创建项目。
2. 启用 **YouTube Data API v3**，创建 API Key。建议将 Key 的 API 使用范围限制为 YouTube Data API；此工具在后端请求，不适用浏览器 HTTP Referer 限制。
3. 设置页输入正在直播的 `watch?v=…`、`youtu.be/…`、`youtube.com/live/…` 链接或 11 位视频 ID。也可以选择 `liveChatId` 类型并直接输入聊天 ID。
4. 本工具通过 `videos.list(part=liveStreamingDetails)` 解析 `activeLiveChatId`，再使用官方 `liveChatMessages.streamList` 接收推送。[官方指南](https://developers.google.com/youtube/v3/live/streaming-live-chat)

官方 API 模式自动识别时，11 位 ID 视为视频 ID；若聊天 ID 恰好也是 11 位，请显式选择 `liveChatId`。频道主页和 `@频道/live` 自动寻找直播暂不支持。默认使用 API Key 访问公开直播，不提供 OAuth 私有直播登录或发送弹幕功能。

YouTube API 有项目配额；`streamList` 每次调用的官方配额成本为 5 单位。程序共享上游连接、带续传令牌重连，不按浏览器数量重复拉取。不承诺免费配额能覆盖任意直播时长；配额耗尽、凭据无效或聊天关闭时停止自动重试并提示。[官方接口](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/streamList)

## 只接收连接后的新弹幕

设置页在点击「连接直播间」的瞬间记录时间（早于保存设置和建立上游连接），只保留发布时间不早于这一时刻的普通弹幕。YouTube 即使在首次响应中返回历史弹幕，程序也会先过滤，不显示、不缓存正文、不进入翻译队列。建立连接期间的新弹幕仍会保留。没有有效时区时间的普通消息无法确认是否属于新消息，直接忽略。

自动重连和打开多个 OBS 浏览器源共享本次连接起点；断开后再次连接会清空上次列表并重新记录起点。已在连接时重复点击不会重建上游连接或重置起点。删除、封禁及直播结束事件仍正常处理，演示模式不受影响。设置页显示已过滤的历史弹幕数量。

时间比较使用本机点击时间与 YouTube 发布时间，请保持系统时间同步。本功能消除连接前历史消息导致的积压；直播期间新弹幕过多或 Google 限流时仍可能排队。

## Google 免 Key 翻译（实验性）

此功能从 **v0.1.1** 起提供；请下载 v0.1.1 或更新版本，v0.1.0 不包含 Google 模式。

1. 启动程序，打开 `http://127.0.0.1:12450`，在「双语翻译」选择 **Google 翻译 · 免 Key（实验性）**。
2. 选择目标语言：简体中文、繁体中文、英语、日语、韩语、西班牙语、法语或德语。
3. 点击 **保存并测试翻译**。程序会向 Google 发送固定外语样例并显示真实结果；不需要连接 YouTube，测试请求不受弹幕翻译开关控制。测试失败时会显示限流、网络不可达或接口变化等原因。
4. 开启翻译并保存设置，连接真实 YouTube 直播间；原文立即显示，各语言译文完成后按所选顺序在原文下方补上。

此模式无需登录、创建 Google Cloud 项目、填写翻译 Key 或开通结算。它直接使用非官方网页接口，**不是官方 Cloud Translation API，没有固定免费额度或稳定性保证**。Google 官方 API 的每月 50 万字符抵扣额度与本模式无关。[官方价格说明](https://cloud.google.com/products/translate/pricing)

Google 默认单并发、相邻请求至少间隔 1 秒、队列最多 200 个任务、网络请求超时 5 秒。重复文本合并请求并缓存结果；纯表情、数字、链接跳过翻译。429 限流后新请求等待 60 秒，失败消息不自动重试；连续三次 429 后暂停。403、验证码页面和响应格式变化会暂停翻译。此时可点击 **恢复翻译**，或手动切换 Azure；恢复操作不能跳过现有冷却时间，程序也不会自动切换付费接口。

翻译测试和弹幕请求共享同一把连接锁、请求间隔、冷却与暂停状态。测试正在进行或直播翻译正占用连接时，重复测试会提示稍后重试；Google 网络不可达时仍保留原文。已复现旧版 httpx 客户端返回 429、同一环境 curl 返回 200 的差异；修复版 Google 请求使用独立的异步 libcurl 客户端，并已通过真实样例测试。接口可用性仍可能随网络和时间变化，请使用测试按钮确认。若显示「正在限流等待中」，表示此前请求触发了 60 秒冷却；此时连续点击不会发送新请求，等待后再测试。失败消息保留原文且不自动重试。点击「恢复翻译」会重新提交当前保留列表中的未完成消息，保留已经成功的译文，且不能跳过限流冷却。设置页显示当前保留弹幕的等待、完成、失败和跳过数量（同语言译文也保留独立语言行）。被删除或移出保留列表的旧弹幕不再占用待处理请求；已显示消息的译文更新直接应用，不等待新消息滚动队列。

新安装默认选择免费网页抓取和 Google，翻译开关仍关闭；旧版本配置缺少 `translation_provider` 时按 Azure 读取，原凭据保留。切换服务时，移除不支持的目标语言；若没有剩余语言则使用简体中文并提示；切换服务或语言会取消旧任务，清除旧译文并重译当前保留消息，不重启 YouTube 连接。切换到 Google 不会删除已保存的 Azure Key。

开启 Google 翻译后，弹幕正文会发送至 Google；作者名称、头像和本地密钥不包含在翻译请求正文中。请求使用 HTTPS，程序不记录包含弹幕内容的外部请求 URL。

实现参考沉浸式翻译的服务适配、缓存与双语展示思路，以及其[早期公开实现](https://github.com/immersive-translate/old-immersive-translate/blob/main/src/background/translationService.js)和 [googletrans 的请求协议](https://github.com/ssut/py-googletrans/blob/main/googletrans/client.py)，适配器代码独立编写，未复制其源码；不依赖插件安装、浏览器登录或私有代理。

## Azure 免费翻译

1. 注册 Azure，在 [Azure Portal](https://portal.azure.com/) 创建 **Translator** 资源。
2. **定价层必须选择 F0 免费档**，不要选择 S1、付费多服务资源或自动升级套餐。
3. 在资源的「Keys and Endpoint」页面复制 Key 和区域，填入本工具。例如区域为 `eastasia`，使用资源实际显示值。
4. 在服务下拉框选择 Azure F0，开启翻译，选择主播语言，点击「保存设置」；若尚未连接，再点击「连接直播间」。

截至 2026-10-09，Azure F0 标准翻译每月提供 **200 万字符免费额度**；实际限制以账号和官方页面为准。本工具只调用标准文本翻译接口，不自动升级资源或切换到付费服务。[官方价格](https://azure.microsoft.com/en-us/pricing/details/translator/)

程序省略 `from` 参数，让 Azure 自动识别源语言；目标语言列表从官方 `/languages` 接口读取。如果列表暂不可用，显示内置常用语言并提示。译文与原文相同时仍保留目标语言行，以保持多语言显示顺序。短句、混合语言、俚语和人名的识别与翻译可能不准确。[翻译接口](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/v3/translate)

默认 4 个翻译 worker、200 个排队任务、每次调用最多等待 5 秒。重复文本共享请求，完成结果保存在最多 1000 条的内存缓存中；纯表情、数字、链接或空文本跳过翻译。限流退避 2 秒，当前消息保留原文；超时或服务失败也保留原文。鉴权或额度错误暂停翻译，点击「恢复翻译」、修改翻译配置或断开后重新连接可恢复。

开启翻译后，消息文本会发送给 Azure；作者名称、头像和 API Key 不包含在翻译正文中。Azure 资源是否为 F0 无法从翻译接口可靠判断，必须由用户创建资源时确认。本工具不显示账号实际剩余额度。

## 表情与贴纸

免费网页抓取模式支持 YouTube 自带图片表情、频道/会员自定义表情和 Super Sticker 图片。文字与多个表情按发送顺序混排，重复表情保留；纯 Unicode 表情继续正常显示。带表情的付费留言也可展示正文和表情，但不复刻付款金额、礼物或会员卡片。

图片表情随字号缩放，贴纸以较大且受限的尺寸显示；若图片过期、被删除或加载失败，回退为原表情名称/描述。原始图片格式由浏览器加载，程序不下载或转码用户图片。只接受 HTTPS 的 YouTube/Google 图片 CDN，阻止任意网页、脚本或内网 URL。

翻译时只发送消息的文字部分，保留原文行中的图片；不会把表情名称、贴纸描述或图片地址发给翻译服务。纯表情/贴纸消息无需翻译，不显示一组「已跳过」语言行。译文原位更新、重连快照、语言排序、删除和封禁均保留原有行为。

官方 YouTube API 只提供文本以及 Super Sticker 的描述/ID，未提供图片 URL 时显示文字描述；完整图片表情支持以免费网页模式的上游图片信息为准。外部任意图片链接不会自动转换为图片，暂不支持用户上传图片或识别图片中文字。

「体验演示」首条消息含本地花朵图片表情，可离线验证预览与 OBS 的图片加载和字号缩放。受限网络需要允许消息实际使用的 `*.ggpht.com`、`*.googleusercontent.com`、`*.gstatic.com` 或 `*.ytimg.com` 图片 CDN。

## 演示与样式

演示使用固定的日语、英语、中文、西班牙语和韩语样例；译文在原文到达约 0.7 秒后加入。不访问 YouTube 或翻译 API，不需要 Key。固定译文覆盖简体中文、繁体中文、英语、日语、韩语、西班牙语、法语和德语；这些语言均按所选顺序显示。Azure 其他语言显示「演示暂无该语言样例」。真实翻译使用设置中选定的 Google 或 Azure 服务；演示模式不能验证这些服务是否可用。

样式面板支持字号、原文颜色、译文颜色、头像显示、保留消息数量和任意自定义 CSS。修改样式即时影响预览；保存后同步所有 OBS 页面。「复制 CSS」可以将完整样式粘贴到 OBS 自定义 CSS。

保留的常用选择器包括：

```css
yt-live-chat-renderer { background: transparent; }
yt-live-chat-text-message-renderer { padding: 10px 16px; }
yt-live-chat-author-chip #author-name { font-weight: bold; }
yt-live-chat-text-message-renderer #message { color: white; }
.translation { color: #8de1cb; font-weight: 600; }
```

`#message` 仍然仅含原文，`.translation` 为每种语言的译文元素。同一条消息用 `data-message-id` 标识。默认样式放在 CSS layer 中，用户提供的普通 CSS 可以覆盖它。OBS 浏览器源自身的自定义 CSS 优先于默认 layer；来自 OBS 和项目配置的自定义 CSS 若相互冲突，仍遵循浏览器常规层叠规则。

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

YouTube 和选定的 Google / Azure 翻译服务必须能从本机访问。YouTube REST / Azure 使用 httpx，Google 网页翻译使用 curl_cffi / libcurl；各自遵循客户端支持的代理环境变量；gRPC 使用其自身的 HTTP CONNECT 代理配置。代理需要支持 TLS 和 HTTP/2。访问失败时查看设置页的状态信息，不要通过分享配置文件排查密钥问题。

## API 与数据流

| 接口 | 用途 |
| --- | --- |
| `GET /api/config` | 读取公开配置及密钥存在标记 |
| `PUT /api/config` | 保存部分配置；省略 Key 表示保留，Key 传空字符串表示清除；`style` 对象整体替换 |
| `POST /api/connect` | 连接当前直播间；同模式运行时重复调用不创建额外连接 |
| `POST /api/disconnect` | 停止上游与翻译，保留已显示消息 |
| `POST /api/demo` | 启动固定样例演示 |
| `GET /api/status` | 读取连接、翻译状态和浏览器连接数 |
| `GET /api/languages?provider=google_web或azure` | 返回指定服务的目标语言列表；省略参数使用已保存的服务，Google 为固定八种语言 |
| `POST /api/translation/test` | 使用已保存配置翻译固定外语样例；无需直播、允许翻译开关关闭时测试；失败返回脱敏错误及 code |
| `POST /api/translation/resume` | 手动恢复选定服务；Google 仍遵守已有冷却时间 |
| `WS /ws` | 推送当前快照与后续事件 |

WebSocket 消息新增有序 `translations` 数组，旧 `translation` 字段为兼容保留。事件含会话 `session`，类型为 `snapshot`、`message`、`translation`、`delete`、`status`。新增消息字段为 `id`、`author_id`、`author`、`avatar`、`role`、`time`、`original`、`translation`、`source_language` 和 `translation_status`。译文事件按 ID 原地更新，不重排或重新插入消息。

换直播源或 YouTube Key 后连接停止并清空消息，需要重新连接；换翻译服务、增删目标语言或翻译凭据会取消旧任务，清除旧译文并重新翻译当前保留的消息，不重启 YouTube 连接。保存纯样式修改也不会重启上游连接。

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

支持单个公开直播间、普通文字、Unicode 表情、作者头像与角色、多语言翻译、样式自定义及独立 EXE 打包。暂不支持发送弹幕、付费卡片、会员事件卡片、多直播间或 OBS 原生插件。

本项目新增代码使用 MIT。上游复用版本、修改范围及许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 `licenses/`。
