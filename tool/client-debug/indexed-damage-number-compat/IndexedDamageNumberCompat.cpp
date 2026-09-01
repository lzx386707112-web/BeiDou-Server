#include <windows.h>

#include <stddef.h>
#include <stdint.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr uintptr_t kDamageMonsterHookAddress = 0x0066C6CB;

static_assert(sizeof(void*) == 4, "This hook must be built for the 32-bit client");

const unsigned char kDamageMonsterOriginal[] = {
    0x8B, 0xCF, 0xE8, 0x21, 0x9F, 0xD9, 0xFF,
    0x8B, 0xCF, 0xE8, 0x50, 0x9F, 0xD9, 0xFF,
    0x6A, 0x00, 0x6A, 0x00, 0x8B, 0xD8, 0x6A, 0x00,
    0x53, 0x8B, 0xCE, 0xE8, 0xEA, 0xCA, 0xFF, 0xFF,
};

void LogLine(const char* line) {
    HANDLE file = CreateFileA(
        "IndexedDamageNumberCompat.log",
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(lstrlenA(line)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

bool BytesEqual(const void* address, const unsigned char* expected, SIZE_T size) {
    const auto* current = static_cast<const unsigned char*>(address);
    for (SIZE_T index = 0; index < size; ++index) {
        if (current[index] != expected[index]) {
            return false;
        }
    }
    return true;
}

extern "C" __attribute__((naked, noinline)) void HookDamageMonsterNumber() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "mov ecx, edi\n"
        "mov eax, 0x004065F3\n"
        "call eax\n"
        "movzx edx, al\n"
        "cmp edx, 0x80\n"
        "jb damage_number_unmarked\n"
        "cmp edx, 0x8E\n"
        "ja damage_number_unmarked\n"
        "and edx, 0x0F\n"
        "jmp damage_number_decoded\n"
        "damage_number_unmarked:\n"
        "xor edx, edx\n"
        "damage_number_decoded:\n"
        "push edx\n"
        "mov ecx, edi\n"
        "mov eax, 0x00406629\n"
        "call eax\n"
        "mov ebx, eax\n"
        "pop edx\n"
        "push 0\n"
        "push 0\n"
        "push edx\n"
        "push ebx\n"
        "mov ecx, esi\n"
        "mov eax, 0x006691D3\n"
        "call eax\n"
        "push 0x0066C6E9\n"
        "ret\n"
        ".att_syntax prefix\n");
}

bool InstallHook() {
    auto* target = reinterpret_cast<unsigned char*>(kDamageMonsterHookAddress);
    if (!BytesEqual(target, kDamageMonsterOriginal, sizeof(kDamageMonsterOriginal))) {
        LogLine("ERROR: DAMAGE_MONSTER hook bytes do not match this BeiDou.exe");
        return false;
    }

    DWORD oldProtect = 0;
    if (!VirtualProtect(
            target,
            sizeof(kDamageMonsterOriginal),
            PAGE_EXECUTE_READWRITE,
            &oldProtect)) {
        LogLine("ERROR: VirtualProtect failed");
        return false;
    }

    const intptr_t displacement =
        reinterpret_cast<unsigned char*>(&HookDamageMonsterNumber) - (target + 5);
    target[0] = 0xE9;
    *reinterpret_cast<int32_t*>(target + 1) = static_cast<int32_t>(displacement);
    for (SIZE_T index = 5; index < sizeof(kDamageMonsterOriginal); ++index) {
        target[index] = 0x90;
    }
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(kDamageMonsterOriginal));
    DWORD ignored = 0;
    VirtualProtect(target, sizeof(kDamageMonsterOriginal), oldProtect, &ignored);
    return true;
}

DWORD WINAPI InstallThread(LPVOID) {
    LogLine("LOAD: Indexed Damage Number Compat v1");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("ERROR: unexpected BeiDou.exe image base; no hook installed");
        return 1;
    }
    if (!InstallHook()) {
        return 2;
    }
    LogLine("OK: indexed DAMAGE_MONSTER numbers enabled for markers 0x80..0x8E");
    return 0;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        DeleteFileA("IndexedDamageNumberCompat.log");
        HANDLE thread = CreateThread(nullptr, 0, InstallThread, nullptr, 0, nullptr);
        if (thread == nullptr) {
            return FALSE;
        }
        CloseHandle(thread);
    }
    return TRUE;
}
