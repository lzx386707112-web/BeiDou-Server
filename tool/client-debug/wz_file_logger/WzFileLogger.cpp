// Lightweight debug DLL for BeiDou.exe.
//
// Logs resource file opens and message boxes after BeiDou.exe loads this DLL.
// Build as 32-bit.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
#include <psapi.h>
#include <tlhelp32.h>

typedef HANDLE(WINAPI *CreateFileWFn)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef HANDLE(WINAPI *CreateFileAFn)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef int(WINAPI *MessageBoxWFn)(HWND, LPCWSTR, LPCWSTR, UINT);
typedef int(WINAPI *MessageBoxAFn)(HWND, LPCSTR, LPCSTR, UINT);
typedef int(WINAPI *MessageBoxExWFn)(HWND, LPCWSTR, LPCWSTR, UINT, WORD);
typedef int(WINAPI *MessageBoxExAFn)(HWND, LPCSTR, LPCSTR, UINT, WORD);
typedef int(WINAPI *MessageBoxIndirectWFn)(const MSGBOXPARAMSW *);
typedef int(WINAPI *MessageBoxIndirectAFn)(const MSGBOXPARAMSA *);
typedef VOID(WINAPI *FatalAppExitWFn)(UINT, LPCWSTR);
typedef VOID(WINAPI *FatalAppExitAFn)(UINT, LPCSTR);
typedef LRESULT(WINAPI *DispatchMessageWFn)(const MSG *);
typedef LRESULT(WINAPI *DispatchMessageAFn)(const MSG *);
typedef HMODULE(WINAPI *LoadLibraryWFn)(LPCWSTR);
typedef HMODULE(WINAPI *LoadLibraryAFn)(LPCSTR);
typedef HMODULE(WINAPI *LoadLibraryExAFn)(LPCSTR, HANDLE, DWORD);
typedef HFILE(WINAPI *LopenFn)(LPCSTR, int);
typedef HANDLE(WINAPI *FindFirstFileAFn)(LPCSTR, LPWIN32_FIND_DATAA);
typedef FARPROC(WINAPI *GetProcAddressFn)(HMODULE, LPCSTR);
typedef HANDLE(WINAPI *CreateFileMappingAFn)(HANDLE, LPSECURITY_ATTRIBUTES, DWORD, DWORD, DWORD, LPCSTR);
typedef HANDLE(WINAPI *OpenFileMappingAFn)(DWORD, BOOL, LPCSTR);
typedef LPVOID(WINAPI *MapViewOfFileFn)(HANDLE, DWORD, DWORD, DWORD, SIZE_T);
typedef BOOL(WINAPI *ReadFileFn)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL(WINAPI *CloseHandleFn)(HANDLE);
typedef LPTOP_LEVEL_EXCEPTION_FILTER(WINAPI *SetUnhandledExceptionFilterFn)(LPTOP_LEVEL_EXCEPTION_FILTER);
typedef VOID(WINAPI *ExitProcessFn)(UINT);
typedef BOOL(WINAPI *TerminateProcessFn)(HANDLE, UINT);
typedef BOOL(WINAPI *GetProcessMemoryInfoFn)(HANDLE, PPROCESS_MEMORY_COUNTERS, DWORD);
typedef BOOL(WINAPI *MiniDumpWriteDumpFn)(HANDLE, DWORD, HANDLE, MINIDUMP_TYPE, PMINIDUMP_EXCEPTION_INFORMATION, PMINIDUMP_USER_STREAM_INFORMATION, PMINIDUMP_CALLBACK_INFORMATION);
typedef DWORD(WINAPI *GetFinalPathNameByHandleWFn)(HANDLE, LPWSTR, DWORD, DWORD);
typedef void *(__cdecl *FopenFn)(const char *, const char *);
typedef size_t(__cdecl *FreadFn)(void *, size_t, size_t, void *);
typedef int(__cdecl *RenderFlashFn)(int, int, int);

#if defined(__GNUC__) && !defined(_MSC_VER)
extern "C" void *memset(void *dest, int value, size_t count) {
    unsigned char *p = (unsigned char *)dest;
    while (count-- > 0) {
        *p++ = (unsigned char)value;
    }
    return dest;
}
#endif

static CreateFileWFn RealCreateFileW = NULL;
static CreateFileAFn RealCreateFileA = NULL;
static MessageBoxWFn RealMessageBoxW = NULL;
static MessageBoxAFn RealMessageBoxA = NULL;
static MessageBoxExWFn RealMessageBoxExW = NULL;
static MessageBoxExAFn RealMessageBoxExA = NULL;
static MessageBoxIndirectWFn RealMessageBoxIndirectW = NULL;
static MessageBoxIndirectAFn RealMessageBoxIndirectA = NULL;
static FatalAppExitWFn RealFatalAppExitW = NULL;
static FatalAppExitAFn RealFatalAppExitA = NULL;
static DispatchMessageWFn RealDispatchMessageW = NULL;
static DispatchMessageAFn RealDispatchMessageA = NULL;
static LoadLibraryWFn RealLoadLibraryW = NULL;
static LoadLibraryAFn RealLoadLibraryA = NULL;
static LoadLibraryExAFn RealLoadLibraryExA = NULL;
static LopenFn RealLopen = NULL;
static FindFirstFileAFn RealFindFirstFileA = NULL;
static GetProcAddressFn RealGetProcAddress = NULL;
static CreateFileMappingAFn RealCreateFileMappingA = NULL;
static OpenFileMappingAFn RealOpenFileMappingA = NULL;
static MapViewOfFileFn RealMapViewOfFile = NULL;
static ReadFileFn RealReadFile = NULL;
static CloseHandleFn RealCloseHandle = NULL;
static SetUnhandledExceptionFilterFn RealSetUnhandledExceptionFilter = NULL;
static ExitProcessFn RealExitProcess = NULL;
static TerminateProcessFn RealTerminateProcess = NULL;
static GetFinalPathNameByHandleWFn RealGetFinalPathNameByHandleW = NULL;
static FopenFn RealFopen = NULL;
static FreadFn RealFread = NULL;
static RenderFlashFn RealRenderFlash = NULL;
static PVOID volatile *g_flashMovieSlot = NULL;
static HMODULE g_flashRendererHeldModule = NULL;

static CRITICAL_SECTION g_logLock;
static CRITICAL_SECTION g_resourceLock;
static HMODULE g_selfModule = NULL;
static WCHAR g_logPath[MAX_PATH];
static WCHAR g_exeDir[MAX_PATH];
static WCHAR g_diagnosticsDir[MAX_PATH];
static WCHAR g_sessionId[64];
static volatile LONG g_patching = 0;
static volatile LONG g_verboseFileLogs = 300;
static volatile LONG g_patchSummaryLogs = 30;
static volatile LONG g_eventSequence = 0;
static volatile LONG g_shutdownRequested = 0;
static volatile LONG g_exitDumpStarted = 0;
static volatile LONG g_errorDialogDumpStarted = 0;
static volatile LONG g_karingMapDetected = 0;
static volatile LONG g_bossSceneCompatLoadStarted = 0;
static volatile LONG g_firstChanceExceptionCount = 0;
static volatile LONG g_cppFirstChanceExceptionCount = 0;
static volatile LONG g_firstChanceExceptionLogging = 0;
static volatile LONG g_cppExceptionDumpStarted = 0;
static volatile LONG g_flashRenderNullSkips = 0;
static volatile LONG g_flashNullDumpStarted = 0;
static volatile LONG g_clientWindowReady = 0;
static BOOL g_inLog = FALSE;
static WCHAR g_wideLogLine[4096];
static CHAR g_utf8LogLine[16384];
static HANDLE g_watchdogThread = NULL;
static LPTOP_LEVEL_EXCEPTION_FILTER g_previousExceptionFilter = NULL;
static PVOID g_vectoredExceptionHandler = NULL;
static DWORD g_healthIntervalMs = 1000;
static DWORD g_hangThresholdMs = 5000;
static DWORD g_highCpuThreshold = 70;
static DWORD g_highCpuThresholdMs = 3000;
static BOOL g_dumpOnHang = TRUE;
static BOOL g_manualDumpHotkey = TRUE;
static BOOL g_logFirstChanceExceptions = TRUE;
// Successful mappings are very frequent during client startup. Keep failure
// diagnostics enabled while avoiding path lookup and synchronous I/O on the
// normal resource preload path.
static BOOL g_logSuccessfulMappings = FALSE;

struct ResourceHandleEntry {
    HANDLE handle;
    WCHAR path[MAX_PATH];
    ULONGLONG openedTick;
    ULONGLONG totalBytesRead;
};

struct RecentResourceRead {
    ULONGLONG tick;
    ULONGLONG offset;
    DWORD requested;
    DWORD actual;
    DWORD elapsedMs;
    BOOL success;
    WCHAR path[MAX_PATH];
};

struct RecentMappingEvent {
    ULONGLONG tick;
    WCHAR api[32];
    HANDLE input;
    HANDLE result;
    DWORD error;
    DWORD access;
    DWORD offsetHigh;
    DWORD offsetLow;
    DWORD bytes;
    WCHAR path[MAX_PATH];
};

struct RecentUiMessage {
    ULONGLONG tick;
    DWORD tid;
    HWND window;
    UINT message;
    WPARAM wParam;
    LPARAM lParam;
};

static const int kMaxResourceHandles = 256;
static ResourceHandleEntry g_resourceHandles[kMaxResourceHandles];
static const int kRecentResourceReadCount = 128;
static RecentResourceRead g_recentResourceReads[kRecentResourceReadCount];
static volatile LONG g_recentResourceReadSequence = 0;
static const int kRecentMappingEventCount = 64;
static RecentMappingEvent g_recentMappingEvents[kRecentMappingEventCount];
static volatile LONG g_recentMappingEventSequence = 0;
static const int kRecentUiMessageCount = 128;
static RecentUiMessage g_recentUiMessages[kRecentUiMessageCount];
static volatile LONG g_recentUiMessageSequence = 0;
static WCHAR g_lastResourcePath[MAX_PATH];
static ULONGLONG g_lastResourceOffset = 0;
static DWORD g_lastResourceBytes = 0;
static ULONGLONG g_lastResourceTick = 0;

static void PatchAllModules();
static HMODULE WINAPI HookLoadLibraryW(LPCWSTR fileName);
static HMODULE WINAPI HookLoadLibraryA(LPCSTR fileName);
static HMODULE WINAPI HookLoadLibraryExA(LPCSTR fileName, HANDLE file, DWORD flags);
static HANDLE WINAPI HookFindFirstFileA(LPCSTR fileName, LPWIN32_FIND_DATAA findFileData);
static FARPROC WINAPI HookGetProcAddress(HMODULE module, LPCSTR procName);
static FARPROC WINAPI HookGr2DGetProcAddress(HMODULE module, LPCSTR procName);
static int __cdecl HookRenderFlash(int x, int y, int tick);
static int WINAPI HookMessageBoxW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type);
static int WINAPI HookMessageBoxA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type);
static int WINAPI HookMessageBoxExW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type, WORD languageId);
static int WINAPI HookMessageBoxExA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type, WORD languageId);
static int WINAPI HookMessageBoxIndirectW(const MSGBOXPARAMSW *params);
static int WINAPI HookMessageBoxIndirectA(const MSGBOXPARAMSA *params);
static VOID WINAPI HookFatalAppExitW(UINT action, LPCWSTR messageText);
static VOID WINAPI HookFatalAppExitA(UINT action, LPCSTR messageText);
static LRESULT WINAPI HookDispatchMessageW(const MSG *message);
static LRESULT WINAPI HookDispatchMessageA(const MSG *message);
static HANDLE WINAPI HookCreateFileMappingA(HANDLE file, LPSECURITY_ATTRIBUTES attrs, DWORD protect, DWORD maxSizeHigh, DWORD maxSizeLow, LPCSTR name);
static HANDLE WINAPI HookOpenFileMappingA(DWORD desiredAccess, BOOL inheritHandle, LPCSTR name);
static LPVOID WINAPI HookMapViewOfFile(HANDLE mapping, DWORD desiredAccess, DWORD offsetHigh, DWORD offsetLow, SIZE_T bytesToMap);
static BOOL WINAPI HookReadFile(HANDLE file, LPVOID buffer, DWORD bytesToRead, LPDWORD bytesRead, LPOVERLAPPED overlapped);
static BOOL WINAPI HookCloseHandle(HANDLE object);
static LPTOP_LEVEL_EXCEPTION_FILTER WINAPI HookSetUnhandledExceptionFilter(LPTOP_LEVEL_EXCEPTION_FILTER filter);
static VOID WINAPI HookExitProcess(UINT exitCode);
static BOOL WINAPI HookTerminateProcess(HANDLE process, UINT exitCode);
static LONG WINAPI DiagnosticExceptionFilter(EXCEPTION_POINTERS *exceptionPointers);
static LONG WINAPI DiagnosticVectoredExceptionHandler(EXCEPTION_POINTERS *exceptionPointers);
static BOOL WriteDiagnosticDump(const WCHAR *reason, EXCEPTION_POINTERS *exceptionPointers);
static BOOL ShouldLogPath(const WCHAR *path);
static void AppendLine(const WCHAR *line);
static void DetectErrorDialog();
static BOOL IsErrorDialogText(const WCHAR *text);
static void CaptureIncidentEvidence(const WCHAR *reason, BOOL writeDump, EXCEPTION_POINTERS *exceptionPointers);
static void *__cdecl HookFopen(const char *fileName, const char *mode);
static size_t __cdecl HookFread(void *buffer, size_t size, size_t count, void *stream);

static void RefreshOriginalFunctions() {
    HMODULE kernel32 = GetModuleHandleW(L"KERNEL32.dll");
    HMODULE user32 = GetModuleHandleW(L"USER32.dll");

    if (kernel32 != NULL) {
        RealGetProcAddress = (GetProcAddressFn)GetProcAddress(kernel32, "GetProcAddress");
        RealCreateFileW = (CreateFileWFn)GetProcAddress(kernel32, "CreateFileW");
        RealCreateFileA = (CreateFileAFn)GetProcAddress(kernel32, "CreateFileA");
        RealLoadLibraryW = (LoadLibraryWFn)GetProcAddress(kernel32, "LoadLibraryW");
        RealLoadLibraryA = (LoadLibraryAFn)GetProcAddress(kernel32, "LoadLibraryA");
        RealLoadLibraryExA = (LoadLibraryExAFn)GetProcAddress(kernel32, "LoadLibraryExA");
        RealLopen = (LopenFn)GetProcAddress(kernel32, "_lopen");
        RealFindFirstFileA = (FindFirstFileAFn)GetProcAddress(kernel32, "FindFirstFileA");
        RealCreateFileMappingA = (CreateFileMappingAFn)GetProcAddress(kernel32, "CreateFileMappingA");
        RealOpenFileMappingA = (OpenFileMappingAFn)GetProcAddress(kernel32, "OpenFileMappingA");
        RealMapViewOfFile = (MapViewOfFileFn)GetProcAddress(kernel32, "MapViewOfFile");
        RealReadFile = (ReadFileFn)GetProcAddress(kernel32, "ReadFile");
        RealCloseHandle = (CloseHandleFn)GetProcAddress(kernel32, "CloseHandle");
        RealSetUnhandledExceptionFilter = (SetUnhandledExceptionFilterFn)GetProcAddress(kernel32, "SetUnhandledExceptionFilter");
        RealExitProcess = (ExitProcessFn)GetProcAddress(kernel32, "ExitProcess");
        RealTerminateProcess = (TerminateProcessFn)GetProcAddress(kernel32, "TerminateProcess");
        RealFatalAppExitW = (FatalAppExitWFn)GetProcAddress(kernel32, "FatalAppExitW");
        RealFatalAppExitA = (FatalAppExitAFn)GetProcAddress(kernel32, "FatalAppExitA");
        RealGetFinalPathNameByHandleW = (GetFinalPathNameByHandleWFn)GetProcAddress(kernel32, "GetFinalPathNameByHandleW");
    }
    if (user32 != NULL) {
        RealMessageBoxW = (MessageBoxWFn)GetProcAddress(user32, "MessageBoxW");
        RealMessageBoxA = (MessageBoxAFn)GetProcAddress(user32, "MessageBoxA");
        RealMessageBoxExW = (MessageBoxExWFn)GetProcAddress(user32, "MessageBoxExW");
        RealMessageBoxExA = (MessageBoxExAFn)GetProcAddress(user32, "MessageBoxExA");
        RealMessageBoxIndirectW = (MessageBoxIndirectWFn)GetProcAddress(user32, "MessageBoxIndirectW");
        RealMessageBoxIndirectA = (MessageBoxIndirectAFn)GetProcAddress(user32, "MessageBoxIndirectA");
        RealDispatchMessageW = (DispatchMessageWFn)GetProcAddress(user32, "DispatchMessageW");
        RealDispatchMessageA = (DispatchMessageAFn)GetProcAddress(user32, "DispatchMessageA");
    }
    HMODULE msvcrt = GetModuleHandleW(L"MSVCRT.dll");
    if (msvcrt != NULL) {
        RealFopen = (FopenFn)GetProcAddress(msvcrt, "fopen");
        RealFread = (FreadFn)GetProcAddress(msvcrt, "fread");
    }
}

static WCHAR ToLowerW(WCHAR c) {
    if (c >= L'A' && c <= L'Z') {
        return (WCHAR)(c + (L'a' - L'A'));
    }
    return c;
}

static char ToLowerA(char c) {
    if (c >= 'A' && c <= 'Z') {
        return (char)(c + ('a' - 'A'));
    }
    return c;
}

static BOOL EqualsNoCaseA(const char *a, const char *b) {
    if (a == NULL || b == NULL) {
        return FALSE;
    }
    while (*a && *b) {
        if (ToLowerA(*a) != ToLowerA(*b)) {
            return FALSE;
        }
        ++a;
        ++b;
    }
    return *a == '\0' && *b == '\0';
}

static int CompareNoCaseW(const WCHAR *a, const WCHAR *b, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        WCHAR ca = ToLowerW(a[i]);
        WCHAR cb = ToLowerW(b[i]);
        if (ca != cb) {
            return (ca < cb) ? -1 : 1;
        }
        if (ca == L'\0') {
            return 0;
        }
    }
    return 0;
}

static WCHAR *FindLastSlash(WCHAR *s) {
    WCHAR *last = NULL;
    for (; *s; ++s) {
        if (*s == L'\\' || *s == L'/') {
            last = s;
        }
    }
    return last;
}

static BOOL StartsWithNoCase(const WCHAR *s, const WCHAR *prefix) {
    size_t prefixLen = lstrlenW(prefix);
    return CompareNoCaseW(s, prefix, prefixLen) == 0;
}

static BOOL ContainsNoCase(const WCHAR *s, const WCHAR *needle) {
    if (s == NULL || needle == NULL) {
        return FALSE;
    }
    size_t needleLen = lstrlenW(needle);
    for (const WCHAR *p = s; *p; ++p) {
        if (CompareNoCaseW(p, needle, needleLen) == 0) {
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL EqualsNoCaseW(const WCHAR *a, const WCHAR *b) {
    if (a == NULL || b == NULL) {
        return FALSE;
    }
    while (*a && *b) {
        if (ToLowerW(*a) != ToLowerW(*b)) {
            return FALSE;
        }
        ++a;
        ++b;
    }
    return *a == L'\0' && *b == L'\0';
}

static BOOL IsBossSceneMapPath(const WCHAR *path) {
    if (path == NULL
            || (!ContainsNoCase(path, L"\\Map\\Map\\Map4\\")
                && !ContainsNoCase(path, L"/Map/Map/Map4/"))) {
        return FALSE;
    }

    const WCHAR *fileName = path;
    for (const WCHAR *p = path; *p; ++p) {
        if (*p == L'\\' || *p == L'/') {
            fileName = p + 1;
        }
    }

    static const WCHAR *const kBossSceneMapFiles[] = {
        L"410007100.img", L"410007120.img", L"410007140.img",
        L"410007160.img", L"410007180.img", L"410007200.img",
        L"410007220.img", L"410007240.img", L"410007260.img",
        L"410007280.img", L"410007300.img",
        L"450004150.img", L"450004250.img",
    };
    for (size_t i = 0;
            i < sizeof(kBossSceneMapFiles) / sizeof(kBossSceneMapFiles[0]); ++i) {
        if (EqualsNoCaseW(fileName, kBossSceneMapFiles[i])) {
            return TRUE;
        }
    }
    return FALSE;
}

static ULONGLONG CurrentTick() {
    return GetTickCount64();
}

static int FindResourceHandleLocked(HANDLE handle) {
    for (int i = 0; i < kMaxResourceHandles; ++i) {
        if (g_resourceHandles[i].handle == handle) {
            return i;
        }
    }
    return -1;
}

static void TrackResourceHandle(HANDLE handle, const WCHAR *path) {
    if (handle == NULL || handle == INVALID_HANDLE_VALUE || !ShouldLogPath(path)) {
        return;
    }
    EnterCriticalSection(&g_resourceLock);
    int slot = FindResourceHandleLocked(handle);
    if (slot < 0) {
        for (int i = 0; i < kMaxResourceHandles; ++i) {
            if (g_resourceHandles[i].handle == NULL) {
                slot = i;
                break;
            }
        }
    }
    if (slot >= 0) {
        g_resourceHandles[slot].handle = handle;
        lstrcpynW(g_resourceHandles[slot].path, path, MAX_PATH);
        g_resourceHandles[slot].openedTick = CurrentTick();
        g_resourceHandles[slot].totalBytesRead = 0;
    }
    LeaveCriticalSection(&g_resourceLock);
}

static BOOL RecordResourceRead(
        HANDLE handle,
        DWORD requested,
        DWORD bytesRead,
        ULONGLONG offset,
        DWORD elapsedMs,
        BOOL success,
        WCHAR *pathOut,
        DWORD pathCount) {
    BOOL tracked = FALSE;
    EnterCriticalSection(&g_resourceLock);
    int slot = FindResourceHandleLocked(handle);
    if (slot >= 0) {
        tracked = TRUE;
        g_resourceHandles[slot].totalBytesRead += bytesRead;
        lstrcpynW(pathOut, g_resourceHandles[slot].path, pathCount);
        lstrcpynW(g_lastResourcePath, g_resourceHandles[slot].path, MAX_PATH);
        g_lastResourceOffset = offset;
        g_lastResourceBytes = bytesRead;
        g_lastResourceTick = CurrentTick();

        LONG sequence = InterlockedIncrement(&g_recentResourceReadSequence);
        RecentResourceRead *recent = &g_recentResourceReads[(sequence - 1) % kRecentResourceReadCount];
        recent->tick = g_lastResourceTick;
        recent->offset = offset;
        recent->requested = requested;
        recent->actual = bytesRead;
        recent->elapsedMs = elapsedMs;
        recent->success = success;
        lstrcpynW(recent->path, g_resourceHandles[slot].path, MAX_PATH);
    }
    LeaveCriticalSection(&g_resourceLock);
    return tracked;
}

static void CopyTrackedResourcePath(HANDLE handle, WCHAR *pathOut, DWORD pathCount) {
    pathOut[0] = L'\0';
    EnterCriticalSection(&g_resourceLock);
    int slot = FindResourceHandleLocked(handle);
    if (slot >= 0) {
        lstrcpynW(pathOut, g_resourceHandles[slot].path, pathCount);
    }
    LeaveCriticalSection(&g_resourceLock);
}

static void RecordMappingEvent(
        const WCHAR *api,
        HANDLE input,
        HANDLE result,
        DWORD error,
        DWORD access,
        DWORD offsetHigh,
        DWORD offsetLow,
        DWORD bytes,
        const WCHAR *path) {
    LONG sequence = InterlockedIncrement(&g_recentMappingEventSequence);
    EnterCriticalSection(&g_resourceLock);
    RecentMappingEvent *event = &g_recentMappingEvents[(sequence - 1) % kRecentMappingEventCount];
    event->tick = CurrentTick();
    lstrcpynW(event->api, api ? api : L"(unknown)", 32);
    event->input = input;
    event->result = result;
    event->error = error;
    event->access = access;
    event->offsetHigh = offsetHigh;
    event->offsetLow = offsetLow;
    event->bytes = bytes;
    lstrcpynW(event->path, path && path[0] ? path : L"(unknown)", MAX_PATH);
    LeaveCriticalSection(&g_resourceLock);
}

static BOOL IsDiagnosticUiMessage(UINT message) {
    return message == WM_KEYDOWN
        || message == WM_KEYUP
        || message == WM_SYSKEYDOWN
        || message == WM_SYSKEYUP
        || message == WM_LBUTTONDOWN
        || message == WM_LBUTTONUP
        || message == WM_LBUTTONDBLCLK
        || message == WM_RBUTTONDOWN
        || message == WM_RBUTTONUP
        || message == WM_COMMAND
        || message == WM_SYSCOMMAND;
}

static void RecordUiMessage(const MSG *message) {
    if (message == NULL || !IsDiagnosticUiMessage(message->message)) {
        return;
    }
    LONG sequence = InterlockedIncrement(&g_recentUiMessageSequence);
    EnterCriticalSection(&g_resourceLock);
    RecentUiMessage *event = &g_recentUiMessages[(sequence - 1) % kRecentUiMessageCount];
    event->tick = CurrentTick();
    event->tid = GetCurrentThreadId();
    event->window = message->hwnd;
    event->message = message->message;
    event->wParam = message->wParam;
    event->lParam = message->lParam;
    LeaveCriticalSection(&g_resourceLock);
}

static void FlushRecentResourceHistory(const WCHAR *reason) {
    LONG readSequence = InterlockedCompareExchange(&g_recentResourceReadSequence, 0, 0);
    LONG readCount = readSequence < kRecentResourceReadCount ? readSequence : kRecentResourceReadCount;
    LONG readFirst = readSequence - readCount;
    for (LONG i = 0; i < readCount; ++i) {
        RecentResourceRead event;
        EnterCriticalSection(&g_resourceLock);
        event = g_recentResourceReads[(readFirst + i) % kRecentResourceReadCount];
        LeaveCriticalSection(&g_resourceLock);
        if (event.tick == 0) {
            continue;
        }
        WCHAR line[1024];
        wsprintfW(
            line,
            L"event=incident_resource_read reason=%s age_ms=%I64u status=%s offset=%I64u requested=%lu read=%lu elapsed_ms=%lu path=\"%s\"",
            reason,
            CurrentTick() - event.tick,
            event.success ? L"ok" : L"failed",
            event.offset,
            event.requested,
            event.actual,
            event.elapsedMs,
            event.path);
        AppendLine(line);
    }

    LONG mappingSequence = InterlockedCompareExchange(&g_recentMappingEventSequence, 0, 0);
    LONG mappingCount = mappingSequence < kRecentMappingEventCount ? mappingSequence : kRecentMappingEventCount;
    LONG mappingFirst = mappingSequence - mappingCount;
    for (LONG i = 0; i < mappingCount; ++i) {
        RecentMappingEvent event;
        EnterCriticalSection(&g_resourceLock);
        event = g_recentMappingEvents[(mappingFirst + i) % kRecentMappingEventCount];
        LeaveCriticalSection(&g_resourceLock);
        if (event.tick == 0) {
            continue;
        }
        WCHAR line[1024];
        wsprintfW(
            line,
            L"event=incident_mapping reason=%s age_ms=%I64u api=%s input=%p result=%p error=%lu access=0x%08lx offset=%lu:%lu bytes=%lu path=\"%s\"",
            reason,
            CurrentTick() - event.tick,
            event.api,
            event.input,
            event.result,
            event.error,
            event.access,
            event.offsetHigh,
            event.offsetLow,
            event.bytes,
            event.path);
        AppendLine(line);
    }

    LONG uiSequence = InterlockedCompareExchange(&g_recentUiMessageSequence, 0, 0);
    LONG uiCount = uiSequence < kRecentUiMessageCount ? uiSequence : kRecentUiMessageCount;
    LONG uiFirst = uiSequence - uiCount;
    for (LONG i = 0; i < uiCount; ++i) {
        RecentUiMessage event;
        EnterCriticalSection(&g_resourceLock);
        event = g_recentUiMessages[(uiFirst + i) % kRecentUiMessageCount];
        LeaveCriticalSection(&g_resourceLock);
        if (event.tick == 0) {
            continue;
        }
        WCHAR line[768];
        wsprintfW(
            line,
            L"event=incident_ui_message reason=%s age_ms=%I64u tid=%lu hwnd=%p message=0x%04x wparam=0x%08lx lparam=0x%08lx",
            reason,
            CurrentTick() - event.tick,
            event.tid,
            event.window,
            event.message,
            (DWORD)(ULONG_PTR)event.wParam,
            (DWORD)(ULONG_PTR)event.lParam);
        AppendLine(line);
    }
}

static BOOL UntrackResourceHandle(HANDLE handle, WCHAR *pathOut, DWORD pathCount, ULONGLONG *totalBytes, ULONGLONG *lifetimeMs) {
    BOOL tracked = FALSE;
    EnterCriticalSection(&g_resourceLock);
    int slot = FindResourceHandleLocked(handle);
    if (slot >= 0) {
        tracked = TRUE;
        lstrcpynW(pathOut, g_resourceHandles[slot].path, pathCount);
        *totalBytes = g_resourceHandles[slot].totalBytesRead;
        *lifetimeMs = CurrentTick() - g_resourceHandles[slot].openedTick;
        ZeroMemory(&g_resourceHandles[slot], sizeof(g_resourceHandles[slot]));
    }
    LeaveCriticalSection(&g_resourceLock);
    return tracked;
}

static void AppendLine(const WCHAR *line) {
    if (g_inLog || RealCreateFileW == NULL || g_logPath[0] == L'\0') {
        return;
    }
    g_inLog = TRUE;
    EnterCriticalSection(&g_logLock);

    HANDLE file = RealCreateFileW(
        g_logPath,
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (file != INVALID_HANDLE_VALUE) {
        SYSTEMTIME st;
        DWORD bytesWritten = 0;
        GetLocalTime(&st);
        wsprintfW(
            g_wideLogLine,
            L"%04u-%02u-%02u %02u:%02u:%02u.%03u [seq=%ld] [tid=%lu] %s\r\n",
            st.wYear, st.wMonth, st.wDay,
            st.wHour, st.wMinute, st.wSecond, st.wMilliseconds,
            InterlockedIncrement(&g_eventSequence),
            GetCurrentThreadId(),
            line);
        if (GetFileSize(file, NULL) == 0) {
            static const BYTE utf8Bom[] = {0xEF, 0xBB, 0xBF};
            WriteFile(file, utf8Bom, sizeof(utf8Bom), &bytesWritten, NULL);
        }
        int utf8Bytes = WideCharToMultiByte(
            CP_UTF8,
            0,
            g_wideLogLine,
            -1,
            g_utf8LogLine,
            sizeof(g_utf8LogLine),
            NULL,
            NULL);
        if (utf8Bytes > 1) {
            WriteFile(file, g_utf8LogLine, (DWORD)(utf8Bytes - 1), &bytesWritten, NULL);
        }
        CloseHandle(file);
    }

    LeaveCriticalSection(&g_logLock);
    g_inLog = FALSE;
}

static void DetectKaringMapOpen(const WCHAR *path) {
    if (!IsBossSceneMapPath(path)
            || InterlockedCompareExchange(&g_karingMapDetected, 1, 0) != 0) {
        return;
    }
    WCHAR line[2048];
    wsprintfW(line, L"event=boss_scene_map status=detected path=\"%s\"", path);
    AppendLine(line);
}

static BOOL ShouldLogPath(const WCHAR *path) {
    return ContainsNoCase(path, L".img")
        || ContainsNoCase(path, L".wz")
        || ContainsNoCase(path, L"\\Data\\")
        || ContainsNoCase(path, L"/Data/");
}

static BOOL ShouldLogFileApiPath(const WCHAR *path) {
    if (path == NULL) {
        return FALSE;
    }
    // These compatibility DLLs open their own append-only logs for nearly every
    // equipment probe. Recording those opens again obscures the resource and
    // exception timeline and adds synchronous I/O to the character draw path.
    if (ContainsNoCase(path, L"EquipSlotDiagnostic.log")
            || ContainsNoCase(path, L"BeiDouSetItemCompat.log")
            || ContainsNoCase(path, L"DawnWarriorSkillCompat.log")) {
        return FALSE;
    }
    if (ShouldLogPath(path)) {
        return TRUE;
    }
    if (g_verboseFileLogs > 0) {
        --g_verboseFileLogs;
        return TRUE;
    }
    return FALSE;
}

static void LogCreateFileW(LPCWSTR path, DWORD desiredAccess, DWORD creationDisposition, HANDLE result) {
    if (!ShouldLogFileApiPath(path)) {
        return;
    }

    WCHAR line[4096];
    DWORD err = (result == INVALID_HANDLE_VALUE) ? GetLastError() : 0;
    wsprintfW(
        line,
        L"event=resource_open status=%s handle=%p error=%lu access=0x%08lx disposition=%lu path=\"%s\"",
        result == INVALID_HANDLE_VALUE ? L"failed" : L"ok",
        result,
        err,
        desiredAccess,
        creationDisposition,
        path);
    AppendLine(line);
}

static void LogLopenW(LPCWSTR path, int flags, HFILE result) {
    if (!ShouldLogFileApiPath(path)) {
        return;
    }

    WCHAR line[4096];
    DWORD err = (result == HFILE_ERROR) ? GetLastError() : 0;
    wsprintfW(
        line,
        L"event=resource_open api=_lopen status=%s handle=0x%08lx error=%lu flags=0x%08x path=\"%s\"",
        result == HFILE_ERROR ? L"failed" : L"ok",
        (DWORD)result,
        err,
        flags,
        path);
    AppendLine(line);
}

static void LogFindFirstFileW(LPCWSTR path, HANDLE result) {
    if (!ShouldLogFileApiPath(path)) {
        return;
    }

    WCHAR line[4096];
    DWORD err = (result == INVALID_HANDLE_VALUE) ? GetLastError() : 0;
    wsprintfW(
        line,
        L"event=resource_search status=%s handle=%p error=%lu pattern=\"%s\"",
        result == INVALID_HANDLE_VALUE ? L"failed" : L"ok",
        result,
        err,
        path);
    AppendLine(line);
}

static void AnsiToWide(LPCSTR input, WCHAR *out, size_t outCount);

static BOOL IsWzFlashRendererPath(const WCHAR *path) {
    return path != NULL && ContainsNoCase(path, L"WzFlashRenderer.dll");
}

static BOOL IsGr2DPath(const WCHAR *path) {
    return path != NULL && ContainsNoCase(path, L"Gr2D_DX8.dll");
}

static BOOL ResolveFlashMovieSlot(HMODULE module, FARPROC renderFlash, PVOID volatile **slotOut) {
    if (module == NULL || renderFlash == NULL || slotOut == NULL) {
        return FALSE;
    }

    BYTE *base = (BYTE *)module;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return FALSE;
    }
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE
            || nt->OptionalHeader.SizeOfImage <= 0x0006e08b
            || (BYTE *)renderFlash != base + 0x000014f0) {
        return FALSE;
    }

    PVOID volatile *movieSlot = (PVOID volatile *)(base + 0x0006e088);
    MEMORY_BASIC_INFORMATION memoryInfo;
    ZeroMemory(&memoryInfo, sizeof(memoryInfo));
    if (VirtualQuery((LPCVOID)movieSlot, &memoryInfo, sizeof(memoryInfo)) == 0
            || memoryInfo.State != MEM_COMMIT
            || (memoryInfo.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return FALSE;
    }

    *slotOut = movieSlot;
    return TRUE;
}

static int __cdecl HookRenderFlash(int x, int y, int tick) {
    if (RealRenderFlash == NULL || g_flashMovieSlot == NULL) {
        return 0;
    }

    PVOID movie = *g_flashMovieSlot;
    if (movie == NULL) {
        LONG occurrence = InterlockedIncrement(&g_flashRenderNullSkips);
        if (occurrence <= 8) {
            WCHAR line[512];
            wsprintfW(
                line,
                L"event=flash_render_guard action=skipped_null_movie occurrence=%ld x=%d y=%d tick=%d",
                occurrence,
                x,
                y,
                tick);
            AppendLine(line);
        }
        if (InterlockedCompareExchange(&g_flashNullDumpStarted, 1, 0) == 0) {
            AppendLine(L"event=flash_render_guard action=capture_first_null_context");
            CaptureIncidentEvidence(L"flash-null", TRUE, NULL);
        }
        return 0;
    }

    return RealRenderFlash(x, y, tick);
}

static FARPROC WINAPI HookGr2DGetProcAddress(HMODULE module, LPCSTR procName) {
    FARPROC realProc = RealGetProcAddress(module, procName);
    if (realProc == NULL
            || ((ULONG_PTR)procName >> 16) == 0
            || !EqualsNoCaseA(procName, "RenderFlash")) {
        return realProc;
    }

    WCHAR modulePath[MAX_PATH];
    modulePath[0] = L'\0';
    GetModuleFileNameW(module, modulePath, MAX_PATH);
    if (!IsWzFlashRendererPath(modulePath)) {
        return realProc;
    }

    PVOID volatile *movieSlot = NULL;
    if (!ResolveFlashMovieSlot(module, realProc, &movieSlot)) {
        WCHAR line[768];
        wsprintfW(
            line,
            L"event=flash_render_guard status=not_installed reason=unexpected_layout module=%p render=%p path=\"%s\"",
            module,
            realProc,
            modulePath);
        AppendLine(line);
        return realProc;
    }

    if (g_flashRendererHeldModule == NULL) {
        HMODULE heldModule = NULL;
        if (!GetModuleHandleExW(
                GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,
                (LPCWSTR)realProc,
                &heldModule)
                || heldModule != module) {
            if (heldModule != NULL) {
                FreeLibrary(heldModule);
            }
            AppendLine(L"event=flash_render_guard status=not_installed reason=module_hold_failed");
            return realProc;
        }
        g_flashRendererHeldModule = heldModule;
    } else if (g_flashRendererHeldModule != module) {
        AppendLine(L"event=flash_render_guard status=not_installed reason=module_changed");
        return realProc;
    }

    RealRenderFlash = (RenderFlashFn)realProc;
    g_flashMovieSlot = movieSlot;
    WCHAR line[768];
    wsprintfW(
        line,
        L"event=flash_render_guard status=installed module=%p render=%p movie_slot=%p path=\"%s\"",
        module,
        realProc,
        movieSlot,
        modulePath);
    AppendLine(line);
    return (FARPROC)HookRenderFlash;
}

static void LogLoadLibraryW(LPCWSTR path, HMODULE result, const WCHAR *apiName) {
    BOOL flashRenderer = IsWzFlashRendererPath(path);
    if (!flashRenderer && !ShouldLogFileApiPath(path)) {
        return;
    }

    WCHAR line[4096];
    DWORD err = (result == NULL) ? GetLastError() : 0;
    wsprintfW(
        line,
        L"event=module_load api=%s status=%s module=%p error=%lu path=\"%s\"",
        apiName,
        result == NULL ? L"failed" : L"ok",
        result,
        err,
        path);
    AppendLine(line);

    if (flashRenderer && result != NULL && RealGetProcAddress != NULL) {
        WCHAR exports[1024];
        const char *names[] = {
            "InitializeFlash",
            "InitializeFlashbyDevice",
            "IsRenderFlash",
            "LoadMediaFile",
            "ReleaseFlash",
            "RenderFlash"
        };
        exports[0] = L'\0';
        for (int i = 0; i < 6; ++i) {
            FARPROC address = RealGetProcAddress(result, names[i]);
            WCHAR name[64];
            AnsiToWide(names[i], name, 64);
            WCHAR entry[128];
            wsprintfW(entry, L"%s=%p%s", name, address, i == 5 ? L"" : L" ");
            lstrcatW(exports, entry);
        }
        WCHAR exportLine[1400];
        wsprintfW(exportLine, L"event=flash_renderer_exports module=%p %s", result, exports);
        AppendLine(exportLine);
    }
}

static void GetPathForHandle(HANDLE file, WCHAR *out, DWORD outCount) {
    out[0] = L'\0';
    if (file == NULL || file == INVALID_HANDLE_VALUE || RealGetFinalPathNameByHandleW == NULL) {
        return;
    }
    DWORD len = RealGetFinalPathNameByHandleW(file, out, outCount, 0);
    if (len == 0 || len >= outCount) {
        out[0] = L'\0';
    }
}

static void LogMappingW(const WCHAR *apiName, HANDLE input, HANDLE result, const WCHAR *name, const WCHAR *filePath) {
    WCHAR line[4096];
    DWORD err = (result == NULL) ? GetLastError() : 0;
    wsprintfW(
        line,
        L"%s input=%p result=%p err=%lu name=%s file=%s",
        apiName,
        input,
        result,
        err,
        name ? name : L"(null)",
        (filePath && filePath[0]) ? filePath : L"(unknown)");
    AppendLine(line);
}

static void AnsiToWide(LPCSTR input, WCHAR *out, size_t outCount) {
    if (input == NULL) {
        lstrcpynW(out, L"(null)", (int)outCount);
        return;
    }
    MultiByteToWideChar(CP_ACP, 0, input, -1, out, (int)outCount);
    out[outCount - 1] = L'\0';
}

static HANDLE WINAPI HookCreateFileW(
    LPCWSTR fileName,
    DWORD desiredAccess,
    DWORD shareMode,
    LPSECURITY_ATTRIBUTES securityAttributes,
    DWORD creationDisposition,
    DWORD flagsAndAttributes,
    HANDLE templateFile) {
    HANDLE result = RealCreateFileW(
        fileName,
        desiredAccess,
        shareMode,
        securityAttributes,
        creationDisposition,
        flagsAndAttributes,
        templateFile);
    DWORD savedError = result == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    if (result != INVALID_HANDLE_VALUE) {
        DetectKaringMapOpen(fileName);
    }
    TrackResourceHandle(result, fileName);
    if (result == INVALID_HANDLE_VALUE) {
        SetLastError(savedError);
    }
    LogCreateFileW(fileName, desiredAccess, creationDisposition, result);
    if (result == INVALID_HANDLE_VALUE) {
        SetLastError(savedError);
    }
    return result;
}

static HANDLE WINAPI HookCreateFileA(
    LPCSTR fileName,
    DWORD desiredAccess,
    DWORD shareMode,
    LPSECURITY_ATTRIBUTES securityAttributes,
    DWORD creationDisposition,
    DWORD flagsAndAttributes,
    HANDLE templateFile) {
    HANDLE result = RealCreateFileA(
        fileName,
        desiredAccess,
        shareMode,
        securityAttributes,
        creationDisposition,
        flagsAndAttributes,
        templateFile);
    DWORD savedError = result == INVALID_HANDLE_VALUE ? GetLastError() : 0;

    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    if (result != INVALID_HANDLE_VALUE) {
        DetectKaringMapOpen(widePath);
    }
    TrackResourceHandle(result, widePath);
    if (result == INVALID_HANDLE_VALUE) {
        SetLastError(savedError);
    }
    LogCreateFileW(widePath, desiredAccess, creationDisposition, result);
    if (result == INVALID_HANDLE_VALUE) {
        SetLastError(savedError);
    }
    return result;
}

static HFILE WINAPI HookLopen(LPCSTR fileName, int flags) {
    HFILE result = RealLopen(fileName, flags);
    DWORD savedError = result == HFILE_ERROR ? GetLastError() : 0;

    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    if (result != HFILE_ERROR) {
        DetectKaringMapOpen(widePath);
    }
    TrackResourceHandle((HANDLE)result, widePath);
    if (result == HFILE_ERROR) {
        SetLastError(savedError);
    }
    LogLopenW(widePath, flags, result);
    if (result == HFILE_ERROR) {
        SetLastError(savedError);
    }
    return result;
}

static HANDLE WINAPI HookFindFirstFileA(LPCSTR fileName, LPWIN32_FIND_DATAA findFileData) {
    HANDLE result = RealFindFirstFileA(fileName, findFileData);
    DWORD savedError = result == INVALID_HANDLE_VALUE ? GetLastError() : 0;

    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    if (result == INVALID_HANDLE_VALUE) {
        SetLastError(savedError);
    }
    LogFindFirstFileW(widePath, result);
    if (result == INVALID_HANDLE_VALUE) {
        SetLastError(savedError);
    }
    return result;
}

static HANDLE WINAPI HookCreateFileMappingA(
    HANDLE file,
    LPSECURITY_ATTRIBUTES attrs,
    DWORD protect,
    DWORD maxSizeHigh,
    DWORD maxSizeLow,
    LPCSTR name) {
    HANDLE result = RealCreateFileMappingA(file, attrs, protect, maxSizeHigh, maxSizeLow, name);
    DWORD savedError = result == NULL ? GetLastError() : 0;

    WCHAR trackedPath[MAX_PATH];
    CopyTrackedResourcePath(file, trackedPath, MAX_PATH);
    RecordMappingEvent(
        L"CreateFileMappingA",
        file,
        result,
        savedError,
        protect,
        maxSizeHigh,
        maxSizeLow,
        0,
        trackedPath);

    if (result == NULL || g_logSuccessfulMappings) {
        WCHAR wideName[1024];
        WCHAR filePath[2048];
        AnsiToWide(name, wideName, 1024);
        GetPathForHandle(file, filePath, 2048);
        LogMappingW(L"CreateFileMappingA", file, result, wideName, filePath);
    }
    if (result == NULL) {
        SetLastError(savedError);
    }
    return result;
}

static HANDLE WINAPI HookOpenFileMappingA(DWORD desiredAccess, BOOL inheritHandle, LPCSTR name) {
    HANDLE result = RealOpenFileMappingA(desiredAccess, inheritHandle, name);
    DWORD savedError = result == NULL ? GetLastError() : 0;

    WCHAR wideNameForHistory[MAX_PATH];
    AnsiToWide(name, wideNameForHistory, MAX_PATH);
    RecordMappingEvent(
        L"OpenFileMappingA",
        NULL,
        result,
        savedError,
        desiredAccess,
        0,
        0,
        0,
        wideNameForHistory);

    if (result == NULL || g_logSuccessfulMappings) {
        WCHAR wideName[1024];
        AnsiToWide(name, wideName, 1024);
        LogMappingW(L"OpenFileMappingA", NULL, result, wideName, L"");
    }
    if (result == NULL) {
        SetLastError(savedError);
    }
    return result;
}

static LPVOID WINAPI HookMapViewOfFile(
    HANDLE mapping,
    DWORD desiredAccess,
    DWORD offsetHigh,
    DWORD offsetLow,
    SIZE_T bytesToMap) {
    LPVOID result = RealMapViewOfFile(mapping, desiredAccess, offsetHigh, offsetLow, bytesToMap);

    DWORD err = (result == NULL) ? GetLastError() : 0;
    RecordMappingEvent(
        L"MapViewOfFile",
        mapping,
        (HANDLE)result,
        err,
        desiredAccess,
        offsetHigh,
        offsetLow,
        (DWORD)bytesToMap,
        L"");
    if (result == NULL || g_logSuccessfulMappings) {
        WCHAR line[512];
        wsprintfW(
            line,
            L"MapViewOfFile mapping=%p result=%p err=%lu access=0x%08lx offset=%lu:%lu bytes=%lu",
            mapping,
            result,
            err,
            desiredAccess,
            offsetHigh,
            offsetLow,
            (DWORD)bytesToMap);
        AppendLine(line);
    }
    if (result == NULL) {
        SetLastError(err);
    }
    return result;
}

static BOOL WINAPI HookReadFile(
    HANDLE file,
    LPVOID buffer,
    DWORD bytesToRead,
    LPDWORD bytesRead,
    LPOVERLAPPED overlapped) {
    ULONGLONG started = CurrentTick();
    BOOL result = RealReadFile(file, buffer, bytesToRead, bytesRead, overlapped);
    DWORD savedError = result ? 0 : GetLastError();
    DWORD actualBytes = bytesRead ? *bytesRead : 0;
    ULONGLONG offset = 0;
    if (overlapped != NULL) {
        offset = ((ULONGLONG)overlapped->OffsetHigh << 32) | overlapped->Offset;
    } else {
        LARGE_INTEGER zero;
        LARGE_INTEGER current;
        zero.QuadPart = 0;
        if (SetFilePointerEx(file, zero, &current, FILE_CURRENT) && current.QuadPart >= actualBytes) {
            offset = (ULONGLONG)current.QuadPart - actualBytes;
        }
    }

    WCHAR path[MAX_PATH];
    path[0] = L'\0';
    DWORD elapsedMs = (DWORD)(CurrentTick() - started);
    BOOL tracked = RecordResourceRead(
        file,
        bytesToRead,
        actualBytes,
        offset,
        elapsedMs,
        result,
        path,
        MAX_PATH);
    if (tracked && (!result || elapsedMs >= 50)) {
        WCHAR line[1024];
        wsprintfW(
            line,
            L"event=resource_read status=%s error=%lu offset=%I64u requested=%lu read=%lu elapsed_ms=%lu path=\"%s\"",
            result ? L"ok" : L"failed",
            savedError,
            offset,
            bytesToRead,
            actualBytes,
            elapsedMs,
            path);
        AppendLine(line);
    }
    if (!result) {
        SetLastError(savedError);
    }
    return result;
}

static BOOL WINAPI HookCloseHandle(HANDLE object) {
    WCHAR path[MAX_PATH];
    ULONGLONG totalBytes = 0;
    ULONGLONG lifetimeMs = 0;
    path[0] = L'\0';
    BOOL tracked = UntrackResourceHandle(object, path, MAX_PATH, &totalBytes, &lifetimeMs);
    BOOL result = RealCloseHandle(object);
    DWORD savedError = result ? 0 : GetLastError();
    if (tracked) {
        WCHAR line[1024];
        wsprintfW(
            line,
            L"event=resource_close status=%s error=%lu bytes_read=%I64u lifetime_ms=%I64u path=\"%s\"",
            result ? L"ok" : L"failed",
            savedError,
            totalBytes,
            lifetimeMs,
            path);
        AppendLine(line);
    }
    if (!result) {
        SetLastError(savedError);
    }
    return result;
}

static LPTOP_LEVEL_EXCEPTION_FILTER WINAPI HookSetUnhandledExceptionFilter(LPTOP_LEVEL_EXCEPTION_FILTER filter) {
    LPTOP_LEVEL_EXCEPTION_FILTER previous = g_previousExceptionFilter;
    if (filter != NULL && filter != DiagnosticExceptionFilter) {
        g_previousExceptionFilter = filter;
        AppendLine(L"event=exception_filter action=preserved_client_filter");
    }
    RealSetUnhandledExceptionFilter(DiagnosticExceptionFilter);
    return previous;
}

static void CaptureProcessExit(const WCHAR *api, UINT exitCode) {
    if (InterlockedExchange(&g_exitDumpStarted, 1) != 0) {
        return;
    }
    WCHAR line[256];
    wsprintfW(line, L"event=process_exit api=%s code=%u tid=%lu", api, exitCode, GetCurrentThreadId());
    AppendLine(line);
    CaptureIncidentEvidence(L"exit-process", TRUE, NULL);
}

static VOID WINAPI HookExitProcess(UINT exitCode) {
    CaptureProcessExit(L"ExitProcess", exitCode);
    RealExitProcess(exitCode);
}

static BOOL WINAPI HookTerminateProcess(HANDLE process, UINT exitCode) {
    DWORD targetPid = GetProcessId(process);
    if (targetPid != 0 && targetPid == GetCurrentProcessId()) {
        CaptureProcessExit(L"TerminateProcess", exitCode);
    }
    return RealTerminateProcess(process, exitCode);
}

static void *__cdecl HookFopen(const char *fileName, const char *mode) {
    void *result = RealFopen(fileName, mode);

    WCHAR widePath[2048];
    WCHAR wideMode[64];
    AnsiToWide(fileName, widePath, 2048);
    AnsiToWide(mode, wideMode, 64);
    if (ShouldLogFileApiPath(widePath)) {
        WCHAR line[4096];
        wsprintfW(
            line,
            L"event=resource_open api=fopen status=%s stream=%p mode=%s path=\"%s\"",
            result ? L"ok" : L"failed",
            result,
            wideMode,
            widePath);
        AppendLine(line);
    }
    return result;
}

static size_t __cdecl HookFread(void *buffer, size_t size, size_t count, void *stream) {
    return RealFread(buffer, size, count, stream);
}

static FARPROC WINAPI HookGetProcAddress(HMODULE module, LPCSTR procName) {
    FARPROC realProc = RealGetProcAddress(module, procName);
    if (((ULONG_PTR)procName >> 16) == 0) {
        return realProc;
    }

    FARPROC replacement = NULL;
    if (EqualsNoCaseA(procName, "CreateFileW")) {
        replacement = (FARPROC)HookCreateFileW;
    } else if (EqualsNoCaseA(procName, "CreateFileA")) {
        replacement = (FARPROC)HookCreateFileA;
    } else if (EqualsNoCaseA(procName, "_lopen")) {
        replacement = (FARPROC)HookLopen;
    } else if (EqualsNoCaseA(procName, "FindFirstFileA")) {
        replacement = (FARPROC)HookFindFirstFileA;
    } else if (EqualsNoCaseA(procName, "CreateFileMappingA")) {
        replacement = (FARPROC)HookCreateFileMappingA;
    } else if (EqualsNoCaseA(procName, "OpenFileMappingA")) {
        replacement = (FARPROC)HookOpenFileMappingA;
    } else if (EqualsNoCaseA(procName, "MapViewOfFile")) {
        replacement = (FARPROC)HookMapViewOfFile;
    } else if (EqualsNoCaseA(procName, "ReadFile")) {
        replacement = (FARPROC)HookReadFile;
    } else if (EqualsNoCaseA(procName, "CloseHandle")) {
        replacement = (FARPROC)HookCloseHandle;
    } else if (EqualsNoCaseA(procName, "SetUnhandledExceptionFilter")) {
        replacement = (FARPROC)HookSetUnhandledExceptionFilter;
    } else if (EqualsNoCaseA(procName, "ExitProcess")) {
        replacement = (FARPROC)HookExitProcess;
    } else if (EqualsNoCaseA(procName, "TerminateProcess")) {
        replacement = (FARPROC)HookTerminateProcess;
    } else if (EqualsNoCaseA(procName, "LoadLibraryW")) {
        replacement = (FARPROC)HookLoadLibraryW;
    } else if (EqualsNoCaseA(procName, "LoadLibraryA")) {
        replacement = (FARPROC)HookLoadLibraryA;
    } else if (EqualsNoCaseA(procName, "LoadLibraryExA")) {
        replacement = (FARPROC)HookLoadLibraryExA;
    } else if (EqualsNoCaseA(procName, "MessageBoxW")) {
        replacement = (FARPROC)HookMessageBoxW;
    } else if (EqualsNoCaseA(procName, "MessageBoxA")) {
        replacement = (FARPROC)HookMessageBoxA;
    } else if (EqualsNoCaseA(procName, "MessageBoxExW")) {
        replacement = (FARPROC)HookMessageBoxExW;
    } else if (EqualsNoCaseA(procName, "MessageBoxExA")) {
        replacement = (FARPROC)HookMessageBoxExA;
    } else if (EqualsNoCaseA(procName, "MessageBoxIndirectW")) {
        replacement = (FARPROC)HookMessageBoxIndirectW;
    } else if (EqualsNoCaseA(procName, "MessageBoxIndirectA")) {
        replacement = (FARPROC)HookMessageBoxIndirectA;
    } else if (EqualsNoCaseA(procName, "FatalAppExitW")) {
        replacement = (FARPROC)HookFatalAppExitW;
    } else if (EqualsNoCaseA(procName, "FatalAppExitA")) {
        replacement = (FARPROC)HookFatalAppExitA;
    } else if (EqualsNoCaseA(procName, "DispatchMessageW")) {
        replacement = (FARPROC)HookDispatchMessageW;
    } else if (EqualsNoCaseA(procName, "DispatchMessageA")) {
        replacement = (FARPROC)HookDispatchMessageA;
    } else if (EqualsNoCaseA(procName, "fopen")) {
        if (RealFopen == NULL) {
            RealFopen = (FopenFn)realProc;
        }
        replacement = (FARPROC)HookFopen;
    } else if (EqualsNoCaseA(procName, "fread")) {
        if (RealFread == NULL) {
            RealFread = (FreadFn)realProc;
        }
        replacement = (FARPROC)HookFread;
    }

    if (realProc != NULL && replacement != NULL) {
        WCHAR wideName[256];
        WCHAR line[512];
        AnsiToWide(procName, wideName, 256);
        wsprintfW(line, L"GetProcAddress hook name=%s real=%p replacement=%p", wideName, realProc, replacement);
        AppendLine(line);
        return replacement;
    }
    return realProc;
}

static void ObserveDialog(
        const WCHAR *api,
        HWND hwnd,
        const WCHAR *text,
        const WCHAR *caption,
        BOOL forceIncident) {
    WCHAR line[4096];
    wsprintfW(
        line,
        L"event=message_box api=%s hwnd=%p caption=\"%s\" text=\"%s\"",
        api,
        hwnd,
        caption ? caption : L"(null)",
        text ? text : L"(null)");
    AppendLine(line);
    if ((forceIncident || IsErrorDialogText(text))
            && InterlockedCompareExchange(&g_errorDialogDumpStarted, 1, 0) == 0) {
        AppendLine(L"event=error_dialog action=capture_before_dialog");
        CaptureIncidentEvidence(L"error-dialog", TRUE, NULL);
    }
}

static int WINAPI HookMessageBoxW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type) {
    ObserveDialog(L"MessageBoxW", hwnd, text, caption, FALSE);
    if (RealMessageBoxW != NULL) {
        return RealMessageBoxW(hwnd, text, caption, type);
    }
    return 0;
}

static int WINAPI HookMessageBoxA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type) {
    WCHAR wideText[2048];
    WCHAR wideCaption[512];
    AnsiToWide(text, wideText, 2048);
    AnsiToWide(caption, wideCaption, 512);
    ObserveDialog(L"MessageBoxA", hwnd, wideText, wideCaption, FALSE);
    if (RealMessageBoxA != NULL) {
        return RealMessageBoxA(hwnd, text, caption, type);
    }
    return 0;
}

static int WINAPI HookMessageBoxExW(
        HWND hwnd,
        LPCWSTR text,
        LPCWSTR caption,
        UINT type,
        WORD languageId) {
    ObserveDialog(L"MessageBoxExW", hwnd, text, caption, FALSE);
    return RealMessageBoxExW != NULL
        ? RealMessageBoxExW(hwnd, text, caption, type, languageId)
        : 0;
}

static int WINAPI HookMessageBoxExA(
        HWND hwnd,
        LPCSTR text,
        LPCSTR caption,
        UINT type,
        WORD languageId) {
    WCHAR wideText[2048];
    WCHAR wideCaption[512];
    AnsiToWide(text, wideText, 2048);
    AnsiToWide(caption, wideCaption, 512);
    ObserveDialog(L"MessageBoxExA", hwnd, wideText, wideCaption, FALSE);
    return RealMessageBoxExA != NULL
        ? RealMessageBoxExA(hwnd, text, caption, type, languageId)
        : 0;
}

static int WINAPI HookMessageBoxIndirectW(const MSGBOXPARAMSW *params) {
    ObserveDialog(
        L"MessageBoxIndirectW",
        params ? params->hwndOwner : NULL,
        params ? params->lpszText : NULL,
        params ? params->lpszCaption : NULL,
        FALSE);
    return RealMessageBoxIndirectW != NULL ? RealMessageBoxIndirectW(params) : 0;
}

static int WINAPI HookMessageBoxIndirectA(const MSGBOXPARAMSA *params) {
    WCHAR wideText[2048];
    WCHAR wideCaption[512];
    AnsiToWide(params ? params->lpszText : NULL, wideText, 2048);
    AnsiToWide(params ? params->lpszCaption : NULL, wideCaption, 512);
    ObserveDialog(
        L"MessageBoxIndirectA",
        params ? params->hwndOwner : NULL,
        wideText,
        wideCaption,
        FALSE);
    return RealMessageBoxIndirectA != NULL ? RealMessageBoxIndirectA(params) : 0;
}

static VOID WINAPI HookFatalAppExitW(UINT action, LPCWSTR messageText) {
    ObserveDialog(L"FatalAppExitW", NULL, messageText, L"(fatal)", TRUE);
    if (RealFatalAppExitW != NULL) {
        RealFatalAppExitW(action, messageText);
    }
}

static VOID WINAPI HookFatalAppExitA(UINT action, LPCSTR messageText) {
    WCHAR wideText[2048];
    AnsiToWide(messageText, wideText, 2048);
    ObserveDialog(L"FatalAppExitA", NULL, wideText, L"(fatal)", TRUE);
    if (RealFatalAppExitA != NULL) {
        RealFatalAppExitA(action, messageText);
    }
}

static LRESULT WINAPI HookDispatchMessageW(const MSG *message) {
    RecordUiMessage(message);
    return RealDispatchMessageW != NULL ? RealDispatchMessageW(message) : 0;
}

static LRESULT WINAPI HookDispatchMessageA(const MSG *message) {
    RecordUiMessage(message);
    return RealDispatchMessageA != NULL ? RealDispatchMessageA(message) : 0;
}

static BOOL PatchThunk(IMAGE_THUNK_DATA *addrThunk, void *replacement) {
    if ((void *)addrThunk->u1.Function == replacement) {
        return FALSE;
    }

    DWORD oldProtect = 0;
    if (VirtualProtect(&addrThunk->u1.Function, sizeof(void *), PAGE_READWRITE, &oldProtect)) {
        addrThunk->u1.Function = (ULONG_PTR)replacement;
        VirtualProtect(&addrThunk->u1.Function, sizeof(void *), oldProtect, &oldProtect);
        return TRUE;
    }
    return FALSE;
}

static int PatchImport(HMODULE module, const char *dllName, const char *funcName, void *original, void *replacement) {
    if (original == NULL || replacement == NULL) {
        return 0;
    }

    BYTE *base = (BYTE *)module;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return 0;
    }

    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return 0;
    }

    DWORD importRva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (importRva == 0) {
        return 0;
    }

    int patched = 0;
    IMAGE_IMPORT_DESCRIPTOR *desc = (IMAGE_IMPORT_DESCRIPTOR *)(base + importRva);
    for (; desc->Name != 0; ++desc) {
        const char *importDll = (const char *)(base + desc->Name);
        if (!EqualsNoCaseA(importDll, dllName)) {
            continue;
        }

        IMAGE_THUNK_DATA *addrThunk = (IMAGE_THUNK_DATA *)(base + desc->FirstThunk);
        if (desc->OriginalFirstThunk == 0) {
            for (; addrThunk->u1.Function != 0; ++addrThunk) {
                if ((void *)addrThunk->u1.Function == original) {
                    if (PatchThunk(addrThunk, replacement)) {
                        ++patched;
                    }
                }
            }
            continue;
        }

        IMAGE_THUNK_DATA *nameThunk = (IMAGE_THUNK_DATA *)(base + desc->OriginalFirstThunk);
        for (; nameThunk->u1.AddressOfData != 0; ++nameThunk, ++addrThunk) {
            if (IMAGE_SNAP_BY_ORDINAL(nameThunk->u1.Ordinal)) {
                continue;
            }
            IMAGE_IMPORT_BY_NAME *importName = (IMAGE_IMPORT_BY_NAME *)(base + nameThunk->u1.AddressOfData);
            if (lstrcmpA((LPCSTR)importName->Name, funcName) != 0) {
                continue;
            }
            if (PatchThunk(addrThunk, replacement)) {
                ++patched;
            }
        }
    }
    return patched;
}

static int PatchKnownBeiDouIat(HMODULE module, DWORD iatRva, void *replacement) {
    if (module != GetModuleHandleW(NULL) || replacement == NULL) {
        return 0;
    }

    BYTE *base = (BYTE *)module;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return 0;
    }
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return 0;
    }
    if (iatRva >= nt->OptionalHeader.SizeOfImage) {
        return 0;
    }

    IMAGE_THUNK_DATA *slot = (IMAGE_THUNK_DATA *)(base + iatRva);
    if (slot->u1.Function == 0) {
        return 0;
    }
    return PatchThunk(slot, replacement) ? 1 : 0;
}

static BOOL IsClientModulePath(const WCHAR *path) {
    if (path == NULL || path[0] == L'\0') {
        return FALSE;
    }
    return StartsWithNoCase(path, g_exeDir);
}

static int PatchModule(HMODULE module, BOOL logResult) {
    if (module == NULL || module == g_selfModule) {
        return 0;
    }

    HMODULE heldModule = NULL;
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,
            reinterpret_cast<LPCWSTR>(module),
            &heldModule)) {
        return 0;
    }
    if (heldModule != module) {
        FreeLibrary(heldModule);
        return 0;
    }

    WCHAR path[MAX_PATH];
    path[0] = L'\0';
    GetModuleFileNameW(module, path, MAX_PATH);
    if (!IsClientModulePath(path)) {
        FreeLibrary(heldModule);
        return 0;
    }

    int createFileW = PatchImport(module, "KERNEL32.dll", "CreateFileW", (void *)RealCreateFileW, (void *)HookCreateFileW);
    int createFileA = PatchImport(module, "KERNEL32.dll", "CreateFileA", (void *)RealCreateFileA, (void *)HookCreateFileA);
    int lopen = PatchImport(module, "KERNEL32.dll", "_lopen", (void *)RealLopen, (void *)HookLopen);
    int findFirstFileA = PatchImport(module, "KERNEL32.dll", "FindFirstFileA", (void *)RealFindFirstFileA, (void *)HookFindFirstFileA);
    int getProcAddress = IsGr2DPath(path)
        ? PatchImport(module, "KERNEL32.dll", "GetProcAddress", (void *)RealGetProcAddress, (void *)HookGr2DGetProcAddress)
        : 0;
    int createFileMappingA = PatchImport(module, "KERNEL32.dll", "CreateFileMappingA", (void *)RealCreateFileMappingA, (void *)HookCreateFileMappingA);
    int openFileMappingA = PatchImport(module, "KERNEL32.dll", "OpenFileMappingA", (void *)RealOpenFileMappingA, (void *)HookOpenFileMappingA);
    int mapViewOfFile = PatchImport(module, "KERNEL32.dll", "MapViewOfFile", (void *)RealMapViewOfFile, (void *)HookMapViewOfFile);
    int readFile = PatchImport(module, "KERNEL32.dll", "ReadFile", (void *)RealReadFile, (void *)HookReadFile);
    int closeHandle = PatchImport(module, "KERNEL32.dll", "CloseHandle", (void *)RealCloseHandle, (void *)HookCloseHandle);
    int exceptionFilter = PatchImport(module, "KERNEL32.dll", "SetUnhandledExceptionFilter", (void *)RealSetUnhandledExceptionFilter, (void *)HookSetUnhandledExceptionFilter);
    int exitProcess = PatchImport(module, "KERNEL32.dll", "ExitProcess", (void *)RealExitProcess, (void *)HookExitProcess);
    int terminateProcess = PatchImport(module, "KERNEL32.dll", "TerminateProcess", (void *)RealTerminateProcess, (void *)HookTerminateProcess);
    int loadLibraryW = PatchImport(module, "KERNEL32.dll", "LoadLibraryW", (void *)RealLoadLibraryW, (void *)HookLoadLibraryW);
    int loadLibraryA = PatchImport(module, "KERNEL32.dll", "LoadLibraryA", (void *)RealLoadLibraryA, (void *)HookLoadLibraryA);
    int loadLibraryExA = PatchImport(module, "KERNEL32.dll", "LoadLibraryExA", (void *)RealLoadLibraryExA, (void *)HookLoadLibraryExA);
    int messageBoxW = PatchImport(module, "USER32.dll", "MessageBoxW", (void *)RealMessageBoxW, (void *)HookMessageBoxW);
    int messageBoxA = PatchImport(module, "USER32.dll", "MessageBoxA", (void *)RealMessageBoxA, (void *)HookMessageBoxA);
    int messageBoxExW = PatchImport(module, "USER32.dll", "MessageBoxExW", (void *)RealMessageBoxExW, (void *)HookMessageBoxExW);
    int messageBoxExA = PatchImport(module, "USER32.dll", "MessageBoxExA", (void *)RealMessageBoxExA, (void *)HookMessageBoxExA);
    int messageBoxIndirectW = PatchImport(module, "USER32.dll", "MessageBoxIndirectW", (void *)RealMessageBoxIndirectW, (void *)HookMessageBoxIndirectW);
    int messageBoxIndirectA = PatchImport(module, "USER32.dll", "MessageBoxIndirectA", (void *)RealMessageBoxIndirectA, (void *)HookMessageBoxIndirectA);
    int fatalAppExitW = PatchImport(module, "KERNEL32.dll", "FatalAppExitW", (void *)RealFatalAppExitW, (void *)HookFatalAppExitW);
    int fatalAppExitA = PatchImport(module, "KERNEL32.dll", "FatalAppExitA", (void *)RealFatalAppExitA, (void *)HookFatalAppExitA);
    int dispatchMessageW = PatchImport(module, "USER32.dll", "DispatchMessageW", (void *)RealDispatchMessageW, (void *)HookDispatchMessageW);
    int dispatchMessageA = PatchImport(module, "USER32.dll", "DispatchMessageA", (void *)RealDispatchMessageA, (void *)HookDispatchMessageA);
    int fopen = PatchImport(module, "MSVCRT.dll", "fopen", (void *)RealFopen, (void *)HookFopen);
    int fread = PatchImport(module, "MSVCRT.dll", "fread", (void *)RealFread, (void *)HookFread);

    if (module == GetModuleHandleW(NULL)) {
        createFileA += PatchKnownBeiDouIat(module, 0x006F0180, (void *)HookCreateFileA);
        lopen += PatchKnownBeiDouIat(module, 0x006F00EC, (void *)HookLopen);
        findFirstFileA += PatchKnownBeiDouIat(module, 0x006F0054, (void *)HookFindFirstFileA);
        readFile += PatchKnownBeiDouIat(module, 0x006F0184, (void *)HookReadFile);
        loadLibraryA += PatchKnownBeiDouIat(module, 0x006F00C0, (void *)HookLoadLibraryA);
        loadLibraryExA += PatchKnownBeiDouIat(module, 0x006F0194, (void *)HookLoadLibraryExA);
        messageBoxA += PatchKnownBeiDouIat(module, 0x006F02E8, (void *)HookMessageBoxA);
    }

    int total = createFileW + createFileA + lopen + findFirstFileA + getProcAddress
        + createFileMappingA + openFileMappingA + mapViewOfFile + readFile + closeHandle + exceptionFilter
        + exitProcess + terminateProcess
        + loadLibraryW + loadLibraryA + loadLibraryExA + messageBoxW + messageBoxA
        + messageBoxExW + messageBoxExA + messageBoxIndirectW + messageBoxIndirectA
        + fatalAppExitW + fatalAppExitA
        + dispatchMessageW + dispatchMessageA
        + fopen + fread;
    if (total > 0 && logResult && g_patchSummaryLogs > 0) {
        --g_patchSummaryLogs;
        WCHAR line[4096];
        wsprintfW(
            line,
            L"event=hook_summary total=%d CreateFileW=%d CreateFileA=%d _lopen=%d FindFirstFileA=%d GetProcAddress=%d Mapping=%d/%d/%d ReadFile=%d CloseHandle=%d ExceptionFilter=%d Exit=%d/%d FatalAppExit=%d/%d LoadLibrary=%d/%d/%d MessageBox=%d/%d Ex=%d/%d Indirect=%d/%d DispatchMessage=%d/%d fopen=%d fread=%d module=\"%s\"",
            total,
            createFileW,
            createFileA,
            lopen,
            findFirstFileA,
            getProcAddress,
            createFileMappingA,
            openFileMappingA,
            mapViewOfFile,
            readFile,
            closeHandle,
            exceptionFilter,
            exitProcess,
            terminateProcess,
            fatalAppExitW,
            fatalAppExitA,
            loadLibraryW,
            loadLibraryA,
            loadLibraryExA,
            messageBoxW,
            messageBoxA,
            messageBoxExW,
            messageBoxExA,
            messageBoxIndirectW,
            messageBoxIndirectA,
            dispatchMessageW,
            dispatchMessageA,
            fopen,
            fread,
            path);
        AppendLine(line);
    }
    FreeLibrary(heldModule);
    return total;
}

static void PatchAllModules() {
    if (InterlockedExchange(&g_patching, 1) != 0) {
        return;
    }

    RefreshOriginalFunctions();
    PatchModule(GetModuleHandleW(NULL), TRUE);

    DWORD pid = GetCurrentProcessId();
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid);
    if (snap != INVALID_HANDLE_VALUE) {
        MODULEENTRY32W entry;
        ZeroMemory(&entry, sizeof(entry));
        entry.dwSize = sizeof(entry);
        if (Module32FirstW(snap, &entry)) {
            do {
                if (entry.hModule != GetModuleHandleW(NULL)) {
                    PatchModule(entry.hModule, TRUE);
                }
            } while (Module32NextW(snap, &entry));
        }
        CloseHandle(snap);
    } else {
        AppendLine(L"PatchAllModules CreateToolhelp32Snapshot failed");
    }

    InterlockedExchange(&g_patching, 0);
}

static HMODULE WINAPI HookLoadLibraryW(LPCWSTR fileName) {
    HMODULE module = RealLoadLibraryW(fileName);
    DWORD savedError = module == NULL ? GetLastError() : 0;
    LogLoadLibraryW(fileName, module, L"LoadLibraryW");
    PatchAllModules();
    if (module == NULL) {
        SetLastError(savedError);
    }
    return module;
}

static HMODULE WINAPI HookLoadLibraryA(LPCSTR fileName) {
    HMODULE module = RealLoadLibraryA(fileName);
    DWORD savedError = module == NULL ? GetLastError() : 0;
    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    if (module == NULL) {
        SetLastError(savedError);
    }
    LogLoadLibraryW(widePath, module, L"LoadLibraryA");
    PatchAllModules();
    if (module == NULL) {
        SetLastError(savedError);
    }
    return module;
}

static HMODULE WINAPI HookLoadLibraryExA(LPCSTR fileName, HANDLE file, DWORD flags) {
    HMODULE module = RealLoadLibraryExA(fileName, file, flags);
    DWORD savedError = module == NULL ? GetLastError() : 0;
    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    if (module == NULL) {
        SetLastError(savedError);
    }
    LogLoadLibraryW(widePath, module, L"LoadLibraryExA");
    PatchAllModules();
    if (module == NULL) {
        SetLastError(savedError);
    }
    return module;
}

static ULONGLONG FileTimeValue(const FILETIME &value) {
    return ((ULONGLONG)value.dwHighDateTime << 32) | value.dwLowDateTime;
}

struct WindowSearch {
    DWORD pid;
    HWND result;
};

static BOOL CALLBACK FindClientWindowCallback(HWND window, LPARAM param) {
    WindowSearch *search = (WindowSearch *)param;
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid == search->pid && IsWindowVisible(window) && GetWindow(window, GW_OWNER) == NULL) {
        search->result = window;
        return FALSE;
    }
    return TRUE;
}

static HWND FindClientWindow() {
    WindowSearch search = {GetCurrentProcessId(), NULL};
    EnumWindows(FindClientWindowCallback, (LPARAM)&search);
    return search.result;
}

struct ErrorDialogSearch {
    DWORD pid;
    HWND result;
    WCHAR text[2048];
};

static BOOL IsErrorDialogText(const WCHAR *text) {
    return text != NULL
        && (ContainsNoCase(text, L"error code")
            || ContainsNoCase(text, L"-2147467261")
            || ContainsNoCase(text, L"0x80004003")
            || ContainsNoCase(text, L"E_POINTER")
            || ContainsNoCase(text, L"\u65e0\u6548\u6307\u9488"));
}

static BOOL CALLBACK FindErrorDialogChildCallback(HWND window, LPARAM param) {
    ErrorDialogSearch *search = (ErrorDialogSearch *)param;
    WCHAR text[1024];
    text[0] = L'\0';
    GetWindowTextW(window, text, 1024);
    if (!IsErrorDialogText(text)) {
        return TRUE;
    }
    search->result = GetAncestor(window, GA_ROOT);
    lstrcpynW(search->text, text, 2048);
    return FALSE;
}

static BOOL CALLBACK FindErrorDialogCallback(HWND window, LPARAM param) {
    ErrorDialogSearch *search = (ErrorDialogSearch *)param;
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid != search->pid || !IsWindowVisible(window)) {
        return TRUE;
    }

    WCHAR text[1024];
    text[0] = L'\0';
    GetWindowTextW(window, text, 1024);
    if (IsErrorDialogText(text)) {
        search->result = window;
        lstrcpynW(search->text, text, 2048);
        return FALSE;
    }

    EnumChildWindows(window, FindErrorDialogChildCallback, param);
    return search->result == NULL;
}

static void DetectErrorDialog() {
    if (InterlockedCompareExchange(&g_errorDialogDumpStarted, 0, 0) != 0) {
        return;
    }

    ErrorDialogSearch search;
    ZeroMemory(&search, sizeof(search));
    search.pid = GetCurrentProcessId();
    EnumWindows(FindErrorDialogCallback, (LPARAM)&search);
    if (search.result == NULL
            || InterlockedCompareExchange(&g_errorDialogDumpStarted, 1, 0) != 0) {
        return;
    }

    WCHAR line[2560];
    wsprintfW(
        line,
        L"event=error_dialog action=detected_by_watchdog hwnd=%p text=\"%s\"",
        search.result,
        search.text[0] ? search.text : L"(unavailable)");
    AppendLine(line);
    CaptureIncidentEvidence(L"error-dialog", TRUE, NULL);
}

static void SnapshotLastResource(WCHAR *path, DWORD pathCount, ULONGLONG *offset, DWORD *bytes, ULONGLONG *ageMs) {
    EnterCriticalSection(&g_resourceLock);
    lstrcpynW(path, g_lastResourcePath[0] ? g_lastResourcePath : L"(none)", pathCount);
    *offset = g_lastResourceOffset;
    *bytes = g_lastResourceBytes;
    *ageMs = g_lastResourceTick ? CurrentTick() - g_lastResourceTick : 0;
    LeaveCriticalSection(&g_resourceLock);
}

static BOOL WriteDiagnosticDump(const WCHAR *reason, EXCEPTION_POINTERS *exceptionPointers) {
    HMODULE dbghelp = RealLoadLibraryW ? RealLoadLibraryW(L"dbghelp.dll") : LoadLibraryW(L"dbghelp.dll");
    if (dbghelp == NULL) {
        WCHAR line[256];
        wsprintfW(line, L"event=dump status=failed reason=%s error=%lu detail=load_dbghelp", reason, GetLastError());
        AppendLine(line);
        return FALSE;
    }

    MiniDumpWriteDumpFn writeDump = (MiniDumpWriteDumpFn)GetProcAddress(dbghelp, "MiniDumpWriteDump");
    if (writeDump == NULL) {
        WCHAR line[256];
        wsprintfW(line, L"event=dump status=failed reason=%s error=%lu detail=missing_export", reason, GetLastError());
        AppendLine(line);
        FreeLibrary(dbghelp);
        return FALSE;
    }

    WCHAR dumpPath[MAX_PATH];
    wsprintfW(dumpPath, L"%s\\%s-%s-%lu.dmp", g_diagnosticsDir, reason, g_sessionId, GetTickCount());
    HANDLE dumpFile = RealCreateFileW(
        dumpPath,
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (dumpFile == INVALID_HANDLE_VALUE) {
        WCHAR line[512];
        wsprintfW(line, L"event=dump status=failed reason=%s error=%lu detail=create_file path=\"%s\"", reason, GetLastError(), dumpPath);
        AppendLine(line);
        FreeLibrary(dbghelp);
        return FALSE;
    }

    MINIDUMP_EXCEPTION_INFORMATION exceptionInfo;
    PMINIDUMP_EXCEPTION_INFORMATION exceptionInfoPtr = NULL;
    if (exceptionPointers != NULL) {
        exceptionInfo.ThreadId = GetCurrentThreadId();
        exceptionInfo.ExceptionPointers = exceptionPointers;
        exceptionInfo.ClientPointers = FALSE;
        exceptionInfoPtr = &exceptionInfo;
    }
    MINIDUMP_TYPE dumpType = (MINIDUMP_TYPE)(
        MiniDumpNormal
        | MiniDumpWithDataSegs
        | MiniDumpWithHandleData);
    BOOL result = writeDump(
        GetCurrentProcess(),
        GetCurrentProcessId(),
        dumpFile,
        dumpType,
        exceptionInfoPtr,
        NULL,
        NULL);
    DWORD savedError = result ? 0 : GetLastError();
    RealCloseHandle(dumpFile);
    FreeLibrary(dbghelp);

    WCHAR line[768];
    wsprintfW(
        line,
        L"event=dump status=%s reason=%s error=%lu path=\"%s\"",
        result ? L"ok" : L"failed",
        reason,
        savedError,
        dumpPath);
    AppendLine(line);
    return result;
}

static void SnapshotCompanionLog(const WCHAR *fileName, const WCHAR *reason) {
    WCHAR sourcePath[MAX_PATH];
    WCHAR destinationPath[MAX_PATH];
    if (lstrlenW(g_exeDir) + lstrlenW(fileName) + 1 >= MAX_PATH
            || lstrlenW(g_diagnosticsDir) + lstrlenW(fileName) + 2 >= MAX_PATH) {
        return;
    }
    lstrcpynW(sourcePath, g_exeDir, MAX_PATH);
    lstrcatW(sourcePath, fileName);
    lstrcpynW(destinationPath, g_diagnosticsDir, MAX_PATH);
    lstrcatW(destinationPath, L"\\");
    lstrcatW(destinationPath, fileName);

    HANDLE source = RealCreateFileW(
        sourcePath,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (source == INVALID_HANDLE_VALUE) {
        return;
    }
    HANDLE destination = RealCreateFileW(
        destinationPath,
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (destination == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        RealCloseHandle(source);
        WCHAR line[768];
        wsprintfW(
            line,
            L"event=incident_log_snapshot reason=%s status=failed error=%lu file=\"%s\"",
            reason,
            error,
            fileName);
        AppendLine(line);
        return;
    }

    BYTE buffer[16 * 1024];
    DWORD total = 0;
    BOOL success = TRUE;
    for (;;) {
        DWORD bytesRead = 0;
        if (!RealReadFile(source, buffer, sizeof(buffer), &bytesRead, NULL)) {
            success = FALSE;
            break;
        }
        if (bytesRead == 0) {
            break;
        }
        DWORD bytesWritten = 0;
        if (!WriteFile(destination, buffer, bytesRead, &bytesWritten, NULL)
                || bytesWritten != bytesRead) {
            success = FALSE;
            break;
        }
        total += bytesWritten;
    }
    DWORD error = success ? 0 : GetLastError();
    RealCloseHandle(destination);
    RealCloseHandle(source);

    WCHAR line[768];
    wsprintfW(
        line,
        L"event=incident_log_snapshot reason=%s status=%s error=%lu bytes=%lu file=\"%s\"",
        reason,
        success ? L"ok" : L"failed",
        error,
        total,
        fileName);
    AppendLine(line);
}

static void SnapshotCompanionLogs(const WCHAR *reason) {
    static const WCHAR *const kLogFiles[] = {
        L"EquipSlotDiagnostic.log",
        L"BeiDouSetItemCompat.log",
        L"DawnWarriorSkillCompat.log",
        L"BeiDouDamageSkinCompat.log",
        L"IndexedDamageNumberCompat.log",
        L"KaringSceneCompat.log",
        L"BeiDouVideo.log",
        L"BeiDouVideoProxy.log"
    };
    for (size_t i = 0; i < sizeof(kLogFiles) / sizeof(kLogFiles[0]); ++i) {
        SnapshotCompanionLog(kLogFiles[i], reason);
    }
}

static void LogIncidentModules(const WCHAR *reason) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (snapshot == INVALID_HANDLE_VALUE) {
        WCHAR line[256];
        wsprintfW(
            line,
            L"event=incident_modules reason=%s status=failed error=%lu",
            reason,
            GetLastError());
        AppendLine(line);
        return;
    }

    MODULEENTRY32W entry;
    ZeroMemory(&entry, sizeof(entry));
    entry.dwSize = sizeof(entry);
    if (Module32FirstW(snapshot, &entry)) {
        do {
            WCHAR line[1024];
            wsprintfW(
                line,
                L"event=incident_module reason=%s base=%p size=%lu path=\"%s\"",
                reason,
                entry.modBaseAddr,
                entry.modBaseSize,
                entry.szExePath);
            AppendLine(line);
        } while (Module32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
}

static void LogIncidentState(const WCHAR *reason) {
    WCHAR resourcePath[MAX_PATH];
    ULONGLONG resourceOffset = 0;
    DWORD resourceBytes = 0;
    ULONGLONG resourceAgeMs = 0;
    SnapshotLastResource(resourcePath, MAX_PATH, &resourceOffset, &resourceBytes, &resourceAgeMs);
    HANDLE process = GetCurrentProcess();
    DWORD handleCount = 0;
    GetProcessHandleCount(process, &handleCount);
    PVOID movie = g_flashMovieSlot != NULL ? *g_flashMovieSlot : NULL;
    WCHAR line[1536];
    wsprintfW(
        line,
        L"event=incident_state reason=%s tid=%lu handles=%lu gdi=%lu user=%lu client_window_ready=%ld flash_slot=%p flash_movie=%p flash_null_skips=%ld last_resource=\"%s\" resource_offset=%I64u resource_bytes=%lu resource_age_ms=%I64u",
        reason,
        GetCurrentThreadId(),
        handleCount,
        GetGuiResources(process, GR_GDIOBJECTS),
        GetGuiResources(process, GR_USEROBJECTS),
        InterlockedCompareExchange(&g_clientWindowReady, 0, 0),
        g_flashMovieSlot,
        movie,
        InterlockedCompareExchange(&g_flashRenderNullSkips, 0, 0),
        resourcePath,
        resourceOffset,
        resourceBytes,
        resourceAgeMs);
    AppendLine(line);
}

static void CaptureIncidentEvidence(
        const WCHAR *reason,
        BOOL writeDump,
        EXCEPTION_POINTERS *exceptionPointers) {
    LogIncidentState(reason);
    FlushRecentResourceHistory(reason);
    SnapshotCompanionLogs(reason);
    LogIncidentModules(reason);
    if (writeDump) {
        WriteDiagnosticDump(reason, exceptionPointers);
    }
}

static void LogDiagnosticFileInventory() {
    static const WCHAR *const kRelativePaths[] = {
        L"Data\\Skill\\000.img",
        L"Data\\Skill\\400.img",
        L"Data\\Skill\\410.img",
        L"Data\\Skill\\411.img",
        L"Data\\Skill\\412.img",
        L"Data\\String\\Skill.img",
        L"WzFileLogger.dll",
        L"WzFlashRenderer.dll",
        L"DawnWarriorSkillCompat.dll",
        L"BeiDouSetItemCompat.dll"
    };
    for (size_t i = 0; i < sizeof(kRelativePaths) / sizeof(kRelativePaths[0]); ++i) {
        WCHAR path[MAX_PATH];
        if (lstrlenW(g_exeDir) + lstrlenW(kRelativePaths[i]) + 1 >= MAX_PATH) {
            continue;
        }
        lstrcpynW(path, g_exeDir, MAX_PATH);
        lstrcatW(path, kRelativePaths[i]);

        WIN32_FILE_ATTRIBUTE_DATA data;
        ZeroMemory(&data, sizeof(data));
        BOOL exists = GetFileAttributesExW(path, GetFileExInfoStandard, &data);
        ULONGLONG size = exists
            ? ((ULONGLONG)data.nFileSizeHigh << 32) | data.nFileSizeLow
            : 0;
        WCHAR line[1024];
        wsprintfW(
            line,
            L"event=diagnostic_file status=%s error=%lu size=%I64u write_time=%08lx:%08lx path=\"%s\"",
            exists ? L"ok" : L"missing",
            exists ? 0 : GetLastError(),
            size,
            data.ftLastWriteTime.dwHighDateTime,
            data.ftLastWriteTime.dwLowDateTime,
            path);
        AppendLine(line);
    }
}

static LONG WINAPI DiagnosticExceptionFilter(EXCEPTION_POINTERS *exceptionPointers) {
    DWORD code = 0;
    PVOID address = NULL;
    if (exceptionPointers != NULL && exceptionPointers->ExceptionRecord != NULL) {
        code = exceptionPointers->ExceptionRecord->ExceptionCode;
        address = exceptionPointers->ExceptionRecord->ExceptionAddress;
    }

    WCHAR modulePath[MAX_PATH];
    modulePath[0] = L'\0';
    HMODULE faultModule = NULL;
    DWORD moduleOffset = 0;
    if (address != NULL && GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)address,
            &faultModule)) {
        GetModuleFileNameW(faultModule, modulePath, MAX_PATH);
        moduleOffset = (DWORD)((BYTE *)address - (BYTE *)faultModule);
    }

    WCHAR resourcePath[MAX_PATH];
    ULONGLONG resourceOffset = 0;
    DWORD resourceBytes = 0;
    ULONGLONG resourceAgeMs = 0;
    SnapshotLastResource(resourcePath, MAX_PATH, &resourceOffset, &resourceBytes, &resourceAgeMs);

    WCHAR line[2048];
    wsprintfW(
        line,
        L"event=crash code=0x%08lx address=%p module=\"%s\" module_offset=0x%08lx last_resource=\"%s\" resource_offset=%I64u resource_bytes=%lu resource_age_ms=%I64u",
        code,
        address,
        modulePath[0] ? modulePath : L"(unknown)",
        moduleOffset,
        resourcePath,
        resourceOffset,
        resourceBytes,
        resourceAgeMs);
    AppendLine(line);
    WriteDiagnosticDump(L"crash", exceptionPointers);

    if (g_previousExceptionFilter != NULL && g_previousExceptionFilter != DiagnosticExceptionFilter) {
        return g_previousExceptionFilter(exceptionPointers);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

static BOOL IsExecutableProtection(DWORD protection) {
    DWORD baseProtection = protection & 0xff;
    return baseProtection == PAGE_EXECUTE
        || baseProtection == PAGE_EXECUTE_READ
        || baseProtection == PAGE_EXECUTE_READWRITE
        || baseProtection == PAGE_EXECUTE_WRITECOPY;
}

static void FormatStackCodeCandidates(CONTEXT *context, DWORD maxStackDwords, WCHAR *out, DWORD outCount) {
    if (out == NULL || outCount == 0) {
        return;
    }
    out[0] = L'\0';
    if (context == NULL || context->Esp == 0) {
        lstrcpynW(out, L"(unavailable)", outCount);
        return;
    }

    BYTE *stackStart = (BYTE *)(ULONG_PTR)context->Esp;
    MEMORY_BASIC_INFORMATION stackInfo;
    ZeroMemory(&stackInfo, sizeof(stackInfo));
    if (VirtualQuery(stackStart, &stackInfo, sizeof(stackInfo)) == 0
            || stackInfo.State != MEM_COMMIT
            || (stackInfo.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        lstrcpynW(out, L"(unreadable)", outCount);
        return;
    }

    SIZE_T available = ((BYTE *)stackInfo.BaseAddress + stackInfo.RegionSize) - stackStart;
    DWORD slotCount = (DWORD)(available / sizeof(DWORD));
    if (slotCount > maxStackDwords) {
        slotCount = maxStackDwords;
    }

    DWORD candidateCount = 0;
    const DWORD *stackWords = (const DWORD *)stackStart;
    for (DWORD slot = 0; slot < slotCount && candidateCount < 8; ++slot) {
        PVOID candidate = (PVOID)(ULONG_PTR)stackWords[slot];
        MEMORY_BASIC_INFORMATION candidateInfo;
        ZeroMemory(&candidateInfo, sizeof(candidateInfo));
        if (candidate == NULL
                || VirtualQuery(candidate, &candidateInfo, sizeof(candidateInfo)) == 0
                || candidateInfo.State != MEM_COMMIT
                || !IsExecutableProtection(candidateInfo.Protect)
                || (candidateInfo.Protect & PAGE_GUARD) != 0) {
            continue;
        }

        HMODULE module = NULL;
        if (!GetModuleHandleExW(
                GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                (LPCWSTR)candidate,
                &module)) {
            continue;
        }

        WCHAR modulePath[MAX_PATH];
        modulePath[0] = L'\0';
        GetModuleFileNameW(module, modulePath, MAX_PATH);
        WCHAR *slash = FindLastSlash(modulePath);
        const WCHAR *moduleName = slash != NULL ? slash + 1 : modulePath;
        WCHAR shortName[64];
        lstrcpynW(shortName, moduleName[0] ? moduleName : L"(unknown)", 64);

        WCHAR entry[192];
        wsprintfW(
            entry,
            L"%ss%lu:%s+0x%08lx@%p",
            candidateCount == 0 ? L"" : L";",
            slot,
            shortName,
            (DWORD)((BYTE *)candidate - (BYTE *)module),
            candidate);
        if ((DWORD)(lstrlenW(out) + lstrlenW(entry) + 1) >= outCount) {
            break;
        }
        lstrcatW(out, entry);
        ++candidateCount;
    }

    if (candidateCount == 0) {
        lstrcpynW(out, L"(none)", outCount);
    }
}

static LONG WINAPI DiagnosticVectoredExceptionHandler(EXCEPTION_POINTERS *exceptionPointers) {
    if (!g_logFirstChanceExceptions
            || exceptionPointers == NULL
            || exceptionPointers->ExceptionRecord == NULL) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    EXCEPTION_RECORD *record = exceptionPointers->ExceptionRecord;
    const DWORD code = record->ExceptionCode;
    const BOOL isAccessViolation = code == EXCEPTION_ACCESS_VIOLATION;
    const BOOL isCppOrPointerException = code == 0xe06d7363 || code == 0x80004003;
    // The client can use C++ exceptions for ordinary control flow during
    // startup. Start this extra capture only after the first visible game
    // window, while still allowing the Flash incident marker to activate it.
    if (!isAccessViolation
            && (!isCppOrPointerException
                || (InterlockedCompareExchange(&g_clientWindowReady, 0, 0) == 0
                    && InterlockedCompareExchange(&g_flashRenderNullSkips, 0, 0) == 0))) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    LONG occurrence = isAccessViolation
        ? InterlockedIncrement(&g_firstChanceExceptionCount)
        : InterlockedIncrement(&g_cppFirstChanceExceptionCount);
    // A broken render loop can raise hundreds of first-chance exceptions. Keep
    // enough samples to identify the fault while avoiding a logging feedback loop.
    LONG limit = 32;
    if (occurrence > limit || InterlockedExchange(&g_firstChanceExceptionLogging, 1) != 0) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    CONTEXT *context = exceptionPointers->ContextRecord;
    PVOID address = record->ExceptionAddress;
    HMODULE faultModule = NULL;
    WCHAR modulePath[MAX_PATH];
    modulePath[0] = L'\0';
    DWORD moduleOffset = 0;
    if (address != NULL && GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)address,
            &faultModule)) {
        GetModuleFileNameW(faultModule, modulePath, MAX_PATH);
        moduleOffset = (DWORD)((BYTE *)address - (BYTE *)faultModule);
    }

    WCHAR stackCandidates[2048];
    if (occurrence <= (isAccessViolation ? 4 : 8)) {
        FormatStackCodeCandidates(context, isAccessViolation ? 32 : 96, stackCandidates, 2048);
    } else {
        lstrcpynW(stackCandidates, L"(sample_limit)", 2048);
    }

    WCHAR exceptionInfo[1024];
    exceptionInfo[0] = L'\0';
    DWORD parameterCount = record->NumberParameters;
    if (parameterCount > EXCEPTION_MAXIMUM_PARAMETERS) {
        parameterCount = EXCEPTION_MAXIMUM_PARAMETERS;
    }
    for (DWORD i = 0; i < parameterCount; ++i) {
        WCHAR entry[64];
        wsprintfW(
            entry,
            L"%si%lu=0x%08lx",
            i == 0 ? L"" : L";",
            i,
            (DWORD)(ULONG_PTR)record->ExceptionInformation[i]);
        if ((DWORD)(lstrlenW(exceptionInfo) + lstrlenW(entry) + 1) >= 1024) {
            break;
        }
        lstrcatW(exceptionInfo, entry);
    }
    if (exceptionInfo[0] == L'\0') {
        lstrcpynW(exceptionInfo, L"(none)", 1024);
    }

    WCHAR line[4096];
    wsprintfW(
        line,
        L"event=%s occurrence=%ld code=0x%08lx address=%p module=\"%s\" module_offset=0x%08lx eip=%p esp=%p eax=0x%08lx ebx=0x%08lx ecx=0x%08lx edx=0x%08lx esi=0x%08lx edi=0x%08lx exception_info=\"%s\" stack_candidates=\"%s\"",
        isAccessViolation ? L"first_chance_av" : L"first_chance_cpp",
        occurrence,
        code,
        address,
        modulePath[0] ? modulePath : L"(unknown)",
        moduleOffset,
        context ? (PVOID)(ULONG_PTR)context->Eip : NULL,
        context ? (PVOID)(ULONG_PTR)context->Esp : NULL,
        context ? context->Eax : 0,
        context ? context->Ebx : 0,
        context ? context->Ecx : 0,
        context ? context->Edx : 0,
        context ? context->Esi : 0,
        context ? context->Edi : 0,
        exceptionInfo,
        stackCandidates);
    AppendLine(line);
    if (!isAccessViolation
            && (code == 0x80004003
                || InterlockedCompareExchange(&g_flashRenderNullSkips, 0, 0) != 0)
            && InterlockedCompareExchange(&g_cppExceptionDumpStarted, 1, 0) == 0) {
        AppendLine(L"event=first_chance_cpp action=dump_incident_context");
        CaptureIncidentEvidence(L"first-chance-cpp", TRUE, exceptionPointers);
    }
    InterlockedExchange(&g_firstChanceExceptionLogging, 0);
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI WatchdogThreadProc(LPVOID) {
    LogDiagnosticFileInventory();
    HMODULE indexedDamageCompat = RealLoadLibraryA != NULL
        ? RealLoadLibraryA("IndexedDamageNumberCompat.dll")
        : NULL;
    AppendLine(indexedDamageCompat != NULL
        ? L"event=indexed_damage_number_compat status=loaded"
        : L"event=indexed_damage_number_compat status=not_found");

    HMODULE psapi = RealLoadLibraryW ? RealLoadLibraryW(L"psapi.dll") : LoadLibraryW(L"psapi.dll");
    GetProcessMemoryInfoFn getMemoryInfo = psapi
        ? (GetProcessMemoryInfoFn)GetProcAddress(psapi, "GetProcessMemoryInfo")
        : NULL;
    HANDLE process = GetCurrentProcess();
    FILETIME createTime;
    FILETIME exitTime;
    FILETIME kernelTime;
    FILETIME userTime;
    GetProcessTimes(process, &createTime, &exitTime, &kernelTime, &userTime);
    ULONGLONG previousCpu = FileTimeValue(kernelTime) + FileTimeValue(userTime);
    ULONGLONG previousTick = CurrentTick();
    ULONGLONG hungSince = 0;
    ULONGLONG highCpuSince = 0;
    BOOL hangDumpWritten = FALSE;
    BOOL highCpuDumpWritten = FALSE;
    BOOL manualDumpWritten = FALSE;
    BOOL sawClientWindow = FALSE;
    BOOL windowLossDumpWritten = FALSE;

    while (InterlockedCompareExchange(&g_shutdownRequested, 0, 0) == 0) {
        Sleep(g_healthIntervalMs);
        if (InterlockedCompareExchange(&g_shutdownRequested, 0, 0) != 0) {
            break;
        }

        ULONGLONG now = CurrentTick();
        GetProcessTimes(process, &createTime, &exitTime, &kernelTime, &userTime);
        ULONGLONG cpu = FileTimeValue(kernelTime) + FileTimeValue(userTime);
        ULONGLONG elapsedMs = now - previousTick;
        ULONGLONG cpuDelta = cpu - previousCpu;
        DWORD cpuTenths = elapsedMs ? (DWORD)(cpuDelta / elapsedMs / 10) : 0;
        previousCpu = cpu;
        previousTick = now;

        PROCESS_MEMORY_COUNTERS memory;
        ZeroMemory(&memory, sizeof(memory));
        memory.cb = sizeof(memory);
        if (getMemoryInfo != NULL) {
            getMemoryInfo(process, &memory, sizeof(memory));
        }
        DWORD handleCount = 0;
        GetProcessHandleCount(process, &handleCount);
        DWORD gdiObjects = GetGuiResources(process, GR_GDIOBJECTS);
        DWORD userObjects = GetGuiResources(process, GR_USEROBJECTS);
        HWND window = FindClientWindow();
        BOOL windowHung = window != NULL && IsHungAppWindow(window);
        DetectErrorDialog();
        if (window != NULL) {
            sawClientWindow = TRUE;
            InterlockedExchange(&g_clientWindowReady, 1);
        }
        if (sawClientWindow
                && GetModuleHandleA("BeiDouVideo.dll") != NULL
                && InterlockedCompareExchange(&g_bossSceneCompatLoadStarted, 1, 0) == 0) {
            HMODULE bossSceneCompat = RealLoadLibraryA != NULL
                ? RealLoadLibraryA("KaringSceneCompat.dll")
                : NULL;
            AppendLine(bossSceneCompat != NULL
                ? L"event=boss_scene_compat status=loaded"
                : L"event=boss_scene_compat status=not_found");
        }

        WCHAR resourcePath[MAX_PATH];
        ULONGLONG resourceOffset = 0;
        DWORD resourceBytes = 0;
        ULONGLONG resourceAgeMs = 0;
        SnapshotLastResource(resourcePath, MAX_PATH, &resourceOffset, &resourceBytes, &resourceAgeMs);

        WCHAR line[2048];
        wsprintfW(
            line,
            L"event=health cpu_core_pct=%lu.%lu working_set_mb=%lu commit_mb=%lu handles=%lu gdi=%lu user=%lu window=%s last_resource=\"%s\" resource_offset=%I64u resource_bytes=%lu resource_age_ms=%I64u",
            cpuTenths / 10,
            cpuTenths % 10,
            (DWORD)(memory.WorkingSetSize / (1024 * 1024)),
            (DWORD)(memory.PagefileUsage / (1024 * 1024)),
            handleCount,
            gdiObjects,
            userObjects,
            window == NULL ? L"missing" : (windowHung ? L"hung" : L"responsive"),
            resourcePath,
            resourceOffset,
            resourceBytes,
            resourceAgeMs);
        AppendLine(line);

        if (sawClientWindow && window == NULL && !windowLossDumpWritten) {
            AppendLine(L"event=window_lost reason=visible_client_window_disappeared");
            WriteDiagnosticDump(L"window-lost", NULL);
            windowLossDumpWritten = TRUE;
        }

        if (g_manualDumpHotkey && !manualDumpWritten
                && (GetAsyncKeyState(VK_CONTROL) & 0x8000)
                && (GetAsyncKeyState(VK_F12) & 0x8000)) {
            AppendLine(L"event=manual_dump hotkey=Ctrl+F12");
            WriteDiagnosticDump(L"manual", NULL);
            manualDumpWritten = TRUE;
        }

        if (windowHung) {
            if (hungSince == 0) {
                hungSince = now;
            }
            if (!hangDumpWritten && now - hungSince >= g_hangThresholdMs) {
                AppendLine(L"event=hang_detected reason=window_unresponsive");
                if (g_dumpOnHang) {
                    WriteDiagnosticDump(L"hang", NULL);
                }
                hangDumpWritten = TRUE;
            }
        } else {
            hungSince = 0;
            hangDumpWritten = FALSE;
        }

        if (cpuTenths >= g_highCpuThreshold * 10) {
            if (highCpuSince == 0) {
                highCpuSince = now;
            }
            if (g_highCpuThresholdMs > 0 && !highCpuDumpWritten && now - highCpuSince >= g_highCpuThresholdMs) {
                AppendLine(L"event=hang_detected reason=sustained_high_cpu");
                if (g_dumpOnHang) {
                    WriteDiagnosticDump(L"high-cpu", NULL);
                }
                highCpuDumpWritten = TRUE;
            }
        } else {
            highCpuSince = 0;
        }
    }

    if (psapi != NULL) {
        FreeLibrary(psapi);
    }
    return 0;
}

static void LoadConfiguration() {
    WCHAR configPath[MAX_PATH];
    lstrcpynW(configPath, g_exeDir, MAX_PATH);
    lstrcatW(configPath, L"beidou_diagnostics.ini");
    g_healthIntervalMs = GetPrivateProfileIntW(L"diagnostics", L"health_interval_ms", 1000, configPath);
    g_hangThresholdMs = GetPrivateProfileIntW(L"diagnostics", L"hang_threshold_ms", 5000, configPath);
    g_highCpuThreshold = GetPrivateProfileIntW(L"diagnostics", L"high_cpu_threshold", 70, configPath);
    g_highCpuThresholdMs = GetPrivateProfileIntW(L"diagnostics", L"high_cpu_threshold_ms", 3000, configPath);
    g_dumpOnHang = GetPrivateProfileIntW(L"diagnostics", L"dump_on_hang", 1, configPath) != 0;
    g_manualDumpHotkey = GetPrivateProfileIntW(L"diagnostics", L"manual_dump_hotkey", 1, configPath) != 0;
    g_logFirstChanceExceptions = GetPrivateProfileIntW(L"diagnostics", L"log_first_chance_exceptions", 1, configPath) != 0;
    g_logSuccessfulMappings = GetPrivateProfileIntW(L"diagnostics", L"log_successful_mappings", 0, configPath) != 0;
    if (g_healthIntervalMs < 1000) {
        g_healthIntervalMs = 1000;
    }
}

static void RemoveDirectoryTree(const WCHAR *directory) {
    WCHAR searchPath[MAX_PATH];
    if (lstrlenW(directory) + 3 >= MAX_PATH) {
        return;
    }
    lstrcpynW(searchPath, directory, MAX_PATH);
    lstrcatW(searchPath, L"\\*");

    WIN32_FIND_DATAW entry;
    HANDLE search = FindFirstFileW(searchPath, &entry);
    if (search != INVALID_HANDLE_VALUE) {
        do {
            if (lstrcmpW(entry.cFileName, L".") == 0 ||
                lstrcmpW(entry.cFileName, L"..") == 0) {
                continue;
            }

            WCHAR childPath[MAX_PATH];
            if (lstrlenW(directory) + lstrlenW(entry.cFileName) + 2 >= MAX_PATH) {
                continue;
            }
            lstrcpynW(childPath, directory, MAX_PATH);
            lstrcatW(childPath, L"\\");
            lstrcatW(childPath, entry.cFileName);

            if ((entry.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
                if ((entry.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
                    RemoveDirectoryW(childPath);
                } else {
                    RemoveDirectoryTree(childPath);
                }
            } else {
                if ((entry.dwFileAttributes & FILE_ATTRIBUTE_READONLY) != 0) {
                    SetFileAttributesW(
                        childPath,
                        entry.dwFileAttributes & ~FILE_ATTRIBUTE_READONLY);
                }
                DeleteFileW(childPath);
            }
        } while (FindNextFileW(search, &entry));
        FindClose(search);
    }
    RemoveDirectoryW(directory);
}

static void InitPaths(HMODULE self) {
    WCHAR exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    lstrcpynW(g_exeDir, exePath, MAX_PATH);
    WCHAR *lastSlash = FindLastSlash(g_exeDir);
    if (lastSlash != NULL) {
        *(lastSlash + 1) = L'\0';
    }
    lstrcpynW(g_diagnosticsDir, g_exeDir, MAX_PATH);
    lstrcatW(g_diagnosticsDir, L"diagnostics");
    RemoveDirectoryTree(g_diagnosticsDir);
    if (!CreateDirectoryW(g_diagnosticsDir, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        lstrcpynW(g_diagnosticsDir, g_exeDir, MAX_PATH);
    }

    SYSTEMTIME st;
    GetLocalTime(&st);
    wsprintfW(
        g_sessionId,
        L"%04u%02u%02u-%02u%02u%02u-pid%lu",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond,
        GetCurrentProcessId());
    wsprintfW(g_logPath, L"%s\\session-%s.log", g_diagnosticsDir, g_sessionId);
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_selfModule = module;
        DisableThreadLibraryCalls(module);
        InitializeCriticalSection(&g_logLock);
        InitializeCriticalSection(&g_resourceLock);
        InitPaths(module);

        RefreshOriginalFunctions();
        LoadConfiguration();

        WCHAR line[1024];
        wsprintfW(
            line,
            L"event=session_start session=%s pid=%lu exe_dir=\"%s\" health_interval_ms=%lu hang_threshold_ms=%lu high_cpu_threshold=%lu high_cpu_threshold_ms=%lu dump_on_hang=%lu manual_dump_hotkey=%lu log_first_chance_exceptions=%lu log_successful_mappings=%lu",
            g_sessionId,
            GetCurrentProcessId(),
            g_exeDir,
            g_healthIntervalMs,
            g_hangThresholdMs,
            g_highCpuThreshold,
            g_highCpuThresholdMs,
            g_dumpOnHang ? 1 : 0,
            g_manualDumpHotkey ? 1 : 0,
            g_logFirstChanceExceptions ? 1 : 0,
            g_logSuccessfulMappings ? 1 : 0);
        AppendLine(line);
        g_previousExceptionFilter = SetUnhandledExceptionFilter(DiagnosticExceptionFilter);
        g_vectoredExceptionHandler = AddVectoredExceptionHandler(1, DiagnosticVectoredExceptionHandler);
        AppendLine(g_vectoredExceptionHandler != NULL
            ? L"event=first_chance_handler status=installed av_limit=32 cpp_limit=32 filters=C0000005/E06D7363/80004003 cpp_after_client_window=1 av_stack_samples=4 cpp_stack_samples=8 stack_dwords=32/96"
            : L"event=first_chance_handler status=failed av_limit=32 cpp_limit=32 filters=C0000005/E06D7363/80004003 cpp_after_client_window=1 av_stack_samples=4 cpp_stack_samples=8 stack_dwords=32/96");
        PatchAllModules();
        g_watchdogThread = CreateThread(NULL, 0, WatchdogThreadProc, NULL, 0, NULL);
        if (g_watchdogThread == NULL) {
            AppendLine(L"event=watchdog status=failed");
        } else {
            AppendLine(L"event=watchdog status=started");
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        InterlockedExchange(&g_shutdownRequested, 1);
        AppendLine(L"event=session_end reason=process_detach");
        if (g_watchdogThread != NULL) {
            CloseHandle(g_watchdogThread);
            g_watchdogThread = NULL;
        }
        if (g_vectoredExceptionHandler != NULL) {
            RemoveVectoredExceptionHandler(g_vectoredExceptionHandler);
            g_vectoredExceptionHandler = NULL;
        }
        SetUnhandledExceptionFilter(g_previousExceptionFilter);
        DeleteCriticalSection(&g_resourceLock);
        DeleteCriticalSection(&g_logLock);
    }
    return TRUE;
}
