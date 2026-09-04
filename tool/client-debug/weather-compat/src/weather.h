#pragma once

// Server-authoritative day/night + weather.
//
// The client owns RENDERING only. It holds no opinion about what time it is:
// the world clock lives on the server and arrives as LP 0x373D, so every player
// sees the same sky at the same moment. There are no hotkeys.
//
// Between packets the client advances its own copy of the clock, so the server
// does not have to broadcast every in-game minute. A packet is a re-sync, not a
// tick: one on map entry and one whenever the sky state actually changes is
// enough, and a late or dropped packet only means the clock drifts by the
// scheduling error until the next one.
//
// WIRE (must match server/weather/WeatherPackets.java field for field):
//   short  opcode            0x373D
//   short  minuteOfDay       0..1439, in-game minutes past midnight
//   int    msPerGameMinute   real milliseconds per in-game minute
//   byte   sky               Weather::SKY_*
//   byte   flags             bit0 = snap (no fade), used on map entry
//   int    skyElapsedSec     how long this sky has held, capped at 3600
//   byte   tintR             the region's night colour, a multiply against the map art
//   byte   tintG
//   byte   tintB
//   short  rainbowSecsLeft   seconds of after-the-rain rainbow still owed
//   byte   palette           client-owned dusk/night palette id (optional)
//   int    skyElapsedMs      precise age for synchronized cosmetic lightning (optional)
//   int    skyToken          per-sky cosmetic seed (optional)
// Twenty-six bytes after the opcode. 0x373C is the reserved recv twin under the house
// even-request / odd-reply convention and is unused: the client never asks.
//
// See IMPLEMENTATION.md for the whole model.
namespace Weather {

// Profile ids. THE NUMBERING IS THE WIRE FORMAT and is owned by
// server/server/weather/WeatherProfile.java; the render parameters for
// each are one row of weather_profiles.inc, in the same order.
enum Sky : unsigned char {
    SKY_CLEAR    = 0,
    SKY_RAIN     = 1,
    SKY_SNOW     = 2,
    SKY_OVERCAST = 3,
    SKY_STORM    = 4,
    SKY_BLIZZARD = 5,
    SKY_LEAVES   = 6,
    SKY_BLOSSOM  = 7,
    SKY_SANDSTORM = 8,
    SKY_COUNT    = 9,
};

// Regional palette ids. The order is WeatherPalette.java's wire contract and indexes
// weather_palettes.inc. They are named here because ambience can vary by region while
// every RGB value remains client-owned.
enum PaletteId : unsigned char {
    PALETTE_EL_NATH = 0,
    PALETTE_RIEN,
    PALETTE_MUSHROOM_SHRINE,
    PALETTE_ELLINIA,
    PALETTE_PERION,
    PALETTE_KERNING_CITY,
    PALETTE_SHOWA,
    PALETTE_ORBIS,
    PALETTE_MU_LUNG,
    PALETTE_ARIANT,
    PALETTE_SLEEPYWOOD,
    PALETTE_AQUA_ROAD,
    PALETTE_LEAFRE,
    PALETTE_LUDIBRIUM,
    PALETTE_FLORINA,
    PALETTE_AMORIA,
    PALETTE_LITH_HARBOUR,
    PALETTE_MAGATIA,
    PALETTE_NAUTILUS,
    PALETTE_HENESYS,
    PALETTE_EREVE,
    PALETTE_TEMPLE_OF_TIME,
    PALETTE_ELLIN_FOREST,
    PALETTE_NEW_LEAF_CITY,
    PALETTE_FORMOSA,
    PALETTE_ZIPANGU,
    PALETTE_DEFAULT,
    PALETTE_COUNT,
};

// Which ambient loop a sky plays. Nodes in Sound/Weather.img, built by
// build_weather_sound.py.
enum Ambience : unsigned char {
    SND_NONE = 0,
    SND_RAIN = 1,   // rain, storm
    SND_WIND = 2,   // the windy skies: overcast, leaves, blossom
};

// What a sky looks like. See weather_profiles.inc for the table and the field meanings.
struct Profile {
    const wchar_t* sName;
    float          fCloud;
    float          fRain;
    int            nNativeItem;
    unsigned char  uR, uG, uB;
    float          fBoost;
    float          fFadeStep;
    unsigned char  uSound;      // Weather::Ambience
};

// The profile currently in force on this client, after the field filter. Always a
// valid row: an unrecognised id resolves to clear.
const Profile& CurrentProfile();

enum Flags : unsigned char {
    FLAG_SNAP   = 0x01,   // jump straight to the target instead of fading
    // A GM has frozen the clock. Stop advancing the local copy: otherwise it creeps
    // forward between packets and gets snapped back on every broadcast, which reads
    // as a stutter rather than as a held time.
    FLAG_FROZEN = 0x02,
    // Testing: hide the map's OWN sky and leave only the injected moon and starfields.
    // The map keeps its hills, trees and ground; only the sky itself goes.
    FLAG_BARESKY = 0x04,
    // Admin disabled the visual system. Hold a clear noon so every tint, lamp and
    // particle path returns to its stock visual identity until the next packet.
    FLAG_DISABLED = 0x08,
};

// Applied by the LP 0x373D handler. Safe to call from the receive thread: it only
// writes the shadow state, which Update() picks up on the next frame.
void SetWorldState(int nMinuteOfDay, int nMsPerGameMinute, unsigned char uSky,
                   unsigned char uFlags, int nSkyElapsedSec, int nRainbowSecsLeft,
                   unsigned char uTintR, unsigned char uTintG, unsigned char uTintB,
                   int nPaletteId, int nSkyElapsedMs, unsigned int uSkyToken);

// True once a world-state packet has been seen this session. Until then the client
// renders a plain noon: the tint is an identity multiply and the injected cloud and
// rain layers sit at alpha 0, so a server that does not speak 0x373D looks stock.
// NOTE the injection itself is NOT gated on this - see LoadMap_hook for why.
bool HasWorldState();

// True only while a weather-aware field owns live scenery/effect state. Frame hooks use
// this to avoid walking stale vectors on login and character-selection stages.
//
// It is true UNDERWATER as well: those fields are tinted and lit like any other. It is
// therefore the wrong gate for anything that falls out of the sky - see HasFallingSky().
bool IsFieldActive();

// True only where there is a sky for things to fall out of. IsFieldActive() also covers
// underwater fields, which are tinted and lit but have no air: rain, snow, sand, puddles,
// drifts, footprints and the slippery-footing physics write all belong behind THIS one.
bool HasFallingSky();

// 0.0 = full day, 1.0 = full night. Derived from the clock by NightLevel(), the
// single place the dusk/dawn curve is defined.
float NightLevel();

// Current in-game clock, for anything that wants to display it.
int MinuteOfDay();

// Current sky, after the field filter (a field with no sky reports SKY_CLEAR
// even while the world is raining).
unsigned char CurrentSky();

// How long the CURRENT sky has held, in seconds, as the server last reported it plus
// the time since. Ground accumulation seeds itself from this so a player walking into a
// map that has been snowing for ten minutes sees ten minutes of drifts rather than bare
// ground. Zero until a world-state packet has arrived.
int SkyElapsedSec();

/** Exact current sky age, for cosmetic events that must agree across clients. */
int SkyElapsedMillis();

/** Per-occurrence sky seed supplied by the server; zero on an older server. */
unsigned int SkyToken();

/** Current regional palette id, or DEFAULT while speaking to an older server. */
unsigned char PaletteId();

// Seconds of after-the-rain rainbow still owed over this map, 0 for none.
//
// Counted DOWN locally from the last report, the mirror of SkyElapsedSec counting up, so
// it keeps ticking between the once-a-minute broadcasts. The deadline itself is the
// server's: a player arriving part way through joins the rainbow already in progress
// rather than starting one of their own.
int RainbowSecsLeft();

}  // namespace Weather

// The night tint as one ARGB dword, with the darkness supplied by the caller instead of
// taken from the world clock. For anything that needs a LOCAL night level: lamps.cpp
// uses it to lift the tint back toward daylight in the pool of light around a lamp.
// Pass EffectiveNight() to get exactly what the map itself is rendering.
unsigned int Weather_TintColor(float fAlpha, float fNight);

// The darkness actually being rendered: the day/night curve floored by the active sky
// profile's boost. NOT the same as Weather::NightLevel(), which is the clock alone --
// a storm at noon renders dark while NightLevel() still says day. Anything that has to
// match what is on screen must read this.
float Weather_EffectiveNight();

// Routed from PacketDispatcher.cpp.
class CInPacket;
void Weather_HandleWorldState(CInPacket* pPacket);
