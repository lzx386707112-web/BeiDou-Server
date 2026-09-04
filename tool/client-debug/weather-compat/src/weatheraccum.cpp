#include "pch.h"
#include "weather.h"
#include "weatherfx.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include <climits>
#include <vector>

// Snow, leaves and petals settling on footholds the longer a sky holds.
//
// Art is Client/Data/Effect/WeatherAccum.img, built by build_weather_accum.py out
// of the same particle sprites that fall, squashed flat and dimmed so a deposit lies on
// the ground instead of standing on its edge. Each variant is its own single-frame
// directory because CreateAnimLayer treats a node's numbered children as FRAMES, so
// pointing it at a multi-sprite weather node would animate one deposit through all of
// them.
//
// THE MODEL
// ---------
// A single level, 0 to 1, rises while an accumulating sky is in force and decays when it
// is not. The number of deposits that SHOULD exist is level * ACCUM_MAX. Every frame the
// live count is nudged one step toward that number, which makes growth and melt fall out
// of the same two lines and keeps the count self correcting after a cull.
//
// Placement is by SLOT, not by random x. The visible world is divided into fixed-width
// columns and a deposit claims one; a second deposit in a claimed slot stacks slightly
// above and offset. Purely random x looks like litter, because clumps and gaps appear at
// the wrong scale. Slots also give an O(n) way to ask what is already covered.
//
// WHAT IT DELIBERATELY DOES NOT DO
//   - synchronise deposit POSITIONS between players. The sky is server authoritative and
//     so is its AGE (Weather::SkyElapsedSec, from LP 0x373D), so everyone entering a map
//     that has been snowing for ten minutes sees ten minutes of drifts at the same
//     density. Where each drift sits is still chosen locally, so two players see
//     different arrangements. That is indistinguishable in play and costs one int on the
//     wire instead of a per-map deposit list.

// FOOTPRINTS
// ----------
// Walking through settled snow leaves a trail of hollows, and clears the drift where the
// player trod. Clearing frees the slot, so the ordinary placement loop refills it: snow
// grows back over a track without a single line of code that knows that is what it is
// doing. Prints are part of THIS module rather than their own for that reason; they need
// the slot list, and the slot list is here.
//
// Snow only. A footprint in fallen leaves would have to disturb them rather than dent
// them, which is a different effect, and petals are too sparse to walk through.

#define ADDR_PHYS_SPACE          0x00BEBFA0
#define ADDR_GET_FH_UNDERNEATH   0x00A45585
#define ADDR_CREATE_ANIM_LAYER   0x0043EA3E

#define ACCUM_UOL_FMT      L"Effect/WeatherAccum.img/%s/%d"
#define ACCUM_MAX          70      // deposits on screen at full level
#define ACCUM_RISE_MS      90000   // bare to full, in continuous weather
#define ACCUM_MELT_MS      25000   // full to bare once the sky changes. Faster than it built.
#define ACCUM_SLOT_W       26      // world px per slot
#define ACCUM_STACK_MAX    3       // deposits allowed in one slot
#define ACCUM_STACK_LIFT   2       // px each stacked deposit sits above the one below
// Pixels to seat a deposit DOWN into the surface it landed on.
//
// The sprite origin is bottom centre, so placing at the reported surface y puts its
// bottom edge exactly on the foothold line, and in game that reads as hovering: real
// settled snow sits slightly INTO whatever it is lying on, and the foothold line is
// itself a little above the visible top of most platform art. Sinking a few pixels
// removes the gap and makes the deposit look like it belongs to the surface.
#define ACCUM_SURFACE_DROP 5
#define ACCUM_PLACE_PER_S  14.0f   // how fast deposits appear, independent of the target
#define ACCUM_MARGIN       80      // place this far outside the view
// How far either side of a candidate column to check for ground before settling there,
// and how big a height difference counts as a step rather than a slope. 14 px is a
// little wider than a deposit sprite's half width, so a deposit never overhangs; 10 px
// of drop is steeper than any walkable ramp in stock data but well under a real ledge.
#define ACCUM_EDGE_PROBE   14
#define ACCUM_EDGE_STEP    10
#define ACCUM_CULL_MULT    3       // cull past this many half-screens from the player
// No ACCUM_Z literal. The engine's layer z is a large scaled value with its own origin
// near -1.07e9 (see Weather_GroundZ), so the old literal 3 put every drift and every
// footprint roughly a billion units in FRONT of the whole map: settled snow painted over
// the tiles, the objects, the NPCs and the player. The plane is measured per field and
// placement waits for the measurement, because a layer's z is fixed at creation.

#define FOOT_KIND          L"print"
#define FOOT_VARIANTS      3
#define FOOT_STRIDE        22      // world px of travel between prints. Roughly one stride.
#define FOOT_LIFE_MS       11000   // how long a hollow lasts before the drift has filled it
#define FOOT_FADE_MS       3500    // of that life, the closing stretch spent fading out
#define FOOT_MAX           20      // a trail this long, then the oldest goes early
#define FOOT_GROUND_TOL    8       // px from the surface that still counts as standing on it
#define FOOT_PROBE_UP      6       // start the ground probe this far above the feet

namespace {

using t_CreateAnimLayer = void**(__cdecl*)(void**, void*, int, void*, int, int,
                                           void*, int, int, int);
const auto CreateAnimLayer = reinterpret_cast<t_CreateAnimLayer>(ADDR_CREATE_ANIM_LAYER);

using t_GetFootholdUnderneath = void*(__thiscall*)(void*, int, int, int*, int, int);
const auto GetFootholdUnderneath =
        reinterpret_cast<t_GetFootholdUnderneath>(ADDR_GET_FH_UNDERNEATH);

// Which art a sky settles as. SKY_STORM and SKY_RAIN are absent on purpose: rain gets
// splashes, and a puddle system is a different feature.
const wchar_t* KindForSky(unsigned char uSky) {
    switch (uSky) {
        case Weather::SKY_SNOW:
        case Weather::SKY_BLIZZARD: return L"snow";
        case Weather::SKY_LEAVES:   return L"leaf";
        case Weather::SKY_BLOSSOM:  return L"petal";
        default:                    return nullptr;
    }
}

struct Deposit {
    IWzGr2DLayer* pLayer;
    int  nWorldX;
    int  nSlot;
    int  nDepth;      // 0 for the first in a slot
    // Half this sprite's width, so a footprint can ask whether it is standing ON this pile
    // rather than merely near it. Read from the canvas at placement rather than assumed:
    // the snow variants are 19, 14 and 24 px wide, so one number for all three would be
    // wrong for two of them whichever number was picked.
    int  nHalfW;
};

// A hollow the player left. Not a Deposit: it expires on a clock of its own rather than
// on the melt level, and it must never be counted toward the deposit target.
struct Print {
    IWzGr2DLayer* pLayer;
    int   nWorldX;
    DWORD dwBorn;
    // Last colour dword written, so an unchanged one is not re-sent every frame.
    unsigned int  uColor;
};

std::vector<Deposit>        g_vLive;
std::vector<Print>          g_vPrints;
std::vector<IWzPropertyPtr> g_vNodes;    // the variants of the CURRENT kind
std::vector<IWzPropertyPtr> g_vFootNodes;
bool                        g_bFootOk  = false;
int                         g_nLastPrintX = INT_MIN;
const wchar_t*              g_sKind    = nullptr;   // what g_vNodes holds
// What the LEVEL and the live deposits are made of, which is a different question from
// what the node cache currently holds and must not share a variable with it.
//
// g_sKind is rewritten by EnsureNodes on any frame where more deposits are wanted, which
// includes frames in the middle of a kind change. Using it as the melt discriminator
// meant one such frame flipped the discriminator to the NEW kind, the melt turned back
// into growth, and the old kind's deposits were stranded on the ground for the rest of
// the visit while the new kind piled up among them.
const wchar_t*              g_sLevelKind = nullptr;
// Last colour dword applied across every live deposit. Deposits are not in any of the
// vectors weather.cpp re-tints, so this module has to follow the night curve itself.
unsigned int                g_uDepositColor = 0;
bool                        g_bNodesOk = false;

float g_fLevel   = 0.0f;
float g_fCarry   = 0.0f;
const wchar_t* g_sSeededFor = nullptr;   // the kind the level was seeded for
int   g_nCatchUp = 0;                    // deposits still owed from a seed
DWORD g_dwLastFrame = 0;
unsigned int g_uRand = 0x7F4A7C15;

inline unsigned int NextRand() {
    g_uRand ^= g_uRand << 13;
    g_uRand ^= g_uRand >> 17;
    g_uRand ^= g_uRand << 5;
    return g_uRand;
}


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

// The two planes this module draws on, measured once per field. Deposits lie ON the
// ground; prints sit one step in front so a hollow draws over the drift it is pressed
// into. File-scope rather than function statics: function statics would measure once per
// SESSION and carry the first map's z onto every map after it.
int  g_nAccumZ    = 0;
int  g_nFootZ     = 0;
bool g_bAccumZSet = false;

bool AccumZ(int* pnDeposit, int* pnPrint) {
    if (!g_bAccumZSet) {
        int nGround = 0, nAbove = 0;
        if (!Weather_GroundZ(&nGround, &nAbove)) {
            return false;
        }
        g_nAccumZ = nGround;
        g_nFootZ  = nAbove;
        g_bAccumZSet = true;
        LOG_ONCE("weatheraccum: drifts at z %d, prints at %d", g_nAccumZ, g_nFootZ);
    }
    if (pnDeposit) *pnDeposit = g_nAccumZ;
    if (pnPrint)   *pnPrint   = g_nFootZ;
    return true;
}

// nZ < 0 is the ordinary case in this space, so "not measured yet" cannot be signalled by
// a sentinel value. The caller passes the plane it wants explicitly.
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

// Resolve every variant of one kind. Reloaded whenever the kind changes, because a
// blossom map that turns snowy must stop dropping petals.
void EnsureNodes(const wchar_t* sKind) {
    if (g_bNodesOk && g_sKind == sKind) {
        return;
    }
    g_vNodes.clear();
    g_sKind = sKind;
    g_bNodesOk = false;
    if (!sKind || !get_rm()) {
        return;
    }
    for (int i = 0; i < 32; ++i) {
        IWzPropertyPtr p;
        try {
            wchar_t uol[128];
            swprintf_s(uol, ACCUM_UOL_FMT, sKind, i);
            p = get_rm()->GetObjectA(uol).GetUnknown();
            if (!p || !p->item[L"0"].GetUnknown()) {
                break;
            }
        } catch (const _com_error&) {
            break;
        }
        g_vNodes.push_back(p);
    }
    g_bNodesOk = !g_vNodes.empty();
    if (!g_bNodesOk) {
        LOG_ONCE("weatheraccum: Effect/WeatherAccum.img/%S has no variants; "
                 "accumulation off for this kind", sKind);
    } else {
        DEBUG_MESSAGE("weatheraccum: %S has %u variants", sKind, (unsigned)g_vNodes.size());
    }
}

int SlotOf(int nWorldX) {
    // Floor division, not truncation: at negative x, truncation folds two slots into one
    // and the left half of every map accumulates at double density.
    return (nWorldX >= 0) ? (nWorldX / ACCUM_SLOT_W)
                          : -(((-nWorldX) + ACCUM_SLOT_W - 1) / ACCUM_SLOT_W);
}

int DepthInSlot(int nSlot) {
    int n = 0;
    for (const Deposit& d : g_vLive) {
        if (d.nSlot == nSlot) {
            ++n;
        }
    }
    return n;
}

bool PlaceOne(void* pSpace,
              int nCamX, int nCamY) {
    const int nHalfW = get_screen_width() / 2 + ACCUM_MARGIN;
    const int nHalfH = get_screen_height() / 2 + ACCUM_MARGIN;

    // A few tries, because a slot may be full or a column may have no foothold at all.
    for (int attempt = 0; attempt < 6; ++attempt) {
        const int nSlot = SlotOf(nCamX - nHalfW)
                        + (int)(NextRand() % (unsigned int)((2 * nHalfW) / ACCUM_SLOT_W + 1));
        const int nDepth = DepthInSlot(nSlot);
        if (nDepth >= ACCUM_STACK_MAX) {
            continue;
        }
        // Jitter within the slot so a filled stretch does not read as a picket fence.
        const int x = nSlot * ACCUM_SLOT_W + (int)(NextRand() % ACCUM_SLOT_W);

        int ySurface = 0;
        if (!CallGetFootholdUnderneath(pSpace, x, nCamY - nHalfH, &ySurface,
                                       nCamY + nHalfH)) {
            continue;
        }

        // Keep off the ends of a platform.
        //
        // A deposit is a sprite about 20 px wide seated on a single probed column, so one
        // placed at the last pixel of a foothold hangs half of itself over the drop. The
        // same goes for the pixel either side of a step or a gap between two platforms.
        //
        // Probing the neighbouring columns settles it without needing the foothold list:
        // a column is safe only if both its neighbours also have ground, at close to the
        // same height. That catches the true end of a platform (no ground at all next
        // door) and a sharp step (ground, but a long way down) with the same test, and it
        // uses the client's own foothold lookup so it cannot disagree with the placement
        // probe about where the surface is.
        bool bEdge = false;
        for (int side = -1; side <= 1 && !bEdge; side += 2) {
            int yNeighbour = 0;
            if (!CallGetFootholdUnderneath(pSpace, x + side * ACCUM_EDGE_PROBE,
                                           nCamY - nHalfH, &yNeighbour,
                                           nCamY + nHalfH)) {
                bEdge = true;       // nothing there: this is the lip
            } else {
                const int d = yNeighbour - ySurface;
                if (d > ACCUM_EDGE_STEP || d < -ACCUM_EDGE_STEP) {
                    bEdge = true;   // a step, so the sprite would straddle two levels
                }
            }
        }
        if (bEdge) {
            continue;
        }

        IWzProperty* pNode = g_vNodes[NextRand() % g_vNodes.size()].GetInterfacePtr();
        if (!pNode) {
            return false;
        }
        // Before the AddRef, so a failed measurement cannot leak a reference.
        int nZ = 0;
        if (!AccumZ(&nZ, nullptr)) {
            return false;   // field art not measured yet; place nothing this frame
        }
    // No origin and no overlay: see the anchoring note in weatherfx.h.
        pNode->AddRef();

        // Seated into the surface, then lifted per stack depth. The drop dominates at
        // depth 0 so a lone deposit never floats, and the lift still gives a pile some
        // relief instead of every sprite landing on the same line.
        const int y = ySurface + ACCUM_SURFACE_DROP - nDepth * ACCUM_STACK_LIFT;
        void* pRaw = CallCreateAnimLayer(pNode, x, y, nZ);
        IWzGr2DLayer* pLayer = reinterpret_cast<IWzGr2DLayer*>(pRaw);
        if (!pLayer) {
            return false;
        }
        try {
            // GA_NORMAL on a one frame animation: it draws that frame and stops. GA_REPEAT
            // would restart a one frame loop forever for no benefit.
            pLayer->Animate(GA_NORMAL);
            pLayer->color = Weather_SceneryColor(1.0f);
            pLayer->visible = 1;
        } catch (const _com_error&) {
            ReleaseLayer(pLayer);
            return false;
        }
        // How wide this deposit actually is. A failure here falls back to half a slot,
        // which is the old behaviour for this one deposit rather than for all of them.
        int nSpriteHalfW = ACCUM_SLOT_W / 2;
        try {
            IWzCanvasPtr c = pLayer->Getcanvas();
            if (c && c->width > 0) {
                nSpriteHalfW = c->width / 2;
            }
        } catch (const _com_error&) {
        }
        g_vLive.push_back({pLayer, x, nSlot, nDepth, nSpriteHalfW});
        return true;
    }
    return false;
}

// Remove the deposit that is furthest from the player, so melting eats the edges of the
// drift first and culling frees the slots nobody can see.
void RemoveFurthest(int nCamX) {
    if (g_vLive.empty()) {
        return;
    }
    size_t iWorst = 0;
    int nWorst = -1;
    for (size_t i = 0; i < g_vLive.size(); ++i) {
        const int d = (g_vLive[i].nWorldX > nCamX)
                    ? (g_vLive[i].nWorldX - nCamX) : (nCamX - g_vLive[i].nWorldX);
        if (d > nWorst) {
            nWorst = d;
            iWorst = i;
        }
    }
    ReleaseLayer(g_vLive[iWorst].pLayer);
    g_vLive.erase(g_vLive.begin() + iWorst);
}

// Deposits far behind the player are invisible and would otherwise sit in the live list
// forever, costing a slot and a layer each. Dropping them frees the slot too, so walking
// back re-accumulates rather than showing the same drift again.
void CullDistant(int nCamX) {
    const int nLimit = (get_screen_width() / 2) * ACCUM_CULL_MULT;
    for (auto it = g_vLive.begin(); it != g_vLive.end();) {
        const int d = (it->nWorldX > nCamX) ? (it->nWorldX - nCamX)
                                               : (nCamX - it->nWorldX);
        if (!it->pLayer || d > nLimit) {
            ReleaseLayer(it->pLayer);
            it = g_vLive.erase(it);
        } else {
            ++it;
        }
    }
}

// ---------------------------------------------------------------------- footprints

bool g_bFootTried    = false;
bool g_bWasGrounded  = false;

// Prints sit one plane ABOVE the deposits, so a hollow draws on top of the drift it is
// pressed into rather than fighting it for the same z. That plane is AccumZ()'s second
// output. Both come from Weather_GroundZ, which is over the map's TILES rather than under
// every object: on most maps no plane satisfies both, so settled snow can draw in front of
// a low map object.
//
// It shares a plane with the rain splashes, which is safe because the two can never be on
// screen together: splashes belong to rain and prints belong to snow.

// Is the player standing ON a drift -- not near one, on one?
//
// This used to accept any deposit in the neighbouring SLOT, which at 26 px a slot let a
// print appear up to 39 px from the nearest snow: a trail across bare ground with drifts
// somewhere off to the side. The test is now the sprite's own footprint, so a print can
// only land inside the horizontal span of a pile that is actually there.
//
// The print is anchored at the player's x, and the widest print variant is 17 px, so its
// centre being over snow does still leave a couple of px of toe over bare ground where the
// player is at the very lip of a small drift. That is the right amount of slack -- the
// alternative, requiring the whole print to be covered, is unsatisfiable against the 14 px
// snow variant, which is narrower than every print.
bool DepositUnder(int nWorldX) {
    // Only snow takes a print: leaves would scatter rather than dent, and petals never lie
    // thick enough. Keyed on the KIND the live deposits were built from and not on the
    // current sky, because a drift outlives the sky that dropped it and the drift is what
    // the print goes into.
    if (g_sLevelKind == nullptr || wcscmp(g_sLevelKind, L"snow") != 0) {
        return false;
    }
    for (const Deposit& d : g_vLive) {
        const int dx = (nWorldX > d.nWorldX) ? (nWorldX - d.nWorldX) : (d.nWorldX - nWorldX);
        if (dx <= d.nHalfW) {
            return true;
        }
    }
    return false;
}

void EnsureFootNodes() {
    if (g_bFootTried) {
        return;
    }
    g_bFootTried = true;
    if (!get_rm()) {
        g_bFootTried = false;      // no ResMan yet: try again next frame
        return;
    }
    for (int i = 0; i < FOOT_VARIANTS; ++i) {
        IWzPropertyPtr p;
        try {
            wchar_t uol[128];
            swprintf_s(uol, ACCUM_UOL_FMT, FOOT_KIND, i);
            p = get_rm()->GetObjectA(uol).GetUnknown();
            if (!p || !p->item[L"0"].GetUnknown()) {
                break;
            }
        } catch (const _com_error&) {
            break;
        }
        g_vFootNodes.push_back(p);
    }
    g_bFootOk = !g_vFootNodes.empty();
    if (!g_bFootOk) {
        LOG_ONCE("weatheraccum: Effect/WeatherAccum.img/print has no variants; "
                 "footprints off. Run build_weather_accum.py");
    } else {
        DEBUG_MESSAGE("weatheraccum: print has %u variants", (unsigned)g_vFootNodes.size());
    }
}

void ClearPrints() {
    for (Print& p : g_vPrints) {
        ReleaseLayer(p.pLayer);
    }
    g_vPrints.clear();
    g_nLastPrintX = INT_MIN;
    g_bWasGrounded = false;
}

void StepFootprints(void* pSpace, DWORD dwNow) {
    // Age out, and fade the ones near the end of their life so a trail dissolves into
    // the drift rather than blinking away a print at a time.
    for (auto it = g_vPrints.begin(); it != g_vPrints.end();) {
        const DWORD dwAge = dwNow - it->dwBorn;
        if (!it->pLayer || dwAge >= FOOT_LIFE_MS) {
            ReleaseLayer(it->pLayer);
            it = g_vPrints.erase(it);
            continue;
        }
        float fAlpha = 1.0f;
        if (dwAge > FOOT_LIFE_MS - FOOT_FADE_MS) {
            fAlpha = (float)(FOOT_LIFE_MS - dwAge) / (float)FOOT_FADE_MS;
        }
        // Written only when it actually changes. A print spends about seven of its eleven
        // seconds at alpha 1.0, during which this was issuing an identical COM property
        // write per print per frame. This is the project's tint rule (re-assert while
        // CHANGING, not every frame); the alpha rule that demands an unconditional
        // per-frame write applies to tiled layers carrying the engine's own per-tile
        // animator, which these do not.
        const unsigned int uWant = Weather_SceneryColor(fAlpha);
        if (uWant != it->uColor) {
            try {
                it->pLayer->color = uWant;
                it->uColor = uWant;
            } catch (const _com_error&) {
            }
        }
        ++it;
    }

    // A cheap early out before the position and foothold probes. The real gate is
    // DepositUnder below -- a drift has to exist and be underfoot -- and these two only
    // save the work of looking when there cannot be one.
    //
    // On permanently snowy ground the sky test is skipped: El Nath's drifts persist and
    // are worth printing in whether or not it happens to be snowing at this moment.
    if (!pSpace || g_vLive.empty()) {
        // Existing prints still age out above; there is simply nothing to print in.
        g_bWasGrounded = false;
        return;
    }

    int nUserX = 0, nUserY = 0;
    if (!Weather_ReadPlayerPos(&nUserX, &nUserY)) {
        g_bWasGrounded = false;
        return;
    }

    int ySurface = 0;
    const bool bFound = CallGetFootholdUnderneath(pSpace, nUserX, nUserY - FOOT_PROBE_UP,
                                                  &ySurface, nUserY + FOOT_GROUND_TOL) != nullptr;
    const int nGap = bFound ? ((ySurface > nUserY) ? (ySurface - nUserY) : (nUserY - ySurface))
                            : (FOOT_GROUND_TOL + 1);
    const bool bGrounded = bFound && nGap <= FOOT_GROUND_TOL;
    // A landing prints regardless of how far the player travelled, because that is the
    // moment the effect is most worth having and a drop straight down moves no x at all.
    const bool bLanded = bGrounded && !g_bWasGrounded;
    g_bWasGrounded = bGrounded;
    if (!bGrounded) {
        return;
    }
    if (!bLanded && g_nLastPrintX != INT_MIN) {
        const int d = (nUserX > g_nLastPrintX) ? (nUserX - g_nLastPrintX)
                                               : (g_nLastPrintX - nUserX);
        if (d < FOOT_STRIDE) {
            return;
        }
    }

    // A print goes IN something, and that something has to be a drift that is really
    // there and really under the player.
    //
    // El Nath and Rien used to be exempt on the argument that their tiles ARE snow, so a
    // print made sense anywhere on them. That is a defensible reading of the world and the
    // wrong reading of the request: prints are wanted in the accumulated piles and nowhere
    // else, which on those two maps now means the drifts rather than the whole ground.
    // Accumulation still runs there -- the server forces SNOW over both -- so they get
    // trails, just along the snow that has actually settled.
    if (!DepositUnder(nUserX)) {
        return;
    }

    EnsureFootNodes();
    if (!g_bFootOk) {
        return;
    }

    IWzProperty* pNode = g_vFootNodes[NextRand() % g_vFootNodes.size()].GetInterfacePtr();
    if (!pNode) {
        return;
    }
    int nFootZ = 0;
    if (!AccumZ(nullptr, &nFootZ)) {
        return;   // field art not measured yet
    }
    // No origin and no overlay: see the anchoring note in weatherfx.h.
    pNode->AddRef();
    void* pRaw = CallCreateAnimLayer(pNode, nUserX, ySurface + ACCUM_SURFACE_DROP, nFootZ);
    IWzGr2DLayer* pLayer = reinterpret_cast<IWzGr2DLayer*>(pRaw);
    if (!pLayer) {
        return;
    }
    const unsigned int uColor = Weather_SceneryColor(1.0f);
    try {
        pLayer->Animate(GA_NORMAL);
        pLayer->color = uColor;
        pLayer->visible = 1;
    } catch (const _com_error&) {
        ReleaseLayer(pLayer);
        return;
    }
    if ((int)g_vPrints.size() >= FOOT_MAX) {
        ReleaseLayer(g_vPrints.front().pLayer);   // push_back order is age order
        g_vPrints.erase(g_vPrints.begin());
    }
    g_vPrints.push_back({pLayer, nUserX, dwNow, uColor});
    g_nLastPrintX = nUserX;
}

}  // namespace


void WeatherAccum_Frame() {
    const DWORD dwNow = GetTickCount();
    DWORD dwDelta = g_dwLastFrame ? (dwNow - g_dwLastFrame) : 0;
    g_dwLastFrame = dwNow;
    if (dwDelta > 100) {
        dwDelta = 100;
    }

    int nCamX = 0, nCamY = 0;
    const bool bHaveCam = ReadCamera(&nCamX, &nCamY);
    if (bHaveCam) {
        CullDistant(nCamX);
    }

    const unsigned char uSky = Weather::CurrentSky();
    const wchar_t* sKind = KindForSky(uSky);

    // Same reason as weatherpuddle's: "no accumulation" has several causes that look the
    // same from inside the game, and the most common one is simply a sky that does not
    // settle anything. Name it rather than making the next session a guess.
    {
        static unsigned char s_uSaid = 0xFF;
        if (s_uSaid != uSky) {
            s_uSaid = uSky;
            LOG_ONCE_PER_ID(0x1000 + (int)uSky,
                "weatheraccum: sky %u, settles as %ls, level %.2f, live %u, nodes %d",
                (unsigned)uSky, sKind ? sKind : L"(nothing)", g_fLevel,
                (unsigned)g_vLive.size(), g_bNodesOk ? 1 : 0);
        }
    }

    // The level rises only while the sky is one that settles, and melts otherwise. A
    // change of KIND melts the old deposits rather than recolouring them: snow does not
    // turn into petals.

// Seed the level from how long the server says this sky has held, so a player walking
// into a map that has been going for ten minutes sees ten minutes of it rather than
// bare ground. Done ONCE per sky, when the level is still zero: after that the local
// clock owns it, or a re-broadcast would keep yanking the level back.
//
// Seeding also arms a CATCH UP allowance, because the normal placement rate would take
// several seconds to fill a fully seeded level and the player would watch it appear.
    if (sKind != nullptr && g_sSeededFor != sKind && g_fLevel <= 0.0f) {
        g_sSeededFor = sKind;
        const int nSec = Weather::SkyElapsedSec();
        if (nSec > 0) {
            g_fLevel = (float)(nSec * 1000) / (float)ACCUM_RISE_MS;
            if (g_fLevel > 1.0f) g_fLevel = 1.0f;
            g_nCatchUp = (int)(g_fLevel * ACCUM_MAX);
        }
    }

    // Keyed on what the LEVEL is made of, never on the node cache: see g_sLevelKind.
    const bool bGrowing = (sKind != nullptr)
                       && (g_sLevelKind == nullptr || g_sLevelKind == sKind);
    if (bGrowing) {
        g_sLevelKind = sKind;
        g_fLevel += (float)dwDelta / (float)ACCUM_RISE_MS;
        if (g_fLevel > 1.0f) g_fLevel = 1.0f;
    } else {
        g_fLevel -= (float)dwDelta / (float)ACCUM_MELT_MS;
        if (g_fLevel < 0.0f) g_fLevel = 0.0f;
    }

    // Deposits FOLLOW THE TINT. A deposit's colour used to be written once, at placement,
    // so a drift built at noon stayed lit at noon while every tile, object and back around
    // it was multiplied down to the region's night colour; a drift built across dusk came
    // out visibly mottled, each sprite frozen at the instant it landed.
    //
    // Guarded on the value, not written unconditionally: this is the project's tint rule
    // (re-assert while CHANGING). A settled frame costs one Weather_SceneryColor call and
    // no COM at all, and a changing frame costs at most ACCUM_MAX writes.
    {
        const unsigned int uWant = Weather_SceneryColor(1.0f);
        if (uWant != g_uDepositColor) {
            g_uDepositColor = uWant;
            for (Deposit& d : g_vLive) {
                if (!d.pLayer) continue;
                try { d.pLayer->color = uWant; } catch (const _com_error&) {}
            }
        }
    }

    // Before the melt short circuit, so a trail keeps ageing out after the snow has gone
    // rather than being frozen on the ground by an early return.
    StepFootprints(ReadPhysSpace(), dwNow);

    if (g_fLevel <= 0.0f) {
        // Fully melted: drop everything and let the next sky pick its own art.
        if (!g_vLive.empty()) {
            for (Deposit& d : g_vLive) {
                ReleaseLayer(d.pLayer);
            }
            g_vLive.clear();
        }
        g_sKind = sKind;
        g_sLevelKind = nullptr;   // nothing on the ground belongs to any kind now
        g_bNodesOk = false;
        g_fCarry = 0.0f;
        g_sSeededFor = nullptr;   // the next sky seeds itself afresh
        g_nCatchUp = 0;
        return;
    }

    const int nTarget = (int)(g_fLevel * ACCUM_MAX);
    if ((int)g_vLive.size() > nTarget) {
        if (bHaveCam) {
            RemoveFurthest(nCamX);
        }
        return;
    }
    if (!bHaveCam || !sKind || (int)g_vLive.size() >= nTarget) {
        return;
    }
    // A MELTING field never loads the incoming kind's nodes. Reaching EnsureNodes here
    // would repoint the node cache mid-melt, and on a sparse map (where PlaceOne fails
    // often enough to hold live below target permanently) that is reachable on the very
    // first frame after a sky change.
    if (!bGrowing) {
        return;
    }

    EnsureNodes(sKind);
    if (!g_bNodesOk) {
        return;
    }
    void* pSpace = ReadPhysSpace();
    if (!pSpace) {
        return;
    }

    // Deposits appear at a fixed rate rather than all at once, so a drift builds visibly
    // instead of popping into existence the moment the level ticks up.
    g_fCarry += ACCUM_PLACE_PER_S * ((float)dwDelta / 1000.0f);
    int nWant = (int)g_fCarry;
    g_fCarry -= (float)nWant;
    int nBurst = 0;
    if (g_nCatchUp > 0) {
        // Bounded per frame so a full seed costs a few frames rather than one hitch.
        nBurst = (g_nCatchUp < 25) ? g_nCatchUp : 25;
        nWant += nBurst;
        g_nCatchUp -= nBurst;
    }
    while (nWant > 0 && (int)g_vLive.size() < nTarget) {
        if (!PlaceOne(pSpace, nCamX, nCamY)) {
            // Stop retrying on a map where placement is failing. On a small map most of
            // the placement band falls off the field, so re-running the whole allowance
            // every frame is pure cost that never reaches the target.
            break;
        }
        --nWant;
    }
    // GIVE THE UNSPENT CATCH-UP BACK. The burst is debited above, before the loop runs, so
    // without this a single transient PlaceOne failure permanently destroyed up to 24 of
    // that frame's 25 seeded placements, and a player walking into a map that had been
    // snowing for ten minutes got a fraction of the drift the seed asked for. Only the
    // catch-up portion is refunded; the ordinary per-second rate is a rate, and a missed
    // frame of it is genuinely gone.
    if (nBurst > 0 && nWant > 0) {
        const int nBack = (nWant < nBurst) ? nWant : nBurst;
        g_nCatchUp += nBack;
    }
}


// How deep the settled accumulation is, 0 to 1, whatever kind it is made of.
//
// DIAGNOSTIC ONLY. weathermove used to read this and now reads WeatherAccum_SnowLevel()
// below, because this one rises for leaves and petals too.
float WeatherAccum_Level() {
    return g_fLevel;
}

// The same level, but ONLY when what is lying on the ground is snow.
//
// weathermove drives the physics table from this. The unqualified level above cannot be
// used for that: settled leaves and cherry petals raise it just as snow does, so a GM
// switching a blossom map to snow made the ground maximally slippery on the same frame,
// before a single flake had settled.
float WeatherAccum_SnowLevel() {
    if (g_sLevelKind == nullptr || wcscmp(g_sLevelKind, L"snow") != 0) {
        return 0.0f;
    }
    return g_fLevel;
}


void WeatherAccum_Shutdown() {
    for (Deposit& d : g_vLive) {
        ReleaseLayer(d.pLayer);
    }
    g_vLive.clear();
    g_vNodes.clear();
    g_sKind = nullptr;
    g_sLevelKind = nullptr;
    g_uDepositColor = 0;   // next field re-tints from scratch
    g_bNodesOk = false;
    g_fLevel = 0.0f;
    g_fCarry = 0.0f;
    g_dwLastFrame = 0;
    // Footprints go too. A trail belongs to a map, and the ResMan nodes are dropped
    // because the field teardown is also where a Data reload would land.
    ClearPrints();
    g_vFootNodes.clear();
    g_bFootOk = false;
    g_bFootTried = false;
    // The z planes belong to the field that was measured, not to the session: the next
    // map has its own tiles and objects and must be measured again.
    g_bAccumZSet = false;
    g_nAccumZ = 0;
    g_nFootZ  = 0;
}
