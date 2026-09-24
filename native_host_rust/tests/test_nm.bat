@echo off
chcp 65001 >nul 2>&1
REM Native Messaging Test Runner for Windows
REM Usage: test_nm.bat [path_to_host.exe]

echo ========================================
echo Native Messaging Test Script
echo ========================================

REM Find host executable
if "%~1"=="" (
    if exist "..\target\debug\winocr_host.exe" (
        set HOST=..\target\debug\winocr_host.exe
    ) else if exist "..\target\release\winocr_host.exe" (
        set HOST=..\target\release\winocr_host.exe
    ) else (
        echo ERROR: winocr_host.exe not found!
        echo Please build first: cargo build
        echo Or specify path: test_nm.bat path\to\winocr_host.exe
        exit /b 1
    )
) else (
    set HOST=%~1
)

echo Using host: %HOST%
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.6+
    exit /b 1
)

REM Run tests
python test_nm.py "%HOST%"

echo.
pause
