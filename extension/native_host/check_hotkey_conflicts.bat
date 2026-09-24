@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM 快捷键冲突检测工具
REM ============================================================
REM 检测当前系统已注册的热键，避免冲突
REM ============================================================

echo ========================================
echo 快捷键冲突检测工具
echo ========================================
echo.

REM 检测常见热键冲突
echo 正在检测系统热键注册情况...
echo.

REM 常见冲突热键列表
set CONFLICT_LIST="Ctrl+Shift+M Ctrl+Alt+Q Ctrl+Shift+A Ctrl+Shift+Z Ctrl+Shift+X Ctrl+Shift+S Ctrl+Alt+S Ctrl+Alt+M"

echo.
echo 常见冲突热键：
echo   Ctrl+Shift+M  - 可能与其他扩展冲突
echo   Ctrl+Alt+Q    - 可能被 QQ/微信占用
echo   Ctrl+Shift+A  - 可能被 IDE 占用
echo   Ctrl+Shift+Z  - 撤销操作（通用）
echo   Ctrl+Shift+X  - 剪切操作（通用）
echo   Ctrl+Shift+S  - 另存为（通用）
echo   Ctrl+Alt+S    - 可能被截图软件占用
echo   Ctrl+Alt+M    - 可能被输入法占用
echo.

echo 推荐热键组合（低冲突风险）：
echo   Win+Shift+A  - 截图 OCR
echo   Win+Shift+Z  - 翻译选中
echo   Ctrl+Alt+W   - 打开面板
echo   F6            - 截图（单键）
echo   F7            - 翻译（单键）
echo.

echo ========================================
echo 注册表检测
echo ========================================
echo.

REM 检测 Chrome 扩展注册的热键
echo [Chrome 扩展热键]
reg query "HKCU\Software\Google\Chrome\Extensions" /s 2>nul | findstr /i "hotkey" || echo   未找到 Chrome 热键注册

REM 检测 AutoHotkey 脚本
echo.
echo [AutoHotkey 检测]
tasklist /fi "imagename eq autohotkey.exe" 2>nul | findstr /i "autohotkey" >nul
if %ERRORLEVEL% equ 0 (
    echo   ⚠️ 检测到 AutoHotkey 运行，可能占用热键
) else (
    echo   ✓ 未检测到 AutoHotkey
)

REM 检测常见截图软件
echo.
echo [截图软件检测]
tasklist /fi "imagename eq SnippingTool.exe" 2>nul | findstr /i "SnippingTool" >nul
if %ERRORLEVEL% equ 0 echo   ⚠️ Windows 截图工具运行中

tasklist /fi "imagename eq ShareX.exe" 2>nul | findstr /i "ShareX" >nul
if %ERRORLEVEL% equ 0 echo   ⚠️ ShareX 运行中（可能占用 PrintScreen）

tasklist /fi "imagename eq Greenshot.exe" 2>nul | findstr /i "Greenshot" >nul
if %ERRORLEVEL% equ 0 echo   ⚠️ Greenshot 运行中

REM 检测即时通讯软件
echo.
echo [即时通讯软件检测]
tasklist /fi "imagename eq WeChat.exe" 2>nul | findstr /i "WeChat" >nul
if %ERRORLEVEL% equ 0 echo   ⚠️ 微信运行中（Ctrl+Alt+A 截图冲突）

tasklist /fi "imagename eq QQ.exe" 2>nul | findstr /i "QQ" >nul
if %ERRORLEVEL% equ 0 echo   ⚠️ QQ 运行中（Ctrl+Alt+A 截图冲突）

echo.
echo ========================================
echo 检测完成
echo ========================================
echo.
pause
