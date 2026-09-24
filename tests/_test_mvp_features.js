// MVP 功能验证测试（纯算法逻辑，不依赖浏览器环境）
// 运行：node tests/_test_mvp_features.js

let passed = 0, failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; console.log('  [+] ' + msg); }
  else { failed++; console.log('  [-] FAIL: ' + msg); }
}

// ---------------- 模拟 common.js 中的核心函数 ----------------
function sm2Calc(quality, easeFactor, interval, repetitions) {
  let newEF = easeFactor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
  if (newEF < 1.3) newEF = 1.3;
  let newInterval;
  if (quality < 3) {
    newInterval = 1;
    repetitions = 0;
  } else {
    repetitions += 1;
    if (repetitions === 1) newInterval = 1;
    else if (repetitions === 2) newInterval = 6;
    else newInterval = Math.round(interval * newEF);
  }
  return {
    easeFactor: newEF,
    interval: newInterval,
    repetitions: repetitions,
    nextReview: Date.now() + newInterval * 24 * 60 * 60 * 1000
  };
}

function decayMastery(mastery, daysSinceReview) {
  const decayRate = 0.05;
  const decayed = mastery - decayRate * daysSinceReview;
  return Math.max(0.1, decayed);
}

function applyTerms(text, termsMap) {
  if (!text || !Object.keys(termsMap).length) return { text, restoreMap: null };
  let result = text;
  const restoreMap = {};
  let idx = 0;
  const sorted = Object.keys(termsMap).sort((a, b) => b.length - a.length);
  for (const src of sorted) {
    const tgt = termsMap[src];
    if (!src || !tgt) continue;
    const placeholder = '⟦T' + (idx++) + '⟧';
    const re = new RegExp(src.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    if (re.test(result)) {
      restoreMap[placeholder] = tgt;
      result = result.replace(re, placeholder);
    }
  }
  return { text: result, restoreMap: Object.keys(restoreMap).length ? restoreMap : null };
}

function restoreTerms(text, restoreMap) {
  if (!restoreMap || !text) return text;
  let result = text;
  Object.entries(restoreMap).forEach(([placeholder, term]) => {
    result = result.split(placeholder).join(term);
  });
  return result;
}

// ---------------- 测试 SM-2 算法 ----------------
console.log('\n=== SM-2 算法测试 ===');
{
  // 首次复习，quality=4（记住了）
  const r1 = sm2Calc(4, 2.5, 1, 0);
  assert(r1.interval === 1, '首次复习 interval=1');
  assert(r1.repetitions === 1, '首次复习 repetitions=1');

  // 第二次复习，quality=4
  const r2 = sm2Calc(4, r1.easeFactor, r1.interval, r1.repetitions);
  assert(r2.interval === 6, '第二次复习 interval=6');
  assert(r2.repetitions === 2, '第二次复习 repetitions=2');

  // 第三次复习，quality=5（完美）
  const r3 = sm2Calc(5, r2.easeFactor, r2.interval, r2.repetitions);
  assert(r3.interval >= 6, '第三次复习 interval>=6');
  assert(r3.easeFactor >= 2.5, 'easeFactor 不降低');

  // 忘了（quality=1）
  const r4 = sm2Calc(1, r3.easeFactor, r3.interval, r3.repetitions);
  assert(r4.interval === 1, '忘了则 interval 重置为 1');
  assert(r4.repetitions === 0, '忘了则 repetitions 重置为 0');

  // easeFactor 最小值 1.3
  const r5 = sm2Calc(0, 1.3, 100, 5);
  assert(r5.easeFactor >= 1.3, 'easeFactor 最小值 1.3');
}

// ---------------- 测试掌握度衰减 ----------------
console.log('\n=== 掌握度衰减测试 ===');
{
  assert(decayMastery(0.8, 0) === 0.8, '当天不衰减');
  assert(Math.abs(decayMastery(0.8, 1) - 0.75) < 0.001, '1 天后衰减 0.05');
  assert(Math.abs(decayMastery(0.8, 10) - 0.3) < 0.001, '10 天后衰减到 0.3（浮点近似）');
  assert(decayMastery(0.2, 10) === 0.1, '最低衰减到 0.1');
}

// ---------------- 测试术语替换 ----------------
console.log('\n=== 术语替换测试 ===');
{
  const terms = {
    'myocardial infarction': '心肌梗死',
    'pneumonia': '肺炎'
  };

  // 基本替换
  const r1 = applyTerms('Patient has myocardial infarction', terms);
  assert(r1.text.includes('⟦T0⟧'), '术语被替换为占位符');
  assert(r1.restoreMap['⟦T0⟧'] === '心肌梗死', 'restoreMap 正确');

  // 还原
  const restored = restoreTerms(r1.text, r1.restoreMap);
  assert(restored === 'Patient has 心肌梗死', '术语还原正确');

  // 多个术语
  const r2 = applyTerms('myocardial infarction and pneumonia', terms);
  assert(Object.keys(r2.restoreMap).length === 2, '多个术语替换');

  // 大小写不敏感
  const r3 = applyTerms('Myocardial Infarction', terms);
  assert(r3.text.includes('⟦T0⟧'), '大小写不敏感匹配');

  // 无术语
  const r4 = applyTerms('hello world', terms);
  assert(r4.text === 'hello world' && !r4.restoreMap, '无术语时原文返回');

  // 空文本
  const r5 = applyTerms('', terms);
  assert(r5.text === '' && !r5.restoreMap, '空文本安全处理');
}

// ---------------- 测试智能路由 ----------------
console.log('\n=== 智能路由测试 ===');
{
  // 模拟路由逻辑
  const SMART_ROUTE_SHORT_LEN = 200;
  function shouldTryFreeFirst(engine, textLen) {
    return engine === 'sf' && textLen < SMART_ROUTE_SHORT_LEN;
  }
  assert(shouldTryFreeFirst('sf', 100), '短文本 SF 引擎走免费');
  assert(!shouldTryFreeFirst('sf', 300), '长文本 SF 引擎不走免费');
  assert(!shouldTryFreeFirst('mymemory', 100), 'MyMemory 引擎不重复走免费');
  assert(!shouldTryFreeFirst('ollama', 100), 'Ollama 引擎不走免费');
}

// ---------------- 测试生词本数据结构 ----------------
console.log('\n=== 生词本数据结构测试 ===');
{
  const vocabItem = {
    id: 'v123',
    word: 'pneumonia',
    translation: '肺炎',
    source: 'test',
    context: 'Patient has pneumonia',
    mastery: 0.3,
    easeFactor: 2.5,
    interval: 1,
    repetitions: 0,
    reviewCount: 0,
    nextReview: Date.now(),
    createdAt: Date.now(),
    lastSeen: Date.now()
  };
  assert(vocabItem.word === 'pneumonia', '生词项字段完整');
  assert(vocabItem.mastery >= 0.1 && vocabItem.mastery <= 1, '掌握度范围正确');
  assert(vocabItem.easeFactor >= 1.3, 'easeFactor 最小值正确');
}

// ---------------- 测试对话导出 ----------------
console.log('\n=== 对话导出测试 ===');
{
  const chat = {
    title: '测试对话',
    engine: 'sf',
    model: 'Qwen/Qwen3-8B',
    messages: [
      { role: 'user', content: '你好' },
      { role: 'assistant', content: '你好！有什么可以帮你的？' }
    ]
  };

  // Markdown 导出
  const md = '# ' + chat.title + '\n\n' + chat.messages.map((m) => {
    const role = m.role === 'user' ? '**你**' : '**AI**';
    return role + '：\n\n' + m.content + '\n\n---\n';
  }).join('\n');
  assert(md.includes('测试对话'), 'Markdown 包含标题');
  assert(md.includes('**你**'), 'Markdown 包含用户角色');
  assert(md.includes('**AI**'), 'Markdown 包含 AI 角色');
  assert(md.includes('你好'), 'Markdown 包含消息内容');

  // JSON 导出
  const json = JSON.stringify({ title: chat.title, messages: chat.messages }, null, 2);
  const parsed = JSON.parse(json);
  assert(parsed.title === '测试对话', 'JSON 导出可解析');
  assert(parsed.messages.length === 2, 'JSON 包含所有消息');

  // 文本导出
  const text = '=== ' + chat.title + ' ===\n\n' +
    chat.messages.map((m) => {
      const role = m.role === 'user' ? '你' : 'AI';
      return '[' + role + '] ' + m.content;
    }).join('\n\n');
  assert(text.includes('=== 测试对话 ==='), '文本导出包含标题');
  assert(text.includes('[你] 你好'), '文本导出格式正确');
}

// ---------------- 总结 ----------------
console.log('\n=== 测试结果 ===');
console.log('通过: ' + passed + ' | 失败: ' + failed);
if (failed === 0) {
  console.log('ALL_TESTS_PASSED');
  process.exit(0);
} else {
  console.log('SOME_TESTS_FAILED');
  process.exit(1);
}
