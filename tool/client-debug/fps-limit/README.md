# BeiDou 60 FPS client

This directory builds the small Direct3D 8 frame limiter used only by
`clien/BeiDou-60FPS.exe`. The original `clien/BeiDou.exe` and the existing
skill compatibility DLL are not modified.

Build the DLL and generate the client copy from the repository root:

```bash
rtk bash tool/client-debug/fps-limit/build.sh
rtk python3 tool/scripts/patch-client/build_60fps_client.py
```

Keep these files in the same client directory:

```text
BeiDou-60FPS.exe
BeiDouFpsLimit.dll
DawnWarriorSkillCompat.dll
```

Start `BeiDou-60FPS.exe`. A successful installation writes this line to
`BeiDouFpsLimit.log`:

```text
OK: Direct3D 8 frame rate limited to 60 FPS
```
