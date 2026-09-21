# -*- coding: utf-8 -*-
"""一次性验证：NM 管道断开后，宿主【整个进程】必须退出，而不只是读取线程死掉。

旧 bug：nm_read_thread 末尾 sys.exit(0) 只结束 daemon 线程，Tk mainloop 仍在 →
进程不退、全局热键被僵尸独占，浏览器重连拉起的新宿主被单实例保护挡住。

流程：像浏览器一样用管道拉起宿主 → 等 hello（证明 Tk+热键线程都起来了）
     → 关闭 stdin（等价于浏览器断开）→ 期望进程在 8s 内自行退出。
"""
import json
import os
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOST_DIR = os.path.join(ROOT, "native_host")
HOST = os.path.join(HOST_DIR, "winocr_host.py")
PY = sys.executable

# 单实例保护：先清场
sys.path.insert(0, HOST_DIR)
try:
    import winocr_host as _H
    if _H.find_running_hosts():
        print("预清理：结束已在运行的宿主 …", flush=True)
        _H.stop_running_hosts()
        time.sleep(1.2)
except Exception as e:
    print("(预清理跳过: %s)" % e, flush=True)

print("管道模式拉起宿主 …", flush=True)
proc = subprocess.Popen([PY, HOST], cwd=HOST_DIR,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)

got_hello = threading.Event()


def reader():
    while True:
        raw = proc.stdout.read(4)
        if len(raw) < 4:
            return
        n = struct.unpack("<I", raw)[0]
        data = proc.stdout.read(n)
        try:
            m = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        if m.get("type") == "hello":
            print("  <- hello (hotkey=%s)" % m.get("hotkey"), flush=True)
            got_hello.set()


t = threading.Thread(target=reader, daemon=True)
t.start()

ok_hello = got_hello.wait(10)
print("[%s] 断开前已收到 hello，宿主 Tk/热键线程均在运行" % ("OK" if ok_hello else "FAIL"), flush=True)
if not ok_hello:
    proc.kill()
    sys.exit(1)

alive_before = proc.poll() is None
print("[%s] 断开前进程存活" % ("OK" if alive_before else "FAIL"), flush=True)

print("关闭 stdin（模拟浏览器断开管道）…", flush=True)
proc.stdin.close()

t0 = time.time()
exited = False
rc = None
while time.time() - t0 < 8:
    rc = proc.poll()
    if rc is not None:
        exited = True
        break
    time.sleep(0.1)

print("[%s] 断管后进程自行退出，耗时 %.1fs，退出码=%s"
      % ("OK" if exited else "FAIL", time.time() - t0, rc), flush=True)

if not exited:
    proc.kill()
    print("\n==> 验证失败：断管 8s 后进程仍在（僵尸宿主 bug 未修复）", flush=True)
    sys.exit(1)

# 日志留痕确认走了完整退出路径
time.sleep(0.5)
tail = ""
try:
    with open(os.path.join(HOST_DIR, "data", "host.log"), "r", encoding="utf-8") as f:
        tail = f.read()[-400:]
except Exception:
    pass
print("[%s] 日志含「宿主退出」留痕" % ("OK" if "宿主退出" in tail else "FAIL"), flush=True)
print("\n==> 验证通过", flush=True)
