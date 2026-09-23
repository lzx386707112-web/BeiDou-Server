// Adds Vellum attack10/11 FIELD_EFFECT video markers on top of the verified v69 core.

#include "../../client-video/BeiDouVideoApi.h"

#include <windows.h>
#include <d3d8.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr uintptr_t kLoadLibraryAIat = 0x00AF00C0;
constexpr uintptr_t kCoreReadyHookAddress = 0x0094F89E;
constexpr uintptr_t kGr2DGetProcAddressIatRva = 0x0002D024;
constexpr size_t kCreateDeviceVtableIndex = 15;
constexpr size_t kPresentVtableIndex = 15;
constexpr size_t kSetTextureVtableIndex = 61;
constexpr size_t kDrawPrimitiveVtableIndex = 70;
constexpr size_t kDrawIndexedPrimitiveVtableIndex = 71;
constexpr size_t kDrawPrimitiveUpVtableIndex = 72;
constexpr size_t kDrawIndexedPrimitiveUpVtableIndex = 73;
constexpr UINT kMarkerWidth = 7;
constexpr UINT kMarkerHeight = 5;
constexpr DWORD kCoreReadyTimeoutMs = 10000;
constexpr DWORD kCoreReadyPollMs = 10;
constexpr int kAttack10MarkerCode = 5;
constexpr int kAttack11MarkerCode = 6;
constexpr char kCoreDllName[] = "BeiDouSkillCompatCore.dll";
constexpr char kAttack10Path[] = "Data\\Video\\root-abyss-vellum-attack10.mcv";
constexpr char kAttack11Path[] = "Data\\Video\\root-abyss-vellum-attack11.mcv";

using PlayFileExFn = int(__stdcall*)(uint32_t, const char*);
using GetLastErrorExFn = void(__stdcall*)(uint32_t, char*, uint32_t);
using AttachDeviceFn = int(__stdcall*)(void*);
using RenderFn = void(__stdcall*)();
using GetStatusExFn = int(__stdcall*)(uint32_t, BdvStatus*);
using LoadLibraryAFn = HMODULE(WINAPI*)(LPCSTR);
using GetProcAddressFn = FARPROC(WINAPI*)(HMODULE, LPCSTR);
using Direct3DCreate8Fn = IDirect3D8*(WINAPI*)(UINT);
using CreateDeviceFn = HRESULT(WINAPI*)(
    IDirect3D8*, UINT, D3DDEVTYPE, HWND, DWORD,
    D3DPRESENT_PARAMETERS*, IDirect3DDevice8**);
using PresentFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, const RECT*, const RECT*, HWND, const RGNDATA*);
using SetTextureFn = HRESULT(WINAPI*)(IDirect3DDevice8*, DWORD, IDirect3DBaseTexture8*);
using DrawPrimitiveFn = HRESULT(WINAPI*)(IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT);
using DrawIndexedPrimitiveFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT, UINT, UINT);
using DrawPrimitiveUpFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, const void*, UINT);
using DrawIndexedPrimitiveUpFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT, UINT,
    const void*, D3DFORMAT, const void*, UINT);

static_assert(sizeof(void*) == 4, "This hook must be built for the 32-bit client");

HMODULE gVideoModule = nullptr;
PlayFileExFn gPlayFileEx = nullptr;
GetLastErrorExFn gGetLastErrorEx = nullptr;
AttachDeviceFn gAttachDevice = nullptr;
RenderFn gRender = nullptr;
GetStatusExFn gGetStatusEx = nullptr;
LoadLibraryAFn gRealLoadLibraryA = nullptr;
GetProcAddressFn gRealGetProcAddress = nullptr;
Direct3DCreate8Fn gRealDirect3DCreate8 = nullptr;
CreateDeviceFn gRealCreateDevice = nullptr;
PresentFn gRealPresent = nullptr;
SetTextureFn gRealSetTexture = nullptr;
DrawPrimitiveFn gRealDrawPrimitive = nullptr;
DrawIndexedPrimitiveFn gRealDrawIndexedPrimitive = nullptr;
DrawPrimitiveUpFn gRealDrawPrimitiveUp = nullptr;
DrawIndexedPrimitiveUpFn gRealDrawIndexedPrimitiveUp = nullptr;
bool gMarkerBound = false;
int gMarkerCode = 0;
bool gVideoPlaying = false;
int gActiveMarkerCode = 0;
bool gRenderedThisFrame = false;
bool gRenderingVideo = false;

template <typename Function>
Function FunctionFromPointer(void* pointer) {
    static_assert(sizeof(Function) == sizeof(pointer), "unexpected Win32 function pointer size");
    Function function = nullptr;
    memcpy(&function, &pointer, sizeof(function));
    return function;
}

template <typename Function>
FARPROC FunctionToFarProc(Function function) {
    static_assert(sizeof(Function) == sizeof(FARPROC), "unexpected Win32 function pointer size");
    union {
        Function function;
        FARPROC address;
    } conversion = {function};
    return conversion.address;
}

template <typename Function>
Function LoadFunction(HMODULE module, const char* name) {
    return FunctionFromPointer<Function>(reinterpret_cast<void*>(GetProcAddress(module, name)));
}

bool Equals(const char* left, const char* right) {
    if (left == nullptr || right == nullptr) return false;
    while (*left != '\0' && *left == *right) {
        ++left;
        ++right;
    }
    return *left == *right;
}

void LogLine(const char* text) {
    HANDLE file = CreateFileA(
        "VellumVideoCompat.log", FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(file, text, static_cast<DWORD>(lstrlenA(text)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

bool PatchPointer(void** slot, void* replacement, void** original) {
    DWORD oldProtect = 0;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &oldProtect)) return false;
    if (*slot != replacement) {
        if (original != nullptr) *original = *slot;
        *slot = replacement;
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(*slot));
    }
    DWORD ignored = 0;
    VirtualProtect(slot, sizeof(*slot), oldProtect, &ignored);
    return true;
}

bool PointerBelongsToModule(const void* pointer, HMODULE module) {
    MEMORY_BASIC_INFORMATION info = {};
    return pointer != nullptr && module != nullptr &&
        VirtualQuery(pointer, &info, sizeof(info)) == sizeof(info) &&
        info.AllocationBase == module;
}

bool CoreHooksAreReady(HMODULE core) {
    const auto* branch = reinterpret_cast<const unsigned char*>(kCoreReadyHookAddress);
    if (branch[0] != 0xE9) return false;
    const auto displacement = *reinterpret_cast<const int32_t*>(branch + 1);
    const void* target = branch + 5 + displacement;
    return PointerBelongsToModule(target, core);
}

bool LoadVideoModule() {
    if (gVideoModule == nullptr) gVideoModule = LoadLibraryA("BeiDouVideo.dll");
    if (gVideoModule == nullptr) return false;
    if (gPlayFileEx == nullptr) {
        gPlayFileEx = LoadFunction<PlayFileExFn>(gVideoModule, "BDV_PlayFileEx");
        gGetLastErrorEx = LoadFunction<GetLastErrorExFn>(gVideoModule, "BDV_GetLastErrorEx");
        gAttachDevice = LoadFunction<AttachDeviceFn>(gVideoModule, "BDV_AttachDevice");
        gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
        gGetStatusEx = LoadFunction<GetStatusExFn>(gVideoModule, "BDV_GetStatusEx");
    }
    return gPlayFileEx != nullptr && gGetLastErrorEx != nullptr &&
        gAttachDevice != nullptr && gRender != nullptr && gGetStatusEx != nullptr;
}

int MarkerCodeFromA4R4G4B4(const uint16_t* pixels) {
    if (pixels[0] != 0xF357 || pixels[1] != 0xF689 ||
        pixels[2] != 0xFABC || pixels[3] != 0xFDEF) {
        return 0;
    }
    const int code = (pixels[4] >> 8) & 0x0F;
    return code == kAttack10MarkerCode || code == kAttack11MarkerCode ? code : 0;
}

int MarkerCodeFromA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    const uint32_t alphaMask = ignoreAlpha ? 0x00000000u : 0xFF000000u;
    const uint32_t colorMask = ignoreAlpha ? 0x00FFFFFFu : 0xFFFFFFFFu;
    if ((pixels[0] & colorMask) != (alphaMask | 0x00335577u) ||
        (pixels[1] & colorMask) != (alphaMask | 0x00668899u) ||
        (pixels[2] & colorMask) != (alphaMask | 0x00AABBCCu) ||
        (pixels[3] & colorMask) != (alphaMask | 0x00DDEEFFu)) {
        return 0;
    }
    const int red = static_cast<int>((pixels[4] >> 16) & 0xFF);
    const int code = red / 17;
    if (red != code * 17) return 0;
    return code == kAttack10MarkerCode || code == kAttack11MarkerCode ? code : 0;
}

int DetectMarker(IDirect3DBaseTexture8* baseTexture) {
    if (baseTexture == nullptr || baseTexture->GetType() != D3DRTYPE_TEXTURE) return 0;
    auto* texture = static_cast<IDirect3DTexture8*>(baseTexture);
    D3DSURFACE_DESC description = {};
    if (FAILED(texture->GetLevelDesc(0, &description)) ||
        description.Width < kMarkerWidth || description.Width > 8 ||
        description.Height < kMarkerHeight || description.Height > 8) {
        return 0;
    }
    D3DLOCKED_RECT locked = {};
    if (FAILED(texture->LockRect(0, &locked, nullptr, D3DLOCK_READONLY))) return 0;
    int code = 0;
    if (description.Format == D3DFMT_A4R4G4B4 && locked.Pitch >= 8) {
        code = MarkerCodeFromA4R4G4B4(static_cast<const uint16_t*>(locked.pBits));
    } else if (description.Format == D3DFMT_A8R8G8B8 && locked.Pitch >= 16) {
        code = MarkerCodeFromA8R8G8B8(static_cast<const uint32_t*>(locked.pBits), false);
    } else if (description.Format == D3DFMT_X8R8G8B8 && locked.Pitch >= 16) {
        code = MarkerCodeFromA8R8G8B8(static_cast<const uint32_t*>(locked.pBits), true);
    }
    texture->UnlockRect(0);
    return code;
}

bool StartVideo(int markerCode) {
    const char* path = markerCode == kAttack10MarkerCode
        ? kAttack10Path
        : markerCode == kAttack11MarkerCode ? kAttack11Path : nullptr;
    if (path == nullptr) return false;
    if (!LoadVideoModule()) {
        LogLine("VELLUM VIDEO ERROR: BeiDouVideo.dll was not found or incompatible");
        return false;
    }
    if (!gPlayFileEx(BDV_CHANNEL_BOSS_SCENE, path)) {
        char error[256] = "unknown Vellum video playback error";
        gGetLastErrorEx(BDV_CHANNEL_BOSS_SCENE, error, sizeof(error));
        LogLine(error);
        return false;
    }
    gVideoPlaying = true;
    gActiveMarkerCode = markerCode;
    gRenderedThisFrame = false;
    LogLine(markerCode == kAttack10MarkerCode
        ? "VELLUM VIDEO OK: attack10 screen started"
        : "VELLUM VIDEO OK: attack11 screen started");
    return true;
}

bool ConsumeMarkerDraw() {
    if (gRenderingVideo || !gMarkerBound) return false;
    if (!gVideoPlaying || gActiveMarkerCode != gMarkerCode) StartVideo(gMarkerCode);
    if (gVideoPlaying && !gRenderedThisFrame && gRender != nullptr) {
        gRenderedThisFrame = true;
        gRenderingVideo = true;
        gRender();
        gRenderingVideo = false;
    }
    return true;
}

HRESULT WINAPI HookSetTexture(
    IDirect3DDevice8* device, DWORD stage, IDirect3DBaseTexture8* texture) {
    if (stage == 0 && !gRenderingVideo) {
        gMarkerCode = DetectMarker(texture);
        gMarkerBound = gMarkerCode != 0;
    }
    return gRealSetTexture(device, stage, texture);
}

HRESULT WINAPI HookDrawPrimitive(
    IDirect3DDevice8* device, D3DPRIMITIVETYPE type, UINT start, UINT count) {
    if (ConsumeMarkerDraw()) return D3D_OK;
    return gRealDrawPrimitive(device, type, start, count);
}

HRESULT WINAPI HookDrawIndexedPrimitive(
    IDirect3DDevice8* device, D3DPRIMITIVETYPE type, UINT minIndex,
    UINT vertices, UINT startIndex, UINT count) {
    if (ConsumeMarkerDraw()) return D3D_OK;
    return gRealDrawIndexedPrimitive(device, type, minIndex, vertices, startIndex, count);
}

HRESULT WINAPI HookDrawPrimitiveUp(
    IDirect3DDevice8* device, D3DPRIMITIVETYPE type, UINT count,
    const void* data, UINT stride) {
    if (ConsumeMarkerDraw()) return D3D_OK;
    return gRealDrawPrimitiveUp(device, type, count, data, stride);
}

HRESULT WINAPI HookDrawIndexedPrimitiveUp(
    IDirect3DDevice8* device, D3DPRIMITIVETYPE type, UINT minIndex,
    UINT vertices, UINT count, const void* indices, D3DFORMAT format,
    const void* data, UINT stride) {
    if (ConsumeMarkerDraw()) return D3D_OK;
    return gRealDrawIndexedPrimitiveUp(
        device, type, minIndex, vertices, count, indices, format, data, stride);
}

HRESULT WINAPI HookPresent(
    IDirect3DDevice8* device, const RECT* source, const RECT* destination,
    HWND window, const RGNDATA* dirtyRegion) {
    if (gVideoPlaying && gGetStatusEx != nullptr) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (gGetStatusEx(BDV_CHANNEL_BOSS_SCENE, &status) &&
            (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR)) {
            gVideoPlaying = false;
            gActiveMarkerCode = 0;
        }
    }
    if (gVideoPlaying && !gRenderedThisFrame && gRender != nullptr) {
        gRenderedThisFrame = true;
        gRenderingVideo = true;
        gRender();
        gRenderingVideo = false;
    }
    const HRESULT result = gRealPresent(device, source, destination, window, dirtyRegion);
    gRenderedThisFrame = false;
    gMarkerBound = false;
    gMarkerCode = 0;
    return result;
}

bool PatchDeviceHooks(void** vtable) {
    void* original = nullptr;
    if (!PatchPointer(&vtable[kPresentVtableIndex], reinterpret_cast<void*>(&HookPresent), &original)) return false;
    if (gRealPresent == nullptr) gRealPresent = FunctionFromPointer<PresentFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kSetTextureVtableIndex], reinterpret_cast<void*>(&HookSetTexture), &original)) return false;
    if (gRealSetTexture == nullptr) gRealSetTexture = FunctionFromPointer<SetTextureFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawPrimitiveVtableIndex], reinterpret_cast<void*>(&HookDrawPrimitive), &original)) return false;
    if (gRealDrawPrimitive == nullptr) gRealDrawPrimitive = FunctionFromPointer<DrawPrimitiveFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawIndexedPrimitiveVtableIndex], reinterpret_cast<void*>(&HookDrawIndexedPrimitive), &original)) return false;
    if (gRealDrawIndexedPrimitive == nullptr) gRealDrawIndexedPrimitive = FunctionFromPointer<DrawIndexedPrimitiveFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawPrimitiveUpVtableIndex], reinterpret_cast<void*>(&HookDrawPrimitiveUp), &original)) return false;
    if (gRealDrawPrimitiveUp == nullptr) gRealDrawPrimitiveUp = FunctionFromPointer<DrawPrimitiveUpFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawIndexedPrimitiveUpVtableIndex], reinterpret_cast<void*>(&HookDrawIndexedPrimitiveUp), &original)) return false;
    if (gRealDrawIndexedPrimitiveUp == nullptr) gRealDrawIndexedPrimitiveUp = FunctionFromPointer<DrawIndexedPrimitiveUpFn>(original);
    return gRealPresent != nullptr && gRealSetTexture != nullptr &&
        gRealDrawPrimitive != nullptr && gRealDrawIndexedPrimitive != nullptr &&
        gRealDrawPrimitiveUp != nullptr && gRealDrawIndexedPrimitiveUp != nullptr;
}

HRESULT WINAPI HookCreateDevice(
    IDirect3D8* direct3D, UINT adapter, D3DDEVTYPE type, HWND window,
    DWORD flags, D3DPRESENT_PARAMETERS* parameters, IDirect3DDevice8** output) {
    const HRESULT result = gRealCreateDevice(
        direct3D, adapter, type, window, flags, parameters, output);
    if (FAILED(result) || output == nullptr || *output == nullptr) return result;
    void** vtable = *reinterpret_cast<void***>(*output);
    if (!PatchDeviceHooks(vtable)) {
        LogLine("VELLUM VIDEO ERROR: failed to chain D3D8 device hooks");
        return result;
    }
    if (LoadVideoModule() && gAttachDevice(*output)) {
        LogLine("VELLUM VIDEO OK: D3D8 device attached");
    } else {
        LogLine("VELLUM VIDEO ERROR: BeiDouVideo.dll could not attach to D3D8");
    }
    return result;
}

IDirect3D8* WINAPI HookDirect3DCreate8(UINT sdkVersion) {
    IDirect3D8* direct3D = gRealDirect3DCreate8(sdkVersion);
    if (direct3D == nullptr) return nullptr;
    void** vtable = *reinterpret_cast<void***>(direct3D);
    void* original = nullptr;
    if (!PatchPointer(
            &vtable[kCreateDeviceVtableIndex],
            reinterpret_cast<void*>(&HookCreateDevice), &original)) {
        LogLine("VELLUM VIDEO ERROR: failed to chain IDirect3D8::CreateDevice");
        return direct3D;
    }
    if (gRealCreateDevice == nullptr) gRealCreateDevice = FunctionFromPointer<CreateDeviceFn>(original);
    LogLine("VELLUM VIDEO OK: Direct3DCreate8 chain installed");
    return direct3D;
}

FARPROC WINAPI HookGetProcAddress(HMODULE module, LPCSTR name) {
    FARPROC address = gRealGetProcAddress(module, name);
    if (reinterpret_cast<uintptr_t>(name) > 0xFFFF && Equals(name, "Direct3DCreate8")) {
        gRealDirect3DCreate8 = FunctionFromPointer<Direct3DCreate8Fn>(
            reinterpret_cast<void*>(address));
        if (gRealDirect3DCreate8 != nullptr) return FunctionToFarProc(&HookDirect3DCreate8);
    }
    return address;
}

bool InstallGr2DHook(HMODULE module) {
    if (module == nullptr) return false;
    auto** slot = reinterpret_cast<void**>(
        reinterpret_cast<uintptr_t>(module) + kGr2DGetProcAddressIatRva);
    if (*slot != reinterpret_cast<void*>(&HookGetProcAddress)) {
        void* original = nullptr;
        if (!PatchPointer(slot, reinterpret_cast<void*>(&HookGetProcAddress), &original)) return false;
        gRealGetProcAddress = FunctionFromPointer<GetProcAddressFn>(original);
    }
    if (gRealGetProcAddress == nullptr) return false;
    LogLine("VELLUM VIDEO OK: chained after core Gr2D hook");
    return true;
}

HMODULE WINAPI HookLoadLibraryA(LPCSTR name) {
    HMODULE module = gRealLoadLibraryA(name);
    HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
    if (module != nullptr && module == gr2D) InstallGr2DHook(module);
    return module;
}

DWORD WINAPI InstallHooks(LPVOID) {
    LogLine("LOAD: Vellum attack10/11 video compatibility v1");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("VELLUM VIDEO ERROR: unexpected BeiDou.exe image base");
        return 1;
    }
    HMODULE core = nullptr;
    for (DWORD waited = 0; waited < kCoreReadyTimeoutMs; waited += kCoreReadyPollMs) {
        core = GetModuleHandleA(kCoreDllName);
        if (core != nullptr && CoreHooksAreReady(core)) break;
        Sleep(kCoreReadyPollMs);
    }
    if (core == nullptr || !CoreHooksAreReady(core)) {
        LogLine("VELLUM VIDEO ERROR: verified v69 core hooks did not become ready");
        return 2;
    }
    auto** slot = reinterpret_cast<void**>(kLoadLibraryAIat);
    if (!PointerBelongsToModule(*slot, core)) {
        LogLine("VELLUM VIDEO ERROR: LoadLibraryA chain is not owned by the v69 core");
        return 3;
    }
    void* original = nullptr;
    if (!PatchPointer(slot, reinterpret_cast<void*>(&HookLoadLibraryA), &original)) {
        LogLine("VELLUM VIDEO ERROR: failed to chain LoadLibraryA");
        return 4;
    }
    gRealLoadLibraryA = FunctionFromPointer<LoadLibraryAFn>(original);
    HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
    if (gr2D != nullptr && !InstallGr2DHook(gr2D)) {
        LogLine("VELLUM VIDEO ERROR: failed to chain existing Gr2D_DX8.dll");
        return 5;
    }
    LogLine("VELLUM VIDEO OK: runtime hook chain ready");
    return 0;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        DeleteFileA("VellumVideoCompat.log");
        HANDLE thread = CreateThread(nullptr, 0, InstallHooks, nullptr, 0, nullptr);
        if (thread != nullptr) CloseHandle(thread);
    }
    return TRUE;
}
