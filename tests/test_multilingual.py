import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Config, ConfigStore
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
    assert Config(target_languages=[]).target_languages == []
    for value in [['bad_language'], ['en'] * 9]:
        with pytest.raises(ValidationError):
            Config(target_languages=value)


def test_api_persists_order_and_supports_old_single_target_clients(tmp_path):
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        saved = client.put('/api/config', json={'target_languages': ['en', 'zh-Hans']}).json()
        assert saved['target_languages'] == ['en', 'zh-Hans'] and saved['target_language'] == 'en'
        assert 'youtube_provider' not in saved and 'youtube_key' not in saved
        saved = client.put('/api/config', json={'target_languages': []}).json()
        assert saved['target_languages'] == []
        saved = client.put('/api/config', json={'target_language': 'ja'}).json()
        assert saved['target_languages'] == ['ja']
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        assert client.get('/api/config').json()['target_languages'] == ['ja']


def test_empty_targets_survive_save_restart_and_unrelated_updates(tmp_path):
    path = tmp_path / 'config.json'
    store = ConfigStore(path)
    store.save(Config(translation_enabled=True, target_languages=[]))
    assert ConfigStore(path).config.target_languages == []
    app = create_app(path)
    with TestClient(app) as client:
        assert client.get('/api/config').json()['target_languages'] == []
        assert client.put('/api/config', json={'translation_enabled': True}).json()['target_languages'] == []
        assert client.put('/api/config', json={'style': {'font_size': 36}}).json()['target_languages'] == []
    assert ConfigStore(path).config.target_languages == []


def test_no_target_diagnostic_and_resume_never_send_translation_requests(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'config.json')
    async def unexpected(*args, **kwargs):
        raise AssertionError('No language was selected')
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.hub.google.client, 'get', unexpected)
        assert client.put('/api/config', json={'target_languages': [], 'translation_enabled': True}).status_code == 200
        result = client.post('/api/translation/test')
        assert result.status_code == 422 and result.json()['code'] == 'no_targets'
        assert '仅显示原文' in result.json()['detail']
        resumed = client.post('/api/translation/resume').json()
        assert resumed['translation'] == 'off'
        assert app.state.hub.pool is None


@pytest.mark.parametrize('mode', ['live', 'demo'])
async def test_empty_targets_keep_original_without_pool_or_placeholder_rows(mode):
    hub = ChatHub(Config(target_languages=[], translation_enabled=True), None, None)
    hub.mode = mode
    hub.provider = lambda: pytest.fail('No translation provider should be used')
    await hub.setup_translation()
    try:
        hub.add(message('demo-0'))
        if mode == 'demo':
            hub.translate_demo('demo-0')
        original = hub.snapshot()['messages'][0]
        assert original['original'] == '你好'
        assert original['translations'] == [] and original['translation'] == ''
        assert original['translation_status'] == 'skipped'
        assert hub.pool is None and hub.status['translation'] == 'off'
    finally:
        await hub.stop()


async def test_removing_all_targets_cancels_pending_work_and_readding_resumes_without_reconnect():
    started = asyncio.Event()
    waiting = True
    calls = []
    class Provider:
        async def translate(self, text, target):
            calls.append((text, target))
            started.set()
            if waiting:
                await asyncio.Event().wait()
            return Result('translated', 'zh-Hans')
    hub = ChatHub(Config(translation_enabled=True), None, None)
    hub.provider = lambda: Provider()
    hub.mode = 'live'
    hub.task = asyncio.create_task(asyncio.Event().wait())
    task, session = hub.task, hub.session
    await hub.setup_translation()
    try:
        hub.add(message())
        await asyncio.wait_for(started.wait(), 1)
        await hub.configure(Config(translation_enabled=True, target_languages=[]))
        hub.translated('one', Result('stale', 'en'), 'complete', 'zh-Hans')
        hub.add(message('two', '欢迎'))
        assert len(calls) == 1 and hub.pool is None
        assert all(m['translations'] == [] and m['translation'] == '' for m in hub.messages.values())
        assert hub.task is task and hub.session == session
        waiting = False
        await hub.configure(Config(translation_enabled=True, target_languages=['en']))
        await asyncio.wait_for(hub.pool.queue.join(), 1)
        assert calls == [('你好', 'zh-Hans'), ('你好', 'en'), ('欢迎', 'en')]
        assert all(m['translations'][0]['text'] == 'translated' for m in hub.messages.values())
        assert hub.task is task and hub.session == session
    finally:
        await hub.stop()


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


async def test_demo_covers_all_google_languages_for_every_sample_without_network():
    from app.config import GOOGLE_LANGUAGES
    from app.hub import DEMO_SAMPLES
    targets = [item['code'] for item in GOOGLE_LANGUAGES]
    hub = ChatHub(Config(target_languages=targets), None, None)
    hub.mode = 'demo'
    for index, sample in enumerate(DEMO_SAMPLES):
        mid = f'demo-{index}'
        hub.add(message(mid, sample[1]))
        hub.translate_demo(mid)
        rows = hub.messages[mid]['translations']
        assert [row['language'] for row in rows] == targets
        assert all(row['status'] == 'complete' and row['text'] for row in rows), rows
    assert hub.pool is None


async def test_live_google_pool_translates_every_selected_language():
    from app.config import GOOGLE_LANGUAGES
    targets = [item['code'] for item in GOOGLE_LANGUAGES]
    calls = []
    async def respond(request):
        code = request.url.params['tl']
        calls.append(code)
        return httpx.Response(200, json=[[[f'translated-{code}']], None, 'zh-CN'])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        hub = ChatHub(Config(translation_enabled=True, target_languages=targets), None, client)
        hub.mode = 'live'
        hub.google.interval = 0
        await hub.setup_translation()
        try:
            hub.add(message())
            await asyncio.wait_for(hub.pool.queue.join(), 1)
            rows = hub.messages['one']['translations']
            assert [row['language'] for row in rows] == targets
            assert all(row['status'] == 'complete' and row['text'] for row in rows)
            assert calls == ['zh-CN', 'zh-TW', 'en', 'ja', 'ko', 'es', 'fr', 'de']
        finally:
            await hub.stop()


async def test_demo_language_added_during_session_has_offline_translation():
    hub = ChatHub(Config(target_languages=['zh-Hans']), None, None)
    await hub.connect(demo=True)
    try:
        await asyncio.sleep(.8)
        await hub.configure(Config(target_languages=['ja', 'fr', 'zh-Hans']))
        rows = hub.messages['demo-0']['translations']
        assert [row['language'] for row in rows] == ['ja', 'fr', 'zh-Hans']
        assert all(row['status'] == 'complete' and row['text'] for row in rows)
        assert rows[0]['text'] == hub.messages['demo-0']['original']
        assert rows[1]['text'].startswith('Bonjour')
    finally:
        await hub.stop()
