#include "pch.h"
#include "hook.h"
#include "weather.h"
#include "wvs/packet.h"
#include "wvs/wvsapp.h"
#include "ztl/ztl.h"

ZALLOC_GLOBAL
ZALLOCEX(ZAllocAnonSelector, 0x00BF0B00)
ZALLOCEX(ZAllocStrSelector<char>, 0x00BF0A90)
ZALLOCEX(ZAllocStrSelector<wchar_t>, 0x00BF0BA8)

extern void Weather_Tick();
extern void WeatherPuddle_Frame();
extern void WeatherAccum_Frame();
extern void WeatherSplash_Frame();
extern void WeatherSway_Frame();
extern void AttachWeatherMod();
extern void AttachWeatherWindMod();

void CWvsApp::CallUpdate_hook(int currentTime) {
    Weather_Tick();
    if (Weather::IsFieldActive()) {
        if (Weather::HasFallingSky()) {
            WeatherSplash_Frame();
            WeatherPuddle_Frame();
            WeatherAccum_Frame();
        }
        WeatherSway_Frame();
    }
    CallUpdate(this, currentTime);
}

namespace {

using RegisterPacketHandlerFn = BOOL(WINAPI*)(BOOL(WINAPI*)(void*));

BOOL WINAPI HandlePacket(void* rawPacket) {
    auto* packet = static_cast<CInPacket*>(rawPacket);
    if (packet == nullptr || packet->Peek2Public() != 0x373D) return FALSE;
    Weather_HandleWorldState(packet);
    return TRUE;
}

bool RegisterPacketHandler() {
    HMODULE setItem = LoadLibraryA("BeiDouSetItemCompat.dll");
    if (setItem == nullptr) return false;
    FARPROC address = GetProcAddress(setItem, "BDS_RegisterPacketHandler");
    if (address == nullptr) return false;
    auto registration = reinterpret_cast<RegisterPacketHandlerFn>(address);
    return registration(&HandlePacket) == TRUE;
}

DWORD WINAPI Install(LPVOID) {
    LogMessage("LOAD: BeiDouWeatherCompat v1 visual-only");
    if (reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != 0x00400000) {
        LogMessage("ERROR: unexpected BeiDou.exe image base");
        return 1;
    }
    if (!RegisterPacketHandler()) {
        LogMessage("ERROR: BeiDouSetItemCompat packet extension API unavailable");
        return 2;
    }
    if (!ATTACH_HOOK(CWvsApp::CallUpdate, CWvsApp::CallUpdate_hook)) {
        LogMessage("ERROR: CallUpdate hook installation failed");
        return 3;
    }
    AttachWeatherMod();
    AttachWeatherWindMod();
    LogMessage("OK: visual weather hooks installed");
    return 0;
}

}  // namespace

extern "C" __declspec(dllexport) void WeatherCompatVersion() {
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(nullptr, 0, Install, nullptr, 0, nullptr);
        if (thread != nullptr) CloseHandle(thread);
    }
    return TRUE;
}
