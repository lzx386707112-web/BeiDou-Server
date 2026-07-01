// Starts BeiDou.exe and injects WzFileLogger.dll.
//
// Build as 32-bit console app:
//   cl /EHsc BeiDouLogLauncher.cpp

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <strsafe.h>
#include <stdio.h>

static BOOL FileExists(const WCHAR *path) {
    DWORD attr = GetFileAttributesW(path);
    return attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

static void DirName(WCHAR *path) {
    WCHAR *slash = wcsrchr(path, L'\\');
    if (slash != NULL) {
        *slash = L'\0';
    }
}

static BOOL InjectDll(HANDLE process, const WCHAR *dllPath) {
    SIZE_T bytes = (lstrlenW(dllPath) + 1) * sizeof(WCHAR);
    LPVOID remote = VirtualAllocEx(process, NULL, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (remote == NULL) {
        wprintf(L"VirtualAllocEx failed: %lu\n", GetLastError());
        return FALSE;
    }

    if (!WriteProcessMemory(process, remote, dllPath, bytes, NULL)) {
        wprintf(L"WriteProcessMemory failed: %lu\n", GetLastError());
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        return FALSE;
    }

    HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
    LPTHREAD_START_ROUTINE loadLibraryW =
        (LPTHREAD_START_ROUTINE)GetProcAddress(kernel32, "LoadLibraryW");
    HANDLE thread = CreateRemoteThread(process, NULL, 0, loadLibraryW, remote, 0, NULL);
    if (thread == NULL) {
        wprintf(L"CreateRemoteThread failed: %lu\n", GetLastError());
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        return FALSE;
    }

    WaitForSingleObject(thread, INFINITE);
    DWORD remoteResult = 0;
    GetExitCodeThread(thread, &remoteResult);
    CloseHandle(thread);
    VirtualFreeEx(process, remote, 0, MEM_RELEASE);

    if (remoteResult == 0) {
        wprintf(L"LoadLibraryW in target returned NULL.\n");
        return FALSE;
    }
    return TRUE;
}

int wmain(int argc, WCHAR **argv) {
    WCHAR exePath[MAX_PATH];
    WCHAR dllPath[MAX_PATH];

    if (argc >= 2) {
        StringCchCopyW(exePath, MAX_PATH, argv[1]);
    } else {
        StringCchCopyW(exePath, MAX_PATH, L"..\\..\\..\\clien\\BeiDou.exe");
    }

    if (argc >= 3) {
        StringCchCopyW(dllPath, MAX_PATH, argv[2]);
    } else {
        GetModuleFileNameW(NULL, dllPath, MAX_PATH);
        DirName(dllPath);
        StringCchCatW(dllPath, MAX_PATH, L"\\WzFileLogger.dll");
    }

    WCHAR fullExe[MAX_PATH];
    WCHAR fullDll[MAX_PATH];
    if (GetFullPathNameW(exePath, MAX_PATH, fullExe, NULL) == 0 ||
        GetFullPathNameW(dllPath, MAX_PATH, fullDll, NULL) == 0) {
        wprintf(L"GetFullPathNameW failed: %lu\n", GetLastError());
        return 1;
    }

    if (!FileExists(fullExe)) {
        wprintf(L"BeiDou.exe not found: %s\n", fullExe);
        return 1;
    }
    if (!FileExists(fullDll)) {
        wprintf(L"WzFileLogger.dll not found: %s\n", fullDll);
        return 1;
    }

    WCHAR workDir[MAX_PATH];
    StringCchCopyW(workDir, MAX_PATH, fullExe);
    DirName(workDir);

    WCHAR commandLine[MAX_PATH * 2];
    StringCchPrintfW(commandLine, MAX_PATH * 2, L"\"%s\"", fullExe);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));
    si.cb = sizeof(si);

    if (!CreateProcessW(
            fullExe,
            commandLine,
            NULL,
            NULL,
            FALSE,
            CREATE_SUSPENDED,
            NULL,
            workDir,
            &si,
            &pi)) {
        wprintf(L"CreateProcessW failed: %lu\n", GetLastError());
        return 1;
    }

    BOOL injected = InjectDll(pi.hProcess, fullDll);
    ResumeThread(pi.hThread);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    if (!injected) {
        wprintf(L"Client started, but DLL injection failed.\n");
        return 2;
    }

    wprintf(L"Client started with logger. Log file: %s\\beidou_wz_access.log\n", workDir);
    return 0;
}
