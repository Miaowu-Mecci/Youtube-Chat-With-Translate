"""Public YouTube live-chat continuation protocol; no account or user API key."""
import asyncio
import json
import re
from datetime import datetime, timezone

import httpx

from .youtube import Batch, SourceError, YouTubeSource, parse_source


def extract_json(html: str, pattern: str):
    decoder = json.JSONDecoder()
    for match in re.finditer(pattern, html):
        try:
            return decoder.raw_decode(html[match.end():].lstrip())[0]
        except ValueError:
            continue
    return None


def continuation(data):
    if not isinstance(data, dict):
        return "", 2
    for entry in data.get("continuations", []):
        for name in ("invalidationContinuationData", "timedContinuationData", "reloadContinuationData"):
            value = entry.get(name, {})
            if value.get("continuation"):
                try:
                    delay = float(value.get("timeoutMs", 2000)) / 1000
                except (ValueError, TypeError):
                    delay = 2
                return value["continuation"], max(1, min(30, delay))
    return "", 2


def text(value):
    if not isinstance(value, dict):
        return ""
    return value.get("simpleText", "") or "".join(
        run.get("text", "") or next(iter(run.get("emoji", {}).get("shortcuts", [])), "")
        for run in value.get("runs", [])
    )


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
    renderer = action.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer")
    if not renderer or not renderer.get("id"):
        return None
    try:
        published = datetime.fromtimestamp(int(renderer["timestampUsec"]) / 1_000_000, timezone.utc).isoformat()
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        return None
    badges = {badge.get("liveChatAuthorBadgeRenderer", {}).get("icon", {}).get("iconType", "")
              for badge in renderer.get("authorBadges", [])}
    thumbnails = renderer.get("authorPhoto", {}).get("thumbnails", [])
    return {"id": renderer["id"], "snippet": {"type": "textMessageEvent", "publishedAt": published,
            "textMessageDetails": {"messageText": text(renderer.get("message"))}},
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
        self.api_key = ""
        self.client_name = "1"

    async def request(self, method, path, **kwargs):
        try:
            headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9",
                       "Origin": "https://www.youtube.com"}
            if self.context:
                client = self.context["client"]
                headers.update({"X-Youtube-Client-Name": self.client_name,
                                "X-Youtube-Client-Version": client["clientVersion"]})
                if client.get("visitorData"):
                    headers["X-Goog-Visitor-Id"] = client["visitorData"]
            response = await self.client.request(method, "https://www.youtube.com" + path,
                headers=headers, timeout=15, **kwargs)
        except httpx.HTTPError:
            raise SourceError("network", "无法访问 YouTube 网页，请检查网络或代理。", True) from None
        if response.status_code == 429:
            raise SourceError("rate_limited", "YouTube 网页暂时限流，请稍后手动重连。")
        if response.status_code in {401, 403} or 300 <= response.status_code < 400:
            raise SourceError("web_blocked", "YouTube 网页要求登录、同意隐私政策或拒绝访问；请检查网络，或切换官方 API。")
        if response.status_code >= 400:
            raise SourceError("network", "YouTube 网页请求失败，请检查直播链接和网络。", response.status_code >= 500)
        return response

    async def resolve(self, source, kind, key=""):
        parsed, video = parse_source(source, "video" if kind == "auto" else kind)
        if parsed != "video":
            raise SourceError("invalid_source", "免费网页模式需要直播视频链接或视频 ID，不支持 liveChatId。")
        response = await self.request("GET", "/live_chat", params={"v": video, "is_popout": "1", "hl": "en"})
        data = extract_json(response.text, r'(?:var\s+ytInitialData\s*=|window\["ytInitialData"\]\s*=|ytInitialData\s*=)')
        cfg = {}
        for match in re.finditer(r'ytcfg\.set\s*\(', response.text):
            try:
                value = json.JSONDecoder().raw_decode(response.text[match.end():].lstrip())[0]
                if isinstance(value, dict):
                    cfg.update(value)
            except ValueError:
                continue
        if not isinstance(data, dict):
            raise SourceError("web_protocol", "无法解析 YouTube 聊天网页，可能需要登录/验证或接口已变化。")
        renderer = data.get("contents", {}).get("liveChatRenderer", {})
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
            raise SourceError("chat_unavailable", "无法读取公开直播聊天：直播未开始、已结束、聊天关闭，或网页要求登录/验证。")
        if not isinstance(context, dict) or not isinstance(context.get("client"), dict) or not context["client"].get("clientVersion"):
            raise SourceError("web_protocol", "YouTube 网页协议已变化，无法获取聊天客户端配置；请更新程序或切换官方 API。")
        self.context, self.initial = context, renderer
        self.api_key = cfg.get("INNERTUBE_API_KEY", "")
        self.client_name = str(cfg.get("INNERTUBE_CONTEXT_CLIENT_NAME", 1))
        return video

    async def stream(self, video, key="", token=""):
        if not token:
            token, delay = continuation(self.initial)
            initial = [item for action in self.initial.get("actions", []) if (item := map_action(action))]
            yield Batch(initial, token)
        else:
            delay = 1
        while token:
            await asyncio.sleep(delay)
            params = {"prettyPrint": "false"}
            if self.api_key:
                params["key"] = self.api_key  # Public webpage client key, never a user's API credential.
            response = await self.request("POST", "/youtubei/v1/live_chat/get_live_chat", params=params, json={
                "context": self.context, "continuation": token,
            })
            try:
                data = response.json()["continuationContents"]["liveChatContinuation"]
                next_token, delay = continuation(data)
                items = [item for action in data.get("actions", []) if (item := map_action(action))]
            except (ValueError, KeyError, TypeError, AttributeError):
                raise SourceError("web_protocol", "YouTube 聊天响应格式变化或要求验证，请更新程序或切换官方 API。") from None
            token = next_token
            yield Batch(items, token, offline=not token)


class ChatSource:
    """The hub supplies a key only when official API mode is explicitly selected."""
    def __init__(self, client):
        self.api, self.web = YouTubeSource(client), WebChatSource(client)

    async def resolve(self, source, kind, key):
        return await (self.api if key else self.web).resolve(source, kind, key)

    async def stream(self, chat_id, key, token):
        async for batch in (self.api if key else self.web).stream(chat_id, key, token):
            yield batch
