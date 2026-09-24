//! 全局热键注册与监听（Windows RegisterHotKey）
//! 支持 Ctrl+Shift+M 截图、Ctrl+Alt+Q 退出

use crate::config::Config;
use std::sync::mpsc::{channel, Sender};
use std::sync::Mutex;
use winapi::um::winuser::{
    RegisterHotKey, UnregisterHotKey, GetMessageW, TranslateMessage, DispatchMessageW,
    MSG, PM_REMOVE, WM_HOTKEY,
};
use winapi::um::winbase::GetMessageW as GetMessage;
use winapi::shared::minwindef::{UINT, WPARAM, LPARAM, LRESULT};
use winapi::shared::windef::HWND;
use winapi::um::winuser::MOD_CONTROL;
use winapi::um::winuser::MOD_SHIFT;
use winapi::um::winuser::MOD_ALT;
use winapi::ctypes::c_int;

pub const HOTKEY_ID_CAPTURE: UINT = 1;
pub const HOTKEY_ID_QUIT: UINT = 2;

/// 解析热键字符串（如 "ctrl+shift+m"）为修饰键 + 主键
fn parse_hotkey(hotkey: &str) -> (UINT, u16) {
    let parts: Vec<&str> = hotkey.split('+').collect();
    let mut modifiers = 0u32;
    let mut key_code = 0u16;

    for part in &parts {
        let part = part.trim().to_lowercase();
        match part.as_str() {
            "ctrl" | "control" => modifiers |= MOD_CONTROL,
            "shift" => modifiers |= MOD_SHIFT,
            "alt" => modifiers |= MOD_ALT,
            "win" | "meta" => modifiers |= winapi::um::winuser::MOD_WIN,
            _ => {
                // 主键：取第一个字符的虚拟键码
                if let Some(ch) = part.chars().next() {
                    key_code = ch as u16;
                }
            }
        }
    }

    (modifiers, key_code)
}

/// 注册全局热键，返回消息通道的 Sender
pub fn register_hotkeys(config: &Config) -> anyhow::Result<Sender<HotkeyEvent>> {
    let (capture_mod, capture_key) = parse_hotkey(&config.hotkey);
    let (quit_mod, quit_key) = parse_hotkey(&config.quit_hotkey);

    let (tx, rx) = channel::<HotkeyEvent>();

    // 注册热键（需要一个窗口句柄，用 desktop window）
    unsafe {
        let hwnd = std::ptr::null_mut::<winapi::shared::windef::HWND__>();
        if RegisterHotKey(hwnd, HOTKEY_ID_CAPTURE as c_int, capture_mod, capture_key as UINT) == 0 {
            log::warn!("注册截图热键失败，可能已被占用");
        }
        if RegisterHotKey(hwnd, HOTKEY_ID_QUIT as c_int, quit_mod, quit_key as UINT) == 0 {
            log::warn!("注册退出热键失败，可能已被占用");
        }
    }

    // 启动热键监听线程
    std::thread::spawn(move || {
        let mut msg: MSG = unsafe { std::mem::zeroed() };
        unsafe {
            while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {
                if msg.message == WM_HOTKEY {
                    let id = msg.wParam as UINT;
                    match id {
                        HOTKEY_ID_CAPTURE => {
                            let _ = tx.send(HotkeyEvent::Capture);
                        }
                        HOTKEY_ID_QUIT => {
                            let _ = tx.send(HotkeyEvent::Quit);
                        }
                        _ => {}
                    }
                }
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }
    });

    Ok(rx)
}

#[derive(Debug, Clone, Copy)]
pub enum HotkeyEvent {
    Capture,
    Quit,
}

/// 等待截图事件（阻塞）
pub fn wait_for_capture(rx: &std::sync::mpsc::Receiver<HotkeyEvent>) -> Option<Region> {
    match rx.recv() {
        Ok(HotkeyEvent::Capture) => Some(Region::default()),
        _ => None,
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct Region {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}
