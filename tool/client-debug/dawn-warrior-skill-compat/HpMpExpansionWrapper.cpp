// Loads the verified compatibility core, then widens HP/MP for BeiDou.exe.

#include <windows.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr int kMaxHpMp = 50000;
constexpr uintptr_t kDecode2Address = 0x0042470C;
constexpr uintptr_t kDecode4Address = 0x00406629;
constexpr uintptr_t kTearShortAddress = 0x004E80EB;
constexpr uintptr_t kTearLongAddress = 0x004165B1;
constexpr uintptr_t kFuseShortAddress = 0x004746DD;
constexpr uintptr_t kFuseLongAddress = 0x00416563;
constexpr char kCoreDllName[] = "BeiDouSkillCompatCore.dll";
constexpr char kWeatherDllName[] = "BeiDouWeatherCompat.dll";

using HpMpFuseFn = int(__cdecl*)(const int*, int);

struct HookSite {
    uintptr_t address;
    const unsigned char* original;
    SIZE_T originalSize;
    void* replacement;
    unsigned char opcode;
};

struct HpMpMovsxSite {
    uintptr_t address;
    unsigned char modrm;
};

constexpr uintptr_t kHpMpDecodeSites[] = {
    0x004E2B9A, 0x004E2BAE, 0x004E2BC2, 0x004E2BD6, 0x0077621A,
    0x004E30DA, 0x004E30F4, 0x004E310E, 0x004E3128,
    0x00A3ECF5, 0x00A3ED02, 0x00980656, 0x00980663,
};

constexpr uintptr_t kHpMpTearShortSites[] = {
    0x004E2BA4, 0x004E2BB8, 0x004E2BCC, 0x004E2BE0, 0x00776224,
    0x004E30E4, 0x004E30FE, 0x004E3118, 0x004E3132,
    0x007646F2, 0x0076470F, 0x00967B94, 0x00967BA2, 0x0078D914,
    0x0078D961,
};

constexpr uintptr_t kHpMpTearLongSites[] = {
    0x0077ED9D, 0x0077EF78, 0x0077F0EF, 0x0077F164, 0x0077F1AF,
    0x0077EDB9, 0x0077EFA7, 0x0077F11E, 0x0077F18E, 0x0077F1CE,
};

constexpr HpMpMovsxSite kHpMpMovsxSites[] = {
    {0x00A3ECFA, 0xC0}, {0x00A3ED09, 0xC8}, {0x0098065B, 0xC0},
    {0x00980668, 0xC0}, {0x008D822D, 0x4D}, {0x008D8237, 0xC0},
    {0x008C5DC4, 0x4D}, {0x008C5EB9, 0x4D}, {0x009203F7, 0x45},
    {0x008C4139, 0xD8}, {0x008C4141, 0xC0}, {0x008C418E, 0xC0},
    {0x008C419F, 0xC0}, {0x008CBF94, 0xC0}, {0x008CC015, 0xC0},
    {0x008CC1CF, 0xC0}, {0x008CC24F, 0xC0}, {0x008CC9DC, 0xC0},
    {0x008CCA8A, 0xC0}, {0x008CD9CE, 0xC0}, {0x008CDAE5, 0xC0},
    {0x008CDF25, 0xC0}, {0x008CDFC0, 0xC0}, {0x00A02F88, 0xC0},
    {0x00A03180, 0xC0}, {0x00A2938D, 0x4D}, {0x00A29412, 0xCF},
    {0x00A29535, 0x4D}, {0x00A29586, 0xCF}, {0x00A23C4A, 0xC0},
    {0x0094B096, 0xC0}, {0x0094B230, 0xC0}, {0x0094EA4C, 0xC0},
    {0x0094BB78, 0xCE}, {0x0095BA30, 0x45}, {0x0095BC7B, 0xC3},
    {0x009584B6, 0xC0}, {0x0095960C, 0xC9}, {0x00967733, 0xC0},
    {0x0096774F, 0xC0}, {0x0077ED97, 0xC8}, {0x0077EDB3, 0xC8},
    {0x0078D8FA, 0xC0}, {0x0078D947, 0xC0}, {0x00764401, 0xC8},
    {0x007644E4, 0xC0}, {0x00764507, 0xC0}, {0x00554AFC, 0xC0},
    {0x00554B31, 0xC0}, {0x007A5B42, 0xC0}, {0x004E3371, 0x4D},
    {0x004E3376, 0x4D}, {0x004E337B, 0x4D}, {0x004E3380, 0x4D},
    {0x0096AE9D, 0xC7}, {0x0064286B, 0xF0}, {0x007656FE, 0xC0},
};

constexpr uintptr_t kHpMpCompare16Sites[] = {0x0078D8E7, 0x0078D934};
constexpr uintptr_t kHpMpTest16Sites[] = {0x00485C1C, 0x00A09687};
constexpr uintptr_t kHpMpLimitSites[] = {0x0078D8D2, 0x0077F1A0, 0x008CD657, 0x008CD6EB};

const unsigned char kFuseShortOriginal[] = {0x55, 0x8B, 0xEC, 0x51, 0x51};
const unsigned char kFuseLongOriginal[] = {0x55, 0x8B, 0xEC, 0x8B, 0x45, 0x08};
const unsigned char kCompare16Original[] = {0x66, 0x3B, 0xC6};
const unsigned char kTest16Original[] = {0x66, 0x85, 0xC0};

HpMpFuseFn gHpMpFuseShortOriginal = nullptr;
HpMpFuseFn gHpMpFuseLongOriginal = nullptr;
HINSTANCE gInstance = nullptr;

static_assert(sizeof(void*) == 4, "This hook must be built for the 32-bit client");

template <typename T, SIZE_T N>
constexpr SIZE_T ArraySize(const T (&)[N]) {
    return N;
}

template <typename Function>
Function FunctionFromPointer(void* pointer) {
    static_assert(sizeof(Function) == sizeof(pointer), "unexpected Win32 function pointer size");
    Function function = nullptr;
    memcpy(&function, &pointer, sizeof(function));
    return function;
}

void LogLine(const char* text) {
    HANDLE file = CreateFileA(
        "HpMpExpansion.log",
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(file, text, static_cast<DWORD>(lstrlenA(text)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

bool BytesEqual(const void* address, const unsigned char* expected, SIZE_T size) {
    const auto* current = static_cast<const unsigned char*>(address);
    for (SIZE_T index = 0; index < size; ++index) {
        if (current[index] != expected[index]) return false;
    }
    return true;
}

bool WriteBytes(uintptr_t address, const unsigned char* replacement, SIZE_T size) {
    DWORD oldProtect = 0;
    auto* target = reinterpret_cast<unsigned char*>(address);
    if (!VirtualProtect(target, size, PAGE_EXECUTE_READWRITE, &oldProtect)) return false;
    memcpy(target, replacement, size);
    FlushInstructionCache(GetCurrentProcess(), target, size);
    DWORD ignored = 0;
    VirtualProtect(target, size, oldProtect, &ignored);
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
    for (SIZE_T index = 5; index < hook.originalSize; ++index) target[index] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), target, hook.originalSize);
    DWORD ignored = 0;
    VirtualProtect(target, hook.originalSize, oldProtect, &ignored);
    return true;
}

uintptr_t RelativeCallTarget(uintptr_t address) {
    const auto* instruction = reinterpret_cast<const unsigned char*>(address);
    if (instruction[0] != 0xE8) return 0;
    int32_t displacement = 0;
    memcpy(&displacement, instruction + 1, sizeof(displacement));
    return address + 5 + displacement;
}

bool PatchRelativeCall(uintptr_t address, void* replacement) {
    const HookSite patch = {address, nullptr, 5, replacement, 0xE8};
    return WriteRelativeBranch(patch);
}

extern "C" int __attribute__((fastcall, noinline)) HpMpFakeTear(int value, int* storage) {
    *storage = value;
    return 0;
}

extern "C" int __cdecl HpMpFuseShort(const int* storage, int checksum) {
    return checksum == 0 ? *storage : gHpMpFuseShortOriginal(storage, checksum);
}

extern "C" int __cdecl HpMpFuseLong(const int* storage, int checksum) {
    return checksum == 0 ? *storage : gHpMpFuseLongOriginal(storage, checksum);
}

bool CreateTrampoline(
    uintptr_t address,
    const unsigned char* original,
    SIZE_T originalSize,
    HpMpFuseFn* output) {
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, originalSize + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) return false;
    memcpy(trampoline, original, originalSize);
    trampoline[originalSize] = 0xE9;
    const intptr_t displacement =
        reinterpret_cast<unsigned char*>(address + originalSize) - (trampoline + originalSize + 5);
    *reinterpret_cast<int32_t*>(trampoline + originalSize + 1) = static_cast<int32_t>(displacement);
    FlushInstructionCache(GetCurrentProcess(), trampoline, originalSize + 5);
    *output = FunctionFromPointer<HpMpFuseFn>(trampoline);
    return true;
}

bool ValidateHpMpPatchSites() {
    static_assert(ArraySize(kHpMpDecodeSites) == 13, "unexpected HP/MP decode patch count");
    static_assert(ArraySize(kHpMpTearShortSites) + ArraySize(kHpMpTearLongSites) == 25,
                  "unexpected HP/MP tear patch count");
    static_assert(ArraySize(kHpMpMovsxSites) == 57, "unexpected HP/MP movsx patch count");

    if (!BytesEqual(reinterpret_cast<const void*>(kFuseShortAddress),
                    kFuseShortOriginal, sizeof(kFuseShortOriginal)) ||
        !BytesEqual(reinterpret_cast<const void*>(kFuseLongAddress),
                    kFuseLongOriginal, sizeof(kFuseLongOriginal))) {
        LogLine("HPMP ERROR: Fuse entry bytes do not match this BeiDou.exe");
        return false;
    }
    for (uintptr_t address : kHpMpDecodeSites) {
        if (RelativeCallTarget(address) != kDecode2Address) {
            LogLine("HPMP ERROR: Decode2 call bytes do not match this BeiDou.exe");
            return false;
        }
    }
    for (uintptr_t address : kHpMpTearShortSites) {
        if (RelativeCallTarget(address) != kTearShortAddress) {
            LogLine("HPMP ERROR: Tear_short call bytes do not match this BeiDou.exe");
            return false;
        }
    }
    for (uintptr_t address : kHpMpTearLongSites) {
        if (RelativeCallTarget(address) != kTearLongAddress) {
            LogLine("HPMP ERROR: Tear_long call bytes do not match this BeiDou.exe");
            return false;
        }
    }
    for (const HpMpMovsxSite& site : kHpMpMovsxSites) {
        const unsigned char expected[] = {0x0F, 0xBF, site.modrm};
        if (!BytesEqual(reinterpret_cast<const void*>(site.address), expected, sizeof(expected))) {
            LogLine("HPMP ERROR: movsx bytes do not match this BeiDou.exe");
            return false;
        }
    }
    for (uintptr_t address : kHpMpCompare16Sites) {
        if (!BytesEqual(reinterpret_cast<const void*>(address),
                        kCompare16Original, sizeof(kCompare16Original))) {
            LogLine("HPMP ERROR: 16-bit comparison bytes do not match this BeiDou.exe");
            return false;
        }
    }
    for (uintptr_t address : kHpMpTest16Sites) {
        if (!BytesEqual(reinterpret_cast<const void*>(address),
                        kTest16Original, sizeof(kTest16Original))) {
            LogLine("HPMP ERROR: 16-bit life-check bytes do not match this BeiDou.exe");
            return false;
        }
    }
    for (uintptr_t address : kHpMpLimitSites) {
        int currentLimit = 0;
        memcpy(&currentLimit, reinterpret_cast<const void*>(address), sizeof(currentLimit));
        if (currentLimit != 30000) {
            LogLine("HPMP ERROR: cap constant does not match this BeiDou.exe");
            return false;
        }
    }
    return true;
}

bool InstallHpMpHooks() {
    if (!CreateTrampoline(kFuseShortAddress, kFuseShortOriginal, sizeof(kFuseShortOriginal),
                          &gHpMpFuseShortOriginal) ||
        !CreateTrampoline(kFuseLongAddress, kFuseLongOriginal, sizeof(kFuseLongOriginal),
                          &gHpMpFuseLongOriginal)) {
        LogLine("HPMP ERROR: failed to create Fuse trampolines");
        return false;
    }

    const HookSite fuseShortHook = {
        kFuseShortAddress, kFuseShortOriginal, sizeof(kFuseShortOriginal),
        reinterpret_cast<void*>(&HpMpFuseShort), 0xE9};
    const HookSite fuseLongHook = {
        kFuseLongAddress, kFuseLongOriginal, sizeof(kFuseLongOriginal),
        reinterpret_cast<void*>(&HpMpFuseLong), 0xE9};
    if (!WriteRelativeBranch(fuseShortHook) || !WriteRelativeBranch(fuseLongHook)) {
        LogLine("HPMP ERROR: failed to install Fuse hooks");
        return false;
    }
    for (uintptr_t address : kHpMpDecodeSites) {
        if (!PatchRelativeCall(address, reinterpret_cast<void*>(kDecode4Address))) return false;
    }
    for (uintptr_t address : kHpMpTearShortSites) {
        if (!PatchRelativeCall(address, reinterpret_cast<void*>(&HpMpFakeTear))) return false;
    }
    for (uintptr_t address : kHpMpTearLongSites) {
        if (!PatchRelativeCall(address, reinterpret_cast<void*>(&HpMpFakeTear))) return false;
    }
    for (const HpMpMovsxSite& site : kHpMpMovsxSites) {
        unsigned char replacement[3] = {0x8B, site.modrm, 0x90};
        if ((site.modrm & 0xC0) != 0xC0) {
            replacement[0] = 0x90;
            replacement[1] = 0x8B;
            replacement[2] = site.modrm;
        }
        if (!WriteBytes(site.address, replacement, sizeof(replacement))) return false;
    }
    const unsigned char compare32[] = {0x3B, 0xC6, 0x90};
    for (uintptr_t address : kHpMpCompare16Sites) {
        if (!WriteBytes(address, compare32, sizeof(compare32))) return false;
    }
    const unsigned char test32[] = {0x85, 0xC0, 0x90};
    for (uintptr_t address : kHpMpTest16Sites) {
        if (!WriteBytes(address, test32, sizeof(test32))) return false;
    }
    for (uintptr_t address : kHpMpLimitSites) {
        if (!WriteBytes(address, reinterpret_cast<const unsigned char*>(&kMaxHpMp),
                        sizeof(kMaxHpMp))) return false;
    }
    LogLine("HPMP OK: 32-bit HP/MP enabled with a 50000 cap");
    return true;
}

bool LoadSiblingDll(const char* dllName) {
    char path[MAX_PATH] = {};
    const DWORD length = GetModuleFileNameA(gInstance, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) return false;
    char* fileName = path;
    for (char* cursor = path; *cursor != '\0'; ++cursor) {
        if (*cursor == '\\' || *cursor == '/') fileName = cursor + 1;
    }
    const SIZE_T prefixLength = static_cast<SIZE_T>(fileName - path);
    if (prefixLength + lstrlenA(dllName) + 1 > MAX_PATH) return false;
    lstrcpyA(fileName, dllName);
    return LoadLibraryA(path) != nullptr;
}

DWORD WINAPI InstallHooks(LPVOID) {
    LogLine("LOAD: HP/MP expansion wrapper v70");
    if (!LoadSiblingDll(kCoreDllName)) {
        LogLine("HPMP ERROR: verified compatibility core failed to load");
        return 1;
    }
    LogLine("HPMP WRAPPER: verified compatibility core loaded");
    if (!LoadSiblingDll(kWeatherDllName)) {
        LogLine("WEATHER ERROR: BeiDouWeatherCompat.dll failed to load");
    } else {
        LogLine("WEATHER WRAPPER: visual weather compatibility loaded");
    }
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("HPMP ERROR: unexpected BeiDou.exe image base");
        return 2;
    }
    if (!ValidateHpMpPatchSites()) return 3;
    if (!InstallHpMpHooks()) {
        LogLine("HPMP ERROR: compatibility installation failed");
        return 4;
    }
    return 0;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        gInstance = instance;
        DisableThreadLibraryCalls(instance);
        DeleteFileA("HpMpExpansion.log");
        HANDLE thread = CreateThread(nullptr, 0, InstallHooks, nullptr, 0, nullptr);
        if (thread != nullptr) CloseHandle(thread);
    }
    return TRUE;
}
