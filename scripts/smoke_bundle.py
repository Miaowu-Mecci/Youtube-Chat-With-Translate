"""Exercise the actual packaged binary without credentials or external API calls."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

import websockets


def smoke(binary: Path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="ytchat-bundle-") as directory:
        env = {**os.environ, "YTCHAT_DATA_DIR": directory, "NO_PROXY": "127.0.0.1,localhost"}
        with open(Path(directory) / "startup.log", "w+") as output:
            process = subprocess.Popen([str(binary.resolve()), "--no-browser", "--port", str(port)],
                                       cwd=directory, env=env, stdout=output, stderr=output)
            try:
                def request(path, method="GET", payload=None):
                    data = json.dumps(payload).encode() if payload is not None else None
                    with urlopen(Request(base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"}), timeout=2) as response:
                        return response.read()
                deadline = time.monotonic() + 60
                while True:
                    try:
                        request("/api/status")
                        break
                    except OSError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            output.seek(0)
                            raise RuntimeError("Packaged server did not start:\n" + output.read()) from None
                        time.sleep(.2)
                import re
                page = request("/").decode()
                assert '<div id="app">' in page
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page)
                assert assets, "Missing bundled frontend assets"
                for asset in assets:
                    assert request(asset)
                assert b'<svg' in request("/avatar.svg")
                assert b'<svg' in request("/emotes/sakura.svg")
                config = json.loads(request("/api/config"))
                assert config["youtube_provider"] == "web"
                assert config["translation_provider"] == "google_web"
                assert not config["translation_enabled"]
                assert len(json.loads(request("/api/languages?provider=google_web"))["languages"]) == 8
                request("/api/config", "PUT", {"target_language": "ja"})
                persisted = json.loads((Path(directory) / "config.json").read_text("utf-8"))
                assert persisted["target_language"] == "ja"
                assert persisted["target_languages"] == ["ja"]
                targets = ["zh-Hans", "zh-Hant", "en", "ja", "ko", "es", "fr", "de"]
                request("/api/config", "PUT", {"target_languages": targets})
                persisted = json.loads((Path(directory) / "config.json").read_text("utf-8"))
                assert persisted["target_languages"] == targets
                clicked_at = datetime.now(timezone.utc).isoformat()
                # No YouTube key: exercise the packaged API without external requests.
                connection = json.loads(request("/api/connect", "POST", {"started_at": clicked_at}))
                assert connection["chat_started_at"] == clicked_at
                assert connection["ignored_history"] == 0
                request("/api/demo", "POST")

                async def check_socket():
                    async with websockets.connect(f"ws://127.0.0.1:{port}/ws", proxy=None) as ws:
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline:
                            event = json.loads(await asyncio.wait_for(ws.recv(), 5))
                            candidates = event.get("messages", []) if event["type"] == "snapshot" else (
                                [event] if event["type"] == "translation" else [])
                            for message in candidates:
                                rows = message.get("translations", [])
                                if len(rows) == len(targets) and all(row["status"] == "complete" for row in rows):
                                    assert [row["language"] for row in rows] == targets
                                    assert all(row["text"] for row in rows)
                                    return message["id"]
                        raise AssertionError("Bundled WebSocket did not deliver multilingual demo")
                mid = asyncio.run(check_socket())
                reordered = list(reversed(targets))
                request("/api/config", "PUT", {"target_languages": reordered})

                async def check_reordered_snapshot():
                    async with websockets.connect(f"ws://127.0.0.1:{port}/ws", proxy=None) as ws:
                        snapshot = json.loads(await asyncio.wait_for(ws.recv(), 5))
                        message = next(message for message in snapshot["messages"] if message["id"] == mid)
                        assert [row["language"] for row in message["translations"]] == reordered
                        assert all(row["status"] == "complete" and row["text"] for row in message["translations"])
                        assert any(part["type"] == "emoji" and part["url"] == "/emotes/sakura.svg" for part in message["content_parts"])
                asyncio.run(check_reordered_snapshot())
                request("/api/disconnect", "POST")
                print("Bundle smoke test passed: assets, free-chat/Google defaults, configuration, multilingual demo, emote asset/content and language reordering.")
            finally:
                if sys.platform == "win32" and process.poll() is None:
                    # A onefile bundle has a bootloader parent and an application child.
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/smoke_bundle.py PATH_TO_BINARY")
    smoke(Path(sys.argv[1]))
