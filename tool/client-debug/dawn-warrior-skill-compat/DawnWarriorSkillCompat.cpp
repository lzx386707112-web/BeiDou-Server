// Runtime compatibility hooks for BeiDou.exe Dawn Warrior 1112 custom skills.
// The DLL is loaded by the tiny EXE startup loader; ijl15.dll is untouched.

#include <windows.h>
#include <stdint.h>

namespace {

constexpr uintptr_t kExpectedImageBase = 0x00400000;
constexpr int kFirstSkill = 11121000;
constexpr int kLastSkill = 11121009;

struct HookSite {
    const char* name;
    uintptr_t address;
    const unsigned char* original;
    SIZE_T originalSize;
    void* replacement;
};

void LogLine(const char* text) {
    HANDLE file = CreateFileA(
        "DawnWarriorSkillCompat.log",
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
    WriteFile(file, text, static_cast<DWORD>(lstrlenA(text)), &written, nullptr);
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

bool WriteRelativeJump(const HookSite& hook) {
    DWORD oldProtect = 0;
    auto* target = reinterpret_cast<unsigned char*>(hook.address);
    if (!VirtualProtect(target, hook.originalSize, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        return false;
    }
    const intptr_t displacement =
        reinterpret_cast<unsigned char*>(hook.replacement) - (target + 5);
    target[0] = 0xE9;
    *reinterpret_cast<int32_t*>(target + 1) = static_cast<int32_t>(displacement);
    for (SIZE_T index = 5; index < hook.originalSize; ++index) {
        target[index] = 0x90;
    }
    FlushInstructionCache(GetCurrentProcess(), target, hook.originalSize);
    DWORD ignored = 0;
    VirtualProtect(target, hook.originalSize, oldProtect, &ignored);
    return true;
}

// Each naked stub preserves the register contract of the overwritten client
// instructions and returns to fixed, non-ASLR BeiDou.exe addresses.
extern "C" __attribute__((naked, noinline)) void HookSkillWindowJob() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "mov ecx, dword ptr [ebp-0x18]\n"
        "cmp eax, 1112\n"
        "jne 1f\n"
        "cmp dword ptr [ecx+0x18], 5\n"
        "je 2f\n"
        "push 0x004F0774\n"
        "ret\n"
        "1:\n"
        "cmp eax, 232\n"
        "jne 3f\n"
        "2:\n"
        "push 0x004F0758\n"
        "ret\n"
        "3:\n"
        "push 0x004F0774\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookSkillWindowAdd() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp eax, 1112\n"
        "je 1f\n"
        "cmp eax, 232\n"
        "je 1f\n"
        "cmp eax, 233\n"
        "je 1f\n"
        "push 0x00A0A49B\n"
        "ret\n"
        "1:\n"
        "push 0x00A0A3E1\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishSkillBranch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp esi, 11121000\n"
        "jb 1f\n"
        "cmp esi, 11121009\n"
        "jbe 2f\n"
        "1:\n"
        "cmp esi, 1121008\n"
        "je 2f\n"
        "push 0x00933ACB\n"
        "ret\n"
        "2:\n"
        "push 0x0093465F\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishActionType() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp eax, 11121000\n"
        "jb 1f\n"
        "cmp eax, 11121009\n"
        "jbe 2f\n"
        "1:\n"
        "cmp eax, 1121008\n"
        "je 2f\n"
        "push 0x00950DF0\n"
        "ret\n"
        "2:\n"
        "push 0x00950F74\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishVisualOffset() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp eax, 11121000\n"
        "jb 1f\n"
        "cmp eax, 11121009\n"
        "jbe 2f\n"
        "1:\n"
        "cmp eax, 1121008\n"
        "je 2f\n"
        "push 0x00952565\n"
        "ret\n"
        "2:\n"
        "push 0x0095262C\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishStateSwitch() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp esi, 11121000\n"
        "jb 1f\n"
        "cmp esi, 11121009\n"
        "jbe 3f\n"
        "1:\n"
        "mov eax, 1121008\n"
        "cmp esi, eax\n"
        "jg 2f\n"
        "je 3f\n"
        "push 0x00967A20\n"
        "ret\n"
        "2:\n"
        "push 0x00967A74\n"
        "ret\n"
        "3:\n"
        "push 0x009690AE\n"
        "ret\n"
        ".att_syntax prefix\n");
}

extern "C" __attribute__((naked, noinline)) void HookBrandishHit() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "cmp ebx, 11121000\n"
        "jb 1f\n"
        "cmp ebx, 11121009\n"
        "jbe 2f\n"
        "1:\n"
        "cmp ebx, 1121008\n"
        "je 2f\n"
        "cmp ebx, 0x00A98A5C\n"
        "jne 3f\n"
        "2:\n"
        "push 0x0078E9E6\n"
        "ret\n"
        "3:\n"
        "push 0x0078E9F3\n"
        "ret\n"
        ".att_syntax prefix\n");
}

const unsigned char kSkillWindowJobOriginal[] = {0x3D, 0xE8, 0x00, 0x00, 0x00, 0x75, 0x1C};
const unsigned char kSkillWindowAddOriginal[] = {0x3D, 0xE8, 0x00, 0x00, 0x00, 0x0F, 0x85, 0xBA, 0x00, 0x00, 0x00};
const unsigned char kSkillBranchOriginal[] = {0x81, 0xFE, 0xF0, 0x1A, 0x11, 0x00, 0x0F, 0x84, 0x94, 0x0B, 0x00, 0x00};
const unsigned char kActionTypeOriginal[] = {0x3D, 0xF0, 0x1A, 0x11, 0x00, 0x0F, 0x84, 0x84, 0x01, 0x00, 0x00};
const unsigned char kVisualOffsetOriginal[] = {0x3D, 0xF0, 0x1A, 0x11, 0x00, 0x0F, 0x84, 0xC7, 0x00, 0x00, 0x00};
const unsigned char kStateSwitchOriginal[] = {0xB8, 0xF0, 0x1A, 0x11, 0x00, 0x3B, 0xF0, 0x7F, 0x5B, 0x0F, 0x84, 0x8F, 0x16, 0x00, 0x00};
const unsigned char kHitOriginal[] = {0x81, 0xFB, 0xF0, 0x1A, 0x11, 0x00, 0x74, 0x08, 0x81, 0xFB, 0x5C, 0x8A, 0xA9, 0x00, 0x75, 0x0D};

HookSite kHooks[] = {
    {"skill-window job", 0x004F0751, kSkillWindowJobOriginal, sizeof(kSkillWindowJobOriginal), reinterpret_cast<void*>(&HookSkillWindowJob)},
    {"skill-window add", 0x00A0A3D6, kSkillWindowAddOriginal, sizeof(kSkillWindowAddOriginal), reinterpret_cast<void*>(&HookSkillWindowAdd)},
    {"Brandish skill branch", 0x00933ABF, kSkillBranchOriginal, sizeof(kSkillBranchOriginal), reinterpret_cast<void*>(&HookBrandishSkillBranch)},
    {"Brandish action type", 0x00950DE5, kActionTypeOriginal, sizeof(kActionTypeOriginal), reinterpret_cast<void*>(&HookBrandishActionType)},
    {"Brandish visual offset", 0x0095255A, kVisualOffsetOriginal, sizeof(kVisualOffsetOriginal), reinterpret_cast<void*>(&HookBrandishVisualOffset)},
    {"Brandish state switch", 0x00967A10, kStateSwitchOriginal, sizeof(kStateSwitchOriginal), reinterpret_cast<void*>(&HookBrandishStateSwitch)},
    {"Brandish hit", 0x0078E9D6, kHitOriginal, sizeof(kHitOriginal), reinterpret_cast<void*>(&HookBrandishHit)},
};

DWORD WINAPI InstallHooks(LPVOID) {
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kExpectedImageBase) {
        LogLine("ERROR: unexpected BeiDou.exe image base; no hooks installed");
        return 1;
    }
    for (const HookSite& hook : kHooks) {
        if (!BytesEqual(reinterpret_cast<const void*>(hook.address), hook.original, hook.originalSize)) {
            LogLine("ERROR: hook bytes do not match this BeiDou.exe; no hooks installed");
            return 2;
        }
    }
    for (const HookSite& hook : kHooks) {
        if (!WriteRelativeJump(hook)) {
            LogLine("ERROR: VirtualProtect/write failed while installing hooks");
            return 3;
        }
    }
    LogLine("OK: Dawn Warrior 11121000-11121009 compatibility hooks installed");
    return 0;
}

}  // namespace

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(nullptr, 0, InstallHooks, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
