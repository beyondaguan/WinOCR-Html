@echo off
REM ============================================================
REM WinOCR-Html Native Host Installer
REM ============================================================
REM Run as Administrator for best results
REM ============================================================

echo ========================================
echo WinOCR-Html Native Host Installer
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "HOST_EXE=%SCRIPT_DIR%winocr_host.exe"

if not exist "%HOST_EXE%" (
    echo ERROR: winocr_host.exe not found
    echo.
    echo Please build first:
    echo   cd ..\..\native_host_rust
    echo   cargo build --release
    echo.
    pause
    exit /b 1
)

for %%I in ("%HOST_EXE%") do set "HOST_EXE_ABS=%%~fI"

set "MANIFEST_FILE=%SCRIPT_DIR%com.winocr_host.json"
set "MANIFEST_TEMP=%TEMP%\com_winocr_host_temp.json"

echo Updating manifest...
powershell -Command "$json = Get-Content -Raw -Path '%MANIFEST_FILE%'; $json = $json -replace 'native_host/winocr_host.exe', $env:HOST_EXE_ABS -replace '\\', '/'; Set-Content -Path '%MANIFEST_TEMP%' -Value $json -NoNewline"

set "REG_KEY_CHROME=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host"
set "REG_KEY_EDGE=HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host"

echo.
echo Registering for Chrome...
reg add "%REG_KEY_CHROME%" /ve /d "%MANIFEST_TEMP%" /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Failed (may need Administrator)
) else (
    echo [OK] Chrome registered
)

echo.
echo Registering for Edge...
reg add "%REG_KEY_EDGE%" /ve /d "%MANIFEST_TEMP%" /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Failed (may need Administrator)
) else (
    echo [OK] Edge registered
)

copy /Y "%MANIFEST_TEMP%" "%SCRIPT_DIR%com.winocr_host_installed.json" >nul 2>&1

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo To verify: chrome://extensions or edge://extensions
echo To uninstall: uninstall_host.bat
echo.
pause
