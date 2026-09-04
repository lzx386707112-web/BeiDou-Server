#include "pch.h"
#include "hook.h"
#include "debug.h"
#include "wvs/field.h"
#include "wvs/packet.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include "weather.h"
#include "weatherfx.h"   // Weather_ObjCount / Weather_GetObj, for the post z
#include "lamps.h"
#include <atomic>
#include <vector>
#include <cmath>

// Street lamps and their light. See lamps.h for the shape of the feature.
//
// THE ONE IDEA: the POST and the LIGHT are different objects with different lives.
// The post is scenery -- it stands there at noon like any other prop, and at night it
// is tinted with the map. The light is a separate additive sprite that switches on.
// The donor package this grew from faded the whole lamp in and out with the clock, so
// a lamp post materialised out of empty air at dusk; that is the thing this does not do.

// ---------------------------------------------------------------- the lamp table

#define LAMP_MAX_EMITTERS 4

struct LAMPEMITTER {
    int nDX, nDY;      // offset from the sprite's placement point to this light
    int nRadius;       // measured bright-cluster radius, in sprite pixels
    // The centre of the HOUSING this light sits in, same space as nDX/nDY, and NOT the
    // same point. nDX/nDY is the centroid of the brightest cluster, which on a shaded
    // glass globe is the specular highlight: on the Henesys post the emitters come out at
    // -28 and +19 about a post that is plainly symmetric, while the housings come out at
    // -24 and +24. The halo hangs off the light, the filament off the glass. See
    // housing_centre() in obj_lamp_emitters.py.
    int nCDX, nCDY;
};

struct LAMPDEF {
    const wchar_t* sOS;
    const wchar_t* sL0;
    const wchar_t* sL1;
    const wchar_t* sL2;
    int            nBaseDY;      // height - origin.y: how far below the anchor the sprite ends
    int            nEmitters;
    int            nWarm;        // 1 = the warm glow canvas, 0 = the neutral one
    LAMPEMITTER    aEmitters[LAMP_MAX_EMITTERS];
    // 0xRRGGBB the glow is tinted, or 0 for the plain white every other lamp uses.
    // LAST in the struct on purpose: the generated rows in weather_lamptable.inc stop at
    // aEmitters, and a trailing member is value initialised to 0 for all of them, so
    // adding this cannot disturb a single existing row.
    unsigned int   uGlowRgb;
};

static const LAMPDEF kLamps[] = {
#include "weather_lamptable.inc"
    // Hand-added, AFTER the generated rows so a regeneration of the .inc cannot clobber
    // it and the ids of everything above it never move.
    //
    // Three glowing sea creatures from Aqua Road. Their origin is dead centre and they
    // are their OWN light source, so the emitter sits at the middle rather than up at a
    // lantern, and the sprite is drawn in FRONT of its glow: the light comes from inside
    // the animal, so a glow painted over it would wash the animal out.
    { L"acc5", L"aquaRoad", L"acc2", L"11", 18, 1, 0,
      { { 0, 0, 11 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } } },
    { L"acc5", L"aquaRoad", L"acc2", L"12", 18, 1, 0,
      { { 0, 0, 11 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } } },
    { L"acc5", L"aquaRoad", L"acc2", L"13", 19, 1, 0,
      { { 0, 0, 11 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } } },

    // The Aquarium's three wall lights: houseAR/house0/acc/1, 2 and 3, four placements
    // between them in map 230000000. These are the only lamps in the table that are
    // ALREADY glow art, a white core in a blue halo, so nothing here is trying to make
    // them look lit. What they were missing is a LIGHT: no glow layer meant no entry in
    // g_aLights, so the building around them stayed at full night tint and they read as
    // stickers rather than as the thing lighting the city.
    //
    // Measured off the art. Origins are dead centre on all three, so the emitters sit
    // within a pixel or two of the anchor; acc/2's bright core is 7 px low, which is the
    // only offset worth carrying. Radii are the measured bright cluster, 25 / 47 / 25,
    // which is well past GLOW_R_LARGE, so all three take the large glow at full alpha.
    //
    // Their own animation is LEFT ALONE, unlike the sea creatures. These ramp 0 to 230
    // and back over 2500 ms (2900 for acc/2), which is a smooth five second breathe
    // rather than the creatures' hard cut to invisible, and it is clearly deliberate.
    // The light this adds is steady underneath it.
    // BLUE, and deliberately small.
    //
    // Tint sampled off acc/2: white core, inner halo 0x91EEF9, deepening to 0x004EF1 at
    // the rim. The inner halo is what the light reads as. White made one fitting throw
    // two different colours of light.
    //
    // The radii here are 12, NOT the 25 / 47 / 25 the bright cores actually measure.
    // The field only picks which glow canvas to draw and how hard, and these three are
    // the one case where the fixture is ALREADY a large soft light: a full size glow
    // added over it, blended LB_ADD, drove the peak of the art's own pulse into a solid
    // white blob. 12 takes the medium canvas at 0.80 alpha, so what we add is a lift
    // rather than a second sun. The light POOL is unaffected either way: its reach is
    // LIGHT_R_OUTER, which no emitter has a say in.
    { L"houseAR", L"house0", L"acc", L"1", 70, 1, 0,
      { { 0, 0, 12 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } }, 0x0091EEF9 },
    { L"houseAR", L"house0", L"acc", L"2", 142, 1, 0,
      { { 0, 7, 12 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } }, 0x0091EEF9 },
    { L"houseAR", L"house0", L"acc", L"3", 70, 1, 0,
      { { 0, 0, 12 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 } }, 0x0091EEF9 },

    // Lamps lifted out of MapleRoot into Map/Obj/MapleMoonLamp2.img -- street posts, wall
    // lanterns, chandeliers, braziers and neon this client had no art for. Generated the
    // same way the first table is, but into a SECOND file so it lands here, below the six
    // hand-written rows: the index into kLamps is what `!lamp` sends over the wire, so a
    // row inserted above them would renumber all six without touching a line of them.
    //
    // None of these is placed by any stock map, so every one arrives through g_aManualLamps.
#include "weather_lamptable2.inc"
};
static const int kLampCount = (int)_countof(kLamps);

int Lamp_TableSize() { return kLampCount; }

// See the note on FX_MARKER in weatherfx.cpp for what the `wfx` prefix is.
#define LAMP_PREVIEW_TAG L"wfxLampPrev"

// The stock glow canvases. Building the glow in code was the donor's approach and it was
// the most fragile thing in the package: it created a canvas, took a raw pixel pointer
// through IWzRawCanvas::_LockAddress and wrote 256 KB through it. These are stock v83
// sprites that are already soft radial glows with their origin dead centre, so the whole
// raw-pixel path goes away.
//
// THEY ALL CARRY a0/a1 ALPHA ANIMATORS (market/2 ramps 20->255 over 2000 ms and back,
// common/2 255->80 over 3300 ms). The engine re-asserts that alpha every frame, so a
// colour written once loses on the next frame -- the same fight the tiled backdrop has,
// recorded in IMPLEMENTATION.md. ApplyGlows therefore writes every frame
// while lit, and that is not an optimisation opportunity.
//
// THREE SIZES, chosen by the emitter's measured radius. A candle flame and a street
// lamp's globe are not the same light, and alpha alone cannot express that: dimming a
// 112 px ball still leaves a 112 px ball, so a candle washed a whole room faintly
// instead of lighting a small patch brightly. The radii come from the same measurement
// that places the emitter, so the glow is sized to the thing that is glowing.

struct GLOWART { const wchar_t* sOS; const wchar_t* sL0; const wchar_t* sL1; const wchar_t* sL2; };

// EVERY ONE OF THESE WAS CHECKED AT TRUE PIXEL SCALE, not on a contact sheet. Judging
// them at thumbnail size picked two sprites that are RINGS -- bright rim, dark middle,
// the exact opposite of a bulb -- because at 60 px a ring and a ball look identical.
// find_glow_art.py now scores the radial alpha profile and rejects anything whose
// brightest ring is not the centre one; glow_compare.py renders the survivors life
// size. Rejected on sight, and not to be re-added:
//   acc8/jenumist/common/2, /3      rings
//   acc6/folkvillige/moon1/17       a moon: a hard disc edge, so it seams against the sky
//   guild/syarenian/common/7        a pale building shape is baked into the glow
// DRAWN, not found. Map/Obj/MapleMoonLamp.img, built by build_lamp_glows.py.
//
// Every glow in the client is a two frame animation carrying a0/a1 alpha ramps, 10 to 255
// and back on the engine's own clock, and since each lamp's copy starts at map load they
// pulse in unison. ApplyGlows writing colour every frame loses to that animator.
//
// Two attempts to keep using client art both failed. Hunting for a STATIC glow scored
// candidates on their radial alpha profile and turned up solid objects wearing a
// glow-shaped falloff: a stone pagoda roof, a gold signpost arrow and a trophy, which in
// game were opaque cones hanging over every lamp. Stopping the animation after capture is
// at the mercy of whatever the engine does on the next frame.
//
// Drawing them settles it. One frame, no animator, warm white rather than aquarium blue,
// and the brightness belongs entirely to ApplyGlows, which is where it always should have
// been.
static const GLOWART kGlowLargeWarm = { L"MapleMoonLamp", L"glow", L"large", L"0" };   // 112
static const GLOWART kGlowLargeCool = { L"MapleMoonLamp", L"glow", L"large", L"0" };   // 112
static const GLOWART kGlowMedium    = { L"MapleMoonLamp", L"glow", L"medium", L"0" };  //  60
static const GLOWART kGlowSmallWarm = { L"MapleMoonLamp", L"glow", L"small", L"0" };   //  38
static const GLOWART kGlowSmallCool = { L"MapleMoonLamp", L"glow", L"small", L"0" };   //  38

// The filament that sits INSIDE a bulb, for lamps whose tune asks for one. Flat hot middle
// rather than a radial ramp; see core() in build_lamp_glows.py for why that
// distinction is the whole point.
static const GLOWART kGlowCore = { L"MapleMoonLamp", L"glow", L"core", L"0" };

// Lamps whose glow is picked explicitly instead of by emitter radius.
static const GLOWART* ForcedGlowFor(const LAMPDEF& d) {
    (void)d;
    return nullptr;      // nothing overrides the size tiers now
}

// Lamps drawn IN FRONT of their own glow.
//
// The default is glow over post, which is right for a street lamp: the light spills out
// past the fitting. A glowing animal is the opposite, the light is coming from inside it,
// so painting the glow on top just washes the creature out.
static bool LampDrawsOverGlow(const LAMPDEF& d) {
    return d.sOS && _wcsicmp(d.sOS, L"acc5") == 0
        && d.sL1 && _wcsicmp(d.sL1, L"acc2") == 0;
}

// Above GLOW_Z, and the sink pass below leaves these alone.
#define LAMP_FRONT_Z (GLOW_Z + 10)

// Which frame of a self-animating lamp sprite to keep, or -1 to leave it animating.
//
// The three Aqua Road creatures are two frame animations whose a0/a1 ramps go to ZERO,
// not to a dim value: in stock Aqua Road they blink completely out and back, which is
// fine for background sea life and wrong for a lamp. Their glow does not blink with
// them, so an unfrozen one is a lit halo around nothing for seconds at a stretch.
//
// Frame 0 is NOT uniformly the opaque one, so StaticiseGlow (which always keeps frame 0)
// would leave two of the three permanently invisible. Measured off the art:
//
//   acc2/11  frame 0 a0/a1 255, frame 1 a0/a1 0   -> keep 0
//   acc2/12  frame 0 a0/a1 0,   frame 1 a0/a1 255 -> keep 1
//   acc2/13  frame 0 a0/a1 0,   frame 1 a0/a1 255 -> keep 1
static int LampStaticFrame(const LAMPDEF& d);

static int LampKeepFrame(const LAMPDEF& d) {
    return LampStaticFrame(d);
}

// Fixtures that animate their OWN brightness and must be stilled.
//
// The Aquarium orbs ramp 0 to 230 and back over 2500 ms. That was left alone at first
// because a smooth breathe is not the sea creatures' hard blink, and in game it turned
// out to be the same fault the street lamps had: brightness that belongs to ApplyGlows
// being driven by the art. Worse here, because our glow is additive, so every peak of
// the pulse stacked on top of an already bright sprite and blew out to white.
//
// Frame 1, whose a0 is the bright end of the ramp. With the animator stopped and one
// canvas left there is nothing to ramp between, and the per frame colour write that
// every captured object gets holds it there.
static int LampStaticFrame(const LAMPDEF& d) {
    (void)d;
    // NOTHING, deliberately, and the mechanism is kept for the next fixture that needs it.
    //
    // Both self animating fixtures are now static IN THE ART. Stopping an animator after
    // capture was never safe: this file already warned that it is "at the mercy of
    // whatever the engine does on the next frame", and in game that is exactly how it
    // behaved. Any rebuild of the layer restarts the animation, and the gap before the
    // next capture re-freezes it is a visible flicker. Fighting it every frame is the
    // same losing fight the glow arts had.
    //
    // So the animators were deleted from the data instead, in Client/Data (a filesystem
    // mount, so the .wz underneath is untouched and a backup sits beside each file):
    //
    //   houseAR.img  house0/acc/1,2,3        the Aquarium orbs, 0 to 230 ramps
    //   acc5.img     aquaRoad/acc2/11,12,13  the sea creatures, ramps to ZERO
    //
    // Each is one opaque frame now with no a0, a1 or delay, so there is no animator to
    // restart and brightness belongs entirely to ApplyGlows.
    //
    // Returning anything but -1 here would now be a BUG: the frames those numbers named
    // no longer exist, and FreezeToFrame would remove the only canvas that does.
    return -1;
}

// Colour and reach for lamps whose row lives in weather_lamptable.inc.
//
// That file is generated, so a value written into it is lost on the next regeneration.
// Hand-added rows carry uGlowRgb in the row itself; a generated row is tuned here, keyed
// by its sprite, and the two are resolved in one place (GlowTuneFor).
struct GLOWTUNE {
    const wchar_t* sOS;
    const wchar_t* sL0;
    const wchar_t* sL1;
    const wchar_t* sL2;
    unsigned int   uRgb;     // 0xRRGGBB
    float          fRange;   // multiplies LIGHT_R_OUTER
    float          fBright;  // multiplies the glow's alpha; 1.0 leaves the size tier alone
    // A second, much tighter sprite drawn ON the emitter, at this fraction of full alpha.
    // 0 for none.
    //
    // The halo alone says "there is light near here"; it does not make the GLASS look lit,
    // because the brightest thing on screen is still the air beside the bulb rather than
    // the bulb. A small dense core sitting inside the globe is what reads as a filament,
    // and additive blending means it also blows the glass slightly toward white, which is
    // exactly what a lit lamp does to its own housing.
    float          fCore;
    // ONE BROAD, SOFT HALO FOR THE WHOLE LAMP, at this fraction of full alpha. 0 for none.
    //
    // The per-emitter halos are sized from the measured bulb radius, so a lamp with small
    // globes gets small pools of light -- correct per bulb, and much tighter than the wash
    // a real street lamp throws. This is that wash: the large canvas, centred on the
    // lamp's lights rather than on any one of them, at a low alpha so it reads as air
    // rather than as a fourth bulb.
    float          fAmbient;
};
static const GLOWTUNE kGlowTune[] = {
    // The desert brazier. Orange, and short.
    //
    // Tint from the art: the brightest 12% of the flame measures 0xC69021, which taken
    // to full value is 0xFFB92A and then pulled a little toward orange rather than gold.
    // Range at 0.60, because a brazier is a fire basket, not a street light: at the full
    // 700 px it lit half a Perion screen from one small flame.
    { L"acc8", L"sahelDesert", L"piramid", L"4", 0x00FFA838, 0.60f, 1.00f, 0.00f , 0.00f },

    // The Nautilus ship's crystal. Not a lamp: it is the ship's power core, and on a map
    // whose only other light is a barrel portal it should read as lighting the whole
    // deck. Range 2.00 (1400 px) and 1.70x brightness, which is the "bright, and twice as
    // far" this was asked for.
    //
    // Tint from the art, same method as the brazier above: the brightest 12% of
    // acc9/nautilus/ship/3 measures (162,159,190), which taken to full value is 0xD9D5FF
    // -- the pale violet-white of the crystal rather than the deep purple of its housing.
    //
    // Its measured emitter radius is 19, already past GLOW_R_LARGE, so it takes the large
    // canvas without needing a forced-art row.
    { L"acc9", L"nautilus", L"ship", L"3", 0x00D9D5FF, 2.00f, 1.70f, 0.00f , 0.00f },

    // The Nautilus barrel portals. Ordinary reach on purpose: they are set dressing along
    // the dock, and at the crystal's range every one of them would wash out the ship.
    //
    // Tint sampled deeper than the brazier, at the top 40% rather than 12%: the ring's
    // core is blown out to pure white (0xFFFFFF at the top 5%), so a shallow sample throws
    // away the gold that actually makes it a portal. 0xFFE7C5 is that 40% at full value.
    { L"acc9", L"nautilusPort", L"portal", L"1", 0x00FFE7C5, 1.00f, 1.00f, 0.00f , 0.00f },
    { L"acc9", L"nautilusPort", L"portal", L"0", 0x00FFE7C5, 1.00f, 1.00f, 0.00f , 0.00f },

    // Henesys' three-globe post. 0.75 brightness, a 25% cut: it carries THREE emitters, so
    // it was putting out three glows where most lamps put out one, and the pools overlapped
    // into something closer to a floodlight than a street lamp. Reach is untouched -- the
    // light should still fall where it fell, just less of it.
    // Tint is a warm sodium white rather than the daylight white it was. The post's own
    // art is cold silver, so a neutral glow read as a fluorescent tube; pulling it toward
    // amber is what makes it look like a street lamp burning rather than a light source
    // that happens to be there. fCore lights the three globes themselves.
    { L"acc1", L"grassySoil", L"space", L"21", 0x00FFDCA8, 1.00f, 0.75f, 0.85f, 0.55f },

    // The MapleRoot street lamp, which now stands in Henesys in place of the post above.
    // It needs a tune for the same reason that one does: with no row here the glow falls
    // back to 0x00FFFFFF, and a white halo on a gold lantern reads as a fluorescent tube.
    //
    // Tint measured the way the barrel portals were rather than the way the brazier was,
    // and for the same reason: this lamp's dome is blown out to (255,254,204) at the top
    // 5%, so a shallow sample throws away the colour that makes it a lamp. 0xFFF25F is
    // the top 25% taken to full value -- the dome's own yellow.
    //
    // fBright stays at 1.00 even though Henesys' old post was cut to 0.75. That cut was
    // for THREE emitters overlapping into a floodlight; this lamp has one, so the town
    // is already getting a third of the light it was.
    //
    // fCore 0.80: the same fight the Henesys globes had. Under the night tint a bright
    // dome goes blue, and additive light can only push it toward white, never toward
    // warm -- the core is an LB_NORMAL replacement drawn on the dome itself.
    { L"MapleMoonLamp2", L"street", L"annual", L"0", 0x00FFF25F, 1.00f, 1.00f, 0.80f, 0.45f },
};

static const GLOWTUNE* GlowTuneFor(const LAMPDEF& d) {
    for (size_t i = 0; i < _countof(kGlowTune); ++i) {
        const GLOWTUNE& g = kGlowTune[i];
        if (d.sOS && _wcsicmp(d.sOS, g.sOS) == 0 && d.sL0 && _wcsicmp(d.sL0, g.sL0) == 0
         && d.sL1 && _wcsicmp(d.sL1, g.sL1) == 0 && d.sL2 && _wcsicmp(d.sL2, g.sL2) == 0) {
            return &g;
        }
    }
    return nullptr;
}

#define GLOW_R_LARGE   14
#define GLOW_R_MEDIUM   7

static const GLOWART& GlowArtFor(int nRadius, bool bWarm) {
    if (nRadius >= GLOW_R_LARGE) {
        return bWarm ? kGlowLargeWarm : kGlowLargeCool;
    }
    if (nRadius >= GLOW_R_MEDIUM) {
        return kGlowMedium;
    }
    return bWarm ? kGlowSmallWarm : kGlowSmallCool;
}

// Alpha per size class. Smaller lights are also dimmer, so the two reinforce instead of
// a small sprite at full alpha reading as a bright pinprick.
static float GlowAlphaScaleFor(int nRadius) {
    if (nRadius >= GLOW_R_LARGE)  return 1.00f;
    if (nRadius >= GLOW_R_MEDIUM) return 0.80f;
    return 0.62f;
}

// ---------------------------------------------------------------- tuning

// The z written into the injected obj ENTRY. Only a fallback: the real placement happens
// at capture time in Lamps_CaptureLayer, which puts the post BEHIND the map's own objects
// by reading what z they actually use.
//
// 12 is in front of everything, because the map's own objects top out at 11 on Henesys
// and 9 on Ellinia. That is the RIGHT fallback: a lamp that fails to be placed should be
// visible in front rather than lost behind the map. Dropping it to 1 was a mistake, and
// it is what made the posts vanish behind everything whenever the measurement below had
// nothing to work with.
#define LAMP_Z             12
#define GLOW_Z             100000   // in front, so its additive light lands on the scene

// Additive strength of a fully lit LARGE glow. Kept well under 255 on purpose: this is
// an LB_ADD layer, so two overlapping lamps sum and three clip to flat white. 95 leaves
// room for a couple of lamps to overlap and still read as light rather than as a hole.
#define GLOW_ALPHA_MAX     95

// The filament's ceiling. It is a plain opacity, because a core is NOT drawn LB_ADD.
//
// Additive cannot make a warm bulb here, and this was measured rather than argued. The
// glass under the Henesys emitter is pure white in the art, which the night tint takes to
// (92,102,158) -- blue dominant by 66. Adding warm light raises red fastest, so red only
// catches blue at the moment all three channels clip: the bulb goes cool, then white, and
// there is no alpha in between where it is warm. The sweep, at the glass centre:
//
//   fCore  0.35 -> (209,202,230)  R-B -21   cool, still looks off
//   fCore  0.55 -> (255,242,255)  R-B   0   neutral white
//   fCore  0.65 -> (255,255,255)  R-B   0   blown out, warmth gone
//
// LB_NORMAL instead, so the core REPLACES the glass colour rather than adding to it, and
// the bulb is whatever kGlowTune says it is: 0.85 lands on (255,229,180). The halo stays
// additive and draws in FRONT of the core, which is also the physical order -- the bloom
// in the air is between the viewer and the glass.
#define GLOW_CORE_ALPHA_MAX 255

// Glows within this radius of each other are treated as one cluster and dimmed.
#define GLOW_CROWD_R       120.0f

// The photocell. A lamp does not dim up with the sun going down: a photocell trips at a
// light level and the lamp warms to full in about a second. A linear ramp off the night
// curve instead starts leaking at 17:01 and creeps for two game-hours, which at the
// default 10 s per game minute is twenty real minutes of a halo brightening over a
// still-daylit town -- far more conspicuous now the post itself is always visible.
//
// The two levels are a hysteresis band, so a night level hovering on the threshold
// cannot strobe the whole town on and off.
//
// LAMP_OFF_LEVEL MUST STAY STRICTLY ABOVE 0. The caller stops running the apply loop
// once the night tint settles to nothing, so a release level of 0 would begin the
// cooldown on the very frame the loop stops and leave every glow stuck near full
// brightness in daylight. The gap to 0 is what guarantees the ramp finishes first.
#define LAMP_ON_LEVEL      0.35f
#define LAMP_OFF_LEVEL     0.28f
#define LAMP_WARMUP_MS     1200.0f
#define LAMP_COOLDOWN_MS   250.0f
// Lamps do not all trip on the same frame: a street lighting up one lamp at a time
// reads as a town waking up, all at once reads as a switch being thrown.
#define LAMP_STAGGER_MS    2600.0f

// TWILIGHT: a dim light before the photocell trips, and after it releases.
//
// The photocell is a hard on/off and that is right for the switch itself, but it left the
// lamps completely dark through the whole of dusk while the town was visibly darkening --
// the one stretch where a street lamp is most obviously wanted.
//
// This is the linear ramp the photocell comment above rejects, kept honest by a FLOOR: it
// contributes nothing until the night level clears LAMP_DIM_FROM, so lamps do not begin
// leaking light at 17:01 over a still-daylit town. Between that floor and LAMP_ON_LEVEL it
// eases up to LAMP_DIM_MAX, and the photocell then takes it the rest of the way to full.
// The result is a lamp that glows faintly as the light goes, then comes properly on.
//
// Smoothstepped rather than linear so there is no visible corner where the dim starts.
#define LAMP_DIM_FROM      0.14f
#define LAMP_DIM_MAX       0.34f

static float TwilightLevel(float fNight) {
    if (fNight <= LAMP_DIM_FROM) {
        return 0.0f;
    }
    float t = (fNight - LAMP_DIM_FROM) / (LAMP_ON_LEVEL - LAMP_DIM_FROM);
    if (t > 1.0f) t = 1.0f;
    return LAMP_DIM_MAX * (t * t * (3.0f - 2.0f * t));
}

// Local lighting: near a lit lamp, lift the night tint back toward daylight.
#define LIGHT_R_INNER      70.0f
#define LIGHT_R_OUTER      700.0f
#define LIGHT_STRENGTH     0.60f
#define MAX_LIGHTS         192

// The post stands at distance 0 from its own light, where the ground is already lifted
// to (1 - LIGHT_STRENGTH) of the night tint. Lifting the post slightly harder makes it
// the brightest thing in its own pool while keeping it part of the scene. Holding it at
// full white instead makes a lamp read as a sticker pasted over a dark town, brighter
// than the pavement its own bulb is lighting.
#define LAMP_SELF_LIFT     0.75f

// Roughly one lamp in this many is a faulty one. Which lamps is decided by a hash of
// the sequence number, not by `seq % N`: with a plain modulo the faulty lamp is always
// number 0, so the FIRST lamp on every map flickers and a map with only a few lamps
// looks like it is mostly broken.
#define FLICKER_EVERY      9

// ---------------------------------------------------------------- depth overrides
//
// LAMP_Z is measured per map (see its comment) and is right almost everywhere, but a
// permanently-visible post has one failure mode a night-only one never had: it can land
// BEHIND a building. Bounding-box overlap against the stock objects is common -- 8 of 10
// Henesys and 21 of 21 Ellinia hand-placed positions overlap something -- and most of
// those are harmless because the overlapping art is transparent where the lamp stands.
// The few that are not need an escape hatch rather than a global z change, because
// raising z for the whole map puts every other lamp in front of things it should be
// behind.
//
// Two levels, per-lamp beating per-map. Both are empty by design: add a row only when
// you have SEEN a lamp in the wrong place, and say which one in the comment.
//
// The keys are the coordinates `!lamp` PRINTED, i.e. the same numbers in g_aManualLamps,
// not the sprite position derived from them. Anything else would mean transcribing a
// second, invisible number.

// Every lamp on this map draws at this z.
static const struct { int nMap; long nZ; } g_aLampZMap[] = {
    // Empty on purpose. Henesys had a row here while the global sink was broken; the
    // per-lamp overlap rule in SinkLampsBehindArt replaced it, and a row here now would
    // SHORT-CIRCUIT that rule (LampZMapOverride makes the sink stand aside). Add one only
    // for a map the overlap rule genuinely cannot satisfy.
    { -1, 0 },   // sentinel: -1 is not a field id, and C++ has no zero-length arrays
};

// One specific hand-placed lamp draws at this z. Beats the per-map row.
static const struct { int nMap; long x; long y; long nZ; } g_aLampZAt[] = {
    // { mapId, x, y, z },
    { -1, 0, 0, 0 },   // sentinel
};

// Inject this map's lamps into a specific obj LAYER instead of the auto-chosen one.
//
// This is the bigger hammer, and it exists because z alone cannot always win: layers are
// composited in order, so an object in a higher layer draws over ANY z in a lower one. A
// town whose buildings live in layer 6 cannot be cleared by bumping a lamp's z in layer
// 1, at any value.
static const struct { int nMap; int nLayer; } g_aLampLayerMap[] = {
    // EMPTY, and Henesys is why it is empty.
    //
    // This forces which obj LAYER the injection goes into. It was added for Henesys so an
    // injected lamp POST could be ordered against the mushrooms by z, which layer 0 allows
    // and the top layer does not -- layer beats z outright.
    //
    // But Henesys has no injected posts. Its lamps are the map's own, found in place, so
    // the override's only remaining effect was on the GLOWS: it put every halo in layer 0,
    // behind the houses in layer 1 and the trees in layer 3. The whole town's lamps lit
    // nothing because their light was underneath the town.
    //
    // A halo belongs in the TOP layer: it is light in the air and should be in front of
    // what it falls on. A row here is only correct for a map that actually injects posts,
    // and then only if that map has nothing it needs the glow to sit in front of.
    { -1, -1 },   // sentinel
};


// True when this map names its own depth for EVERY lamp on it, so the automatic overlap
// sink must stand aside for the whole map.
//
// g_aLampZAt is deliberately NOT consulted here. Its rows are per-LAMP: they carry an x
// and a y precisely so one awkward post can be pinned without disturbing the others.
// Matching them on nMap alone meant a single such row switched the overlap rule off for
// every lamp on that map, which is the exact outcome the per-lamp table exists to avoid.
// The per-post case is handled by LampZFor inside the sink's own loop.
static bool LampZMapOverride(int nMapId, long* pnZ) {
    for (const auto& e : g_aLampZMap) {
        if (e.nMap == nMapId) { *pnZ = e.nZ; return true; }
    }
    return false;
}

static long LampZFor(int nMapId, long x, long y) {
    for (const auto& e : g_aLampZAt) {
        if (e.nMap == nMapId && e.x == x && e.y == y) return e.nZ;
    }
    for (const auto& e : g_aLampZMap) {
        if (e.nMap == nMapId) return e.nZ;
    }
    return LAMP_Z;
}

// -1 means "no override": pick the layer the usual way.
static int LampLayerFor(int nMapId) {
    for (const auto& e : g_aLampLayerMap) {
        if (e.nMap == nMapId) return e.nLayer;
    }
    return -1;
}

// ---------------------------------------------------------------- placement table
//
// Hand-picked positions for maps that have no lamps of their own. A map with ANY row
// here gets exactly these; a map with none relies on whatever lamps it already places.
// Collect coordinates in game with `!lamp <id>`, which previews a lamp where you stand
// and prints the exact numbers to chat.
static const struct { int nMap; long x; long y; int nLamp; } g_aManualLamps[] = {
    // { mapId, x, y, lamp index into kLamps }   <- paste rows from `!lamp` here

    // Henesys, placed by hand. Lamp 6 throughout: the town's own post.
    { 100000000,  1698,   334, 6 },
    { 100000000,  2699,   334, 6 },
    { 100000000,  3733,   454, 6 },
    { 100000000,  4870,   454, 6 },
    { 100000000,  6016,   454, 6 },
    { 100000000,  5713,  -176, 6 },
    { 100000000,   351,   274, 6 },

    // Aquarium, placed by hand. The three glowing sea creatures, 24 / 25 / 26, spread
    // over the towers so no two neighbours are the same colour.
    //
    // The y here is a CHARACTER position, not a sprite position: `!lamp` prints where
    // the player stood, and both the preview and this table put the sprite on the
    // foothold under that column (GroundYAt, then lift by the def's nBaseDY). That is
    // why the numbers look like they are in mid water, and it is also why what was
    // previewed is what gets built.
    // DISABLED, and NOT by choice of placement. These nine rows name lamps 24, 25 and
    // 26, which did not exist: the table ended at 22, so every one of them was already
    // being skipped by the range guard below and NOTHING was being placed in Aquarium.
    //
    // Adding the Nautilus crystal and the two barrel portals took the table to 25, which
    // made 24 and 25 suddenly VALID -- and they resolve to barrelPortal and
    // barrelPortal0. Left live, six of these rows would have stood a pirate barrel on a
    // coral tower. Commented out rather than renumbered because the intent was clearly
    // three glowing sea creatures (LampDrawsOverGlow already matches acc5/*/acc2/*, and
    // and only you know which sprites those
    // were meant to be. Add them to obj_lamp_emitters.py, regenerate, then point
    // these rows at the indices they land on.
    // { 230000000,  -811,  -256, 24 },
    // { 230000000,  -680,   222, 25 },
    // { 230000000,   -71,   123, 26 },
    // { 230000000,  1207,  -276, 24 },
    // { 230000000,  1004,  -599, 25 },
    // { 230000000,  1732,   -24, 26 },
    // { 230000000,   124,  -711, 26 },
    // { 230000000,  -543,  -605, 25 },
    // { 230000000,  -101,  -358, 24 },

    // Lith Harbour, placed by hand. Lamp 0 throughout: the Shanghai waterfront post,
    // which the catalogue lists as unplaced in stock data, so nothing here collides with
    // a lamp the map already has.
    { 104000000,   223,   287, 0 },
    { 104000000,  1004,   347, 0 },
    { 104000000,   569,   707, 0 },
    { 104000000,  1734,   647, 0 },
    { 104000000,  2821,   527, 0 },
    { 104000000,  2582,  -223, 0 },
    { 104000000,  1774,  -133, 0 },
    { 104000000,  3991,  -193, 0 },
    { 104000000,  4080,   437, 0 },

    // Perion, placed by hand. Lamp 12 throughout: the desert brazier.
    { 102000000,   565,  1875, 12 },
    { 102000000,  2422,  1935, 12 },
    { 102000000,  2186,  1239, 12 },
    { 102000000,  1272,   979, 12 },
    { 102000000,   594,   599, 12 },
    { 102000000,  2635,   660, 12 },
    { 102000000,  2393,     1, 12 },

    // Ellinia, placed by hand. Lamp 22 throughout: the glowing bloom, climbing the tree
    // city, so the y runs strongly negative as the placements go up.
    { 101000000,  -453,   241, 22 },
    { 101000000,   215,   -40, 22 },
    { 101000000,  1196,   219, 22 },
    { 101000000,   753,  -418, 22 },
    { 101000000,   126,  -965, 22 },
    { 101000000,  -785,  -806, 22 },
    { 101000000,  -682, -1454, 22 },
    { 101000000,  -359, -2062, 22 },
    { 101000000,  1047, -1900, 22 },
    { 101000000,   403, -2527, 22 },
    { 101000000,  -246, -3140, 22 },
    { 101000000,    36, -4189, 22 },

    // Kerning City, placed by hand. Lamp 8 throughout: the town's own street light.
    { 103000000,   895,   426, 8 },
    { 103000000,  1854,  -204, 8 },
    { 103000000,    -3,   306, 8 },
    { 103000000, -1179,   426, 8 },
    { 103000000, -1878,     6, 8 },
};

// ---------------------------------------------------------------- state

static bool g_bLampField   = false;   // this field has lamps; persists for its lifetime
static bool g_bCaptureLamp = false;   // MakeObj is building an injected lamp post
static bool g_bCaptureGlow = false;   // ...or one of its glows

// One entry per glow object injected, in injection order, so a captured layer can be
// matched to the emitter it belongs to.
struct GLOWPLAN {
    float fAlphaScale;   // from the measured emitter radius: a candle flame lights less than a globe
    int   nLampSeq;      // which physical lamp on this map, for the stagger and the flicker
    unsigned int uRgb;   // 0xRRGGBB written with the alpha every frame
    float fRange;        // multiplies LIGHT_R_OUTER for THIS light
    // This entry casts no light of its own: a filament inside a bulb, or the broad ambient
    // wash. Neither may enter g_aLights, and neither takes the crowd scale.
    bool bNoLight;
    // The broad soft halo for the whole lamp. Additive like an ordinary halo, but its own
    // alpha and excluded from the light list.
    bool bAmbient;
    // This entry is a filament inside a bulb, not a light in the air.
    //
    // It still switches and flickers with its lamp, so it stays in the same list. What it
    // must NOT do is enter g_aLights: a core sits at exactly the same point as the halo it
    // lives inside, so it would relight the scenery a second time from the same place, and
    // -- worse -- CrowdScale counts neighbours within GLOW_CROWD_R, so every Henesys halo
    // would find its own core beside it and dim itself by 1/sqrt(2) for company it brought.
    bool bCore;
};
static std::vector<GLOWPLAN>         g_vGlowPlan;
static std::vector<IWzGr2DLayerPtr>  g_vGlow;
static std::vector<IWzGr2DLayerPtr>  g_vLamp;      // injected posts only; stock posts are ordinary scenery
// Parallel to g_vLamp: each injected post's own obj-entry coordinates, so the per-lamp
// depth table can name one post without disturbing the rest of the map.
static std::vector<POINT>            g_vLampAt;
static POINT                         g_ptCaptureLampAt = {0, 0};

// A lamp that drifts where it hangs, with its light going with it.
//
// The three Aqua Road creatures are alive and underwater, so standing perfectly still is
// the one thing they should not do. Their glow has to move by the SAME delta: the light
// comes from inside the animal, and a halo that stays put while the animal slides out of
// it is worse than no motion at all.
//
// Paired by adjacency: a manual lamp's glows are injected
// immediately after the post, so any glow captured while g_bLastLampDrifts holds belongs
// to the drifter on the back of the list.
struct DRIFTER {
    IWzGr2DLayerPtr pSprite;
    IWzGr2DLayerPtr pGlow[LAMP_MAX_EMITTERS];
    int   nGlows;
    float fPhase;
    int   nX, nY;                // what has been applied, so each frame moves by a delta
};
static std::vector<DRIFTER> g_vDrift;
static bool g_bLastLampDrifts = false;

static bool g_bCaptureFront  = false;
static int  g_nCaptureKeep   = -1;    // frame to freeze the lamp sprite to, -1 = leave it
// Parallel to g_vLamp: this post is deliberately in front of its glow, so the sink pass
// must not drag it back behind the map's art.
static std::vector<bool> g_vLampFront;
static int                           g_nLampSeqCount = 0;

// The photocell, and each lamp's warm-up level (0 dark .. 1 full).
static bool               g_bTripped   = false;
static std::vector<float> g_vLampOn;
static unsigned int       g_tLastTick  = 0;
static float              g_fSinceTrip = 0.0f;   // ms since the photocell last changed state

// Where each lit lamp is, rebuilt once per frame rather than per layer.
struct LIGHTPT { float x, y, on, r; };
static LIGHTPT g_aLights[MAX_LIGHTS];
static int     g_nLights = 0;
// Per-field cache of where each captured scenery layer should be SAMPLED for lamp light:
// the sprite's centre, measured once. Indexed 0 tiles, 1 objects, 2 NPCs, matching the
// three lists Lamps_RelightScenery walks. uFor is the list size the cache was built for,
// which is the invalidation signal: those vectors only ever grow (NPCs arriving) or are
// cleared wholesale on a field change or an object rebuild.
struct RelightPts {
    std::vector<POINT> v;
    size_t             uFor = (size_t)-1;
};
static RelightPts g_aRelightPts[3];

// Broad phase for the per-layer relight pass. Most captured scenery is nowhere near a
// lamp, so rejecting it before scanning up to MAX_LIGHTS keeps large towns inexpensive.
static float   g_fLightMinX = 0.0f, g_fLightMaxX = 0.0f;
static float   g_fLightMinY = 0.0f, g_fLightMaxY = 0.0f;

template <typename T>
struct ScopedSet {
    T* p; T prev;
    ScopedSet(T* pVar, T value) : p(pVar), prev(*pVar) { *pVar = value; }
    ~ScopedSet() { *p = prev; }
};

static int CurrentFieldID() {
    using GetCurFieldID_t = int(__thiscall*)(void*);
    return reinterpret_cast<GetCurFieldID_t>(0x00A1238B)(nullptr);
}

// ---------------------------------------------------------------- table lookup

static bool StrEqI(const wchar_t* a, const wchar_t* b) {
    return a && b && _wcsicmp(a, b) == 0;
}

// Read a string child, or null. Obj entries store oS/l0/l1/l2 as strings.
static const wchar_t* GetStr(IWzPropertyPtr pProp, const wchar_t* sName, Ztl_variant_t* pHold) {
    *pHold = pProp->item[sName];
    if (V_VT(pHold) != VT_BSTR || !V_BSTR(pHold)) {
        return nullptr;
    }
    return V_BSTR(pHold);
}

// Which table row this obj entry is, or -1. Matching on all four path parts rather than
// on the sprite alone matters: banks reuse l1/l2 names freely, and citySG/CBD alone
// holds a lamp, a traffic light and a limousine.
static int LampIndexOf(IWzPropertyPtr pEntry) {
    Ztl_variant_t v0, v1, v2, v3;
    const wchar_t* sOS = GetStr(pEntry, L"oS", &v0);
    if (!sOS) return -1;
    const wchar_t* sL0 = GetStr(pEntry, L"l0", &v1);
    const wchar_t* sL1 = GetStr(pEntry, L"l1", &v2);
    const wchar_t* sL2 = GetStr(pEntry, L"l2", &v3);
    if (!sL0 || !sL1 || !sL2) return -1;
    for (int i = 0; i < kLampCount; ++i) {
        const LAMPDEF& d = kLamps[i];
        if (StrEqI(sOS, d.sOS) && StrEqI(sL0, d.sL0) &&
            StrEqI(sL1, d.sL1) && StrEqI(sL2, d.sL2)) {
            return i;
        }
    }
    return -1;
}

// Which table row this SPRITE PATH is, or -1. Same match as above, against a literal
// path rather than an obj entry.
static int LampIndexOfPath(const wchar_t* const p[4]) {
    for (int i = 0; i < kLampCount; ++i) {
        const LAMPDEF& d = kLamps[i];
        if (StrEqI(p[0], d.sOS) && StrEqI(p[1], d.sL0) &&
            StrEqI(p[2], d.sL1) && StrEqI(p[3], d.sL2)) {
            return i;
        }
    }
    return -1;
}

// ---------------------------------------------------------------- art swaps

// Replace the lamp a map SHIPS WITH by a different one from the table.
//
// This rewrites the map's own obj entry rather than hiding it and injecting a
// replacement beside it. Hiding is the worse of the two: the stock post is ordinary
// scenery that the lamp module does not own, so suppressing it means reaching into a
// layer built by the engine, and the replacement would then arrive through
// g_aManualLamps with a foothold probe deciding where it stands -- a second guess about
// a position the map already knows exactly.
//
// Keyed by sprite PATH, not by table index. An index is what `!lamp` sends over the wire
// and is stable by construction, but it is also just a number, so a row that moved would
// swap some other lamp and look entirely deliberate. A path that stops resolving logs and
// leaves the map alone.
//
// Safe to run twice. The rewrite makes the entry stop matching `sFrom`, and WZ properties
// are cached for the session, so a re-entry sees a swapped entry and skips it -- which is
// what keeps the y correction below from being applied a second time.
struct LAMPSWAP {
    int            nMap;
    const wchar_t* sFrom[4];
    const wchar_t* sTo[4];
};
static const LAMPSWAP g_aLampSwaps[] = {
    // Henesys, both posts (3650,49) and (4029,49): the stock three-globe post for the
    // MapleRoot street lamp. The stock post is cold silver with three white globes, which
    // is why its glow had to be tinted amber to read as burning at all (see kGlowTune);
    // the replacement is a warm gold lantern that already looks lit.
    { 100000000, { L"acc1", L"grassySoil", L"space", L"21" },
                 { L"MapleMoonLamp2", L"street", L"annual", L"0" } },
};

// Rewrite one obj entry in place. Returns the new table row, or nDef unchanged.
//
// The y correction is the whole reason this is not a four-string edit. The engine anchors
// a sprite by its ORIGIN, and these two lamps do not put their origin in the same place:
// the stock post's sits mid-canvas (nBaseDY 77, so 77 px of sprite hangs below the anchor)
// and the replacement's sits on its feet (nBaseDY 1). Swapping the art alone would lift
// the new lamp 76 px into the air. Shifting y by the difference keeps the FEET where the
// map put them, which is the same invariant the injection path maintains with GroundYAt.
static int ApplyLampSwap(IWzPropertyPtr pEntry, int nMapId, int nDef) {
    for (size_t i = 0; i < _countof(g_aLampSwaps); ++i) {
        const LAMPSWAP& s = g_aLampSwaps[i];
        if (s.nMap != nMapId) continue;
        const int nFrom = LampIndexOfPath(s.sFrom);
        const int nTo   = LampIndexOfPath(s.sTo);
        if (nFrom < 0 || nTo < 0) {
            LOG_ONCE("lamps: swap row %u names a sprite the table does not have (%d -> %d)",
                     (unsigned)i, nFrom, nTo);
            continue;
        }
        if (nFrom != nDef) continue;

        const long y = get_int32(pEntry->item[L"y"], 0);
        const long yNew = y + (kLamps[nFrom].nBaseDY - kLamps[nTo].nBaseDY);
        // Add replaces: bNoReplace is left empty. Failures are reported rather than
        // raised, so a half-applied swap cannot take the field load down with it.
        HRESULT hr = pEntry->Add(L"oS", Ztl_variant_t(s.sTo[0]));
        if (SUCCEEDED(hr)) hr = pEntry->Add(L"l0", Ztl_variant_t(s.sTo[1]));
        if (SUCCEEDED(hr)) hr = pEntry->Add(L"l1", Ztl_variant_t(s.sTo[2]));
        if (SUCCEEDED(hr)) hr = pEntry->Add(L"l2", Ztl_variant_t(s.sTo[3]));
        if (SUCCEEDED(hr)) hr = pEntry->Add(L"y", yNew);
        if (FAILED(hr)) {
            LOG_ONCE("lamps: swap on map %d failed 0x%08X", nMapId, (unsigned)hr);
            return nDef;
        }
        LOG_ONCE_PER_ID(nMapId, "lamps: map %d swapped %ls/%ls/%ls/%ls -> %ls/%ls/%ls/%ls, y %ld -> %ld",
                        nMapId, s.sFrom[0], s.sFrom[1], s.sFrom[2], s.sFrom[3],
                        s.sTo[0], s.sTo[1], s.sTo[2], s.sTo[3], y, yNew);
        return nTo;
    }
    return nDef;
}

// ---------------------------------------------------------------- injection

static void AddObjEntry(IWzPropertyPtr pObjList, unsigned int uIndex,
                        const wchar_t* sOS, const wchar_t* sL0,
                        const wchar_t* sL1, const wchar_t* sL2,
                        long x, long y, long z, bool bGlowTag, bool bLampTag,
                        bool bPreviewTag, bool bFrontTag = false,
                        int nKeepFrame = -1) {
    IWzPropertyPtr pEntry;
    PcCreateObject<IWzPropertyPtr>(L"Property", pEntry, nullptr);
    pEntry->Add(L"oS", Ztl_variant_t(sOS));
    pEntry->Add(L"l0", Ztl_variant_t(sL0));
    pEntry->Add(L"l1", Ztl_variant_t(sL1));
    pEntry->Add(L"l2", Ztl_variant_t(sL2));
    pEntry->Add(L"x", x);
    pEntry->Add(L"y", y);
    pEntry->Add(L"z", z);
    pEntry->Add(L"f", 0L);
    // Custom keys. MakeObj ignores anything it does not know, and MakeObj_hook reads
    // these to route the layer the engine is about to build.
    if (bGlowTag) pEntry->Add(L"kaentakeGlow", 1L);
    if (bLampTag) pEntry->Add(L"kaentakeLamp", 1L);
    if (bFrontTag)  pEntry->Add(L"kaentakeFront", 1L);
    // Which frame of a self-animating sprite to keep, stored as frame+1 so that a
    // missing key and "keep frame 0" are different values. See LampKeepFrame.
    if (nKeepFrame >= 0) pEntry->Add(L"kaentakeKeep", (long)(nKeepFrame + 1));
    // Marks an entry as belonging to a `!lamp` preview rather than to the map. Previews
    // are always appended AFTER everything else, so `!lamp clear` can strip them by
    // walking back from the end while this tag holds -- which keeps the obj indices
    // contiguous, and a gap in that sequence is what makes the engine build a null.
    if (bPreviewTag) pEntry->Add(LAMP_PREVIEW_TAG, 1L);
    wchar_t sName[16];
    swprintf_s(sName, L"%u", uIndex);
    pObjList->Add(sName, Ztl_variant_t(static_cast<IUnknown*>(pEntry), true));
}

// Queue one lamp's lights. `bFlip` mirrors the emitter offsets, because a flipped
// sprite puts its lantern on the other side of the post and a glow that ignores f
// hangs in the air beside a two-headed lamp.
//
// A NULL pObjList builds the plan WITHOUT adding entries. That is the re-entry path:
// the entries are already on the cached property from a previous visit and the engine
// is about to rebuild them, but the plan that pairs each glow layer with its emitter
// lives in the DLL and was cleared on field leave. Both paths run the same loop so the
// two can never disagree about how many glows there are, which is the invariant the
// layer-to-plan pairing rests on.
// How many obj entries AddGlowsFor will add for this lamp. A filament is a second entry on
// the same emitter, so a lamp with a core adds two per light, not one. The marker records
// this count and a mismatch is how a stale cached property is detected, so counting
// emitters instead of entries quietly disarmed that check.
static unsigned int GlowEntriesFor(const LAMPDEF& d) {
    const GLOWTUNE* pTune = GlowTuneFor(d);
    const unsigned int nPer = (pTune && pTune->fCore > 0.0f) ? 2u : 1u;
    const int nEm = (d.nEmitters < LAMP_MAX_EMITTERS) ? d.nEmitters : LAMP_MAX_EMITTERS;
    const unsigned int nAmb = (pTune && pTune->fAmbient > 0.0f && d.nEmitters > 0) ? 1u : 0u;
    return (unsigned int)nEm * nPer + nAmb;
}

// nLampLayer / nInjectLayer: which obj layer the LAMP lives in, and which one this
// injection is going into. They are usually the same and the filament core is only emitted
// when they are; see the core block below. -1 on either means "not known", which is the
// injected-lamp case, where the lamp is going into the injection layer by construction.
static void AddGlowsFor(IWzPropertyPtr pObjList, unsigned int* puIndex,
                        const LAMPDEF& d, long x, long y, bool bFlip, int nSeq,
                        bool bPreview = false, long nCoreZ = GLOW_Z - 1,
                        int nLampLayer = -1, int nInjectLayer = -1) {
    for (int e = 0; e < d.nEmitters && e < LAMP_MAX_EMITTERS; ++e) {
        const LAMPEMITTER& em = d.aEmitters[e];
        if (pObjList) {
            const long gx = x + (bFlip ? -(long)em.nDX : (long)em.nDX);
            const long gy = y + (long)em.nDY;
            const GLOWART* pForced = ForcedGlowFor(d);
            const GLOWART& art = pForced ? *pForced : GlowArtFor(em.nRadius, d.nWarm != 0);
            AddObjEntry(pObjList, (*puIndex)++, art.sOS, art.sL0, art.sL1, art.sL2,
                        gx, gy, GLOW_Z, true, false, bPreview);
        }
        GLOWPLAN plan;
        const GLOWTUNE* pTune = GlowTuneFor(d);
        // The size tier sets the base, then the tune scales it. Kept as one product rather
        // than a second field on the plan: a light that reaches further and one that burns
        // brighter are the same knob to everything downstream, and ApplyGlows already
        // clamps the result.
        plan.fAlphaScale = GlowAlphaScaleFor(em.nRadius) * (pTune ? pTune->fBright : 1.0f);
        plan.nLampSeq = nSeq;
        plan.uRgb   = pTune ? pTune->uRgb : (d.uGlowRgb ? d.uGlowRgb : 0x00FFFFFFu);
        plan.fRange = pTune ? pTune->fRange : 1.0f;
        plan.bCore    = false;
        plan.bAmbient = false;
        plan.bNoLight = false;
        g_vGlowPlan.push_back(plan);

        // ...and the filament inside the glass, if this lamp asked for one. Second entry
        // for the same emitter, so both halves of the loop still push exactly as many
        // plans as they add objects and the layer-to-plan pairing survives.
        // THE CORE IS DROPPED WHEN ITS LAMP IS NOT IN THE INJECTION LAYER.
        //
        // The z reasoning below only holds within one layer: layer beats z outright, so a
        // core injected into a higher layer than its post sits in front of everything in
        // every lower layer, at any z. On Henesys the posts are in layer 0 while
        // FindObjList picks layer 3, so each post's three filaments composited over the
        // market cloth and over every building in the town -- the exact artifact the z
        // choice exists to prevent. The comment here used to claim g_aLampLayerMap
        // guaranteed the two matched for Henesys; that table is empty.
        //
        // Skipping is the honest fix rather than injecting into the lamp's own layer,
        // because g_vGlowPlan is paired with the captured layers BY ORDER: splitting the
        // entries across two obj lists reorders the MakeObj sequence and desynchronises
        // every plan after it. A lamp with no filament still lights the street; a filament
        // over the whole town does not.
        const bool bCoreLayerOk = (nLampLayer < 0) || (nInjectLayer < 0)
                               || (nLampLayer == nInjectLayer);
        if (pTune && pTune->fCore > 0.0f && !bCoreLayerOk) {
            LOG_ONCE("lamps: %ls/%ls/%ls is in obj layer %d but injection goes to layer %d; "
                     "its filament core is dropped (layer beats z, so it would draw over "
                     "the whole map). Add a g_aLampLayerMap row for this map to get it back.",
                     d.sOS, d.sL0, d.sL1, nLampLayer, nInjectLayer);
        }
        if (pTune && pTune->fCore > 0.0f && bCoreLayerOk) {
            if (pObjList) {
                const long gx = x + (bFlip ? -(long)em.nCDX : (long)em.nCDX);
                const long gy = y + (long)em.nCDY;
                // THE CORE SITS AT ITS LAMP'S OWN Z, not out in front with the halo.
                //
                // A halo is light in the air and belongs over the scene; a lit bulb is part
                // of the lamp and belongs where the lamp is. At GLOW_Z it drew over
                // everything, which on Henesys means over the market cloth: each lamp there
                // has a companion banner (acc1/grassySoil/space/22) placed at the SAME x,y
                // at exactly z+1, so a bulb in front of the map hangs in front of the cloth
                // that is meant to hang over the lamp.
                //
                // Equal z with the post still draws the core in FRONT of it, because our
                // entry is appended after the map's own and equal z falls back to list
                // order. That is what is wanted: the bulb has to be over its own glass, and
                // only over that. Anything the map placed above the lamp -- the banner at
                // z+1 -- is still above the bulb.
                //
                // This works only because this core's lamp is in the SAME LAYER we are
                // injecting into, which is what bCoreLayerOk above has just established.
                // Layer beats z outright, so a core in a higher layer would sit in front of
                // the cloth at any z at all.
                AddObjEntry(pObjList, (*puIndex)++, kGlowCore.sOS, kGlowCore.sL0,
                            kGlowCore.sL1, kGlowCore.sL2, gx, gy, nCoreZ,
                            true, false, bPreview);
            }
            GLOWPLAN cp = plan;
            // NOT scaled by the emitter size the way the halo is. The halo gets dimmer as
            // the lamp gets smaller because a small light spills less; the glass of a small
            // bulb is exactly as bright as the glass of a big one.
            cp.fAlphaScale = pTune->fCore;
            cp.bCore = true;
            cp.bNoLight = true;
            g_vGlowPlan.push_back(cp);
        }
    }

    // ...and one broad wash for the lamp as a whole.
    //
    // Centred on the MEAN of the emitters rather than on the sprite's anchor: a lamp is
    // placed by its foot, so anchoring here would sink the ambient glow into the pavement
    // on every post. The mean of the lights is where the light actually comes from.
    const GLOWTUNE* pAmb = GlowTuneFor(d);
    if (pAmb && pAmb->fAmbient > 0.0f && d.nEmitters > 0) {
        long ax = 0, ay = 0;
        int nUsed = 0;
        for (int e = 0; e < d.nEmitters && e < LAMP_MAX_EMITTERS; ++e) {
            ax += (bFlip ? -(long)d.aEmitters[e].nDX : (long)d.aEmitters[e].nDX);
            ay += (long)d.aEmitters[e].nDY;
            ++nUsed;
        }
        ax /= nUsed; ay /= nUsed;
        if (pObjList) {
            AddObjEntry(pObjList, (*puIndex)++, kGlowLargeWarm.sOS, kGlowLargeWarm.sL0,
                        kGlowLargeWarm.sL1, kGlowLargeWarm.sL2,
                        x + ax, y + ay, GLOW_Z, true, false, bPreview);
        }
        GLOWPLAN ap;
        ap.fAlphaScale = pAmb->fAmbient;
        ap.nLampSeq = nSeq;
        ap.uRgb   = pAmb->uRgb ? pAmb->uRgb : (d.uGlowRgb ? d.uGlowRgb : 0x00FFFFFFu);
        ap.fRange = pAmb->fRange;
        ap.bCore    = false;
        ap.bAmbient = true;
        ap.bNoLight = true;      // the emitters already light the scene; this is only air
        g_vGlowPlan.push_back(ap);
    }
}

// Every child of a property, by its REAL name.
//
// WZ keys are not a dense 0..count-1 range and assuming they are is silently destructive.
// Henesys' foothold groups are numbered {4, 24, 32, 33, 46, 49, 50, 55} and its segments
// run past 300, so walking 0..count-1 found almost nothing: the sway decided three
// quarters of the map's plants were standing on thin air, and the lamps had nearly no
// ground to snap to. Enumerating is the only correct way to read one of these.
template <typename F>
static void ForEachChild(IWzPropertyPtr pProp, F fn) {
    if (!pProp) {
        return;
    }
    IEnumVARIANTPtr pEnum;
    try {
        pEnum = pProp->_NewEnum;
    } catch (const _com_error&) {
        return;
    }
    if (!pEnum) {
        return;
    }
    for (;;) {
        Ztl_variant_t v;
        ULONG got = 0;
        if (FAILED(pEnum->Next(1, &v, &got)) || got == 0) {
            break;
        }
        if (V_VT(&v) != VT_BSTR || !V_BSTR(&v)) {
            continue;
        }
        try {
            IUnknownPtr pu = pProp->item[V_BSTR(&v)].GetUnknown();
            IWzPropertyPtr pChild;
            if (pu && SUCCEEDED(pu->QueryInterface(&pChild)) && pChild) {
                fn(pChild);
            }
        } catch (const _com_error&) {
        }
    }
}

void Lamps_CollectFootholds(IWzPropertyPtr pPropField, std::vector<FHSEG>& out) {
    IWzPropertyPtr pFH;
    IUnknownPtr pu = pPropField->item[L"foothold"].GetUnknown();
    if (!pu || FAILED(pu->QueryInterface(&pFH)) || !pFH) {
        return;
    }
    ForEachChild(pFH, [&out](IWzPropertyPtr pLay) {
        ForEachChild(pLay, [&out](IWzPropertyPtr pGrp) {
            ForEachChild(pGrp, [&out](IWzPropertyPtr pSeg) {
                try {
                    FHSEG s;
                    s.x1 = get_int32(pSeg->item[L"x1"], 0);
                    s.y1 = get_int32(pSeg->item[L"y1"], 0);
                    s.x2 = get_int32(pSeg->item[L"x2"], 0);
                    s.y2 = get_int32(pSeg->item[L"y2"], 0);
                    if (s.x1 || s.y1 || s.x2 || s.y2) {
                        out.push_back(s);
                    }
                } catch (const _com_error&) {
                }
            });
        });
    });
}

// Ground height at world x, preferring the floor nearest yHint so a lamp stays on the
// street rather than snapping to a rooftop that happens to span the same column.
static bool GroundYAt(const std::vector<FHSEG>& segs, long x, long yHint, long* pOutY) {
    bool bFound = false;
    long lBest = yHint, lBestDist = 0x7FFFFFFF;
    for (size_t i = 0; i < segs.size(); ++i) {
        const FHSEG& s = segs[i];
        if (s.x1 == s.x2) continue;                      // a wall has no ground
        const long lLo = (s.x1 < s.x2) ? s.x1 : s.x2;
        const long lHi = (s.x1 < s.x2) ? s.x2 : s.x1;
        if (x < lLo || x > lHi) continue;
        const long y = s.y1 + (long)((double)(s.y2 - s.y1) *
                       (double)(x - s.x1) / (double)(s.x2 - s.x1));
        const long d = (y > yHint) ? (y - yHint) : (yHint - y);
        if (d < lBestDist) { lBestDist = d; lBest = y; bFound = true; }
    }
    if (bFound) *pOutY = lBest;
    return bFound;
}

// The obj list to inject into: the highest layer that already has one, so our entries
// sit with the map's own props rather than in a layer the map never uses.
//
// nForceLayer (from g_aLampLayerMap) overrides that. It is honoured ONLY if that layer
// actually has an obj list: creating one would put our entries in a layer the engine may
// not composite the way the override intended, and silently landing in the wrong place is
// worse than the problem the override was added to fix. A miss falls back to the scan and
// says so once.
// Defined with the !lamp preview code far below; declared here because Lamps_Inject has to
// be able to strip orphaned previews off a map it is about to decline.
static int ClearPreviews(IWzPropertyPtr pObj);

static IWzPropertyPtr FindObjList(IWzPropertyPtr pPropField, int* pnLayer,
                                  int nForceLayer = -1) {
    if (nForceLayer >= 0 && nForceLayer <= 8) {
        wchar_t sLayer[8];
        swprintf_s(sLayer, L"%d", nForceLayer);
        IUnknownPtr pUnkLayer = pPropField->item[sLayer].GetUnknown();
        IWzPropertyPtr pLayer;
        if (pUnkLayer && SUCCEEDED(pUnkLayer->QueryInterface(&pLayer)) && pLayer) {
            IUnknownPtr pUnkObj = pLayer->item[L"obj"].GetUnknown();
            IWzPropertyPtr pObj;
            if (pUnkObj && SUCCEEDED(pUnkObj->QueryInterface(&pObj)) && pObj) {
                *pnLayer = nForceLayer;
                return pObj;
            }
        }
        LOG_ONCE("lamps: layer override wants layer %d but it has no obj list; "
                 "falling back to the highest layer that does", nForceLayer);
    }
    // THE HIGHEST LAYER THAT HAS OBJECTS IN IT, not merely the highest that has an obj
    // NODE. Those are different, and the difference is silent: Henesys carries an EMPTY
    // obj list on layer 7 while everything it draws is in layers 0..3, and the engine
    // builds nothing from an empty one. Injecting there added 61 entries that produced
    // zero layers -- lamps with no light at all, and nothing to show what went wrong
    // short of counting captured layers against planned ones.
    for (int nL = 7; nL >= 0; --nL) {
        wchar_t sLayer[8];
        swprintf_s(sLayer, L"%d", nL);
        IUnknownPtr pUnkLayer = pPropField->item[sLayer].GetUnknown();
        if (!pUnkLayer) continue;
        IWzPropertyPtr pLayer;
        if (FAILED(pUnkLayer->QueryInterface(&pLayer)) || !pLayer) continue;
        IUnknownPtr pUnkObj = pLayer->item[L"obj"].GetUnknown();
        IWzPropertyPtr pObj;
        if (pUnkObj && SUCCEEDED(pUnkObj->QueryInterface(&pObj)) && pObj) {
            unsigned int uCount = 0;
            try { uCount = pObj->count; } catch (const _com_error&) {}
            if (uCount == 0) {
                continue;      // a list the map never draws from
            }
            *pnLayer = nL;
            return pObj;
        }
    }
    *pnLayer = -1;
    return nullptr;
}

// See the note on FX_MARKER in weatherfx.cpp for what the `wfx` prefix is.
#define LAMP_MARKER L"wfxLampInj"

void Lamps_Inject(CMapLoadable* pField, bool bSky) {
    g_vGlowPlan.clear();
    g_nLampSeqCount = 0;
    g_bLampField = false;
    // Lamps exist only where night happens. On a field with no sky the weather module
    // never applies a tint and its Update returns before any of this runs, so a lamp
    // there would be a post whose light could never come on.
    if (!pField || !bSky) {
        return;
    }
    IWzPropertyPtr pPropField = pField->m_pPropField;
    if (!pPropField) {
        return;
    }

    try {
        // Read up front: the layer override needs it before the obj list is chosen, and
        // it stays inside the try so this function keeps its own no-throw guarantee
        // rather than leaning on the caller's catch.
        const int nMapId = CurrentFieldID();
        int nLayer = -1;
        IWzPropertyPtr pObj = FindObjList(pPropField, &nLayer, LampLayerFor(nMapId));
        if (!pObj) {
            return;   // a map with no obj list anywhere has nothing to light and nowhere to inject
        }

        // THE MARKER MUST LIVE ON THE SAME OBJECT AS THE OBJ LIST. m_pPropFieldInfo
        // (+0x2C) and m_pPropField (+0x30) are not two views of one map: when a map
        // carries info/link the client keeps the LINKING map's info at +0x2C and swaps
        // only the BODY at +0x30. 2266 maps are linked and 99 link to 100020100 alone,
        // so a marker on the private info node reads "not injected" for every one of
        // them while the entries pile up on the one shared cached list. weatherfx.cpp
        // learned this the hard way; the same rule applies here.
        IWzPropertyPtr pMarker;
        IUnknownPtr pUnkInfo = pPropField->item[L"info"].GetUnknown();
        if (pUnkInfo) {
            pUnkInfo->QueryInterface(&pMarker);
        }
        if (!pMarker) {
            pMarker = pPropField;
        }

        // Pass 1: the lamps this map already has. Counted before anything is added so
        // the walk cannot see its own injected entries.
        const unsigned int uOwnCount = pObj->count;
        // srcY is the y as WRITTEN in g_aManualLamps -- the character position `!lamp`
        // printed -- while y is the sprite anchor derived from it. The depth overrides key
        // on srcY so a row can be pasted from chat without transcribing a second number
        // that is never displayed anywhere.
        // nZ is the map's own z for this lamp entry, kept so a bulb can be drawn at the
        // same depth as the post it belongs to. See AddGlowsFor.
        // nLayer: which obj layer this lamp was actually discovered in. The scan walks
        // every layer while injection goes into one, so the two can differ, and the
        // filament core is only valid when they match. See AddGlowsFor.
        struct FOUND { int nDef; long x, y, srcY; bool bFlip; long nZ; int nLayer; };
        std::vector<FOUND> found;
        // EVERY layer, not just the one being injected into.
        //
        // FindObjList returns the highest layer that has an obj list, and the scan used
        // to walk only that one. A map puts its props wherever it likes: Aquarium keeps
        // its three wall lights in layer 1 while layer 6 holds the gates and the front
        // rocks, so the lights were invisible to a scan that only ever looked at layer 6.
        // Every stock lamp found so far happened to live in the top layer, which is why
        // this held up until a map came along where it did not.
        //
        // Injection still goes into pObj alone. Only the FIND has to be exhaustive: a
        // glow is a free standing object and does not care which layer its lamp is in.
        // Up to 8, not 7. Ten maps carry an obj list in a layer 8, which FindObjList's
        // 7..0 walk cannot reach either. Layers that do not exist cost one failed lookup.
        for (int nScanLayer = 8; nScanLayer >= 0; --nScanLayer) {
        wchar_t sScan[8];
        swprintf_s(sScan, L"%d", nScanLayer);
        IUnknownPtr pUnkScanL = pPropField->item[sScan].GetUnknown();
        IWzPropertyPtr pScanLayer;
        if (!pUnkScanL || FAILED(pUnkScanL->QueryInterface(&pScanLayer)) || !pScanLayer) {
            continue;
        }
        IUnknownPtr pUnkScanObj = pScanLayer->item[L"obj"].GetUnknown();
        IWzPropertyPtr pScanObj;
        if (!pUnkScanObj || FAILED(pUnkScanObj->QueryInterface(&pScanObj)) || !pScanObj) {
            continue;
        }
        // The injection target is counted as it was BEFORE we added anything, so the
        // walk cannot see its own entries. Every other layer is never injected into, so
        // its live count is already its own count.
        const unsigned int uScanCount =
                (pScanObj == pObj) ? uOwnCount : (unsigned int)pScanObj->count;
        for (unsigned int i = 0; i < uScanCount; ++i) {
            wchar_t sIdx[16];
            swprintf_s(sIdx, L"%u", i);
            IUnknownPtr pUnkE = pScanObj->item[sIdx].GetUnknown();
            IWzPropertyPtr pEntry;
            if (!pUnkE || FAILED(pUnkE->QueryInterface(&pEntry)) || !pEntry) continue;
            // Skip anything WE put here on a previous visit. WZ properties are cached
            // for the session, so on re-entry this list still holds the entries from
            // last time -- and an injected lamp post is by definition a sprite in the
            // lamp table, so without this it is rediscovered as if the map had shipped
            // with it, and the entry count no longer matches the marker. The glow
            // sprites are not lamps and would not match anyway; the posts are the ones
            // that bite.
            if (get_int32(pEntry->item[L"kaentakeLamp"], 0) != 0 ||
                get_int32(pEntry->item[L"kaentakeGlow"], 0) != 0) {
                continue;
            }
            int nDef = LampIndexOf(pEntry);
            if (nDef < 0) continue;
            // Swap the art BEFORE reading x/y back: ApplyLampSwap corrects y for the
            // replacement's origin, and the glow has to hang off the lamp that is
            // actually going to be built, not the one the map shipped with.
            nDef = ApplyLampSwap(pEntry, nMapId, nDef);
            FOUND f;
            f.nDef  = nDef;
            f.x     = get_int32(pEntry->item[L"x"], 0);
            f.y     = get_int32(pEntry->item[L"y"], 0);
            f.bFlip = get_int32(pEntry->item[L"f"], 0) != 0;
            f.nZ    = get_int32(pEntry->item[L"z"], LAMP_Z);
            f.nLayer = nScanLayer;
            found.push_back(f);
        }
        }
        // Per map, not once overall: "how many lamps did this map turn out to have" is a
        // different answer everywhere, and a single LOG_ONCE would only ever report the
        // first field of the session.
        LOG_ONCE_PER_ID(nMapId, "lamps: map %d, all obj layers scanned, %u stock lamp(s)",
                        nMapId, (unsigned)found.size());

        // Pass 2: hand-placed lamps, for maps that have none of their own.
        std::vector<FOUND> manual;
        std::vector<FHSEG> segs;
        bool bHaveSegs = false;
        for (size_t i = 0; i < _countof(g_aManualLamps); ++i) {
            if (g_aManualLamps[i].nMap != nMapId) continue;
            const int nDef = g_aManualLamps[i].nLamp;
            if (nDef < 0 || nDef >= kLampCount) {
                LOG_ONCE("lamps: manual row %u names lamp %d, table has %d",
                         (unsigned)i, nDef, kLampCount);
                continue;
            }
            if (!bHaveSegs) {
                Lamps_CollectFootholds(pPropField, segs);
                bHaveSegs = true;
            }
            FOUND f;
            f.nDef  = nDef;
            f.x     = g_aManualLamps[i].x;
            f.srcY  = g_aManualLamps[i].y;
            f.bFlip = false;
            f.nZ    = LAMP_Z;   // the real z is computed at injection; never read from here
            long gy = g_aManualLamps[i].y;
            GroundYAt(segs, f.x, g_aManualLamps[i].y, &gy);
            // The engine anchors the sprite by its ORIGIN, so dropping the feet onto the
            // foothold means lifting the anchor by the stored base offset. That value is
            // taken from the table, never recomputed: several lamp origins sit outside
            // their own canvas (Themetown/Streetlight/1's origin x is 183 on a 154-wide
            // sprite) and one sits below its base, so height - origin.y is not always
            // the small positive number it looks like.
            f.y = gy - kLamps[nDef].nBaseDY;
            manual.push_back(f);
        }

        if (found.empty() && manual.empty()) {
            // STRIP ANY ORPHANED PREVIEW FIRST.
            //
            // A `!lamp` preview on a map with nothing of its own leaves g_bLampField false
            // on the way out of here. The entries survive on the field's CACHED obj list,
            // and MakeObj_hook only reads our tags while g_bLampField is true, so on the
            // next entry the preview post and its glows are never claimed by
            // Lamps_CaptureLayer -- weather.cpp captures them as ordinary map objects
            // instead. The glows rebuild at obj entry z GLOW_Z as plain LB_NORMAL objects:
            // a 112x112 opaque-centred radial blob painted in front of the whole map,
            // permanently, with nothing able to switch it off because Lamps_Update never
            // runs for this field. Recovery was `!lamp clear` before leaving, or a restart,
            // and nothing told the user that.
            //
            // Removing them is the right answer rather than claiming them: with no lamps
            // there are no glow PLANS either, so a captured preview glow would have no plan
            // to pair with and would desynchronise every plan index after it.
            const int nStripped = ClearPreviews(pObj);
            if (nStripped > 0) {
                LOG_ONCE("lamps: map %d has nothing to light; removed %d orphaned !lamp "
                         "preview entr%s", nMapId, nStripped, nStripped == 1 ? "y" : "ies");
            }
            return;   // nothing to light here
        }

        // How many entries this build would add, which is also what the marker stores.
        unsigned int uWanted = 0;
        for (size_t i = 0; i < found.size(); ++i)  uWanted += GlowEntriesFor(kLamps[found[i].nDef]);
        for (size_t i = 0; i < manual.size(); ++i) uWanted += 1 + GlowEntriesFor(kLamps[manual[i].nDef]);

        // Already injected into this cached property. The marker stores the COUNT, not a
        // flag: WZ properties live for the session, so if a different build injected a
        // different number of entries into this same property the recovered layout would
        // be wrong. A mismatch is not fixable in place, so the map is left stock and
        // heals itself on the next client start.
        const int nMarked = get_int32(pMarker->item[LAMP_MARKER], 0);
        if (nMarked != 0) {
            if (nMarked != (int)uWanted) {
                LOG_ONCE("lamps: field carries %d injected entries, this build wants %u; "
                         "leaving the map stock until restart", nMarked, uWanted);
                return;
            }
            // Rebuild the plan without adding anything: the entries are already on the
            // list and the engine is about to build them again.
            g_bLampField = true;
            unsigned int uDummy = 0;
            IWzPropertyPtr pNone;                       // null: plan only, add nothing
            for (size_t i = 0; i < found.size(); ++i) {
                AddGlowsFor(pNone, &uDummy, kLamps[found[i].nDef], 0, 0, false,
                            g_nLampSeqCount++, false, GLOW_Z - 1,
                            found[i].nLayer, nLayer);
            }
            for (size_t i = 0; i < manual.size(); ++i) {
                AddGlowsFor(pNone, &uDummy, kLamps[manual[i].nDef], 0, 0, false, g_nLampSeqCount++);
            }
            return;
        }

        unsigned int uIdx = pObj->count;
        const unsigned int uFirst = uIdx;
        for (size_t i = 0; i < found.size(); ++i) {
            AddGlowsFor(pObj, &uIdx, kLamps[found[i].nDef],
                        found[i].x, found[i].y, found[i].bFlip, g_nLampSeqCount++,
                        false, found[i].nZ, found[i].nLayer, nLayer);
        }
        for (size_t i = 0; i < manual.size(); ++i) {
            const LAMPDEF& d = kLamps[manual[i].nDef];
            const bool bFront = LampDrawsOverGlow(d);
            // A front lamp is already above GLOW_Z and cannot be hidden by map art, so the
            // override only applies to the ordinary case -- which is the only one that can
            // end up behind a building.
            const long lZ = bFront ? LAMP_FRONT_Z
                                   : LampZFor(nMapId, manual[i].x, manual[i].srcY);
            AddObjEntry(pObj, uIdx++, d.sOS, d.sL0, d.sL1, d.sL2,
                        manual[i].x, manual[i].y, lZ,
                        false, true, false, bFront, LampKeepFrame(d));
            // Same depth as the post that was just injected, for the same reason a stock
            // lamp's bulb takes its map z: the bulb is part of the lamp, not light in the
            // air. lZ is what the post itself went in at, so the two can never disagree.
            AddGlowsFor(pObj, &uIdx, d, manual[i].x, manual[i].y, false, g_nLampSeqCount++,
                        false, lZ);
        }
        pMarker->Add(LAMP_MARKER, (long)uWanted);
        LOG_ONCE_PER_ID(nMapId * 4 + 1,
            "lamps: map %d INJECTED into layer %d, %u entries (marker %u), plans now %u",
            nMapId, nLayer, uIdx - uFirst, uWanted, (unsigned)g_vGlowPlan.size());
        g_bLampField = true;
        DEBUG_MESSAGE("lamps: map %d, %u stock lamp(s) + %u injected, %u glow(s)",
                      nMapId, (unsigned)found.size(), (unsigned)manual.size(),
                      (unsigned)g_vGlowPlan.size());
    } catch (const _com_error& e) {
        (void)e;
        DEBUG_MESSAGE("lamps: inject failed 0x%08X", e.Error());
        g_bLampField = false;
        g_vGlowPlan.clear();
    }
}

// AddGlowsFor with a null list is the plan-only path used on re-entry.
// (Kept as one function so the plan and the entries can never disagree about count.)

// ---------------------------------------------------------------- capture

// Declared here rather than in a header: one function, one caller, and weatherfx.h is
// shared by five modules that have no business knowing about obj properties.
extern void Weather_NoteObjProp(IWzProperty* pObjProp);

void* CMapLoadable::MakeObj_hook(int nLayer, IWzProperty* pObjProp) {
    // Before the original call, because the layer weather.cpp captures is built INSIDE
    // it. This is also how the flag stays fresh: it is written for every object, so one
    // that builds no layer cannot leave a stale value for the next.
    Weather_NoteObjProp(pObjProp);

    bool bLamp = false, bGlow = false;
    if (g_bLampField && pObjProp) {
        try {
            bGlow = get_int32(pObjProp->item[L"kaentakeGlow"], 0) != 0;
            if (!bGlow) {
                bLamp = get_int32(pObjProp->item[L"kaentakeLamp"], 0) != 0;
            }
        } catch (const _com_error&) {
        }
    }
    // These two are what route the layer the engine is about to build. Reading the tags
    // without arming the flags leaves every glow uncaptured and every lamp unlit, with
    // nothing to show for it: the entries are injected, the layers are built, and no one
    // files them. That is exactly what happened when the bubble lamp was removed and the
    // deletion took these with it.
    ScopedSet<bool> gg(&g_bCaptureGlow, bGlow);
    ScopedSet<bool> gl(&g_bCaptureLamp, bLamp);
    // The entry's own coordinates, carried through to the capture so a per-lamp depth row
    // in g_aLampZAt can be matched against the post it names. Without this the sink knew
    // only "some lamp", so the per-lamp table could not be consulted at all and its rows
    // could only take effect by switching the overlap rule off for the WHOLE map.
    // NOTE the y here is the obj ENTRY y, which is the foothold-snapped anchor
    // (gy - nBaseDY), not the srcY that g_aManualLamps rows are written in. A row keyed on
    // srcY therefore will not match on y. That is tolerable only because the match is used
    // to STAND ASIDE rather than to place: a near-miss costs the automatic overlap rule,
    // not a wrong depth. If per-lamp rows are ever actually used, carry the manual index
    // through instead of the coordinates and key on that.
    POINT ptAt = {0, 0};
    if (bLamp && pObjProp) {
        try {
            ptAt.x = get_int32(pObjProp->item[L"x"], 0);
            ptAt.y = get_int32(pObjProp->item[L"y"], 0);
        } catch (const _com_error&) {
        }
    }
    ScopedSet<POINT> ga(&g_ptCaptureLampAt, ptAt);

    bool bFront = false;
    if (g_bLampField && pObjProp) {
        try { bFront = get_int32(pObjProp->item[L"kaentakeFront"], 0) != 0; }
        catch (const _com_error&) {}
    }
    ScopedSet<bool> gf(&g_bCaptureFront, bFront);
    // Stored as frame+1, so 0 (the key being absent) means "leave it animating" and is
    // not confused with "keep frame 0", which two of these three lamps actually want.
    int nKeep = -1;
    if (g_bLampField && pObjProp) {
        try { nKeep = get_int32(pObjProp->item[L"kaentakeKeep"], 0) - 1; }
        catch (const _com_error&) {}
        // A STOCK lamp carries no tag of ours: it is the map's own object and never went
        // through AddObjEntry. Recognise it by its sprite instead, so a self animating
        // fixture is stilled whether we placed it or the map did.
        if (nKeep < 0) {
            try {
                const int nDef = LampIndexOf(pObjProp);
                if (nDef >= 0) nKeep = LampStaticFrame(kLamps[nDef]);
            } catch (const _com_error&) {}
        }
    }
    ScopedSet<int> gk(&g_nCaptureKeep, nKeep);
    return CMapLoadable::MakeObj(this, nLayer, pObjProp);
}

// The lowest layer z any of the map's OWN objects uses, so a lamp can be put behind all
// of them.
//
// Read from the layers rather than assumed, because the entry's z field (0..11) and the
// engine's layer z are different number spaces: the engine maps one onto the other with a
// scale and a large origin, and guessing at that is how a lamp ends up in front of a
// house. Measuring the real values needs no knowledge of the mapping at all.
//
// Safe to compute during capture: the map's own objects are built BEFORE the injected
// entries, which are appended to the end of the obj list, so by the time a lamp arrives
// they are all present.
static int  g_nObjMinZ = 0;
static bool g_bObjMinZDone = false;

// Put every captured post behind the map's own art. Runs once, from the tick, and only
// once there is something to measure.
//
// The measurement is the whole point and it must not be guessed: a real layer z is a large
// scaled value with its own origin, so the small numbers in the obj entry (0..11) say
// nothing about it, and a literal chosen by eye lands the post either in front of the
// world or behind the backdrop.
// Objects considered in the overlap test. Henesys has 244 and Ellinia 526; the cap is a
// backstop against a map nobody has looked at, not a real limit.
#define SINK_MAX_OBJ 1024

// A layer's box in screen space. Both the post and the map's objects are read this way so
// the two are comparable; mixing a layer corner with an obj entry's origin anchor is off
// by a different constant for every sprite.
static bool LayerBox(const IWzGr2DLayerPtr& p, RECT* pr) {
    if (!p) {
        return false;
    }
    try {
        IWzVector2DPtr lt = p->Getlt();
        IWzVector2DPtr rb = p->Getrb();
        if (!lt || !rb) {
            return false;
        }
        pr->left = lt->x; pr->top = lt->y;
        pr->right = rb->x; pr->bottom = rb->y;
    } catch (const _com_error&) {
        return false;
    }
    return (pr->right > pr->left) && (pr->bottom > pr->top);
}

static void SinkLampsBehindArt() {
    // Glows count as work too. g_vLamp holds only the posts WE inject, so a map lit
    // entirely from its own lamps has an empty g_vLamp and a full g_vGlow: gating on the
    // posts alone left every glow on such a map out at GLOW_Z, in front of the player,
    // which is most of the 95 maps the stock scan now finds.
    if (g_bObjMinZDone || (g_vLamp.empty() && g_vGlow.empty())) {
        return;
    }
    // A map with an explicit depth keeps it. Without this the tables in the header are
    // DEAD: this function writes one global z over every post a frame after the map is
    // built and never consults LampZFor, so a hand-tuned row could not take effect and
    // the escape hatch documented up there did not exist at runtime.
    //
    // Skipping leaves each post at the z its obj ENTRY was injected with, which is
    // exactly what LampZFor already chose.
    {
        long lDummy = 0;
        if (LampZMapOverride(CurrentFieldID(), &lDummy)) {
            g_bObjMinZDone = true;
            return;
        }
    }
    // IN FRONT of everything that is not a plant.
    //
    // Two earlier attempts went the other way and both put the post too far back. Behind
    // the whole map hid it behind haystacks and signposts; behind the lowest FOLIAGE z was
    // no better, because on Henesys the bushes are among the backmost objects, so one
    // below them is one below the map.
    //
    // Higher z is nearer the viewer here, which weather.cpp's HILL_Z promotion relies on.
    // So the target is the top of the NON foliage stack plus one: in front of every
    // building, fence and haystack, and behind any greenery drawn in front of those.
    // Where foliage sits behind the buildings there is no single z that satisfies both,
    // and being visible wins, because a lamp post hidden behind a wall is the worse bug.
    int hiOther = 0;
    bool bOther = false, bAny = false;
    const int n = Weather_ObjCount();
    for (int i = 0; i < n; ++i) {
        IWzGr2DLayerPtr p;
        POINT pt = {0, 0};
        if (!Weather_GetObj(i, p, &pt) || !p) {
            continue;
        }
        bAny = true;
        int z = 0;
        try { z = p->z; } catch (const _com_error&) { continue; }
        if (!Weather_ObjIsPlant(i)) {
            if (!bOther || z > hiOther) { hiOther = z; bOther = true; }
        }
    }
    if (!bAny) {
        return;         // nothing captured yet: try again, do NOT assume 0
    }
    g_bObjMinZDone = true;
    // The fallback, and the old behaviour: in front of the whole non-plant stack. Known
    // good everywhere -- it has never hidden a post -- so it is what a lamp gets when the
    // per-lamp test below finds nothing to reason about.
    g_nObjMinZ = bOther ? (hiOther + 1) : 1;

    // PER LAMP, AND SCOPED TO WHAT ACTUALLY OVERLAPS IT.
    //
    // The old rule was one global z for the map, and on Henesys that is provably wrong in
    // both directions. Its "tuck behind the foliage" escape needed the LOWEST plant on the
    // whole map to be above the HIGHEST building on the whole map, which on a town with a
    // plant at the very back of the stack can never happen -- so every post sat in front
    // of the entire town. Lowering the global z instead put the posts behind the walls.
    //
    // The question is local, so the measurement is too: a post only has to clear the art
    // it actually touches. Take the highest non-plant object whose BOX INTERSECTS the
    // post, and sit one above it. That is in front of every wall the post is standing
    // against, and behind any greenery drawn above those walls -- which is the mushrooms.
    //
    // Distance was tried and rejected: scoping by "nearest plant within N pixels" hides
    // 11 of the 33 hand-placed posts across the five towns that have them, six of those
    // completely, because the nearest plant is often behind a building the post also
    // overlaps. Overlap is the only scope that cannot make a post disappear.
    //
    // Both boxes come from Getlt/Getrb on the LAYER, so they are in one space. Reading the
    // lamp's obj entry instead would compare an origin anchor against a layer corner, and
    // the two differ by a per sprite constant of tens to hundreds of pixels.
    RECT rcObj[SINK_MAX_OBJ];
    int  nObjZ[SINK_MAX_OBJ];
    int  nObjs = 0;
    for (int i = 0; i < n && nObjs < SINK_MAX_OBJ; ++i) {
        IWzGr2DLayerPtr p;
        POINT pt = {0, 0};
        if (!Weather_GetObj(i, p, &pt) || !p || Weather_ObjIsPlant(i)) {
            continue;
        }
        if (!LayerBox(p, &rcObj[nObjs])) {
            continue;
        }
        try { nObjZ[nObjs] = p->z; } catch (const _com_error&) { continue; }
        ++nObjs;
    }

    int nSunk = 0;
    for (size_t i = 0; i < g_vLamp.size(); ++i) {
        IWzGr2DLayer* q = g_vLamp[i].GetInterfacePtr();
        if (!q) continue;
        if (i < g_vLampFront.size() && g_vLampFront[i]) {
            // Into the band, one step above the glows, rather than left out at
            // LAMP_FRONT_Z. It still covers its own light; it no longer covers the
            // player.
            try { q->z = g_nObjMinZ + 1; } catch (const _com_error&) {}
            continue;
        }
        // A per-lamp row wins outright over the overlap rule, for this post only. That is
        // the escape hatch g_aLampZAt is for: a position the overlap rule genuinely cannot
        // satisfy, pinned by hand, without switching the rule off for every other lamp on
        // the same map (which is what matching those rows by map id alone used to do).
        //
        // STAND ASIDE, do not write the row's value here. LampZFor returns a value in the
        // obj-ENTRY z space -- LAMP_Z is 12 because the map's own entries top out at 11 --
        // and this loop writes LAYER z, whose real values are near -1.07e9. Injection has
        // already applied the row to the entry (see the LampZFor call in the manual
        // placement path), so the correct action is simply to leave that post alone.
        if (i < g_vLampAt.size()
                && LampZFor(CurrentFieldID(), g_vLampAt[i].x, g_vLampAt[i].y) != LAMP_Z) {
            continue;
        }
        int nWant = g_nObjMinZ;
        RECT rcL;
        if (LayerBox(g_vLamp[i], &rcL)) {
            int hiHit = 0;
            bool bHit = false;
            for (int k = 0; k < nObjs; ++k) {
                if (rcL.left < rcObj[k].right && rcObj[k].left < rcL.right
                 && rcL.top < rcObj[k].bottom && rcObj[k].top < rcL.bottom) {
                    if (!bHit || nObjZ[k] > hiHit) { hiHit = nObjZ[k]; bHit = true; }
                }
            }
            if (bHit && hiHit + 1 < nWant) {
                nWant = hiHit + 1;
                ++nSunk;
            }
        }
        try { q->z = nWant; } catch (const _com_error&) {}
    }
    // The GLOWS come down with the posts.
    //
    // They were injected at GLOW_Z, which is 100000: an obj entry z chosen so the light
    // lands over the scene, and so far in front that it also landed over the PLAYER. A
    // lamp post correctly disappears behind a character standing in front of it while
    // its own bulb painted over that character's head.
    //
    // g_nObjMinZ, the same band the posts fall back to. Not per post: g_vLamp holds only
    // the posts WE injected while a glow may belong to one of the map's own lamps, and
    // g_vGlowPlan's nLampSeq counts both, so there is no reliable glow to post mapping
    // to copy a sunk z from. The band is what matters here, because the complaint is the
    // player, and everything in the band is behind the player.
    //
    // Equal z with a normal post is deliberate: the glow is injected AFTER its post, so
    // at the same z it still draws over it. A front lamp is lifted one step above, just
    // over its own glow, which is the ordering it wanted from LAMP_FRONT_Z anyway.
    int nGlowSunk = 0;
    for (size_t i = 0; i < g_vGlow.size(); ++i) {
        if (!g_vGlow[i]) {
            continue;
        }
        try {
            g_vGlow[i]->z = g_nObjMinZ;
            ++nGlowSunk;
        } catch (const _com_error&) {}
    }
    DEBUG_MESSAGE("lamps: %u posts, fallback z %d, %d sunk to their own overlap, "
                  "%d glow(s) to the band",
                  (unsigned)g_vLamp.size(), g_nObjMinZ, nSunk, nGlowSunk);
}

// Freeze a self-animating sprite on one frame.
//
// HISTORY, because the comment here used to describe art that is no longer used. The glows
// were originally STOCK canvases (acc7/mureungTW/market/2 and friends), and those really
// do carry a0/a1 alpha ramps the engine drives on its own clock: every lamp's copy started
// at map load, so they pulsed in unison and the per-frame colour write in ApplyGlows lost
// to the animator. That is what this function was written for.
//
// The glows are now DRAWN (Map/Obj/MapleMoonLamp.img, build_lamp_glows.py) and every
// one of them is a single frame with no animator, so on the glow path this is a no-op.
// It is kept, and still called, because the LAMP path genuinely needs it: several stock
// fixtures animate themselves (see kaentakeKeep and LampStaticFrame), and a map's own lamp
// object is recognised by its sprite rather than by a tag of ours.
//
// So the per-frame colour write in ApplyGlows is NOT justified by an animator any more.
// It is justified by the engine re-asserting layer alpha, which is the same reason the
// tiled backdrop has to be re-asserted; see IMPLEMENTATION.md.
//
// Two attempts, cheapest first. Animate(GA_STOP) may be enough on its own; if the layer
// still carries more canvases afterwards, the extras are removed so there is nothing left
// to animate between. Both are guarded, and if both fail the only cost is the pulse.
static void FreezeToFrame(const IWzGr2DLayerPtr& pLayer, int nKeep) {
    if (!pLayer) {
        return;
    }
    try {
        pLayer->Animate(GA_STOP);
    } catch (const _com_error&) {
    }
    // Drop every frame but the one asked for. RemoveCanvas is indexed, so this walks
    // DOWNWARD: removing from the front would renumber the rest under the loop. Indices
    // above nKeep can go in any order; the ones below it are removed last, which slides
    // the survivor down to 0 with nothing left to animate against.
    for (int i = 8; i >= 0; --i) {
        if (i == nKeep) {
            continue;
        }
        try {
            pLayer->RemoveCanvas(i);
        } catch (const _com_error&) {
            // out of range for this layer, which is the normal case for most of them
        }
    }
}

static void StaticiseGlow(const IWzGr2DLayerPtr& pLayer) {
    FreezeToFrame(pLayer, 0);
}

bool Lamps_CaptureLayer(const IWzGr2DLayerPtr& pLayer) {
    // Before the branches, not inside one. A stock lamp matches none of them: it is an
    // ordinary map object that weather.cpp goes on to capture for the tint, and it still
    // has to have its animator stopped.
    if (g_nCaptureKeep >= 0) {
        FreezeToFrame(pLayer, g_nCaptureKeep);
    }
    if (g_bCaptureGlow) {
        StaticiseGlow(pLayer);
        if (g_bLastLampDrifts && !g_vDrift.empty()
                && g_vDrift.back().nGlows < LAMP_MAX_EMITTERS) {
            g_vDrift.back().pGlow[g_vDrift.back().nGlows++] = pLayer;
        }
        g_vGlow.push_back(pLayer);
        return true;
    }
    if (g_bCaptureLamp) {
        // g_bCaptureFront is true for exactly the three sea creatures, which are also
        // exactly the lamps that drift, so it doubles as the test and no second lookup
        // is needed here.
        g_bLastLampDrifts = g_bCaptureFront;
        if (g_bLastLampDrifts) {
            DRIFTER d;
            d.pSprite = pLayer;
            d.nGlows  = 0;
            // A hash, not the index: a linear phase aliases against the oscillator and
            // puts the creatures into lockstep, which is the mistake the lamp flicker
            // made twice before it was taken out.
            const unsigned int h = (unsigned int)(g_vDrift.size() + 1) * 2654435761u;
            d.fPhase = (float)((h ^ (h >> 13)) % 6283u) / 1000.0f;
            d.nX = d.nY = 0;
            g_vDrift.push_back(d);
        }
        g_vLampFront.push_back(g_bCaptureFront);
        g_vLampAt.push_back(g_ptCaptureLampAt);
        // The z is NOT set here. This runs while the field is still being built, and the
        // map's own objects may not be captured yet: measuring then gave a minimum of 0
        // against real layer z values in the hundreds of millions negative, so the post
        // was placed far in FRONT of everything instead of behind it. SinkLampsBehindArt
        // does it once the map is complete.
        g_vLamp.push_back(pLayer);
        return true;
    }
    return false;
}

// ---------------------------------------------------------------- the switch

// The darkness being RENDERED, not the clock. Weather::NightLevel() is the time of day
// alone; a storm at noon renders dark while NightLevel() still says day. Lighting off
// the clock would leave every lamp's pool lifted toward a daylight the rest of the map
// is not at, i.e. a visible seam around each lamp for the whole storm -- and lamps that
// refuse to come on in the one daytime weather dark enough to want them.
static float EffectiveNightSafe() {
    float n = Weather_EffectiveNight();
    if (n < 0.0f) n = 0.0f;
    if (n > 1.0f) n = 1.0f;
    return n;
}

// Steady most of the time, then an occasional burst of stuttering with brief cut-outs.
// A lamp that flickers constantly reads as a broken renderer; one that is fine for a
// minute and then stutters reads as a failing tube.
// Which lamps are faulty. A hash rather than seq % FLICKER_EVERY, because the modulo
// always selects lamp 0 and a street whose first lamp is the broken one, every time,
// reads as a bug rather than as character.
// DISABLED. No lamp is faulty and nothing flickers.
//
// The idea was that roughly one lamp in nine is a failing tube. Two goes at it did not
// survive contact: the first had every lamp stuttering in unison because the per lamp
// offset aliased against the oscillator's period, and even with that fixed and the lamps
// properly spread, a street where lights randomly dim reads as a rendering fault rather
// than as character. The machinery below is left intact and unreferenced so it can be
// switched back on by returning the hash again, but nothing calls for it now.
static bool IsFaultyLamp(int nSeq) {
    (void)nSeq;
    return false;
}

// Steady most of the time, then an occasional burst of stuttering. Tuned DOWN from the
// donor's version after seeing it in game: bursts were frequent (the gate admitted about
// a quarter of the time) and dipped to 4% brightness, so a faulty lamp read as a strobe
// and, with several lamps in view, as the whole scene misbehaving.
//
// Now: the gate admits ~9% of the time, and the deepest dip is a little under half
// brightness rather than a blackout. A real failing tube dims and buzzes; it does not
// switch itself off frame by frame.
// The per lamp time offset.
//
// This was `seed * 7.3`, and a LINEAR multiple always aliases against a periodic
// function. The slow oscillator below has a period of 2*pi/0.45 = 13.96, and 7.3 is
// 0.5228 of that, so the lamps landed in two tight clusters half a cycle apart: seeds 0,
// 2, 4, 6 at phase 0.00 to 0.14 and seeds 1, 3, 5, 7 at 0.52 to 0.66. In game that is a
// street flickering in unison on a schedule, which is what it looked like.
//
// A hash spread over 400 seconds, roughly 28 slow periods, has no such relationship to
// the period and puts every lamp somewhere different.
static float FlickerOffset(int seed) {
    unsigned int h = (unsigned int)seed * 2654435761u;
    h ^= h >> 13;
    h *= 1274126177u;
    h ^= h >> 16;
    return (float)(h % 400000u) * 0.001f;
}

static float Flicker(unsigned long tick, int seed) {
    const float s = tick * 0.001f + FlickerOffset(seed);
    const float slow = sinf(s * 0.45f + sinf(s * 0.13f) * 2.5f);
    float burst = (slow - 0.86f) / 0.14f;
    if (burst <= 0.0f) {
        return 1.0f;
    }
    if (burst > 1.0f) burst = 1.0f;
    const float fast = 0.5f * sinf(s * 32.0f) + 0.3f * sinf(s * 51.0f) + 0.2f * sinf(s * 73.0f);
    float f = 0.72f + 0.28f * fast;                       // shallow stutter, not a strobe
    if (sinf(s * 17.0f + sinf(s * 4.0f) * 3.0f) > 0.86f) {
        f = 0.45f;                                        // the deep dip, still clearly lit
    }
    float out = (1.0f - burst) + burst * f;
    if (out < 0.40f) out = 0.40f;
    if (out > 1.00f) out = 1.00f;
    return out;
}

static void SizeLampState() {
    // Sized to the larger of the two, and every index bounds-checked below: the pairing
    // between a glow layer and its plan entry holds by construction (the entries are
    // injected in order and MakeObj builds them in order), but it is an invariant the
    // engine could break by building two layers for one animated entry, and a silent
    // desync would drive lamp N's light with lamp M's timing.
    size_t n = g_vGlow.size();
    if (g_vGlowPlan.size() > n) n = g_vGlowPlan.size();
    if (g_vLampOn.size() != n) {
        g_vLampOn.assign(n, g_bTripped ? 1.0f : 0.0f);
    }
    if (!g_vGlow.empty() && g_vGlowPlan.size() != g_vGlow.size()) {
        // Expected after a `!lamp` preview, which adds glows outside the plan on
        // purpose; anything beyond the plan falls back to default timing rather than
        // going dark. Worth saying once anyway, because the other way to reach this is
        // the engine building more than one layer for a single obj entry, which would
        // silently drive lamp N's light with lamp M's switch.
        LOG_ONCE("lamps: %u glow layers but %u planned (previews do this); "
                 "the extra glows run on default timing",
                 (unsigned)g_vGlow.size(), (unsigned)g_vGlowPlan.size());
    }
}

// Advance the photocell and each lamp's warm-up. bSnap assigns instead of ramping, for
// map entry: warming every lamp up again after each portal is the same bug the night
// tint already avoids by snapping on arrival.
static void StepSwitch(bool bSnap) {
    const float fNight = EffectiveNightSafe();
    const bool bWant = g_bTripped ? (fNight > LAMP_OFF_LEVEL) : (fNight >= LAMP_ON_LEVEL);
    const unsigned int tNow = GetTickCount();
    float dt = 0.0f;
    if (g_tLastTick != 0) {
        const unsigned int d = tNow - g_tLastTick;      // correct across the 49-day wrap
        dt = (d < 5000u) ? (float)d : 0.0f;             // a long stall must not jump the ramp
    }
    g_tLastTick = tNow;
    if (bWant != g_bTripped) {
        g_bTripped = bWant;
        g_fSinceTrip = 0.0f;
    } else {
        g_fSinceTrip += dt;
    }

    SizeLampState();
    // Full when the photocell has tripped, otherwise whatever twilight is worth. Taking
    // the max rather than branching means the cooldown after release lands on the dim
    // level instead of on nothing, so dawn fades lamps down to a glow and then out rather
    // than snapping them off while it is still half dark.
    const float fTwilight = TwilightLevel(fNight);
    const float fTarget = g_bTripped ? 1.0f : fTwilight;
    const float fRate = dt / (g_bTripped ? LAMP_WARMUP_MS : LAMP_COOLDOWN_MS);
    for (size_t i = 0; i < g_vLampOn.size(); ++i) {
        if (bSnap) {
            g_vLampOn[i] = fTarget;
            continue;
        }
        // Each lamp waits its turn. The sequence is per PHYSICAL lamp, not per glow, so
        // a three-globe post lights all three globes together.
        const int nSeq = (i < g_vGlowPlan.size()) ? g_vGlowPlan[i].nLampSeq : (int)i;
        const float fDelay = (float)((nSeq * 977) % (int)LAMP_STAGGER_MS);
        if (g_fSinceTrip < fDelay) {
            continue;
        }
        float v = g_vLampOn[i];
        if (v < fTarget) {
            v += fRate;
            if (v > fTarget) v = fTarget;
        } else if (v > fTarget) {
            v -= fRate;
            if (v < fTarget) v = fTarget;
        }
        g_vLampOn[i] = v;
    }

    // Rebuild the light list: only lamps that are actually emitting light anything.
    // Gathering them all and relying on the night level to zero the lift is what puts
    // bright discs of pavement under every unlit lamp during the twenty real minutes
    // between the sky starting to darken and the lamps tripping.
    g_nLights = 0;
    for (size_t i = 0; i < g_vGlow.size() && g_nLights < MAX_LIGHTS; ++i) {
        const float on = (i < g_vLampOn.size()) ? g_vLampOn[i] : 0.0f;
        if (on <= 0.0f || !g_vGlow[i]) {
            continue;
        }
        try {
            if (i < g_vGlowPlan.size() && g_vGlowPlan[i].bNoLight) {
                continue;   // a filament lights its own glass; the wash is only air
            }
            g_aLights[g_nLights].x  = (float)g_vGlow[i]->x;
            g_aLights[g_nLights].y  = (float)g_vGlow[i]->y;
            g_aLights[g_nLights].on = on;
            g_aLights[g_nLights].r  = LIGHT_R_OUTER
                    * ((i < g_vGlowPlan.size() && g_vGlowPlan[i].fRange > 0.0f)
                       ? g_vGlowPlan[i].fRange : 1.0f);
            const LIGHTPT& light = g_aLights[g_nLights++];
            const float minX = light.x - light.r, maxX = light.x + light.r;
            const float minY = light.y - light.r, maxY = light.y + light.r;
            if (g_nLights == 1) {
                g_fLightMinX = minX; g_fLightMaxX = maxX;
                g_fLightMinY = minY; g_fLightMaxY = maxY;
            } else {
                if (minX < g_fLightMinX) g_fLightMinX = minX;
                if (maxX > g_fLightMaxX) g_fLightMaxX = maxX;
                if (minY < g_fLightMinY) g_fLightMinY = minY;
                if (maxY > g_fLightMaxY) g_fLightMaxY = maxY;
            }
        } catch (const _com_error&) {
        }
    }
}

bool Lamps_HasLights() {
    return g_nLights > 0;
}

// 0 (dark) .. 1 (at a lamp at full brightness). A MAX over falloff*brightness, not the
// falloff of the nearest lamp: once lamps differ in output, "nearest" stops meaning
// "brightest", and a near lamp still warming up would shadow a far one already at full.
static float LightFactorAt(float px, float py) {
    if (g_nLights == 0 || px < g_fLightMinX || px > g_fLightMaxX
            || py < g_fLightMinY || py > g_fLightMaxY) {
        return 0.0f;
    }
    float fBest = 0.0f;
    for (int i = 0; i < g_nLights; ++i) {
        const float dx = px - g_aLights[i].x;
        const float dy = py - g_aLights[i].y;
        const float d2 = dx * dx + dy * dy;
        // Per light reach, not the global one: a brazier throws less than a street lamp.
        const float rOut = (g_aLights[i].r > 0.0f) ? g_aLights[i].r : LIGHT_R_OUTER;
        if (d2 >= rOut * rOut) {
            continue;
        }
        // The bright core scales with the reach, so shortening a light shrinks the whole
        // falloff rather than leaving a full size hotspot with an abrupt edge on it.
        const float rIn = LIGHT_R_INNER * (rOut / LIGHT_R_OUTER);
        const float d = sqrtf(d2);
        float f;
        if (d <= rIn) {
            f = 1.0f;
        } else {
            const float u = (rOut - d) / (rOut - rIn);
            f = u * u * (3.0f - 2.0f * u);
        }
        f *= g_aLights[i].on;
        if (f > fBest) fBest = f;
    }
    return fBest;
}

// ---------------------------------------------------------------- apply

static void ApplyLampPosts() {
    // The post is scenery, so it is tinted with the map -- and lifted by its own light,
    // which at distance 0 is the strongest lift on the map. At full day this collapses
    // to Weather_SceneryColor(1.0f) with a night of 0, i.e. the plain identity, which is
    // exactly what an untouched object already carries.
    for (size_t i = 0; i < g_vLamp.size(); ++i) {
        if (!g_vLamp[i]) continue;
        try {
            const float lf = LightFactorAt((float)g_vLamp[i]->x, (float)g_vLamp[i]->y);
            g_vLamp[i]->color = Weather_TintColor(1.0f, EffectiveNightSafe() * (1.0f - lf * LAMP_SELF_LIFT));
        } catch (const _com_error&) {
        }
    }
}

// Additive light ADDS UP: two overlapping glows sum and three clip to flat white, which
// is what a cluster of lamps in one spot looked like. Dividing each glow in a cluster by
// sqrt(count) makes N lamps read as sqrt(N) times brighter instead of N times, so a
// crowd still looks brighter than a single lamp but never saturates to a white disc.
//
// Reuses the light list already rebuilt this frame, so this costs nothing to gather.
// The glow's own entry is in that list, hence n >= 1.
static float CrowdScale(float x, float y) {
    int n = 0;
    for (int i = 0; i < g_nLights; ++i) {
        const float dx = x - g_aLights[i].x;
        const float dy = y - g_aLights[i].y;
        if (dx * dx + dy * dy < GLOW_CROWD_R * GLOW_CROWD_R) {
            ++n;
        }
    }
    return (n <= 1) ? 1.0f : (1.0f / sqrtf((float)n));
}

static void ApplyGlows() {
    const unsigned long tick = GetTickCount();

    // WHY ARE THERE NO HALOS. Several causes look identical in game -- no glow layers
    // captured, layers captured but unplanned, plans present but the switch never tripped,
    // or every layer being a core. Say which, once per field per switch state.
    {
        static int s_nSaid = -1;
        const int nState = (int)(EffectiveNightSafe() * 10.0f) * 4 + (g_bTripped ? 1 : 0);
        if (s_nSaid != nState) {
            s_nSaid = nState;
            int nCore = 0, nLit = 0, nNull = 0;
            for (size_t i = 0; i < g_vGlow.size(); ++i) {
                if (!g_vGlow[i]) { ++nNull; continue; }
                if (i < g_vGlowPlan.size() && g_vGlowPlan[i].bCore) ++nCore;
                if (i < g_vLampOn.size() && g_vLampOn[i] > 0.0f) ++nLit;
            }
            LOG_ONCE_PER_ID(nState,
                "lamps: night %.2f tripped %d | %u glow layers (%d core, %d null), "
                "%u plans, %u on-levels, %d lit, %d lights",
                EffectiveNightSafe(), g_bTripped ? 1 : 0,
                (unsigned)g_vGlow.size(), nCore, nNull,
                (unsigned)g_vGlowPlan.size(), (unsigned)g_vLampOn.size(), nLit, g_nLights);
        }
    }
    for (size_t i = 0; i < g_vGlow.size(); ++i) {
        if (!g_vGlow[i]) continue;
        const float on = (i < g_vLampOn.size()) ? g_vLampOn[i] : 0.0f;
        try {
            if (on <= 0.0f) {
                // A hard off, not alpha 0. Relying on a zero alpha to hide an additive
                // layer is an untested assumption about how the engine folds layer alpha
                // into LB_ADD, and with the post now permanently visible a daytime halo
                // would read as an art choice rather than as the bug it is. This also
                // skips the flicker trig for every lamp on every map all day.
                g_vGlow[i]->visible = 0;
                continue;
            }
            g_vGlow[i]->visible = 1;
            const int nSeq = (i < g_vGlowPlan.size()) ? g_vGlowPlan[i].nLampSeq : (int)i;
            const float fScale = (i < g_vGlowPlan.size()) ? g_vGlowPlan[i].fAlphaScale : 1.0f;
            const bool bCore = (i < g_vGlowPlan.size()) && g_vGlowPlan[i].bCore;
            const bool bNoLight = (i < g_vGlowPlan.size()) && g_vGlowPlan[i].bNoLight;
            float a = on * fScale * (float)(bCore ? GLOW_CORE_ALPHA_MAX : GLOW_ALPHA_MAX);
            // Crowding is a fix for stacked light in the AIR. A bulb does not get dimmer
            // because there is another lamp down the street, and on the Henesys post the
            // three globes are 30 px apart -- inside GLOW_CROWD_R of each other -- so
            // applying it here would dim all three for standing on the same lamp.
            if (!bNoLight) {
                a *= CrowdScale((float)g_vGlow[i]->x, (float)g_vGlow[i]->y);
            }
            if (IsFaultyLamp(nSeq)) {
                a *= Flicker(tick, nSeq);
            }
            if (a < 0.0f) a = 0.0f;
            if (a > 255.0f) a = 255.0f;
            // A halo is light in the air and ADDS to what is behind it. A core is the lit
            // glass itself and REPLACES it; see GLOW_CORE_ALPHA_MAX for why that is not a
            // stylistic preference.
            g_vGlow[i]->blend = bCore ? LB_NORMAL : LB_ADD;
            const unsigned int uRgb = (i < g_vGlowPlan.size() && g_vGlowPlan[i].uRgb)
                                    ? g_vGlowPlan[i].uRgb : 0x00FFFFFFu;
            g_vGlow[i]->color = ((unsigned int)a << 24) | uRgb;
        } catch (const _com_error&) {
        }
    }
}

void Lamps_Update() {
    if (!g_bLampField) {
        return;
    }
    StepSwitch(false);
    ApplyLampPosts();
    ApplyGlows();
}

// The colour a piece of scenery at this position should be, lamps included.
//
// For layers the weather module does not own. The foliage sway REPLACES a plant with
// generated frames of its own, so those layers are not in g_vObjs and the relight pass
// never reaches them -- which is why swaying plants stayed at the uniform night tint
// while everything around them lit up. They ask for their colour here instead.
//
// Positions are LAYER space, the same space g_aLights is gathered in.
unsigned int Lamps_SceneryColorAt(float x, float y) {
    const float fNight = EffectiveNightSafe();
    if (g_nLights <= 0) {
        return Weather_TintColor(1.0f, fNight);
    }
    const float lf = LightFactorAt(x, y);
    return Weather_TintColor(1.0f, fNight * (1.0f - lf * LIGHT_STRENGTH));
}

void Lamps_RelightScenery(std::vector<IWzGr2DLayerPtr>& vTiles,
                          std::vector<IWzGr2DLayerPtr>& vObjs,
                          std::vector<IWzGr2DLayerPtr>& vNpc,
                          float fNight, float fNpcScale) {
    if (g_nLights <= 0) {
        return;
    }
    std::vector<IWzGr2DLayerPtr>* aLists[3] = { &vTiles, &vObjs, &vNpc };
    const float aScale[3] = { 1.0f, 1.0f, fNpcScale };
    for (int l = 0; l < 3; ++l) {
        std::vector<IWzGr2DLayerPtr>& v = *aLists[l];
        // The sample point per layer, measured ONCE per field. Two things were wrong with
        // reading it per frame:
        //
        //  1. CORRECTNESS. An IWzGr2DLayer's x/y is its TOP-LEFT, not the sprite's world
        //     anchor, so a tall building beside a lit lamp was asked about a point up to
        //     its full height above and half its width to the left of where it actually
        //     stands. A 400x500 wall 100 px from a Henesys lamp was tested at ~539 px and
        //     came back at 0.13 of the lift instead of ~1.0: the pavement under the lamp
        //     brightened while the wall next to it stayed at almost full night. It was
        //     also self-inconsistent, since the sway path tests a plant at its centre and
        //     the relight path tested the identical non-swaying plant at its corner.
        //
        //  2. COST. This is the most expensive thing the weather system does per tick, and
        //     two thirds of it was recomputing constants: four COM property gets per
        //     captured tile, object and NPC, every tick, before the bounding-box rejection
        //     could even be applied. Map art does not move.
        RelightPts& pts = g_aRelightPts[l];
        if (pts.uFor != v.size()) {
            pts.v.clear();
            pts.v.reserve(v.size());
            for (size_t i = 0; i < v.size(); ++i) {
                POINT pt = {0, 0};
                if (v[i]) {
                    try {
                        // Centre, not corner. The canvas read happens here and only here.
                        int cw = 0, ch = 0;
                        IWzCanvasPtr c = v[i]->Getcanvas();
                        if (c) { cw = c->width; ch = c->height; }
                        pt.x = v[i]->x + cw / 2;
                        pt.y = v[i]->y + ch / 2;
                    } catch (const _com_error&) {
                        pt.x = 0; pt.y = 0;
                    }
                }
                pts.v.push_back(pt);
            }
            pts.uFor = v.size();
        }
        for (size_t i = 0; i < v.size() && i < pts.v.size(); ++i) {
            if (!v[i]) continue;
            const float lf = LightFactorAt((float)pts.v[i].x, (float)pts.v[i].y);
            if (lf <= 0.0f) {
                continue;   // outside every pool: the uniform pass already got it right
            }
            try {
                v[i]->color = Weather_TintColor(1.0f, fNight * aScale[l] * (1.0f - lf * LIGHT_STRENGTH));
            } catch (const _com_error&) {
            }
        }
    }
}

// ---------------------------------------------------------------- lifecycle

void Lamps_OnFieldLoaded() {
    if (!g_bLampField) {
        return;
    }
    g_tLastTick = 0;
    g_fSinceTrip = LAMP_STAGGER_MS;   // past every stagger delay, so a snap really snaps
    g_bTripped = EffectiveNightSafe() >= LAMP_ON_LEVEL;
    g_vLampOn.clear();
    StepSwitch(true);
    ApplyLampPosts();
    ApplyGlows();
}

void Lamps_OnObjRebuild(bool bBefore) {
    if (!g_bLampField) {
        return;
    }
    if (bBefore) {
        // The depth latch has to come off with them. g_bObjMinZDone was cleared only on
        // leaving the field, so after a graphics-detail apply or a `!lamp` preview -- both
        // of which rebuild the objects in place -- SinkLampsBehindArt returned early and
        // every rebuilt post kept nothing but its raw obj entry z. On a map with a depth
        // row that is a low number, so the whole town's lamps dropped behind the scenery
        // the moment the player opened System Options.
        g_bObjMinZDone = false;
    // The sample-point cache belongs to the layer set that has just gone away.
    for (int i = 0; i < 3; ++i) {
        g_aRelightPts[i].v.clear();
        g_aRelightPts[i].uFor = (size_t)-1;
    }
        // The rebuild destroys every object layer, ours included. Dropping the
        // references first is what stops the vectors accumulating a set per rebuild and
        // stops the per-frame apply writing into destroyed layers.
        g_vLamp.clear();
        g_vLampAt.clear();
        g_vLampFront.clear();
        g_vGlow.clear();
        g_vDrift.clear();        // likewise: sprite AND glow refs
        g_bLastLampDrifts = false;
        return;
    }
    g_vLampOn.clear();
    StepSwitch(true);
    ApplyLampPosts();
    ApplyGlows();
}

void Lamps_OnLeaveField() {
    g_vLamp.clear();
    g_vLampAt.clear();
    g_vLampFront.clear();
    g_vGlow.clear();
    g_vDrift.clear();
    g_bLastLampDrifts = false;
    g_vGlowPlan.clear();
    g_vLampOn.clear();
    g_nLights = 0;
    g_fLightMinX = g_fLightMaxX = g_fLightMinY = g_fLightMaxY = 0.0f;
    g_nLampSeqCount = 0;
    g_bLampField = false;
    g_bTripped = false;
    g_tLastTick = 0;
    g_bObjMinZDone = false;
    g_nObjMinZ = 0;
    // The sample-point cache belongs to the layer set that has just gone away.
    for (int i = 0; i < 3; ++i) {
        g_aRelightPts[i].v.clear();
        g_aRelightPts[i].uFor = (size_t)-1;
    }
}

// ---------------------------------------------------------------- !lamp preview
//
// The request only records what to place. Actually placing it means adding a WZ
// property and asking the engine to rebuild its objects, neither of which is safe on
// the receive thread, so the work happens on the next frame.
#define LAMP_MODE_PLACE 0
#define LAMP_MODE_CLEAR 1

static std::atomic<int>  g_nPendingMode{LAMP_MODE_PLACE};
static std::atomic<int>  g_nPendingLamp{-1};
static std::atomic<int>  g_nPendingMapId{0};
static std::atomic<long> g_lPendingX{0};
static std::atomic<long> g_lPendingY{0};
static std::atomic<bool> g_bPendingDirty{false};

void Lamp_HandlePreviewPacket(CInPacket* pPacket) {
    if (!pPacket) {
        return;
    }
    pPacket->SetOffset(pPacket->GetOffset() + 2);
    if (!pPacket->CanRead(14)) {
        return;
    }
    const unsigned char uMode = pPacket->Decode<unsigned char>();
    const unsigned char uLamp = pPacket->Decode<unsigned char>();
    const int nMapId = pPacket->Decode<int>();
    const int nX = pPacket->Decode<int>();
    const int nY = pPacket->Decode<int>();
    g_nPendingMode.store((int)uMode);
    g_nPendingLamp.store((int)uLamp);
    g_nPendingMapId.store(nMapId);
    g_lPendingX.store((long)nX);
    g_lPendingY.store((long)nY);
    g_bPendingDirty.store(true);
}

// Strip every preview entry from the field, walking BACK from the end while the tag
// holds. Previews are always appended after everything else, so they form one trailing
// block; removing from the end is what keeps the obj indices contiguous, and a gap in
// that sequence would make the engine build a null object on the next rebuild.
static int ClearPreviews(IWzPropertyPtr pObj) {
    int nRemoved = 0;
    for (;;) {
        const int nCount = (int)pObj->count;
        if (nCount <= 0) {
            break;
        }
        wchar_t sIdx[16];
        swprintf_s(sIdx, L"%d", nCount - 1);
        IUnknownPtr pUnkE = pObj->item[sIdx].GetUnknown();
        IWzPropertyPtr pEntry;
        if (!pUnkE || FAILED(pUnkE->QueryInterface(&pEntry)) || !pEntry) {
            break;
        }
        if (get_int32(pEntry->item[LAMP_PREVIEW_TAG], 0) == 0) {
            break;   // reached the map's own entries, or ours from a real inject
        }
        pObj->Remove(Ztl_bstr_t(sIdx));
        ++nRemoved;
    }
    return nRemoved;
}

// Append one preview lamp to the live field and rebuild the objects so it appears
// without a map change.
//
// The rebuild goes through RestoreObj_hook rather than the raw RestoreObj: the hook is
// what re-arms the capture flags on a rebuild that did not come from LoadMap, and it is
// the same path the System Options graphics-detail apply already takes, so this is an
// exercised route rather than a new one.
static void ApplyPendingPreview() {
    if (!g_bPendingDirty.exchange(false)) {
        return;
    }
    const int nMode = g_nPendingMode.load();
    const int nLamp = g_nPendingLamp.load();
    if (nMode == LAMP_MODE_PLACE && (nLamp < 0 || nLamp >= kLampCount)) {
        return;
    }
    CField* pField = get_field();
    if (!pField) {
        return;
    }
    // The command packet can race a portal or map change. Never mutate the new field
    // with a preview whose coordinates belonged to the old one.
    if (g_nPendingMapId.load() != CurrentFieldID()) {
        return;
    }
    try {
        IWzPropertyPtr pPropField = pField->m_pPropField;
        if (!pPropField) {
            return;
        }
        // Same layer the permanent injection would use, so a preview lands where the
        // real lamp will. A preview that composited differently from the thing it is
        // previewing would be worse than no preview.
        const int nPrevMapId = CurrentFieldID();
        int nLayer = -1;
        IWzPropertyPtr pObj = FindObjList(pPropField, &nLayer, LampLayerFor(nPrevMapId));
        if (!pObj) {
            return;
        }

        if (nMode == LAMP_MODE_CLEAR) {
            const int nRemoved = ClearPreviews(pObj);
            if (nRemoved > 0) {
                // The plan describes the injected glows only, and the previews that were
                // just removed were appended past its end. Rebuilding drops their layers;
                // the plan itself never included them, so nothing there needs unwinding.
                pField->RestoreObj_hook();
            }
            DEBUG_MESSAGE("lamps: cleared %d preview entries", nRemoved);
            return;
        }

        const LAMPDEF& d = kLamps[nLamp];
        std::vector<FHSEG> segs;
        Lamps_CollectFootholds(pPropField, segs);
        long gy = g_lPendingY.load();
        GroundYAt(segs, g_lPendingX.load(), g_lPendingY.load(), &gy);
        const long x = g_lPendingX.load();
        const long y = gy - d.nBaseDY;

        unsigned int uIdx = pObj->count;
        const bool bFront = LampDrawsOverGlow(d);
        // Keyed on the coordinates the command PRINTED, which is what a g_aLampZAt row
        // would be pasted from, so a per-lamp override can be previewed before it is
        // committed. A per-map row applies here whatever the position.
        const long lZ = bFront ? LAMP_FRONT_Z
                               : LampZFor(nPrevMapId, x, g_lPendingY.load());
        AddObjEntry(pObj, uIdx++, d.sOS, d.sL0, d.sL1, d.sL2, x, y,
                    lZ, false, true, true, bFront,
                    LampKeepFrame(d));
        AddGlowsFor(pObj, &uIdx, d, x, y, false, g_nLampSeqCount++, true);

        // The marker is deliberately NOT bumped. It records what a clean inject would
        // add, and a preview is not that: bumping it would make the next entry to this
        // map compute a different total and disable lamps there until restart, which is
        // a bad trade for a placement tool. Leaving it alone means the preview entries
        // stay on the cached list and are rebuilt on re-entry with default timing --
        // they are outside the plan, which SizeLampState already tolerates. A preview
        // is scaffolding for filling in g_aManualLamps, not a state meant to ship.
        g_bLampField = true;
        pField->RestoreObj_hook();
        DEBUG_MESSAGE("lamps: preview lamp %d at (%ld,%ld), base y %ld", nLamp, x, gy, y);
    } catch (const _com_error& e) {
        (void)e;
        DEBUG_MESSAGE("lamps: preview failed 0x%08X", e.Error());
    }
}

// The bob.
//
// Two layers on DIFFERENT rates, deliberately not a whole-number ratio, so they drift in
// and out of step instead of moving as one welded object. Offsets are applied as deltas
// against what is already there, so nothing accumulates.
#define BUB_DRIFT_X   4.0f
#define BUB_DRIFT_Y   3.0f
#define BUB_CAND_X    2.0f
#define BUB_CAND_Y    3.0f
#define BUB_PERIOD_MS 3400.0f

// Slow, small, and mostly vertical.
//
// These are animals holding station against the current, not debris being carried by it:
// a creature drifting as far as the water moves reads as being swept away.
#define DRIFT_X        2.0f
#define DRIFT_Y        3.5f
#define DRIFT_PERIOD  52000.0f

static void StepDrifters() {
    if (g_vDrift.empty()) {
        return;
    }
    const float w = (float)(GetTickCount() % (DWORD)DRIFT_PERIOD)
                    / DRIFT_PERIOD * 6.2831853f;
    for (DRIFTER& d : g_vDrift) {
        const float s = w + d.fPhase;
        // The horizontal runs at a different rate from the vertical, so the path is a
        // slow figure rather than a straight diagonal slide back and forth.
        const int x = (int)lroundf(sinf(s * 0.7f) * DRIFT_X);
        const int y = (int)lroundf(cosf(s) * DRIFT_Y);
        if (x == d.nX && y == d.nY) {
            continue;
        }
        const int dx = x - d.nX;
        const int dy = y - d.nY;
        try {
            if (d.pSprite) {
                d.pSprite->InterLockedOffset(dx, dy, dx, dy);
            }
            // The same delta, so the light stays centred on the animal it comes from.
            for (int i = 0; i < d.nGlows; ++i) {
                if (d.pGlow[i]) {
                    d.pGlow[i]->InterLockedOffset(dx, dy, dx, dy);
                }
            }
            d.nX = x;
            d.nY = y;
        } catch (const _com_error&) {}
    }
}

void Lamps_Tick() {
    ApplyPendingPreview();
    SinkLampsBehindArt();
    StepDrifters();
}

void Lamps_Attach() {
    ATTACH_HOOK(CMapLoadable::MakeObj, CMapLoadable::MakeObj_hook);
}
