# YouTube OBS 多语言弹幕

**简体中文** | [English](README.en.md) | [日本語](README.ja.md)

免费抓取公开 YouTube 直播弹幕，使用 Google Translate 免 Key 网页接口翻译为多种语言，按自定义顺序显示在透明 OBS 浏览器源中。支持频道自定义表情、图片表情与贴纸。

**v0.5.0** 新增中文、日语和英语界面，继续使用免费抓取和免 Key 的 Google Translate。Windows 下载见 [v0.5.0 Release](https://github.com/Miaowu-Mecci/Youtube-Chat-With-Translate/releases/tag/v0.5.0)，同时提供 EXE、含说明和许可证的 ZIP，以及 SHA-256 校验文件。直接运行 EXE 无需安装 Python、Node.js 或 Git。

## 界面语言

主界面右上角的 **Language** 下拉框可切换「简体中文 / 日本語 / English」。按钮、设置说明、目标语言名称、状态、错误诊断、提示及无障碍标签均使用所选界面语言。界面词库随程序提供，不调用 Google 翻译界面，也不需要网络。

首次打开按浏览器的首个受支持语言选择，无法匹配时使用中文；手动选择保存在当前浏览器中，刷新和再次打开后保留。禁用浏览器存储时仍可在当前页面切换。界面语言独立于弹幕翻译的目标语言，不修改直播配置、不发送翻译请求，也不改变原文和已完成译文。

同一浏览器中同源的预览与已打开 overlay 会即时同步界面语言，不重载页面或重放弹幕。OBS 的浏览器源拥有独立存储，不与外部浏览器共享语言偏好。界面语言切换从 v0.5.0 开始提供。

## 快速开始

### Windows EXE（推荐）

1. 从 [v0.5.0 Release](https://github.com/Miaowu-Mecci/Youtube-Chat-With-Translate/releases/tag/v0.5.0) 下载 `YouTubeOBSChat.exe` 或附带说明与许可证的 ZIP。使用 ZIP 时先解压，无需安装 Python、Node.js 或 Git。
2. 关闭旧程序，再双击 EXE。程序会自动打开设置页；保持终端窗口打开。也可手动访问 `http://127.0.0.1:12450`。
3. 点击「体验演示」，离线查看八语言译文及图片表情。演示不访问外部直播或翻译服务。
4. 粘贴正在直播的 YouTube 视频链接或 11 位视频 ID，点击「连接直播间」。
5. 开启翻译，添加目标语言并排序，保存设置。可先点击「保存并测试翻译」验证 Google 是否可访问。
6. OBS 添加「浏览器」源，地址为 `http://127.0.0.1:12450/overlay`，建议尺寸 480 × 720。

无需申请或填写 API Key，也无需选择接入模式或翻译服务。语言选择、排序、样式、翻译开关和诊断按钮保留。

### 从源码运行

仅源码运行需要 Python 3.11+ 和 Node.js 22+，安装后重新打开终端。Windows 先运行 `install.cmd` 安装依赖并构建前端，再运行 `start.cmd`，打开 `http://127.0.0.1:12450`。

非 Windows 环境或手动安装：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python main.py --no-browser
```

程序默认只监听本机回环地址，可用 `--port 12460` 更改端口。通过 `YTCHAT_DATA_DIR` 指定数据目录；源码默认使用 `data/`，Windows EXE 使用 `%LOCALAPPDATA%\YouTubeOBSChat\`。启动时不会自动连接直播间。

每个 overlay（包括设置页中的预览）打开或刷新后，先显示「弹幕姬开始工作」，只显示该页面随后接收的新弹幕，不回放已有消息。刷新一个页面不会清空其他页面或中断直播连接。保存设置和网络重连只更新该页面已接收的消息，不重新滚动历史；断网期间积压的消息不补播。启动标识表示显示页面已就绪，直播连接状态以设置页为准。

## 免费弹幕抓取

支持 `watch?v=…`、`youtu.be/…`、`youtube.com/live/…` 等视频链接和 11 位视频 ID。网页聊天接口使用服务器提供的续传令牌和轮询间隔；多个预览或 OBS 页面共享上游连接。保留去重、断线续传、删除与作者封禁处理。

只保留点击「连接直播间」后发布的新弹幕。连接建立期间的新消息会保留；历史弹幕不显示、不进入翻译队列。自动重连继续沿用本次连接起点，手动重新连接会重新记录起点。请保持系统时间同步。

只支持公开正在直播的视频聊天，不支持私有直播、聊天回放、liveChatId、频道主页自动找直播或发送消息。使用非官方网页协议，可能因登录/年龄限制、验证码、隐私同意、地区/网络限制、限流或网页变化而失败。

独立聊天页缺少初始数据时，会尝试观看页的聊天引导数据。错误会区分代理失败、登录/验证、未直播与协议解析失败。解析错误包含 HTTP 状态、响应类型、初始标记及聊天令牌是否存在，不包含 Cookie 或网页正文。

如果浏览器未登录可看聊天，程序仍无法连接，请检查程序和浏览器是否使用相同的代理出口。网页抓取使用 httpx，Google 翻译使用 curl_cffi/libcurl，遵循各自支持的 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量。遇到错误请提供界面中的完整诊断提示。

## 多语言翻译

支持简体中文、繁体中文、英语、日语、韩语、西班牙语、法语、德语，最多同时选择 8 种。拖动语言卡片或使用 ↑ ↓ 调整顺序，也可移除全部语言。保存后同步预览和所有 OBS 页面。目标语言为空时，只保留原文，不请求翻译、不显示译文或占位行，演示模式也遵循这一设置；重新添加语言并保存后即可恢复。

译文行只显示内容，不显示 zh-Hans、en、ja 等语言代码。例如选择中文与英语，XXX 发送「你好」：

```text
XXX: 你好
  · 你好
  · Hello
```

原文即时显示，各语言完成后在原消息中补上，不重排消息；相同语言的译文也保留一行。只调换顺序会复用已完成译文，增删语言或切换翻译开关会取消旧任务并更新当前保留消息，不重连直播间。

Google 网页翻译免账号、免 Key，使用非官方接口，没有固定免费额度或稳定性保证。共享单并发、至少 1 秒请求间隔及最多 200 个排队任务，超时 5 秒；相同正文和目标语言合并请求并缓存。语言越多，等待越长。429 后等待 60 秒，连续三次限流暂停；403、验证码或格式变化也会暂停。

失败时保留原文及其他成功译文。「恢复翻译」只重新提交当前保留消息中未完成的语言，不能跳过限流冷却。「保存并测试翻译」逐一测试所选目标语言，无需连接 YouTube，不受翻译开关控制。未选择目标语言时，测试和恢复按钮不可用。

演示为八种语言的固定样例，不消耗外部服务；演示成功不能证明真实 Google 或 YouTube 可用。开启真实翻译后，消息的文字部分会发送至 Google。

## 表情与贴纸

保留 YouTube 图片表情和频道/会员自定义表情的原始顺序，支持重复表情、文字混排、付费留言中的表情和 Super Sticker 图片；不复刻付款金额或礼物/会员卡片。Unicode 表情保持正常显示。

图片表情随字号缩放，贴纸尺寸受限。图片过期或加载失败时回退为表情名称/描述。翻译只处理文字，不发送图片地址或表情名称；纯图片消息无需翻译，不显示一组「已跳过」语言行。图片加载后会重新计算聊天列表布局。

只使用消息提供的 HTTPS YouTube/Google 图片 CDN 地址，不自动展开任意图片链接，不提供上传、OCR 或图像翻译。常见图片域名为 `*.ggpht.com`、`*.googleusercontent.com`、`*.gstatic.com`、`*.ytimg.com`。演示首条消息使用本地花朵图片，无需外网。

## 样式与配置

设置字号、原文/译文颜色、头像和保留消息数，可实时预览；保存后同步 OBS。`.translation` 定义译文样式，`#message` 对应原文。可用的选择器包括：

```css
yt-live-chat-renderer { background: transparent; }
yt-live-chat-text-message-renderer { padding: 10px 16px; }
yt-live-chat-author-chip #author-name { font-weight: bold; }
.translation { color: #8de1cb; font-weight: 600; }
```

普通 CSS 可以覆盖默认 CSS layer，OBS 自定义 CSS 仍遵循浏览器常规层叠。需要支持 `@layer` 和 `:has()` 的新版 OBS 浏览器源。

配置保存为数据目录下的 `config.json`。旧配置加载时会忽略已删除的接入模式、Key、服务和区域字段，保留直播链接、支持的目标语言、语言顺序与样式；下次保存时移除旧字段。不支持的旧目标语言会过滤，非空旧列表被全部过滤时使用简体中文。用户主动保存的空列表保持为空，仅显示原文。

聊天历史只保留在内存，重启不恢复。最多保留 500 条消息，去重与删除 ID 各最多 10000 条。官方网页删除事件未必即时推送，无法保证删除实时同步。

## 开发与构建

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
cd frontend
npm run build
npx playwright install chromium
npm test
```

浏览器测试使用独立临时数据目录和本地服务器，不读取用户配置或消耗外部翻译额度。无须 gRPC/protobuf 或代码生成。详细验证记录见 `VALIDATION.md`。

Windows 本机运行 `build-exe.cmd` 可构建 `dist/YouTubeOBSChat.exe` 并执行启动冒烟测试。必须在 Windows 构建 Windows EXE；Linux 不能直接生成 Windows EXE。打包包含前端、离线图片示例、文档和许可证，不包含用户数据。

仅在用户明确要求发布 release 时创建发布标签并发布；日常源码修改、提交和推送不自动发布。

## 本地接口

| 接口 | 用途 |
| --- | --- |
| `GET /api/config`、`PUT /api/config` | 读取、保存配置 |
| `POST /api/connect`、`POST /api/disconnect` | 连接、停止直播 |
| `POST /api/demo` | 启动离线演示 |
| `GET /api/status` | 连接状态和翻译进度 |
| `GET /api/languages` | 八种 Google 目标语言 |
| `POST /api/translation/test` | 测试全部所选语言 |
| `POST /api/translation/resume` | 恢复未完成翻译 |
| `WS /ws` | 快照、原消息、译文、删除及状态事件 |

消息的 `content_parts` 为文字、表情、贴纸的有序片段；`translations` 为有序语言结果。语言代码只作为数据和 HTML 属性保留，不在弹幕译文前显示。

## 许可

本项目新增代码为 MIT，渲染组件复用 blivechat 的 MIT 代码。协议研究与第三方说明见 `THIRD_PARTY_NOTICES.md` 和 `licenses/`。
