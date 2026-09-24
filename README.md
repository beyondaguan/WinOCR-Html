# WinOCR-Html Rust 版

全场景 OCR 翻译系统 - 高性能 Rust 本地宿主 + Chrome/Edge 浏览器扩展

## 功能特性

- **本地 OCR**: PP-OCRv6 推理，支持 tiny/small/medium 三档
- **全局截图**: DXGI Desktop Duplication + GDI 回退
- **多引擎翻译**: SiliconFlow / MyMemory / Ollama / 浏览器内置
- **全局热键**: 自定义截图/退出热键
- **浮窗显示**: 置顶透明浮窗显示翻译结果
- **浏览器扩展**: Chrome/Edge MV3 扩展，支持侧边栏

## 快速开始

### 前置要求

- Rust 1.75+ (推荐使用 [rustup](https://rustup.rs/))
- Windows 10/11 (64-bit)
- Chrome 或 Edge 浏览器

### 构建

```bash
cd native_host_rust
cargo build --release
```

可执行文件位置：`target/release/winocr_host.exe`

### 运行

#### 独立模式（不依赖浏览器扩展）
```bash
winocr_host.exe --standalone
```
- `Ctrl+Shift+M`: 截图 OCR
- `Ctrl+Alt+Q`: 退出

#### Native Messaging 模式（与浏览器扩展通信）

1. 注册本地宿主（以管理员身份运行）：
```bash
cd ../extension/native_host
install_host.bat
```

2. 加载浏览器扩展：
   - Chrome: 打开 `chrome://extensions` → 开发者模式 → 加载已解压的扩展 → 选择 `extension` 文件夹
   - Edge: 打开 `edge://extensions` → 开发者模式 → 加载已解压的扩展 → 选择 `extension` 文件夹

3. 启动宿主：
```bash
winocr_host.exe
```

### 配置

首次运行会在 `native_host/` 目录下生成 `winocr_config.json`。

```json
{
  "sf_key": "你的SiliconFlow Key",
  "sf_url": "https://api.siliconflow.cn/v1",
  "sf_model": "Qwen/Qwen3-8B",
  "ocr_engine": "local",
  "local_ocr_tier": "tiny",
  "src_lang": "en",
  "tgt_lang": "zh",
  "translate_engine": "sf",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "",
  "hotkey": "ctrl+shift+m",
  "quit_hotkey": "ctrl+alt+q",
  "model_dir": "models/ocr"
}
```

## 性能指标

| 操作 | 耗时 | 说明 |
|------|------|------|
| 本地 OCR (tiny) | ~1.5s | 6.6MB 模型 |
| 本地 OCR (medium) | ~3-5s | 133MB 模型 |
| 截图 (GDI) | ~100ms | 1920x1080 |
| 截图 (DXGI) | ~50ms | Desktop Duplication |
| 翻译 (SiliconFlow) | ~2-5s | 取决于网络 |
| 翻译 (Ollama) | ~1-3s | 取决于硬件 |

## 磁盘空间

| 组件 | 大小 |
|------|------|
| Rust 可执行文件 | ~10 MB |
| PP-OCRv6 tiny 模型 | ~6.6 MB |
| PP-OCRv6 medium 模型 | ~133 MB |
| 浏览器扩展 | ~500 KB |
| **总计（推荐配置）** | **~15 MB** |

## 网络说明

| 服务 | 国内直连 | 备注 |
|------|----------|------|
| SiliconFlow | ✅ 是 | 推荐，质量好 |
| MyMemory | ✅ 是 | 免费兜底 |
| Ollama | ✅ 是 | 完全本地 |
| 浏览器内置 | ❌ 否 | Google CDN 不可达 |

### 代理配置（下载模型必需）

**方式一：环境变量**
```powershell
# PowerShell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"

# CMD
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
```

**方式二：HuggingFace 镜像**
```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

**方式三：配置文件**
编辑 `native_host/winocr_config.json`：
```json
{
  "proxy_url": "http://127.0.0.1:7890",
  "models": {
    "base_url": "https://hf-mirror.com",
    "proxy_enabled": true
  }
}
```

**推荐代理软件端口：**
| 软件 | 默认端口 |
|------|----------|
| Clash | 7890 |
| v2rayN | 10801 |
| Shadowsocks | 1080 |
| Surge | 6152 |

### 模型下载

```bash
cd extension/native_host
download_models.bat
```

详见 [MODELS.md](extension/native_host/MODELS.md)

## 项目结构

```
.
├── native_host_rust/          # Rust 本地宿主
│   ├── src/
│   │   ├── main.rs           # 入口 + 双模式
│   │   ├── config.rs         # 配置管理
│   │   ├── hotkey.rs        # 全局热键
│   │   ├── nm.rs           # Native Messaging
│   │   ├── ocr.rs          # OCR 推理
│   │   ├── screenshot.rs    # 截图
│   │   ├── translate.rs     # 翻译引擎
│   │   └── window.rs       # 浮窗显示
│   └── tests/               # 测试
├── extension/               # 浏览器扩展
│   ├── sidepanel.html       # 侧边栏
│   ├── options.html         # 设置页
│   └── native_host/         # NM 配置
└── README.md
```

## 测试

```bash
# 单元测试
cargo test --test test_nm_protocol

# 构建并运行集成测试
cargo build --release
cd tests
python test_nm.py ../target/release/winocr_host.exe
```

## 卸载

```bash
cd extension/native_host
uninstall_host.bat  # 以管理员身份运行
```

## 许可证

MIT
