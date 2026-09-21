# -*- coding: utf-8 -*-
"""screenshot.py — 截屏模块（从 winocr_host.py 拆出）

两种实现：
  1. PIL.ImageGrab（DXGI Desktop Duplication）—— 本机 DWM/驱动组合下唯一能截到内容的
  2. GDI BitBlt（零依赖兜底）—— 某些机器上 ImageGrab 黑图时的最后手段

公开函数：
  screenshot_png_bytes(x, y, w, h) -> bytes|None
"""

import io
import os
import time
import ctypes
import struct
import zlib

# --------------------- 常量 ---------------------
SCREENSHOT_DELAY_MS = 200       # 遮罩残影等待（do_capture 里 time.sleep 用）
BITMAPINFOHEADER_SIZE = 40
BITMAP_PLANES = 1
BITMAP_BPP = 32
BITMAP_ZLIB_LEVEL = 6
SRCCOPY = 0x00CC0020
BI_RGB = 0


def _get_screen_size():
    """获取主屏幕尺寸（兼容多显示器）。"""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def screenshot_png_bytes(x, y, w, h):
    """截取指定矩形区域，返回 PNG bytes。失败返回 None。

    坐标已经过边界裁剪（调用方负责）。
    """
    SW, SH = _get_screen_size()
    if x >= SW or y >= SH:
        return None
    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, min(int(w), SW - x))
    h = max(1, min(int(h), SH - y))

    # 1) ImageGrab（DXGI Desktop Duplication）
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        buf = io.BytesIO()
        im.save(buf, format='PNG')
        data = buf.getvalue()
        if data:
            return data
    except Exception as e:
        pass  # 静默回退 BitBlt

    # 2) BitBlt 兜底
    return _screenshot_bitblt(x, y, w, h)


def _screenshot_bitblt(x, y, w, h):
    """GDI BitBlt 截屏（零依赖兜底）。返回 PNG bytes 或 None。"""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hwnd = user32.GetDesktopWindow()
    hdc_screen = user32.GetWindowDC(hwnd)
    if not hdc_screen:
        return None
    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        if not hdc_mem:
            return None
        try:
            hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            if not hbitmap:
                return None
            try:
                gdi32.SelectObject(hdc_mem, hbitmap)
                gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, SRCCOPY)

                # BITMAPINFOHEADER
                hdr = struct.pack('<IiiHHIIiiII', BITMAPINFOHEADER_SIZE, w, h,
                                  BITMAP_PLANES, BITMAP_BPP, BI_RGB, 0, 0, 0, 0, 0)
                row_size = ((w * 3 + 3) // 4) * 4
                pixels = b''
                for i in range(h):
                    row = ctypes.string_at(
                        gdi32.GetBitmapBits(hbitmap, w * 4, None) if False else
                        _get_row(gdi32, hbitmap, w, h, i),
                        row_size)
                    pixels += row

                # BMP → PNG（用 zlib 手工压缩，避免依赖 PIL）
                raw = b''.join(
                    b'\x00' + pixels[i * row_size:(i + 1) * row_size]
                    for i in range(h))
                compressed = zlib.compress(raw, BITMAP_ZLIB_LEVEL)

                def chunk(tag, data):
                    c = struct.pack('>I', len(data)) + tag + data
                    c += struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
                    return c

                ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
                png = (b'\x89PNG\r\n\x1a\n'
                       + chunk(b'IHDR', ihdr)
                       + chunk(b'IDAT', compressed)
                       + chunk(b'IEND', b''))
                return png
            finally:
                gdi32.DeleteObject(hbitmap)
        finally:
            gdi32.DeleteDC(hdc_mem)
    finally:
        user32.ReleaseDC(hwnd, hdc_screen)
    return None


def _get_row(gdi32, hbitmap, w, h, i):
    """从 BMP 中读取一行像素（BGR 格式）。"""
    buf = ctypes.create_string_buffer(w * 3)
    gdi32.GetBitmapBits(hbitmap, w * 3, buf)
    return buf.raw
