import asyncio
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

import httpx
from curl_cffi.requests.exceptions import RequestException


class TranslationError(Exception):
    def __init__(self, code: str):
        self.code = code


@dataclass
class Result:
    text: str
    language: str


def should_translate(text: str) -> bool:
    # Unicode symbols, emoji, variation selectors and numbers alone need no API call.
    words = " ".join(part for part in text.split() if not part.lower().startswith(("https://", "http://", "www.")))
    return any(unicodedata.category(char).startswith("L") for char in words)


class AzureTranslator:
    def __init__(self, client: httpx.AsyncClient, key: str, region: str):
        self.client, self.key, self.region = client, key, region

    async def translate(self, text: str, target: str) -> Result:
        try:
            response = await self.client.post(
                "https://api.cognitive.microsofttranslator.com/translate",
                params={"api-version": "3.0", "to": target},
                headers={"Ocp-Apim-Subscription-Key": self.key, "Ocp-Apim-Subscription-Region": self.region},
                json=[{"Text": text}], timeout=5,
            )
        except httpx.HTTPError:
            raise TranslationError("unavailable") from None
        if response.status_code in {401, 403}:
            # Azure 403 covers authorization and quota failures. Do not expose raw responses.
            raise TranslationError("credentials_or_quota")
        if response.status_code == 429:
            raise TranslationError("rate_limited")
        if response.status_code >= 400:
            raise TranslationError("unavailable")
        try:
            data = response.json()[0]
            text = data["translations"][0]["text"]
            language = data.get("detectedLanguage", {}).get("language", "")
            if not isinstance(text, str) or not isinstance(language, str):
                raise ValueError()
            return Result(text, language)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise TranslationError("unavailable") from None


GOOGLE_CODES = {"zh-Hans": "zh-CN", "zh-Hant": "zh-TW", "en": "en", "ja": "ja",
                "ko": "ko", "es": "es", "fr": "fr", "de": "de"}


def normalize_google_language(language: str) -> str:
    return {"zh-cn": "zh-Hans", "zh-tw": "zh-Hant"}.get(language.lower(), language.lower())


class GoogleWebTranslator:
    """Experimental web endpoint. One shared guard for chat and diagnostic requests."""

    def __init__(self, client, on_state=lambda *args: None):
        self.client, self.on_state = client, on_state
        self.lock = asyncio.Lock()
        self.interval = 1.0
        self.backoff = 60.0
        self.last_request = float("-inf")
        self.cooldown_until = 0.0
        self.rate_failures = 0
        self.paused = False
        self.pause_message = ""

    def resume(self):
        self.paused = False
        self.rate_failures = 0
        # Manual resume cannot evade a cooldown already imposed by the server.
        self.on_state("active", "Google 网页翻译已恢复；仍遵守请求间隔和限流等待。")

    async def wait_ready(self):
        if self.paused:
            return
        await asyncio.sleep(max(0, self.cooldown_until - time.monotonic(),
                                self.last_request + self.interval - time.monotonic()))

    def report_error(self, code):
        if code == "paused":
            self.on_state("paused", self.pause_message)
        elif code == "rate_limited":
            self.rate_failures += 1
            self.cooldown_until = time.monotonic() + self.backoff
            if self.rate_failures >= 3:
                self.paused = True
                self.pause_message = "Google 连续三次限流，翻译已暂停；请稍后点击「恢复翻译」。"
                self.on_state("paused", self.pause_message)
            else:
                self.on_state("rate_limited", "Google 网页翻译限流，暂停新请求 60 秒；失败消息保留原文。")
        elif code in {"blocked", "invalid_response"}:
            self.rate_failures = 0
            self.paused = True
            self.pause_message = ("Google 拒绝访问或要求验证码，翻译已暂停。请检查网络后恢复翻译。"
                                  if code == "blocked" else
                                  "Google 网页翻译接口响应格式已变化，翻译已暂停；请等待适配更新或切换 Azure。")
            self.on_state("paused", self.pause_message)
        elif code == "cooldown":
            self.on_state("rate_limited", "Google 正在限流等待中，请稍后测试；当前保留原文。")
        elif code != "busy":
            self.rate_failures = 0
            self.on_state("degraded", "Google 翻译超时或暂不可用，保留原文。")

    async def translate(self, text: str, target: str) -> Result:
        async with self.lock:
            if self.paused:
                raise TranslationError("paused")
            if time.monotonic() < self.cooldown_until:
                raise TranslationError("cooldown")
            await asyncio.sleep(max(0, self.last_request + self.interval - time.monotonic()))
            self.last_request = time.monotonic()
            try:
                response = await asyncio.wait_for(self.client.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params={"client": "gtx", "sl": "auto", "tl": GOOGLE_CODES[target],
                            "dt": "t", "q": text}, timeout=5,
                ), 5)
            except (httpx.HTTPError, RequestException, TimeoutError):
                raise TranslationError("unavailable") from None
            if response.status_code == 429:
                raise TranslationError("rate_limited")
            if response.status_code in {401, 403}:
                raise TranslationError("blocked")
            if response.status_code >= 400:
                raise TranslationError("unavailable")
            if "text/html" in response.headers.get("content-type", "").lower() or response.text.lstrip().lower().startswith(("<!doctype html", "<html")):
                raise TranslationError("blocked")
            try:
                data = response.json()
                if not isinstance(data, list) or len(data) < 3 or not isinstance(data[0], list) or not data[0]:
                    raise ValueError()
                segments = []
                for segment in data[0]:
                    if not isinstance(segment, list) or not segment or not isinstance(segment[0], str):
                        raise ValueError()
                    segments.append(segment[0])
                language = data[2]
                translated = "".join(segments)
                if not isinstance(language, str) or not language or not translated.strip():
                    raise ValueError()
            except (ValueError, TypeError, IndexError):
                raise TranslationError("invalid_response") from None
            self.rate_failures = 0
            self.on_state("active", "Google 网页翻译运行中（实验性）。")
            return Result(translated, normalize_google_language(language))


class TranslationPool:
    """Bounded jobs, coalesced duplicate requests, and an in-memory LRU cache."""

    def __init__(self, provider, target: str, on_result: Callable, on_state: Callable,
                 concurrency: int = 4, capacity: int = 200, timeout: float = 5,
                 is_current: Callable = lambda mid: True):
        self.provider, self.target = provider, target
        self.on_result, self.on_state = on_result, on_state
        self.queue = asyncio.Queue(maxsize=capacity)
        self.pending: dict[str, list[str]] = {}
        self.cache: OrderedDict[str, Result] = OrderedDict()
        self.workers = []
        self.concurrency, self.timeout = concurrency, timeout
        self.paused = False
        self.cooldown_until = 0.0
        self.closed = False
        self.is_current = is_current

    def discard_stale_jobs(self):
        for _ in range(self.queue.qsize()):
            text = self.queue.get_nowait()
            ids = [mid for mid in self.pending.get(text, []) if self.is_current(mid)]
            if ids:
                self.pending[text] = ids
                self.queue.put_nowait(text)
            else:
                self.pending.pop(text, None)
            self.queue.task_done()

    def start(self):
        self.workers = [asyncio.create_task(self.worker()) for _ in range(self.concurrency)]

    async def close(self):
        self.closed = True
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        self.pending.clear()
        self.cache.clear()

    def submit(self, mid: str, text: str) -> str:
        if self.closed or self.paused or getattr(self.provider, "paused", False) or not should_translate(text):
            return "skipped"
        if text in self.cache:
            self.cache.move_to_end(text)
            self.on_result(mid, self.cache[text], "complete")
            return "complete"
        if text in self.pending:
            # Hub only retains 500 messages; bound duplicate waiters as well.
            self.pending[text] = (self.pending[text] + [mid])[-500:]
            return "pending"
        if self.queue.full():
            self.discard_stale_jobs()
        if self.queue.full():
            self.on_state("busy", "翻译队列已满，部分弹幕仅显示原文。")
            return "skipped"
        self.pending[text] = [mid]
        self.queue.put_nowait(text)
        return "pending"

    async def worker(self):
        while True:
            text = await self.queue.get()
            result, status = None, "failed"
            try:
                if not any(self.is_current(mid) for mid in self.pending.get(text, [])):
                    continue
                if not self.paused:
                    await asyncio.sleep(max(0, self.cooldown_until - time.monotonic()))
                    # Another worker may have paused the pool while we waited.
                    if not self.paused:
                        if isinstance(self.provider, GoogleWebTranslator):
                            # Pacing/cooldown is outside the five-second network timeout.
                            await self.provider.wait_ready()
                            if not any(self.is_current(mid) for mid in self.pending.get(text, [])):
                                continue
                            result = await self.provider.translate(text, self.target)
                        else:
                            result = await asyncio.wait_for(self.provider.translate(text, self.target), self.timeout)
                        status = "complete"
                        if not self.paused:
                            self.on_state("active", "翻译运行中。")
                        self.cache[text] = result
                        if len(self.cache) > 1000:
                            self.cache.popitem(last=False)
            except (TimeoutError, TranslationError) as error:
                code = error.code if isinstance(error, TranslationError) else "timeout"
                if isinstance(self.provider, GoogleWebTranslator):
                    self.provider.report_error(code)
                    continue
                if self.paused and code != "credentials_or_quota":
                    continue
                if code == "credentials_or_quota":
                    self.paused = True
                    self.on_state("paused", "翻译已暂停：请检查 Azure Key、区域和 F0 免费额度；修正配置或重新连接后恢复。")
                elif code == "rate_limited":
                    self.cooldown_until = time.monotonic() + 2
                    self.on_state("rate_limited", "翻译服务限流，短暂退避；当前消息保留原文。")
                else:
                    self.on_state("degraded", "翻译超时或暂不可用，保留原文。")
            except Exception:
                # A failed worker must not disappear behind a misleading running status.
                self.paused = True
                self.on_state("paused", "翻译任务异常，已暂停；请点击「恢复翻译」重试。")
            finally:
                for mid in self.pending.pop(text, []):
                    if not self.closed and self.is_current(mid):
                        self.on_result(mid, result, status)
                self.queue.task_done()
