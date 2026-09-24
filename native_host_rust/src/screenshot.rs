//! DXGI Desktop Duplication 截图模块
//! 优先使用 DXGI，失败时回退到 GDI BitBlt

use crate::hotkey::Region;
use anyhow::Result;
use std::ptr;
use winapi::um::winuser::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};

pub struct DxgiScreenshotter {
    // DXGI 接口（延迟初始化）
    // 实际实现需要 d3d11/dxgi crate
}

impl DxgiScreenshotter {
    pub fn new() -> Result<Self> {
        Ok(Self {})
    }

    /// 截取指定区域（优先 DXGI，回退 GDI）
    pub fn capture_region(&self, region: Region) -> Result<Vec<u8>> {
        // 获取屏幕尺寸
        let screen_w = unsafe { GetSystemMetrics(SM_CXSCREEN) };
        let screen_h = unsafe { GetSystemMetrics(SM_CYSCREEN) };

        let x = region.x.max(0).min(screen_w - 1);
        let y = region.y.max(0).min(screen_h - 1);
        let w = region.w.max(1).min(screen_w - x);
        let h = region.h.max(1).min(screen_h - y);

        // 尝试 DXGI Desktop Duplication
        if let Ok(data) = self.capture_dxgi(x, y, w, h) {
            return Ok(data);
        }

        // 回退：GDI BitBlt
        self.capture_gdi(x, y, w, h)
    }

    fn capture_dxgi(&self, _x: i32, _y: i32, _w: i32, _h: i32) -> Result<Vec<u8>> {
        // DXGI 实现（需要 d3d11/dxgi crate 绑定）
        // TODO: 实现 IDXGIOutputDuplication::AcquireNextFrame
        Err(anyhow::anyhow!("DXGI 截图尚未实现"))
    }

    fn capture_gdi(&self, x: i32, y: i32, w: i32, h: i32) -> Result<Vec<u8>> {
        use winapi::um::wingdi::{
            BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject,
            GetDIBits, SelectObject,
        };
        use winapi::um::winuser::{GetDC, ReleaseDC};

        unsafe {
            let hdc_screen = GetDC(ptr::null_mut());
            if hdc_screen.is_null() {
                return Err(anyhow::anyhow!("GetDC 失败"));
            }
            let hdc_mem = CreateCompatibleDC(hdc_screen);
            if hdc_mem.is_null() {
                ReleaseDC(ptr::null_mut(), hdc_screen);
                return Err(anyhow::anyhow!("CreateCompatibleDC 失败"));
            }
            let hbitmap = CreateCompatibleBitmap(hdc_screen, w, h);
            if hbitmap.is_null() {
                DeleteDC(hdc_mem);
                ReleaseDC(ptr::null_mut(), hdc_screen);
                return Err(anyhow::anyhow!("CreateCompatibleBitmap 失败"));
            }
            SelectObject(hdc_mem, hbitmap as *mut _);
            BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, winapi::um::wingdi::SRCCOPY);

            // 读取像素数据
            let row_size = ((w * 3 + 3) / 4) * 4;
            let mut pixels = vec![0u8; (row_size * h) as usize];
            let mut bmi: winapi::um::wingdi::BITMAPINFO = std::mem::zeroed();
            bmi.bmiHeader.biSize = std::mem::size_of::<winapi::um::wingdi::BITMAPINFOHEADER>() as u32;
            bmi.bmiHeader.biWidth = w;
            bmi.bmiHeader.biHeight = -h; // 自上而下
            bmi.bmiHeader.biPlanes = 1;
            bmi.bmiHeader.biBitCount = 24;
            bmi.bmiHeader.biCompression = winapi::um::wingdi::BI_RGB;

            GetDIBits(
                hdc_mem,
                hbitmap as *mut _,
                0,
                h as u32,
                pixels.as_mut_ptr() as *mut _,
                &mut bmi,
                winapi::um::wingdi::DIB_RGB_COLORS,
            );

            DeleteObject(hbitmap as *mut _);
            DeleteDC(hdc_mem);
            ReleaseDC(ptr::null_mut(), hdc_screen);

            Ok(pixels)
        }
    }
}

/// 解码 data_url（base64 编码的图片）
pub fn decode_data_url(data_url: &str) -> Result<Vec<u8>> {
    use base64::Engine;
    let encoded = data_url
        .split(',')
        .nth(1)
        .ok_or_else(|| anyhow::anyhow!("无效的 data_url"))?;
    let data = base64::engine::general_purpose::STANDARD.decode(encoded)?;
    Ok(data)
}

/// 将像素数据编码为 PNG
pub fn encode_png(pixels: &[u8], w: i32, h: i32) -> Result<Vec<u8>> {
    use image::{ImageBuffer, RgbImage};
    let img: RgbImage = ImageBuffer::from_raw(w as u32, h as u32, pixels.to_vec())
        .ok_or_else(|| anyhow::anyhow!("图像数据无效"))?;
    let mut buf = Vec::new();
    img.write_to(&mut buf, image::ImageFormat::Png)?;
    Ok(buf)
}
