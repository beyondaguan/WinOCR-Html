# -*- coding: utf-8 -*-
"""translate.py — 翻译模块（从 winocr_host.py 拆出）

公开函数：
  translate_text(text) -> str       # 总调度：sf / mymemory / none
  sf_translate(text) -> str         # SiliconFlow Qwen3-8B
  mm_translate(text) -> str         # MyMemory 免费接口

模块级注入（由主模块在导入时设置）：
  set_settings(settings_dict, settings_lock)
"""

import json
import urllib.request
import urllib.error
import urllib.parse
import html

# --------------------- 注入点（由主模块设置） ---------------------
_SETTINGS = None
_SETTINGS_LOCK = None


def set_settings(settings, lock):
    """由主模块在导入时注入 SETTINGS 字典和锁。"""
    global _SETTINGS, _SETTINGS_LOCK
    _SETTINGS = settings
    _SETTINGS_LOCK = lock


def _get(key, default=''):
    """线程安全地读取 SETTINGS。"""
    if _SETTINGS is None:
        return default
    if _SETTINGS_LOCK:
        with _SETTINGS_LOCK:
            return _SETTINGS.get(key, default)
    return _SETTINGS.get(key, default)


# --------------------- 常量 ---------------------
SF_TRANSLATE_TIMEOUT = 60
MM_CHUNK_SIZE = 450
MM_MAX_RETRIES = 3
MM_ENDPOINT = 'https://api.mymemory.translated.net/get'
MM_LANG_MAP = {
    'zh': 'zh-CN', 'en': 'en-GB', 'ja': 'ja-JP', 'ko': 'ko-KR', 'fr': 'fr-FR',
    'de': 'de-DE', 'es': 'es-ES', 'ru': 'ru-RU', 'it': 'it-IT', 'pt': 'pt-PT',
    'ar': 'ar-SA', 'th': 'th-TH', 'vi': 'vi-VN',
}


def mm_lang(code):
    c = str(code or '').lower()
    if not c or c == 'auto':
        return 'en-GB'
    return MM_LANG_MAP.get(c, c)


def mm_chunks(text, limit=MM_CHUNK_SIZE):
    """按 limit 字符切块，优先换行/句末，保留换行分隔符。"""
    import re
    out, buf = [], ""
    for seg in re.split(r'(\n+)', str(text or "")):
        if len(buf + seg) <= limit:
            buf += seg
            continue
        if buf:
            out.append(buf)
            buf = ""
        if len(seg) <= limit:
            buf = seg
            continue
        s = seg
        while len(s) > limit:
            cut = max(s.rfind(". ", 0, limit), s.rfind("。", 0, limit),
                      s.rfind("！", 0, limit), s.rfind(" ", 0, limit))
            if cut >= limit or cut < limit * 0.5:
                cut = limit - 1
            out.append(s[:cut + 1])
            s = s[cut + 1:]
        buf = s
    if buf:
        out.append(buf)
    return [x for x in out if x.strip()]


def re_test_warning(s):
    import re
    return bool(re.search(r"MYMEMORY WARNING|ALL AVAILABLE FREE TRANSLATIONS", str(s or ""), re.I))


def mm_once(text, src, tgt, email=""):
    """单次 MyMemory 请求。"""
    url = MM_ENDPOINT + "?q=" + urllib.parse.quote(text) + \
        "&langpair=" + urllib.parse.quote(src + "|" + tgt)
    if email:
        url += "&de=" + urllib.parse.quote(email)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WinOCR-Host"})
        with urllib.request.urlopen(req, timeout=MM_MAX_RETRIES * 10) as r:
            j = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError("MyMemory 网络不可达：%s" % e)
    det = str(j.get("responseDetails") or "")
    if re_test_warning(det) or j.get("quotaFinished"):
        raise RuntimeError("MyMemory 今日免费额度已用尽（匿名约 5000 字符/天）；"
                           "在 winocr_config.json 或扩展选项里填 mymemoryEmail 可提到约 50000。")
    if j.get("responseStatus") and int(j.get("responseStatus")) != 200:
        raise RuntimeError("MyMemory 返回 %s：%s" % (j.get("responseStatus"), det))
    out = html.unescape(str((j.get("responseData") or {}).get("translatedText") or "")).strip()
    if re_test_warning(out):
        raise RuntimeError("MyMemory 今日免费额度已用尽；填 mymemoryEmail 可提到约 50000 字符/天。")
    return out


def mm_translate(text):
    """MyMemory 翻译（免费、免 key、国内可直连）。"""
    src, tgt = mm_lang(_get("srcLang")), mm_lang(_get("tgtLang"))
    email = str(_get("mymemoryEmail") or "").strip()
    if src == tgt:
        return "翻译失败: 源语言与目标语言相同，无需翻译"
    parts = [mm_once(c, src, tgt, email) for c in mm_chunks(text, MM_CHUNK_SIZE)]
    out = "".join(parts).strip()
    if not out:
        return "翻译失败: MyMemory 返回空内容"
    return out


def sf_post(url_path, payload, key, timeout=SF_TRANSLATE_TIMEOUT):
    """SiliconFlow POST 请求。"""
    import urllib.error
    url = _get("sfUrl", "https://api.siliconflow.cn/v1").rstrip("/") + url_path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + str(key or ""),
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        raise RuntimeError("HTTP %s: %s" % (e.code, body))


def sf_translate(text):
    """SiliconFlow 翻译（Qwen3-8B，需 sfKey）。"""
    if not str(text or "").strip():
        return "翻译失败: 原文为空（OCR 未识别到文字），已跳过翻译"
    tgt_lang = _get("tgtLang")
    sys_p = ("You are a professional translator. Translate the user text into %s. "
             "Keep medical/technical terms accurate. Output ONLY the translation, no commentary."
             % tgt_lang)
    sf_model = _get("sfModel", "Qwen/Qwen3-8B")
    sf_key = _get("sfKey")
    payload = {
        "model": sf_model,
        "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": text}],
        "temperature": 0.3, "max_tokens": 4096,
        "enable_thinking": False,
    }
    j = sf_post("/chat/completions", payload, sf_key)
    if j.get("error") and "enable_thinking" in str(j["error"]):
        payload.pop("enable_thinking", None)
        j = sf_post("/chat/completions", payload, sf_key)
    if j.get("error"):
        return "翻译失败: " + str(j["error"])
    out = (j.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
    if not out:
        return "翻译失败: 模型返回空内容（可能被思考模式占用）"
    return out


def translate_text(text):
    """截图 OCR 文本的翻译总调度（引擎开关 = SETTINGS['translateEngine']）。"""
    te = str(_get("translateEngine") or "sf").lower()
    if te == "mymemory":
        return mm_translate(text)
    return sf_translate(text)
