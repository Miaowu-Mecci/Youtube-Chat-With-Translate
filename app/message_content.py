"""Structured chat text, YouTube emoji images and stickers."""
from urllib.parse import urlsplit

IMAGE_DOMAINS = ("ggpht.com", "googleusercontent.com", "gstatic.com", "ytimg.com")
DEMO_IMAGE = "/emotes/sakura.svg"


def safe_image_url(value):
    if value == DEMO_IMAGE:
        return value
    if not isinstance(value, str) or len(value) > 4096:
        return ""
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port in {None, 443}
                and any(host == domain or host.endswith("." + domain) for domain in IMAGE_DOMAINS)):
            return value
    except ValueError:
        pass
    return ""


def dimension(value, default):
    try:
        return max(1, min(512, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def image_part(image, label, kind="emoji", mid=""):
    image = image if isinstance(image, dict) else {}
    thumbnails = image.get("thumbnails", [])
    choices = [t for t in thumbnails if isinstance(t, dict) and safe_image_url(t.get("url"))] if isinstance(thumbnails, list) else []
    selected = max(choices, key=lambda t: dimension(t.get("width"), 24), default={})
    size = 128 if kind == "sticker" else 24
    return {"type": kind, "text": label[:200], "id": str(mid)[:256],
            "url": safe_image_url(selected.get("url", "")),
            "width": dimension(selected.get("width"), size),
            "height": dimension(selected.get("height"), size)}


def parse_runs(value):
    if not isinstance(value, dict):
        return []
    if isinstance(value.get("simpleText"), str) and value["simpleText"]:
        return [{"type": "text", "text": value["simpleText"]}]
    result = []
    runs = value.get("runs")
    for run in runs[:512] if isinstance(runs, list) else []:
        if not isinstance(run, dict):
            continue
        if isinstance(run.get("text"), str):
            result.append({"type": "text", "text": run["text"]})
        elif isinstance(run.get("emoji"), dict):
            emoji = run["emoji"]
            image = emoji.get("image") or {}
            shortcuts = emoji.get("shortcuts") or []
            label = next((s for s in shortcuts if isinstance(s, str) and s), "")
            if not label and isinstance(image, dict):
                label = image.get("accessibility", {}).get("accessibilityData", {}).get("label", "")
            if not isinstance(label, str) or not label:
                label = str(emoji.get("emojiId") or "[表情]")
            result.append(image_part(image, label, mid=emoji.get("emojiId", "")))
    return result


def normalize_parts(parts):
    result = []
    for part in parts[:512] if isinstance(parts, list) else []:
        if not isinstance(part, dict):
            continue
        text = part.get("text", "")
        if not isinstance(text, str):
            continue
        kind = part.get("type")
        if kind == "text":
            result.append({"type": "text", "text": text})
        elif kind in {"emoji", "sticker"}:
            result.append({"type": kind, "text": text[:200] or "[表情]", "id": str(part.get("id", ""))[:256],
                           "url": safe_image_url(part.get("url")),
                           "width": dimension(part.get("width"), 24), "height": dimension(part.get("height"), 24)})
    return result


def plain_text(parts):
    return "".join(part["text"] for part in parts)


def translation_text(message):
    parts = message.get("content_parts")
    if not isinstance(parts, list):
        return message["original"]
    # Image names/URLs are not natural-language text to send to translation APIs.
    return "".join(part.get("text", "") if part.get("type") == "text" else " " for part in parts).strip()
