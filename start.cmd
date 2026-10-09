@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.cmd first.
  pause
  exit /b 1
)
if not exist frontend\dist\index.html (
  echo Frontend not built. Run install.cmd first.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:12450 in your browser.
echo Keep this window open. Press Ctrl+C to stop the server.
.venv\Scripts\python.exe main.py %*
if errorlevel 1 pause
