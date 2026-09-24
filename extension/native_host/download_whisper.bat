@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM Whisper 模型下载脚本（支持代理）
REM ============================================================
REM 下载 Whisper GGML 模型到 models/whisper 目录
REM ============================================================

echo ========================================
echo Whisper 模型下载
echo ========================================
echo.

REM 配置代理（取消注释并修改为你自己的代理）
REM set HTTP_PROXY=http://127.0.0.1:7890
REM set HTTPS_PROXY=http://127.0.0.1:7890

REM 使用 HuggingFace 国内镜像
set HF_ENDPOINT=https://hf-mirror.com

REM 模型下载目录
set MODEL_DIR=%~dp0..\models\whisper

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

echo.
echo 模型保存目录: %MODEL_DIR%
echo.

REM 检查代理
if not "%HTTP_PROXY%"=="" (
    echo 已配置代理: %HTTP_PROXY%
) else (
    echo 未配置代理，将尝试直连...
)
echo.

REM 选择要下载的模型
echo 请选择要下载的模型：
echo   1) tiny (74MB, 推荐, 速度快)
echo   2) base (140MB, 平衡)
echo   3) 全部下载
echo.
set /p CHOICE="请输入选项 (1/2/3): "

if "%CHOICE%"=="1" goto download_tiny
if "%CHOICE%"=="2" goto download_base
if "%CHOICE%"=="3" goto download_all
goto end

:download_tiny
echo.
echo 正在下载 tiny 模型...
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin" "%MODEL_DIR%\ggml-tiny.bin"
goto end

:download_base
echo.
echo 正在下载 base 模型...
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" "%MODEL_DIR%\ggml-base.bin"
goto end

:download_all
echo.
echo 正在下载所有模型...
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin" "%MODEL_DIR%\ggml-tiny.bin"
call :download_model "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" "%MODEL_DIR%\ggml-base.bin"

:end
echo.
echo ========================================
echo 下载完成！
echo ========================================
echo.
pause
exit /b

:download_model
set URL=%~1
set OUTPUT=%~2

echo 下载: %~nx2

where curl >nul 2>&1
if %ERRORLEVEL% equ 0 (
    curl -L --progress-bar -o "%OUTPUT%" "%URL%"
    if %ERRORLEVEL% equ 0 (
        echo   ✓ 下载成功
    ) else (
        echo   ✗ 下载失败，请检查代理设置
    )
) else (
    echo 未找到 curl，请使用浏览器手动下载：
    echo   URL: %URL%
    echo   保存到: %OUTPUT%
)
exit /b
