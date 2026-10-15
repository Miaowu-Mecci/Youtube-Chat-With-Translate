import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


from .message_content import normalize_parts, plain_text


class SourceError(Exception):
    def __init__(self, code: str, message: str, retry: bool = False):
        super().__init__(message)
        self.code, self.message, self.retry = code, message, retry


def parse_source(value: str) -> tuple[str, str]:
    value = value.strip()
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
    parts = normalize_parts(item["content_parts"]) if "content_parts" in item else None
    if parts is not None:
        text = plain_text(parts)
    avatar = author.get("profileImageUrl", "")
    if not avatar.startswith("https://"):
        avatar = ""
    role = "owner" if author.get("isChatOwner") else "moderator" if author.get("isChatModerator") else "member" if author.get("isChatSponsor") else "normal"
    return {"type": "message", "message": {
        "id": mid, "author_id": author.get("channelId", snippet.get("authorChannelId", "")),
        "author": author.get("displayName", "观众"), "avatar": avatar, "role": role,
        "time": snippet.get("publishedAt", ""), "original": text, "translation": "",
        "source_language": "", "translation_status": "skipped",
        **({"content_parts": parts} if parts is not None else {}),
    }}
