@echo off
setlocal
rem ============================================================
rem Install WinOCR-Html native host (writes HKCU only - no admin needed)
rem
rem   1. locate python
rem   2. run setup_host.py  ->  writes winocr_launcher.bat + com.winocr.host.json
rem      (it auto-detects the extension id from the Edge/Chrome profiles,
rem       so there is nothing to edit by hand)
rem   3. register the host manifest for Edge and Chrome
rem
rem Safe to re-run at any time (e.g. after re-loading the extension).
rem Pass extra args through, e.g.:  install_host.bat --id <chrome-ext-id>
rem ============================================================

set "HOST_DIR=%~dp0"
set "SETUP=%HOST_DIR%setup_host.py"
set "JSON=%HOST_DIR%com.winocr.host.json"

rem ---- locate python ----
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

rem ---- generate launcher + host manifest ----
"%PY%" "%SETUP%" %*
if errorlevel 1 (
  echo.
  echo [ERROR] setup_host.py failed - see the messages above.
  pause
  exit /b 1
)

rem ---- register for Edge and Chrome (HKCU) ----
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr.host" /ve /t REG_SZ /d "%JSON%" /f >nul
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr.host" /ve /t REG_SZ /d "%JSON%" /f >nul

echo.
echo [OK] Host manifest registered for Edge + Chrome:
echo      %JSON%
echo.
echo Next steps (inside the extension):
echo   1. edge://extensions          reload this extension
echo   2. extension options          tick "Connect native host", then Save
echo   3. click "Test host connection" -^> it should report: bridged
echo.
pause
