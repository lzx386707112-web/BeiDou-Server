#include <windows.h>

#include <stdint.h>

namespace {

constexpr wchar_t kReportName[] = L"BeiDouDependencyReport.txt";
constexpr int kMaxFiles = 256;
constexpr int kMaxImports = 512;

struct Writer {
    HANDLE file;
};

struct PeFile {
    HANDLE file;
    HANDLE mapping;
    const uint8_t* data;
    DWORD size;
    const IMAGE_NT_HEADERS32* nt;
    bool pe32;
};

struct LocalFile {
    wchar_t name[MAX_PATH];
};

struct ImportEntry {
    char name[128];
    DWORD thunkRva;
    bool delayed;
};

struct Results {
    int files;
    int invalidPe;
    int wrongMachine;
    int missingImports;
    int missingExports;
    int wrongImportMachine;
    bool missingVc140;
    bool missingVc71;
    bool missingDirectX;
};

void CopyWide(wchar_t* destination, int capacity, const wchar_t* source) {
    if (capacity <= 0) {
        return;
    }
    int index = 0;
    while (index + 1 < capacity && source[index] != L'\0') {
        destination[index] = source[index];
        ++index;
    }
    destination[index] = L'\0';
}

void CopyAnsi(char* destination, int capacity, const char* source) {
    if (capacity <= 0) {
        return;
    }
    int index = 0;
    while (index + 1 < capacity && source[index] != '\0') {
        destination[index] = source[index];
        ++index;
    }
    destination[index] = '\0';
}

bool EqualsIgnoreCaseA(const char* left, const char* right) {
    return lstrcmpiA(left, right) == 0;
}

bool StartsWithIgnoreCaseA(const char* text, const char* prefix) {
    while (*prefix != '\0') {
        char left = *text;
        char right = *prefix;
        if (left >= 'A' && left <= 'Z') {
            left = static_cast<char>(left - 'A' + 'a');
        }
        if (right >= 'A' && right <= 'Z') {
            right = static_cast<char>(right - 'A' + 'a');
        }
        if (left != right || *text == '\0') {
            return false;
        }
        ++text;
        ++prefix;
    }
    return true;
}

bool ContainsIgnoreCaseA(const char* text, const char* needle) {
    if (*needle == '\0') {
        return true;
    }
    for (; *text != '\0'; ++text) {
        if (StartsWithIgnoreCaseA(text, needle)) {
            return true;
        }
    }
    return false;
}

void WriteBytes(Writer* writer, const void* data, DWORD size) {
    DWORD written = 0;
    if (writer->file != INVALID_HANDLE_VALUE && size != 0) {
        WriteFile(writer->file, data, size, &written, nullptr);
    }
}

void WriteAnsi(Writer* writer, const char* text) {
    WriteBytes(writer, text, static_cast<DWORD>(lstrlenA(text)));
}

void WriteWide(Writer* writer, const wchar_t* text) {
    char buffer[MAX_PATH * 4];
    const int length = WideCharToMultiByte(
        CP_UTF8, 0, text, -1, buffer, static_cast<int>(sizeof(buffer)), nullptr, nullptr);
    if (length > 1) {
        WriteBytes(writer, buffer, static_cast<DWORD>(length - 1));
    }
}

void WriteNumber(Writer* writer, DWORD value) {
    char digits[16];
    int count = 0;
    do {
        digits[count++] = static_cast<char>('0' + value % 10);
        value /= 10;
    } while (value != 0 && count < static_cast<int>(sizeof(digits)));
    while (count > 0) {
        WriteBytes(writer, &digits[--count], 1);
    }
}

void WriteHex16(Writer* writer, WORD value) {
    constexpr char digits[] = "0123456789ABCDEF";
    char text[6] = {'0', 'x', '0', '0', '0', '0'};
    for (int index = 5; index >= 2; --index) {
        text[index] = digits[value & 0x0f];
        value = static_cast<WORD>(value >> 4);
    }
    WriteBytes(writer, text, sizeof(text));
}

void WriteLine(Writer* writer, const char* text) {
    WriteAnsi(writer, text);
    WriteAnsi(writer, "\r\n");
}

void ClosePe(PeFile* pe) {
    if (pe->data != nullptr) {
        UnmapViewOfFile(pe->data);
    }
    if (pe->mapping != nullptr) {
        CloseHandle(pe->mapping);
    }
    if (pe->file != INVALID_HANDLE_VALUE) {
        CloseHandle(pe->file);
    }
    pe->file = INVALID_HANDLE_VALUE;
    pe->mapping = nullptr;
    pe->data = nullptr;
    pe->size = 0;
    pe->nt = nullptr;
    pe->pe32 = false;
}

bool OpenPe(const wchar_t* path, PeFile* pe) {
    pe->file = CreateFileW(
        path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    pe->mapping = nullptr;
    pe->data = nullptr;
    pe->size = 0;
    pe->nt = nullptr;
    pe->pe32 = false;
    if (pe->file == INVALID_HANDLE_VALUE) {
        return false;
    }

    pe->size = GetFileSize(pe->file, nullptr);
    if (pe->size < sizeof(IMAGE_DOS_HEADER) || pe->size == INVALID_FILE_SIZE) {
        ClosePe(pe);
        return false;
    }
    pe->mapping = CreateFileMappingW(pe->file, nullptr, PAGE_READONLY, 0, 0, nullptr);
    if (pe->mapping == nullptr) {
        ClosePe(pe);
        return false;
    }
    pe->data = static_cast<const uint8_t*>(MapViewOfFile(pe->mapping, FILE_MAP_READ, 0, 0, 0));
    if (pe->data == nullptr) {
        ClosePe(pe);
        return false;
    }

    const IMAGE_DOS_HEADER* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(pe->data);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 ||
        pe->size < sizeof(IMAGE_NT_HEADERS32) ||
        static_cast<DWORD>(dos->e_lfanew) > pe->size - sizeof(IMAGE_NT_HEADERS32)) {
        ClosePe(pe);
        return false;
    }
    pe->nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(pe->data + dos->e_lfanew);
    if (pe->nt->Signature != IMAGE_NT_SIGNATURE) {
        ClosePe(pe);
        return false;
    }
    pe->pe32 = pe->nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    const DWORD sectionBytes =
        static_cast<DWORD>(pe->nt->FileHeader.NumberOfSections) * sizeof(IMAGE_SECTION_HEADER);
    const uint8_t* sectionStart = reinterpret_cast<const uint8_t*>(&pe->nt->OptionalHeader) +
        pe->nt->FileHeader.SizeOfOptionalHeader;
    if (sectionStart < pe->data ||
        static_cast<DWORD>(sectionStart - pe->data) > pe->size ||
        sectionBytes > pe->size - static_cast<DWORD>(sectionStart - pe->data)) {
        ClosePe(pe);
        return false;
    }
    return true;
}

const void* RvaToPointer(const PeFile* pe, DWORD rva, DWORD required) {
    if (!pe->pe32) {
        return nullptr;
    }
    if (rva < pe->nt->OptionalHeader.SizeOfHeaders) {
        if (rva <= pe->size && required <= pe->size - rva) {
            return pe->data + rva;
        }
        return nullptr;
    }

    const IMAGE_SECTION_HEADER* section = IMAGE_FIRST_SECTION(pe->nt);
    for (WORD index = 0; index < pe->nt->FileHeader.NumberOfSections; ++index) {
        const DWORD virtualSize = section[index].Misc.VirtualSize;
        const DWORD rawSize = section[index].SizeOfRawData;
        const DWORD span = virtualSize > rawSize ? virtualSize : rawSize;
        if (rva < section[index].VirtualAddress ||
            rva - section[index].VirtualAddress >= span) {
            continue;
        }
        const DWORD delta = rva - section[index].VirtualAddress;
        if (delta > rawSize || required > rawSize - delta) {
            return nullptr;
        }
        const DWORD offset = section[index].PointerToRawData + delta;
        if (offset > pe->size || required > pe->size - offset) {
            return nullptr;
        }
        return pe->data + offset;
    }
    return nullptr;
}

bool ReadImportName(const PeFile* pe, DWORD rva, char* output, int capacity) {
    const char* name = static_cast<const char*>(RvaToPointer(pe, rva, 1));
    if (name == nullptr) {
        return false;
    }
    const DWORD offset = static_cast<DWORD>(reinterpret_cast<const uint8_t*>(name) - pe->data);
    int index = 0;
    while (index + 1 < capacity && offset + static_cast<DWORD>(index) < pe->size &&
           name[index] != '\0') {
        output[index] = name[index];
        ++index;
    }
    output[index] = '\0';
    return index != 0 && offset + static_cast<DWORD>(index) < pe->size;
}

bool ImportAlreadyListed(const ImportEntry* imports, int count, const char* name, bool delayed) {
    for (int index = 0; index < count; ++index) {
        if (imports[index].delayed == delayed && EqualsIgnoreCaseA(imports[index].name, name)) {
            return true;
        }
    }
    return false;
}

int ReadImports(const PeFile* pe, ImportEntry* imports, int capacity) {
    int count = 0;
    const IMAGE_DATA_DIRECTORY& directory =
        pe->nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (directory.VirtualAddress != 0) {
        DWORD cursor = directory.VirtualAddress;
        for (int guard = 0; guard < kMaxImports; ++guard) {
            const IMAGE_IMPORT_DESCRIPTOR* descriptor =
                static_cast<const IMAGE_IMPORT_DESCRIPTOR*>(
                    RvaToPointer(pe, cursor, sizeof(IMAGE_IMPORT_DESCRIPTOR)));
            if (descriptor == nullptr ||
                (descriptor->Name == 0 && descriptor->FirstThunk == 0)) {
                break;
            }
            char name[128];
            if (ReadImportName(pe, descriptor->Name, name, sizeof(name)) &&
                !ImportAlreadyListed(imports, count, name, false) && count < capacity) {
                CopyAnsi(imports[count].name, sizeof(imports[count].name), name);
                imports[count].thunkRva = descriptor->OriginalFirstThunk != 0
                    ? descriptor->OriginalFirstThunk
                    : descriptor->FirstThunk;
                imports[count].delayed = false;
                ++count;
            }
            cursor += sizeof(IMAGE_IMPORT_DESCRIPTOR);
        }
    }

    struct DelayDescriptor {
        DWORD attributes;
        DWORD name;
        DWORD module;
        DWORD iat;
        DWORD intTable;
        DWORD boundIat;
        DWORD unloadIat;
        DWORD timestamp;
    };
    const IMAGE_DATA_DIRECTORY& delayDirectory =
        pe->nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT];
    if (delayDirectory.VirtualAddress != 0) {
        DWORD cursor = delayDirectory.VirtualAddress;
        for (int guard = 0; guard < kMaxImports; ++guard) {
            const DelayDescriptor* descriptor = static_cast<const DelayDescriptor*>(
                RvaToPointer(pe, cursor, sizeof(DelayDescriptor)));
            if (descriptor == nullptr || descriptor->name == 0) {
                break;
            }
            DWORD nameRva = descriptor->name;
            if ((descriptor->attributes & 1) == 0) {
                const DWORD imageBase = pe->nt->OptionalHeader.ImageBase;
                if (nameRva < imageBase) {
                    break;
                }
                nameRva -= imageBase;
            }
            char name[128];
            if (ReadImportName(pe, nameRva, name, sizeof(name)) &&
                !ImportAlreadyListed(imports, count, name, true) && count < capacity) {
                CopyAnsi(imports[count].name, sizeof(imports[count].name), name);
                imports[count].thunkRva = descriptor->intTable;
                if ((descriptor->attributes & 1) == 0) {
                    const DWORD imageBase = pe->nt->OptionalHeader.ImageBase;
                    if (imports[count].thunkRva >= imageBase) {
                        imports[count].thunkRva -= imageBase;
                    } else {
                        imports[count].thunkRva = 0;
                    }
                }
                imports[count].delayed = true;
                ++count;
            }
            cursor += sizeof(DelayDescriptor);
        }
    }
    return count;
}

void BuildPath(wchar_t* output, int capacity, const wchar_t* directory, const wchar_t* name) {
    CopyWide(output, capacity, directory);
    int length = lstrlenW(output);
    if (length != 0 && output[length - 1] != L'\\' && length + 1 < capacity) {
        output[length++] = L'\\';
        output[length] = L'\0';
    }
    if (length < capacity) {
        CopyWide(output + length, capacity - length, name);
    }
}

bool AnsiToWideName(const char* input, wchar_t* output, int capacity) {
    return MultiByteToWideChar(CP_ACP, 0, input, -1, output, capacity) > 0;
}

bool IsRegularFile(const wchar_t* path) {
    const DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

WORD ReadMachine(const wchar_t* path, bool* valid) {
    PeFile pe;
    if (!OpenPe(path, &pe)) {
        *valid = false;
        return 0;
    }
    const WORD machine = pe.nt->FileHeader.Machine;
    *valid = true;
    ClosePe(&pe);
    return machine;
}

bool IsVc140Name(const char* name) {
    return ContainsIgnoreCaseA(name, "vcruntime140") ||
        ContainsIgnoreCaseA(name, "msvcp140") ||
        ContainsIgnoreCaseA(name, "api-ms-win-crt") ||
        EqualsIgnoreCaseA(name, "ucrtbase.dll");
}

bool IsVc71Name(const char* name) {
    return EqualsIgnoreCaseA(name, "msvcp71.dll") ||
        EqualsIgnoreCaseA(name, "msvcr71.dll");
}

void RecordMissingCategory(Results* results, const char* name) {
    if (IsVc140Name(name)) {
        results->missingVc140 = true;
    }
    if (IsVc71Name(name)) {
        results->missingVc71 = true;
    }
    if (EqualsIgnoreCaseA(name, "d3d8.dll")) {
        results->missingDirectX = true;
    }
}

void VerifyRequiredExports(
    Writer* writer,
    const PeFile* parent,
    const ImportEntry& import,
    HMODULE module,
    Results* results) {
    if (import.thunkRva == 0 || module == nullptr) {
        return;
    }

    DWORD cursor = import.thunkRva;
    for (int guard = 0; guard < 65536; ++guard) {
        const IMAGE_THUNK_DATA32* thunk = static_cast<const IMAGE_THUNK_DATA32*>(
            RvaToPointer(parent, cursor, sizeof(IMAGE_THUNK_DATA32)));
        if (thunk == nullptr || thunk->u1.AddressOfData == 0) {
            break;
        }

        FARPROC procedure = nullptr;
        char functionName[256];
        functionName[0] = '\0';
        WORD ordinal = 0;
        if (IMAGE_SNAP_BY_ORDINAL32(thunk->u1.Ordinal)) {
            ordinal = static_cast<WORD>(IMAGE_ORDINAL32(thunk->u1.Ordinal));
            procedure = GetProcAddress(module, MAKEINTRESOURCEA(ordinal));
        } else if (ReadImportName(
                       parent,
                       thunk->u1.AddressOfData + static_cast<DWORD>(sizeof(WORD)),
                       functionName,
                       sizeof(functionName))) {
            procedure = GetProcAddress(module, functionName);
        }

        if (procedure == nullptr) {
            WriteAnsi(writer, "        [MISSING EXPORT] ");
            WriteAnsi(writer, import.name);
            WriteAnsi(writer, "!");
            if (functionName[0] != '\0') {
                WriteAnsi(writer, functionName);
            } else if (ordinal != 0) {
                WriteAnsi(writer, "#");
                WriteNumber(writer, ordinal);
            } else {
                WriteAnsi(writer, "<invalid import name>");
            }
            WriteLine(writer, "");
            ++results->missingExports;
        }
        cursor += sizeof(IMAGE_THUNK_DATA32);
    }
}

void ReportImport(
    Writer* writer,
    const wchar_t* root,
    const PeFile* parent,
    const ImportEntry& import,
    Results* results) {
    wchar_t wideName[128];
    WriteAnsi(writer, "    ");
    WriteAnsi(writer, import.delayed ? "[DELAY] " : "[IMPORT] ");
    WriteAnsi(writer, import.name);
    WriteAnsi(writer, " -> ");

    if (!AnsiToWideName(import.name, wideName, sizeof(wideName) / sizeof(wideName[0]))) {
        WriteLine(writer, "INVALID NAME");
        ++results->missingImports;
        return;
    }

    wchar_t localPath[MAX_PATH];
    BuildPath(localPath, MAX_PATH, root, wideName);
    if (IsRegularFile(localPath)) {
        bool valid = false;
        const WORD machine = ReadMachine(localPath, &valid);
        if (!valid) {
            WriteLine(writer, "LOCAL FILE IS NOT A VALID 32-BIT PE");
            ++results->wrongImportMachine;
        } else if (machine != IMAGE_FILE_MACHINE_I386) {
            WriteAnsi(writer, "LOCAL FILE HAS WRONG MACHINE ");
            WriteHex16(writer, machine);
            WriteLine(writer, "");
            ++results->wrongImportMachine;
        } else {
            WriteLine(writer, "LOCAL x86");
            HMODULE module = LoadLibraryExW(localPath, nullptr, DONT_RESOLVE_DLL_REFERENCES);
            if (module != nullptr) {
                VerifyRequiredExports(writer, parent, import, module, results);
                FreeLibrary(module);
            } else {
                WriteAnsi(writer, "        [ERROR] Local file could not be mapped (Win32 error ");
                WriteNumber(writer, GetLastError());
                WriteLine(writer, ")");
                ++results->missingImports;
                RecordMissingCategory(results, import.name);
            }
        }
        return;
    }

    SetLastError(ERROR_SUCCESS);
    HMODULE module = LoadLibraryExW(wideName, nullptr, DONT_RESOLVE_DLL_REFERENCES);
    const DWORD error = module == nullptr ? GetLastError() : ERROR_SUCCESS;
    if (module != nullptr) {
        wchar_t resolved[MAX_PATH];
        resolved[0] = L'\0';
        GetModuleFileNameW(module, resolved, MAX_PATH);
        WriteAnsi(writer, "WINDOWS x86");
        if (resolved[0] != L'\0') {
            WriteAnsi(writer, " (");
            WriteWide(writer, resolved);
            WriteAnsi(writer, ")");
        }
        WriteLine(writer, "");
        VerifyRequiredExports(writer, parent, import, module, results);
        FreeLibrary(module);
        return;
    }

    WriteAnsi(writer, "MISSING/UNLOADABLE (Win32 error ");
    WriteNumber(writer, error);
    if (error == ERROR_MOD_NOT_FOUND) {
        WriteLine(writer, ": module not found)");
    } else if (error == ERROR_BAD_EXE_FORMAT) {
        WriteLine(writer, ": wrong architecture or invalid PE)");
    } else if (error == ERROR_PROC_NOT_FOUND) {
        WriteLine(writer, ": imported function not found)");
    } else {
        WriteLine(writer, ")");
    }
    ++results->missingImports;
    RecordMissingCategory(results, import.name);
}

int CompareFiles(const LocalFile& left, const LocalFile& right) {
    return lstrcmpiW(left.name, right.name);
}

void SortFiles(LocalFile* files, int count) {
    for (int index = 1; index < count; ++index) {
        LocalFile value = files[index];
        int cursor = index;
        while (cursor > 0 && CompareFiles(value, files[cursor - 1]) < 0) {
            files[cursor] = files[cursor - 1];
            --cursor;
        }
        files[cursor] = value;
    }
}

bool HasPeExtension(const wchar_t* name) {
    const int length = lstrlenW(name);
    if (length < 4) {
        return false;
    }
    return lstrcmpiW(name + length - 4, L".dll") == 0 ||
        lstrcmpiW(name + length - 4, L".exe") == 0;
}

int EnumerateFiles(const wchar_t* root, LocalFile* files, int capacity) {
    wchar_t pattern[MAX_PATH];
    BuildPath(pattern, MAX_PATH, root, L"*");
    WIN32_FIND_DATAW data;
    HANDLE search = FindFirstFileW(pattern, &data);
    if (search == INVALID_HANDLE_VALUE) {
        return 0;
    }
    int count = 0;
    do {
        if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0 &&
            HasPeExtension(data.cFileName) && count < capacity) {
            CopyWide(files[count].name, MAX_PATH, data.cFileName);
            ++count;
        }
    } while (FindNextFileW(search, &data));
    FindClose(search);
    SortFiles(files, count);
    return count;
}

void ReportEnvironment(Writer* writer, const wchar_t* root) {
    struct RtlVersionInfo {
        ULONG size;
        ULONG major;
        ULONG minor;
        ULONG build;
        ULONG platform;
        wchar_t servicePack[128];
    };
    using RtlGetVersionFn = LONG(WINAPI*)(RtlVersionInfo*);

    SYSTEM_INFO info;
    GetNativeSystemInfo(&info);
    BOOL wow64 = FALSE;
    IsWow64Process(GetCurrentProcess(), &wow64);

    RtlVersionInfo version = {};
    version.size = sizeof(version);
    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    RtlGetVersionFn rtlGetVersion = nullptr;
    if (ntdll != nullptr) {
        union {
            FARPROC raw;
            RtlGetVersionFn typed;
        } conversion = {GetProcAddress(ntdll, "RtlGetVersion")};
        rtlGetVersion = conversion.typed;
    }

    WriteLine(writer, "BeiDou Windows Dependency Report");
    WriteLine(writer, "================================");
    WriteLine(writer, "This tool is read-only. It does not register DLLs or start the game.");
    WriteAnsi(writer, "Client directory: ");
    WriteWide(writer, root);
    WriteLine(writer, "");
    WriteLine(writer, "Checker process: x86 (32-bit)");
    WriteAnsi(writer, "Running under WOW64: ");
    WriteLine(writer, wow64 ? "yes" : "no");
    WriteAnsi(writer, "Native processor architecture: ");
    WriteNumber(writer, info.wProcessorArchitecture);
    WriteLine(writer, "");
    if (rtlGetVersion != nullptr && rtlGetVersion(&version) == 0) {
        WriteAnsi(writer, "Windows version: ");
        WriteNumber(writer, version.major);
        WriteAnsi(writer, ".");
        WriteNumber(writer, version.minor);
        WriteAnsi(writer, " build ");
        WriteNumber(writer, version.build);
        WriteLine(writer, "");
    }
    WriteLine(writer, "");
}

void ReportFile(
    Writer* writer,
    const wchar_t* root,
    const LocalFile& file,
    Results* results) {
    wchar_t path[MAX_PATH];
    BuildPath(path, MAX_PATH, root, file.name);
    WriteAnsi(writer, "[FILE] ");
    WriteWide(writer, file.name);
    WriteLine(writer, "");

    PeFile pe;
    if (!OpenPe(path, &pe)) {
        WriteLine(writer, "    [ERROR] Invalid, unreadable, or non-PE32 file");
        WriteLine(writer, "");
        ++results->invalidPe;
        return;
    }

    WriteAnsi(writer, "    Machine: ");
    WriteHex16(writer, pe.nt->FileHeader.Machine);
    if (pe.nt->FileHeader.Machine == IMAGE_FILE_MACHINE_I386 && pe.pe32) {
        WriteLine(writer, " (x86, expected)");
    } else {
        WriteLine(writer, " (WRONG: BeiDou requires x86)");
        ++results->wrongMachine;
        ClosePe(&pe);
        WriteLine(writer, "");
        return;
    }

    ImportEntry imports[kMaxImports];
    const int importCount = ReadImports(&pe, imports, kMaxImports);
    WriteAnsi(writer, "    Imported modules: ");
    WriteNumber(writer, static_cast<DWORD>(importCount));
    WriteLine(writer, "");
    for (int index = 0; index < importCount; ++index) {
        ReportImport(writer, root, &pe, imports[index], results);
    }
    WriteLine(writer, "");
    ClosePe(&pe);
}

void ReportSummary(Writer* writer, const Results& results) {
    WriteLine(writer, "Summary");
    WriteLine(writer, "=======");
    WriteAnsi(writer, "Files scanned: ");
    WriteNumber(writer, static_cast<DWORD>(results.files));
    WriteLine(writer, "");
    WriteAnsi(writer, "Invalid PE files: ");
    WriteNumber(writer, static_cast<DWORD>(results.invalidPe));
    WriteLine(writer, "");
    WriteAnsi(writer, "Wrong-architecture files: ");
    WriteNumber(writer, static_cast<DWORD>(results.wrongMachine + results.wrongImportMachine));
    WriteLine(writer, "");
    WriteAnsi(writer, "Missing/unloadable imports: ");
    WriteNumber(writer, static_cast<DWORD>(results.missingImports));
    WriteLine(writer, "");
    WriteAnsi(writer, "Missing imported functions: ");
    WriteNumber(writer, static_cast<DWORD>(results.missingExports));
    WriteLine(writer, "");
    WriteLine(writer, "");

    if (results.invalidPe == 0 && results.wrongMachine == 0 &&
        results.wrongImportMachine == 0 && results.missingImports == 0 &&
        results.missingExports == 0) {
        WriteLine(writer, "RESULT: No static dependency or x86 architecture problem was found.");
        WriteLine(writer, "If Windows still reports 'Class not registered' (0x80040154), capture");
        WriteLine(writer, "the exact dialog/error code; that is a runtime COM/object-creation issue.");
    } else {
        WriteLine(writer, "RESULT: One or more loader problems were found above.");
    }

    if (results.missingVc140) {
        WriteLine(writer, "ACTION: Install Microsoft Visual C++ 2015-2022 Redistributable (x86).");
        WriteLine(writer, "Installing only the x64 package does not satisfy this 32-bit client.");
    }
    if (results.missingVc71) {
        WriteLine(writer, "ACTION: MSVCP71/MSVCR71 is missing. Use the known-good legacy client");
        WriteLine(writer, "runtime files; do not download DLLs from an untrusted DLL website.");
    }
    if (results.missingDirectX) {
        WriteLine(writer, "ACTION: d3d8.dll is unavailable. Repair/install the legacy DirectX runtime.");
    }
    if (results.wrongMachine != 0 || results.wrongImportMachine != 0) {
        WriteLine(writer, "ACTION: Replace x64/ARM DLLs with the matching x86 client files.");
    }
    if (results.missingExports != 0) {
        WriteLine(writer, "ACTION: A dependency exists but is the wrong version; replace it with");
        WriteLine(writer, "the matching x86 runtime/client DLL shown by MISSING EXPORT.");
    }
    WriteLine(writer, "Do not run regsvr32 on every DLL. Most BeiDou DLLs are not self-registering.");
}

bool GetExecutableDirectory(wchar_t* directory, int capacity) {
    const DWORD length = GetModuleFileNameW(nullptr, directory, static_cast<DWORD>(capacity));
    if (length == 0 || length >= static_cast<DWORD>(capacity)) {
        return false;
    }
    for (int index = static_cast<int>(length) - 1; index >= 0; --index) {
        if (directory[index] == L'\\' || directory[index] == L'/') {
            directory[index] = L'\0';
            return true;
        }
    }
    return false;
}

int Run() {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX);

    wchar_t root[MAX_PATH];
    if (!GetExecutableDirectory(root, MAX_PATH)) {
        MessageBoxW(nullptr, L"Cannot determine the checker directory.",
                    L"BeiDou dependency check", MB_OK | MB_ICONERROR);
        return 1;
    }
    SetCurrentDirectoryW(root);

    wchar_t reportPath[MAX_PATH];
    BuildPath(reportPath, MAX_PATH, root, kReportName);
    Writer writer;
    writer.file = CreateFileW(
        reportPath, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL, nullptr);
    if (writer.file == INVALID_HANDLE_VALUE) {
        MessageBoxW(nullptr, L"Cannot create BeiDouDependencyReport.txt.",
                    L"BeiDou dependency check", MB_OK | MB_ICONERROR);
        return 1;
    }

    const uint8_t utf8Bom[] = {0xef, 0xbb, 0xbf};
    WriteBytes(&writer, utf8Bom, sizeof(utf8Bom));
    ReportEnvironment(&writer, root);

    LocalFile files[kMaxFiles];
    Results results = {};
    results.files = EnumerateFiles(root, files, kMaxFiles);
    for (int index = 0; index < results.files; ++index) {
        ReportFile(&writer, root, files[index], &results);
    }
    ReportSummary(&writer, results);
    FlushFileBuffers(writer.file);
    CloseHandle(writer.file);

    if (results.invalidPe == 0 && results.wrongMachine == 0 &&
        results.wrongImportMachine == 0 && results.missingImports == 0 &&
        results.missingExports == 0) {
        MessageBoxW(
            nullptr,
            L"Check complete. No static dependency problem was found.\n\n"
            L"Send BeiDouDependencyReport.txt with the exact Windows error message.",
            L"BeiDou dependency check", MB_OK | MB_ICONINFORMATION);
    } else {
        MessageBoxW(
            nullptr,
            L"Check complete. Loader problems were found.\n\n"
            L"Open or send BeiDouDependencyReport.txt for the exact missing DLLs.",
            L"BeiDou dependency check", MB_OK | MB_ICONWARNING);
    }
    return 0;
}

}  // namespace

extern "C" void EntryPoint() {
    ExitProcess(static_cast<UINT>(Run()));
}
