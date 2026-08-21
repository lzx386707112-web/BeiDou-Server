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
static volatile LONG g_karingCompatLoadStarted = 0;
static BOOL g_inLog = FALSE;
static WCHAR g_wideLogLine[4096];
static CHAR g_utf8LogLine[16384];
static HANDLE g_watchdogThread = NULL;
static LPTOP_LEVEL_EXCEPTION_FILTER g_previousExceptionFilter = NULL;
static DWORD g_healthIntervalMs = 1000;
static DWORD g_hangThresholdMs = 5000;
static DWORD g_highCpuThreshold = 70;
static DWORD g_highCpuThresholdMs = 3000;
static BOOL g_dumpOnHang = TRUE;
static BOOL g_manualDumpHotkey = TRUE;

struct ResourceHandleEntry {
    HANDLE handle;
    WCHAR path[MAX_PATH];
    ULONGLONG openedTick;
    ULONGLONG totalBytesRead;
};

static const int kMaxResourceHandles = 256;
static ResourceHandleEntry g_resourceHandles[kMaxResourceHandles];
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
static int WINAPI HookMessageBoxW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type);
static int WINAPI HookMessageBoxA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type);
static HANDLE WINAPI HookCreateFileMappingA(HANDLE file, LPSECURITY_ATTRIBUTES attrs, DWORD protect, DWORD maxSizeHigh, DWORD maxSizeLow, LPCSTR name);
static HANDLE WINAPI HookOpenFileMappingA(DWORD desiredAccess, BOOL inheritHandle, LPCSTR name);
static LPVOID WINAPI HookMapViewOfFile(HANDLE mapping, DWORD desiredAccess, DWORD offsetHigh, DWORD offsetLow, SIZE_T bytesToMap);
static BOOL WINAPI HookReadFile(HANDLE file, LPVOID buffer, DWORD bytesToRead, LPDWORD bytesRead, LPOVERLAPPED overlapped);
static BOOL WINAPI HookCloseHandle(HANDLE object);
static LPTOP_LEVEL_EXCEPTION_FILTER WINAPI HookSetUnhandledExceptionFilter(LPTOP_LEVEL_EXCEPTION_FILTER filter);
static VOID WINAPI HookExitProcess(UINT exitCode);
static BOOL WINAPI HookTerminateProcess(HANDLE process, UINT exitCode);
static LONG WINAPI DiagnosticExceptionFilter(EXCEPTION_POINTERS *exceptionPointers);
static BOOL WriteDiagnosticDump(const WCHAR *reason, EXCEPTION_POINTERS *exceptionPointers);
static BOOL ShouldLogPath(const WCHAR *path);
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
        RealGetFinalPathNameByHandleW = (GetFinalPathNameByHandleWFn)GetProcAddress(kernel32, "GetFinalPathNameByHandleW");
    }
    if (user32 != NULL) {
        RealMessageBoxW = (MessageBoxWFn)GetProcAddress(user32, "MessageBoxW");
        RealMessageBoxA = (MessageBoxAFn)GetProcAddress(user32, "MessageBoxA");
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

static BOOL RecordResourceRead(HANDLE handle, DWORD bytesRead, ULONGLONG offset, WCHAR *pathOut, DWORD pathCount) {
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
    }
    LeaveCriticalSection(&g_resourceLock);
    return tracked;
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

static void LogLoadLibraryW(LPCWSTR path, HMODULE result, const WCHAR *apiName) {
    if (!ShouldLogFileApiPath(path)) {
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

    WCHAR wideName[1024];
    WCHAR filePath[2048];
    AnsiToWide(name, wideName, 1024);
    GetPathForHandle(file, filePath, 2048);
    if (result == NULL) {
        SetLastError(savedError);
    }
    LogMappingW(L"CreateFileMappingA", file, result, wideName, filePath);
    if (result == NULL) {
        SetLastError(savedError);
    }
    return result;
}

static HANDLE WINAPI HookOpenFileMappingA(DWORD desiredAccess, BOOL inheritHandle, LPCSTR name) {
    HANDLE result = RealOpenFileMappingA(desiredAccess, inheritHandle, name);
    DWORD savedError = result == NULL ? GetLastError() : 0;

    WCHAR wideName[1024];
    AnsiToWide(name, wideName, 1024);
    if (result == NULL) {
        SetLastError(savedError);
    }
    LogMappingW(L"OpenFileMappingA", NULL, result, wideName, L"");
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

    WCHAR line[512];
    DWORD err = (result == NULL) ? GetLastError() : 0;
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
    BOOL tracked = RecordResourceRead(file, actualBytes, offset, path, MAX_PATH);
    DWORD elapsedMs = (DWORD)(CurrentTick() - started);
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
    WriteDiagnosticDump(L"exit-process", NULL);
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

static int WINAPI HookMessageBoxW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type) {
    WCHAR line[4096];
    wsprintfW(
        line,
        L"event=message_box api=MessageBoxW caption=\"%s\" text=\"%s\"",
        caption ? caption : L"(null)",
        text ? text : L"(null)");
    AppendLine(line);
    if (text != NULL
            && ContainsNoCase(text, L"error code")
            && InterlockedExchange(&g_errorDialogDumpStarted, 1) == 0) {
        AppendLine(L"event=error_dialog action=dump_before_message_box");
        WriteDiagnosticDump(L"error-dialog", NULL);
    }
    if (RealMessageBoxW != NULL) {
        return RealMessageBoxW(hwnd, text, caption, type);
    }
    return 0;
}

static int WINAPI HookMessageBoxA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type) {
    WCHAR wideText[2048];
    WCHAR wideCaption[512];
    WCHAR line[4096];
    AnsiToWide(text, wideText, 2048);
    AnsiToWide(caption, wideCaption, 512);
    wsprintfW(line, L"event=message_box api=MessageBoxA caption=\"%s\" text=\"%s\"", wideCaption, wideText);
    AppendLine(line);
    if (ContainsNoCase(wideText, L"error code")
            && InterlockedExchange(&g_errorDialogDumpStarted, 1) == 0) {
        AppendLine(L"event=error_dialog action=dump_before_message_box");
        WriteDiagnosticDump(L"error-dialog", NULL);
    }
    if (RealMessageBoxA != NULL) {
        return RealMessageBoxA(hwnd, text, caption, type);
    }
    return 0;
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

    WCHAR path[MAX_PATH];
    path[0] = L'\0';
    GetModuleFileNameW(module, path, MAX_PATH);
    if (!IsClientModulePath(path)) {
        return 0;
    }

    int createFileW = PatchImport(module, "KERNEL32.dll", "CreateFileW", (void *)RealCreateFileW, (void *)HookCreateFileW);
    int createFileA = PatchImport(module, "KERNEL32.dll", "CreateFileA", (void *)RealCreateFileA, (void *)HookCreateFileA);
    int lopen = PatchImport(module, "KERNEL32.dll", "_lopen", (void *)RealLopen, (void *)HookLopen);
    int findFirstFileA = PatchImport(module, "KERNEL32.dll", "FindFirstFileA", (void *)RealFindFirstFileA, (void *)HookFindFirstFileA);
    int getProcAddress = 0;
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
        + fopen + fread;
    if (total > 0 && logResult && g_patchSummaryLogs > 0) {
        --g_patchSummaryLogs;
        WCHAR line[4096];
        wsprintfW(
            line,
            L"event=hook_summary total=%d CreateFileW=%d CreateFileA=%d _lopen=%d FindFirstFileA=%d GetProcAddress=%d Mapping=%d/%d/%d ReadFile=%d CloseHandle=%d ExceptionFilter=%d Exit=%d/%d LoadLibrary=%d/%d/%d MessageBox=%d/%d fopen=%d fread=%d module=\"%s\"",
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
            loadLibraryW,
            loadLibraryA,
            loadLibraryExA,
            messageBoxW,
            messageBoxA,
            fopen,
            fread,
            path);
        AppendLine(line);
    }
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

static DWORD WINAPI WatchdogThreadProc(LPVOID) {
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
        if (window != NULL) {
            sawClientWindow = TRUE;
        }
        if (sawClientWindow
                && GetModuleHandleA("BeiDouVideo.dll") != NULL
                && InterlockedCompareExchange(&g_karingCompatLoadStarted, 1, 0) == 0) {
            HMODULE karingCompat = RealLoadLibraryA != NULL
                ? RealLoadLibraryA("KaringSceneCompat.dll")
                : NULL;
            AppendLine(karingCompat != NULL
                ? L"event=karing_scene_compat status=loaded"
                : L"event=karing_scene_compat status=not_found");
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
    if (g_healthIntervalMs < 1000) {
        g_healthIntervalMs = 1000;
    }
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
            L"event=session_start session=%s pid=%lu exe_dir=\"%s\" health_interval_ms=%lu hang_threshold_ms=%lu high_cpu_threshold=%lu high_cpu_threshold_ms=%lu dump_on_hang=%lu manual_dump_hotkey=%lu",
            g_sessionId,
            GetCurrentProcessId(),
            g_exeDir,
            g_healthIntervalMs,
            g_hangThresholdMs,
            g_highCpuThreshold,
            g_highCpuThresholdMs,
            g_dumpOnHang ? 1 : 0,
            g_manualDumpHotkey ? 1 : 0);
        AppendLine(line);
        g_previousExceptionFilter = SetUnhandledExceptionFilter(DiagnosticExceptionFilter);
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
        SetUnhandledExceptionFilter(g_previousExceptionFilter);
        DeleteCriticalSection(&g_resourceLock);
        DeleteCriticalSection(&g_logLock);
    }
    return TRUE;
}
