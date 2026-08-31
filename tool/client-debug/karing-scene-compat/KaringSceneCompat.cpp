// Adds Karing scene-marker playback through the existing D3D8 hook chain.

#include "../../client-video/BeiDouVideoApi.h"

#include <windows.h>
#include <d3d8.h>
#include <stddef.h>
#include <stdint.h>

namespace {

constexpr size_t kPresentVtableIndex = 15;
constexpr size_t kSetTextureVtableIndex = 61;
constexpr size_t kDrawPrimitiveVtableIndex = 70;
constexpr size_t kDrawIndexedPrimitiveVtableIndex = 71;
constexpr size_t kDrawPrimitiveUpVtableIndex = 72;
constexpr size_t kDrawIndexedPrimitiveUpVtableIndex = 73;
constexpr UINT kMarkerWidth = 7;
constexpr UINT kMarkerHeight = 5;
constexpr int kMarkerCodeCount = 15;
constexpr DWORD kAttachRetryMilliseconds = 100;
constexpr int kAttachRetryCount = 600;
constexpr int kMarkerRearmFrames = 10;

using GetAttachedDeviceFn = void*(__stdcall*)();
using PlayFileExFn = int(__stdcall*)(uint32_t, const char*);
using RenderAllFn = void(__stdcall*)();
using GetStatusExFn = int(__stdcall*)(uint32_t, BdvStatus*);
using GetLastErrorExFn = void(__stdcall*)(uint32_t, char*, uint32_t);
using PresentFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, const RECT*, const RECT*, HWND, const RGNDATA*);
using SetTextureFn = HRESULT(WINAPI*)(IDirect3DDevice8*, DWORD, IDirect3DBaseTexture8*);
using DrawPrimitiveFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT);
using DrawIndexedPrimitiveFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT, UINT, UINT);
using DrawPrimitiveUpFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, const void*, UINT);
using DrawIndexedPrimitiveUpFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT, UINT,
    const void*, D3DFORMAT, const void*, UINT);

static_assert(sizeof(void*) == 4, "This hook must be built for the 32-bit client");

struct SceneMapping {
    int markerCode;
    const char* path;
};

constexpr SceneMapping kScenes[] = {
    {1, "Data\\Video\\karing-dark-pulse.mcv"},
    {2, "Data\\Video\\karing-goongi-screen.mcv"},
    {3, "Data\\Video\\karing-perils-goongi.mcv"},
    {4, "Data\\Video\\karing-perils-dool.mcv"},
    {5, "Data\\Video\\karing-perils-hondon.mcv"},
    {6, "Data\\Video\\karing-reward-screen.mcv"},
    {7, "Data\\Video\\karing-clear-goongi.mcv"},
    {8, "Data\\Video\\karing-clear-goongi2.mcv"},
    {9, "Data\\Video\\karing-clear-dool.mcv"},
    {10, "Data\\Video\\karing-clear-dool2.mcv"},
    {11, "Data\\Video\\karing-clear-hondon.mcv"},
    {12, "Data\\Video\\karing-clear-hondon2.mcv"},
    {13, "Data\\Video\\karing-p2-regen.mcv"},
    {14, "Data\\Video\\karing-p3-regen.mcv"},
};

GetAttachedDeviceFn gGetAttachedDevice = nullptr;
PlayFileExFn gPlayFileEx = nullptr;
RenderAllFn gRenderAll = nullptr;
GetStatusExFn gGetStatusEx = nullptr;
GetLastErrorExFn gGetLastErrorEx = nullptr;
PresentFn gNextPresent = nullptr;
SetTextureFn gNextSetTexture = nullptr;
DrawPrimitiveFn gNextDrawPrimitive = nullptr;
DrawIndexedPrimitiveFn gNextDrawIndexedPrimitive = nullptr;
DrawPrimitiveUpFn gNextDrawPrimitiveUp = nullptr;
DrawIndexedPrimitiveUpFn gNextDrawIndexedPrimitiveUp = nullptr;
bool gMarkerBound = false;
bool gSawMarkerThisFrame[kMarkerCodeCount] = {};
bool gMarkerStarted[kMarkerCodeCount] = {};
bool gRenderedThisFrame = false;
bool gRenderingScene = false;
bool gScenePlaying = false;
int gBoundMarkerCode = 0;
int gPendingMarkerCode = 0;
int gFramesWithoutMarker[kMarkerCodeCount] = {};

void LogLine(const char* line) {
    HANDLE file = CreateFileA(
        "KaringSceneCompat.log",
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
    const char* value = line == nullptr ? "(null)" : line;
    WriteFile(file, value, lstrlenA(value), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

template <typename T>
T LoadFunction(HMODULE module, const char* name) {
    const FARPROC address = GetProcAddress(module, name);
    static_assert(sizeof(T) == sizeof(address), "unexpected Win32 function pointer size");
    union {
        FARPROC source;
        T target;
    } conversion = {};
    conversion.source = address;
    return conversion.target;
}

template <typename T>
T FunctionFromPointer(void* pointer) {
    union {
        void* data;
        T function;
    } value = {};
    value.data = pointer;
    return value.function;
}

bool PatchPointer(void** slot, void* replacement, void** original) {
    if (slot == nullptr || replacement == nullptr) {
        return false;
    }
    DWORD oldProtect = 0;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &oldProtect)) {
        return false;
    }
    if (*slot != replacement) {
        *original = *slot;
        *slot = replacement;
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(*slot));
    }
    DWORD ignored = 0;
    VirtualProtect(slot, sizeof(*slot), oldProtect, &ignored);
    return *slot == replacement;
}

int DetectA4R4G4B4(const uint16_t* pixels) {
    if (pixels[0] != 0xF214 || pixels[1] != 0xF457
            || pixels[2] != 0xF9AB || pixels[3] != 0xFCDD) {
        return -1;
    }
    const int code = (pixels[4] >> 8) & 0x0F;
    return code >= 1 && code <= 14 ? code : -1;
}

int DetectA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    const uint32_t colorMask = ignoreAlpha ? 0x00FFFFFFu : 0xFFFFFFFFu;
    const uint32_t alpha = ignoreAlpha ? 0u : 0xFF000000u;
    if ((pixels[0] & colorMask) != (alpha | 0x00221144u)
            || (pixels[1] & colorMask) != (alpha | 0x00445577u)
            || (pixels[2] & colorMask) != (alpha | 0x0099AABBu)
            || (pixels[3] & colorMask) != (alpha | 0x00CCDDDDu)) {
        return -1;
    }
    const int red = static_cast<int>((pixels[4] >> 16) & 0xFF);
    const int code = red / 17;
    return red == code * 17 && code >= 1 && code <= 14 ? code : -1;
}

int DetectMarker(IDirect3DBaseTexture8* baseTexture) {
    if (baseTexture == nullptr || baseTexture->GetType() != D3DRTYPE_TEXTURE) {
        return -1;
    }
    IDirect3DTexture8* texture = static_cast<IDirect3DTexture8*>(baseTexture);
    D3DSURFACE_DESC description = {};
    if (FAILED(texture->GetLevelDesc(0, &description))
            || description.Width < kMarkerWidth || description.Width > 8
            || description.Height < kMarkerHeight || description.Height > 8) {
        return -1;
    }
    D3DLOCKED_RECT locked = {};
    if (FAILED(texture->LockRect(0, &locked, nullptr, D3DLOCK_READONLY))) {
        return -1;
    }
    int code = -1;
    if (description.Format == D3DFMT_A4R4G4B4 && locked.Pitch >= 10) {
        code = DetectA4R4G4B4(static_cast<const uint16_t*>(locked.pBits));
    } else if (description.Format == D3DFMT_A8R8G8B8 && locked.Pitch >= 20) {
        code = DetectA8R8G8B8(static_cast<const uint32_t*>(locked.pBits), false);
    } else if (description.Format == D3DFMT_X8R8G8B8 && locked.Pitch >= 20) {
        code = DetectA8R8G8B8(static_cast<const uint32_t*>(locked.pBits), true);
    }
    texture->UnlockRect(0);
    return code;
}

const SceneMapping* FindScene(int markerCode) {
    for (size_t index = 0; index < sizeof(kScenes) / sizeof(kScenes[0]); ++index) {
        if (kScenes[index].markerCode == markerCode) {
            return &kScenes[index];
        }
    }
    return nullptr;
}

bool CanStartScene(int markerCode) {
    return markerCode > 0 && markerCode < kMarkerCodeCount
        && (!gMarkerStarted[markerCode]
            || gFramesWithoutMarker[markerCode] >= kMarkerRearmFrames);
}

bool StartScene(int markerCode) {
    if (!CanStartScene(markerCode)) {
        return false;
    }
    const SceneMapping* scene = FindScene(markerCode);
    if (scene == nullptr || gPlayFileEx == nullptr) {
        return false;
    }
    if (!gPlayFileEx(BDV_CHANNEL_BOSS_SCENE, scene->path)) {
        char error[256] = {};
        if (gGetLastErrorEx != nullptr) {
            gGetLastErrorEx(BDV_CHANNEL_BOSS_SCENE, error, sizeof(error));
        }
        LogLine(error[0] == '\0' ? "ERROR: boss-scene playback failed" : error);
        return false;
    }
    gMarkerStarted[markerCode] = true;
    gFramesWithoutMarker[markerCode] = 0;
    gScenePlaying = true;
    gRenderedThisFrame = false;
    char line[128] = {};
    wsprintfA(line, "OK: marker=%d path=%s", markerCode, scene->path);
    LogLine(line);
    return true;
}

void RenderScene() {
    if (!gScenePlaying || gRenderAll == nullptr || gRenderingScene
            || gRenderedThisFrame) {
        return;
    }
    gRenderingScene = true;
    gRenderAll();
    gRenderingScene = false;
    gRenderedThisFrame = true;
}

bool ConsumeMarkerDraw() {
    if (gRenderingScene || !gMarkerBound || gBoundMarkerCode <= 0) {
        return false;
    }
    if (CanStartScene(gBoundMarkerCode)) {
        if (!gScenePlaying) {
            StartScene(gBoundMarkerCode);
        } else if (gPendingMarkerCode == 0) {
            gPendingMarkerCode = gBoundMarkerCode;
        }
    }
    RenderScene();
    return true;
}

HRESULT WINAPI HookSetTexture(
        IDirect3DDevice8* device, DWORD stage, IDirect3DBaseTexture8* texture) {
    if (stage == 0 && !gRenderingScene) {
        const int markerCode = DetectMarker(texture);
        gMarkerBound = markerCode > 0;
        gBoundMarkerCode = markerCode > 0 ? markerCode : 0;
        if (markerCode > 0) {
            gSawMarkerThisFrame[markerCode] = true;
        }
    }
    return gNextSetTexture(device, stage, texture);
}

HRESULT WINAPI HookDrawPrimitive(
        IDirect3DDevice8* device, D3DPRIMITIVETYPE type,
        UINT startVertex, UINT primitiveCount) {
    if (ConsumeMarkerDraw()) {
        return D3D_OK;
    }
    return gNextDrawPrimitive(device, type, startVertex, primitiveCount);
}

HRESULT WINAPI HookDrawIndexedPrimitive(
        IDirect3DDevice8* device, D3DPRIMITIVETYPE type, UINT minIndex,
        UINT vertexCount, UINT startIndex, UINT primitiveCount) {
    if (ConsumeMarkerDraw()) {
        return D3D_OK;
    }
    return gNextDrawIndexedPrimitive(
        device, type, minIndex, vertexCount, startIndex, primitiveCount);
}

HRESULT WINAPI HookDrawPrimitiveUp(
        IDirect3DDevice8* device, D3DPRIMITIVETYPE type,
        UINT primitiveCount, const void* data, UINT stride) {
    if (ConsumeMarkerDraw()) {
        return D3D_OK;
    }
    return gNextDrawPrimitiveUp(device, type, primitiveCount, data, stride);
}

HRESULT WINAPI HookDrawIndexedPrimitiveUp(
        IDirect3DDevice8* device, D3DPRIMITIVETYPE type, UINT minVertexIndex,
        UINT vertexCount, UINT primitiveCount, const void* indexData,
        D3DFORMAT indexFormat, const void* data, UINT stride) {
    if (ConsumeMarkerDraw()) {
        return D3D_OK;
    }
    return gNextDrawIndexedPrimitiveUp(
        device, type, minVertexIndex, vertexCount, primitiveCount,
        indexData, indexFormat, data, stride);
}

HRESULT WINAPI HookPresent(
        IDirect3DDevice8* device, const RECT* source, const RECT* destination,
        HWND overrideWindow, const RGNDATA* dirtyRegion) {
    if (gScenePlaying && gGetStatusEx != nullptr) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (gGetStatusEx(BDV_CHANNEL_BOSS_SCENE, &status)
                && (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR)) {
            gScenePlaying = false;
            if (gPendingMarkerCode > 0) {
                const int pendingMarkerCode = gPendingMarkerCode;
                gPendingMarkerCode = 0;
                StartScene(pendingMarkerCode);
            }
        }
    }
    if (gScenePlaying && !gRenderedThisFrame) {
        RenderScene();
    }
    const HRESULT result = gNextPresent(
        device, source, destination, overrideWindow, dirtyRegion);
    for (int markerCode = 1; markerCode < kMarkerCodeCount; ++markerCode) {
        if (gSawMarkerThisFrame[markerCode]) {
            gFramesWithoutMarker[markerCode] = 0;
        } else if (gMarkerStarted[markerCode]
                && gFramesWithoutMarker[markerCode] < kMarkerRearmFrames) {
            ++gFramesWithoutMarker[markerCode];
        }
        gSawMarkerThisFrame[markerCode] = false;
    }
    gRenderedThisFrame = false;
    gMarkerBound = false;
    gBoundMarkerCode = 0;
    return result;
}

bool PatchDevice(IDirect3DDevice8* device) {
    if (device == nullptr) {
        return false;
    }
    void** vtable = *reinterpret_cast<void***>(device);
    void* original = nullptr;
    if (!PatchPointer(&vtable[kPresentVtableIndex],
            reinterpret_cast<void*>(&HookPresent), &original)) {
        return false;
    }
    gNextPresent = FunctionFromPointer<PresentFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kSetTextureVtableIndex],
            reinterpret_cast<void*>(&HookSetTexture), &original)) {
        return false;
    }
    gNextSetTexture = FunctionFromPointer<SetTextureFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawPrimitiveVtableIndex],
            reinterpret_cast<void*>(&HookDrawPrimitive), &original)) {
        return false;
    }
    gNextDrawPrimitive = FunctionFromPointer<DrawPrimitiveFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawIndexedPrimitiveVtableIndex],
            reinterpret_cast<void*>(&HookDrawIndexedPrimitive), &original)) {
        return false;
    }
    gNextDrawIndexedPrimitive = FunctionFromPointer<DrawIndexedPrimitiveFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawPrimitiveUpVtableIndex],
            reinterpret_cast<void*>(&HookDrawPrimitiveUp), &original)) {
        return false;
    }
    gNextDrawPrimitiveUp = FunctionFromPointer<DrawPrimitiveUpFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawIndexedPrimitiveUpVtableIndex],
            reinterpret_cast<void*>(&HookDrawIndexedPrimitiveUp), &original)) {
        return false;
    }
    gNextDrawIndexedPrimitiveUp = FunctionFromPointer<DrawIndexedPrimitiveUpFn>(original);
    return gNextPresent != nullptr && gNextSetTexture != nullptr
        && gNextDrawPrimitive != nullptr && gNextDrawIndexedPrimitive != nullptr
        && gNextDrawPrimitiveUp != nullptr && gNextDrawIndexedPrimitiveUp != nullptr;
}

bool LoadVideoApi(HMODULE module) {
    gGetAttachedDevice = LoadFunction<GetAttachedDeviceFn>(module, "BDV_GetAttachedDevice");
    gPlayFileEx = LoadFunction<PlayFileExFn>(module, "BDV_PlayFileEx");
    gRenderAll = LoadFunction<RenderAllFn>(module, "BDV_RenderAll");
    gGetStatusEx = LoadFunction<GetStatusExFn>(module, "BDV_GetStatusEx");
    gGetLastErrorEx = LoadFunction<GetLastErrorExFn>(module, "BDV_GetLastErrorEx");
    return gGetAttachedDevice != nullptr && gPlayFileEx != nullptr
        && gRenderAll != nullptr && gGetStatusEx != nullptr
        && gGetLastErrorEx != nullptr;
}

DWORD WINAPI InstallThread(LPVOID) {
    for (int attempt = 0; attempt < kAttachRetryCount; ++attempt) {
        HMODULE video = GetModuleHandleA("BeiDouVideo.dll");
        if (video != nullptr && LoadVideoApi(video)) {
            IDirect3DDevice8* device = static_cast<IDirect3DDevice8*>(gGetAttachedDevice());
            if (device != nullptr && PatchDevice(device)) {
                LogLine("OK: chained after Dawn D3D8 hooks");
                return 0;
            }
        }
        Sleep(kAttachRetryMilliseconds);
    }
    LogLine("ERROR: no attached D3D8 device or compatible BeiDouVideo API");
    return 1;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        DeleteFileA("KaringSceneCompat.log");
        HANDLE thread = CreateThread(nullptr, 0, InstallThread, nullptr, 0, nullptr);
        if (thread == nullptr) {
            return FALSE;
        }
        CloseHandle(thread);
    }
    return TRUE;
}
