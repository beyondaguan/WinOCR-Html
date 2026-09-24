//! DXGI Desktop Duplication screenshot module
//! Uses windows crate for DXGI support

use crate::hotkey::Region;
use anyhow::Result;
use std::io::Cursor;
use std::mem;
use windows::Win32::Graphics::Direct3D::D3D_FEATURE_LEVEL;
use windows::Win32::Graphics::Direct3D11::{
    D3D11CreateDevice, ID3D11Device, ID3D11DeviceContext, ID3D11Texture2D,
    D3D11_CPU_ACCESS_READ, D3D11_MAP_READ, D3D11_MAPPED_SUBRESOURCE, D3D11_TEXTURE2D_DESC,
    D3D11_USAGE_STAGING,
};
use windows::Win32::Graphics::Dxgi::{
    IDXGIFactory1, IDXGIOutput1, IDXGIOutputDuplication,
    IDXGIResource, DXGI_OUTDUPL_FRAME_INFO, DXGI_OUTPUT_DESC,
};
use windows::Win32::System::Com::{CoInitializeEx, COINIT_MULTITHREADED};
use windows::core::Interface;
use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};

pub struct DxgiScreenshotter {
    device: Option<ID3D11Device>,
    context: Option<ID3D11DeviceContext>,
    duplication: Option<IDXGIOutputDuplication>,
    output_width: u32,
    output_height: u32,
}

impl DxgiScreenshotter {
    pub fn new() -> Result<Self> {
        let mut screenshotter = Self {
            device: None,
            context: None,
            duplication: None,
            output_width: 0,
            output_height: 0,
        };

        unsafe {
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        }

        match screenshotter.init_dxgi() {
            Ok(_) => {}
            Err(e) => {
                log::warn!("DXGI init failed: {}, falling back to GDI", e);
            }
        }

        Ok(screenshotter)
    }

    fn init_dxgi(&mut self) -> Result<()> {
        unsafe {
            let mut device: Option<ID3D11Device> = None;
            let mut context: Option<ID3D11DeviceContext> = None;
            let mut feature_level = D3D_FEATURE_LEVEL::default();

            D3D11CreateDevice(
                None,
                windows::Win32::Graphics::Direct3D::D3D_DRIVER_TYPE::default(),
                None,
                windows::Win32::Graphics::Direct3D11::D3D11_CREATE_DEVICE_FLAG(0),
                None,
                windows::Win32::Graphics::Direct3D11::D3D11_SDK_VERSION,
                Some(&mut device),
                Some(&mut feature_level),
                Some(&mut context),
            ).map_err(|e| anyhow::anyhow!("D3D11CreateDevice failed: {:?}", e))?;

            self.device = device;
            self.context = context;

            let factory: IDXGIFactory1 = windows::Win32::Graphics::Dxgi::CreateDXGIFactory1()
                .map_err(|e| anyhow::anyhow!("CreateDXGIFactory1 failed: {:?}", e))?;

            let adapter = factory.EnumAdapters1(0)
                .map_err(|e| anyhow::anyhow!("EnumAdapters1 failed: {:?}", e))?;

            let output = adapter.EnumOutputs(0)
                .map_err(|e| anyhow::anyhow!("EnumOutputs failed: {:?}", e))?;

            let desc: DXGI_OUTPUT_DESC = output.GetDesc()
                .map_err(|e| anyhow::anyhow!("GetDesc failed: {:?}", e))?;
            self.output_width = (desc.DesktopCoordinates.right - desc.DesktopCoordinates.left) as u32;
            self.output_height = (desc.DesktopCoordinates.bottom - desc.DesktopCoordinates.top) as u32;

            let output1: IDXGIOutput1 = output.cast()
                .map_err(|e| anyhow::anyhow!("Cast to IDXGIOutput1 failed: {:?}", e))?;

            let duplication = output1.DuplicateOutput(self.device.as_ref().unwrap())
                .map_err(|e| anyhow::anyhow!("DuplicateOutput failed: {:?}", e))?;

            self.duplication = Some(duplication);
            log::info!("DXGI initialized: {}x{}", self.output_width, self.output_height);

            Ok(())
        }
    }

    pub fn capture_region(&self, region: Region) -> Result<Vec<u8>> {
        let screen_w = unsafe { GetSystemMetrics(SM_CXSCREEN) };
        let screen_h = unsafe { GetSystemMetrics(SM_CYSCREEN) };
        let x = region.x.max(0).min(screen_w - 1);
        let y = region.y.max(0).min(screen_h - 1);
        let w = region.w.max(1).min(screen_w - x);
        let h = region.h.max(1).min(screen_h - y);

        if self.duplication.is_some() {
            match self.capture_dxgi(x, y, w, h) {
                Ok(data) => return Ok(data),
                Err(e) => log::warn!("DXGI capture failed: {}, falling back to GDI", e),
            }
        }

        self.capture_gdi(x, y, w, h)
    }

    fn capture_dxgi(&self, x: i32, y: i32, w: i32, h: i32) -> Result<Vec<u8>> {
        unsafe {
            let duplication = self.duplication.as_ref()
                .ok_or_else(|| anyhow::anyhow!("DXGI not initialized"))?;

            // 1. Acquire next frame
            let mut frame_info = DXGI_OUTDUPL_FRAME_INFO::default();
            let mut resource: Option<IDXGIResource> = None;
            duplication.AcquireNextFrame(1000, &mut frame_info, &mut resource)
                .map_err(|e| anyhow::anyhow!("AcquireNextFrame failed: {:?}", e))?;

            let resource = resource.ok_or_else(|| anyhow::anyhow!("Failed to get frame resource"))?;

            // 2. Get the texture from the resource
            let texture: ID3D11Texture2D = resource.cast()
                .map_err(|e| anyhow::anyhow!("Failed to cast to texture: {:?}", e))?;

            // 3. Get texture description
            let mut desc = D3D11_TEXTURE2D_DESC::default();
            texture.GetDesc(&mut desc);

            // 4. Create a staging texture for CPU read access
            let mut staging_desc = D3D11_TEXTURE2D_DESC::default();
            staging_desc.Height = desc.Height;  // Full desktop height
            staging_desc.Width = desc.Width;   // Full desktop width
            staging_desc.MipLevels = 1;
            staging_desc.ArraySize = 1;
            staging_desc.Format = desc.Format;
            staging_desc.SampleDesc = desc.SampleDesc;
            staging_desc.Usage = D3D11_USAGE_STAGING;
            staging_desc.BindFlags = 0;
            staging_desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ.0 as u32;
            staging_desc.MiscFlags = 0;

            let device = self.device.as_ref()
                .ok_or_else(|| anyhow::anyhow!("Device not initialized"))?;

            let mut staging: Option<ID3D11Texture2D> = None;
            device.CreateTexture2D(&staging_desc, None, Some(&mut staging))
                .map_err(|e| anyhow::anyhow!("CreateTexture2D failed: {:?}", e))?;

            let staging = staging.ok_or_else(|| anyhow::anyhow!("Failed to create staging texture"))?;

            // 5. Copy the full desktop to staging texture
            let context = self.context.as_ref()
                .ok_or_else(|| anyhow::anyhow!("Context not initialized"))?;

            context.CopyResource(&staging, &texture);

            // 6. Map the staging texture to read data
            let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
            context.Map(&staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))
                .map_err(|e| anyhow::anyhow!("Map failed: {:?}", e))?;

            // 7. Extract the requested region
            let row_pitch = mapped.RowPitch as usize;
            let data_ptr = mapped.pData as *const u8;
            let tex_h = desc.Height as usize;
            let tex_w = desc.Width as usize;
            let bytes_per_pixel = 4u32; // BGRA format

            let mut pixels = vec![0u8; (w * h * 3) as usize];

            for row in 0..h as usize {
                let src_y = (row as i32 + y).max(0).min(tex_h as i32 - 1) as usize;
                let src_offset = src_y * row_pitch;
                let dst_offset = row as usize * (w as usize) * 3;

                for col in 0..w as usize {
                    let src_x = (col as i32 + x).max(0).min(tex_w as i32 - 1) as usize;
                    let src_idx = src_offset + src_x * bytes_per_pixel as usize;
                    let dst_idx = dst_offset + col as usize * 3;

                    if dst_idx + 2 < pixels.len() && src_idx + 3 < row_pitch * tex_h {
                        pixels[dst_idx] = *data_ptr.add(src_idx + 2); // R
                        pixels[dst_idx + 1] = *data_ptr.add(src_idx + 1); // G
                        pixels[dst_idx + 2] = *data_ptr.add(src_idx);     // B
                    }
                }
            }

            // 8. Cleanup
            context.Unmap(&staging, 0);
            let _ = duplication.ReleaseFrame();

            Ok(pixels)
        }
    }

    fn capture_gdi(&self, x: i32, y: i32, w: i32, h: i32) -> Result<Vec<u8>> {
        use windows::Win32::Graphics::Gdi::{
            BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject,
            GetDIBits, GetDC, ReleaseDC, SelectObject,
        };

        unsafe {
            let hdc_screen = GetDC(None);
            if hdc_screen.is_invalid() {
                return Err(anyhow::anyhow!("GetDC failed"));
            }
            let hdc_mem = CreateCompatibleDC(hdc_screen);
            if hdc_mem.is_invalid() {
                ReleaseDC(None, hdc_screen);
                return Err(anyhow::anyhow!("CreateCompatibleDC failed"));
            }
            let hbitmap = CreateCompatibleBitmap(hdc_screen, w, h);
            if hbitmap.is_invalid() {
                let _ = DeleteDC(hdc_mem);
                ReleaseDC(None, hdc_screen);
                return Err(anyhow::anyhow!("CreateCompatibleBitmap failed"));
            }
            SelectObject(hdc_mem, hbitmap);
            let _ = BitBlt(
                hdc_mem, 0, 0, w, h,
                hdc_screen, x, y,
                windows::Win32::Graphics::Gdi::SRCCOPY,
            );

            let row_size = ((w * 3 + 3) / 4) * 4;
            let mut pixels = vec![0u8; (row_size * h) as usize];
            let mut bmi = windows::Win32::Graphics::Gdi::BITMAPINFO::default();
            bmi.bmiHeader.biSize = mem::size_of::<windows::Win32::Graphics::Gdi::BITMAPINFOHEADER>() as u32;
            bmi.bmiHeader.biWidth = w;
            bmi.bmiHeader.biHeight = -h;
            bmi.bmiHeader.biPlanes = 1;
            bmi.bmiHeader.biBitCount = 24;
            bmi.bmiHeader.biCompression = windows::Win32::Graphics::Gdi::BI_RGB.0;

            let result = GetDIBits(
                hdc_mem,
                hbitmap,
                0,
                h as u32,
                Some(pixels.as_mut_ptr() as *mut _),
                &mut bmi,
                windows::Win32::Graphics::Gdi::DIB_RGB_COLORS,
            );

            let _ = DeleteObject(hbitmap);
            let _ = DeleteDC(hdc_mem);
            ReleaseDC(None, hdc_screen);

            if result == 0 {
                return Err(anyhow::anyhow!("GetDIBits failed"));
            }

            Ok(pixels)
        }
    }
}

impl Drop for DxgiScreenshotter {
    fn drop(&mut self) {
        if let Some(dup) = &self.duplication {
            unsafe {
                let _ = dup.ReleaseFrame();
            }
        }
    }
}

pub fn decode_data_url(data_url: &str) -> Result<Vec<u8>> {
    use base64::Engine;
    let encoded = data_url
        .split(',')
        .nth(1)
        .ok_or_else(|| anyhow::anyhow!("Invalid data_url"))?;
    let data = base64::engine::general_purpose::STANDARD.decode(encoded)?;
    Ok(data)
}

/// Encode pixel data to PNG format
#[allow(dead_code)]
pub fn encode_png(pixels: &[u8], w: i32, h: i32) -> Result<Vec<u8>> {
    use image::ImageBuffer;
    let img: image::RgbImage = ImageBuffer::from_raw(w as u32, h as u32, pixels.to_vec())
        .ok_or_else(|| anyhow::anyhow!("Invalid image data"))?;
    let mut buf = Vec::new();
    let mut cursor = Cursor::new(&mut buf);
    img.write_to(&mut cursor, image::ImageFormat::Png)?;
    Ok(buf)
}
