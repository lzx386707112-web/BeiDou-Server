// 60 FPS limiter for the legacy Direct3D 8 BeiDou client.

#include <windows.h>
#include <d3d8.h>
#include <mmsystem.h>

#include <stdint.h>

namespace {

constexpr size_t kCreateDeviceVtableIndex = 15;
constexpr size_t kPresentVtableIndex = 15;
constexpr DWORD kInstallRetryMilliseconds = 100;
constexpr int kInstallRetryCount = 300;
constexpr LONGLONG kFramesPerSecond = 60;

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

PresentFn gRealPresent = nullptr;
LARGE_INTEGER gPerformanceFrequency = {};
LONGLONG gNextPresentTick = 0;

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
        "BeiDouFpsLimit.log",
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
    WriteFile(file, text, static_cast<DWORD>(lstrlenA(text)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

void WaitForFrameSlot() {
    if (gPerformanceFrequency.QuadPart <= 0) {
        QueryPerformanceFrequency(&gPerformanceFrequency);
    }
    if (gPerformanceFrequency.QuadPart <= 0) {
        Sleep(16);
        return;
    }

    LARGE_INTEGER now = {};
    QueryPerformanceCounter(&now);
    const LONGLONG frameTicks = gPerformanceFrequency.QuadPart / kFramesPerSecond;
    if (gNextPresentTick == 0 || now.QuadPart > gNextPresentTick + frameTicks * 4) {
        gNextPresentTick = now.QuadPart + frameTicks;
        return;
    }

    while (now.QuadPart < gNextPresentTick) {
        const LONGLONG remainingTicks = gNextPresentTick - now.QuadPart;
        const DWORD remainingMilliseconds = static_cast<DWORD>(
            remainingTicks * 1000 / gPerformanceFrequency.QuadPart);
        Sleep(remainingMilliseconds > 1 ? remainingMilliseconds - 1 : 1);
        QueryPerformanceCounter(&now);
    }
    gNextPresentTick += frameTicks;
}

HRESULT WINAPI HookPresent(
    IDirect3DDevice8* device,
    const RECT* source,
    const RECT* destination,
    HWND overrideWindow,
    const RGNDATA* dirtyRegion) {
    WaitForFrameSlot();
    return gRealPresent(device, source, destination, overrideWindow, dirtyRegion);
}

bool PatchPresent(void** vtable) {
    void** slot = &vtable[kPresentVtableIndex];
    if (*slot == reinterpret_cast<void*>(&HookPresent)) {
        return gRealPresent != nullptr;
    }

    DWORD oldProtect = 0;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &oldProtect)) {
        return false;
    }
    void* original = *slot;
    *slot = reinterpret_cast<void*>(&HookPresent);
    FlushInstructionCache(GetCurrentProcess(), slot, sizeof(*slot));
    DWORD ignored = 0;
    VirtualProtect(slot, sizeof(*slot), oldProtect, &ignored);

    gRealPresent = FunctionFromPointer<PresentFn>(original);
    return gRealPresent != nullptr;
}

bool InstallPresentHook() {
    HMODULE d3d8 = GetModuleHandleA("d3d8.dll");
    if (d3d8 == nullptr || GetModuleHandleA("Gr2D_DX8.dll") == nullptr) {
        return false;
    }
    Direct3DCreate8Fn createDirect3D = LoadFunction<Direct3DCreate8Fn>(d3d8, "Direct3DCreate8");
    if (createDirect3D == nullptr) {
        return false;
    }
    IDirect3D8* direct3D = createDirect3D(D3D_SDK_VERSION);
    if (direct3D == nullptr) {
        return false;
    }

    void** direct3DVtable = *reinterpret_cast<void***>(direct3D);
    CreateDeviceFn createDevice = FunctionFromPointer<CreateDeviceFn>(
        direct3DVtable[kCreateDeviceVtableIndex]);
    D3DPRESENT_PARAMETERS parameters = {};
    parameters.BackBufferWidth = 1;
    parameters.BackBufferHeight = 1;
    parameters.BackBufferFormat = D3DFMT_UNKNOWN;
    parameters.BackBufferCount = 1;
    parameters.MultiSampleType = D3DMULTISAMPLE_NONE;
    parameters.SwapEffect = D3DSWAPEFFECT_DISCARD;
    parameters.hDeviceWindow = GetForegroundWindow();
    if (parameters.hDeviceWindow == nullptr) {
        parameters.hDeviceWindow = GetDesktopWindow();
    }
    parameters.Windowed = TRUE;

    IDirect3DDevice8* dummyDevice = nullptr;
    const HRESULT result = createDevice(
        direct3D,
        D3DADAPTER_DEFAULT,
        D3DDEVTYPE_HAL,
        parameters.hDeviceWindow,
        D3DCREATE_FPU_PRESERVE | D3DCREATE_MULTITHREADED | D3DCREATE_SOFTWARE_VERTEXPROCESSING,
        &parameters,
        &dummyDevice);
    if (FAILED(result) || dummyDevice == nullptr) {
        direct3D->Release();
        return false;
    }

    void** deviceVtable = *reinterpret_cast<void***>(dummyDevice);
    const bool patched = PatchPresent(deviceVtable);
    dummyDevice->Release();
    direct3D->Release();
    return patched;
}

DWORD WINAPI InstallLimiter(LPVOID) {
    for (int attempt = 0; attempt < kInstallRetryCount; ++attempt) {
        if (InstallPresentHook()) {
            timeBeginPeriod(1);
            QueryPerformanceFrequency(&gPerformanceFrequency);
            LogLine("OK: Direct3D 8 frame rate limited to 60 FPS");
            return 0;
        }
        Sleep(kInstallRetryMilliseconds);
    }
    LogLine("ERROR: Direct3D 8 Present hook was not installed within 30 seconds");
    return 1;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(nullptr, 0, InstallLimiter, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
