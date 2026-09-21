#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WinOCR-Html 原生宿主（Windows）
================================
职责（按定稿架构 + v0.3 升级）：
  1) 与浏览器扩展通过 Native Messaging 通信（stdio，4 字节长度前缀）。[NM 模式]
  2) 全局热键 Ctrl+Shift+M（Win32 RegisterHotKey）→ 任意软件/桌面的截图都能触发。
  3) 【v0.3 升级】区域画框截图：热键后全屏半透明遮罩 + 鼠标拖拽画框（Snipaste/Snow Shot 风格）
     → 只截选定区域，OCR 准、省 token。取消用 Esc。
  4) BitBlt 截屏 → 零依赖 PNG 编码（无需 Pillow）。
  5) 调你自带的 SiliconFlow key 做 OCR + 翻译（外部阅读场景，浏览器内置翻译用不上）。
  6) Tkinter 置顶浮窗展示结果（独立 OS 表面，不碰主程序窗口）。
  7) 记录落地：
     - NM 模式：回传扩展写入 chrome.storage，与浏览器内记录统一历史。
     - 独立模式(--standalone)：写本地日积累 Markdown + assets PNG，无需浏览器。

仅用标准库 + tkinter（tkinter 随 Python 安装）。无第三方依赖。

用法：
  python winocr_host.py            # NM 模式（被浏览器扩展通过 connectNative 拉起；或单独跑时会等 NM 连接）
  python winocr_host.py --standalone   # 独立模式（不依赖浏览器，热键+本地配置+本地记录常驻）
"""

import sys
import os
import io
import json
import struct
import base64
import zlib
import threading
import datetime
import time
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import html

# --------------------- 解释器自举（必须早于 tkinter） ---------------------
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

_PYENV_NOTE = ''


def _bootstrap_interpreter():
    """换成「同时具备 tkinter 与本地 OCR 依赖」的解释器，再继续往下跑。

    为什么必须在 import tkinter 之前：本地 OCR 依赖（rapidocr/onnxruntime）通常
    只装在某个解释器里，而启动路径（run_host.bat 的 `where pythonw`、浏览器
    launcher）是按 PATH 顺序盲选的。选到精简解释器时不仅本地 OCR 静默失效，
    连 tkinter 都可能没有 —— 那时会在 import 处直接崩，连自检都做不了。

    NM 模式下 stdin/stdout 是浏览器给的匿名管道，`os.execv` 保留文件描述符，
    换解释器不会弄丢与浏览器的连接。
    """
    global _PYENV_NOTE
    try:
        import pyenv
        _PYENV_NOTE = pyenv.ensure(required=("tkinter",) + tuple(pyenv.REQUIRED))
    except Exception as e:
        _PYENV_NOTE = 'skipped (%s: %s)' % (type(e).__name__, e)


_bootstrap_interpreter()

import tkinter as tk  # noqa: E402  (必须在自举之后，见上)

# --------------------- 运行模式 ---------------------
# NM 模式：与浏览器扩展通信，stdin/stdout 被浏览器接管；断开即退出。
# 独立模式：不读 stdin，从本地 config 读设置，记录写本地，进程常驻不依赖浏览器。
STANDALONE = '--standalone' in sys.argv

CONFIG_PATH = os.path.join(HERE, 'winocr_config.json')
DATA_DIR = os.path.join(HERE, 'data')

# 多实例名册：允许多个宿主进程并存（浏览器拉起的 NM 宿主 + 手动 run_host.bat 的
# 独立宿主等）。Windows 全局热键同一组合键全系统只允许一个进程 RegisterHotKey，
# 所以由名册里「最旧的存活实例」当 leader 独占热键；leader 退出后下一个自动接管。
# 按 Ctrl+Alt+Q 一次只关 leader 一个 → 再按关下一个，实现「逐个关闭」。
ROSTER_PATH = os.path.join(DATA_DIR, 'hosts.roster.json')
ROSTER_LOCK = os.path.join(DATA_DIR, 'hosts.lck')

# --------------------- 常量定义 ---------------------
# NM 协议
NM_LENGTH_PREFIX = 4          # 4 字节小端长度前缀
NM_MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB 最大消息大小

# 热键
HOTKEY_ID_CAPTURE = 1
HOTKEY_ID_QUIT = 2
WM_HOTKEY = 0x0312
WM_RELOAD_HOTKEY = 0x8001
WM_HK_ACQUIRE = 0x8002
WM_HK_RELEASE = 0x8003
MOD_NOREPEAT = 0x4000

# 截图
SF_TRANSLATE_TIMEOUT = 60
SF_OCR_TIMEOUT = 240
MM_CHUNK_SIZE = 450
MM_MAX_RETRIES = 3

# 名册
ROSTER_LOCK_RETRIES = 200
ROSTER_LOCK_RETRY_INTERVAL = 0.05
ROSTER_WRITE_RETRIES = 10
ROSTER_WRITE_RETRY_INTERVAL = 0.05

# 热键注册
HOTKEY_REGISTER_RETRIES = 15
HOTKEY_REGISTER_RETRY_INTERVAL = 0.2

# 截图
SCREENSHOT_DELAY_MS = 200       # 遮罩残影等待
SCREENSHOT_BITMAPINFOHEADER_SIZE = 40
SCREENSHOT_PLANES = 1
SCREENSHOT_BPP = 32
SCREENSHOT_ZLIB_LEVEL = 6

# 浮窗
RESULT_WINDOW_AUTO_CLOSE_MS = 60000

# 选举
LEADER_WATCH_INTERVAL = 0.7

# 解释器
PYENV_WAIT_TIMEOUT = 3.0

# 共享常量（与 JS 扩展共享，修改时需同步更新两侧）
SHARED_CONSTANTS_PATH = os.path.join(HERE, 'shared_constants.json')

def _load_shared_constants():
    """加载共享常量文件（模型名映射、语言映射等）。"""
    try:
        with open(SHARED_CONSTANTS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

_SHARED = _load_shared_constants()
SF_MODEL_ALIASES = _SHARED.get('sfModelAliases', {})
OCR_ALIASES = _SHARED.get('ocrAliases', {})
MM_LANG_MAP = _SHARED.get('mmLangMap', {})
MM_ENDPOINT = _SHARED.get('mmEndpoint', 'https://api.mymemory.translated.net/get')
SF_DEFAULT_URL = _SHARED.get('sfDefaultUrl', 'https://api.siliconflow.cn/v1')

# --------------------- Native Messaging ---------------------
def nm_read():
    raw = sys.stdin.buffer.read(NM_LENGTH_PREFIX)
    if len(raw) < NM_LENGTH_PREFIX:
        return None
    n = struct.unpack('<I', raw)[0]
    if n > NM_MAX_MESSAGE_SIZE:
        host_log('NM 消息过大: %d 字节，拒绝读取' % n)
        return None
    data = sys.stdin.buffer.read(n)
    return json.loads(data.decode('utf-8'))


def nm_write(obj):
    try:
        data = json.dumps(obj).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('<I', len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except Exception:
        # 独立模式或非管道 stdout 时静默忽略
        pass


# --------------------- 本地配置（独立模式用） ---------------------
# --------------------- 免费模型清单（2026-09-20 实测） ---------------------
# 扩展「选项」里的下拉与这里保持一致，改一处即可。
#   文本/翻译   Qwen/Qwen3-8B                     2.5s  ✅ 快
#               deepseek-ai/DeepSeek-R1-0528-Qwen3-8B  9.5~12.3s（推理模型，思考占 400+ 字，慢 4 倍）
#   OCR(云端)   PaddlePaddle/PaddleOCR-VL-1.5     103~121s（正确但有前导幻觉字符）
#               deepseek-ai/DeepSeek-OCR          0.9s(热)/30s(冷)，输出不稳定（会整段退化乱码）
#   OCR(本地)   PP-OCRv6 tiny                     1.2~2.2s 置信度 0.98  ← 截图场景最优，默认
FREE_TEXT_MODELS = ("Qwen/Qwen3-8B", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")
FREE_OCR_MODELS = ("PaddlePaddle/PaddleOCR-VL-1.5", "deepseek-ai/DeepSeek-OCR")

# 硅基流动的模型 id 必须与官方完全一致（含 `PaddlePaddle/` 等前缀）。
# 漏写前缀会返回 20012 "Model does not exist" —— 这个映射让旧的/手写的简写自动痊愈。
# SF_MODEL_ALIASES 从 shared_constants.json 加载（与 JS 扩展共享）


def normalize_sf_model(name, fallback):
    """把模型名规范成 SF 上真实存在的 id（简写 → 全称）。"""
    n = str(name or "").strip()
    if not n:
        return fallback
    return SF_MODEL_ALIASES.get(n.lower(), n)


def default_config():
    return {
        "sfKey": "",
        "sfUrl": "https://api.siliconflow.cn/v1",
        "sfModel": "Qwen/Qwen3-8B",
        # 必须带 PaddlePaddle/ 前缀，否则 20012 Model does not exist
        "sfOcrModel": "PaddlePaddle/PaddleOCR-VL-1.5",
        # OCR 引擎：'local' 本地 PP-OCRv6（离线、零 key、~1.5s，截图首选）
        #           'sf'   云端 SiliconFlow 视觉模型（慢，但能处理照片/手写/复杂版面）
        "ocrEngine": "local",
        "localOcrTier": "tiny",     # 'tiny'（6.6MB，默认）| 'medium'（133MB，更准更慢）
        "srcLang": "en",
        "tgtLang": "zh",
        # 截图 OCR 之后的翻译引擎，与扩展选项页同一套开关（浏览器内置引擎在宿主
        # 里用不了，故无 browser）：
        #   'sf'       SiliconFlow（sfModel，需 sfKey，医疗术语好，默认）
        #   'mymemory' 免费免 key、国内可直连（匿名 ~5000 字符/天，填邮箱 ~50000）
        #   'none'     仅 OCR，不翻译
        "translateEngine": "sf",
        "mymemoryEmail": "",
        # 全局截图热键；被占用时会自动尝试备选键（见 FALLBACK_HOTKEYS）
        # 注意：WinOCR 3.4 的「蒙版翻译」也用 ctrl+shift+m，两者同时运行会冲突
        "hotkey": "ctrl+shift+m",
        # 退出宿主的全局热键（必须带修饰键；不能用裸 Esc，那会劫持全系统的 Esc）
        "quitHotkey": "ctrl+alt+q",
    }


def load_config():
    """读本地 winocr_config.json 填充 SETTINGS。文件不存在则生成模板。"""
    global SETTINGS
    cfg = default_config()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    else:
        # 首次运行生成模板，提示用户填 key
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    with SETTINGS_LOCK:
        SETTINGS.update(cfg)
        # 模型名归一化：把历史遗留的简写（如 `PaddleOCR-VL-1.5`）纠正为 SF 上真实的
        # 全称（`PaddlePaddle/PaddleOCR-VL-1.5`），否则会一直报 20012 Model does not exist。
        SETTINGS["sfModel"] = normalize_sf_model(SETTINGS.get("sfModel"), "Qwen/Qwen3-8B")
        SETTINGS["sfOcrModel"] = normalize_sf_model(SETTINGS.get("sfOcrModel"),
                                               default_config()["sfOcrModel"])
    # OCR 引擎 / 本地档位取值校验（手改配置写错时不要静默跑错分支）
    with SETTINGS_LOCK:
        if str(SETTINGS.get("ocrEngine") or "").lower() not in ("local", "sf"):
            SETTINGS["ocrEngine"] = "local"
        if str(SETTINGS.get("localOcrTier") or "").lower() not in ("tiny", "medium"):
            SETTINGS["localOcrTier"] = "tiny"
        if str(SETTINGS.get("translateEngine") or "").lower() not in ("sf", "mymemory", "none"):
            SETTINGS["translateEngine"] = "sf"


# --------------------- 设置（由扩展同步 / 本地配置） ---------------------
SETTINGS = default_config()
ACTIVE_HOTKEY = ''      # 实际注册成功的热键（可能因占用而回退到备选键）
ACTIVE_QUIT_HOTKEY = ''  # 实际注册成功的「退出宿主」热键
IS_LEADER = False       # 本实例是否持有全局热键（多实例名册选举结果，leader_watcher 维护）

_WRITE_LOCK = threading.Lock()
# SETTINGS 读写锁（可重入）：nm_read_thread 写、hotkey_thread/leader_watcher/do_capture 读
SETTINGS_LOCK = threading.RLock()
# leader_watcher 请求退出时置位，避免 watcher 在退出过程中反复改选
STOP_EVENT = threading.Event()

ROOT = None                     # 主 Tk root（main() 里赋值）；用于无控制台时弹提示
LOG_PATH = os.path.join(DATA_DIR, 'host.log')


def _is_console():
    """判断是否运行在真控制台（而非被浏览器以 NM 管道拉起）。"""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except Exception:
        return False


def _has_nm_stdio():
    """NM 模式是否真的有浏览器提供的 stdin/stdout 管道。

    被浏览器拉起 → 两者都是管道（isatty False）→ True；
    真控制台 → isatty True → False；
    pythonw 下**手动双击** launcher → sys.stdin/stdout 为 None → False
    （这种情况无法与扩展通信，必须让用户知道，不能假装"已桥接"）。
    """
    try:
        if sys.stdin is None or sys.stdout is None:
            return False
        return (not sys.stdin.isatty()) and (not sys.stdout.isatty()) and \
            hasattr(sys.stdout, 'buffer')
    except Exception:
        return False


def host_log(text):
    """把提示追加到 data/host.log（无控制台时唯一的记录，便于事后排查）。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write('[%s] %s\n' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), text))
    except Exception:
        pass


def ui_toast(text, ms=6000):
    """无控制台（pythonw 启动）时的可见提示：屏幕右下角小窗，自动消失。"""
    if ROOT is None:
        return

    def build():
        try:
            w = tk.Toplevel(ROOT)
            w.overrideredirect(True)
            w.attributes('-topmost', True)
            sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
            w.geometry('+%d+%d' % (max(0, sw - 400), max(0, sh - 130)))
            f = tk.Frame(w, bg='#1f2329', padx=13, pady=10, highlightthickness=1,
                         highlightbackground='#1677ff')
            f.pack(fill='both', expand=True)
            tk.Label(f, text=text, bg='#1f2329', fg='#e8edf3', justify='left', wraplength=340,
                     font=('Microsoft YaHei UI', 10)).pack(anchor='w')
            w.after(ms, lambda: (w.winfo_exists() and w.destroy()))
        except Exception:
            pass

    try:
        ROOT.after(0, build)
    except Exception:
        pass


def mode_desc():
    """当前运行模式的可读描述（用于启动提示与状态上报）。"""
    if STANDALONE:
        return '独立模式：不连扩展，记录写本地 Markdown'
    if _is_console():
        return 'NM 模式但未由浏览器拉起（扩展联动不可用；桌面截图请用 run_host.bat）'
    if not _has_nm_stdio():
        return 'NM 模式但没有浏览器管道（八成是手动双击了 winocr_launcher.bat；' \
               '扩展联动不可用，请改用 run_host.bat）'
    return 'NM 模式：已被浏览器扩展桥接（记录会回传扩展历史）'


# --------------------- 单实例保护（全局热键只能有一个宿主来抢） ---------------------
# 曾经踩过：反复启动/手动运行累积了 6 个宿主进程，全局热键被"最早那个（旧代码）"独占，
# 用户按下的热键被旧进程处理 → 看到旧 bug 的报错。所以必须保证同时只有一个宿主。
HOST_WINDOW_TITLES = ('WinOCR-Host', 'WinOCR · 置顶')


def find_running_hosts():
    """返回 {pid: 窗口标题} —— 当前正在运行的本宿主进程（不含自己）。

    靠**顶层窗口标题**识别（Tk root 一定会建 "WinOCR-Host" 窗口，即使 withdraw 也存在），
    而不是"杀掉所有 python.exe" —— 那样会误伤 WinOCR 3.4 或其它 Python 程序。
    """
    import ctypes
    import ctypes.wintypes
    u32 = ctypes.windll.user32
    found = {}
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def cb(hwnd, lparam):
        n = u32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            t = buf.value
            if any(t.startswith(x) for x in HOST_WINDOW_TITLES):
                pid = ctypes.wintypes.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found.setdefault(int(pid.value), t)
        return True

    try:
        u32.EnumWindows(WNDENUMPROC(cb), 0)
    except Exception:
        return {}
    found.pop(os.getpid(), None)
    return found


def stop_running_hosts():
    """结束所有正在运行的宿主进程（--stop / stop_host.bat 用）。返回结束的个数。"""
    import ctypes
    k32 = ctypes.windll.kernel32
    PROCESS_TERMINATE = 0x0001
    hosts = find_running_hosts()
    if not hosts:
        print('[i] 没有正在运行的 WinOCR 宿主进程。')
        return 0
    n = 0
    for pid, title in sorted(hosts.items()):
        h = k32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            k32.TerminateProcess(h, 0)
            k32.CloseHandle(h)
            n += 1
            print('[+] 已结束 pid=%d  (%s)' % (pid, title))
        else:
            print('[-] 无法结束 pid=%d（权限不足？可用任务管理器手动结束）' % pid)
    print('[i] 共结束 %d 个宿主进程。' % n)
    # 全被 --stop 强杀，名册/锁文件清掉，避免下次启动看到陈旧条目
    for p in (ROSTER_PATH, ROSTER_LOCK):
        try:
            os.remove(p)
        except OSError:
            pass
    return n


# --------------------- 多实例名册（leader 选举 / 热键所有权交接） ---------------------
def _pid_alive(pid):
    """进程是否存活（PROCESS_QUERY_LIMITED_INFORMATION 权限即可，Vista+）。"""
    import ctypes
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    except Exception:
        return False
    if not h:
        return False
    ctypes.windll.kernel32.CloseHandle(h)
    return True


def _with_roster_lock(fn):
    """对名册文件的互斥读改写（msvcrt 字节范围锁，Windows 专用）。"""
    import msvcrt
    os.makedirs(DATA_DIR, exist_ok=True)
    f = open(ROSTER_LOCK, 'a+b')
    try:
        for _ in range(ROSTER_LOCK_RETRIES):
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(ROSTER_LOCK_RETRY_INTERVAL)
        else:
            raise RuntimeError('名册锁等待超时')
        try:
            return fn()
        finally:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
    finally:
        f.close()


def _read_roster():
    try:
        with open(ROSTER_PATH, 'r', encoding='utf-8') as f:
            r = json.load(f)
        return r if isinstance(r, list) else []
    except Exception:
        return []


def _write_roster(r):
    tmp = ROSTER_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    # Windows 上 rename 目标文件正被其它进程打开（本进程的无锁读取 / 杀软扫描）
    # 时 os.replace 会抛 WinError 5（拒绝访问）——短暂重试即可，不要一次失败就
    # 让整轮选举作废（实测多实例按键快速交接时撞到过）。
    last = None
    for _ in range(ROSTER_WRITE_RETRIES):
        try:
            os.replace(tmp, ROSTER_PATH)
            return
        except OSError as e:
            last = e
            time.sleep(ROSTER_WRITE_RETRY_INTERVAL)
    raise last


def roster_touch(leave=False):
    """修剪死条目 + 登记/注销自己，返回当前 leader 的 pid（无则 0）与存活实例数。

    名册按启动先后排序：最旧的存活实例为 leader，独占截图/退出全局热键；
    leader 退出后下一名自动顺位接管。
    """
    me = os.getpid()

    def op():
        alive = [e for e in _read_roster()
                 if isinstance(e, dict) and _pid_alive(int(e.get('pid') or 0))]
        pids = [int(e['pid']) for e in alive]
        if leave:
            alive = [e for e in alive if int(e['pid']) != me]
        elif me not in pids:
            alive.append({'pid': me,
                          'start': datetime.datetime.now().strftime('%H:%M:%S'),
                          'mode': 'standalone' if STANDALONE else 'nm'})
        _write_roster(alive)
        leader = int(alive[0]['pid']) if alive else 0
        return leader, len(alive)

    return _with_roster_lock(op)


def roster_count():
    """名册里存活实例数（--stop 提示用，不上锁的短暂读取可接受）。"""
    try:
        return len([e for e in _read_roster()
                    if isinstance(e, dict) and _pid_alive(int(e.get('pid') or 0))])
    except Exception:
        return 0


def ocr_engine_desc():
    """当前 OCR 引擎的可读描述（启动提示 + 扩展状态显示都用它）。"""
    eng = (SETTINGS.get('ocrEngine') or 'local').lower()
    if eng != 'local':
        return '云端 SiliconFlow · %s（慢：实测 0.9~30s DeepSeek-OCR / 103~121s PaddleOCR-VL）' % \
            normalize_sf_model(SETTINGS.get('sfOcrModel'), default_config()['sfOcrModel'])
    try:
        import ocr_local
        ok, why = ocr_local.available()
        if not ok:
            return '本地 PP-OCRv6（不可用：%s → 截图时会回落云端）' % why
        return '本地 PP-OCRv6 %s 档（离线·零 key·~1.5s）' % (SETTINGS.get('localOcrTier') or 'tiny')
    except Exception as e:
        return '本地 PP-OCRv6（模块加载失败：%s）' % e


def announce_hello():
    """NM 模式（真被浏览器拉起）时，把自身状态告诉扩展，便于设置页显示「已桥接」。"""
    if STANDALONE or not _has_nm_stdio():
        return
    try:
        with _WRITE_LOCK:
            with SETTINGS_LOCK:
                nm_write({"type": "hello", "mode": "nm", "hotkey": ACTIVE_HOTKEY,
                          "quitHotkey": ACTIVE_QUIT_HOTKEY,
                          "pid": os.getpid(), "python": sys.executable,
                          # 把「本地配置到底在哪」一并报给扩展：独立模式与扩展是两份配置，
                          # 用户最需要知道的就是这个文件的绝对路径（否则只能去翻 README）。
                          "hostDir": HERE, "configPath": CONFIG_PATH,
                          "ocrEngine": SETTINGS.get("ocrEngine") or "local",
                          "ocrDesc": ocr_engine_desc(),
                          "translateEngine": SETTINGS.get("translateEngine") or "sf",
                          "leader": IS_LEADER})
    except Exception:
        pass


def notify(text):
    """把提示送到**用户实际能看见**的地方：
    - NM 模式（浏览器拉起，stdin 是管道）→ 发 NM toast；
    - 真控制台 → 打印 stderr（真控制台 Unicode 安全）；
    - pythonw 无控制台 → 弹一个自动消失的小窗（否则提示会凭空消失，用户一脸茫然）。
    无论哪条路，都同时写入 data/host.log 留痕。
    """
    host_log(text)
    if not STANDALONE and _has_nm_stdio():
        # 真·被浏览器拉起：走 NM toast（此时 write 一定成功）
        with _WRITE_LOCK:
            nm_write({"type": "toast", "text": text})
        return
    if _is_console():
        try:
            print("[winocr-host] " + str(text), file=sys.stderr, flush=True)
        except Exception:
            pass
        return
    # pythonw 且没有浏览器管道（手动双击 launcher / 独立模式）→ 弹小窗，
    # 否则提示会凭空消失。host_log 已在上方写入，事后可查。
    ui_toast(text)


# --------------------- 热键解析与注册 ---------------------
# 支持 "ctrl+shift+m" / "ctrl+alt+z" / "alt+shift+f9" 等；修饰键可多个。
_MODS = {'ctrl': 0x0002, 'control': 0x0002, 'alt': 0x0001, 'shift': 0x0004, 'win': 0x0008}
MOD_NOREPEAT = 0x4000
# 备用键：配置的热键被占用时依次尝试（很多工具都抢 ctrl+shift+m，例如 WinOCR 3.4 的蒙版翻译）
FALLBACK_HOTKEYS = ['ctrl+alt+m', 'ctrl+shift+f9', 'alt+shift+m', 'ctrl+alt+z']

# 退出键：一个宿主只在需要时存在，给用户一个不用找脚本就能关掉它的办法。
# 为什么不用裸 Esc：RegisterHotKey 注册裸 Esc 会**劫持全系统的 Esc**（对话框/游戏/浏览器全都失效），
# 所以退出必须是"修饰键 + 键"的组合。浮窗内的 Esc 只关窗，不影响宿主。
HOTKEY_ID_CAPTURE = 1
HOTKEY_ID_QUIT = 2
QUIT_FALLBACK_HOTKEYS = ['ctrl+alt+q', 'ctrl+shift+q', 'alt+shift+q']


def parse_hotkey(spec):
    """'ctrl+shift+m' -> (mods, vk)；无法解析返回 None。"""
    if not spec:
        return None
    parts = [p.strip().lower() for p in str(spec).split('+') if p.strip()]
    if len(parts) < 2:
        return None
    mods, key = 0, None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        else:
            key = p
    if not mods or not key:
        return None
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith('f') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in ('space', 'enter', 'tab'):
        vk = {'space': 0x20, 'enter': 0x0D, 'tab': 0x09}[key]
    else:
        return None
    return (mods, vk)


def _register_first_available(user32, specs, hid=1):
    """按顺序尝试注册，返回第一个成功的 (spec, mods, vk)。

    hid 是 RegisterHotKey 的热键 id —— 截图键用 1、退出键用 2，消息循环里靠它区分。
    """
    for spec in specs:
        p = parse_hotkey(spec)
        if not p:
            continue
        mods, vk = p
        if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
            return (spec, mods, vk)
    return None


# 热键线程 id 与线程消息：
#   RELOAD   扩展同步来新热键 → 即时换键（仅 leader 状态下有效）
#   ACQUIRE  本实例当选 leader → 注册截图键 + 退出键
#   RELEASE  本实例失去 leader（正常不会发生，防御性处理）→ 注销全部热键
HOTKEY_TID = 0
HK_READY = threading.Event()     # 热键线程已拿到自身 tid，可以接收线程消息
WM_RELOAD_HOTKEY = 0x8001        # WM_APP + 1
WM_HK_ACQUIRE = 0x8002
WM_HK_RELEASE = 0x8003


def post_hotkey_message(msg):
    """向热键线程发消息；tid 未知/线程已退出时静默失败。"""
    if not HOTKEY_TID:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.PostThreadMessageW(HOTKEY_TID, msg, 0, 0))
    except Exception:
        return False


def save_config():
    """把 SETTINGS 里属于配置的键写回 winocr_config.json（只写已知键，不污染文件）。"""
    try:
        with SETTINGS_LOCK:
            out = {}
            for k in default_config().keys():
                if k in SETTINGS:
                    out[k] = SETTINGS[k]
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def request_hotkey_reload():
    """通知热键线程重新注册（线程 id 未知时静默忽略）。"""
    if not HOTKEY_TID:
        return
    try:
        import ctypes
        ctypes.windll.user32.PostThreadMessageW(HOTKEY_TID, WM_RELOAD_HOTKEY, 0, 0)
    except Exception:
        pass


# --------------------- 设置合并：凭据空值不覆盖 ---------------------
# 扩展推来的 settings 是「全量快照」，其中 sfKey 为空**不代表用户想清空 key**，
# 而往往只是选项页里填了却没点「保存」（实测踩到：本地配置里本来有 key，
# 被扩展推来的空值 + save_config() 一落盘就抹掉了）。所以：空凭据不覆盖旧值。
_CREDENTIAL_KEYS = ('sfKey', 'lexiangToken', 'obsidianKey')


def merge_settings(incoming):
    """把扩展推来的设置合进 SETTINGS，凭据类键的空值不覆盖已有的非空值。"""
    out = dict(incoming or {})
    with SETTINGS_LOCK:
        for k in _CREDENTIAL_KEYS:
            v = out.get(k)
            if isinstance(v, str) and not v.strip() and str(SETTINGS.get(k) or '').strip():
                host_log('忽略扩展推来的空 %s：保留本地已保存的凭据（要清空请在选项页显式清除）' % k)
                out.pop(k, None)
    return out


# --------------------- 本地 OCR 诊断 ---------------------
_LAST_LOCAL_ERR = ''


def local_ocr_diag():
    """本地 OCR 不可用时给出**可执行**的说明：缺什么、该用哪个解释器装。"""
    lines = ['当前解释器：%s' % sys.executable]
    try:
        import pyenv
        miss = pyenv.missing_local()
        if miss:
            lines.append('缺依赖：%s' % ', '.join(miss))
            lines.append('修复：python -m pip install rapidocr onnxruntime numpy Pillow')
            best, _m, _d = pyenv.pick_best()
            if best:
                lines.append('本机已有合格解释器：%s（宿主会在下次启动时自动改用它）' % best)
        else:
            lines.append('依赖齐全 → 问题出在模型或引擎加载，详见 data/host.log')
    except Exception as e:
        lines.append('自检失败：%s' % e)
    return lines


# 超时按用途区分：云端 OCR（VL 模型）实测要 100s+，翻译只要几秒。
# 之前统一 30s，导致模型名对了也会 "read operation timed out"（实测踩到）。
SF_TRANSLATE_TIMEOUT = 60
SF_OCR_TIMEOUT = 240


def sf_error_text(prefix, raw):
    """把 SF 的原始错误体整理成一句人话。

    SF 有两种错误外壳：`{"error":{...}}` 和 `{"code":20012,"message":"..."}`；
    以前是直接把整段 JSON 丢给用户看（截图里那串就是这个），现在解析出 message，
    并对 20012 给出「模型名要写全称」的可操作提示。
    """
    text = str(raw or "")
    msg, code = "", None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            msg = str(obj.get("message") or "")
            code = obj.get("code")
    except Exception:
        pass
    if not msg:
        msg = text[:200]
    if code == 20012 or "does not exist" in msg.lower():
        return ("%s模型名不存在（%s）。硅基流动上模型 id 必须写全称："
                "OCR 用 PaddlePaddle/PaddleOCR-VL-1.5，翻译用 Qwen/Qwen3-8B；"
                "可改 %s 里的 sfOcrModel / sfModel。"
                % (prefix, msg, os.path.basename(CONFIG_PATH)))
    return "%s%s" % (prefix, msg)


def sf_ocr(data_url):
    with SETTINGS_LOCK:
        sf_ocr_model = normalize_sf_model(SETTINGS.get("sfOcrModel"),
                                          default_config()["sfOcrModel"])
        sf_key = SETTINGS["sfKey"]
    j = translate.sf_post("/chat/completions", {
        "model": sf_ocr_model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "OCR all text in this image. Output only the recognized text, preserving line breaks."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}],
        "max_tokens": 2048,
    }, sf_key, timeout=SF_OCR_TIMEOUT)
    if j.get("error"):
        return sf_error_text("OCR失败: ", j["error"])
    out = (j.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
    if not out:
        return "OCR失败: 模型返回空内容（图片里可能没有文字；模型=%s）" % sf_ocr_model
    return out


# --------------------- OCR 调度：本地优先，云端回退 ---------------------
def ocr_png(png_bytes):
    """OCR 一张 PNG。返回识别文本，失败时返回以 "OCR失败" 开头的说明。

    默认走本地 PP-OCRv6（离线、零 key、实测 ~1.5s 且截图场景比云端更准）。
    两种回落都只在「本地引擎本身不可用」时发生：
      - 缺依赖/模型 → 回落云端；
      - 本地引擎正常跑但**没识别到文字**（空白/无文字图）→ 直接返回空串，
        不再去问云端：云端也认不出凭空出现的字，反而白白慢几十秒。
    """
    with SETTINGS_LOCK:
        ocr_engine = (SETTINGS.get("ocrEngine") or "local").lower()
        local_tier = SETTINGS.get("localOcrTier") or ocr_local.DEFAULT_TIER
    if ocr_engine == "local":
        global _LAST_LOCAL_ERR
        _LAST_LOCAL_ERR = ''
        try:
            import ocr_local
            ok, why = ocr_local.available()
            if not ok:
                raise RuntimeError(why)
            tier = local_tier
            text, conf = ocr_local.recognize_png(png_bytes, tier)
            if text.strip():
                host_log("本地 OCR：%s 档，置信度 %.3f，%d 字" % (tier, conf, len(text)))
                return text
            _LAST_LOCAL_ERR = "本地 OCR 未识别到文字（图片里可能本来就没有文字，已不再回落云端）"
            host_log(_LAST_LOCAL_ERR)
            return ""
        except Exception as e:
            _LAST_LOCAL_ERR = "%s: %s" % (type(e).__name__, e)
            host_log("本地 OCR 不可用（%s），回落云端" % e)
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    return sf_ocr(data_url)


# --------------------- 截屏 ---------------------
# 截屏实现已拆到 screenshot.py（ImageGrab 优先、BitBlt 兜底）
from screenshot import screenshot_png_bytes

# --------------------- 翻译 ---------------------
# 翻译实现已拆到 translate.py（SF / MyMemory）
import translate
translate.set_settings(SETTINGS, SETTINGS_LOCK)


# --------------------- 区域画框（全屏遮罩 + 拖拽选区） ---------------------
def select_region(root):
    """弹出全屏半透明遮罩，鼠标拖拽画框。返回 (x, y, w, h) 屏幕绝对坐标；Esc 取消返回 None。"""
    sel = {}
    ov = tk.Toplevel(root)
    ov.attributes('-fullscreen', True)
    ov.attributes('-topmost', True)
    ov.attributes('-alpha', 0.3)          # 整体暗化遮罩
    ov.configure(bg='black')
    cv = tk.Canvas(ov, bg='black', cursor='cross', highlightthickness=0)
    cv.pack(fill='both', expand=True)

    sx = sy = None
    rect = None
    lbl = None

    def down(e):
        nonlocal sx, sy, rect, lbl
        sx, sy = e.x_root, e.y_root
        if rect:
            cv.delete(rect); rect = None
        if lbl:
            cv.delete(lbl); lbl = None

    def move(e):
        nonlocal rect, lbl
        if sx is None:
            return
        x0, y0, x1, y1 = sx, sy, e.x_root, e.y_root
        if rect:
            cv.delete(rect)
        rect = cv.create_rectangle(x0, y0, x1, y1, outline='white', width=2)
        wpx, hpx = abs(x1 - x0), abs(y1 - y0)
        if lbl:
            cv.delete(lbl)
        lbl = cv.create_text(min(x0, x1) + 4, min(y0, y1) - 12, anchor='nw',
                             text='%d × %d' % (wpx, hpx), fill='white',
                             font=('Segoe UI', 11, 'bold'))

    def up(e):
        nonlocal sx, sy
        if sx is None:
            return
        x0, y0, x1, y1 = sx, sy, e.x_root, e.y_root
        sel['region'] = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        ov.destroy()

    def esc(e):
        sel['cancel'] = True
        ov.destroy()

    cv.bind('<ButtonPress-1>', down)
    cv.bind('<B1-Motion>', move)
    cv.bind('<ButtonRelease-1>', up)
    ov.bind('<Escape>', esc)
    ov.focus_set()
    root.wait_window(ov)

    if sel.get('cancel'):
        return None
    return sel.get('region')


# --------------------- 浮窗（独立 OS 表面） ---------------------
def show_result(root, original, translation):
    win = tk.Toplevel(root)
    win.title("WinOCR")
    win.attributes("-topmost", True)
    win.geometry("440x320")
    win.configure(bg="#ffffff")

    # 可拖拽标题栏
    bar = tk.Frame(win, bg="#1677ff", height=22)
    bar.pack(fill="x")
    tk.Label(bar, text="WinOCR · 置顶", bg="#1677ff", fg="#fff", font=("Segoe UI", 11)).pack(side="left", padx=8)
    close_btn = tk.Button(bar, text="×", bg="#1677ff", fg="#fff", bd=0, command=win.destroy, font=("Segoe UI", 12))
    close_btn.pack(side="right", padx=6)
    drag = {"x": 0, "y": 0}
    def press(e): drag.update(x=e.x, y=e.y)
    def move(e):
        win.geometry("+%d+%d" % (win.winfo_x() + e.x - drag["x"], win.winfo_y() + e.y - drag["y"]))
    bar.bind("<ButtonPress-1>", press)
    bar.bind("<B1-Motion>", move)

    body = tk.Frame(win, bg="#fff")
    body.pack(fill="both", expand=True, padx=10, pady=8)

    tk.Label(body, text="原文 / OCR", bg="#fff", fg="#444", anchor="w").pack(fill="x")
    o = tk.Text(body, height=7, wrap="word", bd=0.5, relief="solid")
    o.insert("1.0", original); o.pack(fill="both", expand=True)
    tk.Label(body, text="译文", bg="#fff", fg="#1677ff", anchor="w").pack(fill="x")
    t = tk.Text(body, height=7, wrap="word", bd=0.5, relief="solid")
    t.insert("1.0", translation); t.pack(fill="both", expand=True)

    def copy():
        root.clipboard_clear(); root.clipboard_append(translation)
    tk.Button(body, text="复制译文", command=copy, bg="#f5f5f5", fg="#1677ff", relief="solid", bd=0.5).pack(anchor="e", pady=4)

    # 浮窗内按 Esc 关窗（只关这个窗，不退出宿主；宿主本身有专用退出热键）。
    # 不做 focus_force —— 抢焦点会打断阅读，违反"工具是从属表面"。
    win.bind('<Escape>', lambda e: win.destroy())
    for w in (win, o, t):
        w.bind('<Escape>', lambda e: win.destroy())

    win.after(RESULT_WINDOW_AUTO_CLOSE_MS, lambda: win.destroy() if win.winfo_exists() else None)


# --------------------- 本地记录（独立模式） ---------------------
def save_record_local(png_bytes, ocr, translation):
    """日积累 Markdown + assets PNG。与扩展侧格式对齐（标准图片链接，Obsidian 亦支持）。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, 'assets'), exist_ok=True)
        now = datetime.datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        md_path = os.path.join(DATA_DIR, date_str + '.md')
        img_name = now.strftime('%Y%m%d_%H%M%S') + '.png'
        img_path = os.path.join(DATA_DIR, 'assets', img_name)
        with open(img_path, 'wb') as f:
            f.write(png_bytes)

        block = (
            "\n## " + now.strftime('%H:%M:%S') + "\n\n"
            "![截图](assets/" + img_name + ")\n\n"
            "**原文**\n" + ocr + "\n\n"
            "**译文**\n" + translation + "\n"
        )
        if not os.path.exists(md_path):
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("---\ntitle: WinOCR 日积累 " + date_str + "\ndate: " + date_str + "\n---\n")
        with open(md_path, 'a', encoding='utf-8') as f:
            f.write(block)
    except Exception as e:
        pass  # 本地记录失败不影响浮窗展示


# --------------------- 捕获流程（主线程执行 UI/回传） ---------------------
def do_capture(root):
    # 1) 区域画框
    region = select_region(root)
    if not region:
        return  # 用户按 Esc 取消
    # 遮罩刚 destroy()，DXGI Desktop Duplication（ImageGrab）取的是 DWM 合成帧，
    # 立即抓可能把半透明遮罩残影拍进去；等 SCREENSHOT_DELAY_MS 让它合成掉（人眼几乎无感）。
    time.sleep(SCREENSHOT_DELAY_MS / 1000.0)
    # 2) 截选定区域
    try:
        png = screenshot_png_bytes(*region)
    except Exception as e:
        host_log('截图失败: %s: %s' % (type(e).__name__, e))
        show_result(root, "截图失败: " + str(e), "")
        return
    if not png:
        show_result(root, "截图失败", "")
        return
    # 3) OCR（本地 PP-OCRv6 优先；不可用时自动回落云端 SF）
    #    注意：不再"无 key 就直接拒绝" —— 本地 OCR 是零 key 的，没 key 也照样能出文字。
    try:
        ocr = ocr_png(png)
    except Exception as e:
        host_log('OCR失败: %s: %s' % (type(e).__name__, e))
        ocr = "OCR失败: " + str(e)
    failed = ocr.startswith("OCR失败")

    # 4) 翻译（引擎由 translateEngine 决定：sf / mymemory / none）
    tr = ""
    # 本地引擎正常跑完但没检出文字（选区是空白/纯图，或文字太小）→ ocr 是空串。
    # 绝不能拿空串去调翻译：实测 Qwen3 会把 system 提示词本身当成「原文」翻译成中文
    # 回填译文框（“你是一位专业的翻译人员……”），看起来像出了结果，其实是提示词泄漏，
    # 用户根本无法判断发生了什么。这里直接给出可操作的提示，跳过翻译请求。
    empty_ocr = (not failed) and not ocr.strip()
    if empty_ocr:
        ocr = "（未识别到文字）"
        with SETTINGS_LOCK:
            hotkey_hint = ACTIVE_HOTKEY or SETTINGS.get('hotkey') or '热键'
        tr = ("框选区域里没有检出文字。请重新按 %s 框选：尽量贴紧文字、不要带大片空白，"
              "细小文字可把区域框大一些再试。" % hotkey_hint.upper())
        if _LAST_LOCAL_ERR:
            tr += "\n详情：%s" % _LAST_LOCAL_ERR
        with SETTINGS_LOCK:
            ocr_engine_hint = (SETTINGS.get("ocrEngine") or "local").lower()
            te_hint = str(SETTINGS.get("translateEngine") or "sf").lower()
            sf_key_hint = SETTINGS.get("sfKey")
        if ocr_engine_hint == "local":
            tr += ('\n当前是本地离线 OCR，识别不出时不会自动问云端；若确认区内有清晰文字仍识别不出，'
                   '可在扩展选项（或 %s）里把 ocrEngine 改成 "sf"，用云端视觉模型再试。'
                   % os.path.basename(CONFIG_PATH))
    elif not failed:
        te = te_hint
        if te == "none":
            tr = "（当前为「仅 OCR」模式，未翻译；可在扩展选项或 %s 里把 translateEngine 改成 sf / mymemory）" \
                % os.path.basename(CONFIG_PATH)
        elif te == "sf" and not sf_key_hint:
            tr = "（未配置 SiliconFlow key，仅显示 OCR 结果；也可把 translateEngine 改成 mymemory 免 key 翻译）"
        else:
            try:
                tr = translate.translate_text(ocr)
            except Exception as e:
                tr = "翻译失败: " + str(e)
    elif failed and not sf_key_hint:
        # 两条路都断了：把「为什么」讲清楚，别让用户对着一句 Token is invalid 猜。
        ocr += "\n\n— 本地 OCR 也不可用 —"
        if _LAST_LOCAL_ERR:
            ocr += "\n原因：%s" % _LAST_LOCAL_ERR
        for line in local_ocr_diag():
            ocr += "\n  · " + line
        ocr += ("\n\n— 也没有 SiliconFlow key（云端回退同样不可用）—"
                "\n%s 里的 sfKey 是空的。" % CONFIG_PATH)
        if STANDALONE:
            ocr += "\n独立模式只读上面这个本地文件，和浏览器扩展「选项」页里的设置是" \
                   "两份互不同步的配置 —— 在扩展里连上宿主 ≠ 本地配置里有 key。"

    # 5) 浮窗
    show_result(root, ocr, tr)
    # 6) 落地
    if STANDALONE:
        save_record_local(png, ocr, tr)
    with _WRITE_LOCK:
        nm_write({"type": "record", "record": {"type": "image", "source": "screen", "ocr": ocr, "translation": tr}})


def capture_in_thread(root):
    threading.Thread(target=lambda: do_capture(root), daemon=True).start()


# --------------------- 热键线程 ---------------------
def hotkey_thread(root):
    import ctypes
    import ctypes.wintypes   # 子模块，`import ctypes` 不会自动带出；缺它则 ctypes.wintypes 报 AttributeError
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    WM_HOTKEY = 0x0312

    global ACTIVE_HOTKEY, ACTIVE_QUIT_HOTKEY, IS_LEADER, HOTKEY_TID
    HOTKEY_TID = kernel32.GetCurrentThreadId()   # 供扩展同步新热键时 PostThreadMessage 用
    HK_READY.set()                               # 通知主线程：可以开始选举/发消息了
    acquired = False                             # 本线程是否已注册热键（= 当前是 leader）

    def unregister_all():
        global ACTIVE_HOTKEY, ACTIVE_QUIT_HOTKEY, IS_LEADER
        for hid in (HOTKEY_ID_CAPTURE, HOTKEY_ID_QUIT):
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
        ACTIVE_HOTKEY = ''
        ACTIVE_QUIT_HOTKEY = ''
        IS_LEADER = False

    def _register_with_retry(spec, hid, tries=15):
        """只试指定组合键；被占用时每 0.2s 重试一次（最多 ~3s）。

        交接场景必须重试：旧 leader 从名册摘除到系统真正释放热键之间有窗口
        （优雅退出是毫秒级，被强杀则等系统回收），新 leader 第一次注册常撞上
        HOTKEY_ALREADY_REGISTERED；不重试就会错误地退到备选键，用户继续按
        Ctrl+Alt+Q 时谁都收不到（实测：pid 488 退成了 ctrl+alt+m/ctrl+shift+q）。
        """
        p = parse_hotkey(spec)
        if not p:
            return None
        mods, vk = p
        for i in range(tries):
            if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                return spec
            time.sleep(HOTKEY_REGISTER_RETRY_INTERVAL)
        return None

    def acquire():
        nonlocal acquired
        if acquired:
            return
        global ACTIVE_HOTKEY, ACTIVE_QUIT_HOTKEY
        with SETTINGS_LOCK:
            want_cap = SETTINGS.get('hotkey') or 'ctrl+shift+m'
            want_quit = SETTINGS.get('quitHotkey') or 'ctrl+alt+q'
        # 1) 目标键优先并重试等旧 owner 释放；2) 确实拿不到才退备选
        spec = _register_with_retry(want_cap, HOTKEY_ID_CAPTURE)
        if not spec:
            got = _register_first_available(
                user32, [k for k in FALLBACK_HOTKEYS if k != want_cap], HOTKEY_ID_CAPTURE)
            spec = got[0] if got else None
            if spec:
                notify('热键 %s 持续被占用，已自动改用 %s' % (want_cap, spec.upper()))
        ACTIVE_HOTKEY = spec or ''

        spec_q = _register_with_retry(want_quit, HOTKEY_ID_QUIT)
        if not spec_q:
            got_q = _register_first_available(
                user32, [k for k in QUIT_FALLBACK_HOTKEYS if k != want_quit], HOTKEY_ID_QUIT)
            spec_q = got_q[0] if got_q else None
        ACTIVE_QUIT_HOTKEY = spec_q or ''

        ok = bool(spec)
        acquired = ok
        IS_LEADER = ok
        announce_hello()   # 此时截图键 + 退出键都注册完，扩展拿到完整状态
        if ok:
            host_log('已成为 leader：持有热键 %s / 退出键 %s（pid %d）'
                     % (ACTIVE_HOTKEY or '-', ACTIVE_QUIT_HOTKEY or '-', os.getpid()))
        else:
            notify('热键注册失败：%s 与全部备选键都被占用，请在设置页更换 hotkey。' % want_cap)

    def release():
        nonlocal acquired
        unregister_all()
        acquired = False
        host_log('交出热键所有权（pid %d）' % os.getpid())

    # 多实例：线程启动时**不注册**，等 leader_watcher 选举出本实例后再 ACQUIRE。
    # 这样同一台机器上可以并存任意多个宿主，而全局热键始终只被 leader 一个持有。
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            if int(msg.wParam) == HOTKEY_ID_QUIT:
                # 只关当前 leader 自己；其它实例由 watcher 在 ~0.7s 内顺位接管
                root.after(0, lambda: quit_via_hotkey(root))
            else:
                root.after(0, lambda: capture_in_thread(root))
        elif msg.message == WM_HK_ACQUIRE:
            acquire()
        elif msg.message == WM_HK_RELEASE:
            release()
        elif msg.message == WM_RELOAD_HOTKEY:
            # 扩展同步来新热键 → 先注销旧的（截图键 + 退出键），再按新键注册；
            # 非 leader 没有注册过，收到也忽略（acquire 时自会读到新配置）。
            if not acquired:
                continue
            for hid in (HOTKEY_ID_CAPTURE, HOTKEY_ID_QUIT):
                try:
                    user32.UnregisterHotKey(None, hid)
                except Exception:
                    pass
            ACTIVE_HOTKEY = ''
            acquired = False
            acquire()


def leader_watcher(root):
    """每 0.7s 做一次名册选举：最旧存活实例持有热键，leader 死后顺位接管。"""
    global IS_LEADER
    standby_told = False
    while not STOP_EVENT.wait(LEADER_WATCH_INTERVAL):
        try:
            leader, n_alive = roster_touch()
        except Exception as e:
            host_log('名册选举失败：%s' % e)
            continue
        me = os.getpid()
        if leader == me and not IS_LEADER:
            IS_LEADER = True
            standby_told = False
            post_hotkey_message(WM_HK_ACQUIRE)
            with SETTINGS_LOCK:
                hotkey_str = str(SETTINGS.get('hotkey') or 'alt+q').upper()
                quit_hotkey_str = str(SETTINGS.get('quitHotkey') or 'ctrl+alt+q').upper()
            notify('已就绪（pid %d，共 %d 个实例）：按 %s 截图；%s 关闭当前实例（再按关闭下一个）'
                   % (me, n_alive, hotkey_str, quit_hotkey_str))
        elif leader != me and IS_LEADER:
            IS_LEADER = False
            post_hotkey_message(WM_HK_RELEASE)
        elif leader not in (me, 0) and not standby_told:
            standby_told = True
            notify('备用宿主已启动（pid %d，共 %d 个实例）：热键暂由 pid %d 持有，'
                   '它退出后本实例自动接管；Ctrl+Alt+Q 从最旧实例逐个关闭。'
                   % (me, n_alive, leader))


def quit_via_hotkey(root):
    """Ctrl+Alt+Q：只注销自己这一个实例，并告知还剩几个；剩余实例自动顺位接管。"""
    # 顺序很重要：**先注销热键、再从名册摘除**。否则接管者在下一轮选举（≤0.7s）
    # 就会尝试注册，而系统尚未释放本实例的热键 → 新 leader 撞 HOTKEY_ALREADY_REGISTERED
    # 后退到备选键，用户接着按 Ctrl+Alt+Q 就没人响应（实测复现）。
    try:
        import ctypes
        for hid in (HOTKEY_ID_CAPTURE, HOTKEY_ID_QUIT):
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
    except Exception:
        pass
    n_alive = 0
    try:
        _leader, n_alive = roster_touch(leave=True)
    except Exception:
        pass
    if n_alive > 0:
        reason = '退出热键（剩余 %d 个宿主，热键将自动交给下一个）' % n_alive
    else:
        reason = '退出热键（最后一个宿主已关闭）'
    request_quit(root, reason)


def request_quit(root, reason=''):
    """优雅退出宿主：从名册摘除 → 注销热键 → 销毁 Tk → mainloop 结束 → 进程退出。

    NM 模式下浏览器下次需要时会自动重新拉起，所以"退出"≈"断开"；
    想彻底不让它回来，还要在扩展选项里取消勾选「连接原生宿主」。
    """
    STOP_EVENT.set()
    try:
        roster_touch(leave=True)
    except Exception:
        pass
    msg = '宿主退出（%s）' % (reason or '手动')
    host_log(msg)
    try:
        import ctypes
        for hid in (HOTKEY_ID_CAPTURE, HOTKEY_ID_QUIT):
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
    except Exception:
        pass
    try:
        if not STANDALONE and _has_nm_stdio():
            with _WRITE_LOCK:
                nm_write({"type": "toast", "text": msg})
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


# --------------------- Native Messaging 读取线程 ---------------------
def nm_read_thread(root):
    if STANDALONE:
        return  # 独立模式不读 stdin，避免阻塞/误退出
    if not _has_nm_stdio():
        # 手动双击 launcher（pythonw 无管道）时 sys.stdin 是 None：
        # 直接说明原因并退出本线程，热键截图仍然可用，别静默挂掉。
        notify('未检测到浏览器管道，扩展联动已关闭（热键截图仍可用）。'
               '要联动请从扩展选项里勾选「连接原生宿主」并重新加载扩展。')
        return
    reason = '浏览器主动断开（下次用时会自动重新拉起）'
    while True:
        try:
            msg = nm_read()
        except Exception as e:
            reason = '读取失败：%s: %s' % (type(e).__name__, e)
            break
        if not msg:
            break  # 连接断开 → 退出（浏览器会重新拉起）
        if msg.get("type") == "settings":
            s = merge_settings(msg.get("settings") or {})
            old_hotkey = SETTINGS.get('hotkey')
            old_quit = SETTINGS.get('quitHotkey')
            with SETTINGS_LOCK:
                SETTINGS.update(s)
                if str(SETTINGS.get("translateEngine") or "").lower() not in ("sf", "mymemory", "none"):
                    SETTINGS["translateEngine"] = "sf"
            # 扩展推来的是全量快照（含翻译引擎/key/热键）：落盘，让下次独立模式
            # （run_host.bat，不经过浏览器）也能用到同一份配置；否则选项页里切了
            # MyMemory 只对当次 NM 会话生效，重启独立宿主后又回到 sf。
            save_config()
            host_log('已应用扩展设置：翻译引擎=%s OCR=%s 热键=%s'
                     % (SETTINGS.get('translateEngine'), SETTINGS.get('ocrEngine'),
                        SETTINGS.get('hotkey')))
            # 热键被改 → 通知热键线程即时重新注册（截图键与退出键都覆盖，无需重启宿主）
            if ((s.get('hotkey') and SETTINGS.get('hotkey') != old_hotkey) or
                    (s.get('quitHotkey') and SETTINGS.get('quitHotkey') != old_quit)):
                request_hotkey_reload()
            # 引擎等状态变了 → 重报 hello，让选项页显示最新状态
            announce_hello()
        elif msg.get("type") == "settings.get":
            # 扩展选项页「从本地配置导入」：把 winocr_config.json 里已生效的设置回读过去。
            # 用处：standalone 与扩展是两份配置，用户常只填了一边 —— 一键对齐，别让他手抄 key。
            snap = {}
            for k in default_config().keys():
                if k in SETTINGS:
                    snap[k] = SETTINGS[k]
            with _WRITE_LOCK:
                nm_write({"type": "settings.current", "id": msg.get("id"),
                          "settings": snap, "configPath": CONFIG_PATH, "hostDir": HERE})
        elif msg.get("type") == "openConfigDir":
            # 选项页「打开本地配置文件」：在资源管理器里选中 winocr_config.json。
            # 用 /select 而不是直接打开文件，避免把 .json 关联到某个编辑器/浏览器。
            try:
                if os.name == 'nt':
                    subprocess.Popen('explorer /select,"%s"' % CONFIG_PATH)
                else:
                    subprocess.Popen(['xdg-open', HERE])
            except Exception as e:
                host_log('打开配置目录失败：%s' % e)
        elif msg.get("type") == "capture":
            root.after(0, lambda: capture_in_thread(root))
        elif msg.get("type") == "ocr":
            # 扩展侧「粘贴/拖拽图片 OCR」：让浏览器也吃到本地 OCR 的速度。
            # 走线程，别堵住 NM 读取循环（否则 capture 消息会被卡在后面）。
            mid, data_url = msg.get("id"), msg.get("dataUrl") or ""

            def _do_ocr(mid=mid, data_url=data_url):
                try:
                    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
                    png = base64.b64decode(b64) if b64 else b""
                    if not png:
                        with _WRITE_LOCK:
                            nm_write({"type": "ocr.result", "id": mid,
                                      "error": "OCR失败: 没有收到图片数据"})
                        return
                    text = ocr_png(png)
                    with _WRITE_LOCK:
                        if text.startswith("OCR失败"):
                            # 失败要作为 error 回传，扩展才会显示错误态；
                            # 塞进 text 会被当成"识别结果"。
                            nm_write({"type": "ocr.result", "id": mid, "error": text})
                        else:
                            nm_write({"type": "ocr.result", "id": mid, "text": text})
                except Exception as e:
                    host_log('NM OCR失败: %s: %s' % (type(e).__name__, e))
                    with _WRITE_LOCK:
                        nm_write({"type": "ocr.result", "id": mid, "error": "OCR失败: %s" % e})

            threading.Thread(target=_do_ocr, daemon=True).start()
    host_log('NM 通道结束：%s' % reason)
    # ⚠️ 这里不能 sys.exit(0)：本函数运行在 daemon 读取线程，sys.exit 只结束该
    # 线程，主线程的 root.mainloop() 照常运行 → 进程不退、若它还是 leader 还会继续
    # 独占全局热键；浏览器重连拉起的新宿主虽能并存，但要等这个僵尸让位才接得到热键。
    # 正确做法：切回主线程走与退出热键相同的完整退出 —— 名册摘除 → 注销热键 →
    # 销毁 Tk → mainloop 返回 → 进程结束；下一名实例 0.7s 内自动接管。
    try:
        root.after(0, lambda: request_quit(root, reason))
    except Exception:
        # 竞态兜底：root 已被销毁（如刚按过退出热键），after 会抛 TclError；
        # 此时所有工作线程都是 daemon，直接结束进程即可。
        os._exit(0)


# --------------------- 主入口 ---------------------
def run_doctor():
    """`--doctor`：一条命令说清「为什么 OCR 不通」。

    排查顺序按真实因果排：解释器 → 本地依赖 → 本地模型 → key → 桥接 → 单实例。
    """

    def say(line=''):
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or 'ascii'
            print(line.encode(enc, 'replace').decode(enc, 'replace'), flush=True)

    say('WinOCR-Html host doctor')
    if STANDALONE:
        mode = 'standalone (run_host.bat / --standalone)'
    elif _has_nm_stdio():
        mode = 'native-messaging (started by the browser)'
    else:
        mode = 'INVALID - neither --standalone nor a browser NM pipe'
    say('  mode        : %s' % mode)
    say('  cwd/hostdir : %s' % HERE)

    say('')
    say('  [1/6] interpreter & deps (host needs tkinter + local-OCR stack)')
    say('        current  : %s' % sys.executable)
    try:
        import pyenv
        need = ("tkinter",) + tuple(pyenv.REQUIRED)
        say('        needs    : %s' % ', '.join(need))
        say('        missing  : %s' % (','.join(pyenv.missing_local(need)) or '(none - this one is fine)'))
        say('        all candidates:')
        best = None
        for cand in pyenv.candidates():
            ok, _m, detail = pyenv.probe(cand, need)
            say('          [%s] %s' % ('OK' if ok else '--', cand))
            if not ok:
                say('               %s' % detail[:110])
            elif best is None:
                best = cand
        if best:
            say('        => host would use: %s' % best)
        else:
            say('        => NO candidate satisfies the host; the host will run in')
            say('           cloud-only mode. Fix: %s -m pip install rapidocr' % sys.executable)
            say('           onnxruntime numpy Pillow  (tkinter comes with the official build)')
    except Exception as e:
        say('        self-check failed: %s' % e)

    say('')
    say('  [2/6] local OCR model (models/ocr/v6_*)')
    try:
        import ocr_local
        st = ocr_local.status()
        say('        available: %s   reason: %s' % (st['available'], st['reason']))
        say('        tiers    : %s' % json.dumps(st['tiers']))
        say('        dir      : %s' % st['dir'])
    except Exception as e:
        say('        failed: %s' % e)

    say('')
    say('  [3/6] config file (standalone reads THIS one)')
    cfg = {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception as e:
        say('        unreadable: %s' % e)
    say('        path     : %s' % CONFIG_PATH)
    if cfg:
        key = cfg.get('sfKey') or ''
        say('        ocrEngine: %s   tier: %s' % (cfg.get('ocrEngine'), cfg.get('localOcrTier')))
        say('        sfKey    : %s' % (('set (%d chars, %s...)' % (len(key), key[:6])) if key.strip() else 'EMPTY'))
        say('        sfUrl    : %s' % cfg.get('sfUrl'))
        say('        sfModel  : %s' % cfg.get('sfModel'))
        say('        sfOcr    : %s' % cfg.get('sfOcrModel'))
        say('        hotkey   : %s   quit: %s' % (cfg.get('hotkey'), cfg.get('quitHotkey')))

    say('')
    say('  [4/6] native-messaging registration')
    hj = os.path.join(HERE, 'com.winocr.host.json')
    try:
        with open(hj, 'r', encoding='utf-8') as f:
            host_json = json.load(f)
        origins = host_json.get('allowed_origins') or []
        say('        manifest : %s' % hj)
        say('        launcher : %s (exists=%s)' % (host_json.get('path'), os.path.isfile(host_json.get('path') or '')))
        bad = [o for o in origins if '<EXTENSION_ID>' in o or not o]
        say('        origins  : %s' % (origins if origins else '(none - host cannot connect)'))
        say('        status   : %s' % ('OK' if origins and not bad else 'NEEDS FIX -> run: python setup_host.py'))
    except Exception as e:
        say('        unreadable: %s' % e)

    say('')
    say('  [5/6] launcher interpreter (NM mode uses winocr_launcher.bat)')
    try:
        with open(os.path.join(HERE, 'winocr_launcher.bat'), 'r', encoding='ascii', errors='replace') as f:
            for line in f:
                if 'python' in line.lower() and line.lstrip().lower().startswith('start'):
                    say('        %s' % line.strip())
                    break
    except Exception as e:
        say('        unreadable: %s' % e)

    say('')
    say('  [6/6] running host processes (multi-instance allowed; oldest owns hotkey)')
    try:
        hosts = find_running_hosts()
        say('        window scan : %s' % (', '.join('pid %d' % p for p in sorted(hosts)) or '(none)'))
        n = roster_count()
        say('        roster      : %d alive instance(s) (leader holds ALT+Q / CTRL+ALT+Q;'
            % n)
        say('                      CTRL+ALT+Q closes them one by one; stop_host.bat kills all)')
        with SETTINGS_LOCK:
            te = SETTINGS.get('translateEngine')
        say('        translateEngine=%s (sf/mymemory/none)' % te)
    except Exception as e:
        say('        failed: %s' % e)

    say('')
    say('done.')
    return 0


def main():
    # --stop：结束所有正在运行的宿主（供 stop_host.bat 调用），不需要 Tk
    if '--stop' in sys.argv[1:]:
        return 0 if stop_running_hosts() >= 0 else 1

    if '--doctor' in sys.argv[1:]:
        return run_doctor()

    # 解释器自举已在文件顶部（import tkinter 之前）完成，这里只留痕
    host_log('解释器自举：%s（当前 %s）' % (_PYENV_NOTE or 'unknown', sys.executable))

    load_config()  # 填充本地 config（NM 模式后续会被扩展 settings 覆盖）

    # ---- 多实例并存 ----
    # 不再做单实例拦截：允许多个宿主进程（浏览器拉起的 NM 宿主 + run_host.bat 的
    # 独立宿主可同时存在）。全局热键由 data/hosts.roster.json 名册选举出的唯一一个
    # leader 持有（leader_watcher），leader 退出后下一个实例 0.7s 内自动接管；
    # Ctrl+Alt+Q 一次只关 leader 一个，可逐个关完。旧版「僵尸独占热键 + 单实例
    # 硬拦截」的两难，由「NM 断管即退」+「名册选举」共同解决。
    try:
        _ld, _n = roster_touch()
        host_log('宿主实例登记 pid=%d（当前存活 %d 个，leader pid=%s）'
                 % (os.getpid(), _n, _ld))
    except Exception as e:
        host_log('名册登记失败（不影响运行，热键可能由其它实例持有）：%s' % e)

    root = tk.Tk()
    root.withdraw()  # 不显示主窗口，仅用 Toplevel 浮窗 / 选区遮罩
    root.title("WinOCR-Host")

    global ROOT
    ROOT = root                       # 供 notify() 在无控制台时弹小窗提示

    # ---- 启动方式校验 ----
    # 既不是 --standalone，又没有浏览器给的 NM 管道 → 这种进程什么也做不了，
    # 只会永久挂着一个全局热键（旧版就是这样累积出僵尸的），直接退出并说明正确用法。
    if not STANDALONE and not _has_nm_stdio():
        notify('启动方式无效：既没有 --standalone，也没有浏览器的 Native Messaging 管道。\n'
               '  · 要桌面截图 → 双击 run_host.bat（它会带 --standalone）\n'
               '  · 要和扩展联动 → 让浏览器自动拉起（先 install_host.bat 注册 + 选项里勾选）')
        try:
            root.destroy()
        except Exception:
            pass
        return 1

    # 启动即说明「用的是哪种模式 / 是否已桥接扩展」——这是最容易搞混的一点
    notify('WinOCR 宿主启动 · %s' % mode_desc())
    notify('OCR 引擎：%s' % ocr_engine_desc())

    # 预热本地 OCR：首次识别要构建 onnxruntime 会话（~1s），
    # 放到后台线程做掉，用户第一次按热键就不会等。
    def _warm():
        try:
            import ocr_local
            with SETTINGS_LOCK:
                ocr_engine_warm = (SETTINGS.get('ocrEngine') or 'local').lower()
                local_tier_warm = SETTINGS.get('localOcrTier') or 'tiny'
            if ocr_engine_warm == 'local':
                ok, why = ocr_local.available()
                if not ok:
                    notify('本地 OCR 不可用：%s（会在截图时自动回落云端）' % why)
                    return
                t0 = time.time()
                if ocr_local.warmup(local_tier_warm):
                    host_log('本地 OCR 预热完成 %.1fs' % (time.time() - t0))
        except Exception as e:
            host_log('本地 OCR 预热跳过：%s' % e)

    threading.Thread(target=_warm, daemon=True).start()

    t_hot = threading.Thread(target=hotkey_thread, args=(root,), daemon=True)
    t_hot.start()
    # 等热键线程拿到自己的线程 id 再开选举，避免第一条 ACQUIRE 消息丢失
    HK_READY.wait(PYENV_WAIT_TIMEOUT)

    threading.Thread(target=leader_watcher, args=(root,), daemon=True).start()

    if not STANDALONE:
        t_nm = threading.Thread(target=nm_read_thread, args=(root,), daemon=True)
        t_nm.start()
        # 立刻报一次 hello（此时还没当选 leader，hotkey 可能为空）；
        # 当选/热键注册完会再报一次完整状态。
        announce_hello()

    try:
        root.mainloop()
    finally:
        STOP_EVENT.set()
        try:
            roster_touch(leave=True)
        except Exception:
            pass
    # 跳过解释器 shutdown：多实例并存时 onnxruntime/tkinter 的析构可达 6-8s，
    # 期间进程挂着白占内存。此时名册已摘除、热键已注销、日志已落盘，强退无副作用。
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
