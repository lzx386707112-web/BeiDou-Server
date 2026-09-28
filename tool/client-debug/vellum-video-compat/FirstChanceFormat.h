// FirstChanceFormat.h
//
// First-chance C++ exception reporting: the text/logic half.
//
// This header deliberately avoids <windows.h> so the host compiler (clang++ on macOS) can
// compile it. The contract test turns "which occurrence writes the dump", "how a HRESULT is
// named" and "how the dump file is spelled" into executable assertions instead of comments.
//
// Why this exists (2026-09-28)
// ----------------------------
// The 13:11 session threw 19 `_com_error`s (0xE06D7363) and then the client popped the
// "invalid pointer" dialog, but no `first-chance-cpp-*.dmp` was written: the diagnostics engine
// (WzFileLogger.dll) only arms its first-chance dump after a null flash movie has been captured
// (`flash_render_guard action=capture_first_null_context`). That session had `flash_null_skips=0`,
// so the last - and only interesting - exception left no evidence at all.
//
// This module adds the missing half: every C++ exception leaves one summary line (with the real
// `_com_error::m_hr`, decoded straight from the exception record) and its call site, and the Nth one
// also leaves a full dump on disk.
//
// Why the call site is sampled here and not read out of the dump (2026-09-28, second round)
// -----------------------------------------------------------------------------------------
// v5 wrote its dump from a worker thread, so by the time MiniDumpWriteDump snapshots the process the
// faulting thread has already unwound past the throw: the v5 dump for occurrence 1 shows the main
// thread sitting in the Gr2D_DX8 render path with Esp 0x001AE784, i.e. 2.2 KB *above* the throwing
// Esp of 0x001ADED0 - the throw frames are simply not there any more. The engine has the same
// problem, and on top of it caps its sampling at `cpp_stack_samples=8` per session: in the 13:45
// session occurrences 13 and 14 (the last two before the client's filter popped the "invalid
// pointer" dialog) carry `stack_candidates="(sample_limit)"` and no call site at all.
// So we sample from the exception's own Esp, inside the handler, for **every** occurrence.

#ifndef BEIDOU_FIRST_CHANCE_FORMAT_H
#define BEIDOU_FIRST_CHANCE_FORMAT_H

#include <stddef.h>
#include <stdint.h>

namespace beidou {
namespace firstchance {

// MSVC raises this for every C++ exception; the diagnostics engine lists it as E06D7363.
constexpr uint32_t kCppExceptionCode = 0xE06D7363u;

// MSVC encodes the thrown object as {0x19930520, object, throw_info} in the exception parameters.
// `_com_error::m_hr` sits at object + 4 (see the E_POINTER notes in the project memory).
constexpr uint32_t kMsvcExceptionMagic = 0x19930520u;
constexpr size_t kThrownObjectOffset = 0x4;
constexpr size_t kMinimumCppParameters = 3;

// One summary line per occurrence, but never more than this per session: a broken resource loop
// must not turn the log into a multi-megabyte file.
constexpr unsigned kOccurrenceLogLimit = 64;

// `dump_first_chance_cpp_after` semantics: 0 disables the observer completely, N > 0 enables the
// per-occurrence summaries and writes one full dump when the Nth exception arrives.
constexpr unsigned kDisabledThreshold = 0;
constexpr unsigned kDefaultThreshold = 1;

// ---------------------------------------------------------------------------- text helpers
// No CRT: the DLL is linked with -nostdlib, so strlen/snprintf are unavailable.

struct TextCursor {
    char* cursor;
    char* end;
};

inline size_t TextLength(const char* text) {
    size_t length = 0;
    if (text == nullptr) return 0;
    while (text[length] != '\0') ++length;
    return length;
}

inline size_t TextRoom(const TextCursor& cursor) {
    return static_cast<size_t>(cursor.end - cursor.cursor);
}

inline bool AppendChar(TextCursor& cursor, char value) {
    if (TextRoom(cursor) < 1) return false;
    *cursor.cursor++ = value;
    return true;
}

inline bool AppendText(TextCursor& cursor, const char* text) {
    if (text == nullptr) return false;
    const size_t length = TextLength(text);
    if (TextRoom(cursor) < length) return false;
    for (size_t index = 0; index < length; ++index) cursor.cursor[index] = text[index];
    cursor.cursor += length;
    return true;
}

inline bool AppendUnsigned(TextCursor& cursor, unsigned value, unsigned minDigits) {
    char digits[12];
    unsigned count = 0;
    do {
        digits[count++] = static_cast<char>('0' + (value % 10u));
        value /= 10u;
    } while (value != 0u);
    while (count < minDigits) digits[count++] = '0';
    if (TextRoom(cursor) < count) return false;
    while (count > 0) *cursor.cursor++ = digits[--count];
    return true;
}

inline bool AppendHex(TextCursor& cursor, uint32_t value, unsigned digits) {
    static const char kHex[] = "0123456789abcdef";
    if (digits > 8) digits = 8;
    if (TextRoom(cursor) < digits) return false;
    for (unsigned index = 0; index < digits; ++index) {
        const unsigned shift = (digits - 1 - index) * 4u;
        cursor.cursor[index] = kHex[(value >> shift) & 0xfu];
    }
    cursor.cursor += digits;
    return true;
}

inline bool AppendPointer(TextCursor& cursor, const void* value) {
    if (!AppendText(cursor, "0x")) return false;
    return AppendHex(cursor, static_cast<uint32_t>(reinterpret_cast<uintptr_t>(value)), 8);
}

inline bool TerminateText(TextCursor& cursor) {
    if (TextRoom(cursor) < 1) return false;
    *cursor.cursor = '\0';
    return true;
}

inline void ResetCursor(TextCursor& cursor, char* buffer, size_t capacity) {
    cursor.cursor = buffer;
    cursor.end = buffer + capacity;
    if (capacity > 0) buffer[0] = '\0';
}

// ---------------------------------------------------------------------------- HRESULT naming
// Only the values we have actually met while debugging this client. Everything else stays
// unnamed on purpose: a wrong label is worse than none.
inline const char* HresultTag(int32_t hr) {
    switch (static_cast<uint32_t>(hr)) {
        case 0x80004001u: return "E_NOTIMPL";
        case 0x80004002u: return "E_NOINTERFACE";
        case 0x80004003u: return "E_POINTER";
        case 0x80004005u: return "E_FAIL";
        case 0x80070005u: return "E_ACCESSDENIED";
        case 0x8007000Eu: return "E_OUTOFMEMORY";
        case 0x80030002u: return "STG_E_FILENOTFOUND";
        case 0x80040154u: return "REGDB_E_CLASSNOTREG";
        case 0x800401F0u: return "CO_E_NOTINITIALIZED";
        default: return nullptr;
    }
}

// ---------------------------------------------------------------------------- stack sample
// The faulting stack, read at the throw point. Only words inside the game executable are kept: every
// throw site of this client lives in BeiDou.exe, and a short line is worth more than a complete one.
constexpr unsigned kStackSampleDwords = 96;      // 384 bytes above the faulting Esp
constexpr unsigned kStackSampleCandidates = 12;  // bounded so one occurrence stays one log line

struct StackCandidate {
    unsigned index;    // dword index from the faulting Esp, matching the engine's `sNN` layout
    uint32_t offset;   // offset inside the game executable
    bool verified;     // the five bytes before it are `E8 rel32` landing inside the executable
};

inline bool AppendHexTrimmed(TextCursor& cursor, uint32_t value) {
    unsigned digits = 8;
    while (digits > 1 && ((value >> ((digits - 1) * 4)) & 0xfu) == 0) --digits;
    return AppendHex(cursor, value, digits);
}

// ` stack="s49:+0x3fd5b* s52:+0xa497"` - a `*` means "checked: this really is a return address".
// The index lets the sample line up with the engine's own `stack_candidates`, same dword indexing.
inline bool AppendStackSample(TextCursor& cursor, const StackCandidate* items, unsigned count) {
    if (!AppendText(cursor, " stack=\"")) return false;
    if (count == 0) {
        if (!AppendText(cursor, "(none)")) return false;
        return AppendChar(cursor, '"');
    }
    for (unsigned position = 0; position < count; ++position) {
        if (position != 0 && !AppendChar(cursor, ' ')) return false;
        if (!AppendChar(cursor, 's')) return false;
        if (!AppendUnsigned(cursor, items[position].index, 1)) return false;
        if (!AppendText(cursor, ":+0x")) return false;
        if (!AppendHexTrimmed(cursor, items[position].offset)) return false;
        if (items[position].verified && !AppendChar(cursor, '*')) return false;
    }
    return AppendChar(cursor, '"');
}

// ---------------------------------------------------------------------------- thresholds
inline bool ObserverArmed(unsigned threshold) {
    return threshold != kDisabledThreshold;
}

inline bool ShouldSummarizeOccurrence(unsigned occurrence) {
    return occurrence >= 1 && occurrence <= kOccurrenceLogLimit;
}

// Exactly one dump per session, at the configured occurrence: later exceptions keep their summary
// line but never overwrite the file, so the artifact on disk stays the one that was asked for.
inline bool ShouldDumpAtOccurrence(unsigned occurrence, unsigned threshold) {
    if (!ObserverArmed(threshold)) return false;
    return occurrence == threshold;
}

// ---------------------------------------------------------------------------- artifact naming
// `first-chance-cpp-<YYYYMMDD-HHMMSS>-pid<PID>-<tick>.dmp`
inline bool BuildDumpFileName(
    char* buffer, size_t capacity, const char* stamp, unsigned pid, unsigned tick) {
    TextCursor cursor;
    ResetCursor(cursor, buffer, capacity);
    if (!AppendText(cursor, "first-chance-cpp-")) return false;
    if (!AppendText(cursor, stamp)) return false;
    if (!AppendText(cursor, "-pid")) return false;
    if (!AppendUnsigned(cursor, pid, 1)) return false;
    if (!AppendChar(cursor, '-')) return false;
    if (!AppendUnsigned(cursor, tick, 1)) return false;
    if (!AppendText(cursor, ".dmp")) return false;
    return TerminateText(cursor);
}

// `YYYYMMDD-HHMMSS`, matching the diagnostics engine's session stamp layout.
inline bool BuildSessionStamp(
    char* buffer, size_t capacity,
    unsigned year, unsigned month, unsigned day,
    unsigned hour, unsigned minute, unsigned second) {
    TextCursor cursor;
    ResetCursor(cursor, buffer, capacity);
    if (!AppendUnsigned(cursor, year, 4)) return false;
    if (!AppendUnsigned(cursor, month, 2)) return false;
    if (!AppendUnsigned(cursor, day, 2)) return false;
    if (!AppendChar(cursor, '-')) return false;
    if (!AppendUnsigned(cursor, hour, 2)) return false;
    if (!AppendUnsigned(cursor, minute, 2)) return false;
    if (!AppendUnsigned(cursor, second, 2)) return false;
    return TerminateText(cursor);
}

}  // namespace firstchance
}  // namespace beidou

#endif  // BEIDOU_FIRST_CHANCE_FORMAT_H
