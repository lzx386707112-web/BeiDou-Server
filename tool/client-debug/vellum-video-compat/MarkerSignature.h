// MCV video layer marker signatures.
//
// 2026-09-28 (v7): the player-skill FIELD_EFFECT marker was never recognised by this module, so
// every video fell through to the Present fallback - the very end of the frame, above the mobs, the
// floating damage numbers and the UI. That is why the damage numbers disappeared the moment the
// video finally started playing: the decoder, the device and the channel were all fine, the video
// was simply composited in the wrong place.
//
// The marker is a single 7x5 canvas that the server's
// `PacketCreator.showEffect("customSkill/.../...VideoLayer")` node carries for 30000 ms, so the
// client keeps drawing that small sprite from the skill effect layer for the whole video. Its first
// four pixels are the signature below and the fifth pixel is unused there.
//
// Two families share the 7x5..8x8 size rule but not their signature:
//   * the FIELD_EFFECT marker only marks *where* in the frame the video belongs; which MCV plays is
//     decided elsewhere (the v69 core starts the player-skill channel from the skill id);
//   * the Root Abyss (Vellum) attack10/11 markers additionally select the MCV path through a code
//     packed into their fifth pixel.
//
// This header is deliberately free of Windows dependencies so the exact byte patterns can be
// asserted with a host compiler instead of only on a running client.

#ifndef BEIDOU_VELLUM_MARKER_SIGNATURE_H_
#define BEIDOU_VELLUM_MARKER_SIGNATURE_H_

#include <stdint.h>

namespace beidou {
namespace marker {

enum Kind : int {
    kNoMarker = 0,
    kFieldEffect = 1,
    kVellumScene = 2,
};

struct Hit {
    int kind;
    int code;
};

// The Root Abyss attack10/11 code lives in the fifth pixel, not in the signature family.
constexpr int kVellumAttack10Code = 5;
constexpr int kVellumAttack11Code = 6;

// FIELD_EFFECT marker, canonical ARGB pixels:
//     (17, 34, 51, 255) (68, 85, 102, 255) (119, 136, 153, 255) (170, 187, 204, 255)
// A4R4G4B4 keeps the high nibble of every channel, which turns them into
//     0xF123 0xF456 0xF789 0xFABC
inline bool MatchesFieldEffectA4R4G4B4(const uint16_t* pixels) {
    return pixels[0] == 0xF123 && pixels[1] == 0xF456 &&
        pixels[2] == 0xF789 && pixels[3] == 0xFABC;
}

inline bool MatchesFieldEffectA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    const uint32_t alphaMask = ignoreAlpha ? 0x00000000u : 0xFF000000u;
    const uint32_t colorMask = ignoreAlpha ? 0x00FFFFFFu : 0xFFFFFFFFu;
    return (pixels[0] & colorMask) == (alphaMask | 0x00112233u) &&
        (pixels[1] & colorMask) == (alphaMask | 0x00445566u) &&
        (pixels[2] & colorMask) == (alphaMask | 0x00778899u) &&
        (pixels[3] & colorMask) == (alphaMask | 0x00AABBCCu);
}

// Root Abyss (Vellum) marker, canonical ARGB pixels:
//     (51, 85, 119, 255) (102, 136, 153, 255) (170, 187, 204, 255) (221, 238, 255, 255)
// and a fifth pixel whose red channel is `code * 17`. `0x00AABBCC` appears in both families, so
// only the complete four pixel comparison may decide - never a single pixel.
inline bool MatchesVellumA4R4G4B4(const uint16_t* pixels) {
    return pixels[0] == 0xF357 && pixels[1] == 0xF689 &&
        pixels[2] == 0xFABC && pixels[3] == 0xFDEF;
}

inline bool MatchesVellumA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    const uint32_t alphaMask = ignoreAlpha ? 0x00000000u : 0xFF000000u;
    const uint32_t colorMask = ignoreAlpha ? 0x00FFFFFFu : 0xFFFFFFFFu;
    return (pixels[0] & colorMask) == (alphaMask | 0x00335577u) &&
        (pixels[1] & colorMask) == (alphaMask | 0x00668899u) &&
        (pixels[2] & colorMask) == (alphaMask | 0x00AABBCCu) &&
        (pixels[3] & colorMask) == (alphaMask | 0x00DDEEFFu);
}

// Returns 0 for "not an attack10/11 marker"; the caller turns a non zero code into kVellumScene.
inline int VellumCodeFromA4R4G4B4(const uint16_t* pixels) {
    if (!MatchesVellumA4R4G4B4(pixels)) return 0;
    const int code = (pixels[4] >> 8) & 0x0F;
    return code == kVellumAttack10Code || code == kVellumAttack11Code ? code : 0;
}

inline int VellumCodeFromA8R8G8B8(const uint32_t* pixels, bool ignoreAlpha) {
    if (!MatchesVellumA8R8G8B8(pixels, ignoreAlpha)) return 0;
    const int red = static_cast<int>((pixels[4] >> 16) & 0xFF);
    const int code = red / 17;
    if (red != code * 17) return 0;
    return code == kVellumAttack10Code || code == kVellumAttack11Code ? code : 0;
}

}  // namespace marker
}  // namespace beidou

#endif  // BEIDOU_VELLUM_MARKER_SIGNATURE_H_
