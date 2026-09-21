@echo off
setlocal
rem ============================================================
rem Stop ALL WinOCR-Html native host processes (any instance, any mode).
rem Needed when a stale host keeps holding the global hotkey, which makes
rem the key you press get served by an OLD process (and its old bugs).
rem ============================================================

set "HOST_DIR=%~dp0"
set "PY="
for /f "delims=" %%i in ('where python 2^>nul') do ( if not defined PY set "PY=%%i" )
if not defined PY (
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined PY (
  echo [ERROR] python not found. Install Python 3 and add it to PATH.
  pause
  exit /b 1
)

"%PY%" "%HOST_DIR%winocr_host.py" --stop

echo.
echo Done. Now start exactly ONE host:
echo   * desktop screenshots only   -^> run_host.bat
echo   * bridge to the extension    -^> do NOT start manually; the browser does it
echo.
pause
