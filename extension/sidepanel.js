// sidepanel.js — 面板中枢：翻译（输入 / 划词 / 右键 / 快捷键）+ OCR + 历史 + 导出
(async function () {
  const $ = (s) => document.querySelector(s);
  let s = await WINOCR.getSettings();
  $('#src').value = s.srcLang; $('#tgt').value = s.tgtLang;
  setBadge(s.engine);

  function setBadge(engine) {
    const b = $('#engineBadge');
    if (!b) return;
    const map = { browser: '浏览器内置', mymemory: 'MyMemory' };
    b.textContent = map[engine] || 'SiliconFlow';
  }
  function escapeHtml(t) { return (t || '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }
  function fileToDataUrl(f) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f); }); }

  // ---------------- 原生宿主 / 本地配置路径 ----------------
  // 桌面热键截图与本地 OCR 都靠原生宿主；而独立模式读的是
  // native_host\winocr_config.json —— 和这个面板里保存的设置**不是同一个文件**。
  // 「在扩展里连上了」不代表本地那份有 key，所以把绝对路径直接摆在面板上。
  function renderHost(st) {
    const el = $('#hostLine');
    if (!el) return;
    const h = (st && st.host) || null;
    if (st && st.connected && h) {
      el.className = 'ok';
      el.innerHTML = '原生宿主：已桥接 · 桌面热键 <b>' + escapeHtml(String(h.hotkey || '—').toUpperCase())
        + '</b> · 本地配置 <code>' + escapeHtml(h.configPath || 'native_host\\winocr_config.json')
        + '</code>（桌面截图读这份，与本面板设置是两份文件）';
    } else if (st && !st.enabled) {
      el.className = '';
      el.textContent = '原生宿主：未连接 —— 桌面热键截图 / 本地 OCR 需要它。'
        + '到「选项」勾选「连接原生宿主」并保存，再重新加载扩展。';
    } else {
      el.className = 'warn';
      el.textContent = '原生宿主：未连接 · ' + ((st && st.error) || '宿主未注册或未启动')
        + ' —— 到「选项」点「检测宿主连接」看原因。';
    }
  }
  function pullHost() {
    try {
      chrome.runtime.sendMessage({ type: 'native.status' }, (st) => {
        void chrome.runtime.lastError;
        renderHost(st);
      });
    } catch (e) {}
  }
  pullHost();
  // 宿主可能比面板晚就绪（浏览器按需拉起），补看两次
  setTimeout(pullHost, 1500);
  setTimeout(pullHost, 5000);

  // toast：CSS 控制淡入淡出（.show）
  let msgTimer = null;
  function msg(t, isErr) {
    const m = $('#msg');
    m.textContent = t;
    m.classList.toggle('err', !!isErr);
    m.classList.add('show');
    clearTimeout(msgTimer);
    msgTimer = setTimeout(() => m.classList.remove('show'), 2600);
  }

  function showResult(original, translation, err) {
    const el = $('#result');
    el.classList.remove('is-empty');
    if (err) { el.innerHTML = '<div class="err">' + escapeHtml(err) + '</div>'; return; }
    el.innerHTML =
      '<div><div class="lab">原文</div><div class="o">' + escapeHtml(original) + '</div></div>' +
      '<div><div class="t">' + escapeHtml(translation) + '</div></div>';
  }
  function setLoading(text) {
    const el = $('#result');
    el.classList.remove('is-empty');
    el.innerHTML = '<span class="ph">' + escapeHtml(text) + '</span>';
  }
  function currentTranslation() { const t = $('#result .t'); return t ? t.textContent : ''; }
  function currentOriginal() { const o = $('#result .o'); return o ? o.textContent : ''; }

  async function refresh() {
    const hist = await WINOCR.getHistory();
    const el = $('#hist'); el.innerHTML = '';
    if (!hist.length) { el.innerHTML = '<div class="empty">暂无记录</div>'; return; }
    hist.slice(-30).reverse().forEach((r) => {
      const d = document.createElement('div'); d.className = 'item';
      d.innerHTML =
        '<div class="meta"><span class="kind">' + (r.type === 'image' ? '图' : '文') + '</span>' +
        '<span>' + ((r.ts || '').slice(0, 16).replace('T', ' ')) + '</span></div>' +
        '<div class="o">' + escapeHtml((r.original || r.ocr || '').slice(0, 160)) + '</div>' +
        '<div class="t">' + escapeHtml((r.translation || '').slice(0, 160)) + '</div>';
      el.appendChild(d);
    });
  }
  await refresh();

  // 历史/设置变化时自动刷新（原生宿主回传的记录也会实时出现）
  try {
    chrome.storage.onChanged.addListener((ch, area) => { if (area === 'local') refresh(); });
  } catch (e) {}

  // ---------------- 文本翻译 ----------------
  async function translateText(text) {
    text = (text || '').trim();
    if (!text) { msg('请输入或选取要翻译的文本', true); return; }
    setLoading('翻译中…');
    s = await WINOCR.getSettings();
    setBadge(s.engine);
    try {
      const out = await WINOCR.translate(text, {
        engine: s.engine, sfKey: s.sfKey, sfUrl: s.sfUrl, sfModel: s.sfModel,
        srcLang: s.srcLang, tgtLang: s.tgtLang
      });
      showResult(text, out);
      await WINOCR.addRecord({ type: 'text', source: 'panel', original: text, translation: out });
      await refresh();
    } catch (e) {
      showResult('', '', '翻译失败：' + e.message);
    }
  }

  $('#doTranslate').onclick = () => translateText($('#input').value);
  $('#input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); translateText($('#input').value); }
  });

  // 取当前页面选中 → 填入输入框
  $('#fromSel').onclick = async () => {
    try {
      const tabs = await new Promise((r) => chrome.tabs.query({ active: true, currentWindow: true }, (t) => r(t || [])));
      const tab = tabs[0]; if (!tab) return;
      const res = await new Promise((resolve) => chrome.tabs.sendMessage(tab.id, { type: 'winocr.getSelection' }, (x) => { void chrome.runtime.lastError; resolve(x); }));
      const text = ((res && res.text) || '').trim();
      if (!text) { msg('当前页未选中文字', true); return; }
      $('#input').value = text;
      $('#input').focus();
    } catch (e) { msg('取选中失败：' + e.message, true); }
  };

  $('#saveRec').onclick = async () => {
    const o = currentOriginal() || ($('#input').value || '').trim();
    const t = currentTranslation();
    if (!o && !t) { msg('暂无可记录内容', true); return; }
    await WINOCR.addRecord({ type: 'text', source: 'panel', original: o, translation: t });
    await refresh(); msg('已记录');
  };
  $('#copyOut').onclick = () => {
    const t = currentTranslation();
    if (!t) { msg('暂无译文', true); return; }
    navigator.clipboard.writeText(t); msg('已复制译文');
  };

  // 接收后台（右键菜单 / 快捷键 Alt+Shift+Z）推来的内容
  try {
    chrome.runtime.onMessage.addListener((m) => {
      if (!m) return;
      if (m.type === 'panel-input') { $('#input').value = m.text || ''; }
      else if (m.type === 'panel-result') {
        showResult(m.original || '', m.translation || '', m.error || '');
        refresh();
      }
    });
  } catch (e) {}

  // ---------------- 截图 OCR ----------------
  // OCR 引擎可切：'local' 交给原生宿主的 PP-OCRv6（实测 1.2~2.2s、离线、零 key）；
  // 'sf' 走云端视觉模型（PaddleOCR-VL 实测 103~121s、DeepSeek-OCR 输出不稳）。
  const ocrViaHost = (dataUrl, timeoutMs) => new Promise((res, rej) => {
    try {
      chrome.runtime.sendMessage({ type: 'ocr.viaHost', dataUrl: dataUrl, timeoutMs: timeoutMs }, (x) => {
        void chrome.runtime.lastError;
        if (!x) return rej(new Error('扩展后台无响应'));
        if (x.error) return rej(new Error(x.error));
        res(x.text || '');
      });
    } catch (e) { rej(e); }
  });

  async function runOcr(dataUrl, st) {
    if ((st.ocrEngine || 'local') === 'local') {
      try {
        return await ocrViaHost(dataUrl, 90000);
      } catch (e) {
        // 本地不可用（宿主没连/没注册/缺依赖）→ 回落云端，别让用户两手空空
        msg('本地 OCR 不可用（' + e.message + '），已改用云端…', true);
      }
    }
    return await WINOCR.ocrSF(dataUrl, st);
  }

  async function doOcr(dataUrl) {
    setLoading('OCR 中…');
    try {
      s = await WINOCR.getSettings();
      setBadge(s.engine);
      const ocr = await runOcr(dataUrl, s);
      const tr = await WINOCR.translate(ocr, {
        engine: s.engine, sfKey: s.sfKey, sfUrl: s.sfUrl, sfModel: s.sfModel,
        srcLang: s.srcLang, tgtLang: s.tgtLang
      });
      showResult(ocr, tr);
      await WINOCR.addRecord({ type: 'image', source: 'clipboard', ocr: ocr, translation: tr });
      await refresh();
    } catch (e) { showResult('', '', 'OCR 失败：' + e.message); }
  }

  document.addEventListener('paste', async (e) => {
    const it = Array.from(e.clipboardData.items).find((i) => i.type.startsWith('image/'));
    if (it) doOcr(await fileToDataUrl(it.getAsFile()));
  });
  const drop = $('#drop');
  ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', async (e) => { const f = e.dataTransfer.files[0]; if (f && f.type.startsWith('image/')) doOcr(await fileToDataUrl(f)); });
  $('#pick').onclick = () => $('#file').click();
  $('#file').onchange = async (e) => { const f = e.target.files[0]; if (f) doOcr(await fileToDataUrl(f)); };

  // ---------------- 导出 ----------------
  document.querySelectorAll('[data-x]').forEach((btn) => {
    btn.onclick = async () => {
      const hist = await WINOCR.getHistory();
      if (!hist.length) { msg('暂无记录', true); return; }
      btn.disabled = true;
      try {
        const x = btn.dataset.x; let n;
        if (x === 'folder') n = await WINOCR.exportToFolder(hist);
        else if (x === 'zip') n = await WINOCR.exportToZip(hist);
        else if (x === 'obsidian') n = await WINOCR.exportToObsidian(hist, s);
        else if (x === 'lexiang') n = await WINOCR.exportToLexiang(hist, s);
        msg('已导出 ' + n + ' 项');
      } catch (e) { msg('导出失败：' + e.message, true); }
      btn.disabled = false;
    };
  });

  $('#clear').onclick = async () => { await WINOCR.clearHistory(); await refresh(); msg('已清空'); };
  $('#reload').onclick = async () => { await refresh(); msg('已刷新'); };
  $('#src').onchange = async () => { s.srcLang = $('#src').value; await WINOCR.setSettings(s); };
  $('#tgt').onchange = async () => { s.tgtLang = $('#tgt').value; await WINOCR.setSettings(s); };

  // 编排入场：给分节加 .in（错峰由 CSS :nth-child 控制）
  requestAnimationFrame(() => {
    document.querySelectorAll('.rv').forEach((el) => el.classList.add('in'));
  });
})();
