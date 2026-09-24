//! 翻译引擎模块
//! 支持 SiliconFlow / MyMemory / Ollama 本地模型

use crate::config::Config;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::time::Duration;

pub struct TranslateEngine {
    config: Config,
    client: reqwest::blocking::Client,
}

impl TranslateEngine {
    pub fn new(config: &Config) -> Result<Self> {
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(120))
            .build()?;
        Ok(Self {
            config: config.clone(),
            client,
        })
    }

    pub fn translate(&self, text: &str) -> Result<String> {
        if text.trim().is_empty() {
            return Ok(String::new());
        }
        match self.config.translate_engine.as_str() {
            "sf" | "siliconflow" => self.translate_sf(text),
            "mymemory" => self.translate_mymemory(text),
            "ollama" => self.translate_ollama(text),
            "none" => Ok(String::new()),
            _ => self.translate_sf(text),
        }
    }

    fn translate_sf(&self, text: &str) -> Result<String> {
        #[derive(Serialize)]
        struct SfRequest {
            model: String,
            messages: Vec<SfMessage>,
            temperature: f32,
            max_tokens: u32,
        }
        #[derive(Serialize, Deserialize)]
        struct SfMessage {
            role: String,
            content: String,
        }
        #[derive(Deserialize)]
        struct SfResponse {
            choices: Vec<SfChoice>,
        }
        #[derive(Deserialize)]
        struct SfChoice {
            message: SfMessageContent,
        }
        #[derive(Deserialize)]
        struct SfMessageContent {
            content: String,
        }

        let sys = format!(
            "You are a professional translator. Translate the user text into {}. Keep medical/technical terms accurate. Output ONLY the translation, no commentary, no quotes.",
            self.config.tgt_lang
        );
        let body = SfRequest {
            model: self.config.sf_model.clone(),
            messages: vec![
                SfMessage { role: "system".into(), content: sys },
                SfMessage { role: "user".into(), content: text.to_string() },
            ],
            temperature: 0.3,
            max_tokens: 4096,
        };
        let url = format!("{}/chat/completions", self.config.sf_url.trim_end_matches('/'));
        let resp: SfResponse = self.client
            .post(&url)
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Bearer {}", self.config.sf_key))
            .json(&body)
            .send()?
            .json()?;
        let out = resp.choices.first()
            .map(|c| c.message.content.trim().to_string())
            .filter(|s| !s.is_empty())
            .ok_or_else(|| anyhow::anyhow!("SiliconFlow 返回空内容"))?;
        Ok(out)
    }

    fn translate_mymemory(&self, text: &str) -> Result<String> {
        // 简单 URL 编码
        let encoded_text = url_encode(text);
        let encoded_email = url_encode(&self.config.mymemory_email);
        let url = format!(
            "https://api.mymemory.translated.net/get?q={}&langpair={}|{}&de={}",
            encoded_text,
            self.config.src_lang,
            self.config.tgt_lang,
            encoded_email
        );
        #[derive(Deserialize)]
        struct MmResponse {
            #[serde(rename = "responseData")]
            response_data: MmData,
        }
        #[derive(Deserialize)]
        struct MmData {
            #[serde(rename = "translatedText")]
            translated_text: String,
        }
        let resp: MmResponse = self.client.get(&url).send()?.json()?;
        let out = resp.response_data.translated_text.trim().to_string();
        if out.is_empty() {
            return Err(anyhow::anyhow!("MyMemory 返回空内容"));
        }
        Ok(out)
    }

    fn translate_ollama(&self, text: &str) -> Result<String> {
        if self.config.ollama_model.is_empty() {
            return Err(anyhow::anyhow!("未选择 Ollama 模型"));
        }
        #[derive(Serialize)]
        struct OllamaRequest {
            model: String,
            prompt: String,
            stream: bool,
        }
        #[derive(Deserialize)]
        struct OllamaResponse {
            response: String,
        }
        let body = OllamaRequest {
            model: self.config.ollama_model.clone(),
            prompt: format!(
                "Translate the following text into {}. Keep medical/technical terms accurate. Output ONLY the translation:\n\n{}",
                self.config.tgt_lang, text
            ),
            stream: false,
        };
        let url = format!("{}/api/generate", self.config.ollama_url.trim_end_matches('/'));
        let resp: OllamaResponse = self.client
            .post(&url)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()?
            .json()?;
        let out = resp.response.trim().to_string();
        if out.is_empty() {
            return Err(anyhow::anyhow!("Ollama 返回空内容"));
        }
        Ok(out)
    }
}

impl Default for TranslateEngine {
    fn default() -> Self {
        Self::new(&Config::default()).unwrap_or_else(|_| Self {
            config: Config::default(),
            client: reqwest::blocking::Client::new(),
        })
    }
}

/// 简单 URL 编码（百分编码）
fn url_encode(input: &str) -> String {
    let mut result = String::new();
    for byte in input.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                result.push(byte as char);
            }
            _ => {
                result.push_str(&format!("%{:02X}", byte));
            }
        }
    }
    result
}
