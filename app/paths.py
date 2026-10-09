"""Keep bundled read-only resources separate from persistent user configuration."""
import os
import sys
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def data_directory() -> Path:
    if override := os.environ.get("YTCHAT_DATA_DIR"):
        return Path(override).expanduser().resolve()
    if not getattr(sys, "frozen", False):
        return resource_root() / "data"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "YouTubeOBSChat"
