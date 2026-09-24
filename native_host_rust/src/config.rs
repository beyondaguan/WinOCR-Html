//! 配置管理：加载、保存、默认值

use anyhow::Context;
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(default)]
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
    pub settings_hotkey: String,
    pub mymemory_email: String,
    pub ollama_url: String,
    pub ollama_model: String,
    pub native_host: bool,
    pub model_dir: String,
    pub proxy_url: String,
    pub models: ModelsConfig,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(default)]
pub struct ModelsConfig {
    pub base_url: String,
    pub proxy_enabled: bool,
}

impl Default for ModelsConfig {
    fn default() -> Self {
        Self {
            base_url: "https://hf-mirror.com".to_string(),
            proxy_enabled: true,
        }
    }
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

impl OcrTier {
    /// 根据模型类型返回 ONNX 文件名
    pub fn model_name(&self, kind: &str) -> String {
        match self {
            OcrTier::Tiny => format!("{}_tiny.onnx", kind),
            OcrTier::Small => format!("{}_small.onnx", kind),
            OcrTier::Medium => format!("{}_medium.onnx", kind),
        }
    }
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
            hotkey: "alt+q".to_string(),
            quit_hotkey: "ctrl+alt+q".to_string(),
            settings_hotkey: "ctrl+alt+s".to_string(),
            mymemory_email: String::new(),
            ollama_url: "http://localhost:11434".to_string(),
            ollama_model: String::new(),
            native_host: false,
            model_dir: "models/ocr".to_string(),
            proxy_url: "http://127.0.0.1:7890".to_string(),
            models: ModelsConfig::default(),
        }
    }
}

/// 默认配置文件路径：exe 同目录下的 winocr_config.json
pub fn default_config_path() -> anyhow::Result<String> {
    let exe = std::env::current_exe().context("获取 exe 路径失败")?;
    let dir = exe.parent().context("获取 exe 目录失败")?;
    Ok(dir
        .join("winocr_config.json")
        .to_string_lossy()
        .into_owned())
}

impl Config {
    pub fn load(path: Option<&str>) -> anyhow::Result<Self> {
        let owned;
        let path: &str = match path {
            Some(p) => p,
            // 默认配置文件锚定 exe 所在目录（NM 模式下 cwd 不可控）
            None => {
                owned = default_config_path()?;
                &owned
            }
        };
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
