# WinOCR-Html 模型下载

## 快速下载

### 自动脚本（推荐）

1. **配置代理**（如需）：编辑 `download_models.bat`，取消注释并修改代理地址：
   ```bat
   set HTTP_PROXY=http://127.0.0.1:7890
   set HTTPS_PROXY=http://127.0.0.1:7890
   ```

2. **运行下载**：
   ```bash
   cd extension/native_host
   download_models.bat
   ```

3. **选择模型**：
   - `1` - tiny (6.6MB, 推荐, 速度快)
   - `2` - medium (133MB, 更准确)
   - `3` - 全部下载

### 手动下载

如果自动脚本失败，可手动下载：

1. 访问 HuggingFace 镜像：[https://hf-mirror.com/onnx-community/PaddleOCRv6](https://hf-mirror.com/onnx-community/PaddleOCRv6)

2. 下载以下文件到 `models/ocr/` 目录：

   | 模型 | 文件名 | 大小 |
   |------|--------|------|
   | 检测 (tiny) | `det_tiny.onnx` | 3.3 MB |
   | 识别 (tiny) | `rec_tiny.onnx` | 3.3 MB |
   | 检测 (medium) | `det_medium.onnx` | 66 MB |
   | 识别 (medium) | `rec_medium.onnx` | 67 MB |

3. 字典文件（必需）：
   - `ppocr_keys_v1.txt` (汉字字典)

## 代理配置

### 方式一：环境变量（推荐）

```powershell
# PowerShell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"

# CMD
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
```

### 方式二：修改配置文件

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

### 方式三：使用 HuggingFace 镜像

设置环境变量使用国内镜像：

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

## 模型来源

| 来源 | URL | 说明 |
|------|-----|------|
| HuggingFace 镜像 | https://hf-mirror.com | 国内推荐 |
| GitHub 镜像 | https://github.com.cnpmjs.org | 备选 |
| 官方源 | https://huggingface.co | 需要代理 |

## 验证安装

下载完成后，运行宿主程序检测模型：

```bash
cd native_host_rust
cargo run --release -- --standalone
```

如果模型加载成功，日志会显示：
```
模型加载成功: det_tiny.onnx (输入: 1, 输出: 1)
模型加载成功: rec_tiny.onnx (输入: 1, 输出: 1)
```
