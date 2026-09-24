//! PP-OCRv6 ONNX 推理模块
//! 基于 onnxruntime crate，支持 det/rec/cls 三模型推理

use crate::config::{Config, OcrTier};
use anyhow::Result;
use std::path::PathBuf;

pub struct OcrEngine {
    tier: OcrTier,
    model_dir: PathBuf,
    // onnxruntime 会话（延迟初始化）
    // det_session: Option<onnxruntime::Session>,
    // rec_session: Option<onnxruntime::Session>,
    // cls_session: Option<onnxruntime::Session>,
}

impl OcrEngine {
    pub fn new(config: &Config) -> Result<Self> {
        let tier = config.local_ocr_tier.clone();
        let model_dir = PathBuf::from(&config.model_dir);
        Ok(Self {
            tier,
            model_dir,
        })
    }

    /// 识别图片中的文本
    pub fn recognize(&self, img_data: &[u8]) -> Result<String> {
        // 1. 加载图片
        let img = image::load_from_memory(img_data)
            .map_err(|e| anyhow::anyhow!("图片加载失败: {}", e))?;

        // 2. 预处理（resize + 归一化 + BGR 通道转换）
        let processed = self.preprocess(&img)?;

        // 3. 检测（DBNet）
        let boxes = self.detect(&processed)?;

        // 4. 识别（CTC 解码）
        let text = self.recognize_text(&img, &boxes)?;

        // 5. 后处理（几何重排 + CJK 拼接 + 低置信过滤）
        let result = self.postprocess(text);

        Ok(result)
    }

    fn preprocess(&self, img: &image::DynamicImage) -> Result<ProcessedImage> {
        // 小图放大（宽或高 < 400px 时放大 2 倍）
        let (w, h) = (img.width() as i32, img.height() as i32);
        let img = if w.min(h) < 400 {
            img.resize_exact((w * 2) as u32, (h * 2) as u32, image::imageops::FilterType::Lanczos3)
        } else {
            img
        };

        // 转为 RGB
        let rgb = img.to_rgb8();
        Ok(ProcessedImage {
            width: rgb.width() as i32,
            height: rgb.height() as i32,
            data: rgb.into_raw(),
        })
    }

    fn detect(&self, _img: &ProcessedImage) -> Result<Vec<DetectedBox>> {
        // DBNet 推理（需要 onnxruntime）
        // TODO: 实现检测推理
        Ok(Vec::new())
    }

    fn recognize_text(&self, _img: &image::DynamicImage, _boxes: &[DetectedBox]) -> Result<Vec<TextLine>> {
        // CTC 解码 + 字典映射
        // TODO: 实现识别推理
        Ok(Vec::new())
    }

    fn postprocess(&self, lines: Vec<TextLine>) -> String {
        // 几何重排 + CJK 拼接 + 低置信过滤
        let mut result = String::new();
        for line in lines {
            if line.score < 0.6 {
                continue; // 低置信过滤
            }
            if !result.is_empty() {
                result.push('\n');
            }
            result.push_str(&line.text);
        }
        result
    }
}

struct ProcessedImage {
    width: i32,
    height: i32,
    data: Vec<u8>,
}

struct DetectedBox {
    points: [(f32, f32); 4],
    score: f32,
}

struct TextLine {
    text: String,
    score: f32,
}
