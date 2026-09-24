@echo off
REM ============================================================
REM Hotkey Conflict Detection Tool
REM ============================================================

echo ========================================
echo Hotkey Conflict Detection Tool
echo ========================================
echo.

echo Scanning system for registered hotkeys...
echo.

echo Common conflict hotkeys:
echo   Ctrl+Shift+M  - May conflict with extensions
echo   Ctrl+Alt+Q    - May conflict with QQ/WeChat
echo   Ctrl+Shift+A  - May conflict with IDE
echo   Ctrl+Shift+Z  - Undo (common)
echo   Ctrl+Shift+X  - Cut (common)
echo   Ctrl+Shift+S  - Save As (common)
echo   Ctrl+Alt+S    - May conflict with screenshot tools
echo   Ctrl+Alt+M    - May conflict with IME
echo.

echo Recommended hotkeys (low conflict risk):
echo   Win+Shift+A  - Screenshot OCR
echo   Win+Shift+Z  - Translate selection
echo   Ctrl+Alt+W   - Open panel
echo   F6            - Screenshot (single key)
echo   F7            - Translate (single key)
echo.

echo ========================================
echo Registry Scan
echo ========================================
echo.

echo [Chrome Extensions]
reg query "HKCU\Software\Google\Chrome\Extensions" /s 2>nul | findstr /i "hotkey" || echo   No Chrome hotkey found

echo.
echo [AutoHotkey]
tasklist /fi "imagename eq autohotkey.exe" 2>nul | findstr /i "autohotkey" >nul
if %ERRORLEVEL% equ 0 (
    echo   [WARN] AutoHotkey detected
) else (
    echo   [OK] No AutoHotkey
)

echo.
echo [Screenshot Tools]
tasklist /fi "imagename eq SnippingTool.exe" 2>nul | findstr /i "SnippingTool" >nul
if %ERRORLEVEL% equ 0 echo   [WARN] Windows Snipping Tool

tasklist /fi "imagename eq ShareX.exe" 2>nul | findstr /i "ShareX" >nul
if %ERRORLEVEL% equ 0 echo   [WARN] ShareX

tasklist /fi "imagename eq Greenshot.exe" 2>nul | findstr /i "Greenshot" >nul
if %ERRORLEVEL% equ 0 echo   [WARN] Greenshot

echo.
echo [IM Software]
tasklist /fi "imagename eq WeChat.exe" 2>nul | findstr /i "WeChat" >nul
if %ERRORLEVEL% equ 0 echo   [WARN] WeChat (Ctrl+Alt+A conflict)

tasklist /fi "imagename eq QQ.exe" 2>nul | findstr /i "QQ" >nul
if %ERRORLEVEL% equ 0 echo   [WARN] QQ (Ctrl+Alt+A conflict)

echo.
echo ========================================
echo Scan Complete
echo ========================================
echo.
pause
