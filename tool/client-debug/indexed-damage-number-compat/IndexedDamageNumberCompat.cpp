#include <windows.h>

#include <stddef.h>
#include <stdint.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr uintptr_t kDamageMonsterHookAddress = 0x0066C6CB;
constexpr uintptr_t kLocalAttackLookupHookAddress = 0x00972512;
constexpr uintptr_t kSkipLocalMoveHookAddress = 0x0098046E;
constexpr uintptr_t kSkipLocalAttackByteHookAddress = 0x009803E5;

static_assert(sizeof(void*) == 4, "This hook must be built for the 32-bit client");

const unsigned char kDamageMonsterOriginal[] = {
    0x8B, 0xCF, 0xE8, 0x21, 0x9F, 0xD9, 0xFF,
    0x8B, 0xCF, 0xE8, 0x50, 0x9F, 0xD9, 0xFF,
    0x6A, 0x00, 0x6A, 0x00, 0x8B, 0xD8, 0x6A, 0x00,
    0x53, 0x8B, 0xCE, 0xE8, 0xEA, 0xCA, 0xFF, 0xFF,
};

const unsigned char kLocalAttackLookupOriginal[] = {
    0x85, 0xF6, 0x0F, 0x84, 0x0C, 0x01, 0x00, 0x00,
};

const unsigned char kSkipLocalMoveOriginal[] = {
    0x8B, 0x45, 0xE8, 0x8D, 0xB0, 0x88, 0x00, 0x00, 0x00,
};

const unsigned char kSkipLocalAttackByteOriginal[] = {
    0x88, 0x86, 0xE0, 0x2A, 0x00, 0x00,
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

bool WriteJump(void* address, void* destination, SIZE_T patchSize) {
    auto* target = static_cast<unsigned char*>(address);
    DWORD oldProtect = 0;
    if (!VirtualProtect(target, patchSize, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        LogLine("ERROR: VirtualProtect failed");
        return false;
    }
    const intptr_t displacement =
        static_cast<unsigned char*>(destination) - (target + 5);
    target[0] = 0xE9;
    *reinterpret_cast<int32_t*>(target + 1) = static_cast<int32_t>(displacement);
    for (SIZE_T index = 5; index < patchSize; ++index) {
        target[index] = 0x90;
    }
    FlushInstructionCache(GetCurrentProcess(), target, patchSize);
    DWORD ignored = 0;
    VirtualProtect(target, patchSize, oldProtect, &ignored);
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

// When CLOSE_RANGE_ATTACK lookup fails, only Sword Illusion's hidden replay
// IDs may reuse the local player pointer so later ticks reach native
// 0x0066B05E. MCV ultimates use the Cosmos-style indexed F6 path instead.
// Action writes that would restart Brandish are skipped separately and
// 0x009803AB is never called from here.
extern "C" __attribute__((naked, noinline)) void HookLocalCloseRangeLookup() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "test esi, esi\n"
        "jnz lookup_continue\n"
        "mov eax, dword ptr [edi + 8]\n"
        "add eax, dword ptr [edi + 0x14]\n"
        "cmp byte ptr [eax + 1], 0x5B\n"
        "jne lookup_skip\n"
        "cmp byte ptr [eax + 2], 0\n"
        "je lookup_skip\n"
        "mov ecx, dword ptr [eax + 3]\n"
        "cmp ecx, 0x00111AFD\n"
        "je lookup_use_local\n"
        "cmp ecx, 0x00111AFE\n"
        "je lookup_use_local\n"
        "jmp lookup_skip\n"
        "lookup_use_local:\n"
        "mov esi, dword ptr [0x00BEBF98]\n"
        "test esi, esi\n"
        "jz lookup_skip\n"
        "lookup_continue:\n"
        "push 0x0097251A\n"
        "ret\n"
        "lookup_skip:\n"
        "push 0x00972626\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookSkipLocalMoveAction() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "mov eax, dword ptr [ebp - 0x18]\n"
        "cmp eax, dword ptr [0x00BEBF98]\n"
        "je skip_local_move\n"
        "lea esi, [eax + 0x88]\n"
        "push 0x00980477\n"
        "ret\n"
        "skip_local_move:\n"
        "push 0x009804BB\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookSkipLocalAttackByte() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp esi, dword ptr [0x00BEBF98]\n"
        "je skip_attack_byte\n"
        "mov byte ptr [esi + 0x2AE0], al\n"
        "skip_attack_byte:\n"
        "push 0x009803EB\n"
        "ret\n"
        ".att_syntax prefix\n");
}

bool InstallHook() {
    auto* damageTarget = reinterpret_cast<unsigned char*>(kDamageMonsterHookAddress);
    if (!BytesEqual(damageTarget, kDamageMonsterOriginal, sizeof(kDamageMonsterOriginal))) {
        LogLine("ERROR: DAMAGE_MONSTER hook bytes do not match this BeiDou.exe");
        return false;
    }
    auto* lookupTarget = reinterpret_cast<unsigned char*>(kLocalAttackLookupHookAddress);
    if (!BytesEqual(lookupTarget, kLocalAttackLookupOriginal, sizeof(kLocalAttackLookupOriginal))) {
        LogLine("ERROR: CLOSE_RANGE_ATTACK lookup bytes do not match this BeiDou.exe");
        return false;
    }
    auto* moveTarget = reinterpret_cast<unsigned char*>(kSkipLocalMoveHookAddress);
    if (!BytesEqual(moveTarget, kSkipLocalMoveOriginal, sizeof(kSkipLocalMoveOriginal))) {
        LogLine("ERROR: remote-attack move bytes do not match this BeiDou.exe");
        return false;
    }
    auto* attackByteTarget = reinterpret_cast<unsigned char*>(kSkipLocalAttackByteHookAddress);
    if (!BytesEqual(attackByteTarget, kSkipLocalAttackByteOriginal, sizeof(kSkipLocalAttackByteOriginal))) {
        LogLine("ERROR: remote-attack state-byte bytes do not match this BeiDou.exe");
        return false;
    }
    if (!WriteJump(damageTarget, reinterpret_cast<void*>(&HookDamageMonsterNumber),
                   sizeof(kDamageMonsterOriginal))) {
        return false;
    }
    if (!WriteJump(lookupTarget, reinterpret_cast<void*>(&HookLocalCloseRangeLookup),
                   sizeof(kLocalAttackLookupOriginal))) {
        return false;
    }
    if (!WriteJump(moveTarget, reinterpret_cast<void*>(&HookSkipLocalMoveAction),
                   sizeof(kSkipLocalMoveOriginal))) {
        return false;
    }
    if (!WriteJump(attackByteTarget, reinterpret_cast<void*>(&HookSkipLocalAttackByte),
                   sizeof(kSkipLocalAttackByteOriginal))) {
        return false;
    }
    return true;
}

DWORD WINAPI InstallThread(LPVOID) {
    LogLine("LOAD: Indexed Damage Number Compat v3");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("ERROR: unexpected BeiDou.exe image base; no hook installed");
        return 1;
    }
    if (!InstallHook()) {
        return 2;
    }
    LogLine("OK: indexed DAMAGE_MONSTER numbers and local 0xBA replay numbers enabled");
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
