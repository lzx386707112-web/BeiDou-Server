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
```

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
```

`high_cpu_threshold` 是单核百分比，`100` 表示占满一个核心。高 CPU dump 每个
进程最多生成一次；设 `high_cpu_threshold_ms=0` 可禁用。崩溃 dump 始终保留。

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
