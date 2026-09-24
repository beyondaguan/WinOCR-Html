@echo off
REM ============================================================
REM Whisper Model Download Script (Proxy Supported)
REM ============================================================
REM Download Whisper GGML model to models/whisper directory
REM ============================================================

echo ========================================
echo Whisper Model Download
echo ========================================
echo.

REM Configure proxy (uncomment and modify)
REM set HTTP_PROXY=http://127.0.0.1:7890
REM set HTTPS_PROXY=http://127.0.0.1:7890

REM HuggingFace mirror
set HF_ENDPOINT=https://hf-mirror.com

REM Model directory
set MODEL_DIR=%~dp0..\models\whisper

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

echo.
echo Model dir: %MODEL_DIR%
echo.

if not "%HTTP_PROXY%"=="" (
    echo Proxy: %HTTP_PROXY%
) else (
    echo No proxy configured
)
echo.

echo Select model to download:
echo   1) tiny (74MB, recommended, fast)
echo   2) base (140MB, balanced)
echo   3) Download all
echo.
set /p CHOICE="Enter option (1/2/3): "

if "%CHOICE%"=="1" goto download_tiny
if "%CHOICE%"=="2" goto download_base
if "%CHOICE%"=="3" goto download_all
goto end

:download_tiny
echo.
echo Downloading tiny model...
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin" "%MODEL_DIR%\ggml-tiny.bin"
goto end

:download_base
echo.
echo Downloading base model...
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" "%MODEL_DIR%\ggml-base.bin"
goto end

:download_all
echo.
echo Downloading all models...
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin" "%MODEL_DIR%\ggml-tiny.bin"
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" "%MODEL_DIR%\ggml-base.bin"

:end
echo.
echo ========================================
echo Download Complete!
echo ========================================
echo.
pause
exit /b

:download_model
set URL=%~1
set OUTPUT=%~2

echo Downloading: %~nx2

where curl >nul 2>&1
if %ERRORLEVEL% equ 0 (
    curl -L --progress-bar -o "%OUTPUT%" "%URL%"
    if %ERRORLEVEL% equ 0 (
        echo   [OK] Download success
    ) else (
        echo   [FAIL] Check proxy settings
    )
) else (
    echo curl not found, download manually:
    echo   URL: %URL%
    echo   Save to: %OUTPUT%
)
exit /b
