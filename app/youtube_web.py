"""Public YouTube live-chat continuation protocol; no account or user API key."""
import asyncio
import ast
import json
import re
from datetime import datetime, timezone

import httpx

from .youtube import Batch, SourceError, parse_source
from .message_content import parse_runs, plain_text, image_part


def json_objects(html: str, pattern: str):
    decoder = json.JSONDecoder()
    for match in re.finditer(pattern, html):
        tail = html[match.end():].lstrip()
        try:
            if tail.startswith("JSON.parse("):
                # Parse a literal string only; never execute JavaScript from a page.
                literal = re.match(r"(?:'(?:(?:\\.)|[^'\\])*'|\"(?:(?:\\.)|[^\"\\])*\")", tail[len("JSON.parse("):].lstrip())
                if not literal:
                    continue
                value = json.loads(ast.literal_eval(literal.group()))
            else:
                value = decoder.raw_decode(tail)[0]
            if isinstance(value, dict):
                yield value
        except (ValueError, SyntaxError, TypeError):
            continue


def extract_json(html: str, pattern: str):
    return next(json_objects(html, pattern), None)


def page_state(html):
    name = r"(?:\bytInitialData|window\s*\[\s*[\"']ytInitialData[\"']\s*\])\s*="
    candidates = list(json_objects(html, name))
    # Ignore unrelated early assignments, and accept JSON bootstrap responses too.
    data = next((value for value in candidates if continuation(find_chat_renderer(value))[0]),
                next((value for value in candidates if "contents" in value), None))
    if data is None:
        try:
            value = json.loads(html)
            if isinstance(value, dict) and "contents" in value:
                data = value
        except ValueError:
            pass
    cfg = {}
    for value in json_objects(html, r"ytcfg\.set\s*\("):
        cfg.update(value)
    player = extract_json(html, r"(?:\bytInitialPlayerResponse|window\s*\[\s*[\"']ytInitialPlayerResponse[\"']\s*\])\s*=") or {}
    return data, cfg, player


def page_diagnostic(stage, response, data, renderer):
    # Metadata only: never expose URLs, cookies, page contents, client keys or chat text.
    mime = response.headers.get("content-type", "").split(";", 1)[0].lower()
    kind = {"text/html": "HTML", "application/json": "JSON", "text/plain": "纯文本"}.get(mime, "未知类型")
    marker = "有" if "ytInitialData" in response.text else "无"
    parsed = "成功" if data is not None else "失败"
    token = "有" if continuation(renderer)[0] else "无"
    return f"{stage} HTTP {response.status_code}/{kind}，初始标记{marker}，解析{parsed}，聊天令牌{token}"


def find_chat_renderer(data):
    pending = [data]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            renderer = node.get("liveChatRenderer")
            if isinstance(renderer, dict):
                return renderer
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return {}


def check_page_access(html, player):
    lower = html.lower()
    if any(marker in lower for marker in ("g-recaptcha", "/sorry/index", "unusual traffic", "confirm you're not a bot", "confirm you’re not a bot")):
        raise SourceError("verification_required", "YouTube 要求验证码或机器人验证，免费网页模式无法自动完成验证。请在浏览器检查此直播，请在浏览器检查当前网络和访问状态。")
    if re.search(r'<form[^>]+action=[\"\'][^\"\']*consent\.(?:youtube|google)\.com', lower):
        raise SourceError("consent_required", "YouTube 返回隐私同意页面，未提供聊天数据；请检查所在网络的访问限制，请在浏览器检查当前网络和访问状态。")
    status = player.get("playabilityStatus", {})
    code = status.get("status")
    if code == "LOGIN_REQUIRED":
        raise SourceError("login_required", "此视频要求登录或年龄验证，匿名免费网页模式无法读取聊天；请在浏览器确认视频访问限制。")
    if code == "LIVE_STREAM_OFFLINE":
        raise SourceError("not_live", "直播尚未开始或当前未在直播，暂时无法连接实时聊天。")
    if code in {"ERROR", "UNPLAYABLE"}:
        raise SourceError("video_unavailable", "此视频不可用或受地区/访问权限限制，请在浏览器确认直播可公开观看。")


def continuation(data):
    if not isinstance(data, dict):
        return "", 2
    entries = data.get("continuations", [])
    if not isinstance(entries, list):
        return "", 2
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for name in ("invalidationContinuationData", "timedContinuationData", "reloadContinuationData"):
            value = entry.get(name, {})
            if isinstance(value, dict) and isinstance(value.get("continuation"), str) and value["continuation"]:
                try:
                    delay = float(value.get("timeoutMs", 2000)) / 1000
                except (ValueError, TypeError):
                    delay = 2
                return value["continuation"], max(1, min(30, delay))
    return "", 2


def text(value):
    return plain_text(parse_runs(value))


def map_action(action):
    if not isinstance(action, dict):
        return None
    for name in ("markChatItemAsDeletedAction", "removeChatItemAction"):
        if name in action:
            return {"snippet": {"type": "messageDeletedEvent", "messageDeletedDetails": {
                "deletedMessageId": action[name].get("targetItemId", "")}}}
    if "markChatItemsByAuthorAsDeletedAction" in action:
        return {"snippet": {"type": "userBannedEvent", "userBannedDetails": {"bannedUserDetails": {
            "channelId": action["markChatItemsByAuthorAsDeletedAction"].get("externalChannelId", "")}}}}
    item = action.get("addChatItemAction", {}).get("item", {})
    renderer = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer") or item.get("liveChatPaidStickerRenderer")
    if not renderer or not renderer.get("id"):
        return None
    try:
        published = datetime.fromtimestamp(int(renderer["timestampUsec"]) / 1_000_000, timezone.utc).isoformat()
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        return None
    badges = {badge.get("liveChatAuthorBadgeRenderer", {}).get("icon", {}).get("iconType", "")
              for badge in renderer.get("authorBadges", [])}
    thumbnails = renderer.get("authorPhoto", {}).get("thumbnails", [])
    parts = parse_runs(renderer.get("message"))
    if "liveChatPaidStickerRenderer" in item:
        sticker = renderer.get("sticker") or {}
        label = sticker.get("accessibility", {}).get("accessibilityData", {}).get("label", "[贴纸]")
        parts = [image_part(sticker, label if isinstance(label, str) else "[贴纸]", "sticker")]
    return {"id": renderer["id"], "content_parts": parts, "snippet": {"type": "textMessageEvent", "publishedAt": published,
            "textMessageDetails": {"messageText": plain_text(parts)}},
            "authorDetails": {"channelId": renderer.get("authorExternalChannelId", ""),
                "displayName": text(renderer.get("authorName")) or "观众",
                "profileImageUrl": thumbnails[-1].get("url", "") if thumbnails else "",
                "isChatOwner": "OWNER" in badges, "isChatModerator": "MODERATOR" in badges,
                "isChatSponsor": any("CUSTOM" in badge for badge in badges)}}


class WebChatSource:
    def __init__(self, client):
        self.client = client
        self.context = None
        self.initial = None
        self.page_key = ""
        self.client_name = "1"
        self.video = ""

    async def request(self, method, path, **kwargs):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9",
                       "Origin": "https://www.youtube.com"}
            if self.video:
                headers["Referer"] = "https://www.youtube.com/watch?v=" + self.video
            if self.context:
                client = self.context["client"]
                headers.update({"X-Youtube-Client-Name": self.client_name,
                                "X-Youtube-Client-Version": client["clientVersion"]})
                if client.get("visitorData"):
                    headers["X-Goog-Visitor-Id"] = client["visitorData"]
            response = await self.client.request(method, "https://www.youtube.com" + path,
                headers=headers, timeout=15, **kwargs)
        except httpx.ProxyError:
            raise SourceError("proxy", "代理未能建立到 YouTube 的连接，请检查代理设置和出口网络规则。", True) from None
        except httpx.HTTPError:
            raise SourceError("network", "无法访问 YouTube 网页，请检查网络或代理。", True) from None
        if response.status_code == 429:
            raise SourceError("rate_limited", "YouTube 网页暂时限流，请稍后手动重连。")
        if 300 <= response.status_code < 400:
            host = httpx.URL(response.headers.get("location", "")).host
            if host in {"consent.youtube.com", "consent.google.com"}:
                raise SourceError("consent_required", "YouTube 要求隐私同意，未提供聊天数据；请检查网络访问限制，请在浏览器检查当前网络和访问状态。")
            if host == "accounts.google.com":
                raise SourceError("login_required", "此视频要求登录，匿名免费网页模式无法读取聊天。")
        if response.status_code in {401, 403} or 300 <= response.status_code < 400:
            raise SourceError("web_blocked", "YouTube 网页要求登录、同意隐私政策或拒绝访问；请检查网络，并检查网页协议适配。")
        if response.status_code >= 400:
            raise SourceError("network", "YouTube 网页请求失败，请检查直播链接和网络。", response.status_code >= 500)
        return response

    async def resolve(self, source):
        parsed, video = parse_source(source)
        self.context, self.initial = None, None
        self.video = video
        response = await self.request("GET", "/live_chat", params={"v": video, "is_popout": "1", "hl": "en"})
        data, cfg, player = page_state(response.text)
        renderer = find_chat_renderer(data)
        check_page_access("" if continuation(renderer)[0] else response.text, player)
        diagnostics = [page_diagnostic("聊天页", response, data, renderer)]
        context = cfg.get("INNERTUBE_CONTEXT")
        client = context.get("client") if isinstance(context, dict) else None
        if not continuation(renderer)[0] or not isinstance(client, dict) or not client.get("clientVersion"):
            # Some public pages provide bootstrap data on /watch rather than /live_chat.
            response = await self.request("GET", "/watch", params={"v": video, "hl": "en"})
            watch_data, watch_cfg, player = page_state(response.text)
            watch_renderer = find_chat_renderer(watch_data)
            check_page_access("" if continuation(watch_renderer)[0] else response.text, player)
            diagnostics.append(page_diagnostic("观看页", response, watch_data, watch_renderer))
            cfg.update(watch_cfg)
            if continuation(watch_renderer)[0]:
                renderer = watch_renderer
            if watch_data is not None:
                data = watch_data
        if data is None:
            raise SourceError("web_protocol", "YouTube 聊天页和观看页均未提供可解析的数据。请确认链接在浏览器中可公开观看；若可观看但仍失败，需要更新网页协议适配。" + "；".join(diagnostics))
        if renderer.get("isReplay") or renderer.get("is_replay"):
            raise SourceError("chat_replay", "当前为直播聊天回放，免费网页模式仅支持正在直播的实时聊天。")
        # Select the unfiltered 'Live chat' continuation rather than 'Top chat'.
        menu = renderer.get("header", {}).get("liveChatHeaderRenderer", {}).get("viewSelector", {}).get("sortFilterSubMenuRenderer", {})
        for option in menu.get("subMenuItems", []):
            if option.get("title") == "Live chat":
                token_data = option.get("continuation", {}).get("reloadContinuationData", {})
                if token_data.get("continuation"):
                    renderer["continuations"] = [{"reloadContinuationData": token_data}]
                break
        token, _ = continuation(renderer)
        context = cfg.get("INNERTUBE_CONTEXT")
        if not token:
            raise SourceError("chat_unavailable", "未取得实时聊天令牌；可能是聊天未开放或页面结构已变化。" + "；".join(diagnostics))
        if not isinstance(context, dict) or not isinstance(context.get("client"), dict) or not context["client"].get("clientVersion"):
            raise SourceError("web_protocol", "YouTube 网页协议已变化，无法获取聊天客户端配置；请更新程序并检查网页协议适配。" + "；".join(diagnostics))
        self.context, self.initial = context, renderer
        self.page_key = cfg.get("INNERTUBE_API_KEY", "")
        self.client_name = str(cfg.get("INNERTUBE_CONTEXT_CLIENT_NAME", 1))
        return video

    async def stream(self, video, token=""):
        if not token:
            token, delay = continuation(self.initial)
            initial = [item for action in self.initial.get("actions", []) if (item := map_action(action))]
            yield Batch(initial, token)
        else:
            delay = 1
        while token:
            await asyncio.sleep(delay)
            params = {"prettyPrint": "false"}
            if self.page_key:
                params["key"] = self.page_key  # Public webpage client key, never a user's API credential.
            response = await self.request("POST", "/youtubei/v1/live_chat/get_live_chat", params=params, json={
                "context": self.context, "continuation": token,
            })
            try:
                data = response.json()["continuationContents"]["liveChatContinuation"]
                next_token, delay = continuation(data)
                items = [item for action in data.get("actions", []) if (item := map_action(action))]
            except (ValueError, KeyError, TypeError, AttributeError):
                raise SourceError("web_protocol", "YouTube 聊天响应格式变化或要求验证，请更新程序并检查网页协议适配。") from None
            token = next_token
            yield Batch(items, token, offline=not token)
