#include "BeiDouVideoApi.h"

#include <windows.h>
#include <d3d8.h>

#include <stdint.h>

namespace {

constexpr size_t kCreateDeviceVtableIndex = 15;
constexpr size_t kPresentVtableIndex = 15;

using Direct3DCreate8Fn = IDirect3D8*(WINAPI*)(UINT);
using CreateDeviceFn = HRESULT(WINAPI*)(
    IDirect3D8*,
    UINT,
    D3DDEVTYPE,
    HWND,
    DWORD,
    D3DPRESENT_PARAMETERS*,
    IDirect3DDevice8**);
using PresentFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*,
    const RECT*,
    const RECT*,
    HWND,
    const RGNDATA*);
using AttachDeviceFn = int(BDV_CALL*)(void*);
using RenderFn = void(BDV_CALL*)();

HMODULE gRealD3D8 = nullptr;
HMODULE gVideoModule = nullptr;
Direct3DCreate8Fn gRealDirect3DCreate8 = nullptr;
CreateDeviceFn gRealCreateDevice = nullptr;
PresentFn gRealPresent = nullptr;
AttachDeviceFn gAttachDevice = nullptr;
RenderFn gRender = nullptr;

template <typename Function>
Function LoadFunction(HMODULE module, const char* name) {
    const FARPROC address = GetProcAddress(module, name);
    static_assert(sizeof(Function) == sizeof(address), "unexpected Win32 function pointer size");
    union {
        FARPROC address;
        Function function;
    } conversion = {address};
    return conversion.function;
}

template <typename Function>
Function FunctionFromPointer(void* pointer) {
    static_assert(sizeof(Function) == sizeof(pointer), "unexpected Win32 function pointer size");
    union {
        void* pointer;
        Function function;
    } conversion = {pointer};
    return conversion.function;
}

void LogLine(const char* text) {
    HANDLE file = CreateFileA(
        "BeiDouVideoProxy.log",
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written = 0;
    const char* value = text == nullptr ? "unknown" : text;
    WriteFile(file, value, static_cast<DWORD>(lstrlenA(value)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

bool PatchVtableSlot(void** slot, void* replacement, void** original) {
    DWORD oldProtect = 0;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_EXECUTE_READWRITE, &oldProtect)) {
        return false;
    }
    if (*slot != replacement) {
        if (*original == nullptr) {
            *original = *slot;
        }
        *slot = replacement;
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(*slot));
    }
    DWORD ignored = 0;
    VirtualProtect(slot, sizeof(*slot), oldProtect, &ignored);
    return true;
}

bool LoadVideoModule() {
    if (gVideoModule != nullptr) {
        return gAttachDevice != nullptr && gRender != nullptr;
    }
    gVideoModule = LoadLibraryA("BeiDouVideo.dll");
    if (gVideoModule == nullptr) {
        LogLine("ERROR: BeiDouVideo.dll was not found");
        return false;
    }
    gAttachDevice = LoadFunction<AttachDeviceFn>(gVideoModule, "BDV_AttachDevice");
    gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
    if (gAttachDevice == nullptr || gRender == nullptr) {
        LogLine("ERROR: BeiDouVideo.dll API is incompatible");
        return false;
    }
    return true;
}

HRESULT WINAPI HookPresent(
    IDirect3DDevice8* device,
    const RECT* source,
    const RECT* destination,
    HWND overrideWindow,
    const RGNDATA* dirtyRegion) {
    if (gRender != nullptr && SUCCEEDED(device->BeginScene())) {
        gRender();
        device->EndScene();
    }
    return gRealPresent(device, source, destination, overrideWindow, dirtyRegion);
}

HRESULT WINAPI HookCreateDevice(
    IDirect3D8* direct3D,
    UINT adapter,
    D3DDEVTYPE deviceType,
    HWND focusWindow,
    DWORD behaviorFlags,
    D3DPRESENT_PARAMETERS* parameters,
    IDirect3DDevice8** output) {
    const HRESULT result = gRealCreateDevice(
        direct3D,
        adapter,
        deviceType,
        focusWindow,
        behaviorFlags,
        parameters,
        output);
    if (FAILED(result) || output == nullptr || *output == nullptr) {
        return result;
    }

    void** vtable = *reinterpret_cast<void***>(*output);
    void* original = nullptr;
    if (!PatchVtableSlot(
            &vtable[kPresentVtableIndex],
            reinterpret_cast<void*>(&HookPresent),
            &original)) {
        LogLine("ERROR: failed to hook IDirect3DDevice8::Present");
        return result;
    }
    if (gRealPresent == nullptr) {
        gRealPresent = FunctionFromPointer<PresentFn>(original);
    }
    if (LoadVideoModule() && gAttachDevice(*output)) {
        LogLine("OK: D3D8 device attached to BeiDouVideo.dll");
    } else {
        LogLine("ERROR: video device attachment failed");
    }
    return result;
}

bool LoadRealD3D8() {
    if (gRealDirect3DCreate8 != nullptr) {
        return true;
    }
    char path[MAX_PATH] = {};
    const UINT length = GetSystemDirectoryA(path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH - 10) {
        LogLine("ERROR: failed to resolve the system D3D8 path");
        return false;
    }
    lstrcatA(path, "\\d3d8.dll");
    gRealD3D8 = LoadLibraryA(path);
    if (gRealD3D8 == nullptr) {
        LogLine("ERROR: failed to load the system D3D8 runtime");
        return false;
    }
    gRealDirect3DCreate8 = LoadFunction<Direct3DCreate8Fn>(gRealD3D8, "Direct3DCreate8");
    if (gRealDirect3DCreate8 == nullptr) {
        LogLine("ERROR: system D3D8 runtime has no Direct3DCreate8 export");
        return false;
    }
    return true;
}

bool IsBeiDouProcess() {
    char path[MAX_PATH] = {};
    if (GetModuleFileNameA(nullptr, path, MAX_PATH) == 0) {
        return false;
    }
    const char* name = path;
    for (const char* cursor = path; *cursor != '\0'; ++cursor) {
        if (*cursor == '\\' || *cursor == '/') {
            name = cursor + 1;
        }
    }
    return lstrcmpiA(name, "BeiDou.exe") == 0;
}

}  // namespace

extern "C" __declspec(dllexport) IDirect3D8* WINAPI Direct3DCreate8(UINT sdkVersion) {
    if (!LoadRealD3D8()) {
        return nullptr;
    }
    IDirect3D8* direct3D = gRealDirect3DCreate8(sdkVersion);
    if (direct3D == nullptr || !IsBeiDouProcess()) {
        return direct3D;
    }
    void** vtable = *reinterpret_cast<void***>(direct3D);
    void* original = nullptr;
    if (!PatchVtableSlot(
            &vtable[kCreateDeviceVtableIndex],
            reinterpret_cast<void*>(&HookCreateDevice),
            &original)) {
        LogLine("ERROR: failed to hook IDirect3D8::CreateDevice");
        return direct3D;
    }
    if (gRealCreateDevice == nullptr) {
        gRealCreateDevice = FunctionFromPointer<CreateDeviceFn>(original);
    }
    LogLine("OK: system Direct3DCreate8 forwarded");
    return direct3D;
}

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        LogLine("LOAD: BeiDou D3D8 video test proxy");
    }
    return TRUE;
}
