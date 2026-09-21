// js/common.js — 共享核心（被 content.js / sidepanel.js / options.js / background.js 复用）
// 设计：纯浏览器内闭环（选区气泡、翻译、OCR、日积累 MD、多出口导出）。
// 翻译默认走自带 SiliconFlow key（BYOK, 模型 Qwen/Qwen3-8B）；
// 浏览器内置 Translator API（零 key、离线）仅 Edge/Chrome 138+ 且能访问微软服务时可用，否则自动回落 SF。
(function (global) {
  'use strict';
  const W = (global.WINOCR = {});

  // ---------------- 存储 ----------------
  const K_HIST = 'winocr_history_v1';
  const K_SET = 'winocr_settings_v1';

  // ---------------- 免费模型清单（2026-09-20 实测） ----------------
  // 与原生宿主 winocr_host.py 里的 FREE_TEXT_MODELS / FREE_OCR_MODELS 保持一致。
  // 实测数据（同一张截图）：本地 PP-OCRv6 1.2–2.2s/置信度0.98；
  //   PaddleOCR-VL 103–121s（对但有前导幻觉）；DeepSeek-OCR 不稳定（会整段退化乱码）；
  //   Qwen3-8B 翻译 2.5s；R1-0528 翻译 9.5–12.3s（思考占 400+ 字）。
  W.FREE_TEXT_MODELS = [
    { id: 'Qwen/Qwen3-8B', note: '快（实测 2.5s）· 翻译推荐' },
    { id: 'deepseek-ai/DeepSeek-R1-0528-Qwen3-8B', note: '推理模型，慢 4 倍（9.5–12.3s）' }
  ];
  W.FREE_OCR_MODELS = [
    { id: 'PaddlePaddle/PaddleOCR-VL-1.5', note: '文字对但极慢（103–121s）' },
    { id: 'deepseek-ai/DeepSeek-OCR', note: '输出不稳定（会退化成乱码）' }
  ];

  W.DEFAULT_SETTINGS = {
    engine: 'sf',                 // 网页划词翻译：'sf' | 'mymemory'（免费免 key）| 'browser'（内置, 需 138+）
    // Alt+Q 截图 OCR 之后的翻译引擎（原生宿主使用；浏览器内置引擎在宿主里用不了，
    // 故这里没有 browser）：'sf' | 'mymemory' | 'none'（仅 OCR 不翻译）
    translateEngine: 'sf',
    sfKey: '',
    sfUrl: 'https://api.siliconflow.cn/v1',
    sfModel: 'Qwen/Qwen3-8B',
    // 注意：硅基流动上必须带 `PaddlePaddle/` 前缀，写成 `PaddleOCR-VL-1.5` 会报
    // 20012 "Model does not exist"（normalizeOcrModel 会把旧值自动纠正过来）。
    sfOcrModel: 'PaddlePaddle/PaddleOCR-VL-1.5',
    // OCR 引擎：'local' 本地 PP-OCRv6（离线·零 key·~1.5s，截图首选）
    //           'sf'   云端 SiliconFlow 视觉模型（慢，但能处理照片/手写/复杂版面）
    ocrEngine: 'local',
    localOcrTier: 'tiny',         // 'tiny'（6.6MB，已内置）| 'medium'（需另放 133MB 模型）
    srcLang: 'en',
    tgtLang: 'zh',
    displayMode: 'inline',        // 页面译文形态：'inline' 原地替换原文（默认）| 'bar' 常驻翻译栏 | 'bubble' 临时气泡
    nativeHost: false,            // 是否连接原生宿主 com.winocr.host（仅外部截图记录回传需要；默认关）
    hotkey: 'ctrl+shift+m',       // 原生宿主「截图」热键（扩展设置页可自由录入并同步给宿主）
    quitHotkey: 'ctrl+alt+q',     // 原生宿主「退出」热键（不能用裸 Esc，那会劫持全系统的 Esc）
    mymemoryEmail: '',            // MyMemory 可选邮箱：填了每日额度从 5000 提升到 50000 字符
    exportTargets: { folder: true, zip: false, obsidian: false, lexiang: false },
    obsidianUrl: 'http://127.0.0.1:27123',
    obsidianKey: '',
    lexiangEndpoint: '',
    lexiangToken: ''
  };

  // 扩展上下文是否仍有效。
  // 扩展被重新加载 / 更新 / 禁用后，已打开页面里注入的旧 content script 会失效，
  // 再调 chrome.* 会抛 "Extension context invalidated" → 这里统一兜住。
  function extAlive() {
    try { return !!(typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id); }
    catch (e) { return false; }
  }
  W.extAlive = extAlive;

  function store() {
    try {
      if (!extAlive()) return null;
      return (chrome.storage && chrome.storage.local) ? chrome.storage.local : null;
    } catch (e) { return null; }
  }

  // ---------------- 模型名归一化 ----------------
  // 硅基流动的模型 id 必须完全一致（含 `PaddlePaddle/`、`deepseek-ai/` 前缀），
  // 少写前缀会得到 20012 "Model does not exist"。这里把常见简写/历史错误值纠正回来，
  // 也让「曾经存过错误值」的旧设置自动痊愈。
  const OCR_ALIASES = {
    'paddleocr-vl-1.5': 'PaddlePaddle/PaddleOCR-VL-1.5',
    'paddleocr-vl': 'PaddlePaddle/PaddleOCR-VL-1.5',
    'paddleocr': 'PaddlePaddle/PaddleOCR-VL-1.5',
    'deepseek-ocr': 'deepseek-ai/DeepSeek-OCR'
  };
  function normalizeOcrModel(name) {
    const n = String(name == null ? '' : name).trim();
    if (!n) return W.DEFAULT_SETTINGS.sfOcrModel;
    return OCR_ALIASES[n.toLowerCase()] || n;
  }
  W.normalizeOcrModel = normalizeOcrModel;

  W.getSettings = function () {
    return new Promise((resolve) => {
      const s = store();
      if (!s) return resolve(Object.assign({}, W.DEFAULT_SETTINGS));
      try {
        s.get(K_SET, (o) => {
          void chrome.runtime.lastError;   // 读掉，避免 Unchecked runtime.lastError
          const merged = Object.assign({}, W.DEFAULT_SETTINGS, (o && o[K_SET]) || {});
          merged.sfOcrModel = normalizeOcrModel(merged.sfOcrModel);   // 自动纠正旧值
          // DeepLX 已下线（国内访问 DeepL 源站需代理且常被 429 限流）：旧值一律回落到 sf
          if (merged.engine === 'deeplx') merged.engine = 'sf';
          if (merged.translateEngine === 'deeplx') merged.translateEngine = 'sf';
          resolve(merged);
        });
      } catch (e) { resolve(Object.assign({}, W.DEFAULT_SETTINGS)); }
    });
  };
  W.setSettings = function (s) {
    return new Promise((resolve) => {
      const st = store();
      if (!st) return resolve(false);
      try {
        st.set({ [K_SET]: s }, () => { void chrome.runtime.lastError; resolve(true); });
      } catch (e) { resolve(false); }
    });
  };
  W.getHistory = function () {
    return new Promise((resolve) => {
      const s = store();
      if (!s) return resolve([]);
      try {
        s.get(K_HIST, (o) => { void chrome.runtime.lastError; resolve((o && o[K_HIST]) || []); });
      } catch (e) { resolve([]); }
    });
  };
  function hash(s) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(36); }

  // 记录去重：同一来源+同一原文（或同一 OCR 文本）只存一次
  W.addRecord = async function (rec) {
    const list = await W.getHistory();
    const id = rec.id || (rec.source + ':' + hash(rec.original || '') + ':' + hash(rec.ocr || ''));
    if (list.some((r) => r.id === id)) return list;
    const item = Object.assign(
      { id, ts: new Date().toISOString(), type: 'text', source: '', original: '', translation: '', terms: [], image: '' },
      rec, { id }
    );
    list.push(item);
    const st = store();
    if (st) { try { st.set({ [K_HIST]: list }, () => void chrome.runtime.lastError); } catch (e) {} }
    return list;
  };
  W.clearHistory = function () {
    return new Promise((resolve) => {
      const st = store();
      if (!st) return resolve(false);
      try { st.set({ [K_HIST]: [] }, () => { void chrome.runtime.lastError; resolve(true); }); }
      catch (e) { resolve(false); }
    });
  };

  // ---------------- 翻译 ----------------
  // 重要：浏览器内置 Translator API 只有 Edge/Chrome 138+ 且能访问微软服务时才可用，
  // 旧内核 / 国内网络下不可用 → 一律回落到 SiliconFlow（BYOK）。故默认引擎为 'sf'。
  const SF_DEFAULT_URL = 'https://api.siliconflow.cn/v1';

  // 是否可向后台 Service Worker 转发（SW 有 host_permissions，可绕开页面 CSP/CORS 限制）。
  // Service Worker 自身没有 window，故该值为 false，天然避免自我递归。
  const CAN_MSG = (typeof window !== 'undefined') && (typeof chrome !== 'undefined') &&
    !!(chrome.runtime && chrome.runtime.id && typeof chrome.runtime.sendMessage === 'function');

  function sfEndpoint(opts) {
    return (opts.sfUrl || SF_DEFAULT_URL).replace(/\/+$/, '') + '/chat/completions';
  }

  function friendlySfError(status, msg, code) {
    const m = String(msg || '');
    if (code === 20012 || /does not exist/i.test(m)) {
      return '模型名不存在（' + m + '）。硅基流动上模型 id 必须写全称：' +
        'OCR 用 PaddlePaddle/PaddleOCR-VL-1.5，翻译用 Qwen/Qwen3-8B（扩展「选项」里可改）';
    }
    if (status === 401 || status === 403 || /invalid_token|Token is invalid/i.test(m)) {
      return 'SiliconFlow Key 无效或未填写，请在扩展「选项」里填写正确的 Key';
    }
    if (status === 429) return 'SiliconFlow 限流（429），请稍后重试';
    if (status === 400) return '请求被拒（400）：' + (m || '参数错误');
    return m || ('HTTP ' + status);
  }

  // 兜底：把请求交给后台 Service Worker 发出（绕开页面 CSP / CORS 变动）
  function sfChatViaBackground(url, key, body) {
    return new Promise((resolve, reject) => {
      if (!CAN_MSG || !extAlive()) return reject(new Error('no-runtime'));
      try {
        chrome.runtime.sendMessage({ type: 'sf.chat', url: url, key: key, body: body }, (res) => {
          const le = chrome.runtime.lastError;   // 必读：否则报 Unchecked runtime.lastError
          if (le) return reject(new Error(le.message));
          if (!res) return reject(new Error('后台无响应'));
          if (res.error) return reject(new Error(res.error));
          resolve(res.content || '');
        });
      } catch (e) { reject(e); }
    });
  }

  // 统一调用 SF /chat/completions；返回 content 文本。
  // 首选 content script 内直接 fetch（SF 返回 ACAO:*，实测可跨域）；
  // 若因页面 CSP / 跨域异常而抛 TypeError，则回退走后台 SW 转发。
  async function sfChat(opts, body) {
    const key = (opts && opts.sfKey) || '';
    if (!key) throw new Error('未填写 SiliconFlow Key（请在扩展「选项」中填写）');
    const url = sfEndpoint(opts || {});

    const callViaFetch = async (b) => {
      const ctl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      const timer = ctl ? setTimeout(() => ctl.abort(), 60000) : null;
      let r, j = null;
      try {
        r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
          body: JSON.stringify(b),
          signal: ctl ? ctl.signal : undefined
        });
        try { j = await r.json(); } catch (e) { /* 非 JSON */ }
      } finally { if (timer) clearTimeout(timer); }
      const emsg = j && (j.message || (j.error && j.error.message));
      // SF 的业务错误有两种外壳：{error:{...}} 和 {code:20012,message:"..."}。
      // 后者 HTTP 状态可能仍是 200，若不看 code 就会被当成"成功但内容为空"。
      const code = (j && typeof j.code === 'number') ? j.code : null;
      const bizErr = !!(j && j.error) || (code !== null && code !== 0 && code !== 200);
      if (!r.ok || bizErr) {
        const err = new Error(friendlySfError(r.status, emsg, code));
        err.status = r.status; err.code = code;
        throw err;
      }
      const ch = j && j.choices && j.choices[0];
      return ((ch && ch.message && ch.message.content) || '').trim();
    };

    const call = async (b) => {
      try {
        return await callViaFetch(b);
      } catch (e) {
        if (e && e.name === 'AbortError') throw new Error('请求超时（60 秒），请检查网络');
        // 网络层异常（TypeError：CORS/CSP/断网）→ 尝试后台转发一次
        if (e instanceof TypeError && CAN_MSG) return await sfChatViaBackground(url, key, b);
        throw e;
      }
    };

    try {
      return await call(body);
    } catch (e) {
      // 个别模型不接受 enable_thinking → 去掉该参数重试一次（400）
      if (e && e.status === 400 && body && Object.prototype.hasOwnProperty.call(body, 'enable_thinking')) {
        const b2 = Object.assign({}, body); delete b2.enable_thinking;
        return await call(b2);
      }
      throw e;
    }
  }

  // ---------------- MyMemory（免费 · 免 key · 国内可直连） ----------------
  // 文档：https://mymemory.translated.net/doc/spec.php
  // 实测（2026-09-20）：国内可直连，返回 Access-Control-Allow-Origin: *（浏览器可跨域直连）。
  // 匿名约 5000 字符/天；带 de=<email> 可提到约 50000。质量中等（翻译记忆+MT），适合当"零 key 兜底"。
  const MM_ENDPOINT = 'https://api.mymemory.translated.net/get';
  const MM_LANG = {
    zh: 'zh-CN', en: 'en-GB', ja: 'ja-JP', ko: 'ko-KR', fr: 'fr-FR', de: 'de-DE',
    es: 'es-ES', ru: 'ru-RU', it: 'it-IT', pt: 'pt-PT', ar: 'ar-SA', th: 'th-TH', vi: 'vi-VN'
  };
  function mmLang(code) {
    const c = String(code || '').toLowerCase();
    if (!c || c === 'auto') return 'en-GB';   // MyMemory 不支持 auto 探测，按 en 处理
    return MM_LANG[c] || code;
  }

  // MyMemory 会返回 HTML 实体（&quot; / &#39; 等），统一解码
  function decodeEntities(s) {
    return String(s == null ? '' : s)
      .replace(/&#x([0-9a-fA-F]+);/g, (m, h) => { try { return String.fromCodePoint(parseInt(h, 16)); } catch (e) { return m; } })
      .replace(/&#(\d+);/g, (m, d) => { try { return String.fromCodePoint(parseInt(d, 10)); } catch (e) { return m; } })
      .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
  }

  // MyMemory 的 GET 对 q 有长度上限（约 500 字节）→ 按 450 字符切块，
  // 优先在换行处切，超长行再退到句末/空格。保留换行分隔符，拼接时不丢格式。
  function mmChunks(text, max) {
    const out = []; let buf = '';
    String(text == null ? '' : text).split(/(\n+)/).forEach((seg) => {
      if ((buf + seg).length <= max) { buf += seg; return; }
      if (buf) { out.push(buf); buf = ''; }
      if (seg.length <= max) { buf = seg; return; }
      let s = seg;
      while (s.length > max) {
        let cut = Math.max(s.lastIndexOf('. ', max), s.lastIndexOf('。', max), s.lastIndexOf('！', max), s.lastIndexOf(' ', max));
        // cut 必须落在 [max*0.5, max-1]，否则退化为硬切，避免出现 max+1 长度
        if (cut >= max || cut < max * 0.5) cut = max - 1;
        out.push(s.slice(0, cut + 1)); s = s.slice(cut + 1);
      }
      buf = s;
    });
    if (buf) out.push(buf);
    return out.filter((x) => x.trim());
  }

  async function mmOnce(text, src, tgt, email) {
    let url = MM_ENDPOINT + '?q=' + encodeURIComponent(text) +
      '&langpair=' + encodeURIComponent(src + '|' + tgt);
    if (email) url += '&de=' + encodeURIComponent(email);
    let r, j = null;
    try {
      r = await fetch(url, { method: 'GET' });
      try { j = await r.json(); } catch (e) { /* 非 JSON */ }
    } catch (e) {
      if (e instanceof TypeError && CAN_MSG && extAlive()) {
        return await mmViaBackground(url);   // 页面 CSP 兜底：走后台 SW
      }
      throw new Error('MyMemory 网络不可达：' + ((e && e.message) || e));
    }
    const det = String((j && j.responseDetails) || '');
    if (/MYMEMORY WARNING|ALL AVAILABLE FREE TRANSLATIONS/i.test(det) || (j && j.quotaFinished)) {
      throw new Error('MyMemory 今日免费额度已用尽（匿名约 5000 字符/天）；在扩展「选项」里填一个邮箱可提升到约 50000 字符/天。');
    }
    if (!r.ok || !j || (j.responseStatus && Number(j.responseStatus) !== 200)) {
      throw new Error('MyMemory 返回 ' + ((j && j.responseStatus) || r.status) + (det ? '：' + det : ''));
    }
    const out = decodeEntities(j.responseData && j.responseData.translatedText);
    if (/MYMEMORY WARNING|ALL AVAILABLE FREE TRANSLATIONS/i.test(out)) {
      throw new Error('MyMemory 今日免费额度已用尽；可在「选项」里填邮箱提升到约 50000 字符/天。');
    }
    return out.trim();
  }

  // 后台转发（兜底）：复用 sf.chat 通用通道；MyMemory 走 GET、无需 key。
  // 该函数仅用于 MyMemory，故结果统一做一次 HTML 实体解码。
  function mmViaBackground(url) {
    return new Promise((resolve, reject) => {
      try {
        chrome.runtime.sendMessage({ type: 'sf.chat', url: url, method: 'GET', key: '', body: null }, (res) => {
          const le = chrome.runtime.lastError;
          if (le) return reject(new Error(le.message));
          if (!res) return reject(new Error('后台无响应'));
          if (res.error) return reject(new Error(res.error));
          resolve(decodeEntities(res.content || ''));
        });
      } catch (e) { reject(e); }
    });
  }

  W.translateMyMemory = async function (text, opts) {
    opts = opts || {};
    const src = mmLang(opts.srcLang), tgt = mmLang(opts.tgtLang);
    if (src === tgt) throw new Error('源语言与目标语言相同，无需翻译');
    const parts = [];
    for (const c of mmChunks(text, 450)) parts.push(await mmOnce(c, src, tgt, opts.mymemoryEmail));
    const out = parts.join('');
    if (!out) throw new Error('MyMemory 返回空内容');
    return out;
  };

  W.translate = async function (text, opts) {
    opts = opts || {};
    // 兼容旧配置：已下线的 deeplx（国内需代理/会被 DeepL 限流）一律回落到 sf
    const engine = opts.engine === 'deeplx' ? 'sf' : (opts.engine || 'sf');
    if (engine === 'mymemory') return await W.translateMyMemory(text, opts);
    const tgt = opts.tgtLang || 'zh';
    const src = opts.srcLang || 'en';
    // 优先浏览器内置（仅 138+ 且 availability==='available' 时才用；否则回落 SF）
    if (engine === 'browser' && global.Translator && typeof global.Translator.availability === 'function') {
      try {
        const avail = await global.Translator.availability({ sourceLanguage: src, targetLanguage: tgt });
        if (avail === 'available') {
          const tr = await global.Translator.create({ sourceLanguage: src, targetLanguage: tgt });
          return await tr.translate(text);
        }
      } catch (e) { /* 回落 SF */ }
    }
    return await W.translateSF(text, opts);
  };

  W.translateSF = async function (text, opts) {
    opts = opts || {};
    const sys = 'You are a professional translator. Translate the user text into ' + (opts.tgtLang || 'zh') +
      '. Keep medical/technical terms accurate. Output ONLY the translation, no commentary, no quotes.';
    const body = {
      model: opts.sfModel || 'Qwen/Qwen3-8B',
      messages: [{ role: 'system', content: sys }, { role: 'user', content: text }],
      temperature: 0.3,
      max_tokens: 4096,
      // Qwen3 系列在硅基流动上 enable_thinking 默认为 true，思考 token 会耗尽 max_tokens 导致正文为空 → 必须关闭
      enable_thinking: false
    };
    const out = await sfChat(opts, body);
    if (!out) throw new Error('模型返回空内容（可能被思考模式占用），请重试或改小文本');
    return out;
  };

  // ---------------- OCR（图片 dataUrl -> 文本，走 SF 视觉模型） ----------------
  W.ocrSF = async function (dataUrl, opts) {
    opts = opts || {};
    const body = {
      model: normalizeOcrModel(opts.sfOcrModel),
      messages: [{
        role: 'user',
        content: [
          { type: 'text', text: 'OCR all text in this image. Output only the recognized text, preserving line breaks.' },
          { type: 'image_url', image_url: { url: dataUrl } }
        ]
      }],
      max_tokens: 4096
    };
    try {
      return await sfChat(opts, body);
    } catch (e) {
      // 20012 = 模型名不存在（常见于漏写 `PaddlePaddle/` 前缀）
      if (/does not exist|not exist|20012/i.test(String(e && e.message))) {
        throw new Error('OCR 模型名不存在（' + normalizeOcrModel(opts.sfOcrModel) +
          '）。硅基流动上要写全称：PaddlePaddle/PaddleOCR-VL-1.5 或 deepseek-ai/DeepSeek-OCR（扩展「选项」里可改）');
      }
      throw e;
    }
  };

  // ---------------- Markdown 生成 ----------------
  function pad(n) { return String(n).padStart(2, '0'); }
  function fmtDateTime(iso) { const d = new Date(iso); return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); }
  function fmtDate(iso) { const d = new Date(iso); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }

  W.groupByDate = function (records) {
    const m = {};
    records.forEach((r) => { const k = fmtDate(r.ts); (m[k] = m[k] || []).push(r); });
    return m;
  };

  W.recordsToMarkdown = function (records) {
    let out = '';
    records.slice().sort((a, b) => (a.ts < b.ts ? -1 : 1)).forEach((r) => {
      out += '## ' + fmtDateTime(r.ts);
      if (r.source) out += ' · [' + (r.source.length > 40 ? r.source.slice(0, 40) + '…' : r.source) + '](' + r.source + ')';
      out += '\n\n';
      if (r.type === 'image' && r.image) out += '![' + (r.ocr || '截图') + '](' + r.image + ')\n\n';
      out += '**原文**: ' + (r.original || r.ocr || '') + '\n\n';
      out += '**译文**: ' + (r.translation || '') + '\n\n';
      if (r.terms && r.terms.length) out += '**术语**: ' + r.terms.map((t) => '[[' + t + ']]').join(' / ') + '\n\n';
    });
    return out;
  };

  W.buildDailyMarkdown = function (records) {
    const groups = W.groupByDate(records);
    let md = '';
    Object.keys(groups).sort().forEach((date) => {
      md += '---\n\n# WinOCR ' + date + '\n\n' + W.recordsToMarkdown(groups[date]);
    });
    return md;
  };

  // ---------------- 零依赖 ZIP（store，无压缩） ----------------
  function crc32(buf) {
    let c = ~0;
    for (let i = 0; i < buf.length; i++) { c ^= buf[i]; for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xEDB88320 & -(c & 1)); }
    return ~c >>> 0;
  }
  W.makeZip = function (files) { // files: [{name, data:Uint8Array}]
    const chunks = []; let offset = 0; const central = [];
    const enc = (s) => new TextEncoder().encode(s);
    files.forEach((f) => {
      const name = enc(f.name); const data = f.data; const crc = crc32(data); const size = data.length;
      const local = new Uint8Array(30 + name.length); const dv = new DataView(local.buffer);
      dv.setUint32(0, 0x04034b50, true); dv.setUint16(4, 20, true); dv.setUint16(6, 0, true);
      dv.setUint16(8, 0, true); dv.setUint16(10, 0, true); dv.setUint32(14, crc, true);
      dv.setUint32(18, size, true); dv.setUint32(22, size, true); dv.setUint16(26, name.length, true);
      dv.setUint16(28, 0, true); local.set(name, 30);
      chunks.push(local); chunks.push(data);
      const cen = new Uint8Array(46 + name.length); const cd = new DataView(cen.buffer);
      cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 20, true); cd.setUint16(6, 20, true);
      cd.setUint16(8, 0, true); cd.setUint16(10, 0, true); cd.setUint16(12, 0, true);
      cd.setUint32(16, crc, true); cd.setUint32(20, size, true); cd.setUint32(24, size, true);
      cd.setUint16(28, name.length, true); cd.setUint16(30, 0, true); cd.setUint16(32, 0, true);
      cd.setUint16(34, 0, true); cd.setUint16(36, 0, true); cd.setUint32(38, offset, true); cd.setUint32(42, 0, true);
      cen.set(name, 46); central.push(cen); offset += local.length + data.length;
    });
    const cdStart = offset; let cdSize = 0; central.forEach((c) => { chunks.push(c); cdSize += c.length; });
    const end = new Uint8Array(22); const ed = new DataView(end.buffer);
    ed.setUint32(0, 0x06054b50, true); ed.setUint16(8, files.length, true); ed.setUint16(10, files.length, true);
    ed.setUint32(12, cdSize, true); ed.setUint32(16, cdStart, true); ed.setUint16(20, 0, true);
    chunks.push(end);
    return new Blob(chunks, { type: 'application/zip' });
  };

  // ---------------- 导出 ----------------
  // 文件夹（File System Access，真实写文件，免解压）
  W.exportToFolder = async function (records) {
    if (!global.showDirectoryPicker) throw new Error('当前浏览器不支持 File System Access，请改用 ZIP 或升级 Edge/Chrome');
    const dir = await global.showDirectoryPicker({ mode: 'readwrite' });
    const groups = W.groupByDate(records); let n = 0;
    for (const date of Object.keys(groups).sort()) {
      const f = await dir.getFileHandle('WinOCR-' + date + '.md', { create: true });
      const w = await f.createWritable();
      await w.write('# WinOCR ' + date + '\n\n' + W.recordsToMarkdown(groups[date]));
      await w.close(); n++;
    }
    return n;
  };

  // ZIP 归档（单文件可移植）
  W.exportToZip = async function (records) {
    const groups = W.groupByDate(records); const files = [];
    for (const date of Object.keys(groups).sort()) {
      files.push({ name: 'WinOCR-' + date + '.md', data: new TextEncoder().encode('# WinOCR ' + date + '\n\n' + W.recordsToMarkdown(groups[date])) });
    }
    const blob = W.makeZip(files);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'WinOCR-' + new Date().toISOString().slice(0, 10) + '.zip';
    document.body.appendChild(a); a.click(); a.remove();
    return files.length;
  };

  // Obsidian Local REST API
  W.exportToObsidian = async function (records, settings) {
    const base = (settings.obsidianUrl || 'http://127.0.0.1:27123').replace(/\/+$/, '');
    const key = settings.obsidianKey || '';
    const groups = W.groupByDate(records); let n = 0;
    for (const date of Object.keys(groups).sort()) {
      const md = '# WinOCR ' + date + '\n\n' + W.recordsToMarkdown(groups[date]);
      const r = await fetch(base + '/vault/WinOCR/' + ('WinOCR-' + date + '.md'), {
        method: 'PUT',
        headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'text/markdown' },
        body: md
      });
      if (r.ok) n++; else throw new Error('Obsidian 返回 ' + r.status);
    }
    return n;
  };

  // 乐享（占位：填入端点 + token 即可启用）
  W.exportToLexiang = async function (records, settings) {
    const ep = settings.lexiangEndpoint;
    if (!ep) throw new Error('请在设置中配置乐享 API 端点');
    const body = {
      title: 'WinOCR 导出 ' + new Date().toISOString().slice(0, 10),
      format: 'markdown',
      content: W.buildDailyMarkdown(records)
    };
    const r = await fetch(ep, {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + (settings.lexiangToken || ''), 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error('乐享返回 ' + r.status);
    return true;
  };

})(typeof window !== 'undefined' ? window : globalThis);
