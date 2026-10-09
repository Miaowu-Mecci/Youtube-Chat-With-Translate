import asyncio
import json
import time
from datetime import datetime, timezone

import httpx
import pytest
from curl_cffi import AsyncSession
from curl_cffi.requests.exceptions import RequestException
from fastapi.testclient import TestClient

from app.config import Config, ConfigStore
from app.hub import ChatHub
from app.server import create_app
from app.translation import GoogleWebTranslator, Result, TranslationError, TranslationPool
from app.youtube import Batch


def item():
    return {'id': 'one', 'snippet': {'type': 'textMessageEvent',
            'publishedAt': datetime.now(timezone.utc).isoformat(), 'textMessageDetails': {'messageText': 'hello'}},
            'authorDetails': {'channelId': 'author', 'displayName': 'Alice'}}


def payload(text='你好', language='en'):
    return [[[text, 'Hello', None, None]], None, language]


def test_new_config_and_legacy_migration(tmp_path):
    path = tmp_path / 'config.json'
    assert ConfigStore(path).config.translation_provider == 'google_web'
    path.write_text(json.dumps({'azure_key': 'PRIVATE', 'azure_region': 'eastasia',
                                'target_language': 'it', 'translation_enabled': True}), encoding='utf-8')
    store = ConfigStore(path)
    assert store.config.translation_provider == 'azure'
    assert store.config.target_language == 'it'
    assert store.config.azure_key == 'PRIVATE'
    assert 'PRIVATE' not in str(store.config.public())
    store.save(store.config)
    assert ConfigStore(path).config.translation_provider == 'azure'
    assert Config(translation_provider='google_web', target_language='it').target_language == 'zh-Hans'


@pytest.mark.parametrize('target,google', [('zh-Hans', 'zh-CN'), ('zh-Hant', 'zh-TW'), ('ja', 'ja')])
async def test_google_request_segments_and_language_mapping(target, google):
    def respond(request):
        assert request.url.host == 'translate.googleapis.com'
        assert dict(request.url.params) == {'client': 'gtx', 'sl': 'auto', 'tl': google, 'dt': 't', 'q': 'Hello! Welcome!'}
        assert 'key' not in request.url.params
        return httpx.Response(200, json=[[['你好！', 'Hello!', None], ['欢迎！', 'Welcome!', None]], None, 'zh-CN'])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await GoogleWebTranslator(client).translate('Hello! Welcome!', target) == Result('你好！欢迎！', 'zh-Hans')


@pytest.mark.parametrize('data', [{}, [], [[], None, 'en'], [[[None]], None, 'en'],
                                  [[['hello']], None, None], [[['']], None, 'en'], [[123], None, 'en']])
async def test_invalid_response_pauses_without_exposing_body(data):
    states = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))) as client:
        provider = GoogleWebTranslator(client, lambda *event: states.append(event))
        with pytest.raises(TranslationError) as error:
            await provider.translate('Hello', 'ja')
        assert error.value.code == 'invalid_response'
        provider.report_error(error.value.code)
        assert provider.paused and states[-1][0] == 'paused'


@pytest.mark.parametrize('response,code', [(httpx.Response(403, text='PRIVATE'), 'blocked'),
    (httpx.Response(200, text='<html>captcha</html>'), 'blocked'),
    (httpx.Response(200, text='not JSON'), 'invalid_response'),
    (httpx.Response(503, text='PRIVATE'), 'unavailable')])
async def test_google_errors(response, code):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
        provider = GoogleWebTranslator(client)
        with pytest.raises(TranslationError) as error:
            await provider.translate('Hello', 'ja')
        assert error.value.code == code
        assert 'PRIVATE' not in str(error.value)


async def test_network_timeout_keeps_pool_alive():
    def respond(request):
        raise httpx.ReadTimeout('PRIVATE URL', request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GoogleWebTranslator(client)
        pool = TranslationPool(provider, 'ja', lambda *args: None, lambda *args: None, concurrency=1)
        pool.start()
        try:
            pool.submit('one', 'hello')
            await asyncio.wait_for(pool.queue.join(), 1)
            assert not provider.paused and not pool.workers[0].done()
        finally:
            await pool.close()


async def test_three_429s_pause_and_manual_resume_keeps_cooldown():
    calls, states = [], []
    def respond(request):
        calls.append(request)
        return httpx.Response(429)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GoogleWebTranslator(client, lambda *event: states.append(event))
        provider.interval = 0
        pool = TranslationPool(provider, 'ja', lambda *args: None, lambda *args: None, concurrency=1)
        pool.start()
        try:
            for index in range(3):
                provider.cooldown_until = 0
                pool.submit(str(index), f'hello {index}')
                await asyncio.wait_for(pool.queue.join(), 1)
            assert len(calls) == 3 and provider.paused and states[-1][0] == 'paused'
            assert pool.submit('four', 'hello four') == 'skipped'
            until = provider.cooldown_until
            assert until > time.monotonic() + 59
            provider.resume()
            assert not provider.paused and provider.cooldown_until == until
            with pytest.raises(TranslationError) as error:
                await provider.translate('test', 'ja')
            assert error.value.code == 'cooldown' and len(calls) == 3
        finally:
            await pool.close()


async def test_success_resets_429_count_and_requests_are_serialized():
    active = 0
    maximum = 0
    starts = []
    async def respond(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        starts.append(time.monotonic())
        await asyncio.sleep(.01)
        active -= 1
        return httpx.Response(200, json=payload())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GoogleWebTranslator(client)
        provider.interval = .03
        provider.rate_failures = 2
        await asyncio.gather(provider.translate('one', 'ja'), provider.translate('two', 'ja'))
        assert maximum == 1 and starts[1] - starts[0] >= .025
        assert provider.rate_failures == 0
        assert GoogleWebTranslator(client).interval == 1


def test_api_google_no_keys_languages_test_and_shared_cooldown(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'config.json')
    calls = []
    async def respond(url, **kwargs):
        calls.append(kwargs['params'])
        return httpx.Response(429)
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.hub.google.client, 'get', respond)
        assert client.get('/api/config').json()['translation_provider'] == 'google_web'
        assert len(client.get('/api/languages').json()['languages']) == 8
        assert client.get('/api/languages?provider=invalid').status_code == 422
        assert client.put('/api/config', json={'translation_provider': 'invalid'}).status_code == 422
        assert client.put('/api/config', json={'translation_provider': 'google_web', 'target_language': 'it'}).json()['target_language'] == 'zh-Hans'
        result = client.post('/api/translation/test')
        assert result.status_code == 503 and result.json()['code'] == 'rate_limited'
        assert client.post('/api/translation/test').json()['code'] == 'cooldown'
        client.put('/api/config', json={'target_language': 'ja'})
        client.post('/api/translation/resume')
        assert client.post('/api/translation/test').json()['code'] == 'cooldown'
        assert len(calls) == 1
        client.put('/api/config', json={'translation_provider': 'azure'})
        assert client.post('/api/translation/test').json()['code'] == 'missing_credentials'


def test_api_success_and_english_test_uses_foreign_sample(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'config.json')
    async def respond(url, **kwargs):
        assert kwargs['params']['q'].startswith('你好')
        return httpx.Response(200, json=payload('Hello, welcome!', 'zh-CN'))
    with TestClient(app) as client:
        assert isinstance(app.state.hub.google.client, AsyncSession)
        assert app.state.hub.google.client is not app.state.client
        monkeypatch.setattr(app.state.hub.google.client, 'get', respond)
        client.put('/api/config', json={'target_language': 'en'})
        result = client.post('/api/translation/test')
        assert result.status_code == 200
        assert result.json()['translation'] == 'Hello, welcome!'
        assert result.json()['source_language'] == 'zh-Hans'


async def test_libcurl_network_error_keeps_worker_alive_and_hides_request_details(monkeypatch):
    async with AsyncSession() as client:
        async def unavailable(*args, **kwargs):
            raise RequestException('PRIVATE URL AND MESSAGE')
        monkeypatch.setattr(client, 'get', unavailable)
        provider = GoogleWebTranslator(client)
        provider.interval = 0
        with pytest.raises(TranslationError) as error:
            await provider.translate('Hello', 'ja')
        assert error.value.code == 'unavailable'
        assert 'PRIVATE' not in str(error.value)
        results = []
        pool = TranslationPool(provider, 'ja', lambda *args: results.append(args), lambda *args: None, concurrency=1)
        pool.start()
        try:
            pool.submit('one', 'hello')
            await asyncio.wait_for(pool.queue.join(), 1)
            assert results == [('one', None, 'failed')]
            assert not pool.workers[0].done() and not provider.paused
        finally:
            await pool.close()


async def test_diagnostic_and_live_chat_share_guard_and_provider_switch_cancels_old_jobs():
    started, release = asyncio.Event(), asyncio.Event()
    async def respond(request):
        if request.url.host == 'translate.googleapis.com':
            started.set()
            await release.wait()
            return httpx.Response(200, json=payload('旧译文'))
        return httpx.Response(200, json=[{'detectedLanguage': {'language': 'en'}, 'translations': [{'text': '新译文'}]}])
    class Source:
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, *args):
            yield Batch([item()], 'token')
            await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        config = Config(source='CHAT', youtube_key='YT', translation_enabled=True)
        hub = ChatHub(config, Source(), client)
        await hub.connect()
        try:
            await asyncio.wait_for(started.wait(), 1)
            stream = hub.task
            with pytest.raises(TranslationError) as error:
                await hub.test_translation()
            assert error.value.code == 'busy'
            await hub.configure(config.model_copy(update={'translation_provider': 'azure', 'azure_key': 'KEY', 'azure_region': 'eastasia'}))
            release.set()
            await asyncio.wait_for(hub.pool.queue.join(), 1)
            assert hub.messages['one']['translation'] == '新译文'
            assert hub.task is stream
        finally:
            await hub.disconnect()


async def test_configuration_change_cancels_diagnostic():
    started = asyncio.Event()
    async def respond(request):
        started.set()
        await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        hub = ChatHub(Config(), None, client)
        test = asyncio.create_task(hub.test_translation())
        await asyncio.wait_for(started.wait(), 1)
        await hub.configure(Config(target_language='ja'))
        with pytest.raises(TranslationError) as error:
            await test
        assert error.value.code == 'stale'
        assert not hub.google.lock.locked()


async def test_resume_restores_unfinished_messages_without_duplicate_or_stale_updates():
    started, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def respond(request):
        text = request.url.params['q']
        calls.append(text)
        if text != 'first':
            started.set()
            await release.wait()
        return httpx.Response(200, json=payload('訳文 ' + text, 'en'))
    class Source:
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, *args):
            for mid, text in [('one', 'first'), ('two', 'second'), ('three', 'third'), ('four', 'third'), ('deleted', 'deleted')]:
                value = item()
                value['id'] = mid
                value['snippet']['textMessageDetails']['messageText'] = text
                yield Batch([value], 'token')
            await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        hub = ChatHub(Config(source='CHAT', youtube_key='YT', translation_enabled=True, target_language='ja'), Source(), client)
        hub.google.interval = 0
        await hub.connect()
        try:
            await asyncio.wait_for(started.wait(), 1)
            assert hub.messages['one']['translation'] == '訳文 first'
            hub.delete(['deleted'])
            await hub.resume_translation()
            assert hub.current_status()['translation_counts']['pending'] == 3
            release.set()
            await asyncio.wait_for(hub.pool.queue.join(), 1)
            assert [hub.messages[mid]['translation'] for mid in ('one', 'two', 'three', 'four')] == ['訳文 first', '訳文 second', '訳文 third', '訳文 third']
            assert calls.count('first') == 1 and calls.count('third') == 1 and 'deleted' not in calls
            assert hub.current_status()['translation_counts'] == {'pending': 0, 'complete': 4, 'failed': 0, 'skipped': 0}
        finally:
            await hub.stop()
