import asyncio
import copy
from collections import OrderedDict
from datetime import datetime, timezone
from uuid import uuid4

from .config import Config
from .translation import AzureTranslator, GoogleWebTranslator, TranslationError, TranslationPool, Result
from .youtube import SourceError, map_item


class ChatHub:
    def __init__(self, config: Config, source, http_client):
        self.config, self.source, self.http_client = config, source, http_client
        self.clients: set[asyncio.Queue] = set()
        self.messages: OrderedDict[str, dict] = OrderedDict()
        self.seen: OrderedDict[str, None] = OrderedDict()
        self.deleted: OrderedDict[str, None] = OrderedDict()
        self.status = {"connection": "idle", "code": "", "message": "尚未连接。",
                       "translation": "off", "translation_message": "翻译未开启。"}
        self.task = None
        self.pool = None
        self.google = GoogleWebTranslator(http_client, self.google_state)
        self.test_task = None
        self.mode = "idle"
        self.session = uuid4().hex
        self.lock = asyncio.Lock()

    def snapshot(self):
        return {"type": "snapshot", "session": self.session, "messages": copy.deepcopy(list(self.messages.values())),
                "config": self.config.public(), "status": self.status.copy()}

    def subscribe(self):
        queue = asyncio.Queue(maxsize=1000)
        queue.put_nowait(self.snapshot())
        self.clients.add(queue)
        return queue

    def publish(self, event):
        event = {"session": self.session, **event}
        for queue in self.clients.copy():
            if queue.full():
                # A slow browser gets the current bounded snapshot, rather than an unbounded backlog.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(self.snapshot())
            else:
                queue.put_nowait(copy.deepcopy(event))

    def set_status(self, connection: str, message: str, code: str = ""):
        self.status.update(connection=connection, message=message, code=code)
        self.publish({"type": "status", "status": self.status.copy()})

    def translation_state(self, state, message):
        if self.status["translation"] == state and self.status["translation_message"] == message:
            return
        self.status.update(translation=state, translation_message=message)
        self.publish({"type": "status", "status": self.status.copy()})

    def translated(self, mid: str, result: Result | None, status: str):
        message = self.messages.get(mid)
        if message is None:
            return
        fields = {"translation_status": status, "translation": "", "source_language": ""}
        if result:
            fields["source_language"] = result.language
            # Chinese script variants are distinct targets; English region variants share a language.
            same_language = result.language.lower() == self.config.target_language.lower()
            if not same_language and result.text.strip() != message["original"].strip():
                fields["translation"] = result.text
        message.update(fields)
        self.publish({"type": "translation", "id": mid, **fields})

    def google_state(self, state, message):
        if self.config.translation_provider == "google_web" and self.mode != "demo":
            self.translation_state(state, message)

    def provider(self):
        if self.config.translation_provider == "google_web":
            return self.google
        if not self.config.azure_key or not self.config.azure_region:
            raise TranslationError("missing_credentials")
        return AzureTranslator(self.http_client, self.config.azure_key, self.config.azure_region)

    async def cancel_translation_test(self):
        if self.test_task and not self.test_task.done():
            self.test_task.cancel()
            await asyncio.gather(self.test_task, return_exceptions=True)

    async def test_translation(self):
        async with self.lock:
            if self.test_task and not self.test_task.done():
                raise TranslationError("busy")
            provider, target = self.provider(), self.config.target_language
            if isinstance(provider, GoogleWebTranslator) and provider.lock.locked():
                raise TranslationError("busy")
            sample = "你好，欢迎观看直播！" if target == "en" else "Hello, welcome to the stream!"
            self.test_task = asyncio.create_task(provider.translate(sample, target))
            task = self.test_task
        try:
            result = await task
            return {"provider": self.config.translation_provider, "target_language": target,
                    "original": sample, "translation": result.text, "source_language": result.language}
        except asyncio.CancelledError:
            raise TranslationError("stale") from None
        except TranslationError as error:
            if isinstance(provider, GoogleWebTranslator):
                provider.report_error(error.code)
            raise

    async def resume_translation(self):
        async with self.lock:
            await self.cancel_translation_test()
            if self.config.translation_provider == "google_web":
                self.google.resume()
            if self.mode == "live" and self.task and not self.task.done():
                await self.setup_translation()
                self.mark_pending_failed()
            return self.status

    async def setup_translation(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
        if self.mode == "demo":
            self.translation_state("demo", "演示译文为固定样例，不调用外部 API。")
        elif not self.config.translation_enabled:
            self.translation_state("off", "翻译未开启。")
        elif self.config.translation_provider == "azure" and (not self.config.azure_key or not self.config.azure_region):
            self.translation_state("paused", "请填写 Azure Key 和区域；当前仅显示原文。")
        else:
            self.pool = TranslationPool(
                self.provider(), self.config.target_language, self.translated, self.translation_state,
                concurrency=1 if self.config.translation_provider == "google_web" else 4,
            )
            self.pool.start()
            if self.config.translation_provider == "google_web" and self.google.paused:
                self.google.report_error("paused")
            else:
                self.translation_state("active", "翻译运行中；可点击「保存并测试翻译」验证服务。")

    async def stop(self):
        await self.cancel_translation_test()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def disconnect(self):
        async with self.lock:
            await self.stop()
            self.mode = "idle"
            self.mark_pending_failed()
            self.translation_state("off", "连接已停止。")
            self.set_status("idle", "连接已停止，保留现有消息。")

    def mark_pending_failed(self):
        for mid, message in self.messages.items():
            if message["translation_status"] == "pending":
                self.translated(mid, None, "failed")

    async def connect(self, demo: bool = False):
        async with self.lock:
            # Multiple callers must not open multiple connections.
            if self.task and not self.task.done() and self.mode == ("demo" if demo else "live"):
                return
            await self.stop()
            if self.google.paused:
                self.google.resume()
            self.mode = "demo" if demo else "live"
            self.session = uuid4().hex
            self.messages.clear()
            self.seen.clear()
            self.deleted.clear()
            self.set_status("connecting", "正在启动演示…" if demo else "正在连接 YouTube…")
            await self.setup_translation()
            self.publish(self.snapshot())
            self.task = asyncio.create_task(self.run_demo() if demo else self.run_live())

    async def configure(self, config: Config):
        async with self.lock:
            old = self.config
            source_changed = any(getattr(old, key) != getattr(config, key) for key in ("source", "source_type", "youtube_key"))
            translation_changed = any(getattr(old, key) != getattr(config, key) for key in (
                "translation_provider", "target_language", "translation_enabled", "azure_key", "azure_region"))
            if source_changed or translation_changed:
                await self.cancel_translation_test()
            if source_changed:
                await self.stop()
                self.mode = "idle"
                self.session = uuid4().hex
                self.messages.clear()
                self.seen.clear()
                self.deleted.clear()
                self.set_status("idle", "直播源配置已改变，请重新连接。")
            self.config = config
            while len(self.messages) > config.style.max_messages:
                self.messages.popitem(last=False)
            if source_changed or translation_changed:
                # Cancel all old work before starting any new-language work.
                if self.pool:
                    await self.pool.close()
                    self.pool = None
                for message in self.messages.values():
                    message.update(translation="", source_language="", translation_status="skipped")
                if self.mode != "idle":
                    await self.setup_translation()
                    if self.pool:
                        for message in self.messages.values():
                            message["translation_status"] = self.pool.submit(message["id"], message["original"])
                else:
                    self.translation_state("off", "连接后启动翻译。")
            self.publish(self.snapshot())

    @staticmethod
    def remember(collection, value, limit=10000):
        collection[value] = None
        collection.move_to_end(value)
        if len(collection) > limit:
            collection.popitem(last=False)

    def add(self, message: dict):
        mid = message["id"]
        if mid in self.seen or mid in self.deleted:
            return
        self.remember(self.seen, mid)
        self.messages[mid] = message
        while len(self.messages) > self.config.style.max_messages:
            self.messages.popitem(last=False)
        # Publish first, so even cached translation events can never precede the original.
        if self.pool:
            message["translation_status"] = "pending"
        self.publish({"type": "message", "message": message})
        if self.pool:
            state = self.pool.submit(mid, message["original"])
            if state != "pending":
                message["translation_status"] = state
                self.publish({"type": "translation", "id": mid, "translation": message["translation"],
                              "source_language": message["source_language"], "translation_status": state})

    def delete(self, ids: list[str]):
        ids = [mid for mid in ids if mid]
        for mid in ids:
            self.messages.pop(mid, None)
            self.remember(self.deleted, mid)
        if ids:
            self.publish({"type": "delete", "ids": ids})

    def consume(self, item: dict) -> bool:
        event = map_item(item)
        if not event:
            return False
        if event["type"] == "message":
            self.add(event["message"])
        elif event["type"] == "delete":
            self.delete(event["ids"])
        elif event["type"] == "ban" and event["author_id"]:
            self.delete([mid for mid, message in self.messages.items() if message["author_id"] == event["author_id"]])
        elif event["type"] == "ended":
            return True
        return False

    async def run_live(self):
        token, failures = "", 0
        try:
            if not self.config.youtube_key:
                raise SourceError("credentials", "请先填写 YouTube API Key。")
            chat_id = await self.source.resolve(self.config.source, self.config.source_type, self.config.youtube_key)
            while True:
                ended = False
                received = False
                try:
                    async for batch in self.source.stream(chat_id, self.config.youtube_key, token):
                        received = True
                        failures = 0
                        token = batch.token or token
                        self.set_status("connected", "已连接 YouTube 直播聊天。")
                        for item in batch.items:
                            if self.consume(item):
                                ended = True
                                break
                        if batch.offline or ended:
                            self.set_status("ended", "直播聊天已结束。", "chat_ended")
                            return
                    # A normal stream close resumes using the latest token, with a small delay.
                    if not received:
                        failures += 1
                    self.set_status("reconnecting", "连接已关闭，正在续传。")
                except SourceError as error:
                    if not error.retry:
                        raise
                    failures += 1
                    self.set_status("reconnecting", error.message, error.code)
                if failures >= 6:
                    raise SourceError("network", "多次重连失败，请检查网络并手动重连。")
                await asyncio.sleep(min(30, 2 ** max(0, failures - 1)))
        except SourceError as error:
            self.set_status("error", error.message, error.code)
        except Exception:
            # Raw upstream errors may contain credentials or request URLs.
            self.set_status("error", "连接出现异常，请检查网络、配置并重新连接。", "unexpected")
        finally:
            if self.pool:
                await self.pool.close()
                self.pool = None
            if self.status["translation"] not in {"paused", "off"}:
                self.translation_state("off", "直播连接已停止，翻译已停止。")
            self.mark_pending_failed()

    async def run_demo(self):
        samples = [
            ("Mika", "こんにちは！配信楽しみにしていました 🌸", "你好！一直很期待这次直播 🌸", "ja"),
            ("Alex", "Hello from London! Love this stream 💚", "来自伦敦的问候！好喜欢这场直播 💚", "en"),
            ("小雨", "晚上好，今天也要加油呀！", "晚上好，今天也要加油呀！", "zh-Hans"),
            ("Sofia", "¡Qué bonito! Gracias por compartir ✨", "太漂亮了！谢谢分享 ✨", "es"),
            ("Min", "오늘 방송 정말 재밌어요!", "今天的直播真的很有趣！", "ko"),
            ("测试观众", "<script>alert('文本安全测试')</script>", "<script>alert('文本安全测试')</script>", "zh-Hans"),
        ]
        self.set_status("demo", "演示模式：固定样例，不消耗 API 额度。")
        index = 0
        while True:
            author, original, translation, language = samples[index % len(samples)]
            mid = f"demo-{index}"
            self.add({"id": mid, "author_id": author, "author": author, "avatar": "/avatar.svg",
                      "role": "moderator" if index % 6 == 0 else "normal", "time": datetime.now(timezone.utc).isoformat(),
                      "original": original, "translation": "", "source_language": "", "translation_status": "pending"})
            await asyncio.sleep(0.7)
            # Demo translations are explicitly fixed examples, not live machine translation.
            if self.config.target_language == "zh-Hans":
                self.translated(mid, Result(translation, language), "complete")
            else:
                self.translated(mid, None, "skipped")
            index += 1
            await asyncio.sleep(1.5)
