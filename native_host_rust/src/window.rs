//! Overlay Window Module (WinAPI Layered Window + GDI Drawing)
//! Displays original text + translation near the screenshot region

use crate::hotkey::Region;
use anyhow::Result;
use std::mem;
use std::ptr;
use std::sync::Mutex;
use winapi::shared::windef::HWND;
use winapi::um::wingdi::{
    CreateFontW, CreatePen, DeleteObject, GetStockObject, SelectObject, SetBkMode, SetTextColor,
    TextOutW, FW_NORMAL, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
    TRANSPARENT, RGB, WHITE_BRUSH,
};
use winapi::um::winuser::{
    BeginPaint, CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW, EndPaint,
    GetClientRect, GetDC, GetMessageW, LoadCursorW, PostQuitMessage, RegisterClassW, ReleaseDC,
    SetLayeredWindowAttributes, ShowWindow, TranslateMessage, UpdateWindow, CS_HREDRAW, CS_VREDRAW,
    IDC_ARROW, LWA_ALPHA, MSG, SW_SHOW, WM_CLOSE, WM_DESTROY, WM_KEYDOWN, WM_LBUTTONDOWN,
    WM_PAINT, WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP, WS_VISIBLE,
};

// Global text buffer for window drawing
static OVERLAY_TEXT: Mutex<String> = Mutex::new(String::new());
static OVERLAY_TITLE: Mutex<String> = Mutex::new(String::new());

/// Overlay window manager
pub struct OverlayWindow {
    hwnd: Option<HWND>,
}

impl OverlayWindow {
    pub fn new(_config: &crate::config::Config) -> Result<Self> {
        Ok(Self { hwnd: None })
    }

    /// Show translation result overlay
    pub fn show_translation(&mut self, region: &Region, original: &str, translation: &str) {
        self.hide();

        // Position: below the screenshot region
        let x = region.x;
        let y = region.y + region.h + 10;
        let w = region.w.max(300).min(600);
        let h = calculate_text_height(original, translation);

        let title = "WinOCR Translation".to_string();
        let text = format!("Original: {}\nTranslation: {}", original, translation);

        // Store text for WM_PAINT
        if let Ok(mut t) = OVERLAY_TEXT.lock() {
            *t = text.clone();
        }
        if let Ok(mut t) = OVERLAY_TITLE.lock() {
            *t = title.clone();
        }

        let hwnd = create_overlay_window(x, y, w, h, &title);
        self.hwnd = Some(hwnd);
    }

    /// Show custom message overlay
    #[allow(dead_code)]
    pub fn show_message(&mut self, x: i32, y: i32, message: &str) {
        self.hide();

        let w = 300i32.min(message.len() as i32 * 10 + 40).max(200);
        let h = calculate_text_height(message, "");

        if let Ok(mut t) = OVERLAY_TEXT.lock() {
            *t = message.to_string();
        }
        if let Ok(mut t) = OVERLAY_TITLE.lock() {
            *t = "WinOCR".to_string();
        }

        let hwnd = create_overlay_window(x, y, w, h, "WinOCR");
        self.hwnd = Some(hwnd);
    }

    /// Close overlay
    pub fn hide(&mut self) {
        if let Some(hwnd) = self.hwnd {
            unsafe {
                DestroyWindow(hwnd);
            }
            self.hwnd = None;
        }
    }
}

/// Calculate required text height
fn calculate_text_height(text1: &str, text2: &str) -> i32 {
    let lines = if text2.is_empty() {
        text1.lines().count().max(1)
    } else {
        text1.lines().count() + text2.lines().count()
    };
    (lines as i32 * 24) + 40 // 24px per line + padding
}

/// Create layered overlay window
fn create_overlay_window(x: i32, y: i32, w: i32, h: i32, title: &str) -> HWND {
    unsafe {
        let class_name = encode_wide("WinOCROverlayWindow");
        let title_wide = encode_wide(title);

        // Register window class
        let wnd_class = winapi::um::winuser::WNDCLASSW {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(window_proc),
            hInstance: ptr::null_mut(),
            hCursor: LoadCursorW(ptr::null_mut(), IDC_ARROW),
            hbrBackground: GetStockObject(WHITE_BRUSH as i32) as *mut _,
            lpszClassName: class_name.as_ptr(),
            lpszMenuName: ptr::null_mut(),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hIcon: ptr::null_mut(),
        };

        RegisterClassW(&wnd_class);

        // Create layered popup window
        let hwnd = CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
            class_name.as_ptr(),
            title_wide.as_ptr(),
            WS_POPUP | WS_VISIBLE,
            x,
            y,
            w,
            h,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
        );

        if hwnd.is_null() {
            return ptr::null_mut();
        }

        // Set transparency (90% opaque)
        SetLayeredWindowAttributes(hwnd, RGB(0, 0, 0), 230, LWA_ALPHA);

        // Show window
        ShowWindow(hwnd, SW_SHOW);
        UpdateWindow(hwnd);

        // Message loop (30 second timeout)
        let mut msg: MSG = mem::zeroed();
        let start_time = std::time::Instant::now();
        let timeout = std::time::Duration::from_secs(30);

        while GetMessageW(&mut msg, ptr::null_mut(), 0, 0) > 0 {
            if start_time.elapsed() > timeout {
                break;
            }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        hwnd
    }
}

/// Draw rounded rectangle background
fn draw_rounded_rect(hdc: winapi::shared::windef::HDC, x: i32, y: i32, w: i32, h: i32) {
    unsafe {
        // Create dark background brush
        let bg_brush = winapi::um::wingdi::CreateSolidBrush(RGB(30, 30, 30));
        let border_pen = CreatePen(winapi::um::wingdi::PS_SOLID as i32, 1, RGB(80, 80, 80));

        let old_brush = SelectObject(hdc, bg_brush as *mut _);
        let old_pen = SelectObject(hdc, border_pen as *mut _);

        // Draw filled rectangle
        winapi::um::wingdi::Rectangle(hdc, x, y, x + w, y + h);

        SelectObject(hdc, old_brush);
        SelectObject(hdc, old_pen);

        DeleteObject(bg_brush as *mut _);
        DeleteObject(border_pen as *mut _);
    }
}

/// Draw text with proper formatting
fn draw_overlay_content(hwnd: HWND) {
    unsafe {
        let hdc = GetDC(hwnd);
        if hdc.is_null() {
            return;
        }

        let mut rect = mem::zeroed::<winapi::shared::windef::RECT>();
        GetClientRect(hwnd, &mut rect);

        // Draw background
        draw_rounded_rect(
            hdc,
            rect.left,
            rect.top,
            rect.right - rect.left,
            rect.bottom - rect.top,
        );

        // Set text properties
        SetBkMode(hdc, TRANSPARENT as i32);
        SetTextColor(hdc, RGB(255, 255, 255));

        // Create font
        let font = CreateFontW(
            16, 0, 0, 0,
            FW_NORMAL,
            0, 0, 0,
            DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS,
            CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY,
            0,
            encode_wide("Microsoft YaHei").as_ptr(),
        );

        let old_font = SelectObject(hdc, font as *mut _);

        // Create title font (larger)
        let title_font = CreateFontW(
            18, 0, 0, 0,
            FW_NORMAL + 300, // Semi-bold
            0, 0, 0,
            DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS,
            CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY,
            0,
            encode_wide("Microsoft YaHei").as_ptr(),
        );

        // Get stored text
        let text = match OVERLAY_TEXT.lock() {
            Ok(guard) => guard.clone(),
            Err(_) => String::new(),
        };
        let title = match OVERLAY_TITLE.lock() {
            Ok(guard) => guard.clone(),
            Err(_) => String::new(),
        };

        // Draw title
        if !title.is_empty() {
            SelectObject(hdc, title_font as *mut _);
            SetTextColor(hdc, RGB(0, 180, 255)); // Blue title
            let title_wide = encode_wide(&title);
            TextOutW(
                hdc,
                12,
                8,
                title_wide.as_ptr(),
                (title_wide.len() as i32 - 1).max(0),
            );
            SelectObject(hdc, font as *mut _);
            SetTextColor(hdc, RGB(255, 255, 255));
        }

        // Draw content text
        let mut y_offset = 32i32;
        for line in text.lines() {
            let line_wide = encode_wide(line);
            if !line_wide.is_empty() {
                TextOutW(
                    hdc,
                    12,
                    y_offset,
                    line_wide.as_ptr(),
                    (line_wide.len() as i32 - 1).max(0),
                );
            }
            y_offset += 22;
        }

        // Cleanup
        SelectObject(hdc, old_font);
        DeleteObject(font as *mut _);
        DeleteObject(title_font as *mut _);
        ReleaseDC(hwnd, hdc);
    }
}

/// Window procedure
unsafe extern "system" fn window_proc(
    hwnd: HWND,
    msg: u32,
    wparam: usize,
    lparam: isize,
) -> isize {
    match msg {
        WM_PAINT => {
            let mut ps: winapi::um::winuser::PAINTSTRUCT = mem::zeroed();
            let _hdc = BeginPaint(hwnd, &mut ps);
            draw_overlay_content(hwnd);
            EndPaint(hwnd, &ps);
            0
        }
        WM_LBUTTONDOWN => {
            // Close on click
            DestroyWindow(hwnd);
            0
        }
        WM_KEYDOWN => {
            // Close on ESC or Enter
            if wparam == 27 || wparam == 13 {
                // ESC = 27, Enter = 13
                DestroyWindow(hwnd);
            }
            0
        }
        WM_CLOSE => {
            DestroyWindow(hwnd);
            0
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

/// Encode string to wide characters
fn encode_wide(s: &str) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    std::ffi::OsString::from(s)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect()
}
