# 第三方源码说明

## blivechat

- 上游：https://github.com/xfgryujk/blivechat
- 提交：`848409df78d2cca65d3cc8ffe938eb6b6f261b76`，`dev` 分支，获取日期 2026-10-09。
- 复用：`frontend/src/components/ChatRenderer/`、`frontend/src/assets/css/youtube/`。
- 许可：MIT，Copyright (c) 2019 xfgryujk，完整文本见 `licenses/blivechat-MIT.txt`。
- 改动：普通消息传入独立译文、增加 `.translation` 和 `data-message-id`；使用 Vue 响应式字段更新；清空消息时取消旧滚动帧与消息定时器；移除普通消息重复计数控件，将徽章 tooltip 改为原生 title，并用本项目的配置、时间、头像及文案辅助模块适配。其余滚动逻辑和基础 DOM 保留。
- 付费消息、会员卡片及 ticker 源码作为组件依赖保留，但首版后端不产生这些消息。没有复用 B 站连接、翻译服务或插件系统。

## curl_cffi

- Google 网页翻译使用 curl_cffi 0.16.3 的异步 libcurl 会话，正常请求模式，未启用浏览器指纹模拟。
- 上游：https://github.com/lexiforest/curl_cffi
- 许可：MIT，完整文本见 `licenses/curl-cffi-MIT.txt`。原生库及传递依赖保留各自许可证。

## 依赖

Python 运行依赖固定在 `requirements.txt`，前端依赖固定在 `frontend/package-lock.json`。各依赖保留其自身许可证。

为复用上游组件，前端使用 Vue 2.7.16。`npm audit` 仍报告 Vue 2 模板解析器的低风险 ReDoS 项及其构建插件关联项；项目使用构建时预编译模板，运行时不会编译弹幕或用户 HTML。消息文字和译文以文本插值呈现；表情/贴纸使用校验后的图片 URL，通过 img 元素展示，不把消息当作 HTML。Vue 2 上游已停止常规维护，后续可单独计划迁移渲染组件。

## YouTube 表情协议参考

- 公开实现参考：[chat-downloader 的 YouTube 适配](https://github.com/xenova/chat-downloader/blob/94ed3fe9dd2af8f193ea5b25adc7509a8cbb0e63/chat_downloader/sites/youtube.py)，上游许可 MIT，查阅日期 2026-10-15。
- 参考 `message.runs[].emoji` 的 `emojiId`、`shortcuts`、`image.thumbnails`、`isCustomEmoji`，以及 `liveChatPaidStickerRenderer.sticker` 的消息结构。新增代码独立实现，未引入该项目依赖或复制其源码。
- 表情和贴纸图片由上游消息提供的 YouTube/Google CDN 地址加载，权利归原作者或平台所有。离线演示的 `frontend/public/emotes/sakura.svg` 为本项目自行绘制的示例。
