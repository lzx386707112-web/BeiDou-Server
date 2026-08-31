#define BDV_BUILD
#include "BeiDouVideoApi.h"
#include "McvFormat.h"

#include <windows.h>
#include <d3d8.h>

#include <vpx/vp8dx.h>
#include <vpx/vpx_decoder.h>
#include <vpx/vpx_image.h>

#include <algorithm>
#include <atomic>
#include <new>
#include <vector>

namespace {

constexpr int kQueueSize = 3;
constexpr DWORD kWorkerPollMilliseconds = 2;
constexpr uint32_t kBgraBytesPerPixel = 4;

struct MappedFile {
    HANDLE file = INVALID_HANDLE_VALUE;
    HANDLE mapping = nullptr;
    const uint8_t* data = nullptr;
    size_t size = 0;
};

struct FrameSlot {
    std::vector<uint8_t> bgra;
    uint64_t startNanoseconds = 0;
    uint32_t frameIndex = 0;
    bool ready = false;
};

struct Vertex {
    float x;
    float y;
    float z;
    float rhw;
    float u;
    float v;
};

class Player {
public:
    explicit Player(const char* channelName) : channelName_(channelName) {
        InitializeCriticalSection(&lock_);
        QueryPerformanceFrequency(&performanceFrequency_);
        stopEvent_ = CreateEventA(nullptr, TRUE, FALSE, nullptr);
        SetError("not initialized");
    }

    ~Player() {
        Stop();
        DetachDevice();
        if (stopEvent_ != nullptr) {
            CloseHandle(stopEvent_);
        }
        DeleteCriticalSection(&lock_);
    }

    bool AttachDevice(void* value) {
        auto* device = static_cast<IDirect3DDevice8*>(value);
        if (device == nullptr) {
            SetError("D3D8 device is null");
            return false;
        }
        EnterCriticalSection(&lock_);
        ReleaseTexturesLocked();
        if (device_ != nullptr) {
            device_->Release();
        }
        device_ = device;
        device_->AddRef();
        LeaveCriticalSection(&lock_);
        Log("device attached");
        return true;
    }

    void DetachDevice() {
        EnterCriticalSection(&lock_);
        ReleaseTexturesLocked();
        if (device_ != nullptr) {
            device_->Release();
            device_ = nullptr;
        }
        LeaveCriticalSection(&lock_);
    }

    void* GetAttachedDevice() {
        EnterCriticalSection(&lock_);
        void* device = device_;
        LeaveCriticalSection(&lock_);
        return device;
    }

    bool Play(const char* path) {
        if (path == nullptr || path[0] == '\0') {
            SetError("video path is empty");
            return false;
        }
        Stop();

        EnterCriticalSection(&lock_);
        const bool deviceAttached = device_ != nullptr;
        LeaveCriticalSection(&lock_);
        if (!deviceAttached) {
            SetError("D3D8 device is not attached");
            return false;
        }

        MappedFile mapped;
        if (!OpenMappedFile(path, &mapped)) {
            return false;
        }
        bdv::McvVideo video;
        char parseError[256] = {};
        if (!bdv::ParseMcv(mapped.data, mapped.size, &video, parseError, sizeof(parseError))) {
            CloseMappedFile(&mapped);
            SetError(parseError);
            return false;
        }

        EnterCriticalSection(&lock_);
        mapped_ = mapped;
        video_ = video;
        decodedFrames_ = 0;
        displayedFrames_ = 0;
        droppedFrames_ = 0;
        decodeComplete_ = false;
        playbackStarted_ = false;
        currentFrameIndex_ = static_cast<uint32_t>(-1);
        state_.store(BDV_STATE_DECODING, std::memory_order_release);
        for (FrameSlot& slot : slots_) {
            slot.ready = false;
            slot.bgra.clear();
        }
        ResetEvent(stopEvent_);
        worker_ = CreateThread(nullptr, 0, &WorkerEntry, this, 0, nullptr);
        const bool started = worker_ != nullptr;
        LeaveCriticalSection(&lock_);

        if (!started) {
            SetError("failed to create decoder thread");
            Stop();
            return false;
        }
        Log("playback queued");
        return true;
    }

    void Stop() {
        HANDLE worker = nullptr;
        EnterCriticalSection(&lock_);
        worker = worker_;
        if (worker != nullptr) {
            SetEvent(stopEvent_);
        }
        LeaveCriticalSection(&lock_);

        if (worker != nullptr) {
            WaitForSingleObject(worker, INFINITE);
        }

        EnterCriticalSection(&lock_);
        if (worker_ != nullptr) {
            CloseHandle(worker_);
            worker_ = nullptr;
        }
        for (FrameSlot& slot : slots_) {
            slot.ready = false;
            slot.bgra.clear();
        }
        CloseMappedFile(&mapped_);
        video_ = bdv::McvVideo{};
        ReleaseTexturesLocked();
        playbackStarted_ = false;
        decodeComplete_ = false;
        state_.store(BDV_STATE_IDLE, std::memory_order_release);
        LeaveCriticalSection(&lock_);
    }

    void Render() {
        EnterCriticalSection(&lock_);
        if (device_ == nullptr || !playbackStarted_) {
            LeaveCriticalSection(&lock_);
            return;
        }

        const uint64_t elapsed = ElapsedNanosecondsLocked();
        if (decodeComplete_ && elapsed >= video_.durationNanoseconds) {
            for (FrameSlot& slot : slots_) {
                slot.ready = false;
                slot.bgra.clear();
            }
            ReleaseTexturesLocked();
            state_.store(BDV_STATE_FINISHED, std::memory_order_release);
            LeaveCriticalSection(&lock_);
            return;
        }

        int selected = -1;
        uint64_t selectedStart = 0;
        for (int index = 0; index < kQueueSize; ++index) {
            FrameSlot& slot = slots_[index];
            if (slot.ready && slot.startNanoseconds <= elapsed &&
                (selected < 0 || slot.startNanoseconds >= selectedStart)) {
                selected = index;
                selectedStart = slot.startNanoseconds;
            }
        }

        if (selected >= 0) {
            FrameSlot& frame = slots_[selected];
            for (FrameSlot& slot : slots_) {
                if (slot.ready && slot.startNanoseconds < frame.startNanoseconds) {
                    slot.ready = false;
                    ++droppedFrames_;
                }
            }
            if (UploadFrameLocked(frame)) {
                frame.ready = false;
                currentFrameIndex_ = frame.frameIndex;
                ++displayedFrames_;
            }
        }

        if (currentTexture_ != nullptr) {
            DrawTextureLocked();
        }
        LeaveCriticalSection(&lock_);
    }

    bool GetStatus(BdvStatus* status) {
        if (status == nullptr || status->structureSize < sizeof(BdvStatus)) {
            return false;
        }
        EnterCriticalSection(&lock_);
        status->state = state_.load(std::memory_order_acquire);
        status->width = video_.width;
        status->height = video_.height;
        status->frameCount = static_cast<uint32_t>(video_.frames.size());
        status->decodedFrames = decodedFrames_;
        status->displayedFrames = displayedFrames_;
        status->droppedFrames = droppedFrames_;
        status->durationMilliseconds = video_.durationNanoseconds / 1000000u;
        status->positionMilliseconds = playbackStarted_ ? ElapsedNanosecondsLocked() / 1000000u : 0;
        LeaveCriticalSection(&lock_);
        return true;
    }

    void GetLastErrorText(char* buffer, uint32_t capacity) {
        if (buffer == nullptr || capacity == 0) {
            return;
        }
        EnterCriticalSection(&lock_);
        lstrcpynA(buffer, lastError_, static_cast<int>(capacity));
        LeaveCriticalSection(&lock_);
    }

private:
    static DWORD WINAPI WorkerEntry(LPVOID value) {
        static_cast<Player*>(value)->DecodeWorker();
        return 0;
    }

    bool OpenMappedFile(const char* path, MappedFile* output) {
        output->file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (output->file == INVALID_HANDLE_VALUE) {
            char message[512] = {};
            wsprintfA(message, "failed to open MCV file: %s (GetLastError=%lu)", path, GetLastError());
            SetError(message);
            return false;
        }
        LARGE_INTEGER size = {};
        if (!GetFileSizeEx(output->file, &size) || size.QuadPart <= 0 ||
            static_cast<uint64_t>(size.QuadPart) > static_cast<uint64_t>(SIZE_MAX)) {
            CloseMappedFile(output);
            SetError("invalid MCV file size");
            return false;
        }
        output->size = static_cast<size_t>(size.QuadPart);
        output->mapping = CreateFileMappingA(output->file, nullptr, PAGE_READONLY, 0, 0, nullptr);
        if (output->mapping == nullptr) {
            CloseMappedFile(output);
            SetError("failed to map MCV file");
            return false;
        }
        output->data = static_cast<const uint8_t*>(MapViewOfFile(output->mapping, FILE_MAP_READ, 0, 0, 0));
        if (output->data == nullptr) {
            CloseMappedFile(output);
            SetError("failed to map MCV view");
            return false;
        }
        return true;
    }

    static void CloseMappedFile(MappedFile* mapped) {
        if (mapped->data != nullptr) {
            UnmapViewOfFile(mapped->data);
        }
        if (mapped->mapping != nullptr) {
            CloseHandle(mapped->mapping);
        }
        if (mapped->file != INVALID_HANDLE_VALUE) {
            CloseHandle(mapped->file);
        }
        *mapped = MappedFile{};
    }

    void DecodeWorker() {
        vpx_codec_ctx_t colorDecoder = {};
        vpx_codec_ctx_t alphaDecoder = {};
        bool colorReady = false;
        bool alphaReady = false;

        const vpx_codec_iface_t* codec = video_.fourCc == bdv::kVp8FourCc ? vpx_codec_vp8_dx() : vpx_codec_vp9_dx();
        vpx_codec_dec_cfg_t configuration = {};
        configuration.threads = 2;
        configuration.w = video_.width;
        configuration.h = video_.height;
        if (vpx_codec_dec_init(&colorDecoder, codec, &configuration, 0) != VPX_CODEC_OK) {
            WorkerError("failed to initialize color VPX decoder");
            return;
        }
        colorReady = true;
        if ((video_.flags & bdv::kAlphaMap) != 0) {
            if (vpx_codec_dec_init(&alphaDecoder, codec, &configuration, 0) != VPX_CODEC_OK) {
                vpx_codec_destroy(&colorDecoder);
                WorkerError("failed to initialize alpha VPX decoder");
                return;
            }
            alphaReady = true;
        }

        for (uint32_t index = 0; index < video_.frames.size(); ++index) {
            if (WaitForSingleObject(stopEvent_, 0) == WAIT_OBJECT_0) {
                break;
            }
            const bdv::McvFrame& frame = video_.frames[index];
            vpx_image_t* color = DecodeFrame(
                &colorDecoder,
                mapped_.data + frame.colorOffset,
                frame.colorSize);
            if (color == nullptr) {
                WorkerError("VPX color frame decode failed");
                break;
            }

            vpx_image_t* alpha = nullptr;
            if (frame.alphaSize != 0) {
                alpha = DecodeFrame(
                    &alphaDecoder,
                    mapped_.data + frame.alphaOffset,
                    frame.alphaSize);
                if (alpha == nullptr) {
                    WorkerError("VPX alpha frame decode failed");
                    break;
                }
            }

            std::vector<uint8_t> pixels;
            if (!ConvertFrame(color, alpha, video_.width, video_.height, &pixels)) {
                WorkerError("unsupported VPX output pixel format");
                break;
            }

            bool queued = false;
            while (!queued && WaitForSingleObject(stopEvent_, 0) != WAIT_OBJECT_0) {
                EnterCriticalSection(&lock_);
                for (FrameSlot& slot : slots_) {
                    if (!slot.ready) {
                        slot.bgra.swap(pixels);
                        slot.startNanoseconds = frame.startNanoseconds;
                        slot.frameIndex = index;
                        slot.ready = true;
                        ++decodedFrames_;
                        if (!playbackStarted_) {
                            QueryPerformanceCounter(&playbackStart_);
                            playbackStarted_ = true;
                            state_.store(BDV_STATE_PLAYING, std::memory_order_release);
                        }
                        queued = true;
                        break;
                    }
                }
                LeaveCriticalSection(&lock_);
                if (!queued) {
                    WaitForSingleObject(stopEvent_, kWorkerPollMilliseconds);
                }
            }
        }

        if (alphaReady) {
            vpx_codec_destroy(&alphaDecoder);
        }
        if (colorReady) {
            vpx_codec_destroy(&colorDecoder);
        }
        EnterCriticalSection(&lock_);
        decodeComplete_ = true;
        LeaveCriticalSection(&lock_);
    }

    static vpx_image_t* DecodeFrame(vpx_codec_ctx_t* decoder, const uint8_t* data, uint32_t size) {
        if (vpx_codec_decode(decoder, data, size, nullptr, 0) != VPX_CODEC_OK) {
            return nullptr;
        }
        vpx_codec_iter_t iterator = nullptr;
        return vpx_codec_get_frame(decoder, &iterator);
    }

    static bool IsPlanar420(vpx_img_fmt_t format) {
        const vpx_img_fmt_t base = static_cast<vpx_img_fmt_t>(format & ~VPX_IMG_FMT_HIGHBITDEPTH);
        return base == VPX_IMG_FMT_I420 || base == VPX_IMG_FMT_YV12;
    }

    static uint8_t Clamp(int value) {
        if (value < 0) {
            return 0;
        }
        if (value > 255) {
            return 255;
        }
        return static_cast<uint8_t>(value);
    }

    static void YuvToRgb(int y, int u, int v, uint8_t* red, uint8_t* green, uint8_t* blue) {
        const int c = std::max(0, y - 16);
        const int d = u - 128;
        const int e = v - 128;
        *red = Clamp((298 * c + 409 * e + 128) >> 8);
        *green = Clamp((298 * c - 100 * d - 208 * e + 128) >> 8);
        *blue = Clamp((298 * c + 516 * d + 128) >> 8);
    }

    static bool ConvertFrame(
        const vpx_image_t* color,
        const vpx_image_t* alpha,
        uint32_t width,
        uint32_t height,
        std::vector<uint8_t>* output) {
        if (color == nullptr || color->d_w != width || color->d_h != height || !IsPlanar420(color->fmt)) {
            return false;
        }
        if (alpha != nullptr && (alpha->d_w != width || alpha->d_h != height || !IsPlanar420(alpha->fmt))) {
            return false;
        }
        output->resize(static_cast<size_t>(width) * height * kBgraBytesPerPixel);
        const bool colorYv12 = (color->fmt & ~VPX_IMG_FMT_HIGHBITDEPTH) == VPX_IMG_FMT_YV12;
        const int colorUPlane = colorYv12 ? VPX_PLANE_V : VPX_PLANE_U;
        const int colorVPlane = colorYv12 ? VPX_PLANE_U : VPX_PLANE_V;
        const bool alphaYv12 = alpha != nullptr &&
            (alpha->fmt & ~VPX_IMG_FMT_HIGHBITDEPTH) == VPX_IMG_FMT_YV12;
        const int alphaUPlane = alphaYv12 ? VPX_PLANE_V : VPX_PLANE_U;
        const int alphaVPlane = alphaYv12 ? VPX_PLANE_U : VPX_PLANE_V;

        for (uint32_t y = 0; y < height; ++y) {
            const uint8_t* colorY = color->planes[VPX_PLANE_Y] + y * color->stride[VPX_PLANE_Y];
            const uint8_t* colorU = color->planes[colorUPlane] + (y / 2) * color->stride[colorUPlane];
            const uint8_t* colorV = color->planes[colorVPlane] + (y / 2) * color->stride[colorVPlane];
            const uint8_t* alphaY = alpha == nullptr ? nullptr : alpha->planes[VPX_PLANE_Y] + y * alpha->stride[VPX_PLANE_Y];
            const uint8_t* alphaU = alpha == nullptr ? nullptr : alpha->planes[alphaUPlane] + (y / 2) * alpha->stride[alphaUPlane];
            const uint8_t* alphaV = alpha == nullptr ? nullptr : alpha->planes[alphaVPlane] + (y / 2) * alpha->stride[alphaVPlane];
            uint8_t* destination = output->data() + static_cast<size_t>(y) * width * kBgraBytesPerPixel;
            for (uint32_t x = 0; x < width; ++x) {
                uint8_t red = 0;
                uint8_t green = 0;
                uint8_t blue = 0;
                YuvToRgb(colorY[x], colorU[x / 2], colorV[x / 2], &red, &green, &blue);
                uint8_t opacity = 255;
                if (alpha != nullptr) {
                    uint8_t ignoredGreen = 0;
                    uint8_t ignoredBlue = 0;
                    YuvToRgb(alphaY[x], alphaU[x / 2], alphaV[x / 2], &opacity, &ignoredGreen, &ignoredBlue);
                }
                destination[x * 4] = blue;
                destination[x * 4 + 1] = green;
                destination[x * 4 + 2] = red;
                destination[x * 4 + 3] = opacity;
            }
        }
        return true;
    }

    bool UploadFrameLocked(const FrameSlot& frame) {
        if (!EnsureTexturesLocked()) {
            return false;
        }
        currentTextureIndex_ = (currentTextureIndex_ + 1) % 2;
        IDirect3DTexture8* texture = textures_[currentTextureIndex_];
        D3DLOCKED_RECT locked = {};
        if (FAILED(texture->LockRect(0, &locked, nullptr, 0))) {
            SetErrorLocked("failed to lock D3D8 video texture");
            return false;
        }
        const size_t sourcePitch = static_cast<size_t>(video_.width) * kBgraBytesPerPixel;
        for (uint32_t y = 0; y < video_.height; ++y) {
            memcpy(
                static_cast<uint8_t*>(locked.pBits) + static_cast<size_t>(y) * locked.Pitch,
                frame.bgra.data() + static_cast<size_t>(y) * sourcePitch,
                sourcePitch);
        }
        texture->UnlockRect(0);
        currentTexture_ = texture;
        return true;
    }

    bool EnsureTexturesLocked() {
        if (textures_[0] != nullptr && textureWidth_ == video_.width && textureHeight_ == video_.height) {
            return true;
        }
        ReleaseTexturesLocked();
        for (IDirect3DTexture8*& texture : textures_) {
            const HRESULT result = device_->CreateTexture(
                video_.width,
                video_.height,
                1,
                0,
                D3DFMT_A8R8G8B8,
                D3DPOOL_MANAGED,
                &texture);
            if (FAILED(result)) {
                ReleaseTexturesLocked();
                SetErrorLocked("failed to create D3D8 video texture");
                return false;
            }
        }
        textureWidth_ = video_.width;
        textureHeight_ = video_.height;
        currentTextureIndex_ = 0;
        return true;
    }

    void DrawTextureLocked() {
        D3DVIEWPORT8 originalViewport = {};
        if (FAILED(device_->GetViewport(&originalViewport))) {
            return;
        }
        IDirect3DSurface8* renderTarget = nullptr;
        if (FAILED(device_->GetRenderTarget(&renderTarget)) || renderTarget == nullptr) {
            return;
        }
        D3DSURFACE_DESC renderTargetDescription = {};
        const HRESULT descriptionResult = renderTarget->GetDesc(&renderTargetDescription);
        renderTarget->Release();
        if (FAILED(descriptionResult) || renderTargetDescription.Width == 0 || renderTargetDescription.Height == 0) {
            return;
        }
        DWORD stateBlock = 0;
        if (FAILED(device_->CreateStateBlock(D3DSBT_ALL, &stateBlock))) {
            return;
        }

        D3DVIEWPORT8 fullViewport = {};
        fullViewport.Width = renderTargetDescription.Width;
        fullViewport.Height = renderTargetDescription.Height;
        fullViewport.MinZ = 0.0f;
        fullViewport.MaxZ = 1.0f;
        if (FAILED(device_->SetViewport(&fullViewport))) {
            device_->DeleteStateBlock(stateBlock);
            return;
        }

        const float left = -0.5f;
        const float top = -0.5f;
        const float right = left + static_cast<float>(renderTargetDescription.Width);
        const float bottom = top + static_cast<float>(renderTargetDescription.Height);
        const Vertex vertices[4] = {
            {left, top, 0.0f, 1.0f, 0.0f, 0.0f},
            {right, top, 0.0f, 1.0f, 1.0f, 0.0f},
            {left, bottom, 0.0f, 1.0f, 0.0f, 1.0f},
            {right, bottom, 0.0f, 1.0f, 1.0f, 1.0f},
        };

        device_->SetRenderState(D3DRS_ZENABLE, FALSE);
        device_->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
        device_->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
        device_->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
        device_->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
        device_->SetRenderState(D3DRS_LIGHTING, FALSE);
        device_->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
        device_->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
        device_->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG1);
        device_->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
        device_->SetTextureStageState(0, D3DTSS_MINFILTER, D3DTEXF_LINEAR);
        device_->SetTextureStageState(0, D3DTSS_MAGFILTER, D3DTEXF_LINEAR);
        device_->SetTexture(0, currentTexture_);
        device_->SetPixelShader(0);
        device_->SetVertexShader(D3DFVF_XYZRHW | D3DFVF_TEX1);
        device_->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, vertices, sizeof(Vertex));
        device_->SetTexture(0, nullptr);
        device_->ApplyStateBlock(stateBlock);
        device_->SetViewport(&originalViewport);
        device_->DeleteStateBlock(stateBlock);
    }

    void ReleaseTexturesLocked() {
        for (IDirect3DTexture8*& texture : textures_) {
            if (texture != nullptr) {
                texture->Release();
                texture = nullptr;
            }
        }
        currentTexture_ = nullptr;
        textureWidth_ = 0;
        textureHeight_ = 0;
    }

    uint64_t ElapsedNanosecondsLocked() const {
        if (!playbackStarted_ || performanceFrequency_.QuadPart <= 0) {
            return 0;
        }
        LARGE_INTEGER now = {};
        QueryPerformanceCounter(&now);
        const uint64_t ticks = static_cast<uint64_t>(now.QuadPart - playbackStart_.QuadPart);
        return ticks * 1000000000ull / static_cast<uint64_t>(performanceFrequency_.QuadPart);
    }

    void WorkerError(const char* text) {
        EnterCriticalSection(&lock_);
        SetErrorLocked(text);
        state_.store(BDV_STATE_ERROR, std::memory_order_release);
        decodeComplete_ = true;
        LeaveCriticalSection(&lock_);
    }

    void SetError(const char* text) {
        EnterCriticalSection(&lock_);
        SetErrorLocked(text);
        LeaveCriticalSection(&lock_);
    }

    void SetErrorLocked(const char* text) {
        lstrcpynA(lastError_, text == nullptr ? "unknown error" : text, sizeof(lastError_));
        Log(text);
    }

    void Log(const char* text) const {
        HANDLE file = CreateFileA(
            "BeiDouVideo.log",
            FILE_APPEND_DATA,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            nullptr,
            OPEN_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            nullptr);
        if (file == INVALID_HANDLE_VALUE) {
            return;
        }
        DWORD written = 0;
        WriteFile(file, channelName_, lstrlenA(channelName_), &written, nullptr);
        WriteFile(file, ": ", 2, &written, nullptr);
        const char* value = text == nullptr ? "unknown" : text;
        WriteFile(file, value, lstrlenA(value), &written, nullptr);
        WriteFile(file, "\r\n", 2, &written, nullptr);
        CloseHandle(file);
    }

    CRITICAL_SECTION lock_ = {};
    HANDLE stopEvent_ = nullptr;
    HANDLE worker_ = nullptr;
    std::atomic<uint32_t> state_{BDV_STATE_IDLE};
    MappedFile mapped_;
    bdv::McvVideo video_;
    FrameSlot slots_[kQueueSize];
    bool decodeComplete_ = false;
    bool playbackStarted_ = false;
    uint32_t decodedFrames_ = 0;
    uint32_t displayedFrames_ = 0;
    uint32_t droppedFrames_ = 0;
    uint32_t currentFrameIndex_ = static_cast<uint32_t>(-1);
    LARGE_INTEGER performanceFrequency_ = {};
    LARGE_INTEGER playbackStart_ = {};
    IDirect3DDevice8* device_ = nullptr;
    IDirect3DTexture8* textures_[2] = {};
    IDirect3DTexture8* currentTexture_ = nullptr;
    int currentTextureIndex_ = 0;
    uint32_t textureWidth_ = 0;
    uint32_t textureHeight_ = 0;
    char lastError_[256] = {};
    const char* channelName_ = nullptr;
};

Player* gPlayers[BDV_CHANNEL_COUNT] = {};

Player* GetPlayer(uint32_t channel) {
    return channel < BDV_CHANNEL_COUNT ? gPlayers[channel] : nullptr;
}

}  // namespace

int BDV_CALL BDV_AttachDevice(void* direct3DDevice8) {
    if (direct3DDevice8 == nullptr) {
        return 0;
    }
    for (uint32_t channel = 0; channel < BDV_CHANNEL_COUNT; ++channel) {
        Player* player = GetPlayer(channel);
        if (player == nullptr || !player->AttachDevice(direct3DDevice8)) {
            for (uint32_t attached = 0; attached < channel; ++attached) {
                GetPlayer(attached)->DetachDevice();
            }
            return 0;
        }
    }
    return 1;
}

void* BDV_CALL BDV_GetAttachedDevice() {
    Player* player = GetPlayer(BDV_CHANNEL_PLAYER_SKILL);
    return player == nullptr ? nullptr : player->GetAttachedDevice();
}

void BDV_CALL BDV_DetachDevice() {
    for (uint32_t channel = 0; channel < BDV_CHANNEL_COUNT; ++channel) {
        if (GetPlayer(channel) != nullptr) {
            GetPlayer(channel)->DetachDevice();
        }
    }
}

int BDV_CALL BDV_PlayFile(const char* path) {
    return BDV_PlayFileEx(BDV_CHANNEL_PLAYER_SKILL, path);
}

int BDV_CALL BDV_PlayFileEx(uint32_t channel, const char* path) {
    Player* player = GetPlayer(channel);
    return player != nullptr && player->Play(path) ? 1 : 0;
}

void BDV_CALL BDV_Stop() {
    BDV_StopChannel(BDV_CHANNEL_PLAYER_SKILL);
}

void BDV_CALL BDV_StopChannel(uint32_t channel) {
    if (GetPlayer(channel) != nullptr) {
        GetPlayer(channel)->Stop();
    }
}

void BDV_CALL BDV_Render() {
    BDV_RenderAll();
}

void BDV_CALL BDV_RenderAll() {
    const uint32_t renderOrder[] = {
        BDV_CHANNEL_BOSS_SCENE,
        BDV_CHANNEL_PLAYER_SKILL,
    };
    for (uint32_t channel : renderOrder) {
        if (GetPlayer(channel) != nullptr) {
            GetPlayer(channel)->Render();
        }
    }
}

int BDV_CALL BDV_GetStatus(BdvStatus* status) {
    return BDV_GetStatusEx(BDV_CHANNEL_PLAYER_SKILL, status);
}

int BDV_CALL BDV_GetStatusEx(uint32_t channel, BdvStatus* status) {
    Player* player = GetPlayer(channel);
    return player != nullptr && player->GetStatus(status) ? 1 : 0;
}

void BDV_CALL BDV_GetLastError(char* buffer, uint32_t capacity) {
    BDV_GetLastErrorEx(BDV_CHANNEL_PLAYER_SKILL, buffer, capacity);
}

void BDV_CALL BDV_GetLastErrorEx(uint32_t channel, char* buffer, uint32_t capacity) {
    if (GetPlayer(channel) != nullptr) {
        GetPlayer(channel)->GetLastErrorText(buffer, capacity);
    } else if (buffer != nullptr && capacity != 0) {
        lstrcpynA(buffer, "invalid or uninitialized video channel", static_cast<int>(capacity));
    }
}

extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DeleteFileA("BeiDouVideo.log");
        gPlayers[BDV_CHANNEL_PLAYER_SKILL] = new (std::nothrow) Player("player-skill");
        gPlayers[BDV_CHANNEL_BOSS_SCENE] = new (std::nothrow) Player("boss-scene");
        if (gPlayers[BDV_CHANNEL_PLAYER_SKILL] == nullptr ||
            gPlayers[BDV_CHANNEL_BOSS_SCENE] == nullptr) {
            for (Player*& player : gPlayers) {
                delete player;
                player = nullptr;
            }
            return FALSE;
        }
        return TRUE;
    }
    if (reason == DLL_PROCESS_DETACH) {
        for (Player*& player : gPlayers) {
            delete player;
            player = nullptr;
        }
    }
    return TRUE;
}
