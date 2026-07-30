#include "BeiDouVideoApi.h"

#include <windows.h>
#include <d3d8.h>

#include <string.h>

namespace {

using AttachDeviceFn = int(BDV_CALL*)(void*);
using DetachDeviceFn = void(BDV_CALL*)();
using PlayFileFn = int(BDV_CALL*)(const char*);
using StopFn = void(BDV_CALL*)();
using RenderFn = void(BDV_CALL*)();
using GetStatusFn = int(BDV_CALL*)(BdvStatus*);
using GetLastErrorFn = void(BDV_CALL*)(char*, uint32_t);

HMODULE gVideoModule = nullptr;
IDirect3D8* gDirect3D = nullptr;
IDirect3DDevice8* gDevice = nullptr;
DetachDeviceFn gDetachDevice = nullptr;
StopFn gStop = nullptr;
RenderFn gRender = nullptr;
GetStatusFn gGetStatus = nullptr;
GetLastErrorFn gGetLastError = nullptr;

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

void ShowVideoError(const char* title) {
    char message[256] = "video operation failed";
    if (gGetLastError != nullptr) {
        gGetLastError(message, sizeof(message));
    }
    MessageBoxA(nullptr, message, title, MB_OK | MB_ICONERROR);
}

void Cleanup() {
    if (gStop != nullptr) {
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

}  // namespace

int WINAPI WinMain(HINSTANCE instance, HINSTANCE, LPSTR commandLine, int showCommand) {
    const char* videoPath = commandLine != nullptr && commandLine[0] != '\0'
        ? commandLine
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
    gDetachDevice = LoadFunction<DetachDeviceFn>(gVideoModule, "BDV_DetachDevice");
    gStop = LoadFunction<StopFn>(gVideoModule, "BDV_Stop");
    gRender = LoadFunction<RenderFn>(gVideoModule, "BDV_Render");
    gGetStatus = LoadFunction<GetStatusFn>(gVideoModule, "BDV_GetStatus");
    gGetLastError = LoadFunction<GetLastErrorFn>(gVideoModule, "BDV_GetLastError");
    if (attachDevice == nullptr || playFile == nullptr || gDetachDevice == nullptr ||
        gStop == nullptr || gRender == nullptr || gGetStatus == nullptr || gGetLastError == nullptr) {
        MessageBoxA(window, "BeiDouVideo.dll has an incompatible API", "BeiDou video harness", MB_OK | MB_ICONERROR);
        Cleanup();
        return 1;
    }
    if (!attachDevice(gDevice) || !playFile(videoPath)) {
        ShowVideoError("BeiDou video harness");
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

        BdvStatus status = {};
        status.structureSize = sizeof(status);
        if (gGetStatus(&status) && (status.state == BDV_STATE_FINISHED || status.state == BDV_STATE_ERROR)) {
            if (status.state == BDV_STATE_ERROR) {
                ShowVideoError("BeiDou video decode error");
            }
            running = false;
        }
        Sleep(1);
    }
    Cleanup();
    return 0;
}
