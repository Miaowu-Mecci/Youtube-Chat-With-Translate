import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import grpc
import httpx
from google.protobuf.json_format import MessageToDict

from .proto import stream_list_pb2 as pb
from .proto import stream_list_pb2_grpc as rpc


class SourceError(Exception):
    def __init__(self, code: str, message: str, retry: bool = False):
        super().__init__(message)
        self.code, self.message, self.retry = code, message, retry


def parse_source(value: str, kind: str = "auto") -> tuple[str, str]:
    value = value.strip()
    if kind == "chat":
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", value):
            raise SourceError("invalid_source", "liveChatId 格式不正确。")
        return "chat", value
    video = value
    if "://" in value or value.startswith(("www.youtube.com/", "youtube.com/", "youtu.be/")):
        url = urlparse(value if "://" in value else "https://" + value)
        host = (url.hostname or "").lower()
        parts = url.path.strip("/").split("/")
        if url.scheme not in {"http", "https"}:
            raise SourceError("invalid_source", "请使用 YouTube 直播链接。")
        if host in {"youtu.be", "www.youtu.be"}:
            video = parts[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            video = parse_qs(url.query).get("v", [""])[0] if parts[0] == "watch" else (
                parts[1] if len(parts) == 2 and parts[0] in {"live", "embed", "shorts"} else ""
            )
        else:
            raise SourceError("invalid_source", "只接受 YouTube 直播链接。")
    elif kind == "auto" and not re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return parse_source(value, "chat")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise SourceError("invalid_source", "视频 ID 必须为 11 位；频道主页地址不受支持。")
    return "video", video


@dataclass
class Batch:
    items: list[dict]
    token: str = ""
    offline: bool = False


def map_item(item: dict) -> dict | None:
    snippet, author = item.get("snippet", {}), item.get("authorDetails", {})
    kind, mid = snippet.get("type"), item.get("id", "")
    if kind in {"TOMBSTONE", "tombstone", "messageDeletedEvent"}:
        return {"type": "delete", "ids": [snippet.get("messageDeletedDetails", {}).get("deletedMessageId", mid)]}
    if kind in {"USER_BANNED_EVENT", "userBannedEvent"}:
        return {"type": "ban", "author_id": snippet.get("userBannedDetails", {}).get("bannedUserDetails", {}).get("channelId", "")}
    if kind in {"CHAT_ENDED_EVENT", "chatEndedEvent"}:
        return {"type": "ended"}
    if kind not in {"TEXT_MESSAGE_EVENT", "textMessageEvent"} or not mid:
        return None
    text = snippet.get("textMessageDetails", {}).get("messageText", snippet.get("displayMessage", ""))
    avatar = author.get("profileImageUrl", "")
    if not avatar.startswith("https://"):
        avatar = ""
    role = "owner" if author.get("isChatOwner") else "moderator" if author.get("isChatModerator") else "member" if author.get("isChatSponsor") else "normal"
    return {"type": "message", "message": {
        "id": mid, "author_id": author.get("channelId", snippet.get("authorChannelId", "")),
        "author": author.get("displayName", "观众"), "avatar": avatar, "role": role,
        "time": snippet.get("publishedAt", ""), "original": text, "translation": "",
        "source_language": "", "translation_status": "skipped",
    }}


def grpc_error(error: grpc.aio.AioRpcError) -> SourceError:
    code, details = error.code(), error.details() or ""
    upper = details.upper()
    if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
        if "QUOTA" in upper or "DAILY" in upper:
            return SourceError("quota_exhausted", "YouTube 配额已耗尽，请检查 Google Cloud 配额。")
        # Ambiguous exhaustion must not create an endless quota-consuming retry loop.
        return SourceError("rate_limited", "YouTube 限流或配额不足，请稍后手动重连。")
    if code == grpc.StatusCode.UNAUTHENTICATED or code == grpc.StatusCode.PERMISSION_DENIED:
        return SourceError("credentials", "YouTube Key 无效、API 未启用或没有访问权限。")
    if code == grpc.StatusCode.FAILED_PRECONDITION:
        return SourceError("chat_unavailable", "直播已结束或聊天已关闭。")
    if code == grpc.StatusCode.NOT_FOUND:
        return SourceError("chat_not_found", "找不到直播聊天，请检查输入。")
    if code == grpc.StatusCode.INVALID_ARGUMENT:
        return SourceError("invalid_request", "YouTube 请求参数或续传令牌无效，请重新连接。")
    return SourceError("network", "YouTube 连接中断，正在重连。", retry=code in {
        grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.INTERNAL,
    })


class YouTubeSource:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def resolve(self, source: str, kind: str, key: str) -> str:
        parsed, value = parse_source(source, kind)
        if parsed == "chat":
            return value
        try:
            response = await self.client.get("https://www.googleapis.com/youtube/v3/videos", params={
                "part": "liveStreamingDetails", "id": value, "key": key,
            }, timeout=10)
        except httpx.HTTPError:
            raise SourceError("network", "无法访问 YouTube API，请检查网络或代理。") from None
        if response.status_code != 200:
            reason = ""
            try:
                reason = response.json()["error"]["errors"][0]["reason"]
            except (ValueError, KeyError, IndexError, TypeError):
                pass
            if reason in {"quotaExceeded", "dailyLimitExceeded"}:
                raise SourceError("quota_exhausted", "YouTube 配额已耗尽。")
            raise SourceError("credentials", "无法读取直播信息，请检查 Key、API 启用状态和权限。")
        try:
            items = response.json().get("items", [])
            chat_id = items[0].get("liveStreamingDetails", {}).get("activeLiveChatId") if items else None
        except (ValueError, TypeError, AttributeError):
            raise SourceError("invalid_response", "YouTube 返回了无效的直播信息。") from None
        if not chat_id:
            raise SourceError("chat_unavailable", "直播未开始、已结束、聊天关闭或视频不可访问。")
        return chat_id

    async def stream(self, chat_id: str, key: str, token: str):
        async with grpc.aio.secure_channel("youtube.googleapis.com:443", grpc.ssl_channel_credentials()) as channel:
            stub = rpc.V3DataLiveChatMessageServiceStub(channel)
            request = pb.LiveChatMessageListRequest(
                live_chat_id=chat_id, part=["id", "snippet", "authorDetails"],
                profile_image_size=88, page_token=token, max_results=500,
            )
            try:
                async for response in stub.StreamList(request, metadata=(("x-goog-api-key", key),)):
                    data = MessageToDict(response)
                    yield Batch(data.get("items", []), data.get("nextPageToken", ""), bool(data.get("offlineAt")))
            except grpc.aio.AioRpcError as error:
                raise grpc_error(error) from None
