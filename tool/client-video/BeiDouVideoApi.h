#pragma once

#include <stdint.h>

#ifdef _WIN32
#define BDV_CALL __stdcall
#ifdef BDV_BUILD
#define BDV_API extern "C" __declspec(dllexport)
#else
#define BDV_API extern "C" __declspec(dllimport)
#endif
#else
#define BDV_CALL
#define BDV_API extern "C"
#endif

struct BdvStatus {
    uint32_t structureSize;
    uint32_t state;
    uint32_t width;
    uint32_t height;
    uint32_t frameCount;
    uint32_t decodedFrames;
    uint32_t displayedFrames;
    uint32_t droppedFrames;
    uint64_t durationMilliseconds;
    uint64_t positionMilliseconds;
};

enum BdvState : uint32_t {
    BDV_STATE_IDLE = 0,
    BDV_STATE_DECODING = 1,
    BDV_STATE_PLAYING = 2,
    BDV_STATE_FINISHED = 3,
    BDV_STATE_ERROR = 4,
};

BDV_API int BDV_CALL BDV_AttachDevice(void* direct3DDevice8);
BDV_API void BDV_CALL BDV_DetachDevice();
BDV_API int BDV_CALL BDV_PlayFile(const char* path);
BDV_API void BDV_CALL BDV_Stop();
BDV_API void BDV_CALL BDV_Render();
BDV_API int BDV_CALL BDV_GetStatus(BdvStatus* status);
BDV_API void BDV_CALL BDV_GetLastError(char* buffer, uint32_t capacity);

