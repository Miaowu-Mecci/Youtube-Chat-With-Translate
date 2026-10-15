import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Config
from app.hub import ChatHub
from app.server import create_app
from app.translation import Result, TranslationError, TranslationPool


def message(mid='one', original='你好'):
    return {'id': mid, 'author_id': 'alice', 'author': 'Alice', 'original': original, 'translation': '',
            'source_language': '', 'translation_status': 'skipped', 'time': '', 'avatar': '', 'role': 'normal'}


def test_target_config_order_duplicates_migration_and_validation():
    assert Config(target_languages=['en', 'zh-Hans', 'en']).target_languages == ['en', 'zh-Hans']
    assert Config(target_languages=['en', 'zh-Hans']).target_language == 'en'
    assert Config(target_language='ja').target_languages == ['ja']
    for value in [[], ['bad_language'], ['en'] * 9]:
        with pytest.raises(ValidationError):
            Config(target_languages=value)


def test_api_persists_order_and_supports_old_single_target_clients(tmp_path):
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        saved = client.put('/api/config', json={'target_languages': ['en', 'zh-Hans']}).json()
        assert saved['target_languages'] == ['en', 'zh-Hans'] and saved['target_language'] == 'en'
        assert saved['youtube_provider'] == 'web' and not saved['youtube_key_set']
        assert client.put('/api/config', json={'target_languages': []}).status_code == 422
        saved = client.put('/api/config', json={'target_language': 'ja'}).json()
        assert saved['target_languages'] == ['ja']
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        assert client.get('/api/config').json()['target_languages'] == ['ja']


async def test_same_language_kept_and_out_of_order_results_follow_selection():
    hub = ChatHub(Config(target_languages=['zh-Hans', 'en']), None, None)
    hub.mode = 'demo'
    hub.add(message())
    hub.translated('one', Result('Hello', 'zh-Hans'), 'complete', 'en')
    assert hub.messages['one']['translation_status'] == 'pending'
    hub.translated('one', Result('你好', 'zh-Hans'), 'complete', 'zh-Hans')
    rows = hub.messages['one']['translations']
    assert [(r['language'], r['text']) for r in rows] == [('zh-Hans', '你好'), ('en', 'Hello')]
    assert hub.messages['one']['translation_status'] == 'complete'
    hub.delete(['one'])
    hub.translated('one', Result('late', 'en'), 'complete', 'zh-Hans')
    assert not hub.messages


async def test_pool_cache_is_scoped_to_language_and_duplicates_coalesce():
    calls, results = [], []
    class Provider:
        async def translate(self, text, target):
            calls.append((target, text))
            return Result('你好' if target == 'zh-Hans' else 'Hello', 'zh-Hans')
    pool = TranslationPool(Provider(), ['zh-Hans', 'en'], lambda *args: results.append(args), lambda *args: None, concurrency=1)
    pool.submit('one', '你好')
    pool.submit('two', '你好')
    pool.start()
    try:
        await asyncio.wait_for(pool.queue.join(), 1)
        assert calls == [('zh-Hans', '你好'), ('en', '你好')]
        assert pool.submit('three', '你好') == 'complete'
        assert [(r[3], r[1].text) for r in results if r[0] == 'three'] == [('zh-Hans', '你好'), ('en', 'Hello')]
    finally:
        await pool.close()


async def test_partial_failure_preserves_other_results_and_resume_retries_only_failed():
    class Provider:
        calls = []
        fail = True
        async def translate(self, text, target):
            self.calls.append(target)
            if target == 'en' and self.fail:
                raise TranslationError('unavailable')
            return Result('你好' if target == 'zh-Hans' else 'Hello', 'zh-Hans')
    provider = Provider()
    hub = ChatHub(Config(target_languages=['zh-Hans', 'en'], translation_enabled=True), None, None)
    hub.provider = lambda: provider
    hub.mode = 'live'
    hub.task = asyncio.create_task(asyncio.Event().wait())
    await hub.setup_translation()
    hub.add(message())
    try:
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert [r['status'] for r in hub.messages['one']['translations']] == ['complete', 'failed']
        provider.fail = False
        await hub.resume_translation()
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert provider.calls == ['zh-Hans', 'en', 'en']
        assert hub.messages['one']['translation_status'] == 'complete'
        assert [r['text'] for r in hub.messages['one']['translations']] == ['你好', 'Hello']
    finally:
        await hub.stop()


async def test_reordering_keeps_pool_connection_and_completed_translations():
    config = Config(target_languages=['zh-Hans', 'en'], translation_enabled=True)
    hub = ChatHub(config, None, None)
    hub.mode = 'live'
    hub.add(message())
    hub.messages['one']['translations'] = hub.translation_rows()
    hub.translated('one', Result('你好', 'zh-Hans'), 'complete', 'zh-Hans')
    hub.translated('one', Result('Hello', 'zh-Hans'), 'complete', 'en')
    class Pool:
        target = ['zh-Hans', 'en']
    hub.pool = Pool()
    pool = hub.pool
    await hub.configure(Config(target_languages=['en', 'zh-Hans'], translation_enabled=True))
    assert hub.pool is pool and hub.pool.target == ['en', 'zh-Hans']
    assert [(r['language'], r['text']) for r in hub.messages['one']['translations']] == [('en', 'Hello'), ('zh-Hans', '你好')]
    assert hub.messages['one']['translation_status'] == 'complete'


async def test_multilingual_diagnostic_exercises_every_selected_target():
    calls = []
    async def respond(request):
        target = request.url.params['tl']
        calls.append(target)
        return httpx.Response(200, json=[[[target]], None, 'en'])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        hub = ChatHub(Config(target_languages=['zh-Hans', 'en']), None, client)
        hub.google.interval = 0
        result = await hub.test_translation()
        assert calls == ['zh-CN', 'en']
        assert [r['language'] for r in result['translations']] == ['zh-Hans', 'en']


async def test_demo_language_change_updates_retained_rows():
    hub = ChatHub(Config(target_languages=['zh-Hans']), None, None)
    await hub.connect(demo=True)
    try:
        await asyncio.sleep(.8)
        await hub.configure(Config(target_languages=['zh-Hans', 'en']))
        assert [row['status'] for row in hub.messages['demo-0']['translations']] == ['complete', 'complete']
        assert hub.messages['demo-0']['translations'][1]['text'].startswith('Hello!')
    finally:
        await hub.stop()


async def test_disabling_translation_removes_waiting_rows():
    hub = ChatHub(Config(target_languages=['zh-Hans', 'en'], translation_enabled=True), None, None)
    hub.mode = 'live'
    await hub.setup_translation()
    hub.add(message())
    await hub.configure(Config(target_languages=['zh-Hans', 'en'], translation_enabled=False))
    assert hub.messages['one']['translations'] == []
    assert hub.messages['one']['translation_status'] == 'skipped'
    assert hub.pool is None
    await hub.stop()
