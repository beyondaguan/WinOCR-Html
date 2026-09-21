#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解释器选址：找出「装了本地 OCR 依赖」的那个 Python。

为什么需要它
------------
本地 OCR（rapidocr + onnxruntime + numpy + Pillow）是**可选依赖**，用户往往
只把它装进某几个解释器里；而启动路径过去一律按 PATH 顺序盲选 —— 选到裸解释器
时本地 OCR 就静默不可用，用户最后只看到一个和真实原因毫无关系的报错
（实测踩到：`run_host.bat` 用 `where pythonw` 取到 PATH 最前面的托管 3.13，
零依赖，于是「本地 OCR 不可用 + 未配置 key」→ 云端回退报 `Token is invalid`）。

把「用哪个解释器」变成显式、可复现、有记录的决策：

    missing_local()   当前解释器缺什么（快，只查 spec，不 import）
    probe(exe)        某个控制台解释器的依赖齐不齐
    candidates()      枚举本机候选解释器（py launcher / 注册表 / PATH / 常见目录）
    pick_best()       选第一个合格的（合格结果带 TTL 缓存，避免每次启动探测）
    ensure()          宿主自举：当前不合格就用合格的 execv 重启自己

设计约束
--------
* 纯标准库（numpy 都没装的时候也要能跑）。
* 输出全 ASCII —— 36 号代码页下中文会乱码，这个模块会被 .bat 生成器调用。
* 探测一律走 `python.exe`（`pythonw.exe` 没有 stdout，读不到结果）；
  真正启动宿主时才换成同目录的 `pythonw.exe`。
* 只缓存「找到了」的结果，不缓存「没找到」—— 否则用户新装完依赖还得等缓存过期。
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "data", "pyenv.json")

# 本地 OCR 需要的全部运行时依赖
REQUIRED = ("numpy", "PIL", "rapidocr", "onnxruntime")

# 自举哨兵：execv 前后靠它防重入
SENTINEL = "WINOCR_BOOTSTRAPPED"
NO_BOOTSTRAP = "WINOCR_NO_BOOTSTRAP"

CACHE_TTL = 24 * 3600.0
PROBE_TIMEOUT = 25

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_PROBE_CODE = (
    "import importlib, json, sys\n"
    "miss, vers = [], {}\n"
    "for m in %r:\n"
    "    try:\n"
    "        mod = importlib.import_module(m)\n"
    "        vers[m] = getattr(mod, '__version__', '') or '?'\n"
    "    except Exception:\n"
    "        miss.append(m)\n"
    "print('@PYENV@' + json.dumps({'missing': miss, 'versions': vers, 'exe': sys.executable}))\n"
)


# ----------------------------- 小工具 -----------------------------
def emit(msg=""):
    """打印且绝不因编码抛错（重定向到文件 / 936 控制台都安全）。"""
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, "replace").decode(enc, "replace"), flush=True)


def _console_variant(exe):
    """pythonw.exe -> python.exe（探测必须有 stdout）。"""
    if not exe:
        return None
    d, n = os.path.split(exe)
    if n.lower() == "pythonw.exe":
        cand = os.path.join(d, "python.exe")
        if os.path.isfile(cand):
            return cand
    return exe


def _windowless_variant(exe):
    """python.exe -> pythonw.exe（启动时要无控制台窗口）。"""
    if not exe:
        return None
    d, n = os.path.split(exe)
    if n.lower() == "python.exe":
        cand = os.path.join(d, "pythonw.exe")
        if os.path.isfile(cand):
            return cand
    return exe


def _reexec_target(exe):
    """重启成目标解释器时，保持当前进程「有没有控制台」的属性。

    当前是 pythonw（无控制台，双击 .bat / 浏览器拉起）→ 也用 pythonw；
    当前是 python（命令行 / 输出重定向）→ 就用 python。
    反过来的话，`--doctor` 这类命令行输出会凭空消失（pythonw 没有 stdout）。
    """
    if os.path.basename(sys.executable or "").lower().startswith("pythonw"):
        return _windowless_variant(exe) or exe
    return _console_variant(exe) or exe


def _which_all(name):
    out = []
    for d in (os.environ.get("PATH") or "").split(os.pathsep):
        d = d.strip().strip('"')
        if not d:
            continue
        for ext in (".exe", ".EXE"):
            p = os.path.join(d, name + ext)
            if os.path.isfile(p):
                out.append(p)
                break
    return out


# 公开别名：别的模块不需要知道下划线约定
console_variant = _console_variant
windowless_variant = _windowless_variant


# ----------------------------- 候选枚举 -----------------------------
def _from_py_launcher():
    """`py -0p` 会列出所有已注册解释器（含 Store 版之外的自定义安装）。"""
    try:
        p = subprocess.run(
            ["py", "-0p"], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, creationflags=_CREATE_NO_WINDOW,
        )
    except Exception:
        return []
    out = []
    for line in (p.stdout or "").splitlines():
        m = re.search(r"([A-Za-z]:\\[^\s]*?python\.exe)", line)
        if m:
            out.append(m.group(1))
    return out


def _from_registry():
    if os.name != "nt":
        return []
    try:
        import winreg
    except Exception:
        return []
    out = []
    roots = (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Python\PythonCore"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Python\PythonCore"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Python\PythonCore"),
    )
    for root, path in roots:
        try:
            with winreg.OpenKey(root, path) as k:
                count = winreg.QueryInfoKey(k)[0]
                for i in range(count):
                    try:
                        ver = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, ver + r"\InstallPath") as ip:
                            val, _ = winreg.QueryValueEx(ip, "ExecutablePath")
                            if val:
                                out.append(val)
                    except OSError:
                        continue
        except OSError:
            continue
    return out


def _from_globs():
    pats = []
    la = os.environ.get("LOCALAPPDATA") or ""
    if la:
        pats += [
            os.path.join(la, "Programs", "Python", "Python3*", "python.exe"),
            os.path.join(la, "Python", "pythoncore-*", "python.exe"),
            os.path.join(la, "Python", "bin", "python.exe"),
        ]
    pf = os.environ.get("ProgramFiles") or ""
    if pf:
        pats.append(os.path.join(pf, "Python3*", "python.exe"))
    out = []
    for pat in pats:
        out.extend(glob.glob(pat))
    return out


def candidates(include_current=True):
    """本机可能的解释器（去重、保序、只保留存在的文件）。

    顺序即优先级：当前解释器 → py launcher → 注册表 → PATH → 常见目录。
    """
    out = []

    def add(p):
        if not p:
            return
        try:
            p = os.path.abspath(p)
        except Exception:
            return
        if os.path.isfile(p) and p not in out:
            out.append(p)

    if include_current:
        add(_console_variant(sys.executable))
    for p in _from_py_launcher():
        add(_console_variant(p))
    for p in _from_registry():
        add(_console_variant(p))
    for p in _which_all("python"):
        add(_console_variant(p))
    for p in _from_globs():
        add(_console_variant(p))
    return out


# ----------------------------- 探测 -----------------------------
def missing_local(required=REQUIRED):
    """当前解释器缺哪些依赖。只查 spec（不 import），毫秒级。"""
    import importlib.util

    miss = []
    for m in required:
        try:
            if importlib.util.find_spec(m) is None:
                miss.append(m)
        except Exception:
            miss.append(m)
    return miss


def probe(exe, required=REQUIRED, timeout=PROBE_TIMEOUT):
    """探测某个解释器。返回 (ok, missing, detail)，detail 为可读的 ASCII 说明。"""
    c = _console_variant(exe)
    if not c or not os.path.isfile(c):
        return False, list(required), "not found"
    try:
        p = subprocess.run(
            [c, "-c", _PROBE_CODE % (tuple(required),)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return False, list(required), "timeout after %ss" % timeout
    except Exception as e:
        return False, list(required), "spawn failed: %s" % type(e).__name__
    for line in reversed((p.stdout or "").splitlines()):
        line = line.strip()
        idx = line.find("@PYENV@")
        if idx < 0:
            continue
        try:
            j = json.loads(line[idx + len("@PYENV@"):])
        except Exception:
            continue
        miss = list(j.get("missing") or [])
        if not miss:
            vers = j.get("versions") or {}
            detail = "ok (" + " ".join("%s=%s" % (k, vers.get(k, "?")) for k in required) + ")"
        else:
            detail = "missing: " + ",".join(miss)
        return (not miss), miss, detail
    return False, list(required), "no probe output (exit=%s)" % p.returncode


# ----------------------------- 缓存 -----------------------------
def _cache_key(required=REQUIRED):
    """缓存按「需要哪些依赖」分桶 —— 宿主需要 tkinter，别的调用者未必。"""
    return ",".join(sorted(required))


def _read_cache(required=REQUIRED):
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return {}
    if not isinstance(j, dict):
        return {}
    entry = (j.get("entries") or {}).get(_cache_key(required))
    return entry if isinstance(entry, dict) else {}


def _write_cache(exe, detail, required=REQUIRED):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        j = {}
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, dict):
                j = old
        except Exception:
            j = {}
        entries = j.get("entries")
        if not isinstance(entries, dict):
            entries = {}
        entries[_cache_key(required)] = {"exe": exe, "detail": detail, "ts": time.time()}
        j["entries"] = entries
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(j, f, indent=2)
    except Exception:
        pass


def clear_cache():
    try:
        os.remove(CACHE_PATH)
        return True
    except OSError:
        return False


# ----------------------------- 选址 -----------------------------
# 托管环境 / 商店别名不适合作为「装依赖」的目标：前者可能被工具链回收，
# 后者只是 App Execution Alias，pip 装进去会落到一个让人找不到的位置。
_BAD_INSTALL_MARKERS = (
    "\\.workbuddy\\",
    "\\windowsapps\\",
)


def install_target():
    """挑一个「适合往里面 pip install」的解释器（控制台版）。

    与 pick_best() 的区别：**不要求**依赖已经齐全 —— 本函数就是给「还没有依赖」
    的机器用的，所以只挑一个合理的落点：优先用户自己的官方安装，
    排除托管环境与 Microsoft Store 的别名。
    """
    for exe in candidates():
        low = exe.lower()
        if any(m in low for m in _BAD_INSTALL_MARKERS):
            continue
        c = _console_variant(exe)
        if c and c.lower().endswith("python.exe"):
            return c
    cands = candidates()
    return _console_variant(cands[0]) if cands else None


def pick_best(required=REQUIRED, use_cache=True, verbose=False):
    """返回 (exe, missing, detail)。exe 为 None 表示本机没有任何合格解释器。

    只缓存合格结果（TTL 内直接信任），不合格结果永远重探 —— 用户刚 pip install
    完依赖就能立刻生效，不必等缓存过期。
    """
    if use_cache:
        c = _read_cache(required)
        exe = c.get("exe")
        if exe and os.path.isfile(exe) and (time.time() - float(c.get("ts") or 0)) < CACHE_TTL:
            if verbose:
                emit("      [cache] %s" % exe)
            return exe, [], str(c.get("detail") or "cached")

    seen = []
    for exe in candidates():
        ok, miss, detail = probe(exe, required)
        seen.append((exe, miss, detail))
        if verbose:
            emit("      [%s] %s  %s" % ("OK " if ok else "no ", exe, detail))
        if ok:
            _write_cache(exe, detail, required)
            return exe, [], detail
    # 没找到合格解释器：报「最接近」的那个（缺得最少）便于用户补装
    if seen:
        _exe, miss, detail = min(seen, key=lambda t: len(t[1]))
        return None, list(miss), detail
    return None, list(required), "no interpreter candidates found"


# ----------------------------- 自举 -----------------------------
def ensure(required=REQUIRED, argv=None, force=False):
    """宿主启动自举：当前解释器缺依赖时，换合格解释器重启自己。

    返回一个短字符串说明「为什么没自举」（真正自举时进程已被替换，不会返回）。

    注意：Native Messaging 模式下 stdin/stdout 是浏览器给的匿名管道，
    `os.execv` 会保留文件描述符，所以换解释器不会弄丢与浏览器的连接。
    """
    if os.environ.get(NO_BOOTSTRAP) and not force:
        return "disabled by %s" % NO_BOOTSTRAP
    if os.environ.get(SENTINEL):
        return "already bootstrapped"
    miss = missing_local(required)
    if not miss:
        return "current ok"
    exe, _m, detail = pick_best(required)
    if not exe:
        return "no suitable interpreter (%s)" % detail
    target = _reexec_target(exe)
    args = [target] + list(argv or sys.argv)
    os.environ[SENTINEL] = "1"
    try:
        os.execv(target, args)
    except Exception as e:
        return "execv failed: %s" % e
    return "unreachable"


# ----------------------------- CLI -----------------------------
def main():
    args = sys.argv[1:]
    if "--pick" in args:
        # 给启动器用：优先无窗口解释器（pythonw），避免常驻却挂着黑框
        exe, _m, _d = pick_best(use_cache="--repick" not in args)
        emit(_windowless_variant(exe) if exe else "")
        return 0 if exe else 1
    if "--repick" in args:
        clear_cache()

    emit("WinOCR-Html python picker")
    emit("  current : %s" % sys.executable)
    miss = missing_local()
    emit("  missing in current: %s" % (",".join(miss) if miss else "(none)"))
    emit("  required: %s" % ", ".join(REQUIRED))
    emit("")
    emit("probing candidates:")
    exe, miss, detail = pick_best(use_cache="--nocache" not in args, verbose=True)
    emit("")
    if exe:
        emit("[+] best    : %s" % exe)
        emit("    windowless: %s" % _windowless_variant(exe))
        emit("    detail  : %s" % detail)
        return 0
    emit("[-] no interpreter with the local-OCR deps was found. %s" % detail)
    emit("    fix: python -m pip install rapidocr onnxruntime numpy Pillow")
    return 1


if __name__ == "__main__":
    sys.exit(main())
