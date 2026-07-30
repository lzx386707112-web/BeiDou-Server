#include "McvFormat.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <limits>

namespace bdv {
namespace {

constexpr uint32_t kFourCcXor = 0xa5a5a5a5u;
constexpr size_t kFixedHeaderSize = 36;
constexpr uint32_t kMaxFrames = 100000;
constexpr uint16_t kMaxDimension = 8192;

void SetError(char* error, size_t capacity, const char* format, ...) {
    if (error == nullptr || capacity == 0) {
        return;
    }
    va_list args;
    va_start(args, format);
    vsnprintf(error, capacity, format, args);
    va_end(args);
    error[capacity - 1] = '\0';
}

bool HasBytes(size_t position, size_t count, size_t size) {
    return position <= size && count <= size - position;
}

uint16_t Read16(const uint8_t* data) {
    return static_cast<uint16_t>(data[0]) |
           static_cast<uint16_t>(static_cast<uint16_t>(data[1]) << 8);
}

uint32_t Read32(const uint8_t* data) {
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
}

uint64_t Read64(const uint8_t* data) {
    return static_cast<uint64_t>(Read32(data)) |
           (static_cast<uint64_t>(Read32(data + 4)) << 32);
}

bool Multiply(uint64_t a, uint64_t b, uint64_t* result) {
    if (a != 0 && b > std::numeric_limits<uint64_t>::max() / a) {
        return false;
    }
    *result = a * b;
    return true;
}

bool Add(uint64_t a, uint64_t b, uint64_t* result) {
    if (b > std::numeric_limits<uint64_t>::max() - a) {
        return false;
    }
    *result = a + b;
    return true;
}

}  // namespace

const char* FourCcName(uint32_t fourCc) {
    if (fourCc == kVp8FourCc) {
        return "VP80";
    }
    if (fourCc == kVp9FourCc) {
        return "VP90";
    }
    return "unknown";
}

bool ParseMcv(
    const uint8_t* data,
    size_t size,
    McvVideo* output,
    char* error,
    size_t errorCapacity) {
    if (output == nullptr) {
        SetError(error, errorCapacity, "output is null");
        return false;
    }
    *output = McvVideo{};
    if (data == nullptr || size < kFixedHeaderSize) {
        SetError(error, errorCapacity, "MCV payload is shorter than %u bytes", static_cast<unsigned>(kFixedHeaderSize));
        return false;
    }
    if (memcmp(data, "MCV0", 4) != 0) {
        SetError(error, errorCapacity, "invalid MCV signature");
        return false;
    }

    const uint16_t headerLength = Read16(data + 6);
    const uint32_t fourCc = Read32(data + 8) ^ kFourCcXor;
    const uint16_t width = Read16(data + 12);
    const uint16_t height = Read16(data + 14);
    const uint32_t frameCount = Read32(data + 16);
    const uint8_t flags = data[20];
    const uint64_t delayUnit = Read64(data + 24);
    const uint32_t defaultDelay = Read32(data + 32);

    if (headerLength < kFixedHeaderSize || headerLength > size) {
        SetError(error, errorCapacity, "invalid MCV header length %u", headerLength);
        return false;
    }
    if (fourCc != kVp8FourCc && fourCc != kVp9FourCc) {
        SetError(error, errorCapacity, "unsupported MCV codec 0x%08x", fourCc);
        return false;
    }
    if (width == 0 || height == 0 || width > kMaxDimension || height > kMaxDimension) {
        SetError(error, errorCapacity, "invalid MCV dimensions %ux%u", width, height);
        return false;
    }
    if (frameCount == 0 || frameCount > kMaxFrames) {
        SetError(error, errorCapacity, "invalid MCV frame count %u", frameCount);
        return false;
    }
    if ((flags & ~(kAlphaMap | kPerFrameDelay | kPerFrameTimeline)) != 0) {
        SetError(error, errorCapacity, "unsupported MCV flags 0x%02x", flags);
        return false;
    }

    McvVideo parsed;
    parsed.fourCc = fourCc;
    parsed.width = width;
    parsed.height = height;
    parsed.flags = flags;
    parsed.frames.resize(frameCount);

    size_t position = headerLength;
    const size_t frameTableBytes = static_cast<size_t>(frameCount) * 8;
    if (!HasBytes(position, frameTableBytes, size)) {
        SetError(error, errorCapacity, "truncated MCV color frame table");
        return false;
    }
    for (uint32_t index = 0; index < frameCount; ++index) {
        parsed.frames[index].colorOffset = Read32(data + position);
        parsed.frames[index].colorSize = Read32(data + position + 4);
        position += 8;
    }

    if ((flags & kAlphaMap) != 0) {
        if (!HasBytes(position, frameTableBytes, size)) {
            SetError(error, errorCapacity, "truncated MCV alpha frame table");
            return false;
        }
        for (uint32_t index = 0; index < frameCount; ++index) {
            parsed.frames[index].alphaOffset = Read32(data + position);
            parsed.frames[index].alphaSize = Read32(data + position + 4);
            position += 8;
        }
    }

    if ((flags & kPerFrameDelay) != 0) {
        const size_t delayBytes = static_cast<size_t>(frameCount) * 4;
        if (!HasBytes(position, delayBytes, size)) {
            SetError(error, errorCapacity, "truncated MCV delay table");
            return false;
        }
        for (uint32_t index = 0; index < frameCount; ++index) {
            if (!Multiply(Read32(data + position), delayUnit, &parsed.frames[index].delayNanoseconds)) {
                SetError(error, errorCapacity, "MCV frame delay overflow at %u", index);
                return false;
            }
            position += 4;
        }
    } else {
        uint64_t delay = 0;
        if (!Multiply(defaultDelay, delayUnit, &delay)) {
            SetError(error, errorCapacity, "MCV default delay overflow");
            return false;
        }
        for (McvFrame& frame : parsed.frames) {
            frame.delayNanoseconds = delay;
        }
    }

    if ((flags & kPerFrameTimeline) != 0) {
        const size_t timelineBytes = static_cast<size_t>(frameCount) * 8;
        if (!HasBytes(position, timelineBytes, size)) {
            SetError(error, errorCapacity, "truncated MCV timeline table");
            return false;
        }
        for (uint32_t index = 0; index < frameCount; ++index) {
            if (!Multiply(Read64(data + position), delayUnit, &parsed.frames[index].startNanoseconds)) {
                SetError(error, errorCapacity, "MCV frame timeline overflow at %u", index);
                return false;
            }
            position += 8;
        }
    } else {
        uint64_t start = 0;
        for (uint32_t index = 0; index < frameCount; ++index) {
            parsed.frames[index].startNanoseconds = start;
            if (!Add(start, parsed.frames[index].delayNanoseconds, &start)) {
                SetError(error, errorCapacity, "MCV timeline overflow at %u", index);
                return false;
            }
        }
    }

    const uint64_t dataStart = position;
    if (dataStart > std::numeric_limits<uint32_t>::max()) {
        SetError(error, errorCapacity, "MCV data offset exceeds 32-bit format limit");
        return false;
    }
    uint64_t duration = 0;
    for (uint32_t index = 0; index < frameCount; ++index) {
        McvFrame& frame = parsed.frames[index];
        uint64_t absoluteOffset = 0;
        if (!Add(dataStart, frame.colorOffset, &absoluteOffset) ||
            absoluteOffset > std::numeric_limits<uint32_t>::max() ||
            absoluteOffset > size || frame.colorSize > size - absoluteOffset) {
            SetError(error, errorCapacity, "MCV color payload is out of bounds at frame %u", index);
            return false;
        }
        frame.colorOffset = static_cast<uint32_t>(absoluteOffset);

        if (frame.alphaSize != 0) {
            if (!Add(dataStart, frame.alphaOffset, &absoluteOffset) ||
                absoluteOffset > std::numeric_limits<uint32_t>::max() ||
                absoluteOffset > size || frame.alphaSize > size - absoluteOffset) {
                SetError(error, errorCapacity, "MCV alpha payload is out of bounds at frame %u", index);
                return false;
            }
            frame.alphaOffset = static_cast<uint32_t>(absoluteOffset);
        }

        uint64_t end = 0;
        if (!Add(frame.startNanoseconds, frame.delayNanoseconds, &end)) {
            SetError(error, errorCapacity, "MCV duration overflow at frame %u", index);
            return false;
        }
        if (end > duration) {
            duration = end;
        }
    }
    parsed.durationNanoseconds = duration;
    *output = parsed;
    if (error != nullptr && errorCapacity != 0) {
        error[0] = '\0';
    }
    return true;
}

}  // namespace bdv
