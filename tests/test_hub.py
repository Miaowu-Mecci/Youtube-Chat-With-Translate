import asyncio

import httpx

from app.config import Config
from app.hub import ChatHub
from app.translation import Result
from app.youtube import Batch, SourceError


def item(mid='one', author='author'):
    return {'id': mid, 'snippet': {'type': 'textMessageEvent', 'publishedAt': '2026-10-09T00:00:00Z',
                                  'textMessageDetails': {'messageText': 'hello'}},
            'authorDetails': {'channelId': author, 'displayName': 'Alice'}}


async def test_multiple_clients_share_stream_and_resume_token(monkeypatch):
    started = asyncio.Event()
    class Source:
        calls = []
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, chat, key, token):
            self.calls.append(token)
            yield Batch([item()], 'next-token')
            if len(self.calls) == 1:
                raise SourceError('network', 'retry', True)
            started.set()
            await asyncio.Event().wait()
    source = Source()
    hub = ChatHub(Config(source='CHAT', youtube_key='SECRET'), source, None)
    q1, q2 = hub.subscribe(), hub.subscribe()
    await asyncio.gather(hub.connect(), hub.connect())
    await asyncio.wait_for(started.wait(), 3)
    assert source.calls == ['', 'next-token']
    assert len(hub.messages) == 1
    assert len(hub.clients) == 2
    for queue in [q1, q2]:
        events = []
        while not queue.empty(): events.append(queue.get_nowait())
        assert len([event for event in events if event['type'] == 'message']) == 1
    await hub.disconnect()


async def test_delete_ban_and_late_translation_do_not_resurrect():
    hub = ChatHub(Config(), None, None)
    queue = hub.subscribe()
    hub.consume(item('one'))
    hub.consume(item('two'))
    hub.consume({'id': 'ban', 'snippet': {'type': 'userBannedEvent',
                                         'userBannedDetails': {'bannedUserDetails': {'channelId': 'author'}}}})
    assert not hub.messages
    hub.translated('one', Result('你好', 'en'), 'complete')
    hub.consume(item('one'))
    assert not hub.messages
    hub.consume({'id': 'future', 'snippet': {'type': 'tombstone'}})
    hub.consume(item('future'))
    assert not hub.messages
    assert not any(event['type'] == 'translation' for event in list(queue._queue))


async def test_language_change_cancels_old_jobs_and_keeps_one_stream():
    request_started = asyncio.Event()
    release = asyncio.Event()
    calls = []
    async def response(request):
        target = request.url.params['to']
        calls.append(target)
        if target == 'ja':
            request_started.set()
            await release.wait()
        return httpx.Response(200, json=[{'detectedLanguage': {'language': 'en'}, 'translations': [{'text': target}]}])
    class Source:
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, *args):
            yield Batch([item()], 'token')
            await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        config = Config(source='CHAT', youtube_key='SECRET', translation_enabled=True, azure_key='SECRET', azure_region='eastasia', target_language='ja')
        hub = ChatHub(config, Source(), client)
        await hub.connect()
        await asyncio.wait_for(request_started.wait(), 1)
        source_task = hub.task
        await hub.configure(config.model_copy(update={'target_language': 'zh-Hans'}))
        release.set()
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert hub.messages['one']['translation'] == 'zh-Hans'
        assert hub.task is source_task
        assert calls == ['ja', 'zh-Hans']
        await hub.disconnect()


async def test_same_language_and_text_are_not_duplicated():
    hub = ChatHub(Config(target_language='en'), None, None)
    hub.consume(item())
    hub.translated('one', Result('hello differently', 'en'), 'complete')
    assert hub.messages['one']['translation'] == ''
    hub.translated('one', Result('hello', 'fr'), 'complete')
    assert hub.messages['one']['translation'] == ''


async def test_terminal_quota_error_stops_retrying():
    class Source:
        calls = 0
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, *args):
            self.calls += 1
            raise SourceError('quota_exhausted', '额度用完')
            yield
    source = Source()
    hub = ChatHub(Config(source='CHAT', youtube_key='SECRET'), source, None)
    await hub.connect()
    await asyncio.wait_for(hub.task, 1)
    assert source.calls == 1 and hub.status['code'] == 'quota_exhausted'
    await hub.disconnect()


async def test_demo_needs_no_credentials_and_publishes_bilingual():
    hub = ChatHub(Config(), None, None)
    await hub.connect(demo=True)
    await asyncio.sleep(.8)
    assert hub.messages['demo-0']['translation']
    assert hub.status['connection'] == 'demo'
    await hub.disconnect()


async def test_history_and_slow_client_are_bounded():
    hub = ChatHub(Config(), None, None)
    queue = hub.subscribe()
    for index in range(1200): hub.consume(item(str(index)))
    assert len(hub.messages) == 100
    assert queue.qsize() <= 1000
    assert any(event['type'] == 'snapshot' for event in list(queue._queue))


async def test_source_change_clears_messages_and_stops_old_session():
    class Source:
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, *args):
            yield Batch([item()], 'token')
            await asyncio.Event().wait()
    config = Config(source='CHAT', youtube_key='SECRET')
    hub = ChatHub(config, Source(), None)
    await hub.connect()
    await asyncio.sleep(.01)
    old_session = hub.session
    await hub.configure(config.model_copy(update={'source': 'OTHER_CHAT'}))
    assert not hub.messages and hub.task is None
    assert hub.mode == 'idle' and old_session != hub.session


async def test_style_save_does_not_restart_connection():
    class Source:
        calls = 0
        async def resolve(self, *args): return 'CHAT'
        async def stream(self, *args):
            self.calls += 1
            yield Batch([item()], 'token')
            await asyncio.Event().wait()
    config = Config(source='CHAT', youtube_key='SECRET')
    source = Source()
    hub = ChatHub(config, source, None)
    await hub.connect()
    await asyncio.sleep(.01)
    original_task = hub.task
    await hub.configure(config.model_copy(update={'style': config.style.model_copy(update={'font_size': 30})}))
    assert hub.task is original_task and source.calls == 1
    assert len(hub.messages) == 1
    await hub.disconnect()


async def test_cached_translation_is_published_after_original():
    class Pool:
        def submit(self, mid, text):
            hub.translated(mid, Result('你好', 'en'), 'complete')
            return 'complete'
    hub = ChatHub(Config(), None, None)
    hub.pool = Pool()
    queue = hub.subscribe()
    hub.consume(item())
    events = list(queue._queue)
    assert events[1]['type'] == 'message'
    assert events[1]['message']['translation'] == ''
    assert events[2]['type'] == 'translation'
    assert hub.messages['one']['translation'] == '你好'
