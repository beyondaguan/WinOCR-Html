@echo off
REM ============================================================
REM WinOCR-Html Native Host Uninstaller
REM ============================================================

echo ========================================
echo WinOCR-Html Native Host Uninstaller
echo ========================================
echo.

set "REG_KEY_CHROME=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host"
set "REG_KEY_EDGE=HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host"

echo Removing Chrome registration...
reg delete "%REG_KEY_CHROME%" /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Failed (may not exist)
) else (
    echo [OK] Chrome removed
)

echo.
echo Removing Edge registration...
reg delete "%REG_KEY_EDGE%" /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Failed (may not exist)
) else (
    echo [OK] Edge removed
)

echo.
echo ========================================
echo Uninstallation Complete!
echo ========================================
echo.
pause
