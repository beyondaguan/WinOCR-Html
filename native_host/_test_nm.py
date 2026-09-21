# -*- coding: utf-8 -*-
"""NM 协议 harness：像浏览器那样用管道拉起 winocr_host.py，真实跑一轮
settings / hello / ocr 往返，验证本地 OCR 通道与宿主状态。

注意：宿主的 save_config() 会把收到的 settings 持久化进 winocr_config.json
（这是正常功能），所以本脚本**测前快照、测后还原**该文件 —— 否则假 key 会覆盖真 key。

用法：python _test_nm.py
"""

import base64
import io
import json
import os
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe"
HOST = os.path.join(HERE, "winocr_host.py")
CFG = os.path.join(HERE, "winocr_config.json")

sys.path.insert(0, HERE)
from PIL import Image, ImageDraw, ImageFont   # noqa: E402

# ---------------- 造一张"已知答案"的测试图 ----------------
im = Image.new("RGB", (860, 120), "white")
d = ImageDraw.Draw(im)
f = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 30)
d.text((20, 20), "Urinalysis: WBC 12 /HPF, nitrite positive.", fill="black", font=f)
try:
    fc = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 28)
except Exception:
    fc = f
d.text((20, 72), "患者因急性尿潴留入院。", fill="black", font=fc)
_buf = io.BytesIO()
im.save(_buf, "PNG")
DATA_URL = "data:image/png;base64," + base64.b64encode(_buf.getvalue()).decode()
WANT = ["Urinalysis", "nitrite", "尿潴留"]

fails = []


def check(name, cond, extra=""):
    print(("[OK]   " if cond else "[FAIL] ") + name + (("  -> " + str(extra)) if extra else ""), flush=True)
    if not cond:
        fails.append(name)


# ---------------- 预清理 + 快照 ----------------
# 宿主有单实例保护：不清掉已有实例，这里会被正确拒绝而"测不出东西"。
try:
    import winocr_host as _H
    if _H.find_running_hosts():
        print("检测到已有宿主在运行，先结束它们（单实例保护要求同时只有一个）…", flush=True)
        _H.stop_running_hosts()
        time.sleep(1.0)
except Exception as e:
    print("  (跳过预清理：%s)" % e, flush=True)

_cfg_backup = None
try:
    with open(CFG, "rb") as fh:
        _cfg_backup = fh.read()
except Exception:
    pass

print("启动宿主（管道模式，等价于浏览器拉起）…", flush=True)
proc = subprocess.Popen([PY, HOST], cwd=HERE, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

inbox = []
lock = threading.Lock()


def reader():
    while True:
        raw = proc.stdout.read(4)
        if len(raw) < 4:
            break
        n = struct.unpack("<I", raw)[0]
        data = proc.stdout.read(n)
        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        with lock:
            inbox.append((time.time(), msg))
        print("  <- %s" % json.dumps(msg, ensure_ascii=False)[:200], flush=True)


threading.Thread(target=reader, daemon=True).start()


def send(obj):
    data = json.dumps(obj).encode("utf-8")
    proc.stdin.write(struct.pack("<I", len(data)) + data)
    proc.stdin.flush()


def wait_for(pred, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with lock:
            for ts, m in inbox:
                if pred(m):
                    return m
        if proc.poll() is not None:
            return None
        time.sleep(0.1)
    return None


try:
    time.sleep(1.2)
    # 1) 发设置（模拟扩展保存后同步）—— 用一眼可辨的假 key
    send({"type": "settings", "settings": {
        "ocrEngine": "local", "localOcrTier": "tiny",
        "sfKey": "sk-TEST-not-a-real-key", "sfUrl": "https://api.siliconflow.cn/v1",
        "sfModel": "Qwen/Qwen3-8B", "sfOcrModel": "PaddlePaddle/PaddleOCR-VL-1.5",
        "srcLang": "zh", "tgtLang": "en", "hotkey": "ctrl+alt+m"}})
    time.sleep(0.8)

    # 2) 热键切换是否真的生效（旧版曾因局部变量 bug 从不注销旧键）
    hk = wait_for(lambda m: m.get("type") == "hello" and m.get("hotkey") == "ctrl+alt+m", 6)
    check("同步新热键后 hello 已更新为 ctrl+alt+m", hk is not None)

    # 3) OCR 往返
    t0 = time.time()
    send({"type": "ocr", "id": "o1", "dataUrl": DATA_URL})
    res = wait_for(lambda m: m.get("type") == "ocr.result" and m.get("id") == "o1", 120)
    dt = time.time() - t0
    check("收到 ocr.result", res is not None, "超时" if res is None else "")
    if res:
        check("ocr.result 无 error", not res.get("error"), res.get("error"))
        text = res.get("text") or ""
        print("      本地 OCR 用时 %.2fs" % dt, flush=True)
        print("      文本: %s" % text.replace("\n", " | "), flush=True)
        for w in WANT:
            check("识别出 %r" % w, w in text)

    # 4) 错误路径：空 dataUrl 应该回 error 而不是静默
    send({"type": "ocr", "id": "o2", "dataUrl": ""})
    res2 = wait_for(lambda m: m.get("type") == "ocr.result" and m.get("id") == "o2", 90)
    check("空图片返回 ocr.result", res2 is not None)
    if res2:
        e = res2.get("error") or ""
        check("空图片 → 报 error（不静默）", bool(e) and "OCR失败" in e, e)

    # 5) hello 是否上报 OCR 引擎与退出键
    h = wait_for(lambda m: m.get("type") == "hello" and m.get("quitHotkey"), 2)
    if h:
        check("hello 带 ocrDesc", bool(h.get("ocrDesc")), h.get("ocrDesc"))
        check("hello 带 quitHotkey", bool(h.get("quitHotkey")), h.get("quitHotkey"))
    else:
        print("  (未收到带 quitHotkey 的 hello —— 沙箱里热键注册可能失败，不影响 OCR 结论)", flush=True)

    # 6) 进程仍然存活（NM 宿主应常驻）
    check("宿主仍然存活（常驻，不自行退出）", proc.poll() is None, proc.poll())

finally:
    try:
        proc.kill()
    except Exception:
        pass
    # 还原配置：宿主的 save_config 会把测试 settings 写进 winocr_config.json
    if _cfg_backup is not None:
        try:
            with open(CFG, "wb") as fh:
                fh.write(_cfg_backup)
            print("  (已还原 winocr_config.json)", flush=True)
        except Exception as e:
            print("  [WARN] 还原配置失败：%s" % e, flush=True)
    err = proc.stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("\n--- stderr ---\n" + err[:1500], flush=True)

print("\n==> %d 项失败" % len(fails), flush=True)
sys.exit(1 if fails else 0)
