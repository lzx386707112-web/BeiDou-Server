#include "pch.h"
#include "weather.h"
#include "weatherfx.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include <vector>

// Puddles: the rain half of accumulation.
//
// Art is Client/Data/Effect/WeatherPuddle.img, built by build_weather_puddle.py.
// It is GENERATED rather than borrowed because every water asset in v83 is lit pool
// water seen from the side, which on dirt reads as glowing ice. The one real piece kept
// is the Ellinia surface ripple, used as the moving sheen ON the puddle rather than as
// the puddle itself. See that script for the reasoning.
//
// HOW THIS DIFFERS FROM weatheraccum.cpp, which it otherwise mirrors
// -------------------------------------------------------------------
//   1. A PUDDLE GROWS, IT DOES NOT MULTIPLY. Snow gets denser as it falls; standing
//      water gets wider. So a slot holds exactly one puddle and rain PROMOTES it through
//      three size tiers, rather than stacking a second one beside it.
//   2. IT NEEDS FLAT GROUND. Water does not sit on a slope. The check does not read
//      CFoothold fields: the struct offsets past +0x0C were never verified, and a bad
//      raw deref here would be a crash rather than a cosmetic bug. Instead the surface
//      height is sampled twice more, left and right of the candidate, using the same
//      GetFootholdUnderneath call that found it. Three cheap queries beat one unverified
//      pointer dereference.
//   3. SPLASHES AIM AT IT. WeatherPuddle_PickWetX lets weathersplash bias some of its
//      drops onto standing water, so the two systems look connected instead of
//      coincidental.
//   4. IT CAN BE STEPPED IN. Landing in or walking into a puddle throws water up, through
//      the same splash art. See StepInteraction.

#define ADDR_PHYS_SPACE          0x00BEBFA0
#define ADDR_GET_FH_UNDERNEATH   0x00A45585
#define ADDR_CREATE_ANIM_LAYER   0x0043EA3E

#define PUDDLE_UOL_FMT     L"Effect/WeatherPuddle.img/%d/%d"
#define PUDDLE_TIERS       3
#define PUDDLE_VARIANTS    3       // must match VARIANTS in the build script
#define PUDDLE_MAX         26      // puddles on screen at full level
#define PUDDLE_RISE_MS     75000   // dry to full, in continuous rain
#define PUDDLE_DRY_MS      40000   // full to dry once the rain stops
// Minimum CLEAR GROUND between two puddles, in world px, and the vertical distance below
// which two of them count as sharing a floor.
//
// The spacing is measured against the WIDEST tier, never against the tier a puddle
// currently has, because every puddle eventually grows into that width. A pair spaced
// only far enough to clear their tier-0 sprites merges into one shape the moment both
// promote, and promotion is exactly what sustained rain does to all of them.
//
// THIS REPLACED A 96 px SLOT LATTICE, which is what made heavy rain read as a continuous
// pale strip along a platform instead of as puddles. The lattice failed twice over. Its
// pitch was 96 against a top-tier width of 70, so two neighbours left 26 px of dry ground
// at best -- and each puddle was then placed at a RANDOM offset inside its own slot, so
// two could land 1 px apart and simply overlap. Meanwhile the on-screen window offers far
// fewer slots than the target count (see the saturation note in WeatherPuddle_Frame), so
// in any sustained rain EVERY slot filled and every one of them grew to full width.
#define PUDDLE_MIN_GAP     56
#define PUDDLE_SAME_FLOOR_DY 24
#define PUDDLE_PLACE_PER_S 3.0f
#define PUDDLE_MARGIN      80
#define PUDDLE_CULL_MULT   3
// There is deliberately no PUDDLE_Z literal. These small numbers are not in the same
// space as a real layer z, which the engine builds as a large scaled value with its own
// origin near -1.07e9, so z = 2 put standing water above the entire world and the player
// with it. The z is measured per field by PuddleZ() below, and placement waits for it.
// THE SLOPE PROBE. DO NOT WIDEN PUDDLE_PROBE_DX TO COVER THE SPRITE -- that is the
// obvious fix for the overhang below and it is the wrong one. The two constants are one
// unit: MAX_SLOPE is a tolerance measured PER ARM, so 3 px over 12 is a 1:4
// gradient limit. Widening the arm to 35 while leaving the tolerance at 3 silently
// tightens that to 1:11.7, which strips most eligible ground off any ramp-heavy map and
// makes every flat run shorter than 71 px permanently dry. It would also fail placement
// far more often, and a failed placement falls through to PROMOTING an existing puddle,
// which is the very thing that produces the overhang. Ground EXTENT is a separate
// question from ground SLOPE and gets its own probe, below.
#define PUDDLE_PROBE_DX    12      // how far either side the ground is sampled
#define PUDDLE_MAX_SLOPE   3       // px of height change tolerated per arm, over PROBE_DX
// THE EXTENT PROBE. The slope test above authorises a sprite up to 70 px wide after
// checking 24 px of ground, so a puddle could be placed 13 px from the end of a platform,
// pass, and then grow until 22 px of water hung in the air past the lip. These two ask
// the other question: does the platform actually REACH as far as this sprite draws?
//
// EDGE_PAD puts the probe just outside the sprite, because the art has no alpha ramp --
// the outermost column is inked at 140/255 -- so the last drawn pixel needs ground under
// it, not merely beside it.
//
// EDGE_DY is deliberately looser than PUDDLE_MAX_SLOPE and must stay that way. It is an
// EXISTENCE test, not a second flatness test: the slope test already caps the gradient at
// 1:4, which over the widest extent probe (35 + 2 = 37 px) permits a legitimate 9.25 px
// of fall. Anything below 10 here would re-impose a tighter slope limit at long range and
// reject ramps the slope test just accepted.
#define PUDDLE_EDGE_PAD    2
#define PUDDLE_EDGE_DY     10
// Seat the puddle into the ground, same reason as ACCUM_SURFACE_DROP: standing water
// lies IN a surface, and the foothold line sits slightly above the visible platform top.
// A touch deeper than the deposits, because a puddle should read as a depression.
#define PUDDLE_SURFACE_DROP 6

// Stepping in one.
#define PUDDLE_FOOT_TOL     14      // px between the feet and the water that counts as in it
#define PUDDLE_ENTER_BURST  6       // splashes thrown by arriving in a puddle
#define PUDDLE_WALK_BURST   2       // and by each stride taken while already in it
#define PUDDLE_WALK_STRIDE  26      // px of travel between those
#define PUDDLE_BURST_SPREAD 11      // px either side of the foot that water is thrown

namespace {

using t_CreateAnimLayer = void**(__cdecl*)(void**, void*, int, void*, int, int,
                                           void*, int, int, int);
const auto CreateAnimLayer = reinterpret_cast<t_CreateAnimLayer>(ADDR_CREATE_ANIM_LAYER);

using t_GetFootholdUnderneath = void*(__thiscall*)(void*, int, int, int*, int, int);
const auto GetFootholdUnderneath =
        reinterpret_cast<t_GetFootholdUnderneath>(ADDR_GET_FH_UNDERNEATH);

struct Puddle {
    IWzGr2DLayer* pLayer;
    int nWorldX;
    int nWorldY;
    int nTier;
    int nVariant;
    // The widest tier the ground under this spot can actually hold, measured ONCE at
    // placement. Footholds are static WZ data and WeatherPuddle_Shutdown runs on every
    // field change, so this can never go stale; caching it costs a few probes per
    // accepted placement instead of two per puddle per frame forever.
    int nMaxTier;
};

std::vector<Puddle>         g_vLive;
IWzPropertyPtr              g_apNode[PUDDLE_TIERS][PUDDLE_VARIANTS];
bool                        g_bNodesTried = false;
bool                        g_bNodesOk    = false;

float g_fLevel   = 0.0f;
float g_fCarry   = 0.0f;
bool  g_bSeeded  = false;   // level seeded from the server's sky age for this wet spell
int   g_nCatchUp = 0;

// The measured water plane, and whether it has been measured for THIS field.
//
// These were function-local statics inside PuddleZ, which meant the z was measured once
// per SESSION: the first weather map the player visited chose the plane for every map
// after it, however differently that map stacked its art. Same shape of bug as the one
// that made every lamp share one map's depth.
int   g_nPuddleZ    = 0;
bool  g_bPuddleZSet = false;
// Last colour dword applied across every live puddle. Puddles are in none of the vectors
// weather.cpp re-tints, so this module follows the night curve and the lightning itself.
unsigned int g_uPuddleColor = 0;
DWORD g_dwLastFrame = 0;
unsigned int g_uRand = 0x2545F491;

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

void* CallGetFh(void* pSpace, int x, int y, int* pyOut, int yLimit) {
    __try {
        return GetFootholdUnderneath(pSpace, x, y, pyOut, yLimit, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}

// On the ground: over the map's TILES. Not under every object -- see Weather_GroundZ,
// which measures that no such plane exists on most maps -- so a puddle can draw in front
// of a low map object. It is still behind the player, who is a world entity and sits in
// the object z band well above the tile stack.
//
// False until the field's art has been measured. There is deliberately NO literal
// fallback: the engine's layer z sits near -1.07e9, so any small number is about a
// billion units in front of the whole map, and a layer's z is fixed at creation, so one
// frame of falling back leaves water floating over the player for its whole 115 s life.
// Placing nothing for a frame or two is invisible; placing it wrong is not.
bool PuddleZ(int* pnZ) {
    if (!g_bPuddleZSet) {
        int nGround = 0;
        if (!Weather_GroundZ(&nGround, nullptr)) {
            return false;
        }
        g_nPuddleZ = nGround;
        g_bPuddleZSet = true;
        LOG_ONCE("weatherpuddle: water goes at z %d", g_nPuddleZ);
    }
    *pnZ = g_nPuddleZ;
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

void EnsureNodes() {
    if (g_bNodesTried) {
        return;
    }
    g_bNodesTried = true;
    g_bNodesOk = false;
    if (!get_rm()) {
        return;
    }
    for (int t = 0; t < PUDDLE_TIERS; ++t) {
        for (int v = 0; v < PUDDLE_VARIANTS; ++v) {
            try {
                wchar_t uol[128];
                swprintf_s(uol, PUDDLE_UOL_FMT, t, v);
                g_apNode[t][v] = get_rm()->GetObjectA(uol).GetUnknown();
                if (!g_apNode[t][v] || !g_apNode[t][v]->item[L"0"].GetUnknown()) {
                    LOG_ONCE("weatherpuddle: %S missing or empty; puddles off", uol);
                    return;
                }
            } catch (const _com_error&) {
                LOG_ONCE("weatherpuddle: could not resolve tier %d variant %d; puddles off", t, v);
                return;
            }
        }
    }
    g_bNodesOk = true;
}

int HalfWidthFor(int nTier);

// Would a puddle here end up touching one that already exists?
//
// Both sides are measured at each puddle's OWN attainable full growth -- nMaxTier, not
// the tier it happens to be wearing -- so the answer cannot change later when either of
// them promotes. That is the whole point: a test against current widths lets the ground
// pass as sparse and then quietly fill in.
//
// Using the attainable tier rather than a flat PUDDLE_TIERS-1 is what stops the extent
// probe costing density. A puddle capped at tier 0 by a short ledge is never going to be
// 70 px wide, and reserving 126 px around it would leave narrow ledges both drier AND
// emptier than before. Two tier-2-capable puddles still reserve 35 + 35 + 56 = 126, so
// the anti-merge guarantee on open ground is exactly what it was.
//
// The floor test is what keeps this from thinning multi-level maps. Two puddles at the
// same x on platforms a screen apart never read as one shape, so only puddles within
// PUDDLE_SAME_FLOOR_DY of each other -- close enough that the eye joins them into a
// single wet stretch -- are held apart. A short flight of steps counts as one floor,
// which is the conservative direction.
bool TooClose(int nWorldX, int nWorldY, int nMaxTier) {
    for (const Puddle& p : g_vLive) {
        const int nMinDx = HalfWidthFor(nMaxTier) + HalfWidthFor(p.nMaxTier)
                         + PUDDLE_MIN_GAP;
        const int dy = (nWorldY > p.nWorldY) ? (nWorldY - p.nWorldY)
                                             : (p.nWorldY - nWorldY);
        if (dy > PUDDLE_SAME_FLOOR_DY) {
            continue;
        }
        const int dx = (nWorldX > p.nWorldX) ? (nWorldX - p.nWorldX)
                                             : (p.nWorldX - nWorldX);
        if (dx < nMinDx) {
            return true;
        }
    }
    return false;
}

// Ground flat enough to hold water? Sampled, not read off the CFoothold struct: see the
// header comment. Also rejects a candidate whose neighbours sit on a DIFFERENT platform,
// since that shows up as a large height difference too.
bool GroundIsFlat(void* pSpace, int x, int yFrom, int yTo, int ySurface) {
    int yL = 0, yR = 0;
    if (!CallGetFh(pSpace, x - PUDDLE_PROBE_DX, yFrom, &yL, yTo)) {
        return false;
    }
    if (!CallGetFh(pSpace, x + PUDDLE_PROBE_DX, yFrom, &yR, yTo)) {
        return false;
    }
    const int dL = (yL > ySurface) ? (yL - ySurface) : (ySurface - yL);
    const int dR = (yR > ySurface) ? (yR - ySurface) : (ySurface - yR);
    return dL <= PUDDLE_MAX_SLOPE && dR <= PUDDLE_MAX_SLOPE;
}

// Does the platform reach as far as this tier's sprite draws?
//
// GroundIsFlat answers "is this level". This answers "is there still ground out there",
// and conflating the two is what let a 70 px sprite sit on 24 px of validated ground.
//
// Past the end of a platform the client's lookup does NOT simply fail: it rescans the
// column and returns the floor BELOW if one spans that x. So the height comparison is the
// real gate, not the null check -- a floor a screen down blows past PUDDLE_EDGE_DY at
// once, and a lip with a riser 10 px or more below it rejects too, which is correct
// because water does not lie flat across a step.
bool GroundHoldsTier(void* pSpace, int x, int yFrom, int yTo, int ySurface, int nTier) {
    const int nProbe = HalfWidthFor(nTier) + PUDDLE_EDGE_PAD;
    int yL = 0, yR = 0;
    // TEST THE RETURN, never yL/yR on their own: the callee writes *pyOut = yLimit even
    // when it finds nothing, so a not-found read hands back the bottom of the search
    // window and would look like ground at the far edge of the map.
    if (!CallGetFh(pSpace, x - nProbe, yFrom, &yL, yTo)) {
        return false;
    }
    if (!CallGetFh(pSpace, x + nProbe, yFrom, &yR, yTo)) {
        return false;
    }
    const int dL = (yL > ySurface) ? (yL - ySurface) : (ySurface - yL);
    const int dR = (yR > ySurface) ? (yR - ySurface) : (ySurface - yR);
    return dL <= PUDDLE_EDGE_DY && dR <= PUDDLE_EDGE_DY;
}

IWzGr2DLayer* MakeLayer(int nTier, int nVariant,
                        int dx, int dy) {
    IWzProperty* pNode = g_apNode[nTier][nVariant].GetInterfacePtr();
    if (!pNode) {
        return nullptr;
    }
    // Before the AddRef, so a failed measurement cannot leak a reference.
    int nZ = 0;
    if (!PuddleZ(&nZ)) {
        return nullptr;
    }
    // No origin and no overlay: see the anchoring note in weatherfx.h.
    pNode->AddRef();
    IWzGr2DLayer* pLayer =
            reinterpret_cast<IWzGr2DLayer*>(CallCreateAnimLayer(pNode, dx, dy, nZ));
    if (!pLayer) {
        return nullptr;
    }
    try {
        // GA_REPEAT, unlike everything else in this system: the sheen drifting across a
        // puddle is a LOOP, not a one shot. A puddle that played its ripple once and
        // froze would look like a decal.
        pLayer->Animate(GA_REPEAT);
        pLayer->color = Weather_SceneryColor(1.0f);
        pLayer->visible = 1;
    } catch (const _com_error&) {
        ReleaseLayer(pLayer);
        return nullptr;
    }
    return pLayer;
}

bool PlaceOne(void* pSpace,
              int nCamX, int nCamY) {
    const int nHalfW = get_screen_width() / 2 + PUDDLE_MARGIN;
    const int nHalfH = get_screen_height() / 2 + PUDDLE_MARGIN;
    const int yFrom = nCamY - nHalfH;
    const int yTo   = nCamY + nHalfH;

    // Twelve attempts rather than eight. The spacing rule rejects far more candidates
    // than the slot rule did, and a rejection costs one walk of a list at most PUDDLE_MAX
    // long, so the extra attempts are nearly free and keep placement responsive while
    // there is still room. Once there is not, all twelve fail and the caller falls
    // through to promoting an existing puddle, which is the intended path.
    for (int attempt = 0; attempt < 12; ++attempt) {
        // Uniform across the window, not one pick per cell of a lattice. The lattice
        // pinned every puddle centre to a global 96 px grid, which put a regular pitch on
        // the result as well -- half of why a wet platform read as a repeating pattern
        // rather than as scattered water.
        const int x = nCamX - nHalfW + (int)(NextRand() % (unsigned int)(2 * nHalfW));
        int ySurface = 0;
        if (!CallGetFh(pSpace, x, yFrom, &ySurface, yTo)) {
            continue;
        }
        if (!GroundIsFlat(pSpace, x, yFrom, yTo, ySurface)) {
            continue;
        }
        // How wide is this spot ever allowed to get? Measured now, once. A spot that
        // cannot hold even the smallest sprite is not a puddle site at all.
        if (!GroundHoldsTier(pSpace, x, yFrom, yTo, ySurface, 0)) {
            continue;
        }
        int nMaxTier = 0;
        while (nMaxTier + 1 < PUDDLE_TIERS &&
               GroundHoldsTier(pSpace, x, yFrom, yTo, ySurface, nMaxTier + 1)) {
            ++nMaxTier;
        }
        // AFTER the ground probes: the spacing test has to know which floor the candidate
        // landed on, and how wide it can grow, before it can work out whose neighbour it
        // is and how much room the pair will eventually need.
        if (TooClose(x, ySurface + PUDDLE_SURFACE_DROP, nMaxTier)) {
            continue;
        }
        const int nVariant = (int)(NextRand() % PUDDLE_VARIANTS);
        const int y = ySurface + PUDDLE_SURFACE_DROP;
        IWzGr2DLayer* pLayer = MakeLayer(0, nVariant, x, y);
        if (!pLayer) {
            return false;
        }
        // nWorldY stores the DRAWN y, so a promotion rebuilds at the same seated height
        // rather than popping back up to the bare foothold line.
        g_vLive.push_back({pLayer, x, y, 0, nVariant, nMaxTier});
        return true;
    }
    return false;
}

// Grow one puddle a tier. Rebuilt rather than resized because a layer's canvas set is
// fixed at creation; there is no "swap the animation" on IWzGr2DLayer.
bool PromoteOne(int nTargetTier) {
    for (Puddle& p : g_vLive) {
        if (p.nTier >= nTargetTier || p.nTier + 1 >= PUDDLE_TIERS) {
            continue;
        }
        // The ground under this puddle was measured once, at placement. A puddle sitting
        // near a lip simply stops growing instead of draping its new width over the drop.
        //
        // CONTINUE, NEVER return false. The caller breaks its whole per-frame allowance
        // on a false, so a single capped puddle at the head of the list would stall
        // growth for every other puddle on screen, every frame, and the rain would
        // visibly stop developing. false has to keep meaning "nothing anywhere can grow".
        if (p.nTier + 1 > p.nMaxTier) {
            continue;
        }
        IWzGr2DLayer* pNew = MakeLayer(p.nTier + 1, p.nVariant, p.nWorldX, p.nWorldY);
        if (!pNew) {
            return false;      // a real failure: stop for this frame
        }
        ReleaseLayer(p.pLayer);
        p.pLayer = pNew;
        p.nTier += 1;
        return true;
    }
    return false;
}

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

void CullDistant(int nCamX) {
    const int nLimit = (get_screen_width() / 2) * PUDDLE_CULL_MULT;
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

// Half the baked width of a tier, READ OFF THE ART rather than computed. The canvases
// are 30 / 48 / 70 wide with origin.x = w / 2, so the half extents are 15 / 24 / 35.
//
// It used to be 15 + nTier * 10, which is right at tiers 0 and 2 and one pixel wide at
// tier 1 -- close enough to look correct and wrong in the direction that matters, since
// four separate systems measure the water through this one function: the spacing rule,
// the extent probe, the "player is standing in it" test, and the scatter that aims one
// rain drop in three at a puddle. A formula that happens to fit two of three data points
// desyncs all four the next time a tier width changes.
//
// Tier 2 MUST stay 35: the 126 px separation and the saturation arithmetic in the frame
// loop are both derived from it. The origin sits at w / 2 on an even canvas, so the true
// extents are very slightly asymmetric (-15/+14, -24/+23, -35/+34); the extra pixel is
// left on the near side deliberately rather than being split.
int HalfWidthFor(int nTier) {
    static_assert(PUDDLE_TIERS == 3, "kHalf tracks the tier count");
    static const int kHalf[PUDDLE_TIERS] = { 15, 24, 35 };
    return kHalf[nTier];
}

bool g_bWasInWater  = false;
int  g_nLastWalkX   = 0;

// Stepping in a puddle throws water up.
//
// ONE transition test covers both cases worth having. Landing from a jump and walking in
// from the side both move the player from "not in water" to "in water", because the
// height check that decides "in water" is only satisfied while standing on the puddle's
// own surface. There is no separate airborne test and none is needed.
void StepInteraction() {
    int nUserX = 0, nUserY = 0;
    if (g_vLive.empty() || !Weather_ReadPlayerPos(&nUserX, &nUserY)) {
        g_bWasInWater = false;
        return;
    }

    const Puddle* pIn = nullptr;
    for (const Puddle& p : g_vLive) {
        if (!p.pLayer) {
            continue;
        }
        const int nHalf = HalfWidthFor(p.nTier);
        if (nUserX < p.nWorldX - nHalf || nUserX > p.nWorldX + nHalf) {
            continue;
        }
        const int dy = (nUserY > p.nWorldY) ? (nUserY - p.nWorldY) : (p.nWorldY - nUserY);
        if (dy <= PUDDLE_FOOT_TOL) {
            pIn = &p;
            break;
        }
    }

    if (!pIn) {
        g_bWasInWater = false;
        return;
    }

    // nWorldY is the DRAWN y, already seated into the ground by PUDDLE_SURFACE_DROP.
    // The burst seats itself the same way, so hand it the real surface or the water is
    // thrown up from twice as deep.
    const int nSurface = pIn->nWorldY - PUDDLE_SURFACE_DROP;

    if (!g_bWasInWater) {
        g_bWasInWater = true;
        g_nLastWalkX = nUserX;
        WeatherSplash_Burst(nUserX, nSurface, PUDDLE_ENTER_BURST, PUDDLE_BURST_SPREAD);
        return;
    }

    const int d = (nUserX > g_nLastWalkX) ? (nUserX - g_nLastWalkX)
                                          : (g_nLastWalkX - nUserX);
    if (d >= PUDDLE_WALK_STRIDE) {
        g_nLastWalkX = nUserX;
        WeatherSplash_Burst(nUserX, nSurface, PUDDLE_WALK_BURST, PUDDLE_BURST_SPREAD);
    }
}

}  // namespace


// For weathersplash: a world x with standing water on it, so some drops land in a puddle
// instead of everywhere but. False when there is nothing wet.
bool WeatherPuddle_PickWetX(int* px) {
    if (!px || g_vLive.empty()) {
        return false;
    }
    const Puddle& p = g_vLive[NextRand() % g_vLive.size()];
    if (!p.pLayer) {
        return false;
    }
    // Anywhere across the puddle, not dead centre, or every splash lines up.
    const int nHalf = HalfWidthFor(p.nTier);
    *px = p.nWorldX - nHalf + (int)(NextRand() % (unsigned int)(2 * nHalf + 1));
    return true;
}


void WeatherPuddle_Frame() {
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

    // Before the sky is consulted. A puddle can be stepped in for as long as it exists,
    // including the whole of the drying stretch after the rain has stopped.
    StepInteraction();

    // Puddles FOLLOW THE TINT, for the same reason deposits do: their colour was written
    // once at creation, so they alone stayed dark through every lightning flash that
    // brightened the rest of the map, and puddles created up to 115 s apart across dusk
    // sat side by side at visibly different brightnesses. Guarded on the value, so a
    // settled frame costs no COM calls.
    //
    // ABOVE every early return, not at the end of the function. Three of the returns below
    // (level exhausted, over target, and "not wet") are exactly the ones taken all through
    // the 40 s dry-out, which is when a puddle lives longest and when dusk is most likely
    // to move underneath it. The sibling block in weatheraccum.cpp is placed the same way
    // and for the same reason.
    {
        const unsigned int uWant = Weather_SceneryColor(1.0f);
        if (uWant != g_uPuddleColor) {
            g_uPuddleColor = uWant;
            for (Puddle& p : g_vLive) {
                if (!p.pLayer) continue;
                try { p.pLayer->color = uWant; } catch (const _com_error&) {}
            }
        }
    }

    const unsigned char uSky = Weather::CurrentSky();
    const bool bWet = (uSky == Weather::SKY_RAIN || uSky == Weather::SKY_STORM);

    // "I see no puddles" has several possible causes that look identical in game -- wrong
    // sky, no nodes, no physics space, nothing placed, placed somewhere invisible -- and
    // guessing between them has cost a session each time. Say which it is, once per sky,
    // so a single visit answers it.
    {
        static unsigned char s_uSaid = 0xFF;
        if (s_uSaid != uSky) {
            s_uSaid = uSky;
            LOG_ONCE_PER_ID((int)uSky,
                "weatherpuddle: sky %u, wet %d, level %.2f, live %u, nodes %d, space %d",
                (unsigned)uSky, bWet ? 1 : 0, g_fLevel, (unsigned)g_vLive.size(),
                g_bNodesOk ? 1 : 0, ReadPhysSpace() ? 1 : 0);
        }
    }
    // Seeded once per wet spell from the server's sky age, so walking into a map that
    // has been raining for ten minutes shows standing water rather than dry ground.
    if (bWet && !g_bSeeded && g_fLevel <= 0.0f) {
        g_bSeeded = true;
        const int nSec = Weather::SkyElapsedSec();
        if (nSec > 0) {
            g_fLevel = (float)(nSec * 1000) / (float)PUDDLE_RISE_MS;
            if (g_fLevel > 1.0f) g_fLevel = 1.0f;
            g_nCatchUp = (int)(g_fLevel * PUDDLE_MAX);
        }
    }
    if (!bWet) {
        g_bSeeded = false;
    }

    if (bWet) {
        g_fLevel += (float)dwDelta / (float)PUDDLE_RISE_MS;
        if (g_fLevel > 1.0f) g_fLevel = 1.0f;
    } else {
        g_fLevel -= (float)dwDelta / (float)PUDDLE_DRY_MS;
        if (g_fLevel < 0.0f) g_fLevel = 0.0f;
    }

    if (g_fLevel <= 0.0f) {
        if (!g_vLive.empty()) {
            for (Puddle& p : g_vLive) {
                ReleaseLayer(p.pLayer);
            }
            g_vLive.clear();
        }
        g_fCarry = 0.0f;
        return;
    }

    const int nTarget = (int)(g_fLevel * PUDDLE_MAX);
    if ((int)g_vLive.size() > nTarget) {
        if (bHaveCam) {
            RemoveFurthest(nCamX);
        }
        return;
    }
    if (!bHaveCam || !bWet) {
        return;
    }

    EnsureNodes();
    if (!g_bNodesOk) {
        return;
    }
    void* pSpace = ReadPhysSpace();
    if (!pSpace) {
        return;
    }

    // Tier rises with the level, so early rain leaves scattered small puddles and a long
    // storm turns them into wide ones rather than simply more of them.
    int nTargetTier = (int)(g_fLevel * PUDDLE_TIERS);
    if (nTargetTier >= PUDDLE_TIERS) {
        nTargetTier = PUDDLE_TIERS - 1;
    }

    g_fCarry += PUDDLE_PLACE_PER_S * ((float)dwDelta / 1000.0f);
    int nWant = (int)g_fCarry;
    g_fCarry -= (float)nWant;
    if (g_nCatchUp > 0) {
        const int nBurst = (g_nCatchUp < 10) ? g_nCatchUp : 10;
        nWant += nBurst;
        g_nCatchUp -= nBurst;
    }
    while (nWant-- > 0) {
        // PlaceOne's RESULT drives the fallthrough, not the count alone, and under the
        // spacing rule that matters more than it used to. Random placement into a window
        // 2*nHalfW wide against a 126 px minimum separation jams at roughly
        // 0.75 * 2*nHalfW / 126 puddles per floor, which at 800x600 is about six -- far
        // fewer than PUDDLE_MAX (26) and fewer than the 17 that first makes tier 2 the
        // target. So size < nTarget stays true indefinitely in sustained rain. Without
        // the fallthrough the else-if would never be evaluated and the widest tier would
        // be unreachable, which is what once made this file's own headline claim -- that
        // a puddle GROWS rather than multiplying -- false on the default resolution.
        // Falling through on a failed placement is what lets a saturated window promote
        // instead, and promotion is now the ONLY way the ground gets wetter once it is
        // spaced full. That is the intended shape: heavier rain means WIDER puddles with
        // clear ground between them, never a longer chain of them.
        if ((int)g_vLive.size() < nTarget && PlaceOne(pSpace, nCamX, nCamY)) {
            continue;
        }
        if (!PromoteOne(nTargetTier)) {
            break;      // nothing left to place or grow this frame
        }
    }

}


void WeatherPuddle_Shutdown() {
    for (Puddle& p : g_vLive) {
        ReleaseLayer(p.pLayer);
    }
    g_vLive.clear();
    for (int t = 0; t < PUDDLE_TIERS; ++t) {
        for (int v = 0; v < PUDDLE_VARIANTS; ++v) {
            g_apNode[t][v] = nullptr;
        }
    }
    g_bNodesTried = false;
    g_bNodesOk    = false;
    g_fLevel      = 0.0f;
    g_fCarry      = 0.0f;
    g_bSeeded     = false;
    // Or the first puddle entered on the next map is treated as one already being stood in.
    g_bWasInWater = false;
    g_nLastWalkX  = 0;
    g_nCatchUp    = 0;
    // Re-measure on the next map. Its art may stack nothing like this one's.
    g_bPuddleZSet = false;
    g_nPuddleZ    = 0;
    g_uPuddleColor = 0;   // next field re-tints from scratch
    g_dwLastFrame = 0;
}
