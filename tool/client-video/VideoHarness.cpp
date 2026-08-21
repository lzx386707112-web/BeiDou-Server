#include "BeiDouVideoApi.h"

#include <windows.h>
#include <d3d8.h>

#include <string.h>

namespace {

using AttachDeviceFn = int(BDV_CALL*)(void*);
using DetachDeviceFn = void(BDV_CALL*)();
using PlayFileFn = int(BDV_CALL*)(const char*);
using PlayFileExFn = int(BDV_CALL*)(uint32_t, const char*);
using StopFn = void(BDV_CALL*)();
using StopChannelFn = void(BDV_CALL*)(uint32_t);
using RenderFn = void(BDV_CALL*)();
using GetStatusFn = int(BDV_CALL*)(BdvStatus*);
using GetStatusExFn = int(BDV_CALL*)(uint32_t, BdvStatus*);
using GetLastErrorFn = void(BDV_CALL*)(char*, uint32_t);
using GetLastErrorExFn = void(BDV_CALL*)(uint32_t, char*, uint32_t);

HMODULE gVideoModule = nullptr;
IDirect3D8* gDirect3D = nullptr;
IDirect3DDevice8* gDevice = nullptr;
DetachDeviceFn gDetachDevice = nullptr;
StopFn gStop = nullptr;
StopChannelFn gStopChannel = nullptr;
RenderFn gRender = nullptr;
GetStatusFn gGetStatus = nullptr;
GetStatusExFn gGetStatusEx = nullptr;
GetLastErrorFn gGetLastError = nullptr;
GetLastErrorExFn gGetLastErrorEx = nullptr;
bool gBossVideoEnabled = false;

template <typename Function>
Function LoadFunction(HMODULE module, const char* name) {
    const FARPROC address = GetProcAddress(module, name);
    static_assert(sizeof(Function) == sizeof(address), "unexpected Win32 function pointer size");
    Function function = nullptr;
    memcpy(&function, &address, sizeof(function));
    return function;
}

LRESULT CALLBACK WindowProcedure(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == WM_CLOSE) {
        DestroyWindow(window);
        return 0;
    }
    if (message == WM_DESTROY) {
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcA(window, message, wParam, lParam);
}

void ShowVideoError(const char* title, uint32_t channel = BDV_CHANNEL_PLAYER_SKILL) {
    char message[256] = "video operation failed";
    if (gGetLastErrorEx != nullptr) {
        gGetLastErrorEx(channel, message, sizeof(message));
    } else if (gGetLastError != nullptr) {
        gGetLastError(message, sizeof(message));
    }
    MessageBoxA(nullptr, message, title, MB_OK | MB_ICONERROR);
}

void Cleanup() {
    if (gStopChannel != nullptr) {
        gStopChannel(BDV_CHANNEL_BOSS_SCENE);
        gStopChannel(BDV_CHANNEL_PLAYER_SKILL);
    } else if (gStop != nullptr) {
        gStop();
    }
    if (gDetachDevice != nullptr) {
        gDetachDevice();
    }
    if (gDevice != nullptr) {
        gDevice->Release();
        gDevice = nullptr;
    }
    if (gDirect3D != nullptr) {
        gDirect3D->Release();
        gDirect3D = nullptr;
    }
    if (gVideoModule != nullptr) {
        FreeLibrary(gVideoModule);
        gVideoModule = nullptr;
    }
}

char* TrimArgument(char* value) {
    while (*value == ' ' || *value == '\t' || *value == '"') {
        ++value;
    }
    char* end = value + lstrlenA(value);
    while (end > value && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '"')) {
        --end;
    }
    *end = '\0';
    return value;
}

}  // namespace

int WINAPI WinMain(HINSTANCE instance, HINSTANCE, LPSTR commandLine, int showCommand) {
    char* bossVideoPath = nullptr;
    if (commandLine != nullptr) {
        bossVideoPath = strchr(commandLine, '|');
        if (bossVideoPath != nullptr) {
            *bossVideoPath++ = '\0';
            bossVideoPath = TrimArgument(bossVideoPath);
            gBossVideoEnabled = bossVideoPath[0] != '\0';
        }
    }
    char* playerVideoArgument = commandLine == nullptr ? nullptr : TrimArgument(commandLine);
    const char* playerVideoPath = playerVideoArgument != nullptr && playerVideoArgument[0] != '\0'
        ? playerVideoArgument
        : "Data\\Video\\soul-eclipse.mcv";

    WNDCLASSA windowClass = {};
    windowClass.lpfnWndProc = WindowProcedure;
    windowClass.hInstance = instance;
    windowClass.hCursor = LoadCursor(nullptr, IDC_ARROW);
    windowClass.lpszClassName = "BeiDouVideoHarness";
    if (!RegisterClassA(&windowClass)) {
        return 1;
    }
    RECT bounds = {0, 0, 1280, 720};
    AdjustWindowRect(&bounds, WS_OVERLAPPEDWINDOW, FALSE);
    HWND window = CreateWindowExA(
        0,
        windowClass.lpszClassName,
        "BeiDou MCV Streaming Harness",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        bounds.right - bounds.left,
        bounds.bottom - bounds.top,
        nullptr,
        nullptr,
        instance,
        nullptr);
    if (window == nullptr) {
        return 1;
    }
    ShowWindow(window, showCommand);

    gDirect3D = Direct3DCreate8(D3D_SDK_VERSION);
    if (gDirect3D == nullptr) {
        MessageBoxA(window, "Direct3DCreate8 failed", "BeiDou video harness", MB_OK | MB_ICONERROR);
        Cleanup();
        return 1;
    }
    D3DPRESENT_PARAMETERS present = {};
    present.Windowed = TRUE;
    present.SwapEffect = D3DSWAPEFFECT_DISCARD;
    present.BackBufferFormat = D3DFMT_UNKNOWN;
    if (FAILED(gDirect3D->CreateDevice(
            D3DADAPTER_DEFAULT,
            D3DDEVTYPE_HAL,
            window,
            D3DCREATE_SOFTWARE_VERTEXPROCESSING,
            &present,
            &gDevice))) {
        MessageBoxA(window, "D3D8 device creation failed", "BeiDou video harness", MB_OK | MB_ICONERROR);
        Cleanup();
        return 1;
    }

    gVideoModule = LoadLibraryA("BeiDouVideo.dll");
    if (gVideoModule == nullptr) {
        MessageBoxA(window, "BeiDouVideo.dll was not found", "BeiDou video harness", MB_OK | MB_ICONERROR);
        Cleanup();
        return 1;
    }
    auto attachDevice = LoadFunction<AttachDeviceFn>(gVideoModule, "BDV_AttachDevice");
    auto playFile = LoadFunction<PlayFileFn>(gVideoModule, "BDV_PlayFile");
    auto playFileEx = LoadFunction<PlayFileExFn>(gVideoModule, "BDV_PlayFileEx");
    gDetachDevice = LoadFunction<DetachDeviceFn>(gVideoModule, "BDV_DetachDevice");
    gStop = LoadFunction<StopFn>(gVideoModule, "BDV_Stop");
    gStopChannel = LoadFunction<StopChannelFn>(gVideoModule, "BDV_StopChannel");
    gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
    gGetStatus = LoadFunction<GetStatusFn>(gVideoModule, "BDV_GetStatus");
    gGetStatusEx = LoadFunction<GetStatusExFn>(gVideoModule, "BDV_GetStatusEx");
    gGetLastError = LoadFunction<GetLastErrorFn>(gVideoModule, "BDV_GetLastError");
    gGetLastErrorEx = LoadFunction<GetLastErrorExFn>(gVideoModule, "BDV_GetLastErrorEx");
    if (attachDevice == nullptr || playFile == nullptr || gDetachDevice == nullptr ||
        playFileEx == nullptr || gStop == nullptr || gStopChannel == nullptr ||
        gRender == nullptr || gGetStatus == nullptr || gGetStatusEx == nullptr ||
        gGetLastError == nullptr || gGetLastErrorEx == nullptr) {
        MessageBoxA(window, "BeiDouVideo.dll has an incompatible API", "BeiDou video harness", MB_OK | MB_ICONERROR);
        Cleanup();
        return 1;
    }
    if (!attachDevice(gDevice) || !playFile(playerVideoPath)) {
        ShowVideoError("BeiDou video harness");
        Cleanup();
        return 1;
    }
    if (gBossVideoEnabled && !playFileEx(BDV_CHANNEL_BOSS_SCENE, bossVideoPath)) {
        ShowVideoError("BeiDou boss video decode error", BDV_CHANNEL_BOSS_SCENE);
        Cleanup();
        return 1;
    }

    MSG message = {};
    bool running = true;
    while (running) {
        while (PeekMessageA(&message, nullptr, 0, 0, PM_REMOVE)) {
            if (message.message == WM_QUIT) {
                running = false;
                break;
            }
            TranslateMessage(&message);
            DispatchMessageA(&message);
        }
        if (!running) {
            break;
        }
        gDevice->Clear(0, nullptr, D3DCLEAR_TARGET, D3DCOLOR_XRGB(32, 32, 32), 1.0f, 0);
        if (SUCCEEDED(gDevice->BeginScene())) {
            gRender();
            gDevice->EndScene();
        }
        gDevice->Present(nullptr, nullptr, nullptr, nullptr);

        BdvStatus playerStatus = {};
        playerStatus.structureSize = sizeof(playerStatus);
        BdvStatus bossStatus = {};
        bossStatus.structureSize = sizeof(bossStatus);
        const bool playerComplete = gGetStatus(&playerStatus) &&
            (playerStatus.state == BDV_STATE_FINISHED || playerStatus.state == BDV_STATE_ERROR);
        const bool bossComplete = !gBossVideoEnabled || (gGetStatusEx(BDV_CHANNEL_BOSS_SCENE, &bossStatus) &&
            (bossStatus.state == BDV_STATE_FINISHED || bossStatus.state == BDV_STATE_ERROR));
        if (playerStatus.state == BDV_STATE_ERROR) {
            ShowVideoError("BeiDou player video decode error");
            running = false;
        } else if (bossStatus.state == BDV_STATE_ERROR) {
            ShowVideoError("BeiDou boss video decode error", BDV_CHANNEL_BOSS_SCENE);
            running = false;
        } else if (playerComplete && bossComplete) {
            running = false;
        }
        Sleep(1);
    }
    Cleanup();
    return 0;
}
