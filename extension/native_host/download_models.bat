@echo off
REM ============================================================
REM WinOCR-Html Optional Model Download (Proxy Supported)
REM ============================================================
REM NOTE: The tiny OCR model set (det_tiny.onnx, rec_tiny.onnx,
REM       ppocr_dict.txt) is ALREADY BUNDLED with the installer.
REM       You only need this script for the higher-accuracy
REM       medium models (~60 MB) or to restore tiny files.
REM ============================================================

echo ========================================
echo WinOCR-Html Model Download (optional)
echo ========================================
echo.
echo Tiny models are already bundled - nothing to do.
echo This script is only needed for:
echo   1) medium models (higher accuracy, ~60 MB)
echo   2) restore tiny models (if deleted)
echo.

REM Configure proxy (uncomment and modify)
REM set HTTP_PROXY=http://127.0.0.1:7890
REM set HTTPS_PROXY=http://127.0.0.1:7890

set BASE=https://hf-mirror.com/xberg-io/paddleocr-onnx-models/resolve/main/v6
set MODEL_DIR=%~dp0models\ocr

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

echo Model dir: %MODEL_DIR%
if not "%HTTP_PROXY%"=="" (
    echo Proxy: %HTTP_PROXY%
) else (
    echo No proxy configured
)
echo.
echo Select:
echo   1) medium (higher accuracy, ~60 MB)
echo   2) restore tiny (bundled default)
echo   3) cancel
echo.
set /p CHOICE="Enter option (1/2/3): "

if "%CHOICE%"=="1" goto download_medium
if "%CHOICE%"=="2" goto download_tiny
goto end

:download_medium
echo.
call :download_model "%BASE%/det/medium/model.onnx" "%MODEL_DIR%\det_medium.onnx"
call :download_model "%BASE%/rec/medium/model.onnx" "%MODEL_DIR%\rec_medium.onnx"
call :download_model "%BASE%/rec/medium/dict.txt" "%MODEL_DIR%\ppocr_dict_medium.txt"
echo.
echo Then set OCR tier to "medium" in extension options.
goto end

:download_tiny
echo.
call :download_model "%BASE%/det/tiny/model.onnx" "%MODEL_DIR%\det_tiny.onnx"
call :download_model "%BASE%/rec/tiny/model.onnx" "%MODEL_DIR%\rec_tiny.onnx"
call :download_model "%BASE%/rec/tiny/dict.txt" "%MODEL_DIR%\ppocr_dict.txt"
goto end

:end
echo.
echo ========================================
echo Done!
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
