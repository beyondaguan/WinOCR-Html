#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地 OCR：RapidOCR + PP-OCRv6 ONNX（完全离线、零 API key）。

为什么要有它
------------
实测（2026-09-20，同一张医学截图）：
    本地 PP-OCRv6 tiny   1.2 ~ 2.2 s   置信度 0.986   文字完全正确
    PaddlePaddle/PaddleOCR-VL-1.5   103 ~ 121 s       正确但有前导幻觉字符
    deepseek-ai/DeepSeek-OCR        0.9 s(热) / 30 s(冷)   时好时坏，会整段退化成乱码
截图是「屏幕上的清晰文字」，正是传统检测+识别模型的主场；云端 VL 模型是为
照片/手写/复杂版面准备的，用在这里既慢又更容易幻觉。所以本地优先，云端只做回退。

依赖
----
可选依赖，缺了只是本模块不可用，宿主照常跑（会明确告诉你缺什么）：
    pip install rapidocr onnxruntime numpy Pillow
模型放在 models/ocr/v6_tiny/ （PP-OCRv6 det/rec onnx + cls onnx，共约 6.6 MB）。
"""

from __future__ import annotations

import os
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_ROOT = os.path.join(HERE, "models", "ocr")

TIERS = ("tiny", "medium")
DEFAULT_TIER = "tiny"

# 低于此体积的 .onnx 视为占位 / 下载残缺（rapidocr 会报难懂的 protobuf 错）
_MIN_MODEL_SIZE = 100 * 1024

# 低置信「鬼字」拦截阈值（tiny 档正常行一般 ≥0.90，鬼字常 ≤0.60）
_OUTLIER_SCORE = 0.60

_lock = threading.Lock()
_engine = None
_engine_sig = None          # 当前引擎对应的 (tier, det, rec, cls)
_last_error = ""


# ----------------------------- 模型查找 -----------------------------
def model_dir(tier: str = DEFAULT_TIER) -> str:
    return os.path.join(MODELS_ROOT, "v6_" + tier)


def _valid(path) -> bool:
    try:
        return bool(path) and os.path.isfile(path) and os.path.getsize(path) >= _MIN_MODEL_SIZE
    except OSError:
        return False


def find_models(tier: str = DEFAULT_TIER):
    """返回 (det, rec, cls)。兼容两种社区命名（RapidOCR 官方命名 / PaddleOCR 旧命名）。"""
    d = model_dir(tier)
    cand = {
        "det": [f"PP-OCRv6_det_{tier}.onnx", f"PP-OCRv6_{tier}_det_infer.onnx"],
        "rec": [f"PP-OCRv6_rec_{tier}.onnx", f"PP-OCRv6_{tier}_rec_infer.onnx"],
        "cls": ["ch_ppocr_mobile_v2.0_cls_mobile.onnx", f"PP-OCRv6_{tier}_cls_infer.onnx"],
    }
    out = {}
    for part in ("det", "rec", "cls"):
        hit = None
        for name in cand[part]:
            p = os.path.join(d, name)
            if _valid(p):
                hit = p
                break
        out[part] = hit
    if not (out["det"] and out["rec"]):
        return None, None, None
    return out["det"], out["rec"], out["cls"]


def available():
    """(bool, reason)：本模块是否能跑（依赖齐 + 模型在）。"""
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception as e:
        return False, "缺少依赖 %s（pip install numpy Pillow）" % type(e).__name__
    try:
        import rapidocr  # noqa: F401
    except Exception:
        return False, "缺少依赖 rapidocr（pip install rapidocr onnxruntime）"
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return False, "缺少依赖 onnxruntime（pip install onnxruntime）"
    det, rec, _ = find_models(DEFAULT_TIER)
    if not (det and rec):
        return False, "本地模型缺失：%s 下需要有 PP-OCRv6 的 det/rec onnx" % model_dir(DEFAULT_TIER)
    return True, "ready"


def status():
    """给 UI / 日志用的一览。"""
    ok, reason = available()
    tiers = {}
    for t in TIERS:
        det, rec, _ = find_models(t)
        tiers[t] = bool(det and rec)
    return {"available": ok, "reason": reason, "tiers": tiers,
            "dir": MODELS_ROOT, "lastError": _last_error,
            "engineReady": _engine is not None}


# ----------------------------- 引擎 -----------------------------
def _build_params(tier: str):
    """rapidocr 3.x 必须传枚举，传字符串会被拒（winOCR3.4 踩过的坑）。"""
    from rapidocr import EngineType, ModelType, OCRVersion

    try:
        mt = ModelType(tier)
    except ValueError:
        mt = ModelType.TINY
    params = {
        "Global.log_level": "error",           # 屏蔽加载期 info 刷屏
        "Det.engine_type": EngineType.ONNXRUNTIME,
        "Det.ocr_version": OCRVersion.PPOCRV6,
        "Det.model_type": mt,
        "Rec.engine_type": EngineType.ONNXRUNTIME,
        "Rec.ocr_version": OCRVersion.PPOCRV6,
        "Rec.model_type": mt,
    }
    det, rec, cls = find_models(tier)
    if det and rec:                            # 本地模型优先，彻底零联网
        params["Det.model_path"] = det
        params["Rec.model_path"] = rec
        if cls:
            params["Cls.model_path"] = cls
    return params


def _get_engine(tier: str = DEFAULT_TIER):
    """按 tier 建/复用引擎；档位或模型路径变化时重建。"""
    global _engine, _engine_sig, _last_error
    det, rec, cls = find_models(tier)
    if not (det and rec):
        raise RuntimeError("本地 OCR 模型缺失：%s" % model_dir(tier))
    sig = (tier, det, rec, cls)
    if _engine is not None and _engine_sig == sig:
        return _engine
    with _lock:
        if _engine is not None and _engine_sig == sig:
            return _engine
        try:
            from rapidocr import RapidOCR
        except Exception as e:
            _last_error = "import rapidocr 失败: %s" % e
            raise RuntimeError("未安装 rapidocr，请执行：pip install rapidocr onnxruntime") from e
        try:
            _engine = RapidOCR(params=_build_params(tier))
            _engine_sig = sig
            _last_error = ""
        except Exception as e:
            _last_error = "引擎加载失败: %s" % e
            raise RuntimeError("RapidOCR 引擎加载失败: %s" % e) from e
    return _engine


def warmup(tier: str = DEFAULT_TIER) -> bool:
    try:
        _get_engine(tier)
        return True
    except Exception:
        return False


# ----------------------------- 文本还原 -----------------------------
def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3000 <= o <= 0x303F) or (0x4E00 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF)


def _join(parts) -> str:
    """同一行内的多个框拼接：中日韩之间不加空格，拉丁词之间加一个空格。"""
    out = ""
    for p in parts:
        if not p:
            continue
        if not out:
            out = p
        elif _is_cjk(out[-1]) or _is_cjk(p[0]):
            out += p
        else:
            out += " " + p
    return out


def _drop_outliers(items):
    """过滤明显低于正常水平的「鬼字」（tiny 档中文新闻/截图实测有效）。"""
    if not items:
        return items, 0
    scores = sorted(float(s) for _, _, s in items if s)
    if len(scores) < 3:
        return items, 0
    q3 = scores[int(len(scores) * 0.75)]
    thr = min(_OUTLIER_SCORE, q3 - 0.30)
    if thr <= 0:
        return items, 0
    kept = [it for it in items if float(it[2]) >= thr]
    return kept, len(items) - len(kept)


def _group_lines(items):
    """按 y 中心聚类分行，行内按 x 排序 —— 还原真实阅读顺序。

    RapidOCR 返回的是「文本框」，一行可能被切成多个框（英文词组、中英混排）；
    直接按返回顺序拼接会把行读乱，所以必须按几何重排。
    """
    rows = []
    parsed = []
    for box, text, score in items:
        if not text:
            continue
        xs = [p[0] for p in box] if box else [0.0]
        ys = sorted(p[1] for p in box) if box else [0.0]
        parsed.append({
            "text": text,
            "cx": sum(xs) / len(xs),
            "cy": ys[len(ys) // 2],          # 中位数，抗离群
            "top": min(ys), "bottom": max(ys),
            "h": max(ys) - min(ys),
        })
    if not parsed:
        return []
    heights = sorted(p["h"] for p in parsed if p["h"] > 0)
    med_h = heights[len(heights) // 2] if heights else 12.0
    thr = max(4.0, med_h * 0.6)
    for it in sorted(parsed, key=lambda x: (x["top"], x["cx"])):
        if rows and abs(it["cy"] - rows[-1]["cy"]) <= thr:
            rows[-1]["items"].append(it)
            ys = [x["cy"] for x in rows[-1]["items"]]
            rows[-1]["cy"] = sum(ys) / len(ys)
        else:
            rows.append({"cy": it["cy"], "items": [it]})
    lines = []
    for r in rows:
        r["items"].sort(key=lambda x: x["cx"])
        lines.append(_join([x["text"] for x in r["items"]]))
    return lines


# ----------------------------- 对外接口 -----------------------------
def _effective_tier(tier: str) -> str:
    """请求档位缺模型时回退 tiny（与 WinOCR3.4 行为一致：宁可降档也不崩/不联网）。"""
    t = str(tier or "").lower()
    if t not in TIERS:
        return DEFAULT_TIER
    det, rec, _ = find_models(t)
    if det and rec:
        return t
    return DEFAULT_TIER if t != DEFAULT_TIER else t


def recognize_image(pil_image, tier: str = DEFAULT_TIER):
    """PIL Image -> (text, confidence)。

    rapidocr 2.x/3.x 的引擎返回 **RapidOCROutput dataclass**（含 .txts/.boxes/.scores），
    它是一个**不可迭代**的对象；旧 1.x 返回 (boxes, txts, scores) 元组。
    两种形态都要兼容，且**检测不到文字时 txts 为 None，必须安全返回空串**，
    绝不能用 `result, _ = output` 去解包那个 dataclass —— 那会抛
    `cannot unpack non-iterable RapidOCROutput object`，宿主捕获后又回落云端（慢几十秒）。
    """
    import numpy as np

    img = pil_image
    if img.mode != "RGB":                    # RapidOCR 按 3 通道处理
        img = img.convert("RGB")
    # 小图放大：截图里的细小文字直接识别会掉字，放大 2× 命中率明显更好
    w, h = img.size
    if min(w, h) < 400:
        try:
            from PIL import Image as _I
            img = img.resize((int(w * 2), int(h * 2)), _I.LANCZOS)
        except Exception:
            pass
    engine = _get_engine(_effective_tier(tier))
    output = engine(np.array(img))
    # —— 统一把输出规整成 (txts, boxes, scores) 三个序列 ——
    if hasattr(output, "txts"):              # 新 dataclass：直接取属性
        txts = output.txts
        boxes = getattr(output, "boxes", None)
        scores = getattr(output, "scores", None)
    else:                                    # 旧元组：(boxes, txts, scores)
        try:
            boxes, txts, scores = output
        except Exception:
            boxes, txts, scores = None, None, None
    items = []
    n = len(txts or [])
    for i in range(n):
        box = boxes[i].tolist() if boxes is not None else None
        sc = float(scores[i]) if scores is not None else 0.0
        items.append((box, txts[i], sc))
    if not items:                            # 没识别到任何文字：安全返回空，不崩、也不谎报
        return "", 0.0
    items, _dropped = _drop_outliers(items)
    conf = (sum(float(s) for _, _, s in items) / len(items)) if items else 0.0
    return "\n".join(_group_lines(items)), conf


def recognize_png(png_bytes, tier: str = DEFAULT_TIER):
    """PNG 字节 -> (text, confidence)。宿主截图路径用这个。"""
    import io as _io
    from PIL import Image
    with Image.open(_io.BytesIO(png_bytes)) as im:
        im.load()
        return recognize_image(im, tier)


def recognize_file(path, tier: str = DEFAULT_TIER):
    from PIL import Image
    with Image.open(path) as im:
        im.load()
        return recognize_image(im, tier)
