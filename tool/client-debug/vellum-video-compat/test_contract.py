#!/usr/bin/env python3
"""Contract for BeiDouVellumVideoCompat.dll.

Covers three regressions this module has to keep working around:

* 2026-09-28 (v1): the client diagnostics engine also rewrites the Gr2D_DX8 GetProcAddress IAT
  slot and can win that race, so the chain may not be owned by the v69 core. The extension must
  never fail hard because of a hijacked slot.
* 2026-09-28 (v2): the diagnostics engine rewrites BeiDou.exe+0x00AF00C0 on every module load,
  which silently removes any other LoadLibraryA hook from the chain. Measured timeline of the
  failing run: Gr2D_DX8.DLL at 10:17:52.578, D3D8.DLL at .606 (28 ms later), device created right
  after - a 10 ms polling loop is always several milliseconds late. The capture must therefore be
  installed *before* the client resolves Direct3DCreate8, which means preloading d3d8.dll and
  hooking the export code itself, with no IAT slot and no polling in the critical path.
* 2026-09-28 (v3): KaringSceneCompat chains its own Present hook *on top of* these hooks (it reads
  the client device vtable slot 15, keeps the pointer it finds - this module's HookPresent - and
  calls it every frame; KaringSceneCompat.log: "OK: chained after Dawn D3D8 hooks"). The device
  vtable therefore never holds this module's HookPresent while the hook runs, so a v2 style
  "am I the outermost hook?" identity check is always false and silently drops every frame: the v2
  delivery attached the device ("D3D8 device attached", "player-skill: playback queued") yet never
  drew a pixel. Rendering must not depend on the hook position at all.
* 2026-09-28 (v4): the same binaries ran on the PC but killed the phone with
  STATUS_ILLEGAL_INSTRUCTION at trampoline+4, right after "reached the capture hook". The v3 hook
  overwrote and copied a *fixed* five bytes, which only works when the prologue's first
  instruction boundary lands exactly on offset 5 - true for the Microsoft d3d8.dll the PC loads,
  false for the Wine builtin d3d8.dll the phone loads. There, an instruction starting at offset 4
  (`C7 45 F8 imm32`, `mov dword ptr [ebp-8], imm32`) lost its ModRM byte to the 0xE9 opcode, so
  the trampoline decoded `C7 E9`, an undefined opcode, and the process died the instant it was
  called. The entry patch now covers whole instructions: relocate N bytes (N >= 5), resume at
  target + N, pad the rest of the entry with 0x90.
* Player-skill MCV is only drawn if someone issues BDV_Render (== BDV_RenderAll). Karing calls it
  only while its own boss-scene video runs, and the v69 core reported that its D3D8 field-layer
  hooks never installed, so this module is the only layer that can present the channel.
* 2026-09-28 (v5): the 13:11 session threw 19 `_com_error`s and then popped the client dialog, yet
  it produced no `first-chance-cpp-*.dmp`: the diagnostics engine (WzFileLogger.dll) only arms its
  own first-chance dump after a null flash movie has been captured, and that session had
  `flash_null_skips=0`. The diagnostics engine ships as a binary with no source in the repository,
  so the missing half is added here instead: a vectored exception observer that summarizes every
  C++ exception (real `_com_error::m_hr` included) and stores one dump at the occurrence named in
  `beidou_diagnostics.ini`. It must never change control flow, must be switchable off, and must
  not depend on the flash guard being armed first.
* 2026-09-28 (v6): v5 proved the observer works on the real client but exposed two gaps. The dump it
  writes is taken by a worker thread, so it catches the faulting thread after it has unwound past
  the throw (its stack pointer is 2.2 KB above the throwing one - the throw frames are gone), and
  the engine samples a stack for at most 8 C++ exceptions per session, so the two occurrences that
  mattered in the 13:45 session read `stack_candidates="(sample_limit)"`. Now every occurrence
  carries its own call-site sample, taken from the exception's Esp inside the handler: only the
  words inside the game executable are kept, and a `*` marks the ones that a preceding `E8 rel32`
  confirms as real return addresses.
* 2026-09-28 (v7): v3..v6 finally drew the video, and the damage numbers disappeared while it
  played. The capture, the device, the channel and the decoder were all fine - the insertion point
  was wrong. The server sends the caster one FIELD_EFFECT
  (`showEffect("customSkill/.../...VideoLayer")`) whose `Map/Effect.img` node holds a single 7x5
  canvas for 30000 ms, so the client keeps drawing that small sprite from the skill effect layer
  for the whole video. Swallowing *that* draw and calling BDV_Render there keeps the native order
  of skill effect, mobs, damage numbers and UI; drawing at Present pins the video to the end of the
  frame, above the damage numbers and the UI. This module only knew the Root Abyss (Vellum)
  signature, never the FIELD_EFFECT one, so every skill degraded to Present. Present is now an
  explicitly reported fallback, one summary line counts both paths per playback, and the signature
  matching lives in MarkerSignature.h so the byte patterns are host tested.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name("VellumVideoCompat.cpp")
MARKER_SIGNATURE = Path(__file__).with_name("MarkerSignature.h")
RELOCATION_HEADER = Path(__file__).with_name("PrologueRelocation.h")
FIRSTCHANCE_FORMAT = Path(__file__).with_name("FirstChanceFormat.h")
FIRSTCHANCE_DUMP = Path(__file__).with_name("FirstChanceDump.h")
DIAGNOSTICS_INI = ROOT / "clien/beidou_diagnostics.ini"
WRAPPER = ROOT / "tool/client-debug/dawn-warrior-skill-compat/HpMpExpansionWrapper.cpp"
SHIPPED = ROOT / "clien/BeiDouVellumVideoCompat.dll"
CORE = ROOT / "clien/BeiDouSkillCompatCore.dll"
VERIFIED_CORE_SHA256 = "3882737456d7c95795b2afe63ad91703cd70ef299c6b83fefe5f6f70764b466f"

BUILD_FLAGS = [
    "-std=c++17", "-Os", "-s", "-shared", "-nostdlib",
    "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
    # The DLL is linked with -nostdlib, so the optimiser must not rewrite the hand written length
    # loops in FirstChanceFormat.h into `strlen` calls (undefined reference at link time).
    "-fno-tree-loop-distribute-patterns",
    "-Wl,--entry,_DllMain@12", "-Wl,--subsystem,windows",
    "-Wl,--no-insert-timestamp", "-Wl,--image-base,0x69140000",
    "-Wall", "-Wextra", "-Werror",
]
# Import libraries must follow the source file, exactly as in build.sh.
BUILD_LIBS = ["-lkernel32", "-luser32", "-lgcc"]

# Retired markers. Their presence in the shipped DLL means a stale build is being delivered.
RETIRED_MARKERS = (
    b"VELLUM VIDEO WARN: LoadLibraryA slot is not owned by the v69 core; chaining defensively",
    b"VELLUM VIDEO OK: IDirect3D8::CreateDevice captured without an IAT race",
    b"LoadLibraryA chain is not owned by the v69 core",
    b"BUILD: vellum-video-compat 2026-09-28 v2 capture=d3d8-code-hook no-iat-slots deterministic",
    b"LOAD: Vellum attack10/11 video compatibility v2",
    b"BUILD: vellum-video-compat 2026-09-28 v3 capture=d3d8-code-hook present=position-independent deterministic",
    b"LOAD: Vellum attack10/11 video compatibility v3 (d3d8 preload + code hook)",
    b"BUILD: vellum-video-compat 2026-09-28 v4 capture=whole-instruction-prologue present=position-independent deterministic",
    b"LOAD: Vellum attack10/11 video compatibility v4 (d3d8 preload + whole-instruction code hook)",
    b"BUILD: vellum-video-compat 2026-09-28 v5 capture=whole-instruction-prologue present=position-independent deterministic firstchance=veh-summary-plus-dump",
    b"LOAD: Vellum attack10/11 video compatibility v5 (d3d8 preload + whole-instruction code hook + first-chance C++ evidence)",
    b"BUILD: vellum-video-compat 2026-09-28 v6 capture=whole-instruction-prologue present=position-independent deterministic firstchance=veh-summary-stack-plus-dump",
    b"LOAD: Vellum attack10/11 video compatibility v6 (d3d8 preload + whole-instruction code hook + first-chance C++ call sites)",
)
# Sizes of retired deliveries. The client is launched out of a shared folder that keys its cache on
# file size, so an equal length replacement is served stale; never ship these sizes again.
# 10240 is the v3 delivery that crashed the phone with an illegal instruction.
# 11264 is the v4 delivery that fixed the phone but shipped without the first-chance observer.
# 17920 is the v5 delivery whose observer wrote a dump too late to see the throw, and no call site.
# 18944 is the v6 delivery that drew every video at Present and hid the damage numbers with it.
# 19968 is an intermediate v7 build (same fix, inline signature predicates) that was never
# delivered; its size is retired too so a shipped file can never be confused with it.
RETIRED_SIZES = (8704, 9216, 10240, 11264, 17920, 18944, 19968)

NEW_MARKERS = (
    b"VELLUM VIDEO OK: d3d8 Direct3DCreate8 code hook installed ahead of the client",
    b"VELLUM VIDEO OK: the client's Direct3DCreate8 reached the capture hook",
    b"VELLUM VIDEO OK: capture confirmed by a live D3D8 device",
    b"VELLUM VIDEO OK: FIELD_EFFECT marker texture recognised",
    b"VELLUM VIDEO OK: field-effect marker draw; the video is rendered at the skill effect layer",
    b"VELLUM VIDEO WARN: Present fallback active (no field-effect marker was drawn)",
    b"VELLUM VIDEO SUMMARY: marker_frames=",
    b"LAYER: the video is drawn where the client draws the FIELD_EFFECT marker",
    b"VELLUM VIDEO STATUS: channel=",
    b"FIRST-CHANCE: status=armed filter=0xe06d7363",
    b"FIRST-CHANCE CPP: occurrence=",
    b"FIRST-CHANCE DUMP: status=",
)

# Host side harness for the relocation decoder. The header has no Windows dependency, so the exact
# byte patterns that decide the entry patch width are testable without a client run.
#
# The two patterns that matter:
#   * a prologue whose first instruction boundary is exactly at offset 5 (what the PC's Microsoft
#     d3d8.dll looks like) must keep relocating five bytes, so the PC's bytes stay untouched;
#   * a prologue with a boundary at offset 4 (the phone's Wine builtin d3d8.dll) must relocate the
#     whole instruction. Five bytes would cut its ModRM byte, and the trampoline copy would decode
#     `C7 E9` / `C6 E9`, whose opcode extension is undefined (#UD) - the phone crash.
HARNESS = r'''
#include "@HEADER@"

#include <cstdio>

namespace {

struct Case {
    const char* name;
    unsigned char code[20];
    size_t length;
    size_t minimum;
    size_t maximum;
    size_t expected;
};

size_t checked = 0;
size_t failures = 0;

void Check(const Case& item) {
    ++checked;
    const size_t got =
        beidou::prologue::RelocationLength(item.code, item.length, item.minimum, item.maximum);
    if (got != item.expected) {
        std::printf("FAIL %s: got %zu expected %zu\n", item.name, got, item.expected);
        ++failures;
    } else {
        std::printf("OK %s: %zu\n", item.name, got);
    }
}

}  // namespace

int main() {
    const Case table[] = {
        // Boundary exactly at five: the detour keeps its historical width.
        {"microsoft-aligned", {0x55, 0x8B, 0xEC, 0x90, 0x90}, 5, 5, 16, 5},
        // The phone crash: `mov dword ptr [ebp-8], imm32` starts at offset 4. Five bytes would
        // leave `C7 E9` in the trampoline.
        {"wine-c7-at-offset-4", {0x53, 0x55, 0x8B, 0xEC, 0xC7, 0x45, 0xF8, 0x00, 0x00, 0x00, 0x00},
         11, 5, 16, 11},
        // Same shape with the byte sized store (`C6 45 F8 imm8` -> `C6 E9`).
        {"wine-c6-at-offset-4", {0x53, 0x55, 0x8B, 0xEC, 0xC6, 0x45, 0xF8, 0x00}, 8, 5, 16, 8},
        // `and esp, -16` straddling offset 5.
        {"align-stack", {0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF0}, 6, 5, 16, 6},
        {"sub-esp-imm32", {0x55, 0x8B, 0xEC, 0x81, 0xEC, 0x00, 0x01, 0x00, 0x00}, 9, 5, 16, 9},
        {"register-modrm", {0x89, 0xE5, 0x50, 0x51, 0x52, 0x53}, 6, 5, 16, 5},
        {"push-imm8", {0x6A, 0x00, 0x55, 0x8B, 0xEC}, 5, 5, 16, 5},
        {"hotpatch-mov-edi-edi", {0x8B, 0xFF, 0x55, 0x8B, 0xEC}, 5, 5, 16, 5},
        {"sib-lea", {0x8D, 0x64, 0x24, 0x08, 0x90}, 5, 5, 16, 5},
        {"long-single-instruction", {0xC7, 0x45, 0xF8, 0x00, 0x00, 0x00, 0x00}, 7, 5, 16, 7},
        // Everything below must be refused: a rejected prologue only downgrades to the probe path.
        {"relative-call", {0xE8, 0x00, 0x00, 0x00, 0x00, 0x90}, 6, 5, 16, 0},
        {"escape-0f", {0x0F, 0x1F, 0x00, 0x90, 0x90}, 5, 5, 16, 0},
        {"absolute-moffs", {0xA1, 0x00, 0x00, 0x00, 0x00}, 5, 5, 16, 0},
        {"indirect-jump-absolute", {0xFF, 0x25, 0x00, 0x00, 0x00, 0x00}, 6, 5, 16, 0},
        {"sib-without-base", {0x8B, 0x04, 0x85, 0x00, 0x00, 0x00, 0x00}, 7, 5, 16, 0},
        {"window-exhausted", {0xFF, 0xD0, 0x90}, 3, 5, 16, 0},
        {"truncated-immediate", {0xB8, 0x00, 0x00}, 3, 5, 16, 0},
    };
    for (const Case& item : table) {
        Check(item);
    }
    std::printf("cases=%zu failures=%zu\n", checked, failures);
    return failures == 0 ? 0 : 1;
}
'''

# Host side harness for the first-chance report logic. FirstChanceFormat.h is Windows free as well,
# so the decisions that actually matter - which occurrence stores the dump, whether a threshold of
# zero really disables the observer, how the artifact is named, how a HRESULT is labelled - are
# testable on the host instead of only on the next crash.
FIRSTCHANCE_HARNESS = r'''
#include "@HEADER@"

#include <cstdio>
#include <cstring>

namespace {

size_t checked = 0;
size_t failures = 0;

void Check(bool passed, const char* name) {
    ++checked;
    if (!passed) {
        std::printf("FAIL %s\n", name);
        ++failures;
    }
}

bool Same(const char* left, const char* right) {
    return left != nullptr && right != nullptr && std::strcmp(left, right) == 0;
}

}  // namespace

int main() {
    using namespace beidou::firstchance;

    // Thresholds: zero has to mean "no observer at all", and the dump is a one shot.
    Check(!ObserverArmed(kDisabledThreshold), "threshold-zero-disables");
    Check(ObserverArmed(kDefaultThreshold), "threshold-default-arms");
    Check(!ShouldDumpAtOccurrence(1, kDisabledThreshold), "disabled-never-dumps");
    Check(!ShouldDumpAtOccurrence(2, 3), "silent-before-the-nth");
    Check(ShouldDumpAtOccurrence(3, 3), "dumps-exactly-at-the-nth");
    Check(!ShouldDumpAtOccurrence(4, 3), "one-shot-after-the-nth");

    // Summaries are capped so a runaway resource loop cannot fill the disk.
    Check(ShouldSummarizeOccurrence(1), "summarize-first");
    Check(ShouldSummarizeOccurrence(kOccurrenceLogLimit), "summarize-last");
    Check(!ShouldSummarizeOccurrence(kOccurrenceLogLimit + 1), "summarize-capped");

    // Artifact naming, matching the layout the diagnostics engine uses for its own dumps.
    char name[64];
    Check(BuildDumpFileName(name, sizeof name, "20260928-131114", 5976u, 123456u), "name-built");
    Check(Same(name, "first-chance-cpp-20260928-131114-pid5976-123456.dmp"), "name-exact");

    char stamp[32];
    Check(BuildSessionStamp(stamp, sizeof stamp, 2026u, 9u, 28u, 13u, 11u, 14u), "stamp-built");
    Check(Same(stamp, "20260928-131114"), "stamp-exact");

    // A buffer that cannot hold the whole name must fail loudly instead of shipping a partial path.
    char tiny[8];
    Check(!BuildDumpFileName(tiny, sizeof tiny, "20260928-131114", 5976u, 1u), "tiny-refused");

    // The MSVC exception record encoding: the object pointer sits at parameter 1 and the HRESULT
    // at object + 4. Those two constants are what turn an exception record into evidence.
    Check(kMsvcExceptionMagic == 0x19930520u, "msvc-magic");
    Check(kThrownObjectOffset == 0x4u, "hresult-offset");
    Check(kMinimumCppParameters == 3u, "parameter-count");
    Check(kCppExceptionCode == 0xE06D7363u, "exception-code");

    // Only values we have actually met get a name; anything else stays unnamed on purpose, because
    // a wrong label is worse than none.
    Check(Same(HresultTag(static_cast<int32_t>(0x80004003u)), "E_POINTER"), "tag-e-pointer");
    Check(Same(HresultTag(static_cast<int32_t>(0x80004002u)), "E_NOINTERFACE"), "tag-e-nointerface");
    Check(Same(HresultTag(static_cast<int32_t>(0x80030002u)), "STG_E_FILENOTFOUND"), "tag-stg");
    Check(HresultTag(static_cast<int32_t>(0x8000FFFFu)) == nullptr, "tag-unknown-unnamed");

    // The call-site sample: the engine only records eight of these per session, which is exactly
    // how the 13:45 session lost the two occurrences that mattered.
    Check(kStackSampleDwords == 96u, "stack-window-dwords");
    Check(kStackSampleCandidates == 12u, "stack-candidate-cap");

    char hexbuf[16];
    TextCursor hex;
    ResetCursor(hex, hexbuf, sizeof hexbuf);
    Check(AppendHexTrimmed(hex, 0x0u), "hex-zero-built");
    Check(TerminateText(hex) && Same(hexbuf, "0"), "hex-zero-exact");
    ResetCursor(hex, hexbuf, sizeof hexbuf);
    Check(AppendHexTrimmed(hex, 0x3fd5bu), "hex-trim-built");
    Check(TerminateText(hex) && Same(hexbuf, "3fd5b"), "hex-trim-exact");

    StackCandidate items[3];
    items[0].index = 49;  items[0].offset = 0x3fd5bu; items[0].verified = true;
    items[1].index = 52;  items[1].offset = 0xa497u;  items[1].verified = false;
    items[2].index = 101; items[2].offset = 0x0u;     items[2].verified = false;

    char sample[128];
    TextCursor cursor;
    ResetCursor(cursor, sample, sizeof sample);
    Check(AppendStackSample(cursor, items, 3), "stack-built");
    Check(TerminateText(cursor), "stack-terminated");
    Check(Same(sample, " stack=\"s49:+0x3fd5b* s52:+0xa497 s101:+0x0\""), "stack-exact");

    StackCandidate empty[1];
    ResetCursor(cursor, sample, sizeof sample);
    Check(AppendStackSample(cursor, empty, 0), "stack-empty-built");
    Check(TerminateText(cursor) && Same(sample, " stack=\"(none)\""), "stack-empty-exact");

    // A buffer that cannot hold the whole sample must fail instead of shipping half a line.
    char tight[12];
    TextCursor small;
    ResetCursor(small, tight, sizeof tight);
    Check(!AppendStackSample(small, items, 3), "stack-refused");

    std::printf("cases=%zu failures=%zu\n", checked, failures);
    return failures == 0 ? 0 : 1;
}
'''

# Host side harness for the marker signature matcher. MarkerSignature.h has no Windows dependency,
# so the exact bytes that decide "this draw is the FIELD_EFFECT insertion point" can be asserted
# here. The v7 defect was precisely this check: the module only knew the Root Abyss (Vellum)
# signature, so the FIELD_EFFECT marker stayed invisible and every skill fell through to the
# Present fallback, which composites the video above the damage numbers and the UI.
MARKER_HARNESS = r'''
#include "@HEADER@"

#include <cstdint>
#include <cstdio>

namespace {

size_t checked = 0;
size_t failures = 0;

void Check(bool value, const char* name) {
    ++checked;
    if (!value) {
        ++failures;
        std::printf("FAIL %s\n", name);
    }
}

}  // namespace

int main() {
    using namespace beidou::marker;

    // FIELD_EFFECT marker, A4R4G4B4: (17,34,51,255) (68,85,102,255) (119,136,153,255)
    // (170,187,204,255) keeps the high nibble of every channel.
    const uint16_t field4444[8] = {0xF123, 0xF456, 0xF789, 0xFABC, 0, 0, 0, 0};
    Check(MatchesFieldEffectA4R4G4B4(field4444), "field-effect 4444 accepted");

    const uint16_t foreignFirstPixel[8] = {0xF357, 0xF456, 0xF789, 0xFABC, 0, 0, 0, 0};
    Check(!MatchesFieldEffectA4R4G4B4(foreignFirstPixel), "foreign first pixel rejected");

    const uint16_t field4444NearMiss[8] = {0xF123, 0xF456, 0xF789, 0xFABD, 0, 0, 0, 0};
    Check(!MatchesFieldEffectA4R4G4B4(field4444NearMiss), "4444 near miss rejected");

    // FIELD_EFFECT marker, A8R8G8B8 and X8R8G8B8 (same colours, alpha significant or ignored).
    const uint32_t field8888[8] = {0xFF112233, 0xFF445566, 0xFF778899, 0xFFAABBCC, 0, 0, 0, 0};
    Check(MatchesFieldEffectA8R8G8B8(field8888, false), "field-effect 8888 accepted");

    const uint32_t field8888WrongSecond[8] = {
        0xFF112233, 0xFF445567, 0xFF778899, 0xFFAABBCC, 0, 0, 0, 0};
    Check(!MatchesFieldEffectA8R8G8B8(field8888WrongSecond, false), "8888 near miss rejected");

    const uint32_t alphaZero[8] = {0x00112233, 0x00445566, 0x00778899, 0x00AABBCC, 0, 0, 0, 0};
    Check(!MatchesFieldEffectA8R8G8B8(alphaZero, false), "alpha is significant in A8R8G8B8");
    Check(MatchesFieldEffectA8R8G8B8(alphaZero, true), "alpha is ignored in X8R8G8B8");

    // Root Abyss (Vellum) attack10/11: same 7x5 rule, different signature, plus a code pixel.
    const uint16_t vellum10[8] = {0xF357, 0xF689, 0xFABC, 0xFDEF, 0xF58E, 0, 0, 0};
    Check(VellumCodeFromA4R4G4B4(vellum10) == 5, "attack10 code 5 from the fifth pixel");
    const uint16_t vellum11[8] = {0xF357, 0xF689, 0xFABC, 0xFDEF, 0xF68E, 0, 0, 0};
    Check(VellumCodeFromA4R4G4B4(vellum11) == 6, "attack11 code 6 from the fifth pixel");
    const uint16_t vellumOtherCode[8] = {0xF357, 0xF689, 0xFABC, 0xFDEF, 0xF48E, 0, 0, 0};
    Check(VellumCodeFromA4R4G4B4(vellumOtherCode) == 0, "code outside 5/6 rejected");

    const uint32_t vellum10_8888[8] = {
        0xFF335577, 0xFF668899, 0xFFAABBCC, 0xFFDDEEFF, 0xFF5588EE, 0, 0, 0};
    Check(VellumCodeFromA8R8G8B8(vellum10_8888, false) == 5, "attack10 code 5 in A8R8G8B8");
    const uint32_t vellum11_8888[8] = {
        0xFF335577, 0xFF668899, 0xFFAABBCC, 0xFFDDEEFF, 0xFF6688EE, 0, 0, 0};
    Check(VellumCodeFromA8R8G8B8(vellum11_8888, false) == 6, "attack11 code 6 in A8R8G8B8");
    const uint32_t vellumOtherCode_8888[8] = {
        0xFF335577, 0xFF668899, 0xFFAABBCC, 0xFFDDEEFF, 0xFF4488EE, 0, 0, 0};
    Check(VellumCodeFromA8R8G8B8(vellumOtherCode_8888, false) == 0, "8888 code outside 5/6 rejected");
    const uint32_t vellum10_x8[8] = {
        0x00335577, 0x00668899, 0x00AABBCC, 0x00DDEEFF, 0x005588EE, 0, 0, 0};
    Check(VellumCodeFromA8R8G8B8(vellum10_x8, true) == 5, "attack10 code 5 in X8R8G8B8");

    // 0x00AABBCC belongs to both families, so only the whole four pixel signature may decide: a
    // marker that mixes them has to match neither, and the families have to stay disjoint.
    const uint16_t mixed[8] = {0xF123, 0xF456, 0xFABC, 0xFDEF, 0, 0, 0, 0};
    Check(!MatchesVellumA4R4G4B4(mixed), "mixed signature is not a vellum marker");
    Check(!MatchesFieldEffectA4R4G4B4(mixed), "mixed signature is not a field-effect marker");
    Check(!MatchesFieldEffectA4R4G4B4(vellum10), "vellum marker is not a field-effect marker");
    Check(!MatchesVellumA4R4G4B4(field4444), "field-effect marker is not a vellum marker");
    Check(!MatchesVellumA8R8G8B8(field8888, false), "families stay disjoint in A8R8G8B8");
    Check(!MatchesFieldEffectA8R8G8B8(vellum10_8888, false), "families stay disjoint both ways");

    std::printf("cases=%zu failures=%zu\n", checked, failures);
    return failures == 0 ? 0 : 1;
}
'''


def code_only(source: str) -> str:
    """Strip C++ comments so documentation may still name the retired hook sites."""
    out: list[str] = []
    i = 0
    while i < len(source):
        if source.startswith("//", i):
            i = source.find("\n", i)
            if i < 0:
                break
        elif source.startswith("/*", i):
            i = source.find("*/", i)
            if i < 0:
                break
            i += 2
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


class VellumVideoCompatContract(unittest.TestCase):
    def test_only_new_vellum_screens_are_mapped(self) -> None:
        source = SOURCE.read_text()
        signature = MARKER_SIGNATURE.read_text()
        self.assertIn("kVellumAttack10Code = 5", signature)
        self.assertIn("kVellumAttack11Code = 6", signature)
        self.assertIn("root-abyss-vellum-attack10.mcv", source)
        self.assertIn("root-abyss-vellum-attack11.mcv", source)
        # The codes are defined once, in the header the host harness compiles.
        self.assertNotIn("kAttack10MarkerCode", source)
        self.assertNotIn("kAttack11MarkerCode", source)
        for old_name in ("pierre.mcv", "vonbon.mcv", "queen.mcv", "root-abyss-vellum.mcv"):
            self.assertNotIn(old_name, source)

    def test_extension_still_loads_after_the_verified_core(self) -> None:
        wrapper = WRAPPER.read_text()
        self.assertLess(
            wrapper.index("LoadSiblingDll(kCoreDllName)"),
            wrapper.index("LoadSiblingDll(kVellumVideoDllName)"),
        )

    def test_no_iat_slot_is_touched_any_more(self) -> None:
        # The whole point of v2: neither the EXE LoadLibraryA slot nor the Gr2D_DX8
        # GetProcAddress slot may be in the capture path, because the diagnostics engine
        # overwrites both of them on every module load.
        code = code_only(SOURCE.read_text())
        for retired in ("kLoadLibraryAIat", "0x00AF00C0", "kGr2DGetProcAddressIatRva", "0x0002D024"):
            self.assertNotIn(retired, code)
        for retired in ("HookLoadLibraryA", "HookGetProcAddress", "InstallGr2DHook"):
            self.assertNotIn(retired, code)

    def test_d3d8_is_preloaded_before_the_client_needs_it(self) -> None:
        source = SOURCE.read_text()
        preload = source.index("LoadLibraryA(kD3D8DllName)")
        install = source.index("InstallDirect3DCreate8CodeHook(d3d8)")
        self.assertLess(preload, install)
        # No polling may sit between the load and the hook install.
        self.assertNotIn("Sleep", source[:install])

    def test_export_code_hook_patches_the_opcode_last(self) -> None:
        source = SOURCE.read_text()
        self.assertIn("kDirect3DCreate8Name", source)
        self.assertIn("Direct3DCreate8 code hook installed", source)
        self.assertIn("VirtualAlloc", source)
        # Both stores go through volatile pointers so the displacement lands before the opcode.
        operand = source.index("*reinterpret_cast<volatile int32_t*>(target + 1) = jump;")
        opcode = source.index("*reinterpret_cast<volatile unsigned char*>(target) = 0xE9;")
        self.assertLess(operand, opcode)
        # The padding that covers the rest of the relocated prologue has to sit between them, for
        # the same reason: another thread must never see a jump with a half written operand.
        padding = source.index("for (size_t pad = kMinimumPrologueBytes; pad < relocation; ++pad)")
        self.assertLess(operand, padding)
        self.assertLess(padding, opcode)
        # A non relocatable prologue must fall back instead of patching blindly.
        fallback = source.index("InstallProbeInterfaceHook(d3d8)")
        self.assertLess(source.index("InstallDirect3DCreate8CodeHook(d3d8)"), fallback)

    def test_the_entry_patch_covers_whole_instructions(self) -> None:
        # v4: the width may not be a fixed five bytes any more. Everything that used to assume the
        # constant - the trampoline copy, the resume target, the writable range and the cache flush
        # - now has to be driven by the decoded relocation length.
        source = SOURCE.read_text()
        self.assertIn("PrologueRelocation.h", source)
        self.assertIn("RelocationLength", source)
        for retired in ("PrologueIsRelocatable", "kCreateDeviceSlotPatchSize"):
            self.assertNotIn(retired, source)
        for width_from_decoder in (
            "memcpy(trampoline, target, relocation);",
            "trampoline[relocation] = 0xE9;",
            "memcpy(trampoline + relocation + 1, &back, sizeof(back));",
            "VirtualProtect(target, relocation, PAGE_EXECUTE_READWRITE, &oldProtect)",
            "FlushInstructionCache(GetCurrentProcess(), target, relocation);",
        ):
            self.assertIn(width_from_decoder, source)
        # The trampoline must resume at the boundary the decoder reported, never at a hard coded 5.
        self.assertIn("(target + relocation) - (trampoline + relocation + 5)", source)
        self.assertIn("kMaximumPrologueBytes", source)

    def test_prologue_relocation_decides_the_patch_width(self) -> None:
        # The decoder is pure C++ with no Windows dependency on purpose, so the exact byte patterns
        # that decide the patch width can be exercised on the host instead of only on a crash.
        self.run_host_harness(HARNESS, RELOCATION_HEADER, "cases=17 failures=0")

    def test_marker_signature_decides_the_insertion_point(self) -> None:
        # v7: matching the FIELD_EFFECT marker is what keeps the video inside the skill effect layer
        # instead of on top of the damage numbers. Byte exactness matters here, so the whole four
        # pixel signature is asserted on the host, including both near misses and the pixel that the
        # two marker families share.
        self.run_host_harness(MARKER_HARNESS, MARKER_SIGNATURE, "cases=20 failures=0")

    def run_host_harness(self, harness_text: str, header: Path, expected: str) -> None:
        compiler = shutil.which("c++") or shutil.which("clang++")
        if compiler is None:
            self.skipTest("no host C++ compiler is installed")
        harness = harness_text.replace("@HEADER@", str(header))
        with tempfile.TemporaryDirectory(prefix="beidou-vellum-harness-") as build_dir:
            source_file = Path(build_dir) / "harness.cpp"
            source_file.write_text(harness)
            binary = Path(build_dir) / "harness"
            completed = subprocess.run(
                [compiler, "-std=c++17", "-o", str(binary), str(source_file)],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn(expected, ran.stdout)

    def test_host_installs_the_first_chance_observer(self) -> None:
        source = SOURCE.read_text()
        self.assertIn('#include "FirstChanceDump.h"', source)
        self.assertIn("beidou::firstchance::Install(&LogLine)", source)
        # Installed on the same worker thread that arms the D3D8 capture, and only after the image
        # base check: in a foreign host nothing may be hooked.
        install = source.index("beidou::firstchance::Install(&LogLine)")
        self.assertLess(source.index("unexpected BeiDou.exe image base"), install)
        # One definition of the observer, in the header - never a second copy in the host.
        self.assertNotIn("AddVectoredExceptionHandler", code_only(source))

    def test_first_chance_observer_never_changes_control_flow(self) -> None:
        # The observer is a witness, not a handler: it always continues the search, so the client's
        # own exception filter sees exactly what it saw before this module existed.
        header = FIRSTCHANCE_DUMP.read_text()
        self.assertNotIn("EXCEPTION_CONTINUE_EXECUTION", header)
        self.assertEqual(code_only(header).count("return EXCEPTION_CONTINUE_SEARCH;"), 4)
        self.assertIn("record->ExceptionCode != kCppExceptionCode", header)
        self.assertIn("AddVectoredExceptionHandler(1, &HandleException)", header)
        # Never re-raise from inside the callback: that would replace the real exception with ours.
        self.assertNotIn("RaiseException", code_only(header))

    def test_first_chance_dump_is_defensive(self) -> None:
        header = FIRSTCHANCE_DUMP.read_text()
        # The dump comes from a worker thread: MiniDumpWriteDump can take a second on a 700 MB
        # client and the exception callback has to stay as short as possible.
        self.assertIn("CreateThread(nullptr, 0, DumpWorker, nullptr, 0, nullptr)", header)
        # Exactly one dump per session, claimed with an interlocked exchange so two concurrent
        # exceptions cannot both start writing.
        self.assertIn("InterlockedExchange(&gDumpStarted, 1) == 0", header)
        self.assertIn("InterlockedIncrement(&gOccurrences)", header)
        self.assertIn("ShouldDumpAtOccurrence(occurrence, gThreshold)", header)
        # dbghelp is resolved lazily: the delivery must not gain a hard dependency on it.
        self.assertIn('LoadLibraryW(L"dbghelp.dll")', header)
        self.assertIn('GetProcAddress(dbghelp, "MiniDumpWriteDump")', header)
        # No full memory dump - a 700 MB process, and stacks plus the thrown object are enough.
        self.assertNotIn("MiniDumpWithFullMemory", header)
        self.assertIn("constexpr uint32_t kDumpType", header)
        self.assertNotIn("0x00000002u", header)
        # The exception record is copied before the callback returns; the original lives in a frame
        # the worker thread never sees.
        self.assertIn(
            "memcpy(&gSnapshot.record, info->ExceptionRecord, sizeof(EXCEPTION_RECORD))", header)
        self.assertIn(
            "memcpy(&gSnapshot.context, info->ContextRecord, sizeof(CONTEXT))", header)
        # The thrown object is read with a checked copy, never a raw dereference: the pointer comes
        # from an exception record and may be anything.
        self.assertIn("ReadProcessMemory", header)
        self.assertIn("kMsvcExceptionMagic", header)

    def test_first_chance_switch_lives_in_the_diagnostics_ini(self) -> None:
        ini = DIAGNOSTICS_INI.read_text()
        self.assertIn("dump_first_chance_cpp_after=", ini)
        header = FIRSTCHANCE_DUMP.read_text()
        # Reading the very ini the diagnostics engine reads keeps a single switch in charge.
        self.assertIn('"diagnostics", "dump_first_chance_cpp_after"', header)
        self.assertIn("beidou_diagnostics.ini", header)
        self.assertIn('"diagnostics\\\\"', header)
        self.assertIn("GetPrivateProfileIntA", header)

    def test_first_chance_format_decides_the_evidence(self) -> None:
        compiler = shutil.which("c++") or shutil.which("clang++")
        if compiler is None:
            self.skipTest("no host C++ compiler is installed")
        harness = FIRSTCHANCE_HARNESS.replace("@HEADER@", str(FIRSTCHANCE_FORMAT))
        with tempfile.TemporaryDirectory(prefix="beidou-vellum-firstchance-") as build_dir:
            source_file = Path(build_dir) / "harness.cpp"
            source_file.write_text(harness)
            binary = Path(build_dir) / "harness"
            completed = subprocess.run(
                [compiler, "-std=c++17", "-o", str(binary), str(source_file)],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("cases=34 failures=0", ran.stdout)

    def test_every_occurrence_records_its_call_site(self) -> None:
        # v6: the call site has to come from the exception's own Esp, inside the handler. The dump is
        # written by a worker thread and therefore only ever sees the faulting thread after it has
        # unwound past the throw - the v5 dump is proof of that, not an assumption.
        header = FIRSTCHANCE_DUMP.read_text()
        self.assertIn("AppendFaultingStack(cursor, info->ContextRecord)", header)
        self.assertIn("context->Esp", header)
        self.assertIn("ResolveExeRange()", header)
        self.assertIn("PrecededByCallIntoExe(value)", header)
        # Only the game executable's image is sampled, and its end comes from the PE header rather
        # than a hard-coded size.
        self.assertIn("gExeBase", header)
        self.assertIn("gExeEnd", header)
        self.assertIn("*reinterpret_cast<const uint32_t*>(image + 0x50)", header)
        # The sample must never be able to run away: both the window and the candidate list are
        # bounded by constants that the harness above pins down.
        self.assertIn("words[kStackSampleDwords]", header)
        self.assertIn("count < kStackSampleCandidates", header)

    def test_capture_is_confirmed_and_reported(self) -> None:
        source = SOURCE.read_text()
        self.assertIn("gCreateDeviceFired", source)
        self.assertIn("capture confirmed by a live D3D8 device", source)
        self.assertIn("no D3D8 device was observed within the capture window", source)
        self.assertIn("kCreateDeviceVtableIndex = 15", source)
        self.assertIn("D3D_SDK_VERSION", source)
        # Never release the probe interface: releasing it could free a per-object vtable that was
        # just patched, turning a silent no-op into a first-chance crash.
        self.assertNotIn("->Release()", source)

    def test_present_render_does_not_depend_on_the_hook_position(self) -> None:
        # v3: KaringSceneCompat chains on top of this hook, so vtable[15] never points at
        # HookPresent while it runs. Any "am I outermost?" identity check silently drops every
        # frame, which is exactly how the v2 delivery attached the device and drew nothing.
        code = code_only(SOURCE.read_text())
        self.assertNotIn("IsOutermostPresentHook", code)
        source = SOURCE.read_text()
        self.assertIn("AnyChannelHasVideo", source)
        self.assertIn("BDV_CHANNEL_PLAYER_SKILL", source)
        # Present is the safety net, never the first choice: it only fires when the frame produced
        # no marker draw, and it says so in the log instead of reporting a plain success.
        present = source.index("HRESULT WINAPI HookPresent(")
        fallback = source.index("++gFallbackRenderFrames;", present)
        warn = source.index("VELLUM VIDEO WARN: Present fallback active", present)
        self.assertLess(fallback, warn)

    def test_the_video_is_drawn_at_the_field_effect_marker(self) -> None:
        # v7: drawing at Present pins the video to the end of the frame, above the mobs, the
        # floating damage numbers and the UI - that is the bug this release fixes. The render call
        # therefore has to sit in the marker draw, and the marker draw has to consume exactly one
        # draw so the rest of the frame survives.
        source = SOURCE.read_text()
        signature = MARKER_SIGNATURE.read_text()
        self.assertIn('#include "MarkerSignature.h"', source)
        self.assertIn("MatchesFieldEffectA4R4G4B4", signature)
        self.assertIn("MatchesFieldEffectA8R8G8B8", signature)
        self.assertIn("0xF123", signature)
        self.assertIn("0x00112233u", signature)
        # The signature check has exactly one home; the host may not keep a second copy.
        self.assertNotIn("IsFieldEffectMarkerA4R4G4B4", code_only(source))
        self.assertNotIn("IsFieldEffectMarkerA8R8G8B8", code_only(source))
        # One shot consume: the bound flag is cleared before the render call, so only the marker's
        # own draw is swallowed instead of every draw until the next texture bind.
        consume = source.index("bool ConsumeMarkerDraw()")
        clear = source.index("gMarkerBound = false;", consume)
        render = source.index("gRender();", consume)
        self.assertLess(clear, render)
        self.assertLess(clear, source.index("StartVideo(code);", consume))
        # Both marker families have to be reachable from the D3D8 side, and the fifth pixel code
        # must only ever start a mapped Root Abyss screen.
        self.assertIn("beidou::marker::VellumCodeFromA4R4G4B4", source)
        self.assertIn("beidou::marker::VellumCodeFromA8R8G8B8", source)
        self.assertIn("if (hit.kind == kNoMarker && hit.code != 0) hit.kind = kVellumScene;", source)
        self.assertIn("if (kind == kVellumScene && (!gVideoPlaying || gActiveMarkerCode != code))", source)

    def test_present_hook_reports_channel_health(self) -> None:
        # Without the periodic status line a failed run cannot be told apart from a decoder that
        # never produced a frame. Keep the counters in the log.
        source = SOURCE.read_text()
        self.assertIn("LogChannelStatusesIfDue", source)
        for field in ("decoded=", "displayed=", "dropped=", "position="):
            self.assertIn(field, source)
        self.assertIn("kStatusLogIntervalMs", source)

    def test_verified_core_is_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(CORE.read_bytes()).hexdigest(), VERIFIED_CORE_SHA256)

    def test_shipped_binary_is_rebuilt_from_this_source(self) -> None:
        compiler = shutil.which("i686-w64-mingw32-g++")
        if compiler is None:
            self.skipTest("i686-w64-mingw32-g++ is not installed")
        with tempfile.TemporaryDirectory(prefix="beidou-vellum-contract-") as build_dir:
            output = Path(build_dir) / "BeiDouVellumVideoCompat.dll"
            completed = subprocess.run(
                [compiler, *BUILD_FLAGS, str(SOURCE), "-o", str(output), *BUILD_LIBS],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            # The linker writes the output file name into the export directory, so the file name
            # has to stay identical for this comparison to be meaningful.
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(),
                hashlib.sha256(SHIPPED.read_bytes()).hexdigest(),
                "clien/BeiDouVellumVideoCompat.dll is stale: rebuild with build.sh and ship it",
            )

    def test_build_script_keeps_the_outgoing_delivery(self) -> None:
        # v4 (11264) was lost because a build overwrites clien/ directly and the retired version
        # cannot be rebuilt byte for byte once the source has moved on. One backup per size.
        script = Path(__file__).with_name("build.sh").read_text()
        self.assertIn("BeiDouVellumVideoCompat.dll.size$outgoing_size", script)
        self.assertIn('stat -f %z "$output_file"', script)
        self.assertLess(script.index("BeiDouVellumVideoCompat.dll.size$outgoing_size"),
                        script.index('mv "$build_dir/BeiDouVellumVideoCompat.dll"'))

    def test_shipped_binary_carries_the_current_capture(self) -> None:
        binary = SHIPPED.read_bytes()
        for marker in NEW_MARKERS:
            self.assertIn(marker, binary)
        for retired in RETIRED_MARKERS:
            self.assertNotIn(retired, binary)
        self.assertIn(b"KERNEL32.dll", binary)
        self.assertIn(b"d3d8.dll", binary)

    def test_shipped_binary_does_not_reuse_a_retired_size(self) -> None:
        # clien/ is served to the client through a shared folder that caches by file size; an
        # equal length replacement is silently ignored. Keep the delivered size distinct.
        self.assertNotIn(SHIPPED.stat().st_size, RETIRED_SIZES)


if __name__ == "__main__":
    unittest.main()
