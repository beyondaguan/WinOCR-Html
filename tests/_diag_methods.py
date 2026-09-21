#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓屏方法对比：同一块屏幕区域，试 4 种抓法，看哪种不是黑屏。

纯黑 BitBlt 的常见原因：缺 CAPTUREBLT、DC 句柄取法、DWM/驱动组合。
每种方法保存 data/_diag_mN.png，并输出黑色占比。
"""
import ctypes
import os
import sys
import zlib
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOST = os.path.join(ROOT, "native_host")
DATA = os.path.join(HOST, "data")
os.makedirs(DATA, exist_ok=True)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
SW, SH = 300, 200   # 左上角 300x200 采样即可，快


def grab(x, y, w, h, hdc, rop, tag):
    hmem = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(hmem, hbmp)
    ok = gdi32.BitBlt(hmem, 0, 0, w, h, hdc, x, y, rop)
    bmi = ctypes.create_string_buffer(40)
    ctypes.memset(bmi, 0, 40)
    ctypes.cast(bmi, ctypes.POINTER(ctypes.c_int))[0] = 40
    ctypes.cast(bmi, ctypes.POINTER(ctypes.c_int))[1] = w
    ctypes.cast(bmi, ctypes.POINTER(ctypes.c_int))[2] = -h
    ctypes.cast(bmi, ctypes.POINTER(ctypes.c_short))[3] = 1
    ctypes.cast(bmi, ctypes.POINTER(ctypes.c_short))[4] = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hmem, hbmp, 0, h, buf, bmi, 0)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hmem)
    raw = bytes(buf)
    n_black = 0
    n = w * h
    for i in range(0, len(raw), 4):
        if raw[i + 2] < 8 and raw[i + 1] < 8 and raw[i] < 8:
            n_black += 1
    pct = round(100.0 * n_black / n, 1)

    # 存 PNG
    out = bytearray()
    for yy in range(h):
        out.append(0)
        row = raw[yy * w * 4:(yy + 1) * w * 4]
        for xx in range(w):
            i = xx * 4
            out += bytes((row[i + 2], row[i + 1], row[i], 255))
    comp = zlib.compress(bytes(out), 6)

    def chunk(typ, dt):
        c = typ + dt
        return struct.pack('>I', len(dt)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', comp) + chunk(b'IEND', b'')
    path = os.path.join(DATA, "_diag_m%s.png" % tag)
    with open(path, "wb") as f:
        f.write(png)
    print("  method %s: BitBlt=%s black=%5.1f%%  %s" % (tag, ok, pct, path))


def main():
    print("screen metrics:", user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    # M1: 宿主现用法 GetWindowDC(GetDesktopWindow) + SRCCOPY
    hwnd = user32.GetDesktopWindow()
    hdc = user32.GetWindowDC(hwnd)
    grab(0, 0, SW, SH, hdc, SRCCOPY, "1")
    user32.ReleaseDC(hwnd, hdc)
    # M2: GetDC(NULL) + SRCCOPY
    hdc = user32.GetDC(0)
    grab(0, 0, SW, SH, hdc, SRCCOPY, "2")
    # M3: GetDC(NULL) + SRCCOPY|CAPTUREBLT
    grab(0, 0, SW, SH, hdc, SRCCOPY | CAPTUREBLT, "3")
    user32.ReleaseDC(0, hdc)
    # M4: Pillow ImageGrab（内部即 GetDC(0)+CAPTUREBLT，实现成熟）
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab(bbox=(0, 0, SW, SH)).convert("RGB")
        px = list(im.getdata())
        nb = sum(1 for r, g, b in px if r < 8 and g < 8 and b < 8)
        p4 = os.path.join(DATA, "_diag_m4.png")
        im.save(p4)
        print("  method 4: ImageGrab black=%5.1f%%  %s" % (100.0 * nb / len(px), p4))
    except Exception as e:
        print("  method 4: ImageGrab ERR %s: %s" % (type(e).__name__, e))


if __name__ == "__main__":
    main()
