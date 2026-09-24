# WinOCR-Html 模型说明

## 内置模型（无需下载）

安装包已内置 PP-OCRv6 tiny 模型集，安装后即可本地 OCR（中英文+数字），无需联网：

| 文件 | 大小 | 说明 |
|------|------|------|
| `models/ocr/det_tiny.onnx` | 1.8 MB | 文本检测 |
| `models/ocr/rec_tiny.onnx` | 4.5 MB | 文本识别 |
| `models/ocr/ppocr_dict.txt` | 27 KB | 识别字典（6904 字符） |
| `onnxruntime.dll` | 17.8 MB | ONNX Runtime 1.28.0 |

## 可选：medium 高精度模型（~60 MB）

如需更高精度，运行 `download_models.bat` 选择 `1`，将下载：

| 文件 | 说明 |
|------|------|
| `models/ocr/det_medium.onnx` | 检测（medium） |
| `models/ocr/rec_medium.onnx` | 识别（medium） |
| `models/ocr/ppocr_dict_medium.txt` | medium 专用字典（与 tiny 字典不同，必须配套） |

下载后在扩展设置中将 OCR tier 切换为 `medium`。

## 模型来源

https://hf-mirror.com/xberg-io/paddleocr-onnx-models （HuggingFace 国内镜像）

## 代理配置

如下载失败，编辑 `download_models.bat`，取消注释并修改：

```bat
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
```

## 手动下载

```bash
curl -L -o det_medium.onnx  https://hf-mirror.com/xberg-io/paddleocr-onnx-models/resolve/main/v6/det/medium/model.onnx
curl -L -o rec_medium.onnx  https://hf-mirror.com/xberg-io/paddleocr-onnx-models/resolve/main/v6/rec/medium/model.onnx
curl -L -o ppocr_dict_medium.txt https://hf-mirror.com/xberg-io/paddleocr-onnx-models/resolve/main/v6/rec/medium/dict.txt
```
