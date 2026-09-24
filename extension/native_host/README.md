# WinOCR-Html Native Host

浏览器扩展的本地消息宿主，通过 Native Messaging 协议与 Chrome/Edge 浏览器通信。

## 安装步骤

### 1. 构建宿主程序

```bash
cd ..\..\native_host_rust
cargo build --release
```

### 2. 注册本地宿主

以管理员身份运行：

```
install_host.bat
```

### 3. 验证安装

**Chrome:**
1. 打开 `chrome://extensions`
2. 开启"开发者模式"
3. 加载解压的扩展（选择 `extension` 文件夹）
4. 点击扩展的"背景页"查看连接状态

**Edge:**
1. 打开 `edge://extensions`
2. 开启"开发者模式"
3. 加载解压的扩展（选择 `extension` 文件夹）
4. 点击扩展查看连接状态

## 卸载

以管理员身份运行：

```
uninstall_host.bat
```

## 手动注册表配置

如果自动安装失败，可以手动创建注册表项：

### Chrome

```
HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.winocr_host
    (Default) = C:\path\to\com.winocr_host.json
```

### Edge

```
HKEY_CURRENT_USER\Software\Microsoft\Edge\NativeMessagingHosts\com.winocr_host
    (Default) = C:\path\to\com.winocr_host.json
```

## Manifest 文件格式

`com.winocr_host.json` 必须包含：

```json
{
  "name": "com.winocr_host",
  "description": "WinOCR-Html Native Host",
  "path": "C:/path/to/winocr_host.exe",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://YOUR_EXTENSION_ID/"
  ]
}
```

**注意：**
- `path` 必须是**绝对路径**
- 路径使用**正斜杠 `/` 或双反斜杠 `\\`
- `allowed_origins` 中的扩展 ID 必须与 `manifest.json` 中的扩展 ID 匹配

## 通信协议

### 消息格式

```
4字节小端序长度前缀 + UTF-8 JSON 消息体
```

### 消息类型

| 类型 | 说明 |
|------|------|
| `init` | 初始化连接 |
| `translate` | 文本翻译 |
| `ocr` | OCR 识别 |
| `capture` | 触发截图 |
| `get_settings` | 获取配置 |
| `update_settings` | 更新配置 |
| `ping` | 心跳检测 |

### 响应类型

| 类型 | 说明 |
|------|------|
| `init_ack` | 初始化确认 |
| `translate` | 翻译结果 |
| `ocr` | OCR 结果 |
| `pong` | 心跳响应 |
| `version` | 版本信息 |
| `error` | 错误信息 |

## 故障排除

### 扩展无法连接宿主

1. 检查宿主可执行文件是否存在
2. 检查注册表路径是否正确
3. 检查 manifest.json 中的 `allowed_origins` 是否匹配扩展 ID
4. 以管理员身份重新运行安装脚本

### 宿主启动失败

1. 检查可执行文件是否损坏
2. 检查依赖库是否完整（MSVC Runtime）
3. 查看 Windows 事件查看器

### 通信异常

1. 重启浏览器
2. 重新加载扩展
3. 检查扩展背景页的控制台日志
