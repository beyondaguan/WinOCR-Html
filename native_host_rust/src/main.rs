//! WinOCR-Html 本地壳程序（Rust 版）
//! 职责：全局截图 + PP-OCRv6 OCR + 翻译 + 浮窗显示
//! 通过 Native Messaging 与浏览器扩展通信

mod config;
mod hotkey;
mod nm;
mod ocr;
mod screenshot;
mod translate;
mod whisper;
mod window;

use clap::Parser;
use config::Config;
use nm::NmHandler;
use std::sync::atomic::{AtomicBool, Ordering};
use base64::Engine;

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
    log::info!("配置加载完成");

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
    let _hotkey_tx = hotkey::register_hotkeys(&config)?;

    // 启动截图/OCR/翻译循环
    let mut ocr_engine = ocr::OcrEngine::new(&config)?;
    let translate_engine = translate::TranslateEngine::new(&config)?;

    let mut window = window::OverlayWindow::new(&config)?;

    let screenshot = screenshot::DxgiScreenshotter::new()?;

    let hotkey_rx = {
        let (_tx, rx) = std::sync::mpsc::channel();
        rx
    };

    while RUNNING.load(Ordering::SeqCst) {
        // 等待热键触发
        match hotkey_rx.recv() {
            Ok(hotkey::HotkeyEvent::Capture) => {
                // 截图
                log::info!("开始截图");
                let img_data = screenshot.capture_region(hotkey::Region::default())?;

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
                window.show_translation(&hotkey::Region::default(), &text, &translation);
            }
            Ok(hotkey::HotkeyEvent::Quit) => {
                log::info!("退出热键触发");
                break;
            }
            Ok(hotkey::HotkeyEvent::Translate) => {
                log::info!("翻译热键触发（占位）");
            }
            Ok(hotkey::HotkeyEvent::Settings) => {
                log::info!("设置热键触发（占位）");
            }
            Err(_) => break,
        }
    }

    Ok(())
}

/// Native Messaging 模式：与浏览器扩展通信
fn run_nm_mode(config: Config) -> anyhow::Result<()> {
    log::info!("进入 Native Messaging 模式");

    let handler = NmModeHandler::new(config)?;
    nm::run_nm_loop(&handler)?;

    Ok(())
}

/// NM 模式消息处理器
struct NmModeHandler {
    config: Config,
}

impl NmModeHandler {
    fn new(config: Config) -> anyhow::Result<Self> {
        Ok(Self { config })
    }
}

impl NmHandler for NmModeHandler {
    fn handle_translate(
        &self,
        text: &str,
        _source_lang: Option<&str>,
        _target_lang: Option<&str>,
    ) -> anyhow::Result<String> {
        let engine = translate::TranslateEngine::new(&self.config)?;
        let result = engine.translate(text)?;
        log::info!("翻译结果: {} -> {}", text.chars().take(50).collect::<String>(), result.chars().take(50).collect::<String>());
        Ok(result)
    }

    fn handle_ocr(&self, data_url: &str) -> anyhow::Result<(String, Option<f32>)> {
        let img_data = screenshot::decode_data_url(data_url)?;
        let mut engine = ocr::OcrEngine::new(&self.config)?;
        let text = engine.recognize(&img_data)?;
        log::info!("OCR 结果: {} 字符", text.len());
        Ok((text, None))
    }

    fn handle_capture(&self, region: Option<&nm::NmRegion>) -> anyhow::Result<Option<String>> {
        let screenshot = screenshot::DxgiScreenshotter::new()?;
        let region = region.cloned().unwrap_or_default().into();
        let pixels = screenshot.capture_region(region)?;
        // 这里可以编码为 base64 返回
        let encoded = base64::engine::general_purpose::STANDARD.encode(&pixels);
        Ok(Some(format!("data:image/png;base64,{}", encoded)))
    }

    fn handle_get_settings(&self) -> anyhow::Result<serde_json::Value> {
        let json = self.config.to_json();
        Ok(serde_json::Value::String(json))
    }

    fn handle_update_settings(&self, settings: &serde_json::Value) -> anyhow::Result<()> {
        log::info!("更新配置: {:?}", settings);
        // TODO: 实现配置更新逻辑
        Ok(())
    }

    fn handle_region_crop(&self, data_url: &str, _region: &nm::NmRegion) -> anyhow::Result<String> {
        let img_data = screenshot::decode_data_url(data_url)?;
        let mut engine = ocr::OcrEngine::new(&self.config)?;
        let text = engine.recognize(&img_data)?;
        Ok(text)
    }
}
