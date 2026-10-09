# Build on the target OS. Never bundle data/config.json or other user credentials.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
mode = os.environ.get("YTCHAT_BUNDLE_MODE", "onefile")
if mode not in {"onefile", "onedir"}:
    raise ValueError("YTCHAT_BUNDLE_MODE must be onefile or onedir")
if not (root / "frontend" / "dist" / "index.html").exists():
    raise ValueError("Build the frontend with npm ci and npm run build first")

datas = [
    (str(root / "frontend" / "dist"), "frontend/dist"),
    (str(root / "frontend" / "public" / "avatar.svg"), "frontend/public"),
    (str(root / "licenses"), "licenses"),
    (str(root / "LICENSE"), "."),
    (str(root / "THIRD_PARTY_NOTICES.md"), "."),
]
a = Analysis(
    [str(root / "main.py")], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=collect_submodules("uvicorn") + ["grpc._cython.cygrpc"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["pytest", "grpc_tools", "tkinter"], noarchive=False,
)
pyz = PYZ(a.pure)
if mode == "onefile":
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="YouTubeOBSChat",
              debug=False, strip=False, upx=False, console=True)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="YouTubeOBSChat",
              debug=False, strip=False, upx=False, console=True)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="YouTubeOBSChat")
