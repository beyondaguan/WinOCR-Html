@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM WinOCR-Html Native Host Uninstaller
REM ============================================================
REM This script removes the native messaging host registration
REM Run as Administrator for best results
REM ============================================================

echo ========================================
echo WinOCR-Html Native Host Uninstaller
echo ========================================
echo.

REM Registry keys
set "REG_KEY_CHROME=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host"
set "REG_KEY_EDGE=HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host"

echo Removing Chrome registration...
reg delete "%REG_KEY_CHROME%" /f >nul 2>&1
if errorlevel 1 (
    echo WARNING: Failed to remove Chrome registration (may not exist)
) else (
    echo OK: Chrome registration removed
)

echo.
echo Removing Edge registration...
reg delete "%REG_KEY_EDGE%" /f >nul 2>&1
if errorlevel 1 (
    echo WARNING: Failed to remove Edge registration (may not exist)
) else (
    echo OK: Edge registration removed
)

echo.
echo ========================================
echo Uninstallation Complete!
echo ========================================
echo.
pause
