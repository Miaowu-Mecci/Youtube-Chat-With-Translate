import argparse
import asyncio
import multiprocessing
import sys
import webbrowser

import uvicorn

from app.server import create_app
from app.paths import data_directory


class LocalServer(uvicorn.Server):
    def __init__(self, config, browser_url=None):
        super().__init__(config)
        self.browser_url = browser_url

    async def startup(self, sockets=None):
        await super().startup(sockets)
        if self.started and self.browser_url:
            # Open only after the HTTP socket and application are ready.
            try:
                await asyncio.to_thread(webbrowser.open, self.browser_url)
            except Exception:
                print(f"Open this address in your browser: {self.browser_url}")


def main():
    parser = argparse.ArgumentParser(description="YouTube OBS 双语弹幕本地服务")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost", "::1"])
    parser.add_argument("--port", default=12450, type=int)
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument("--open-browser", dest="open_browser", action="store_true")
    browser.add_argument("--no-browser", dest="open_browser", action="store_false")
    parser.set_defaults(open_browser=bool(getattr(sys, "frozen", False)))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    host = f"[{args.host}]" if args.host == "::1" else args.host
    url = f"http://{host}:{args.port}"
    print(f"YouTube OBS Chat\nSettings: {url}\nOBS: {url}/overlay\nData: {data_directory()}", flush=True)
    print("Keep this window open. Press Ctrl+C to stop.", flush=True)
    server = LocalServer(uvicorn.Config(create_app(), host=args.host, port=args.port,
                                      loop="asyncio", http="h11", ws="websockets", access_log=False),
                         browser_url=url if args.open_browser else None)
    server.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except (Exception, SystemExit) as error:
        if getattr(sys, "frozen", False) and "--no-browser" not in sys.argv:
            # Keep double-click startup errors visible without printing config contents.
            code = error.code if isinstance(error, SystemExit) else 1
            if code:
                print("Startup failed. Check the port and local config.json, then try again.")
                if sys.stdin and sys.stdin.isatty():
                    input("Press Enter to close...")
            raise SystemExit(code) from None
        raise
