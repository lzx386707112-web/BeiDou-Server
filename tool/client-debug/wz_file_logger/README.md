# BeiDou Client Diagnostics

这是面向地图、Boss 和资源迁移问题的旧客户端诊断系统。它不会修改 WZ/IMG
节点，目标是让一次复现留下足够证据，替代逐资源猜测和反复制作 A/B 客户端。

## 能定位什么

- 客户端异常退出：异常码、故障地址、模块名、模块内偏移、崩溃前最后资源和
  minidump。
- 黑屏/卡死：窗口连续无响应、当时的 CPU、内存、句柄、GDI/USER 对象和
  hang dump；窗口仍响应时可按住 `Ctrl+F12` 手动抓取现场。
- 高负载：每秒记录一次性能状态；单核 CPU 持续超过阈值时生成一次
  high-cpu dump。
- 资源失败：IMG/WZ 打开失败、读取失败、慢读取、文件偏移和 Win32 错误码。
- 可疑节点：分析器用运行时文件偏移匹配本地 IMG 的 Canvas、Sound、Video、
  String 或数值节点。没有命中时会明确停留在文件级，不会给出猜测节点。

运行证据存放在：

```text
clien\diagnostics\session-<时间>-pid<进程>.log
clien\diagnostics\crash-<会话>.dmp
clien\diagnostics\hang-<会话>.dmp
clien\diagnostics\high-cpu-<会话>.dmp
clien\diagnostics\manual-<会话>.dmp
clien\diagnostics\flash-null-<会话>.dmp
clien\diagnostics\first-chance-cpp-<会话>.dmp
clien\diagnostics\error-dialog-<会话>.dmp
clien\diagnostics\exit-process-<会话>.dmp
```

每次客户端进程启动时会先清理旧的 `diagnostics` 目录，再创建本次会话的日志和
dump；因此该目录只保留最近一次启动产生的诊断数据。

## 构建与安装

在 macOS 仓库根目录执行：

```bash
rtk bash tool/client-debug/wz_file_logger/build.sh
rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh
rtk python3 tool/scripts/patch-client/patch_exe_wz_logger.py --dry-run
```

当前 `BeiDou.exe` 已加载统一的 `DawnWarriorSkillCompat.dll`，该 DLL 会继续加载
同目录的 `WzFileLogger.dll`，不需要占用第二个 EXE 代码洞。dry-run 应显示：

```text
BeiDou.exe loads DawnWarriorSkillCompat.dll; that runtime loads WzFileLogger.dll ...
```

如果客户端没有统一兼容 DLL，可在 32 位 Windows 环境构建并使用
`BeiDouLogLauncher.exe`：

```bat
cd /d Z:\path\to\BeiDou-Server\tool\client-debug\wz_file_logger
build_msvc.bat
BeiDouLogLauncher.exe ..\..\..\clien\BeiDou.exe
```

客户端是 32 位程序，DLL 和 launcher 必须使用 x86 工具链。

## 复现和分析

1. 正常启动 `clien\BeiDou.exe`。
2. 进入待排查地图或召唤 Boss；黑屏后按住 `Ctrl+F12` 约 2 秒，并至少保留
   进程 5 秒，让 watchdog 写完日志和 dump。直接崩溃不需要等待。
3. 退出客户端，在仓库根目录分析最新会话：

```bash
rtk python3 tool/client-debug/wz_file_logger/analyze_client_diagnostics.py
```

保存 Markdown 报告：

```bash
rtk python3 tool/client-debug/wz_file_logger/analyze_client_diagnostics.py \
  --output clien/diagnostics/latest-report.md
```

也可以把指定日志作为第一个参数传入。报告包含故障分类、性能峰值、最可疑资源、
可解析节点、关键时间线和 dump 路径。

## 配置

可将 `tool/client-debug/wz_file_logger/beidou_diagnostics.ini` 复制到 `clien` 后修改：

```ini
[diagnostics]
health_interval_ms=1000
hang_threshold_ms=5000
high_cpu_threshold=70
high_cpu_threshold_ms=3000
dump_on_hang=1
manual_dump_hotkey=1
log_first_chance_exceptions=1
; Successful mappings are noisy during startup; failures are always retained.
log_successful_mappings=0
```

`high_cpu_threshold` 是单核百分比，`100` 表示占满一个核心。高 CPU dump 每个
进程最多生成一次；设 `high_cpu_threshold_ms=0` 可禁用。崩溃 dump 始终保留。
成功的文件映射默认不记录，以避免在资源预加载热路径中执行路径解析和同步日志写入；
将 `log_successful_mappings` 设为 `1` 可临时恢复详细映射日志。
`log_first_chance_exceptions` 默认开启，最多记录 32 次访问冲突，并保留异常地址、模块偏移和
寄存器。前 4 次还会扫描异常栈开头的 32 个 DWORD，仅记录落在已加载模块可执行页内的地址
候选。游戏窗口出现后，额外捕获最多 32 次 MSVC C++ / `E_POINTER` 异常；前 8 次扫描 96 个
栈 DWORD。若异常出现在 Flash 空指针现场之后，会在第一次异常处生成 `first-chance-cpp` dump。
所有异常仍交给客户端原有异常链，不会被日志器吞掉。

日志器会在内存中保留最近 128 条键盘/鼠标/命令窗口消息、128 次 IMG/WZ 读取和 64 次文件
映射。正常运行时不逐条同步写盘；出现 Flash 空对象、C++/COM 现场、错误对话框或退出时，才以
`incident_ui_message`、`incident_resource_read`、`incident_mapping` 写入会话日志，同时记录
进程状态和完整模块表。这样可以把“点击技能栏 → 读取技能/文本/图标资源 → UI/COM 失败”放进
同一时间线，又不会恢复资源预加载阶段的大量同步日志 I/O。

错误框同时覆盖 `MessageBoxA/W`、`MessageBoxExA/W`、`MessageBoxIndirectA/W`、
`FatalAppExitA/W` 和 watchdog 窗口扫描；只要文本包含 `error code`、`E_POINTER` 或“无效指针”，
就会在用户关闭对话框前自动生成 `error-dialog` dump。

已确认的旧版 `WzFlashRenderer.dll` 会在 GR2D 回调仍注册、内部 movie/player 指针为空时，
从 `RenderFlash+0x45` 进入空指针读取。日志器仅对布局完全匹配的版本替换 GR2D 获取到的
`RenderFlash` 回调：movie 指针为空时跳过该帧并最多记录 8 次 `flash_render_guard`，正常状态
仍透传给原函数；第一次为空时立即生成 `flash-null` dump，并刷新上述 UI/资源/映射历史。
布局不匹配时不安装保护。

`EquipSlotDiagnostic.log`、`BeiDouSetItemCompat.log` 和 `DawnWarriorSkillCompat.log` 的重复
打开事件会被过滤；这些 DLL 自己写入的日志内容不受影响。发生 incident 时，日志器还会把
这些日志及其他已存在的兼容层日志自动复制进 `diagnostics`，用户无需额外寻找文件。

## Dump 深入分析

用 WinDbg 打开报告列出的 dump，先执行：

```text
!analyze -v
~* kb
lm
```

崩溃报告中的 `module + module_offset` 可与反汇编对应；hang/high-cpu dump 应重点
查看主线程和持续运行线程是否在 `ResMan.dll`、`NameSpace.dll`、`Gr2D_DX8.dll`
或某个兼容 DLL 内反复解析资源。

## 边界

旧客户端没有源码和原生节点日志接口。文件读取偏移覆盖资源 payload 时，分析器可
精确回溯节点；如果资源已被客户端缓存、故障发生在节点元数据解析阶段，证据只能到
IMG/WZ 文件和 dump 调用栈。日志中“最后资源”代表时间相关性，不单独证明因果，
应优先结合资源失败、重复高负载样本和 dump 栈共同判断。
