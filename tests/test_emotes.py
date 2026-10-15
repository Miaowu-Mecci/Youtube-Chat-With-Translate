import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.hub import ChatHub
from app.message_content import parse_runs, plain_text, safe_image_url, translation_text
from app.server import create_app
from app.translation import Result
from app.youtube import map_item
from app.youtube_web import map_action

IMAGE = 'https://yt3.ggpht.com/channel-emote=w48-h48'
STICKER = 'https://lh3.googleusercontent.com/sticker'


def emoji(label=':wave:', url=IMAGE):
    return {'emoji': {'emojiId': 'channel/wave', 'shortcuts': [label], 'isCustomEmoji': True,
            'image': {'thumbnails': [{'url': url, 'width': 48, 'height': 48}]}}}


def action(runs):
    return {'addChatItemAction': {'item': {'liveChatTextMessageRenderer': {
        'id': 'one', 'timestampUsec': str(int(datetime.now(timezone.utc).timestamp() * 1_000_000)),
        'authorName': {'simpleText': 'Alice'}, 'message': {'runs': runs},
    }}}}


def mapped(runs):
    return map_item(map_action(action(runs)))['message']


def test_runs_keep_text_emoji_order_repeats_and_unicode():
    msg = mapped([{'text': 'Hello '}, emoji(), {'text': ' 🌸 '}, emoji()])
    assert msg['original'] == 'Hello :wave: 🌸 :wave:'
    parts = msg['content_parts']
    assert [p['type'] for p in parts] == ['text', 'emoji', 'text', 'emoji']
    assert parts[1]['url'] == IMAGE == parts[3]['url']
    assert parts[1]['width'] == parts[1]['height'] == 48
    assert ':wave:' not in translation_text(msg) and IMAGE not in translation_text(msg)
    assert 'Hello' in translation_text(msg)


def test_missing_shortcut_uses_accessibility_or_unicode_id():
    value = emoji()['emoji']
    value.pop('shortcuts')
    value['image']['accessibility'] = {'accessibilityData': {'label': '挥手'}}
    parts = parse_runs({'runs': [{'emoji': value}, {'emoji': {'emojiId': '🌸'}}]})
    assert plain_text(parts) == '挥手🌸'
    assert parts[1]['url'] == ''


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'data:image/svg+xml,evil', 'http://yt3.ggpht.com/x',
    'https://yt3.ggpht.com.evil.example/x', 'https://evil.example/x', 'https://user:password@yt3.ggpht.com/x',
    'https://127.0.0.1/x', 'https://yt3.ggpht.com:1234/x'])
def test_untrusted_image_urls_never_reach_renderer(url):
    msg = mapped([emoji(url=url)])
    assert msg['original'] == ':wave:'
    assert msg['content_parts'][0]['url'] == ''
    assert safe_image_url(url) == ''


def test_paid_sticker_uses_image_metadata_and_bounded_dimensions():
    data = action([])
    item = data['addChatItemAction']['item']
    renderer = item.pop('liveChatTextMessageRenderer')
    renderer['sticker'] = {'thumbnails': [{'url': STICKER, 'width': 9999999, 'height': -2}],
                           'accessibility': {'accessibilityData': {'label': '开心贴纸'}}}
    item['liveChatPaidStickerRenderer'] = renderer
    msg = map_item(map_action(data))['message']
    assert msg['original'] == '开心贴纸'
    sticker = msg['content_parts'][0]
    assert sticker['type'] == 'sticker' and sticker['url'] == STICKER
    assert 1 <= sticker['width'] <= 512 and 1 <= sticker['height'] <= 512
    assert translation_text(msg) == ''




async def test_pure_images_never_request_translation_and_remain_in_snapshots():
    class Provider:
        async def translate(self, *args):
            raise AssertionError('Image names must not be translated')
    hub = ChatHub(Config(translation_enabled=True, target_languages=['zh-Hans', 'en']), None, None)
    hub.mode = 'live'
    hub.provider = lambda: Provider()
    await hub.setup_translation()
    try:
        hub.add(mapped([emoji(), emoji(':dance:')]))
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        msg = hub.snapshot()['messages'][0]
        assert len(msg['content_parts']) == 2
        assert msg['translations'] == [] and msg['translation_status'] == 'skipped'
        await hub.configure(Config(translation_enabled=True, target_languages=['ja']))
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert hub.messages['one']['translations'] == []
    finally:
        await hub.stop()


async def test_mixed_text_translates_only_text_and_preserves_images_after_language_change():
    calls = []
    class Provider:
        async def translate(self, text, target):
            calls.append((text, target))
            return Result('你好', 'en')
    hub = ChatHub(Config(translation_enabled=True, target_languages=['zh-Hans', 'en']), None, None)
    hub.mode = 'live'
    hub.provider = lambda: Provider()
    await hub.setup_translation()
    hub.add(mapped([{'text': 'Hello'}, emoji(), {'text': 'world'}]))
    parts = hub.messages['one']['content_parts']
    try:
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert calls == [('Hello world', 'zh-Hans'), ('Hello world', 'en')]
        assert hub.messages['one']['content_parts'] == parts
        await hub.configure(Config(translation_enabled=True, target_languages=['ja']))
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert calls[-1] == ('Hello world', 'ja')
        assert hub.messages['one']['content_parts'] == parts
        hub.delete(['one'])
        hub.translated('one', Result('迟到', 'en'), 'complete', 'ja')
        assert not hub.messages
    finally:
        await hub.stop()


def test_demo_image_asset_is_served_without_external_access(tmp_path):
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        response = client.get('/emotes/sakura.svg')
        assert response.status_code == 200 and '<svg' in response.text
        assert 'image/svg+xml' in response.headers['content-type']
