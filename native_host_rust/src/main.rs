//! WinOCR-Html 本地壳程序（Rust 版）
//! 职责：全局截图 + PP-OCRv6 OCR + 翻译 + 浮窗显示
//! 通过 Native Messaging 与浏览器扩展通信

mod config;
mod hotkey;
mod nm;
mod ocr;
mod screenshot;
mod translate;
mod window;

use clap::Parser;
use config::Config;
use nm::{NmMessage, NmResponse};
use std::io::{self, Read, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

static RUNNING: AtomicBool = AtomicBool::new(true);

#[derive(Parser, Debug)]
#[command(name = "winocr_host")]
#[command(about = "WinOCR-Html 本地壳程序（Rust 版）")]
struct Args {
    /// 独立模式（不依赖浏览器扩展）
    #[arg(long)]
    standalone: bool,
    /// 配置文件路径
    #[arg(long, short)]
    config: Option<String>,
    /// 日志级别
    #[arg(long, short, default_value = "info")]
    log_level: String,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    // 初始化日志
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or(&args.log_level)).init();

    log::info!("WinOCR-Html Rust 宿主启动");
    log::info!("独立模式: {}", args.standalone);

    // 加载配置
    let config = Config::load(args.config.as_deref())?;
    log::info!("配置加载完成: {:?}", config);

    if args.standalone {
        run_standalone(config)
    } else {
        run_nm_mode(config)
    }
}

/// 独立模式：不依赖浏览器扩展，直接运行
fn run_standalone(config: Config) -> anyhow::Result<()> {
    log::info!("进入独立模式");

    // 注册全局热键
    let hotkey_tx = hotkey::register_hotkeys(&config)?;

    // 启动截图/OCR/翻译循环
    let ocr_engine = ocr::OcrEngine::new(&config)?;
    let translate_engine = translate::TranslateEngine::new(&config)?;

    let window = window::OverlayWindow::new(&config)?;

    let screenshot = screenshot::DxgiScreenshotter::new()?;

    while RUNNING.load(Ordering::Seq) {
        // 等待热键触发
        if let Some(region) = hotkey::wait_for_capture(&hotkey_tx) {
            // 截图
            log::info!("开始截图");
            let img_data = screenshot.capture_region(region)?;

            // OCR 识别
            log::info!("开始 OCR 识别");
            let text = ocr_engine.recognize(&img_data)?;

            // 翻译
            let translation = if !text.is_empty() {
                translate_engine.translate(&text)?
            } else {
                String::new()
            };

            // 浮窗显示
            window.show_translation(&region, &text, &translation)?;
        }
    }

    Ok(())
}

/// Native Messaging 模式：与浏览器扩展通信
fn run_nm_mode(config: Config) -> anyhow::Result<()> {
    log::info!("进入 Native Messaging 模式");

    let mut nm = nm::NmConnection::new();

    while RUNNING.load(Ordering::Seq) {
        // 读取浏览器扩展发来的消息
        let msg = match nm.read_message()? {
            Some(m) => m,
            None => break, // 连接断开
        };

        log::info!("收到消息: {:?}", msg);

        match msg {
            NmMessage::Translate { text, .. } => {
                let config = config.clone();
                let result = handle_translate(&config, text);
                nm.write_message(&NmResponse::Translate(result))?;
            }
            NmMessage::Ocr { data_url, .. } => {
                let config = config.clone();
                let result = handle_ocr(&config, data_url);
                nm.write_message(&NmResponse::Ocr(result))?;
            }
            NmMessage::Capture => {
                // 触发截图（与独立模式共享逻辑）
            }
            NmMessage::GetSettings => {
                let settings = config.to_json();
                nm.write_message(&NmResponse::Settings(settings))?;
            }
            NmMessage::UpdateSettings { settings } => {
                // 更新配置
                log::info!("更新配置: {:?}", settings);
            }
        }
    }

    Ok(())
}

/// 处理翻译请求
fn handle_translate(config: &Config, text: String) -> String {
    let engine = translate::TranslateEngine::new(config).unwrap_or_default();
    engine.translate(&text).unwrap_or_else(|e| {
        log::error!("翻译失败: {}", e);
        format!("翻译失败: {}", e)
    })
}

/// 处理 OCR 请求
fn handle_ocr(config: &Config, data_url: String) -> String {
    // 从 data_url 解码图片
    let img_data = match screenshot::decode_data_url(&data_url) {
        Ok(d) => d,
        Err(e) => return format!("图片解码失败: {}", e),
    };

    let engine = ocr::OcrEngine::new(config).unwrap_or_default();
    engine.recognize(&img_data).unwrap_or_else(|e| {
        log::error!("OCR 失败: {}", e);
        format!("OCR 失败: {}", e)
    })
}

// Ctrl+C 处理
#[cfg(windows)]
fn setup_ctrlc_handler() {
    use winapi::um::consolectrl::{SetConsoleCtrlHandler, HandlerRoutine, CTRL_C_EVENT};
    unsafe {
        SetConsoleCtrlHandler(Some(ctrlc_handler), TRUE);
    }
}

#[cfg(windows)]
unsafe extern "system" fn ctrlc_handler(ctrl_type: u32) -> i32 {
    if ctrl_type == CTRL_C_EVENT {
        RUNNING.store(false, Ordering::SeqCst);
        1
    } else {
        0
    }
}

#[cfg(not(windows))]
fn setup_ctrlc_handler() {}
