//! 热键设置窗口（Win32 控件版）
//! standalone 模式下按设置热键弹出，修改截图/设置/退出热键，保存后立即生效

use crate::config::Config;
use std::mem;
use std::ptr;
use winapi::shared::minwindef::{LOWORD, WPARAM};
use winapi::shared::windef::HWND;
use winapi::um::wingdi::{GetStockObject, DEFAULT_GUI_FONT};
use winapi::um::winuser::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW, GetDlgItem,
    GetMessageW, LoadCursorW, MessageBoxW, PostQuitMessage, RegisterClassW, SendMessageW,
    SetFocus, ShowWindow, TranslateMessage, CS_HREDRAW, CS_VREDRAW, IDC_ARROW, MSG,
    SW_SHOW, WM_CLOSE, WM_COMMAND, WM_DESTROY, WM_SETFONT, WS_CHILD, WS_EX_CLIENTEDGE,
    WS_OVERLAPPEDWINDOW, WS_VISIBLE, WNDCLASSW,
};

// 控件 ID
const IDC_EDIT_CAPTURE: i32 = 101;
const IDC_EDIT_SETTINGS: i32 = 102;
const IDC_EDIT_QUIT: i32 = 103;
const IDC_BTN_SAVE: i32 = 201;
const IDC_BTN_CANCEL: i32 = 202;

// 样式常量（winapi 中 BS_/ES_ 分散在各模块，直接用数值）
const STYLE_BUTTON: u32 = 0x0000_0001; // BS_PUSHBUTTON
const STYLE_EDIT: u32 = 0x0080_0000; // ES_AUTOHSCROLL

/// 保存结果：(capture, settings, quit)
static RESULT: std::sync::Mutex<Option<(String, String, String)>> =
    std::sync::Mutex::new(None);

/// 弹出设置窗口（模态），返回 Some(新热键三元组) 表示用户点了保存
pub fn show_settings(config: &Config) -> Option<(String, String, String)> {
    unsafe {
        let class_name = to_wide("WinOCRSettingsWindow");
        let wnd_class = WNDCLASSW {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(settings_proc),
            hInstance: ptr::null_mut(),
            hCursor: LoadCursorW(ptr::null_mut(), IDC_ARROW),
            hbrBackground: GetStockObject(6 /* COLOR_WINDOW+1 as brush */) as *mut _,
            lpszClassName: class_name.as_ptr(),
            lpszMenuName: ptr::null_mut(),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hIcon: ptr::null_mut(),
        };
        RegisterClassW(&wnd_class);

        let title = to_wide("WinOCR-Html 设置");
        let hwnd = CreateWindowExW(
            0,
            class_name.as_ptr(),
            title.as_ptr(),
            WS_OVERLAPPEDWINDOW,
            380, 260, 460, 340,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
        );
        if hwnd.is_null() {
            return None;
        }

        let hfont = GetStockObject(DEFAULT_GUI_FONT as i32);

        // 标题说明
        create_control(hwnd, "STATIC", "全局热键设置（修改后点击保存立即生效）", 20, 15, 400, 20, -1, hfont, 0);
        // 三个热键行
        create_control(hwnd, "STATIC", "截图 OCR 热键：", 20, 55, 130, 20, -1, hfont, 0);
        let edit_capture = create_control(hwnd, "EDIT", &config.hotkey, 160, 52, 260, 24, IDC_EDIT_CAPTURE, hfont, WS_EX_CLIENTEDGE | STYLE_EDIT);
        create_control(hwnd, "STATIC", "打开本设置窗口：", 20, 95, 130, 20, -1, hfont, 0);
        let _edit_settings = create_control(hwnd, "EDIT", &config.settings_hotkey, 160, 92, 260, 24, IDC_EDIT_SETTINGS, hfont, WS_EX_CLIENTEDGE | STYLE_EDIT);
        create_control(hwnd, "STATIC", "退出程序热键：", 20, 135, 130, 20, -1, hfont, 0);
        let _edit_quit = create_control(hwnd, "EDIT", &config.quit_hotkey, 160, 132, 260, 24, IDC_EDIT_QUIT, hfont, WS_EX_CLIENTEDGE | STYLE_EDIT);

        // 格式提示
        create_control(hwnd, "STATIC", "格式：修饰键+主键，如 ctrl+alt+s、alt+q、f2", 20, 180, 420, 20, -1, hfont, 0);
        create_control(hwnd, "STATIC", "主键支持：字母、数字、F1-F12；修饰键：ctrl / alt / shift / win", 20, 200, 420, 20, -1, hfont, 0);

        // 按钮
        create_control(hwnd, "BUTTON", "保存", 240, 240, 90, 32, IDC_BTN_SAVE, hfont, STYLE_BUTTON);
        create_control(hwnd, "BUTTON", "取消", 340, 240, 90, 32, IDC_BTN_CANCEL, hfont, STYLE_BUTTON);

        ShowWindow(hwnd, SW_SHOW);
        SetFocus(edit_capture);

        // 模态消息循环
        let mut msg: MSG = mem::zeroed();
        while GetMessageW(&mut msg, ptr::null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }

    RESULT.lock().ok().and_then(|r| r.clone())
}

/// 创建子控件，返回 HWND
unsafe fn create_control(
    parent: HWND,
    class: &str,
    text: &str,
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    id: i32,
    hfont: *mut std::ffi::c_void,
    style_extra: u32,
) -> HWND {
    let class_w = to_wide(class);
    let text_w = to_wide(text);
    let hwnd = CreateWindowExW(
        0,
        class_w.as_ptr(),
        text_w.as_ptr(),
        WS_CHILD | WS_VISIBLE | style_extra,
        x,
        y,
        w,
        h,
        parent,
        id as *mut _,
        ptr::null_mut(),
        ptr::null_mut(),
    );
    if !hfont.is_null() {
        SendMessageW(hwnd, WM_SETFONT, hfont as WPARAM, 1);
    }
    hwnd
}

/// 读取 Edit 控件文本
unsafe fn read_edit(hwnd_dialog: HWND, id: i32) -> String {
    let hwnd = GetDlgItem(hwnd_dialog, id);
    if hwnd.is_null() {
        return String::new();
    }
    let len = winapi::um::winuser::GetWindowTextLengthW(hwnd);
    if len <= 0 {
        return String::new();
    }
    let mut buf = vec![0u16; (len + 1) as usize];
    let n = winapi::um::winuser::GetWindowTextW(hwnd, buf.as_mut_ptr(), len + 1);
    String::from_utf16_lossy(&buf[..n.max(0) as usize])
}

unsafe extern "system" fn settings_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: isize,
) -> isize {
    match msg {
        WM_COMMAND => {
            let id = LOWORD(wparam as u32) as i32;
            // 只响应控件通知（lparam 非空）且通知码为 BN_CLICKED(0)
            if lparam != 0 && ((wparam >> 16) & 0xFFFF) == 0 {
                match id {
                    IDC_BTN_SAVE => {
                        let capture = read_edit(hwnd, IDC_EDIT_CAPTURE).trim().to_lowercase();
                        let settings = read_edit(hwnd, IDC_EDIT_SETTINGS).trim().to_lowercase();
                        let quit = read_edit(hwnd, IDC_EDIT_QUIT).trim().to_lowercase();
                        if capture.is_empty() || settings.is_empty() || quit.is_empty() {
                            MessageBoxW(
                                hwnd,
                                to_wide("三个热键都不能为空").as_ptr(),
                                to_wide("提示").as_ptr(),
                                0x30, // MB_ICONWARNING
                            );
                            return 0;
                        }
                        if let Ok(mut r) = RESULT.lock() {
                            *r = Some((capture, settings, quit));
                        }
                        DestroyWindow(hwnd);
                    }
                    IDC_BTN_CANCEL => {
                        DestroyWindow(hwnd);
                    }
                    _ => {}
                }
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

/// &str -> UTF-16 Vec（含 NUL 结尾）
fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}
