import asyncio
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

import httpx


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


class TranslationPool:
    """Bounded jobs, coalesced duplicate requests, and an in-memory LRU cache."""

    def __init__(self, provider, target: str, on_result: Callable, on_state: Callable,
                 concurrency: int = 4, capacity: int = 200, timeout: float = 5):
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
        if self.closed or self.paused or not should_translate(text):
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
                if not self.paused:
                    await asyncio.sleep(max(0, self.cooldown_until - time.monotonic()))
                    # Another worker may have paused the pool while we waited.
                    if not self.paused:
                        result = await asyncio.wait_for(self.provider.translate(text, self.target), self.timeout)
                        status = "complete"
                        if not self.paused:
                            self.on_state("active", "翻译运行中。")
                        self.cache[text] = result
                        if len(self.cache) > 1000:
                            self.cache.popitem(last=False)
            except (TimeoutError, TranslationError) as error:
                code = error.code if isinstance(error, TranslationError) else "timeout"
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
            finally:
                for mid in self.pending.pop(text, []):
                    if not self.closed:
                        self.on_result(mid, result, status)
                self.queue.task_done()
