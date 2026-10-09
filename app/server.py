import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from curl_cffi import AsyncSession
from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Config, ConfigStore, GOOGLE_LANGUAGES
from .hub import ChatHub
from .paths import data_directory, resource_root
from .youtube import YouTubeSource
from .translation import TranslationError

ROOT = resource_root()
FALLBACK_LANGUAGES = [{"code": code, "name": name} for code, name in [
    ("zh-Hans", "简体中文"), ("zh-Hant", "繁體中文"), ("en", "English"),
    ("ja", "日本語"), ("ko", "한국어"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"),
]]


def valid_origin(origin: str | None, host: str) -> bool:
    if origin is None:
        return True  # Local CLI clients do not send an Origin header.
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc == host


def create_app(config_path: Path | None = None, source_factory=YouTubeSource):
    store = ConfigStore(config_path or data_directory() / "config.json")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient() as client, AsyncSession() as google_client:
            app.state.client = client
            app.state.hub = ChatHub(store.config, source_factory(client), client, google_client=google_client)
            app.state.languages = None
            yield
            await app.state.hub.stop()

    app = FastAPI(title="YouTube OBS 双语弹幕", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        if not valid_origin(request.headers.get("origin"), request.headers.get("host", "")):
            return JSONResponse({"detail": "仅允许同源本地请求。"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "仅允许同源本地请求。"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # FastAPI's default validation response can echo submitted API secrets.
        return JSONResponse({"detail": "请求参数格式不正确。"}, status_code=422)

    @app.get("/api/config")
    async def get_config():
        return store.config.public()

    @app.put("/api/config")
    async def put_config(request: Request):
        try:
            incoming = await request.json()
            if not isinstance(incoming, dict):
                raise ValueError()
            # Omitted secret = keep; empty string = delete. Public indicators aren't writable fields.
            values = store.config.model_dump()
            values.update(incoming)
            config = Config.model_validate(values)
        except (ValueError, TypeError, ValidationError):
            return JSONResponse({"detail": "配置无效，请检查语言、颜色、数值和字段。"}, status_code=422)
        try:
            store.save(config)
        except OSError:
            return JSONResponse({"detail": "无法保存本地配置，请检查数据目录权限。"}, status_code=500)
        await app.state.hub.configure(config)
        return config.public()

    @app.get("/api/status")
    async def get_status():
        return {**app.state.hub.status, "clients": len(app.state.hub.clients)}

    @app.post("/api/connect")
    async def connect():
        await app.state.hub.connect()
        return app.state.hub.status

    @app.post("/api/disconnect")
    async def disconnect():
        await app.state.hub.disconnect()
        return app.state.hub.status

    @app.post("/api/demo")
    async def demo():
        await app.state.hub.connect(demo=True)
        return app.state.hub.status

    @app.post("/api/translation/test")
    async def test_translation():
        try:
            return await app.state.hub.test_translation()
        except TranslationError as error:
            messages = {
                "busy": "翻译请求正在进行，请稍后测试。",
                "missing_credentials": "请填写 Azure Key 和资源区域。",
                "credentials_or_quota": "Azure 鉴权或额度错误，请检查 Key、区域和 F0 额度。",
                "rate_limited": "翻译服务限流；Google 将等待 60 秒，请稍后测试。",
                "cooldown": "Google 正在限流等待中，请稍后测试。",
                "paused": app.state.hub.google.pause_message,
                "blocked": "Google 拒绝访问或要求验证码，已暂停；请检查网络后恢复翻译。",
                "invalid_response": "Google 接口响应格式变化，已暂停；请等待更新或切换 Azure。",
                "stale": "配置或连接已改变，本次测试已取消，请重新测试。",
            }
            return JSONResponse({"code": error.code, "detail": messages.get(error.code, "翻译超时或服务暂不可用，请检查网络。")},
                                status_code=409 if error.code in {"busy", "stale"} else 503)

    @app.post("/api/translation/resume")
    async def resume_translation():
        return await app.state.hub.resume_translation()

    @app.get("/api/languages")
    async def languages(provider: str | None = None):
        selected = provider or store.config.translation_provider
        if selected == "google_web":
            return {"languages": GOOGLE_LANGUAGES, "cached": True}
        if selected != "azure":
            return JSONResponse({"detail": "未知翻译服务。"}, status_code=422)
        if app.state.languages:
            return {"languages": app.state.languages, "cached": True}
        try:
            response = await app.state.client.get(
                "https://api.cognitive.microsofttranslator.com/languages",
                params={"api-version": "3.0", "scope": "translation"},
                headers={"Accept-Language": "zh-Hans"}, timeout=5,
            )
            response.raise_for_status()
            supported = response.json()["translation"]
            app.state.languages = sorted([
                {"code": code, "name": item["name"]} for code, item in supported.items()
            ], key=lambda item: item["name"])
            return {"languages": app.state.languages, "cached": False}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            return {"languages": FALLBACK_LANGUAGES, "fallback": True,
                    "message": "语言列表暂不可用，显示内置常用语言。"}

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        host = ws.headers.get("host", "")
        hostname = urlparse("http://" + host).hostname
        if hostname not in {"localhost", "127.0.0.1", "::1", "testserver"} or not valid_origin(ws.headers.get("origin"), host):
            await ws.close(code=1008)
            return
        await ws.accept()
        hub = app.state.hub
        queue = hub.subscribe()

        async def send():
            while True:
                await ws.send_json(await queue.get())

        async def receive():
            while True:
                await ws.receive_text()

        sender, receiver = asyncio.create_task(send()), asyncio.create_task(receive())
        try:
            await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            hub.clients.discard(queue)
            sender.cancel()
            receiver.cancel()
            await asyncio.gather(sender, receiver, return_exceptions=True)

    dist = ROOT / "frontend" / "dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/avatar.svg")
    async def avatar():
        return FileResponse(ROOT / "frontend" / "public" / "avatar.svg", media_type="image/svg+xml")

    @app.get("/")
    @app.get("/overlay")
    async def frontend():
        if not (dist / "index.html").exists():
            return JSONResponse({"detail": "请先在 frontend 目录运行 npm ci 和 npm run build。"}, status_code=503)
        return FileResponse(dist / "index.html")

    return app
