# WinOCR-Html 0.7.5

浏览器内 + 其他软件阅读的 OCR/翻译工具壳。**第一性设计：工具是从属表面，绝不违反阅读焦点。**

- 浏览器内 → 翻译四种触发 = 面板输入框 / 划词 / 右键菜单 / 快捷键；译文默认**原地替换原文**（点译文可切回原文）
- 面板形态可选：**工具栏弹窗**（任意内核）或**常驻右侧栏**（Edge/Chrome 116+）
- 三种翻译引擎：**SiliconFlow**（自带 key）/ **MyMemory**（免费免 key，国内可直连）/ 浏览器内置（需 138+，语言包国内拉不动）
- OCR 双引擎：**本地 PP-OCRv6**（离线 · 零 key · 实测 1.2–2.2s，**截图首选**）/ 云端 SF 视觉模型（慢，适合照片/手写/复杂版面）
- 任意软件/桌面 → 全局热键（默认 `Ctrl+Shift+M`，**可配置 + 占用时自动回退**）→ 原生截屏 → **本地 OCR** + 翻译 → 置顶浮窗
- 记录去重 → 日积累 Markdown → 多出口导出（文件夹 / ZIP / Obsidian / 乐享）

## 目录结构

```
WinOCR-Html0.3/
├── extension/              # MV3 浏览器扩展（浏览器内闭环，可直接加载）
│   ├── manifest.json                   # 当前生效 = 弹窗版（兼容旧内核；切侧栏见第一节）
│   ├── manifest.sidepanel.json         # 常驻侧栏版（Edge/Chrome 116+ 时改名覆盖 manifest.json）
│   ├── icons/icon128.png
│   ├── sidepanel.html / sidepanel.js   # 常驻侧栏中枢（翻译输入 + 结果 + OCR + 历史 + 导出）
│   ├── options.html / options.js       # 设置（免费模型下拉 / OCR 引擎 / SF key / 导出目标）
│   ├── js/content.js                   # 选区气泡 + 供侧栏读取选中
│   ├── background.js                   # 侧栏行为 + 快捷键 + 右键菜单 + NM 桥 + 本地 OCR 往返
│   └── js/common.js                    # 共享：存储/翻译/OCR/MD/导出
└── native_host/           # 原生宿主（外部截图 / 独立运行）
    ├── winocr_host.py                  # 热键 + 区域画框 + 截屏 + 浮窗 + NM + OCR 调度
    ├── pyenv.py                        # 解释器选址：挑一个真正装了本地 OCR 依赖的 Python
    ├── ocr_local.py                    # 本地 OCR：RapidOCR + PP-OCRv6（离线零 key）
    ├── models/ocr/v6_tiny/             # PP-OCRv6 det/rec + cls ONNX（共 6.6MB，随项目内置）
    ├── install_deps.py                 # 装本地 OCR 可选依赖（选解释器 + 装 + 复验）
    ├── install_deps.bat                # ← 上面那个的一键入口（双击即可）
    ├── requirements-ocr.txt            # 可选依赖清单（平台/ABI 绑定，故不 vendor）
    ├── winocr_config.json              # 独立模式配置（SF key / ocrEngine / hotkey 等）
    ├── run_host.bat                    # 独立模式启动器（pythonw 无窗常驻）
    ├── setup_host.py                   # 生成 launcher + 宿主清单（自动探测扩展 ID）
    ├── install_host.bat                # 注册脚本（调用 setup_host.py + 写注册表）
    ├── stop_host.bat                   # 一次结束所有宿主实例
    ├── winocr_launcher.bat             # ← setup_host.py 生成，勿手改
    ├── com.winocr.host.json            # ← setup_host.py 生成，勿手改
    ├── _test_nm.py                     # NM 协议 harness：不开浏览器也能验证宿主（见第一节末）
    └── _gen_bat.py                     # 四个 .bat 的唯一真源（纯 ASCII+CRLF）
```

## 一、加载浏览器扩展

`extension/` 里有两份 manifest，**同一时刻只有一个生效**（生效的那个必须叫 `manifest.json`）：

| 生效的 `manifest.json` | 面板形态 | 要求 |
|---|---|---|
| 默认（弹窗版，当前就是它） | 工具栏弹窗面板 | 任意 Chromium / Firefox（含 32 位 Chrome 109、Edge 92） |
| `manifest.sidepanel.json` 改名覆盖后 | **常驻右侧栏** | Edge / Chrome **116+** |

**A. 先让它跑起来（旧内核，默认已就绪）**
1. `edge://extensions` → 开启「开发人员模式」→「加载已解压的扩展」→ 选 `extension/` 目录。
2. 点扩展图标 → 弹出面板；页面选中文字 → 气泡「译」。
3. 设置页（扩展管理页里点「扩展选项」）选引擎：
   - **SiliconFlow**：填你自己的 key，点「测试所选引擎」（质量好，医疗术语佳）。
   - **MyMemory**：**不用填任何 key**，直接点「测试所选引擎」即可用（免费、国内可直连；匿名约 5000 字符/天，填邮箱可提到约 50000）。
   - **浏览器内置**：需内核 138+ 且语言包可下载（国内基本拉不动），一般不用选。

> **关于「MyMemory」**：免费翻译记忆库接口（`api.mymemory.translated.net`），**免 key、国内可直连、实测返回
> `Access-Control-Allow-Origin: *`**（浏览器可直接跨域调用）。质量中等，适合当「零 key 兜底」。
> 超长文本会自动按 450 字符切块后拼接；额度用尽时会明确提示并建议填邮箱提额。

> **关于「浏览器内置」引擎**：它走设备端 `Translator API`（需内核 **138+**）。
> `可用性 = downloadable` 表示**内核支持、但该语言包还没下载** —— 点选项页的 **「下载语言包」** 拉一次即可离线零 key 翻译；
> 语言包源在 Google（CDN），国内通常是**拉不动**的 —— 表现为"点了没反应"，45 秒后才会明确报超时；
> 那就继续用 SiliconFlow（功能完全不受影响）。
> 若选项页能读到 `Translator`，说明你的内核 ≥138，那么**侧栏版（116+）也早就能用了**（见 B）。

**B. 升级到 Edge/Chrome 116+ 后切「常驻右侧栏」**
1. 在 `extension/` 里：先把 `manifest.json` 备份成 `manifest.popup.bak`，再把 `manifest.sidepanel.json` 复制/改名为 `manifest.json`。
2. 回 `edge://extensions` 点「重新加载」。
3. 点扩展图标 → **右侧常驻侧栏**（切标签页不消失）；`Alt+Shift+W` 开侧栏、`Alt+Shift+Z` 翻译选中。
4. 想切回弹窗版：反向操作（把侧栏版另存，恢复 `manifest.popup.bak` 为 `manifest.json`）。

## 一-之二、怎么拿到 116+ 浏览器（国内可用地址）

**结论：用 Edge 最省事** —— Edge 连 32 位版本都还在出（153 有 32-bit），不像 Chrome 的 32 位停在 109。

| 途径 | 地址 / 操作 |
|---|---|
| 已在用 Edge | 打开 `edge://settings/help`，会自动检查更新（升到 **153** 即满足 116+） |
| Edge 官方在线下载 | https://www.microsoft.com/zh-cn/edge/download |
| **Edge 官方离线安装包（推荐，不挑网络）** | https://www.microsoft.com/zh-cn/edge/business/download → 选 **Stable → Windows 64-bit（或 32-bit）→ 简体中文 → 下载 .msi**（当前 153.0.4234.32）→ 双击安装 |
| Chrome 64 位（国内可能连不上） | https://dl.google.com/chrome/install/ChromeStandaloneSetup64.exe |

## 一-之三、翻译的四种触发方式 + 快捷键

| 触发 | 操作 | 结果去哪 |
|---|---|---|
| 面板输入框 | 面板输入/粘贴文本 → 点「翻译」（或 Ctrl+Enter） | 面板结果卡 + 自动记录 |
| 划词 | 页面选中文字 → 原位弹**常驻翻译栏**（原文 + 译文，可拖动） | 页面原位；**开栏即自动翻译**（不必再点「译」），点「→栏」送入面板 |
| 右键菜单 | 选中文字 → 右键「WinOCR：翻译选中」 | 原位弹常驻翻译栏（同时记录） |
| 快捷键 | 选中文字 → `Alt+Shift+Z` | 同上 |

**译文显示方式**（扩展选项 → 「译文显示」）
- `原地替换原文`（**默认**）：划词后点气泡「译」→ **译文直接替换页面原文**（淡蓝底 + 虚线下划线）；
  **点该段可在「译文 ↔ 原文」间切换**，气泡里的「还原」一次性恢复全部。
- `原位常驻翻译栏`：在原文位置显示「原文 + 译文」，**选中即自动翻译**，**拖动标题栏可移动**，
  只有点 × 才关闭，绝不自动消失；位置会自动避让屏幕下沿（划到页面最后几行也不会掉出视口）。
- `临时气泡`：滚动 / 点别处 / 取消选中即消失，最不打扰阅读。
- 切换后需**刷新网页**生效。

**快捷键**
- `Alt+Shift+W`：侧栏版=打开侧栏；弹窗版=打开面板。
- `Alt+Shift+Z`：翻译当前页面选中文字。
- 想改键：`edge://extensions/shortcuts`（或 `chrome://extensions/shortcuts`）。

> 浏览器内闭环**无需安装原生宿主**即可使用（面板 + 选区气泡 + 粘贴截图 OCR）。

## 一-之四、OCR 引擎与免费模型（含实测数据）

### 只用免费模型，并在扩展里随时切换
「扩展选项」里模型是**下拉选择**（不再手打，杜绝 `20012 Model does not exist` 那类错名）：

| 用途 | 可选（都是免费的） | 实测耗时 |
|---|---|---|
| 翻译 · 文本模型 | `Qwen/Qwen3-8B` | **2.5s** ← 推荐 |
| | `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` | 9.5–12.3s（推理模型，思考占 400+ 字，**慢 4 倍**） |
| OCR · 云端模型 | `PaddlePaddle/PaddleOCR-VL-1.5` | 103–121s（文字对，但有前导幻觉字符） |
| | `deepseek-ai/DeepSeek-OCR` | 0.9s(热)/30s(冷)，**输出不稳定**（会整段退化成无关文字） |
| OCR · **本地** | `PP-OCRv6 tiny`（随项目内置） | **1.2–2.2s**，置信度 0.98 ← **截图首选** |

> 实测条件：2026-09-20，同一张「英文医学句 + 中文句」截图，SiliconFlow 官方端点。

### 为什么 OCR 默认走本地
截图是**屏幕上的清晰文字**，正是传统「检测 + 识别」模型（PP-OCRv6）的主场；
云端 VL 模型是为照片/手写/复杂版面准备的，用在截图上既慢 60–80 倍、又更容易幻觉。
所以 `ocrEngine` 默认 `local`，**本地不可用时自动回落云端**（不会让你两手空空）。

### 本地 OCR 的开关与档位
- 选项页「OCR 引擎」：`本地 PP-OCRv6`（默认）/ `云端 SiliconFlow`。
- 选项页「本地 OCR 档位」：`tiny`（6.6MB，已内置）/ `medium`（**需自行放 133MB 模型**，更准更慢；
  缺模型时会自动回退 tiny，不会报错）。
- 依赖（可选，缺了只是本地 OCR 不可用，宿主照常跑）：
  ```
  pip install rapidocr onnxruntime numpy Pillow
  ```
- 模型来源：从 WinOCR 3.4 的 `models/v6_tiny` 复制而来（`PP-OCRv6_det_tiny.onnx`
  + `PP-OCRv6_rec_tiny.onnx` + `ch_ppocr_mobile_v2.0_cls_mobile.onnx`）。
- 浏览器内的图片 OCR（粘贴/拖拽/「测试 OCR」按钮）也会**经过原生宿主走本地引擎**，
  所以要先在选项里勾选「连接原生宿主」；没勾/没连上会自动回落云端。

### 不开浏览器验证宿主（复用工具）
```
python native_host/winocr_host.py --doctor   # 七段体检：解释器/依赖/模型/配置/注册/launcher/实例数
python native_host/install_deps.py --list    # 每个候选解释器各自缺什么
python native_host/install_deps.py --check   # 宿主会用的那个解释器，依赖齐不齐
python native_host/setup_host.py             # 生成清单 + 自动填扩展 ID
python native_host/_test_nm.py               # 用管道真跑一轮 settings/hello/ocr 往返
```
`_test_nm.py` 会像浏览器那样以管道拉起宿主，发一张自造的图并核对 OCR 结果与耗时 ——
改完宿主先跑它，比开浏览器试快得多。

`--doctor` 是**第 0 步**：它按真实因果顺序逐段检查（解释器 → 依赖 → 模型 → 配置文件 →
NM 注册 → launcher → 运行中进程数），而不是给一句结论。桌面截图不通时先跑它，
基本能直接看到是哪一段断了。

### 不开浏览器验证扩展（气泡竞态回归）
```
node tests/_test_bubble_race.js             # 重放「划词 → 常驻栏 → 点气泡按钮」的真实事件序列
node tests/_test_bubble_race.js <某份 content.js>   # 也可指定被测文件（做对照）
```
`_test_bubble_race.js` 用**最小 DOM 桩**（不是 jsdom，零依赖）复现 0.7.2 修掉的那条竞态：
点气泡按钮时 `mouseup` 冒泡到 document，会让 `onSelect` 再跑一遍、把正在翻译的气泡拆掉重建，
译文最终写进孤儿节点 → 「译文永远不显示 / 秒退」。输出全 **ASCII**，Windows 936 管道下不会乱码。
≥ 0.7.2 的 content.js 应 **11/11 PASS**。

## 二、安装原生宿主（启用「其他软件」截图）

仅在你需要「截浏览器外的桌面/PDF/Word」时才装。

1. 安装 Python 3（已装可跳过）。
2. 双击 `native_host/install_host.bat`（**不需要管理员**，只写 HKCU）。
   - 它会定位 python → 调用 `setup_host.py` 生成 `winocr_launcher.bat` 和 `com.winocr.host.json`
     → 再把清单路径写进 Edge + Chrome 的注册表。
   - **扩展 ID 全自动**：`setup_host.py` 直接扫描 Edge/Chrome 的 profile
     （`Secure Preferences`，按扩展目录路径匹配），把真实 32 位 ID 填进 `allowed_origins`，
     **不用再手改 JSON**。若确实没探测到，它会打印提示，可手动补：
     `python native_host/setup_host.py --id <你的扩展ID>`（可逗号分隔多个）。
   - 重跑永远安全：重载扩展后若 ID 变了（换目录/换浏览器），再跑一次即可。
3. 在扩展设置里填好 SiliconFlow key（外部截图走云端 OCR+翻译）。
4. **在扩展「选项」里勾选「连接原生宿主 com.winocr.host」并保存**（0.4.4 起默认关闭）。
5. 重新加载扩展（`edge://extensions` → 重新加载）。
6. 之后**不要手动启动宿主**：浏览器会在需要时自动拉起它。
   验证：扩展选项页点「检测宿主连接」→ 应显示 `已桥接扩展 · 生效热键 XXX · pid N`。
   按热键截一张图，记录若出现在扩展面板「最近记录」里，即联动成功。

> **报 `Specified native messaging host not found` 怎么办**：说明扩展在连接原生宿主，但它没注册/清单不合法。
> 先跑 `install_host.bat`（会顺带验证清单是合法 JSON 且 ID 已填）；
> **纯浏览器使用请在选项里保持该开关关闭**（0.4.4 起默认关闭，不会再报）。
> （只想桌面截图不装扩展的话，直接用第二节「二-之二、独立运行模式」即可。）

> 原生宿主**核心零第三方依赖**：截屏用 Win32 BitBlt + 内置 PNG 编码，浮窗用 tkinter。

### 关于依赖：什么随项目走，什么必须自己装

| 类别 | 例子 | 怎么来 | 为什么 |
|---|---|---|---|
| **模型**（纯数据） | `models/ocr/v6_tiny/*.onnx`（6.6 MB） | **已随项目**，无需下载 | 数据没有 ABI，跨平台跨版本通用 |
| **Python 包**（二进制 wheel） | `rapidocr` `onnxruntime` `numpy` `Pillow` | **要装进解释器**，见下 | 绑定 OS/架构 + Python ABI：cp311 的装不进 cp314，win_amd64 的用不了 arm64 |
| **tkinter** | 官方 Python 自带 | 装 Python 时勾上 `tcl/tk and IDLE` | pip 装不了 |

**必须装吗？不是必须。** 没装本地 OCR 也能跑 —— 宿主自动回落 SiliconFlow 云端 OCR
（那就需要 `sfKey`，实测 100s+/张）。**装了才快**：离线、零 key、约 1~2 秒。

**一键安装（推荐）**：

```
native_host\install_deps.bat            # 自动挑解释器 + 装缺失的 + 装完复验
native_host\install_deps.bat --mirror   # 国内网络慢时走清华 PyPI 镜像
native_host\install_deps.bat --check    # 只体检，不安装
native_host\install_deps.bat --list     # 列出这台机器每个解释器各自缺什么
```

脚本幂等（已满足就跳过）：它先算出**哪些解释器缺什么**，再挑一个合理的落点装进去，
装完必复验 —— 因为 pip 报成功 ≠ import 成功（缺 VC++ 运行库时 `onnxruntime`
会装上但导入失败，脚本会把这条也告诉你）。

> 依赖清单声明在 `native_host/requirements-ocr.txt`，但它**不该**被当成
> 「打开终端 `pip install -r` 一下」的常规路径：这些是**可选**依赖，不装也能用，
> 而装错解释器更是白装（这正是之前那次事故的成因）。
> 手动装可以，但先回答一个问题：**你装的那个 python，是不是宿主会用的那个？**
> 不确定就别装，跑 `install_deps.bat` —— 它替你把这个问题答了。

> 想确认现状：`python native_host/winocr_host.py --doctor`
> 会列出每个候选解释器缺哪些包，以及宿主最终会用哪一个。

## 二-之二、独立运行模式（脱离浏览器扩展）

如果你**不想装浏览器扩展**，只想在桌面用热键截图 OCR 翻译，用独立模式即可——宿主完全不依赖浏览器。

1. **填 key**：编辑 `native_host/winocr_config.json`，把 `sfKey` 填成你自己的 SiliconFlow key。

   > ⚠️ **这是和扩展完全独立的另一份配置。** 独立模式只读这个文件；扩展「选项」页保存的是浏览器里的设置。
   > 两边都填过才能两边都能用 —— **在扩展里连上宿主 ≠ 本地配置里有 key**，
   > 症状就是扩展里显示「已桥接」但桌面热键截图报 `Token is invalid`。
   > 想省事就用扩展选项页的 **「从本地配置导入」**：把这份文件里已生效的设置一键读回浏览器。

2. 双击 `native_host/run_host.bat`（或命令行 `python winocr_host.py --standalone`）。
   - 用 `pythonw` 无控制台窗口常驻后台，看不到黑框；启动时会弹两条提示，**明确告诉你当前是哪种模式**。
   - 启动器会挑一个装了 `rapidocr` / `onnxruntime` 的解释器；万一挑错，宿主会在 `import tkinter`
     **之前**用 `native_host/pyenv.py` 换一个合格的解释器重启自己 —— 不会静默降级成云端。
3. 按 `winocr_config.json` 里的 `hotkey`（默认 `Alt+Q`）→ 屏幕变暗 → 拖拽画框选区 →
   松开即截该区域并做 OCR + 翻译 → 置顶浮窗显示。
   - 按 `Esc` 取消本次截图；按 `quitHotkey`（默认 `Ctrl+Alt+Q`）关掉宿主。
4. 记录写入本地 `native_host/data/YYYY-MM-DD.md` + `data/assets/截图.png`，与扩展侧格式对齐，可直接拖进 Obsidian / 乐享。

### 桌面截图不工作？先跑这一条

```
python native_host/winocr_host.py --doctor
```

它按**真实因果顺序**逐段体检，而不是给一句结论：

| 段 | 查什么 | 出问题时你会看到 |
|---|---|---|
| 1 | 解释器 + 依赖（宿主需要 `tkinter` + 本地 OCR 四件套） | 每个候选解释器缺哪些包，以及宿主会选哪个 |
| 2 | 本地模型 `models/ocr/v6_*` | `available` / 缺哪个 onnx |
| 3 | **本地配置文件**（独立模式读的那份） | `sfKey: EMPTY` 还是 `set (51 chars…)` |
| 4 | NM 注册清单 | `allowed_origins` 是否已填真扩展 ID |
| 5 | `winocr_launcher.bat` 用的解释器 | 与第 1 段比对是否一致 |
| 6 | 正在运行的宿主进程数 | > 1 就说明有僵尸进程在抢全局热键 |

> **为什么要专门查解释器**：本地 OCR 依赖是*可选*的，往往只装在某个 Python 里；
> 而启动路径过去是 `where pythonw` 按 PATH 顺序盲选 —— 选到精简解释器时不仅本地 OCR 失效，
> 有些环境连 `tkinter` 都没有，进程在 import 处直接死掉，`pythonw` 又没有 stdout 可打印，
> 于是表现为「按了热键毫无反应」。`pyenv.py` 就是为了消灭这类静默失败。

> 独立模式与 NM 模式的差异：
> | 维度 | NM 模式（默认） | 独立模式（--standalone） |
> |---|---|---|
> | 是否需要浏览器扩展 | 需要（connectNative） | 不需要 |
> | 设置来源 | 扩展「扩展选项」自动同步 | 本地 winocr_config.json |
> | 记录落地 | chrome.storage（扩展历史） | 本地 Markdown + PNG |
> | 进程生命周期 | 浏览器断开即退出 | 常驻，手动关进程才退 |

两种模式都支持**区域画框截图**；NM 模式下若也已连扩展，记录会同时回传扩展历史。

## 二-之三、壳怎么启动（二选一，别混）

| 目标 | 用哪个 | 说明 |
|---|---|---|
| **先让本地 OCR 能用**（可选但强烈建议） | 双击 **`install_deps.bat`** | 装 `rapidocr onnxruntime numpy Pillow`。已装会跳过；重复跑无副作用 |
| **只要桌面截图**（不连扩展） | 双击 **`run_host.bat`** | 独立模式（`--standalone`）；记录写本地 `native_host/data/日期.md` |
| **要和扩展联动**（记录回传 + 热键从扩展改） | 先跑一次 **`install_host.bat`** 注册，然后**不要手动启动** | NM 模式；**由浏览器在需要时自动拉起**（`connectNative`） |
| **出问题时** | `python native_host\winocr_host.py --doctor` | 七段体检，直接指出断在哪一环 |
| **热键被僵尸进程占着** | 双击 **`stop_host.bat`** | 一次结束所有宿主实例 |

**联动的前提**：① 跑过 `install_host.bat`（注册 + 清单合法 + 扩展 ID 已自动填好）；
② 扩展**选项页勾选「连接原生宿主」并保存**；③ 重新加载扩展。
④ 验证：选项页「检测宿主连接」显示 `已桥接扩展 · 生效热键 XXX · pid N`。

⚠️ **别手动双击 `winocr_launcher.bat`** —— 它是给浏览器调用的（无控制台、靠浏览器提供的管道通信），
手动双击会启动一个"没有浏览器管道"的宿主，宿主会明确提示 `NM 模式但没有浏览器管道` 并写入 `data/host.log`。
自己测试桌面截图请用 `run_host.bat`。

**怎么确认"已经桥接联动"**（三处任选）：

1. **扩展选项页 → 「检测宿主连接」** → 显示 `已桥接扩展 · 生效热键 CTRL+ALT+M · pid 1234`
   （宿主启动后会自动发 `hello` 自报状态）。
2. **宿主启动提示**（自动区分模式）：
   - `独立模式：不连扩展，记录写本地 Markdown`
   - `NM 模式：已被浏览器扩展桥接（记录会回传扩展历史）`
   - ⚠️ 手动在命令行跑、却显示 `NM 模式但未由浏览器拉起` → **联动不可用**，桌面截图请改用 `run_host.bat`。
   提示去向：真控制台 → stderr；`run_host.bat`（pythonw 无控制台）→ **屏幕右下角小窗**；
   两种情况都同时写入 `native_host/data/host.log` 留痕。
3. 用宿主热键截一张图，看记录是否出现在**扩展面板的「最近记录」**里 —— 出现即联动成功。

### 热键（可配置 · 自由录入 · 冲突自动回退）

- **自由录入**：扩展**选项页 → 「截图热键」输入框**，点一下然后**直接按下想要的组合键**即可录进去
  （如 `Ctrl+Alt+M`、`Alt+Shift+F9`）；支持 Ctrl / Alt / Shift / Win + 字母 / 数字 / F1–F24；Esc/Backspace 清空。
  点「保存」后扩展把热键同步给原生宿主并**即时重新注册**（无需重启宿主）。
- 也可手改 `native_host/winocr_config.json` 的 `"hotkey"`（独立模式用户）。
- **冲突自动回退**：若该键被占用，宿主依次尝试 `ctrl+alt+m` → `ctrl+shift+f9` → `alt+shift+m` → `ctrl+alt+z`，
  并提示最终生效的键；全部失败才报错并指向配置项。
- ⚠️ **`Ctrl+Shift+M` 会与 WinOCR 3.4 的「蒙版翻译」冲突**（同一个键）→ 建议改用 `ctrl+alt+m`，或不要同时开。
- 提示去向：**控制台/独立模式**打印到 stderr（中文可读文本）；**NM 模式**发 toast。
- 扩展自身的快捷键（`Alt+Shift+W` / `Alt+Shift+Z`）**Chrome 不允许扩展修改**，需到 `edge://extensions/shortcuts` 手动改。

### 怎么关掉壳（退出宿主）

| 方式 | 说明 |
|---|---|
| **退出热键 `Ctrl+Alt+Q`**（默认，可改） | 一按就优雅退出：注销热键 → 关窗 → 进程结束。选项页「退出热键」可自由录入 |
| **双击 `stop_host.bat`** | 一次性结束**所有**宿主实例（含历史遗留的僵尸进程） |
| **浮窗内按 `Esc`** | 只**关掉那个浮窗**，不退出宿主 |
| **选区时按 `Esc`** | 只**取消这次截图**，不退出宿主 |

⚠️ **为什么退出键不能用裸 `Esc`**：全局注册裸 `Esc` 会**劫持整个系统的 Esc**（对话框、游戏、浏览器全都失效）。
`RegisterHotKey` 因此必须带修饰键 —— 想录裸键时设置页会直接拒绝并提示。

⚠️ **NM 模式下"退出"≈"断开"**：宿主是浏览器拉起的，下次扩展需要时会**自动重新拉起**。
想让它彻底不再出现，还要在扩展选项里**取消勾选「连接原生宿主」**。

### 单实例保护（避免"热键被旧进程占着"）

宿主**同时只允许一个**。启动时若发现已有实例，会等待约 1.5s（给旧实例退出时间），仍在则**拒绝启动**并写明：
```
已有 N 个 WinOCR 宿主在运行（pid …）—— 同时只允许一个宿主，否则全局热键会被先注册的那个独占。
请先双击 stop_host.bat 全部关掉，再启动一个
```
**为什么必须这样**（实测踩过）：全局热键是**先注册者独占**。反复启动累积了 6 个宿主进程后，
`alt+q` 被**最早那个（跑着旧代码）**的进程占着 —— 用户按 Alt+Q 唤醒的是旧进程，
于是"修好的 bug 又出现了"。进程识别靠**顶层窗口标题**（`WinOCR-Host`），
不用"杀掉所有 python.exe"，避免误伤 WinOCR 3.4 等其它 Python 程序。

另外两种"不该存在"的启动方式现在会被直接拒绝，不会再悄悄留下僵尸：
- **NM 模式但没有浏览器管道**（手动双击 `winocr_launcher.bat`）→ 提示并退出；
- 手动在命令行跑 `python winocr_host.py`（既非 `--standalone`，也没有管道）→ 提示并退出。

## 三、两条触发器，一个输出表面（无显式模式切换）

| 你在哪 | 动作 | 路径 |
|---|---|---|
| 浏览器内 | 选中文字 | 扩展气泡（纯浏览器，不经原生） |
| 浏览器内 | 截某区域 | 全局热键 → 原生截屏 |
| PDF / Word / 桌面 | 全局热键 | 原生截屏 → OCR → 浮窗 |

两者都汇聚到**同一个置顶浮窗**。你读在哪、按哪个键，工具自动判断上下文，永远不让你为「模式」分心。

## 四、导出

- **文件夹**（推荐）：`showDirectoryPicker` 直接写真实 `.md` + `assets/`，免解压，可直拖进 Obsidian / 乐享导入。
- **ZIP**：零依赖打包（MD + assets）单文件归档。
- **Obsidian**：需装免费社区插件 *Local REST API*，填 URL + Key。
- **乐享**：填端点 + Token 后启用（占位接口，按你乐享 API 调整）。

记录只存**相对路径与文本**，绝不把图片 base64 塞进 `chrome.storage`（避免 10MB 上限）。

## 五、已知限制 / 后续

- **常驻侧栏（`side_panel`）需 Edge/Chrome 116+**；更旧内核留在弹窗版即可（第一节 A）。
- Chrome 无「关闭侧栏」API，热键只能打开，关闭需点面板 ×。
- 浏览器内置翻译走设备端 `Translator API`（需内核 138+）：状态 `downloadable` 表示**语言包还没下载**，
  用选项页「下载语言包」拉一次即可（语言包源在 Google，国内可能失败）；不可用时自动回落 SF（需 key）。
  地址栏那个「文A」图标是**浏览器自己的整页翻译**入口，与设备端 Translator API 不是同一套东西。
- 译文默认「原地替换原文」（点译文可切回原文，气泡「还原」可恢复全部）；想改用浮层可在选项里切「常驻翻译栏 / 临时气泡」。
- **MyMemory 引擎有免费额度**（匿名约 5000 字符/天，填邮箱约 50000）；超限会明确报错，不是 bug。
- **宿主热键默认 `Ctrl+Shift+M` 与 WinOCR 3.4 蒙版翻译冲突** → 改 `winocr_config.json` 的 `hotkey`（如 `ctrl+alt+m`）。
- **浏览器内置引擎在国内实际不可用**（语言包在 Google CDN 上，拉不动）；请用 SiliconFlow / MyMemory。
- **重载扩展后若页面控制台报 `Extension context invalidated`**：属正常现象（旧页面里的旧脚本失效），**刷新网页即可**；0.4.6 起已做降级不会再抛未捕获异常。
- 原生宿主连接**默认关闭**；开启但未注册会报 `Specified native messaging host not found`（属预期）。
- **语言包下载不在页面里发生**（由浏览器组件更新器在浏览器进程内完成），所以选项页按 F12 的 Network 面板**看不到该请求**；
  查语言包状态请用 `chrome://on-device-translation-internals`（Edge 用 `edge://`）或 `chrome://components/`。
- **内置引擎没有"国内镜像"可用**：语言包是**浏览器内置组件**，由 Chrome 自带组件更新器按 `update.googleapis.com` 清单
  从 Google CDN（`dl.google.com` / `*.gvt1.com`）拉取，**地址硬编码、无用户可配置的镜像**，Google 也不提供第三方镜像。
  国内能镜像的只是"浏览器安装包 / 商店 CRX / npm 之类"，**没有人镜像浏览器内部模型组件**（清单签名 + 组件 ID 校验，对不上）。
  → 想用内置引擎，只能等有能访问 Google 的网络出口；否则请用 SiliconFlow（默认，功能不受影响）。
- 外部/独立截图依赖原生宿主；**本地 OCR 不需要 key/联网**，翻译才需要（SF key 或免 key 的 MyMemory）。
- **本地 OCR 依赖装在哪台解释器里，决定它能不能用**：这些是**可选**依赖，可能只装在
  某几个 Python 中。宿主启动时用 `native_host/pyenv.py` 自己找（必要时 `os.execv`
  换一个合格的解释器重启自己），所以正常情况无需干预；要确认现状跑
  `python native_host/winocr_host.py --doctor`，要补装跑 `install_deps.bat`。
- **本地 OCR tiny 档对极小字号可能掉个别字符**（实测合成图掉过 1 个字母，置信度仍 0.98）；
  要更准可放 medium 模型（133MB），或把 OCR 引擎切云端。
- 浏览器内的图片 OCR 走本地引擎时**必须已连接原生宿主**；未连接会自动回落云端（慢）。
- 区域画框截图已支持（热键 Ctrl+Shift+M → 画框）；多显示器仅主屏精确，副屏坐标需后续校准。
- v0.8 可补：术语自动抽取、批量后台 OCR、副屏坐标校准、截图区域存本地可选开关。

## 七、版本说明

- **0.7.6**（2026-09-21）
  - **DeepLX 引擎下线**：实测 DeepL 源站对本机出口 IP 返回 429 临时封禁，免代理无法稳定使用
    （不符合项目"零门槛国内直连"原则）。两个引擎开关（网页划词 `engine` / 截图 `translateEngine`）、
    选项页地址框、宿主 `deeplx_translate()` 全部移除；旧配置值自动回落 `sf`，`deeplxUrl` 废弃。
  - **截图翻译引擎开关补齐**：Alt+Q 截图 OCR 后的翻译与插件同一套开关 —— `sf`（默认）/
    `mymemory`（免 key 直连，450 字符切块 + 邮箱提额）/ `none`（仅 OCR）；
    选项页保存经 NM 即时同步宿主并落盘，独立模式读同一份 `winocr_config.json`。
  - **多实例并存**：取消单实例硬拦截，新增 `data/hosts.roster.json` 名册 + 文件锁选举，
    最旧存活实例当 leader 独占全局热键，退出后下一名 ≤1s 自动接管（注册重试 3s，杜绝交接窗口
    误退备选键）；**Ctrl+Alt+Q 精确逐个关闭**，`stop_host.bat` 仍一次全关。
  - **修 NM 断管后僵尸宿主不退**（`sys.exit` 只死读取线程、Tk 主循环继续占热键）→ 切主线程
    走完整退出路径。
  - **修截图永远纯黑导致 OCR 零结果**：本机 DWM/驱动组合下 GDI BitBlt 三种写法全截黑图，
    改用 PIL ImageGrab（DXGI Desktop Duplication）优先、BitBlt 兜底；框选后等 200ms 再抓。
  - **修空 OCR 文本泄漏翻译提示词**：框选区无文字时不再拿空串请求模型（Qwen 会把 system
    prompt 当原文回译成中文），改为明确提示重新框选。
  - 验证：新增 `tests/_test_multi_instance.py`（3 实例选举 + 模拟全局按键逐个关闭，两轮全过）、
    `tests/_diag_capture.py`（抓屏/OCR 端到端诊断）。

- **0.7.5**（2026-09-20）
  - **修「Alt+Q 截图后浮窗出来极慢」**：根因不是慢，是**本地 OCR 崩溃后回落云端**。
    rapidocr 2.x/3.x 的引擎返回 **`RapidOCROutput` dataclass（不可迭代）**，而 `ocr_local.recognize_image`
    在「检测不到文字」时（空白/无文字截图区）走 `result, _ = output` 兜底分支，对已不可迭代的
    dataclass 解包 → `cannot unpack non-iterable RapidOCROutput object` → 宿主捕获异常 →
    **回落云端 SiliconFlow（100s+）** → 浮窗才出来。
  - 修法（defense in depth）：
    - `recognize_image` 改为**统一按属性取** `txts/boxes/scores`（兼容新版 dataclass 与旧版元组），
      检测不到文字时**安全返回空串**（`("", 0.0)`），绝不崩；
    - `ocr_png` 在「本地引擎正常跑但没认出字」时**不再回落云端**（云端也认不出凭空出现的字，
      只会白白慢几十秒）；只有本地引擎**本身不可用**（缺依赖/模型）才回退。
  - 验证：空白图此前必崩 → 现返回 `("", 0.0)`；文字图在主线程/子线程各 3 次稳定识别（conf 0.96）；
    `_test_nm.py` **0 项失败**。

- **0.7.4**（2026-09-20）
  - **把「本地配置地址」直接写进面板**，不再让人去 README 里翻：
    - **选项页**：宿主区域显示绝对路径 `native_host\winocr_config.json`，并新增
      **「打开所在文件夹」**按钮（宿主用 `explorer /select` 在资源管理器里选中该文件，
      不会误关联成编辑器/浏览器）。
    - **侧栏面板**：顶部新增一行**原生宿主状态条**（`#hostLine`），已桥接时直接展示
      桌面热键、OCR 引擎，以及那份本地配置的绝对路径，并明确提示「桌面截图读这份，
      与本面板设置是两份文件」。
    - 路径不是写死的：宿主在 `hello` 与 `settings.current` 里都上报 `configPath`
      （= `native_host/winocr_config.json`），面板从 `native.status` 取，随时可改。
  - 验证：`_test_nm.py` **0 项失败**，hello 带 `configPath`；JS ×5 / manifest ×2 校验通过。

- **0.7.3**（2026-09-20）
  - **修「桌面截图 OCR 完全不通」**：报 `Token is invalid` + 本地 OCR 也不可用。
    不是配置填错，是**两个独立缺陷叠在一起**，而且报错把因果指反了：
    - **① 解释器选错（真根因）**：本地 OCR 依赖只装在部分解释器里，而 `run_host.bat`
      用 `where pythonw` **按 PATH 顺序盲选** —— 选中的精简解释器 `tkinter` 和 `rapidocr`
      **都没有**，本地 OCR 必然失效、只剩云端；云端又因没 key 报 `Token is invalid`。
      **报错和真实原因毫无关系**。新增 `native_host/pyenv.py`：枚举候选解释器
      （py launcher / 注册表 / PATH / 常见目录）、探测依赖、带缓存选址，并在
      `import tkinter` **之前**自举 —— 不合格就 `os.execv` 换合格解释器重启自己
      （NM 模式下文件描述符保留，不断开浏览器连接）；重启目标保持「有无控制台」属性，
      否则 `--doctor` 的输出会被 pythonw 吞掉。
    - **② 两份配置互不同步**：独立模式读 `native_host/winocr_config.json`，扩展读
      `chrome.storage` —— 在扩展里「连上了」只代表桥接通，**不代表本地有 key**。
      而扩展选项页存在**「填了 key 却没点保存」**：扩展随后把空 `sfKey` 全量推给宿主，
      宿主 `save_config()` 一落盘，本地**本来好好的 key 被抹掉**。
      修法：宿主 `merge_settings()` 对凭据类键（`sfKey` / `lexiangToken` / `obsidianKey`）
      **空值不覆盖非空旧值**；扩展选项页加**未保存改动提示**，「检测宿主连接」前先落盘。
  - **新增「从本地配置导入」**：宿主加 `settings.get` 消息，扩展选项页一键把
    `winocr_config.json` 里正在生效的设置（含 key）读回浏览器，不必手抄。
  - **新增 `--doctor` 体检**：解释器 → 本地依赖 → 本地模型 → 配置文件（key 是否为空）
    → NM 注册 → launcher 解释器 → 运行中宿主数，一条命令定位到底。
  - 本地 OCR 失败时的报错不再含糊：直接给**当前解释器路径 + 缺哪个包 + 该在哪装**。
  - `run_host.bat` 改为**生成时定格解释器**（`_gen_bat.py` 调 `pyenv.pick_best()` 注入），
    路径失效才回退 PATH；`.bat` 仍是纯 ASCII + CRLF。
  - **补齐依赖的「声明 + 一键装 + 装完自检」**（此前只有模型随项目，Python 包全靠用户猜）：
    新增 `native_host/requirements-ocr.txt`、`install_deps.py` / `install_deps.bat`
    （自动挑解释器 → 装缺失的 → **装完复验**，因为 pip 成功 ≠ import 成功：
    缺 VC++ 运行库时 `onnxruntime` 会装上但导入失败）、`install_deps.py --list`
    （列出每个解释器各缺什么）。幂等，已满足即跳过。
    **不 vendor 依赖包是有意的**：它们是平台 + ABI 绑定的二进制 wheel
    （cp311 的装不进 cp314），vendor 会同时带来体积膨胀、升级死锁与重复安装；
    随项目走的只有纯数据（`models/ocr/v6_tiny/`）。
  - 验证：`--doctor` 在裸解释器下自动切到合格解释器并全绿；`_test_nm.py` **0 项失败**
    （本地 OCR 经宿主 **2.55s**，识别出 `Urinalysis` / `nitrite` / `尿潴留`）。
- **0.7.2**（2026-09-20）
  - **修「原位常驻翻译栏」译文永远不显示 / 秒退**（真 bug，不是模型问题）。
    根因是一条**事件竞态**：气泡内的 `mousedown` 必须 `preventDefault()`（否则选区被清空，
    `inline` 模式取不到 range），代价是**点气泡按钮时页面选区依然存在** → 这次 `mouseup` 冒泡到
    `document` → `onSelect()` 又跑一遍 → 220ms 后 `showBubble()` 开头那句 `removeBubble()`
    **把正在翻译的气泡整块拆掉**并新建一个空的 → `await` 回来的译文最终写进**已脱离文档的节点**
    （孤儿）→ 永远看不见。视觉上就是「翻译中…」闪一下（≈220ms）然后什么都没有。
    修法两道：① `onSelect(e)` **忽略来自气泡内部的 mouseup**（顺带修掉"拖动常驻栏会被重置"）；
    ② **同一段文本复用同一气泡**，绝不拆掉重建；③ 写入前判 `b.isConnected`，杜绝孤儿写入。
  - **常驻翻译栏改为开栏即自动翻译**：以前"选中只给原文、要点一下才有译文"，
    对**翻译栏**这个形态本身就是设计缺陷 —— 那只是个照抄栏。现在划词即出译文，
    「译」按钮保留为手动重译；翻译栏位置还会**自动避让屏幕下沿**（划到页面末尾不再掉出视口）。
  - **新增零依赖回归测试 `tests/_test_bubble_race.js`**：用最小 DOM 桩重放
    「划词 → 常驻栏 → 点气泡按钮」的真实事件序列。实测对照：
    **0.7.1 线上代码 5/11（复现："译文区空" + "气泡被重建" + "译文丢失"），0.7.2 是 11/11 PASS**。
- **0.7.1**（2026-09-20）
  - **新增「退出宿主」方式**（一个宿主不该只能靠任务管理器结束）：
    - **退出热键 `Ctrl+Alt+Q`**（默认，选项页可自由录入，占用时自动回退 `ctrl+shift+q` → `alt+shift+q`）；
    - **`stop_host.bat`**：一次结束**所有**宿主实例；
    - **浮窗内 `Esc`** 关窗、**选区时 `Esc`** 取消截图（都不退出宿主）。
    - 明确不做"裸 Esc 退出"：全局注册裸 Esc 会**劫持全系统的 Esc**，设置页录裸键会被直接拒绝。
  - **单实例保护**（修一个真事故）：全局热键**先注册者独占**。实测累积了 **6 个**宿主进程后，
    `alt+q` 被最早那个（跑旧代码）占着 → 用户按 Alt+Q 唤醒的是旧进程，"修好的 bug 又出现"。
    现在启动时若已有实例，先等 ~1.5s 再判定，仍在则**拒绝启动并写明 pid**；
    进程识别用**顶层窗口标题**（`WinOCR-Host`），不误伤其它 Python 程序。
  - **新增 `find_running_hosts()` / `stop_running_hosts()` / `--stop`**；`hello` 增加 `quitHotkey`。
  - **僵尸根因也堵住了**：`NM 模式但无浏览器管道` 与"手动跑 `python winocr_host.py`"这两种
    无效启动方式，现在**提示正确用法后直接退出**（以前会永久挂着一个全局热键）。
  - 换热键时**截图键与退出键一起重新注册**（此前只重注册截图键，且因局部变量 bug 连注销都做不到）。
- **0.7.0**（2026-09-20）
  - **OCR 新增本地引擎（离线 · 零 key）**：`native_host/ocr_local.py` = RapidOCR + **PP-OCRv6 ONNX**，
    模型从 WinOCR 3.4 的 `models/v6_tiny` 复制（6.6MB 随项目内置）。
    实测 **1.2–2.2s、置信度 0.98**，而云端 `PaddleOCR-VL-1.5` 要 **103–121s**、
    `DeepSeek-OCR` **输出不稳定** → **默认 `ocrEngine='local'`，不可用时自动回落云端**。
  - **免费模型清单 + 下拉切换**：扩展选项里「文本模型 / 云端 OCR 模型」改为**下拉**
    （`Qwen/Qwen3-8B`、`deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` / `PaddlePaddle/PaddleOCR-VL-1.5`、
    `deepseek-ai/DeepSeek-OCR`），并新增「OCR 引擎（本地/云端）」「本地档位（tiny/medium）」；
    实测耗时表直接印在设置页，选之前就能看到代价。
  - **模型名不再"越设越错"**：`SF_MODEL_ALIASES` / `normalizeOcrModel()` 把历史简写
    （`PaddleOCR-VL-1.5`）自动纠正成全称 —— 这正是 `20012 Model does not exist` 的根因。
  - **浏览器内图片 OCR 也吃到本地速度**：新增 NM 往返 `{type:'ocr', id, dataUrl}` → `ocr.result`
    （`background.js` 带 id 关联 + 超时 + 断线时统一 reject）；宿主在多线程里处理，不堵 NM 读循环。
  - **SF 超时按用途区分**：翻译 60s、云端 OCR 240s —— 原来统一 30s，模型名对了也会
    `read operation timed out`（实测踩到）。
  - **修一个潜伏 bug**：`register_current()` 里给 `ACTIVE_HOTKEY` 赋值**没声明 global**
    （嵌套函数里赋值只写局部）→ 宿主上报的热键永远为空，且**切换热键时旧热键从不注销**。已修。
  - OCR 失败作为 `error` 字段回传扩展（塞进 `text` 会被当成识别结果）。
  - 启动时后台预热本地 OCR（首次识别不用等引擎建会话）；新增 `_test_nm.py`
    —— **不用开浏览器**就能用管道真跑一轮 NM 协议（本次 9/9 通过）。
  - 设置页新增 **「测试 OCR」** 按钮：现画一张中英文字图，按当前引擎实测并报耗时。
- **0.6.2**（2026-09-20）
  - **修 Native Messaging 注册链路的两个致命 bug**（此前宿主**永远连不上**）：
    1. 生成的 `com.winocr.host.json` **不是合法 JSON** —— 模板里已有引号，`install_host.bat`
       的 PowerShell `-replace` 又加了一对，变成 `"path": ""D:\...\x.bat""` → 浏览器拒绝加载清单；
    2. `allowed_origins` 里的 `<EXTENSION_ID>` **从来没被替换过**，只打印一句"请自行替换"。
  - **新增 `setup_host.py`**（唯一真源）：生成 `winocr_launcher.bat` + `com.winocr.host.json`，
    **自动扫描 Edge/Chrome 的 profile（`Secure Preferences`，按扩展目录路径匹配）填入真实扩展 ID**，
    写完自校验（合法 JSON + `path` 存在 + ID 已填）。可用 `--id <id>` 手动补、`--check` 干跑。
  - `install_host.bat` 重写：**彻底去掉 PowerShell**（改为调用 `setup_host.py`），只保留 `reg add`（HKCU）。
  - launcher 改用 **pythonw + `start /b`**：宿主常驻整个浏览器会话，否则会一直挂着一个黑色控制台窗口。
  - 宿主新增第 4 种模式识别：`NM 模式但没有浏览器管道（八成是手动双击了 winocr_launcher.bat）`，
    并在 NM 线程退出时写 `data/host.log` 说明原因（不再静默）。
  - 删除 `com.winocr.host.json.tmpl`（与 `setup_host.py` 重复、正是引号 bug 的来源）。
- **0.6.1**（2026-09-20）
  - **让"用的是哪种模式 / 是否已桥接扩展"变得可见**（此前极易混淆）：
    - 宿主启动即播报模式，三态分明：`独立模式：不连扩展…` / `NM 模式：已被浏览器扩展桥接…` /
      `NM 模式但未由浏览器拉起（联动不可用；桌面截图请用 run_host.bat）`。
    - **修复 pythonw 下提示凭空消失**：`run_host.bat` 用 pythonw 没有控制台，原来 stderr 全丢 →
      现在无控制台时弹**屏幕右下角小窗**，且所有提示都追加写入 `native_host/data/host.log`。
    - 宿主新增 `hello` 消息（模式 / 生效热键 / pid）自报状态；扩展后台记录之，`native.status` 一并返回；
      选项页「检测宿主连接」改为显示 **`已桥接扩展 · 生效热键 XXX · pid N`**。
  - README 新增「二-之三、壳怎么启动（二选一，别混）」含三种确认联动的方法。
- **0.6.0**（2026-09-20）
  - **新增「原地替换原文」译文形态**（并设为默认）：划词 → 气泡点「译」→ 译文**直接写回页面原位**；
    用 `Range.extractContents()` 保留原 DOM fragment，可**点译文在「译文 ↔ 原文」间切换**，气泡「还原」一次性恢复全部。
    译文带淡蓝底 + 虚线下划线以便辨识；气泡改为 transient（替换后自动收起）。选区 Range 在 `mouseup` 时即缓存，
    并给气泡加 `mousedown → preventDefault`，避免点按钮时页面选中被清空导致取不到 Range。
  - **面板「翻译」按钮放大**：整行全宽、高 44px、字号 14px（原 34px 小按钮）。
  - **截图热键支持自由录入**：选项页新增「截图热键」录制框 —— 点一下后**直接按组合键**即可录入
    （Ctrl/Alt/Shift/Win + 字母/数字/F1–F24），保存后经 NM 同步给宿主；宿主新增 `save_config()` 持久化到
    `winocr_config.json`，并用 `PostThreadMessageW(WM_APP+1)` 让热键线程**即时重注册**（无需重启宿主）。
  - `background.js` 的 `syncSettings` 改为**连接后补发一次**设置，确保刚开启宿主时热键也能送达。
- **0.5.1**（2026-09-20）
  - **DeepLX 引擎（已下线）**：0.5.1 曾加入自建 DeepLX 通道（免 key · `POST <地址>` body
    `{text, source_lang, target_lang}`，响应取 `data`，默认 `http://localhost:1188/translate`）。
    **2026-09-21 实测下线**：DeepL 源站对本机出口 IP 直接返回 `429 your IP has been blocked
    temporarily`，免代理无法稳定使用（前一天"返回 429 而非超时=可达可行"的判断不成立：
    可达≠可用，限流即不可用）。随后已从两个引擎开关、选项页、宿主中全部移除；
    旧配置里的 `deeplx` 值自动回落到 `sf`，`deeplxUrl` 配置项废弃。
  - **横向实测了另外两条"免 key"方案，结论是否掉的**（已写入选项页说明）：
    ① **有道** `fanyi.youdao.com/translate` → **302 跳网页 / `error.html`，不再返回 JSON（接口已失效）**；
    ② **Google** `translate.googleapis.com/translate_a/single` → **`http=000` 15s 超时（被墙）**。两者都不必考虑。
  - 宿主**热键可配置 + 冲突自动回退**：`winocr_config.json` 新增 `"hotkey"`（默认 `ctrl+shift+m`），
    被占用时自动尝试 4 个备选键；`notify()` 统一提示出口（控制台→stderr 可读文本，NM→toast），
    并在启动时告知最终生效的热键。**修掉"热键注册失败"只丢一句 JSON 到控制台、用户无从下手的问题。**
- **0.5.0**（2026-09-20）
  - **新增 MyMemory 引擎**（免费 · 免 key · 国内可直连）：`https://api.mymemory.translated.net/get`，
    实测返回 `Access-Control-Allow-Origin: *` → content script 可直连；后台转发通道也已兼容 GET。
  - 引擎下拉变为三项：`SiliconFlow`（自带 key，质量最好）/ `MyMemory`（零 key）/ `浏览器内置`（138+，语言包国内拉不动）。
  - 细节：语言代码映射（`zh→zh-CN`、`en→en-GB`、`ja→ja-JP`…；`auto→en-GB`）、响应 HTML 实体解码、
    **超长文本按 450 字符切块**（GET 有长度上限）并拼接、额度用尽/`quotaFinished`/`responseStatus≠200` 均有明确提示、
    `srcLang===tgtLang` 提前拦截。新增设置 `mymemoryEmail`（填了额度 5000→50000）与 `host_permissions` 白名单。
  - 原生宿主**不加** MyMemory：宿主入口是"截图→OCR"，OCR 必须用视觉模型（只有 SF 有），加文本引擎是死代码。
- **0.4.8**（2026-09-20）
  - 超时提示中补充**浏览器自带诊断页**指引：`chrome://on-device-translation-internals`
    （Edge 用 `edge://`）可查看语言包是否卡在 `Installing`、并可 Uninstall/重装 —— 用来判定"是网络问题还是扩展问题"。
  - 实测佐证：当该页显示 `en-zh  Installing` 时，说明**扩展已成功触发下载**，卡住的是模型源（Google CDN）→ 属网络问题。
- **0.4.7**（2026-09-20）
  - **「下载语言包」不再静默卡死**：语言包托管在 **Google 的 CDN**，国内网络到不了时
    `Translator.create()` 会长时间悬而不决、连 `downloadprogress` 都不触发（表现为"点了没反应"）。
    现改为：**每秒刷新「已等待 Ns（尚无进度事件）」+ 45 秒硬超时**，超时给出明确结论
    （模型源不可达 → 保持 SiliconFlow 即可），并区分「需用户手势被拒」等其他错误；下载中禁用按钮防重复点击。
  - 选项页引擎说明补上"国内会表现为无响应"的预期，避免误判为 bug。
- **0.4.6**（2026-09-20）
  - **修复 `Uncaught (in promise) Error: Extension context invalidated`**：
    这是**重新加载/更新扩展后**、已打开页面里残留的旧 content script 再调 `chrome.*` 时的必然报错
    （`content.js` 的 `loadMode()` 未写 `.catch()` → 变成未捕获 promise 异常）。
    **用户侧处置：刷新该网页即可**（新脚本会重新注入）。
  - 代码侧做**防御式降级**：新增 `extAlive()`（检测 `chrome.runtime.id`）；
    `getSettings/setSettings/getHistory/addRecord/clearHistory` 全部 try/catch + 读 `lastError`，
    上下文失效时**静默返回默认值/空值而非抛异常**；`content.js` 检测到失效会**自我撤销**
    （移除监听、不再弹栏）；`CAN_MSG` 与后台转发加存活判断。
- **0.4.5**（2026-09-20）
  - **澄清并支持「浏览器内置」引擎**：`availability = downloadable` 不是"不可用"，而是**内核已支持、语言包未下载**。
    新增选项页 **「下载语言包」** 按钮：在用户手势内调 `Translator.create()` 触发下载，带 `downloadprogress` 进度回显，
    成功后自动把引擎切到「浏览器内置」并提示保存。
  - 「测试所选引擎」按状态给出**可操作**的结论（`available` / `downloadable` / `downloading` / `unavailable`），
    不再笼统说"国内网络不可用"；`srcLang=auto` 时按 `en` 探测（Translator API 不接受 `auto`）。
  - README 说明：地址栏「文A」是浏览器**整页翻译**入口，与设备端 `Translator API` 不是同一套；
    能读到 `Translator` 即说明内核 ≥138，**侧栏版（116+）同时可用**。
- **0.4.4**（2026-09-20）
  - **修复控制台报 `Unchecked runtime.lastError: Specified native messaging host not found`**：
    此前 `background.js` 在**安装时自动** `connectNative` 且**每 2 秒无限重试**，未注册宿主就持续报错。
  - 改为**原生宿主连接默认关闭**（新增设置 `nativeHost`，默认 `false`，选项页有开关 + 「检测宿主连接」）：
    纯浏览器使用完全不触发该报错；需要「外部截图记录回传」时才开启。
  - 失败处理：`onDisconnect` 内**必读** `chrome.runtime.lastError`（抑制 Unchecked 日志）+ 引入代次号
    `nativeGen` 忽略陈旧 disconnect + **重试上限 3 次 / 5s 间隔**（不再无限刷屏）+ 状态经 `native.status` 上报。
- **0.4.3**（2026-09-20）
  - **面板重新布局 + 美化**（定调：工业实用）：
    - 设计令牌层（颜色/字阶/间距/圆角/阴影/动效时长全部 CSS 变量）+ **暗色模式**（`prefers-color-scheme` 覆盖语义令牌，组件代码不动）。
    - **自绘细滚动条**（面板与页面翻译栏统一：`::-webkit-scrollbar` + `scrollbar-width:thin`）。
    - 粘性页头（品牌 + 引擎徽标）、分节**错峰入场**（5 组 × 80ms，`prefers-reduced-motion` 下全关）、
      历史条目悬停左侧强调条、结果卡/空态/错误态/加载态/禁用态全覆盖、`Ctrl+Enter` 翻译、拖拽投放高亮。
    - 兼容性：不使用 `color-mix()`（旧内核不支持），已改为每主题的 `--accent-line` 令牌。
  - **修复「测试连接」误导**：此前它**写死调用 SiliconFlow**，即使下拉选「浏览器内置」也报"连接成功"。
    现改为**按所选引擎实测**（选 SF 才打 SF；选内置则检查本机 `Translator` API 是否就绪并如实报告），
    按钮更名「测试所选引擎」。
- **0.4.2**（2026-09-20）
  - **修复"译文一闪就没"**：页面译文默认改为**原位常驻翻译栏**——显示「原文 + 译文」，**拖动标题栏可移动**，
    **只有点 × 才关闭**，不再因滚动 / 点空白 / 取消选中而消失。
  - 新增设置 **「译文显示」**：`原位常驻翻译栏`（默认）/ `临时气泡`（旧行为）。切换后刷新页面生效。
  - `common.js` 增 `displayMode` 设置项；`content.js` 重写气泡为「标题栏 + 原文 + 译文」结构并支持拖动（全局单一监听，无泄漏）。
- **0.4.1**（2026-09-20）
  - **默认改回弹窗版**（`manifest.json`），因为用户浏览器仍 <116、侧栏版会加载失败；侧栏版存为 `manifest.sidepanel.json` 备用（第一节 B 一键切换）。
  - **弹窗版补齐热键反馈**：`Alt+Shift+Z` / 右键菜单翻译后，无侧栏时**就地弹页面气泡**显示译文（此前只写历史、界面无反应）。
  - `content.js` 支持 `winocr.showBubble`（后台推结果到页面气泡）。
  - README 增补「116+ 浏览器国内可用下载地址」（Edge 官方离线包，当前 153.0.4234.32）。
- **0.4.0**（2026-09-20）
  - **重新设计为常驻侧栏**（`side_panel`，需 116+）：点图标开右侧栏，切换标签页不消失。
  - **补齐翻译四种触发**：面板输入框 + 翻译按钮（此前面板无翻译入口 = "按翻译没反应"）、划词气泡、右键菜单、快捷键。
  - **新增快捷键**：`Alt+Shift+W` 开面板、`Alt+Shift+Z` 翻译当前选中。
  - 右键菜单 / 快捷键的翻译结果**推送面板**并记录（此前只写历史、界面无任何反馈）。
  - 新增 `tabs` 权限（记录来源 URL）。
- **0.3.1**（2026-09-20）
  - 翻译默认引擎改为 **SiliconFlow**（0.3.0 默认浏览器内置，在旧内核 / 国内网络下不可用，导致"翻译形同未实现"）。
  - 修复 **Qwen3 思考模式导致译文为空**：请求显式带 `enable_thinking:false`（硅基流动该参数默认 `true`，
    思考 token 会耗尽 `max_tokens` 使 `content` 为空）；若模型不支持该参数，自动去掉并重试一次。
  - 错误提示可读化（401 → 提示填 Key；429 限流；超时 60s 明确提示）；设置页新增「测试连接」按钮。
  - content script 直连失败（页面 CSP / 跨域）时，自动改由后台 Service Worker 转发 SiliconFlow 请求。
- **0.3.0** 首个可用骨架：选区气泡 + 截图 OCR + 日积累 MD + 四出口导出；原生宿主区域画框 + 独立运行。

## 八、界面设计定调（面板 · 0.4.3）

| 维度 | 决策 |
|---|---|
| **目的** | 阅读时顺手翻译/OCR/积累，面板需在高密度信息下保持清晰层级 |
| **调性** | **工业实用**（信息密度 + 发丝边框 + 等宽数字），不混搭其他方向 |
| **记忆点** | 自绘细滚动条 + 分节错峰入场 + 历史条目悬停左侧强调条 |
| **字体** | 中文优先栈 `PingFang SC / Microsoft YaHei UI / Segoe UI`；标签与时间用等宽 + `tabular-nums`。
**刻意不引外链字体**（Google Fonts 国内不可达，且扩展需离线自足）——这是对"展示字禁用清单"的有据偏离。 |
| **色彩** | 暖白主表面（非纯白）+ 单一强调色 `#1677ff`（延续项目既有色，非默认蓝）；暗色由语义令牌覆盖 |
| **动效** | 一次编排的入场序列（5 组 × 80ms）+ 160ms 微交互；全部在 `prefers-reduced-motion: reduce` 下关闭 |
| **可访问性** | 正文对比度 ≥4.5:1、`:focus-visible` 2px 描边、语义地标（`header`/`main`/`section`/唯一 `h1`）、8 种状态覆盖 |
| **有据偏离** | 按钮高度 32–34px（非 44px）：本面板为桌面鼠标场景、宽度仅 340–400px，44px 会显著压缩信息量 |
