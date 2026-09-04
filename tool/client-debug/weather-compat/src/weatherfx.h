#pragma once
#include "ztl/ztl.h"

class CMapLoadable;

// Clouds, rain and snow. Driven entirely by weather.cpp, which owns the shared
// CMapLoadable hooks and the world state; this module has no hooks and no input
// of its own (the original's F7/F8 polling is gone: the sky is the server's).
//
//   SKY_RAIN  -> clouds + scrolling rain sheets  (injected back layers)
//   SKY_SNOW  -> clouds + the engine's own snow  (CField::BlowWeather)
//   SKY_CLEAR -> both faded out
//
// Rain is injected back entries rather than engine particles because v83 ships
// NO rain art: nothing in Map/MapHelper.img/weather is rainfall. See
// IMPLEMENTATION.md.
namespace WeatherFx {
    void Inject(CMapLoadable* pField);   // add sky / moon / cloud / rain entries to the back list
    unsigned int InjectedLastIndex();    // last back index we own, for the z promotion
    void SetSky(unsigned char uSky, bool bSnap = false); // Weather::SKY_* from the server
    bool IsSkyIndex(int nIndex);         // back index owned by the tiled night sky
    bool IsNightIndex(int nIndex);       // back index owned by the moon / starfields
    bool IsDustIndex(int nIndex);        // back index owned by the sandstorm backdrop
    bool IsRainbowIndex(int nIndex);     // back index owned by the after-the-rain rainbow
    bool IsCloudIndex(int nIndex);       // back index owned by the cloud layers
    bool IsRainIndex(int nIndex);        // back index owned by the rain layers
    bool IsFogIndex(int nIndex);         // back index owned by the blizzard fog layers
    bool IsSnowIndex(int nIndex);        // back index owned by the two snow planes
    // Which SHEET a back index belongs to, or -1. One entry becomes many tile layers, so
    // the drift has to move a whole sheet at once; see g_aCloudSheet in weatherfx.cpp.
    int  CloudSlot(int nIndex);
    int  FogSlot(int nIndex);
    void CaptureSky(const IWzGr2DLayerPtr& pLayer);    // routed from the CreateLayer hook
    void CaptureNight(const IWzGr2DLayerPtr& pLayer);
    void CaptureDust(const IWzGr2DLayerPtr& pLayer);
    void CaptureRainbow(const IWzGr2DLayerPtr& pLayer);
    void CaptureCloud(const IWzGr2DLayerPtr& pLayer, int nSlot);
    void CaptureRain(const IWzGr2DLayerPtr& pLayer);
    void CaptureFog(const IWzGr2DLayerPtr& pLayer, int nSlot);
    // No slot: nothing translates the snow planes, so they need no per-sheet grouping.
    void CaptureSnow(const IWzGr2DLayerPtr& pLayer);

    void OnEnterField(bool bSkyField);   // after a field finishes loading
    void OnLeaveField();                 // map unload: drop refs, stop engine snow
    void ClearBackLayers();              // back rebuild (resolution / zoom)
    void Reapply();                      // re-apply the current fade
    // Advance the deterministic storm-flash timeline before weather.cpp colours the
    // scene. LP_WeatherSync supplies a shared age and seed for every region.
    void TickLightning();
    float LightningLevel();              // 0..1 illumination pulse, current frame
    void Update();                       // per frame: step fades, hold alpha
}

// Capture flags set by weather.cpp's MakeBack hook so its CreateLayer hook can
// route the rebuilt cloud / rain layers back into this module.
extern bool g_bCaptureFxSky;
extern bool g_bCaptureFxNight;
extern bool g_bCaptureFxDust;
extern bool g_bCaptureFxRainbow;
extern bool g_bCaptureFxCloud;
extern bool g_bCaptureFxRain;
extern bool g_bCaptureFxFog;
extern bool g_bCaptureFxSnow;

// Colour helpers owned by weather.cpp: the night tint and the weather fade share
// one dword, so this module cannot compute its own colours.
unsigned int Weather_SceneryColor(float fAlpha);
// The moon and starfields: alpha follows the CLOCK and they take no night tint, because
// they are what the night looks like.
unsigned int Weather_NightSkyColor();
// The tiled backdrop. Alpha follows the clock like the moon does, but it SNAPS rather
// than fades at tall resolutions: see the comment on the function.
unsigned int Weather_SkyBackdropColor();
unsigned int Weather_RainColor(float fAlpha);

// The local player's world position, or false when there is no player: outside a field,
// and on the one client where the accessor does not resolve. Owned by weather.cpp
// because two ground modules need it. See the comment on the definition for how the
// vtable slot was established.
bool Weather_ReadPlayerPos(int* px, int* py);

// The ambient rain loop (weathersound.cpp).
//
// SetWanted is called from RefreshTargets whenever the profile changes and says only
// whether the loop SHOULD be playing; it does no audio work itself, because it can be
// reached from a field load. Tick does the actual start / stop and the volume ramp, on
// the main thread. The two are split for the same reason every other module here is:
// audio and UI objects are not safe on the socket thread.
void WeatherSound_SetWanted(unsigned char uAmbience);   // Weather::Ambience, SND_NONE to stop
void WeatherSound_Tick(float fIntensity);   // 0..1, follows the rain fade
void WeatherSound_Shutdown();              // stop and release; called on field teardown
// The prevailing wind (weatherwind.cpp), roughly -300..+300, 0 when nothing is blowing.
//
// Rolled once per particle build rather than eased on a clock, because a particle's
// trajectory is VM_FOREVER and cannot be revised after it is launched. weather.cpp reads
// it to sway the map's own scenery, so the wind moves the whole map and not only the
// things falling through it.
int WeatherWind_Prevailing();

// HOW THE GROUND EFFECT MODULES ANCHOR THEIR LAYERS
//
// weathersplash, weatheraccum and weatherpuddle all place sprites at fixed world
// positions. They do it by passing CreateAnimLayer NO origin and NO overlay and then
// plain world coordinates, because such a layer lives in world space and the engine
// offsets it by the camera itself.
//
// Both other approaches were tried and both are wrong:
//   - parenting to the avatar's under-face layer inherits the avatar's transform, so
//     the double jump front flip rotates every sprite with it. Passing a null overlay
//     does not help: put_origin carries the transform too.
//   - placing at (world - camera) and correcting per frame double-compensates for a
//     scroll the engine is already doing, which pins the sprites to the screen.
// There is therefore no per frame position work in any of the three modules.


// Splashes on footholds (weathersplash.cpp).
//
// SPLIT ACROSS TWO DRIVERS, and the split is load bearing. Intensity comes from the
// 30ms logic tick so splashes follow the same rain fade as the sheets and the sound,
// but spawning happens every RENDERED frame. At 30ms the spawn rate visibly beats
// against the frame rate and splashes appear in bursts rather than a steady patter.
void WeatherSplash_SetIntensity(float fIntensity);  // 0..1, from WeatherFx::Update
void WeatherSplash_Frame();                 // per rendered frame, from CallUpdate_hook
void WeatherSplash_Shutdown();              // release every live layer; field teardown
// A burst at one spot, for weatherpuddle when the player steps in standing water. Ignores
// the rain intensity: the cause is the boot, not the sky.
void WeatherSplash_Burst(int nWorldX, int nSurfaceY, int nCount, int nSpread);

// Settled snow / leaves / petals on footholds, and footprints through them
// (weatheraccum.cpp).
//
// Unlike splashes these are LONG LIVED, so the module culls anything that falls far
// behind the player rather than carrying it for the whole session.
void WeatherAccum_Frame();
void WeatherAccum_Shutdown();               // release every deposit; field teardown
// How deep the current visual accumulation is, 0 to 1. Diagnostic only.
float WeatherAccum_Level();
// The same visual level, but 0 unless the material is snow. Diagnostic only.
float WeatherAccum_SnowLevel();

// CAST SHADOWS ARE NOT PART OF THIS BUNDLE. The three entry points of the shadow
// module were declared here and are gone with it: it was the only caller that ever asked
// weathercanvas.cpp for a raw pixel buffer, and that path is held off by a kill switch
// after its first in-game test hung the client. See the README.

// The captured map objects. Owned by weather.cpp because everything that rebuilds them is;
// lamps.cpp reads them to work out how deep a post should sit.
int  Weather_ObjCount();
// The layer comes back by REFERENCE: _com_ptr_t::operator& releases and hands out a
// raw IWzGr2DLayer**, so a pointer-to-smart-pointer parameter cannot be passed one.
bool Weather_GetObj(int i, IWzGr2DLayerPtr& pLayer, POINT* pPos);
// 0 none, 1 foliage, 2 rope or ladder.
unsigned char Weather_ObjSwayKind(int i);

// Is this object greenery, for DEPTH purposes? Not the same question as "does it sway":
// the sway classifier demotes anything that animates itself, which is right for shearing
// a sprite and wrong for deciding draw order. A sunflower head and a butterfly are still
// plants and should be allowed in front of a lamp post.
unsigned char Weather_ObjIsPlant(int i);
// Did this object's map entry carry the mirror flag `f`? A generated layer cannot carry a
// flip -- IWzGr2D::CreateLayer has no such parameter, and only the engine's own
// CreateAnimLayer path takes one -- so weathersway leaves these sprites stock rather than
// replacing them with an un-mirrored copy.
unsigned char Weather_ObjFlip(int i);

// The object's WZ path (oS/l0/l1/l2) as one FNV-1a hash, lowercased. For recognising a
// specific sprite without anyone having to store or own the WZ strings, which do not
// outlive the property call that produced them.
unsigned long long Weather_ObjPathHash(int i);

// The current field id, for per-map logging and keying.
int Weather_CurrentFieldId();

// Props that sway although they are not filed as foliage. Returns where the bend starts as
// a fraction of the sprite's height (1.0 = at the base, 0.55 = only the top 45% moves), or
// 0 when the sprite is not one of them. Owned by weathersway.cpp; weather.cpp calls it
// while classifying so such a prop is treated as foliage from the start.
float WeatherSway_ExtraFoliagePivot(unsigned long long uHash);

// Two deliberately selected Mushroom Shrine trees are much larger than the normal
// foliage safety band.  Keep the exception keyed to their WZ art path so a generic
// large tree or a building can never enter the generated-canvas path by accident.
bool WeatherSway_IsLargeTree(unsigned long long uHash);

// Leafre stores its large rooted trees under `nature1`, rather than the usual
// `tree` category.  Recognise only those two known Minar/Dragon Road families.
bool WeatherSway_IsLeafreTreeObject(const wchar_t* sOS, const wchar_t* sL0,
                                    const wchar_t* sL1);

// Leafre town's large trees are parallax background layers, not map objects.  They
// retain their engine-owned back-layer transform while their canvas frames are swapped.
bool WeatherSway_IsLeafreTreeBack(const wchar_t* sBS, int nNo);
void WeatherSway_ReplaceLeafreBack(const IWzGr2DLayerPtr& pLayer);

// Explicit map-art whitelist for objects that hang from an upper attachment
// (banners, flags, cages, ivy and hanging lamps). The caller passes the WZ
// object path while it is still live, so this can safely use family wildcards.
bool WeatherSway_IsHangingObject(const wchar_t* sOS, const wchar_t* sL0,
                                 const wchar_t* sL1, const wchar_t* sL2);

// Is a sprite whose bottom row is at (x, y) standing on a platform, and far enough in
// from its ends to bend? Called with the sprite's BASE, which only the sway planner
// knows: the obj entry's y is the canvas origin and is often somewhere else entirely.
bool Weather_RootedWellInside(long x, long y, long nSpriteH);

// The z band the map's own art occupies: highest tile z, lowest object z. A ground effect
// that must lie ON the ground but UNDER everything standing on it, the player included,
// belongs between them. False when the field has no captured art to measure.
bool Weather_ZBands(int* pTileMax, int* pObjMin);

// The ground plane derived from that band, and the plane one step in front of it, shared
// by every module that draws on the floor. Both outputs are optional.
//
// pnGround is over the map's TILES. It is NOT under every object: on almost every map the
// tile stack reaches into the object layers, so no such z exists and this picks
// over-the-tiles. Ground effects can therefore draw in front of low map objects.
//
// THE VALUES ARE LARGE AND NEGATIVE. That is the engine's layer-z space, not an error:
// see the definition in weather.cpp for the three formulas. Never floor a z at 0, and
// never substitute a small literal when this returns false -- a literal is roughly 1.07
// billion units in FRONT of the whole map, so the layer draws over the player. Returns
// false until the field's art has been captured; skip drawing until it is true.
bool Weather_GroundZ(int* pnGround, int* pnAbove);

// Foliage that BENDS: base planted, everything above it leaning (weathersway.cpp). Needs
// generated canvases, so it does nothing on a client where that is unavailable, and
// weather.cpp's translate sway stands in.
void WeatherSway_Frame();
void WeatherSway_Shutdown();
bool WeatherSway_Active();

// Puddles, the rain half of accumulation (weatherpuddle.cpp). Same drivers and lifetime
// rules as WeatherAccum, but a slot holds ONE puddle that grows through size tiers.
void WeatherPuddle_Frame();
void WeatherPuddle_Shutdown();
// A world x with standing water on it, for weathersplash to aim some drops at. False
// when nothing is wet.
bool WeatherPuddle_PickWetX(int* px);
