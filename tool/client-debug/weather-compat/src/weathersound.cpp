#include "pch.h"
#include "debug.h"
#include "weather.h"
#include "weatherfx.h"
#include "wvs/util.h"
#include "ztl/ztl.h"

// The ambient rain loop, played through the client's own CSoundMan so it follows the
// SOUND EFFECTS slider.
//
// WHY NOT RAW IWzSound. An earlier version owned the voice directly so it could track a
// different slider, and it never made a sound: IWzSound::Play only CREATES the voice.
// What starts it is put_playing, which PlaySE does immediately afterwards
// (Play(0) -> put_volume -> put_playing(bLoop ? -1: 1), 0x0043FDAB / 0x0043FDE0). With
// that missing, Play threw a _com_error every single frame, which the crash log caught
// as a repeating trace through WeatherFx::Update -> WeatherSound_Tick.
//
// Going through PlaySE fixes that by construction and is the right call anyway: it is
// the code path 24 stock call sites already use, it applies the SFX master for free
// (put_volume(m_nSEVolume * nVolume / 100)), and it owns the IWzSound cache so the
// megabyte is decoded once.
//
// The node is built by build_weather_sound.py: a seamless 60 s loop reusing the
// media-type header of an existing 44.1 kHz stereo 128 kbps node, with the ID3 tag and
// Xing frame stripped so the stream starts on a frame sync like every stock node does.
// Sound/Weather.img is a file stock v83 never had, which works because resman.cpp mounts
// Client/Data as a NameSpace#FileSystem over the packed archives.

// unsigned int __thiscall CSoundMan::PlaySE(const wchar_t* pPath, unsigned nVolume, int bLoop)
//   Handle ONLY when bLoop is set. Throws _com_error if the path does not resolve
//   (0x0043FD46 raises 0x80004003 on a null sound), and returns -1 rather than 0 when
//   CSoundMan::Init failed and there is no ResMan (0x0043FBB8).
#define ADDR_PLAYSE     0x0043FB25
// void __thiscall CSoundMan::StopSE(unsigned int nId, unsigned int nFadeDelayMs)
//   Erases the handle then MoveVolume(-volume, delay), so a non-zero delay is a fade.
#define ADDR_STOPSE     0x00773156
#define ADDR_SOUNDMAN   0x00BEBF94
#define OFF_SE_VOLUME   0x14      // the SFX master, 0..100

// One node per ambience id. Index by Weather::Ambience; SND_NONE has no node.
static const wchar_t* const kAmbienceUol[] = {
    nullptr,                        // SND_NONE
    L"Sound/Weather.img/rain",      // SND_RAIN
    L"Sound/Weather.img/wind",      // SND_WIND
};

// PlaySE's nVolume is 0..100 and is multiplied by the SFX master. It is applied once, at
// start: moving it afterwards would mean holding the IWzSoundState, and StopSE tears a
// voice down by dropping the map's reference and letting the release happen, so a
// retained pointer would strand a live-but-silent voice. The loop therefore starts at a
// fixed trim and STOPS with a fade, which StopSE gives for free.
#define RAIN_VOLUME     70
#define RAIN_FADE_MS    1500

// Start once the rain is visibly established, with hysteresis so a fade that stalls near
// the threshold cannot chatter the voice.
#define RAIN_ON_AT      0.35f
#define RAIN_OFF_AT     0.10f

namespace {

unsigned int  g_uHandle = 0;      // 0 = not playing
unsigned char g_uWanted = Weather::SND_NONE;
unsigned char g_uPlaying = Weather::SND_NONE;   // which node the live voice is
unsigned int  g_uFailedMask = 0;  // bit per ambience id that did not resolve
int           g_nLastSeVolume = -1;

void* SoundMan() {
    return *reinterpret_cast<void* volatile*>(ADDR_SOUNDMAN);
}

int SeMasterVolume() {
    void* p = SoundMan();
    if (!p) {
        return -1;
    }
    return *reinterpret_cast<int*>(static_cast<char*>(p) + OFF_SE_VOLUME);
}

void Start(unsigned char uAmbience) {
    void* p = SoundMan();
    if (!p || uAmbience == Weather::SND_NONE || uAmbience >= _countof(kAmbienceUol)) {
        return;
    }
    if (g_uFailedMask & (1u << uAmbience)) {
        return;
    }
    const wchar_t* sUol = kAmbienceUol[uAmbience];
    using PlaySE_t = unsigned int(__thiscall*)(void*, const wchar_t*, unsigned int, int);
    unsigned int uId = 0;
    try {
        uId = reinterpret_cast<PlaySE_t>(ADDR_PLAYSE)(p, sUol, RAIN_VOLUME, 1);
    } catch (const _com_error& e) {
        g_uFailedMask |= (1u << uAmbience);
        LOG_ONCE("weathersound: PlaySE(%ls) threw hr=0x%08X; that ambience will be silent",
                 sUol, (unsigned int)e.Error());
        return;
    } catch (...) {
        g_uFailedMask |= (1u << uAmbience);
        LOG_ONCE("weathersound: PlaySE(%ls) threw; that ambience will be silent", sUol);
        return;
    }
    if (uId == 0 || uId == 0xFFFFFFFFu) {
        g_uFailedMask |= (1u << uAmbience);
        LOG_ONCE("weathersound: PlaySE(%ls) returned no handle (0x%08X)", sUol, uId);
        return;
    }
    g_uHandle = uId;
    g_uPlaying = uAmbience;
    g_nLastSeVolume = SeMasterVolume();
    LOG_ONCE("weathersound: ambience %ls started, handle 0x%08X, SFX master %d",
             sUol, uId, g_nLastSeVolume);
}

void Stop(unsigned int uFadeMs) {
    if (!g_uHandle) {
        return;
    }
    void* p = SoundMan();
    if (p) {
        using StopSE_t = void(__thiscall*)(void*, unsigned int, unsigned int);
        try {
            reinterpret_cast<StopSE_t>(ADDR_STOPSE)(p, g_uHandle, uFadeMs);
        } catch (...) {}
    }
    g_uHandle = 0;
    g_uPlaying = Weather::SND_NONE;
}

}  // namespace


void WeatherSound_SetWanted(unsigned char uAmbience) {
    g_uWanted = uAmbience;
}

// Every frame from WeatherFx::Update, with the current rain fade level.
//
// Note the intensity gate applies only to RAIN. Wind belongs to skies where nothing is
// falling, so there is no fade level to follow; it simply plays while the profile asks
// for it.
void WeatherSound_Tick(float fIntensity) {
    const int nSe = SeMasterVolume();

    // A mute / unmute cycle permanently silences a long-lived loop, and it is not our
    // bug: CSoundMan::SetSEVolume (0x00772F77) rescales every live state by
    // vol * nNew / nOld and forces nOld = 1 when the old master was 0 (0x00773082), so a
    // state muted to 0 computes 0 * nNew / 1 = 0 and never recovers. Stock SEs are too
    // short to notice; a permanent ambient loop is not, so restart across the transition.
    if (g_uHandle && g_nLastSeVolume == 0 && nSe > 0) {
        Stop(0);
    }
    g_nLastSeVolume = nSe;

    unsigned char uWant = g_uWanted;
    // The rain gate is keyed on what is PLAYING as well as on what is wanted. Keying it
    // only on the wanted ambience meant a rain-to-wind change bypassed both the intensity
    // gate and the fade: the rain loop was cut with fade 0 and the wind loop started at
    // full volume on the same frame, several seconds before the rain sheets had finished
    // falling. Holding the rain until the visual has decayed past RAIN_OFF_AT makes the
    // audio follow the picture on every transition, not just on rain-to-nothing.
    if (uWant == Weather::SND_RAIN || g_uPlaying == Weather::SND_RAIN) {
        // Hysteresis, so a fade that stalls near the threshold cannot chatter the voice.
        const float fGate = (g_uPlaying == Weather::SND_RAIN) ? RAIN_OFF_AT : RAIN_ON_AT;
        if (g_uPlaying == Weather::SND_RAIN && fIntensity >= fGate) {
            uWant = Weather::SND_RAIN;      // still raining on screen; hold the loop
        } else if (uWant == Weather::SND_RAIN && fIntensity < fGate) {
            uWant = Weather::SND_NONE;      // not established yet
        }
    }

    if (uWant == g_uPlaying) {
        return;
    }
    // Any change of ambience is a stop then a start: one voice at a time, so swapping
    // rain for wind cannot leave both running. The stop always fades -- StopSE gives the
    // crossfade for free, and one voice is still torn down before the next is created.
    Stop(RAIN_FADE_MS);
    if (uWant != Weather::SND_NONE) {
        Start(uWant);
    }
}

// Nothing in the client stops a voice a mod started: CField::Close only tears down its
// own weather handle and the CSoundMan handle map is never flushed. Without this the rain
// would follow the player through a portal, a channel change and the cash shop.
void WeatherSound_Shutdown() {
    g_uWanted = Weather::SND_NONE;
    Stop(0);
}


// THE PUDDLE STEP SOUND WAS REMOVED. A one-shot PlaySE fired here as the player walked
// through standing water. The splash VISUALS are untouched; only the audio is gone, and the
// Sound/Weather.img/splash node it played is still in the bank, unreferenced.
//
// If it ever comes back it is four lines: PlaySE(SoundMan(), L"Sound/Weather.img/splash",
// 40, 0) wrapped in a try/catch that latches a static bool on failure. LATCH IT: an
// unresolvable ResMan path RAISES, and an unhandled _com_error out of the frame hook exits
// the process with no message, so a missing node must not be retried once per footstep.
// The rate limit belonged to the caller, not here.
