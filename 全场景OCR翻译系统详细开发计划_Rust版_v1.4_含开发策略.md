# 全场景OCR翻译系统 — 详细开发计划（Rust架构版 v1.3）

## 一、项目概述

### 1.1 项目背景

本项目旨在构建一个**全场景、全链路**的翻译系统，整合四种开源方案的核心能力：

- **WinLens**：系统级屏幕OCR翻译（任意界面）
- **沉浸式翻译**：浏览器内全页双语翻译
- **Microsoft Edge Translator API**：浏览器内置本地离线翻译
- **MouseTooltipTranslator**：浏览器悬停翻译+图片OCR

通过整合，用户只需**一个浏览器插件 + 一个轻量本地壳程序**，即可实现浏览器内/外全场景覆盖的翻译能力。

### 1.2 核心目标

| 目标 | 指标 |
|------|------|
| 全场景覆盖 | 浏览器内 + 浏览器外 + 视频 + 语音 |
| 空间最小 | 插件 < 1MB + 本地壳 ~100-200KB，总计 < 2MB |
| 传输最快 | Native Messaging IPC直连，延迟 < 1ms |
| 多引擎调度 | 本地离线 + 云端高质量，智能路由 |
| 隐私安全 | OCR本地运行，翻译可完全离线 |
| 毫秒级响应 | Rust零GC停顿 + PP-OCRv6本地推理，截图→译文 < 100ms |

### 1.3 技术架构总览

```
+------------------------------------------------------------------+
|                    用户交互层（统一入口）                           |
|  浏览器内：悬停翻译 / 划词翻译 / 一键全页翻译                       |
|  浏览器外：全局快捷键截图翻译 / 任意窗口覆盖翻译                    |
|  视频：实时双语字幕                                                |
|  语音：TTS朗读 / 语音输入翻译                                      |
+----------------------------------+-------------------------------+
                                   |
+----------------------------------+-------------------------------+
|                    内容采集层（多源输入）                           |
|  1) DOM文本捕获 ---- 沉浸式翻译的DOM遍历 + MutationObserver        |
|  2) 鼠标悬停捕获 -- MouseTooltipTranslator的getSelection()         |
|  3) 屏幕截图OCR --- Rust壳 + PP-OCRv6 ONNX Runtime                |
|  4) 图像OCR ------- Tesseract.js（浏览器端）                       |
|  5) 视频字幕提取 -- YouTube/Netflix Player API                     |
|  6) PDF解析 ------- PDF.js 文本层 + 扫描件OCR                      |
|  7) 语音输入 ------ Web Speech API                                 |
+----------------------------------+-------------------------------+
                                   |
+----------------------------------+-------------------------------+
|                    翻译处理层（多引擎调度）                         |
|  本地离线：Edge Translator API（设备端ONNX推理，零延迟）            |
|  本地大模型：Ollama / LM Studio / text-generation-webui            |
|    （Qwen / Llama / ChatGLM 等，HTTP REST API 调用）               |
|  云端高质量：SiliconFlow / OpenAI GPT / Claude / Gemini / DeepL    |
|  云端通用：Google Translate / Bing Translate                       |
|  云端免费：MyMemory（免Key，国内直连）                              |
|  智能路由：根据文本类型/长度/网络状况/成本自动选最优引擎             |
|  术语库：专业术语库 + 用户自定义术语                                 |
+----------------------------------+-------------------------------+
                                   |
+----------------------------------+-------------------------------+
|                    AI 对话界面层（新增 v1.3）                      |
|  多轮对话 / 上下文管理 / 引擎切换 / 文件上传 / 对话历史管理         |
|  与学习模块集成（对话生词自动入本） / 对话导出（MD/PDF/文本）        |
+----------------------------------+-------------------------------+
                                   |
+----------------------------------+-------------------------------+
|                    结果展示层（多模态输出）                         |
|  浏览器内：双语对照行内嵌入 / 悬停Tooltip弹窗 / 输入框实时翻译       |
|  浏览器外（Native Messaging）：Rust浮窗原位覆盖绘制 / 浮动翻译窗口   |
|  特殊场景：视频双语字幕叠加 / PDF保留排版翻译 / TTS语音朗读          |
+------------------------------------------------------------------+
```

---

## 二、模块划分

### 2.1 模块总览

| 模块编号 | 模块名称 | 所属层 | 职责 |
|---------|---------|--------|------|
| M1 | 用户交互管理器 | 用户交互层 | 统一快捷键、弹窗、设置界面 |
| M2 | DOM内容采集器 | 内容采集层 | 网页文本捕获、MutationObserver监听 |
| M3 | 悬停翻译器 | 内容采集层 | 鼠标悬停文本捕获与翻译 |
| M4 | 屏幕截图OCR引擎 | 内容采集层 | 浏览器内Canvas截图+Tesseract.js |
| M5 | Native Messaging通信桥 | 传输层 | 插件与本地壳的IPC管道通信 |
| M6 | 本地壳程序（Rust） | 系统层 | 全局截图、PP-OCRv6 OCR、Rust浮窗绘制 |
| M7 | 翻译引擎路由器 | 翻译处理层 | 多引擎调度、智能路由、缓存 |
| M8 | 结果渲染引擎 | 结果展示层 | DOM注入、CSS覆盖、Tooltip渲染 |
| M9 | 视频字幕模块 | 内容采集+展示 | YouTube/Netflix字幕提取与叠加 |
| M10 | PDF翻译模块 | 内容采集+展示 | PDF.js解析+排版保留翻译 |
| M11 | 术语库管理器 | 翻译处理层 | 术语加载、匹配、用户自定义 |
| M12 | 设置与配置中心 | 用户交互层 | 用户偏好、引擎密钥、快捷键配置 |
| M13 | 历史记录服务（学习模块） | 学习层 | 翻译记录、掌握度追踪、复习调度 |
| M14 | 生词本服务（学习模块） | 学习层 | 生词采集、间隔重复、掌握度管理 |
| M15 | 复习引擎（学习模块） | 学习层 | SM-2算法、复习队列、掌握度衰减 |
| M16 | 导出服务（学习模块） | 学习层 | 多格式导出、跨设备迁移 |
| M17 | 本地大模型引擎接口 | 翻译处理层 | 本地部署大模型（Ollama/LM Studio）作为翻译引擎，支持Qwen/Llama/ChatGLM等 |
| M18 | AI对话界面 | 用户交互层 | 类ChatGPT对话式UI，多轮对话、引擎切换、文件上传、对话历史管理、与学习模块集成 |

### 2.2 各模块详细设计

#### M1 — 用户交互管理器

- **职责**：统一管理所有用户交互入口
- **功能**：
  - 全局快捷键注册与分发（见第四章快捷键系统详述）
  - Popup页面（插件图标点击弹出的设置面板）
  - 选项页面（长期设置存储）
  - 通知推送（翻译完成提示、错误提示）
- **技术**：Chrome Extension API `chrome.commands`、`chrome.storage`

#### M2 — DOM内容采集器

- **职责**：从网页DOM中提取可翻译文本
- **功能**：
  - DOM树遍历，智能识别正文区域（过滤导航、广告、代码块）
  - MutationObserver监听SPA动态内容变化
  - 文本清洗（去HTML标签、合并碎片TextNode、段落识别）
  - 长文本分块（避免API超时）
- **技术**：Content Script、DOM API、DOMParser

#### M3 — 悬停翻译器

- **职责**：鼠标悬停时实时翻译选中文本
- **功能**：
  - 监听 `mousemove` / `mouseup` 事件
  - 使用 `window.getSelection()` 捕获文本
  - 防抖处理（避免频繁请求）
  - 显示Tooltip浮动层
- **技术**：Content Script、DOM事件监听、CSS定位

#### M4 — 屏幕截图OCR引擎

- **职责**：浏览器内图片/漫画OCR识别
- **功能**：
  - Canvas API捕获页面指定区域
  - 调用Tesseract.js进行OCR识别
  - 语言包懒加载（首次使用时从CDN下载）
  - 识别结果缓存（相同图片不重复OCR）
- **技术**：Tesseract.js、Web Worker、Canvas API

#### M5 — Native Messaging通信桥

- **职责**：浏览器插件与本地壳程序之间的IPC通信
- **功能**：
  - 插件端：`chrome.runtime.connectNative()` 建立持久连接
  - 插件端：`port.postMessage()` 发送翻译请求
  - 插件端：`port.onMessage` 接收翻译结果
  - 本地壳端（Rust）：stdin写入/读取（4字节长度前缀 + UTF-8 JSON）
- **消息协议**：
  - 请求格式：`{4字节小端序长度}[UTF-8 JSON]`
  - 响应格式：`{4字节小端序长度}[UTF-8 JSON]`
- **JSON schema（请求）**：
  ```json
  {
    "type": "translate",
    "text": "原文内容",
    "source_lang": "en",
    "target_lang": "zh",
    "task": "ocr_translate",
    "timestamp": 1726963200000
  }
  ```
- **JSON schema（响应）**：
  ```json
  {
    "type": "translate_result",
    "translation": "翻译结果",
    "original_text": "原文内容",
    "source_lang": "en",
    "target_lang": "zh",
    "engine": "siliconflow",
    "ok": true,
    "error": null
  }
  ```

#### M6 — 本地壳程序（Rust版）

- **职责**：浏览器外的屏幕截图、OCR、译文绘制（Rust实现，毫秒级响应）
- **功能**：
  - **全局快捷键监听**：Win32 `RegisterHotKey`（Rust `winapi` crate 绑定）
  - **区域画框截图**：DXGI Desktop Duplication 优先 + GDI BitBlt 兜底
  - **OCR引擎调度**：PP-OCRv6 ONNX Runtime（本地离线，零key）/ SiliconFlow云端（兜底）
  - **三档模型切换**：Tiny（6MB，~100ms）/ Small（30MB，~500ms）/ Medium（133MB，~1.4s）
  - **Native Messaging通信**：通过 stdin/stdout 与浏览器插件通信
  - **Rust浮窗绘制**：tkinter替代方案 — 使用 `tao` + `winit` 创建置顶透明窗口进行GDI+绘制
  - **窗口句柄枚举**：GetForegroundWindow + EnumWindows 识别前景窗口
  - **单实例保护**：命名互斥量防止多实例冲突
- **技术栈**：
  - 语言：Rust 2021 Edition
  - 构建：Cargo + cargo-clippy + cargo-test
  - OCR推理：`onnxruntime` crate（Microsoft官方Rust绑定）
  - 截图：`d3d12` + `dxgi`（DXGI Desktop Duplication）
  - 窗口/热键：`winapi` / `windows` crate
  - JSON序列化：`serde` + `serde_json`
  - 浮窗绘制：`winit` + `wgpu`（GPU加速）或 `gdi32`（CPU兜底）
  - 配置管理：`serde` 序列化 JSON 配置文件
- **体积目标**：< 200KB（静态链接ONNX Runtime动态库约5-10MB可选项）
- **启动时间**：< 50ms（对比Python版1-2秒）
- **内存占用**：< 30MB（对比Python版~200MB）

**PP-OCRv6 三档模型选型策略**：

| 档位 | 模型体积 | 推理速度 | 适用场景 | 默认推荐 |
|------|---------|---------|---------|---------|
| Tiny | ~6MB | ~100ms/图 | 划词翻译、快速预览、屏幕截图 | 默认（平衡速度/精度） |
| Small | ~30MB | ~500ms/图 | 日常截图翻译、文档OCR | 用户可选 |
| Medium | ~133MB | ~1.4s/图 | 病历/医学文档、复杂版面、手写体 | 高精度场景 |

**OCR引擎降级策略**：

```
用户选择OCR引擎
    |
    v
+-----------+     不可用      +---------------+
|  本地PP-OCRv6  | ---------> | SiliconFlow   |
|  (onnxruntime)|  自动降级   |  云端OCR      |
+-----------+                 +---------------+
    |                                |
    v                                v
 Tiny/Small/Medium              PaddleOCR-VL-1.5
 100ms/500ms/1.4s               103-121s
 置信度0.98                     有前导幻觉
```

#### M7 — 翻译引擎路由器

- **职责**：统一管理所有翻译引擎（含本地大模型），智能选择最优引擎
- **功能**：
  - 引擎注册与发现（插件启动时扫描可用引擎）
  - 可用性检测（网络状态、API密钥有效性、本地服务可达性）
  - **全引擎列表**：
    - 本地离线：Edge Translator API（设备端ONNX推理）
    - **本地大模型：Ollama / LM Studio（Qwen/Llama/ChatGLM等）**
    - 云端高质量：SiliconFlow / OpenAI GPT-4o / Claude / Gemini / DeepL
    - 云端通用：Google Translate / Bing Translate
    - 云端免费：MyMemory（免Key，国内直连）
  - **智能路由策略表**：

| 场景 | 首选引擎 | 备选引擎 | 路由理由 |
|------|---------|---------|---------|
| 日常划词翻译（短文本） | Edge内置 / MyMemory | SiliconFlow | 免费快速，无需key |
| 专业文档翻译 | OpenAI GPT-4o / SiliconFlow | Claude | 高质量专业翻译 |
| 医学/法律等专业领域 | SiliconFlow / DeepL | OpenAI GPT-4o | 专业术语准确 |
| 隐私敏感内容 | 本地Ollama / Edge内置 | — | 数据不出本机 |
| 长文本（>4000字符） | Claude / OpenAI GPT-4o | SiliconFlow | 长上下文处理能力强 |
| 中日韩翻译 | Google / 百度 / 有道 | SiliconFlow | 东亚语言优化 |
| 离线环境 | Edge内置 / 本地Ollama | 无备选，提示联网 | 无云端可用 |
| 用户指定引擎 | 用户选择 | 降级到默认 | 尊重用户偏好 |

  - 请求缓存（相同文本相同语言对不重复请求）
  - 失败自动降级（主引擎失败 → 备选引擎 → 提示用户）
  - 并发请求与结果优先返回（多引擎并行请求，最快响应优先）
  - **成本优化**：短文本优先用免费引擎，长文本/专业文本自动切换高质量引擎
- **技术**：Service Worker、Fetch API、IndexedDB（缓存）、reqwest（Rust壳端HTTP客户端）

#### M8 — 结果渲染引擎

- **职责**：将翻译结果以多种方式展示给用户
- **功能**：
  - **双语对照模式**：译文以不同样式嵌入原文下方
  - **仅译文模式**：原文替换为译文
  - **Tooltip模式**：悬停时弹出浮动翻译层
  - **CSS变量控制**：背景色、字体、透明度、圆角等可配置
  - **原位覆盖**：通过绝对定位将译文覆盖在原文上
  - **动画过渡**：淡入淡出效果
- **技术**：Content Script、DOM操作、CSS注入、Shadow DOM

#### M9 — 视频字幕模块

- **职责**：视频平台双语字幕支持
- **功能**：
  - YouTube Player API集成
  - Netflix字幕轨道提取
  - 字幕时间轴对齐
  - 双语字幕轨道叠加
  - 字幕样式自定义
- **技术**：YouTube Player API、Content Script

#### M10 — PDF翻译模块

- **职责**：PDF文档双语翻译（保留原始排版）
- **功能**：
  - PDF.js文本层解析
  - 扫描件OCR（Tesseract.js）
  - 原文/译文双栏并排显示
  - 公式/表格保留
  - 页面级翻译缓存
- **技术**：PDF.js、Tesseract.js、Content Script

#### M11 — 术语库管理器

- **职责**：专业术语管理与翻译一致性
- **功能**：
  - 内置术语库（法律/医学/技术/金融等）
  - 用户自定义术语（关键词→翻译映射）
  - 术语匹配（正则匹配、模糊匹配）
  - 术语优先级（自定义术语 > 内置术语 > 引擎默认）
  - 术语库版本更新
- **技术**：IndexedDB、RegExp

#### M12 — 设置与配置中心

- **职责**：用户偏好统一管理
- **功能**：
  - 翻译引擎选择（默认引擎、备选引擎）
  - 源语言/目标语言设置
  - **快捷键自定义系统**（见第四章详述）
  - 显示样式配置（字体、颜色、大小、透明度）
  - **OCR引擎选择**：本地PP-OCRv6（Tiny/Small/Medium）/ SiliconFlow云端
  - 术语库管理
  - 隐私设置（是否允许云端翻译）
  - 设置导入/导出
- **技术**：`chrome.storage.sync`、Options Page

#### M13 — 历史记录服务（学习模块）

- **职责**：管理用户翻译历史记录，作为学习资产的基础数据源
- **功能**：
  - 翻译行为自动入池（每次翻译自动记录，无需手动操作）
  - 掌握度追踪（基于 SM-2 间隔重复算法，0~1 浮点数表示掌握程度）
  - 复习调度（自动计算下次复习时间，支持延迟/提前复习）
  - 来源溯源（记录翻译时的页面 URL 和上下文段落，复习时一键跳回原文）
  - 领域标签（自动或手动打标签：医学/法律/日常/技术，支持按领域筛选复习）
  - 去重合并（相同原文+相同语言对自动去重，合并复习记录）
- **技术**：IndexedDB（浏览器端）、chrome.storage.local（扩展设置端）

#### M14 — 生词本服务（学习模块）

- **职责**：管理用户生词库，提供主动学习系统
- **功能**：
  - **自动采集**：翻译行为自动入池；用户可设置过滤规则；支持手动添加
  - **间隔重复调度**：基于 SM-2 算法自动安排复习时间
  - **复习模式**：英→中、中→英、填空、听写四种模式
  - **掌握度追踪与毕业**：掌握度达到0.95且连续3次正确→毕业归档；衰减到0.3以下→回退待学习
- **技术**：IndexedDB、Web Worker（批量计算复习队列）

#### M15 — 复习引擎（学习模块）

- **职责**：实现 SM-2 间隔重复算法，管理复习调度与掌握度计算
- **功能**：
  - SM-2 算法实现（计算下次复习时间、更新 ease factor）
  - 掌握度衰减机制（长期未复习自动衰减）
  - 复习队列管理（获取到期复习列表、优先级排序）
  - 复习结果提交（用户反馈"忘了"/"有点印象"/"记住了"→更新掌握度）
  - 学习统计（每日/每周复习趋势、领域分布、掌握度分布）
- **技术**：纯 TypeScript 实现（无外部依赖），可运行在 Service Worker 中

#### M16 — 导出服务（学习模块）

- **职责**：将学习数据（历史记录+生词本）导出为多种格式
- **功能**：
  - JSON / CSV / Anki .apkg / Markdown / TSV / SRT 六种格式导出
  - 增量同步（上次导出以来的增量变更）
  - 版本兼容（导出文件包含版本号）
- **技术**：纯 TypeScript 实现，浏览器端 Blob API 下载

#### M17 — 本地大模型引擎接口

- **职责**：将本地部署的大语言模型作为翻译引擎接入系统，提供高质量离线翻译能力
- **功能**：
  - **本地模型服务发现**：自动探测本地运行的 Ollama / LM Studio / text-generation-webui 服务
  - **模型列表获取**：列出本地可用模型（Qwen2.5-7B / Llama-3-8B / ChatGLM3-6B 等）
  - **模型切换**：用户选择使用哪个本地模型进行翻译
  - **翻译Prompt模板**：预置多种翻译prompt模板（直译/意译/专业领域/文学翻译），支持用户自定义
  - **流式响应**：支持 SSE (Server-Sent Events) 流式输出，实时显示翻译进度
  - **上下文窗口管理**：自动处理长文本的上下文窗口分割与拼接
  - **批量翻译**：支持批量文本提交，提高吞吐量
  - **健康检查**：检测本地服务是否可用、模型是否加载
  - **降级策略**：本地模型不可用时自动降级到云端引擎（SiliconFlow/OpenAI等）
- **通信协议**：HTTP REST API（Ollama兼容接口）
  - 模型列表：`GET http://localhost:11434/api/tags`
  - 生成翻译：`POST http://localhost:11434/api/generate`
  - 聊天翻译：`POST http://localhost:11434/api/chat`
- **Rust壳集成**：通过 `reqwest` crate 调用本地HTTP接口，`tokio` 异步运行时处理并发请求
- **技术栈**：
  - 浏览器端：TypeScript + Fetch API / XMLHttpRequest
  - Rust壳：reqwest + tokio + serde
  - 本地服务：Ollama (默认) / LM Studio / text-generation-webui (可选)
- **优势**：
  - 完全离线运行，隐私安全，数据不出本机
  - 无API费用，可无限使用
  - 可定制翻译风格（通过prompt工程）
  - 支持多种开源模型，灵活选择质量/速度平衡
- **限制**：
  - 依赖用户自行安装和运行本地大模型服务
  - 推理速度取决于本地硬件（GPU加速显著优于CPU）
  - 首次加载模型可能需要等待（冷启动5-30秒）

#### M18 — AI对话界面

- **职责**：提供一个类ChatGPT的对话式AI界面，让用户可以通过自然语言与翻译系统交互
- **功能**：
  - **多轮对话**：保留完整对话上下文，支持多轮追问和澄清
  - **引擎切换**：在对话中随时切换翻译引擎/大模型（云端SF/OpenAI/Claude/本地Ollama等）
  - **对话历史管理**：保存、搜索、加载、删除对话历史
  - **文件上传**：支持上传图片/PDF/文档，AI可分析并翻译文件内容
  - **代码/公式渲染**：对话中嵌入的代码块和数学公式正确渲染
  - **对话导出**：导出为 Markdown / PDF / 纯文本格式
  - **学习模块集成**：对话中用户标记的词汇/句子自动加入生词本
  - **消息操作**：复制、重新生成、点赞/踩反馈、删除单条消息
  - **多会话管理**：同时维护多个独立对话会话
  - **快捷指令**：预设快捷指令（"翻译这段话"、"用更地道的表达"、"解释这个语法"等）
- **UI规格**：
  - 聊天消息气泡式布局（用户消息右对齐，AI消息左对齐）
  - 深色/浅色主题自动切换 + 手动切换
  - 响应式设计，适配不同屏幕尺寸
  - 打字机效果（流式输出时的逐字显示）
  - 加载状态指示器（三点跳动动画）
- **技术实现**：
  - 浏览器端：TypeScript + Content Script 注入
  - 状态管理：IndexedDB 存储对话历史
  - 文件处理：FileReader API + Canvas (图片) / PDF.js (PDF)
  - 流式响应：EventSource / fetch + ReadableStream
- **位置**：浏览器扩展侧栏（Side Panel）或 Popup 面板内嵌iframe
- **技术栈**：
  - 前端：TypeScript + CSS Variables (Design Tokens)
  - 状态管理：IndexedDB (store) + 内存缓存
  - 文件解析：PDF.js / Tesseract.js (图片OCR)
  - 代码高亮：Highlight.js (轻量级)

---

## 三、数据流设计

### 3.1 浏览器内翻译数据流

```
用户操作（悬停/划词/全页翻译）
        |
        v
+----------------------+
|   M1 交互管理器      |  获取用户操作类型和目标语言
+----------+-----------+
           |
           v
+----------------------+
|   M2/M3 内容采集     |  DOM遍历或getSelection获取文本
+----------+-----------+
           | text + lang_pair
           v
+----------------------+
|   M7 引擎路由器      |  智能选择最优翻译引擎
+----------+-----------+
           |
    +------+------+
    |             |
    v             v
+--------+  +------------+
|本地引擎|  |  云端引擎   |
|Edge    |  | SiliconFlow/|
|Translator| | Google/    |
|API      |  | MyMemory    |
+---+----+  +----+-------+
    |             |
    +-----+------+
          | translation
          v
+----------------------+
|   M8 结果渲染        |  DOM注入/CSS覆盖/Tooltip显示
+----------------------+
```

### 3.2 浏览器外（任意界面）翻译数据流（Rust壳）

```
用户触发全局快捷键（可配置，默认Ctrl+Shift+M）
        |
        v
+----------------------+
|   M6 Rust壳程序      |  DXGI Desktop Duplication截图
+----------+-----------+
           | 屏幕像素数据
           v
+----------------------+
|   M6 Rust壳程序      |  PP-OCRv6 ONNX Runtime OCR识别
|   (Tiny/Small/Medium)|  (本地离线，零key，~100ms)
+----------+-----------+
           | 识别文本 + 坐标
           v
+----------------------+
|   M6 Rust壳程序      |  打包JSON -> stdin写入(NM协议)
+----------+-----------+
           | Native Messaging (IPC管道)
           v
+----------------------+
|   M5 通信桥(插件端)   |  connectNative接收消息
+----------+-----------+
           | text + lang_pair
           v
+----------------------+
|   M7 引擎路由器      |  智能选择最优翻译引擎
+----------+-----------+
           | translation
           v
+----------------------+
|   M5 通信桥(插件端)   |  port.postMessage -> stdout返回
+----------+-----------+
           | Native Messaging (IPC管道)
           v
+----------------------+
|   M6 Rust壳程序      |  stdout读取JSON
+----------+-----------+
           | 译文 + 坐标
           v
+----------------------+
|   M6 Rust壳程序      |  winit浮窗/GDI+原位覆盖绘制译文
+----------------------+
```

### 3.3 视频字幕翻译数据流

```
用户打开视频页面
        |
        v
+----------------------+
|   M9 视频字幕模块    |  Player API监听字幕事件
+----------+-----------+
           | 字幕文本 + 时间轴
           v
+----------------------+
|   M7 引擎路由器      |  批量翻译字幕
+----------+-----------+
           | 翻译字幕 + 时间轴
           v
+----------------------+
|   M9 视频字幕模块    |  创建双语字幕轨道
+----------+-----------+
           |
           v
+----------------------+
|  视频播放器          |  叠加显示双语字幕
+----------------------+
```

### 3.4 学习数据流（历史记录 + 生词本 + 复习）

```
用户翻译行为（悬停/划词/全页/截图）
        |
        v
+----------------------+
|   M7 引擎路由器      |  执行翻译
+----------+-----------+
           | translation result
           v
+----------------------+
|   M8 结果渲染        |  展示翻译结果
+----------+-----------+
           |
           v
+----------------------+
|   M13 历史记录服务   |  自动入池（含来源溯源+领域标签）
+----------+-----------+
           | HistoryRecord
           v
+----------------------+
|   M14 生词本服务     |  自动采集/手动添加 → 进入待学习池
+----------+-----------+
           | VocabularyWord
           v
+----------------------+
|   M15 复习引擎       |  SM-2 计算下次复习时间
+----------+-----------+
           | ReviewSchedule
           v
+----------------------+
|   浏览器通知/侧栏    |  提醒用户复习
|   复习面板（闪卡）   |  四种复习模式
+----------+-----------+
           |
           v
+----------------------+
|   M16 导出服务       |  JSON/CSV/Anki/Markdown/TSV/SRT
+----------------------+
```

**收集闭环**：

```
翻译行为 → 自动入生词本 → 间隔重复复习 → 掌握度更新 → 毕业归档
    ↑                                                    │
    └────────── 导出/备份 ← 学习报告 ←──────────────────┘
```

### 3.5 AI对话数据流（v1.3新增）

```
用户在AI对话界面输入消息
        |
        v
+----------------------+
|   M18 AI对话界面     |  消息输入/渲染/上下文管理
+----------+-----------+
           | 消息文本 + 上下文ID
           v
+----------------------+
|   M18 AI对话界面     |  判断消息类型（翻译请求/闲聊/文件分析）
+----------+-----------+
           |
    +------+------+
    | 翻译请求     | 文件上传
    v             v
+--------+  +------------+
| M7引擎 |  | 文件处理器  |
| 路由器 |  | (PDF.js/    |
|        |  | Tesseract)  |
+---+----+  +----+-------+
    |             |
    v             v
+--------+  +------------+
|云端/   |  | 提取文本/   |
|本地LLM |  | OCR识别     |
|翻译    |  | 结果        |
+---+----+  +----+-------+
    |             |
    +-----+------+
          | 翻译/分析结果
          v
+----------------------+
|   M18 AI对话界面     |  流式渲染AI回复（打字机效果）
+----------+-----------+
           |
           v
+----------------------+
|   M13历史记录        |  自动保存对话到历史记录
+----------+-----------+
           |
           v
+----------------------+
|   M14生词本          |  用户标记的词汇自动入生词本
+----------+-----------+
           |
           v
+----------------------+
|   M16导出服务        |  对话导出（MD/PDF/文本）
+----------------------+
```

**对话上下文管理流**：

```
新对话开始
    |
    v
+----------------------+
| 创建对话会话          |  生成sessionID，初始化空上下文
+----------+-----------+
           |
           v
<用户发送消息>
           |
           v
+----------------------+
| 追加消息到上下文      |  用户消息 + AI回复成对存储
+----------+-----------+
           |
           v
+----------------------+
| 检查上下文窗口        |  超出窗口限制时裁剪最早消息
+----------+-----------+
           |
           v
+----------------------+
| 发送请求到引擎        |  带完整上下文发送
+----------+-----------+
           |
           v
+----------------------+
| 接收并渲染AI回复      |  流式显示 + 保存到上下文
+----------------------+
```

---

## 四、快捷键自定义系统（详细设计）

### 4.1 设计原则

快捷键系统遵循**第一性原理**：用户应该能完全控制如何触发翻译行为，且系统应智能处理冲突。

**核心原则**：
1. **自由录入**：用户通过界面直接按下目标组合键即可录入，无需手动输入键码
2. **冲突检测与自动回退**：检测到快捷键被占用时，自动尝试备选方案并提示用户
3. **即时生效**：修改后无需重启浏览器或壳程序，热键即时重新注册
4. **持久化**：设置保存到 `chrome.storage.sync`（浏览器端）+ `winocr_config.json`（Rust壳端）
5. **多端同步**：浏览器端设置通过 Native Messaging 同步到 Rust 壳

### 4.2 快捷键定义表

| 快捷键ID | 功能描述 | 默认值 | 作用域 | 说明 |
|---------|---------|--------|--------|------|
| `screenshot_area` | 区域截图翻译 | `Ctrl+Shift+M` | Rust壳 | 触发全局画框截图→OCR→翻译→浮窗显示 |
| `screenshot_full` | 全屏截图翻译 | `Ctrl+Shift+F` | Rust壳 | 触发全屏截图翻译（无需画框） |
| `quit_host` | 退出Rust壳程序 | `Ctrl+Alt+Q` | Rust壳 | 优雅退出宿主进程 |
| `open_panel` | 打开插件面板 | `Alt+Shift+W` | 浏览器 | 打开扩展Popup/侧栏 |
| `translate_selection` | 翻译选中文字 | `Alt+Shift+Z` | 浏览器 | 翻译当前页面选中文字 |
| `toggle_overlay` | 切换原位覆盖 | `Ctrl+O` | 浏览器 | 切换译文原位覆盖显示 |
| `start_review` | 开始复习 | `Ctrl+Shift+R` | 浏览器 | 打开复习面板 |
| `quick_add_word` | 快速添加生词 | `Ctrl+Shift+A` | 浏览器 | 将当前选中词添加到生词本 |
| `custom_1` | 用户自定义1 | 未设置 | 浏览器/壳 | 用户自由绑定 |
| `custom_2` | 用户自定义2 | 未设置 | 浏览器/壳 | 用户自由绑定 |

### 4.3 快捷键录入流程

```
用户进入设置页 → 点击"录入快捷键"输入框
        |
        v
+----------------------+
|  浏览器端录制        |  监听keydown事件，捕获组合键
+----------+-----------+
           | 组合键信息(Ctrl+Shift+M)
           v
+----------------------+
|  冲突检测            |  检查是否被其他扩展/系统占用
+----------+-----------+
        |
    +---+---+
    | 有冲突 |  无冲突
    v        v
+------+ +------------------+
|自动   | | 保存到chrome.    |
|尝试   | | storage.sync     |
|备选键 | +--------+---------+
|       |          |
|提示用户|          v
|选择    |    通过NM同步到Rust壳
+------+          |
                  v
          +----------------------+
          | Rust壳重新注册热键     |
          | PostThreadMessageW    |
          | (即时生效，不需重启)   |
          +----------------------+
```

### 4.4 冲突自动回退策略

当用户设置的快捷键已被占用时，系统按以下优先级尝试备选键：

```
用户设置: Ctrl+Shift+M (被WinOCR 3.4蒙版翻译占用)
        |
        v
+----------------------+
|  备选1: Ctrl+Alt+M   |  可用 → 提示用户"已自动切换为Ctrl+Alt+M"
+----------+-----------+
        | 仍被占用
        v
+----------------------+
|  备选2: Ctrl+Shift+F |  可用 → 提示用户
+----------+-----------+
        | 仍被占用
        v
+----------------------+
|  备选3: Alt+Shift+M  |  可用 → 提示用户
+----------+-----------+
        | 仍被占用
        v
+----------------------+
|  备选4: Ctrl+Alt+Z   |  可用 → 提示用户
+----------+-----------+
        | 全被占用
        v
+----------------------+
|  报错：请手动设置     |  指向配置项 winocr_config.json
+----------------------+
```

### 4.5 Rust壳端热键管理

Rust壳程序使用 `winapi` crate 管理全局热键：

```rust
// 热键注册核心逻辑（伪代码）
use winapi::um::winuser::{RegisterHotKey, UnregisterHotKey, MOD_ALT, MOD_CONTROL, MOD_SHIFT};

struct HotKeyManager {
    hotkeys: HashMap<String, HotKey>,
    window_handle: HWND,
}

impl HotKeyManager {
    fn register(&mut self, id: &str, modifiers: u32, vk: u32) -> Result<(), HotKeyError> {
        unsafe {
            let success = RegisterHotKey(self.window_handle, id as i32, modifiers, vk);
            if success == 0 {
                Err(HotKeyError::RegistrationFailed)
            } else {
                Ok(())
            }
        }
    }

    fn unregister_all(&mut self) {
        for hotkey in self.hotkeys.values() {
            unsafe { UnregisterHotKey(self.window_handle, hotkey.id as i32); }
        }
    }

    fn reload_from_config(&mut self, config: &HotKeyConfig) {
        self.unregister_all();
        for (name, key_def) in config.hotkeys.iter() {
            self.register(name, key_def.modifiers, key_def.vk);
        }
    }
}
```

### 4.6 快捷键配置文件格式

```json
{
  "hotkeys": {
    "screenshot_area": {
      "key": "m",
      "modifiers": ["ctrl", "shift"],
      "description": "区域截图翻译"
    },
    "screenshot_full": {
      "key": "f",
      "modifiers": ["ctrl", "shift"],
      "description": "全屏截图翻译"
    },
    "quit_host": {
      "key": "q",
      "modifiers": ["ctrl", "alt"],
      "description": "退出宿主程序"
    },
    "custom_1": null,
    "custom_2": null
  },
  "hotkeyConflictStrategy": "autoFallback",
  "lastConflictResult": "screenshot_area: auto-fallback to Ctrl+Alt+M"
}
```

---

## 五、界面设计与UI规范

### 5.1 设计哲学

**核心原则：工具是从属表面，绝不违反阅读焦点。**

UI设计服务于翻译这个核心行为，不喧宾夺主。采用**工业实用**风格——信息密度高、层级清晰、操作路径最短。

### 5.2 设计令牌（Design Tokens）

#### 色彩体系

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--color-primary` | `#1677ff` | 主色调（按钮、链接、激活态） |
| `--color-primary-hover` | `#4096ff` | 悬停态 |
| `--color-primary-active` | `#0958d9` | 按下态 |
| `--color-success` | `#52c41a` | 成功状态 |
| `--color-warning` | `#faad14` | 警告状态 |
| `--color-error` | `#ff4d4f` | 错误状态 |
| `--color-text-primary` | `rgba(0,0,0,0.88)` | 主文本 |
| `--color-text-secondary` | `rgba(0,0,0,0.65)` | 次要文本 |
| `--color-text-disabled` | `rgba(0,0,0,0.25)` | 禁用态文本 |
| `--color-bg-container` | `#ffffff` | 容器背景 |
| `--color-bg-layout` | `#f5f5f5` | 布局背景 |
| `--color-border` | `#d9d9d9` | 边框色 |
| `--color-shadow` | `rgba(0,0,0,0.15)` | 阴影色 |

#### 暗色模式令牌

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--color-primary` | `#4096ff` | 主色调（暗色适配） |
| `--color-text-primary` | `rgba(255,255,255,0.85)` | 主文本 |
| `--color-bg-container` | `#141414` | 容器背景 |
| `--color-bg-layout` | `#000000` | 布局背景 |
| `--color-border` | `#303030` | 边框色 |

#### 字体体系

| 用途 | 字体栈 | 字号 |
|------|--------|------|
| 中文标题 | `PingFang SC, Microsoft YaHei UI, -apple-system, BlinkMacSystemFont, sans-serif` | 16px/14px/12px |
| 中文正文 | `PingFang SC, Microsoft YaHei UI, -apple-system, BlinkMacSystemFont, sans-serif` | 14px |
| 等宽数字 | `SF Mono, Monaco, Consolas, 'Liberation Mono', monospace` | 12px |
| 英文/代码 | `SF Mono, Monaco, Consolas, 'Liberation Mono', monospace` | 13px |

#### 间距体系

| 令牌 | 值 | 用途 |
|------|------|------|
| `--spacing-xs` | `4px` | 紧凑间距 |
| `--spacing-sm` | `8px` | 小间距 |
| `--spacing-md` | `12px` | 中等间距 |
| `--spacing-lg` | `16px` | 大间距 |
| `--spacing-xl` | `24px` | 超大间距 |

#### 圆角与阴影

| 令牌 | 值 | 用途 |
|------|------|------|
| `--radius-sm` | `4px` | 小圆角（标签、输入框） |
| `--radius-md` | `6px` | 中圆角（按钮、卡片） |
| `--radius-lg` | `8px` | 大圆角（弹窗、面板） |
| `--shadow-sm` | `0 2px 4px rgba(0,0,0,0.1)` | 小阴影 |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.15)` | 中阴影 |
| `--shadow-lg` | `0 8px 24px rgba(0,0,0,0.2)` | 大阴影 |

### 5.3 按钮设计规范

#### 按钮类型

| 按钮类型 | 样式 | 使用场景 |
|---------|------|---------|
| **主按钮** | 实心填充 `#1677ff`，白色文字，圆角6px | 主要操作（翻译、保存、提交） |
| **次按钮** | 边框 `#1677ff`，文字 `#1677ff`，圆角6px | 次要操作（取消、重置） |
| **文本按钮** | 无背景无边框，文字 `#1677ff` | 链接式操作（了解更多、查看详情） |
| **危险按钮** | 实心填充 `#ff4d4f`，白色文字 | 删除、重置等危险操作 |
| **图标按钮** | 圆形/方形，仅图标无文字 | 工具栏图标（设置、关闭、最小化） |
| **胶囊按钮** | 圆角16px（pill形状），小字号 | 标签切换、引擎选择 |

#### 按钮尺寸

| 尺寸 | 高度 | 字号 | 内边距 | 适用场景 |
|------|------|------|--------|---------|
| **大** | `44px` | `14px` | `8px 16px` | 面板主操作按钮 |
| **中** | `32px` | `14px` | `6px 12px` | 常规操作按钮 |
| **小** | `24px` | `12px` | `4px 8px` | 工具栏、紧凑布局 |
| **迷你** | `20px` | `12px` | `2px 6px` | 标签、状态指示 |

#### 按钮交互状态

```css
/* 主按钮状态变化 */
.btn-primary {
  background: #1677ff;
  color: white;
  border: none;
  transition: all 160ms ease;
}

.btn-primary:hover {
  background: #4096ff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.35);
  transform: translateY(-1px);
}

.btn-primary:active {
  background: #0958d9;
  transform: translateY(0);
  box-shadow: none;
}

.btn-primary:disabled {
  background: #d9d9d9;
  color: rgba(0,0,0,0.25);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
```

### 5.4 面板/弹窗设计规范

#### 面板结构

```
+--------------------------------------------------+
|  [Logo]  WinOCR           [引擎徽标]  [设置图标] |  ← 粘性页头（高度48px）
+--------------------------------------------------+
|                                                  |
|  [翻译输入区 - 多行文本框，带占位符提示]           |  ← 间距16px
|                                                  |
|  [源语言 ▼]  [目标语言 ▼]    [翻译按钮(主)]      |  ← 间距12px
|                                                  |
+--------------------------------------------------+
|  译文结果区                                      |
|  +--------------------------------------------+ |
|  | The patient presented with acute...        | |  ← 卡片样式
|  | 患者出现急性尿潴留。                         | |    圆角8px+阴影
|  | [复制] [朗读] [加入生词本] [复习]           | |
|  +--------------------------------------------+ |
|                                                  |
+--------------------------------------------------+
|  [历史记录] [生词本] [复习] [导出]                |  ← 底部导航栏
+--------------------------------------------------+
```

#### 卡片组件规范

| 属性 | 值 | 说明 |
|------|------|------|
| 圆角 | `8px` | 统一圆角 |
| 阴影 | `0 2px 8px rgba(0,0,0,0.09)` | 默认阴影 |
| 悬停阴影 | `0 4px 12px rgba(0,0,0,0.12)` | 悬停增强 |
| 内边距 | `12px 16px` | 内容间距 |
| 背景 | `#ffffff`（亮色）/ `#1f1f1f`（暗色） | 容器色 |
| 边框 | `1px solid #f0f0f0` | 细分隔线 |

#### 输入框规范

| 属性 | 值 | 说明 |
|------|------|------|
| 高度 | `32px`（中）/ `44px`（大） | 与按钮对齐 |
| 圆角 | `6px` | 统一圆角 |
| 边框 | `1px solid #d9d9d9` | 默认边框 |
| 聚焦边框 | `2px solid #1677ff` | 聚焦高亮 |
| 内边距 | `6px 12px` | 输入间距 |
| 过渡 | `all 160ms ease` | 平滑状态变化 |

### 5.5 动画与动效规范

| 动效 | 时长 | 缓动函数 | 用途 |
|------|------|---------|------|
| 淡入/淡出 | `160ms` | `ease` | 面板开关、结果出现 |
| 滑入/滑出 | `200ms` | `cubic-bezier(0.4, 0, 0.2, 1)` | 侧栏展开/收起 |
| 按钮悬停 | `160ms` | `ease` | 按钮交互反馈 |
| 卡片悬浮 | `200ms` | `cubic-bezier(0.4, 0, 0.2, 1)` | 卡片悬停上浮 |
| 加载旋转 | `1s` | `linear` 无限 | 翻译加载中 |

**无障碍**：所有动效必须尊重 `prefers-reduced-motion: reduce` 媒体查询，用户偏好减少动效时全部关闭。

### 5.6 浮窗（Rust壳译文显示）设计规范

Rust壳的译文浮窗采用**置顶透明窗口**实现：

| 属性 | 值 | 说明 |
|------|------|------|
| 窗口类型 | 顶层置顶 + 透明背景 + 点击穿透 | 不遮挡用户操作 |
| 圆角 | `6px` | 现代感 |
| 阴影 | `0 4px 16px rgba(0,0,0,0.2)` | 浮出感 |
| 字体 | 系统默认无衬线字体 | 与系统融合 |
| 文字颜色 | `#1a1a1a`（亮背景）/ `#f0f0f0`（暗背景） | 自适应 |
| 动画 | 出现时 `scale(0.95) → scale(1)` + 淡入，`200ms` | 平滑出现 |
| 关闭方式 | 点击外部区域 / `Esc` / 自动消失（可配置超时） | 灵活 |

### 5.7 图标规范

| 图标 | 尺寸 | 线宽 | 圆角 | 用途 |
|------|------|------|------|------|
| 常规图标 | `16px` / `20px` / `24px` | `1.5px` | `2px` | 工具栏、列表项 |
| 大图标 | `32px` / `40px` | `2px` | `3px` | 空状态、引导页 |
| 加载图标 | `20px` | `2px` | `-` | 加载中旋转 |

**图标风格**：线性图标（Outline），统一线宽，圆角端点，保持视觉一致性。

### 5.8 AI对话界面设计规范（v1.3新增）

#### 布局结构

```
+--------------------------------------------------+
|  [WinOCR Logo]  AI对话        [引擎徽标] [设置]  |  ← 顶部导航栏 (48px)
+--------------------------------------------------+
|                                                  |
|  +--------------------------------------------+ |
|  | 📄 对话标题：英文学习会话                    | |  ← 会话标题栏
|  | [切换引擎: Qwen-7B ▼] [清空] [导出]         | |
|  +--------------------------------------------+ |
|                                                  |
|  +--------------------------------------------+ |
|  | 用户：翻译下面这段话                          | |  ← 消息气泡区(可滚动)
|  | [右对齐/蓝色背景]                             | |
|  |                                              | |
|  | AI：当然可以！请提供您需要翻译的内容...       | |  ← AI消息
|  | [左对齐/灰色背景]                             | |
|  | (打字机效果：逐字显示)                        | |
|  +--------------------------------------------+ |
|                                                  |
|  +--------------------------------------------+ |
|  | [📎附件] [输入消息...]            [发送▲]   | |  ← 输入区
|  +--------------------------------------------+ |
|  [上传图片] [上传PDF] [快捷指令: 翻译/解释/改写]|
+--------------------------------------------------+
```

#### 消息气泡样式

| 属性 | 用户消息 | AI消息 |
|------|---------|--------|
| 对齐 | 右对齐 | 左对齐 |
| 背景色 | `#1677ff` (主色) | `#f5f5f5` (浅灰) |
| 文字颜色 | `#ffffff` (白) | `#1a1a1a` (深色) |
| 圆角 | `12px 12px 4px 12px` | `12px 12px 12px 4px` |
| 最大宽度 | 70% | 70% |
| 内边距 | `10px 14px` | `10px 14px` |
| 阴影 | `0 2px 8px rgba(22,119,255,0.15)` | `0 2px 8px rgba(0,0,0,0.06)` |

#### 输入区设计

| 属性 | 值 | 说明 |
|------|------|------|
| 高度 | `44px`（单行）/ 自适应（多行） | 与按钮对齐 |
| 圆角 | `22px`（胶囊形） | 现代感 |
| 边框 | `1px solid #d9d9d9` | 默认边框 |
| 聚焦边框 | `2px solid #1677ff` | 聚焦高亮 |
| 内边距 | `12px 16px` | 输入间距 |
| 发送按钮 | 圆形图标按钮，主色填充 | 右对齐 |
| 附件按钮 | 图标按钮，边框样式 | 左对齐 |

#### 引擎选择器

- 位置：对话栏顶部，显示当前使用的引擎/模型
- 样式：胶囊按钮（`border-radius: 16px`），点击展开下拉菜单
- 选项列表：显示所有可用引擎，标注状态（在线/离线/本地/云端）
- 切换动画：平滑过渡，切换时显示加载指示器

#### 快捷指令栏

- 位置：输入框下方，水平滚动标签栏
- 样式：胶囊标签，默认灰色边框
- 激活态：主色填充 + 白色文字
- 预设指令：`翻译这段话` `用更地道的表达` `解释语法` `举例说明` `缩写展开` `同义词替换`

#### 加载状态

- 打字机效果：AI回复逐字显示（每字50ms延迟）
- 加载指示器：三个跳动圆点（`#1677ff`主色）
- 流式输出：使用 ReadableStream 实时接收并渲染

#### 文件上传处理

- 支持格式：图片(JPG/PNG/GIF/WebP)、PDF、TXT、DOCX
- 上传反馈：显示文件名 + 进度条 + 处理状态
- OCR处理：图片/PDF扫描件 → Tesseract.js/PP-OCRv6 → 提取文本 → 送入AI

#### 深色模式适配

| 元素 | 浅色模式 | 深色模式 |
|------|---------|---------|
| 页面背景 | `#ffffff` | `#141414` |
| 用户气泡 | `#1677ff` | `#4096ff` |
| AI气泡 | `#f5f5f5` | `#2a2a2a` |
| 输入框背景 | `#ffffff` | `#1f1f1f` |
| 输入框边框 | `#d9d9d9` | `#303030` |
| 文字主色 | `#1a1a1a` | `#f0f0f0` |
| 文字次要 | `#888888` | `#888888` |

---

## 六、接口定义

### 6.1 Native Messaging 接口（插件 <-> Rust壳）

#### 请求消息（Rust壳 -> 插件）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 消息类型："translate"/"ping"/"screenshot"/"ocr_result" |
| text | string | 条件 | 需要翻译的文本（OCR识别结果） |
| source_lang | string | 是 | 源语言代码（如 "en", "ja", "ko"） |
| target_lang | string | 是 | 目标语言代码（如 "zh", "en"） |
| task | string | 是 | 任务类型："ocr_translate"/"text_translate"/"screenshot" |
| timestamp | number | 是 | 请求时间戳（毫秒），用于去重 |
| screenshot | string | 条件 | Base64编码的截图（screenshot任务时） |
| ocr_model | string | 条件 | 使用的OCR模型档位："tiny"/"small"/"medium" |
| ocr_confidence | number | 条件 | OCR置信度（0-1） |

#### 响应消息（插件 -> Rust壳）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 消息类型："translate_result"/"pong"/"error" |
| translation | string | 条件 | 翻译结果文本 |
| original_text | string | 条件 | 原文内容 |
| source_lang | string | 是 | 源语言代码 |
| target_lang | string | 是 | 目标语言代码 |
| engine | string | 是 | 使用的翻译引擎名称 |
| ok | boolean | 是 | 是否成功 |
| error | string | 条件 | 错误信息 |
| boxes | array | 条件 | 文字位置坐标数组（OCR场景） |

### 6.2 浏览器插件内部接口

#### TranslationEngine 接口（翻译引擎抽象）

```typescript
interface TranslationEngine {
  name: string;                    // 引擎名称
  available: boolean;               // 是否可用
  supportsLanguagePair(src: string, tgt: string): boolean;
  translate(text: string, src: string, tgt: string): Promise<TranslateResult>;
  translateBatch(texts: TextItem[], tgt: string): Promise<TranslateResult[]>;
  healthCheck(): Promise<boolean>;
}

interface TranslateResult {
  text: string;                     // 翻译结果
  confidence?: number;              // 置信度
  engine: string;                   // 使用引擎
  cached?: boolean;                 // 是否来自缓存
}
```

#### ContentService 接口（内容采集抽象）

```typescript
interface ContentService {
  type: 'dom' | 'selection' | 'ocr' | 'video' | 'pdf';
  capture(): Promise<ContentCapture>;
}

interface ContentCapture {
  text: string;                     // 捕获的文本
  lang: string;                     // 检测到的语言
  metadata: Record<string, any>;    // 附加元数据（坐标、时间戳等）
}
```

#### RenderingService 接口（结果渲染抽象）

```typescript
interface RenderingService {
  mode: 'bilingual' | 'translation_only' | 'tooltip' | 'overlay';
  render(result: TranslateResult, metadata: Record<string, any>): void;
  destroy(): void;
}
```

### 6.3 配置接口

```typescript
interface AppConfig {
  // 翻译配置
  defaultSourceLang: string;
  defaultTargetLang: string;
  preferredEngine: string;
  fallbackEngines: string[];
  enableOffline: boolean;

  // OCR配置
  ocrEngine: 'ppocr_tiny' | 'ppocr_small' | 'ppocr_medium' | 'siliconflow';
  ocrLang: string[];
  enhanceImage: boolean;

  // 显示配置
  translationStyle: TranslationStyle;
  tooltipPosition: TooltipPosition;
  overlayOpacity: number;

  // 快捷键配置
  hotkeys: Record<string, HotKeyConfig>;

  // 术语库配置
  enabledTermBases: string[];
  customTerms: CustomTerm[];

  // 隐私配置
  allowCloudTranslation: boolean;
  cacheTranslations: boolean;
}

interface HotKeyConfig {
  key: string;                     // 键帽字符
  modifiers: ('ctrl' | 'alt' | 'shift' | 'meta')[];  // 修饰键
  description: string;             // 功能描述
  isConflict: boolean;             // 是否有冲突
  fallbackKey?: string;            // 回退键（冲突时自动切换）
}
```

### 6.4 学习模块接口

#### HistoryService 接口（历史记录服务抽象）

```typescript
interface HistoryService {
  addRecord(record: Omit<HistoryRecord, 'id' | 'mastery' | 'reviewCount'>): Promise<HistoryRecord>;
  getRecord(id: string): Promise<HistoryRecord | null>;
  getRecords(filter?: RecordFilter): Promise<HistoryRecord[]>;
  deleteRecord(id: string): Promise<void>;
  updateRecord(id: string, updates: Partial<HistoryRecord>): Promise<HistoryRecord>;
  exportRecords(config: ExportConfig): Promise<ExportResult>;
  importRecords(data: HistoryRecord[]): Promise<number>;
  getStats(): Promise<ReviewStats>;
}
```

#### VocabularyService 接口（生词本服务抽象）

```typescript
interface VocabularyService {
  addWord(word: Omit<VocabularyWord, 'wordId' | 'mastery' | 'reviewCount'>): Promise<VocabularyWord>;
  getWord(id: string): Promise<VocabularyWord | null>;
  getWords(filter?: WordFilter): Promise<VocabularyWord[]>;
  updateWord(id: string, updates: Partial<VocabularyWord>): Promise<VocabularyWord>;
  deleteWord(id: string): Promise<void>;
  importWords(data: VocabularyWord[]): Promise<number>;
  exportWords(config: ExportConfig): Promise<ExportResult>;
  mergeDuplicates(): Promise<number>;
}
```

#### ReviewEngine 接口（复习引擎抽象）

```typescript
interface ReviewEngine {
  calculateNextReview(word: VocabularyWord, quality: ReviewQuality): ReviewSchedule;
  getDueReviews(): Promise<VocabularyWord[]>;
  submitReview(wordId: string, quality: ReviewQuality): Promise<VocabularyWord>;
  submitReviews(reviews: ReviewSubmission[]): Promise<VocabularyWord[]>;
  getStats(): Promise<ReviewStats>;
  getDailyTrend(days: number): Promise<DailyStat[]>;
  decayMastery(cutoffDays: number): Promise<string[]>;
  checkGraduation(): Promise<string[]>;
}

type ReviewQuality = 0 | 1 | 2 | 3;
// 0 = 完全忘记  1 = 困难  2 = 一般  3 = 容易
```

#### ExportService 接口（导出服务抽象）

```typescript
interface ExportService {
  exportToJSON(records: HistoryRecord[], words: VocabularyWord[], config: ExportConfig): Promise<ExportResult>;
  exportToCSV(records: HistoryRecord[], words: VocabularyWord[], config: ExportConfig): Promise<ExportResult>;
  exportToAnki(records: HistoryRecord[], words: VocabularyWord[], config: ExportConfig): Promise<ExportResult>;
  exportToMarkdown(records: HistoryRecord[], words: VocabularyWord[], config: ExportConfig): Promise<ExportResult>;
  exportToTSV(records: HistoryRecord[], words: VocabularyWord[], config: ExportConfig): Promise<ExportResult>;
  exportToSRT(words: VocabularyWord[], config: ExportConfig): Promise<ExportResult>;
  importFromJSON(data: string): Promise<ImportResult>;
  validateExport(data: string, format: ExportFormat): Promise<ValidationResult>;
}
```

### 6.5 LocalLLMService 接口（本地大模型引擎抽象，v1.3新增）

```typescript
interface LocalLLMService {
  // 服务发现
  discoverServices(): Promise<LocalServiceInfo[]>;
  healthCheck(serviceUrl: string): Promise<boolean>;

  // 模型管理
  getModelList(serviceUrl?: string): Promise<LLMModel[]>;
  switchModel(modelName: string): Promise<void>;
  getActiveModel(): Promise<LLMModel | null>;

  // 翻译功能
  translate(text: string, params?: LLMTranslateParams): Promise<TranslationResult>;
  translateStream(text: string, params?: LLMTranslateParams): AsyncIterable<string>;
  batchTranslate(texts: string[], params?: LLMTranslateParams): Promise<TranslationResult[]>;

  // 聊天功能（多轮对话）
  chat(messages: ChatMessage[], params?: LLMChatParams): Promise<ChatResponse>;
  chatStream(messages: ChatMessage[], params?: LLMChatParams): AsyncIterable<ChatChunk>;

  // 配置
  updateConfig(config: LocalLLMConfig): Promise<void>;
  getConfig(): Promise<LocalLLMConfig>;
}

interface LocalServiceInfo {
  name: string;               // 服务名称: "Ollama" / "LM Studio" / "text-generation-webui"
  url: string;                // 服务地址
  version?: string;           // 服务版本
  available: boolean;         // 是否可达
}

interface LLMModel {
  id: string;                 // 模型ID (如 "qwen2.5:7b")
  name: string;               // 模型名称
  size: string;               // 模型大小
  parameters: string;         // 参数量
  quantization?: string;      // 量化方式
}

interface LLMTranslateParams {
  model?: string;             // 指定模型
  temperature?: number;       // 随机性 (0-2)
  maxTokens?: number;         // 最大生成token数
  promptTemplate?: string;    // 自定义prompt模板
  systemPrompt?: string;      // 系统提示词
}

interface LLMChatParams {
  model?: string;
  temperature?: number;
  maxTokens?: number;
  keepContext?: boolean;      // 是否保留上下文
  contextWindow?: number;     // 上下文窗口大小
}

interface LocalLLMConfig {
  serviceType: 'ollama' | 'lmstudio' | 'textgen';
  serviceUrl: string;         // 默认 http://localhost:11434
  defaultModel: string;
  timeout: number;            // 请求超时(ms)
  enableStreaming: boolean;   // 是否启用流式
  autoFallback: boolean;      // 失败时自动降级到云端
}
```

### 6.6 AIChatService 接口（AI对话服务抽象，v1.3新增）

```typescript
interface AIChatService {
  // 会话管理
  createSession(title?: string): Promise<ChatSession>;
  getSession(sessionId: string): Promise<ChatSession | null>;
  listSessions(filter?: SessionFilter): Promise<ChatSession[]>;
  deleteSession(sessionId: string): Promise<void>;
  updateSessionTitle(sessionId: string, title: string): Promise<ChatSession>;

  // 消息管理
  sendMessage(sessionId: string, message: ChatInput): Promise<AsyncIterable<ChatChunk>>;
  getMessages(sessionId: string): Promise<ChatMessage[]>;
  deleteMessage(sessionId: string, messageId: string): Promise<void>;
  regenerateMessage(sessionId: string, messageId: string): Promise<AsyncIterable<ChatChunk>>;

  // 引擎切换
  setSessionEngine(sessionId: string, engineId: string): Promise<void>;
  getSessionEngine(sessionId: string): Promise<string>;

  // 文件处理
  attachFile(sessionId: string, file: File): Promise<FileAttachment>;
  processFile(sessionId: string, fileId: string): Promise<FileAnalysisResult>;

  // 导出
  exportSession(sessionId: string, format: ExportFormat): Promise<ExportResult>;

  // 学习集成
  addToVocabulary(sessionId: string, messageId: string): Promise<void>;
  getLearningStats(sessionId?: string): Promise<LearningStats>;
}

interface ChatSession {
  sessionId: string;
  title: string;
  engineId: string;           // 当前使用的引擎
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

interface ChatInput {
  content: string;
  files?: FileAttachment[];   // 附加文件
  command?: string;           // 快捷指令
}

interface ChatMessage {
  messageId: string;
  sessionId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  files?: FileAttachment[];
  engineUsed?: string;        // 使用哪个引擎回复的
  createdAt: number;
  isRegenerated?: boolean;
}

interface ChatChunk {
  messageId: string;
  delta: string;              // 增量文本（流式）
  done: boolean;              // 是否完成
  usage?: UsageStats;         // token使用情况
}

interface FileAttachment {
  fileId: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  processedText?: string;     // 处理后的文本内容
}

interface FileAnalysisResult {
  text: string;               // 提取的文本
  pageCount?: number;         // PDF页数
  imageUrl?: string;          // OCR后的图片(如果有)
  error?: string;
}

interface SessionFilter {
  keyword?: string;           // 搜索关键词
  engineId?: string;          // 按引擎筛选
  dateRange?: { start: number; end: number };
  limit?: number;
}

interface LearningStats {
  wordsAdded: number;         // 对话中添加的生词数
  sessionsCount: number;      // 会话总数
  totalMessages: number;      // 总消息数
  enginesUsed: Record<string, number>;  // 各引擎使用次数
}
```

---

## 七、开发优先级与里程碑

### 7.1 总体时间规划

| 阶段 | 时间 | 目标 | 交付物 |
|------|------|------|--------|
| **Phase 0** | 第1-2周 | 基础架构搭建 | 项目脚手架、CI/CD、代码规范 |
| **Phase 1** | 第3-6周 | 核心能力MVP | 浏览器内DOM翻译 + Tooltip渲染 |
| **Phase 2** | 第7-10周 | 多引擎与OCR | 引擎路由器 + Tesseract.js OCR |
| **Phase 3** | 第11-14周 | 浏览器外能力 | Native Messaging + Rust壳程序 |
| **Phase 4** | 第15-18周 | 高级功能+UI完善 | 视频字幕、PDF翻译、术语库、UI设计 |
| **Phase 5** | 第19-20周 | 优化与发布 | 性能优化、测试、上架商店 |
| **Phase 6** | 第21-26周 | 学习模块 | 历史记录、生词本、复习引擎、导出 |

### 7.2 Phase 0：基础架构搭建（第1-2周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| 项目仓库初始化（Monorepo结构） | 架构师 | 1天 | - |
| 构建工具链配置（Vite + TypeScript） | 前端工程师 | 1天 | - |
| Chrome Extension Manifest V3 基础模板 | 前端工程师 | 1天 | - |
| Service Worker 基础通信框架 | 前端工程师 | 2天 | Manifest模板 |
| **Rust本地壳项目脚手架** | 后端工程师 | 2天 | - |
| **Cargo.toml配置（serde/onnxruntime/winapi/winit）** | 后端工程师 | 1天 | Rust脚手架 |
| Native Messaging Host 注册脚本 | 后端工程师 | 1天 | Rust脚手架 |
| ESLint/Prettier/Commitlint配置 | 全员 | 1天 | - |
| **Clippy + Rustfmt代码规范** | 全员 | 1天 | - |
| GitHub Actions CI/CD流水线 | 运维 | 2天 | - |
| 单元测试框架搭建 | 测试工程师 | 2天 | - |

### 7.3 Phase 1：核心能力MVP（第3-6周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| M2 DOM内容采集器（基础遍历） | 前端工程师 | 3天 | Phase 0 |
| M2 DOM内容采集器（智能识别+过滤） | 前端工程师 | 3天 | DOM基础 |
| M2 MutationObserver动态监听 | 前端工程师 | 2天 | DOM基础 |
| M3悬停翻译器（基础版） | 前端工程师 | 3天 | DOM采集器 |
| M8结果渲染引擎（双语对照模式） | 前端工程师 | 4天 | 悬停翻译器 |
| M8结果渲染引擎（Tooltip模式） | 前端工程师 | 3天 | 双语对照 |
| M7翻译引擎路由器（Google引擎） | 前端工程师 | 3天 | 渲染引擎 |
| M7翻译引擎路由器（Bing引擎） | 前端工程师 | 2天 | Google引擎 |
| M12设置与配置中心（基础版） | 前端工程师 | 3天 | 路由器 |
| M1用户交互管理器（快捷键+Popup） | 前端工程师 | 3天 | 配置中心 |
| MVP内部测试与调试 | 全员 | 3天 | 全部模块 |

**MVP里程碑交付物**：安装插件后可在网页上实现悬停翻译和全页翻译，支持Google和Bing两种引擎。

### 7.4 Phase 2：多引擎与OCR（第7-10周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| M7引擎路由器（SiliconFlow引擎集成） | 前端工程师 | 3天 | Phase 1 |
| M7引擎路由器（Edge Translator API集成） | 前端工程师 | 4天 | SiliconFlow引擎 |
| M7引擎路由器（MyMemory免Key引擎） | 前端工程师 | 2天 | Edge引擎 |
| M7智能路由策略实现 | 前端工程师 | 3天 | 所有引擎 |
| M4屏幕截图OCR引擎（Tesseract.js集成） | 前端工程师 | 5天 | Edge引擎 |
| M4语言包懒加载机制 | 前端工程师 | 2天 | Tesseract集成 |
| M10 PDF翻译模块（基础版） | 前端工程师 | 5天 | OCR引擎 |
| M11术语库管理器（基础版） | 前端工程师 | 3天 | 路由器 |
| M8渲染引擎增强（CSS变量配置） | 前端工程师 | 2天 | 基础渲染 |
| 请求缓存机制（IndexedDB） | 前端工程师 | 3天 | 路由器 |
| 失败自动降级与并发请求优化 | 前端工程师 | 3天 | 路由器 |
| Phase 2测试与调试 | 全员 | 3天 | 全部模块 |

**Phase 2里程碑交付物**：支持6+翻译引擎智能路由、浏览器内图片OCR翻译、PDF文档翻译、术语库管理。

### 7.5 Phase 3：浏览器外能力 — Rust壳开发（第11-14周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| M5 Native Messaging通信桥（插件端） | 前端工程师 | 3天 | Phase 2 |
| M5 Native Messaging通信桥（Rust壳端） | 后端工程师 | 3天 | 插件端 |
| **M6 Rust壳：截图模块（DXGI+BitBlt）** | 后端工程师 | 5天 | Phase 0 Rust脚手架 |
| **M6 Rust壳：PP-OCRv6 ONNX Runtime集成** | 后端工程师 | 7天 | 截图模块 |
| **M6 Rust壳：三档模型管理（Tiny/Small/Medium）** | 后端工程师 | 3天 | OCR集成 |
| **M6 Rust壳：winit浮窗+GDI绘制** | 后端工程师 | 5天 | OCR模块 |
| **M6 Rust壳：全局热键管理（含冲突回退）** | 后端工程师 | 4天 | 绘制模块 |
| **M6 Rust壳：JSON序列化/反序列化** | 后端工程师 | 2天 | 通信桥 |
| **M6 Rust壳：单实例保护+多实例名册** | 后端工程师 | 3天 | 热键模块 |
| **M6 Rust壳：配置管理（winocr_config.json）** | 后端工程师 | 2天 | 通信桥 |
| 端到端联调（插件<->Rust壳） | 前后端协作 | 5天 | 全部子模块 |
| 多显示器支持 | 后端工程师 | 2天 | 联调完成 |
| 内存管理与异常处理 | 后端工程师 | 3天 | 联调完成 |
| Phase 3测试与调试 | 全员 | 4天 | 全部模块 |

**Phase 3里程碑交付物**：Rust壳程序编译为~100-200KB可执行文件，通过全局快捷键在任何界面实现截图翻译，译文原位覆盖显示。启动时间<50ms，内存占用<30MB。

### 7.6 Phase 4：高级功能与UI完善（第15-18周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| M9视频字幕模块（YouTube） | 前端工程师 | 5天 | Phase 2 |
| M9视频字幕模块（Netflix） | 前端工程师 | 4天 | YouTube |
| M10 PDF翻译模块（扫描件OCR） | 前端工程师 | 4天 | Phase 2 PDF基础 |
| M11术语库管理器（高级版） | 前端工程师 | 3天 | Phase 2术语库 |
| M12设置中心（高级配置+快捷键系统） | 前端工程师 | 5天 | Phase 1设置中心 |
| **UI设计系统实现（Design Tokens+组件库）** | 前端工程师 | 5天 | Phase 1设置中心 |
| TTS语音朗读集成 | 前端工程师 | 3天 | Phase 2 |
| 输入框实时翻译 | 前端工程师 | 3天 | Phase 1 |
| 暗色模式支持 | 前端工程师 | 2天 | Phase 2渲染 |
| 多语言UI（i18n） | 前端工程师 | 4天 | Phase 1 |
| 无障碍访问优化 | 前端工程师 | 3天 | 全部功能 |
| Phase 4测试与调试 | 全员 | 4天 | 全部模块 |

**Phase 4里程碑交付物**：完整的视频双语字幕、PDF扫描件翻译、TTS语音朗读、多语言UI、完善的快捷键自定义系统、现代化UI组件库。

### 7.7 Phase 5：优化与发布（第19-20周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| 性能优化（启动速度、内存占用） | 全员 | 3天 | Phase 4 |
| 包体积优化（Tree-shaking、代码压缩） | 前端工程师 | 2天 | Phase 4 |
| **Rust壳体积优化（静态链接、strip调试信息）** | 后端工程师 | 2天 | Phase 3 |
| **Rust壳启动时间优化（延迟加载ONNX Runtime）** | 后端工程师 | 2天 | Phase 3 |
| 安全审计（权限最小化、隐私合规） | 安全工程师 | 3天 | Phase 4 |
| 兼容性测试（Chrome/Edge/Firefox） | 测试工程师 | 3天 | Phase 4 |
| 用户文档与帮助页面 | 文档工程师 | 3天 | Phase 4 |
| Chrome Web Store 上架准备 | 运维 | 2天 | 安全审计通过 |
| Microsoft Edge Add-ons 上架 | 运维 | 2天 | Chrome上架 |
| Firefox Add-ons 上架 | 运维 | 2天 | Chrome上架 |
| 正式发布与监控搭建 | 运维 | 2天 | 上架完成 |

**Phase 5里程碑交付物**：正式版发布至Chrome Web Store、Edge Add-ons、Firefox Add-ons，具备完整的用户文档和监控体系。

### 7.8 Phase 6：学习模块（第21-26周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| M13 历史记录服务（基础版） | 前端工程师 | 4天 | Phase 2 |
| M13 历史记录自动入池逻辑 | 前端工程师 | 3天 | 基础版 |
| M14 生词本服务（基础版） | 前端工程师 | 5天 | Phase 2 |
| M14 手动添加/过滤规则 | 前端工程师 | 3天 | 基础版 |
| M15 复习引擎（SM-2 算法） | 前端工程师 | 5天 | 生词本服务 |
| M15 复习队列管理 | 前端工程师 | 3天 | SM-2算法 |
| M15 掌握度衰减与毕业逻辑 | 前端工程师 | 2天 | 复习队列 |
| M16 导出服务（JSON/CSV） | 前端工程师 | 3天 | Phase 2 |
| M16 导出服务（Anki/Markdown/TSV/SRT） | 前端工程师 | 5天 | JSON/CSV |
| M16 导入与验证逻辑 | 前端工程师 | 3天 | 导出服务 |
| 复习面板 UI（闪卡模式） | 前端工程师 | 5天 | 复习引擎 |
| 学习统计仪表盘 | 前端工程师 | 4天 | 复习引擎 |
| 每日学习报告/通知 | 前端工程师 | 3天 | 复习引擎 |
| 增量同步机制 | 前端工程师 | 3天 | 导出服务 |
| 学习模块端到端联调 | 前后端协作 | 5天 | 全部子模块 |
| Phase 6 测试与调试 | 全员 | 5天 | 全部模块 |

**Phase 6里程碑交付物**：完整的翻译→学习闭环——每次翻译自动记录、自动进入复习队列、支持四种复习模式、六种格式导出、跨设备数据迁移。

### 7.9 Phase 7：本地大模型与AI对话界面（第27-34周）

| 任务 | 负责人 | 预估工时 | 依赖 |
|------|--------|---------|------|
| M17 本地大模型服务发现模块 | 前端工程师 | 3天 | Phase 2 |
| M17 Ollama API集成（模型列表/健康检查） | 前端工程师 | 3天 | 服务发现 |
| M17 翻译接口实现（普通翻译+流式翻译） | 前端工程师 | 5天 | API集成 |
| M17 Rust壳端本地LLM客户端 | 后端工程师 | 5天 | Phase 3 Rust壳 |
| M17 本地模型管理UI（设置页） | 前端工程师 | 4天 | 翻译接口 |
| M17 降级策略实现（本地→云端自动切换） | 前端工程师 | 3天 | 翻译接口 |
| M18 AI对话界面基础框架 | 前端工程师 | 5天 | Phase 4 UI系统 |
| M18 消息气泡组件（用户/AI消息渲染） | 前端工程师 | 4天 | 基础框架 |
| M18 流式输出/打字机效果 | 前端工程师 | 3天 | 消息组件 |
| M18 会话管理（创建/切换/删除/搜索） | 前端工程师 | 5天 | 基础框架 |
| M18 引擎切换器组件 | 前端工程师 | 3天 | 会话管理 |
| M18 文件上传与处理（图片/PDF） | 前端工程师 | 5天 | 会话管理 |
| M18 快捷指令系统 | 前端工程师 | 3天 | 消息组件 |
| M18 对话导出功能 | 前端工程师 | 4天 | 会话管理 |
| M18 学习模块集成（对话生词→生词本） | 前端工程师 | 4天 | Phase 6学习模块 |
| M18 深色模式适配 | 前端工程师 | 3天 | 全部组件 |
| M18 端到端联调（对话→引擎→学习模块） | 前后端协作 | 5天 | 全部子模块 |
| Phase 7 测试与调试 | 全员 | 5天 | 全部模块 |

**Phase 7里程碑交付物**：完整的AI对话界面——支持多轮对话、引擎切换、文件上传分析、流式输出、对话历史管理、与学习模块无缝集成。本地大模型引擎接口可用，支持Ollama/LM Studio等本地服务，具备自动降级能力。

---

## 八、技术栈总览

### 8.1 前端（浏览器插件）

| 技术 | 用途 | 版本要求 |
|------|------|---------|
| TypeScript | 主要开发语言 | >= 5.0 |
| Vite | 构建工具 | >= 5.0 |
| Chrome Extension API | 扩展能力 | Manifest V3 |
| Tesseract.js | 浏览器端OCR | >= 5.0 |
| PDF.js | PDF解析 | >= 4.0 |
| IndexedDB | 本地缓存 | - |
| Web Worker | OCR后台线程 | - |
| CSS Variables / Tailwind | 样式管理（Design Tokens） | - |
| Highlight.js | 代码高亮（AI对话界面） | >= 11.0 |
| EventSource / ReadableStream | 流式响应处理 | - |

### 8.2 后端（Rust本地壳程序）

| 技术 | 用途 | 版本要求 |
|------|------|---------|
| **Rust 2021** | **主要开发语言** | **>= 1.70** |
| **Cargo** | **构建系统 + 包管理** | **>= 1.70** |
| **onnxruntime** | **PP-OCRv6 ONNX模型推理** | **>= 1.16** |
| **winapi / windows** | **Win32 API绑定（截图/热键/窗口）** | **最新** |
| **winit** | **跨平台窗口管理（浮窗绘制）** | **>= 0.29** |
| **serde + serde_json** | **JSON序列化/反序列化** | **>= 1.0** |
| **tokio** | **异步运行时（NM通信）** | **>= 1.0** |
| **clap** | **命令行参数解析** | **>= 4.0** |
| **anyhow + thiserror** | **错误处理** | **最新** |
| **reqwest** | **HTTP客户端（调用本地Ollama等）** | **>= 0.11** |
| **tokio** | **异步运行时（HTTP流式响应）** | **>= 1.0** |

### 8.3 OCR引擎对比

| 引擎 | 类型 | 速度 | 精度 | 离线 | 体积 | 推荐场景 |
|------|------|------|------|------|------|---------|
| **PP-OCRv6 Tiny** | 本地ONNX | ~100ms | 84.1%检测 | 是 | ~6MB | 默认推荐，快速预览 |
| **PP-OCRv6 Small** | 本地ONNX | ~500ms | 86.2%检测 | 是 | ~30MB | 日常截图翻译 |
| **PP-OCRv6 Medium** | 本地ONNX | ~1.4s | 最高精度 | 是 | ~133MB | 医学文档/复杂版面 |
| **SiliconFlow云端** | 云端API | 103-121s | 有幻觉 | 否 | 无 | 本地不可用时兜底 |

### 8.4 Rust壳 vs Python壳 性能对比

| 指标 | Python壳（旧） | Rust壳（新） | 提升 |
|------|---------------|-------------|------|
| 二进制体积 | ~50MB（含Python解释器） | ~100-200KB | **250-500倍** |
| 启动时间 | 1-2秒 | <50ms | **20-40倍** |
| 截图→OCR延迟 | ~500ms | <100ms | **5倍** |
| 内存占用 | ~200MB | ~20-30MB | **7-10倍** |
| 并发能力 | 单线程（GIL锁） | 多线程无锁 | **质的飞跃** |
| 类型安全 | 动态类型 | 编译期类型检查 | **零空指针** |

### 8.5 翻译引擎

| 引擎 | 类型 | 费用 | 特点 |
|------|------|------|------|
| Edge Translator API | 本地离线 | 免费 | 零延迟、隐私安全、145+语言 |
| Google Translate | 云端 | 免费(限量) | 通用性强、语言覆盖广 |
| Bing Translate | 云端 | 免费 | 微软背书、中文优化 |
| SiliconFlow | 云端 | 免费(带key) | 高质量、国内直连、Qwen模型 |
| MyMemory | 云端 | 免费(免key) | 国内直连、匿名5000字符/天 |
| OpenAI GPT | 云端 | 按量付费 | 长文本/专业领域强 |
| Claude | 云端 | 按量付费 | 上下文理解强 |
| Gemini | 云端 | 按量付费 | Google多模态，代码/图像理解强 |
| DeepL | 云端 | 免费(限量)/付费 | 专业翻译质量高，欧洲语言优势 |
| **Ollama(本地)** | **本地** | **免费** | **完全离线、隐私安全、Qwen/Llama/ChatGLM等** |

### 8.6 开发工具

| 工具 | 用途 |
|------|------|
| Git + GitHub | 版本管理 |
| GitHub Actions | CI/CD |
| ESLint + Prettier | 前端代码规范 |
| **rustfmt + clippy** | **Rust代码规范** |
| Vitest | 单元测试 |
| Playwright | E2E测试 |
| VS Code | 前端开发 |
| **VS Code + rust-analyzer** | **Rust开发（无需Visual Studio）** |
| Wireshark | 网络调试 |
| **Ollama** | **本地大模型运行服务** |
| **LM Studio** | **本地大模型GUI管理工具** |

---

## 九、风险与应对

### 9.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| **PP-OCRv6 ONNX Runtime Rust绑定稳定性** | OCR功能不可用 | 中 | 保留SiliconFlow云端兜底；监控onnxruntime crate更新 |
| Tesseract.js OCR准确率不足 | 用户体验差 | 中 | 集成PP-OCRv6作为主力；图像预处理增强 |
| Edge Translator API稳定性 | 离线翻译不可用 | 低 | 自动降级到云端引擎 |
| Native Messaging兼容性 | 部分浏览器不支持 | 中 | Firefox/Edge各有差异，需分别适配测试 |
| **Rust壳被杀毒软件误报** | 用户安装失败 | 中 | 代码签名证书；提供开源源码供审计 |
| 翻译API限流 | 高频使用受限 | 高 | 请求队列+指数退避；多引擎负载均衡 |
| Manifest V3迁移 | 扩展API变更 | 中 | 紧跟Chrome更新；提前适配V3 |
| **Rust编译时间** | 开发效率影响 | 低 | CI缓存依赖；增量编译默认开启 |

### 9.2 合规风险

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 翻译内容隐私 | 用户数据泄露 | 默认本地OCR；云端翻译可选；明确隐私政策 |
| 版权合规 | 翻译文本版权 | 不存储用户翻译内容；引用翻译引擎服务条款 |
| 商店审核 | 上架被拒 | 权限最小化声明；提供清晰的功能说明 |

### 9.3 运维风险

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 翻译API变更 | 功能中断 | 抽象引擎接口；快速适配新API |
| 浏览器更新 | 扩展不兼容 | 自动化测试覆盖主流浏览器版本 |
| 用户反馈处理 | 口碑影响 | 建立反馈渠道；定期发布更新 |
| **ONNX Runtime版本兼容性** | 模型推理失败 | 锁定ONNX Runtime版本；模型格式版本声明 |

---

## 十、项目目录结构

```
screen-translator/
|-- browser-extension/          # 浏览器插件（TypeScript）
|   |-- src/
|   |   |-- background/         # Service Worker（后台脚本）
|   |   |   |-- engine-router.ts    # 翻译引擎路由器
|   |   |   |-- native-bridge.ts    # Native Messaging桥
|   |   |   |-- cache.ts            # 请求缓存
|   |   |   |-- hotkey-manager.ts   # 快捷键管理器
|   |   |-- content/            # Content Script
|   |   |   |-- dom-capture.ts      # DOM内容采集
|   |   |   |-- hover-translator.ts # 悬停翻译
|   |   |   |-- renderer.ts         # 结果渲染
|   |   |   |-- ui-components.ts    # UI组件（Design Tokens）
|   |   |   |-- pdf-translator.ts   # PDF翻译
|   |   |   |-- video-subtitles.ts  # 视频字幕
|   |   |-- worker/             # Web Worker
|   |   |   |-- ocr-worker.ts       # Tesseract.js OCR
|   |   |-- popup/              # 弹窗页面
|   |   |   |-- popup.html
|   |   |   |-- popup.ts
|   |   |   |-- popup.css         # 样式（Design Tokens）
|   |   |-- options/            # 选项页面
|   |   |   |-- options.html
|   |   |   |-- options.ts
|   |   |   |-- options.css       # 样式（Design Tokens）
|   |   |-- types/              # TypeScript类型定义
|   |   |   |-- engine.ts
|   |   |   |-- message.ts
|   |   |   |-- config.ts
|   |   |   |-- hotkey.ts         # 快捷键类型
|   |   |   |-- ui.ts             # UI类型
|   |   |-- utils/              # 公共工具函数
|   |       |-- language.ts
|   |       |-- debounce.ts
|   |       |-- storage.ts
|   |-- public/                 # 静态资源
|   |   |-- icons/              # 扩展图标
|   |-- manifest.json           # Manifest V3配置
|   |-- vite.config.ts
|   |-- package.json

|-- learning-module/              # 学习模块（历史记录 + 生词本 + 复习 + 导出）
|   |-- src/
|   |   |-- history/              # 历史记录服务
|   |   |   |-- history-service.ts
|   |   |   |-- history-store.ts
|   |   |   |-- history-model.ts
|   |   |   |-- history-filter.ts
|   |   |-- vocabulary/           # 生词本服务
|   |   |   |-- vocab-service.ts
|   |   |   |-- vocab-store.ts
|   |   |   |-- vocab-model.ts
|   |   |   |-- vocab-merge.ts
|   |   |-- review/               # 复习引擎
|   |   |   |-- review-engine.ts
|   |   |   |-- sm2-algorithm.ts
|   |   |   |-- review-scheduler.ts
|   |   |   |-- review-queue.ts
|   |   |   |-- decay.ts
|   |   |   |-- graduation.ts
|   |   |-- export/               # 导出服务
|   |   |   |-- export-service.ts
|   |   |   |-- export-json.ts
|   |   |   |-- export-csv.ts
|   |   |   |-- export-anki.ts
|   |   |   |-- export-md.ts
|   |   |   |-- export-tsv.ts
|   |   |   |-- export-srt.ts
|   |   |   |-- import.ts
|   |   |   |-- validator.ts
|   |   |-- ui/                   # 学习模块 UI 组件
|   |   |   |-- review-panel.ts
|   |   |   |-- vocab-manager.ts
|   |   |   |-- stats-dashboard.ts
|   |   |   |-- export-dialog.ts
|   |   |-- types/                # 类型定义
|   |   |   |-- learning.ts
|   |   |   |-- export.ts
|   |   |-- utils/                # 工具函数
|   |       |-- date-formatter.ts
|   |       |-- notification.ts
|   |       |-- download.ts

|-- local-llm/                  # 本地大模型引擎接口（v1.3新增）
|   |-- src/
|   |   |-- discovery/          # 服务发现
|   |   |   |-- service-discover.ts   # 本地服务自动探测
|   |   |   |-- ollama-client.ts      # Ollama API客户端
|   |   |   |-- lmstudio-client.ts    # LM Studio API客户端
|   |   |   |-- textgen-client.ts     # text-generation-webui客户端
|   |   |-- models/               # 模型管理
|   |   |   |-- model-list.ts       # 模型列表获取
|   |   |   |-- model-switcher.ts   # 模型切换
|   |   |   |-- model-cache.ts      # 模型信息缓存
|   |   |-- translation/          # 翻译功能
|   |   |   |-- llm-translator.ts   # 本地LLM翻译主类
|   |   |   |-- stream-handler.ts   # 流式响应处理
|   |   |   |-- batch-translate.ts  # 批量翻译
|   |   |   |-- prompt-templates.ts # 翻译prompt模板
|   |   |-- chat/                 # 聊天功能
|   |   |   |-- llm-chat.ts         # 本地LLM聊天
|   |   |   |-- context-manager.ts  # 上下文窗口管理
|   |   |   |-- message-formatter.ts # 消息格式化
|   |   |-- config/               # 配置管理
|   |   |   |-- llm-config.ts       # 本地LLM配置
|   |   |   |-- fallback.ts         # 降级策略
|   |   |-- types/                # 类型定义
|   |   |   |-- llm-service.ts
|   |   |   |-- ollama.ts
|   |   |   |-- chat.ts
|   |-- tests/
|       |-- service-discover.test.ts
|       |-- ollama-client.test.ts
|       |-- stream-handler.test.ts

|-- ai-chat/                      # AI对话界面（v1.3新增）
|   |-- src/
|   |   |-- session/              # 会话管理
|   |   |   |-- session-manager.ts  # 会话CRUD操作
|   |   |   |-- session-store.ts    # IndexedDB存储
|   |   |   |-- session-search.ts   # 会话搜索
|   |   |-- messages/             # 消息管理
|   |   |   |-- message-manager.ts  # 消息CRUD操作
|   |   |   |-- message-renderer.ts # 消息渲染(气泡样式)
|   |   |   |-- stream-reader.ts    # 流式读取器
|   |   |   |-- typing-effect.ts    # 打字机效果
|   |   |-- components/           # UI组件
|   |   |   |-- chat-input.ts       # 输入框组件
|   |   |   |-- message-bubble.ts   # 消息气泡组件
|   |   |   |-- engine-switcher.ts  # 引擎选择器
|   |   |   |-- quick-commands.ts   # 快捷指令栏
|   |   |   |-- file-uploader.ts    # 文件上传组件
|   |   |   |-- loading-indicator.ts # 加载指示器
|   |   |   |-- chat-panel.ts       # 对话面板主组件
|   |   |-- files/                # 文件处理
|   |   |   |-- file-processor.ts   # 文件处理主类
|   |   |   |-- image-ocr.ts        # 图片OCR
|   |   |   |-- pdf-reader.ts       # PDF读取
|   |   |   |-- text-reader.ts      # 文本文件读取
|   |   |-- export/               # 对话导出
|   |   |   |-- chat-export.ts      # 导出主类
|   |   |   |-- export-md.ts        # Markdown导出
|   |   |   |-- export-pdf.ts       # PDF导出
|   |   |   |-- export-text.ts      # 纯文本导出
|   |   |-- learning/             # 学习模块集成
|   |   |   |-- vocab-saver.ts      # 对话生词保存
|   |   |   |-- learning-stats.ts   # 学习统计
|   |   |-- utils/                # 工具函数
|   |   |   |-- markdown-render.ts  # Markdown渲染
|   |   |   |-- code-highlight.ts   # 代码高亮
|   |   |   |-- theme-manager.ts    # 主题管理
|   |   |-- types/                # 类型定义
|   |   |   |-- ai-chat.ts
|   |   |   |-- file-attachment.ts
|   |   |-- styles/               # 样式
|   |       |-- chat-theme.css      # 主题变量
|   |       |-- chat-components.css # 组件样式
|   |-- tests/
|       |-- session-manager.test.ts
|       |-- message-renderer.test.ts
|       |-- stream-reader.test.ts

|-- native-host/                # Rust本地壳程序
|   |-- src/
|   |   |-- main.rs               # 入口（多实例管理+模式判断）
|   |   |-- screenshot.rs         # 截图模块（DXGI优先+BitBlt兜底）
|   |   |-- ocr.rs                # OCR引擎调度（PP-OCRv6 + SiliconFlow兜底）
|   |   |-- ocr_models.rs         # 三档模型管理（Tiny/Small/Medium）
|   |   |-- draw.rs               # 浮窗绘制（winit+GDI）
|   |   |-- ipc.rs                # Native Messaging通信（stdin/stdout）
|   |   |-- hotkey.rs             # 全局热键管理（RegisterHotKey）
|   |   |-- config.rs             # 配置管理（serde序列化）
|   |   |-- instance.rs           # 单实例保护+多实例名册
|   |   |-- error.rs              # 错误处理（thiserror）
|   |   |-- types.rs              # 共享类型定义
|   |   |-- llm_client.rs         # 本地大模型HTTP客户端（reqwest）[v1.3新增]
|   |   |-- llm_translate.rs      # 本地LLM翻译调度 [v1.3新增]
|   |-- Cargo.toml                # Rust依赖配置
|   |-- Cargo.lock
|   |-- models/                   # PP-OCRv6模型文件
|   |   |-- ocr/
|   |       |-- v6_tiny/          # Tiny档（6.6MB，随项目内置）
|   |       |-- v6_small/         # Small档（用户自行下载）
|   |       |-- v6_medium/        # Medium档（用户自行下载）
|   |-- scripts/
|   |   |-- install.bat           # Windows安装脚本
|   |   |-- uninstall.bat         # Windows卸载脚本
|   |   |-- install_deps.bat      # 依赖安装（ONNX Runtime等）

|-- docs/                       # 文档
|   |-- api.md                  # 接口文档
|   |-- setup.md                # 搭建指南
|   |-- user-guide.md           # 用户手册
|   |-- ui-guide.md             # UI设计规范
|-- scripts/                    # 构建/部署脚本
|   |-- build-all.sh
|   |-- build-rust.sh
|   |-- package-extension.sh
|   |-- sign-binary.ps1
|-- .github/
|   |-- workflows/
|   |   |-- ci.yml              # CI流水线（含Rust + TS）
|   |   |-- release.yml         # 发布流水线
|-- .eslintrc.json
|-- .prettierrc
|-- README.md
|-- package.json                # 根包管理
```

---

## 十一、验收标准

### 11.1 功能验收

| 编号 | 功能点 | 验收标准 |
|------|--------|---------|
| F1 | 网页悬停翻译 | 鼠标悬停文本0.5秒内显示翻译Tooltip |
| F2 | 全页翻译 | 一键翻译整页，支持双语对照/仅译文切换 |
| F3 | 图片OCR翻译 | 截图后自动OCR识别并翻译，准确率>=85% |
| F4 | 任意界面翻译 | 全局快捷键触发，Rust壳截图OCR翻译后浮窗显示 |
| F5 | 多引擎切换 | 支持6+引擎，智能路由自动选择最优 |
| F6 | 离线翻译 | Edge引擎可用时完全离线翻译 |
| F7 | 视频字幕 | YouTube视频双语字幕实时叠加 |
| F8 | PDF翻译 | PDF文档双语对照显示，保留排版 |
| F9 | 术语库 | 自定义术语正确匹配并优先使用 |
| F10 | **快捷键自定义** | **用户可自由录入/修改所有快捷键，冲突自动回退，即时生效** |
| F11 | 翻译历史记录 | 每次翻译自动记录，支持按领域/日期筛选，记录含来源溯源 |
| F12 | 生词本管理 | 自动采集+手动添加，支持掌握度追踪与毕业归档 |
| F13 | 间隔重复复习 | SM-2算法调度复习，支持四种复习模式（英中/中英/填空/听写） |
| F14 | 学习数据导出 | 支持JSON/CSV/Anki/Markdown/TSV/SRT六种格式导出，保留学习元数据 |
| F15 | 跨设备数据迁移 | 导出文件可完整恢复学习状态，支持增量同步 |
| F16 | **现代UI设计** | **Design Tokens统一、暗色模式、按钮交互反馈、动效符合规范** |
| F17 | **本地大模型翻译引擎** | **可自动发现本地Ollama/LM Studio服务，支持Qwen/Llama/ChatGLM等模型切换，翻译质量可接受，本地不可用时自动降级到云端引擎** |
| F18 | **AI对话界面** | **提供类ChatGPT对话式UI，支持多轮对话上下文、引擎切换、文件上传分析、流式打字机效果、对话历史管理、深色模式** |
| F19 | **对话与学习模块集成** | **对话中用户标记的词汇自动加入生词本，对话历史可导出，对话数据统计可用** |
| F20 | **智能路由增强** | **根据文本类型/长度/网络状况/成本自动选择最优引擎（含本地大模型），路由决策准确率高，降级策略可靠** |

### 11.2 性能验收

| 指标 | 目标值 | 测试条件 |
|------|--------|---------|
| 插件启动时间 | < 2秒 | 冷启动 |
| 悬停翻译延迟 | < 500ms | 网络正常 |
| **Rust壳启动时间** | **< 50ms** | **冷启动** |
| **截图→OCR→译文（本地）** | **< 100ms** | **Tiny模型，本地OCR** |
| 截图→OCR→译文（云端兜底） | < 3秒 | SiliconFlow OCR |
| **Rust壳二进制体积** | **< 200KB** | **release构建+strip** |
| **Rust壳内存占用** | **< 30MB** | **正常运行** |
| 插件包体积 | < 1MB | 生产构建 |
| 内存占用 | < 50MB | 正常使用场景 |
| OCR准确率 | >= 90% | 清晰文本 |
| 翻译准确率 | >= 95% | 常用语言对 |

### 11.3 兼容性验收

| 浏览器 | 版本要求 | 状态 |
|--------|---------|------|
| Chrome | >= 120 | 必须支持 |
| Edge | >= 120 | 必须支持 |
| Firefox | >= 120 | 应该支持 |
| Opera | >= 105 | 最好支持 |

---


## 十三、开发策略：复制 vs AI写 vs 自研

### 13.1 策略总览

本项目采用**三种策略混合使用**的开发模式，根据模块复杂度、技术栈匹配度、代码复用价值三个维度决定每个模块的实现方式：

| 策略 | 适用场景 | 预估效率提升 | 代码质量保障 |
|------|---------|-------------|-------------|
| **直接复制开源代码** | 技术栈完全一致、代码经过验证、模块边界清晰 | 省3-4周 | 社区验证，bug少 |
| **AI从零写** | 小模块、一次性代码、需求高度定制化 | 省60-80%时间 | 需逐行审查 |
| **复制骨架+AI填充** | 架构参考开源、细节让AI实现 | 省50%时间 | 架构可控，细节AI辅助 |
| **完全自研** | 项目独创功能、无参考项目 | 基准速度 | 完全自主可控 |

**核心原则**：成熟的轮子直接复制（省3-4周），小模块让AI写（省60-80%时间），核心架构复制骨架让AI填充（省50%时间但保证质量）。算法和架构决策你自己定，重复性的代码生成和文档编写全部交给AI。AI是执行者，你是架构师和审查员。

### 13.2 参考开源项目清单

| 优先级 | 项目 | GitHub | 技术栈 | 可复用核心价值 |
|--------|------|--------|--------|---------------|
| 必下 | Prism | prism-app/prism | Rust + Tauri | Rust壳架构、AI大模型接口、SQLite存储 |
| 必下 | 飞舟OCR | docvelo-ai/velocr | Rust + Tauri + MNN | PP-OCRv6三档模型集成、MNN桥接层 |
| 必下 | STranslate | STranslate/STranslate | C# WPF | 多引擎路由设计、划词翻译、插件系统 |
| 强烈建议 | Pot Desktop | pot-app/pot-desktop | TypeScript + Tauri | 插件扩展系统、剪贴板监听 |
| 强烈建议 | Crow Translate | Shatur95/Crow-Translate | C++17 + Qt 6 | 全局热键钩子、内存优化 |
| 强烈建议 | Translumo | Translumo/Translumo | C# .NET | 多OCR引擎择优机制 |
| 按需下载 | Argos Translate | argosopentech/argos-translate | Python | 离线翻译降级方案 |
| 按需下载 | BabelDOC | BabelDOC/BabelDOC | Python | PDF排版保持技术 |

### 13.3 逐模块开发策略矩阵

#### 模块 M1 — 用户交互管理器

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Pot Desktop | chrome.storage管理、popup/options页面结构 | 功能名/图标替换 |
| **AI写** | — | — | 项目特定交互逻辑 |

**预估**：复制60% + AI写40% = 约2天完成

#### 模块 M2 — DOM内容采集器

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | STranslate | DOM遍历逻辑、MutationObserver监听、文本清洗 | 过滤规则适配项目需求 |
| **AI写** | — | — | 长文本分块策略 |

**预估**：复制70% + AI写30% = 约3天完成

#### 模块 M3 — 悬停翻译器

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | STranslate | mousemove/mouseup事件监听、getSelection捕获、防抖处理 | Tooltip定位逻辑适配 |
| **AI写** | — | — | 特定场景优化 |

**预估**：复制80% + AI写20% = 约2天完成

#### 模块 M4 — 屏幕截图OCR引擎

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Prism | Canvas截图API、Tesseract.js集成 | 语言包管理适配 |
| **参考重写** | STranslate | 离线模型下载管理流程 | Rust端实现 |

**预估**：复制50% + 参考重写50% = 约5天完成

#### 模块 M5 — Native Messaging通信桥

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Pot Desktop | chrome.runtime.connectNative、port.postMessage/onMessage | 消息schema适配 |
| **直接复制** | 飞舟OCR | Rust端stdin/stdout JSON序列化 | 协议字段适配 |

**预估**：复制90% + AI写10% = 约2天完成

#### 模块 M6 — 本地壳程序（Rust）

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Prism | Tauri项目结构、main.rs/lib.rs入口、tauri.conf.json、capabilities权限声明 | 项目名/配置微调 |
| **直接复制** | Pot Desktop | src-tauri/src/下模块划分(hotkey.rs/screenshot.rs/clipboard.rs/tray.rs/config.rs/server.rs/window.rs) | 功能适配 |
| **直接复制** | 飞舟OCR | Rust HTTP Proxy实现(reqwest绕过CORS)、Per-provider配置隔离 | 引擎适配 |
| **直接复制** | 飞舟OCR | MNN推理桥接层(Rust FFI调用C++ MNN)、PP-OCRv6三档模型加载逻辑 | ONNX Runtime适配 |
| **参考重写** | Crow Translate | 全局键盘钩子机制(WinAPI RegisterHotKey) | Rust实现 |
| **参考重写** | STranslate | 离线模型下载/管理流程 | Rust实现 |

**预估**：复制60% + 参考重写30% + AI写10% = 约4周完成

#### 模块 M7 — 翻译引擎路由器

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **参考重写** | STranslate | 多引擎抽象接口设计(TranslationEngine trait)、19种引擎适配器接口规范、三级调度策略 | Rust重写(约400行) |
| **参考重写** | Pot Desktop | 20+翻译引擎HTTP API调用模式、统一参数签名、结果缓存策略 | Rust重写 |
| **参考重写** | Crow Translate | QOnlineTranslator统一引擎抽象层设计思路 | 设计思路参考 |
| **参考重写** | Translumo | 多引擎负载均衡、TranslatorFactory动态选择模式 | 设计思路参考 |
| **AI写** | — | — | 项目特定路由策略 |

**预估**：参考设计 + AI写 = 约2周完成（接口设计1:1迁移，Rust重写约400行）

#### 模块 M8 — 结果渲染引擎

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **参考设计** | STranslate | 悬浮窗翻译结果UI交互设计、设置页面布局 | React重写 |
| **参考设计** | Translumo | 实时翻译悬浮窗OverlayWindow交互设计 | React重写 |
| **AI写** | — | — | Design Tokens定义后批量生成CSS |

**预估**：参考设计 + AI写 = 约3天完成

#### 模块 M9 — 视频字幕模块

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **参考设计** | STranslate | 批量文件翻译处理流程 | YouTube/Netflix API适配 |
| **AI写** | — | — | 具体平台集成 |

**预估**：参考设计 + AI写 = 约4天完成

#### 模块 M10 — PDF翻译模块

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Prism | PDF.js文本层解析基础 | 排版保留逻辑 |
| **参考设计** | BabelDOC | PDF智能布局重建技术、表格/公式处理 | Rust/TS实现 |

**预估**：复制40% + 参考设计60% = 约5天完成

#### 模块 M11 — 术语库管理器

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **参考设计** | Pot Desktop | 术语库版本更新机制 | IndexedDB实现 |
| **AI写** | — | — | 匹配算法 |

**预估**：参考设计 + AI写 = 约3天完成

#### 模块 M12 — 设置与配置中心

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Pot Desktop | chrome.storage.sync管理、配置导入导出 | UI适配 |
| **AI写** | — | — | 快捷键配置文件(JSON格式)、项目特定配置项 |

**预估**：复制60% + AI写40% = 约3天完成

#### 模块 M13 — 历史记录服务（学习模块）

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **参考设计** | Pot Desktop | Anki导出工作流、生词保存流程 | SM-2算法核心实现 |
| **AI写** | — | — | 掌握度追踪、复习调度逻辑 |

**预估**：参考设计 + AI写 = 约4天完成（完全自研为主，这是项目独创功能）

#### 模块 M14 — 生词本服务（学习模块）

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **参考设计** | Pot Desktop | Anki导出流程 | 间隔重复算法核心 |
| **AI写** | — | — | 自动采集/过滤规则/掌握度管理 |

**预估**：参考设计 + AI写 = 约5天完成（完全自研为主）

#### 模块 M15 — 复习引擎（学习模块）

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **完全自研** | — | — | SM-2算法实现、掌握度衰减、复习队列管理 |

**预估**：完全自研 = 约5天完成（项目独创核心功能）

#### 模块 M16 — 导出服务（学习模块）

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **AI写** | — | — | 模式固定的格式转换代码(JSON->CSV、JSON->Anki) |
| **参考设计** | Pot Desktop | Anki导出工作流 | 具体实现 |

**预估**：AI写 = 约3天完成（模式固定，AI擅长）

#### 模块 M17 — 本地大模型引擎接口

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Prism | AI大模型接口对接(OpenAI/腾讯混元/Qwen)、流式输出实现、SQLite存储对话记录 | 适配本地服务 |
| **直接复制** | 飞舟OCR | Ollama/LM Studio本地大模型对接、OpenAI Compatible接口适配 | 项目集成 |

**预估**：复制80% + AI写20% = 约2周完成

#### 模块 M18 — AI对话界面

| 策略 | 来源 | 可复用内容 | 需重写内容 |
|------|------|-----------|-----------|
| **直接复制** | Prism | 对话式UI基础框架、流式输出 | 气泡样式适配 |
| **参考设计** | STranslate | 设置页面布局、多引擎并行翻译界面 | React重写 |
| **AI写** | — | — | Design Tokens定义后批量生成CSS/组件样式 |

**预估**：复制50% + 参考设计30% + AI写20% = 约3周完成

### 13.4 代码复用总表

| 模块 | 直接复制 | 参考重写 | 参考设计 | 完全自研/AI写 | 预估节省时间 |
|------|---------|---------|---------|--------------|-------------|
| M1 用户交互管理器 | Prism + Pot Desktop | — | — | AI写 | ~1周 |
| M2 DOM内容采集器 | STranslate | — | — | AI写 | ~2天 |
| M3 悬停翻译器 | STranslate | — | — | AI写 | ~2天 |
| M4 屏幕截图OCR | Prism | STranslate | — | AI写 | ~3天 |
| M5 Native Messaging桥 | Pot Desktop + 飞舟OCR | — | — | AI写 | ~1天 |
| M6 Rust壳程序 | Prism + Pot Desktop + 飞舟OCR | Crow + STranslate | — | AI写 | ~3-4周 |
| M7 翻译引擎路由器 | — | STranslate + Pot Desktop | Crow + Translumo | AI写 | ~1-2周 |
| M8 结果渲染引擎 | — | — | STranslate + Translumo | AI写 | ~2天 |
| M9 视频字幕 | — | — | STranslate | AI写 | ~3天 |
| M10 PDF翻译 | Prism | — | BabelDOC | AI写 | ~3天 |
| M11 术语库管理 | — | — | Pot Desktop | AI写 | ~2天 |
| M12 设置配置中心 | Pot Desktop | — | — | AI写 | ~2天 |
| M13 历史记录服务 | — | — | Pot Desktop | AI写 | ~3天 |
| M14 生词本服务 | — | — | Pot Desktop | AI写 | ~4天 |
| M15 复习引擎 | — | — | — | 完全自研 | 基准 |
| M16 导出服务 | — | — | Pot Desktop | AI写 | ~2天 |
| M17 本地大模型接口 | Prism + 飞舟OCR | — | — | AI写 | ~1-2周 |
| M18 AI对话界面 | Prism | — | STranslate | AI写 | ~2-3周 |

### 13.5 AI辅助开发工作流

#### 第一步：用 WorkBuddy 生成项目骨架文档

- 让 WorkBuddy 根据技术规格文档，生成每个文件夹的 README.md
- 生成 UI 设计规范文档（按钮/面板/弹窗的 CSS 变量和 HTML 原型）
- 生成快捷键配置 JSON 模板
- 生成测试用例清单

#### 第二步：用 Trae CN 写核心代码

- 打开 Trae CN，用 Builder 模式输入需求描述，让它生成 Rust 代码骨架
- 逐模块实现：Rust壳 -> OCR集成 -> 翻译路由 -> 本地大模型 -> AI对话界面 -> 学习模块
- 每写完一个模块，让 Trae CN 的 Chat 模式帮你 review 和补单测

#### 第三步：用 WorkBuddy 生成配套材料

- 让 WorkBuddy 根据 Trae CN 写好的代码，自动生成 API 文档
- 生成用户手册/使用说明
- 生成项目周报和进度报告

### 13.6 AI写代码质量保障

Karpathy 七步法（适用于所有AI生成代码）：

1. **上下文拉满**：把项目目录结构、接口定义、依赖关系完整喂给AI
2. **策略先行**：先让AI输出设计文档/接口定义，确认后再写实现代码
3. **获取初稿**：让AI生成代码初稿
4. **逐行审查**：逐行审查AI生成的代码，重点关注边界条件和错误处理
5. **测试验证**：编写单元测试验证核心逻辑
6. **提交**：通过审查后提交
7. **循环**：重复以上步骤

**关键提醒**：

- AI生成的代码表面完整，但可能包含细微逻辑错误，排查时间远超手写
- AI不了解项目上下文，会重新实现已有功能（实测：不喂上下文AI写1800行，喂了上下文只写400行）
- AI倾向于"新增"而非"复用"，导致代码重复率从3.3%飙升到7.1%
- **正确姿势**：不是"复制粘贴"，而是"AI写，你审"。AI是执行者，你是架构师和审查员

### 13.7 工具分工总结

| 工作类型 | 工具 | 适用场景 |
|---------|------|---------|
| **写代码** | Trae CN | 核心代码、算法实现、系统编程 |
| **写文档/设计** | WorkBuddy | 技术文档、README、UI设计规范、测试用例 |
| **造轮子（核心）** | 你自己 + Trae CN | 算法和架构决策你自己定 |
| **造轮子（重复）** | Trae CN Builder | UI组件CSS、格式转换代码、配置文件解析 |
| **代码审查** | 你自己 | 所有AI生成的代码必须逐行审查 |

### 13.8 预估总工期

| 策略 | 模块数 | 预估时间 | 说明 |
|------|--------|---------|------|
| 直接复制为主 | M1,M5,M17 | ~3周 | 技术栈匹配度高，改动小 |
| 复制+AI混合 | M2,M3,M4,M6,M8,M10,M12,M18 | ~8-10周 | 架构参考+AI填充 |
| AI写为主 | M7,M9,M11,M13,M14,M16 | ~5-6周 | 设计参考+AI实现 |
| 完全自研 | M15 | ~1周 | 独创核心功能 |
| **合计** | **18个模块** | **约18-20周** | **对比从零开发34周，节省约40-45%** |

---
## 十二、附录

### 12.1 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| Native Messaging | 原生消息传递 | Chrome/Edge官方IPC机制 |
| Content Script | 内容脚本 | 注入网页的扩展脚本 |
| Service Worker | 服务工作者 | 扩展后台脚本（Manifest V3） |
| Manifest V3 | 清单V3 | Chrome扩展最新规范 |
| OCR | 光学字符识别 | 将图片文字转为可编辑文本 |
| IPC | 进程间通信 | 不同进程间的通信机制 |
| DOM | 文档对象模型 | 网页的树形结构表示 |
| SPA | 单页应用 | 现代前端框架构建的应用 |
| MutationObserver | 变异观察者 | 监听DOM变化的API |
| PP-OCRv6 | PaddlePaddle OCR v6 | 百度飞桨第六版OCR引擎 |
| ONNX Runtime | 开放神经网络交换运行时 | 微软开源跨平台ML推理引擎 |
| Rust | Rust | Mozilla开发的系统级编程语言 |
| FFI | 外部函数接口 | 跨语言调用机制 |
| GIL | 全局解释器锁 | Python多线程限制 |
| DXGI | 直接图形交换接口 | Windows图形捕获API |
| Web Worker | Web工作线程 | 浏览器后台线程 |
| Design Token | 设计令牌 | 设计系统的可复用变量 |
| Shadow DOM | 阴影DOM | Web组件封装DOM/CSS |

### 12.2 参考资源

- Chrome Extension Manifest V3 文档
- Native Messaging 文档
- PP-OCRv6 官方文档（PaddlePaddle）
- ONNX Runtime Rust 文档
- Rust winapi crate 文档
- winit 窗口管理 crate 文档
- Edge Translator API 文档
- PDF.js 文档
- SiliconFlow API 文档

### 12.3 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-09-22 | 初始版本，完整开发计划 |
| v1.1 | 2026-09-22 | 补充学习模块（M13-M16）接口定义、数据流、目录结构、里程碑 |
| **v1.2** | **2026-09-22** | **架构切换：C++→Rust + PP-OCRv6 ONNX Runtime；新增快捷键自定义系统；新增现代UI设计规范** |
| **v1.4** | **2026-09-22** | **新增第十三章"开发策略：复制vs AI写"，含逐模块策略矩阵、参考项目清单、代码复用总表、AI辅助开发工作流、工具分工总结、预估工期**；新增M17本地大模型引擎接口（Ollama/LM Studio/text-generation-webui，支持Qwen/Llama/ChatGLM）；新增M18 AI对话界面（类ChatGPT多轮对话/引擎切换/文件上传/流式输出）；翻译引擎路由器升级（新增OpenAI GPT/Claude/Gemini/DeepL引擎及智能路由策略表）；新增Phase 7开发计划（第27-34周）；新增LocalLLMService/AIChatService接口定义；新增AI对话界面UI设计规范；更新项目目录结构** |
