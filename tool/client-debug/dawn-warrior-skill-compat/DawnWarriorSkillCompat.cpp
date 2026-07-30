// Runtime compatibility hooks for BeiDou.exe Dawn Warrior 1112 custom skills.
// The DLL is loaded by the tiny EXE startup loader; ijl15.dll is untouched.

#include "../../client-video/BeiDouVideoApi.h"

#include <windows.h>
#include <d3d8.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr uintptr_t kLoadLibraryAIat = 0x00AF00C0;
constexpr uintptr_t kGr2DGetProcAddressIatRva = 0x0002D024;
constexpr size_t kCreateDeviceVtableIndex = 15;
constexpr size_t kPresentVtableIndex = 15;
constexpr size_t kSetTextureVtableIndex = 61;
constexpr size_t kDrawPrimitiveVtableIndex = 70;
constexpr size_t kDrawIndexedPrimitiveVtableIndex = 71;
constexpr size_t kDrawPrimitiveUpVtableIndex = 72;
constexpr size_t kDrawIndexedPrimitiveUpVtableIndex = 73;
constexpr DWORD kVideoHookRetryMilliseconds = 100;
constexpr int kVideoHookRetryCount = 300;
constexpr int kFirstSkill = 11121005;
constexpr int kLastSkill = 11121012;
constexpr UINT kVideoMarkerWidth = 7;
constexpr UINT kVideoMarkerHeight = 5;
constexpr int kMaxVideoMarkerTextures = 8;
constexpr uintptr_t kMagicBulletNodeUpdateAddress = 0x00441090;
constexpr int kNightWalkerFirstSkill = 14121003;
constexpr int kNightWalkerLastSkill = 14121036;
constexpr int kMaxTrackedProjectiles = 256;

using PlayFileFn = int(__stdcall*)(const char*);
using GetLastErrorFn = void(__stdcall*)(char*, uint32_t);
using AttachDeviceFn = int(__stdcall*)(void*);
using RenderFn = void(__stdcall*)();
using GetStatusFn = int(__stdcall*)(BdvStatus*);
using LoadLibraryAFn = HMODULE(WINAPI*)(LPCSTR);
using GetProcAddressFn = FARPROC(WINAPI*)(HMODULE, LPCSTR);
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
using SetTextureFn = HRESULT(WINAPI*)(IDirect3DDevice8*, DWORD, IDirect3DBaseTexture8*);
using DrawPrimitiveFn = HRESULT(WINAPI*)(IDirect3DDevice8*, D3DPRIMITIVETYPE, UINT, UINT);
using DrawIndexedPrimitiveFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*,
    D3DPRIMITIVETYPE,
    UINT,
    UINT,
    UINT,
    UINT);
using DrawPrimitiveUpFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*,
    D3DPRIMITIVETYPE,
    UINT,
    const void*,
    UINT);
using DrawIndexedPrimitiveUpFn = HRESULT(WINAPI*)(
    IDirect3DDevice8*,
    D3DPRIMITIVETYPE,
    UINT,
    UINT,
    UINT,
    const void*,
    D3DFORMAT,
    const void*,
    UINT);

static_assert(sizeof(void*) == 4, "This hook must be built for the 32-bit client");

struct HookSite {
    const char* name;
    uintptr_t address;
    const unsigned char* original;
    SIZE_T originalSize;
    void* replacement;
    unsigned char opcode;
};

HMODULE gVideoModule = nullptr;
PlayFileFn gPlayFile = nullptr;
GetLastErrorFn gVideoGetLastError = nullptr;
AttachDeviceFn gAttachDevice = nullptr;
RenderFn gRender = nullptr;
GetStatusFn gVideoGetStatus = nullptr;
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
bool gGr2DHookInstalled = false;
bool gVideoDeviceAttached = false;
bool gVideoPlaying = false;
bool gVideoMarkerBound = false;
bool gVideoRenderedThisFrame = false;
bool gRenderingVideo = false;
bool gMissingMarkerLogged = false;
DWORD gMissingMarkerFrames = 0;
IDirect3DBaseTexture8* gVideoMarkerTextures[kMaxVideoMarkerTextures] = {};
int gVideoMarkerTextureCount = 0;
DWORD gNightWalkerProjectileWindowEnd = 0;
constexpr int kProjectileProfileNone = 0;
constexpr int kProjectileProfileRapidThrow = 1;
constexpr int kProjectileProfileSilentNight = 2;
constexpr int kProjectileProfileShadowBiteBat = 3;
int gNightWalkerProjectileProfile = kProjectileProfileNone;
unsigned int gNightWalkerProjectileLane = 0;

struct MagicBulletNode {
    void* vtable;
    void* layer;
    int flagOrState;
    int unknown0C;
    int unknown10;
    int unknown14;
    int startTime;
    int endTime;
    int x1;
    int y1;
    int x2;
    int y2;
    IUnknown* origin;
    int a8;
    void* bstrData;
    int a10;
};

static_assert(offsetof(MagicBulletNode, startTime) == 0x18, "unexpected projectile startTime offset");
static_assert(offsetof(MagicBulletNode, x1) == 0x20, "unexpected projectile start point offset");
static_assert(offsetof(MagicBulletNode, x2) == 0x28, "unexpected projectile end point offset");

struct ProjectileRuntime {
    MagicBulletNode* node;
    int startX;
    int startY;
    int endX;
    int endY;
    int controlX;
    int controlY;
    int seed;
    int mode;
    int profile;
    int lane;
    unsigned int startTime;
    unsigned int endTime;
};

using MagicBulletNodeUpdateFn = int(__thiscall*)(MagicBulletNode*, unsigned int);
MagicBulletNodeUpdateFn gRealMagicBulletNodeUpdate = nullptr;
ProjectileRuntime gProjectileRuntime[kMaxTrackedProjectiles] = {};
unsigned int gProjectileSeed = 0x4E575649;

template <typename Function>
Function LoadFunction(HMODULE module, const char* name) {
    const FARPROC address = GetProcAddress(module, name);
    static_assert(sizeof(Function) == sizeof(address), "unexpected Win32 function pointer size");
    Function function = nullptr;
    memcpy(&function, &address, sizeof(function));
    return function;
}

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

bool Equals(const char* left, const char* right) {
    if (left == nullptr || right == nullptr) {
        return false;
    }
    while (*left != '\0' && *left == *right) {
        ++left;
        ++right;
    }
    return *left == *right;
}

void LogLine(const char* text) {
    HANDLE file = CreateFileA(
        "DawnWarriorSkillCompat.log",
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

bool BytesEqual(const void* address, const unsigned char* expected, SIZE_T size) {
    const auto* current = static_cast<const unsigned char*>(address);
    for (SIZE_T index = 0; index < size; ++index) {
        if (current[index] != expected[index]) {
            return false;
        }
    }
    return true;
}

bool WriteRelativeBranch(const HookSite& hook) {
    DWORD oldProtect = 0;
    auto* target = reinterpret_cast<unsigned char*>(hook.address);
    if (!VirtualProtect(target, hook.originalSize, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        return false;
    }
    const intptr_t displacement =
        reinterpret_cast<unsigned char*>(hook.replacement) - (target + 5);
    target[0] = hook.opcode;
    *reinterpret_cast<int32_t*>(target + 1) = static_cast<int32_t>(displacement);
    for (SIZE_T index = 5; index < hook.originalSize; ++index) {
        target[index] = 0x90;
    }
    FlushInstructionCache(GetCurrentProcess(), target, hook.originalSize);
    DWORD ignored = 0;
    VirtualProtect(target, hook.originalSize, oldProtect, &ignored);
    return true;
}

bool IsReadablePointer(const void* pointer) {
    if (pointer == nullptr) {
        return false;
    }
    MEMORY_BASIC_INFORMATION information = {};
    if (VirtualQuery(pointer, &information, sizeof(information)) == 0) {
        return false;
    }
    return information.State == MEM_COMMIT &&
        (information.Protect & (PAGE_NOACCESS | PAGE_GUARD)) == 0;
}

int ProjectileRandom(int minimum, int maximum) {
    gProjectileSeed = gProjectileSeed * 1103515245u + 12345u;
    const unsigned int range = static_cast<unsigned int>(maximum - minimum + 1);
    return minimum + static_cast<int>((gProjectileSeed >> 16) % range);
}

float Clamp01(float value) {
    if (value < 0.0f) {
        return 0.0f;
    }
    if (value > 1.0f) {
        return 1.0f;
    }
    return value;
}

int TriangleWave(int phase, int amplitude) {
    phase &= 1023;
    const int triangle = phase < 512 ? phase : 1024 - phase;
    return (triangle - 256) * amplitude / 256;
}

ProjectileRuntime* FindProjectileRuntime(MagicBulletNode* node) {
    for (int index = 0; index < kMaxTrackedProjectiles; ++index) {
        if (gProjectileRuntime[index].node == node) {
            return &gProjectileRuntime[index];
        }
    }
    return nullptr;
}

void ReleaseProjectileRuntime(MagicBulletNode* node) {
    ProjectileRuntime* runtime = FindProjectileRuntime(node);
    if (runtime != nullptr) {
        *runtime = {};
    }
}

ProjectileRuntime* RegisterProjectileRuntime(MagicBulletNode* node) {
    ProjectileRuntime* existing = FindProjectileRuntime(node);
    if (existing != nullptr) {
        return existing;
    }
    ProjectileRuntime* runtime = nullptr;
    for (int index = 0; index < kMaxTrackedProjectiles; ++index) {
        if (gProjectileRuntime[index].node == nullptr) {
            runtime = &gProjectileRuntime[index];
            break;
        }
    }
    if (runtime == nullptr) {
        runtime = &gProjectileRuntime[ProjectileRandom(0, kMaxTrackedProjectiles - 1)];
    }
    const int dx = node->x2 - node->x1;
    const int dy = node->y2 - node->y1;
    int length = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy);
    if (length < 1) {
        length = 1;
    }
    const int lane = static_cast<int>(gNightWalkerProjectileLane++);
    int curvePower = 0;
    if (gNightWalkerProjectileProfile == kProjectileProfileRapidThrow) {
        constexpr int kRapidThrowCurves[] = {-105, 0, 105};
        curvePower = kRapidThrowCurves[lane % 3];
    } else if (gNightWalkerProjectileProfile == kProjectileProfileSilentNight) {
        constexpr int kSilentNightCurves[] = {-120, -80, 80, 120};
        curvePower = kSilentNightCurves[lane % 4];
    } else if (gNightWalkerProjectileProfile == kProjectileProfileShadowBiteBat) {
        constexpr int kShadowBiteBatCurves[] = {-85, 85, -115, 115};
        curvePower = kShadowBiteBatCurves[lane % 4];
    }
    *runtime = {};
    runtime->node = node;
    runtime->startX = node->x1;
    runtime->startY = node->y1;
    runtime->endX = node->x2;
    runtime->endY = node->y2;
    runtime->controlX = (node->x1 + node->x2) / 2 + (-dy * curvePower / length);
    runtime->controlY = (node->y1 + node->y2) / 2 + (dx * curvePower / length);
    runtime->seed = 0;
    runtime->mode = 0;
    runtime->profile = gNightWalkerProjectileProfile;
    runtime->lane = lane;
    runtime->startTime = static_cast<unsigned int>(node->startTime);
    runtime->endTime = static_cast<unsigned int>(node->endTime);
    return runtime;
}

bool SetDispatchIntegerProperty(void* object, const wchar_t* propertyName, int value) {
    if (!IsReadablePointer(object)) {
        return false;
    }
    auto* dispatch = reinterpret_cast<IDispatch*>(object);
    LPOLESTR name = const_cast<LPOLESTR>(propertyName);
    DISPID property = DISPID_UNKNOWN;
    const IID nullIid = {};
    if (FAILED(dispatch->GetIDsOfNames(nullIid, &name, 1, LOCALE_USER_DEFAULT, &property))) {
        return false;
    }
    VARIANTARG argument = {};
    argument.vt = VT_I4;
    argument.lVal = value;
    DISPID namedArgument = DISPID_PROPERTYPUT;
    DISPPARAMS parameters = {&argument, &namedArgument, 1, 1};
    return SUCCEEDED(dispatch->Invoke(
        property,
        nullIid,
        LOCALE_USER_DEFAULT,
        DISPATCH_PROPERTYPUT,
        &parameters,
        nullptr,
        nullptr,
        nullptr));
}

void BuildProjectilePoint(const ProjectileRuntime& runtime, float rawT, int* outputX, int* outputY) {
    const float t = Clamp01(rawT);
    const float smooth = t * t * (3.0f - 2.0f * t);
    const float inverse = 1.0f - smooth;
    float x = inverse * inverse * runtime.startX +
        2.0f * inverse * smooth * runtime.controlX + smooth * smooth * runtime.endX;
    float y = inverse * inverse * runtime.startY +
        2.0f * inverse * smooth * runtime.controlY + smooth * smooth * runtime.endY;
    const int dx = runtime.endX - runtime.startX;
    const int dy = runtime.endY - runtime.startY;
    int length = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy);
    if (length < 1) {
        length = 1;
    }
    const float envelope = 4.0f * smooth * (1.0f - smooth);
    if (runtime.mode == 1 || runtime.mode == 4) {
        const int wave = static_cast<int>(TriangleWave(
            static_cast<int>(smooth * 2048.0f) + runtime.seed, 65) * envelope);
        x += static_cast<float>(-dy * wave / length);
        y += static_cast<float>(dx * wave / length);
    } else if (runtime.mode == 2) {
        const int normal = static_cast<int>(TriangleWave(
            static_cast<int>(smooth * 3072.0f) + runtime.seed, 70) * envelope);
        const int along = static_cast<int>(TriangleWave(
            static_cast<int>(smooth * 3072.0f) + runtime.seed + 256, 35) * envelope);
        x += static_cast<float>((-dy * normal + dx * along) / length);
        y += static_cast<float>((dx * normal + dy * along) / length);
    }
    if ((runtime.mode == 3 || runtime.mode == 4) && smooth > 0.60f && smooth < 0.94f) {
        const float overshoot = 1.0f - ((smooth - 0.77f) * (smooth - 0.77f) / 0.0289f);
        const int distance = static_cast<int>(90.0f * (overshoot > 0.0f ? overshoot : 0.0f));
        x += static_cast<float>(dx * distance / length);
        y += static_cast<float>(dy * distance / length);
    }
    if (rawT > 0.94f) {
        const float settle = Clamp01((rawT - 0.94f) / 0.06f);
        x = x * (1.0f - settle) + runtime.endX * settle;
        y = y * (1.0f - settle) + runtime.endY * settle;
    }
    *outputX = static_cast<int>(x);
    *outputY = static_cast<int>(y);
}

bool NightWalkerProjectileWindowActive() {
    return static_cast<LONG>(gNightWalkerProjectileWindowEnd - GetTickCount()) > 0;
}

extern "C" __attribute__((used, noinline)) void ArmNightWalkerProjectiles(int skillId) {
    DWORD duration = 0;
    switch (skillId) {
        case 14121003:
        case 14121016:
        case 14121017:
            gNightWalkerProjectileProfile = kProjectileProfileShadowBiteBat;
            duration = 2400;
            break;
        case 14121014:
        case 14121015:
            return;
        case 14121004:
            gNightWalkerProjectileProfile = kProjectileProfileRapidThrow;
            duration = 2700;
            break;
        case 14121032:
            gNightWalkerProjectileProfile = kProjectileProfileSilentNight;
            duration = 5000;
            break;
        default:
            gNightWalkerProjectileProfile = kProjectileProfileNone;
            gNightWalkerProjectileWindowEnd = 0;
            return;
    }
    gNightWalkerProjectileWindowEnd = GetTickCount() + duration;
}

int __fastcall HookMagicBulletNodeUpdate(MagicBulletNode* node, void*, unsigned int currentTime) {
    if (node != nullptr && IsReadablePointer(node) && node->layer == nullptr &&
        NightWalkerProjectileWindowActive() && FindProjectileRuntime(node) == nullptr) {
        int duration = node->endTime - node->startTime;
        if (duration > 0) {
            if (gNightWalkerProjectileProfile == kProjectileProfileShadowBiteBat) {
                if (duration < 240) {
                    duration = 240;
                } else if (duration > 900) {
                    duration = 900;
                }
            } else if (gNightWalkerProjectileProfile == kProjectileProfileSilentNight) {
                duration = duration * 6 / 5;
                if (duration < 240) {
                    duration = 240;
                } else if (duration > 1800) {
                    duration = 1800;
                }
            }
            node->endTime = node->startTime + duration;
            RegisterProjectileRuntime(node);
        }
    }
    const int result = gRealMagicBulletNodeUpdate(node, currentTime);
    ProjectileRuntime* runtime = FindProjectileRuntime(node);
    if (runtime != nullptr) {
        if (result != 0) {
            ReleaseProjectileRuntime(node);
        } else if (node->layer != nullptr && runtime->endTime > runtime->startTime) {
            const float t = static_cast<float>(currentTime - runtime->startTime) /
                static_cast<float>(runtime->endTime - runtime->startTime);
            int x = 0;
            int y = 0;
            BuildProjectilePoint(*runtime, t, &x, &y);
            SetDispatchIntegerProperty(node->layer, L"rx", x);
            SetDispatchIntegerProperty(node->layer, L"ry", y);
        }
    }
    return result;
}

bool InstallMagicBulletHook() {
    const unsigned char original[] = {0xB8, 0xDC, 0xAD, 0xA7, 0x00};
    auto* target = reinterpret_cast<unsigned char*>(kMagicBulletNodeUpdateAddress);
    if (!BytesEqual(target, original, sizeof(original))) {
        LogLine("PROJECTILE ERROR: MagicBulletNode::Update bytes do not match");
        return false;
    }
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 10, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        LogLine("PROJECTILE ERROR: trampoline allocation failed");
        return false;
    }
    memcpy(trampoline, original, sizeof(original));
    trampoline[5] = 0xE9;
    *reinterpret_cast<int32_t*>(trampoline + 6) = static_cast<int32_t>(
        (target + 5) - (trampoline + 10));
    gRealMagicBulletNodeUpdate = reinterpret_cast<MagicBulletNodeUpdateFn>(trampoline);
    const HookSite hook = {
        "Night Walker projectile trajectory",
        kMagicBulletNodeUpdateAddress,
        original,
        sizeof(original),
        reinterpret_cast<void*>(&HookMagicBulletNodeUpdate),
        0xE9,
    };
    if (!WriteRelativeBranch(hook)) {
        VirtualFree(trampoline, 0, MEM_RELEASE);
        gRealMagicBulletNodeUpdate = nullptr;
        LogLine("PROJECTILE ERROR: MagicBulletNode::Update patch failed");
        return false;
    }
    LogLine("PROJECTILE OK: Night Walker-only Bezier trajectory hook installed");
    return true;
}

bool PatchPointer(void** slot, void* replacement, void** original) {
    DWORD oldProtect = 0;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &oldProtect)) {
        return false;
    }
    if (*slot != replacement) {
        if (original != nullptr) {
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
    if (gVideoModule == nullptr) {
        gVideoModule = LoadLibraryA("BeiDouVideo.dll");
    }
    if (gVideoModule == nullptr) {
        return false;
    }
    if (gPlayFile == nullptr) {
        gPlayFile = LoadFunction<PlayFileFn>(gVideoModule, "BDV_PlayFile");
        gVideoGetLastError = LoadFunction<GetLastErrorFn>(gVideoModule, "BDV_GetLastError");
        gAttachDevice = LoadFunction<AttachDeviceFn>(gVideoModule, "BDV_AttachDevice");
        gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
        gVideoGetStatus = LoadFunction<GetStatusFn>(gVideoModule, "BDV_GetStatus");
    }
    return gPlayFile != nullptr && gVideoGetLastError != nullptr &&
        gAttachDevice != nullptr && gRender != nullptr && gVideoGetStatus != nullptr;
}

bool IsKnownVideoMarkerTexture(IDirect3DBaseTexture8* texture) {
    for (int index = 0; index < gVideoMarkerTextureCount; ++index) {
        if (gVideoMarkerTextures[index] == texture) {
            return true;
        }
    }
    return false;
}

bool MatchesVideoMarkerPixels(IDirect3DTexture8* texture, const D3DSURFACE_DESC& description) {
    D3DLOCKED_RECT locked = {};
    if (FAILED(texture->LockRect(0, &locked, nullptr, D3DLOCK_READONLY))) {
        return false;
    }
    bool matches = false;
    if (description.Format == D3DFMT_A4R4G4B4 && locked.Pitch >= 8) {
        const auto* pixels = static_cast<const uint16_t*>(locked.pBits);
        matches = pixels[0] == 0xF123 && pixels[1] == 0xF456 &&
            pixels[2] == 0xF789 && pixels[3] == 0xFABC;
    } else if (description.Format == D3DFMT_A8R8G8B8 && locked.Pitch >= 16) {
        const auto* pixels = static_cast<const uint32_t*>(locked.pBits);
        matches = pixels[0] == 0xFF112233 && pixels[1] == 0xFF445566 &&
            pixels[2] == 0xFF778899 && pixels[3] == 0xFFAABBCC;
    } else if (description.Format == D3DFMT_X8R8G8B8 && locked.Pitch >= 16) {
        const auto* pixels = static_cast<const uint32_t*>(locked.pBits);
        matches = (pixels[0] & 0x00FFFFFF) == 0x00112233 &&
            (pixels[1] & 0x00FFFFFF) == 0x00445566 &&
            (pixels[2] & 0x00FFFFFF) == 0x00778899 &&
            (pixels[3] & 0x00FFFFFF) == 0x00AABBCC;
    }
    texture->UnlockRect(0);
    return matches;
}

bool DetectVideoMarkerTexture(IDirect3DBaseTexture8* baseTexture) {
    if (baseTexture == nullptr || baseTexture->GetType() != D3DRTYPE_TEXTURE) {
        return false;
    }
    auto* texture = static_cast<IDirect3DTexture8*>(baseTexture);
    D3DSURFACE_DESC description = {};
    if (FAILED(texture->GetLevelDesc(0, &description))) {
        return false;
    }
    const bool plausibleSize =
        description.Width >= kVideoMarkerWidth && description.Width <= 8 &&
        description.Height >= kVideoMarkerHeight && description.Height <= 8;
    if (!plausibleSize || !MatchesVideoMarkerPixels(texture, description)) {
        return false;
    }
    if (gVideoMarkerTextureCount < kMaxVideoMarkerTextures) {
        baseTexture->AddRef();
        gVideoMarkerTextures[gVideoMarkerTextureCount++] = baseTexture;
    }
    LogLine("VIDEO OK: Gr2D field-layer marker texture detected");
    return true;
}

bool ConsumeVideoMarkerDraw() {
    if (gRenderingVideo || !gVideoMarkerBound) {
        return false;
    }
    if (gVideoPlaying && !gVideoRenderedThisFrame && gRender != nullptr) {
        gVideoRenderedThisFrame = true;
        gRenderingVideo = true;
        gRender();
        gRenderingVideo = false;
    }
    return true;
}

HRESULT WINAPI HookSetTexture(
    IDirect3DDevice8* device,
    DWORD stage,
    IDirect3DBaseTexture8* texture) {
    if (stage == 0 && !gRenderingVideo) {
        gVideoMarkerBound = IsKnownVideoMarkerTexture(texture) ||
            (gVideoPlaying && DetectVideoMarkerTexture(texture));
    }
    return gRealSetTexture(device, stage, texture);
}

HRESULT WINAPI HookDrawPrimitive(
    IDirect3DDevice8* device,
    D3DPRIMITIVETYPE primitiveType,
    UINT startVertex,
    UINT primitiveCount) {
    if (ConsumeVideoMarkerDraw()) {
        return D3D_OK;
    }
    return gRealDrawPrimitive(device, primitiveType, startVertex, primitiveCount);
}

HRESULT WINAPI HookDrawIndexedPrimitive(
    IDirect3DDevice8* device,
    D3DPRIMITIVETYPE primitiveType,
    UINT minIndex,
    UINT vertexCount,
    UINT startIndex,
    UINT primitiveCount) {
    if (ConsumeVideoMarkerDraw()) {
        return D3D_OK;
    }
    return gRealDrawIndexedPrimitive(
        device,
        primitiveType,
        minIndex,
        vertexCount,
        startIndex,
        primitiveCount);
}

HRESULT WINAPI HookDrawPrimitiveUp(
    IDirect3DDevice8* device,
    D3DPRIMITIVETYPE primitiveType,
    UINT primitiveCount,
    const void* data,
    UINT stride) {
    if (ConsumeVideoMarkerDraw()) {
        return D3D_OK;
    }
    return gRealDrawPrimitiveUp(device, primitiveType, primitiveCount, data, stride);
}

HRESULT WINAPI HookDrawIndexedPrimitiveUp(
    IDirect3DDevice8* device,
    D3DPRIMITIVETYPE primitiveType,
    UINT minVertexIndex,
    UINT vertexCount,
    UINT primitiveCount,
    const void* indexData,
    D3DFORMAT indexFormat,
    const void* data,
    UINT stride) {
    if (ConsumeVideoMarkerDraw()) {
        return D3D_OK;
    }
    return gRealDrawIndexedPrimitiveUp(
        device,
        primitiveType,
        minVertexIndex,
        vertexCount,
        primitiveCount,
        indexData,
        indexFormat,
        data,
        stride);
}

HRESULT WINAPI HookPresent(
    IDirect3DDevice8* device,
    const RECT* source,
    const RECT* destination,
    HWND overrideWindow,
    const RGNDATA* dirtyRegion) {
    if (!gVideoDeviceAttached && LoadVideoModule() && gAttachDevice(device)) {
        gVideoDeviceAttached = true;
        LogLine("VIDEO OK: active D3D8 device attached on first Present");
    }
    if (gVideoPlaying && gVideoGetStatus != nullptr) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (gVideoGetStatus(&status) &&
            (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR)) {
            gVideoPlaying = false;
        }
    }
    if (gVideoPlaying && !gVideoRenderedThisFrame) {
        ++gMissingMarkerFrames;
        if (!gMissingMarkerLogged && gMissingMarkerFrames >= 30) {
            LogLine("VIDEO ERROR: active video has no Gr2D field-layer marker draw");
            gMissingMarkerLogged = true;
        }
    } else {
        gMissingMarkerFrames = 0;
    }
    const HRESULT result = gRealPresent(device, source, destination, overrideWindow, dirtyRegion);
    gVideoRenderedThisFrame = false;
    gVideoMarkerBound = false;
    return result;
}

bool PatchDeviceVideoHooks(void** vtable) {
    void* original = nullptr;
    if (!PatchPointer(
            &vtable[kPresentVtableIndex],
            reinterpret_cast<void*>(&HookPresent),
            &original)) {
        return false;
    }
    if (gRealPresent == nullptr && original != nullptr) {
        gRealPresent = FunctionFromPointer<PresentFn>(original);
    }

    original = nullptr;
    if (!PatchPointer(
            &vtable[kSetTextureVtableIndex],
            reinterpret_cast<void*>(&HookSetTexture),
            &original)) {
        return false;
    }
    if (gRealSetTexture == nullptr && original != nullptr) {
        gRealSetTexture = FunctionFromPointer<SetTextureFn>(original);
    }

    original = nullptr;
    if (!PatchPointer(
            &vtable[kDrawPrimitiveVtableIndex],
            reinterpret_cast<void*>(&HookDrawPrimitive),
            &original)) {
        return false;
    }
    if (gRealDrawPrimitive == nullptr && original != nullptr) {
        gRealDrawPrimitive = FunctionFromPointer<DrawPrimitiveFn>(original);
    }

    original = nullptr;
    if (!PatchPointer(
            &vtable[kDrawIndexedPrimitiveVtableIndex],
            reinterpret_cast<void*>(&HookDrawIndexedPrimitive),
            &original)) {
        return false;
    }
    if (gRealDrawIndexedPrimitive == nullptr && original != nullptr) {
        gRealDrawIndexedPrimitive = FunctionFromPointer<DrawIndexedPrimitiveFn>(original);
    }

    original = nullptr;
    if (!PatchPointer(
            &vtable[kDrawPrimitiveUpVtableIndex],
            reinterpret_cast<void*>(&HookDrawPrimitiveUp),
            &original)) {
        return false;
    }
    if (gRealDrawPrimitiveUp == nullptr && original != nullptr) {
        gRealDrawPrimitiveUp = FunctionFromPointer<DrawPrimitiveUpFn>(original);
    }

    original = nullptr;
    if (!PatchPointer(
            &vtable[kDrawIndexedPrimitiveUpVtableIndex],
            reinterpret_cast<void*>(&HookDrawIndexedPrimitiveUp),
            &original)) {
        return false;
    }
    if (gRealDrawIndexedPrimitiveUp == nullptr && original != nullptr) {
        gRealDrawIndexedPrimitiveUp = FunctionFromPointer<DrawIndexedPrimitiveUpFn>(original);
    }

    return gRealPresent != nullptr && gRealSetTexture != nullptr &&
        gRealDrawPrimitive != nullptr && gRealDrawIndexedPrimitive != nullptr &&
        gRealDrawPrimitiveUp != nullptr && gRealDrawIndexedPrimitiveUp != nullptr;
}

bool DeviceVideoHooksReady() {
    return gRealPresent != nullptr && gRealSetTexture != nullptr &&
        gRealDrawPrimitive != nullptr && gRealDrawIndexedPrimitive != nullptr &&
        gRealDrawPrimitiveUp != nullptr && gRealDrawIndexedPrimitiveUp != nullptr;
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
    if (!PatchDeviceVideoHooks(vtable)) {
        LogLine("VIDEO ERROR: failed to hook D3D8 field-layer rendering");
        return result;
    }
    if (LoadVideoModule() && gAttachDevice(*output)) {
        gVideoDeviceAttached = true;
        LogLine("VIDEO OK: D3D8 device attached without a proxy DLL");
    } else {
        LogLine("VIDEO ERROR: BeiDouVideo.dll could not attach to D3D8");
    }
    return result;
}

IDirect3D8* WINAPI HookDirect3DCreate8(UINT sdkVersion) {
    IDirect3D8* direct3D = gRealDirect3DCreate8(sdkVersion);
    if (direct3D == nullptr) {
        return nullptr;
    }
    void** vtable = *reinterpret_cast<void***>(direct3D);
    void* original = nullptr;
    if (!PatchPointer(
            &vtable[kCreateDeviceVtableIndex],
            reinterpret_cast<void*>(&HookCreateDevice),
            &original)) {
        LogLine("VIDEO ERROR: failed to hook IDirect3D8::CreateDevice");
        return direct3D;
    }
    if (gRealCreateDevice == nullptr) {
        gRealCreateDevice = FunctionFromPointer<CreateDeviceFn>(original);
    }
    LogLine("VIDEO OK: real Direct3DCreate8 intercepted");
    return direct3D;
}

FARPROC WINAPI HookGetProcAddress(HMODULE module, LPCSTR name) {
    FARPROC address = gRealGetProcAddress(module, name);
    if (reinterpret_cast<uintptr_t>(name) > 0xFFFF && Equals(name, "Direct3DCreate8")) {
        gRealDirect3DCreate8 = FunctionFromPointer<Direct3DCreate8Fn>(reinterpret_cast<void*>(address));
        if (gRealDirect3DCreate8 != nullptr) {
            return FunctionToFarProc(&HookDirect3DCreate8);
        }
    }
    return address;
}

bool InstallGr2DHook(HMODULE module) {
    if (module == nullptr || gGr2DHookInstalled) {
        return gGr2DHookInstalled;
    }
    auto** slot = reinterpret_cast<void**>(
        reinterpret_cast<uintptr_t>(module) + kGr2DGetProcAddressIatRva);
    void* original = nullptr;
    if (!PatchPointer(slot, reinterpret_cast<void*>(&HookGetProcAddress), &original)) {
        LogLine("VIDEO ERROR: failed to patch Gr2D_DX8 GetProcAddress");
        return false;
    }
    gRealGetProcAddress = FunctionFromPointer<GetProcAddressFn>(original);
    gGr2DHookInstalled = gRealGetProcAddress != nullptr;
    if (gGr2DHookInstalled) {
        LogLine("VIDEO OK: Gr2D_DX8 hook installed");
    }
    return gGr2DHookInstalled;
}

HMODULE WINAPI HookLoadLibraryA(LPCSTR name) {
    HMODULE module = gRealLoadLibraryA(name);
    HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
    if (module != nullptr && module == gr2D) {
        InstallGr2DHook(module);
    }
    return module;
}

bool InstallLoadLibraryHook() {
    auto** slot = reinterpret_cast<void**>(kLoadLibraryAIat);
    void* original = nullptr;
    if (!PatchPointer(slot, reinterpret_cast<void*>(&HookLoadLibraryA), &original)) {
        return false;
    }
    gRealLoadLibraryA = FunctionFromPointer<LoadLibraryAFn>(original);
    HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
    if (gr2D != nullptr) {
        InstallGr2DHook(gr2D);
    }
    return gRealLoadLibraryA != nullptr;
}

bool InstallSharedVideoHooks() {
    HMODULE d3d8 = GetModuleHandleA("d3d8.dll");
    if (d3d8 == nullptr) {
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
    if (createDevice == &HookCreateDevice && gRealCreateDevice != nullptr) {
        createDevice = gRealCreateDevice;
    }

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
    const bool patched = PatchDeviceVideoHooks(deviceVtable);
    dummyDevice->Release();
    direct3D->Release();
    if (patched && DeviceVideoHooksReady()) {
        LogLine("VIDEO OK: shared D3D8 field-layer hooks installed after initialization");
        return true;
    }
    return false;
}

struct VideoSkillMapping {
    int skillId;
    const char* path;
    const char* successMessage;
};

constexpr VideoSkillMapping kVideoSkills[] = {
    {11121005, "Data\\Video\\galaxy-star-burst.mcv", "VIDEO OK: Galaxy Star Burst started"},
    {11121006, "Data\\Video\\eclipse-force.mcv", "VIDEO OK: Eclipse Force started"},
    {11121008, "Data\\Video\\soul-eclipse.mcv", "VIDEO OK: Soul Eclipse started"},
    {12121025, "Data\\Video\\eternal-phoenix.mcv", "VIDEO OK: Eternal Phoenix started"},
    {12121028, "Data\\Video\\flame-concerto.mcv", "VIDEO OK: Flame Concerto started"},
    {14121030, "Data\\Video\\dominion.mcv", "VIDEO OK: Dominion started"},
    {14121032, "Data\\Video\\silent-night.mcv", "VIDEO OK: Silent Night started"},
    {14121035, "Data\\Video\\stygian-command.mcv", "VIDEO OK: Stygian Command started"},
};

extern "C" __attribute__((used, noinline)) void StartVideoSkill(int skillId) {
    const VideoSkillMapping* mapping = nullptr;
    for (const VideoSkillMapping& candidate : kVideoSkills) {
        if (candidate.skillId == skillId) {
            mapping = &candidate;
            break;
        }
    }
    if (mapping == nullptr) {
        return;
    }
    if (!LoadVideoModule()) {
        LogLine("VIDEO ERROR: BeiDouVideo.dll was not found or incompatible");
        return;
    }
    if (!gPlayFile(mapping->path)) {
        char error[256] = "unknown video playback error";
        gVideoGetLastError(error, sizeof(error));
        LogLine(error);
        return;
    }
    gVideoPlaying = true;
    gVideoRenderedThisFrame = false;
    gMissingMarkerFrames = 0;
    gMissingMarkerLogged = false;
    LogLine(mapping->successMessage);
}

// Each naked stub preserves the register contract of the overwritten client
// instructions and returns to fixed, non-ASLR BeiDou.exe addresses.
extern "C" __attribute__((naked, noinline)) void HookKeyboardDispatch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "mov ecx, dword ptr [esi+1]\n"
        "cmp ecx, 14121003\n"
        "jb 4f\n"
        "cmp ecx, 14121036\n"
        "jbe 2f\n"
        "4:\n"
        "cmp ecx, 12121000\n"
        "jb 1f\n"
        "cmp ecx, 12121036\n"
        "jbe 2f\n"
        "1:\n"
        "cmp ecx, 11121005\n"
        "jb 3f\n"
        "cmp ecx, 11121012\n"
        "ja 3f\n"
        "cmp ecx, 11121010\n"
        "je 3f\n"
        "2:\n"
        "mov edi, 10000\n"
        "push 0x0094F9E9\n"
        "ret\n"
        "3:\n"
        "mov eax, ecx\n"
        "mov edi, 10000\n"
        "push 0x0094F8A8\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookActiveSkillDispatch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp esi, 14121003\n"
        "jb 7f\n"
        "cmp esi, 14121036\n"
        "jbe 8f\n"
        "7:\n"
        "cmp esi, 12121000\n"
        "jb 1f\n"
        "cmp esi, 12121036\n"
        "jbe 5f\n"
        "1:\n"
        "cmp esi, 11121005\n"
        "jb 2f\n"
        "cmp esi, 11121012\n"
        "ja 2f\n"
        "cmp esi, 11121010\n"
        "jne 3f\n"
        "2:\n"
        "cmp esi, 0x407\n"
        "push 0x009678FF\n"
        "ret\n"
        "3:\n"
        "cmp esi, 11121005\n"
        "je 4f\n"
        "cmp esi, 11121006\n"
        "je 4f\n"
        "cmp esi, 11121008\n"
        "jne 6f\n"
        "4:\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _StartVideoSkill\n"
        "add esp, 4\n"
        "popad\n"
        "popfd\n"
        "6:\n"
        "push 0x009690AE\n"
        "ret\n"
        "5:\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _StartVideoSkill\n"
        "add esp, 4\n"
        "popad\n"
        "popfd\n"
        "push 0x0096928B\n"
        "ret\n"
        "8:\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _StartVideoSkill\n"
        "add esp, 4\n"
        "push esi\n"
        "call _ArmNightWalkerProjectiles\n"
        "add esp, 4\n"
        "popad\n"
        "popfd\n"
        "push 0x009690E9\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookHighSkillVisualBranch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp esi, 14121003\n"
        "jb 6f\n"
        "cmp esi, 14121036\n"
        "jbe 5f\n"
        "6:\n"
        "cmp esi, 12121000\n"
        "jb 1f\n"
        "cmp esi, 12121036\n"
        "jbe 5f\n"
        "1:\n"
        "cmp esi, 11121005\n"
        "jb 3f\n"
        "cmp esi, 11121012\n"
        "ja 3f\n"
        "cmp esi, 11121010\n"
        "jne 2f\n"
        "3:\n"
        "cmp esi, 0x00989A7E\n"
        "jl 4f\n"
        "push 0x00934623\n"
        "ret\n"
        "2:\n"
        "push 0x0093465F\n"
        "ret\n"
        "4:\n"
        "push 0x0093587C\n"
        "ret\n"
        "5:\n"
        "push 0x00934623\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishActionType() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp eax, 11121005\n"
        "jb 1f\n"
        "cmp eax, 11121012\n"
        "ja 1f\n"
        "cmp eax, 11121010\n"
        "jne 2f\n"
        "1:\n"
        "cmp eax, 1121008\n"
        "je 2f\n"
        "push 0x00950DF0\n"
        "ret\n"
        "2:\n"
        "push 0x00950F74\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishVisualOffset() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp eax, 11121005\n"
        "jb 1f\n"
        "cmp eax, 11121012\n"
        "ja 1f\n"
        "cmp eax, 11121010\n"
        "jne 2f\n"
        "1:\n"
        "cmp eax, 1121008\n"
        "je 2f\n"
        "push 0x00952565\n"
        "ret\n"
        "2:\n"
        "push 0x0095262C\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishStateSwitch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp esi, 11121005\n"
        "jb 1f\n"
        "cmp esi, 11121012\n"
        "ja 1f\n"
        "cmp esi, 11121010\n"
        "jne 3f\n"
        "1:\n"
        "mov eax, 1121008\n"
        "cmp esi, eax\n"
        "jg 2f\n"
        "je 3f\n"
        "push 0x00967A1F\n"
        "ret\n"
        "2:\n"
        "push 0x00967A74\n"
        "ret\n"
        "3:\n"
        "push 0x009690AE\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishHit() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp ebx, 11121005\n"
        "jb 1f\n"
        "cmp ebx, 11121012\n"
        "ja 1f\n"
        "cmp ebx, 11121010\n"
        "jne 2f\n"
        "1:\n"
        "cmp ebx, 1121008\n"
        "je 2f\n"
        "cmp ebx, 0x00A98A5C\n"
        "jne 3f\n"
        "2:\n"
        "push 0x0078E9E6\n"
        "ret\n"
        "3:\n"
        "push 0x0078E9F3\n"
        "ret\n"
        ".att_syntax prefix\n");
}

const unsigned char kKeyboardDispatchOriginal[] = {0x8B, 0x4E, 0x01, 0x8B, 0xC1, 0xBF, 0x10, 0x27, 0x00, 0x00};
const unsigned char kActiveSkillDispatchOriginal[] = {0x81, 0xFE, 0x07, 0x04, 0x00, 0x00};
const unsigned char kHighSkillVisualOriginal[] = {0x81, 0xFE, 0x7E, 0x9A, 0x98, 0x00, 0x0F, 0x8C, 0x59, 0x12, 0x00, 0x00};
const unsigned char kActionTypeOriginal[] = {0x3D, 0xF0, 0x1A, 0x11, 0x00, 0x0F, 0x84, 0x84, 0x01, 0x00, 0x00};
const unsigned char kVisualOffsetOriginal[] = {0x3D, 0xF0, 0x1A, 0x11, 0x00, 0x0F, 0x84, 0xC7, 0x00, 0x00, 0x00};
const unsigned char kStateSwitchOriginal[] = {0xB8, 0xF0, 0x1A, 0x11, 0x00, 0x3B, 0xF0, 0x7F, 0x5B, 0x0F, 0x84, 0x8F, 0x16, 0x00, 0x00};
const unsigned char kHitOriginal[] = {0x81, 0xFB, 0xF0, 0x1A, 0x11, 0x00, 0x74, 0x08, 0x81, 0xFB, 0x5C, 0x8A, 0xA9, 0x00, 0x75, 0x0D};

HookSite kHooks[] = {
    {"keyboard active-skill dispatch", 0x0094F89E, kKeyboardDispatchOriginal, sizeof(kKeyboardDispatchOriginal), reinterpret_cast<void*>(&HookKeyboardDispatch), 0xE9},
    {"DoActiveSkill custom dispatch", 0x009678F9, kActiveSkillDispatchOriginal, sizeof(kActiveSkillDispatchOriginal), reinterpret_cast<void*>(&HookActiveSkillDispatch), 0xE9},
    {"high-ID Brandish visual branch", 0x00934617, kHighSkillVisualOriginal, sizeof(kHighSkillVisualOriginal), reinterpret_cast<void*>(&HookHighSkillVisualBranch), 0xE9},
    {"Brandish action type", 0x00950DE5, kActionTypeOriginal, sizeof(kActionTypeOriginal), reinterpret_cast<void*>(&HookBrandishActionType), 0xE9},
    {"Brandish visual offset", 0x0095255A, kVisualOffsetOriginal, sizeof(kVisualOffsetOriginal), reinterpret_cast<void*>(&HookBrandishVisualOffset), 0xE9},
    {"Brandish state switch", 0x00967A10, kStateSwitchOriginal, sizeof(kStateSwitchOriginal), reinterpret_cast<void*>(&HookBrandishStateSwitch), 0xE9},
    {"Brandish hit", 0x0078E9D6, kHitOriginal, sizeof(kHitOriginal), reinterpret_cast<void*>(&HookBrandishHit), 0xE9},
};

DWORD WINAPI InstallHooks(LPVOID) {
    LogLine("LOAD: Dawn Warrior/Blaze Wizard/Night Walker Skill Compat v15");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("ERROR: unexpected BeiDou.exe image base; no hooks installed");
        return 1;
    }
    for (const HookSite& hook : kHooks) {
        if (!BytesEqual(reinterpret_cast<const void*>(hook.address), hook.original, hook.originalSize)) {
            LogLine("ERROR: hook bytes do not match this BeiDou.exe; no hooks installed");
            return 2;
        }
    }
    for (const HookSite& hook : kHooks) {
        if (!WriteRelativeBranch(hook)) {
            LogLine("ERROR: VirtualProtect/write failed while installing hooks");
            return 3;
        }
    }
    LogLine("OK: unified skill compat v15 hooks installed (melee/magic/ranged dispatch)");
    InstallMagicBulletHook();
    for (int attempt = 0; attempt < kVideoHookRetryCount && !DeviceVideoHooksReady(); ++attempt) {
        HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
        if (gr2D != nullptr) {
            InstallGr2DHook(gr2D);
        }
        if (InstallSharedVideoHooks()) {
            break;
        }
        Sleep(kVideoHookRetryMilliseconds);
    }
    if (!DeviceVideoHooksReady()) {
        LogLine("VIDEO ERROR: no complete D3D8 field-layer hooks were installed within 30 seconds");
    }
    return 0;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InstallLoadLibraryHook();
        HANDLE thread = CreateThread(nullptr, 0, InstallHooks, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
