#include "pch.h"
#include "weatherfx.h"
#include "weather.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include "ztl/zstr.h"
#include <vector>

// Clouds, rain sheets and the engine's native particles. See weatherfx.h.
//
// Every visual parameter is read off the current profile row (weather_profiles.inc),
// so adding a sky is a line of data. Changed from the original package: no F7/F8 polling
// (the sky is server state), the injection is self-contained here, and the colour
// comes from weather.cpp so the night tint and the fade share one dword.

#define FX_FADE_STEP     0.015f          // ~2s fade

#define FX_RAIN_COUNT    4
// Falling snow: two imported sheets rather than the engine's particle blower.
//
// The particle path is still there and is still what a blizzard and a sandstorm use. Snow
// moved off it because these two planes carry a depth cue the particle engine cannot: one
// sheet BEHIND the map art and one IN FRONT of the player, with the near one larger,
// brighter and falling twice as fast. BlowWeather picks a variant per particle at random,
// so size, brightness and speed are uncorrelated there by construction, and the depth
// reads as noise instead of distance.
#define FX_SNOW_COUNT    2
// THE BLIZZARD DRAWS NO SHEETS, and there is no count here to raise.
//
// Two attempts at one were tried and both failed for the same underlying reason, which is
// worth stating so a third is not started. The first was an imported sheet of soft diagonal
// STREAKS: a streak is a picture of a direction, its pixels lie on a fixed 135 degree axis,
// and the particle direction is rolled fresh from the server's per-sky token every
// occurrence, so the two visibly fought about half the time. The second reused the round
// snow planes driven twice as fast and leftward, which cannot disagree with anything -- but
// round flakes at snow's scale read as SNOW however fast they move, and a blizzard with
// tidy legible flakes in front of it reads as weaker than the plain snow beside it.
//
// What distinguishes a blizzard here is density and blindness: 280 hard particles against
// snow's ~40, and the fog.
// The blizzard's rolling fog: FOUR sheets at different sizes, shapes and speeds.
//
// One sheet at one speed reads as a texture sliding over the glass. Two was better and
// still had a tell: both were 800 wide, so both tiled on an 800 px pitch and the pair
// realigned every 800 px of relative travel, bringing the same coincidence of shapes back
// over and over. These four are 1024, 900, 640 and 800 wide, which share no useful common
// factor, so the combined pattern only repeats after their least common multiple.
//
// They also differ in HEIGHT and in where they sit, which is what makes them overlap rather
// than stack: a 460-tall bank low in the frame and a 240-tall veil high in it CROSS, and
// the crossing is the depth. Four sheets at one height and one size would just be one sheet
// at four times the opacity.
#define FX_FOG_COUNT     4
// The layer alpha each fog sheet reaches at full level.
//
// DOWN FROM 0.85 BECAUSE THERE ARE NOW FOUR OF THEM AND THEY MULTIPLY. Transmission is the
// product of (1 - a) over every sheet covering a pixel, so doubling the sheet count roughly
// squares the thinning. Measured over the composite at the injected offsets: 0.85 gives a
// 74% peak and a 50% p95, against the 55% peak the old PAIR reached. 0.60 puts the four
// back at a 58% peak, so this change is more shapes rather than more fog. Raise it only if
// a blizzard is meant to get thicker, and check the p95 rather than the peak: the peak is
// one lucky overlap, the p95 is what the player is looking through.
#define FOG_ALPHA_MAX    0.60f
#define FX_CLOUD_COUNT   3
#define FX_RAINBOW_COUNT 1
// The sandstorm backdrop: nightDesert back/19, an 800x350 dust choked orange sky, tiled
// horizontally across the sky band. Two rows, so it covers a tall viewport.
#define FX_DUST_COUNT    2
// The alpha a rainbow is seen at. The art is baked opaque and this is the whole of
// its subtlety, so it is the one number to change if it reads too strong or too weak.
#define RAINBOW_ALPHA    0.22f
#define FX_NIGHT_COUNT   3     // the moon and two starfields
// back/0 fill + the gradient, and nothing else. Must match the AddBack calls in Inject:
// every later band's index range is computed by adding these counts, so a stale value
// misaddresses the dust, night, rainbow, cloud and rain layers. The self check at the end
// of Inject reports a mismatch.
#define FX_SKY_COUNT     (1 + 1)

// Native particle ids now live in weather_profiles.inc, one per sky.
#define ADDR_BLOWWEATHER    0x00534A35   // void __thiscall CField::BlowWeather(int itemID, ZXString<char>)
#define ADDR_WEATHER_REMOVE 0x00641AEB   // void __thiscall CMapLoadable::WeatherLayer_RemoveAll()

// Marker written into the field's info node so the entries are added once per
// cached property. The ranges are still recomputed on EVERY entry (see Inject).
//
// THE `wfx` PREFIX IS THIS BUNDLE'S PRIVATE NAMESPACE on the field property, shared with
// the two lamp keys in lamps.cpp. A stock v83 field property has no child by any of these
// names, and the prefix is what keeps them from colliding with another mod's. It is
// deliberately not the name of any particular server: these keys are written and read by
// this DLL alone, within one session, so the string is free to be generic. Change all
// three together if you change it at all.
#define FX_MARKER L"wfxWeatherBacks"

bool g_bCaptureFxSky   = false;
bool g_bCaptureFxNight = false;
bool g_bCaptureFxDust = false;
bool g_bCaptureFxRainbow = false;
bool g_bCaptureFxCloud = false;
bool g_bCaptureFxRain  = false;
bool g_bCaptureFxFog   = false;
bool g_bCaptureFxSnow  = false;

namespace {

struct BACKENTRY { long no, x, y, rx, ry, type, cx, cy, a, ani; };

// The tiled night sky: back/0 is the base fill, back/1 the tall vertical gradient that
// makes the horizon glow, back/2 the near-black upper sky stacked upward above it.
// Geometry is the original's verbatim, because it is tuned and it works.
//
// This is OPAQUE, and that is why it also needs the z promotion in weather.cpp's
// MakeBack hook: injected entries land at HIGHER back indices than the map's own, so
// without pulling the map's scenery backs in front of this, Ellinia's trees and
// Henesys's hills would simply be painted over.
//
// cx / cy are the exact canvas size, filled in at injection from the art itself. Left
// at 0 the engine auto-sizes tile spacing and overlaps tiles by about a pixel, which
// double blends into visible dark seam lines while the layer is mid-fade.
#define SKY_DY          (-100)      // lift the whole backdrop this far
const BACKENTRY g_back0  = { 0,  162,  204, -10, -90, 3, 50, 50, 255, 0 };  // H+V tile, backmost
// The gradient. Its own bank, Map/Back/MapleMoonSky.img back/0, built by
// build_sky_gradient.py.
//
// PRIVATE ART, and for the same reason WeatherParticles.img is: nightDesert is stock, and
// Ariant's night desert maps read the same back/1. Restyling it in place would restyle
// them. An injected entry names its bank per entry, so only this one moved -- the fill,
// the moon, the starfields, the clouds and the sandstorm sky are all still nightDesert's.
//
// ONE COPY, NOT TWO. The stock strip was 440 px tall and needed a second offset copy to
// reach; this one is 1302 and covers the same span on its own. Keeping both would draw an
// opaque sheet twice for nothing.
// y is -241, up 100 from the -141 the stock strip used. The gradient is anchored on its
// CENTRE, so a taller strip grows in both directions and its top edge landed below the
// stacked back/2 tiles -- which showed as a band of near-black across the very top of
// the sky. Lifting the centre lifts that edge past them.
const BACKENTRY g_back1a = { 0,  162, -241, -10, -15, 1, 50,  0, 255, 0 };  // H tile, the gradient

// The moon and starfields. nightDesert back/3 is a full moon with a glow (312x312) and
// ani/0 and ani/1 are twinkling starfields. These fade with the CLOCK, not the weather,
// and sit in front of the tiled sky but behind the clouds.
// The moon stays at this authored position. It fades with the clock like the stars,
// while its small parallax keeps it in the sky when the camera moves.
const BACKENTRY g_aNight[] = {
    { 3,  346, -275,  -5,  -5, 0,   0,   0, 255, 0 },   // moon, slight parallax
    { 0,    0,    0,   0,   0, 3, 440, 360, 255, 1 },   // stars, H+V tiled, animated
    { 1,  150, -120,   0,   0, 3, 500, 400, 255, 1 },   // second starfield, offset so they interleave
};
// The sandstorm sky.
//
// This is the ONLY weather that swaps the backdrop rather than tinting it, and it works
// for a reason that is easy to miss: weather.cpp promotes the map's own backs in front of
// our injected band, but ONLY from index HILL_FIRST (2) upward. A v83 map's back/0 and
// back/1 are its sky, so those two stay BEHIND us. An injected sheet therefore covers the
// map's own sky and still sits behind its hills and trees, which is exactly what a sky
// swap needs and is the same trick the night backdrop uses.
//
// back/19 was chosen over back/21 and back/22 by rendering all three: 21 is scattered
// smoke wisps, 22 is a mountain silhouette, and only 19 is a solid dust sky.
//
// Type 1, horizontally tiled: one 800px sheet does not span a wide viewport.
//
// THE TWO ROWS ABUT, THEY DO NOT OVERLAP. back/19 is 800x350 and, like every stock back
// canvas, its origin is its centre, so a row at y covers [y-175, y+175]. The second row
// used to sit at y=60, which left [-115,-85] covered by BOTH rows: while the sandstorm is
// mid-fade that 30 px strip composites twice and renders at 1-(1-a)^2 instead of a, i.e.
// 0.75 against 0.50 at the halfway point. That is a hard-edged darker stripe running the
// full width of the viewport, present for the whole fade in and again for the whole fade
// out. y=90 puts the second row's top edge exactly on the first row's bottom edge.
const BACKENTRY g_aDust[] = {
    { 19, 0, -260, -6, -12, 1, 0, 0, 255, 0 },   // covers [-435, -85]
    { 19, 0,   90, -6, -12, 1, 0, 0, 255, 0 },   // covers [ -85, 265]
};

// The after-the-rain rainbow. Its own art, Map/Back/WeatherRainbow.img back/0, drawn by
// build_weather_rainbow.py because this client has no rainbow anywhere in it.
//
// Type 0, not tiled and not scrolling: it is one arc in one place, like the moon, and it
// takes the moon's small parallax so it sits in the sky rather than on the glass. It is
// injected BEHIND the clouds, so an overcast sky rolling back in covers it, which is what
// should happen.
//
// The canvas origin is its CENTRE, which is the convention every stock back canvas uses,
// so x and y here are where the middle of the arc goes.
const BACKENTRY g_rainbow = { 0, 0, -150, -5, -5, 0, 0, 0, 255, 0 };

// Clouds: nightDesert back/8 (800x183), scrolling copies at varied heights.
// type 4 = horizontally tiled + scrolling.
//
// rx IS THE SCROLL RATE, not a parallax factor: the engine moves the sheet 5*|rx| px/s in
// the -sign(rx) direction, forever, and hardcodes X parallax to 0 for type 4 at
// 0x0063E0D8. NEGATIVE therefore means rightward, which is the way the snow now slants
// (weatherwind.cpp pins the flake drift rightward because the sprite is a drawn streak).
// Three different rates is the parallax: the near sheet overtakes the far one.
const BACKENTRY g_aClouds[] = {
    { 8, -454, -340, -2, -50, 4, 0, 0, 255, 0 },   // far,  10 px/s right
    { 8,  120, -420, -3, -50, 4, 0, 0, 255, 0 },   // mid,  15 px/s
    { 8, -700, -270, -4, -50, 4, 0, 0, 255, 0 },   // near, 20 px/s
};

// Rain: ancientForest back/28-31 as foreground sheets (front=1).
// type 7 = tiled + vertically scrolling, i.e. falling.
// The blizzard fog. Map/Back/WeatherFog.img, built by build_weather_fog.py.
//
// front=1, so it sits in FRONT of the map like the rain sheets do: fog that the terrain
// draws over is not fog, it is a sky. The near sheet is the faster and the thinner of the
// two; see the tool for why the pair exists.
//
// type 4 = horizontally tiled + scrolling, and cx is filled from the art at injection for
// exactly the reason the clouds now are: the drift wraps on the tile pitch, so the two
// have to be the same number or the sheet walks out of step with its own tiling.
// rx IS THE ENGINE'S OWN SCROLL SPEED on a type 4 back, not a parallax factor. MakeBack
// turns it into 100 px per 20000/|rx| ms in the -sign(rx) direction (0x0063DF25), and X
// parallax is hardcoded to 0 for type 4 at 0x0063E0D8. At -14 / -26 that was a permanent
// 70 / 130 px/s LEFTWARD scroll that the wind-driven drift had to fight, so any rightward
// gust under about 110 left the fog visibly blowing against the snow.
//
// -1 leaves 5 px/s, under 8% of the drift floor, so the wind decides the direction.
// IT MUST NOT BE 0: the idiv at 0x0063DF2B runs BEFORE the rx == 0 guard at 0x0063DF44,
// so a type 4 back with rx 0 is a divide by zero.
// A type 4 back tiles HORIZONTALLY ONLY, so each of these is a single row of tiles at one
// height, and y is what places the band. Those four heights are chosen to overlap.
//
// rx is the engine's own scroll speed, 5 * |rx| px/s, and NEGATIVE IS RIGHTWARD. That is
// read out of the binary rather than taken from the paragraph above, which has the word
// backwards: MakeBack loads rx into esi at 0x0063DEE9 and at 0x0063DF2F does
// `test esi, esi; jle`, negating the delta only when rx is POSITIVE.
//
// The four rates are deliberately not multiples of each other, for the same reason the four
// widths are not: equal or harmonic speeds put the sheets back in step on a short cycle.
//
// IT MUST NOT BE 0: the idiv at 0x0063DF2B runs BEFORE the rx == 0 guard at 0x0063DF44,
// so a type 4 back with rx 0 is a divide by zero.
const BACKENTRY g_aFog[] = {
    { 0,    0,  -40, -22, -6, 4, 0, 0, 255, 0 },   // far bank,  1024x460, 110 px/s right
    { 1,    0,   90, -37, -4, 4, 0, 0, 255, 0 },   // mid lumps,  900x380, 185 px/s
    { 2,    0,  -10, -61, -8, 4, 0, 0, 255, 0 },   // near wisps, 640x300, 305 px/s
    { 3,    0, -150, -13, -3, 4, 0, 0, 255, 0 },   // high veil,  800x240,  65 px/s
};
// The snow planes. Map/Back/WeatherSnow.img, imported by build_weather_snow.py.
//
// EVERY NUMBER HERE IS THE SOURCE MAP'S, NOT A GUESS. Eight maps in the set this art came
// from place exactly these two backs, and all eight use these values:
//
//   no=0  x=-21   y=-212  rx=-20  ry=5   type=7  cx=1000 cy=300  front=0
//   no=1  x=-270  y=-249  rx=0    ry=10  type=7  cx=900  cy=500  front=1   (source ani/2)
//
// CX AND CY ARE NOT THE CANVAS SIZE, and that is the one thing to preserve. The far sheet
// is 802x144 on a 1000x300 pitch and the near one 841x114 on a 900x500 pitch, so the tiled
// copies are spaced with a 198x156 and a 59x386 GAP. Abut them instead -- which is what
// happens if anything auto-fills cx/cy from the art, as the clouds and the fog legitimately
// do -- and the repeat lands on a regular grid and reads as wallpaper rather than weather.
//
// THE TWO SIT ON OPPOSITE SIDES OF THE MAP. front=0 puts the far plane behind the scenery
// and front=1 puts the near plane over everything including the player. That split is the
// depth, more than the size difference is; injecting both at the same front loses it.
//
// ry is the fall rate on a type 7 back and the near plane's is double the far one's. rx=0
// is safe HERE, unlike on the type 4 fog: the divide that makes rx 0 fatal at 0x0063DF2B
// is on the type 4 path, and a type 7 back reaches it through a different branch. The far
// plane's -20 is a slow sideways drift, not a parallax factor.
const BACKENTRY g_aSnow[] = {
    {  0,  -21, -212, -20,   5, 7, 1000, 300, 255, 1 },   // far,  behind the map
    {  1, -270, -249,   0,  10, 7,  900, 500, 255, 1 },   // near, in front of the player
};

const BACKENTRY g_aRain[] = {
    { 28, -330, -435, -100, 207, 7, 700,  400, 255, 0 },
    { 29,  136, -195, -100, 205, 7, 500,  500, 255, 0 },
    { 30,  165,  -26, -100, 195, 7, 750,  450, 255, 0 },
    { 31, -623,  -52, -100, 200, 7, 500, 1200, 255, 0 },
};

unsigned char g_uSky    = Weather::SKY_CLEAR;
bool          g_bActive = false;   // currently in a sky field

unsigned int g_nSkyBase   = 0;     // dynamic back index ranges, recomputed per entry
unsigned int g_nNightBase = 0;
unsigned int g_nDustBase = 0;
unsigned int g_nRainbowBase = 0;
unsigned int g_nCloudBase = 0;
unsigned int g_nRainBase  = 0;
unsigned int g_nFogBase   = 0;
unsigned int g_nSnowBase  = 0;
bool         g_bHaveBase  = false;

float g_fDustLevel = 0.0f, g_fDustTarget = 0.0f;
// The blizzard fog. Its own level so it can fade independently of the cloud sheets, which
// a blizzard also raises to full.
float g_fFogLevel = 0.0f, g_fFogTarget = 0.0f;
float g_fRainbowLevel = 0.0f, g_fRainbowTarget = 0.0f;
float g_fCloudLevel = 0.0f, g_fCloudTarget = 0.0f;
float g_fRainLevel  = 0.0f, g_fRainTarget  = 0.0f;
// Falling snow, its own level: a blizzard raises the cloud and the fog to full and
// leaves the sheets alone, because the blizzard's snow is still the particle blower.
float g_fSnowLevel  = 0.0f, g_fSnowTarget  = 0.0f;
float g_fLightningLevel = 0.0f;
float g_fFadeStep   = FX_FADE_STEP;   // per profile; storms roll in slower than they clear
int   g_nNativeOn   = 0;              // the BlowWeather item currently installed, 0 for none

std::vector<IWzGr2DLayerPtr> g_vSky;
std::vector<IWzGr2DLayerPtr> g_vNight;

std::vector<IWzGr2DLayerPtr> g_vDust;
std::vector<IWzGr2DLayerPtr> g_vRainbow;
std::vector<IWzGr2DLayerPtr> g_vClouds;
std::vector<IWzGr2DLayerPtr> g_vRain;
std::vector<IWzGr2DLayerPtr> g_vFog;
std::vector<IWzGr2DLayerPtr> g_vSnow;
// PER SHEET, not per entry. CMapLoadable::MakeGrid (0x0063E2C5) turns ONE type 4 back
// entry into a canvas-less template plus (nTilesX + 1) tile layers, every one of them
// built through the same IWzGr2D::CreateLayer weather.cpp hooks, so g_vClouds and g_vFog
// hold 4 to 7 layers PER SHEET rather than one. Indexing them as [sheet] therefore moved
// individual tiles -- including two neighbouring tiles of the same sheet at two different
// rates -- and left the rest standing still. That is the gap the user reported, in both
// the clouds and the brand new fog. Grouping by sheet is what lets a sheet move as one.
std::vector<IWzGr2DLayerPtr> g_aCloudSheet[FX_CLOUD_COUNT];
std::vector<IWzGr2DLayerPtr> g_aFogSheet[FX_FOG_COUNT];

void AddBack(IWzPropertyPtr pBack, unsigned int uIndex, const wchar_t* sBS,
             const BACKENTRY& e, long lFront, long lDY = 0) {
    IWzPropertyPtr pEntry;
    PcCreateObject<IWzPropertyPtr>(L"Property", pEntry, nullptr);
    pEntry->Add(L"bS", Ztl_variant_t(sBS));
    pEntry->Add(L"front", lFront);
    pEntry->Add(L"ani", e.ani);
    pEntry->Add(L"f", 0L);
    pEntry->Add(L"no", e.no);
    pEntry->Add(L"x", e.x);
    pEntry->Add(L"y", e.y + lDY);
    pEntry->Add(L"rx", e.rx);
    pEntry->Add(L"ry", e.ry);
    pEntry->Add(L"type", e.type);
    pEntry->Add(L"cx", e.cx);
    pEntry->Add(L"cy", e.cy);
    pEntry->Add(L"a", e.a);
    wchar_t sName[16];
    swprintf_s(sName, L"%u", uIndex);
    pBack->Add(sName, Ztl_variant_t(static_cast<IUnknown*>(pEntry), true));
}

// Read a back canvas's real size so the tiler abuts tiles instead of overlapping them
// by about a pixel, which is what double blends into dark seam lines during a fade.
void QueryBackCanvasSize(const wchar_t* sBS, long no, int* pcx, int* pcy) {
    *pcx = 0;
    *pcy = 0;
    wchar_t uol[128];
    swprintf_s(uol, L"Map/Back/%s.img/back/%ld", sBS, no);
    try {
        Ztl_variant_t v = get_rm()->GetObjectA(uol);
        IUnknownPtr pUnk = v.GetUnknown();
        IWzCanvasPtr pCanvas;
        if (pUnk && SUCCEEDED(pUnk->QueryInterface(__uuidof(IWzCanvas), reinterpret_cast<void**>(&pCanvas))) && pCanvas) {
            *pcx = pCanvas->width;
            *pcy = pCanvas->height;
        }
    } catch (const _com_error&) {}
}

// ------------------------------------------------- wind on the clouds and the fog
//
// THE ENGINE SCROLLS THESE ITSELF, AND NOTHING HERE MAY TRANSLATE THEM.
//
// A type 4 back is horizontally tiled AND self scrolling. CMapLoadable::MakeBack builds a
// standalone Shape2D vector and gives it RelMove(x, y, now + 20000/|rx|, VM_FOREVER) at
// 0x0063E049, which is a constant 5*|rx| px/s in the -sign(rx) direction, forever. It then
// hands the entry to the tiler, MakeGrid at 0x0063E2C5, which creates one layer per tile
// and gives EACH ONE
//
//     WrapClip(Gr2D.center, -(cx + xSpan/2), -(cy + ySpan/2), xSpan + cx, ySpan + cy)
//
// at 0x0063EB96. That wrap band is anchored to the CAMERA CENTRE and re-evaluated as the
// camera moves, and each tile is wrapped into it modulo the band. So a tile's on screen
// position is a function of its own coordinates MODULO that band, not of where it was put.
//
// Translating a tile with InterLockedOffset therefore does not slide the sheet: it moves
// that tile to a different place in the wrap band. Two tiles land on the same slot, or a
// slot is left empty, and what appears on screen is hard edged rectangular blocks of sky
// appearing and disappearing. Three separate attempts were made to keep a wind driven
// drift and all three produced that artifact:
//
//   1. per entry drift        -- moved individual TILES, because g_vClouds holds one layer
//                                per tile plus a template, not one per sheet
//   2. cx filled from the art -- a no op; at magLevel 0 the engine's auto cx already IS
//                                the canvas width (0x0063E36A)
//   3. per sheet grouping     -- moved every tile of a sheet by the same delta, which is
//                                still a translate, and still lands them in the wrong
//                                wrap slots
//
// So the drift is gone. Speed and direction now live entirely in each entry's rx, which is
// the field the engine provides for exactly this and which cannot desynchronise from the
// tiling because the engine owns both. The cost is that the scroll is CONSTANT rather than
// following the prevailing gust; the wind still drives the snow, the sway and the sand.

void ApplyBackFade(std::vector<IWzGr2DLayerPtr>& v, unsigned int uColor) {
    for (auto& p : v) {
        if (p) { try { p->color = uColor; } catch (const _com_error&) {} }
    }
}

void StepFade(float& level, float target) {
    if (level < target) {
        level += g_fFadeStep;
        if (level > target) level = target;
    } else if (level > target) {
        level -= g_fFadeStep;
        if (level < target) level = target;
    }
}

// The engine's own weather. The message is an empty ZXString (null buffer), which
// suppresses the on-screen notice: the server's own startMapEffect path passes a
// real message and WOULD show a banner, which is why ambient weather does not use it.
// There is no client-side auto-expiry, so one call persists until removed.
//
// KNOWN LIMIT: the field has exactly ONE weather slot. The builder calls
// WeatherLayer_RemoveAll before installing, so a second BlowWeather replaces the
// first, and this module shares that slot with the stock cash weather items
// (UseCashItemHandler -> MapleMap.startMapEffect -> LP_BlowWeather, which is live on
// this server). Two consequences, both cosmetic and both rare:
//   - a player uses a weather item while it is snowing, then the world rolls off snow:
//     StopNative wipes the whole slot and the item's effect ends early
//   - a player uses one WHILE it is snowing: their item replaces ours, and g_nNativeOn
//     still names our effect, so the ambient one does not come back until the profile
//     changes or the player changes map
// Fixing it properly means observing the server's own weather packet
// (CField::OnBlowWeather, 0x00535179) so this module knows when it no longer owns
// the slot. That is a new hook on a packet path and is deliberately NOT taken here
// without a runtime test: a blind hook on a packet-decode path is exactly what broke
// login once before. See IMPLEMENTATION.md.
void StartNative(int nItemId) {
    CField* pField = get_field();
    if (!pField) return;
    using BlowWeather_t = void(__thiscall*)(CField*, int, ZXString<char>);
    try {
        reinterpret_cast<BlowWeather_t>(ADDR_BLOWWEATHER)(pField, nItemId, ZXString<char>());
    } catch (const _com_error&) {}
}

// BlowWeather(0) only starts a slow fade that can stick, so teardown uses the same
// hard removal the engine itself uses on map close.
void StopNative() {
    CField* pField = get_field();
    if (!pField) return;
    using RemoveAll_t = void(__thiscall*)(CField*);
    try {
        reinterpret_cast<RemoveAll_t>(ADDR_WEATHER_REMOVE)(pField);
    } catch (const _com_error&) {}
}

// Everything this module does is now read off the profile row, so a new sky is a
// line of data rather than another branch here. The old shape was three hardcoded
// tests against SKY_CLEAR / SKY_RAIN / SKY_SNOW, which could not express a storm
// (rain AND full cloud AND a slower fade) at all.
// The rainbow's fade target. Split out of Update because RefreshTargets has to be able to
// compute it too: OnEnterField and SetSky(bSnap) both SNAP every level to its target, and
// this was the one target RefreshTargets did not recompute. Update owns it, but Update
// early-returns whenever g_bActive is false, so after any stretch in a non-sky field the
// target stayed frozen at whatever the last sky map left -- and the entry snap replayed
// it, painting a full rainbow arc that then faded out over about half a second.
void RefreshRainbowTarget() {
    g_fRainbowTarget = 0.0f;
    if (Weather::RainbowSecsLeft() > 0) {
        const float fDay = 1.0f - Weather::NightLevel();
        if (fDay > 0.0f) {
            g_fRainbowTarget = RAINBOW_ALPHA * fDay;
        }
    }
}

void RefreshTargets() {
    const Weather::Profile& p = Weather::CurrentProfile();
    g_fCloudTarget = p.fCloud;
    g_fRainTarget  = p.fRain;
    g_fFadeStep    = p.fFadeStep;
    RefreshRainbowTarget();
    // The one sky driven by its ID rather than by a column of the profile row. A backdrop
    // swap is not a continuous quantity like cloud or rain alpha: exactly one sky has one,
    // so a whole column carrying 0.0 for the other eight would be worse than this test.
    g_fDustTarget  = (Weather::CurrentSky() == Weather::SKY_SANDSTORM) ? 1.0f : 0.0f;
    // Fog belongs to the blizzard alone. Plain snow gets the oblong flakes and nothing
    // else: a blizzard is snow you cannot see through, and that distinction is the fog.
    g_fFogTarget   = (Weather::CurrentSky() == Weather::SKY_BLIZZARD) ? 1.0f : 0.0f;
    // Snow sheets belong to plain snow alone, for the mirror of the reason the fog belongs
    // to the blizzard alone. A blizzard is a wall of driven particles plus fog; these two
    // planes are individually legible flakes at two distances, which is the opposite
    // reading. Running both at once gives a blizzard with tidy foreground snowflakes in it.
    //
    // Driven by the sky ID rather than a profile column for the same reason the sandstorm
    // backdrop is: one sky has it, so a column carrying 0.0 for the other eight rows would
    // be more to maintain and no clearer.
    g_fSnowTarget  = (Weather::CurrentSky() == Weather::SKY_SNOW) ? 1.0f : 0.0f;

    // The native particle effect. Tracked by ITEM ID rather than by a boolean, because
    // several profiles use the engine and they use DIFFERENT effects: switching snow to
    // maple leaves has to tear the first one down, and a bool cannot see that.
    const int nWant = g_bActive ? p.nNativeItem : 0;
    if (nWant != g_nNativeOn) {
        if (g_nNativeOn != 0) {
            StopNative();
        }
        if (nWant != 0) {
            StartNative(nWant);
        }
        g_nNativeOn = nWant;
    }

    WeatherSound_SetWanted(g_bActive ? p.uSound : (unsigned char)Weather::SND_NONE);
}

}  // namespace


// Add the cloud + rain entries to this field's back list.
//
// Entries are added ONCE (marker-gated, because WZ properties are cached and
// shared), but the index RANGES are recomputed on EVERY entry. MakeBack classifies
// by range, and a portal back to a previously visited map reuses the cached
// property: ranges computed only on first injection would go stale the moment
// another map was visited, and every back layer here would be misclassified.
//
// THE MARKER MUST LIVE ON THE SAME OBJECT AS THE BACK LIST. m_pPropFieldInfo (+0x2C)
// and m_pPropField (+0x30) are NOT two views of one map: when a map carries
// info/link the client keeps the LINKING map's own info at +0x2C and swaps only the
// BODY at +0x30 to the link target. The original wrote the marker to +0x2C while
// appending entries to +0x30's back list, which is only harmless because it only
// ever ran on unlinked maps.
//
// It is not harmless here. 2266 maps (42%) are linked, and 178 targets are shared:
// 99 maps link to 100020100 alone. With the marker on the private info node, every
// distinct linking map looks un-injected and appends another 7 entries to the SAME
// cached back list. Entering all 99 would leave 693 entries on it, the ranges would
// classify the newest batch as ours and every older batch as "the map's own backs",
// and those orphans get driven at full alpha: permanent opaque rain over the map,
// plus an unbounded list RestoreBack walks on every rebuild.
//
// Reaching the marker through the BODY's info node makes the two agree by
// construction. On an unlinked map pPropField->item["info"] IS m_pPropFieldInfo, so
// nothing changes there.
//
// The entries MUST be contiguous with the map's own backs. A gap makes RestoreBack
// call MakeBack(null) and crash.
void WeatherFx::Inject(CMapLoadable* pField) {
    if (!pField) {
        return;
    }
    IWzPropertyPtr pPropField = pField->m_pPropField;
    if (!pPropField) {
        return;
    }
    IWzPropertyPtr pBack;
    IUnknownPtr pUnkBack = pPropField->item[L"back"].GetUnknown();
    if (!pUnkBack || FAILED(pUnkBack->QueryInterface(&pBack)) || !pBack) {
        return;
    }

    // The marker node: the BODY's info, falling back to the body itself.
    IWzPropertyPtr pMarker;
    IUnknownPtr pUnkInfo = pPropField->item[L"info"].GetUnknown();
    if (pUnkInfo) {
        pUnkInfo->QueryInterface(&pMarker);
    }
    if (!pMarker) {
        pMarker = pPropField;
    }

    const unsigned int uTotal = FX_SKY_COUNT + FX_DUST_COUNT + FX_NIGHT_COUNT
                              + FX_RAINBOW_COUNT + FX_CLOUD_COUNT + FX_RAIN_COUNT
                              + FX_FOG_COUNT + FX_SNOW_COUNT;

    // The marker stores the COUNT injected, not a bare 1. WZ properties are cached for
    // the session, so if this build's layout differs from whatever injected into this
    // property earlier (a DLL swapped under a running client, or a future build that
    // adds a layer), the recovered base would be wrong by the difference and would
    // misclassify that many of the map's own backs as ours, which drives them at full
    // alpha. A mismatch is not recoverable in place, so bail and leave the map stock;
    // it self-heals on the next client start, when the property is read fresh.
    const int nMarked = get_int32(pMarker->item[FX_MARKER], 0);
    if (nMarked != 0 && nMarked != (int)uTotal) {
        g_bHaveBase = false;
        LOG_ONCE("weatherfx: field already carries %d injected backs, this build wants %u; "
                 "leaving the map stock until restart", nMarked, uTotal);
        return;
    }
    const bool bInjected = nMarked != 0;

    // On re-entry our entries are the last uTotal children, so the base is
    // recoverable from the current count.
    //
    // The count guard is a backstop, and its original justification was wrong: it claimed
    // a throw between the first AddBack and the marker write could leave the marker set on
    // a short list, but the marker is written LAST, so such a throw leaves it UNSET. The
    // guard could never fire from the case it named. It is kept because an unsigned
    // (count - uTotal) wrapping to ~4 billion is a bad enough outcome to be worth a cheap
    // test, however it is reached. The REACHABLE version of that hazard is handled at the
    // end of this function, where the marker now records what was actually appended.
    const unsigned int uCount = pBack->count;
    if (bInjected && uCount < uTotal) {
        g_bHaveBase = false;
        DEBUG_MESSAGE("weatherfx: marker set but only %u backs (< %u); disabling", uCount, uTotal);
        return;
    }
    unsigned int uBase = bInjected ? (uCount - uTotal) : uCount;
    g_nSkyBase   = uBase;
    g_nDustBase  = uBase + FX_SKY_COUNT;
    g_nNightBase = g_nDustBase + FX_DUST_COUNT;
    g_nRainbowBase = g_nNightBase + FX_NIGHT_COUNT;
    g_nCloudBase = g_nRainbowBase + FX_RAINBOW_COUNT;
    g_nRainBase  = g_nCloudBase + FX_CLOUD_COUNT;
    g_nFogBase   = g_nRainBase + FX_RAIN_COUNT;
    g_nSnowBase  = g_nFogBase + FX_FOG_COUNT;
    g_bHaveBase  = true;

    if (bInjected) {
        return;
    }

    unsigned int uIdx = uBase;
    // EVERY AddBack IS INSIDE THIS TRY. A COM failure part way through -- PcCreateObject
    // under memory pressure, an IWzProperty::Add throwing -- used to propagate out to
    // LoadMap_hook's catch with the marker unwritten and a partial batch already appended
    // to the field's CACHED back list. On the next visit to that map, or to any of the up
    // to 99 maps sharing the list through info/link, nMarked was still 0, so a second full
    // batch went on top of the orphans; the orphans were then classified as the map's own
    // backs and driven at full alpha, and the first of them is g_back0, an OPAQUE tiled
    // fill. The map's hills and trees vanish behind flat sky, and the list grows by uTotal
    // on every subsequent visit.
    bool bThrew = false;
    try {
    // The tiled sky first, so it is the backmost of everything we add.
    AddBack(pBack, uIdx++, L"nightDesert", g_back0,  0L, SKY_DY);
    AddBack(pBack, uIdx++, L"MapleMoonSky", g_back1a, 0L, SKY_DY);
    // NO back/2 STACK. It was ten near-black tiles continuing the sky above the stock
    // 440 px gradient, which reached only -384. The private strip spans -992..310 on its
    // own -- higher than the whole stack, whose top was -884 -- so every copy landed INSIDE
    // the gradient and, being injected after it, painted a dark band across it. That band
    // is what removing this fixes; moving the gradient only slid it under the same tiles.
    // Straight after the tiled night sky and before the moon: the dust sky replaces the
    // sky, so nothing that belongs IN the sky may sit behind it.
    for (unsigned int i = 0; i < FX_DUST_COUNT; ++i) {
        AddBack(pBack, uIdx++, L"nightDesert", g_aDust[i], 0L, SKY_DY);
    }
    for (unsigned int i = 0; i < FX_NIGHT_COUNT; ++i) {
        AddBack(pBack, uIdx++, L"nightDesert", g_aNight[i], 0L);     // front=0, backmost of ours
    }
    AddBack(pBack, uIdx++, L"WeatherRainbow", g_rainbow, 0L);        // front=0, behind the clouds
    // cx is left at 0 deliberately: at magLevel 0 the engine's auto value (0x0063E36A)
    // is already exactly the canvas width, so writing 800 here is a no-op. Speed and
    // direction live in rx; see the note above the fade helpers.
    for (unsigned int i = 0; i < FX_CLOUD_COUNT; ++i) {
        AddBack(pBack, uIdx++, L"nightDesert", g_aClouds[i], 0L);    // front=0, in the sky
    }
    for (unsigned int i = 0; i < FX_RAIN_COUNT; ++i) {
        AddBack(pBack, uIdx++, L"ancientForest", g_aRain[i], 1L);    // front=1, foreground
    }
    // The fog goes LAST, so it is the frontmost thing we inject: in a blizzard it is
    // between the player and everything else, which is the whole point of it.
    for (unsigned int i = 0; i < FX_FOG_COUNT; ++i) {
        AddBack(pBack, uIdx++, L"WeatherFog", g_aFog[i], 1L);        // front=1, foreground
    }
    // The snow planes carry their own front per row, unlike every other group here: the
    // far one goes BEHIND the map and the near one in FRONT of the player, and that split
    // is most of what makes them read as depth. Injecting both at one front loses it.
    for (unsigned int i = 0; i < FX_SNOW_COUNT; ++i) {
        AddBack(pBack, uIdx++, L"WeatherSnow", g_aSnow[i], i == 0 ? 0L : 1L);
    }
    } catch (const _com_error& e) {
        bThrew = true;
        LOG_ONCE("weatherfx: inject threw hr=0x%08X after %u of %u entries",
                 (unsigned int)e.Error(), uIdx - uBase, uTotal);
    }

    // THE MARKER RECORDS WHAT WAS ACTUALLY APPENDED, not what was intended.
    //
    // That is what makes a partial inject self-limiting. The mismatch bail near the top of
    // this function refuses any field whose marker disagrees with uTotal, so recording a
    // short count means the next visit leaves the map stock instead of stacking a second
    // batch on the orphans. A count of 0 is the one value that means "nothing to clean up",
    // and it correctly reads as not-injected, so that case retries from scratch.
    unsigned int uAppended = uIdx - uBase;
    try {
        const unsigned int uNow = pBack->count;
        uAppended = (uNow > uBase) ? (uNow - uBase) : 0;
    } catch (const _com_error&) {
    }

    // The counts and the AddBack calls are maintained by hand and must agree: a
    // mismatch makes the index ranges classify the wrong layers as ours, which drives
    // some of the map's own backs at our alpha. Catch it here rather than in game.
    if (bThrew || uAppended != uTotal) {
        g_bHaveBase = false;
        try { pMarker->Add(FX_MARKER, (long)uAppended); } catch (const _com_error&) {}
        LOG_ONCE("weatherfx: appended %u of %u entries; leaving this map stock until restart",
                 uAppended, uTotal);
        return;
    }
    pMarker->Add(FX_MARKER, (long)uTotal);
}

unsigned int WeatherFx::InjectedLastIndex() {
    return g_bHaveBase ? (g_nFogBase + FX_FOG_COUNT - 1) : 0;
}

void WeatherFx::SetSky(unsigned char uSky, bool bSnap) {
    if (uSky == g_uSky && !bSnap) {
        return;
    }
    g_uSky = uSky;
    RefreshTargets();
    if (bSnap && g_bActive) {
        // Map-entry packets arrive after the map's initial OnEnterField call. The
        // first call necessarily used the previous field's profile, so snap the real
        // packet profile here instead of visibly fading from that stale state.
        g_fCloudLevel = g_fCloudTarget;
        g_fRainLevel = g_fRainTarget;
        g_fRainbowLevel = g_fRainbowTarget;
        g_fDustLevel = g_fDustTarget;
        g_fFogLevel = g_fFogTarget;
        g_fSnowLevel = g_fSnowTarget;
        Reapply();
    }
    DEBUG_MESSAGE("weatherfx: sky -> %d", (int)uSky);
}

// g_bHaveBase, not a base != 0 test: a map with no native backs would legitimately
// put our first cloud at index 0, and the original's `base != 0` guard silently
// disabled the whole module on exactly that map.
bool WeatherFx::IsSkyIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nSkyBase && nIndex < (int)(g_nSkyBase + FX_SKY_COUNT);
}
bool WeatherFx::IsDustIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nDustBase
        && nIndex < (int)(g_nDustBase + FX_DUST_COUNT);
}

bool WeatherFx::IsRainbowIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nRainbowBase
        && nIndex < (int)(g_nRainbowBase + FX_RAINBOW_COUNT);
}

bool WeatherFx::IsNightIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nNightBase && nIndex < (int)(g_nNightBase + FX_NIGHT_COUNT);
}
bool WeatherFx::IsCloudIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nCloudBase && nIndex < (int)(g_nCloudBase + FX_CLOUD_COUNT);
}
int WeatherFx::CloudSlot(int nIndex) {
    return IsCloudIndex(nIndex) ? (nIndex - (int)g_nCloudBase) : -1;
}
int WeatherFx::FogSlot(int nIndex) {
    return IsFogIndex(nIndex) ? (nIndex - (int)g_nFogBase) : -1;
}
bool WeatherFx::IsFogIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nFogBase && nIndex < (int)(g_nFogBase + FX_FOG_COUNT);
}
bool WeatherFx::IsRainIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nRainBase && nIndex < (int)(g_nRainBase + FX_RAIN_COUNT);
}
bool WeatherFx::IsSnowIndex(int nIndex) {
    return g_bHaveBase && nIndex >= (int)g_nSnowBase && nIndex < (int)(g_nSnowBase + FX_SNOW_COUNT);
}

void WeatherFx::CaptureSky(const IWzGr2DLayerPtr& pLayer) { if (pLayer) g_vSky.push_back(pLayer); }
void WeatherFx::CaptureNight(const IWzGr2DLayerPtr& pLayer) { if (pLayer) g_vNight.push_back(pLayer); }
void WeatherFx::CaptureDust(const IWzGr2DLayerPtr& pLayer) { if (pLayer) g_vDust.push_back(pLayer); }
void WeatherFx::CaptureRainbow(const IWzGr2DLayerPtr& pLayer) { if (pLayer) g_vRainbow.push_back(pLayer); }
void WeatherFx::CaptureCloud(const IWzGr2DLayerPtr& pLayer, int nSlot) {
    if (!pLayer) return;
    g_vClouds.push_back(pLayer);
    if (nSlot >= 0 && nSlot < FX_CLOUD_COUNT) g_aCloudSheet[nSlot].push_back(pLayer);
}
void WeatherFx::CaptureRain(const IWzGr2DLayerPtr& pLayer)  { if (pLayer) g_vRain.push_back(pLayer); }
// FLAT, with no per-sheet vector beside it, unlike the clouds and the fog. Those need one
// because a code-driven drift has to move a whole sheet's tiles together; these two scroll
// on the engine's own ry and nothing here ever translates them.
void WeatherFx::CaptureSnow(const IWzGr2DLayerPtr& pLayer)  { if (pLayer) g_vSnow.push_back(pLayer); }
void WeatherFx::CaptureFog(const IWzGr2DLayerPtr& pLayer, int nSlot) {
    if (!pLayer) return;
    g_vFog.push_back(pLayer);
    if (nSlot >= 0 && nSlot < FX_FOG_COUNT) g_aFogSheet[nSlot].push_back(pLayer);
}

void WeatherFx::ClearBackLayers() {
    g_vSky.clear();
    g_vNight.clear();
    g_vDust.clear();
    g_vRainbow.clear();
    g_vClouds.clear();
    g_vRain.clear();
    g_vFog.clear();
    g_vSnow.clear();
    for (int i = 0; i < FX_CLOUD_COUNT; ++i) g_aCloudSheet[i].clear();
    for (int i = 0; i < FX_FOG_COUNT; ++i)   g_aFogSheet[i].clear();
    g_fLightningLevel = 0.0f;
}

void WeatherFx::OnLeaveField() {
    WeatherSound_Shutdown();
    // Before ClearBackLayers, and unconditionally: these layers hold references to the
    // field's own art, so they must not outlive the map.
    WeatherSplash_Shutdown();
    WeatherAccum_Shutdown();
    WeatherPuddle_Shutdown();
    WeatherSway_Shutdown();
    ClearBackLayers();
    g_bActive   = false;
    g_bHaveBase = false;
    // Engine weather is per field and is cleared by the map change itself, so the
    // flag is dropped rather than the effect removed: get_field() already points
    // somewhere new by the time this runs.
    g_nNativeOn = 0;
    g_fLightningLevel = 0.0f;
}

void WeatherFx::OnEnterField(bool bSkyField) {
    g_bActive = bSkyField;
    if (!bSkyField) {
        return;
    }
    // Snap to the current targets on entry; only a weather CHANGE fades.
    RefreshTargets();
    g_fCloudLevel = g_fCloudTarget;
    g_fRainLevel  = g_fRainTarget;
    g_fRainbowLevel = g_fRainbowTarget;
    g_fDustLevel = g_fDustTarget;
    g_fSnowLevel = g_fSnowTarget;
    Reapply();
}

void WeatherFx::Reapply() {
    ApplyBackFade(g_vSky,    Weather_SkyBackdropColor());
    ApplyBackFade(g_vNight,  Weather_NightSkyColor());
    // The dust sky takes the full night tint like any other scenery, so a sandstorm that
    // runs into dusk goes dark rather than staying daytime orange against a black map.
    ApplyBackFade(g_vDust,   Weather_SceneryColor(g_fDustLevel));
    // CAPPED WELL SHORT OF OPAQUE. A blizzard should cost visibility, not playability:
    // at full level the map is still readable and the player and the platforms are still
    // legible through it. Two sheets multiply, so the pair reaches about 0.55 together.
    ApplyBackFade(g_vFog,    Weather_SceneryColor(g_fFogLevel * FOG_ALPHA_MAX));
    ApplyBackFade(g_vRainbow, Weather_SceneryColor(g_fRainbowLevel));
    ApplyBackFade(g_vClouds, Weather_SceneryColor(g_fCloudLevel));
    ApplyBackFade(g_vRain,   Weather_RainColor(g_fRainLevel));
    // The SCENERY tint, not the rain tint. Rain sheets take a fraction of the night
    // multiply because a black streak reads as a hole in the sky; snow is discrete white
    // flecks with a lot of transparent between them, so the full tint just makes them the
    // colour of the night they are falling through, which is right.
    ApplyBackFade(g_vSnow,   Weather_SceneryColor(g_fSnowLevel));
}

// ---------------------------------------------------------------- lightning
//
// Lightning is illumination first, not a bolt sprite pasted over the map. Its level
// feeds weather.cpp's existing tint path, so terrain, objects, NPCs, clouds and rain
// all brighten together. The server supplies the sky's precise age and a token derived
// from when it began, so players entering one regional storm see the same flash.
//
// The PATTERN is client-owned and selected by the current regional palette: rain on a
// coast rolls through in rapid squalls, forests hold a diffuse canopy glow, cities get
// sharp reflected shutter flashes, and high alpine / celestial regions occasionally
// light up for longer. The server sends no visual recipe, only the palette id and the
// shared timeline; retuning any of this is therefore a client-only art decision.
enum LightningKind {
    LIGHTNING_CLASSIC,
    LIGHTNING_HENESYS,
    LIGHTNING_COASTAL,
    LIGHTNING_FOREST,
    LIGHTNING_URBAN,
    LIGHTNING_CELESTIAL,
    LIGHTNING_ALPINE,
    LIGHTNING_ARID,
};

struct LightningPattern {
    unsigned int windowMs;
    unsigned int earliestMs;
    unsigned int pulseMs;
    unsigned int quietEvery;   // one window in N has no strike
    unsigned int clusterEvery; // one window in N gets a second independent flash
    float minBrightness;       // lower bound of the per-strike intensity roll
    LightningKind kind;
};

static unsigned int LightningHash(unsigned int x) {
    x ^= x >> 16;
    x *= 0x7FEB352Du;
    x ^= x >> 15;
    x *= 0x846CA68Bu;
    x ^= x >> 16;
    return x;
}

static LightningPattern LightningPatternForRegion() {
    switch (Weather::PaletteId()) {
        // Every palette has its own weather recipe. The visual silhouette is shared
        // where appropriate, but cadence, silence, clustering and intensity are all
        // regional so no two places storm with the same rhythm.
        case Weather::PALETTE_EL_NATH:          return { 19000u, 2000u, 1150u, 5u, 0u, 0.84f, LIGHTNING_ALPINE };
        case Weather::PALETTE_RIEN:             return { 22500u, 1600u, 1150u, 4u, 2u, 0.76f, LIGHTNING_ALPINE };
        case Weather::PALETTE_MUSHROOM_SHRINE:  return { 17500u, 1000u, 1100u, 6u, 5u, 0.72f, LIGHTNING_CLASSIC };
        case Weather::PALETTE_ELLINIA:          return { 18000u, 1500u, 1200u, 5u, 0u, 0.76f, LIGHTNING_FOREST };
        case Weather::PALETTE_PERION:           return { 25000u, 3000u,  380u, 3u, 0u, 0.88f, LIGHTNING_ARID };
        case Weather::PALETTE_KERNING_CITY:     return { 11000u,  800u,  640u, 9u, 2u, 0.84f, LIGHTNING_URBAN };
        case Weather::PALETTE_SHOWA:            return {  9500u,  500u,  640u, 8u, 2u, 0.80f, LIGHTNING_URBAN };
        case Weather::PALETTE_ORBIS:            return { 21000u, 2000u, 1500u, 4u, 3u, 0.72f, LIGHTNING_CELESTIAL };
        case Weather::PALETTE_MU_LUNG:          return { 20000u, 1400u, 1200u, 6u, 0u, 0.72f, LIGHTNING_FOREST };
        case Weather::PALETTE_ARIANT:           return { 28000u, 2500u,  380u, 4u, 0u, 0.78f, LIGHTNING_ARID };
        case Weather::PALETTE_SLEEPYWOOD:       return { 17000u, 1500u, 1200u, 5u, 2u, 0.82f, LIGHTNING_FOREST };
        case Weather::PALETTE_AQUA_ROAD:        return { 16000u, 1000u,  780u, 6u, 2u, 0.70f, LIGHTNING_COASTAL };
        case Weather::PALETTE_LEAFRE:           return { 19500u, 2200u, 1200u, 4u, 0u, 0.78f, LIGHTNING_FOREST };
        case Weather::PALETTE_LUDIBRIUM:        return { 19000u, 1800u, 1500u, 5u, 3u, 0.76f, LIGHTNING_CELESTIAL };
        case Weather::PALETTE_FLORINA:          return { 12000u,  700u,  780u, 6u, 2u, 0.85f, LIGHTNING_COASTAL };
        case Weather::PALETTE_AMORIA:           return { 18000u, 1200u, 1100u, 5u, 4u, 0.70f, LIGHTNING_CLASSIC };
        case Weather::PALETTE_LITH_HARBOUR:     return { 14000u, 1000u,  780u, 7u, 3u, 0.78f, LIGHTNING_COASTAL };
        case Weather::PALETTE_MAGATIA:          return { 23000u, 2000u,  380u, 3u, 0u, 0.80f, LIGHTNING_ARID };
        case Weather::PALETTE_NAUTILUS:         return { 13000u,  750u,  780u, 7u, 2u, 0.82f, LIGHTNING_COASTAL };
        case Weather::PALETTE_HENESYS:          return { 15000u,  500u, 1250u, 5u, 2u, 0.80f, LIGHTNING_HENESYS };
        case Weather::PALETTE_EREVE:            return { 23000u, 2500u, 1500u, 3u, 2u, 0.72f, LIGHTNING_CELESTIAL };
        case Weather::PALETTE_TEMPLE_OF_TIME:   return { 26000u, 3000u, 1500u, 3u, 0u, 0.68f, LIGHTNING_CELESTIAL };
        case Weather::PALETTE_ELLIN_FOREST:     return { 17500u, 1200u, 1200u, 5u, 2u, 0.80f, LIGHTNING_FOREST };
        case Weather::PALETTE_NEW_LEAF_CITY:    return { 10500u,  700u,  640u, 8u, 2u, 0.86f, LIGHTNING_URBAN };
        case Weather::PALETTE_FORMOSA:          return { 15500u, 1000u,  780u, 5u, 3u, 0.74f, LIGHTNING_COASTAL };
        case Weather::PALETTE_ZIPANGU:          return { 16500u,  900u, 1100u, 6u, 4u, 0.76f, LIGHTNING_CLASSIC };
        default:                                 return { 12000u,  700u, 1100u, 7u, 4u, 0.75f, LIGHTNING_CLASSIC };
    }
}

static float LightningEnvelope(LightningKind kind, unsigned int t, unsigned int variation) {
    switch (kind) {
        case LIGHTNING_HENESYS:
            // Henesys has several genuinely different storm silhouettes, chosen once
            // per strike. This avoids the old clockwork double-flash feeling.
            switch (variation & 3u) {
                case 0u: // One clean, isolated flash.
                    if (t < 95u)  return 1.00f - 0.30f * (float)t / 95.0f;
                    if (t < 590u) return 0.42f * (1.0f - (float)(t - 95u) / 495.0f);
                    return 0.0f;
                case 1u: // A short ragged burst that rolls under the clouds.
                    if (t < 45u)  return 1.00f - 0.30f * (float)t / 45.0f;
                    if (t < 145u) return 0.0f;
                    if (t < 210u) return 0.72f - 0.24f * (float)(t - 145u) / 65.0f;
                    if (t < 320u) return 0.0f;
                    if (t < 410u) return 0.90f - 0.36f * (float)(t - 320u) / 90.0f;
                    if (t < 700u) return 0.28f * (1.0f - (float)(t - 410u) / 290.0f);
                    return 0.0f;
                case 2u: // Long, distant sheet lightning before one bright return.
                    if (t < 170u) return 0.88f - 0.20f * (float)t / 170.0f;
                    if (t < 700u) return 0.58f - 0.17f * (float)(t - 170u) / 530.0f;
                    if (t < 840u) return 0.80f - 0.26f * (float)(t - 700u) / 140.0f;
                    return 0.30f * (1.0f - (float)(t - 840u) / 410.0f);
                default: // A compact double, but with a quieter tail than the classic.
                    if (t < 65u)  return 0.96f - 0.24f * (float)t / 65.0f;
                    if (t < 245u) return 0.34f - 0.14f * (float)(t - 65u) / 180.0f;
                    if (t < 360u) return 0.84f - 0.32f * (float)(t - 245u) / 115.0f;
                    if (t < 880u) return 0.30f * (1.0f - (float)(t - 360u) / 520.0f);
                    return 0.0f;
            }

        case LIGHTNING_COASTAL:
            // Three quick strikes under a long wet afterglow.
            if (t < 55u)  return 1.00f - 0.22f * (float)t / 55.0f;
            if (t < 145u) return 0.0f;
            if (t < 205u) return 0.82f - 0.20f * (float)(t - 145u) / 60.0f;
            if (t < 315u) return 0.0f;
            if (t < 390u) return 0.94f - 0.32f * (float)(t - 315u) / 75.0f;
            return 0.30f * (1.0f - (float)(t - 390u) / 390.0f);

        case LIGHTNING_FOREST:
            // A flash diffused by foliage: one strong entry, then a long green-black glow.
            if (t < 150u) return 0.88f - 0.20f * (float)t / 150.0f;
            if (t < 680u) return 0.46f - 0.16f * (float)(t - 150u) / 530.0f;
            if (t < 800u) return 0.62f - 0.24f * (float)(t - 680u) / 120.0f;
            return 0.30f * (1.0f - (float)(t - 800u) / 400.0f);

        case LIGHTNING_URBAN:
            // Buildings and wet pavement read as a rapid shutter of reflected light.
            if (t < 48u)  return 1.00f - 0.24f * (float)t / 48.0f;
            if (t < 105u) return 0.0f;
            if (t < 160u) return 0.78f - 0.20f * (float)(t - 105u) / 55.0f;
            if (t < 225u) return 0.0f;
            if (t < 295u) return 0.92f - 0.34f * (float)(t - 225u) / 70.0f;
            return 0.34f * (1.0f - (float)(t - 295u) / 345.0f);

        case LIGHTNING_CELESTIAL:
            // Distant sheet lightning holds the whole high sky pale before returning.
            if (t < 160u) return 0.92f - 0.20f * (float)t / 160.0f;
            if (t < 760u) return 0.46f - 0.13f * (float)(t - 160u) / 600.0f;
            if (t < 940u) return 0.76f - 0.22f * (float)(t - 760u) / 180.0f;
            return 0.42f * (1.0f - (float)(t - 940u) / 560.0f);

        case LIGHTNING_ALPINE:
            // Snow cloud turns one bolt into a wide, slow sheet of white.
            if (t < 220u) return 0.96f - 0.18f * (float)t / 220.0f;
            if (t < 760u) return 0.58f - 0.22f * (float)(t - 220u) / 540.0f;
            return 0.34f * (1.0f - (float)(t - 760u) / 390.0f);

        case LIGHTNING_ARID:
            // Short, dry crack with almost no lingering wet-air glow.
            if (t < 65u)  return 1.00f - 0.38f * (float)t / 65.0f;
            if (t < 150u) return 0.18f * (1.0f - (float)(t - 65u) / 85.0f);
            if (t < 220u) return 0.70f * (1.0f - (float)(t - 150u) / 70.0f);
            return 0.10f * (1.0f - (float)(t - 220u) / 160.0f);

        default: // LIGHTNING_CLASSIC
            // The default also varies between an isolated strike, the original double,
            // and a broader return flash; regional patterns above keep their own look.
            if ((variation % 3u) == 0u) {
                if (t < 85u)  return 1.00f - 0.32f * (float)t / 85.0f;
                if (t < 540u) return 0.40f * (1.0f - (float)(t - 85u) / 455.0f);
                return 0.0f;
            }
            if ((variation % 3u) == 1u) {
                if (t < 70u)  return 1.00f - 0.26f * (float)t / 70.0f;
                if (t < 170u) return 0.38f - 0.13f * (float)(t - 70u) / 100.0f;
                if (t < 270u) return 0.88f - 0.28f * (float)(t - 170u) / 100.0f;
                if (t < 520u) return 0.44f * (1.0f - (float)(t - 270u) / 250.0f);
                return 0.0f;
            }
            if (t < 150u) return 0.90f - 0.22f * (float)t / 150.0f;
            if (t < 620u) return 0.52f - 0.18f * (float)(t - 150u) / 470.0f;
            if (t < 770u) return 0.82f - 0.30f * (float)(t - 620u) / 150.0f;
            return 0.30f * (1.0f - (float)(t - 770u) / 330.0f);
    }
}

static float LightningEvent(const LightningPattern& p, unsigned int within, unsigned int h) {
    const unsigned int span = p.windowMs - p.earliestMs - p.pulseMs;
    const unsigned int at = p.earliestMs + ((h >> 4) % span);
    if (within < at || within - at >= p.pulseMs) {
        return 0.0f;
    }
    // No two storm windows feel equally intense, even when they choose the same silhouette.
    const float strength = p.minBrightness
                         + (1.0f - p.minBrightness) * (float)((h >> 24) & 0xFFu) / 255.0f;
    return LightningEnvelope(p.kind, within - at, h >> 12) * strength;
}

static float LightningPulse(unsigned int ageMs, unsigned int seed) {
    const LightningPattern p = LightningPatternForRegion();
    const unsigned int window = ageMs / p.windowMs;
    const unsigned int h = LightningHash(seed ^ (window * 0x9E3779B9u));
    if (p.quietEvery > 0u && h % p.quietEvery == 0u) {
        return 0.0f;
    }
    const unsigned int within = ageMs % p.windowMs;
    float level = LightningEvent(p, within, h);
    // Some fronts roll through in clusters. The independent second event breaks the
    // one-flash-per-window rhythm without sacrificing shared client synchronisation.
    if (p.clusterEvery > 0u && ((h >> 8) % p.clusterEvery) == 0u) {
        const float followUp = LightningEvent(p, within, LightningHash(h ^ 0xA511E9B3u));
        if (followUp > level) {
            level = followUp;
        }
    }
    return level;
}

void WeatherFx::TickLightning() {
    if (!g_bActive || Weather::CurrentSky() != Weather::SKY_STORM || g_fRainLevel < 0.70f) {
        g_fLightningLevel = 0.0f;
        return;
    }
    const int age = Weather::SkyElapsedMillis();
    g_fLightningLevel = age > 0 ? LightningPulse((unsigned int)age, Weather::SkyToken()) : 0.0f;
}

float WeatherFx::LightningLevel() {
    return g_fLightningLevel;
}

void WeatherFx::Update() {
    if (!g_bActive) {
        return;
    }
    StepFade(g_fCloudLevel, g_fCloudTarget);
    StepFade(g_fRainLevel, g_fRainTarget);
    StepFade(g_fDustLevel, g_fDustTarget);
    StepFade(g_fFogLevel, g_fFogTarget);
    StepFade(g_fSnowLevel, g_fSnowTarget);

    // The rainbow's target is recomputed every frame rather than set on a sky change,
    // because its two conditions both expire on their own: the server's countdown runs
    // out, and the sun goes down. Neither sends a packet when it happens.
    //
    // The DAYLIGHT gate is the client's because the client owns the clock. It is the
    // night level rather than a clock reading so the rainbow dims as dusk comes in
    // instead of being cut off at a threshold.
    RefreshRainbowTarget();
    StepFade(g_fRainbowLevel, g_fRainbowTarget);

    // Re-assert every frame: the engine's scroll / tile animator overwrites colour
    // otherwise. Clouds take the full night tint, rain a fraction of it (a pitch
    // black sheet reads as a hole in the sky).
    // The moon and stars ride the CLOCK, not the weather, and take no night tint of
    // their own: they are what the night looks like, so darkening them is backwards.
    ApplyBackFade(g_vSky,    Weather_SkyBackdropColor());
    ApplyBackFade(g_vNight,  Weather_NightSkyColor());
    // The moon's layer stays at its authored coordinates for the whole night. Moving
    // it along a rise/set arc looked like the entire sky was sliding across the map.
    // The dust sky takes the full night tint like any other scenery, so a sandstorm that
    // runs into dusk goes dark rather than staying daytime orange against a black map.
    ApplyBackFade(g_vDust,   Weather_SceneryColor(g_fDustLevel));
    // CAPPED WELL SHORT OF OPAQUE. A blizzard should cost visibility, not playability:
    // at full level the map is still readable and the player and the platforms are still
    // legible through it. Two sheets multiply, so the pair reaches about 0.55 together.
    ApplyBackFade(g_vFog,    Weather_SceneryColor(g_fFogLevel * FOG_ALPHA_MAX));
    ApplyBackFade(g_vRainbow, Weather_SceneryColor(g_fRainbowLevel));
    ApplyBackFade(g_vClouds, Weather_SceneryColor(g_fCloudLevel));
    ApplyBackFade(g_vRain,   Weather_RainColor(g_fRainLevel));
    // The SCENERY tint, not the rain tint. Rain sheets take a fraction of the night
    // multiply because a black streak reads as a hole in the sky; snow is discrete white
    // flecks with a lot of transparent between them, so the full tint just makes them the
    // colour of the night they are falling through, which is right.
    ApplyBackFade(g_vSnow,   Weather_SceneryColor(g_fSnowLevel));
    // Falling snow is engine-managed; no per-frame work.

    // Audio follows the RAIN FADE rather than the profile, so the sound rises and
    // falls with the visual instead of snapping on the moment the sky changes.
    WeatherSound_Tick(g_fRainLevel);
    // Splashes follow the same fade, so they thin out as the rain does instead of
    // stopping dead when the profile changes. Only the LEVEL is published here: the
    // spawning and the anchor correction run per rendered frame, not on this tick.
    WeatherSplash_SetIntensity(g_fRainLevel);
}
