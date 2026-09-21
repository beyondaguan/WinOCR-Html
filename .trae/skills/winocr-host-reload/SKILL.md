---
name: winocr-host-reload
description: WinOCR 原生宿主（native_host/winocr_host.py）改码后的编译、清场、重启与日志/名册闭环核对流程。用户要求重启宿主、热键没反应、截图/OCR/翻译异常排查或改了宿主代码后验证时使用。不用于纯扩展 JS/HTML 改动。
---

# WinOCR 宿主改码 → 重启闭环

修改 `native_host/winocr_host.py` 后，必须完成「编译 → 停旧 → 确认清空 → 启新 → 证据核对」全链路。
在运行中的宿主不会自动加载新代码，**只改文件不重启等于没改**；没有日志/进程证据就不要声称「已重启/已生效」。

## 关键事实（先读，避免重踩）

- 解释器固定为 `C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\`，GUI 用 `pythonw.exe`，跑脚本/编译用 `python.exe`（或该目录下 python.exe）。
- 宿主已支持**多实例并存**：全局热键（截图/退出）只由名册 `native_host/data/hosts.roster.json` 里最旧的存活实例（leader）持有；leader 退出后下一名 ≤1s 自动接管。Ctrl+Alt+Q 一次只关一个，`--stop` 全关。
- 抓屏走 PIL ImageGrab（DXGI），老式 BitBlt 在本机只能截到纯黑；OCR 引擎本身通常没问题，先怀疑截图。
- 独立模式（`--standalone`）记录写本地 Markdown；NM 模式由浏览器管道拉起，断管即整体退出。
- 宿主窗口标题含 `WinOCR-Host`；配置文件 `native_host/winocr_config.json`；日志 `native_host/data/host.log`。

## 标准流程

### 1. 编译校验（改完立刻做）

```powershell
python -m py_compile native_host\winocr_host.py
```

看到 `COMPILE_OK`（无输出即成功）再继续。扩展 JS 改动另跑 `node --check extension\js\common.js`、`node --check extension\options.js`。

### 2. 停止全部旧宿主并确认清空

```powershell
python winocr_host.py --stop
Start-Sleep -Seconds 1
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'python' -and $_.CommandLine -like '*winocr_host.py*' }
```

- `--stop` 在 `native_host` 目录下执行；正常会打印「已结束 pid=…」。
- 查询**必须同时**限定 Name 匹配 python 和 CommandLine 含 `winocr_host.py`：只匹配命令行会把执行查询的 PowerShell 自身算进去（假阳性）。
- 无输出 = 已清空。个别卡死窗口枚举不到的孤儿，用 `taskkill /PID <pid> /F` 补刀。

### 3. 拉起独立模式宿主

```powershell
$pyw = 'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe'
Start-Process -FilePath $pyw -ArgumentList 'winocr_host.py','--standalone' `
  -WorkingDirectory 'd:\AI\WinOCR-Html0.3\native_host' -WindowStyle Hidden
Start-Sleep -Seconds 6
```

注意 WorkingDirectory 必须是 native_host（配置/模型/日志都是相对路径）。浏览器不会在 8 秒内自动拉起休眠的 Service Worker，需要 NM 模式时让用户去扩展页点「重新加载」。

### 4. 证据核对（三项缺一不可）

```powershell
# a) 进程存活，拿 pid
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'python' -and $_.CommandLine -like '*winocr_host.py*' } |
  ForEach-Object { "pid=" + $_.ProcessId }
# b) 名册：自己是唯一/最旧条目
Get-Content native_host\data\hosts.roster.json
# c) 日志尾部：预热完成 + 「已成为 leader：持有热键 …/ 退出键 …」
Get-Content native_host\data\host.log -Tail 8
```

日志必须出现：`已成为 leader：持有热键 alt+q / 退出键 ctrl+alt+q`。
若退成了备选键（如 ctrl+alt+m / ctrl+shift+q），说明交接窗口或外部占用，用户按 Ctrl+Alt+Q 将无人响应——查是否有未清的旧实例。

## 现成验证脚本（改对应模块时直接跑，不要另写）

| 脚本 | 验证什么 |
|---|---|
| `tests\_test_nm_disconnect.py` | NM 管道断开后整个进程退出（不是只死读取线程） |
| `tests\_test_multi_instance.py` | 3 实例选举、Ctrl+Alt+Q 精确逐个关闭、名册清空、零残留；会真实模拟全局按键 |
| `tests\_diag_capture.py` | 截图像素体检 + OCR 端到端；截图全黑=抓屏问题，图正常但 0 字=OCR 问题 |

用固定解释器执行：
`& 'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe' tests\_diag_capture.py`

诊断脚本落盘的截图可能含患者信息，验证完立即删除 `data\_diag_*`。

## 配置变更要点

- 新增配置项要同时改三处：`default_config()`、扩展 `DEFAULT_SETTINGS`（common.js）、选项页 options.html/options.js。
- 扩展保存设置会经 NM 推给宿主并 `save_config()` 落盘；独立模式只读文件，手改后需重启宿主。
- 翻译引擎开关是 `translateEngine`（sf/mymemory/none），与网页划词的 `engine` 是两个独立开关。
  DeepLX 已下线（DeepL 源站对国内 IP 429 限流、免代理不可用），旧值 deeplx 会被自动归一化成 sf。

## 结束时的状态义务

- 向用户汇报必须带具体 pid、日志关键行、验证脚本输出；不要凭推断说「应该可以了」。
- 收尾时桌面应保留一个健康的独立模式宿主（除非用户另有要求）。
