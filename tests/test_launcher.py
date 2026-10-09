import uvicorn

from main import LocalServer


async def test_browser_opens_only_after_successful_startup(monkeypatch):
    calls = []
    async def startup(server, sockets=None):
        calls.append('ready')
        server.started = True
    monkeypatch.setattr(uvicorn.Server, 'startup', startup)
    monkeypatch.setattr('main.webbrowser.open', lambda url: calls.append(url))
    server = LocalServer(uvicorn.Config('unused'), 'http://127.0.0.1:12450')
    await server.startup()
    assert calls == ['ready', 'http://127.0.0.1:12450']


async def test_failed_startup_does_not_open_browser(monkeypatch):
    calls = []
    async def startup(server, sockets=None):
        server.started = False
    monkeypatch.setattr(uvicorn.Server, 'startup', startup)
    monkeypatch.setattr('main.webbrowser.open', lambda url: calls.append(url))
    await LocalServer(uvicorn.Config('unused'), 'http://127.0.0.1:12450').startup()
    assert calls == []
