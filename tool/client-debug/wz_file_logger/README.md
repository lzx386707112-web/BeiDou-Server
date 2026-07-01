# BeiDou WZ File Logger

This debug helper writes a resource access log to:

```text
clien\beidou_wz_access.log
```

The log is written as UTF-8 with BOM so Windows Notepad and common editors can
read Chinese text without mojibake.

The current recommended mode patches `clien\BeiDou.exe` so it loads
`WzFileLogger.dll` from the same folder at startup. It does not modify WZ/IMG
files.

## Direct EXE Patch

From macOS in the repo:

```bash
rtk python3 tool/scripts/patch-client/patch_exe_wz_logger.py --dry-run
rtk python3 tool/scripts/patch-client/patch_exe_wz_logger.py
rtk i686-w64-mingw32-g++ -shared -nostdlib -Wl,-e,_DllMain@12 -o clien/WzFileLogger.dll tool/client-debug/wz_file_logger/WzFileLogger.cpp -lkernel32 -luser32 -lgcc
```

The patch creates:

```text
clien\BeiDou.exe.bak-wz-logger
```

To restore the original EXE:

```bash
rtk python3 tool/scripts/patch-client/patch_exe_wz_logger.py --restore
```

After patching, run `BeiDou.exe` normally in the Windows VM. Reproduce the
popup, then open `clien\beidou_wz_access.log`.

## Optional Launcher Build

Open **x86 Native Tools Command Prompt for VS** in the Windows VM, then run:

```bat
cd /d Z:\path\to\BeiDou-Server\tool\client-debug\wz_file_logger
build_msvc.bat
```

`BeiDou.exe` is 32-bit, so the logger DLL and launcher must also be built as
32-bit. Do not use the x64 Developer Command Prompt.

## Optional Launcher Run

From the same folder:

```bat
BeiDouLogLauncher.exe ..\..\..\clien\BeiDou.exe
```

Then reproduce the client popup:

```text
不正确的游戏数据
请下载最新客户端。
```

After the popup appears, open:

```text
clien\beidou_wz_access.log
```

The important lines are usually the last `CreateFileA/W` entries before the
`MessageBoxA/W` line. Use those IMG/WZ paths as the next resource audit target.

## What It Logs

- `CreateFileA/W` calls for `.img`, `.wz`, or paths containing `\Data\`.
- `MessageBoxA/W` text, including the incorrect-game-data popup.
- The current thread id and timestamp for each line.

This logger intentionally avoids changing node names, adding WZ nodes, or
guessing resource compatibility. It only tells us what the client loaded before
the failure.
