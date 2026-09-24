#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_host.py - build the Native Messaging glue for WinOCR-Html.

Generates / refreshes, in this directory:

  * winocr_launcher.bat    launcher (pure ASCII + CRLF) that starts the host
                           with pythonw, so no console window stays open
  * com.winocr.host.json   Native Messaging host manifest with the REAL
                           extension id(s) already filled in

Why this script exists
----------------------
1. Chrome/Edge reject a host manifest that is not strict JSON.  The old
   install_host.bat built it with a PowerShell `-replace` that added a second
   pair of quotes -> `"path": ""D:\\...\\x.bat""` -> invalid JSON -> the host
   could never be found ("Specified native messaging host not found").
2. `allowed_origins` needs the actual 32-char extension id (wildcards are NOT
   supported).  An unpacked extension's id is derived from its folder, so
   hard-coding one is fragile.  We detect it from the browser profiles.

Usage
-----
    python setup_host.py                  detect + write both files
    python setup_host.py --id <ext-id>    additionally allow this extension id
    python setup_host.py --check          dry run, print what would be written
"""

import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER_BAT = os.path.join(HERE, "winocr_launcher.bat")
HOST_JSON = os.path.join(HERE, "com.winocr.host.json")
HOST_SCRIPT = os.path.join(HERE, "winocr_host.py")
HOST_NAME = "com.winocr.host"
DESCRIPTION = "WinOCR-Html native host (Python)"

# The unpacked extension folder we are looking for (parent of this dir).
EXT_DIR = os.path.normcase(os.path.join(os.path.dirname(HERE), "extension"))

ID_RE = re.compile(r"^[a-p]{32}$")

BROWSER_ROOTS = [
    ("Edge", r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
    ("Chrome", r"%LOCALAPPDATA%\Google\Chrome\User Data"),
]


# --------------------------- console output (936-safe) ---------------------------
def emit(msg=""):
    """Print without ever raising UnicodeEncodeError (redirected stdout / 936)."""
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(text.encode(enc, "replace").decode(enc, "replace"), flush=True)


# --------------------------- extension id detection ---------------------------
def _load_json(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception:
        return None


def detect_extension_ids():
    """Return [(browser, profile, id)] for the WinOCR-Html extension.

    Unpacked extension ids are derived from the folder path, so we look for
    the profile entry whose `path` equals our extension directory.
    """
    hits = []
    for browser, raw_root in BROWSER_ROOTS:
        root = os.path.expandvars(raw_root)
        if not os.path.isdir(root):
            continue
        for entry in sorted(os.listdir(root)):
            pdir = os.path.join(root, entry)
            if not os.path.isdir(pdir):
                continue
            if entry != "Default" and not entry.startswith("Profile"):
                continue
            for fname in ("Secure Preferences", "Preferences"):
                data = _load_json(os.path.join(pdir, fname))
                if not data:
                    continue
                settings = (data.get("extensions") or {}).get("settings") or {}
                for eid, meta in settings.items():
                    if not ID_RE.match(eid or ""):
                        continue
                    path = str((meta or {}).get("path") or "")
                    if path and os.path.normcase(path).rstrip("\\/") == EXT_DIR:
                        hits.append((browser, entry, eid))
    # de-duplicate while keeping order
    seen, out = set(), []
    for b, p, eid in hits:
        if eid in seen:
            continue
        seen.add(eid)
        out.append((b, p, eid))
    return out


# --------------------------- launcher .bat (ASCII + CRLF) ---------------------------
def find_python_console():
    """Pick the interpreter the browser should spawn.

    Prefer one that actually has tkinter + the local-OCR stack, because the
    launcher decides who the browser spawns and a bare interpreter has no
    tkinter at all -> the host dies at import with nothing to print
    (pythonw has nowhere to write). Falls back to this interpreter's pythonw,
    then to PATH. winocr_host.py re-execs itself into a good interpreter
    anyway, so a miss here only costs one extra re-exec.
    """
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import pyenv
        exe, _miss, _detail = pyenv.pick_best(required=("tkinter",) + tuple(pyenv.REQUIRED))
        if exe:
            return pyenv.windowless_variant(exe) or exe
    except Exception:
        pass
    exe = sys.executable or ""
    if exe:
        cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(cand):
            return cand
    for name in ("pythonw", "python"):
        found = shutil.which(name)
        if found:
            return found
    return "pythonw"


def launcher_text(py_exe):
    """`start "" /b` keeps the inherited stdio pipes but lets cmd.exe exit
    immediately, so no console window lingers for the whole browser session."""
    # 将路径中的非 ASCII 字符替换为 ?（.bat 文件需要 ASCII）
    py_exe_ascii = py_exe.encode("ascii", "replace").decode("ascii")
    host_script_ascii = HOST_SCRIPT.encode("ascii", "replace").decode("ascii")
    return (
        "@echo off\r\n"
        "rem WinOCR-Html native host launcher (auto-generated by setup_host.py)\r\n"
        "rem Do not edit by hand - re-run: python setup_host.py\r\n"
        'start "" /b "%s" "%s" %%*\r\n' % (py_exe_ascii, host_script_ascii)
    )


def write_launcher(path, py_exe, dry_run=False):
    text = launcher_text(py_exe)
    # 路径可能含非 ASCII（如中文），用 replace 避免编码失败
    data = text.encode("ascii", "replace")
    if b"\r\n" not in data:
        raise AssertionError("launcher: missing CRLF")
    if data.replace(b"\r\n", b"").find(b"\n") != -1:
        raise AssertionError("launcher: lone LF found")
    if not dry_run:
        with open(path, "wb") as fh:
            fh.write(data)
    return len(data)


# --------------------------- host manifest ---------------------------
def build_manifest(ids):
    origins = ["chrome-extension://%s/" % i for i in ids]
    return {
        "name": HOST_NAME,
        "description": DESCRIPTION,
        "path": LAUNCHER_BAT,
        "type": "stdio",
        "allowed_origins": origins or ["chrome-extension://<EXTENSION_ID>/"],
    }


def write_manifest(path, doc, dry_run=False):
    text = json.dumps(doc, ensure_ascii=True, indent=2) + "\n"
    if not dry_run:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return text


# --------------------------- main ---------------------------
def main():
    args = sys.argv[1:]
    dry_run = "--check" in args
    extra_ids = []
    for i, a in enumerate(args):
        if a == "--id" and i + 1 < len(args):
            extra_ids.extend(x for x in args[i + 1].split(",") if x.strip())

    emit("WinOCR-Html native host setup")
    emit("  host dir : %s" % HERE)
    emit("  extension: %s" % EXT_DIR)
    emit("")

    # --- 1) extension ids ---
    hits = detect_extension_ids()
    if hits:
        emit("[+] detected extension id(s):")
        for browser, profile, eid in hits:
            emit("      %-7s %-10s %s" % (browser, profile, eid))
    else:
        emit("[-] could not find the extension in Edge/Chrome profiles.")
        emit("    Load the extension once (edge://extensions -> Load unpacked),")
        emit("    then re-run this script - or pass --id <extension-id>.")

    ids = []
    for _, _, eid in hits:
        if eid not in ids:
            ids.append(eid)
    for eid in extra_ids:
        if not ID_RE.match(eid.strip()):
            emit("[-] ignoring --id %r (not a 32-char id in a..p)" % eid)
            continue
        if eid.strip() not in ids:
            ids.append(eid.strip())
            emit("[+] added id from command line: %s" % eid.strip())

    if not ids:
        emit("")
        emit("[!] no id available -> writing the placeholder manifest.")
        emit("    Native messaging will NOT work until you re-run this script")
        emit("    (or edit com.winocr.host.json) with the real id.")

    # --- 2) launcher ---
    py = find_python_console()
    try:
        size = write_launcher(LAUNCHER_BAT, py, dry_run=dry_run)
        emit("")
        emit("[+] launcher  : %s" % LAUNCHER_BAT)
        emit("      python   : %s" % py)
        emit("      %d bytes, ASCII+CRLF" % size)
    except (AssertionError, UnicodeEncodeError) as e:
        emit("[-] launcher FAILED: %s" % e)
        return 1

    # --- 3) manifest ---
    doc = build_manifest(ids)
    try:
        text = write_manifest(HOST_JSON, doc, dry_run=dry_run)
    except UnicodeEncodeError as e:
        emit("[-] manifest FAILED (non-ASCII path?): %s" % e)
        return 1
    emit("")
    emit("[+] manifest  : %s" % HOST_JSON)
    for line in text.splitlines():
        emit("      " + line)

    # --- 4) sanity check: path exists & json round-trips ---
    if not dry_run:
        try:
            with open(HOST_JSON, encoding="utf-8") as fh:
                parsed = json.load(fh)
        except Exception as e:
            emit("[-] written manifest is not valid JSON: %s" % e)
            return 1
        if not os.path.isfile(parsed.get("path", "")):
            emit("[-] manifest paths to a missing file: %s" % parsed.get("path"))
            return 1
        if not parsed.get("allowed_origins") or "<EXTENSION_ID>" in parsed["allowed_origins"][0]:
            emit("[!] allowed_origins still has no real id - host will not connect.")
        else:
            emit("")
            emit("[OK] manifest is valid JSON and the id(s) are filled in.")

    emit("")
    emit("Next: extension options -> tick 'connect native host' -> reload the")
    emit("extension.  Then the host is started by the browser automatically.")
    emit("")
    emit("Local OCR (optional, offline + ~1-2s per shot): run install_deps.bat")
    emit("Health check (run this first when something is off): python winocr_host.py --doctor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
