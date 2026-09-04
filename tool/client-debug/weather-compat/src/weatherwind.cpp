#include "pch.h"
#include "hook.h"
#include "weather.h"
#include "debug.h"
#include "patch_common.h"

// Wind for the falling leaves, blossoms and snow.
//
// WHICH BRANCH RUNS. The weather builder at 0x0063FE57 has a seven way switch at
// 0x006404C0 on its third argument. That argument is info/**direction**, NOT info/type:
//
//   0x00534C48  push 0xEC5                 string pool id for "direction"
//   0x00534C76  call VariantToIntOrDefault
//   0x00534C7B  mov [ebp-0x24], eax
//   0x00534F33  push [ebp-0x24]            becomes the builder's [ebp+0x10]
//
// No weather item carries a `direction` child, ours or stock, so every ambient sky lands
// in branch 0. A cave placed in any other branch installs cleanly and never executes.
//
// BRANCH 0, at 0x006406BD:
//   006406BD  rand()%800   startX = that - SCREEN_WIDTH_MAX/2
//   006406CF  rand()%600   startY = that - SCREEN_HEIGHT_MAX/2
//   006406E3  rand()%200
//   006406F3  lea eax,[edx+eax-0x64]   endX = startX + rand()%200 - 100   <- THE DRIFT
//   006406F7  mov [ebp-0x2c],eax
//   006406FA  lea eax,[ebx+0x12c]      endY = startY + SCREEN_HEIGHT_MAX/2
//
// The stock spread is only +/-100 px over a whole fall, which reads as a wobble rather
// than as wind. This cave widens it and adds a prevailing gust.
//
// WHAT IT CANNOT DO. 0x0063FE57 is a one shot BUILDER and the RelMove it feeds is
// nType = VM_FOREVER, so a particle keeps its trajectory for life. The per particle
// spread is therefore the continuous effect; the prevailing gust is rolled once per
// build, so it changes on a sky change or a map entry but does not swell while a sky
// holds. Animating it would mean re-blowing the weather, and BlowWeather calls
// WeatherLayer_RemoveAll first, so every particle would pop. Nothing here needs a per
// frame tick. The prevailing gust itself is derived from the server's per-sky token,
// so every client in the same region agrees on its direction and strength.
//
// REGISTER LIVENESS AT 0x006406F3:
//   eax  the value being computed. Overwritten at 0x006406FA, free afterwards.
//   edx  rand()%200. Only consumer is the instruction being replaced. Dead after.
//   ecx  holds 200. Dead.
//   ebx  startY, read at 0x006406FA. MUST SURVIVE.
//   esi  SCREEN_HEIGHT_MAX/2, edi SCREEN_WIDTH_MAX/2. Not written here.
//   ebp  the builder's frame. The cave reads [ebp-0x20] and writes [ebp-0x2c] through
//        it, which is safe because a naked stub sets up no frame of its own.
// The callee is __cdecl, whose volatile set is eax/ecx/edx: exactly the dead three.
//
// resolution.cpp rewrites constants at 0x006406C3+1, 0x006406D5+1 and 0x006406FA+2 in
// this same branch. This cave owns 0x006406F3..0x006406F9 and overlaps none of them, but
// it must still install AFTER AttachResolutionMod.

#define ADDR_WIND_SITE   0x006406F3     // lea eax,[edx+eax-0x64] ; mov [ebp-0x2c],eax
#define WIND_SITE_LEN    7

// Absolute pixels of horizontal travel over one fall. NOT scaled to the screen: unlike
// the start box, resolution.cpp leaves branch 0's +/-100 spread alone at every mode.
#define WIND_SPREAD      150     // per particle, replacing the stock +/-100
#define WIND_GUST_MAX    300     // prevailing, sampled per particle at build time

// The sandstorm flies almost FLAT, and this is the only lever that can make it.
//
// Branch 0 sets endY = startY + SCREEN_HEIGHT_MAX/2, so the vertical fall is fixed at
// about 300 to 400px and is a constant resolution.cpp owns. The angle of the path is
// therefore decided entirely by how far the particle travels HORIZONTALLY in the same
// time, which is exactly what this cave returns. At 1200 to 1800 against a ~350 fall the
// path is roughly 4:1, which reads as blown sideways rather than as falling.
//
// One direction per build, and the spread is far smaller than the minimum gust, so no
// grain can ever end up flying back into the wind.
#define SAND_GUST_MIN    1200
// A blizzard's own floor, for the same reason the sandstorm has one.
#define BLIZZ_GUST_MIN   150

// SNOW HAS TO SLANT. Branch 0 fixes the vertical fall at the immediate resolution.cpp
// writes to 0x006406FA+2, i.e. SCREEN_HEIGHT_MAX/2 = 720, so the path angle is
// atan(drift / 720). With a prevailing gust uniform in [-300, +300] that is a mean of
// about 12 degrees and a third of snowfalls arrive under it: straight down, as reported.
//
// These are the TANGENT of the wanted angle in percent, applied to the LIVE fall distance,
// so what is pinned is the angle rather than a pixel count that quietly changes meaning if
// SCREEN_HEIGHT_MAX ever moves.
#define SNOW_SLANT_MIN_PCT  45      // about 24 degrees
#define SNOW_SLANT_MAX_PCT  75      // about 37 degrees
#define SNOW_SPREAD         90      // per particle, well under the minimum slant
#define SAND_GUST_MAX    1800
#define SAND_SPREAD      260
namespace {

bool  g_bInstalled  = false;
int   g_nWindNow    = 0;        // prevailing wind for the current server sky token
unsigned int g_uWindToken = 0;
unsigned char g_uWindSky = Weather::SKY_CLEAR;
bool  g_bHaveWind   = false;

unsigned int g_uRand = 0x9E3779B9;

// Not rand(). The builder is mid way through its own rand() sequence here, and stealing
// a draw would shift every particle position the engine is about to compute: a change
// nobody would ever trace back to wind.
inline unsigned int NextRand() {
    g_uRand ^= g_uRand << 13;
    g_uRand ^= g_uRand >> 17;
    g_uRand ^= g_uRand << 5;
    return g_uRand;
}

inline bool SkyBlows(unsigned char uSky) {
    return uSky == Weather::SKY_LEAVES || uSky == Weather::SKY_BLOSSOM
        || uSky == Weather::SKY_SNOW || uSky == Weather::SKY_BLIZZARD
        || uSky == Weather::SKY_STORM || uSky == Weather::SKY_OVERCAST
        || uSky == Weather::SKY_SANDSTORM;
}

// The vertical fall the engine is about to use. resolution.cpp rewrites the imm32 of
// `lea eax,[ebx+imm32]` at 0x006406FA (opcode 8D 83, so the immediate is at +2). Reading
// it back is the only way to be sure of the number, and it is safe here because
// AttachWeatherWindMod runs after AttachResolutionMod.
inline int FallDistance() {
    const int n = *reinterpret_cast<const int*>(0x006406FA + 2);
    return (n > 0 && n <= 4000) ? n : 300;
}

inline unsigned int Mix(unsigned int v) {
    v ^= v >> 16;
    v *= 0x7FEB352Du;
    v ^= v >> 15;
    v *= 0x846CA68Bu;
    return v ^ (v >> 16);
}

void EnsureWindForSky() {
    const unsigned char uSky = Weather::CurrentSky();
    if (!SkyBlows(uSky)) {
        g_bHaveWind = false;
        g_nWindNow = 0;
        return;
    }

    // Include the profile in the key for older servers, which report token zero for
    // every sky. New servers supply a distinct token for each regional occurrence.
    const unsigned int uToken = Weather::SkyToken() ^ ((unsigned int)uSky * 0x9E3779B9u);
    if (g_bHaveWind && g_uWindToken == uToken && g_uWindSky == uSky) {
        return;
    }

    unsigned int u = Mix(uToken);
    if (uSky == Weather::SKY_SANDSTORM) {
        const int nDir = (u & 1u) ? 1 : -1;
        u = Mix(u + 0xA511E9B3u);
        g_nWindNow = nDir * (SAND_GUST_MIN
                + (int)(u % (unsigned int)(SAND_GUST_MAX - SAND_GUST_MIN + 1)));
    } else if (uSky == Weather::SKY_BLIZZARD) {
        // A BLIZZARD NEVER ROLLS A CALM. It is wind by definition, and the generic roll
        // below is uniform over [-MAX, +MAX], so a third of blizzards came out under a
        // third strength and the fog had almost nothing to blow it. This also keeps
        // |gust| above StepFogDrift's magnitude floor, so the floor stops being reachable
        // and the fog can never take its direction from the sign of a zero.
        const int nDir = (u & 1u) ? 1 : -1;
        u = Mix(u + 0x2545F491u);
        g_nWindNow = nDir * (BLIZZ_GUST_MIN
                + (int)(u % (unsigned int)(WIND_GUST_MAX - BLIZZ_GUST_MIN + 1)));
    } else {
        g_nWindNow = (int)(u % (unsigned int)(2 * WIND_GUST_MAX + 1)) - WIND_GUST_MAX;
    }
    g_uWindToken = uToken;
    g_uWindSky = uSky;
    g_bHaveWind = true;
}

}  // namespace


// The prevailing wind, -WIND_GUST_MAX..+WIND_GUST_MAX, or 0 when nothing is blowing.
// For weather.cpp, which sways the map's own scenery with it so the wind is something
// the whole map is in rather than something only the particles know about.
int WeatherWind_Prevailing() {
    const unsigned char uSky = Weather::CurrentSky();
    EnsureWindForSky();
    if (!SkyBlows(uSky) || !g_bHaveWind) {
        return 0;
    }
    return g_nWindNow;
}


// Called from the cave, once per particle. Returns the horizontal travel to apply.
//
// The sky is sampled here rather than cached: the builder runs ON a sky change, before a
// frame tick could have observed it, so a cached flag reads false exactly when it matters.
extern "C" __declspec(noinline) int __cdecl WeatherWind_NextDrift() {
    const unsigned char uSky = Weather::CurrentSky();
    if (!SkyBlows(uSky)) {
        // Stock behaviour for every other sky and for a player's own cash weather:
        // rand()%200 - 100, reproduced exactly.
        return (int)(NextRand() % 200u) - 100;
    }

    // The builder only chooses the per-particle spread. The prevailing part comes from
    // the server token, rather than from this client's timing of the builder calls.
    const bool bSand = (uSky == Weather::SKY_SANDSTORM);
    EnsureWindForSky();

    // The spread stays well under the sandstorm's minimum gust, so no grain can be pushed
    // back through zero and end up flying into the wind.
    // Snow gets a FLOOR AND A CEILING on the slant, and a pinned direction. The flakes
    // are drawn as a vertical streak and the engine never rotates a particle, so a wind
    // that reversed per occurrence would leave half of them leaning the wrong way against
    // their own motion.
    if (uSky == Weather::SKY_SNOW || uSky == Weather::SKY_BLIZZARD) {
        const int nFall = FallDistance();
        int nMag = (g_nWindNow < 0) ? -g_nWindNow : g_nWindNow;
        const int nMin = nFall * SNOW_SLANT_MIN_PCT / 100;
        const int nMax = nFall * SNOW_SLANT_MAX_PCT / 100;
        if (nMag < nMin) nMag = nMin;
        if (nMag > nMax) nMag = nMax;
        const int nJit = (int)(NextRand() % (unsigned int)(2 * SNOW_SPREAD + 1)) - SNOW_SPREAD;
        return nMag + nJit;      // always rightward; see above
    }

    const int nRange = bSand ? SAND_SPREAD : WIND_SPREAD;
    const int nSpread = (int)(NextRand() % (unsigned int)(2 * nRange + 1)) - nRange;
    return g_nWindNow + nSpread;
}


// Replaces, at 0x006406F3:
//     lea eax, [edx + eax - 0x64]      endX = startX + rand()%200 - 100
//     mov [ebp-0x2c], eax
// with the same store, over a drift this module chooses. eax, ecx and edx are all dead
// here and are the only registers a __cdecl callee may clobber, so nothing is preserved.
__declspec(naked) void WeatherWind_Cave() {
    __asm {
        call WeatherWind_NextDrift
        add  eax, [ebp - 0x20]      // + startX, which 0x006406CC just stored
        mov  [ebp - 0x2c], eax      // endX, the store this replaces
        ret
    }
}


void AttachWeatherWindMod() {
    // The exact two instructions this was written against. resolution.cpp does not touch
    // this window, so unlike the previous site the bytes really are fixed and asserting
    // them is right.
    static const unsigned char kExpect[WIND_SITE_LEN] = {
        0x8D, 0x44, 0x02, 0x9C,     // lea eax, [edx + eax - 0x64]
        0x89, 0x45, 0xD4,           // mov [ebp-0x2c], eax
    };
    const unsigned char* p = reinterpret_cast<const unsigned char*>(ADDR_WIND_SITE);
    for (int i = 0; i < WIND_SITE_LEN; ++i) {
        if (p[i] != kExpect[i]) {
            ErrorMessage("Weather wind: 0x%08X is not the expected drift computation "
                         "(byte %d is 0x%02X, wanted 0x%02X). Leaving leaf and blossom "
                         "drift stock.", ADDR_WIND_SITE, i, p[i], kExpect[i]);
            return;
        }
    }
    PatchCall(ADDR_WIND_SITE, &WeatherWind_Cave, WIND_SITE_LEN);
    g_bInstalled = true;
    DEBUG_MESSAGE("weather wind: cave at 0x%08X, spread +/-%d, gust +/-%d",
                  ADDR_WIND_SITE, WIND_SPREAD, WIND_GUST_MAX);
}
