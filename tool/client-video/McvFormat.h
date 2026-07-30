#pragma once

#include <stddef.h>
#include <stdint.h>

#include <vector>

namespace bdv {

constexpr uint32_t MakeFourCc(char a, char b, char c, char d) {
    return static_cast<uint32_t>(static_cast<unsigned char>(a)) |
           (static_cast<uint32_t>(static_cast<unsigned char>(b)) << 8) |
           (static_cast<uint32_t>(static_cast<unsigned char>(c)) << 16) |
           (static_cast<uint32_t>(static_cast<unsigned char>(d)) << 24);
}

constexpr uint32_t kVp8FourCc = MakeFourCc('V', 'P', '8', '0');
constexpr uint32_t kVp9FourCc = MakeFourCc('V', 'P', '9', '0');
constexpr uint8_t kAlphaMap = 1;
constexpr uint8_t kPerFrameDelay = 2;
constexpr uint8_t kPerFrameTimeline = 4;

struct McvFrame {
    uint32_t colorOffset = 0;
    uint32_t colorSize = 0;
    uint32_t alphaOffset = 0;
    uint32_t alphaSize = 0;
    uint64_t delayNanoseconds = 0;
    uint64_t startNanoseconds = 0;
};

struct McvVideo {
    uint32_t fourCc = 0;
    uint16_t width = 0;
    uint16_t height = 0;
    uint8_t flags = 0;
    uint64_t durationNanoseconds = 0;
    std::vector<McvFrame> frames;
};

bool ParseMcv(
    const uint8_t* data,
    size_t size,
    McvVideo* output,
    char* error,
    size_t errorCapacity);

const char* FourCcName(uint32_t fourCc);

}  // namespace bdv

