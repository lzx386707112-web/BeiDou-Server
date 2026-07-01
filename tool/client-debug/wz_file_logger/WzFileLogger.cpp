// Lightweight debug DLL for BeiDou.exe.
//
// Logs resource file opens and message boxes after BeiDou.exe loads this DLL.
// Build as 32-bit.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
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
static GetFinalPathNameByHandleWFn RealGetFinalPathNameByHandleW = NULL;
static FopenFn RealFopen = NULL;
static FreadFn RealFread = NULL;

static CRITICAL_SECTION g_logLock;
static HMODULE g_selfModule = NULL;
static WCHAR g_logPath[MAX_PATH];
static WCHAR g_exeDir[MAX_PATH];
static volatile LONG g_patching = 0;
static volatile LONG g_verboseFileLogs = 300;
static volatile LONG g_patchSummaryLogs = 30;
static BOOL g_inLog = FALSE;
static WCHAR g_wideLogLine[4096];
static CHAR g_utf8LogLine[16384];

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
            L"%04u-%02u-%02u %02u:%02u:%02u.%03u [tid=%lu] %s\r\n",
            st.wYear, st.wMonth, st.wDay,
            st.wHour, st.wMinute, st.wSecond, st.wMilliseconds,
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
        L"CreateFileW result=%p err=%lu access=0x%08lx disp=%lu path=%s",
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
        L"_lopen result=0x%08lx err=%lu flags=0x%08x path=%s",
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
        L"FindFirstFileA result=%p err=%lu pattern=%s",
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
        L"%s result=%p err=%lu path=%s",
        apiName,
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

static void LogReadFile(HANDLE file, DWORD bytesToRead, DWORD bytesReadValue, BOOL result) {
    if (g_verboseFileLogs <= 0 && result) {
        return;
    }
    if (g_verboseFileLogs > 0) {
        --g_verboseFileLogs;
    }

    WCHAR line[512];
    DWORD err = result ? 0 : GetLastError();
    wsprintfW(
        line,
        L"ReadFile file=%p result=%lu err=%lu requested=%lu read=%lu",
        file,
        result ? 1 : 0,
        err,
        bytesToRead,
        bytesReadValue);
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
    LogCreateFileW(fileName, desiredAccess, creationDisposition, result);
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

    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    LogCreateFileW(widePath, desiredAccess, creationDisposition, result);
    return result;
}

static HFILE WINAPI HookLopen(LPCSTR fileName, int flags) {
    HFILE result = RealLopen(fileName, flags);

    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    LogLopenW(widePath, flags, result);
    return result;
}

static HANDLE WINAPI HookFindFirstFileA(LPCSTR fileName, LPWIN32_FIND_DATAA findFileData) {
    HANDLE result = RealFindFirstFileA(fileName, findFileData);

    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    LogFindFirstFileW(widePath, result);
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

    WCHAR wideName[1024];
    WCHAR filePath[2048];
    AnsiToWide(name, wideName, 1024);
    GetPathForHandle(file, filePath, 2048);
    LogMappingW(L"CreateFileMappingA", file, result, wideName, filePath);
    return result;
}

static HANDLE WINAPI HookOpenFileMappingA(DWORD desiredAccess, BOOL inheritHandle, LPCSTR name) {
    HANDLE result = RealOpenFileMappingA(desiredAccess, inheritHandle, name);

    WCHAR wideName[1024];
    AnsiToWide(name, wideName, 1024);
    LogMappingW(L"OpenFileMappingA", NULL, result, wideName, L"");
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
    return result;
}

static BOOL WINAPI HookReadFile(
    HANDLE file,
    LPVOID buffer,
    DWORD bytesToRead,
    LPDWORD bytesRead,
    LPOVERLAPPED overlapped) {
    BOOL result = RealReadFile(file, buffer, bytesToRead, bytesRead, overlapped);
    LogReadFile(file, bytesToRead, bytesRead ? *bytesRead : 0, result);
    return result;
}

static void *__cdecl HookFopen(const char *fileName, const char *mode) {
    void *result = RealFopen(fileName, mode);

    WCHAR widePath[2048];
    WCHAR wideMode[64];
    AnsiToWide(fileName, widePath, 2048);
    AnsiToWide(mode, wideMode, 64);
    if (ShouldLogFileApiPath(widePath)) {
        WCHAR line[4096];
        wsprintfW(line, L"fopen result=%p mode=%s path=%s", result, wideMode, widePath);
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
        L"MessageBoxW caption=%s text=%s",
        caption ? caption : L"(null)",
        text ? text : L"(null)");
    AppendLine(line);
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
    wsprintfW(line, L"MessageBoxA caption=%s text=%s", wideCaption, wideText);
    AppendLine(line);
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
        + createFileMappingA + openFileMappingA + mapViewOfFile + readFile
        + loadLibraryW + loadLibraryA + loadLibraryExA + messageBoxW + messageBoxA
        + fopen + fread;
    if (total > 0 && logResult && g_patchSummaryLogs > 0) {
        --g_patchSummaryLogs;
        WCHAR line[4096];
        wsprintfW(
            line,
            L"PatchModule total=%d CreateFileW=%d CreateFileA=%d _lopen=%d FindFirstFileA=%d GetProcAddress=%d Mapping=%d/%d/%d ReadFile=%d LoadLibrary=%d/%d/%d MessageBox=%d/%d fopen=%d fread=%d module=%s",
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
    LogLoadLibraryW(fileName, module, L"LoadLibraryW");
    PatchAllModules();
    return module;
}

static HMODULE WINAPI HookLoadLibraryA(LPCSTR fileName) {
    HMODULE module = RealLoadLibraryA(fileName);
    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    LogLoadLibraryW(widePath, module, L"LoadLibraryA");
    PatchAllModules();
    return module;
}

static HMODULE WINAPI HookLoadLibraryExA(LPCSTR fileName, HANDLE file, DWORD flags) {
    HMODULE module = RealLoadLibraryExA(fileName, file, flags);
    WCHAR widePath[2048];
    AnsiToWide(fileName, widePath, 2048);
    LogLoadLibraryW(widePath, module, L"LoadLibraryExA");
    PatchAllModules();
    return module;
}

static void InitPaths(HMODULE self) {
    WCHAR exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    lstrcpynW(g_exeDir, exePath, MAX_PATH);
    WCHAR *lastSlash = FindLastSlash(g_exeDir);
    if (lastSlash != NULL) {
        *(lastSlash + 1) = L'\0';
    }
    lstrcpynW(g_logPath, g_exeDir, MAX_PATH);
    lstrcatW(g_logPath, L"beidou_wz_access.log");
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_selfModule = module;
        DisableThreadLibraryCalls(module);
        InitializeCriticalSection(&g_logLock);
        InitPaths(module);

        RefreshOriginalFunctions();

        AppendLine(L"WzFileLogger attached");
        PatchAllModules();
    } else if (reason == DLL_PROCESS_DETACH) {
        AppendLine(L"WzFileLogger detached");
        DeleteCriticalSection(&g_logLock);
    }
    return TRUE;
}
