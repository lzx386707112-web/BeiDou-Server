# BeiDou visual weather compatibility DLL

This project builds only the day/night and visual-weather modules from the
weather bundle. It does not include Kaentake's bypass, resolution, ResMan,
launcher, server combat effects, debuffs, nocturnal mobs, or the lamp preview
protocol. It also excludes the bundle's weather-footing module, so snow never
changes client movement physics.

The source is pinned to the verified v83 addresses for `BeiDou.exe` SHA-256
`06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18`.
The network route is cooperative: `BeiDouSetItemCompat.dll` owns
`CClientSocket::ProcessPacket` and exports `BDS_RegisterPacketHandler`; this DLL
registers opcode `0x373D` through that API instead of attaching a second detour.

Build from a Visual Studio developer PowerShell with CMake and Python available:

```powershell
.\build.ps1
```

The build is intentionally Windows-only because WzLib generates its COM headers
with `midl`. CMake fetches Detours and WzLib at the fixed commits recorded in
`CMakeLists.txt`. Rebuild `BeiDouSetItemCompat.dll` from its adjacent project as
well, because the weather packet registration export is part of this change.

Runtime files are `BeiDouWeatherCompat.dll`, the rebuilt
`BeiDouSetItemCompat.dll`, and the weather IMG files under `Data`. The HP/MP
wrapper loads the weather DLL after the verified compatibility core.
