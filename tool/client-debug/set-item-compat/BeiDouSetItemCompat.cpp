#include <windows.h>
#include <stdint.h>
#include <string.h>

namespace {

constexpr uintptr_t kImageBase = 0x00400000;
constexpr uintptr_t kProcessPacket = 0x004965F1;
constexpr uintptr_t kEquipTooltip = 0x008ECA0C;
constexpr uintptr_t kClearTooltip = 0x008E6E23;
constexpr uintptr_t kMakeLayer = 0x008F3141;
constexpr uintptr_t kTooltipConstructor = 0x008E49B5;
constexpr uintptr_t kEquipMakeLayer1 = 0x008E7E5E;
constexpr uintptr_t kEquipMakeLayer2 = 0x008E97C3;
constexpr uintptr_t kEquipMakeLayer3 = 0x008E97E7;
constexpr uintptr_t kRefreshNameplate = 0x00942DCC;
constexpr uintptr_t kMakeNameplate = 0x005F0334;
constexpr uintptr_t kFindUser = 0x009716ED;
constexpr uintptr_t kUserPool = 0x00BEBFA8;
constexpr unsigned short kSetItemUpdate = 0x017A;
constexpr unsigned short kDamageSkinUpdate = 0x017B;
constexpr unsigned short kNameplatePowerUpdate = 0x017C;
constexpr unsigned short kSpawnPlayer = 0x00A0;
constexpr unsigned short kRemovePlayer = 0x00A1;
constexpr int kMaxSets = 96;
constexpr int kMaxSlots = 8;
constexpr int kMaxAlts = 10;
constexpr int kMaxTiers = 8;
constexpr int kMaxStats = 24;

struct PacketView {
    int loopback;
    int state;
    unsigned char* data;
    unsigned short length;
    unsigned short rawSequence;
    unsigned short dataLength;
    unsigned short padding;
    size_t offset;
};
static_assert(sizeof(PacketView) == 0x18, "unexpected packet layout");

void MemoryCopy(void* destination, const void* source, size_t size) {
    unsigned char* out = static_cast<unsigned char*>(destination);
    const unsigned char* in = static_cast<const unsigned char*>(source);
    for (size_t i = 0; i < size; i++) out[i] = in[i];
}

void MemoryZero(void* destination, size_t size) {
    unsigned char* out = static_cast<unsigned char*>(destination);
    for (size_t i = 0; i < size; i++) out[i] = 0;
}

struct Reader {
    const unsigned char* data;
    size_t length;
    size_t offset;
    bool ok;
    size_t needed;

    int read1() {
        if (offset + 1 > length) { ok = false; needed = 1; return 0; }
        return data[offset++];
    }

    int read2() {
        if (offset + 2 > length) { ok = false; needed = 2; return 0; }
        int value = data[offset] | (data[offset + 1] << 8);
        offset += 2;
        return static_cast<short>(value);
    }

    int read4() {
        if (offset + 4 > length) { ok = false; needed = 4; return 0; }
        int value;
        MemoryCopy(&value, data + offset, 4);
        offset += 4;
        return value;
    }

    void readString(char* out, int capacity) {
        int lengthValue = read2();
        if (!ok || lengthValue < 0 || static_cast<size_t>(lengthValue) > length - offset) {
            ok = false;
            needed = lengthValue < 0 ? 0 : static_cast<size_t>(lengthValue);
            out[0] = 0;
            return;
        }
        int copy = lengthValue < capacity - 1 ? lengthValue : capacity - 1;
        MemoryCopy(out, data + offset, copy);
        out[copy] = 0;
        offset += lengthValue;
    }
};

struct Alt { int id; bool equipped; char name[96]; char type[32]; };
struct Slot { int count; Alt alts[kMaxAlts]; };
struct Stat { char key[24]; int value; };
struct Tier { int required; int count; Stat stats[kMaxStats]; };
struct SetData {
    int id;
    char name[96];
    int complete;
    int slotCount;
    Slot slots[kMaxSlots];
    int tierCount;
    Tier tiers[kMaxTiers];
    int activeTier;
    int equippedCount;
};

SetData gSets[kMaxSets] = {};
SetData gDecoded[kMaxSets] = {};
int gSetCount = 0;
void* gHoveredTip = nullptr;
int gPendingItem = -1;

using ProcessPacketFn = void(__thiscall*)(void*, PacketView*);
using EquipTooltipFn = void(__thiscall*)(void*, void*);
using ClearTooltipFn = void(__thiscall*)(void*);
using MakeLayerFn = void*(__thiscall*)(void*, void**, int, int, int, int, int, unsigned int);
using SetDamageSkinFn = void(__cdecl*)(int);
using RefreshNameplateFn = void(__thiscall*)(void*);
using MakeNameplateFn = int(__thiscall*)(void*, const char*, void*, void*, int, int, int, int, int, int);
using FindUserFn = void*(__thiscall*)(void*, int);
ProcessPacketFn gRealProcessPacket = nullptr;
EquipTooltipFn gRealEquipTooltip = nullptr;
ClearTooltipFn gRealClearTooltip = nullptr;
MakeLayerFn gRealMakeLayer = nullptr;
SetDamageSkinFn gSetDamageSkin = nullptr;
RefreshNameplateFn gRealRefreshNameplate = nullptr;
MakeNameplateFn gMakeNameplate = reinterpret_cast<MakeNameplateFn>(kMakeNameplate);
FindUserFn gFindUser = reinterpret_cast<FindUserFn>(kFindUser);

size_t TextLength(const char* text) {
    size_t length = 0;
    while (text && text[length]) length++;
    return length;
}

bool BytesEqual(const void* left, const void* right, size_t size) {
    const unsigned char* a = static_cast<const unsigned char*>(left);
    const unsigned char* b = static_cast<const unsigned char*>(right);
    for (size_t i = 0; i < size; i++) if (a[i] != b[i]) return false;
    return true;
}

bool HasText(const char* text, const char* needle) {
    size_t length = TextLength(needle);
    if (!length) return true;
    for (; TextLength(text) >= length; text++) if (BytesEqual(text, needle, length)) return true;
    return false;
}

void Log(const char* line) {
    HANDLE file = CreateFileA("BeiDouSetItemCompat.log", FILE_APPEND_DATA, FILE_SHARE_READ,
            nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(TextLength(line)), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

int DecodeSecureItemId(void* equip) {
    if (!equip) return -1;
    unsigned char* base = static_cast<unsigned char*>(equip);
    uint32_t fake1 = *reinterpret_cast<uint32_t*>(base + 0x0C);
    unsigned char* secure = *reinterpret_cast<unsigned char**>(base + 0x14);
    if (!secure || IsBadReadPtr(secure, 12)) return -1;
    unsigned char key = secure[4];
    uint16_t checksum = 0x9A65;
    int value = 0;
    for (int i = 0; i < 4; i++) {
        if (!key) key = 42;
        unsigned char encoded = secure[i];
        reinterpret_cast<unsigned char*>(&value)[i] = encoded ^ key;
        key = static_cast<unsigned char>(encoded + 42 + key);
        checksum = static_cast<uint16_t>((checksum << 3) | (key + (checksum >> 13)));
    }
    if (checksum != *reinterpret_cast<uint16_t*>(secure + 8)
            || static_cast<unsigned char>(fake1) != secure[5]) return -1;
    return value;
}

bool SetContains(const SetData& set, int itemId) {
    for (int slot = 0; slot < set.slotCount; slot++) {
        for (int alt = 0; alt < set.slots[slot].count; alt++) {
            if (set.slots[slot].alts[alt].id == itemId) return true;
        }
    }
    return false;
}

void DecodeSetPacket(PacketView* packet) {
    Reader reader{packet->data, packet->length, packet->offset, true, 0};
    int phase = 0;
    int setIndex = -1;
    int slotIndex = -1;
    int altIndex = -1;
    int tierIndex = -1;
    int statIndex = -1;
    if (reader.read2() != kSetItemUpdate) return;
    int count = reader.read2();
    if (count < 0 || count > kMaxSets) { Log("ERROR: invalid set count"); return; }
    MemoryZero(gDecoded, sizeof(gDecoded));
    for (int i = 0; i < count && reader.ok; i++) {
        phase = 1;
        setIndex = i;
        slotIndex = altIndex = tierIndex = statIndex = -1;
        SetData& set = gDecoded[i];
        set.id = reader.read4();
        reader.readString(set.name, sizeof(set.name));
        set.complete = reader.read2();
        int slots = reader.read2();
        set.slotCount = slots < kMaxSlots ? slots : kMaxSlots;
        for (int slot = 0; slot < slots && reader.ok; slot++) {
            phase = 2;
            slotIndex = slot;
            altIndex = -1;
            int alternatives = reader.read2();
            for (int alt = 0; alt < alternatives && reader.ok; alt++) {
                phase = 3;
                altIndex = alt;
                int id = reader.read4();
                bool worn = reader.read1() != 0;
                char name[96];
                char type[32];
                reader.readString(name, sizeof(name));
                reader.readString(type, sizeof(type));
                reader.read4();
                if (slot < kMaxSlots && alt < kMaxAlts) {
                    Alt& out = set.slots[slot].alts[alt];
                    out.id = id;
                    out.equipped = worn;
                    lstrcpynA(out.name, name, sizeof(out.name));
                    lstrcpynA(out.type, type, sizeof(out.type));
                    set.slots[slot].count++;
                }
            }
        }
        int tiers = reader.read2();
        set.tierCount = tiers < kMaxTiers ? tiers : kMaxTiers;
        for (int tier = 0; tier < tiers && reader.ok; tier++) {
            phase = 4;
            tierIndex = tier;
            statIndex = -1;
            int required = reader.read2();
            int stats = reader.read2();
            for (int stat = 0; stat < stats && reader.ok; stat++) {
                phase = 5;
                statIndex = stat;
                char key[24];
                reader.readString(key, sizeof(key));
                int value = reader.read4();
                if (tier < kMaxTiers && stat < kMaxStats) {
                    Tier& out = set.tiers[tier];
                    out.required = required;
                    lstrcpynA(out.stats[stat].key, key, sizeof(out.stats[stat].key));
                    out.stats[stat].value = value;
                    out.count++;
                }
            }
        }
        phase = 6;
        set.activeTier = reader.read2();
        char story[256];
        reader.readString(story, sizeof(story));
        set.equippedCount = reader.read4();
        reader.read4();
    }
    if (!reader.ok) {
        char line[256];
        wsprintfA(line,
                "ERROR: truncated 0x17A len=%u dataLen=%u start=%u fail=%u need=%u phase=%d set=%d slot=%d alt=%d tier=%d stat=%d",
                packet->length, packet->dataLength, static_cast<unsigned int>(packet->offset),
                static_cast<unsigned int>(reader.offset), static_cast<unsigned int>(reader.needed),
                phase, setIndex, slotIndex, altIndex, tierIndex, statIndex);
        Log(line);
        return;
    }
    char line[128];
    wsprintfA(line, "OK: decoded 0x17A sets=%d bytes=%u/%u", count,
            static_cast<unsigned int>(reader.offset), packet->length);
    Log(line);
    MemoryCopy(gSets, gDecoded, sizeof(gDecoded));
    gSetCount = count;
}

const wchar_t* StatLabel(const char* key) {
    if (!lstrcmpA(key, "PAD")) return L"攻击力";
    if (!lstrcmpA(key, "MAD")) return L"魔法攻击力";
    if (!lstrcmpA(key, "HP")) return L"最大HP";
    if (!lstrcmpA(key, "MP")) return L"最大MP";
    if (!lstrcmpA(key, "FinalDamage")) return L"最终伤害";
    if (!lstrcmpA(key, "BossDamage")) return L"Boss伤害";
    if (!lstrcmpA(key, "ExpRate")) return L"经验获得";
    if (!lstrcmpA(key, "DropRate")) return L"掉落率";
    if (!lstrcmpA(key, "MesoRate")) return L"金币获得";
    return L"属性";
}

void GbkToWide(const char* text, wchar_t* out, int capacity) {
    if (!MultiByteToWideChar(936, 0, text, -1, out, capacity)) {
        MultiByteToWideChar(CP_UTF8, 0, text, -1, out, capacity);
    }
}

constexpr int kNativePanelWidth = 236;
constexpr int kNativeLineHeight = 16;
constexpr int kPanelLeft = 8;
constexpr int kStatLeft = 16;
constexpr int kPanelRight = kNativePanelWidth - 8;
constexpr GUID kWzFontGuid = {
    0x2BEF046D, 0xCCD6, 0x445A, {0x88, 0xC4, 0x92, 0x9F, 0xC3, 0x5D, 0x30, 0xAC}
};
alignas(16) unsigned char gNativeTip[0x2000] = {};
bool gNativeTipInitialized = false;
bool gNativePanelActive = false;
int gNativePanelItem = -1;
void* gNativeCanvas = nullptr;
void* gNativeFontTitle = nullptr;
void* gNativeFontActive = nullptr;
void* gNativeFontLabel = nullptr;
void* gNativeFontDim = nullptr;

void* ComMethod(void* object, int index) {
    return object ? (*reinterpret_cast<void***>(object))[index] : nullptr;
}

void ComRelease(void* object) {
    if (object) reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(object, 2))(object);
}

VARIANT MissingVariant() {
    VARIANT value;
    MemoryZero(&value, sizeof(value));
    value.vt = VT_ERROR;
    value.scode = DISP_E_PARAMNOTFOUND;
    return value;
}

bool CreateNativeFont(void*& font, unsigned int color, unsigned int height = 12) {
    if (font) return true;
    void* createObject = reinterpret_cast<void**>(0x00BF0CC0)[0];
    if (!createObject) { Log("ERROR: PcCreateObject API is null"); return false; }
    HRESULT result = reinterpret_cast<HRESULT(__cdecl*)(const wchar_t*, const GUID*, void**, void*)>(
            createObject)(L"Canvas#Font", &kWzFontGuid, &font, nullptr);
    if (FAILED(result) || !font) {
        char line[96];
        wsprintfA(line, "ERROR: PcCreateObject font hr=%08X", static_cast<unsigned int>(result));
        Log(line);
        return false;
    }
    BSTR face = SysAllocString(L"Arial");
    BSTR empty = SysAllocString(L"");
    VARIANT style;
    MemoryZero(&style, sizeof(style));
    style.vt = VT_BSTR;
    style.bstrVal = empty;
    result = reinterpret_cast<HRESULT(__stdcall*)(void*, BSTR, UINT, UINT, VARIANT)>(
            ComMethod(font, 3))(font, face, height, color, style);
    SysFreeString(face);
    SysFreeString(empty);
    if (FAILED(result)) {
        char line[96];
        wsprintfA(line, "ERROR: IWzFont::Create hr=%08X", static_cast<unsigned int>(result));
        Log(line);
        ComRelease(font);
        font = nullptr;
        return false;
    }
    return true;
}

bool EnsureNativeFonts() {
    return CreateNativeFont(gNativeFontTitle, 0xFFFFE137)
            && CreateNativeFont(gNativeFontActive, 0xFFFFFFFF)
            && CreateNativeFont(gNativeFontLabel, 0xFFD2D2D2)
            && CreateNativeFont(gNativeFontDim, 0xFF90949D);
}

void DrawNativeText(void* canvas, void* font, int x, int y, const wchar_t* text) {
    if (!canvas || !font || !text || !text[0]) return;
    BSTR value = SysAllocString(text);
    if (!value) return;
    VARIANT missing = MissingVariant();
    UINT height = 0;
    reinterpret_cast<HRESULT(__stdcall*)(void*, int, int, BSTR, void*, VARIANT, VARIANT, UINT*)>(
            ComMethod(font, 12))(font, x, y, value, canvas, missing, missing, &height);
    SysFreeString(value);
}

int EstimateTextWidth(const wchar_t* text) {
    int width = 0;
    for (int i = 0; text && text[i]; i++) width += text[i] < 0x80 ? 6 : 12;
    return width;
}

int CenteredTextX(const wchar_t* text) {
    int x = (kNativePanelWidth - EstimateTextWidth(text)) / 2;
    return x > kPanelLeft ? x : kPanelLeft;
}

int RightAlignedTextX(const wchar_t* text) {
    int x = kPanelRight - EstimateTextWidth(text);
    return x > kPanelLeft ? x : kPanelLeft;
}

void TrimTextToWidth(wchar_t* text, int maxWidth) {
    int length = 0;
    while (text[length]) length++;
    if (EstimateTextWidth(text) <= maxWidth) return;
    while (length > 3 && EstimateTextWidth(text) + 18 > maxWidth) text[--length] = 0;
    if (length >= 3) {
        text[length - 3] = L'.';
        text[length - 2] = L'.';
        text[length - 1] = L'.';
    }
}

void LayerVisible(void* layer, int visible) {
    if (layer) reinterpret_cast<HRESULT(__stdcall*)(void*, int)>(ComMethod(layer, 71))(layer, visible);
}

void LayerMove(void* layer, int x, int y) {
    if (!layer) return;
    VARIANT missing = MissingVariant();
    reinterpret_cast<HRESULT(__stdcall*)(void*, int, int, VARIANT, VARIANT)>(ComMethod(layer, 36))(
            layer, x, y, missing, missing);
}

void* LayerCanvas(void* layer) {
    if (!layer) return nullptr;
    VARIANT index;
    MemoryZero(&index, sizeof(index));
    index.vt = VT_I4;
    index.lVal = 0;
    void* canvas = nullptr;
    if (FAILED(reinterpret_cast<HRESULT(__stdcall*)(void*, VARIANT, void**)>(ComMethod(layer, 64))(
            layer, index, &canvas))) return nullptr;
    return canvas;
}

bool LayerCoordinate(void* layer, int method, int& value) {
    return layer && SUCCEEDED(reinterpret_cast<HRESULT(__stdcall*)(void*, int*)>(
            ComMethod(layer, method))(layer, &value));
}

int LayerHeight(void* layer) {
    void* canvas = LayerCanvas(layer);
    if (!canvas) return kNativeLineHeight;
    int height = kNativeLineHeight;
    reinterpret_cast<HRESULT(__stdcall*)(void*, int*)>(ComMethod(canvas, 18))(canvas, &height);
    ComRelease(canvas);
    return height > 0 ? height : kNativeLineHeight;
}

constexpr int kMaxPowerNameplates = 128;
struct PowerNameplateState {
    int characterId;
    int power;
    bool enabled;
    void* layer;
};
PowerNameplateState gPowerNameplates[kMaxPowerNameplates] = {};

PowerNameplateState* FindPowerState(int characterId, bool create) {
    PowerNameplateState* empty = nullptr;
    for (int i = 0; i < kMaxPowerNameplates; i++) {
        if (gPowerNameplates[i].characterId == characterId) return &gPowerNameplates[i];
        if (!gPowerNameplates[i].characterId && !empty) empty = &gPowerNameplates[i];
    }
    if (!create) return nullptr;
    if (!empty) {
        for (int i = 0; i < kMaxPowerNameplates; i++) {
            if (!gPowerNameplates[i].layer) { empty = &gPowerNameplates[i]; break; }
        }
    }
    if (!empty) return nullptr;
    empty->characterId = characterId;
    return empty;
}

void ReleasePowerLayer(PowerNameplateState& state) {
    if (state.layer) {
        LayerVisible(state.layer, 0);
        ComRelease(state.layer);
        state.layer = nullptr;
    }
}

void ClearPowerState(int characterId) {
    PowerNameplateState* state = FindPowerState(characterId, false);
    if (!state) return;
    ReleasePowerLayer(*state);
    MemoryZero(state, sizeof(*state));
}

void FormatPower(int power, char* out, int capacity) {
    char digits[24];
    wsprintfA(digits, "%d", power);
    int length = static_cast<int>(TextLength(digits));
    int commas = length > 0 ? (length - 1) / 3 : 0;
    int outputLength = length + commas;
    if (capacity <= outputLength) { lstrcpynA(out, digits, capacity); return; }
    out[outputLength] = 0;
    int source = length - 1;
    int target = outputLength - 1;
    int group = 0;
    while (source >= 0) {
        out[target--] = digits[source--];
        if (++group == 3 && source >= 0) { out[target--] = ','; group = 0; }
    }
}

void LayoutPowerNameplate(void* user, PowerNameplateState& state) {
    unsigned char* base = static_cast<unsigned char*>(user);
    void* nameLayer = *reinterpret_cast<void**>(base + 0x7C);
    void* guildLayer = *reinterpret_cast<void**>(base + 0x80);
    void* medalLayer = *reinterpret_cast<void**>(base + 0x84);
    if (!nameLayer || !state.layer) return;
    int nameY = 0;
    if (!LayerCoordinate(nameLayer, 28, nameY)) return;
    int nextY = nameY + LayerHeight(nameLayer) + 1;
    void* layers[] = {state.layer, guildLayer, medalLayer};
    for (int i = 0; i < 3; i++) {
        void* layer = layers[i];
        if (!layer) continue;
        int x = 0;
        if (!LayerCoordinate(layer, 26, x)) continue;
        LayerMove(layer, x, nextY);
        nextY += LayerHeight(layer) + 1;
    }
}

void CreatePowerLayer(void* user, PowerNameplateState& state) {
    ReleasePowerLayer(state);
    if (!state.enabled || !user) return;
    unsigned char* base = static_cast<unsigned char*>(user);
    void** guildSlot = reinterpret_cast<void**>(base + 0x80);
    void* oldGuild = *guildSlot;
    void* origin = *reinterpret_cast<void**>(base + 0x1150);
    void* nameTag = *reinterpret_cast<void**>(base + 0x11A4);
    if (!*reinterpret_cast<void**>(base + 0x7C) || !origin || !nameTag) return;

    char number[32];
    char label[64];
    FormatPower(state.power, number, sizeof(number));
    wsprintfA(label, "\xD5\xBD\xB6\xB7\xC1\xA6: %s", number);

    if (oldGuild) reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(oldGuild, 1))(oldGuild);
    reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(origin, 1))(origin);
    reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(nameTag, 1))(nameTag);
    char line[160];
    wsprintfA(line, "POWER PHASE: native create begin character=%d power=%d",
            state.characterId, state.power);
    Log(line);
    int makeResult = gMakeNameplate(user, label, origin, nameTag, 1004, 0, 0, 0, 0, 0);

    void* created = *guildSlot;
    wsprintfA(line, "POWER PHASE: native create returned result=%d layer=%08X oldGuild=%08X",
            makeResult, static_cast<unsigned int>(reinterpret_cast<uintptr_t>(created)),
            static_cast<unsigned int>(reinterpret_cast<uintptr_t>(oldGuild)));
    Log(line);
    if (created && created != oldGuild) {
        reinterpret_cast<ULONG(__stdcall*)(void*)>(ComMethod(created, 1))(created);
        *guildSlot = oldGuild;
        ComRelease(created);
        state.layer = created;
        Log("POWER PHASE: unsafe custom Canvas styling bypassed");
        Log("POWER PHASE: layout begin");
        LayoutPowerNameplate(user, state);
        Log("POWER PHASE: layout complete");
        return;
    }
    if (!created) {
        *guildSlot = oldGuild;
    } else {
        ComRelease(oldGuild);
    }
}

void* FindUser(int characterId) {
    void* pool = *reinterpret_cast<void**>(kUserPool);
    return pool ? gFindUser(pool, characterId) : nullptr;
}

void DecodePowerNameplatePacket(PacketView* packet) {
    if (packet->offset + 11 != packet->length) {
        Log("ERROR: invalid 0x17C nameplate-power packet");
        return;
    }
    int characterId = 0;
    int power = 0;
    MemoryCopy(&characterId, packet->data + packet->offset + 2, sizeof(characterId));
    bool enabled = packet->data[packet->offset + 6] != 0;
    MemoryCopy(&power, packet->data + packet->offset + 7, sizeof(power));
    if (characterId <= 0 || power < 0) {
        Log("ERROR: invalid 0x17C nameplate-power values");
        return;
    }
    PowerNameplateState* state = FindPowerState(characterId, true);
    if (!state) { Log("ERROR: nameplate-power state table full"); return; }
    state->enabled = enabled;
    state->power = enabled ? power : 0;
    char line[160];
    wsprintfA(line, "POWER PHASE: packet accepted character=%d enabled=%d power=%d",
            characterId, enabled ? 1 : 0, state->power);
    Log(line);
    void* user = FindUser(characterId);
    if (user) {
        Log("POWER PHASE: native refresh begin");
        gRealRefreshNameplate(user);
        Log("POWER PHASE: native refresh complete; custom create begin");
        CreatePowerLayer(user, *state);
    } else {
        Log("POWER PHASE: user not present; creation deferred");
    }
    wsprintfA(line, "OK: decoded 0x17C character=%d enabled=%d power=%d",
            characterId, enabled ? 1 : 0, state->power);
    Log(line);
}

void AlignNativeLayer(void* nativeLayer, void* panelLayer, int x, int y) {
    if (!panelLayer) return;
    if (nativeLayer) {
        int z = 0;
        reinterpret_cast<HRESULT(__stdcall*)(void*, int*)>(ComMethod(nativeLayer, 44))(nativeLayer, &z);
        reinterpret_cast<HRESULT(__stdcall*)(void*, int)>(ComMethod(panelLayer, 45))(panelLayer, z);
        VARIANT origin;
        VariantInit(&origin);
        if (SUCCEEDED(reinterpret_cast<HRESULT(__stdcall*)(void*, VARIANT*)>(ComMethod(nativeLayer, 24))(
                nativeLayer, &origin))) {
            reinterpret_cast<HRESULT(__stdcall*)(void*, VARIANT)>(ComMethod(panelLayer, 25))(
                    panelLayer, origin);
        }
        VariantClear(&origin);
    }
    LayerVisible(panelLayer, 1);
    LayerMove(panelLayer, x, y);
}

SetData* FindSetForItem(int itemId) {
    for (int i = 0; i < gSetCount; i++) if (SetContains(gSets[i], itemId)) return &gSets[i];
    return nullptr;
}

int NativePanelLineCount(const SetData& set) {
    int lines = 2 + set.slotCount;
    for (int tier = 0; tier < set.tierCount; tier++) {
        lines++;
        for (int stat = 0; stat < set.tiers[tier].count; stat++) {
            if (set.tiers[tier].stats[stat].value) lines++;
        }
    }
    return lines;
}

void RenderNativePanel(void* canvas, const SetData& set, int itemId) {
    int y = 7;
    wchar_t wide[160];
    wchar_t line[240];
    GbkToWide(set.name, wide, 160);
    wsprintfW(line, L"%s (%d/%d)", wide, set.equippedCount, set.complete);
    DrawNativeText(canvas, gNativeFontTitle, CenteredTextX(line), y, line);
    y += kNativeLineHeight + 2;

    for (int slot = 0; slot < set.slotCount; slot++) {
        const Alt* shown = set.slots[slot].count ? &set.slots[slot].alts[0] : nullptr;
        for (int alt = 0; alt < set.slots[slot].count; alt++) {
            const Alt& candidate = set.slots[slot].alts[alt];
            if (candidate.equipped || candidate.id == itemId) shown = &candidate;
        }
        if (!shown) continue;
        GbkToWide(shown->name, wide, 160);
        wchar_t type[48];
        GbkToWide(shown->type, type, 48);
        wsprintfW(line, L"(%s)", type);
        int typeX = RightAlignedTextX(line);
        TrimTextToWidth(wide, typeX - kPanelLeft - 6);
        void* font = shown->id == itemId
                ? gNativeFontTitle
                : (shown->equipped ? gNativeFontActive : gNativeFontDim);
        DrawNativeText(canvas, font, kPanelLeft, y, wide);
        DrawNativeText(canvas, font, typeX, y, line);
        y += kNativeLineHeight;
    }

    y += 3;
    DrawNativeText(canvas, gNativeFontTitle, kPanelLeft, y, L"套装效果");
    y += kNativeLineHeight;
    for (int tier = 0; tier < set.tierCount; tier++) {
        const Tier& bonus = set.tiers[tier];
        bool active = set.activeTier >= tier;
        wsprintfW(line, L"[%d件]", bonus.required);
        DrawNativeText(canvas, active ? gNativeFontActive : gNativeFontDim, kPanelLeft, y, line);
        y += kNativeLineHeight;
        for (int stat = 0; stat < bonus.count; stat++) {
            const Stat& value = bonus.stats[stat];
            if (!value.value) continue;
            bool percent = HasText(value.key, "Damage") || HasText(value.key, "Rate")
                    || HasText(value.key, "Pct") || !lstrcmpA(value.key, "StatusRes")
                    || !lstrcmpA(value.key, "BuffDuration");
            wsprintfW(line, L"%s +%d%s", StatLabel(value.key), value.value,
                    percent ? L"%" : L"");
            DrawNativeText(canvas, active ? gNativeFontLabel : gNativeFontDim, kStatLeft, y, line);
            y += kNativeLineHeight;
        }
    }
}

void HideNativePanel() {
    if (!gNativeTipInitialized) return;
    void* layer = *reinterpret_cast<void**>(gNativeTip + 0x10);
    LayerVisible(layer, 0);
    if (gNativePanelActive && gRealClearTooltip) gRealClearTooltip(gNativeTip);
    if (gNativeCanvas) {
        ComRelease(gNativeCanvas);
        gNativeCanvas = nullptr;
    }
    gNativePanelActive = false;
    gNativePanelItem = -1;
}

void ShowNativePanel(int itemId, void* nativeTip, int left, int top, int nativeWidth,
        int doubleOutline, unsigned int color) {
    SetData* set = FindSetForItem(itemId);
    if (!set || !EnsureNativeFonts()) { HideNativePanel(); return; }
    if (!gNativeTipInitialized) {
        MemoryZero(gNativeTip, sizeof(gNativeTip));
        reinterpret_cast<void(__thiscall*)(void*)>(kTooltipConstructor)(gNativeTip);
        gNativeTipInitialized = true;
    }
    void* nativeLayer = *reinterpret_cast<void**>(static_cast<unsigned char*>(nativeTip) + 0x10);
    int x = left + nativeWidth + 4;
    if (gNativePanelActive && gNativePanelItem == itemId) {
        AlignNativeLayer(nativeLayer, *reinterpret_cast<void**>(gNativeTip + 0x10), x, top);
        return;
    }
    HideNativePanel();
    int height = NativePanelLineCount(*set) * kNativeLineHeight + 28;
    *reinterpret_cast<int*>(gNativeTip + 0x08) = height;
    *reinterpret_cast<int*>(gNativeTip + 0x0C) = kNativePanelWidth;
    void* canvas = nullptr;
    gRealMakeLayer(gNativeTip, &canvas, x, top, doubleOutline, 0, 0, color);
    void* panelLayer = *reinterpret_cast<void**>(gNativeTip + 0x10);
    if (!canvas || !panelLayer) {
        if (canvas) ComRelease(canvas);
        Log("ERROR: native set panel MakeLayer failed");
        return;
    }
    gNativeCanvas = canvas;
    void* drawCanvas = LayerCanvas(panelLayer);
    if (!drawCanvas) {
        HideNativePanel();
        Log("ERROR: native set panel canvas[0] missing");
        return;
    }
    RenderNativePanel(drawCanvas, *set, itemId);
    ComRelease(drawCanvas);
    gNativePanelActive = true;
    gNativePanelItem = itemId;
    AlignNativeLayer(nativeLayer, panelLayer, x, top);
    char logLine[96];
    wsprintfA(logLine, "OK: native set panel shown item=%d set=%d", itemId, set->id);
    Log(logLine);
}

void __fastcall HookProcessPacket(void* self, void*, PacketView* packet) {
    if (packet && packet->data && packet->offset + 2 <= packet->length) {
        const unsigned short opcode = *reinterpret_cast<unsigned short*>(packet->data + packet->offset);
        if ((opcode == kSpawnPlayer || opcode == kRemovePlayer)
                && packet->offset + 6 <= packet->length) {
            int characterId = 0;
            MemoryCopy(&characterId, packet->data + packet->offset + 2, sizeof(characterId));
            ClearPowerState(characterId);
        }
        if (opcode == kSetItemUpdate) {
            DecodeSetPacket(packet);
            return;
        }
        if (opcode == kDamageSkinUpdate) {
            if (packet->offset + 6 == packet->length && gSetDamageSkin != nullptr) {
                int skinId = 0;
                MemoryCopy(&skinId, packet->data + packet->offset + 2, sizeof(skinId));
                gSetDamageSkin(skinId);
                char line[96];
                wsprintfA(line, "OK: decoded 0x17B skin=%d", skinId);
                Log(line);
            } else {
                Log("ERROR: invalid 0x17B damage-skin packet");
            }
            return;
        }
        if (opcode == kNameplatePowerUpdate) {
            DecodePowerNameplatePacket(packet);
            return;
        }
    }
    gRealProcessPacket(self, packet);
}

void __fastcall HookRefreshNameplate(void* self, void*) {
    gRealRefreshNameplate(self);
    int characterId = *reinterpret_cast<int*>(static_cast<unsigned char*>(self) + 0x11A8);
    PowerNameplateState* state = FindPowerState(characterId, false);
    if (state) CreatePowerLayer(self, *state);
}

void __fastcall HookEquipTooltip(void* self, void*, void* equip) {
    gRealEquipTooltip(self, equip);
    int itemId = DecodeSecureItemId(equip);
    if (!gHoveredTip) {
        char line[96];
        wsprintfA(line, "INFO: equipment tooltip item=%d sets=%d", itemId, gSetCount);
        Log(line);
        gHoveredTip = self;
        gPendingItem = itemId;
    }
}

void __fastcall HookClearTooltip(void* self, void*) {
    gRealClearTooltip(self);
    if (self == gHoveredTip) {
        gHoveredTip = nullptr;
        gPendingItem = -1;
        HideNativePanel();
    }
}

void* __fastcall HookMakeLayer(void* self, void*, void** result, int left, int top,
        int doubleOutline, int login, int characterTooltip, unsigned int color) {
    void* out = gRealMakeLayer(self, result, left, top, doubleOutline, login, characterTooltip, color);
    if (self == gHoveredTip) {
        if (gPendingItem >= 0) {
            ShowNativePanel(gPendingItem, self, left, top,
                    *reinterpret_cast<int*>(static_cast<unsigned char*>(self) + 0x0C),
                    doubleOutline, color);
        } else {
            HideNativePanel();
        }
    }
    return out;
}

void* InstallHook(uintptr_t address, const unsigned char* expected, size_t patchSize,
        void* replacement) {
    unsigned char* site = reinterpret_cast<unsigned char*>(address);
    void* previous = nullptr;
    if (site[0] == 0xE9) {
        previous = site + 5 + *reinterpret_cast<int32_t*>(site + 1);
    } else {
        if (!BytesEqual(site, expected, patchSize)) return nullptr;
        unsigned char* trampoline = static_cast<unsigned char*>(VirtualAlloc(
                nullptr, patchSize + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
        if (!trampoline) return nullptr;
        MemoryCopy(trampoline, site, patchSize);
        trampoline[patchSize] = 0xE9;
        *reinterpret_cast<int32_t*>(trampoline + patchSize + 1) = static_cast<int32_t>(
                (site + patchSize) - (trampoline + patchSize + 5));
        previous = trampoline;
    }
    DWORD oldProtection;
    if (!VirtualProtect(site, patchSize, PAGE_EXECUTE_READWRITE, &oldProtection)) return nullptr;
    site[0] = 0xE9;
    *reinterpret_cast<int32_t*>(site + 1) = static_cast<int32_t>(
            reinterpret_cast<unsigned char*>(replacement) - site - 5);
    for (size_t i = 5; i < patchSize; i++) site[i] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), site, patchSize);
    VirtualProtect(site, patchSize, oldProtection, &oldProtection);
    return previous;
}

bool CanInstallHook(uintptr_t address, const unsigned char* expected, size_t size) {
    const unsigned char* site = reinterpret_cast<const unsigned char*>(address);
    return site[0] == 0xE9 || BytesEqual(site, expected, size);
}

bool CanPatchCall(uintptr_t address, uintptr_t expectedTarget) {
    const unsigned char* site = reinterpret_cast<const unsigned char*>(address);
    if (site[0] != 0xE8) return false;
    return reinterpret_cast<uintptr_t>(site + 5 + *reinterpret_cast<const int32_t*>(site + 1))
            == expectedTarget;
}

bool PatchCall(uintptr_t address, void* replacement) {
    unsigned char* site = reinterpret_cast<unsigned char*>(address);
    DWORD oldProtection = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &oldProtection)) return false;
    site[0] = 0xE8;
    *reinterpret_cast<int32_t*>(site + 1) = static_cast<int32_t>(
            reinterpret_cast<unsigned char*>(replacement) - site - 5);
    FlushInstructionCache(GetCurrentProcess(), site, 5);
    DWORD ignored = 0;
    VirtualProtect(site, 5, oldProtection, &ignored);
    return true;
}

DWORD WINAPI Install(LPVOID instance) {
    Log("LOAD: BeiDouSetItemCompat v12 native-power-nameplate");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != kImageBase) {
        Log("ERROR: unexpected image base");
        return 1;
    }
    (void)instance;
    HMODULE damageSkins = LoadLibraryA("BeiDouDamageSkinCompat.dll");
    if (damageSkins != nullptr) {
        FARPROC selector = GetProcAddress(damageSkins, "BDS_SetSkin");
        MemoryCopy(&gSetDamageSkin, &selector, sizeof(gSetDamageSkin));
    }
    Log(gSetDamageSkin != nullptr
            ? "OK: damage-skin selector loaded"
            : "INFO: damage-skin selector not present");

    const unsigned char processBytes[] = {0xB8, 0xB0, 0x12, 0xA8, 0x00};
    const unsigned char equipBytes[] = {0xB8, 0xA8, 0x4B, 0xAD, 0x00};
    const unsigned char clearBytes[] = {0x56, 0x8B, 0xF1, 0x57, 0x33, 0xFF};
    const unsigned char nameplateBytes[] = {0xB8, 0x14, 0xDA, 0xAD, 0x00};
    if (!CanInstallHook(kProcessPacket, processBytes, sizeof(processBytes))
            || !CanInstallHook(kEquipTooltip, equipBytes, sizeof(equipBytes))
            || !CanInstallHook(kClearTooltip, clearBytes, sizeof(clearBytes))
            || !CanInstallHook(kRefreshNameplate, nameplateBytes, sizeof(nameplateBytes))
            || !CanPatchCall(kEquipMakeLayer1, kMakeLayer)
            || !CanPatchCall(kEquipMakeLayer2, kMakeLayer)
            || !CanPatchCall(kEquipMakeLayer3, kMakeLayer)) {
        Log("ERROR: hook byte mismatch; no set-item hooks installed");
        return 2;
    }
    gRealProcessPacket = reinterpret_cast<ProcessPacketFn>(InstallHook(
            kProcessPacket, processBytes, sizeof(processBytes),
            reinterpret_cast<void*>(&HookProcessPacket)));
    gRealEquipTooltip = reinterpret_cast<EquipTooltipFn>(InstallHook(
            kEquipTooltip, equipBytes, sizeof(equipBytes),
            reinterpret_cast<void*>(&HookEquipTooltip)));
    gRealClearTooltip = reinterpret_cast<ClearTooltipFn>(InstallHook(
            kClearTooltip, clearBytes, sizeof(clearBytes),
            reinterpret_cast<void*>(&HookClearTooltip)));
    gRealRefreshNameplate = reinterpret_cast<RefreshNameplateFn>(InstallHook(
            kRefreshNameplate, nameplateBytes, sizeof(nameplateBytes),
            reinterpret_cast<void*>(&HookRefreshNameplate)));
    gRealMakeLayer = reinterpret_cast<MakeLayerFn>(kMakeLayer);
    if (!gRealProcessPacket || !gRealEquipTooltip || !gRealClearTooltip || !gRealRefreshNameplate
            || !PatchCall(kEquipMakeLayer1, reinterpret_cast<void*>(&HookMakeLayer))
            || !PatchCall(kEquipMakeLayer2, reinterpret_cast<void*>(&HookMakeLayer))
            || !PatchCall(kEquipMakeLayer3, reinterpret_cast<void*>(&HookMakeLayer))) {
        Log("ERROR: hook installation failed");
        return 3;
    }
    Log("OK: set item, damage skin, and power nameplate hooks installed");
    return 0;
}

}

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(nullptr, 0, Install, instance, 0, nullptr);
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
