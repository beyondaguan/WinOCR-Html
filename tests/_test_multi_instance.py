# -*- coding: utf-8 -*-
"""多实例 + Ctrl+Alt+Q 逐个关闭 的端到端验证（一次性）。

前置：所有宿主已 --stop。脚本拉起 3 个独立模式宿主，然后：
  1. data/hosts.roster.json 应有 3 个存活条目，leader = 最早启动者；
  2. 用 keybd_event 模拟一次 Ctrl+Alt+Q → 必须且只有 leader 死亡（全局热键
     排他性：若多个实例都注册成功，一次按键会死多个，测试即失败）；
  3. ~1.5s 内新 leader 接管；再按 → 再死一个；第三次按 → 全部退出、名册清空。
"""
import ctypes
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOST_DIR = os.path.join(ROOT, "native_host")
ROSTER = os.path.join(HOST_DIR, "data", "hosts.roster.json")
PYW = r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"

user32 = ctypes.windll.user32
KEYUP = 0x0002
VK_CTRL, VK_MENU, VK_Q = 0x11, 0x12, 0x51


def tap_ctrl_alt_q():
    user32.keybd_event(VK_CTRL, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_Q, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_Q, 0, KEYUP, 0)
    user32.keybd_event(VK_MENU, 0, KEYUP, 0)
    user32.keybd_event(VK_CTRL, 0, KEYUP, 0)


def roster_pids():
    try:
        with open(ROSTER, "r", encoding="utf-8") as f:
            r = json.load(f)
        return [int(e["pid"]) for e in r]
    except Exception:
        return []


def alive(pid):
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    ctypes.windll.kernel32.CloseHandle(h)
    return True


def wait_dead(pid, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not alive(pid):
            return True
        time.sleep(0.1)
    return False


def wait_cond(fn, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.1)
    return False


def main():
    # 清场
    subprocess.run([sys.executable, os.path.join(HOST_DIR, "winocr_host.py"), "--stop"],
                   cwd=HOST_DIR, capture_output=True)
    time.sleep(1.0)

    pids = []
    for i in range(3):
        subprocess.Popen([PYW, "winocr_host.py", "--standalone"], cwd=HOST_DIR,
                         creationflags=0x08000000)  # CREATE_NO_WINDOW
        time.sleep(1.2)   # 错开启动，保证名册顺序 = 启动顺序
        pids.append(roster_pids()[-1:][0])
    print("启动顺序 pids:", pids, flush=True)

    ok = True
    time.sleep(2.0)
    rp = roster_pids()
    n3 = len([p for p in rp if alive(p)])
    print("[%s] 名册存活 %d 个（期望 3）：%s" % ("OK" if n3 == 3 else "FAIL", n3, rp), flush=True)
    ok &= (n3 == 3)

    expected_leader = rp[0]
    print("[%s] 首个 leader = pid %d（期望最早启动的 %d）"
          % ("OK" if expected_leader == pids[0] else "FAIL", expected_leader, pids[0]), flush=True)
    ok &= (expected_leader == pids[0])

    # 逐个关闭：每按一次，精确死亡一个（当前 leader），其余存活
    round_n = 0
    while len([p for p in roster_pids() if alive(p)]) > 0:
        round_n += 1
        before = [p for p in roster_pids() if alive(p)]
        leader = before[0]
        tap_ctrl_alt_q()
        died = wait_dead(leader)
        others_alive = all(alive(p) for p in before[1:])
        time.sleep(2.5)   # 给接管者 0.7s 选举 + 注册重试留足时间
        after = [p for p in roster_pids() if alive(p)]
        print("[%s] 第%d次 Ctrl+Alt+Q：leader pid %d 死亡=%s；其余存活=%s；剩余 %s"
              % ("OK" if died and others_alive and len(after) == len(before) - 1 else "FAIL",
                 round_n, leader, died, others_alive, after), flush=True)
        ok &= died and others_alive and len(after) == len(before) - 1
        if round_n > 3:
            print("!! 轮次异常，中止", flush=True)
            ok = False
            break

    time.sleep(1.0)
    final = roster_pids()
    print("[%s] 三次后名册：%s（期望空）" % ("OK" if not final else "FAIL", final), flush=True)
    ok &= (not final)

    # 进程级再确认：只数 python 宿主（排除执行查询的 PowerShell 自身——它的
    # 命令行里就含 '*winocr_host.py*' 匹配串，不过滤会自匹配成 1~2 个假阳性）
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' "
         "-and $_.CommandLine -like '*winocr_host.py*' }).Count"],
        capture_output=True, text=True)
    cnt = int((out.stdout or "0").strip() or 0)
    print("[%s] 系统中 winocr_host.py python 进程数 = %d（期望 0）"
          % ("OK" if cnt == 0 else "FAIL", cnt), flush=True)
    ok &= (cnt == 0)

    print(("\n==> 多实例验证通过" if ok else "\n==> 验证失败"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
