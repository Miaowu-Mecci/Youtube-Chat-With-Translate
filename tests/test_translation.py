import asyncio

import httpx
import pytest

from app.translation import AzureTranslator, Result, TranslationError, TranslationPool, should_translate


@pytest.mark.parametrize('text', ['', '  ', '🌸👍🏽 👨‍👩‍👧‍👦', '1234', 'https://example.com', 'www.example.com'])
def test_skip_nonlinguistic_text(text):
    assert not should_translate(text)


@pytest.mark.parametrize('text', ['こんにちは！', 'Hello 🌸', '你好123', 'Привет', 'مرحبا', 'hello https://example.com'])
def test_translate_unicode_letters(text):
    assert should_translate(text)


async def test_azure_request_autodetect_and_language():
    def respond(request):
        assert 'from' not in request.url.params
        assert request.url.params['to'] == 'zh-Hans'
        assert request.headers['Ocp-Apim-Subscription-Key'] == 'SECRET'
        return httpx.Response(200, json=[{'detectedLanguage': {'language': 'en'}, 'translations': [{'text': '你好'}]}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await AzureTranslator(client, 'SECRET', 'eastasia').translate('hello', 'zh-Hans') == Result('你好', 'en')


@pytest.mark.parametrize('code,expected', [(401, 'credentials_or_quota'), (403, 'credentials_or_quota'), (429, 'rate_limited'), (503, 'unavailable')])
async def test_azure_error_mapping(code, expected):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(code, text='SECRET'))) as client:
        with pytest.raises(TranslationError) as error:
            await AzureTranslator(client, 'SECRET', 'eastasia').translate('hello', 'zh-Hans')
        assert error.value.code == expected
        assert 'SECRET' not in str(error.value)


async def test_coalescing_cache_and_queue_bound():
    release = asyncio.Event()
    calls, results = [], []
    class Provider:
        async def translate(self, text, target):
            calls.append(text)
            await release.wait()
            return Result('译文', 'en')
    pool = TranslationPool(Provider(), 'zh-Hans', lambda *result: results.append(result), lambda *state: None, concurrency=1, capacity=1)
    pool.start()
    try:
        assert pool.submit('one', 'hello') == 'pending'
        assert pool.submit('two', 'hello') == 'pending'
        assert pool.submit('three', 'other') == 'skipped'
        release.set()
        await asyncio.wait_for(pool.queue.join(), 1)
        assert calls == ['hello']
        assert [result[0] for result in results] == ['one', 'two']
        assert pool.submit('four', 'hello') == 'complete'
        assert calls == ['hello']
    finally:
        await pool.close()


async def test_timeout_retains_original_and_pool_stays_alive():
    results, states = [], []
    class Provider:
        async def translate(self, text, target):
            await asyncio.sleep(1)
    pool = TranslationPool(Provider(), 'ja', lambda *args: results.append(args), lambda *args: states.append(args), timeout=.01)
    pool.start()
    try:
        pool.submit('one', 'hello')
        await asyncio.wait_for(pool.queue.join(), 1)
        assert results == [('one', None, 'failed')]
        assert states[-1][0] == 'degraded'
    finally:
        await pool.close()


async def test_quota_failure_pauses_and_drains_without_more_calls():
    calls, states = [], []
    class Provider:
        async def translate(self, text, target):
            calls.append(text)
            raise TranslationError('credentials_or_quota')
    pool = TranslationPool(Provider(), 'ja', lambda *args: None, lambda *args: states.append(args), concurrency=1)
    pool.start()
    try:
        pool.submit('one', 'hello')
        pool.submit('two', 'world')
        await asyncio.wait_for(pool.queue.join(), 1)
        assert pool.paused and calls == ['hello']
        assert pool.submit('three', 'new') == 'skipped'
        assert states[-1][0] == 'paused'
    finally:
        await pool.close()


async def test_rate_limit_cooldown():
    class Provider:
        async def translate(self, text, target): raise TranslationError('rate_limited')
    states = []
    pool = TranslationPool(Provider(), 'ja', lambda *args: None, lambda *args: states.append(args))
    pool.start()
    try:
        pool.submit('one', 'hello')
        await asyncio.wait_for(pool.queue.join(), 1)
        assert states[-1][0] == 'rate_limited'
        assert pool.cooldown_until > 0 and not pool.paused
    finally:
        await pool.close()


async def test_close_cancels_inflight_and_suppresses_old_callbacks():
    started = asyncio.Event()
    results = []
    class Provider:
        async def translate(self, text, target):
            started.set()
            await asyncio.sleep(100)
    pool = TranslationPool(Provider(), 'ja', lambda *args: results.append(args), lambda *args: None)
    pool.start()
    pool.submit('one', 'hello')
    await started.wait()
    await pool.close()
    assert not results and not pool.workers and not pool.pending


@pytest.mark.parametrize('payload', [[], [{'detectedLanguage': None, 'translations': [{'text': 'hi'}]}],
                                    [{'translations': [{'text': 123}]}], {'error': 'unexpected'}])
async def test_malformed_provider_response_is_a_controlled_failure(payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        with pytest.raises(TranslationError) as error:
            await AzureTranslator(client, 'SECRET', 'eastasia').translate('hello', 'ja')
        assert error.value.code == 'unavailable'


async def test_other_workers_cannot_overwrite_a_paused_quota_state():
    first_failed = asyncio.Event()
    states = []
    class Provider:
        async def translate(self, text, target):
            if text == 'quota':
                first_failed.set()
                raise TranslationError('credentials_or_quota')
            await first_failed.wait()
            await asyncio.sleep(.01)
            raise TranslationError('unavailable')
    pool = TranslationPool(Provider(), 'ja', lambda *args: None, lambda *args: states.append(args), concurrency=2)
    pool.start()
    try:
        pool.submit('one', 'quota')
        pool.submit('two', 'network')
        await asyncio.wait_for(pool.queue.join(), 1)
        assert pool.paused
        assert states[-1][0] == 'paused'
    finally:
        await pool.close()


async def test_obsolete_queued_jobs_do_not_block_current_messages():
    current, calls = {'old-1', 'old-2'}, []
    class Provider:
        async def translate(self, text, target):
            calls.append(text)
            return Result('译文 ' + text, 'en')
    pool = TranslationPool(Provider(), 'ja', lambda *args: None, lambda *args: None, concurrency=1, capacity=2, is_current=lambda mid: mid in current)
    pool.submit('old-1', 'old one')
    pool.submit('old-2', 'old two')
    current.clear()
    current.add('new')
    assert pool.submit('new', 'new message') == 'pending'
    pool.start()
    try:
        await asyncio.wait_for(pool.queue.join(), 1)
        assert calls == ['new message'] and not pool.pending
    finally:
        await pool.close()


async def test_unexpected_worker_error_is_visible_and_does_not_silently_kill_worker():
    states = []
    class Provider:
        async def translate(self, text, target): raise RuntimeError('PRIVATE')
    pool = TranslationPool(Provider(), 'ja', lambda *args: None, lambda *args: states.append(args), concurrency=1)
    pool.start()
    try:
        pool.submit('one', 'hello')
        await asyncio.wait_for(pool.queue.join(), 1)
        assert pool.paused and not pool.workers[0].done()
        assert states[-1][0] == 'paused' and 'PRIVATE' not in str(states)
    finally:
        await pool.close()
