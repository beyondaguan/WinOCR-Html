#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「某个解释器」装上本地 OCR 的可选依赖。

    python install_deps.py              # 自动挑解释器，缺什么装什么，装完复验
    python install_deps.py --check      # 只体检，不安装（退出码 1 = 有缺）
    python install_deps.py --list       # 列出所有候选解释器各自的依赖状态
    python install_deps.py --target <python.exe>
    python install_deps.py --mirror     # 走清华 PyPI 镜像（国内网络更快）

为什么需要这个脚本
------------------
依赖是**平台 + ABI 绑定**的二进制 wheel（cp311 的装不进 cp314，win_amd64 的用不了
arm64），所以只能装进解释器、不能随项目分发。于是「装到哪个解释器」就成了必须先
回答的问题 —— 而这正是之前那次事故的根源：本地 OCR 装在一个解释器里，启动器却
按 PATH 顺序选中了另一个（连 tkinter 都没有），表现成「按热键毫无反应」。

这个脚本把三件事串起来：**选对解释器 → 装 → 装完复验**。
复验不能省：pip 报成功 ≠ import 成功（缺 VC++ 运行库时 onnxruntime 会装上但导入失败）。

幂等：已满足的直接跳过，可以反复跑。
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pyenv  # noqa: E402

REQ_FILE = os.path.join(HERE, "requirements-ocr.txt")
FALLBACK_PKGS = ["rapidocr", "onnxruntime", "numpy", "Pillow"]
TSINGHUA = "https://pypi.tuna.tsinghua.edu.cn/simple"
VC_REDIST = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

# 宿主还需要 tkinter，但它随官方 Python 安装包走，pip 装不了
NEED = ("tkinter",) + tuple(pyenv.REQUIRED)


def say(msg=""):
    """打印且绝不因编码抛错（936 控制台 / 重定向到文件都安全）。"""
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(text.encode(enc, "replace").decode(enc, "replace"), flush=True)


def pip_install(exe, spec, extra):
    cmd = [exe, "-m", "pip", "install", "--upgrade"] + extra + spec
    say("$ " + " ".join(cmd))
    say("")
    try:
        return subprocess.call(cmd)
    except Exception as e:
        say("[!] could not run pip: %s" % e)
        return 1


def main():
    ap = argparse.ArgumentParser(description="Install WinOCR-Html local-OCR deps.")
    ap.add_argument("--check", action="store_true", help="only report, do not install")
    ap.add_argument("--list", action="store_true", help="list every candidate interpreter")
    ap.add_argument("--mirror", action="store_true", help="use the Tsinghua PyPI mirror")
    ap.add_argument("--target", metavar="PYTHON.EXE", help="install into this interpreter")
    args = ap.parse_args()

    # ---- 列出所有候选 ----
    if args.list:
        say("interpreter candidates (host needs: %s)" % ", ".join(NEED))
        say("")
        for exe in pyenv.candidates():
            ok, _miss, detail = pyenv.probe(exe, NEED)
            say("[%s] %s" % ("OK" if ok else "--", exe))
            if not ok:
                say("     %s" % detail)
        return 0

    # ---- 选目标解释器 ----
    exe = args.target or pyenv.install_target()
    if not exe or not os.path.isfile(exe):
        say("[!] no python interpreter found.")
        say("    Install Python 3 from https://www.python.org/downloads/windows/")
        say("    (keep 'tcl/tk and IDLE' checked - the host GUI needs tkinter)")
        return 1
    say("target interpreter: %s" % exe)

    ok, miss, detail = pyenv.probe(exe, NEED)
    if ok:
        say("[+] already satisfied - nothing to install.")
        say("    %s" % detail)
        return 0

    say("[i] missing: %s" % ", ".join(miss))
    if "tkinter" in miss:
        say("")
        say("[!] tkinter is missing from this interpreter, and pip CANNOT install it.")
        say("    Re-run the official Python installer and enable 'tcl/tk and IDLE',")
        say("    or pick another interpreter (--list shows what each one has).")
        if len(miss) == 1:
            return 1
        say("")

    if args.check:
        say("")
        say("(--check: nothing was installed)")
        return 1

    # ---- 安装 ----
    extra = ["-i", TSINGHUA] if args.mirror else []
    if os.path.isfile(REQ_FILE):
        rc = pip_install(exe, ["-r", REQ_FILE], extra)
    else:
        rc = pip_install(exe, FALLBACK_PKGS, extra)

    if rc != 0 and not args.mirror:
        say("")
        say("[i] pip failed. On a slow/blocked network retry with the mirror:")
        say("    install_deps.bat --mirror")

    # ---- 复验（pip 成功 != import 成功）----
    say("")
    ok2, miss2, detail2 = pyenv.probe(exe, NEED)
    if ok2:
        say("[OK] local OCR is ready: %s" % detail2)
        say("")
        say("next steps:")
        say("  * desktop screenshots -> double-click run_host.bat")
        say("  * browser extension   -> reload it, then tick 'connect native host'")
        say("  * full health check   -> python winocr_host.py --doctor")
        return 0

    say("[-] still missing after install: %s" % ", ".join(miss2))
    say("")
    say("    If pip reported success but the import still fails, the usual cause is")
    say("    the Microsoft Visual C++ Redistributable (x64) being absent:")
    say("    %s" % VC_REDIST)
    return 1


if __name__ == "__main__":
    sys.exit(main())
