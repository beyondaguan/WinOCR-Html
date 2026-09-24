//! Native Messaging 通信协议
//! 与浏览器扩展通过 stdin/stdout 通信（4 字节小端序长度前缀 + UTF-8 JSON）

use crate::config::Config;
use serde::{Deserialize, Serialize};
use std::io::{self, Read, Write};

pub const NM_MAX_MESSAGE_SIZE: usize = 10 * 1024 * 1024; // 10MB

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NmMessage {
    Translate {
        text: String,
        #[serde(default)]
        source_lang: Option<String>,
        #[serde(default)]
        target_lang: Option<String>,
    },
    Ocr {
        data_url: String,
        #[serde(default)]
        timeout_ms: Option<u64>,
    },
    Capture,
    GetSettings,
    UpdateSettings {
        settings: serde_json::Value,
    },
    RegionCrop {
        data_url: String,
    },
    #[serde(other)]
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NmResponse {
    Translate(String),
    Ocr(String),
    Settings(serde_json::Value),
    CaptureAck,
    Error(String),
    Hello {
        version: String,
        pid: u32,
        ocr_engine: String,
    },
}

pub struct NmConnection;

impl NmConnection {
    pub fn new() -> Self {
        Self
    }

    /// 从 stdin 读取一条 NM 消息
    pub fn read_message(&mut self) -> anyhow::Result<Option<NmMessage>> {
        let mut len_buf = [0u8; 4];
        if io::stdin().read_exact(&mut len_buf).is_err() {
            return Ok(None); // 连接断开
        }
        let len = u32::from_le_bytes(len_buf) as usize;
        if len > NM_MAX_MESSAGE_SIZE {
            return Err(anyhow::anyhow!("消息过大: {} 字节", len));
        }
        let mut buf = vec![0u8; len];
        io::stdin().read_exact(&mut buf)?;
        let msg: NmMessage = serde_json::from_slice(&buf)?;
        Ok(Some(msg))
    }

    /// 向 stdout 写入一条 NM 响应
    pub fn write_message(&mut self, resp: &NmResponse) -> anyhow::Result<()> {
        let data = serde_json::to_vec(resp)?;
        let len = (data.len() as u32).to_le_bytes();
        io::stdout().write_all(&len)?;
        io::stdout().write_all(&data)?;
        io::stdout().flush()?;
        Ok(())
    }
}
