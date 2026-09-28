// FirstChanceDump.h
//
// First-chance C++ exception observer: the Win32 half.
//
// Hooks the vectored exception chain, counts 0xE06D7363 (MSVC C++ exception), writes one summary
// line per occurrence - including the real HRESULT decoded out of the thrown object - and hands
// the Nth occurrence to a worker thread that stores a full minidump under `diagnostics\`.
//
// Hard rules (all enforced by the contract test):
//   * always return EXCEPTION_CONTINUE_SEARCH: the observer never changes control flow, never
//     swallows and never re-raises. The client's own filter still sees exactly what it saw before.
//   * threshold 0 disables the module completely - no hook, no allocation, no logging.
//   * one dump per session, at the configured occurrence; later exceptions only add a summary line.
//   * no CRT (the host links -nostdlib): only kernel32 Win32 APIs plus the pure helpers in
//     FirstChanceFormat.h.
//
// The dump is written from a worker thread, not from the exception callback: MiniDumpWriteDump can
// take a second on a 700 MB client and the callback must stay as short as possible.

#ifndef BEIDOU_FIRST_CHANCE_DUMP_H
#define BEIDOU_FIRST_CHANCE_DUMP_H

#include "FirstChanceFormat.h"

#include <windows.h>
#include <string.h>

namespace beidou {
namespace firstchance {

using LogLineFn = void (*)(const char*);

constexpr size_t kPathCapacity = 512;
// One occurrence line now carries a call-site sample as well, which needs the head room.
constexpr size_t kLineCapacity = 512;
constexpr size_t kStampCapacity = 32;
constexpr size_t kNameCapacity = 160;

// MINIDUMP_TYPE bits: data segments | handle data | unloaded modules | indirectly referenced
// memory | full memory info | thread info. Deliberately not WithFullMemory: the client sits at
// ~700 MB, and everything the forensic scripts need (thread stacks, the COM object reachable from
// the exception record, the module list) is covered by these bits at a fraction of the size.
constexpr uint32_t kDumpType =
    0x00000001u | 0x00000004u | 0x00000020u | 0x00000040u | 0x00000800u | 0x00001000u;

using MiniDumpWriteDumpFn = BOOL(WINAPI*)(HANDLE, DWORD, HANDLE, uint32_t, void*, void*, void*);

// dbghelp's MINIDUMP_EXCEPTION_INFORMATION, spelled out here so the host build stays free of the
// dbghelp SDK header: the library itself is resolved with LoadLibrary/GetProcAddress at runtime.
struct MinidumpExceptionInformation {
    DWORD threadId;
    EXCEPTION_POINTERS* exceptionPointers;
    BOOL clientPointers;
};

LogLineFn gLog = nullptr;
unsigned gThreshold = kDefaultThreshold;
char gDiagnosticsDir[kPathCapacity] = {0};
char gIniPath[kPathCapacity] = {0};
volatile LONG gOccurrences = 0;
volatile LONG gDumpStarted = 0;

struct Snapshot {
    EXCEPTION_RECORD record;
    CONTEXT context;
    DWORD threadId;
    unsigned occurrence;
};

Snapshot gSnapshot;

inline void EmitLine(const char* text) {
    if (gLog != nullptr) gLog(text);
}

// ---------------------------------------------------------------------------- paths
// `<exe dir>\diagnostics\` and `<exe dir>\beidou_diagnostics.ini`, i.e. exactly the file the
// diagnostics engine reads, so one ini keeps controlling both.
inline bool BuildPaths() {
    char modulePath[kPathCapacity] = {0};
    const DWORD length =
        GetModuleFileNameA(nullptr, modulePath, static_cast<DWORD>(kPathCapacity));
    if (length == 0 || length >= kPathCapacity) return false;
    size_t cut = 0;
    for (size_t index = 0; index < length; ++index) {
        if (modulePath[index] == '\\' || modulePath[index] == '/') cut = index + 1;
    }
    modulePath[cut] = '\0';

    TextCursor cursor;
    ResetCursor(cursor, gDiagnosticsDir, kPathCapacity);
    if (!AppendText(cursor, modulePath)) return false;
    if (!AppendText(cursor, "diagnostics\\")) return false;
    if (!TerminateText(cursor)) return false;

    ResetCursor(cursor, gIniPath, kPathCapacity);
    if (!AppendText(cursor, modulePath)) return false;
    if (!AppendText(cursor, "beidou_diagnostics.ini")) return false;
    return TerminateText(cursor);
}

// ---------------------------------------------------------------------------- summary line
inline bool ReadHresult(const void* object, int32_t& value) {
    if (object == nullptr) return false;
    SIZE_T read = 0;
    const char* address = static_cast<const char*>(object) + kThrownObjectOffset;
    if (!ReadProcessMemory(GetCurrentProcess(), address, &value, sizeof(value), &read)) return false;
    return read == sizeof(value);
}

// ---------------------------------------------------------------------------- faulting stack
// Every throw site in this client lives in BeiDou.exe, so sampling only its image keeps the line
// short and the offline reading unambiguous. The range comes from our own PE header rather than a
// hard-coded size, so a rebuilt executable cannot silently invalidate it.
uint32_t gExeBase = 0;
uint32_t gExeEnd = 0;

inline bool ResolveExeRange() {
    const unsigned char* base = reinterpret_cast<const unsigned char*>(GetModuleHandleA(nullptr));
    if (base == nullptr) return false;
    const uint32_t lfanew = *reinterpret_cast<const uint32_t*>(base + 0x3c);
    if (lfanew < 0x40 || lfanew > 0x1000) return false;
    const unsigned char* image = base + lfanew;
    if (image[0] != 'P' || image[1] != 'E' || image[2] != 0 || image[3] != 0) return false;
    if (*reinterpret_cast<const uint16_t*>(image + 0x18) != 0x010b) return false;   // PE32
    const uint32_t size = *reinterpret_cast<const uint32_t*>(image + 0x50);         // SizeOfImage
    if (size == 0) return false;
    gExeBase = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(base));
    gExeEnd = gExeBase + size;
    return true;
}

// A dword that looks like a code address is only a return address if a `call` precedes it. Checking
// that is what separates the real chain from the strings and constants that also sit on the stack.
inline bool PrecededByCallIntoExe(uint32_t value) {
    if (value < 5) return false;
    unsigned char bytes[5];
    SIZE_T read = 0;
    const uint32_t start = value - 5;
    if (!ReadProcessMemory(
            GetCurrentProcess(),
            reinterpret_cast<const void*>(static_cast<uintptr_t>(start)),
            bytes, sizeof(bytes), &read)) {
        return false;
    }
    if (read != sizeof(bytes) || bytes[0] != 0xE8) return false;
    int32_t relative = 0;
    memcpy(&relative, bytes + 1, sizeof(relative));
    const uint32_t target = (value + static_cast<uint32_t>(relative)) & 0xffffffffu;
    return target >= gExeBase && target < gExeEnd;
}

inline void AppendFaultingStack(TextCursor& cursor, const CONTEXT* context) {
    StackCandidate items[kStackSampleCandidates];
    unsigned count = 0;
    if (context != nullptr && gExeBase != 0 && context->Esp >= 0x10000u) {
        uint32_t words[kStackSampleDwords];
        SIZE_T read = 0;
        if (ReadProcessMemory(
                GetCurrentProcess(),
                reinterpret_cast<const void*>(static_cast<uintptr_t>(context->Esp)),
                words, sizeof(words), &read) && read >= sizeof(uint32_t)) {
            const unsigned available = static_cast<unsigned>(read / sizeof(uint32_t));
            for (unsigned index = 0; index < available && count < kStackSampleCandidates; ++index) {
                const uint32_t value = words[index];
                if (value < gExeBase || value >= gExeEnd) continue;
                items[count].index = index;
                items[count].offset = value - gExeBase;
                items[count].verified = PrecededByCallIntoExe(value);
                ++count;
            }
        }
    }
    AppendStackSample(cursor, items, count);
}

inline void SummarizeOccurrence(unsigned occurrence, const EXCEPTION_POINTERS* info) {
    const EXCEPTION_RECORD* record = info->ExceptionRecord;
    char line[kLineCapacity];
    TextCursor cursor;
    ResetCursor(cursor, line, kLineCapacity);

    const void* object = nullptr;
    if (record->NumberParameters >= kMinimumCppParameters &&
        record->ExceptionInformation[0] == kMsvcExceptionMagic) {
        object = reinterpret_cast<const void*>(record->ExceptionInformation[1]);
    }

    AppendText(cursor, "FIRST-CHANCE CPP: occurrence=");
    AppendUnsigned(cursor, occurrence, 1);
    AppendText(cursor, " code=0xe06d7363");
    AppendText(cursor, " tid=");
    AppendUnsigned(cursor, static_cast<unsigned>(GetCurrentThreadId()), 1);
    AppendText(cursor, " address=");
    AppendPointer(cursor, record->ExceptionAddress);
    AppendText(cursor, " object=");
    if (object != nullptr) {
        AppendPointer(cursor, object);
    } else {
        AppendText(cursor, "(none)");
    }
    AppendText(cursor, " hr=");
    int32_t hr = 0;
    if (object != nullptr && ReadHresult(object, hr)) {
        AppendText(cursor, "0x");
        AppendHex(cursor, static_cast<uint32_t>(hr), 8);
        const char* tag = HresultTag(hr);
        if (tag != nullptr) {
            AppendChar(cursor, ' ');
            AppendText(cursor, tag);
        }
    } else {
        AppendText(cursor, "(unreadable)");
    }
    AppendFaultingStack(cursor, info->ContextRecord);
    TerminateText(cursor);
    EmitLine(line);
}

// ---------------------------------------------------------------------------- dump worker
inline void CaptureSnapshot(const EXCEPTION_POINTERS* info, unsigned occurrence) {
    gSnapshot.occurrence = occurrence;
    gSnapshot.threadId = GetCurrentThreadId();
    if (info->ExceptionRecord != nullptr) {
        memcpy(&gSnapshot.record, info->ExceptionRecord, sizeof(EXCEPTION_RECORD));
    } else {
        memset(&gSnapshot.record, 0, sizeof(gSnapshot.record));
    }
    if (info->ContextRecord != nullptr) {
        memcpy(&gSnapshot.context, info->ContextRecord, sizeof(CONTEXT));
    } else {
        memset(&gSnapshot.context, 0, sizeof(gSnapshot.context));
    }
}

inline DWORD WINAPI DumpWorker(LPVOID) {
    CreateDirectoryA(gDiagnosticsDir, nullptr);

    SYSTEMTIME local;
    GetLocalTime(&local);
    char stamp[kStampCapacity] = {0};
    if (!BuildSessionStamp(
            stamp, kStampCapacity, local.wYear, local.wMonth, local.wDay,
            local.wHour, local.wMinute, local.wSecond)) {
        EmitLine("FIRST-CHANCE DUMP: status=failed detail=build_stamp");
        return 1;
    }
    char name[kNameCapacity] = {0};
    if (!BuildDumpFileName(
            name, kNameCapacity, stamp, static_cast<unsigned>(GetCurrentProcessId()),
            static_cast<unsigned>(GetTickCount()))) {
        EmitLine("FIRST-CHANCE DUMP: status=failed detail=build_name");
        return 2;
    }
    char path[kPathCapacity] = {0};
    TextCursor cursor;
    ResetCursor(cursor, path, kPathCapacity);
    if (!AppendText(cursor, gDiagnosticsDir) || !AppendText(cursor, name) ||
        !TerminateText(cursor)) {
        EmitLine("FIRST-CHANCE DUMP: status=failed detail=build_path");
        return 3;
    }

    HMODULE dbghelp = LoadLibraryW(L"dbghelp.dll");
    if (dbghelp == nullptr) {
        EmitLine("FIRST-CHANCE DUMP: status=failed detail=load_dbghelp");
        return 4;
    }
    MiniDumpWriteDumpFn write = reinterpret_cast<MiniDumpWriteDumpFn>(
        reinterpret_cast<void*>(GetProcAddress(dbghelp, "MiniDumpWriteDump")));
    if (write == nullptr) {
        EmitLine("FIRST-CHANCE DUMP: status=failed detail=missing_export");
        return 5;
    }

    HANDLE file = CreateFileA(
        path, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        char line[kLineCapacity];
        TextCursor failed;
        ResetCursor(failed, line, kLineCapacity);
        AppendText(failed, "FIRST-CHANCE DUMP: status=failed detail=create_file error=");
        AppendUnsigned(failed, static_cast<unsigned>(GetLastError()), 1);
        AppendText(failed, " path=\"");
        AppendText(failed, path);
        AppendChar(failed, '"');
        TerminateText(failed);
        EmitLine(line);
        return 6;
    }

    EXCEPTION_POINTERS pointers;
    pointers.ExceptionRecord = &gSnapshot.record;
    pointers.ContextRecord = &gSnapshot.context;
    MinidumpExceptionInformation exceptionInfo;
    exceptionInfo.threadId = gSnapshot.threadId;
    exceptionInfo.exceptionPointers = &pointers;
    exceptionInfo.clientPointers = FALSE;

    const BOOL stored = write(
        GetCurrentProcess(), GetCurrentProcessId(), file, kDumpType, &exceptionInfo, nullptr,
        nullptr);
    const DWORD error = stored ? 0 : GetLastError();
    CloseHandle(file);

    char line[kLineCapacity];
    TextCursor result;
    ResetCursor(result, line, kLineCapacity);
    AppendText(result, stored ? "FIRST-CHANCE DUMP: status=ok reason=first-chance-cpp"
                              : "FIRST-CHANCE DUMP: status=failed reason=first-chance-cpp");
    AppendText(result, " occurrence=");
    AppendUnsigned(result, gSnapshot.occurrence, 1);
    AppendText(result, " error=");
    AppendUnsigned(result, static_cast<unsigned>(error), 1);
    AppendText(result, " path=\"");
    AppendText(result, path);
    AppendChar(result, '"');
    TerminateText(result);
    EmitLine(line);

    if (!stored) DeleteFileA(path);
    return stored ? 0 : 7;
}

// ---------------------------------------------------------------------------- vectored handler
inline LONG CALLBACK HandleException(EXCEPTION_POINTERS* info) {
    if (info == nullptr || info->ExceptionRecord == nullptr) return EXCEPTION_CONTINUE_SEARCH;
    const EXCEPTION_RECORD* record = info->ExceptionRecord;
    if (record->ExceptionCode != kCppExceptionCode) return EXCEPTION_CONTINUE_SEARCH;
    if (!ObserverArmed(gThreshold) || gLog == nullptr) return EXCEPTION_CONTINUE_SEARCH;

    const unsigned occurrence = static_cast<unsigned>(InterlockedIncrement(&gOccurrences));
    if (ShouldSummarizeOccurrence(occurrence)) SummarizeOccurrence(occurrence, info);

    if (ShouldDumpAtOccurrence(occurrence, gThreshold) &&
        InterlockedExchange(&gDumpStarted, 1) == 0) {
        CaptureSnapshot(info, occurrence);
        HANDLE worker = CreateThread(nullptr, 0, DumpWorker, nullptr, 0, nullptr);
        if (worker != nullptr) CloseHandle(worker);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

// ---------------------------------------------------------------------------- installation
inline bool Install(LogLineFn log) {
    gLog = log;
    if (!BuildPaths()) {
        EmitLine("FIRST-CHANCE: status=failed detail=module_path");
        return false;
    }
    const unsigned threshold = GetPrivateProfileIntA(
        "diagnostics", "dump_first_chance_cpp_after", kDefaultThreshold, gIniPath);
    gThreshold = threshold;
    if (!ObserverArmed(threshold)) {
        EmitLine("FIRST-CHANCE: status=disabled dump_first_chance_cpp_after=0");
        return false;
    }
    ResolveExeRange();
    if (AddVectoredExceptionHandler(1, &HandleException) == nullptr) {
        EmitLine("FIRST-CHANCE: status=failed detail=add_veh");
        return false;
    }

    char line[kLineCapacity];
    TextCursor cursor;
    ResetCursor(cursor, line, kLineCapacity);
    AppendText(cursor, "FIRST-CHANCE: status=armed filter=0xe06d7363 summarize_limit=");
    AppendUnsigned(cursor, kOccurrenceLogLimit, 1);
    AppendText(cursor, " dump_after=");
    AppendUnsigned(cursor, threshold, 1);
    // The sampled range is printed once so a line that says `(none)` can be told apart from a
    // sampler that never resolved the executable to begin with.
    AppendText(cursor, " exe=");
    if (gExeBase != 0) {
        AppendText(cursor, "0x");
        AppendHex(cursor, gExeBase, 8);
        AppendText(cursor, "+0x");
        AppendHexTrimmed(cursor, gExeEnd - gExeBase);
    } else {
        AppendText(cursor, "unresolved");
    }
    AppendText(cursor, " stack_dwords=");
    AppendUnsigned(cursor, kStackSampleDwords, 1);
    AppendText(cursor, " ini=\"");
    AppendText(cursor, gIniPath);
    AppendChar(cursor, '"');
    TerminateText(cursor);
    EmitLine(line);
    return true;
}

}  // namespace firstchance
}  // namespace beidou

#endif  // BEIDOU_FIRST_CHANCE_DUMP_H
