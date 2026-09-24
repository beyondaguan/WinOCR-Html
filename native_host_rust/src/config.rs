//! 配置管理：加载、保存、默认值

use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Config {
    pub sf_key: String,
    pub sf_url: String,
    pub sf_model: String,
    pub ocr_engine: OcrEngine,
    pub local_ocr_tier: OcrTier,
    pub src_lang: String,
    pub tgt_lang: String,
    pub translate_engine: String,
    pub hotkey: String,
    pub quit_hotkey: String,
    pub mymemory_email: String,
    pub ollama_url: String,
    pub ollama_model: String,
    pub native_host: bool,
    pub model_dir: String,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum OcrEngine {
    Local,
    Sf,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum OcrTier {
    Tiny,
    Small,
    Medium,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            sf_key: String::new(),
            sf_url: "https://api.siliconflow.cn/v1".to_string(),
            sf_model: "Qwen/Qwen3-8B".to_string(),
            ocr_engine: OcrEngine::Local,
            local_ocr_tier: OcrTier::Tiny,
            src_lang: "en".to_string(),
            tgt_lang: "zh".to_string(),
            translate_engine: "sf".to_string(),
            hotkey: "ctrl+shift+m".to_string(),
            quit_hotkey: "ctrl+alt+q".to_string(),
            mymemory_email: String::new(),
            ollama_url: "http://localhost:11434".to_string(),
            ollama_model: String::new(),
            native_host: false,
            model_dir: "models/ocr".to_string(),
        }
    }
}

impl Config {
    pub fn load(path: Option<&str>) -> anyhow::Result<Self> {
        let path = path.unwrap_or("winocr_config.json");
        if Path::new(path).exists() {
            let content = std::fs::read_to_string(path)?;
            let config: Config = serde_json::from_str(&content)?;
            Ok(config)
        } else {
            let config = Config::default();
            config.save(path)?;
            Ok(config)
        }
    }

    pub fn save(&self, path: &str) -> anyhow::Result<()> {
        let content = serde_json::to_string_pretty(self)?;
        std::fs::write(path, content)?;
        Ok(())
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).unwrap_or_default()
    }
}
