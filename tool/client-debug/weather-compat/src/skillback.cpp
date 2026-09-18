#include "pch.h"
#include "skillback.h"
#include "weatherfx.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/packet.h"
#include "wvs/util.h"
#include "ztl/ztl.h"

#include <cctype>
#include <cstring>

// Independent far-plane for skill art. Weather inject occupies back indices
// 0..InjectedLastIndex at z = 1000*idx - 0x4001F400. Hills are rewritten to
// HILL_Z(idx) = 1000*(idx + InjectedLastIndex + 8) - 0x4001F400. Sitting at
// InjectedLastIndex+5 puts this plane in front of the whole weather band
// (sky, clouds, rain sheets) and still behind tiles/objects.
//
// Large playback is MCV, not a Canvas sequence. The layer we create is only the
// proven 7x5 signature marker; BeiDouVideo.dll holds the VP9 frames.

#define ADDR_CREATE_ANIM_LAYER 0x0043EA3E
#define SKILLBACK_OPCODE       0x373F
#define SKILLBACK_PATH_MAX     192
#define SKILLBACK_Z_ORIGIN     0x4001F400
#define SKILLBACK_Z_AFTER      5
#define BDV_CHANNEL_PLAYER_SKILL 0u

namespace {

using t_CreateAnimLayer = void**(__cdecl*)(void**, void*, int, void*, int, int,
                                           void*, int, int, int);
const auto CreateAnimLayer = reinterpret_cast<t_CreateAnimLayer>(ADDR_CREATE_ANIM_LAYER);

using BdvPlayFileExFn = int(__stdcall*)(unsigned int, const char*);
using BdvStopChannelFn = void(__stdcall*)(unsigned int);
using BdvPlayFileFn = int(__stdcall*)(const char*);
using BdvStopFn = void(__stdcall*)();

char g_szPath[SKILLBACK_PATH_MAX + 1];
int g_nDurationMs = 0;
DWORD g_uExpireTick = 0;
bool g_bHaveRequest = false;
bool g_bNeedRebuild = false;
bool g_bOwnMcv = false;
IWzGr2DLayer* g_pLayer = nullptr;
HMODULE g_hVideo = nullptr;
BdvPlayFileExFn g_PlayFileEx = nullptr;
BdvStopChannelFn g_StopChannel = nullptr;
BdvPlayFileFn g_PlayFile = nullptr;
BdvStopFn g_Stop = nullptr;

const wchar_t* kMarkerUols[] = {
        L"Map/Effect.img/customSkill/skillBackdrop/videoLayer",
        L"Map/Effect.img/customSkill/dawnWarrior/galaxyStarBurstVideoLayer",
        L"Map/Effect.img/customSkill/dawnWarrior/soulEclipseVideoLayer",
        L"Map/Effect.img/customSkill/dawnWarrior/eclipseForceVideoLayer",
};

void ReleaseLayer(IWzGr2DLayer* pLayer) {
    if (!pLayer) {
        return;
    }
    try {
        pLayer->visible = 0;
    } catch (const _com_error&) {
    }
    pLayer->Release();
}

bool BindVideo() {
    if (g_PlayFileEx || g_PlayFile) {
        return true;
    }
    g_hVideo = GetModuleHandleA("BeiDouVideo.dll");
    if (!g_hVideo) {
        g_hVideo = LoadLibraryA("BeiDouVideo.dll");
    }
    if (!g_hVideo) {
        LOG_ONCE("skillback: BeiDouVideo.dll missing");
        return false;
    }
    g_PlayFileEx = reinterpret_cast<BdvPlayFileExFn>(GetProcAddress(g_hVideo, "BDV_PlayFileEx"));
    g_StopChannel = reinterpret_cast<BdvStopChannelFn>(GetProcAddress(g_hVideo, "BDV_StopChannel"));
    g_PlayFile = reinterpret_cast<BdvPlayFileFn>(GetProcAddress(g_hVideo, "BDV_PlayFile"));
    g_Stop = reinterpret_cast<BdvStopFn>(GetProcAddress(g_hVideo, "BDV_Stop"));
    return g_PlayFileEx || g_PlayFile;
}

void StopOwnedMcv() {
    if (!g_bOwnMcv) {
        return;
    }
    if (g_StopChannel) {
        g_StopChannel(BDV_CHANNEL_PLAYER_SKILL);
    } else if (g_Stop) {
        g_Stop();
    }
    g_bOwnMcv = false;
}

void DropLayer() {
    StopOwnedMcv();
    if (g_pLayer) {
        ReleaseLayer(g_pLayer);
        g_pLayer = nullptr;
    }
}

int PlaneZ() {
    return 1000 * (static_cast<int>(WeatherFx::InjectedLastIndex()) + SKILLBACK_Z_AFTER)
            - SKILLBACK_Z_ORIGIN;
}

bool IsMcvPath(const char* s, int n) {
    return n >= 5 && std::memcmp(s + n - 4, ".mcv", 4) == 0;
}

bool PathOk(const char* s, int n) {
    if (n <= 0 || n > SKILLBACK_PATH_MAX) {
        return false;
    }
    for (int i = 0; i < n; ++i) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c == '.' && i + 1 < n && s[i + 1] == '.') {
            return false;
        }
        if (!(isalnum(c) || c == '_' || c == '.' || c == '/' || c == '-')) {
            return false;
        }
    }
    if (IsMcvPath(s, n)) {
        const char* slash = std::strrchr(s, '/');
        const char* stem = slash ? slash + 1 : s;
        if (slash && std::strncmp(s, "Video/", 6) != 0) {
            return false;
        }
        if (slash && slash != s + 5) {
            return false;
        }
        const int stemLen = static_cast<int>(n - (stem - s) - 4);
        return stemLen > 0;
    }
    bool slash = false;
    bool img = false;
    for (int i = 0; i < n; ++i) {
        if (s[i] == '/') {
            slash = true;
        }
    }
    for (int i = 0; i + 4 < n; ++i) {
        if (s[i] == '.' && s[i + 1] == 'i' && s[i + 2] == 'm' && s[i + 3] == 'g'
                && s[i + 4] == '/') {
            img = true;
            break;
        }
    }
    return slash && img;
}

void* CallCreateAnimLayer(void* pNode, void* pOverlay, int nZ) {
    void* pLayer = nullptr;
    __try {
        CreateAnimLayer(&pLayer, pNode, 0, nullptr, 0, 0, pOverlay, nZ, 255, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        pLayer = nullptr;
    }
    return pLayer;
}

IWzPropertyPtr LoadMarkerNode(bool mcv, const wchar_t* wzPath) {
    if (!mcv && wzPath && wzPath[0]) {
        try {
            IWzPropertyPtr node = get_rm()->GetObjectA(wzPath).GetUnknown();
            if (node) {
                return node;
            }
        } catch (const _com_error&) {
        }
    }
    for (const wchar_t* uol : kMarkerUols) {
        try {
            IWzPropertyPtr node = get_rm()->GetObjectA(uol).GetUnknown();
            if (node) {
                return node;
            }
        } catch (const _com_error&) {
        }
    }
    return nullptr;
}

bool PlayMcvFile(const char* logical) {
    if (!BindVideo()) {
        return false;
    }
    char disk[MAX_PATH];
    const char* slash = std::strrchr(logical, '/');
    const char* file = slash ? slash + 1 : logical;
    if (FAILED(StringCchPrintfA(disk, MAX_PATH, "Data\\Video\\%s", file))) {
        return false;
    }
    int rc = -1;
    if (g_PlayFileEx) {
        rc = g_PlayFileEx(BDV_CHANNEL_PLAYER_SKILL, disk);
    } else if (g_PlayFile) {
        rc = g_PlayFile(disk);
    }
    if (rc != 0) {
        LOG_ONCE("skillback: BDV_PlayFile failed");
        return false;
    }
    g_bOwnMcv = true;
    return true;
}

bool BuildLayer() {
    DropLayer();
    if (!g_bHaveRequest || g_szPath[0] == 0) {
        return false;
    }
    if (!get_field() || !get_rm() || !get_gr()) {
        return false;
    }

    const int nLen = static_cast<int>(std::strlen(g_szPath));
    const bool mcv = IsMcvPath(g_szPath, nLen);
    wchar_t wz[SKILLBACK_PATH_MAX + 1];
    for (int i = 0; i <= nLen; ++i) {
        wz[i] = static_cast<wchar_t>(static_cast<unsigned char>(g_szPath[i]));
    }

    IWzPropertyPtr pNode = LoadMarkerNode(mcv, wz);
    if (!pNode) {
        LOG_ONCE("skillback: no 7x5 marker (need Map/Effect VideoLayer)");
        return false;
    }

    IWzVector2DPtr pCenter;
    try {
        pCenter = get_gr()->Getcenter();
    } catch (const _com_error&) {
        pCenter = nullptr;
    }
    if (!pCenter) {
        return false;
    }

    const int nZ = PlaneZ();
    pNode->AddRef();
    pCenter->AddRef();
    auto* pLayer = reinterpret_cast<IWzGr2DLayer*>(
            CallCreateAnimLayer(pNode.GetInterfacePtr(), pCenter.GetInterfacePtr(), nZ));
    if (!pLayer) {
        LOG_ONCE("skillback: CreateAnimLayer failed");
        return false;
    }
    try {
        pLayer->Animate(GA_REPEAT);
        pLayer->visible = 1;
    } catch (const _com_error&) {
        ReleaseLayer(pLayer);
        return false;
    }
    g_pLayer = pLayer;
    if (mcv) {
        PlayMcvFile(g_szPath);
    }
    return true;
}

}  // namespace

void SkillBack_HandlePacket(CInPacket* pPacket) {
    if (!pPacket) {
        return;
    }
    pPacket->SetOffset(pPacket->GetOffset() + 2);
    if (!pPacket->CanRead(1)) {
        return;
    }
    const unsigned char uMode = pPacket->Decode<unsigned char>();
    if (uMode == 0) {
        g_bHaveRequest = false;
        g_szPath[0] = 0;
        g_nDurationMs = 0;
        g_uExpireTick = 0;
        g_bNeedRebuild = true;
        return;
    }
    if (!pPacket->CanRead(2)) {
        return;
    }
    const int nLen = static_cast<int>(pPacket->Decode<unsigned short>());
    if (nLen < 0 || nLen > SKILLBACK_PATH_MAX || !pPacket->CanRead(static_cast<size_t>(nLen) + 4)) {
        return;
    }
    char path[SKILLBACK_PATH_MAX + 1];
    for (int i = 0; i < nLen; ++i) {
        path[i] = static_cast<char>(pPacket->Decode<unsigned char>());
    }
    path[nLen] = 0;
    const int nDuration = pPacket->Decode<int>();
    if (!PathOk(path, nLen)) {
        LOG_ONCE("skillback: rejected path");
        return;
    }
    std::memcpy(g_szPath, path, static_cast<size_t>(nLen) + 1);
    g_nDurationMs = nDuration > 0 ? nDuration : 0;
    g_uExpireTick = g_nDurationMs > 0 ? (GetTickCount() + static_cast<DWORD>(g_nDurationMs)) : 0;
    g_bHaveRequest = true;
    g_bNeedRebuild = true;
}

void SkillBack_Frame() {
    if (g_bHaveRequest && g_nDurationMs > 0 && static_cast<int>(g_uExpireTick - GetTickCount()) <= 0) {
        g_bHaveRequest = false;
        g_szPath[0] = 0;
        g_nDurationMs = 0;
        g_bNeedRebuild = true;
    }
    if (!get_field()) {
        DropLayer();
        return;
    }
    if (g_bNeedRebuild) {
        g_bNeedRebuild = false;
        if (g_bHaveRequest) {
            BuildLayer();
        } else {
            DropLayer();
        }
    }
}

void SkillBack_OnLeaveField() {
    DropLayer();
    g_bHaveRequest = false;
    g_szPath[0] = 0;
    g_nDurationMs = 0;
    g_uExpireTick = 0;
    g_bNeedRebuild = false;
}
