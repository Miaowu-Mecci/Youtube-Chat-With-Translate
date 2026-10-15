import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Config, ConfigStore
from app.hub import ChatHub
from app.youtube import SourceError, map_item
from app.youtube_web import WebChatSource, continuation, extract_json, map_action


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
        source = WebChatSource(client)
        video = await source.resolve('https://youtu.be/abcdefghijk')
        stream = source.stream(video)
        initial = await anext(stream)
        assert initial.token == 'initial' and initial.items[0]['id'] == 'one'
        batch = await anext(stream)
        assert batch.token == 'next' and not batch.offline
        await stream.aclose()
        resumed = source.stream(video, batch.token)
        final = await anext(resumed)
        assert final.offline
        await resumed.aclose()
        assert [json.loads(r.content)['continuation'] for r in calls[1:]] == ['initial', 'next']


@pytest.mark.parametrize('status,code,retry', [(403, 'web_blocked', False), (429, 'rate_limited', False), (503, 'network', True)])
async def test_web_failures_are_actionable(status, code, retry):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text='private upstream data'))) as client:
        with pytest.raises(SourceError) as exc:
            await WebChatSource(client).resolve('abcdefghijk')
        assert exc.value.code == code and exc.value.retry == retry
        assert 'private upstream data' not in exc.value.message


@pytest.mark.parametrize('html', ['<html>consent required</html>', 'var ytInitialData = {"contents":{}};'])
async def test_unavailable_chat_is_not_a_fake_connection(html):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html))) as client:
        with pytest.raises(SourceError):
            await WebChatSource(client).resolve('abcdefghijk')


async def test_chat_id_rejected_before_request():
    with pytest.raises(SourceError, match='视频 ID'):
        await WebChatSource(None).resolve('chat-id')


async def test_web_source_filters_historical_messages():
    cutoff = datetime.now(timezone.utc)
    delivered = asyncio.Event()
    class Source:
        async def resolve(self, source):
            return 'abcdefghijk'
        async def stream(self, source, token):
            from app.youtube import Batch
            yield Batch([map_action(action('old')), map_action(action('new', timestamp=str(int(cutoff.timestamp() * 1_000_000) + 1)))], 'token')
            delivered.set()
            await asyncio.Event().wait()
    hub = ChatHub(Config(source='abcdefghijk'), Source(), None)
    await hub.connect(started_at=cutoff)
    try:
        await asyncio.wait_for(delivered.wait(), 1)
        assert list(hub.messages) == ['new']
        assert hub.ignored_history == 1
    finally:
        await hub.stop()


def test_legacy_config_migration_discards_removed_credentials(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'youtube_key': 'OLD', 'target_language': 'en'}))
    config = ConfigStore(path).config
    assert 'youtube_provider' not in config.public() and config.target_languages == ['en']
    assert 'youtube_key' not in Config().public()


def test_continuation_delay_bounds_and_safe_json_extraction():
    assert continuation({'continuations': [{'timedContinuationData': {'continuation': 'x', 'timeoutMs': 0}}]}) == ('x', 1)
    assert continuation({'continuations': [{'timedContinuationData': {'continuation': 'x', 'timeoutMs': 90000}}]}) == ('x', 30)
    assert extract_json('var ytInitialData = {"x":"};literal"}; extra()', r'ytInitialData\s*=') == {'x': '};literal'}


@pytest.mark.parametrize('assignment', [
    "window['ytInitialData'] = ",
    "window [ 'ytInitialData' ] = ",
    'window [ "ytInitialData" ] = ',
    'let ytInitialData = ',
])
async def test_web_bootstrap_accepts_script_assignment_variants(assignment):
    html = page().replace('var ytInitialData = ', assignment)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html))) as client:
        assert await WebChatSource(client).resolve('Sv2vZ8uZKVI') == 'Sv2vZ8uZKVI'


def test_page_state_accepts_json_parse_without_executing_script():
    from app.youtube_web import page_state
    data = {'contents': {'liveChatRenderer': {'continuations': []}}}
    html = 'window["ytInitialData"] = JSON.parse(' + json.dumps(json.dumps(data)) + ');'
    assert page_state(html)[0] == data
    html = "window['ytInitialData'] = JSON.parse('" + json.dumps(data) + "');"
    assert page_state(html)[0] == data
    assert page_state("ytInitialData = JSON.parse(__import__('os').system('false'));")[0] is None


async def test_missing_chat_bootstrap_falls_back_to_watch_page_and_polls(monkeypatch):
    from app.youtube_web import page_state
    data, cfg, _ = page_state(page())
    renderer = data['contents']['liveChatRenderer']
    watch_data = {'contents': {'twoColumnWatchNextResults': {'conversationBar': {'liveChatRenderer': renderer}}}}
    html = '<script>ytcfg.set(' + json.dumps(cfg) + '); window[\'ytInitialData\'] = ' + json.dumps(watch_data) + ';</script>'
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.url.path == '/live_chat':
            return httpx.Response(200, text='<html><body>chat frame without bootstrap</body></html>')
        if request.url.path == '/watch':
            return httpx.Response(200, text=html)
        body = json.loads(request.content)
        assert body['continuation'] == 'initial'
        return httpx.Response(200, json={'continuationContents': {'liveChatContinuation': {'actions': [action('new')], 'continuations': []}}})
    async def immediate(_): pass
    monkeypatch.setattr('app.youtube_web.asyncio.sleep', immediate)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        source = WebChatSource(client)
        video = await source.resolve('https://www.youtube.com/watch?v=Sv2vZ8uZKVI')
        stream = source.stream(video)
        try:
            await anext(stream)
            final = await anext(stream)
            assert final.items[0]['id'] == 'new' and final.offline
        finally:
            await stream.aclose()
    assert calls == ['/live_chat', '/watch', '/youtubei/v1/live_chat/get_live_chat']


@pytest.mark.parametrize('status,expected', [
    ('LOGIN_REQUIRED', 'login_required'), ('LIVE_STREAM_OFFLINE', 'not_live'),
    ('ERROR', 'video_unavailable'), ('UNPLAYABLE', 'video_unavailable'),
])
async def test_watch_fallback_identifies_video_access_state(status, expected):
    calls = []
    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(200, text='var ytInitialPlayerResponse = ' + json.dumps({'playabilityStatus': {'status': status}}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SourceError) as error:
            await WebChatSource(client).resolve('Sv2vZ8uZKVI')
        assert error.value.code == expected
        assert calls == ['/live_chat']


@pytest.mark.parametrize('html,code', [
    ('<html><div class="g-recaptcha"></div></html>', 'verification_required'),
    ('<html><p>Sign in to confirm you’re not a bot</p></html>', 'verification_required'),
    ('<form action="https://consent.youtube.com/save"></form>', 'consent_required'),
])
async def test_challenge_pages_report_specific_blocker_without_retry(html, code):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, text=html)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SourceError) as error:
            await WebChatSource(client).resolve('Sv2vZ8uZKVI')
        assert error.value.code == code and not error.value.retry
    assert len(calls) == 1


@pytest.mark.parametrize('destination,code', [
    ('https://consent.youtube.com/m', 'consent_required'),
    ('https://accounts.google.com/ServiceLogin', 'login_required'),
])
async def test_access_redirect_is_not_followed(destination, code):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(303, headers={'location': destination}))) as client:
        with pytest.raises(SourceError) as error:
            await WebChatSource(client).resolve('Sv2vZ8uZKVI')
        assert error.value.code == code


async def test_proxy_rejection_is_not_reported_as_page_parser_failure():
    def respond(request):
        raise httpx.ProxyError('CONNECT tunnel rejected')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SourceError) as error:
            await WebChatSource(client).resolve('Sv2vZ8uZKVI')
        assert error.value.code == 'proxy'


async def test_chat_text_cannot_be_mistaken_for_a_verification_page():
    html = page().replace('你好', "Sign in to confirm you're not a bot")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html))) as client:
        assert await WebChatSource(client).resolve('Sv2vZ8uZKVI') == 'Sv2vZ8uZKVI'


async def test_parser_diagnostics_include_only_safe_page_metadata():
    def respond(request):
        return httpx.Response(200, text='<html>TOP_SECRET private-body</html>', headers={'content-type': 'text/html', 'set-cookie': 'SECRET=hidden'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SourceError) as error:
            await WebChatSource(client).resolve('Sv2vZ8uZKVI')
        assert error.value.code == 'web_protocol'
        assert '聊天页 HTTP 200/HTML' in error.value.message
        assert '观看页 HTTP 200/HTML' in error.value.message
        assert '初始标记无' in error.value.message
        assert 'TOP_SECRET' not in error.value.message and 'SECRET' not in error.value.message
