//! 浮窗绘制模块（winit + wgpu 置顶透明窗口）
//! 在截图区域附近显示原文 + 译文

use crate::config::Config;
use crate::hotkey::Region;

pub struct OverlayWindow {
    config: Config,
    // winit event loop 和 wgpu surface（延迟初始化）
    // event_loop: Option<winit::event_loop::EventLoop<()>>,
    // window: Option<winit::window::Window>,
}

impl OverlayWindow {
    pub fn new(config: &Config) -> Result<Self> {
        Ok(Self {
            config: config.clone(),
        })
    }

    /// 显示翻译结果浮窗
    pub fn show_translation(&self, region: &Region, original: &str, translation: &str) {
        // 创建置顶透明窗口
        // 1. 初始化 winit event loop
        // 2. 创建窗口（置顶、透明、无边框）
        // 3. 使用 wgpu 绘制原文 + 译文
        // 4. 自动关闭（60 秒后）

        // 简化实现：使用 Windows API 直接绘制
        // TODO: 完整的 wgpu 浮窗实现
        log::info!(
            "浮窗显示: 区域=({},{},{}x{}), 原文={}, 译文={}",
            region.x, region.y, region.w, region.h,
            original, translation
        );

        // 暂时使用 MessageBox 作为占位（后续替换为真正的浮窗）
        // 实际实现需要 winit + wgpu
    }

    /// 关闭浮窗
    pub fn hide(&self) {
        // 销毁窗口
    }
}
