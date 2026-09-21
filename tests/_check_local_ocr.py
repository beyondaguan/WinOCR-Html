#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地 OCR 冒烟测试：给一张图，验证 rapidocr + PP-OCRv6 端到端可用。

    python tests/_check_local_ocr.py <image> [tier]

会打印依赖体检 + 冷/热耗时 + 置信度，并把识别文本写到
native_host/data/_ocr_probe.txt（避免 936 控制台吞中文）。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "native_host"))

import ocr_local  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("usage: _check_local_ocr.py <image> [tier]")
        return 2
    img = sys.argv[1]
    tier = sys.argv[2] if len(sys.argv) > 2 else "tiny"

    print("interpreter : %s" % sys.executable)
    st = ocr_local.status()
    print("available   : %s" % st["available"])
    print("reason      : %s" % st["reason"])
    print("tiers       : %s" % json.dumps(st["tiers"]))
    if not st["available"]:
        return 1

    t0 = time.time()
    text, conf = ocr_local.recognize_file(img, tier)
    cold = time.time() - t0
    print("cold        : %.2fs  conf=%.3f  chars=%d" % (cold, conf, len(text)))

    t0 = time.time()
    ocr_local.recognize_file(img, tier)
    print("warm        : %.2fs" % (time.time() - t0))

    out = os.path.join(ROOT, "native_host", "data", "_ocr_probe.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print("text written: %s" % out)
    print("preview     : %s" % text.replace("\n", " | ")[:120].encode("ascii", "replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
