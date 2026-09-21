#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""屏幕截图 + 本地 OCR 端到端诊断（一次性）。

排查「壳按 Alt+Q 提示未识别到文字，怀疑没走 OCR 引擎」：
  1. DPI 感知状态 / 逻辑 vs 物理分辨率（坐标系错位会让 BitBlt 截到空白区）；
  2. 用宿主**同一个** screenshot_png_bytes() 截全屏，落盘 data/_diag_full.png；
  3. 像素统计：全黑/全白/颜色数（BitBlt 对硬件加速表面可能截出黑屏）；
  4. 用宿主**同一个** ocr_local.recognize_png() 跑识别，打印耗时/置信度/文本。

结果写 data/_diag_capture.json（避免 939 控制台吞中文），控制台只打 ascii 摘要。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOST = os.path.join(ROOT, "native_host")
sys.path.insert(0, HOST)

import winocr_host as W   # noqa: E402  复用宿主的截图函数（import 会触发解释器自举说明）


def main():
    import ctypes
    user32 = ctypes.windll.user32

    info = {"interpreter": sys.executable}

    # ---- DPI / 分辨率 ----
    try:
        info["isProcessDPIAware"] = bool(user32.IsProcessDPIAware())
    except Exception as e:
        info["isProcessDPIAware"] = "err:%s" % e
    try:
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        info["logicalPX_W"] = gdi32.GetDeviceCaps(hdc, 8)   # HORZRES
        info["logicalPX_H"] = gdi32.GetDeviceCaps(hdc, 10)  # VERTRES
        user32.ReleaseDC(0, hdc)
    except Exception as e:
        info["logicalPX_err"] = str(e)
    info["GetSystemMetrics"] = [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)]
    try:
        info["GetDpiForSystem"] = user32.GetDpiForSystem()
    except Exception:
        info["GetDpiForSystem"] = None

    # ---- 截全屏（宿主同款函数）----
    t0 = time.time()
    png = W.screenshot_png_bytes(0, 0, None, None)
    info["capture_ms"] = round((time.time() - t0) * 1000)
    info["png_bytes"] = len(png or b"")

    out_png = os.path.join(HOST, "data", "_diag_full.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    with open(out_png, "wb") as f:
        f.write(png)
    info["png_saved"] = out_png

    # ---- 像素体检：黑屏/白屏/单色检测 ----
    try:
        import io as _io
        from PIL import Image
        with Image.open(_io.BytesIO(png)) as im:
            im.load()
            info["pil_size"] = list(im.size)
            info["pil_mode"] = im.mode
            small = im.convert("RGB").resize((64, 64))
            colors = small.getcolors(64 * 64)
            n_colors = len(colors) if colors else -1
            px = list(small.getdata())
            n_black = sum(1 for r, g, b in px if r < 8 and g < 8 and b < 8)
            n_white = sum(1 for r, g, b in px if r > 247 and g > 247 and b > 247)
            info["sample_colors"] = n_colors
            info["sample_black_pct"] = round(100.0 * n_black / len(px), 1)
            info["sample_white_pct"] = round(100.0 * n_white / len(px), 1)
    except Exception as e:
        info["pixel_check_err"] = "%s: %s" % (type(e).__name__, e)

    # ---- 本地 OCR（宿主同款引擎）----
    try:
        import ocr_local
        ok, why = ocr_local.available()
        info["ocr_available"] = ok
        info["ocr_reason"] = why
        if ok:
            t0 = time.time()
            text, conf = ocr_local.recognize_png(png, W.SETTINGS.get("localOcrTier") or "tiny")
            info["ocr_ms"] = round((time.time() - t0) * 1000)
            info["ocr_conf"] = round(conf, 4)
            info["ocr_chars"] = len(text)
            info["ocr_text_head"] = text[:300]
            txt_out = os.path.join(HOST, "data", "_diag_ocr.txt")
            with open(txt_out, "w", encoding="utf-8") as f:
                f.write(text)
            info["ocr_text_saved"] = txt_out
    except Exception as e:
        info["ocr_err"] = "%s: %s" % (type(e).__name__, e)

    out_json = os.path.join(HOST, "data", "_diag_capture.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    # ascii 摘要（中文不打控制台）
    print("== capture diag ==")
    for k in ("interpreter", "isProcessDPIAware", "logicalPX_W", "logicalPX_H",
              "GetSystemMetrics", "GetDpiForSystem", "capture_ms", "png_bytes",
              "pil_size", "sample_colors", "sample_black_pct", "sample_white_pct",
              "ocr_available", "ocr_reason", "ocr_ms", "ocr_conf", "ocr_chars",
              "ocr_err"):
        if k in info:
            print("  %-20s: %s" % (k, info[k]))
    print("json: %s" % out_json)
    print("png : %s" % out_png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
