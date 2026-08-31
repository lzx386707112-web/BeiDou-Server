#include <windows.h>
#include <oleauto.h>
#include <stdint.h>

namespace {

constexpr uintptr_t kImageBase = 0x00400000;
constexpr uintptr_t kResourceManagerAddress = 0x00BF14E8;
constexpr uintptr_t kAnimationDisplayerAddress = 0x00BEBF6C;
constexpr uintptr_t kEffectHitAddress = 0x00437D0F;
constexpr uintptr_t kEffectHitContinueAddress = 0x00437D14;
constexpr uintptr_t kEffectHitOriginalEax = 0x00A79ACF;
constexpr int kGroupCount = 4;
constexpr int kCacheOffsets[kGroupCount] = {0x170, 0x174, 0x188, 0x18C};
const wchar_t* const kGroupNames[kGroupCount] = {
    L"NoRed0",
    L"NoRed1",
    L"NoCri0",
    L"NoCri1",
};
const unsigned char kEffectHitOriginal[] = {0xB8, 0xCF, 0x9A, 0xA7, 0x00};
constexpr GUID kWzPropertyGuid = {
    0x986515D9,
    0x0A0B,
    0x4929,
    {0x8B, 0x4F, 0x71, 0x86, 0x82, 0x17, 0x7B, 0x92},
};

volatile LONG gRequestedSkin = 0;
int gAppliedSkin = 0;
int gFailedSkin = -1;
void* gDefaultGroups[kGroupCount] = {};
bool gDefaultsCaptured = false;

size_t TextLength(const char* text) {
    size_t length = 0;
    while (text != nullptr && text[length] != 0) {
        ++length;
    }
    return length;
}

bool BytesEqual(const void* left, const void* right, size_t size) {
    const auto* a = static_cast<const unsigned char*>(left);
    const auto* b = static_cast<const unsigned char*>(right);
    for (size_t index = 0; index < size; ++index) {
        if (a[index] != b[index]) {
            return false;
        }
    }
    return true;
}

void Log(const char* line) {
    HANDLE file = CreateFileA(
        "BeiDouDamageSkinCompat.log",
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
    WriteFile(file, line, static_cast<DWORD>(TextLength(line)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

void* ComMethod(void* object, int index) {
    return object != nullptr ? (*reinterpret_cast<void***>(object))[index] : nullptr;
}

void ComAddRef(void* object) {
    if (object != nullptr) {
        reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(object, 1))(object);
    }
}

void ComRelease(void* object) {
    if (object != nullptr) {
        reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(object, 2))(object);
    }
}

VARIANT MissingVariant() {
    VARIANT value = {};
    value.vt = VT_ERROR;
    value.scode = DISP_E_PARAMNOTFOUND;
    return value;
}

void* DetachVariantObject(VARIANT& value) {
    void* object = nullptr;
    if (value.vt == VT_DISPATCH) {
        object = value.pdispVal;
    } else if (value.vt == VT_UNKNOWN) {
        object = value.punkVal;
    }
    if (object != nullptr) {
        value.vt = VT_EMPTY;
        value.punkVal = nullptr;
    }
    VariantClear(&value);
    return object;
}

void* QueryWzProperty(void* object) {
    if (object == nullptr) {
        return nullptr;
    }
    void* property = nullptr;
    using QueryInterfaceFn = HRESULT(__stdcall*)(void*, const GUID&, void**);
    const HRESULT status = reinterpret_cast<QueryInterfaceFn>(ComMethod(object, 0))(
        object, kWzPropertyGuid, &property);
    ComRelease(object);
    if (FAILED(status)) {
        char line[96] = {};
        wsprintfA(line, "ERROR: IWzProperty QueryInterface failed hr=%08X", static_cast<unsigned int>(status));
        Log(line);
        return nullptr;
    }
    return property;
}

void* LoadEffectImage(int skinId) {
    void* resourceManager = *reinterpret_cast<void**>(kResourceManagerAddress);
    if (resourceManager == nullptr) {
        Log("ERROR: WZ resource manager is not initialized");
        return nullptr;
    }
    wchar_t resourcePath[64] = {};
    wsprintfW(resourcePath, L"Effect/DamageSkin/%d.img", skinId);
    BSTR path = SysAllocString(resourcePath);
    if (path == nullptr) {
        Log("ERROR: cannot allocate damage-skin WZ path");
        return nullptr;
    }
    VARIANT result = {};
    const VARIANT missing = MissingVariant();
    using GetObjectFn = HRESULT(__stdcall*)(void*, BSTR, VARIANT, VARIANT, VARIANT*);
    const HRESULT status = reinterpret_cast<GetObjectFn>(ComMethod(resourceManager, 7))(
        resourceManager, path, missing, missing, &result);
    SysFreeString(path);
    if (FAILED(status)) {
        char line[96] = {};
        wsprintfA(
            line,
            "ERROR: Effect/DamageSkin/%d.img load failed hr=%08X",
            skinId,
            static_cast<unsigned int>(status));
        Log(line);
        VariantClear(&result);
        return nullptr;
    }
    void* image = QueryWzProperty(DetachVariantObject(result));
    if (image == nullptr) {
        Log("ERROR: damage-skin IMG did not return a WZ object");
    }
    return image;
}

void* GetChild(void* property, const wchar_t* name) {
    if (property == nullptr || name == nullptr) {
        return nullptr;
    }
    BSTR childName = SysAllocString(name);
    if (childName == nullptr) {
        return nullptr;
    }
    VARIANT result = {};
    using GetItemFn = HRESULT(__stdcall*)(void*, BSTR, VARIANT*);
    const HRESULT status = reinterpret_cast<GetItemFn>(ComMethod(property, 5))(
        property, childName, &result);
    SysFreeString(childName);
    if (FAILED(status)) {
        VariantClear(&result);
        return nullptr;
    }
    return QueryWzProperty(DetachVariantObject(result));
}

void ReleaseGroups(void** groups) {
    for (int index = 0; index < kGroupCount; ++index) {
        ComRelease(groups[index]);
        groups[index] = nullptr;
    }
}

bool LoadSkinGroups(int skinId, void** groups) {
    void* image = LoadEffectImage(skinId);
    if (image == nullptr) {
        return false;
    }
    for (int index = 0; index < kGroupCount; ++index) {
        groups[index] = GetChild(image, kGroupNames[index]);
        if (groups[index] == nullptr) {
            char line[96] = {};
            wsprintfA(line, "ERROR: damage-skin group load failed skin=%d group=%d", skinId, index);
            Log(line);
            ComRelease(image);
            ReleaseGroups(groups);
            return false;
        }
    }
    ComRelease(image);
    return true;
}

void** CacheSlot(void* displayer, int offset) {
    return reinterpret_cast<void**>(static_cast<unsigned char*>(displayer) + offset);
}

bool CaptureDefaults(void* displayer) {
    if (gDefaultsCaptured) {
        return true;
    }
    for (int index = 0; index < kGroupCount; ++index) {
        void* group = *CacheSlot(displayer, kCacheOffsets[index]);
        if (group == nullptr) {
            return false;
        }
    }
    for (int index = 0; index < kGroupCount; ++index) {
        gDefaultGroups[index] = *CacheSlot(displayer, kCacheOffsets[index]);
        ComAddRef(gDefaultGroups[index]);
    }
    gDefaultsCaptured = true;
    Log("OK: captured BasicEff normal/critical damage glyph groups");
    return true;
}

void ReplaceCacheGroups(void* displayer, void** replacements) {
    for (int index = 0; index < kGroupCount; ++index) {
        void** slot = CacheSlot(displayer, kCacheOffsets[index]);
        void* previous = *slot;
        *slot = replacements[index];
        replacements[index] = nullptr;
        ComRelease(previous);
    }
}

void RestoreDefaultGroups(void* displayer) {
    void* replacements[kGroupCount] = {};
    for (int index = 0; index < kGroupCount; ++index) {
        replacements[index] = gDefaultGroups[index];
        ComAddRef(replacements[index]);
    }
    ReplaceCacheGroups(displayer, replacements);
}

void ApplyRequestedSkin() {
    const int requested = static_cast<int>(InterlockedCompareExchange(&gRequestedSkin, 0, 0));
    if (requested == gAppliedSkin || requested == gFailedSkin) {
        return;
    }
    void* displayer = *reinterpret_cast<void**>(kAnimationDisplayerAddress);
    if (displayer == nullptr || !CaptureDefaults(displayer)) {
        return;
    }
    if (requested == 0) {
        RestoreDefaultGroups(displayer);
        gAppliedSkin = 0;
        gFailedSkin = -1;
        Log("OK: restored default BasicEff damage glyphs");
        return;
    }
    void* replacements[kGroupCount] = {};
    if (!LoadSkinGroups(requested, replacements)) {
        gFailedSkin = requested;
        return;
    }
    if (requested != static_cast<int>(InterlockedCompareExchange(&gRequestedSkin, 0, 0))) {
        ReleaseGroups(replacements);
        return;
    }
    ReplaceCacheGroups(displayer, replacements);
    gAppliedSkin = requested;
    gFailedSkin = -1;
    char line[96] = {};
    wsprintfA(line, "OK: applied WZ damage glyph groups skin=%d", requested);
    Log(line);
}

bool InstallEffectHitHook();

DWORD WINAPI Initialize(LPVOID) {
    Log("LOAD: BeiDouDamageSkinCompat v5 split-IWzProperty-cache");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kImageBase) {
        Log("ERROR: unexpected BeiDou.exe image base; no damage-skin hook installed");
        return 1;
    }
    if (!BytesEqual(
            reinterpret_cast<const void*>(kEffectHitAddress),
            kEffectHitOriginal,
            sizeof(kEffectHitOriginal))) {
        Log("ERROR: Effect_Hit bytes do not match this BeiDou.exe");
        return 2;
    }
    if (!InstallEffectHitHook()) {
        Log("ERROR: Effect_Hit hook installation failed");
        return 3;
    }
    Log("OK: Effect_Hit native WZ cache hook installed");
    return 0;
}

}  // namespace

extern "C" __attribute__((noinline)) void ApplyRequestedDamageSkin() {
    ApplyRequestedSkin();
}

extern "C" __attribute__((naked, noinline)) void HookDamageSkinEffectHit() {
    __asm__ __volatile__(
        ".intel_syntax noprefix\n"
        "pushfd\n"
        "pushad\n"
        "call _ApplyRequestedDamageSkin\n"
        "popad\n"
        "popfd\n"
        "mov eax, 0x00A79ACF\n"
        "push 0x00437D14\n"
        "ret\n"
        ".att_syntax prefix\n");
}

namespace {

bool InstallEffectHitHook() {
    DWORD oldProtect = 0;
    auto* target = reinterpret_cast<unsigned char*>(kEffectHitAddress);
    if (!VirtualProtect(target, sizeof(kEffectHitOriginal), PAGE_EXECUTE_READWRITE, &oldProtect)) {
        return false;
    }
    target[0] = 0xE9;
    *reinterpret_cast<int32_t*>(target + 1) = static_cast<int32_t>(
        reinterpret_cast<unsigned char*>(&HookDamageSkinEffectHit) - (target + 5));
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(kEffectHitOriginal));
    DWORD ignored = 0;
    VirtualProtect(target, sizeof(kEffectHitOriginal), oldProtect, &ignored);
    return true;
}

}  // namespace

extern "C" __declspec(dllexport) void BDS_SetSkin(int skinId) {
    if (skinId < 0) {
        skinId = 0;
    }
    InterlockedExchange(&gRequestedSkin, skinId);
    gFailedSkin = -1;
    char line[96] = {};
    wsprintfA(line, "SELECT: pending WZ damage glyph skin=%d", skinId);
    Log(line);
}

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        DeleteFileA("BeiDouDamageSkinCompat.log");
        HANDLE thread = CreateThread(nullptr, 0, Initialize, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
