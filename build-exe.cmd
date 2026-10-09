@echo off
setlocal
cd /d "%~dp0"
call install.cmd
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
set "YTCHAT_BUNDLE_MODE=onefile"
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm YouTubeOBSChat.spec
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\smoke_bundle.py dist\YouTubeOBSChat.exe
if errorlevel 1 goto failed
echo Build and smoke test finished: dist\YouTubeOBSChat.exe
echo Share this EXE together with README.md, THIRD_PARTY_NOTICES.md and licenses.
pause
exit /b 0
:failed
echo Build failed. Check the message above.
pause
exit /b 1
