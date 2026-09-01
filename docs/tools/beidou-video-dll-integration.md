# BeiDouVideo.dll 与 BeiDou.exe 对接说明

> 文档基线：2026-09-01，仓库提交 `2173036bf4`。
> 适用对象：当前仓库中的 32 位 `BeiDou.exe`、Direct3D 8 客户端和 MCV 播放器。
> 本文说明的是当前仓库已经落地的调用链，不是通用 MapleStory 客户端地址表。

## 1. 结论

`BeiDou.exe` 不直接导入或直接调用 `BeiDouVideo.dll`。正式运行链路是：

```text
BeiDou.exe
  └─ 入口点 0x00A63FF3 跳到代码洞 0x00AEFA20
       └─ LoadLibraryA("DawnWarriorSkillCompat.dll")
            ├─ 拦截 Gr2D_DX8.dll 对 Direct3DCreate8 的动态查询
            ├─ 捕获真实 IDirect3D8 / IDirect3DDevice8
            ├─ LoadLibraryA("BeiDouVideo.dll")
            ├─ GetProcAddress 取得 BDV_* C ABI
            ├─ BDV_AttachDevice(real IDirect3DDevice8*)
            ├─ 技能或场景触发时 BDV_PlayFile / BDV_PlayFileEx
            └─ FIELD_EFFECT 标记 draw 时 BDV_Render
                 └─ BeiDouVideo.dll 解码、上传纹理并在当前 D3D8 scene 中绘制
```

因此，对接分成三个完全不同的层次：

1. EXE 只负责在启动时加载统一兼容 DLL；
2. `DawnWarriorSkillCompat.dll` 是游戏、D3D8 和播放器之间的适配层；
3. `BeiDouVideo.dll` 是独立播放器，只通过稳定的 `__stdcall` C API 接收设备、播放路径和渲染调用。

不能把 `BeiDouVideo.dll` 填进 EXE 入口代码洞直接播放。EXE 入口阶段还没有真实 D3D8 设备，也不处于可安全绘制的 scene。

## 2. 当前版本基线和已知版本偏差

当前仓库运行文件：

| 文件 | SHA-256 | 说明 |
| --- | --- | --- |
| `clien/BeiDou.exe` | `06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18` | 已安装兼容 DLL loader |
| `clien/DawnWarriorSkillCompat.dll` | `3882737456d7c95795b2afe63ad91703cd70ef299c6b83fefe5f6f70764b466f` | 当前客户端成品适配层 |
| `clien/BeiDouVideo.dll` | `0ab46df3c19b5bd4ead054903e1dfd5b5d3b08dc6d425a13f67bf7cb2d6047a1` | 当前 32 位播放器 |

必须注意一个交付风险：

- 当前 `DawnWarriorSkillCompat.cpp` 的日志版本字符串仍是 v43；
- 当前成品 DLL 的字符串和最近运行日志显示 `LOAD ... v69`、`hooks installed v67`；
- 成品 DLL 还包含若干当前源码映射表中没有的后续技能映射。

因此，本文件中的代码用于说明和继续开发当前调用设计；它不能证明从仓库现有 C++ 源码重编译出的 DLL 与现网成品逐字节、逐功能相同。给别人交付时应优先分发上表已经验证的成品。若要重编译兼容 DLL，必须先补齐或找回与 v69/v67 成品对应的源代码，再重新审计和测试。

`BeiDouVideo.dll` 的 API、双通道和当前导出表与仓库播放器源码一致。

## 3. 地址类型约定

本文使用三个地址概念：

| 名称 | 含义 | 计算方式 |
| --- | --- | --- |
| VA | 进程中的虚拟地址 | 当前 EXE 为固定值，例如 `0x00A63FF3` |
| RVA | 相对于模块基址的偏移 | `RVA = VA - moduleBase` |
| 文件偏移 | PE 文件内的位置 | 只有当前 EXE 的相关段恰好满足脚本中的换算，不能对任意 PE 直接套用 |

当前 `BeiDou.exe`：

- PE32 / x86 / Windows GUI；
- ImageBase：`0x00400000`；
- 重定位表已剥离，当前实现要求它实际加载在 `0x00400000`；
- AddressOfEntryPoint RVA：`0x00663FF3`；
- 入口点 VA：`0x00A63FF3`。

`Gr2D_DX8.dll`、`DawnWarriorSkillCompat.dll` 和 `BeiDouVideo.dll` 的运行基址不能写死。代码应使用模块句柄作为基址，再加模块 RVA。2026-08-28 的一次日志中，`Gr2D_DX8.dll` 恰好加载在 `0x50400000`、`BeiDouVideo.dll` 恰好加载在 `0x709A0000`；这只是一次运行证据，不是 ABI。

## 4. EXE 启动加载器

### 4.1 固定地址

加载器生成脚本：

```text
tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py
```

| 项目 | VA | RVA/文件位置 | 说明 |
| --- | ---: | ---: | --- |
| EXE ImageBase | `0x00400000` | `0` | 固定基址 |
| 原入口点 | `0x00A63FF3` | `0x00663FF3` | 改成 `jmp cave` |
| 入口返回点 | `0x00A63FF8` | `0x00663FF8` | 重放 5 字节后返回 |
| 代码洞 | `0x00AEFA20` | `0x006EFA20` | 预留 `0x80` 字节 |
| DLL 名字符串 | `0x00AEFA68` | `0x006EFA68` | `cave + 0x48` |
| `LoadLibraryA` IAT 槽 | `0x00AF00C0` | `0x006F00C0` | 间接调用 Kernel32 |

原入口前五字节必须为：

```text
55 8B EC 6A FF
```

已打补丁的入口前五字节为：

```text
E9 28 BA 08 00        ; jmp 0x00AEFA20
```

### 4.2 代码洞逻辑

脚本生成的等价汇编：

```asm
; VA 0x00AEFA20
pushfd
pushad
push 0x00AEFA68                 ; "DawnWarriorSkillCompat.dll"
call dword ptr [0x00AF00C0]     ; LoadLibraryA IAT
popad
popfd

; 重放被入口 JMP 覆盖的原始指令
push ebp                         ; 55
mov  ebp, esp                    ; 8B EC
push -1                          ; 6A FF
jmp  0x00A63FF8
```

对应 Python 核心代码：

```python
IMAGE_BASE = 0x00400000
ENTRY_VA = 0x00A63FF3
ENTRY_ORIGINAL = bytes.fromhex("55 8B EC 6A FF")
ENTRY_RETURN_VA = ENTRY_VA + len(ENTRY_ORIGINAL)

CAVE_VA = 0x00AEFA20
CAVE_SIZE = 0x80
DLL_NAME_OFFSET = 0x48
DLL_NAME = b"DawnWarriorSkillCompat.dll\x00"
LOAD_LIBRARY_A_IAT = 0x00AF00C0

code = bytearray()
code += b"\x9C\x60"                           # pushfd; pushad
code += b"\x68" + struct.pack("<I", CAVE_VA + DLL_NAME_OFFSET)
code += b"\xFF\x15" + struct.pack("<I", LOAD_LIBRARY_A_IAT)
code += b"\x61\x9D"                           # popad; popfd
code += ENTRY_ORIGINAL
code += jump(CAVE_VA + len(code), ENTRY_RETURN_VA)
```

该 loader 有三项保护：检查 DLL 文件存在、检查入口原字节、检查代码洞仍为空。写入前还会保留 `BeiDou.exe.bak-dawn-warrior-skill-dll-loader`。不要跳过这些检查手工覆盖另一版 EXE。

### 4.3 安装检查

```bash
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py --dry-run
```

当前 EXE 应输出：

```text
BeiDou.exe already loads DawnWarriorSkillCompat.dll
```

## 5. 兼容 DLL 初始化

`DawnWarriorSkillCompat.dll` 的 `DllMain(DLL_PROCESS_ATTACH)` 不在 loader lock 内执行完整挂钩，而是：

```cpp
extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        DeleteFileA("DawnWarriorSkillCompat.log");
        InstallLoadLibraryHook();
        HANDLE thread = CreateThread(nullptr, 0, InstallHooks, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
```

安装线程首先确认主模块基址确实是 `0x00400000`，再逐个比较挂钩点原始字节。任意原字节不匹配都拒绝安装，而不是把未知 EXE 打坏。

与视频触发最直接相关的 EXE 挂钩点是：

| 作用 | VA | RVA | 当前源码要求的原字节 |
| --- | ---: | ---: | --- |
| 键盘主动技能分发 | `0x0094F89E` | `0x0054F89E` | `8B 4E 01 8B C1 BF 10 27 00 00` |
| `DoActiveSkill` 自定义分发 | `0x009678F9` | `0x005678F9` | `81 FE 07 04 00 00` |
| 高 ID 视觉分支 | `0x00934617` | `0x00534617` | `81 FE 7E 9A 98 00 0F 8C 59 12 00 00` |

下面四个 Brandish 兼容点用于把特定旧端不认识的技能送进已验证的原生动作、偏移、状态和 hit 分支。它们不是 `BeiDouVideo.dll` API 的组成部分，但当前技能触发链依赖统一兼容 DLL 同时维护这些原生契约：

| 作用 | VA | RVA |
| --- | ---: | ---: |
| action type | `0x00950DE5` | `0x00550DE5` |
| visual offset | `0x0095255A` | `0x0055255A` |
| state switch | `0x00967A10` | `0x00567A10` |
| hit | `0x0078E9D6` | `0x0038E9D6` |

这些 VA 只适用于当前目标 EXE。换 EXE 后必须重新反汇编、重新记录原始字节和返回地址。

## 6. 捕获真实 D3D8 设备

### 6.1 为什么不放置 d3d8.dll 代理

正式手机路径不替换系统/Wine/DXVK 的 `d3d8.dll`。本项目早期桌面代理只保留作实验；在 Winlator/Mobox 根目录放置代理 `d3d8.dll` 会干扰 `Gr2D_DX8.dll` 初始化。

当前方案是在真实 `Gr2D_DX8.dll` 内部拦截 `GetProcAddress("Direct3DCreate8")`。

### 6.2 LoadLibraryA 链

兼容 DLL先替换 EXE 的 `LoadLibraryA` IAT 槽 `0x00AF00C0`，用于观察 `Gr2D_DX8.dll` 何时加载：

```cpp
constexpr uintptr_t kLoadLibraryAIat = 0x00AF00C0;

HMODULE WINAPI HookLoadLibraryA(LPCSTR name) {
    HMODULE module = gRealLoadLibraryA(name);
    HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
    if (module != nullptr && module == gr2D) {
        InstallGr2DHook(module);
    }
    return module;
}
```

诊断 DLL 也可能挂钩 `LoadLibraryA`。所以兼容 DLL 在诊断器加载后会再次链入，避免早期拦截被覆盖。

### 6.3 Gr2D 的 GetProcAddress IAT

```cpp
constexpr uintptr_t kGr2DGetProcAddressIatRva = 0x0002D024;

bool InstallGr2DHook(HMODULE module) {
    auto** slot = reinterpret_cast<void**>(
        reinterpret_cast<uintptr_t>(module) + kGr2DGetProcAddressIatRva);
    // 将 *slot 替换为 HookGetProcAddress，并保存原函数
}
```

这里的 `0x0002D024` 是 `Gr2D_DX8.dll` 的 RVA，不是绝对地址。正确计算是：

```text
slot = runtimeBaseOf(Gr2D_DX8.dll) + 0x0002D024
```

若以某次日志的 `0x50400000` 为例，那个会话中的槽地址是 `0x5042D024`；下次运行不能照抄这个绝对值。

### 6.4 Direct3DCreate8 → CreateDevice

```cpp
FARPROC WINAPI HookGetProcAddress(HMODULE module, LPCSTR name) {
    FARPROC address = gRealGetProcAddress(module, name);
    if (reinterpret_cast<uintptr_t>(name) > 0xFFFF &&
        Equals(name, "Direct3DCreate8")) {
        gRealDirect3DCreate8 = ToFunction<Direct3DCreate8Fn>(address);
        if (gRealDirect3DCreate8 != nullptr) {
            return ToFarProc(&HookDirect3DCreate8);
        }
    }
    return address;
}

IDirect3D8* WINAPI HookDirect3DCreate8(UINT sdkVersion) {
    IDirect3D8* d3d = gRealDirect3DCreate8(sdkVersion);
    if (d3d != nullptr) {
        void** vtable = *reinterpret_cast<void***>(d3d);
        PatchPointer(&vtable[15], &HookCreateDevice, &originalCreateDevice);
    }
    return d3d;
}
```

`IDirect3D8::CreateDevice` 成功返回真实 `IDirect3DDevice8*` 后，兼容 DLL 安装设备 vtable hook，并立即调用播放器：

```cpp
if (LoadVideoModule() && gAttachDevice(*output)) {
    gVideoDeviceAttached = true;
}
```

`BDV_AttachDevice` 会为两个播放器通道分别保存同一真实设备并各自 `AddRef()`。调用方仍拥有原来的设备引用。

### 6.5 D3D8 vtable 索引

| 接口方法 | 索引 | 用途 |
| --- | ---: | --- |
| `IDirect3D8::CreateDevice` | `15` | 取得真实设备 |
| `IDirect3DDevice8::Present` | `15` | 帧边界、状态轮询和无 marker 兜底 |
| `IDirect3DDevice8::SetTexture` | `61` | 识别 stage 0 的标记纹理 |
| `DrawPrimitive` | `70` | marker draw 入口之一 |
| `DrawIndexedPrimitive` | `71` | marker draw 入口之一 |
| `DrawPrimitiveUP` | `72` | marker draw 入口之一 |
| `DrawIndexedPrimitiveUP` | `73` | marker draw 入口之一 |

这些索引来自标准 D3D8 COM 接口布局；仍须保证目标确实是 `IDirect3D8/IDirect3DDevice8`，不能把未知 COM 对象 vtable 按这些索引改写。

## 7. BeiDouVideo.dll ABI

公共头文件：

```text
tool/client-video/BeiDouVideoApi.h
```

构建时使用 `--kill-at`，所以 PE 导出名称是未修饰的 `BDV_AttachDevice`，不是调用方需要手写的 `_BDV_AttachDevice@4`。调用约定仍然是 x86 `__stdcall`。

### 7.1 数据类型

```cpp
#include <stdint.h>

#define BDV_CALL __stdcall

struct BdvStatus {
    uint32_t structureSize;
    uint32_t state;
    uint32_t width;
    uint32_t height;
    uint32_t frameCount;
    uint32_t decodedFrames;
    uint32_t displayedFrames;
    uint32_t droppedFrames;
    uint64_t durationMilliseconds;
    uint64_t positionMilliseconds;
};

enum BdvState : uint32_t {
    BDV_STATE_IDLE = 0,
    BDV_STATE_DECODING = 1,
    BDV_STATE_PLAYING = 2,
    BDV_STATE_FINISHED = 3,
    BDV_STATE_ERROR = 4,
};

enum BdvChannel : uint32_t {
    BDV_CHANNEL_PLAYER_SKILL = 0,
    BDV_CHANNEL_BOSS_SCENE = 1,
    BDV_CHANNEL_COUNT = 2,
};
```

调用 `GetStatus` 前必须清零结构并设置：

```cpp
BdvStatus status = {};
status.structureSize = sizeof(status);
```

当前播放器接受 `structureSize >= sizeof(BdvStatus)`，用于阻止旧的短结构发生越界写入。

### 7.2 13 个导出函数

| 导出 | 原型 | 语义 |
| --- | --- | --- |
| `BDV_AttachDevice` | `int(void*)` | 给两个通道附加真实 `IDirect3DDevice8*`，成功返回 1 |
| `BDV_GetAttachedDevice` | `void*()` | 返回 player 通道当前设备的借用指针，不额外 AddRef |
| `BDV_DetachDevice` | `void()` | 两个通道释放纹理和设备引用 |
| `BDV_PlayFile` | `int(const char*)` | 在 player-skill 通道播放；同通道旧播放先停止 |
| `BDV_PlayFileEx` | `int(uint32_t,const char*)` | 指定通道播放 |
| `BDV_Stop` | `void()` | 停止 player-skill 通道 |
| `BDV_StopChannel` | `void(uint32_t)` | 停止指定通道 |
| `BDV_Render` | `void()` | 兼容入口；当前实现等价于 `BDV_RenderAll()` |
| `BDV_RenderAll` | `void()` | 先画 boss-scene，再画 player-skill |
| `BDV_GetStatus` | `int(BdvStatus*)` | 查询 player-skill 通道 |
| `BDV_GetStatusEx` | `int(uint32_t,BdvStatus*)` | 查询指定通道 |
| `BDV_GetLastError` | `void(char*,uint32_t)` | player-skill 最近错误 |
| `BDV_GetLastErrorEx` | `void(uint32_t,char*,uint32_t)` | 指定通道最近错误 |

旧接口默认操作 `player-skill` 通道。`BDV_Render()` 是例外：为了让旧调用方同时支持场景视频，当前实现会画两个通道。

当前成品导出 RVA 仅供核对 PE，不应作为调用 ABI：

| 导出 | RVA |
| --- | ---: |
| `BDV_AttachDevice` | `0x00005120` |
| `BDV_DetachDevice` | `0x00005400` |
| `BDV_GetAttachedDevice` | `0x000053C0` |
| `BDV_GetLastError` | `0x000057C0` |
| `BDV_GetLastErrorEx` | `0x00005870` |
| `BDV_GetStatus` | `0x000057A0` |
| `BDV_GetStatusEx` | `0x00005600` |
| `BDV_PlayFile` | `0x000054C0` |
| `BDV_PlayFileEx` | `0x000054F0` |
| `BDV_Render` | `0x00005580` |
| `BDV_RenderAll` | `0x000055C0` |
| `BDV_Stop` | `0x00005530` |
| `BDV_StopChannel` | `0x00005550` |

这些 RVA 会随编译器、优化和代码修改变化。正式代码必须用 `GetProcAddress` 按名称获取函数。

## 8. 推荐的 API 加载代码

下面是可以交给其他项目使用的最小动态加载器。它不依赖 C++ import library，也不会把某次编译的导出 RVA 写死。

```cpp
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "BeiDouVideoApi.h"

struct BdvApi {
    HMODULE module = nullptr;
    int  (__stdcall* AttachDevice)(void*) = nullptr;
    void* (__stdcall* GetAttachedDevice)() = nullptr;
    void (__stdcall* DetachDevice)() = nullptr;
    int  (__stdcall* PlayFile)(const char*) = nullptr;
    int  (__stdcall* PlayFileEx)(uint32_t, const char*) = nullptr;
    void (__stdcall* Stop)() = nullptr;
    void (__stdcall* StopChannel)(uint32_t) = nullptr;
    void (__stdcall* RenderAll)() = nullptr;
    int  (__stdcall* GetStatusEx)(uint32_t, BdvStatus*) = nullptr;
    void (__stdcall* GetLastErrorEx)(uint32_t, char*, uint32_t) = nullptr;
};

template <typename T>
static T LoadProc(HMODULE module, const char* name) {
    FARPROC raw = GetProcAddress(module, name);
    T value = nullptr;
    static_assert(sizeof(value) == sizeof(raw), "unexpected x86 function pointer size");
    memcpy(&value, &raw, sizeof(value));
    return value;
}

static bool LoadBdvApi(BdvApi* api) {
    if (api == nullptr) return false;
    api->module = LoadLibraryA("BeiDouVideo.dll");
    if (api->module == nullptr) return false;

    api->AttachDevice = LoadProc<decltype(api->AttachDevice)>(api->module, "BDV_AttachDevice");
    api->GetAttachedDevice = LoadProc<decltype(api->GetAttachedDevice)>(api->module, "BDV_GetAttachedDevice");
    api->DetachDevice = LoadProc<decltype(api->DetachDevice)>(api->module, "BDV_DetachDevice");
    api->PlayFile = LoadProc<decltype(api->PlayFile)>(api->module, "BDV_PlayFile");
    api->PlayFileEx = LoadProc<decltype(api->PlayFileEx)>(api->module, "BDV_PlayFileEx");
    api->Stop = LoadProc<decltype(api->Stop)>(api->module, "BDV_Stop");
    api->StopChannel = LoadProc<decltype(api->StopChannel)>(api->module, "BDV_StopChannel");
    api->RenderAll = LoadProc<decltype(api->RenderAll)>(api->module, "BDV_RenderAll");
    api->GetStatusEx = LoadProc<decltype(api->GetStatusEx)>(api->module, "BDV_GetStatusEx");
    api->GetLastErrorEx = LoadProc<decltype(api->GetLastErrorEx)>(api->module, "BDV_GetLastErrorEx");

    return api->AttachDevice && api->GetAttachedDevice && api->DetachDevice &&
        api->PlayFile && api->PlayFileEx && api->Stop && api->StopChannel &&
        api->RenderAll && api->GetStatusEx && api->GetLastErrorEx;
}
```

典型调用顺序：

```cpp
BdvApi bdv;
if (!LoadBdvApi(&bdv)) {
    // 记录 GetLastError；不要阻止普通游戏启动
    return;
}

if (!bdv.AttachDevice(realD3D8Device)) {
    return;
}

if (!bdv.PlayFile("Data\\Video\\my-skill.mcv")) {
    char error[256] = {};
    bdv.GetLastErrorEx(BDV_CHANNEL_PLAYER_SKILL, error, sizeof(error));
    return;
}

// 必须在游戏的 D3D8 渲染线程和有效 BeginScene/EndScene 区间调用
bdv.RenderAll();

BdvStatus status = {};
status.structureSize = sizeof(status);
if (bdv.GetStatusEx(BDV_CHANNEL_PLAYER_SKILL, &status)) {
    if (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR) {
        // 清除调用方自己的 playing 标志
    }
}

// 退出或设备失效时
bdv.StopChannel(BDV_CHANNEL_PLAYER_SKILL);
bdv.StopChannel(BDV_CHANNEL_BOSS_SCENE);
bdv.DetachDevice();
FreeLibrary(bdv.module);
```

### 调用线程约束

- `BDV_PlayFile*` 可以建立后台解码任务，但当前游戏适配层从已验证的客户端调用点发起；
- `BDV_Render*` 必须在拥有真实 D3D8 device 的渲染线程、有效 scene 内调用；
- 不要从解码线程、服务端网络线程或任意新建线程调用 D3D8 draw；
- D3D8 设备 Reset、窗口/分辨率切换前后，应先停止播放并重新执行设备附加；当前播放器没有完整的 Reset 回调协议；
- `BDV_GetAttachedDevice()` 返回借用指针，调用方若要跨作用域持有，必须自行 `AddRef()`，并在结束后配对 `Release()`。

## 9. 技能触发到播放

### 9.1 ActiveSkill hook

当前主动技能分发 hook 在 `0x009678F9` 读取 `ESI` 中的技能 ID。命中视频技能时保存通用寄存器和标志，调用 C 函数，然后回到对应旧端原生攻击分支。

简化后的等价逻辑：

```asm
; ESI = skillId
pushfd
pushad
push esi
call _StartVideoSkill       ; 某些容易受攻击状态切换影响的分支改用 _QueueVideoSkill
add  esp, 4
popad
popfd
jmp  native_attack_branch
```

雷电冲击等分支会先调用 `QueueVideoSkill(skillId)`，再在下一个真实 `Present` 中 `InterlockedExchange` 取出并调用 `StartVideoSkill`。这样可以避开原生构造器正在修改攻击状态的窗口。

### 9.2 ID 到 MCV 的映射

映射位于兼容 DLL，不在 `BeiDouVideo.dll` 内：

```cpp
struct VideoSkillMapping {
    int skillId;
    const char* path;
    const char* successMessage;
};

constexpr VideoSkillMapping kVideoSkills[] = {
    {11121005, "Data\\Video\\galaxy-star-burst.mcv", "VIDEO OK: Galaxy Star Burst started"},
    {11121006, "Data\\Video\\eclipse-force.mcv", "VIDEO OK: Eclipse Force started"},
    {11121008, "Data\\Video\\soul-eclipse.mcv", "VIDEO OK: Soul Eclipse started"},
    // 其余职业同样按 skillId -> 普通磁盘路径映射
};

void StartVideoSkill(int skillId) {
    const VideoSkillMapping* mapping = FindMapping(skillId);
    if (mapping == nullptr || !LoadVideoModule()) return;

    if (!gPlayFile(mapping->path)) {
        char error[256] = {};
        gVideoGetLastError(error, sizeof(error));
        LogLine(error);
        return;
    }
    gVideoPlaying = true;
}
```

MCV 路径是相对于游戏当前工作目录的普通文件路径。它不通过 WZ/IMG 资源管理器读取，也不能打成 `Video.wz`。

### 9.3 场景通道

Boss/场景视频使用：

```cpp
gPlayFileEx(BDV_CHANNEL_BOSS_SCENE, "Data\\Video\\karing-dark-pulse.mcv");
```

当前仓库还有一层可选链：

```text
DawnWarriorSkillCompat.dll 加载 WzFileLogger.dll
  └─ 诊断 watchdog 确认窗口与 BeiDouVideo.dll 已存在
       └─ LoadLibraryA("KaringSceneCompat.dll")
            └─ BDV_GetAttachedDevice + BDV_PlayFileEx + BDV_RenderAll
```

`KaringSceneCompat.dll` 不重新创建设备，而是从播放器取得已有设备，随后在现有 vtable hook 后继续链入。集成者如果只需要技能视频，不需要部署这个可选场景模块。

## 10. FIELD_EFFECT 标记与实际绘制

### 10.1 player-skill 标记

服务端向施法者发送一个 FIELD_EFFECT。对应 `Map/Effect.img` 节点只有一张 `7x5` Canvas，不包含真正的视频帧。

前四个 ARGB 像素签名：

| 格式 | 像素 0..3 |
| --- | --- |
| `A4R4G4B4` | `F123 F456 F789 FABC` |
| `A8R8G8B8` | `FF112233 FF445566 FF778899 FFAABBCC` |
| `X8R8G8B8` | 忽略 Alpha 后比较 `112233 445566 778899 AABBCC` |

`SetTexture(stage=0)` 发现签名后设置 `gVideoMarkerBound`。随后任意一种 draw hook 执行：

```cpp
if (ConsumeVideoMarkerDraw()) {
    return D3D_OK;                 // 吞掉 7x5 标记本身
}
return gRealDrawPrimitive(...);    // 普通纹理继续走原始 D3D8
```

`ConsumeVideoMarkerDraw()` 每帧只调用一次 `BDV_Render()`，并用 `gRenderingVideo` 防止播放器内部 `SetTexture/DrawPrimitiveUP` 递归进入 hook。

### 10.2 场景 marker code

场景标记同样为 7x5/至多 8x8，但第五个像素编码 `1..14`。咖凌签名得到 code `1..14`，路西德签名再加 14 得到 code `15..28`。code 再映射到 `boss-scene` MCV 路径。

### 10.3 Present 的真实职责

当前源码中 `Present` 有四个职责：

1. 必要时在第一次真实 Present 再尝试 `BDV_AttachDevice`；
2. 消费跨线程/跨原生状态窗口排队的技能 ID；
3. 查询两个通道是否到达 `FINISHED/ERROR`；
4. 如果视频正在播放但本帧没有 marker draw，则执行一次兜底 `BDV_Render`。

因此，旧 README 中“Present 不再绘制视频”的绝对说法已经不完全符合当前源码。正常层级路径仍是 marker draw；Present 只在 marker 缺失时兜底，日志会记录：

```text
VIDEO OK: Present fallback active (field marker was not drawn)
```

## 11. 播放器内部生命周期

### 11.1 DLL 初始化

`BeiDouVideo.dll` 被加载后创建固定两个 `Player`：

```cpp
gPlayers[BDV_CHANNEL_PLAYER_SKILL] = new Player("player-skill");
gPlayers[BDV_CHANNEL_BOSS_SCENE] = new Player("boss-scene");
```

初始化日志中的：

```text
player-skill: not initialized
boss-scene: not initialized
```

只是构造时初始错误文本，不等于最终初始化失败。后续应看到两个 `device attached`。

### 11.2 文件和解码

- 使用 `CreateFileA` 打开 MCV；
- 使用 `CreateFileMappingA + MapViewOfFile` 只读映射，不把整文件再复制进堆；
- 校验 `MCV0`、VP80/VP90、尺寸、帧数、flags、时间轴和所有 offset/size；
- 每个通道创建一个 Win32 worker；颜色和 Alpha 各有一个 libvpx decoder；
- 每个 decoder 配置 2 个内部线程；
- 解码结果转换成 BGRA8；
- CPU 侧只有 3 个 `FrameSlot`，队列满时等待 2ms；
- GPU 侧循环使用 2 张 `D3DFMT_A8R8G8B8 / D3DPOOL_MANAGED` 纹理。

### 11.3 时间轴和结束

播放时钟使用 `QueryPerformanceCounter`。渲染时从三帧队列中选择时间不晚于当前时钟的最新帧，过期的更早帧计入 `droppedFrames`，避免卡顿后整段视频越来越滞后。

解码完成且时间到达容器时长后，状态变为 `FINISHED`，帧队列和两张纹理会释放，不保留最后一帧。

### 11.4 D3D 状态

播放器绘制前：

- 获取完整 render target 尺寸，不沿用游戏可能留下的局部 viewport；
- 创建 `D3DSBT_ALL` state block；
- 设置全 render target viewport；
- 使用全屏 triangle strip；
- 开启 `SRCALPHA / INVSRCALPHA`；
- 关闭 Z、光照和剔除；
- 使用线性过滤。

绘制后应用 state block、恢复原 viewport 并删除 state block，尽量不污染旧端后续渲染。

## 12. 新增一个调用方或新视频技能

### 12.1 只接播放器 API

如果另一个 DLL 已经能可靠取得真实 `IDirect3DDevice8*` 和渲染线程调用点，只需：

1. 以名称加载全部所需 `BDV_*`；
2. 调用一次 `BDV_AttachDevice`；
3. 触发时调用 `BDV_PlayFile` 或 `BDV_PlayFileEx`；
4. 每帧在有效 scene 中调用 `BDV_RenderAll`；
5. 轮询状态；
6. 设备失效或卸载前 Stop、Detach、FreeLibrary。

不要再复制当前 EXE 地址 hook，除非新调用方也确实针对同一个 EXE、同一版 Gr2D。

### 12.2 在当前技能适配层增加映射

最小改动是只在 `kVideoSkills[]` 增加一个 `skillId -> path`，然后确认该技能已经从正确的主动技能分支调用 `StartVideoSkill` 或 `QueueVideoSkill`。

还必须同步确认：

- MCV 文件存在且 `mcv_probe` 通过；
- 技能触发不会在隐藏 replay/tick ID 上重复播放整段主演出；
- player-skill 通道的新播放会替换同通道旧播放；
- FIELD_EFFECT marker 的层级、持续时间和只发给施法者的范围正确；
- 服务端伤害时间轴与视频命中时刻一致；
- 大 Canvas 已被视频替代时，部署不能遗漏 MCV。

### 12.3 换 EXE 或 Gr2D

必须重新做以下工作：

1. 确认 PE 位数、ImageBase、ASLR/重定位属性；
2. 找到可验证的启动加载点和代码洞；
3. 记录被覆盖指令的完整边界和原始字节；
4. 重新找 `LoadLibraryA` IAT；
5. 重新找 `Gr2D_DX8.dll` 的 `GetProcAddress` IAT RVA；
6. 从反汇编确认真正的 `Direct3DCreate8 -> CreateDevice` 路径；
7. 重新定位主动技能分发寄存器契约和返回分支；
8. 安装前逐点比较原始字节；
9. 没有任何匹配时安全禁用视频，而不是猜地址继续写内存。

## 13. 构建

播放器：

```bash
rtk bash tool/client-video/build.sh
```

关键编译选项：

```text
i686-w64-mingw32-g++
-std=c++17 -O2 -shared -static -static-libgcc -static-libstdc++
-lvpx -ld3d8 -lwinmm
-Wl,--kill-at
```

输出：

```text
clien/BeiDouVideo.dll
clien/BeiDouVideoHarness.exe
tool/client-video/build/mcv_probe
```

兼容 DLL 的仓库构建入口是：

```bash
rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh
```

但是受第 2 节的源码/成品版本偏差影响，在找回 v69/v67 对应源码之前，不应把重编译结果覆盖到交付客户端。

## 14. 部署清单

最小运行目录：

```text
游戏根目录/
  BeiDou.exe
  DawnWarriorSkillCompat.dll
  BeiDouVideo.dll
  Data/
    Video/
      <实际映射使用的所有 .mcv>
```

若使用诊断和 Boss 场景链，还需要：

```text
WzFileLogger.dll
KaringSceneCompat.dll
```

明确禁止作为手机正式部署项：

```text
d3d8.dll
d3d8-desktop-test.dll
BeiDouVideoHarness.exe
```

`BeiDouVideoHarness.exe` 仅用于 Windows/Winlator 独立验证播放器。MCV 必须保留为普通 `Data/Video` 文件，不能打入 WZ。

## 15. 验证流程

### 15.1 静态验证

```bash
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py --dry-run
rtk python3 tool/client-video/test_multichannel_contract.py
rtk python3 tool/client-debug/dawn-warrior-skill-compat/test_video_hook_contract.py
rtk git diff --check
```

检查导出：

```bash
rtk proxy i686-w64-mingw32-objdump -p clien/BeiDouVideo.dll
```

必须看到本文件第 7.2 节列出的 13 个未修饰导出名。

检查 MCV：

```bash
rtk tool/client-video/build/mcv_probe clien/Data/Video/<name>.mcv
```

### 15.2 独立播放器验证

Windows/Winlator 客户端根目录运行：

```text
BeiDouVideoHarness.exe "Data\Video\player.mcv|Data\Video\boss.mcv"
```

竖线前是 player-skill，后面是 boss-scene。此步骤可把容器/解码/Alpha 问题与游戏 hook 问题分开。

### 15.3 游戏内成功日志

`DawnWarriorSkillCompat.log`：

```text
VIDEO OK: Gr2D_DX8 hook installed
VIDEO OK: real Direct3DCreate8 intercepted
VIDEO OK: D3D8 device attached without a proxy DLL
VIDEO OK: Gr2D field-layer marker texture detected
VIDEO OK: <skill name> started
```

`BeiDouVideo.log`：

```text
player-skill: device attached
boss-scene: device attached
player-skill: playback queued
```

还要实机确认：启动、登录、首次施放、连续施放、换图、死亡、窗口/分辨率变化、完整视频时长、Alpha、伤害数字层级、命中特效、伤害时序和退出清理。

## 16. 常见故障

| 现象 | 首查项 | 处理 |
| --- | --- | --- |
| EXE 启动即崩 | EXE 哈希、入口原字节、代码洞 | 不要套用本地址表到另一 EXE |
| 找不到 `BeiDouVideo.dll` | 工作目录和 DLL 文件 | 与 EXE 同目录部署 |
| `D3D8 device is not attached` | Direct3DCreate8/CreateDevice 日志 | 检查 Gr2D RVA、LoadLibrary hook 链和 DLL 版本 |
| 视频开始但看不到 | marker draw、Present fallback | 检查 Map/Effect marker 和服务端 FIELD_EFFECT |
| `failed to open MCV file` | `Data/Video` 普通目录 | 不要打入 WZ，检查相对路径 |
| `invalid MCV signature` | 文件是否为完整 MCV0 | 重新同步并用 `mcv_probe` 校验 |
| 视频裁在小矩形 | 播放器版本 | 使用按完整 render target 绘制的版本 |
| 技能层压住 UI/飘字 | draw 插入点 | 优先使用已验证 FIELD_EFFECT marker 层，不要随意移到 Present |
| 普通渲染递归或栈溢出 | hook 链和 `gRenderingVideo` | 保留递归保护，正确保存每层 next/original 函数 |
| 新 DLL 编译后功能倒退 | v43 源码与 v69/v67 成品偏差 | 停止覆盖，恢复已验证成品并补齐对应源码 |

## 17. 证据文件索引

| 内容 | 仓库路径 |
| --- | --- |
| EXE loader 生成器 | `tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py` |
| 统一兼容 DLL 源码 | `tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp` |
| 兼容 DLL说明 | `tool/client-debug/dawn-warrior-skill-compat/README.md` |
| 播放器公共 ABI | `tool/client-video/BeiDouVideoApi.h` |
| 播放器实现 | `tool/client-video/BeiDouVideo.cpp` |
| MCV 解析器 | `tool/client-video/McvFormat.h/.cpp` |
| 独立调用示例 | `tool/client-video/VideoHarness.cpp` |
| 播放器总说明 | `tool/client-video/README.md` |
| 可选场景调用方 | `tool/client-debug/karing-scene-compat/KaringSceneCompat.cpp` |
| 可选场景加载点 | `tool/client-debug/wz_file_logger/WzFileLogger.cpp` |
| 真实模块加载日志 | `clien/diagnostics/session-20260828-082236-pid8156.log` |

## 18. 对外说明模板

可以把下面这段作为交付摘要：

> BeiDouVideo.dll 是一个 32 位 Direct3D 8 MCV 播放器，不由 BeiDou.exe 直接导入。BeiDou.exe 的固定入口补丁只加载 DawnWarriorSkillCompat.dll；兼容 DLL 再从 Gr2D_DX8.dll 的真实 Direct3DCreate8/CreateDevice 路径取得游戏设备，以 GetProcAddress 加载 BDV_* API。触发时调用 BDV_PlayFile/BDV_PlayFileEx，渲染时在 Map/Effect FIELD_EFFECT 标记的原生 draw 层调用 BDV_RenderAll。视频文件必须作为 Data/Video 下的普通 MCV 文件部署。所有 EXE VA 和 Gr2D RVA 都绑定当前二进制版本，换版本必须重新反汇编和核对原始字节；BeiDouVideo.dll 自身应始终按导出名调用，不能写死导出地址。
