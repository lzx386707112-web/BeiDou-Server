// Draws MCV skill videos at the client's own FIELD_EFFECT layer on top of the verified v69 core.
//
// Layer contract (why the video may not be drawn at Present):
// the server sends the caster one `PacketCreator.showEffect("customSkill/.../...VideoLayer")`, and
// the matching `Map/Effect.img` node holds a single 7x5 canvas for 30000 ms. The client therefore
// keeps drawing that tiny sprite from the skill's own field-effect layer for the whole video, and
// that draw is the verified insertion point: it sits below the floating damage numbers and the UI.
// Swallowing the marker draw and calling BDV_Render there keeps the native order of skill effect,
// mobs, damage numbers and UI. Drawing at Present instead - which is what v2..v6 did, because the
// marker signature below was never recognised - pins the video to the very end of the frame and
// covers the damage numbers and the UI with it. See docs/tools/beidou-video-dll-integration.md
// (10.1/10.3) and tool/client-video/README.md ("最终层级方案").

#include "../../client-video/BeiDouVideoApi.h"
#include "FirstChanceDump.h"
#include "MarkerSignature.h"
#include "PrologueRelocation.h"

#include <windows.h>
#include <d3d8.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr size_t kCreateDeviceVtableIndex = 15;
constexpr size_t kPresentVtableIndex = 15;
constexpr size_t kSetTextureVtableIndex = 61;
constexpr size_t kDrawPrimitiveVtableIndex = 70;
constexpr size_t kDrawIndexedPrimitiveVtableIndex = 71;
constexpr size_t kDrawPrimitiveUpVtableIndex = 72;
constexpr size_t kDrawIndexedPrimitiveUpVtableIndex = 73;
// The detour itself only needs a five byte `E9 rel32`, but it may only ever be written over whole
// instructions: patching a fixed five bytes assumes the prologue's first instruction boundary
// lands exactly on offset 5. That holds for the Microsoft d3d8.dll the PC loads and not for the
// Wine builtin d3d8.dll the phone loads, which is the v4 fix documented in PrologueRelocation.h.
constexpr size_t kMinimumPrologueBytes = 5;
constexpr size_t kMaximumPrologueBytes = 16;
constexpr size_t kTrampolineBytes = 32;
static_assert(
    kTrampolineBytes >= kMaximumPrologueBytes + 5,
    "the trampoline has to hold the relocated prologue plus the jump back");
constexpr DWORD kWatcdogPollMs = 50;
constexpr DWORD kDeviceCaptureTimeoutMs = 20000;
constexpr DWORD kStatusLogIntervalMs = 2000;
constexpr size_t kStatusTextCapacity = 192;
constexpr UINT kMarkerWidth = 7;
constexpr UINT kMarkerHeight = 5;
constexpr char kD3D8DllName[] = "d3d8.dll";
constexpr char kDirect3DCreate8Name[] = "Direct3DCreate8";
using AttachDeviceFn = int(__stdcall*)(void*);
using RenderFn = void(__stdcall*)();
using GetStatusExFn = int(__stdcall*)(uint32_t, BdvStatus*);
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

// Defined below. The capture installs a code hook on d3d8!Direct3DCreate8 and the device
// hooks start from that entry point, so both entries have to be declared before the helpers
// that reference them.
HRESULT WINAPI HookCreateDevice(
    IDirect3D8*, UINT, D3DDEVTYPE, HWND, DWORD, D3DPRESENT_PARAMETERS*, IDirect3DDevice8**);
HRESULT WINAPI HookPresent(
    IDirect3DDevice8*, const RECT*, const RECT*, HWND, const RGNDATA*);
IDirect3D8* WINAPI HookDirect3DCreate8(UINT sdkVersion);

// Defined with the status reporting helpers at the bottom of the file. The hook installer builds
// its evidence line with them, so they have to be visible here as well.
char* AppendText(char* cursor, const char* end, const char* text);
char* AppendUnsigned(char* cursor, const char* end, unsigned int value);

HMODULE gVideoModule = nullptr;
AttachDeviceFn gAttachDevice = nullptr;
RenderFn gRender = nullptr;
GetStatusExFn gGetStatusEx = nullptr;
Direct3DCreate8Fn gRealDirect3DCreate8 = nullptr;
CreateDeviceFn gRealCreateDevice = nullptr;
PresentFn gRealPresent = nullptr;
SetTextureFn gRealSetTexture = nullptr;
DrawPrimitiveFn gRealDrawPrimitive = nullptr;
DrawIndexedPrimitiveFn gRealDrawIndexedPrimitive = nullptr;
DrawPrimitiveUpFn gRealDrawPrimitiveUp = nullptr;
DrawIndexedPrimitiveUpFn gRealDrawIndexedPrimitiveUp = nullptr;
unsigned char* gCreate8CodeTarget = nullptr;
bool gCreate8CodeHooked = false;
bool gCreateDeviceSlotHooked = false;
bool gCreateDeviceFired = false;
bool gMarkerBound = false;
bool gRenderedThisFrame = false;
bool gRenderingVideo = false;
bool gFieldLayerLogged = false;
bool gMarkerSeenLogged = false;
bool gPresentFallbackLogged = false;
bool gPlaybackActive = false;
unsigned int gMarkerRenderFrames = 0;
unsigned int gFallbackRenderFrames = 0;
bool gShapeProbed = false;
DWORD gStatusLogTick = 0;

template <typename Function>
Function FunctionFromPointer(void* pointer) {
    static_assert(sizeof(Function) == sizeof(pointer), "unexpected Win32 function pointer size");
    Function function = nullptr;
    memcpy(&function, &pointer, sizeof(function));
    return function;
}

template <typename Function>
void* PointerFromFunction(Function function) {
    static_assert(sizeof(Function) == sizeof(void*), "unexpected Win32 function pointer size");
    void* pointer = nullptr;
    memcpy(&pointer, &function, sizeof(pointer));
    return pointer;
}

template <typename Function>
Function LoadFunction(HMODULE module, const char* name) {
    return FunctionFromPointer<Function>(reinterpret_cast<void*>(GetProcAddress(module, name)));
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

// 2026-09-28 (v2): the client diagnostics engine rewrites BeiDou.exe+0x00AF00C0 every time a
// module loads, which silently removes any other LoadLibraryA hook from the chain. Measured
// timeline of the failing run: Gr2D_DX8.DLL loads at 10:17:52.578, D3D8.DLL at .606 (28 ms
// later) and the device is created immediately after, while a 10 ms polling loop can only
// notice d3d8.dll several milliseconds too late. MCV playback therefore stopped being a race
// about IAT slots at all: the capture has to be in place *before* the client resolves
// Direct3DCreate8, which means hooking the export code itself.
//
// d3d8.dll is preloaded here (roughly 2.5 s before Gr2D_DX8.DLL in the failing run) and the
// entry point of Direct3DCreate8 is patched with a jump through a trampoline that keeps the
// original prologue. The client then hands us its own IDirect3D8 instance, so the CreateDevice
// slot is patched on the exact interface the client is about to use - no IAT slot, no polling and
// no per-object vtable assumption.
//
// 2026-09-28 (v4): the entry patch has to cover *whole instructions*. v3 copied and overwrote a
// fixed five bytes, which assumes the prologue's first instruction boundary is exactly at offset
// 5. The PC's Microsoft d3d8.dll satisfies that; the Wine builtin d3d8.dll the phone loads does
// not, and the truncated copy decoded as `C7 E9` (#UD) and killed the process the moment the
// trampoline ran. The trampoline now resumes at the first boundary at or past five bytes and the
// entry keeps the same width, so a non aligned prologue is patched rather than rejected.
bool InstallCreateDeviceSlot(void** vtable) {
    if (vtable == nullptr) return false;
    void* original = vtable[kCreateDeviceVtableIndex];
    if (original == nullptr) return false;
    if (original == PointerFromFunction(&HookCreateDevice)) {
        gCreateDeviceSlotHooked = true;
        return true;
    }
    if (gRealCreateDevice == nullptr) {
        gRealCreateDevice = FunctionFromPointer<CreateDeviceFn>(original);
    }
    if (!PatchPointer(
            &vtable[kCreateDeviceVtableIndex],
            PointerFromFunction(&HookCreateDevice), nullptr)) {
        return false;
    }
    gCreateDeviceSlotHooked = true;
    return true;
}

// A prologue can only be relocated into the trampoline when every instruction it covers keeps its
// meaning after being moved: no relative branch, no absolute address, no operand that spans the
// end of the window. beidou::prologue::RelocationLength answers with the number of whole bytes to
// relocate, and returning 0 simply downgrades us to the probe interface path below.
bool InstallDirect3DCreate8CodeHook(HMODULE d3d8) {
    if (d3d8 == nullptr) return false;
    auto* target = reinterpret_cast<unsigned char*>(
        reinterpret_cast<uintptr_t>(GetProcAddress(d3d8, kDirect3DCreate8Name)));
    if (target == nullptr) {
        LogLine("VIDEO LAYER ERROR: d3d8.dll has no Direct3DCreate8 export");
        return false;
    }
    // Follow export thunks so the patch lands on the real body.
    for (int hop = 0; hop < 4; ++hop) {
        if (target[0] == 0xE9) {
            int32_t displacement = 0;
            memcpy(&displacement, target + 1, sizeof(displacement));
            target = target + 5 + displacement;
            continue;
        }
        if (target[0] == 0xFF && target[1] == 0x25) {
            void* indirect = nullptr;
            memcpy(&indirect, target + 2, sizeof(indirect));
            target = static_cast<unsigned char*>(indirect);
            continue;
        }
        break;
    }
    if (gCreate8CodeHooked && gCreate8CodeTarget == target) return true;

    // v4: relocate whole instructions instead of a fixed five bytes. Five is the smallest detour
    // the jump needs; the trampoline resumes at the first instruction boundary at or past it. A
    // prologue whose boundary is not exactly at offset 5 therefore gets patched with its extra
    // bytes as well, instead of having an instruction cut in half.
    const size_t relocation = beidou::prologue::RelocationLength(
        target, kMaximumPrologueBytes, kMinimumPrologueBytes, kMaximumPrologueBytes);
    if (relocation == 0) {
        LogLine("VIDEO LAYER WARN: d3d8 Direct3DCreate8 prologue is not relocatable; using the probe interface");
        return false;
    }

    auto* trampoline = static_cast<unsigned char*>(
        VirtualAlloc(nullptr, kTrampolineBytes, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        LogLine("VIDEO LAYER ERROR: failed to allocate the Direct3DCreate8 trampoline");
        return false;
    }
    memcpy(trampoline, target, relocation);
    trampoline[relocation] = 0xE9;
    int32_t back = 0;
    back = static_cast<int32_t>((target + relocation) - (trampoline + relocation + 5));
    memcpy(trampoline + relocation + 1, &back, sizeof(back));
    FlushInstructionCache(GetCurrentProcess(), trampoline, relocation + 5);
    gRealDirect3DCreate8 = FunctionFromPointer<Direct3DCreate8Fn>(trampoline);

    DWORD oldProtect = 0;
    if (!VirtualProtect(target, relocation, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        LogLine("VIDEO LAYER ERROR: failed to make d3d8 Direct3DCreate8 writable");
        return false;
    }
    int32_t jump = 0;
    jump = static_cast<int32_t>(
        reinterpret_cast<unsigned char*>(&HookDirect3DCreate8) - (target + 5));
    // Both stores go through volatile pointers so the compiler keeps the order: the displacement
    // has to be in place before the opcode, otherwise another thread could execute a jump with a
    // half written operand. The padding that covers the rest of the relocated prologue is written
    // between the two stores for the same reason.
    *reinterpret_cast<volatile int32_t*>(target + 1) = jump;
    for (size_t pad = kMinimumPrologueBytes; pad < relocation; ++pad) {
        *reinterpret_cast<volatile unsigned char*>(target + pad) = 0x90;
    }
    *reinterpret_cast<volatile unsigned char*>(target) = 0xE9;
    FlushInstructionCache(GetCurrentProcess(), target, relocation);
    DWORD ignored = 0;
    VirtualProtect(target, relocation, oldProtect, &ignored);

    gCreate8CodeTarget = target;
    gCreate8CodeHooked = true;
    // The relocated width is the number that tells the two d3d8 builds apart in a log. The PC's
    // Microsoft build reports 5, so its bytes are exactly what v3 wrote; a Wine build reports
    // whatever its own prologue needs.
    char buffer[160] = {};
    char* cursor = buffer;
    const char* end = buffer + sizeof(buffer) - 1;
    cursor = AppendText(
        cursor, end,
        "VIDEO LAYER OK: d3d8 Direct3DCreate8 code hook installed ahead of the client (relocated ");
    cursor = AppendUnsigned(cursor, end, static_cast<unsigned int>(relocation));
    cursor = AppendText(cursor, end, " whole prologue bytes)");
    *cursor = '\0';
    LogLine(buffer);
    return true;
}

// Fallback for the (unlikely) case where the export prologue cannot be relocated: hook the
// CreateDevice slot of an interface created here. d3d8.dll hands out static vtables, so this
// normally covers every interface the client creates afterwards.
bool InstallProbeInterfaceHook(HMODULE d3d8) {
    if (gCreateDeviceSlotHooked) return true;
    Direct3DCreate8Fn create = LoadFunction<Direct3DCreate8Fn>(d3d8, kDirect3DCreate8Name);
    if (create == nullptr) return false;
    IDirect3D8* probe = create(D3D_SDK_VERSION);
    if (probe == nullptr) {
        LogLine("VIDEO LAYER ERROR: Direct3DCreate8 probe returned null");
        return false;
    }
    void** vtable = *reinterpret_cast<void***>(probe);
    if (!InstallCreateDeviceSlot(vtable)) {
        LogLine("VIDEO LAYER ERROR: IDirect3D8::CreateDevice slot is not patchable");
        return false;
    }
    // Deliberately never released: if d3d8.dll ever handed out a per-object vtable, releasing
    // the probe would free the bytes that were just patched.
    LogLine("VIDEO LAYER OK: IDirect3D8::CreateDevice captured through the probe interface");
    return true;
}

bool LoadVideoModule() {
    if (gVideoModule == nullptr) gVideoModule = LoadLibraryA("BeiDouVideo.dll");
    if (gVideoModule == nullptr) return false;
    if (gAttachDevice == nullptr) {
        gAttachDevice = LoadFunction<AttachDeviceFn>(gVideoModule, "BDV_AttachDevice");
        gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
        gGetStatusEx = LoadFunction<GetStatusExFn>(gVideoModule, "BDV_GetStatusEx");
    }
    return gAttachDevice != nullptr && gRender != nullptr && gGetStatusEx != nullptr;
}

// The signatures themselves live in MarkerSignature.h (no Windows dependency, host tested). This
// function only adds the D3D8 side: the marker is a texture whose canvas is 7x5 up to 8x8.
bool DetectMarker(IDirect3DBaseTexture8* baseTexture) {
    if (baseTexture == nullptr || baseTexture->GetType() != D3DRTYPE_TEXTURE) return false;
    auto* texture = static_cast<IDirect3DTexture8*>(baseTexture);
    D3DSURFACE_DESC description = {};
    if (FAILED(texture->GetLevelDesc(0, &description)) ||
        description.Width < kMarkerWidth || description.Width > 8 ||
        description.Height < kMarkerHeight || description.Height > 8) {
        return false;
    }
    D3DLOCKED_RECT locked = {};
    if (FAILED(texture->LockRect(0, &locked, nullptr, D3DLOCK_READONLY))) return false;
    bool matches = false;
    if (description.Format == D3DFMT_A4R4G4B4 && locked.Pitch >= 8) {
        const auto* pixels = static_cast<const uint16_t*>(locked.pBits);
        if (beidou::marker::MatchesFieldEffectA4R4G4B4(pixels)) {
            matches = true;
        }
    } else if (description.Format == D3DFMT_A8R8G8B8 && locked.Pitch >= 16) {
        const auto* pixels = static_cast<const uint32_t*>(locked.pBits);
        if (beidou::marker::MatchesFieldEffectA8R8G8B8(pixels, false)) {
            matches = true;
        }
    } else if (description.Format == D3DFMT_X8R8G8B8 && locked.Pitch >= 16) {
        const auto* pixels = static_cast<const uint32_t*>(locked.pBits);
        if (beidou::marker::MatchesFieldEffectA8R8G8B8(pixels, true)) {
            matches = true;
        }
    }
    texture->UnlockRect(0);
    return matches;
}

// BDV_Render() is BDV_RenderAll(): it draws every channel. Whoever owns the outermost Present
// hook has to issue that call, otherwise a decoding video is never presented.
bool AnyChannelHasVideo() {
    if (gGetStatusEx == nullptr) return false;
    const uint32_t channels[] = {BDV_CHANNEL_BOSS_SCENE, BDV_CHANNEL_PLAYER_SKILL};
    for (const uint32_t channel : channels) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (!gGetStatusEx(channel, &status)) continue;
        if (status.state == BDV_STATE_DECODING || status.state == BDV_STATE_PLAYING) return true;
    }
    return false;
}

// 2026-09-28 (v3): the render decision must NOT depend on this layer being the outermost Present
// hook. KaringSceneCompat chains its Present hook on top of these hooks - it reads the client
// device vtable slot 15, stores the current value (this module's HookPresent) in its own table and
// calls it on every frame end (KaringSceneCompat.log: "OK: chained after Dawn D3D8 hooks"). The
// device vtable therefore points at Karing's entry while this hook runs, so an identity check
// against vtable[15] is always false and silently discarded every single video frame. That was the
// exact reason the v2 delivery attached the device yet never drew anything.
//
// Only Karing and the v69 core could render besides this module:
//   * Karing calls BDV_RenderAll only while its own boss-scene video runs (it gates on an internal
//     byte flag before reaching its render helper), so player-skill videos are never presented by
//     it;
//   * the v69 core reported that its D3D8 field-layer hooks never installed
//     ("no complete D3D8 field-layer hooks were installed within 30 seconds"), so it never renders
//     either.
// Drawing here is therefore the only thing that puts a player-skill MCV on screen.
char* AppendText(char* cursor, const char* end, const char* text) {
    while (*text != '\0' && cursor < end) {
        *cursor++ = *text++;
    }
    return cursor;
}

char* AppendUnsigned(char* cursor, const char* end, unsigned int value) {
    char digits[12] = {};
    int count = 0;
    do {
        digits[count++] = static_cast<char>('0' + (value % 10u));
        value /= 10u;
    } while (value != 0 && count < 11);
    while (count > 0 && cursor < end) {
        *cursor++ = digits[--count];
    }
    return cursor;
}

// One status line per channel every kStatusLogIntervalMs while a channel is not idle. This is the
// evidence that separates "the decoder never produced a frame" (state=1 decoded=0) from "frames are
// decoded but nothing is uploaded" (decoded>0 displayed=0) from "it renders fine".
void LogChannelStatus(uint32_t channel, const BdvStatus& status) {
    char buffer[kStatusTextCapacity] = {};
    char* cursor = buffer;
    const char* end = buffer + sizeof(buffer) - 1;
    cursor = AppendText(cursor, end, "VIDEO LAYER STATUS: channel=");
    cursor = AppendUnsigned(cursor, end, channel);
    cursor = AppendText(cursor, end, " state=");
    cursor = AppendUnsigned(cursor, end, status.state);
    cursor = AppendText(cursor, end, " decoded=");
    cursor = AppendUnsigned(cursor, end, status.decodedFrames);
    cursor = AppendText(cursor, end, " displayed=");
    cursor = AppendUnsigned(cursor, end, status.displayedFrames);
    cursor = AppendText(cursor, end, " dropped=");
    cursor = AppendUnsigned(cursor, end, status.droppedFrames);
    cursor = AppendText(cursor, end, " position=");
    cursor = AppendUnsigned(cursor, end, status.positionMilliseconds);
    cursor = AppendText(cursor, end, "ms");
    *cursor = '\0';
    LogLine(buffer);
}

void LogChannelStatusesIfDue() {
    if (gGetStatusEx == nullptr) return;
    const DWORD now = GetTickCount();
    if (now - gStatusLogTick < kStatusLogIntervalMs) return;
    gStatusLogTick = now;
    const uint32_t channels[] = {BDV_CHANNEL_BOSS_SCENE, BDV_CHANNEL_PLAYER_SKILL};
    for (const uint32_t channel : channels) {
        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (!gGetStatusEx(channel, &status) || status.state == BDV_STATE_IDLE) continue;
        LogChannelStatus(channel, status);
    }
}

// One evidence line per playback: how many frames were drawn at the verified field-effect layer and
// how many had to fall back to Present. Present sits above the UI and the floating damage numbers,
// so a non zero `present_fallback_frames` names the exact reason a skill's damage numbers vanish -
// the server did not send that skill's FIELD_EFFECT marker, or Map.wz lost its 7x5 node.
void TrackPlaybackLayer(bool channelActive) {
    if (channelActive) {
        if (!gPlaybackActive) {
            gPlaybackActive = true;
            gMarkerRenderFrames = 0;
            gFallbackRenderFrames = 0;
        }
        return;
    }
    if (!gPlaybackActive) return;
    gPlaybackActive = false;
    char buffer[kStatusTextCapacity] = {};
    char* cursor = buffer;
    const char* end = buffer + sizeof(buffer) - 1;
    cursor = AppendText(cursor, end, "VIDEO LAYER SUMMARY: marker_frames=");
    cursor = AppendUnsigned(cursor, end, gMarkerRenderFrames);
    cursor = AppendText(cursor, end, " present_fallback_frames=");
    cursor = AppendUnsigned(cursor, end, gFallbackRenderFrames);
    cursor = AppendText(
        cursor, end,
        gFallbackRenderFrames == 0
            ? " (every frame was drawn at the skill effect layer)"
            : " (this video had no FIELD_EFFECT marker draw)");
    *cursor = '\0';
    LogLine(buffer);
}

// Called from all four draw hooks. The return value means "this draw belongs to the marker and has
// been handled", so the caller must not forward it.
bool ConsumeMarkerDraw() {
    if (gRenderingVideo || !gMarkerBound) return false;
    // Consume exactly the marker's own draw. Leaving the bound flag set until Present would drop
    // every other draw of the frame, which is a silent way to lose damage numbers and effect layers.
    gMarkerBound = false;
    if (!gRenderedThisFrame && gRender != nullptr && AnyChannelHasVideo()) {
        gRenderedThisFrame = true;
        ++gMarkerRenderFrames;
        gRenderingVideo = true;
        gRender();
        gRenderingVideo = false;
        if (!gFieldLayerLogged) {
            gFieldLayerLogged = true;
            LogLine("VIDEO LAYER OK: field-effect marker draw; the video is rendered at the skill effect layer");
        }
    }
    return true;
}

HRESULT WINAPI HookSetTexture(
    IDirect3DDevice8* device, DWORD stage, IDirect3DBaseTexture8* texture) {
    if (stage == 0 && !gRenderingVideo) {
        gMarkerBound = DetectMarker(texture);
        // One line per session, and only once the texture is actually recognised: it separates
        // "the server never sent the FIELD_EFFECT / Map.wz lost the node" (no such line at all)
        // from "the marker is there but no video was playing when it was drawn".
        if (gMarkerBound && !gMarkerSeenLogged) {
            gMarkerSeenLogged = true;
            LogLine("VIDEO LAYER OK: FIELD_EFFECT marker texture recognised");
        }
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
    LogChannelStatusesIfDue();
    // Queried once per frame: the same answer drives both the fallback decision and the per
    // playback layer summary below.
    const bool channelActive = AnyChannelHasVideo();
    if (!gRenderedThisFrame && gRender != nullptr && channelActive) {
        // Safety net only. No field-effect marker was drawn this frame, so the video has no place
        // in the native order and has to go on top of the finished frame - above the mobs, the
        // floating damage numbers and the UI. Reaching this branch is a resource problem (the
        // server did not send the skill's FIELD_EFFECT, or Map.wz lost the 7x5 marker node), not a
        // rendering problem, which is why it is reported as a warning instead of an OK line.
        gRenderedThisFrame = true;
        ++gFallbackRenderFrames;
        gRenderingVideo = true;
        gRender();
        gRenderingVideo = false;
        if (!gPresentFallbackLogged) {
            gPresentFallbackLogged = true;
            LogLine("VIDEO LAYER WARN: Present fallback active (no field-effect marker was drawn)");
        }
    }
    TrackPlaybackLayer(channelActive);
    const HRESULT result = gRealPresent(device, source, destination, window, dirtyRegion);
    gRenderedThisFrame = false;
    gMarkerBound = false;
    return result;
}

bool PatchDeviceHooks(void** vtable) {
    void* original = nullptr;
    if (!PatchPointer(&vtable[kPresentVtableIndex], PointerFromFunction(&HookPresent), &original)) return false;
    if (gRealPresent == nullptr) gRealPresent = FunctionFromPointer<PresentFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kSetTextureVtableIndex], PointerFromFunction(&HookSetTexture), &original)) return false;
    if (gRealSetTexture == nullptr) gRealSetTexture = FunctionFromPointer<SetTextureFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawPrimitiveVtableIndex], PointerFromFunction(&HookDrawPrimitive), &original)) return false;
    if (gRealDrawPrimitive == nullptr) gRealDrawPrimitive = FunctionFromPointer<DrawPrimitiveFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawIndexedPrimitiveVtableIndex], PointerFromFunction(&HookDrawIndexedPrimitive), &original)) return false;
    if (gRealDrawIndexedPrimitive == nullptr) gRealDrawIndexedPrimitive = FunctionFromPointer<DrawIndexedPrimitiveFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawPrimitiveUpVtableIndex], PointerFromFunction(&HookDrawPrimitiveUp), &original)) return false;
    if (gRealDrawPrimitiveUp == nullptr) gRealDrawPrimitiveUp = FunctionFromPointer<DrawPrimitiveUpFn>(original);
    original = nullptr;
    if (!PatchPointer(&vtable[kDrawIndexedPrimitiveUpVtableIndex], PointerFromFunction(&HookDrawIndexedPrimitiveUp), &original)) return false;
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
    gCreateDeviceFired = true;
    void** vtable = *reinterpret_cast<void***>(*output);
    if (!PatchDeviceHooks(vtable)) {
        LogLine("VIDEO LAYER ERROR: failed to chain D3D8 device hooks");
        return result;
    }
    if (LoadVideoModule() && gAttachDevice(*output)) {
        LogLine("VIDEO LAYER OK: D3D8 device attached");
    } else {
        LogLine("VIDEO LAYER ERROR: BeiDouVideo.dll could not attach to D3D8");
    }
    return result;
}

IDirect3D8* WINAPI HookDirect3DCreate8(UINT sdkVersion) {
    // The client resolves this export hundreds of times (measured: 301 per session), so both the
    // evidence line and the shape probe only run once. Probing on every call would also leak one
    // IDirect3D8 per call, because the probe interface is deliberately never released.
    if (!gShapeProbed) {
        LogLine("VIDEO LAYER OK: the client's Direct3DCreate8 reached the capture hook");
    }
    if (gRealDirect3DCreate8 == nullptr) {
        LogLine("VIDEO LAYER ERROR: Direct3DCreate8 trampoline is missing");
        return nullptr;
    }
    IDirect3D8* direct3D = gRealDirect3DCreate8(sdkVersion);
    if (direct3D == nullptr) {
        LogLine("VIDEO LAYER ERROR: Direct3DCreate8 returned null");
        return nullptr;
    }
    void** vtable = *reinterpret_cast<void***>(direct3D);
    if (!InstallCreateDeviceSlot(vtable)) {
        LogLine("VIDEO LAYER ERROR: the client interface CreateDevice slot is not patchable");
        return direct3D;
    }
    // Evidence line: does d3d8.dll share one static vtable across instances? The CreateDevice
    // slot of the client interface above is patched either way, so this only records which of
    // the two shapes we are dealing with.
    if (!gShapeProbed) {
        gShapeProbed = true;
        IDirect3D8* probe = gRealDirect3DCreate8(sdkVersion);
        if (probe != nullptr) {
            void** probeVtable = *reinterpret_cast<void***>(probe);
            if (probeVtable == vtable) {
                LogLine("VIDEO LAYER OK: IDirect3D8 vtable is shared process wide");
            } else {
                InstallCreateDeviceSlot(probeVtable);
                LogLine("VIDEO LAYER WARN: IDirect3D8 hands out per-object vtables");
            }
        }
    }
    return direct3D;
}

DWORD WINAPI InstallHooks(LPVOID) {
    LogLine("LOAD: shared MCV field-effect layer compatibility v8 (d3d8 preload + whole-instruction code hook + first-chance C++ call sites)");
    // Written on every start so the delivery can be told apart from earlier builds even when the
    // client is launched out of the size-cached shared directory: never reuse the previous file
    // size, the shared folder would keep serving the stale copy.
    LogLine("BUILD: video-layer-compat 2026-09-29 v8 capture=whole-instruction-prologue layer=field-effect-marker present=fallback-only deterministic firstchance=veh-summary-stack-plus-dump");
    LogLine("CAPABILITIES: shared-only; region-specific routes removed; marker=FIELD_EFFECT; formats=A4R4G4B4,A8R8G8B8,X8R8G8B8; channels=boss-scene,player-skill; render=BDV_RenderAll; primary-layer=native-field-effect; fallback-layer=Present; capture=d3d8-Direct3DCreate8-whole-instruction-trampoline; device-hooks=Present,SetTexture,DrawPrimitive,DrawIndexedPrimitive,DrawPrimitiveUP,DrawIndexedPrimitiveUP; diagnostics=channel-status,layer-summary,first-chance-cpp-summary,first-chance-minidump; runtime=32-bit-v69-client; build=v8");
    // The layer contract, logged once per session so one log says where the video is composited and
    // what to check when a skill's damage numbers are hidden.
    LogLine("LAYER: the video is drawn where the client draws the FIELD_EFFECT marker (7x5 canvas, signature F123/F456/F789/FABC in A4R4G4B4, FF112233/FF445566/FF778899/FFAABBCC in A8R8G8B8 or the same colours in X8R8G8B8), so the skill effect, the mobs, the floating damage numbers and the UI keep their native order");
    LogLine("LAYER: Present only draws when no marker was seen in this frame; that layer sits above the damage numbers and the UI, so VIDEO LAYER SUMMARY reports marker_frames against present_fallback_frames");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("VIDEO LAYER ERROR: unexpected BeiDou.exe image base");
        return 1;
    }
    // 2026-09-28 (v5): the diagnostics engine (WzFileLogger.dll) only arms its first-chance dump
    // after a null flash movie has been captured, so the 13:11 session - 19 `_com_error`s and no
    // `flash_null_skips` - left the exception that popped the client dialog undocumented. This
    // observer closes that gap from inside a module we own: every C++ exception leaves a summary
    // with the real `_com_error::m_hr`, and the occurrence named in `beidou_diagnostics.ini`
    // also leaves a dump. It never changes control flow, so the client's filter still sees
    // exactly the exceptions it saw before.
    beidou::firstchance::Install(&LogLine);
    // Preloading d3d8.dll is what makes the capture race free: the client only loads it at the
    // moment it needs a device, which is far too late to install anything from a polling thread.
    HMODULE d3d8 = GetModuleHandleA(kD3D8DllName);
    if (d3d8 == nullptr) d3d8 = LoadLibraryA(kD3D8DllName);
    if (d3d8 == nullptr) {
        LogLine("VIDEO LAYER ERROR: d3d8.dll could not be loaded");
        return 2;
    }
    if (!InstallDirect3DCreate8CodeHook(d3d8)) InstallProbeInterfaceHook(d3d8);
    LogLine("VIDEO LAYER OK: runtime capture armed");

    for (DWORD waited = 0; waited < kDeviceCaptureTimeoutMs; waited += kWatcdogPollMs) {
        if (gCreateDeviceFired) {
            LogLine("VIDEO LAYER OK: capture confirmed by a live D3D8 device");
            return 0;
        }
        Sleep(kWatcdogPollMs);
    }
    if (!gCreateDeviceFired) {
        LogLine("VIDEO LAYER ERROR: no D3D8 device was observed within the capture window");
    }
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
