// _test_bubble_race.js — 不开浏览器验证 content.js 的「常驻翻译栏不显示译文」修复
//
// 为什么需要它：这个 bug 只在真实事件序列里出现，纯读代码很容易漏。
//   气泡内的 mousedown 被 preventDefault（为了保住选区）→ 点气泡按钮时页面选区仍在
//   → 该次 mouseup 冒泡到 document → onSelect() 又来一遍 → 220ms 后 showBubble()
//   把**正在翻译的气泡**整块 removeBubble() 掉 → await 回来的译文写进孤儿节点 → 永远看不见。
//
// 本测试用最小 DOM 桩重放这条链路，断言：
//   1) 划词后常驻栏自动翻译（此前必须手动点「译」，是设计缺陷的一半）
//   2) 点气泡按钮后，**同一个**气泡节点仍在文档里，译文没丢（修复前必然失败）
//   3) DOM 里不残留第二个气泡（没有孤儿累积）
//
// 用法： node tests/_test_bubble_race.js [被测的 content.js 路径]
//   省略路径时默认测 ../extension/js/content.js
// 输出全部 ASCII（Windows 936 管道下不会乱码）。

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const TARGET = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.resolve(__dirname, '..', 'extension', 'js', 'content.js');

// ---------------------------------------------------------------- DOM 桩
function matches(el, sel) {
  const parts = sel.match(/\.[\w-]+|\[[^\]]+\]|^[a-zA-Z]+/g) || [];
  return parts.every((p) => {
    if (p[0] === '.') return String(el.className).split(/\s+/).indexOf(p.slice(1)) >= 0;
    if (p[0] === '[') {
      const m = p.match(/\[([\w-]+)(?:="([^"]*)")?\]/);
      if (!m) return false;
      const v = el.attrs[m[1]];
      return m[2] === undefined ? v !== undefined : v === m[2];
    }
    return el.tagName === p.toUpperCase();
  });
}

class El {
  constructor(tag, doc) {
    this.tagName = String(tag).toUpperCase();
    this.ownerDoc = doc;
    this.childNodes = [];
    this.parentNode = null;
    this.style = {};
    this.className = '';
    this.attrs = {};
    this._text = '';
    this._listeners = {};
    this.isText = false;
  }
  get children() { return this.childNodes.filter((n) => !n.isText); }
  get textContent() {
    if (this.isText) return this._text;
    // 元素级：set 会清空 childNodes 只留 _text；innerHTML 会只留 childNodes。两者互斥，相加即可。
    return this._text + this.childNodes.map((n) => n.textContent).join('');
  }
  set textContent(v) { this.childNodes = []; this._text = String(v == null ? '' : v); }
  get isConnected() {
    let n = this;
    while (n) { if (n === this.ownerDoc.root) return true; n = n.parentNode; }
    return false;
  }
  appendChild(c) {
    if (c.parentNode) c.parentNode.removeChild(c);
    c.parentNode = this;
    this.childNodes.push(c);
    return c;
  }
  removeChild(c) {
    const i = this.childNodes.indexOf(c);
    if (i >= 0) this.childNodes.splice(i, 1);
    c.parentNode = null;
    return c;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  contains(n) { while (n) { if (n === this) return true; n = n.parentNode; } return false; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  addEventListener(t, fn) { (this._listeners[t] = this._listeners[t] || []).push(fn); }
  removeEventListener(t, fn) {
    const a = this._listeners[t] || [];
    const i = a.indexOf(fn);
    if (i >= 0) a.splice(i, 1);
  }
  // 真实浏览器的冒泡顺序：目标 → 各级祖先 → document
  dispatch(type, extra) {
    const e = Object.assign({
      type: type,
      target: this,
      preventDefault() {},
      stopPropagation() { this._stop = true; },
      _stop: false
    }, extra || {});
    let n = this;
    while (n) {
      (n._listeners[type] || []).slice().forEach((fn) => fn.call(n, e));
      if (e._stop) break;
      n = n.parentNode;
    }
    if (!e._stop) (this.ownerDoc._listeners[type] || []).slice().forEach((fn) => fn.call(this.ownerDoc, e));
    return e;
  }
  set innerHTML(html) { this.childNodes = []; this._text = ''; parseInto(String(html), this, this.ownerDoc); }
  get innerHTML() { return ''; }
  querySelector(sel) { const r = this._walk(sel, true); return r || null; }
  querySelectorAll(sel) { return this._walk(sel, false); }
  _walk(sel, first) {
    const out = [];
    const visit = (root) => {
      for (const c of root.childNodes) {
        if (c.isText) continue;
        if (matches(c, sel)) { out.push(c); if (first) return true; }
        if (visit(c)) return true;
      }
      return false;
    };
    visit(this);
    return first ? (out[0] || null) : out;
  }
}

function parseInto(html, parent, doc) {
  const re = /<(\/)?([a-zA-Z]+)((?:\s+[^>]*?)?)(\/)?>/g;
  const stack = [parent];
  let last = 0, m;
  const pushText = (txt) => {
    if (!txt.trim()) return;
    const t = new El('#text', doc);
    t.isText = true;
    t._text = txt;
    stack[stack.length - 1].appendChild(t);
  };
  while ((m = re.exec(html))) {
    pushText(html.slice(last, m.index));
    last = re.lastIndex;
    if (m[1]) { if (stack.length > 1) stack.pop(); continue; }
    const el = new El(m[2], doc);
    const ar = /([\w-]+)(?:="([^"]*)")?/g;
    let a;
    while ((a = ar.exec(m[3] || ''))) {
      if (a[1] === 'class') el.className = a[2] || '';
      else el.attrs[a[1]] = a[2] === undefined ? '' : a[2];
    }
    stack[stack.length - 1].appendChild(el);
    if (!m[4]) stack.push(el);
  }
  pushText(html.slice(last));
}

// ---------------------------------------------------------------- 测试环境
function buildEnv() {
  const doc = { _listeners: {}, _byId: {} };
  const html = new El('html', doc);
  doc.root = html;
  doc.documentElement = html;
  const body = new El('body', doc);
  html.appendChild(body);
  doc.body = body;
  doc.createElement = (t) => new El(t, doc);
  doc.getElementById = (id) => doc._byId[id] || null;
  doc.addEventListener = (t, fn) => (doc._listeners[t] = doc._listeners[t] || []).push(fn);
  doc.removeEventListener = (t, fn) => {
    const a = doc._listeners[t] || [];
    const i = a.indexOf(fn);
    if (i >= 0) a.splice(i, 1);
  };

  const range = {
    cloneRange() { return range; },
    extractContents() { const f = new El('#fragment', doc); return f; },
    getBoundingClientRect() { return { left: 100, top: 300, bottom: 360 }; }
  };
  const selection = {
    text: '',
    rangeCount: 0,
    toString() { return this.text; },
    getRangeAt() { return range; }
  };

  const win = {
    scrollY: 0, innerWidth: 1280, innerHeight: 800,
    _listeners: {},
    getSelection() { return selection; },
    addEventListener(t, fn) { (this._listeners[t] = this._listeners[t] || []).push(fn); },
    removeEventListener(t, fn) {
      const a = this._listeners[t] || [];
      const i = a.indexOf(fn);
      if (i >= 0) a.splice(i, 1);
    }
  };

  const stats = { translateCalls: 0, records: 0 };
  const WINOCR = {
    getSettings: async () => ({
      engine: 'sf', sfKey: 'sk-TEST-not-a-real-key', sfUrl: 'https://api.siliconflow.cn/v1',
      sfModel: 'Qwen/Qwen3-8B', srcLang: 'en', tgtLang: 'zh', displayMode: 'bar'
    }),
    translate: async () => { stats.translateCalls++; await delay(60); return 'TRANSLATED_OK'; },
    addRecord: async () => { stats.records++; return []; }
  };

  const chrome = {
    runtime: {
      id: 'test-extension-id',
      lastError: null,
      onMessage: { addListener() {} },
      sendMessage() {}
    },
    storage: { local: { get() {}, set() {} }, onChanged: { addListener() {} } }
  };

  const nav = { clipboard: { writeText() {} } };
  const loc = { href: 'https://example.com/article' };

  return { doc, body, win, selection, WINOCR, chrome, nav, loc, stats };
}

function delay(ms) { return new Promise((r) => setTimeout(r, ms)); }

// ---------------------------------------------------------------- 断言
const results = [];
function ok(cond, msg) {
  results.push(!!cond);
  console.log((cond ? '  [+] ' : '  [-] ') + msg);
}

async function main() {
  const code = fs.readFileSync(TARGET, 'utf8');
  const env = buildEnv();
  const sandbox = {
    window: env.win, document: env.doc, chrome: env.chrome, WINOCR: env.WINOCR,
    navigator: env.nav, location: env.loc, setTimeout: setTimeout, clearTimeout: clearTimeout,
    console: console
  };
  vm.runInNewContext(code, sandbox, { filename: TARGET });

  console.log('target: ' + TARGET);
  await delay(20);   // 让 loadMode() 的 getSettings() 落定

  // ---- 1) 划词（mouseup 落在页面上，不在气泡里） ----
  env.selection.text = 'Stretching 1,240 km across Jilin, G331 runs along the province border';
  env.body.dispatch('mouseup');
  await delay(320);                       // 越过 DEBOUNCE(220)

  const bubbles = () => env.body.querySelectorAll('.winocr-bubble');
  const first = bubbles()[0];
  ok(bubbles().length === 1, 'exactly 1 bubble after selection (got ' + bubbles().length + ')');
  ok(first && first.className.indexOf('winocr-mode-bar') >= 0, 'bubble is the resident bar (winocr-mode-bar)');
  ok(env.stats.translateCalls === 1, 'bar auto-translated on open (translateCalls=' + env.stats.translateCalls + ')');
  await delay(200);
  ok(first && first.querySelector('.winocr-out').textContent === 'TRANSLATED_OK',
    'translation rendered in the bar: "' + (first && first.querySelector('.winocr-out').textContent) + '"');

  // ---- 2) 点气泡里的按钮：mousedown + mouseup 都落在气泡内部 ----
  //     修复前：这次 mouseup 会让 onSelect 再跑一遍，220ms 后把气泡拆掉重建 → 译文丢失
  const btn = first.querySelector('[data-act="trans"]');
  btn.dispatch('mousedown');
  btn.dispatch('mouseup');
  await delay(420);                       // 越过 DEBOUNCE(220) 再等一截

  const after = bubbles();
  ok(after.length === 1, 'still exactly 1 bubble after clicking inside it (got ' + after.length + ')');
  ok(after[0] === first, 'same bubble node survived (not rebuilt / not orphaned)');
  ok(after[0] && after[0].isConnected, 'bubble still attached to the document');
  ok(first.querySelector('.winocr-out').textContent === 'TRANSLATED_OK',
    'translation survived the click: "' + first.querySelector('.winocr-out').textContent + '"');

  // ---- 3) 手动重译仍在原地生效 ----
  const before = env.stats.translateCalls;
  btn.onclick();
  await delay(200);
  ok(env.stats.translateCalls === before + 1, 'manual 译 triggers a re-translate');
  ok(bubbles().length === 1 && bubbles()[0] === first, 're-translate stays in the same bubble');

  // ---- 4) 同一段文本重复划词不重建（复用） ----
  env.body.dispatch('mouseup');
  await delay(320);
  ok(bubbles().length === 1 && bubbles()[0] === first, 're-selecting the same text reuses the bubble');

  const pass = results.every(Boolean);
  console.log(pass ? 'RESULT: PASS (' + results.length + '/' + results.length + ')'
                   : 'RESULT: FAIL (' + results.filter(Boolean).length + '/' + results.length + ')');
  process.exit(pass ? 0 : 1);
}

main().catch((e) => { console.error('harness error: ' + (e && e.stack || e)); process.exit(2); });
