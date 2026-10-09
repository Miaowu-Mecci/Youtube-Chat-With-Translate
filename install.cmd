@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "YTCHAT_PYTHON=python"
) else (
  set "YTCHAT_PYTHON=py -3"
)
%YTCHAT_PYTHON% -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or newer is required'"
if errorlevel 1 goto failed
where npm >nul 2>nul
if errorlevel 1 (
  echo Please install Node.js 22 LTS or newer and reopen this script.
  goto failed
)
if not exist .venv\Scripts\python.exe (
  %YTCHAT_PYTHON% -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
pushd frontend
call npm ci
if errorlevel 1 goto frontend_failed
call npm run build
if errorlevel 1 goto frontend_failed
popd
echo Installation finished. Run start.cmd, then open http://127.0.0.1:12450
pause
exit /b 0
:frontend_failed
popd
:failed
echo Installation failed. Check the message above and README.md.
pause
exit /b 1
