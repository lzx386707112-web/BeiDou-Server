// MCV video layer marker signature.
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
// The FIELD_EFFECT marker only marks *where* in the frame the video belongs. Which MCV plays is
// decided elsewhere by the compatibility module that starts the appropriate video channel.
//
// This header is deliberately free of Windows dependencies so the exact byte patterns can be
// asserted with a host compiler instead of only on a running client.

#ifndef BEIDOU_VELLUM_MARKER_SIGNATURE_H_
#define BEIDOU_VELLUM_MARKER_SIGNATURE_H_

#include <stdint.h>

namespace beidou {
namespace marker {

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

}  // namespace marker
}  // namespace beidou

#endif  // BEIDOU_VELLUM_MARKER_SIGNATURE_H_
