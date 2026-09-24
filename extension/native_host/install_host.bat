@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM WinOCR-Html Native Host Installer
REM ============================================================
REM This script registers the native messaging host with Chrome/Edge
REM Run as Administrator for best results
REM ============================================================

echo ========================================
echo WinOCR-Html Native Host Installer
echo ========================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "HOST_EXE=%SCRIPT_DIR%winocr_host.exe"

REM Check if executable exists
if not exist "%HOST_EXE%" (
    echo ERROR: winocr_host.exe not found at:
    echo %HOST_EXE%
    echo.
    echo Please build the host first:
    echo   cd ..\..\native_host_rust
    echo   cargo build --release
    echo.
    pause
    exit /b 1
)

REM Get absolute path
for %%I in ("%HOST_EXE%") do set "HOST_EXE_ABS=%%~fI"

REM Update manifest with absolute path
set "MANIFEST_FILE=%SCRIPT_DIR%com.winocr_host.json"
set "MANIFEST_TEMP=%TEMP%\com_winocr_host_temp.json"

echo Updating manifest with executable path...
powershell -Command "$json = Get-Content -Raw -Path '%MANIFEST_FILE%'; $json = $json -replace 'native_host/winocr_host.exe', $env:HOST_EXE_ABS -replace '\\', '/'; Set-Content -Path '%MANIFEST_TEMP%' -Value $json -NoNewline"

REM Registry key for Chrome
set "REG_KEY_CHROME=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host"
REM Registry key for Edge
set "REG_KEY_EDGE=HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host"

echo.
echo Registering native host for Chrome...
reg add "%REG_KEY_CHROME%" /ve /d "%MANIFEST_TEMP%" /f >nul 2>&1
if errorlevel 1 (
    echo WARNING: Failed to register for Chrome (may need Administrator)
) else (
    echo OK: Chrome registration successful
)

echo.
echo Registering native host for Edge...
reg add "%REG_KEY_EDGE%" /ve /d "%MANIFEST_TEMP%" /f >nul 2>&1
if errorlevel 1 (
    echo WARNING: Failed to register for Edge (may need Administrator)
) else (
    echo OK: Edge registration successful
)

REM Copy manifest to script directory for reference
copy /Y "%MANIFEST_TEMP%" "%SCRIPT_DIR%com.winocr_host_installed.json" >nul 2>&1

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Manifest file: %MANIFEST_TEMP%
echo.
echo To verify installation:
echo   Chrome: chrome://extensions -> Developer mode -> Check native host
echo   Edge: edge://extensions -> Developer mode -> Check native host
echo.
echo To uninstall, run: uninstall_host.bat
echo.
pause
