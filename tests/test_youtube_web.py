import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Config, ConfigStore
from app.hub import ChatHub
from app.youtube import SourceError, map_item
from app.youtube_web import ChatSource, WebChatSource, continuation, extract_json, map_action


def action(mid='one', body='你好', timestamp='1770000000000000'):
    return {'addChatItemAction': {'item': {'liveChatTextMessageRenderer': {
        'id': mid, 'timestampUsec': timestamp,
        'message': {'runs': [{'text': body}, {'emoji': {'shortcuts': ['🌸']}}]},
        'authorName': {'simpleText': 'Alice'}, 'authorExternalChannelId': 'channel',
        'authorPhoto': {'thumbnails': [{'url': 'https://yt3.ggpht.com/avatar'}]},
        'authorBadges': [{'liveChatAuthorBadgeRenderer': {'icon': {'iconType': 'MODERATOR'}}}],
    }}}}


def page():
    renderer = {'continuations': [{'invalidationContinuationData': {'continuation': 'initial', 'timeoutMs': 0}}],
                'actions': [action()]}
    context = {'client': {'clientName': 'WEB', 'clientVersion': '2.20261015', 'visitorData': 'public-visitor'}}
    return '<script>ytcfg.set({"OTHER":1});ytcfg.set(' + json.dumps({
        'INNERTUBE_CONTEXT': context, 'INNERTUBE_API_KEY': 'public-page-key', 'INNERTUBE_CONTEXT_CLIENT_NAME': 1
    }) + '); var ytInitialData = ' + json.dumps({'contents': {'liveChatRenderer': renderer}}) + ';</script>'


def test_web_mapping_text_emoji_roles_and_moderation():
    event = map_item(map_action(action()))
    assert event['message']['original'] == '你好🌸'
    assert event['message']['author'] == 'Alice'
    assert event['message']['role'] == 'moderator'
    assert datetime.fromisoformat(event['message']['time']).tzinfo is not None
    for kind in ['markChatItemAsDeletedAction', 'removeChatItemAction']:
        assert map_item(map_action({kind: {'targetItemId': 'one'}})) == {'type': 'delete', 'ids': ['one']}
    assert map_item(map_action({'markChatItemsByAuthorAsDeletedAction': {'externalChannelId': 'channel'}})) == {
        'type': 'ban', 'author_id': 'channel'}
    assert map_action(action(timestamp='invalid')) is None
    assert map_action({'addChatItemAction': {'item': {'liveChatPaidMessageRenderer': {}}}}) is None
    assert map_action(None) is None


async def test_web_resolve_poll_resume_and_end_without_user_key(monkeypatch):
    async def immediate(_): pass
    monkeypatch.setattr('app.youtube_web.asyncio.sleep', immediate)
    calls = []
    def respond(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, text=page())
        body = json.loads(request.content)
        assert body['context']['client']['clientName'] == 'WEB'
        assert request.headers['X-Youtube-Client-Version'] == '2.20261015'
        assert request.url.params['key'] == 'public-page-key'
        token = body['continuation']
        return httpx.Response(200, json={'continuationContents': {'liveChatContinuation': {
            'actions': [action('two')], 'continuations': [] if token == 'next' else [
                {'timedContinuationData': {'continuation': 'next', 'timeoutMs': 2000}}]}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        source = ChatSource(client)
        video = await source.resolve('https://youtu.be/abcdefghijk', 'auto', '')
        stream = source.stream(video, '', '')
        initial = await anext(stream)
        assert initial.token == 'initial' and initial.items[0]['id'] == 'one'
        batch = await anext(stream)
        assert batch.token == 'next' and not batch.offline
        await stream.aclose()
        resumed = source.stream(video, '', batch.token)
        final = await anext(resumed)
        assert final.offline
        await resumed.aclose()
        assert [json.loads(r.content)['continuation'] for r in calls[1:]] == ['initial', 'next']


@pytest.mark.parametrize('status,code,retry', [(403, 'web_blocked', False), (429, 'rate_limited', False), (503, 'network', True)])
async def test_web_failures_are_actionable(status, code, retry):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text='private upstream data'))) as client:
        with pytest.raises(SourceError) as exc:
            await WebChatSource(client).resolve('abcdefghijk', 'auto')
        assert exc.value.code == code and exc.value.retry == retry
        assert 'private upstream data' not in exc.value.message


@pytest.mark.parametrize('html', ['<html>consent required</html>', 'var ytInitialData = {"contents":{}};'])
async def test_unavailable_chat_is_not_a_fake_connection(html):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html))) as client:
        with pytest.raises(SourceError):
            await WebChatSource(client).resolve('abcdefghijk', 'auto')


async def test_chat_id_rejected_before_request():
    with pytest.raises(SourceError, match='直播视频链接'):
        await WebChatSource(None).resolve('chat-id', 'chat')


async def test_web_source_keeps_key_private_and_filters_historical_messages():
    cutoff = datetime.now(timezone.utc)
    delivered = asyncio.Event()
    class Source:
        async def resolve(self, source, kind, key):
            assert key == ''
            return 'abcdefghijk'
        async def stream(self, source, key, token):
            from app.youtube import Batch
            assert key == ''
            yield Batch([map_action(action('old')), map_action(action('new', timestamp=str(int(cutoff.timestamp() * 1_000_000) + 1)))], 'token')
            delivered.set()
            await asyncio.Event().wait()
    hub = ChatHub(Config(source='abcdefghijk', youtube_provider='web', youtube_key='DO_NOT_SEND'), Source(), None)
    await hub.connect(started_at=cutoff)
    try:
        await asyncio.wait_for(delivered.wait(), 1)
        assert list(hub.messages) == ['new']
        assert hub.ignored_history == 1
    finally:
        await hub.stop()


def test_legacy_config_migration_preserves_official_mode(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'youtube_key': 'OLD', 'target_language': 'en'}))
    config = ConfigStore(path).config
    assert config.youtube_provider == 'api' and config.target_languages == ['en']
    assert Config().youtube_provider == 'web'


def test_continuation_delay_bounds_and_safe_json_extraction():
    assert continuation({'continuations': [{'timedContinuationData': {'continuation': 'x', 'timeoutMs': 0}}]}) == ('x', 1)
    assert continuation({'continuations': [{'timedContinuationData': {'continuation': 'x', 'timeoutMs': 90000}}]}) == ('x', 30)
    assert extract_json('var ytInitialData = {"x":"};literal"}; extra()', r'ytInitialData\s*=') == {'x': '};literal'}
