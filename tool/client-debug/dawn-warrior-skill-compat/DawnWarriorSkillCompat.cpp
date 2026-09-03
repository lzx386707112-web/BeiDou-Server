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
constexpr int kFirstSkill = 11121005;
constexpr int kLastSkill = 11121012;
constexpr UINT kVideoMarkerWidth = 7;
constexpr UINT kVideoMarkerHeight = 5;
constexpr int kMaxVideoMarkerTextures = 64;
constexpr uintptr_t kMagicBulletNodeUpdateAddress = 0x00441090;
constexpr uintptr_t kMagicBulletManagerAddress = 0x00BEBF6C;
constexpr uintptr_t kMagicBulletCreateAddress = 0x00435F47;
constexpr uintptr_t kZtlBstrFromWideAddress = 0x00403382;
constexpr uintptr_t kRangedSkillRangeClassifierAddress = 0x007666CB;
constexpr uintptr_t kRangedMultiTargetClassifierAddress = 0x00766722;
constexpr uintptr_t kRangedTargetCollectorAddress = 0x00678476;
constexpr uintptr_t kMobGetBodyRectAddress = 0x00664559;
constexpr uintptr_t kRangedProjectileDestinationAddress = 0x00954596;
constexpr int kShadowBiteProjectileTravelMilliseconds = 660;
constexpr DWORD kRapidThrowImpactDedupMilliseconds = 80;
constexpr int kNightWalkerFirstSkill = 14121003;
constexpr int kNightWalkerLastSkill = 14121036;
constexpr int kWindArcherFirstSkill = 13121003;
constexpr int kWindArcherLastSkill = 13121023;
constexpr int kThunderBreakerFirstSkill = 15121000;
constexpr int kThunderBreakerLastSkill = 15121033;
constexpr int kMaxTrackedProjectiles = 256;

using PlayFileFn = int(__stdcall*)(const char*);
using PlayFileExFn = int(__stdcall*)(uint32_t, const char*);
using GetLastErrorFn = void(__stdcall*)(char*, uint32_t);
using GetLastErrorExFn = void(__stdcall*)(uint32_t, char*, uint32_t);
using AttachDeviceFn = int(__stdcall*)(void*);
using RenderFn = void(__stdcall*)();
using GetStatusFn = int(__stdcall*)(BdvStatus*);
using GetStatusExFn = int(__stdcall*)(uint32_t, BdvStatus*);
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
PlayFileExFn gPlayFileEx = nullptr;
GetLastErrorFn gVideoGetLastError = nullptr;
GetLastErrorExFn gVideoGetLastErrorEx = nullptr;
AttachDeviceFn gAttachDevice = nullptr;
RenderFn gRender = nullptr;
GetStatusFn gVideoGetStatus = nullptr;
GetStatusExFn gVideoGetStatusEx = nullptr;
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
bool gBossSceneVideoPlaying = false;
bool gVideoMarkerBound = false;
int gVideoMarkerBoundCode = 0;
bool gVideoRenderedThisFrame = false;
bool gRenderingVideo = false;
bool gMissingMarkerLogged = false;
DWORD gMissingMarkerFrames = 0;
volatile LONG gPendingVideoSkillId = 0;
IDirect3DBaseTexture8* gVideoMarkerTextures[kMaxVideoMarkerTextures] = {};
int gVideoMarkerTextureCodes[kMaxVideoMarkerTextures] = {};
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
    int rapidThrowSkillId;
    unsigned int startTime;
    unsigned int endTime;
};

struct ProjectileTarget {
    int x;
    int y;
};

struct PendingRapidThrowImpact {
    volatile LONG state;
    IUnknown* origin;
    unsigned int startTime;
    int x;
    int y;
    int z;
    int skillId;
    int duration;
};

struct RecentRapidThrowImpact {
    IUnknown* origin;
    int skillId;
    DWORD time;
};

using MagicBulletNodeUpdateFn = int(__thiscall*)(MagicBulletNode*, unsigned int);
MagicBulletNodeUpdateFn gRealMagicBulletNodeUpdate = nullptr;
using RangedMultiTargetClassifierFn = int(__cdecl*)(int);
RangedMultiTargetClassifierFn gRealRangedMultiTargetClassifier = nullptr;
RangedMultiTargetClassifierFn gRealRangedSkillRangeClassifier = nullptr;
using RangedTargetCollectorFn = int(__thiscall*)(
    void*, void*, void**, int, void*, void*, void*, void*, void*);
RangedTargetCollectorFn gRealRangedTargetCollector = nullptr;
using MobGetBodyRectFn = int(__thiscall*)(void*, RECT*, int);
using MagicBulletCreateFn = void(__thiscall*)(
    void*, unsigned int, unsigned int, int, int, int, int,
    IUnknown*, int, void*, int);
using ZtlBstrFromWideFn = void*(__thiscall*)(void**, const wchar_t*);
volatile LONG gShadowBiteClassifierObserved = 0;
volatile LONG gShadowBiteRangeClassifierObserved = 0;
volatile LONG gCustomRangedTargetLimit = 0;
ProjectileRuntime gProjectileRuntime[kMaxTrackedProjectiles] = {};
unsigned int gProjectileSeed = 0x4E575649;
void* gProjectileLayerVtable = nullptr;
DISPID gProjectileRxProperty = DISPID_UNKNOWN;
DISPID gProjectileRyProperty = DISPID_UNKNOWN;
bool gProjectilePropertyLookupAttempted = false;
volatile LONG gProjectileMoveObserved = 0;
volatile LONG gProjectileLoggedNodes = 0;
ProjectileTarget gProjectileTargets[15] = {};
volatile LONG gProjectileTargetCount = 0;
volatile LONG gProjectileTargetIndex = 0;
DWORD gProjectileTargetWindowEnd = 0;
volatile LONG gNativeRangedProjectileIndex = 0;
volatile LONG gNativeRangedProjectileLogged = 0;
DWORD gNativeRangedProjectileWindowEnd = 0;
constexpr int kMaxPendingRapidThrowImpacts = 64;
PendingRapidThrowImpact gPendingRapidThrowImpacts[kMaxPendingRapidThrowImpacts] = {};
RecentRapidThrowImpact gRecentRapidThrowImpacts[kMaxPendingRapidThrowImpacts] = {};
void* gProjectileOriginVtable = nullptr;
DISPID gProjectileOriginRxProperty = DISPID_UNKNOWN;
DISPID gProjectileOriginRyProperty = DISPID_UNKNOWN;
bool gProjectileOriginPropertyLookupAttempted = false;
volatile LONG gRapidThrowImpactQueuedObserved = 0;
volatile LONG gRapidThrowImpactCreatedObserved = 0;
volatile LONG gRapidThrowImpactErrorObserved = 0;
bool gRapidThrowImpactSupportReady = false;

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

bool WideContains(const wchar_t* text, const wchar_t* needle) {
    if (text == nullptr || needle == nullptr || *needle == L'\0') {
        return false;
    }
    for (const wchar_t* candidate = text; *candidate != L'\0'; ++candidate) {
        const wchar_t* left = candidate;
        const wchar_t* right = needle;
        while (*left != L'\0' && *right != L'\0' && *left == *right) {
            ++left;
            ++right;
        }
        if (*right == L'\0') {
            return true;
        }
    }
    return false;
}

const wchar_t* MagicBulletResourcePath(const MagicBulletNode* node) {
    if (node == nullptr || !IsReadablePointer(node->bstrData)) {
        return nullptr;
    }
    const auto* data = static_cast<const void* const*>(node->bstrData);
    const auto* path = static_cast<const wchar_t*>(*data);
    return IsReadablePointer(path) ? path : nullptr;
}

int RapidThrowSkillFromBullet(const MagicBulletNode* node) {
    const wchar_t* path = MagicBulletResourcePath(node);
    if (path == nullptr || WideContains(path, L"/hit/")) {
        return 0;
    }
    if (WideContains(path, L"14121005")) return 14121005;
    if (WideContains(path, L"14121006")) return 14121006;
    if (WideContains(path, L"14121007")) return 14121007;
    if (WideContains(path, L"14121008")) return 14121008;
    return 0;
}

bool IsRapidThrowImpactNode(const MagicBulletNode* node) {
    const wchar_t* path = MagicBulletResourcePath(node);
    return path != nullptr && WideContains(path, L"/hit/") &&
        (WideContains(path, L"14121005") ||
         WideContains(path, L"14121006") ||
         WideContains(path, L"14121007") ||
         WideContains(path, L"14121008"));
}

const wchar_t* RapidThrowImpactPath(int skillId) {
    switch (skillId) {
        case 14121005: return L"Skill/1412.img/skill/14121005/hit/0";
        case 14121006: return L"Skill/1412.img/skill/14121006/hit/0";
        case 14121007: return L"Skill/1412.img/skill/14121007/hit/0";
        case 14121008: return L"Skill/1412.img/skill/14121008/hit/0";
        default: return nullptr;
    }
}

int RapidThrowImpactDuration(int skillId) {
    return skillId == 14121005 ? 660 : 600;
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
        constexpr int kShadowBiteBatCurves[] = {-180, 180, -240, 240};
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
    runtime->rapidThrowSkillId = gNightWalkerProjectileProfile == kProjectileProfileRapidThrow
        ? RapidThrowSkillFromBullet(node)
        : 0;
    runtime->startTime = static_cast<unsigned int>(node->startTime);
    runtime->endTime = static_cast<unsigned int>(node->endTime);
    const LONG loggedNode = InterlockedIncrement(&gProjectileLoggedNodes);
    if (loggedNode <= 6) {
        char message[160] = {};
        wsprintfA(
            message,
            "PROJECTILE NODE: index=%ld start=(%d,%d) end=(%d,%d)",
            loggedNode,
            node->x1,
            node->y1,
            node->x2,
            node->y2);
        LogLine(message);
    }
    return runtime;
}

bool ResolveProjectileLayerProperties(void* object) {
    if (!IsReadablePointer(object)) {
        return false;
    }
    void* vtable = *reinterpret_cast<void**>(object);
    if (!IsReadablePointer(vtable)) {
        return false;
    }
    if (vtable == gProjectileLayerVtable && gProjectilePropertyLookupAttempted) {
        return gProjectileRxProperty != DISPID_UNKNOWN &&
            gProjectileRyProperty != DISPID_UNKNOWN;
    }
    gProjectileLayerVtable = vtable;
    gProjectilePropertyLookupAttempted = true;
    gProjectileRxProperty = DISPID_UNKNOWN;
    gProjectileRyProperty = DISPID_UNKNOWN;
    auto* dispatch = reinterpret_cast<IDispatch*>(object);
    LPOLESTR rxName = const_cast<LPOLESTR>(L"rx");
    LPOLESTR ryName = const_cast<LPOLESTR>(L"ry");
    const IID nullIid = {};
    if (FAILED(dispatch->GetIDsOfNames(
            nullIid, &rxName, 1, LOCALE_USER_DEFAULT, &gProjectileRxProperty)) ||
        FAILED(dispatch->GetIDsOfNames(
            nullIid, &ryName, 1, LOCALE_USER_DEFAULT, &gProjectileRyProperty))) {
        return false;
    }
    return true;
}

bool PutDispatchIntegerProperty(IDispatch* dispatch, DISPID property, int value) {
    const IID nullIid = {};
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

bool SetProjectileLayerPosition(void* object, int x, int y) {
    if (!ResolveProjectileLayerProperties(object)) {
        return false;
    }
    auto* dispatch = reinterpret_cast<IDispatch*>(object);
    return PutDispatchIntegerProperty(dispatch, gProjectileRxProperty, x) &&
        PutDispatchIntegerProperty(dispatch, gProjectileRyProperty, y);
}

bool ResolveProjectileOriginProperties(void* object) {
    if (!IsReadablePointer(object)) {
        return false;
    }
    void* vtable = *reinterpret_cast<void**>(object);
    if (!IsReadablePointer(vtable)) {
        return false;
    }
    if (vtable == gProjectileOriginVtable && gProjectileOriginPropertyLookupAttempted) {
        return gProjectileOriginRxProperty != DISPID_UNKNOWN &&
            gProjectileOriginRyProperty != DISPID_UNKNOWN;
    }
    gProjectileOriginVtable = vtable;
    gProjectileOriginPropertyLookupAttempted = true;
    gProjectileOriginRxProperty = DISPID_UNKNOWN;
    gProjectileOriginRyProperty = DISPID_UNKNOWN;
    auto* dispatch = reinterpret_cast<IDispatch*>(object);
    LPOLESTR rxName = const_cast<LPOLESTR>(L"rx");
    LPOLESTR ryName = const_cast<LPOLESTR>(L"ry");
    const IID nullIid = {};
    if (FAILED(dispatch->GetIDsOfNames(
            nullIid, &rxName, 1, LOCALE_USER_DEFAULT, &gProjectileOriginRxProperty)) ||
        FAILED(dispatch->GetIDsOfNames(
            nullIid, &ryName, 1, LOCALE_USER_DEFAULT, &gProjectileOriginRyProperty))) {
        return false;
    }
    return true;
}

bool GetDispatchIntegerProperty(IDispatch* dispatch, DISPID property, int* value) {
    if (dispatch == nullptr || value == nullptr || property == DISPID_UNKNOWN) {
        return false;
    }
    const IID nullIid = {};
    DISPPARAMS parameters = {};
    VARIANT result = {};
    if (FAILED(dispatch->Invoke(
            property,
            nullIid,
            LOCALE_USER_DEFAULT,
            DISPATCH_PROPERTYGET,
            &parameters,
            &result,
            nullptr,
            nullptr))) {
        return false;
    }
    switch (result.vt) {
        case VT_I2:
            *value = result.iVal;
            return true;
        case VT_I4:
        case VT_INT:
            *value = result.lVal;
            return true;
        case VT_UI2:
            *value = result.uiVal;
            return true;
        case VT_UI4:
        case VT_UINT:
            *value = static_cast<int>(result.ulVal);
            return true;
        case VT_R4:
            *value = static_cast<int>(result.fltVal);
            return true;
        case VT_R8:
            *value = static_cast<int>(result.dblVal);
            return true;
        default:
            return false;
    }
}

bool GetProjectileOriginPosition(IUnknown* origin, int* x, int* y) {
    if (!ResolveProjectileOriginProperties(origin)) {
        return false;
    }
    auto* dispatch = reinterpret_cast<IDispatch*>(origin);
    return GetDispatchIntegerProperty(dispatch, gProjectileOriginRxProperty, x) &&
        GetDispatchIntegerProperty(dispatch, gProjectileOriginRyProperty, y);
}

bool RememberRapidThrowImpact(IUnknown* origin, int skillId, DWORD now) {
    if (origin == nullptr) {
        return true;
    }
    int replacement = 0;
    DWORD replacementAge = 0;
    for (int index = 0; index < kMaxPendingRapidThrowImpacts; ++index) {
        RecentRapidThrowImpact& recent = gRecentRapidThrowImpacts[index];
        const DWORD age = now - recent.time;
        if (recent.origin == origin && recent.skillId == skillId &&
            age < kRapidThrowImpactDedupMilliseconds) {
            return false;
        }
        if (recent.origin == nullptr || age >= replacementAge) {
            replacement = index;
            replacementAge = age;
        }
    }
    gRecentRapidThrowImpacts[replacement].origin = origin;
    gRecentRapidThrowImpacts[replacement].skillId = skillId;
    gRecentRapidThrowImpacts[replacement].time = now;
    return true;
}

void QueueRapidThrowImpact(
    const ProjectileRuntime& runtime,
    MagicBulletNode* node,
    unsigned int currentTime) {
    if (!gRapidThrowImpactSupportReady || runtime.rapidThrowSkillId == 0 || node == nullptr ||
        RapidThrowImpactPath(runtime.rapidThrowSkillId) == nullptr) {
        return;
    }
    const DWORD now = GetTickCount();
    if (!RememberRapidThrowImpact(node->origin, runtime.rapidThrowSkillId, now)) {
        return;
    }
    int absoluteX = runtime.endX;
    int absoluteY = runtime.endY;
    int originX = 0;
    int originY = 0;
    if (node->origin != nullptr &&
        GetProjectileOriginPosition(node->origin, &originX, &originY)) {
        absoluteX += originX;
        absoluteY += originY;
    } else {
        const LONG targetCount = InterlockedCompareExchange(&gProjectileTargetCount, 0, 0);
        if (targetCount > 0 &&
            static_cast<LONG>(gProjectileTargetWindowEnd - now) > 0) {
            const LONG targetIndex = runtime.lane % targetCount;
            absoluteX = gProjectileTargets[targetIndex].x;
            absoluteY = gProjectileTargets[targetIndex].y;
        } else if (node->origin != nullptr) {
            if (InterlockedCompareExchange(&gRapidThrowImpactErrorObserved, 1, 0) == 0) {
                LogLine("RAPID THROW HIT ERROR: target origin position unavailable");
            }
            return;
        }
    }
    for (int index = 0; index < kMaxPendingRapidThrowImpacts; ++index) {
        PendingRapidThrowImpact& pending = gPendingRapidThrowImpacts[index];
        if (InterlockedCompareExchange(&pending.state, 1, 0) != 0) {
            continue;
        }
        pending.origin = node->origin;
        if (pending.origin != nullptr) {
            pending.origin->AddRef();
        }
        pending.startTime = currentTime;
        pending.x = absoluteX;
        pending.y = absoluteY;
        pending.z = node->a8;
        pending.skillId = runtime.rapidThrowSkillId;
        pending.duration = RapidThrowImpactDuration(runtime.rapidThrowSkillId);
        InterlockedExchange(&pending.state, 2);
        if (InterlockedCompareExchange(&gRapidThrowImpactQueuedObserved, 1, 0) == 0) {
            LogLine("RAPID THROW HIT QUEUED: arrival-synced impact animation ready");
        }
        return;
    }
    if (InterlockedCompareExchange(&gRapidThrowImpactErrorObserved, 1, 0) == 0) {
        LogLine("RAPID THROW HIT ERROR: impact queue is full");
    }
}

void DrainRapidThrowImpacts() {
    if (!gRapidThrowImpactSupportReady) {
        return;
    }
    auto** managerSlot = reinterpret_cast<void**>(kMagicBulletManagerAddress);
    if (!IsReadablePointer(managerSlot) || !IsReadablePointer(*managerSlot)) {
        return;
    }
    const auto createBullet = reinterpret_cast<MagicBulletCreateFn>(kMagicBulletCreateAddress);
    const auto constructBstr = reinterpret_cast<ZtlBstrFromWideFn>(kZtlBstrFromWideAddress);
    for (int index = 0; index < kMaxPendingRapidThrowImpacts; ++index) {
        PendingRapidThrowImpact& pending = gPendingRapidThrowImpacts[index];
        if (InterlockedCompareExchange(&pending.state, 3, 2) != 2) {
            continue;
        }
        const wchar_t* path = RapidThrowImpactPath(pending.skillId);
        if (path != nullptr) {
            void* pathData = nullptr;
            constructBstr(&pathData, path);
            if (pathData != nullptr) {
                createBullet(
                    *managerSlot,
                    pending.startTime,
                    pending.startTime + pending.duration,
                    pending.x,
                    pending.y,
                    pending.x,
                    pending.y,
                    pending.origin,
                    pending.z,
                    pathData,
                    0);
                if (InterlockedCompareExchange(
                        &gRapidThrowImpactCreatedObserved, 1, 0) == 0) {
                    LogLine("RAPID THROW HIT OK: impact MagicBullet created at target");
                }
            }
        }
        if (pending.origin != nullptr) {
            pending.origin->Release();
        }
        pending.origin = nullptr;
        InterlockedExchange(&pending.state, 0);
    }
}

bool EnableRapidThrowImpactSupport() {
    const unsigned char createOriginal[] = {0xB8, 0xD0, 0x95, 0xA7, 0x00};
    const unsigned char bstrOriginal[] = {0x56, 0xFF, 0x74, 0x24, 0x08};
    if (!BytesEqual(
            reinterpret_cast<const void*>(kMagicBulletCreateAddress),
            createOriginal,
            sizeof(createOriginal)) ||
        !BytesEqual(
            reinterpret_cast<const void*>(kZtlBstrFromWideAddress),
            bstrOriginal,
            sizeof(bstrOriginal))) {
        LogLine("RAPID THROW HIT ERROR: internal MagicBullet creator bytes do not match");
        return false;
    }
    gRapidThrowImpactSupportReady = true;
    LogLine("RAPID THROW HIT OK: arrival-synced impact creator enabled");
    return true;
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
        case 13121003:
            gNightWalkerProjectileProfile = kProjectileProfileNone;
            gNightWalkerProjectileWindowEnd = 0;
            gNativeRangedProjectileWindowEnd = GetTickCount() + 1200;
            return;
        case 14121003:
            gNightWalkerProjectileProfile = kProjectileProfileNone;
            gNightWalkerProjectileWindowEnd = 0;
            gNativeRangedProjectileWindowEnd = GetTickCount() + 2400;
            return;
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
            gNativeRangedProjectileWindowEnd = 0;
            return;
    }
    gNativeRangedProjectileWindowEnd = 0;
    gNightWalkerProjectileWindowEnd = GetTickCount() + duration;
}

extern "C" __attribute__((used, noinline)) void AssignNativeRangedProjectileTarget(
    int* targetX,
    int* targetY,
    int* travelMilliseconds) {
    if (targetX == nullptr || targetY == nullptr || travelMilliseconds == nullptr ||
        static_cast<LONG>(gNativeRangedProjectileWindowEnd - GetTickCount()) <= 0 ||
        static_cast<LONG>(gProjectileTargetWindowEnd - GetTickCount()) <= 0) {
        return;
    }
    const LONG targetCount = InterlockedCompareExchange(&gProjectileTargetCount, 0, 0);
    if (targetCount <= 0) {
        return;
    }
    const LONG projectileIndex = InterlockedIncrement(&gNativeRangedProjectileIndex) - 1;
    const LONG targetIndex = projectileIndex % targetCount;
    *targetX = gProjectileTargets[targetIndex].x;
    *targetY = gProjectileTargets[targetIndex].y;
    if (*travelMilliseconds > kShadowBiteProjectileTravelMilliseconds) {
        *travelMilliseconds = kShadowBiteProjectileTravelMilliseconds;
    }
    const LONG logged = InterlockedIncrement(&gNativeRangedProjectileLogged);
    if (logged <= 6) {
        char message[160] = {};
        wsprintfA(
            message,
            "RANGED PROJECTILE: index=%ld target=%ld/%ld end=(%d,%d) travel=%dms",
            projectileIndex,
            targetIndex + 1,
            targetCount,
            *targetX,
            *targetY,
            *travelMilliseconds);
        LogLine(message);
    }
}

extern "C" __attribute__((naked, noinline)) void HookNativeRangedProjectileDestination() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "mov dword ptr [ebp-0x24], eax\n"
        "pushfd\n"
        "pushad\n"
        "lea eax, [ebp-0x2c]\n"
        "push eax\n"
        "lea eax, [ebp-0x24]\n"
        "push eax\n"
        "lea eax, [ebp-0x28]\n"
        "push eax\n"
        "call _AssignNativeRangedProjectileTarget\n"
        "add esp, 12\n"
        "popad\n"
        "popfd\n"
        "jne 1f\n"
        "push 0x0095459F\n"
        "ret\n"
        "1:\n"
        "push 0x009546AC\n"
        "ret\n"
        ".att_syntax prefix\n");
}

bool InstallNativeRangedProjectileHook() {
    const unsigned char original[] = {
        0x89, 0x45, 0xDC,
        0x0F, 0x85, 0x0D, 0x01, 0x00, 0x00,
    };
    const HookSite hook = {
        "Shared native ranged projectile destination",
        kRangedProjectileDestinationAddress,
        original,
        sizeof(original),
        reinterpret_cast<void*>(&HookNativeRangedProjectileDestination),
        0xE9,
    };
    if (!BytesEqual(reinterpret_cast<const void*>(hook.address), original, sizeof(original))) {
        LogLine("RANGED PROJECTILE ERROR: destination bytes do not match");
        return false;
    }
    if (!WriteRelativeBranch(hook)) {
        LogLine("RANGED PROJECTILE ERROR: destination patch failed");
        return false;
    }
    LogLine("RANGED PROJECTILE OK: native per-target destination hook installed");
    return true;
}

int __fastcall HookMagicBulletNodeUpdate(MagicBulletNode* node, void*, unsigned int currentTime) {
    if (node != nullptr && IsReadablePointer(node) && node->layer == nullptr &&
        NightWalkerProjectileWindowActive() && FindProjectileRuntime(node) == nullptr &&
        !IsRapidThrowImpactNode(node)) {
        int duration = node->endTime - node->startTime;
        if (duration > 0) {
            if (gNightWalkerProjectileProfile == kProjectileProfileShadowBiteBat) {
                const LONG targetCount = InterlockedCompareExchange(
                    &gProjectileTargetCount, 0, 0);
                if (targetCount > 0 &&
                    static_cast<LONG>(gProjectileTargetWindowEnd - GetTickCount()) > 0) {
                    const LONG targetIndex = InterlockedIncrement(&gProjectileTargetIndex) - 1;
                    if (targetIndex >= 0 && targetIndex < targetCount) {
                        node->x2 = gProjectileTargets[targetIndex].x;
                        node->y2 = gProjectileTargets[targetIndex].y;
                    }
                }
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
            QueueRapidThrowImpact(*runtime, node, currentTime);
            ReleaseProjectileRuntime(node);
        } else if (node->layer != nullptr && runtime->endTime > runtime->startTime) {
            const float t = static_cast<float>(currentTime - runtime->startTime) /
                static_cast<float>(runtime->endTime - runtime->startTime);
            int x = 0;
            int y = 0;
            BuildProjectilePoint(*runtime, t, &x, &y);
            const bool moved = SetProjectileLayerPosition(node->layer, x, y);
            if (InterlockedCompareExchange(&gProjectileMoveObserved, 1, 0) == 0) {
                LogLine(moved
                    ? "PROJECTILE MOVE OK: cached rx/ry updates active"
                    : "PROJECTILE MOVE ERROR: layer rx/ry update failed");
            }
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

LONG CustomRangedTargetLimit(int skillId) {
    switch (skillId) {
        case 3121010: return 10;
        case 3121011: return 1;
        case 3121013: return 6;
        case 3121015: return 1;
        case 3121020: return 1;
        case 3121022: return 8;
        case 3121024: return 4;
        case 3121025: return 6;
        case 3121026: return 5;
        case 3121028: return 12;
        case 3121029: return 15;
        case 3121031: return 15;
        case 3221009: return 12;
        case 3221011: return 10;
        case 3221013: return 10;
        case 3221014: return 1;
        case 3221016: return 1;
        case 3221017: return 1;
        case 3221022: return 8;
        case 3221029: return 6;
        case 3221030: return 8;
        case 3221031: return 12;
        case 3221032: return 15;
        case 3221034: return 15;
        case 4121010: return 1;
        case 4121011: return 6;
        case 4121012: return 7;
        case 4121013: return 8;
        case 4121015: return 1;
        case 4121016: return 4;
        case 4121019: return 6;
        case 4121021: return 1;
        case 4121022: return 15;
        case 4121023: return 8;
        case 4121026: return 15;
        case 4121028: return 15;
        case 5221011: return 15;
        case 5221012: return 12;
        case 5221013: return 15;
        case 5221016: return 7;
        case 5221018: return 4;
        case 5221020: return 6;
        case 5221022: return 4;
        case 5221024: return 8;
        case 5221028: return 1;
        case 5221029: return 15;
        case 5221030: return 15;
        case 5221032: return 15;
        case 5221034: return 15;
        case 14121003: return 10;
        case 14121016: return 3;
        case 14121017: return 1;
        case 13121003: return 10;
        case 13121004: return 3;
        case 13121009: return 7;
        case 13121010: return 15;
        case 13121011: return 12;
        case 13121013: return 15;
        case 13121019: return 15;
        default: return 0;
    }
}

bool IsExplorerRangedSkill(int skillId) {
    return (skillId >= 3121010 && skillId <= 3121032) ||
        (skillId >= 3221009 && skillId <= 3221035) ||
        (skillId >= 4121010 && skillId <= 4121029) ||
        (skillId >= 5221011 && skillId <= 5221035);
}

bool IsCustomRangedSkill(int skillId) {
    return CustomRangedTargetLimit(skillId) > 0 ||
        IsExplorerRangedSkill(skillId) ||
        (skillId >= kWindArcherFirstSkill && skillId <= kWindArcherLastSkill);
}

int __cdecl HookRangedMultiTargetClassifier(int skillId) {
    const LONG targetLimit = CustomRangedTargetLimit(skillId);
    if (targetLimit > 0) {
        InterlockedExchange(&gCustomRangedTargetLimit, targetLimit);
        if (skillId == 14121003 &&
            InterlockedCompareExchange(&gShadowBiteClassifierObserved, 1, 0) == 0) {
            LogLine("RANGED TARGET HIT: Shadow Bite classified as native multi-target");
        }
        return 1;
    }
    InterlockedExchange(&gCustomRangedTargetLimit, 0);
    return gRealRangedMultiTargetClassifier(skillId);
}

int __cdecl HookRangedSkillRangeClassifier(int skillId) {
    if (IsCustomRangedSkill(skillId)) {
        if (skillId == 14121003 &&
            InterlockedCompareExchange(&gShadowBiteRangeClassifierObserved, 1, 0) == 0) {
            LogLine("RANGED RANGE HIT: Shadow Bite uses its skill lt/rb bounds");
        }
        return 1;
    }
    return gRealRangedSkillRangeClassifier(skillId);
}

void CaptureProjectileTargets(void** targets, int targetCount) {
    InterlockedExchange(&gProjectileTargetCount, 0);
    InterlockedExchange(&gProjectileTargetIndex, 0);
    InterlockedExchange(&gNativeRangedProjectileIndex, 0);
    gNightWalkerProjectileLane = 0;
    if (targets == nullptr || targetCount <= 0) {
        gProjectileTargetWindowEnd = 0;
        return;
    }
    const auto getBodyRect = reinterpret_cast<MobGetBodyRectFn>(kMobGetBodyRectAddress);
    int captured = 0;
    for (int index = 0; index < targetCount && captured < 15; ++index) {
        void* monster = targets[index];
        if (!IsReadablePointer(monster)) {
            continue;
        }
        RECT body = {};
        if (getBodyRect(monster, &body, 1) == 0) {
            continue;
        }
        gProjectileTargets[captured].x = (body.left + body.right) / 2;
        gProjectileTargets[captured].y = (body.top + body.bottom) / 2;
        ++captured;
    }
    InterlockedExchange(&gProjectileTargetCount, captured);
    gProjectileTargetWindowEnd = captured > 0 ? GetTickCount() + 2400 : 0;
    char message[96] = {};
    wsprintfA(message, "PROJECTILE TARGETS: captured=%d", captured);
    LogLine(message);
}

int __fastcall HookRangedTargetCollector(
    void* self,
    void*,
    void* bounds,
    void** targets,
    int maxTargets,
    void* filter1,
    void* filter2,
    void* filter3,
    void* filter4,
    void* filter5) {
    const LONG forcedLimit = InterlockedExchange(&gCustomRangedTargetLimit, 0);
    if (forcedLimit > 0) {
        maxTargets = forcedLimit;
    }
    const int result = gRealRangedTargetCollector(
        self, bounds, targets, maxTargets, filter1, filter2, filter3, filter4, filter5);
    if (forcedLimit > 0) {
        CaptureProjectileTargets(targets, result & 0xFFFF);
        const auto* selectionBounds = static_cast<const RECT*>(bounds);
        char message[192] = {};
        wsprintfA(
            message,
            "RANGED TARGET RESULT: requested=%ld selected=%d bounds=(%ld,%ld)-(%ld,%ld)",
            forcedLimit,
            result & 0xFFFF,
            selectionBounds->left,
            selectionBounds->top,
            selectionBounds->right,
            selectionBounds->bottom);
        LogLine(message);
    }
    return result;
}

bool InstallRangedMultiTargetClassifierHook() {
    const unsigned char original[] = {
        0x8B, 0x44, 0x24, 0x04,
        0xB9, 0x90, 0xAA, 0x4F, 0x00,
    };
    auto* target = reinterpret_cast<unsigned char*>(kRangedMultiTargetClassifierAddress);
    if (!BytesEqual(target, original, sizeof(original))) {
        LogLine("RANGED TARGET ERROR: classifier bytes do not match");
        return false;
    }
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 14, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        LogLine("RANGED TARGET ERROR: classifier trampoline allocation failed");
        return false;
    }
    memcpy(trampoline, original, sizeof(original));
    trampoline[9] = 0xE9;
    *reinterpret_cast<int32_t*>(trampoline + 10) = static_cast<int32_t>(
        (target + 9) - (trampoline + 14));
    gRealRangedMultiTargetClassifier =
        reinterpret_cast<RangedMultiTargetClassifierFn>(trampoline);
    const HookSite hook = {
        "Night Walker ranged multi-target classifier",
        kRangedMultiTargetClassifierAddress,
        original,
        sizeof(original),
        reinterpret_cast<void*>(&HookRangedMultiTargetClassifier),
        0xE9,
    };
    if (!WriteRelativeBranch(hook)) {
        VirtualFree(trampoline, 0, MEM_RELEASE);
        gRealRangedMultiTargetClassifier = nullptr;
        LogLine("RANGED TARGET ERROR: classifier patch failed");
        return false;
    }
    LogLine("RANGED TARGET OK: Shadow Bite uses native multi-target selection");
    return true;
}

bool InstallRangedSkillRangeClassifierHook() {
    const unsigned char original[] = {
        0x8B, 0x44, 0x24, 0x04,
        0xB9, 0x90, 0xAA, 0x4F, 0x00,
    };
    auto* target = reinterpret_cast<unsigned char*>(kRangedSkillRangeClassifierAddress);
    if (!BytesEqual(target, original, sizeof(original))) {
        LogLine("RANGED RANGE ERROR: classifier bytes do not match");
        return false;
    }
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 14, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        LogLine("RANGED RANGE ERROR: classifier trampoline allocation failed");
        return false;
    }
    memcpy(trampoline, original, sizeof(original));
    trampoline[9] = 0xE9;
    *reinterpret_cast<int32_t*>(trampoline + 10) = static_cast<int32_t>(
        (target + 9) - (trampoline + 14));
    gRealRangedSkillRangeClassifier =
        reinterpret_cast<RangedMultiTargetClassifierFn>(trampoline);
    const HookSite hook = {
        "Night Walker ranged skill-range classifier",
        kRangedSkillRangeClassifierAddress,
        original,
        sizeof(original),
        reinterpret_cast<void*>(&HookRangedSkillRangeClassifier),
        0xE9,
    };
    if (!WriteRelativeBranch(hook)) {
        VirtualFree(trampoline, 0, MEM_RELEASE);
        gRealRangedSkillRangeClassifier = nullptr;
        LogLine("RANGED RANGE ERROR: classifier patch failed");
        return false;
    }
    LogLine("RANGED RANGE OK: Night Walker skill lt/rb hook installed");
    return true;
}

bool InstallRangedTargetCollectorHook() {
    const unsigned char original[] = {0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x28};
    auto* target = reinterpret_cast<unsigned char*>(kRangedTargetCollectorAddress);
    if (!BytesEqual(target, original, sizeof(original))) {
        LogLine("RANGED TARGET ERROR: collector bytes do not match");
        return false;
    }
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 11, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        LogLine("RANGED TARGET ERROR: collector trampoline allocation failed");
        return false;
    }
    memcpy(trampoline, original, sizeof(original));
    trampoline[6] = 0xE9;
    *reinterpret_cast<int32_t*>(trampoline + 7) = static_cast<int32_t>(
        (target + 6) - (trampoline + 11));
    gRealRangedTargetCollector = reinterpret_cast<RangedTargetCollectorFn>(trampoline);
    const HookSite hook = {
        "Night Walker ranged target collector",
        kRangedTargetCollectorAddress,
        original,
        sizeof(original),
        reinterpret_cast<void*>(&HookRangedTargetCollector),
        0xE9,
    };
    if (!WriteRelativeBranch(hook)) {
        VirtualFree(trampoline, 0, MEM_RELEASE);
        gRealRangedTargetCollector = nullptr;
        LogLine("RANGED TARGET ERROR: collector patch failed");
        return false;
    }
    LogLine("RANGED TARGET OK: Night Walker target limits override installed");
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
        gPlayFileEx = LoadFunction<PlayFileExFn>(gVideoModule, "BDV_PlayFileEx");
        gVideoGetLastError = LoadFunction<GetLastErrorFn>(gVideoModule, "BDV_GetLastError");
        gVideoGetLastErrorEx = LoadFunction<GetLastErrorExFn>(gVideoModule, "BDV_GetLastErrorEx");
        gAttachDevice = LoadFunction<AttachDeviceFn>(gVideoModule, "BDV_AttachDevice");
        gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
        gVideoGetStatus = LoadFunction<GetStatusFn>(gVideoModule, "BDV_GetStatus");
        gVideoGetStatusEx = LoadFunction<GetStatusExFn>(gVideoModule, "BDV_GetStatusEx");
    }
    return gPlayFile != nullptr && gVideoGetLastError != nullptr &&
        gAttachDevice != nullptr && gRender != nullptr && gVideoGetStatus != nullptr &&
        gPlayFileEx != nullptr && gVideoGetStatusEx != nullptr && gVideoGetLastErrorEx != nullptr;
}

int KnownVideoMarkerTextureCode(IDirect3DBaseTexture8* texture) {
    for (int index = 0; index < gVideoMarkerTextureCount; ++index) {
        if (gVideoMarkerTextures[index] == texture) {
            return gVideoMarkerTextureCodes[index];
        }
    }
    return -1;
}

int KaringMarkerCodeFromA4R4G4B4(const uint16_t* pixels) {
    if (pixels[0] == 0xF214 && pixels[1] == 0xF457 &&
        pixels[2] == 0xF9AB && pixels[3] == 0xFCDD) {
        const int code = (pixels[4] >> 8) & 0x0F;
        return code >= 1 && code <= 14 ? code : -1;
    }
    return -1;
}

int KaringMarkerCodeFromA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    const uint32_t alphaMask = ignoreAlpha ? 0x00000000u : 0xFF000000u;
    const uint32_t colorMask = ignoreAlpha ? 0x00FFFFFFu : 0xFFFFFFFFu;
    if ((pixels[0] & colorMask) == (alphaMask | 0x00221144u) &&
        (pixels[1] & colorMask) == (alphaMask | 0x00445577u) &&
        (pixels[2] & colorMask) == (alphaMask | 0x0099AABBu) &&
        (pixels[3] & colorMask) == (alphaMask | 0x00CCDDDDu)) {
        const int red = static_cast<int>((pixels[4] >> 16) & 0xFF);
        const int code = red / 17;
        return red == code * 17 && code >= 1 && code <= 14 ? code : -1;
    }
    return -1;
}

int LucidMarkerCodeFromA4R4G4B4(const uint16_t* pixels) {
    if (pixels[0] == 0xF124 && pixels[1] == 0xF567 &&
        pixels[2] == 0xF89A && pixels[3] == 0xFBCE) {
        const int code = (pixels[4] >> 8) & 0x0F;
        return code >= 1 && code <= 15 ? 14 + code : -1;
    }
    return -1;
}

int LucidMarkerCodeFromA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    const uint32_t alphaMask = ignoreAlpha ? 0x00000000u : 0xFF000000u;
    const uint32_t colorMask = ignoreAlpha ? 0x00FFFFFFu : 0xFFFFFFFFu;
    if ((pixels[0] & colorMask) == (alphaMask | 0x00112244u) &&
        (pixels[1] & colorMask) == (alphaMask | 0x00556677u) &&
        (pixels[2] & colorMask) == (alphaMask | 0x008899AAu) &&
        (pixels[3] & colorMask) == (alphaMask | 0x00BBCCEEu)) {
        const int red = static_cast<int>((pixels[4] >> 16) & 0xFF);
        const int code = red / 17;
        return red == code * 17 && code >= 1 && code <= 15 ? 14 + code : -1;
    }
    return -1;
}

int DetectVideoMarkerPixels(IDirect3DTexture8* texture, const D3DSURFACE_DESC& description) {
    D3DLOCKED_RECT locked = {};
    if (FAILED(texture->LockRect(0, &locked, nullptr, D3DLOCK_READONLY))) {
        return -1;
    }
    int markerCode = -1;
    if (description.Format == D3DFMT_A4R4G4B4 && locked.Pitch >= 8) {
        const auto* pixels = static_cast<const uint16_t*>(locked.pBits);
        if (pixels[0] == 0xF123 && pixels[1] == 0xF456 &&
            pixels[2] == 0xF789 && pixels[3] == 0xFABC) {
            markerCode = 0;
        } else {
            markerCode = KaringMarkerCodeFromA4R4G4B4(pixels);
            if (markerCode < 0) {
                markerCode = LucidMarkerCodeFromA4R4G4B4(pixels);
            }
        }
    } else if (description.Format == D3DFMT_A8R8G8B8 && locked.Pitch >= 16) {
        const auto* pixels = static_cast<const uint32_t*>(locked.pBits);
        if (pixels[0] == 0xFF112233 && pixels[1] == 0xFF445566 &&
            pixels[2] == 0xFF778899 && pixels[3] == 0xFFAABBCC) {
            markerCode = 0;
        } else {
            markerCode = KaringMarkerCodeFromA8R8G8B8(pixels, false);
            if (markerCode < 0) {
                markerCode = LucidMarkerCodeFromA8R8G8B8(pixels, false);
            }
        }
    } else if (description.Format == D3DFMT_X8R8G8B8 && locked.Pitch >= 16) {
        const auto* pixels = static_cast<const uint32_t*>(locked.pBits);
        if ((pixels[0] & 0x00FFFFFF) == 0x00112233 &&
            (pixels[1] & 0x00FFFFFF) == 0x00445566 &&
            (pixels[2] & 0x00FFFFFF) == 0x00778899 &&
            (pixels[3] & 0x00FFFFFF) == 0x00AABBCC) {
            markerCode = 0;
        } else {
            markerCode = KaringMarkerCodeFromA8R8G8B8(pixels, true);
            if (markerCode < 0) {
                markerCode = LucidMarkerCodeFromA8R8G8B8(pixels, true);
            }
        }
    }
    texture->UnlockRect(0);
    return markerCode;
}

int DetectVideoMarkerTexture(IDirect3DBaseTexture8* baseTexture) {
    if (baseTexture == nullptr || baseTexture->GetType() != D3DRTYPE_TEXTURE) {
        return -1;
    }
    auto* texture = static_cast<IDirect3DTexture8*>(baseTexture);
    D3DSURFACE_DESC description = {};
    if (FAILED(texture->GetLevelDesc(0, &description))) {
        return -1;
    }
    const bool plausibleSize =
        description.Width >= kVideoMarkerWidth && description.Width <= 8 &&
        description.Height >= kVideoMarkerHeight && description.Height <= 8;
    if (!plausibleSize) {
        return -1;
    }
    const int markerCode = DetectVideoMarkerPixels(texture, description);
    if (markerCode < 0) {
        return -1;
    }
    if (gVideoMarkerTextureCount < kMaxVideoMarkerTextures) {
        baseTexture->AddRef();
        gVideoMarkerTextures[gVideoMarkerTextureCount++] = baseTexture;
        gVideoMarkerTextureCodes[gVideoMarkerTextureCount - 1] = markerCode;
    }
    LogLine(markerCode == 0
        ? "VIDEO OK: Gr2D field-layer marker texture detected"
        : "VIDEO OK: boss-scene marker texture detected");
    return markerCode;
}

struct KaringSceneMapping {
    int markerCode;
    const char* path;
    const char* successMessage;
};

constexpr KaringSceneMapping kKaringSceneVideos[] = {
    {1, "Data\\Video\\karing-dark-pulse.mcv", "VIDEO OK: Karing Dark Pulse started"},
    {2, "Data\\Video\\karing-goongi-screen.mcv", "VIDEO OK: Karing Goongi transition started"},
    {3, "Data\\Video\\karing-perils-goongi.mcv", "VIDEO OK: Karing Goongi peril screen started"},
    {4, "Data\\Video\\karing-perils-dool.mcv", "VIDEO OK: Karing Dool peril screen started"},
    {5, "Data\\Video\\karing-perils-hondon.mcv", "VIDEO OK: Karing Hondon peril screen started"},
    {6, "Data\\Video\\karing-reward-screen.mcv", "VIDEO OK: Karing reward screen started"},
    {7, "Data\\Video\\karing-clear-goongi.mcv", "VIDEO OK: Karing Goongi clear started"},
    {8, "Data\\Video\\karing-clear-goongi2.mcv", "VIDEO OK: Karing Goongi clear 2 started"},
    {9, "Data\\Video\\karing-clear-dool.mcv", "VIDEO OK: Karing Dool clear started"},
    {10, "Data\\Video\\karing-clear-dool2.mcv", "VIDEO OK: Karing Dool clear 2 started"},
    {11, "Data\\Video\\karing-clear-hondon.mcv", "VIDEO OK: Karing Hondon clear started"},
    {12, "Data\\Video\\karing-clear-hondon2.mcv", "VIDEO OK: Karing Hondon clear 2 started"},
    {13, "Data\\Video\\karing-p2-regen.mcv", "VIDEO OK: Karing P2 spawn started"},
    {14, "Data\\Video\\karing-p3-regen.mcv", "VIDEO OK: Karing P3 spawn started"},
    {15, "Data\\Video\\lucid-dragon-p1.mcv", "VIDEO OK: Lucid P1 dragon started"},
    {16, "Data\\Video\\lucid-dragon-p2.mcv", "VIDEO OK: Lucid P2 dragon started"},
    {17, "Data\\Video\\lucid-laser-rain.mcv", "VIDEO OK: Lucid laser rain started"},
    {18, "Data\\Video\\lucid-phantom-barrage.mcv", "VIDEO OK: Lucid phantom barrage started"},
    {19, "Data\\Video\\lucid-rush.mcv", "VIDEO OK: Lucid rush started"},
    {20, "Data\\Video\\lucid-fury.mcv", "VIDEO OK: Lucid fury started"},
    {21, "Data\\Video\\lucid-butterfly-burst.mcv", "VIDEO OK: Lucid butterfly burst started"},
    {22, "Data\\Video\\lucid-bomb.mcv", "VIDEO OK: Lucid bomb started"},
    {23, "Data\\Video\\lucid-stained-glass.mcv", "VIDEO OK: Lucid stained glass started"},
    {24, "Data\\Video\\lucid-stained-glass-1.mcv", "VIDEO OK: Lucid stained glass 1 started"},
    {25, "Data\\Video\\lucid-stained-glass-2.mcv", "VIDEO OK: Lucid stained glass 2 started"},
    {26, "Data\\Video\\lucid-stained-glass-3.mcv", "VIDEO OK: Lucid stained glass 3 started"},
    {27, "Data\\Video\\lucid-stained-glass-4.mcv", "VIDEO OK: Lucid stained glass 4 started"},
    {28, "Data\\Video\\lucid-stained-glass-5.mcv", "VIDEO OK: Lucid stained glass 5 started"},
    {29, "Data\\Video\\lucid-flower-explosion.mcv", "VIDEO OK: Lucid flower explosion started"},
};

bool StartKaringSceneVideo(int markerCode) {
    if (markerCode <= 0) {
        return false;
    }
    const KaringSceneMapping* mapping = nullptr;
    for (const KaringSceneMapping& candidate : kKaringSceneVideos) {
        if (candidate.markerCode == markerCode) {
            mapping = &candidate;
            break;
        }
    }
    if (mapping == nullptr) {
        return false;
    }
    if (!LoadVideoModule()) {
        LogLine("VIDEO ERROR: BeiDouVideo.dll was not found or incompatible");
        return false;
    }
    if (!gPlayFileEx(BDV_CHANNEL_BOSS_SCENE, mapping->path)) {
        char error[256] = "unknown boss-scene video playback error";
        gVideoGetLastErrorEx(BDV_CHANNEL_BOSS_SCENE, error, sizeof(error));
        LogLine(error);
        return false;
    }
    gBossSceneVideoPlaying = true;
    gVideoRenderedThisFrame = false;
    gMissingMarkerFrames = 0;
    gMissingMarkerLogged = false;
    LogLine(mapping->successMessage);
    return true;
}

bool ConsumeVideoMarkerDraw() {
    if (gRenderingVideo || !gVideoMarkerBound) {
        return false;
    }
    if (gVideoMarkerBoundCode > 0 && !gBossSceneVideoPlaying) {
        StartKaringSceneVideo(gVideoMarkerBoundCode);
    }
    if ((gVideoPlaying || gBossSceneVideoPlaying) && !gVideoRenderedThisFrame && gRender != nullptr) {
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
        int markerCode = KnownVideoMarkerTextureCode(texture);
        if (markerCode < 0) {
            markerCode = DetectVideoMarkerTexture(texture);
        }
        gVideoMarkerBound = markerCode >= 0;
        gVideoMarkerBoundCode = markerCode >= 0 ? markerCode : 0;
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

extern "C" void StartVideoSkill(int skillId);

HRESULT WINAPI HookPresent(
    IDirect3DDevice8* device,
    const RECT* source,
    const RECT* destination,
    HWND overrideWindow,
    const RGNDATA* dirtyRegion) {
    DrainRapidThrowImpacts();
    if (!gVideoDeviceAttached && LoadVideoModule() && gAttachDevice(device)) {
        gVideoDeviceAttached = true;
        LogLine("VIDEO OK: active D3D8 device attached on first Present");
    }
    const LONG pendingVideoSkillId = InterlockedExchange(&gPendingVideoSkillId, 0);
    if (pendingVideoSkillId != 0) {
        StartVideoSkill(static_cast<int>(pendingVideoSkillId));
    }
    if (gVideoPlaying && gVideoGetStatus != nullptr) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (gVideoGetStatus(&status) &&
            (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR)) {
            gVideoPlaying = false;
        }
    }
    if (gBossSceneVideoPlaying && gVideoGetStatusEx != nullptr) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (gVideoGetStatusEx(BDV_CHANNEL_BOSS_SCENE, &status) &&
            (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR)) {
            gBossSceneVideoPlaying = false;
        }
    }
    if ((gVideoPlaying || gBossSceneVideoPlaying) && !gVideoRenderedThisFrame) {
        ++gMissingMarkerFrames;
        if (gVideoDeviceAttached && gRender != nullptr) {
            gVideoRenderedThisFrame = true;
            gRenderingVideo = true;
            gRender();
            gRenderingVideo = false;
            if (!gMissingMarkerLogged) {
                LogLine("VIDEO OK: Present fallback active (field marker was not drawn)");
                gMissingMarkerLogged = true;
            }
        } else if (!gMissingMarkerLogged && gMissingMarkerFrames >= 30) {
            LogLine("VIDEO ERROR: active video has no renderable D3D8 path");
            gMissingMarkerLogged = true;
        }
    } else {
        gMissingMarkerFrames = 0;
    }
    const HRESULT result = gRealPresent(device, source, destination, overrideWindow, dirtyRegion);
    gVideoRenderedThisFrame = false;
    gVideoMarkerBound = false;
    gVideoMarkerBoundCode = 0;
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
    if (module == nullptr) {
        return false;
    }
    auto** slot = reinterpret_cast<void**>(
        reinterpret_cast<uintptr_t>(module) + kGr2DGetProcAddressIatRva);
    void* replacement = reinterpret_cast<void*>(&HookGetProcAddress);
    if (*slot != replacement) {
        void* original = nullptr;
        if (!PatchPointer(slot, replacement, &original)) {
            LogLine("VIDEO ERROR: failed to patch Gr2D_DX8 GetProcAddress");
            return false;
        }
        gRealGetProcAddress = FunctionFromPointer<GetProcAddressFn>(original);
    }
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
    void* replacement = reinterpret_cast<void*>(&HookLoadLibraryA);
    if (*slot != replacement) {
        void* original = nullptr;
        if (!PatchPointer(slot, replacement, &original)) {
            return false;
        }
        gRealLoadLibraryA = FunctionFromPointer<LoadLibraryAFn>(original);
    }
    HMODULE gr2D = GetModuleHandleA("Gr2D_DX8.dll");
    if (gr2D != nullptr) {
        InstallGr2DHook(gr2D);
    }
    return gRealLoadLibraryA != nullptr;
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
    {13121010, "Data\\Video\\monsoon-vi.mcv", "VIDEO OK: Monsoon VI started"},
    {13121013, "Data\\Video\\mistral-spring.mcv", "VIDEO OK: Mistral Spring started"},
    {13121019, "Data\\Video\\elemental-tempest.mcv", "VIDEO OK: Elemental Tempest started"},
    {15121016, "Data\\Video\\god-of-sea-vi.mcv", "VIDEO OK: God of the Sea VI started"},
    {15121017, "Data\\Video\\wave-riding-thunder.mcv", "VIDEO OK: Wave Riding Thunder started"},
    {15121019, "Data\\Video\\swift-annihilation.mcv", "VIDEO OK: Swift Annihilation started"},
    {1121023, "Data\\Video\\spirit-caliber.mcv", "VIDEO OK: Spirit Caliber started"},
    {1221020, "Data\\Video\\sacred-bastion.mcv", "VIDEO OK: Sacred Bastion started"},
    {1221030, "Data\\Video\\dominus-obrion.mcv", "VIDEO OK: Dominus Obrion started"},
    {1321018, "Data\\Video\\dead-space.mcv", "VIDEO OK: Dead Space started"},
    {1321025, "Data\\Video\\dark-halidom.mcv", "VIDEO OK: Dark Halidom started"},
    {2121032, "Data\\Video\\explorer-2121032.mcv", "VIDEO OK: Infernal Venom started"},
    {2121035, "Data\\Video\\explorer-2121035.mcv", "VIDEO OK: Blaze started"},
    {2221027, "Data\\Video\\explorer-2221027.mcv", "VIDEO OK: Frozen Realm started"},
    {2221030, "Data\\Video\\explorer-2221030.mcv", "VIDEO OK: Arc Lightning started"},
    {2321037, "Data\\Video\\explorer-2321037.mcv", "VIDEO OK: Divine Punishment started"},
    {2321042, "Data\\Video\\explorer-2321042.mcv", "VIDEO OK: Holy Command started"},
    {3121029, "Data\\Video\\explorer-3121029.mcv", "VIDEO OK: Arrow Rain Origin started"},
    {3121031, "Data\\Video\\explorer-3121031.mcv", "VIDEO OK: Zero Shot started"},
    {3221032, "Data\\Video\\explorer-3221032.mcv", "VIDEO OK: Split Space started"},
    {3221034, "Data\\Video\\explorer-3221034.mcv", "VIDEO OK: Death Trigger started"},
    {4121026, "Data\\Video\\explorer-4121026.mcv", "VIDEO OK: Forbidden Talisman started"},
    {4121028, "Data\\Video\\explorer-4121028.mcv", "VIDEO OK: Fatal Assault started"},
    {4221036, "Data\\Video\\explorer-4221036.mcv", "VIDEO OK: Severance started"},
    {4221039, "Data\\Video\\explorer-4221039.mcv", "VIDEO OK: Dark Truth started"},
    {5121029, "Data\\Video\\explorer-5121029.mcv", "VIDEO OK: Sea Dragon Fist started"},
    {5121035, "Data\\Video\\explorer-5121035.mcv", "VIDEO OK: Power Strike started"},
    {5221032, "Data\\Video\\explorer-5221032.mcv", "VIDEO OK: Emergency Muster started"},
    {5221034, "Data\\Video\\explorer-5221034.mcv", "VIDEO OK: Burst Scatter started"},
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

extern "C" __attribute__((used, noinline)) void QueueVideoSkill(int skillId) {
    InterlockedExchange(&gPendingVideoSkillId, static_cast<LONG>(skillId));
}

// Each naked stub preserves the register contract of the overwritten client
// instructions and returns to fixed, non-ASLR BeiDou.exe addresses.
extern "C" __attribute__((naked, noinline)) void HookKeyboardDispatch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "mov ecx, dword ptr [esi+1]\n"
        "cmp ecx, 15121000\n"
        "jb thunder_keyboard_next\n"
        "cmp ecx, 15121021\n"
        "jbe 2f\n"
        "thunder_keyboard_next:\n"
        "cmp ecx, 13121003\n"
        "jb wind_keyboard_next\n"
        "cmp ecx, 13121023\n"
        "jbe 2f\n"
        "wind_keyboard_next:\n"
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
        "cmp esi, 1121012\n"
        "jb explorer_hero_active_next\n"
        "cmp esi, 1121030\n"
        "jbe explorer_melee_active\n"
        "explorer_hero_active_next:\n"
        "cmp esi, 1221015\n"
        "jb explorer_paladin_active_next\n"
        "cmp esi, 1221032\n"
        "jbe explorer_melee_active\n"
        "explorer_paladin_active_next:\n"
        "cmp esi, 1321011\n"
        "jb explorer_dark_knight_active_next\n"
        "cmp esi, 1321026\n"
        "jbe explorer_melee_active\n"
        "explorer_dark_knight_active_next:\n"
        "cmp esi, 2121009\n"
        "jb explorer_fp_active_next\n"
        "cmp esi, 2121036\n"
        "jbe explorer_magic_active\n"
        "explorer_fp_active_next:\n"
        "cmp esi, 2221009\n"
        "jb explorer_il_active_next\n"
        "cmp esi, 2221031\n"
        "jbe explorer_magic_active\n"
        "explorer_il_active_next:\n"
        "cmp esi, 2321020\n"
        "jb explorer_bishop_active_next\n"
        "cmp esi, 2321043\n"
        "jbe explorer_magic_active\n"
        "explorer_bishop_active_next:\n"
        "cmp esi, 3121010\n"
        "jb explorer_bowmaster_active_next\n"
        "cmp esi, 3121032\n"
        "jbe explorer_ranged_active\n"
        "explorer_bowmaster_active_next:\n"
        "cmp esi, 3221009\n"
        "jb explorer_marksman_active_next\n"
        "cmp esi, 3221035\n"
        "jbe explorer_ranged_active\n"
        "explorer_marksman_active_next:\n"
        "cmp esi, 4121010\n"
        "jb explorer_night_lord_active_next\n"
        "cmp esi, 4121029\n"
        "jbe explorer_ranged_active\n"
        "explorer_night_lord_active_next:\n"
        "cmp esi, 4221009\n"
        "jb explorer_shadower_active_next\n"
        "cmp esi, 4221040\n"
        "jbe explorer_melee_active\n"
        "explorer_shadower_active_next:\n"
        "cmp esi, 5121011\n"
        "jb explorer_buccaneer_active_next\n"
        "cmp esi, 5121036\n"
        "jbe explorer_melee_active\n"
        "explorer_buccaneer_active_next:\n"
        "cmp esi, 5221011\n"
        "jb explorer_corsair_active_next\n"
        "cmp esi, 5221035\n"
        "jbe explorer_ranged_active\n"
        "explorer_corsair_active_next:\n"
        "cmp esi, 15121000\n"
        "jb thunder_active_next\n"
        "cmp esi, 15121033\n"
        "ja thunder_active_next\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _QueueVideoSkill\n"
        "add esp, 4\n"
        "popad\n"
        "popfd\n"
        "push 0x009690AE\n"
        "ret\n"
        "thunder_active_next:\n"
        "cmp esi, 13121003\n"
        "jb wind_active_next\n"
        "cmp esi, 13121023\n"
        "jbe wind_active\n"
        "wind_active_next:\n"
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
        "wind_active:\n"
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
        "explorer_melee_active:\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _StartVideoSkill\n"
        "add esp, 4\n"
        "popad\n"
        "popfd\n"
        "push 0x009690AE\n"
        "ret\n"
        "explorer_magic_active:\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _StartVideoSkill\n"
        "add esp, 4\n"
        "popad\n"
        "popfd\n"
        "push 0x0096928B\n"
        "ret\n"
        "explorer_ranged_active:\n"
        "pushfd\n"
        "pushad\n"
        "push esi\n"
        "call _StartVideoSkill\n"
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
        "cmp esi, 1121012\n"
        "jb explorer_hero_visual_next\n"
        "cmp esi, 1121030\n"
        "jbe 5f\n"
        "explorer_hero_visual_next:\n"
        "cmp esi, 1221015\n"
        "jb explorer_paladin_visual_next\n"
        "cmp esi, 1221032\n"
        "jbe 5f\n"
        "explorer_paladin_visual_next:\n"
        "cmp esi, 15121000\n"
        "jb thunder_visual_next\n"
        "cmp esi, 15121033\n"
        "jbe 5f\n"
        "thunder_visual_next:\n"
        "cmp esi, 13121003\n"
        "jb wind_visual_next\n"
        "cmp esi, 13121023\n"
        "jbe 5f\n"
        "wind_visual_next:\n"
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
        "cmp eax, 1121012\n"
        "jb explorer_hero_action_next\n"
        "cmp eax, 1121030\n"
        "jbe 2f\n"
        "explorer_hero_action_next:\n"
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
        "cmp eax, 1121012\n"
        "jb explorer_hero_offset_next\n"
        "cmp eax, 1121030\n"
        "jbe 2f\n"
        "explorer_hero_offset_next:\n"
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
        "cmp esi, 1121012\n"
        "jb explorer_hero_state_next\n"
        "cmp esi, 1121030\n"
        "jbe 3f\n"
        "explorer_hero_state_next:\n"
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
        "cmp ebx, 1121012\n"
        "jb explorer_hero_hit_next\n"
        "cmp ebx, 1121030\n"
        "jbe 2f\n"
        "explorer_hero_hit_next:\n"
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
    LogLine("LOAD: Cygnus/Explorer V-VI Attack Skill Compat v43");
    HMODULE diagnostics = LoadLibraryA("WzFileLogger.dll");
    if (diagnostics != nullptr) {
        LogLine("OK: client diagnostics loaded");
    } else {
        LogLine("INFO: WzFileLogger.dll not present; client diagnostics disabled");
    }
    if (!InstallLoadLibraryHook()) {
        LogLine("VIDEO ERROR: failed to chain LoadLibraryA after diagnostics initialization");
    }
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
    LogLine("OK: unified skill compat v43 hooks installed");
    InstallRangedSkillRangeClassifierHook();
    InstallRangedMultiTargetClassifierHook();
    InstallRangedTargetCollectorHook();
    InstallNativeRangedProjectileHook();
    InstallMagicBulletHook();
    EnableRapidThrowImpactSupport();
    return 0;
}

}  // namespace

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
