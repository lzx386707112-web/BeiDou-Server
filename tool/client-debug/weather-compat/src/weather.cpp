#include "pch.h"
#include "hook.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/packet.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include "weather.h"
#include "weatherfx.h"
#include "lamps.h"
#include <atomic>
#include <climits>
#include <cmath>
#include <vector>
#include <cstdio>

// Server-authoritative day/night, on every map that has a sky.
//
// WHAT CHANGED FROM THE PACKAGE THIS WAS PORTED FROM, and why:
//
//  1. NO HOTKEYS. F6/F7/F8 polling is gone. State arrives as LP 0x373D from
//     server/weather/WeatherPackets.java, so every player in the world sees the
//     same sky. The client advances its own clock between packets, so a dropped
//     packet costs drift, not correctness.
//
//  2. NO HARDCODED MAP LIST. g_aWeatherFieldIDs (14 entries, half of them test
//     maps) is replaced by FieldHasSky(), a data rule that reads the field's own
//     property. See its comment for the rule and its measured accuracy.
//
//  3. NO INJECTED nightDesert BACKDROP. The original hid each map's own sky behind
//     15 injected desert-sky layers and tinted only what sat in front. That is
//     wrong once this runs everywhere: it pastes a desert over Ellinia, and it
//     costs the contiguity requirement, the hand-maintained NIGHT_INJECT_COUNT,
//     the HILL_Z promotion, and the tall-view seam snap. Instead the map's OWN
//     sky backs are tinted like everything else, so every map darkens into its
//     own night. The cost is the starfield, which belongs to a per-map profile
//     rather than to every map in the game (IMPLEMENTATION.md).
//
//  4. ONE COLOUR WRITE. IWzGr2DLayer::color carries alpha AND a multiply tint in
//     one dword, so the night tint and the weather fade are now combined in
//     Argb() instead of fighting over the same property.
//
// What is kept verbatim, because it is all load-bearing and hard-won:
//   - the single IWzGr2D::CreateLayer capture hook and its scoped-flag routing
//   - RAII ScopedSet, so a thrown loader cannot leave a capture flag stuck on
//   - the RestoreBack re-arm (resolution / zoom rebuilds do not pass LoadMap)
//   - re-asserting layer colour EVERY frame (the engine's per-tile animator
//     overwrites it otherwise)
//   - exact cx/cy tile sizing, to avoid the double-blended seam lines

// The sky table. One row per profile id; see weather_profiles.inc for the field
// meanings and for why the ORDER is load-bearing.
// constexpr, not const: the name anchors below have to read sName at compile time.
static constexpr Weather::Profile kProfiles[] = {
#include "weather_profiles.inc"
};
static_assert(_countof(kProfiles) == Weather::SKY_COUNT,
              "weather_profiles.inc must have exactly one row per Weather::Sky id");

// A row count alone does not catch the likeliest mistake, which is INSERTING a sky in
// the middle: add an enum value and a row together and the count still matches while
// every id above the insertion silently shifts, so the client renders storms as
// blizzards and the server's numbering no longer means anything. Anchoring three rows
// by name makes that a compile error instead of a mystery.
constexpr bool kNameEq(const wchar_t* a, const wchar_t* b) {
    return (*a == *b) && (*a == 0 || kNameEq(a + 1, b + 1));
}
static_assert(kNameEq(kProfiles[Weather::SKY_CLEAR].sName, L"clear"),   "profile row 0 moved");
static_assert(kNameEq(kProfiles[Weather::SKY_SNOW].sName, L"snow"),     "profile row 2 moved");
static_assert(kNameEq(kProfiles[Weather::SKY_STORM].sName, L"storm"),   "profile row 4 moved");
static_assert(kNameEq(kProfiles[Weather::SKY_BLOSSOM].sName, L"blossom"), "profile row 7 moved");
static_assert(kNameEq(kProfiles[Weather::SKY_SANDSTORM].sName, L"sandstorm"), "profile row 8 moved");

// Regional colour curves. The server sends ONLY the palette id; every RGB value is
// client-owned in weather_palettes.inc so visual tuning never changes gameplay code.
struct Palette {
    const wchar_t* sName;
    unsigned char uDuskR, uDuskG, uDuskB;
    unsigned char uNightR, uNightG, uNightB;
};
static constexpr Palette kPalettes[] = {
#include "weather_palettes.inc"
};
static constexpr int PALETTE_TABLE_COUNT = (int)_countof(kPalettes);
static_assert(PALETTE_TABLE_COUNT == Weather::PALETTE_COUNT,
              "weather_palettes.inc must match WeatherPalette.java");
static_assert(kNameEq(kPalettes[0].sName, L"el_nath"), "palette row 0 moved");
static_assert(kNameEq(kPalettes[19].sName, L"henesys"), "palette row 19 moved");
static_assert(kNameEq(kPalettes[26].sName, L"default"), "palette row 26 moved");

// NPCs and rain get a fraction of the scenery darkening: NPCs so they stay
// readable, rain because a pitch-black sheet reads as a hole in the sky.
#define NPC_TINT_SCALE     0.45f
#define RAIN_TINT_SCALE    0.55f

// Night level moves this much per frame when it is chasing a jump (a GM command,
// or the first packet after a long stall). Normal clock motion is far slower than
// this and is never rate-limited.
#define NIGHT_CATCHUP_STEP 0.015f

// ---------------------------------------------------------------- world state
//
// Written by the LP 0x373D handler on the RECEIVE thread, read by Update() on the
// main thread. Plain atomics rather than a mutex: these are four independent
// scalars and a reader that catches a half-applied update sees one stale field
// for one frame, which is invisible.

static std::atomic<int>           g_nNetMinuteOfDay{0};
static std::atomic<int>           g_nNetMsPerGameMinute{10000};
static std::atomic<unsigned char> g_uNetSky{Weather::SKY_CLEAR};
static std::atomic<bool>          g_bNetSnap{false};
static std::atomic<bool>          g_bNetFrozen{false};
// Testing only: hide the map's own sky, leaving the moon and the starfields.
static std::atomic<bool>          g_bNetBareSky{false};
// How long the current sky has held, as the server last reported it, plus the local tick
// at which that report arrived. Two values rather than one so the age keeps advancing
// between broadcasts, which are up to a minute apart.
// LEGACY, and nothing reads it. The wire still carries a seconds field with a 3600 s cap
// (WeatherService.ELAPSED_CAP_SEC), but Weather::SkyElapsedSec() derives its answer from
// the UNCAPPED millisecond field appended later in the same packet, so the cap bounds
// nothing. Kept because the field is POSITIONAL: dropping it has to happen on both sides
// in one change or the palette, elapsedMs and token reads all shift.
static std::atomic<int>           g_nNetSkyElapsedSec{0};
// The base age (high 32 bits, milliseconds) and the local tick it was stamped against
// (low 32 bits) PACKED INTO ONE ATOMIC, so a reader can never pair a fresh age with a
// stale stamp. As two atomics a torn read inflated the reported age by the whole gap
// between broadcasts, which is enough to put this client's lightning in a different
// window from everyone else's for that frame.
static std::atomic<unsigned long long> g_uNetSkyAge{0};
// Seconds of rainbow left as the server last reported it, and when that arrived. Same
// two-value shape as the sky age and for the same reason: broadcasts are up to a minute
// apart, so a single stored value would sit still between them.
static std::atomic<int>           g_nNetRainbowSec{0};
static std::atomic<DWORD>         g_dwNetRainbowStamp{0};
// The region's night colour, from LP 0x373D. Defaults to the neutral tint, which is row 0
// of weather_profiles.inc, so a server that does not send it renders exactly as before.
static std::atomic<unsigned char> g_uNetTintR{0x4A};
static std::atomic<unsigned char> g_uNetTintG{0x5A};
static std::atomic<unsigned char> g_uNetTintB{0x8C};
// Palette is appended to the existing packet, so a server that predates it continues
// to drive the legacy RGB endpoint path below.
static std::atomic<unsigned char> g_uNetPalette{0};
static std::atomic<bool>          g_bNetPalette{false};
static std::atomic<unsigned int>  g_uNetSkyToken{0};
static std::atomic<bool>          g_bNetDirty{false};
static std::atomic<bool>          g_bHasWorldState{false};

// main-thread copies.
//
// The clock starts at NOON, not at zero. Zero is midnight, and because the field
// hooks deliberately do not wait for the first packet (see LoadMap_hook), a zero
// default would render the first map of every session at full night and then fade
// to day when the packet landed. Noon is the neutral value: NightFromMinute(720)
// is exactly 0, so the pre-packet state is an untinted stock map.
static float        g_fMinuteOfDay     = 720.0f;  // advanced locally between packets
static int          g_nMsPerGameMinute = 10000;
static unsigned char g_uSky            = Weather::SKY_CLEAR;
static float        g_fNight           = 0.0f;   // 0 day .. 1 night, what is rendered
static unsigned int g_tLastUpdate      = 0;      // GetTickCount at the previous frame

// True when the last colour written was the identity (full day). Lets the per-frame
// re-assert be skipped entirely while it is daytime, which is most of the time: the
// loop is otherwise a COM property write per tile, per object, per back and per NPC,
// every frame, writing 0xFFFFFFFF over 0xFFFFFFFF. One final apply still runs on the
// way INTO neutral, so nothing is left half-tinted.
static bool         g_bNeutral         = true;

// The PROFILE's own contribution is chased, not applied on the frame the packet lands.
// Cloud and rain alpha already faded, but the darkness boost and the tint colour did
// not, so switching clear -> storm used to snap the whole map dark and cold in one
// frame while the clouds rolled in gently behind it. These chase the active profile at
// its own fFadeStep, so the entire sky arrives together.
static float g_fBoost = 0.0f;
static float g_fTintR = 255.0f, g_fTintG = 255.0f, g_fTintB = 255.0f;
static bool  g_bTintPrimed = false;   // first frame snaps rather than fading up from white

// region * profile / neutral, per channel, clamped. The neutral is row 0 of the profile
// table, which is what every region tint was chosen against.
static float Lerp(float a, float b, float t) {
    return a + (b - a) * t;
}

// At the first third of the clock's transition a palette reaches its coloured dusk;
// the rest of the transition travels to its deep-night endpoint. This gives Ariant a
// sunset and El Nath a pale blue shoulder instead of every map merely dimming linearly.
static void PaletteTint(float* pr, float* pg, float* pb) {
    if (!g_bNetPalette.load()) {
        *pr = (float)g_uNetTintR.load();
        *pg = (float)g_uNetTintG.load();
        *pb = (float)g_uNetTintB.load();
        return;
    }
    unsigned char u = g_uNetPalette.load();
    if (u >= Weather::PALETTE_COUNT) {
        u = Weather::PALETTE_DEFAULT; // never an out-of-bounds colour
    }
    const Palette& q = kPalettes[u];
    const float n = g_fNight;
    constexpr float DUSK_LEVEL = 0.35f;
    if (n <= DUSK_LEVEL) {
        const float t = n / DUSK_LEVEL;
        *pr = Lerp(255.0f, (float)q.uDuskR, t);
        *pg = Lerp(255.0f, (float)q.uDuskG, t);
        *pb = Lerp(255.0f, (float)q.uDuskB, t);
    } else {
        const float t = (n - DUSK_LEVEL) / (1.0f - DUSK_LEVEL);
        *pr = Lerp((float)q.uDuskR, (float)q.uNightR, t);
        *pg = Lerp((float)q.uDuskG, (float)q.uNightG, t);
        *pb = Lerp((float)q.uDuskB, (float)q.uNightB, t);
    }
}

static void RegionProfileTint(const Weather::Profile& p, float* pr, float* pg, float* pb) {
    const Weather::Profile& clear = kProfiles[Weather::SKY_CLEAR];
    float rr = 255.0f, gg = 255.0f, bb = 255.0f;
    PaletteTint(&rr, &gg, &bb);
    rr = rr * (float)p.uR / (float)(clear.uR ? clear.uR : 1);
    gg = gg * (float)p.uG / (float)(clear.uG ? clear.uG : 1);
    bb = bb * (float)p.uB / (float)(clear.uB ? clear.uB : 1);
    *pr = rr > 255.0f ? 255.0f : rr;
    *pg = gg > 255.0f ? 255.0f : gg;
    *pb = bb > 255.0f ? 255.0f : bb;
}

static void StepToward(float& v, float target, float step) {
    if (v < target) {
        v += step;
        if (v > target) v = target;
    } else if (v > target) {
        v -= step;
        if (v < target) v = target;
    }
}

// ---------------------------------------------------------------- capture state

static bool g_bInSkyField    = false;  // this field is TINTED and LIT (sky or underwater)
// This field has an actual sky overhead, i.e. things can fall out of it. Set from bSky,
// where g_bInSkyField is set from bNight = bSky || underwater.
//
// The two are different questions and conflating them put the whole ground-effect suite
// under the sea: on the 32 maps of 230xxxxxx the falling particles and the rain loop were
// correctly suppressed while puddles, snowdrifts, footprints and the slippery-footing
// physics write all ran on the sea floor.
static bool g_bFallingSkyField = false;

// The CField the captured layers belong to, compared (never dereferenced) by
// Weather_Tick to notice that the field went away. See that function.
static void* g_pOwningField  = nullptr;
static bool g_bSceneryScope  = false;  // inside a sky field's load / back rebuild
static bool g_bCapture       = false;  // capture tiles / objects
static bool g_bCaptureObj    = false;  // ...and it is an object, not a tile
static bool g_bCaptureBack   = false;  // capture one of the map's own back layers
static bool g_bSwayLeafreBack = false; // current MakeBack is a selected Minar tree
// The map author's `front` flag on the back entry currently being built. See the
// promotion gate in the CreateLayer hook: a front back lives in a different z band and
// must never be rewritten with HILL_Z.
static bool g_bOwnBackIsFront = false;
// The cloud / fog sheet currently being built, or -1. See MakeBack_hook.
static int  g_nFxCaptureSlot = -1;
static bool g_bCaptureNpc    = false;  // capture an NPC layer (during OnNpcEnterField)
static int  g_nOwnBackIndex  = 0;      // which of the map's own backs is being built

// Back 0 and 1 are the map's own SKY. They stay behind the injected backdrop, which is
// what replaces them; everything from 2 up is scenery and gets promoted in front of it.
// The first of the map's OWN backs that counts as scenery rather than as sky.
//
// A heuristic, and on its own a wrong one. It assumes a map's sky is backs 0 and 1 and
// that everything above is hills and trees, which is true of Henesys and false of 514 of
// the 2854 maps with backdrop art. Kerning City spreads one tiled `sunsetCity/0` across
// backs 0, 1, 2 AND 3 to build its sunset, so backs 2 and 3 were promoted in front of the
// injected band and painted over the moon and the starfields.
//
// SkyBackIndices below is the correction: any back that REPEATS the backmost base is more
// of the sky, whatever its index, and stays behind us with backs 0 and 1.
#define HILL_FIRST 2
// Relative to the top of our injected band, so the promotion always clears the whole of
// it however many backs the map has. The 0x4001F400 base is the engine's own back-layer
// z origin.
#define HILL_Z(idx) (1000 * ((idx) + (int)WeatherFx::InjectedLastIndex() + 8) - 0x4001F400)

// Four vectors, not one, because the four layer kinds have four different
// LIFETIMES and a combined vector would have to be cleared on the union of their
// rebuild paths, silently dropping whatever the current path did not rebuild.
//
//   tiles   rebuilt ONLY by LoadMap
//   objects rebuilt by LoadMap AND by the graphics-detail apply at 0x00642890,
//           which calls RestoreObj (0x0064293F) then RestoreBack (0x00642A73)
//           without ever passing through LoadMap. That path is reached from the
//           System Options dialog, so changing detail at night used to leave every
//           object at full daylight for the rest of the map while tiles and backs
//           stayed tinted, and left us writing colour into destroyed layers.
//   backs   rebuilt by LoadMap AND by RestoreBack (resolution / zoom / detail)
//   NPCs    per spawn, never in a batch
static std::vector<IWzGr2DLayerPtr> g_vTiles;
static std::vector<IWzGr2DLayerPtr> g_vObjs;
// Declared with g_vObjs rather than with the sway code below, because every place that
// rebuilds that vector has to invalidate this and two of them sit above it in the file.
static bool g_bSwayClassified = false;
// Whether the translate-sway standby has already handed back the offsets it applied. It
// unwinds exactly once per field, on the frame weathersway.cpp reports itself active;
// resetting this alongside g_bSwayClassified is what makes the unwind happen again after
// the object layers are rebuilt.
static bool g_bSwayStoodDown = false;
// Parallel to g_vObjs: SwayKind for each captured object.
static std::vector<unsigned char> g_vObjSway;
static std::vector<unsigned char> g_vObjPlant;
static std::vector<unsigned long long> g_vObjPathHash;
// Parallel to g_vObjs: the object's world position, straight off its map entry. Read from
// the property rather than from the layer's lt, because the map data says plainly what
// the layer's coordinate space does not.
static std::vector<POINT> g_vObjPos;
static POINT g_ptObjPos = {0, 0};
// Parallel to g_vObjs: whether each captured object's entry carried the mirror flag.
static unsigned char g_uObjFlip = 0;
static std::vector<unsigned char> g_vObjFlip;
// Set by MakeObj_hook for every object, just before the engine builds its layer, and read
// by the CreateLayer capture immediately afterwards. Written on EVERY object rather than
// only on foliage, so it is self clearing: an object that builds no layer cannot leave a
// stale true behind for the next one. Declared up here because the capture hook that
// reads it sits above the sway code that owns it.
static unsigned char g_uObjSwayKind = 0;   // SwayKind, defined with the sway code below
// Whether the object is a PLANT, for depth decisions. Deliberately separate from the sway
// kind: the sway classifier demotes anything that animates itself, because shearing a
// frozen frame of a butterfly looks wrong. That is a sway concern and has nothing to do
// with what should draw in front of what -- a sunflower head and a butterfly are still
// greenery, and lamps.cpp wants them treated as such when deciding how deep a post sits.
static unsigned char g_uObjIsPlant = 0;
// FNV-1a over the object's four WZ path parts, lowercased, with a separator between them.
// Stored instead of the strings themselves: the BSTRs belong to the property tree and do
// not outlive the call, and 244 objects x four copied paths is a lot of memory to hold
// for a lookup that only has to answer "is this that sprite".
static unsigned long long g_uObjPathHash = 0;

static unsigned long long HashPathPart(unsigned long long h, const wchar_t* s) {
    h ^= 0x2Fu; h *= 1099511628211ULL;          // separator, so a/bc and ab/c differ
    for (; s && *s; ++s) {
        wchar_t c = *s;
        if (c >= L'A' && c <= L'Z') c = (wchar_t)(c - L'A' + L'a');
        h ^= (unsigned long long)c;
        h *= 1099511628211ULL;
    }
    return h;
}
static std::vector<IWzGr2DLayerPtr> g_vBacks;
static std::vector<IWzGr2DLayerPtr> g_vNpc;

// RAII set-and-restore, so a thrown COM error in a loader cannot leave a capture
// flag stuck on (which would tint the wrong layers on the next map).
template <typename T>
struct ScopedSet {
    T* p;
    T prev;
    ScopedSet(T* pVar, T value) : p(pVar), prev(*pVar) { *pVar = value; }
    ~ScopedSet() { *p = prev; }
};

// ---------------------------------------------------------------- the clock

// The dusk / dawn curve. THIS IS THE TWIN of WeatherService.nightLevel() in
// server/weather/WeatherService.java; the two must agree or server-side logic
// will disagree with what the player can see. 05:00-07:00 dawn, 17:00-19:00 dusk.
#define DAWN_START (5 * 60)
#define DAWN_END   (7 * 60)
#define DUSK_START (17 * 60)
#define DUSK_END   (19 * 60)

// ---------------------------------------------------------------- golden hour
//
// The sun is on the horizon twice a day and it is not blue either time. Dawn runs pink,
// dusk runs gold, and without this both transitions are the same walk from white to the
// night blue: the light dims but never CHANGES COLOUR, which is the thing that actually
// reads as sunrise and sunset.
//
// Applied to the tint the whole tonemap already multiplies by, so one change reaches
// tiles, objects, backs and NPCs together rather than needing a pass each.
#define DAWN_R 0xF2
#define DAWN_G 0x9E
#define DAWN_B 0xB8      // pink, leaning red
#define DUSK_R 0xFF
#define DUSK_G 0xA2
#define DUSK_B 0x48      // gold, leaning orange
#define GOLDEN_STRENGTH 0.85f

// Peaks in the MIDDLE of a transition and is zero at both ends, so the warmth arrives and
// leaves with the sun instead of switching on at a boundary.
static float GoldenFactor(float fMinute, int nStart, int nEnd) {
    if (fMinute < nStart || fMinute >= nEnd) {
        return 0.0f;
    }
    const float t = (fMinute - (float)nStart) / (float)(nEnd - nStart);
    return sinf(t * 3.14159265f);
}

// The tint actually rendered: the region and profile colour, warmed toward pink or gold
// while the sun is low.
//
// The warmth is CUT BY THE PROFILE'S BOOST, so there is no golden hour under a storm. A
// heavy sky is exactly when the sun does not reach the horizon, and a gold cast under
// black cloud reads as a bug rather than as evening.
static void EffectiveTint(float* pr, float* pg, float* pb) {
    float r = g_fTintR, g = g_fTintG, b = g_fTintB;
    const float fDawn = GoldenFactor(g_fMinuteOfDay, DAWN_START, DAWN_END);
    const float fDusk = GoldenFactor(g_fMinuteOfDay, DUSK_START, DUSK_END);
    float k = (fDawn > fDusk) ? fDawn : fDusk;
    if (k > 0.0f) {
        float fClear = 1.0f - g_fBoost * 2.0f;
        if (fClear < 0.0f) fClear = 0.0f;
        k *= GOLDEN_STRENGTH * fClear;
        const float wr = (fDawn > fDusk) ? (float)DAWN_R : (float)DUSK_R;
        const float wg = (fDawn > fDusk) ? (float)DAWN_G : (float)DUSK_G;
        const float wb = (fDawn > fDusk) ? (float)DAWN_B : (float)DUSK_B;
        r += (wr - r) * k;
        g += (wg - g) * k;
        b += (wb - b) * k;
    }
    *pr = r; *pg = g; *pb = b;
}

static float NightFromMinute(float fMinute) {
    if (fMinute < DAWN_START || fMinute >= DUSK_END) {
        return 1.0f;
    }
    if (fMinute < DAWN_END) {
        return 1.0f - (fMinute - DAWN_START) / (float)(DAWN_END - DAWN_START);
    }
    if (fMinute < DUSK_START) {
        return 0.0f;
    }
    return (fMinute - DUSK_START) / (float)(DUSK_END - DUSK_START);
}

float Weather::NightLevel()   { return g_fNight; }
int   Weather::MinuteOfDay()  { return (int)g_fMinuteOfDay; }
bool  Weather::HasWorldState(){ return g_bHasWorldState.load(); }
bool  Weather::IsFieldActive(){ return g_bInSkyField; }
bool  Weather::HasFallingSky(){ return g_bFallingSkyField; }

unsigned char Weather::CurrentSky() {
    return g_bInSkyField ? g_uSky : (unsigned char)Weather::SKY_CLEAR;
}

const Weather::Profile& Weather::CurrentProfile() {
    const unsigned char u = Weather::CurrentSky();
    return kProfiles[u < Weather::SKY_COUNT ? u : Weather::SKY_CLEAR];
}

void Weather::SetWorldState(int nMinuteOfDay, int nMsPerGameMinute,
                            unsigned char uSky, unsigned char uFlags,
                            int nSkyElapsedSec, int nRainbowSecsLeft,
                            unsigned char uTintR, unsigned char uTintG,
                            unsigned char uTintB, int nPaletteId,
                            int nSkyElapsedMs, unsigned int uSkyToken) {
    if (uFlags & Weather::FLAG_DISABLED) {
        nMinuteOfDay = 12 * 60;
        uSky = Weather::SKY_CLEAR;
        uFlags |= Weather::FLAG_FROZEN;
        nRainbowSecsLeft = 0;
    }
    if (nMinuteOfDay < 0 || nMinuteOfDay > 1439) {
        nMinuteOfDay = 0;
    }
    if (nMsPerGameMinute < 100) {
        nMsPerGameMinute = 100;         // a runaway clock is worse than a slow one
    }
    if (uSky >= Weather::SKY_COUNT) {
        uSky = Weather::SKY_CLEAR;   // an id from a newer server renders as clear, not as garbage
    }
    g_nNetMinuteOfDay.store(nMinuteOfDay);
    g_nNetMsPerGameMinute.store(nMsPerGameMinute);
    g_uNetSky.store(uSky);
    if (uFlags & Weather::FLAG_SNAP) {
        g_bNetSnap.store(true);
    }
    g_bNetFrozen.store((uFlags & Weather::FLAG_FROZEN) != 0);
    g_bNetBareSky.store((uFlags & Weather::FLAG_BARESKY) != 0);
    // Stamped against the local clock so SkyElapsedSec can keep counting between
    // packets. Storing the reported value alone would freeze the age until the next
    // broadcast, which is up to a minute away.
    if (nSkyElapsedSec < 0) {
        nSkyElapsedSec = 0;
    }
    g_nNetSkyElapsedSec.store(nSkyElapsedSec);
    // Old servers have no millisecond field; preserving their seconds value keeps
    // accumulation and the deterministic lightning fallback well-defined.
    const bool bHasTimeline = nSkyElapsedMs >= 0;
    if (!bHasTimeline) {
        nSkyElapsedMs = nSkyElapsedSec > INT_MAX / 1000 ? INT_MAX
                                                         : nSkyElapsedSec * 1000;
    }
    // Published as one value; see g_uNetSkyAge. A tick of 0 is nudged to 1 because 0 is
    // the reader's "never stamped" sentinel, and GetTickCount really does return it once
    // per 49.7 days.
    {
        DWORD dwNow = GetTickCount();
        if (dwNow == 0) {
            dwNow = 1;
        }
        g_uNetSkyAge.store(((unsigned long long)(unsigned int)nSkyElapsedMs << 32)
                           | (unsigned long long)dwNow);
    }
    if (nRainbowSecsLeft < 0) {
        nRainbowSecsLeft = 0;
    }
    g_nNetRainbowSec.store(nRainbowSecsLeft);
    g_dwNetRainbowStamp.store(GetTickCount());
    // A black tint would multiply the whole map to nothing, so treat all zero as "not
    // sent" rather than as an instruction.
    if (uTintR || uTintG || uTintB) {
        g_uNetTintR.store(uTintR);
        g_uNetTintG.store(uTintG);
        g_uNetTintB.store(uTintB);
    }
    if (nPaletteId >= 0 && nPaletteId < Weather::PALETTE_COUNT) {
        g_uNetPalette.store((unsigned char)nPaletteId);
        g_bNetPalette.store(true);
    }
    if (bHasTimeline) {
        g_uNetSkyToken.store(uSkyToken);
    }
    g_bHasWorldState.store(true);
    g_bNetDirty.store(true);
}

// Reported age plus the time since it was reported. Uses the raw NETWORK sky age, not
// the field-filtered one: a cave still accumulates nothing because its sky reports
// SKY_CLEAR, but stepping out of that cave into the open should show the drifts that
// built up while the player was inside, not a fresh start.
int Weather::SkyElapsedSec() {
    if (!g_bHasWorldState.load()) {
        return 0;
    }
    return SkyElapsedMillis() / 1000;
}

int Weather::SkyElapsedMillis() {
    if (!g_bHasWorldState.load()) {
        return 0;
    }
    // ONE atomic, not two. The base age and the tick it was stamped against are published
    // together as a single 64-bit value, because a reader that caught the new base against
    // the not-yet-updated old stamp got an age inflated by the whole inter-broadcast gap
    // -- up to a minute -- which is enough to land the synchronized lightning in a
    // different window from every other client for that frame.
    const unsigned long long uPair = g_uNetSkyAge.load();
    const int   nBase   = (int)(unsigned int)(uPair >> 32);
    const DWORD dwStamp = (DWORD)(uPair & 0xFFFFFFFFull);
    if (dwStamp == 0) {
        return nBase;
    }
    const DWORD dwSince = GetTickCount() - dwStamp;
    const int nSince = dwSince > (DWORD)INT_MAX ? INT_MAX : (int)dwSince;
    if (nBase > INT_MAX - nSince) {
        return INT_MAX;
    }
    return nBase + nSince;
}

unsigned int Weather::SkyToken() {
    return g_uNetSkyToken.load();
}

unsigned char Weather::PaletteId() {
    if (!g_bNetPalette.load()) {
        return Weather::PALETTE_DEFAULT;
    }
    const unsigned char u = g_uNetPalette.load();
    return u < Weather::PALETTE_COUNT ? u : Weather::PALETTE_DEFAULT;
}

// Reported remainder minus the time since it was reported. Floors at zero, so a rainbow
// that expires between broadcasts ends on time rather than hanging until the next packet.
int Weather::RainbowSecsLeft() {
    if (!g_bHasWorldState.load()) {
        return 0;
    }
    const int nLeft = g_nNetRainbowSec.load();
    if (nLeft <= 0) {
        return 0;
    }
    const DWORD dwStamp = g_dwNetRainbowStamp.load();
    if (dwStamp == 0) {
        return nLeft;
    }
    const int nSince = (int)((GetTickCount() - dwStamp) / 1000u);
    const int nNow = nLeft - nSince;
    return nNow > 0 ? nNow : 0;
}

// LP 0x373D. Runs on the RECEIVE thread: this only writes atomics, which is why
// it is allowed to. No WZ, no layers, no CWnd, no sending.
void Weather_HandleWorldState(CInPacket* pPacket) {
    if (!pPacket) {
        return;
    }
    // The dispatcher hands the packet over with the offset AT the opcode, and the
    // offset at entry is NOT guaranteed to be 0. Skip relative to our own entry.
    pPacket->SetOffset(pPacket->GetOffset() + 2);
    if (!pPacket->CanRead(8)) {
        return;
    }
    const int  nMinute = (int)(unsigned short)pPacket->Decode<unsigned short>();
    const int  nMsPer  = (int)pPacket->Decode<int>();
    const unsigned char uSky   = pPacket->Decode<unsigned char>();
    const unsigned char uFlags = pPacket->Decode<unsigned char>();
    // The elapsed field was added after the first eight bytes shipped, so it is read
    // only if it is actually there. A server that predates it simply reports 0, which
    // means accumulation starts bare exactly as it used to.
    int nElapsed = 0;
    if (pPacket->CanRead(4)) {
        nElapsed = pPacket->Decode<int>();
        if (nElapsed < 0) {
            nElapsed = 0;
        }
    }
    // Also optional, and for the same reason: a server predating the region palettes
    // sends nothing here and the neutral tint stays in force.
    unsigned char uTR = 0, uTG = 0, uTB = 0;
    if (pPacket->CanRead(3)) {
        uTR = pPacket->Decode<unsigned char>();
        uTG = pPacket->Decode<unsigned char>();
        uTB = pPacket->Decode<unsigned char>();
    }
    // Optional for the third time, same rule: a server predating the rainbow sends
    // nothing and none is ever raised.
    int nRainbow = 0;
    if (pPacket->CanRead(2)) {
        nRainbow = (int)(short)pPacket->Decode<unsigned short>();
        if (nRainbow < 0) {
            nRainbow = 0;
        }
    }
    // Appended fields: leaving every older field in place makes this decoder forward
    // compatible with the 19-byte original packet and its later rainbow extension.
    int nPalette = -1;
    int nElapsedMs = -1;
    unsigned int uSkyToken = 0;
    if (pPacket->CanRead(1)) {
        nPalette = (int)pPacket->Decode<unsigned char>();
    }
    if (pPacket->CanRead(4)) {
        nElapsedMs = pPacket->Decode<int>();
    }
    if (pPacket->CanRead(4)) {
        uSkyToken = pPacket->Decode<unsigned int>();
    }
    Weather::SetWorldState(nMinute, nMsPer, uSky, uFlags, nElapsed, nRainbow,
                           uTR, uTG, uTB, nPalette, nElapsedMs, uSkyToken);
}

// ---------------------------------------------------------------- which fields

// Which maps have a sky to put weather in.
//
// The original shipped a hardcoded 14-entry field-ID list, half of them test maps.
// Generalising it needed an actual signal, and v83 map data has NO outdoor flag.
// Every cheaper candidate was measured over all 5381 maps and rejected:
//
//   signal                                    accuracy   why it fails
//   info/town == 1                              47.7%    worse than always-on. Henesys
//                                                        Weapon Store has town=1; 2401
//                                                        outdoor maps have town=0.
//   info/cloud == 1                             41.9%    means "falling off lands you in
//                                                        cloud". Perion 1, Henesys 0.
//   info/rain, info/snow                           --    exist in the schema, present on
//                                                        ONE map (103000002), both 0.
//   info/fieldType                              59.8%    UI / party-quest behaviour.
//   (always on)                                 62.4%    the baseline to beat
//   back->count > 0                             75.3%    admits 99.8% once links resolve
//   back[0] tiling type in {1,3,4,6,7}             --    caves tile like skies: darkCave
//                                                        and Henesys are both type 3
//
// What actually decides it is the BACKMOST background canvas, because that is not a
// proxy for sky visibility, it IS the sky. Across all 5381 maps there are only 159
// distinct (bank, index) keys in that position, so it can be enumerated. The 57 below
// were classified from the decoded artwork (weather_base_sheet.py renders the
// contact sheet; weather_base_backgrounds.png is the result) using opacity
// plus hue, then hand-corrected for the warm skies colour cannot recognise, of which
// Kerning's sunsetCity is the clearest.
//
// Result: 2834 of 5381 maps (52.7%) get weather. That is 57 banks, not the 59
// originally classified: shineWood2 (21 maps) and department (76 maps) were pulled
// back out as interiors, and the table's own header records why. Verified correct on all of Henesys,
// Ellinia, Perion, Kerning, Lith Harbor, Orbis, El Nath, Ludibrium, Leafre, Mu Lung,
// Ariant, Temple of Time, Florina, Mushroom Castle, Folk Town, Amoria (sky) and Ant
// Tunnel, Kerning subway, Aqua Road, Zakum's altar and lab, Sleepy Dungeon, Mu Lung
// Dojo, Ludibrium dungeon, Abandoned Tower (no sky).
//
// TWO THINGS TO KNOW BEFORE EDITING:
//
//   1. It is a WHITELIST. Anything unrecognised gets no weather, which is the safe
//      direction: a missed sky is a map that looks stock, a false positive is rain
//      falling inside a cave.
//   2. Opacity matters as much as colour. mureung/46 has mean RGB (253,253,253) but
//      is only 21% opaque: it is a cloud sprite over a black void, and all 90 Mu Lung
//      Dojo maps behind it render black. Classifying on colour alone puts snow in the
//      Dojo.
//
// This table is also the seam the per-region palettes grow from: the bank name is
// already the right key for "what does night look like here".
// See IMPLEMENTATION.md.
struct SKYKEY { const wchar_t* sBank; int nNo; };
static const SKYKEY kSkyBases[] = {
#include "weather_skytable.inc"
};

// Which of the map's own backs are part of its SKY rather than its scenery.
//
// Filled once per field, by the same walk that reads the backmost base. A back qualifies
// by repeating that base exactly: same bank, same index. That is a deliberately narrow
// test. A map's sky is almost always one canvas tiled or offset several times, so
// repetition identifies it precisely, whereas anything looser (a y threshold, a type
// test) starts swallowing distant scenery and hiding hills behind the night backdrop.
static std::vector<int> g_vSkyBackIdx;
// The map's own sky layers, kept apart from g_vBacks so they can be hidden as a set.
// Still tinted with everything else: they are in g_vBacks too, this is a second
// reference for visibility alone.
static std::vector<IWzGr2DLayerPtr> g_vSkyBackLayer;
static bool g_bBareSkyApplied = false;
// Did WeatherFx inject its backdrop into THIS field? Not the same question as "is it
// night here": an underwater field is tinted and lit but gets no injected band, and the
// hill promotion below only makes sense when there is a band to be promoted in front of.
static bool g_bFxBand = false;

static bool IsOwnSkyBack(int nIndex) {
    for (int i : g_vSkyBackIdx) {
        if (i == nIndex) {
            return true;
        }
    }
    return false;
}

// The (bank, index) of the field's backmost layer. False when the map has no
// background art at all, which is 719 maps: shop interiors, training rooms and
// arena stubs, whose back node is absent or holds one placeholder with bS="".
static bool ReadBackmostBase(CMapLoadable* pField, wchar_t* pBank, size_t uMax, int* pNo) {
    pBank[0] = L'\0';
    *pNo = 0;
    IWzPropertyPtr pPropField = pField->m_pPropField;
    if (!pPropField) {
        return false;
    }
    IUnknownPtr pUnkBack = pPropField->item[L"back"].GetUnknown();
    if (!pUnkBack) {
        return false;
    }
    IWzPropertyPtr pBack;
    if (FAILED(pUnkBack->QueryInterface(&pBack)) || !pBack || pBack->count <= 0) {
        return false;
    }
    IUnknownPtr pUnkEntry = pBack->item[L"0"].GetUnknown();
    if (!pUnkEntry) {
        return false;
    }
    IWzPropertyPtr pEntry;
    if (FAILED(pUnkEntry->QueryInterface(&pEntry)) || !pEntry) {
        return false;
    }
    Ztl_variant_t vBS = pEntry->item[L"bS"];
    if (V_VT(&vBS) != VT_BSTR || !V_BSTR(&vBS) || !V_BSTR(&vBS)[0]) {
        return false;   // placeholder entry: no backdrop art
    }
    wcsncpy_s(pBank, uMax, V_BSTR(&vBS), _TRUNCATE);
    *pNo = get_int32(pEntry->item[L"no"], 0);

    // Same pass, second job: every other back that repeats this base is also sky.
    g_vSkyBackIdx.clear();
    const int nCount = pBack->count;
    for (int i = 0; i < nCount; ++i) {
        wchar_t sName[16];
        swprintf_s(sName, L"%d", i);
        IUnknownPtr pUnkN = pBack->item[sName].GetUnknown();
        if (!pUnkN) {
            continue;
        }
        IWzPropertyPtr pN;
        if (FAILED(pUnkN->QueryInterface(&pN)) || !pN) {
            continue;
        }
        Ztl_variant_t vN = pN->item[L"bS"];
        if (V_VT(&vN) != VT_BSTR || !V_BSTR(&vN)) {
            continue;
        }
        if (_wcsicmp(V_BSTR(&vN), pBank) == 0 && get_int32(pN->item[L"no"], -1) == *pNo) {
            g_vSkyBackIdx.push_back(i);
        }
    }
    return true;
}

// CWvsContext::GetCurFieldID ignores its 'this' and resolves the field itself through
// get_field(), so a null this is fine. Verified: it opens by calling get_field
// (0x00437A0C) and has 15 call sites.
static int CurrentFieldID() {
    using GetCurFieldID_t = int(__thiscall*)(void*);
    return reinterpret_cast<GetCurFieldID_t>(0x00A1238B)(nullptr);
}

// Maps excluded by hand, whatever their background says. Sorted, binary searched.
//
// The (bank, index) rule below is right for the overwhelming majority of maps, but it
// is blind to one case it cannot possibly see: an INTERIOR that reuses its town's sky
// bank. Orbis and Ludibrium shop interiors, Kerning Square's mall and the tree dungeons
// all key to the same canvas as the open town around them, so no amount of classifying
// the artwork separates them. Naming them is the only way.
static const int kNoSkyMaps[] = {
#include "weather_nosky_maps.inc"
};

static bool IsExcludedMap(int nFieldId) {
    int lo = 0, hi = (int)_countof(kNoSkyMaps) - 1;
    while (lo <= hi) {
        const int mid = lo + (hi - lo) / 2;
        if (kNoSkyMaps[mid] == nFieldId) {
            return true;
        }
        if (kNoSkyMaps[mid] < nFieldId) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return false;
}

// Underwater: no sky, but still a night.
//
// Every Aqua Road and Aquarium map is on kNoSkyMaps, and rightly so: a rain layer or a
// moon under the sea is nonsense. But that list gates FOUR things at once through a
// single bSky, and only one of them is about the sky. It also suppresses the scenery
// capture, the per frame tick and the lamps, so an excluded map is frozen at full
// daylight forever and cannot hold a lamp.
//
// That is right for the other 232 entries, which are shop interiors and dungeons
// excluded precisely because their lighting should not track the clock. It is wrong
// here: the sea gets dark at night, the region already carries a night tint that has
// never once been applied, and an Aqua Road lamp is pointless in a map that is always
// noon.
//
// A range rather than a list. The whole of 230xxxxxx is under the sea, there is no
// dry map in it, and a range cannot drift out of step with kNoSkyMaps the way a second
// hand written list would.
static bool IsUnderwaterMap(int nFieldId) {
    return nFieldId / 1000000 == 230;
}

// Back banks whose backmost base is not only the SKY. Most maps put a sky up there and
// nothing else, so replacing it with the injected night backdrop is exactly right. A few
// use one flat tiled swatch as the fill behind EVERYTHING, sky and sea alike -- Nautilus
// Harbor's nautilusPort/0 is a 50x50 solid blue tiled H+V across the whole field -- and
// covering that with an opaque backdrop does not just change the sky, it deletes the sea
// and leaves the starfield showing through where the water was.
//
// Keyed on the BANK rather than the map id so every map drawn on the same base behaves
// the same way; there are 13 Nautilus maps and they should not need listing one by one.
static bool BaseIsAlsoWater(const wchar_t* sBank) {
    return sBank && _wcsicmp(sBank, L"nautilusPort") == 0;
}

// Set by FieldHasSky for the field being loaded. Read by Weather_SkyBackdropColor, which
// is the single place the injected backdrop's alpha is decided.
static bool g_bBaseIsWater = false;

static bool FieldHasSky(CMapLoadable* pField) {
    g_bBaseIsWater = false;
    if (!pField) {
        return false;
    }
    // Checked FIRST and by id, so an excluded map costs one binary search and never
    // touches the property tree at all.
    if (IsExcludedMap(CurrentFieldID())) {
        return false;
    }
    try {
        wchar_t sBank[64];
        int nNo = 0;
        if (!ReadBackmostBase(pField, sBank, _countof(sBank), &nNo)) {
            return false;
        }
        for (const SKYKEY& k : kSkyBases) {
            if (k.nNo == nNo && _wcsicmp(sBank, k.sBank) == 0) {
                g_bBaseIsWater = BaseIsAlsoWater(sBank);
                return true;
            }
        }
        return false;
    } catch (const _com_error&) {
        return false;
    }
}

// ---------------------------------------------------------------- colour

// One dword carries both the fade alpha and the night multiply, which is why the
// original's separate ApplyScenery / ApplyWeather / ApplyBackdrop passes collapse
// into this.
// Darkness actually rendered: the day/night curve, floored by the profile's own boost
// so an overcast noon is dim and a storm is dimmer. max(), not sum: a storm at midnight
// should be as dark as midnight, not darker than black.
// Lightning used to release 82% of the scene darkness at full strength. A 15% reduction
// keeps the regional timing readable while leaving enough of the night tint in place for
// a less disruptive, photosensitivity-friendlier flash.
static constexpr float LIGHTNING_SCENE_RELEASE = 0.697f;  // 0.82 * 0.85
static constexpr float LIGHTNING_SKY_RELEASE   = 0.578f;  // 0.68 * 0.85

static float EffectiveNight() {
    const float n = (g_fNight > g_fBoost) ? g_fNight : g_fBoost;
    // Lightning releases most, but not all, of the storm darkness. The residual tint
    // prevents a lightning frame from becoming a flat white UI flash.
    return n * (1.0f - LIGHTNING_SCENE_RELEASE * WeatherFx::LightningLevel());
}

static unsigned int Argb(float fAlpha, float fNight) {
    if (fAlpha < 0.0f) fAlpha = 0.0f;
    if (fAlpha > 1.0f) fAlpha = 1.0f;
    if (fNight < 0.0f) fNight = 0.0f;
    if (fNight > 1.0f) fNight = 1.0f;
    float tr, tg, tb;
    EffectiveTint(&tr, &tg, &tb);
    const unsigned int a = (unsigned int)(fAlpha * 255.0f);
    const unsigned int r = 255 - (unsigned int)(fNight * (255.0f - tr));
    const unsigned int g = 255 - (unsigned int)(fNight * (255.0f - tg));
    const unsigned int b = 255 - (unsigned int)(fNight * (255.0f - tb));
    return (a << 24) | (r << 16) | (g << 8) | b;
}

// The same tint with the darkness supplied by the caller, for anything that needs a
// night level other than the map's own. lamps.cpp uses it to lift the scenery around a
// lit lamp: the whole point is a DIFFERENT night level a few hundred pixels wide.
unsigned int Weather_TintColor(float fAlpha, float fNight) {
    return Argb(fAlpha, fNight);
}

// The darkness actually being RENDERED, which is not the same as Weather::NightLevel():
// that is the clock alone, while this is floored by the active profile's boost, so an
// overcast noon is dim and a storm is dimmer. Anything that has to agree with the tint
// on screen has to read this one -- a module lighting its own corner of the map from
// NightLevel() would lift toward a daylight the rest of the map is not at, and leave a
// visible seam around every lamp for the whole of a daytime storm.
float Weather_EffectiveNight() {
    return EffectiveNight();
}

unsigned int Weather_SceneryColor(float fAlpha) {
    return Argb(fAlpha, EffectiveNight());
}

// ------------------------------------------------------- the local player's position
//
// Shared by the ground modules: footprints need to know where the player walked, and
// puddles need to know when they were stepped in.
//
// CUserLocal + 4 is a subobject whose vtable slot 4 returns a POINT* of the object's
// world x and y. Confirmed at two independent sites in the client, which is what makes
// it safe to rely on:
//
//   0x0096D9D9  calls it twice and pushes GetPos()->y then GetPos()->x as arguments
//   0x00441767  reads GetPos()->x, then GetPos()->y MINUS half the sprite height, which
//               is how the engine turns a character's foot anchor into a body centre
//
// The second is decisive: subtracting half a height from the +4 field only makes sense
// if that field is a y coordinate. The two sites are also on different objects, a
// CUserLocal and a pooled CUser, so the layout belongs to their shared base rather than
// to one class.
//
// The global is null outside a field, which is the normal state on the login screens.
#define ADDR_CUSER_LOCAL 0x00BEBF98

// v83 world coordinates fit comfortably inside this. The bound is not defensive padding:
// it is the check that the vtable slot really is the position accessor. If it ever
// resolves to something else the values go wild rather than merely wrong, and a caller
// can turn itself off instead of scattering sprites across the map.
#define POS_SANE_LIMIT 200000

static bool ReadPlayerPosRaw(int* px, int* py) {
    __try {
        unsigned char* pUser = *reinterpret_cast<unsigned char**>(ADDR_CUSER_LOCAL);
        if (!pUser) {
            return false;
        }
        void*  pSub  = pUser + 4;
        void** pVtbl = *reinterpret_cast<void***>(pSub);
        if (!pVtbl) {
            return false;
        }
        using t_GetPos = POINT*(__thiscall*)(void*);
        POINT* pPos = reinterpret_cast<t_GetPos>(pVtbl[4])(pSub);
        if (!pPos) {
            return false;
        }
        *px = pPos->x;
        *py = pPos->y;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool Weather_ReadPlayerPos(int* px, int* py) {
    if (!ReadPlayerPosRaw(px, py)) {
        return false;
    }
    if (*px > POS_SANE_LIMIT || *px < -POS_SANE_LIMIT ||
        *py > POS_SANE_LIMIT || *py < -POS_SANE_LIMIT) {
        LOG_ONCE("weather: player position read %d,%d is out of range. CUserLocal+4 "
                 "vtable slot 4 is not the position accessor on this client; the ground "
                 "effects that need it are off.", *px, *py);
        return false;
    }
    return true;
}

// The tiled backdrop's alpha.
//
// It follows the clock like the moon, with one exception that is not cosmetic fussiness:
// at tall viewports a TILED back at partial alpha shows a faint per-tile grid, because
// the engine blends each tile to the screen separately and overlapped tile edges double
// blend. Below about 900px it is invisible; above it, the taller view magnifies it into
// a visible lattice for the whole two seconds of the fade. So at tall resolutions the
// backdrop snaps between on and off, skipping the partial-alpha window entirely, while
// the tint, the moon, the clouds and the rain still fade smoothly everywhere.
//
// This project ships nine resolution modes, so this threshold is reached by real players.
#define BACKDROP_SNAP_MIN_H 900

unsigned int Weather_SkyBackdropColor() {
    // Held at nothing where the map's own base doubles as its water. Only the OPAQUE
    // backdrop is suppressed: the moon and the starfields ride Weather_NightSkyColor and
    // still draw, and the clouds, rain and tint are untouched, so such a map still gets a
    // full night -- over its own sea instead of over a hole where the sea used to be.
    if (g_bBaseIsWater) {
        return 0x00FFFFFFu;
    }
    // The tall-viewport snap is applied to the CLOCK component ONLY, and the lightning
    // pulse then modulates the snapped result. Folding the pulse in before the quantiser
    // turned a 20-100 ms strike into a one-tick full-screen cut: at a peak strength above
    // 0.865 the combined alpha crossed below 0.5, the opaque night backing was written at
    // alpha 0, and the map's own daytime sky was exposed with a half-faded moon still
    // drawn over it -- a single-frame full-screen brightness jump, which is exactly the
    // photosensitivity hazard the 0.85 reduction above exists to avoid. Below 900 px the
    // same strike merely lifted the backdrop smoothly, so the defect was invisible at the
    // resolution the snap was tuned on.
    //
    // The lattice the snap exists to hide only appears during the multi-second dusk ramp,
    // never during a sub-100 ms pulse, so keeping the pulse out of the quantiser costs
    // nothing.
    float aClock = g_fNight;
    if (get_screen_height() >= BACKDROP_SNAP_MIN_H) {
        aClock = (aClock > 0.5f) ? 1.0f : 0.0f;
    }
    // The opaque night backing recedes during a strike too; leaving it at full alpha
    // while every hill and tree brightens makes lightning look like a tint bug.
    float a = aClock * (1.0f - LIGHTNING_SKY_RELEASE * WeatherFx::LightningLevel());
    if (a < 0.0f) a = 0.0f;
    if (a > 1.0f) a = 1.0f;
    return ((unsigned int)(a * 255.0f) << 24) | 0x00FFFFFFu;
}

// Full brightness, alpha only. The moon must not be darkened by the night tint.
unsigned int Weather_NightSkyColor() {
    float a = g_fNight * (1.0f - LIGHTNING_SKY_RELEASE * WeatherFx::LightningLevel());
    if (a < 0.0f) a = 0.0f;
    if (a > 1.0f) a = 1.0f;
    return ((unsigned int)(a * 255.0f) << 24) | 0x00FFFFFFu;
}

unsigned int Weather_RainColor(float fAlpha) {
    return Argb(fAlpha, EffectiveNight() * RAIN_TINT_SCALE);
}

static void ApplyList(std::vector<IWzGr2DLayerPtr>& v, unsigned int uColor) {
    for (auto& p : v) {
        if (p) {
            try { p->color = uColor; } catch (const _com_error&) {}
        }
    }
}

// ---------------------------------------------------------------- capture hook

static auto IWzGr2D__CreateLayer = reinterpret_cast<IWzGr2DLayerPtr*(__thiscall*)(
    void*, IWzGr2DLayerPtr*, int, int, unsigned int, unsigned int, int, Ztl_variant_t*, Ztl_variant_t*)>(0x00426C7E);

IWzGr2DLayerPtr* __fastcall IWzGr2D__CreateLayer_hook(
        void* pThis, void* _EDX, IWzGr2DLayerPtr* pRet,
        int nLeft, int nTop, unsigned int uWidth, unsigned int uHeight, int nZ,
        Ztl_variant_t* pvCanvas, Ztl_variant_t* pvFilter) {
    IWzGr2DLayerPtr* pResult = IWzGr2D__CreateLayer(pThis, pRet, nLeft, nTop, uWidth, uHeight, nZ, pvCanvas, pvFilter);
    if (pResult && *pResult) {
        try {
            // Order is a priority list, not a set of independent tests.
            //
            // Lamps go FIRST. A lamp post and its glow are built by MakeObj during the
            // same RestoreObj that builds the map's ordinary objects, so g_bCapture is
            // armed at the same time; asking lamps first is what keeps a glow out of
            // the tinted scenery list, where the night tint would darken the light.
            if (Lamps_CaptureLayer(*pResult)) {
                // consumed
            } else if (g_bCaptureNpc) {
                g_vNpc.push_back(*pResult);
            } else if (g_bCaptureFxSky) {
                WeatherFx::CaptureSky(*pResult);
            } else if (g_bCaptureFxNight) {
                WeatherFx::CaptureNight(*pResult);
            } else if (g_bCaptureFxDust) {
                WeatherFx::CaptureDust(*pResult);
            } else if (g_bCaptureFxRainbow) {
                WeatherFx::CaptureRainbow(*pResult);
            } else if (g_bCaptureFxCloud) {
                WeatherFx::CaptureCloud(*pResult, g_nFxCaptureSlot);
            } else if (g_bCaptureFxRain) {
                WeatherFx::CaptureRain(*pResult);
            } else if (g_bCaptureFxFog) {
                WeatherFx::CaptureFog(*pResult, g_nFxCaptureSlot);
            } else if (g_bCaptureFxSnow) {
                WeatherFx::CaptureSnow(*pResult);
            } else if (g_bCaptureBack) {
                // Pull the map's own scenery backs IN FRONT of our injected backdrop.
                // Our entries sit at higher back indices, so by default they paint over
                // the map's trees and hills; the backdrop is opaque, so without this the
                // map would lose its scenery to a flat sky.
                //
                // The z is relative to the TOP of our injected band, not a fixed offset.
                // A fixed one worked on Henesys and failed on Ellinia, where the map has
                // enough backs of its own that the band reached past the low tree layers.
                // Not IsOwnSkyBack: those repeat the backmost base, so they are the
                // map's sky continuing past index 1 and belong BEHIND the injected band
                // with backs 0 and 1. Promoting them is what hid the moon in Kerning City.
                // g_bFxBand, not just the index. The promotion exists to pull the map's
                // scenery in FRONT of our opaque injected backdrop. With no backdrop
                // there is nothing to get in front of, and rewriting z then only
                // reorders the map's own backs against each other: on an underwater map
                // that put a back's bottom edge over the one behind it and drew a hard
                // horizontal line across the field where the art was meant to blend.
                // A `front` back needs no promotion and must not get one: the engine has
                // already put it in its own foreground band, 399,200 units NEARER than the
                // whole injected band, so rewriting its z with HILL_Z (which is built from
                // the background origin) is a demotion that drops the map's foreground art
                // in among its background art. It is not sky either, so it does not join
                // g_vSkyBackLayer; it is captured for the tint and otherwise left alone.
                if (g_bFxBand && !g_bOwnBackIsFront && g_nOwnBackIndex >= HILL_FIRST
                        && !IsOwnSkyBack(g_nOwnBackIndex)) {
                    (*pResult)->z = HILL_Z(g_nOwnBackIndex);
                } else if (g_bOwnBackIsFront) {
                    // Tinted with everything else, but neither promoted nor treated as sky.
                } else {
                    // The other side of that same test: a back below HILL_FIRST, or one
                    // repeating the backmost base, IS the map's sky. Held separately so
                    // FLAG_BARESKY can hide exactly this set and nothing else.
                    g_vSkyBackLayer.push_back(*pResult);
                }
                g_vBacks.push_back(*pResult);
                if (g_bSwayLeafreBack) {
                    WeatherSway_ReplaceLeafreBack(*pResult);
                }
            } else if (g_bCapture) {
                if (g_bCaptureObj) {
                    g_vObjs.push_back(*pResult);
                    g_vObjSway.push_back(g_uObjSwayKind);
                    g_vObjPlant.push_back(g_uObjIsPlant);
                    g_vObjPathHash.push_back(g_uObjPathHash);
                    g_vObjPos.push_back(g_ptObjPos);
                    g_vObjFlip.push_back(g_uObjFlip);
                } else {
                    g_vTiles.push_back(*pResult);
                }
            }
        } catch (const _com_error&) {
        }
    }
    return pResult;
}

// ---------------------------------------------------------------- field hooks

void CMapLoadable::RestoreTile_hook() {
    ScopedSet<bool> g(&g_bCapture, g_bSceneryScope);
    ScopedSet<bool> go(&g_bCaptureObj, false);
    CMapLoadable::RestoreTile(this);
}

// RestoreObj is reached TWO ways: from LoadMap (scope set there), and from the
// graphics-detail apply at 0x00642890, which the System Options dialog drives and
// which never touches LoadMap. Arming only on g_bSceneryScope therefore missed the
// second path entirely: the rebuilt objects were never captured, so they stayed at
// full daylight while the rest of the map was tinted, and the per-frame apply kept
// writing into the destroyed layers the old vector still held.
//
// Re-arm for any rebuild that happens while already in a sky field, and drop the
// old object refs first so the vector cannot accumulate a set per apply.
void CMapLoadable::RestoreObj_hook() {
    const bool bRearm = !g_bSceneryScope && g_bInSkyField;
    if (bRearm) {
        g_vObjs.clear();
        g_vObjSway.clear();
        g_vObjPlant.clear();
        g_vObjPathHash.clear();
        g_vObjPos.clear();
        g_vObjFlip.clear();
        g_bSwayClassified = false;
        g_bSwayStoodDown  = false;
        // Lamp posts and glows are objects too, so this path destroys and rebuilds them
        // as well; their layer references have to be dropped on exactly the same edge.
        Lamps_OnObjRebuild(true);
        // WEATHERSWAY DELIBERATELY DOES NOT GET THIS EDGE, and that is a known gap
        // rather than an oversight. It would need it -- its frame sets are keyed to object
        // indices that this path invalidates -- but the version of the module that ships
        // here is reverted to its pre-review state while a foliage corruption on Leafre is
        // bisected, and that form has no rebuild entry point to call. The visible cost is
        // that changing graphics detail or resolution while standing in foliage can leave
        // sway frames attached to the wrong objects until the next map load.
    }
    ScopedSet<bool> g(&g_bCapture, g_bSceneryScope || bRearm);
    ScopedSet<bool> go(&g_bCaptureObj, true);
    CMapLoadable::RestoreObj(this);
    if (bRearm) {
        try { ApplyList(g_vObjs, Argb(1.0f, EffectiveNight())); } catch (const _com_error&) {}
        // Unconditional, like the apply above: this path is reached from the System
        // Options dialog at any hour, and at full day the gated per-frame apply never
        // runs, so nothing else would ever colour the rebuilt lamps.
        Lamps_OnObjRebuild(false);
        try {
            Lamps_RelightScenery(g_vTiles, g_vObjs, g_vNpc, EffectiveNight(), NPC_TINT_SCALE);
        } catch (const _com_error&) {}
        g_bNeutral = (EffectiveNight() <= 0.0f);
    }
}

// ------------------------------------------------------------------ foliage sway
//
// A TEST. Bushes, flowers and grass tufts nudged from side to side, gently in fair
// weather and faster in a storm.
//
// WHAT THIS CANNOT DO, stated up front so the result is judged for what it is. A real
// sway BENDS: the base stays planted and the top leans. That needs a shear, and
// IWzGr2DLayer has none, so this TRANSLATES the whole sprite instead. At two pixels the
// base slides two pixels, and whether that reads as wind or as sliding is the entire
// question this is here to answer. If it reads as sliding, the next thing to try is
// InterLockedOffset with DIFFERENT deltas for the lt and rb corners, which deforms the
// layer rect rather than moving it; that is untested because whether this engine's
// renderer stretches a sprite into its rect or merely clips it is not knowable from the
// WzLib headers, which forward straight into Gr2D_DX8.dll.
//
// WHICH OBJECTS. By NAME first, then by size.
//
// Size alone was the first cut and it was wrong in the way that matters: it swayed
// benches, signposts and rope rungs, because "small and near the ground" describes those
// just as well as it describes a bush. Objects carry their identity in oS/l0/l1/l2, and
// CMapLoadable::MakeObj already hands that property to a hook lamps.cpp owns, so the name
// is available at the moment the layer is built.
//
// The foliage whitelist is the l1 CATEGORY and it is deliberately narrow. Map/Obj has 818
// distinct categories, and the two biggest, `acc` at 1641 groups and `basic` at 641, are
// mixed buckets holding foliage and furniture side by side. Admitting those would put the
// benches straight back. So this UNDER selects: some bushes in the mixed buckets will
// stand still. That is the right way round to be wrong.
//
// Ropes and ladders are matched separately and more loosely, because they are unambiguous
// by name and there is nothing in a bank called `rope` that should stand still.
#define FOL_MIN_PX        10      // smaller than this is a pebble; nothing to see
// What SWAYS is small growing things: flowers, bushes, grass. Not trees, not the mushroom
// stalks Henesys is built out of. A tree trunk does not bend in a breeze, and at this
// scale a whole canopy leaning reads as the map wobbling.
//
// These numbers were checked against Henesys's grassySoil/nature bank rather than picked:
// The limits are set by RENDERING the bank, not by reading the numbers. Doing it the other
// way put nature/13 in the blocked column as a "tree" when it is the big green hedge, and
// that is the one thing on the map most obviously wanting to move.
//
//   passes    nature/0  131x39   bushes and grass
//             nature/13 223x128  the big green hedge
//             nature/14  97x90   red mushroom cluster
//             nature/16 200x105  scattered leaves
//             nature/17 141x62   small mushrooms
//   blocked   nature/11 132x294  nature/12 120x287  mushroom STALKS, tall and narrow
//             nature/15 290x239  a tree, it has a trunk
//             nature/27 337x27   a ground-cover strip, too wide to read as one plant
//
// So the discriminator is really HEIGHT: a hedge is wide and low, a stalk or a trunk is
// tall. 140 admits the hedge at 128 and stops the stalks at 287.
// Raised from 140x260 to admit BUSHES. Henesys' acc1/grassySoil/nature/15 is 290x239 and
// was failing on both axes, so the biggest, softest, most obviously wind-catching thing on
// the map was the one piece of greenery standing perfectly still.
//
// Deliberately NOT raised further. 300x250 stops short of the 306x316 midForest trees and
// the 241x340 nature/0: a whole tree shearing about its trunk reads as the trunk bending,
// which is worse than it not moving, and those three alone would have cost another 42% of
// the frame budget.
#define FOL_MAX_H        250
#define FOL_MAX_W        300
#define FOL_AMP_CALM      2.0f    // pixels either side, fair weather
#define FOL_AMP_ROUGH     5.0f    // storm and blizzard
#define FOL_PERIOD_CALM   2600.0f // ms for one lean out and back
#define FOL_PERIOD_ROUGH   850.0f
// Rope and ladder on their own, slower clock. Kept in step with weathersway.cpp so the
// standby path does not move differently from the real one.
#define ROPE_PERIOD_CALM  6400.0f
#define ROPE_PERIOD_ROUGH 2400.0f

namespace {
struct SwayObj {
    size_t uIdx;          // into g_vObjs
    float  fPhase;        // so they do not all lean on the same frame
    int    nApplied;
    float  fAmpScale;     // a hanging rope swings further than a planted bush
};
}  // namespace

static std::vector<SwayObj> g_vSway;

// The l1 categories that are unambiguously growing things.
static const wchar_t* const kFoliageCats[] = {
    L"nature", L"nature1", L"nature2", L"tree", L"flower", L"grass", L"bush", L"plant", L"forest", L"leaf",
};

// Ropes and ladders sway too, and they are ORDINARY MAP OBJECTS. The map's own
// ladderRope node is collision data only, x / y1 / y2 / uf / page / l with no art, so
// the thing you can see and climb is an obj like any other: 1682 of them, filed under
// l1 = rope or l1 = ladder in the named banks and under a numeric l1 in the rest, which
// is why l2 is checked as well.
//
// They need their own size band. A rope is TALL and THIN, up to 28x250, and the foliage
// ceiling of 90px high would throw most of them out.
#define ROPE_MAX_H  320
#define ROPE_MAX_W   96
// Hanging signs and cages are wider than ropes, but are still intentionally
// bounded so a whole building facade cannot enter the generated-frame budget.
#define HANG_MAX_H  340
#define HANG_MAX_W  320
// Mushroom Shrine's two explicit landmark-tree sprites.  This is not a generic
// relaxation of the foliage guard: only WeatherSway_IsLargeTree may use this band.
#define TREE_MAX_H  740
#define TREE_MAX_W  900

enum SwayKind { SWAY_NONE = 0, SWAY_FOLIAGE = 1, SWAY_ROPE = 2, SWAY_HANGING = 3, SWAY_TREE = 4 };

static bool ContainsI(const wchar_t* hay, const wchar_t* needle) {
    if (!hay || !needle) {
        return false;
    }
    for (const wchar_t* p = hay; *p; ++p) {
        const wchar_t* a = p; const wchar_t* b = needle;
        while (*a && *b && towlower(*a) == towlower(*b)) { ++a; ++b; }
        if (!*b) {
            return true;
        }
    }
    return false;
}

// Does this object's ART have more than one frame?
//
// The obj ENTRY does not say, so the art node has to be resolved:
// Map/Obj/<oS>.img/<l0>/<l1>/<l2>, whose numbered children are the frames. One ResMan
// lookup per object, and only for objects that already matched the name filter, so it is
// a few dozen per map load rather than hundreds.
static bool ObjIsAnimated(IWzProperty* pObjProp) {
    try {
        Ztl_variant_t vOS = pObjProp->item[L"oS"];
        Ztl_variant_t v0 = pObjProp->item[L"l0"];
        Ztl_variant_t v1 = pObjProp->item[L"l1"];
        Ztl_variant_t v2 = pObjProp->item[L"l2"];
        if (V_VT(&vOS) != VT_BSTR || V_VT(&v0) != VT_BSTR
         || V_VT(&v1) != VT_BSTR || V_VT(&v2) != VT_BSTR) {
            return true;      // cannot tell, so assume animated and leave it alone
        }
        wchar_t uol[256];
        swprintf_s(uol, L"Map/Obj/%s.img/%s/%s/%s",
                   V_BSTR(&vOS), V_BSTR(&v0), V_BSTR(&v1), V_BSTR(&v2));
        if (!get_rm()) {
            return true;
        }
        IWzPropertyPtr pArt = get_rm()->GetObjectA(uol).GetUnknown();
        if (!pArt) {
            return true;
        }
        // Frame 1 existing is the whole test: frame 0 is always there.
        return pArt->item[L"1"].GetUnknown() != nullptr;
    } catch (const _com_error&) {
        return true;
    }
}

// ---------------------------------------------------------------- planted, or not

// The field's footholds, read once before LoadMap so every object can be tested against
// them as it is built. Cleared with the field.
static std::vector<FHSEG> g_vFH;
// x of every foothold endpoint that no other segment shares: the real ends of the real
// platforms, as opposed to the joints between collinear segments, which are far more
// numerous and are not edges of anything.
static std::vector<POINT>  g_vFHEdge;

// How close a plant's BOTTOM ROW has to be to the foothold line to count as growing out
// of it.
//
// Measured, not guessed. Over 389 foliage objects across Henesys, Ellinia, Perion, Lith
// Harbour, Nautilus, Sleepywood and two hunting grounds, the sprite base sits within a
// few pixels of the line for the median object, with a long tail both ways.
//
// Asymmetric, because the two tails mean different things. A base ABOVE the line is
// almost always empty padding at the bottom of the canvas or a plant on a slope, so it
// is tolerated generously. A base well BELOW the line is a prop hung over the FACE of
// the platform rather than standing on top of it, which is exactly the "in front of a
// platform" case, so that side is tight. This band keeps about 73% of foliage.
//
// This is measured against the sprite's bottom row and NOT against the obj entry's y.
// The entry y is where the canvas ORIGIN goes, which for a good part of the set is not
// the base at all: testing it directly threw out 100% of the foliage in Ellinia and
// Nautilus and 60% of Henesys.
#define SWAY_FH_ABOVE   28
#define SWAY_FH_BELOW   10
// How far from the end of a platform a plant has to be before it may sway. A plant right
// on the lip has nothing under half its root.
#define SWAY_EDGE_PX    16
// How close in y an edge has to be to count as the same platform, so a plant is not
// silenced by a ledge somewhere far above or below it.
#define SWAY_EDGE_Y     24

static void BuildFootholdEdges() {
    g_vFHEdge.clear();
    for (size_t i = 0; i < g_vFH.size(); ++i) {
        const long ax[2] = { g_vFH[i].x1, g_vFH[i].x2 };
        const long ay[2] = { g_vFH[i].y1, g_vFH[i].y2 };
        for (int e = 0; e < 2; ++e) {
            bool bShared = false;
            for (size_t j = 0; j < g_vFH.size() && !bShared; ++j) {
                if (j == i) {
                    continue;
                }
                // Exact match. Stock foothold chains join on identical integers, so any
                // tolerance here would start folding genuinely separate platforms whose
                // ends happen to be a pixel apart into one.
                if ((g_vFH[j].x1 == ax[e] && g_vFH[j].y1 == ay[e])
                 || (g_vFH[j].x2 == ax[e] && g_vFH[j].y2 == ay[e])) {
                    bShared = true;
                }
            }
            if (!bShared) {
                POINT pt;
                pt.x = ax[e];
                pt.y = ay[e];
                g_vFHEdge.push_back(pt);
            }
        }
    }
}

// Is this anchor standing on a platform, and far enough in from its ends to sway?
bool Weather_RootedWellInside(long x, long y, long nSpriteH) {
    if (g_vFH.empty()) {
        return true;   // no foothold data: filtering on it would silence the whole map
    }
    bool bOn = false;
    for (size_t i = 0; i < g_vFH.size() && !bOn; ++i) {
        const FHSEG& s = g_vFH[i];
        if (s.x1 == s.x2) {
            continue;              // a wall is not ground
        }
        const long lo = (s.x1 < s.x2) ? s.x1 : s.x2;
        const long hi = (s.x1 < s.x2) ? s.x2 : s.x1;
        if (x < lo || x > hi) {
            continue;
        }
        const long fy = s.y1 + (long)((double)(s.y2 - s.y1)
                      * (double)(x - s.x1) / (double)(s.x2 - s.x1));
        // The anchor may be anywhere inside the sprite, so accept from one sprite-height
        // above the foothold down to just below it. A fixed window here is what silenced
        // three quarters of the game's foliage.
        const long lAbove = (nSpriteH > 0) ? (nSpriteH + SWAY_FH_ABOVE) : SWAY_FH_ABOVE;
        if (y >= fy - lAbove && y <= fy + SWAY_FH_BELOW) {
            bOn = true;
        }
    }
    if (!bOn) {
        return false;
    }
    for (size_t i = 0; i < g_vFHEdge.size(); ++i) {
        const long dx = (x > g_vFHEdge[i].x) ? (x - g_vFHEdge[i].x) : (g_vFHEdge[i].x - x);
        const long dy = (y > g_vFHEdge[i].y) ? (y - g_vFHEdge[i].y) : (g_vFHEdge[i].y - y);
        if (dx < SWAY_EDGE_PX && dy < SWAY_EDGE_Y) {
            return false;
        }
    }
    return true;
}

void Weather_NoteObjProp(IWzProperty* pObjProp) {
    g_uObjSwayKind = SWAY_NONE;
    g_uObjIsPlant = 0;
    g_uObjPathHash = 0;
    g_ptObjPos.x = 0;
    g_ptObjPos.y = 0;
    if (!pObjProp) {
        return;
    }
    try {
        // The obj entry's MIRROR flag. The engine passes it to CreateAnimLayer (the
        // argument pushed at 0x0063C278), but weathersway builds its own layers through
        // IWzGr2D::CreateLayer, which has no flip parameter at all, so a generated sway
        // frame silently comes out UN-mirrored. Captured here so the sway planner can
        // recognise those sprites rather than render them backwards.
        g_uObjFlip = (unsigned char)(get_int32(pObjProp->item[L"f"], 0) != 0 ? 1 : 0);
        g_ptObjPos.x = get_int32(pObjProp->item[L"x"], 0);
        g_ptObjPos.y = get_int32(pObjProp->item[L"y"], 0);
    } catch (const _com_error&) {
    }
    try {
        Ztl_variant_t v0 = pObjProp->item[L"l0"];
        Ztl_variant_t v1 = pObjProp->item[L"l1"];
        Ztl_variant_t v2 = pObjProp->item[L"l2"];
        const wchar_t* sL0 = (V_VT(&v0) == VT_BSTR) ? V_BSTR(&v0) : nullptr;
        const wchar_t* sL1 = (V_VT(&v1) == VT_BSTR) ? V_BSTR(&v1) : nullptr;
        const wchar_t* sL2 = (V_VT(&v2) == VT_BSTR) ? V_BSTR(&v2) : nullptr;
        Ztl_variant_t vOS = pObjProp->item[L"oS"];
        const wchar_t* sOS = (V_VT(&vOS) == VT_BSTR) ? V_BSTR(&vOS) : nullptr;

        {
            unsigned long long h = 1469598103934665603ULL;
            h = HashPathPart(h, sOS);
            h = HashPathPart(h, sL0);
            h = HashPathPart(h, sL1);
            h = HashPathPart(h, sL2);
            g_uObjPathHash = h;
        }
        // Props that are not filed as foliage but move like it, named by weathersway.cpp.
        // Checked before the category match so a hay bundle filed under `market` still
        // reaches the bend.
        if (WeatherSway_ExtraFoliagePivot(g_uObjPathHash) > 0.0f) {
            g_uObjSwayKind = SWAY_FOLIAGE;
            g_uObjIsPlant = 1;
            return;
        }
        // Leafre's trees are whole trunk-and-crown canvases in `nature1`.  They need a
        // dedicated rooted-tree treatment rather than the normal small-plant band.
        if (WeatherSway_IsLeafreTreeObject(sOS, sL0, sL1)) {
            g_uObjSwayKind = ObjIsAnimated(pObjProp) ? SWAY_NONE : SWAY_TREE;
            g_uObjIsPlant = 1;
            return;
        }
        // Banners and similar art are selectively listed in weathersway.cpp.
        // Never freeze an asset that already has its own frame animation.
        if (WeatherSway_IsHangingObject(sOS, sL0, sL1, sL2)) {
            if (!ObjIsAnimated(pObjProp)) g_uObjSwayKind = SWAY_HANGING;
            return;
        }
        // Rope and ladder, as a SUBSTRING and on ALL THREE path parts.
        //
        // l0 is the one that matters and it was missing: of the 1682 rope and ladder
        // objects, 1542 name themselves in l0 (citySG has l0=rope, l1=0, l2=0), 138 in l1
        // and 2 in l2. Testing l1 and l2 alone matched about 8% of them, which is why
        // almost nothing was swinging.
        if (ContainsI(sL0, L"rope") || ContainsI(sL0, L"ladder")
         || ContainsI(sL1, L"rope") || ContainsI(sL1, L"ladder")
         || ContainsI(sL2, L"rope") || ContainsI(sL2, L"ladder")) {
            g_uObjSwayKind = SWAY_ROPE;
            return;
        }
        // Foliage is an EXACT category match rather than a substring. `nature` as a
        // substring would also take `naturalStone`, and not swaying things that are not
        // alive is the whole reason this filter exists.
        if (sL1) {
            for (const wchar_t* s : kFoliageCats) {
                if (_wcsicmp(sL1, s) == 0) {
                    g_uObjSwayKind = SWAY_FOLIAGE;
                    g_uObjIsPlant = 1;   // kept even if the demotion below fires
                    break;
                }
            }
        }
        // NEVER an object that animates itself.
        //
        // The bend takes one canvas, shears it nine ways and cycles those, which for an
        // animated object means freezing its animation and waving the frozen frame about.
        // Henesys is the case that showed it: grassySoil/nature/19, 20 and 21 are the
        // BUTTERFLIES, 9 and 6 frame flap cycles, and they were being caught, stopped
        // mid-flap and sheared. nature/25 and 26, the big sunflowers, already animate a
        // sway of their own and do not want a second one either.
        if (g_uObjSwayKind != SWAY_NONE && ObjIsAnimated(pObjProp)) {
            g_uObjSwayKind = SWAY_NONE;
        }
    } catch (const _com_error&) {
    }
}

// The object vectors are private to this file because everything that rebuilds them is,
// so lamps.cpp reads them through here rather than by extern.
int Weather_ObjCount() {
    return (int)g_vObjs.size();
}

bool Weather_GetObj(int i, IWzGr2DLayerPtr& pLayer, POINT* pPos) {
    if (i < 0 || i >= (int)g_vObjs.size() || i >= (int)g_vObjPos.size()) {
        return false;
    }
    pLayer = g_vObjs[i];
    if (pPos) *pPos = g_vObjPos[i];
    return true;
}

// The z BAND the map's own art occupies: the highest z any tile uses and the lowest any
// object uses. Anything that should lie on the ground but under everything standing on it
// belongs between the two.
//
// Measured rather than assumed. The small z numbers the ground effects were written with
// (2, 3, 4) are not in the same space as a real layer z, which the engine builds as a
// large scaled value with its own origin, so a literal put them above the whole world
// including the player.
bool Weather_ZBands(int* pTileMax, int* pObjMin) {
    bool bTile = false, bObj = false;
    int tmax = 0, omin = 0;
    for (auto& p : g_vTiles) {
        IWzGr2DLayer* q = p.GetInterfacePtr();
        if (!q) continue;
        try { const int z = q->z; if (!bTile || z > tmax) { tmax = z; bTile = true; } }
        catch (const _com_error&) {}
    }
    for (auto& p : g_vObjs) {
        IWzGr2DLayer* q = p.GetInterfacePtr();
        if (!q) continue;
        try { const int z = q->z; if (!bObj || z < omin) { omin = z; bObj = true; } }
        catch (const _com_error&) {}
    }
    if (!bTile && !bObj) {
        return false;
    }
    if (pTileMax) *pTileMax = bTile ? tmax : (omin - 2);
    if (pObjMin)  *pObjMin  = bObj  ? omin : (tmax + 2);
    return true;
}

// The GROUND plane, and the plane just in front of it, in the engine's layer-z space.
// One measurement shared by every module that draws on the floor, because three separate
// copies of this reasoning produced three separate bugs.
//
// THE VALUES ARE LARGE AND NEGATIVE AND THAT IS NORMAL. The engine's own formulas, read
// out of the client:
//   backs   1000*idx           - 0x4001F400   (MakeBack,     0x0063D2ED)
//   tiles   z + 10*(3000*L-zM) - 0x3FFFB1EA   (RestoreTile,  0x0063A91F)
//   objects z + 30000*L        - 0x3FFFF830   (MakeObj path, 0x0063C289)
// so every real field layer sits near -1.07e9 and larger z means NEARER the camera. Any
// "floor it at zero if it went negative" guard therefore does not floor anything, it
// throws the measurement away and puts the layer about 1.07 billion units in front of the
// entire map. A floor has to be expressed against the measurement, never against 0.
//
// WHAT THIS ACTUALLY GUARANTEES: pnGround is over the map's TILES, and pnAbove is one
// plane in front of it. It is NOT under every object -- see the measurement in the body.
//
// Returns false until the field's tiles and objects have been captured; a caller that
// cannot wait must skip drawing rather than substitute a literal, because a layer's z is
// chosen at creation and the mistake is then permanent for that layer's life.
bool Weather_GroundZ(int* pnGround, int* pnAbove) {
    int tmax = 0, omin = 0;
    if (!Weather_ZBands(&tmax, &omin)) {
        return false;
    }
    // THE INVERTED BAND IS THE ORDINARY CASE, NOT THE EXCEPTION. Tiles and objects both
    // carry a 30000-per-layer term, and the tile origin (-0x3FFFB1EA) is 17,990 units
    // NEARER the camera than the object origin (-0x3FFFF830), so a tile is in front of an
    // object on the same layer. Measured over the stock data: of the 2221 maps that carry
    // both tiles and objects, 2153 are inverted and only 68 leave a real gap.
    //
    // So on almost every map there is NO z that is both over the tiles and under every
    // object, and this deliberately chooses over-the-tiles. Ground effects therefore DO
    // draw in front of map objects on layers at or below the topmost tile layer. That is
    // the lesser evil: the alternative buries standing water and snow under the floor
    // they are lying on, and invisible is the one outcome worth ruling out.
    //
    // Written as tmax + half the gap rather than (tmax+omin)/2, so the sum of two values
    // near -2^30 cannot overflow.
    const int nGap = omin - tmax;
    int nGround, nAbove;
    if (nGap >= 3) {
        // A real gap, wide enough for both planes to sit inside it.
        nGround = tmax + nGap / 2;
        if (nGround > omin - 2) {
            nGround = omin - 2;
        }
        nAbove = nGround + 1;
    } else {
        // Inverted, or too narrow to fit two planes. Sit on the top of the tile stack.
        // nAbove is simply one in front: layer z is an integer and every object is
        // already behind tmax, so there is no object plane between these two to protect,
        // and clamping nAbove down to nGround here would collapse the two outputs into
        // one -- which would put footprints in the same plane as the drifts they are
        // pressed into, and rain splashes in the same plane as the puddles they land in.
        nGround = tmax;
        nAbove  = tmax + 1;
    }
    if (pnGround) {
        *pnGround = nGround;
    }
    if (pnAbove) {
        *pnAbove = nAbove;
    }
    return true;
}

// Did this object's map entry carry the mirror flag? weathersway cannot reproduce a flip
// on a generated layer, so it uses this to leave such sprites stock.
unsigned char Weather_ObjFlip(int i) {
    return (i >= 0 && (size_t)i < g_vObjFlip.size()) ? g_vObjFlip[i] : 0;
}

// For lamps.cpp's depth pass. See g_uObjIsPlant: this is the sway kind WITHOUT the
// self-animation demotion, because animation says nothing about draw order.
unsigned char Weather_ObjIsPlant(int i) {
    return (i >= 0 && (size_t)i < g_vObjPlant.size()) ? g_vObjPlant[i] : 0;
}

// The object's WZ path as one hash, for a module that needs to recognise a specific
// sprite. See g_uObjPathHash for why it is a hash and not the strings.
// The field the client is in, for anything that wants to log or key per map.
int Weather_CurrentFieldId() {
    return CurrentFieldID();
}

unsigned long long Weather_ObjPathHash(int i) {
    return (i >= 0 && (size_t)i < g_vObjPathHash.size()) ? g_vObjPathHash[i] : 0;
}

unsigned char Weather_ObjSwayKind(int i) {
    return (i >= 0 && i < (int)g_vObjSway.size()) ? g_vObjSway[i] : (unsigned char)SWAY_NONE;
}

// Read once per field, not per frame: this is two COM calls per object and the size of a
// layer does not change.
static void ClassifySwayObjects() {
    g_vSway.clear();
    for (size_t i = 0; i < g_vObjs.size(); ++i) {
        IWzGr2DLayer* p = g_vObjs[i].GetInterfacePtr();
        if (!p) {
            continue;
        }
        int w = 0, h = 0;
        try {
            IWzVector2DPtr lt = p->Getlt();
            IWzVector2DPtr rb = p->Getrb();
            if (!lt || !rb) {
                continue;
            }
            w = rb->x - lt->x;
            h = rb->y - lt->y;
        } catch (const _com_error&) {
            continue;
        }
        // Name first. Size is only a backstop now, against a whole forest canopy filed
        // under `tree` sliding about as one sprite.
        const unsigned char kind = (i < g_vObjSway.size()) ? g_vObjSway[i] : SWAY_NONE;
        if (kind == SWAY_NONE) {
            continue;
        }
        const bool bLargeTree = WeatherSway_IsLargeTree(Weather_ObjPathHash((int)i));
        const int maxW = (bLargeTree || kind == SWAY_TREE) ? TREE_MAX_W
                       : (kind == SWAY_ROPE) ? ROPE_MAX_W
                       : (kind == SWAY_HANGING) ? HANG_MAX_W : FOL_MAX_W;
        const int maxH = (bLargeTree || kind == SWAY_TREE) ? TREE_MAX_H
                       : (kind == SWAY_ROPE) ? ROPE_MAX_H
                       : (kind == SWAY_HANGING) ? HANG_MAX_H : FOL_MAX_H;
        if (w < FOL_MIN_PX || h < FOL_MIN_PX || w > maxW || h > maxH) {
            continue;
        }
        // Heavy wooden ladders and rigging barely move. Kept in step with the same
        // figure in weathersway.cpp, so the standby path does not look different.
        const float fAmp = (kind == SWAY_ROPE) ? 0.18f
                         : (kind == SWAY_HANGING) ? 0.26f : 1.0f;
        // A cheap spread of phases. Any hash would do; this one is stable per index so a
        // rebuild puts every plant back on the beat it was already on.
        const float fPhase = (float)((i * 2654435761u) % 6283u) / 1000.0f;
        g_vSway.push_back({i, fPhase, 0, fAmp});
    }
    DEBUG_MESSAGE("weather: %u of %u objects are foliage sized and will sway",
                  (unsigned)g_vSway.size(), (unsigned)g_vObjs.size());
}

// Hide or restore the map's own sky, on the frame the flag changes and not before.
//
// Latched rather than written every frame, for the same reason the glow colour is not:
// the engine re-asserts what it wants and a write per frame is a fight. visible is not
// contested that way, but a per frame COM call per sky layer for a testing mode is still
// a cost worth not paying, and the latch also makes the restore exact.
static void ApplyBareSky() {
    const bool bWant = g_bNetBareSky.load();
    if (bWant == g_bBareSkyApplied || g_vSkyBackLayer.empty()) {
        return;
    }
    for (size_t i = 0; i < g_vSkyBackLayer.size(); ++i) {
        if (!g_vSkyBackLayer[i]) {
            continue;
        }
        try {
            g_vSkyBackLayer[i]->visible = bWant ? 0 : 1;
        } catch (const _com_error&) {}
    }
    g_bBareSkyApplied = bWant;
    DEBUG_MESSAGE("weather: bare sky %s, %u sky layer(s)",
                  bWant ? "on" : "off", (unsigned)g_vSkyBackLayer.size());
}

static void SweepFoliageSway() {
    // weathersway.cpp does it properly, by bending the sprite. This translate version is
    // the standby for a client where canvases cannot be generated, so it steps aside the
    // moment the real one is running rather than nudging the originals underneath it.
    if (WeatherSway_Active()) {
        // UNWIND FIRST. InterLockedOffset is a RELATIVE move, so simply returning left
        // every offset this sweep had already applied on the layer for the life of the
        // field: a permanent lean on each plant, underneath the real sway. The accumulated
        // amount is tracked per object precisely so it can be given back, and it is given
        // back exactly once, on the frame the real sway takes over.
        if (!g_bSwayStoodDown) {
            g_bSwayStoodDown = true;
            for (SwayObj& s : g_vSway) {
                if (s.nApplied == 0 || s.uIdx >= g_vObjs.size()) {
                    s.nApplied = 0;
                    continue;
                }
                IWzGr2DLayer* p = g_vObjs[s.uIdx].GetInterfacePtr();
                if (p) {
                    try {
                        p->InterLockedOffset(-s.nApplied, 0, -s.nApplied, 0);
                    } catch (const _com_error&) {}
                }
                s.nApplied = 0;
            }
        }
        return;
    }
    if (!g_bSwayClassified) {
        ClassifySwayObjects();
        g_bSwayClassified = true;
    }
    if (g_vSway.empty()) {
        return;
    }
    const unsigned char uSky = Weather::CurrentSky();
    const bool bRough = (uSky == Weather::SKY_STORM || uSky == Weather::SKY_BLIZZARD
                      || uSky == Weather::SKY_SANDSTORM);
    const float fAmp     = bRough ? FOL_AMP_ROUGH : FOL_AMP_CALM;
    const float fFoliage = bRough ? FOL_PERIOD_ROUGH : FOL_PERIOD_CALM;
    const float fRope    = bRough ? ROPE_PERIOD_ROUGH : ROPE_PERIOD_CALM;
    const DWORD dwNow = GetTickCount();

    for (SwayObj& s : g_vSway) {
        const float fPeriod = (s.fAmpScale < 1.0f) ? fRope : fFoliage;
        const float fNow = (float)(dwNow % (DWORD)fPeriod) / fPeriod * 6.2831853f;
        if (s.uIdx >= g_vObjs.size()) {
            continue;
        }
        const int nWant = (int)(fAmp * s.fAmpScale * sinf(fNow + s.fPhase));
        const int dx = nWant - s.nApplied;
        // At two pixels the integer only changes a handful of times per cycle, so this
        // skips almost every frame for almost every plant. That is what keeps a hundred
        // swaying objects off the frame budget.
        if (dx == 0) {
            continue;
        }
        IWzGr2DLayer* p = g_vObjs[s.uIdx].GetInterfacePtr();
        if (!p) {
            continue;
        }
        try {
            p->InterLockedOffset(dx, 0, dx, 0);
            s.nApplied = nWant;
        } catch (const _com_error&) {
        }
    }
}

// RestoreBack rebuilds ALL back layers and is reached three ways: from LoadMap
// (scope set there), and from SetFieldMagLevel / ReloadBack, which are resolution
// and zoom changes that do NOT pass through LoadMap. Without re-arming here, the
// rebuilt rain layers would never be captured and would ignore the fade: i.e.
// rain would stay on screen forever after the weather cleared.
void CMapLoadable::RestoreBack_hook() {
    if (!g_bInSkyField) {
        CMapLoadable::RestoreBack(this);
        return;
    }
    // ONLY the backs. Tiles and objects are not rebuilt by this path, so their
    // captured layers stay valid and must not be dropped.
    g_vBacks.clear();
    // Shadows g_vBacks, so it is rebuilt by the same pass and must be dropped with it.
    g_vSkyBackLayer.clear();
    g_bBareSkyApplied = false;
    // NOT g_vSkyBackIdx. This rebuilds the SAME field's backs, from a resolution, zoom or
    // detail change, so the sky classification still holds. Clearing it here would put
    // every repeated sky back on the promoted path again and hide the moon a second time,
    // only now for anyone who touched System Options.
    WeatherFx::ClearBackLayers();
    ScopedSet<bool> g(&g_bSceneryScope, true);
    CMapLoadable::RestoreBack(this);
    try {
        ApplyList(g_vBacks, Argb(1.0f, EffectiveNight()));
    } catch (const _com_error&) {}
    WeatherFx::Reapply();
    g_bNeutral = (EffectiveNight() <= 0.0f);
}

// Classify the back layer being built. Everything that is NOT one of WeatherFx's
// injected cloud / rain entries is one of the map's own backs, and gets captured
// for the night tint, including back 0 and 1, the sky itself, which the original
// deliberately left alone because its injected backdrop covered them.
void* CMapLoadable::MakeBack_hook(int nIndex, void* pProp) {
    const bool bFxSky   = g_bSceneryScope && WeatherFx::IsSkyIndex(nIndex);
    const bool bFxNight = g_bSceneryScope && WeatherFx::IsNightIndex(nIndex);
    const bool bFxDust  = g_bSceneryScope && WeatherFx::IsDustIndex(nIndex);
    const bool bFxBow   = g_bSceneryScope && WeatherFx::IsRainbowIndex(nIndex);
    const bool bFxCloud = g_bSceneryScope && WeatherFx::IsCloudIndex(nIndex);
    const bool bFxRain  = g_bSceneryScope && WeatherFx::IsRainIndex(nIndex);
    const bool bFxFog   = g_bSceneryScope && WeatherFx::IsFogIndex(nIndex);
    const bool bFxSnow  = g_bSceneryScope && WeatherFx::IsSnowIndex(nIndex);
    const bool bOwnBack = g_bSceneryScope && !bFxSky && !bFxNight && !bFxDust && !bFxBow
                       && !bFxCloud && !bFxRain && !bFxFog && !bFxSnow;

    // Leafre town's tree backs are entries 7..10 (art 8, 9, 11 and 14).  MakeBack's
    // second argument is not consistently an IWzProperty on this client build, so the
    // map-local indices are the authoritative route for this one fixed scene.
    bool bLeafreTreeBack = bOwnBack && CurrentFieldID() == 240000000
                         && nIndex >= 7 && nIndex <= 10;
    // The map author's FOREGROUND flag. MakeBack reads string-pool id 0x5EC ("front") at
    // 0x0063D284 and branches on it at 0x0063D2D3, picking a completely different z origin
    // for each case: front == 0 gives
    // 1000*idx - 0x4001F400, front != 0 gives 1000*idx - 0x3FFBDCA0, a band 399,200 units
    // NEARER the camera and in front of the tiles.
    //
    // It has to be published to the capture hook because HILL_Z is built from the front==0
    // origin only. Without it the hill promotion rewrote a front layer's z from the
    // foreground band down into the background band -- the exact opposite of what the flag
    // means -- and every one of a town's foreground layers sank behind the town.
    bool bOwnBackFront = false;
    if (bOwnBack && pProp) {
        try {
            IWzProperty* pEntry = reinterpret_cast<IWzProperty*>(pProp);
            bOwnBackFront = get_int32(pEntry->item[L"front"], 0) != 0;
            if (!bLeafreTreeBack) {
                Ztl_variant_t vBS = pEntry->item[L"bS"];
                const int nNo = get_int32(pEntry->item[L"no"], -1);
                if (V_VT(&vBS) == VT_BSTR) {
                    bLeafreTreeBack = WeatherSway_IsLeafreTreeBack(V_BSTR(&vBS), nNo);
                }
            }
        } catch (const _com_error&) {
        }
    }

    ScopedSet<bool> gb(&g_bCaptureBack, bOwnBack);
    ScopedSet<bool> gff(&g_bOwnBackIsFront, bOwnBackFront);
    ScopedSet<bool> gl(&g_bSwayLeafreBack, bLeafreTreeBack);
    ScopedSet<int>  gi(&g_nOwnBackIndex, bOwnBack ? nIndex : g_nOwnBackIndex);
    ScopedSet<bool> gfs(&g_bCaptureFxSky, bFxSky);
    ScopedSet<bool> gfn(&g_bCaptureFxNight, bFxNight);
    ScopedSet<bool> gfd(&g_bCaptureFxDust, bFxDust);
    ScopedSet<bool> gfb(&g_bCaptureFxRainbow, bFxBow);
    ScopedSet<bool> gfc(&g_bCaptureFxCloud, bFxCloud);
    ScopedSet<bool> gfr(&g_bCaptureFxRain, bFxRain);
    ScopedSet<bool> gff2(&g_bCaptureFxFog, bFxFog);
    ScopedSet<bool> gfsn(&g_bCaptureFxSnow, bFxSnow);
    // Which cloud / fog SHEET this entry is, held across the whole MakeBack call so every
    // tile layer the tiler builds inside it is filed under the same sheet.
    ScopedSet<int> gfsl(&g_nFxCaptureSlot,
                        bFxCloud ? WeatherFx::CloudSlot(nIndex)
                                 : (bFxFog ? WeatherFx::FogSlot(nIndex) : -1));
    return CMapLoadable::MakeBack(this, nIndex, pProp);
}

// NPC layers are built synchronously inside this call, in CNpc::Init.
void CNpcPool::OnNpcEnterField_hook(void* pPacket) {
    ScopedSet<bool> g(&g_bCaptureNpc, g_bInSkyField);
    CNpcPool::OnNpcEnterField(this, pPacket);
}

// Drop every captured layer and reset to a neutral, field-less state.
static void ReleaseField() {
    g_vTiles.clear();
    g_vObjs.clear();
    g_vObjSway.clear();
    g_vObjPlant.clear();
    g_vObjPathHash.clear();
    g_vObjPos.clear();
    g_vObjFlip.clear();
    g_bSwayClassified = false;
    g_bSwayStoodDown  = false;
    g_vBacks.clear();
    g_vNpc.clear();
    // HERE and not in RestoreBack_hook: this is the real teardown, the point at which the
    // next field will have a different sky to classify.
    g_vSkyBackIdx.clear();
    g_bFxBand = false;
    g_vSkyBackLayer.clear();
    g_bBareSkyApplied = false;
    g_vFH.clear();
    g_vFHEdge.clear();
    WeatherFx::OnLeaveField();
    Lamps_OnLeaveField();
    g_bInSkyField  = false;
    g_bFallingSkyField = false;
    g_pOwningField = nullptr;
    g_fNight       = 0.0f;
    g_bNeutral     = true;
    g_bTintPrimed  = false;
}

// Per-frame, from CWvsApp::CallUpdate_hook, which runs on EVERY stage.
//
// LoadMap_hook used to be the module's only teardown point, and that is not enough:
// CMapLoadable::LoadMap has exactly ONE call site in the whole binary (0x00529BC6,
// inside CField's stage-entry path), so it runs when a field is ENTERED and never
// when one is left. Log out of a sky field and all four vectors keep that field's
// entire layer set AddRef'd through world select, character select and the whole
// login session, with g_bInSkyField still asserted, until the next map load.
//
// A stale g_bInSkyField is not inert either: it is what arms RestoreObj_hook's
// re-capture, RestoreBack_hook's re-arm and OnNpcEnterField_hook.
//
// The pointer is COMPARED, never dereferenced. get_field() reads the global stage
// slot (0xBEDED4), so on the login stage it hands back a CLogin, which is exactly
// the change this needs to notice and exactly why dereferencing it would be wrong.
//
// Not a crash today: CMapLoadable::Update also has one caller, inside CField::Update,
// and CLogin's Update slot is CLogin::Update, so the per-frame apply genuinely cannot
// run on the login stage and never writes into the stale layers. This is retention
// and state hygiene, fixed before it becomes something worse.
void Weather_Tick() {
    // Before the early returns: a pending `!lamp` preview has to be placed on the main
    // thread, and it must work at noon as well as at midnight, so it cannot sit behind
    // either the owning-field check below or the daytime apply gate in Update_hook.
    Lamps_Tick();
    if (!g_pOwningField) {
        return;
    }
    if (static_cast<void*>(get_field()) == g_pOwningField) {
        return;
    }
    ReleaseField();
    DEBUG_MESSAGE("weather: field went away outside LoadMap; released");
}

void CMapLoadable::LoadMap_hook() {
    ReleaseField();

    bool bSky = false;
    bool bNight = false;
    try {
        // Deliberately NOT gated on HasWorldState(). The server sends the world
        // state from MapleMap.addPlayer, which lands AFTER the client has already
        // loaded the map it is warping into, so gating here would leave the first
        // map of every session permanently sunlit. Injecting unconditionally is
        // free: the cloud and rain layers arrive at alpha 0 and the day tint is an
        // identity multiply, so a server that never sends 0x373D renders stock.
        bSky = FieldHasSky(this);
        if (bSky) {
            WeatherFx::Inject(this);   // clouds + rain; built by the LoadMap below
        }
        // bSky drives the SKY: the injected cloud, rain and moon layers. bNight drives
        // the DARKNESS: the scenery tint, the per frame tick and the lamps. They are the
        // same answer everywhere except under the sea, which has the second without the
        // first. See IsUnderwaterMap.
        g_bFxBand = bSky;
        bNight = bSky || IsUnderwaterMap(CurrentFieldID());
        // Before LoadMap, because MakeObj runs inside it and every object tests itself
        // against this list as it is built. The property tree is already fully populated
        // at this point, which is the same fact Lamps_Inject relies on to stand a lamp
        // on the ground before any object exists.
        g_vFH.clear();
        g_vFHEdge.clear();
        if (bNight && m_pPropField) {
            Lamps_CollectFootholds(m_pPropField, g_vFH);
            BuildFootholdEdges();
        }
        // Lamps, likewise built by the LoadMap below. This both lights the lamps the
        // map already places and injects any hand-placed ones; it MUST run before the
        // engine's LoadMap, because building an object with a direct MakeObj call
        // afterwards faults.
        Lamps_Inject(this, bNight);
    } catch (const _com_error& e) {
        (void)e;
        DEBUG_MESSAGE("weather: inject failed 0x%08X", e.Error());
        bSky = false;
        bNight = false;
    }

    {
        struct Guard {
            Guard(bool b) { g_bSceneryScope = b; }
            ~Guard() { g_bSceneryScope = false; }
        } guard(bNight);
        CMapLoadable::LoadMap(this);
    }

    if (bNight) {
        g_bInSkyField = true;
        g_bFallingSkyField = bSky;   // underwater is lit and tinted, but nothing falls
        // Remember who owns these layers, so Weather_Tick can notice the field
        // going away by any route that does not come back through here.
        g_pOwningField = this;
        // Snap on arrival. The server sends map-entry state with FLAG_SNAP for the
        // same reason: a two second dusk fade after every portal reads as a bug.
        g_fNight = NightFromMinute(g_fMinuteOfDay);
        const unsigned int uScenery = Argb(1.0f, EffectiveNight());
        try {
            ApplyList(g_vTiles, uScenery);
            ApplyList(g_vObjs, uScenery);
            ApplyList(g_vBacks, uScenery);
        } catch (const _com_error&) {}
        // Unconditional, NOT inside the g_bNeutral gate: at full day that gate skips
        // the per-frame apply entirely, so this is the write that leaves a lamp post at
        // the plain identity colour instead of whatever the engine happened to build it
        // with. Snapped rather than warmed up, for the same reason the night tint snaps
        // on arrival: a town warming its lamps up after every portal reads as a bug.
        Lamps_OnFieldLoaded();
        try {
            Lamps_RelightScenery(g_vTiles, g_vObjs, g_vNpc, EffectiveNight(), NPC_TINT_SCALE);
        } catch (const _com_error&) {}
        g_bNeutral = (EffectiveNight() <= 0.0f);
        DEBUG_MESSAGE("weather: %s field (night=%.2f, sky=%d, %zu tiles, %zu objs)",
                      bSky ? "sky" : "underwater",
                      g_fNight, (int)g_uSky, g_vTiles.size(), g_vObjs.size());
    }
    // THE SKY IS REGION STATE AND DOES NOT TRAVEL. The clock does: it is a world fact, so
    // g_fMinuteOfDay is deliberately carried across the map change and NightFromMinute is
    // snapped above. g_uSky is not: since regional weather shipped it is per region, and
    // its only writer is Update_hook's dirty block, which does not run until the next
    // 30 ms logic tick. Everything between here and that tick would otherwise be driven by
    // the sky of the map the player just LEFT -- and bypass.cpp runs the six ground-effect
    // frames BEFORE the stage update, so a warp out of a raining region into a dry one
    // seeded a full burst of puddles onto the dry map before anything corrected it.
    //
    // Cleared rather than guessed. The server sends a FLAG_SNAP map-entry packet from
    // MapleMap.addPlayer on every entry, so the correct regional sky lands on the next
    // tick and snaps in. Snapping IN from clear is strictly safer than snapping out of a
    // wrong sky and back: clear seeds no puddles, settles nothing, installs no native
    // weather effect and starts no ambient loop.
    g_uSky = Weather::SKY_CLEAR;
    WeatherFx::SetSky(Weather::SKY_CLEAR, true);

    // bSky, not bNight. An underwater field is tinted and lit but gets no particles:
    // rain, snow and blowing sand all fall through air the map does not have.
    WeatherFx::OnEnterField(bSky);
}

void CMapLoadable::Update_hook() {
    CMapLoadable::Update(this);

    // Consume anything the receive thread left for us.
    if (g_bNetDirty.exchange(false)) {
        g_fMinuteOfDay     = (float)g_nNetMinuteOfDay.load();
        g_nMsPerGameMinute = g_nNetMsPerGameMinute.load();
        g_uSky             = g_uNetSky.load();
        const bool bSnap = g_bNetSnap.exchange(false);
        if (bSnap) {
            g_fNight = NightFromMinute(g_fMinuteOfDay);
            // This packet belongs to a new map. Prime the regional/profile colour
            // below from its target instead of fading from the field we just left.
            g_bTintPrimed = false;
        }
        WeatherFx::SetSky(g_uSky, bSnap);
    }

    // Advance the local clock by real elapsed time. GetTickCount wraps every 49
    // days; the unsigned subtraction is correct across the wrap.
    //
    // Not while FROZEN. A GM holding the time still is the one case where the local
    // advance is wrong: it would creep forward and be snapped back on every 60 s
    // broadcast, so a held midnight would visibly stutter toward dawn and jump back.
    const unsigned int tNow = GetTickCount();
    if (g_tLastUpdate != 0 && g_nMsPerGameMinute > 0 && !g_bNetFrozen.load()) {
        const unsigned int dt = tNow - g_tLastUpdate;
        if (dt < 60000u) {   // ignore a long stall (alt-tab, loading); the next packet re-syncs
            g_fMinuteOfDay += (float)dt / (float)g_nMsPerGameMinute;
            while (g_fMinuteOfDay >= 1440.0f) {
                g_fMinuteOfDay -= 1440.0f;
            }
        }
    }
    g_tLastUpdate = tNow;

    if (!g_bInSkyField) {
        WeatherFx::Update();   // no-op off-field, but keeps its own state clean
        return;
    }

    // Chase the active profile's darkness and colour. On the very first frame in a
    // field there is nothing to fade FROM, so prime instead of ramping up from white.
    {
        const Weather::Profile& p = Weather::CurrentProfile();
        const float fStep = p.fFadeStep;
        // The REGION says what colour the night is; the PROFILE says how a given sky
        // shifts it. Combining them as region * profile / neutral means a profile's tint
        // keeps its meaning as a change RELATIVE to a clear night, so a storm is still
        // darker and colder than clear wherever you are, and a region sitting at the
        // neutral tint behaves exactly as it did before regions had colours.
        float fTR = 0.0f, fTG = 0.0f, fTB = 0.0f;
        RegionProfileTint(p, &fTR, &fTG, &fTB);
        if (!g_bTintPrimed) {
            g_fBoost = p.fBoost;
            g_fTintR = fTR; g_fTintG = fTG; g_fTintB = fTB;
            g_bTintPrimed = true;
        } else {
            StepToward(g_fBoost, p.fBoost, fStep);
            StepToward(g_fTintR, fTR, fStep * 255.0f);
            StepToward(g_fTintG, fTG, fStep * 255.0f);
            StepToward(g_fTintB, fTB, fStep * 255.0f);
        }
    }

    // Chase the curve. Normal clock motion is far smaller than the catch-up step,
    // so this only rate-limits a jump (a GM !weather, or the first packet after a
    // stall), which is exactly the case that should fade rather than snap.
    const float fTarget = NightFromMinute(g_fMinuteOfDay);
    if (g_fNight < fTarget) {
        g_fNight = std::min(fTarget, g_fNight + NIGHT_CATCHUP_STEP);
    } else if (g_fNight > fTarget) {
        g_fNight = std::max(fTarget, g_fNight - NIGHT_CATCHUP_STEP);
    }

    // Before the tint pass: lightning is folded into EffectiveNight(), so calculating
    // it after this point would visibly delay each short strike by a rendered frame.
    WeatherFx::TickLightning();

    // Re-assert EVERY frame while the tint is live. Tiled backs carry an
    // engine-installed per-tile alpha animator that overwrites this otherwise, and
    // NPC animation resets sprite colour on its own, so this is not an optimisation
    // opportunity WHILE IT IS DARK. The only saving available is skipping the whole
    // loop once the tint has settled back to the identity, which g_bNeutral does.
    // Also re-apply while the profile is still CHASING, even if both ends are neutral:
    // the tint colour can be mid-interpolation with EffectiveNight() at 0, and skipping
    // then would freeze it part way.
    const Weather::Profile& pNow = Weather::CurrentProfile();
    float fNowR = 0.0f, fNowG = 0.0f, fNowB = 0.0f;
    RegionProfileTint(pNow, &fNowR, &fNowG, &fNowB);
    const bool bChasing = (g_fBoost != pNow.fBoost)
                       || (g_fTintR != fNowR)
                       || (g_fTintG != fNowG)
                       || (g_fTintB != fNowB);
    const bool bNeutral = (EffectiveNight() <= 0.0f);
    // Lamps_HasLights() is part of the gate because Lamps_Update() is the ONLY driver of
    // the photocell, the warm-up/cool-down ramp and the glow alpha, and it is called from
    // inside this block. lamps.cpp assumes the gap between LAMP_OFF_LEVEL and 0 keeps the
    // block running long enough for the ramp to finish, but that only accounts for the
    // 250 ms cooldown, not the 2600 ms per-lamp stagger.
    //
    // The sequence that broke it: a DAYTIME storm (boost 0.38, the only profile boost
    // above LAMP_ON_LEVEL 0.35) trips the lamps on, then clears. g_fBoost falls to 0 in
    // roughly 560 ms of real time, at which point bNeutral and !bChasing both hold and the
    // block stops running forever. Every lamp whose stagger delay exceeded that window had
    // not begun ramping down and stayed frozen at full brightness, so six of Henesys' nine
    // lamps burned over a noon town until the player changed map or night actually fell.
    if (!bNeutral || !g_bNeutral || bChasing || Lamps_HasLights()) {
        const unsigned int uScenery = Argb(1.0f, EffectiveNight());
        try { ApplyList(g_vTiles, uScenery); } catch (const _com_error&) {}
        try { ApplyList(g_vObjs, uScenery); } catch (const _com_error&) {}
        try { ApplyList(g_vBacks, uScenery); } catch (const _com_error&) {}
        try { ApplyList(g_vNpc, Argb(1.0f, EffectiveNight() * NPC_TINT_SCALE)); } catch (const _com_error&) {}
        // AFTER the uniform pass, because it overwrites the colour of just the layers
        // near a lit lamp. Lamps_Update first so the switch levels and the light list
        // are current for the relight that follows.
        try { Lamps_Update(); } catch (const _com_error&) {}
        try {
            Lamps_RelightScenery(g_vTiles, g_vObjs, g_vNpc, EffectiveNight(), NPC_TINT_SCALE);
        } catch (const _com_error&) {}
        g_bNeutral = bNeutral;
    }

    ApplyBareSky();
    SweepFoliageSway();

    WeatherFx::Update();
}

void AttachWeatherMod() {
    ATTACH_HOOK(CMapLoadable::LoadMap, CMapLoadable::LoadMap_hook);
    ATTACH_HOOK(CMapLoadable::Update, CMapLoadable::Update_hook);
    ATTACH_HOOK(CMapLoadable::RestoreTile, CMapLoadable::RestoreTile_hook);
    ATTACH_HOOK(CMapLoadable::RestoreObj, CMapLoadable::RestoreObj_hook);
    ATTACH_HOOK(CMapLoadable::RestoreBack, CMapLoadable::RestoreBack_hook);
    ATTACH_HOOK(CMapLoadable::MakeBack, CMapLoadable::MakeBack_hook);
    Lamps_Attach();   // CMapLoadable::MakeObj, owned by lamps.cpp
    ATTACH_HOOK(CNpcPool::OnNpcEnterField, CNpcPool::OnNpcEnterField_hook);
    ATTACH_HOOK(IWzGr2D__CreateLayer, IWzGr2D__CreateLayer_hook);
}
