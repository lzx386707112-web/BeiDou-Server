#include "pch.h"
#include "weather.h"
#include "weatherfx.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include <vector>

// Rain splashes on footholds.
//
// While a rain profile is in force this drops short animations onto the ground the
// player can actually see. The art is Client/Data/Effect/WeatherSplash.img, built by
// build_weather_splash.py out of the only genuine water-on-a-surface art the v83
// client owns: the crown of spray at the base of the Ellinia waterfalls. See that
// script for how it is cut out and why nothing else in the client would do.
//
// Layers are anchored the way weatherfx.h describes: no origin, no overlay, plain world
// coordinates.

#define ADDR_PHYS_SPACE          0x00BEBFA0   // CPhysicalSpace2D** , null with no stage
#define ADDR_GET_FH_UNDERNEATH   0x00A45585   // CPhysicalSpace2D::GetFootholdUnderneath
#define ADDR_CREATE_ANIM_LAYER   0x0043EA3E   // the animation-layer factory

// Tuning. All of it is here rather than scattered through the code.
#define SPLASH_UOL_FMT     L"Effect/WeatherSplash.img/rain/%d"
#define SPLASH_VARIANTS    3        // must match VARIANTS in build_weather_splash.py
#define SPLASH_LIFETIME_MS 520      // 5 frames x 80ms, plus slack so nothing pops
#define SPLASH_MAX_LIVE    40       // hard ceiling: protects frame time on a wide view
// At full rain intensity. Raised from 16 after the first in-game look: 16 read as
// occasional drips rather than rainfall. With a 520ms lifetime this holds about 12
// splashes on screen at once, still well under SPLASH_MAX_LIVE, so the ceiling is not
// what limits density and this can go higher again if it still reads thin.
#define SPLASH_PER_SEC     22.4f
#define SPLASH_MARGIN      64       // spawn this far outside the view so edges are not bare
// No SPLASH_Z literal. The engine's layer z is a large scaled value with its own origin
// near -1.07e9 (see Weather_GroundZ), so the old literal 4 drew every splash roughly a
// billion units in FRONT of the map: over the player, the NPCs and the buildings. The
// plane is measured per field: Weather_GroundZ's second output, one in front of the ground
// plane, which is what puts a splash over the puddle it lands in. It shares that plane with
// the snow footprints, which is safe because rain and snow are never on screen together.
// Seat the splash into the surface, for the same reason the deposits need it: the
// foothold line sits a little above the visible top of most platform art, so a sprite
// whose bottom edge lands exactly on it reads as hovering.
#define SPLASH_SURFACE_DROP 4

namespace {

// void** __cdecl CreateAnimLayer(void** ppRet, IWzProperty* pNode, int bFlip,
//                                IWzVector2D* pOrigin, int x, int y,
//                                IWzGr2DLayer* pOverlay, int nZ, int nAlpha, int n)
// Verified at 0x0043EA3E: the callee RELEASES pNode, pOrigin and pOverlay (0x0043EEB5,
// 0x0043EEC6, 0x0043EED7) and AddRefs the layer it hands back (0x0043EE8E). Only pNode
// is passed here, so only pNode is AddRef'd; releasing a null smart pointer is a no-op.
using t_CreateAnimLayer = void**(__cdecl*)(void**, void*, int, void*, int, int,
                                           void*, int, int, int);
const auto CreateAnimLayer = reinterpret_cast<t_CreateAnimLayer>(ADDR_CREATE_ANIM_LAYER);

// CFoothold* __thiscall GetFootholdUnderneath(void* pSpace, int x, int y,
//                                             int* pyFoothold, int yLimit, int dx)
// Returns the foothold at or below y and strictly above yLimit, writing its surface y
// through pyFoothold. Null when the column is empty. `this` is the space itself: the
// function adds the +0x44 index offset on its own. dx is the broad-phase half width and
// is 1 at every stock call site.
using t_GetFootholdUnderneath = void*(__thiscall*)(void*, int, int, int*, int, int);
const auto GetFootholdUnderneath =
        reinterpret_cast<t_GetFootholdUnderneath>(ADDR_GET_FH_UNDERNEATH);

struct Live {
    IWzGr2DLayer* pLayer;
    DWORD         dwExpires;
};

std::vector<Live> g_vLive;
IWzPropertyPtr    g_apNode[SPLASH_VARIANTS];   // the art, resolved once per field
bool              g_bNodesTried = false;
bool              g_bHaveNodes  = false;

float g_fCarry   = 0.0f;    // fractional splashes owed from previous frames
DWORD g_dwLastFrame = 0;    // for the elapsed-time spawn quota
unsigned int g_uRand = 0x1D872B41;

// Written by the 30ms logic tick, read by the per-frame driver. The two run at
// different rates and this is the only thing that crosses between them.
float g_fIntensity = 0.0f;

// xorshift rather than rand(): rand() is a shared global the rest of the client also
// draws from, and perturbing its sequence from a render tick is the kind of thing that
// changes unrelated behaviour in ways nobody connects back to weather.
inline unsigned int NextRand() {
    g_uRand ^= g_uRand << 13;
    g_uRand ^= g_uRand >> 17;
    g_uRand ^= g_uRand << 5;
    return g_uRand;
}

inline int RandRange(int lo, int hi) {
    if (hi <= lo) {
        return lo;
    }
    return lo + (int)(NextRand() % (unsigned int)(hi - lo));
}

// MSVC forbids __try in a function that also owns objects needing unwinding, so every
// raw-pointer read lives in its own POD-only helper.

void* ReadPhysSpace() {
    __try {
        return *reinterpret_cast<void**>(ADDR_PHYS_SPACE);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}

void* CallGetFootholdUnderneath(void* pSpace, int x, int y, int* pyOut, int yLimit) {
    __try {
        return GetFootholdUnderneath(pSpace, x, y, pyOut, yLimit, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}

// The plane splashes land on, measured once per field. Splashes are transient, so a
// missed frame is genuinely invisible; a wrong z is not, so there is no literal fallback.
int  g_nSplashZ    = 0;
bool g_bSplashZSet = false;

bool SplashZ(int* pnZ) {
    if (!g_bSplashZSet) {
        int nAbove = 0;
        if (!Weather_GroundZ(nullptr, &nAbove)) {
            return false;
        }
        g_nSplashZ = nAbove;
        g_bSplashZSet = true;
        LOG_ONCE("weathersplash: splashes go at z %d", g_nSplashZ);
    }
    *pnZ = g_nSplashZ;
    return true;
}

// nZ is passed in rather than measured here, so the caller can bail out BEFORE it AddRefs
// the WZ node. The factory consumes that reference; returning null from inside this
// function after the caller has already taken it orphans it once per attempt.
void* CallCreateAnimLayer(void* pNode, int dx, int dy, int nZ) {
    void* pLayer = nullptr;
    __try {
        CreateAnimLayer(&pLayer, pNode, 0, nullptr, dx, dy, nullptr, nZ, 255, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        pLayer = nullptr;
    }
    return pLayer;
}

// The camera, in world coordinates: IWzGr2D::center, which CAnimationDisplayer::Update
// clips against CField::m_rcViewRange at 0x004378B6. Used ONLY to decide which stretch of
// the map is worth placing on, never to position a layer. See weatherfx.h for why.
bool ReadCamera(int* px, int* py) {
    try {
        IWzGr2DPtr& pGr = get_gr();
        if (!pGr) {
            return false;
        }
        IWzVector2DPtr pCenter = pGr->Getcenter();
        if (!pCenter) {
            return false;
        }
        *px = pCenter->x;
        *py = pCenter->y;
        return true;
    } catch (const _com_error&) {
        return false;
    }
}

void ReleaseLayer(IWzGr2DLayer* pLayer) {
    if (!pLayer) {
        return;
    }
    try { pLayer->visible = 0; } catch (...) {}
    pLayer->Release();
}

// The art is three separate animations so a busy foothold is not one sprite repeated.
// Resolved once and held: GetObjectA on every spawn would be a WZ lookup 16 times a
// second.
void EnsureNodes() {
    if (g_bNodesTried) {
        return;
    }
    g_bNodesTried = true;
    g_bHaveNodes = false;
    if (!get_rm()) {
        return;
    }
    for (int i = 0; i < SPLASH_VARIANTS; ++i) {
        try {
            wchar_t uol[96];
            swprintf_s(uol, SPLASH_UOL_FMT, i);
            g_apNode[i] = get_rm()->GetObjectA(uol).GetUnknown();
            if (!g_apNode[i] || !g_apNode[i]->item[L"0"].GetUnknown()) {
                g_apNode[i] = nullptr;
                LOG_ONCE("weathersplash: %S missing or has no frame 0; splashes off", uol);
                return;
            }
        } catch (const _com_error&) {
            g_apNode[i] = nullptr;
            LOG_ONCE("weathersplash: could not resolve variant %d; splashes off", i);
            return;
        }
    }
    g_bHaveNodes = true;
}

// Put one splash on the ground at a random visible x.
//
// The vertical search runs from the top of the view to the bottom and takes the FIRST
// surface it meets, so a splash lands on the highest platform at that x rather than on
// whatever floor happens to be under the player. That is what rain does.
bool SpawnOne(void* pSpace,
              int nCamX, int nCamY, unsigned int uColor) {
    const int nHalfW = get_screen_width() / 2 + SPLASH_MARGIN;
    const int nHalfH = get_screen_height() / 2 + SPLASH_MARGIN;
    // ONE DROP IN THREE AIMS AT STANDING WATER, the rest fall anywhere.
    //
    // weatherpuddle.cpp's header lists "SPLASHES AIM AT IT" as one of the four ways
    // puddles differ from accumulation, and exported WeatherPuddle_PickWetX for it -- but
    // nothing ever called it, so the two systems were only coincidentally in the same
    // rain. A third is enough to read as connected without starving the rest of the
    // ground: PickWetX answers false whenever nothing is wet, which is every non-rain sky
    // and the whole of the rise before the first puddle lands.
    int x = 0;
    if ((NextRand() % 3u) != 0u || !WeatherPuddle_PickWetX(&x)) {
        x = RandRange(nCamX - nHalfW, nCamX + nHalfW);
    }

    int ySurface = 0;
    void* pFh = CallGetFootholdUnderneath(pSpace, x, nCamY - nHalfH, &ySurface,
                                          nCamY + nHalfH);
    if (!pFh) {
        return false;
    }

    const int nVariant = (int)(NextRand() % SPLASH_VARIANTS);
    IWzProperty* pNode = g_apNode[nVariant].GetInterfacePtr();
    if (!pNode) {
        return false;
    }

    // Before the AddRef, so a failed measurement cannot leak a reference.
    int nZ = 0;
    if (!SplashZ(&nZ)) {
        return false;
    }
    // The factory consumes one reference to each of these three.
    // No origin and no overlay: see the anchoring note in weatherfx.h.
    pNode->AddRef();

    void* pRaw = CallCreateAnimLayer(pNode, x, ySurface + SPLASH_SURFACE_DROP, nZ);
    IWzGr2DLayer* pLayer = reinterpret_cast<IWzGr2DLayer*>(pRaw);
    if (!pLayer) {
        return false;
    }

    try {
        // GA_NORMAL, not GA_REPEAT: a repeating splash would sit on the foothold
        // forever. The engine's own weather uses GA_REPEAT at 0x00640B3C precisely
        // because falling particles are meant to loop.
        pLayer->Animate(GA_NORMAL);
        // Alpha and the night tint in one dword, from the same helper the rain sheets
        // use, so a splash is never brighter than the rain that caused it. Written once
        // at creation rather than per frame: a splash outlives only about 17 ticks and
        // the tint cannot meaningfully change inside that window.
        pLayer->color = uColor;
        pLayer->visible = 1;
    } catch (const _com_error&) {
        ReleaseLayer(pLayer);
        return false;
    }

    g_vLive.push_back({pLayer, GetTickCount() + SPLASH_LIFETIME_MS});
    return true;
}

// Retire splashes whose animation has run out. Wall clock rather than the engine's
// animationState, because the lifetime is known at build time and one comparison is
// cheaper than a vtable call per splash per frame.
void Sweep(DWORD dwNow) {
    for (auto it = g_vLive.begin(); it != g_vLive.end();) {
        if (!it->pLayer || (LONG)(dwNow - it->dwExpires) >= 0) {
            ReleaseLayer(it->pLayer);
            it = g_vLive.erase(it);
        } else {
            ++it;
        }
    }
}

}  // namespace


void WeatherSplash_SetIntensity(float fRainLevel) {
    g_fIntensity = fRainLevel;
}


// A burst of splashes at one spot, for weatherpuddle when the player steps into standing
// water. Three things differ from a rain splash and all three are deliberate:
//
//   - it does not go through the rain intensity. Water thrown up by a boot is caused by
//     the player, not the sky, so it still happens while a puddle is drying under a sky
//     that has already cleared.
//   - the colour is Weather_SceneryColor rather than Weather_RainColor, for the same
//     reason: at the end of a shower the rain colour has faded to nothing and the burst
//     would be invisible.
//   - the surface y is passed in. The caller already knows which puddle was stepped in
//     and where its surface is, and probing again could find a different platform.
void WeatherSplash_Burst(int nWorldX, int nSurfaceY, int nCount, int nSpread) {
    EnsureNodes();
    if (nCount <= 0) {
        return;
    }
    // No readiness flag to test: this module nulls the individual variants it could not
    // resolve, and the per-variant null check inside the loop is the same gate SpawnOne
    // uses.
    if (nSpread < 1) {
        nSpread = 1;
    }
    const unsigned int uColor = Weather_SceneryColor(1.0f);
    for (int i = 0; i < nCount && (int)g_vLive.size() < SPLASH_MAX_LIVE; ++i) {
        const int x = nWorldX - nSpread
                    + (int)(NextRand() % (unsigned int)(2 * nSpread + 1));

        const int nVariant = (int)(NextRand() % SPLASH_VARIANTS);
        IWzProperty* pNode = g_apNode[nVariant].GetInterfacePtr();
        if (!pNode) {
            return;
        }
        // Before the AddRef, so a failed measurement cannot leak a reference.
        int nZ = 0;
        if (!SplashZ(&nZ)) {
            return;
        }
        // No origin and no overlay: see the anchoring note in weatherfx.h.
        pNode->AddRef();
        void* pRaw = CallCreateAnimLayer(pNode, x, nSurfaceY + SPLASH_SURFACE_DROP, nZ);
        IWzGr2DLayer* pLayer = reinterpret_cast<IWzGr2DLayer*>(pRaw);
        if (!pLayer) {
            return;
        }
        try {
            pLayer->Animate(GA_NORMAL);
            pLayer->color = uColor;
            pLayer->visible = 1;
        } catch (const _com_error&) {
            ReleaseLayer(pLayer);
            return;
        }
        g_vLive.push_back({pLayer, GetTickCount() + SPLASH_LIFETIME_MS});
    }
}


// Every rendered frame, from CWvsApp::CallUpdate_hook. Not CMapLoadable::Update: that is
// the 30ms logic tick inside CallUpdate's loop, too coarse to spawn against, and the rate
// here is driven by measured elapsed time rather than an assumed frame period.
void WeatherSplash_Frame() {
    const DWORD dwNow = GetTickCount();
    DWORD dwDelta = g_dwLastFrame ? (dwNow - g_dwLastFrame) : 0;
    g_dwLastFrame = dwNow;
    // A stall (alt-tab, a map load, a breakpoint) must not cash out as a burst.
    if (dwDelta > 100) {
        dwDelta = 100;
    }

    int nCamX = 0, nCamY = 0;
    const bool bHaveCam = ReadCamera(&nCamX, &nCamY);
    Sweep(dwNow);

    const float fRainLevel = g_fIntensity;
    if (fRainLevel <= 0.0f || !bHaveCam || dwDelta == 0) {
        return;
    }
    // Only the skies that actually rain. Snow and blossom land differently and get
    // their own treatment; splashing them would be wrong, not merely unfinished.
    //
    // GATED ON THE FADED LEVEL, NOT ON THE TARGET PROFILE. g_fIntensity is driven by
    // g_fRainLevel, which takes two to four seconds to reach zero after the sky flips,
    // and the rain sheets are still visibly falling for all of it. Testing
    // CurrentProfile().fRain instead cut the splashes dead on the frame the packet landed
    // and left rain falling on completely dry ground for the rest of the fade -- which is
    // the exact behaviour the driver's own comment says the split-driver design avoids.
    // The fRainLevel > 0 test above is now the whole gate; a snow or blossom sky has no
    // rain level to decay, so it still reaches no splashes.
    //
    // The one case this deliberately allows is a rain-to-snow crossfade, where the last
    // of the rain keeps splashing as it fades. That is what the sky is still showing.

    EnsureNodes();
    if (!g_bHaveNodes) {
        return;
    }

    void* pSpace = ReadPhysSpace();
    if (!pSpace) {
        return;
    }

    // The quota is the per-second rate scaled by intensity over the time this frame
    // actually took. The fraction is carried rather than rounded, or a rate below one
    // per frame would floor to zero and nothing would ever spawn.
    g_fCarry += (SPLASH_PER_SEC * fRainLevel) * ((float)dwDelta / 1000.0f);
    int nWant = (int)g_fCarry;
    g_fCarry -= (float)nWant;

    const unsigned int uColor = Weather_RainColor(fRainLevel);
    while (nWant-- > 0) {
        if ((int)g_vLive.size() >= SPLASH_MAX_LIVE) {
            g_fCarry = 0.0f;
            break;
        }
        SpawnOne(pSpace, nCamX, nCamY, uColor);
    }
}


void WeatherSplash_Shutdown() {
    for (Live& live : g_vLive) {
        ReleaseLayer(live.pLayer);
    }
    g_vLive.clear();
    for (int i = 0; i < SPLASH_VARIANTS; ++i) {
        g_apNode[i] = nullptr;
    }
    // The art is re-resolved on the next field because ResMan hands out per-session
    // objects and holding one across a map change is how this module would keep a dead
    // property alive.
    g_bNodesTried = false;
    g_bHaveNodes  = false;
    g_fCarry      = 0.0f;
    g_dwLastFrame = 0;
    // Measured per field, not per session: the next map has its own z band.
    g_bSplashZSet = false;
    g_nSplashZ    = 0;
    // The logic tick sets this every frame it is active. Clearing it here is what stops
    // splashes on a field with no sky, where WeatherFx::Update returns before it would
    // otherwise refresh the value.
    g_fIntensity  = 0.0f;
}
