"""Exercise the actual packaged binary without credentials or external API calls."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
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
                request("/api/config", "PUT", {"target_language": "ja"})
                persisted = json.loads((Path(directory) / "config.json").read_text("utf-8"))
                assert persisted["target_language"] == "ja"
                request("/api/config", "PUT", {"target_language": "zh-Hans"})
                request("/api/demo", "POST")

                async def check_socket():
                    async with websockets.connect(f"ws://127.0.0.1:{port}/ws", proxy=None) as ws:
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline:
                            event = json.loads(await asyncio.wait_for(ws.recv(), 5))
                            if event["type"] == "translation" and event.get("translation"):
                                return
                            if event["type"] == "snapshot" and any(m["translation"] for m in event["messages"]):
                                return
                        raise AssertionError("Bundled WebSocket did not deliver bilingual demo")
                asyncio.run(check_socket())
                request("/api/disconnect", "POST")
                print("Bundle smoke test passed: assets, configuration, WebSocket, bilingual demo.")
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
