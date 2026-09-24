//! Native Messaging Communication Protocol
//! Communicates with browser extension via stdin/stdout (4-byte little-endian length prefix + UTF-8 JSON)

use serde::{Deserialize, Serialize};
use std::io::{self, Read, Write};
use std::time::{Duration, Instant};

/// Maximum message size (10MB)
pub const NM_MAX_MESSAGE_SIZE: usize = 10 * 1024 * 1024;

/// Native Messaging protocol version
pub const NM_PROTOCOL_VERSION: &str = "1.0.0";

/// Message type tag for serialization
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NmMessage {
    /// Text translation request
    Translate {
        text: String,
        #[serde(default)]
        source_lang: Option<String>,
        #[serde(default)]
        target_lang: Option<String>,
        #[serde(default)]
        engine: Option<String>,
    },
    /// OCR recognition from image data URL
    Ocr {
        data_url: String,
        #[serde(default)]
        timeout_ms: Option<u64>,
    },
    /// Trigger screenshot capture
    Capture {
        #[serde(default)]
        region: Option<NmRegion>,
    },
    /// Get current settings
    GetSettings,
    /// Update settings
    UpdateSettings {
        settings: serde_json::Value,
    },
    /// Crop image by region
    RegionCrop {
        data_url: String,
        region: NmRegion,
    },
    /// Health check / ping
    Ping {
        #[serde(default)]
        timestamp: Option<u64>,
    },
    /// Get version info
    GetVersion,
    /// Initialize connection
    Init {
        #[serde(default)]
        extension_version: Option<String>,
    },
    /// Unknown message type
    #[serde(other)]
    Unknown,
}

/// Region for screenshot/crop
#[derive(Debug, Clone, Deserialize, Serialize, Default)]
pub struct NmRegion {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

/// Response type tag for serialization
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NmResponse {
    /// Translation result
    Translate {
        text: String,
        #[serde(default)]
        source_lang: Option<String>,
        #[serde(default)]
        target_lang: Option<String>,
    },
    /// OCR recognition result
    Ocr {
        text: String,
        #[serde(default)]
        confidence: Option<f32>,
    },
    /// Capture acknowledgment
    CaptureAck {
        #[serde(default)]
        data_url: Option<String>,
    },
    /// Current settings
    Settings(serde_json::Value),
    /// Error response
    Error {
        code: String,
        message: String,
    },
    /// Pong response (keep-alive)
    Pong {
        timestamp: u64,
        #[serde(default)]
        uptime_seconds: Option<u64>,
    },
    /// Version info
    Version {
        protocol_version: String,
        app_version: String,
        #[serde(default)]
        ocr_engine: Option<String>,
        #[serde(default)]
        translate_engines: Option<Vec<String>>,
    },
    /// Initialization complete
    InitAck {
        success: bool,
        #[serde(default)]
        capabilities: Option<Vec<String>>,
    },
}

/// Native Messaging connection manager
pub struct NmConnection {
    start_time: Instant,
    message_count: u64,
}

impl NmConnection {
    /// Create new NM connection
    pub fn new() -> Self {
        Self {
            start_time: Instant::now(),
            message_count: 0,
        }
    }

    /// Read a message from stdin (blocking)
    /// Returns None if connection is closed
    pub fn read_message(&mut self) -> anyhow::Result<Option<NmMessage>> {
        // Read 4-byte length prefix (little-endian)
        let mut len_buf = [0u8; 4];
        match io::stdin().read_exact(&mut len_buf) {
            Ok(_) => {}
            Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => return Ok(None),
            Err(e) => return Err(anyhow::anyhow!("读取消息长度失败: {}", e)),
        }

        let len = u32::from_le_bytes(len_buf) as usize;

        // Validate message size
        if len == 0 {
            return Err(anyhow::anyhow!("收到空消息"));
        }
        if len > NM_MAX_MESSAGE_SIZE {
            return Err(anyhow::anyhow!("消息过大: {} 字节 (最大 {} 字节)", len, NM_MAX_MESSAGE_SIZE));
        }

        // Read message body
        let mut buf = vec![0u8; len];
        io::stdin().read_exact(&mut buf)?;

        // Parse JSON
        let msg: NmMessage = match serde_json::from_slice(&buf) {
            Ok(m) => m,
            Err(e) => {
                log::error!("JSON 解析失败: {}", e);
                return Err(anyhow::anyhow!("消息解析失败: {}", e));
            }
        };

        self.message_count += 1;
        log::debug!("收到消息 #{}: {:?}", self.message_count, msg);

        Ok(Some(msg))
    }

    /// Write a response to stdout
    pub fn write_message(&mut self, resp: &NmResponse) -> anyhow::Result<()> {
        // Serialize to JSON
        let data = serde_json::to_vec(resp)?;

        // Validate size
        if data.len() > NM_MAX_MESSAGE_SIZE {
            return Err(anyhow::anyhow!(
                "响应过大: {} 字节 (最大 {} 字节)",
                data.len(),
                NM_MAX_MESSAGE_SIZE
            ));
        }

        // Write 4-byte length prefix (little-endian)
        let len = (data.len() as u32).to_le_bytes();
        io::stdout().write_all(&len)?;

        // Write message body
        io::stdout().write_all(&data)?;
        io::stdout().flush()?;

        log::debug!("发送响应: {:?}", resp);

        Ok(())
    }

    /// Send error response
    pub fn send_error(&mut self, code: &str, message: &str) -> anyhow::Result<()> {
        self.write_message(&NmResponse::Error {
            code: code.to_string(),
            message: message.to_string(),
        })
    }

    /// Send pong response
    pub fn send_pong(&mut self, timestamp: u64) -> anyhow::Result<()> {
        self.write_message(&NmResponse::Pong {
            timestamp,
            uptime_seconds: Some(self.start_time.elapsed().as_secs()),
        })
    }

    /// Get uptime in seconds
    #[allow(dead_code)]
    pub fn uptime(&self) -> Duration {
        self.start_time.elapsed()
    }

    /// Get total messages processed
    #[allow(dead_code)]
    pub fn message_count(&self) -> u64 {
        self.message_count
    }
}

impl Default for NmConnection {
    fn default() -> Self {
        Self::new()
    }
}

/// Message handler trait for processing NM messages
pub trait NmHandler: Send + Sync {
    /// Handle translate request
    fn handle_translate(
        &self,
        text: &str,
        source_lang: Option<&str>,
        target_lang: Option<&str>,
    ) -> anyhow::Result<String>;

    /// Handle OCR request
    fn handle_ocr(&self, data_url: &str) -> anyhow::Result<(String, Option<f32>)>;

    /// Handle capture request
    fn handle_capture(&self, region: Option<&NmRegion>) -> anyhow::Result<Option<String>>;

    /// Handle get settings
    fn handle_get_settings(&self) -> anyhow::Result<serde_json::Value>;

    /// Handle update settings
    fn handle_update_settings(&self, settings: &serde_json::Value) -> anyhow::Result<()>;

    /// Handle region crop
    fn handle_region_crop(&self, data_url: &str, region: &NmRegion) -> anyhow::Result<String>;
}

/// Process messages using handler
pub fn process_message(conn: &mut NmConnection, handler: &dyn NmHandler) -> anyhow::Result<bool> {
    let msg = match conn.read_message()? {
        Some(m) => m,
        None => return Ok(false), // Connection closed
    };

    match msg {
        NmMessage::Translate {
            text,
            source_lang,
            target_lang,
            ..
        } => {
            match handler.handle_translate(&text, source_lang.as_deref(), target_lang.as_deref()) {
                Ok(result) => {
                    conn.write_message(&NmResponse::Translate {
                        text: result,
                        source_lang,
                        target_lang,
                    })?;
                }
                Err(e) => {
                    conn.send_error("TRANSLATE_ERROR", &e.to_string())?;
                }
            }
        }
        NmMessage::Ocr { data_url, .. } => {
            match handler.handle_ocr(&data_url) {
                Ok((text, confidence)) => {
                    conn.write_message(&NmResponse::Ocr { text, confidence })?;
                }
                Err(e) => {
                    conn.send_error("OCR_ERROR", &e.to_string())?;
                }
            }
        }
        NmMessage::Capture { region } => {
            match handler.handle_capture(region.as_ref()) {
                Ok(data_url) => {
                    conn.write_message(&NmResponse::CaptureAck { data_url })?;
                }
                Err(e) => {
                    conn.send_error("CAPTURE_ERROR", &e.to_string())?;
                }
            }
        }
        NmMessage::GetSettings => {
            match handler.handle_get_settings() {
                Ok(settings) => {
                    conn.write_message(&NmResponse::Settings(settings))?;
                }
                Err(e) => {
                    conn.send_error("SETTINGS_ERROR", &e.to_string())?;
                }
            }
        }
        NmMessage::UpdateSettings { settings } => {
            match handler.handle_update_settings(&settings) {
                Ok(_) => {
                    conn.write_message(&NmResponse::InitAck {
                        success: true,
                        capabilities: None,
                    })?;
                }
                Err(e) => {
                    conn.send_error("UPDATE_ERROR", &e.to_string())?;
                }
            }
        }
        NmMessage::RegionCrop { data_url, region } => {
            match handler.handle_region_crop(&data_url, &region) {
                Ok(result) => {
                    conn.write_message(&NmResponse::Ocr {
                        text: result,
                        confidence: None,
                    })?;
                }
                Err(e) => {
                    conn.send_error("CROP_ERROR", &e.to_string())?;
                }
            }
        }
        NmMessage::Ping { timestamp } => {
            let ts = timestamp.unwrap_or_else(|| {
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs()
            });
            conn.send_pong(ts)?;
        }
        NmMessage::GetVersion => {
            conn.write_message(&NmResponse::Version {
                protocol_version: NM_PROTOCOL_VERSION.to_string(),
                app_version: env!("CARGO_PKG_VERSION").to_string(),
                ocr_engine: Some("PP-OCRv6".to_string()),
                translate_engines: Some(vec![
                    "siliconflow".to_string(),
                    "mymemory".to_string(),
                    "ollama".to_string(),
                ]),
            })?;
        }
        NmMessage::Init { extension_version } => {
            log::info!("浏览器扩展连接: {:?}", extension_version);
            conn.write_message(&NmResponse::InitAck {
                success: true,
                capabilities: Some(vec![
                    "translate".to_string(),
                    "ocr".to_string(),
                    "capture".to_string(),
                    "settings".to_string(),
                ]),
            })?;
        }
        NmMessage::Unknown => {
            conn.send_error("UNKNOWN_TYPE", "未知消息类型")?;
        }
    }

    Ok(true) // Continue processing
}

/// Default NM loop
pub fn run_nm_loop(handler: &dyn NmHandler) -> anyhow::Result<()> {
    let mut conn = NmConnection::new();

    log::info!("Native Messaging 循环启动");

    loop {
        match process_message(&mut conn, handler) {
            Ok(true) => continue,
            Ok(false) => {
                log::info!("连接关闭，退出");
                break;
            }
            Err(e) => {
                log::error!("处理消息错误: {}", e);
                // Try to send error response
                let _ = conn.send_error("INTERNAL_ERROR", &e.to_string());
            }
        }
    }

    Ok(())
}

/// Helper to convert crate::hotkey::Region to NmRegion
impl From<crate::hotkey::Region> for NmRegion {
    fn from(r: crate::hotkey::Region) -> Self {
        Self {
            x: r.x,
            y: r.y,
            width: r.w,
            height: r.h,
        }
    }
}

/// Helper to convert NmRegion to crate::hotkey::Region
impl From<NmRegion> for crate::hotkey::Region {
    fn from(r: NmRegion) -> Self {
        Self {
            x: r.x,
            y: r.y,
            w: r.width,
            h: r.height,
        }
    }
}
