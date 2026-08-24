#!/usr/bin/env python3
"""Static contract checks for the fixed two-channel MCV player."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "tool" / "client-video"
COMPAT = (
    ROOT
    / "tool"
    / "client-debug"
    / "karing-scene-compat"
    / "KaringSceneCompat.cpp"
)
WZ_LOGGER = (
    ROOT
    / "tool"
    / "client-debug"
    / "wz_file_logger"
    / "WzFileLogger.cpp"
)


class MultiChannelContractTest(unittest.TestCase):
    def test_api_keeps_legacy_entry_points_and_adds_channel_operations(self) -> None:
        header = (VIDEO / "BeiDouVideoApi.h").read_text(encoding="utf-8")
        for declaration in (
            "BDV_CHANNEL_PLAYER_SKILL = 0",
            "BDV_CHANNEL_BOSS_SCENE = 1",
            "BDV_CHANNEL_COUNT = 2",
            "BDV_GetAttachedDevice()",
            "BDV_PlayFile(const char* path)",
            "BDV_PlayFileEx(uint32_t channel, const char* path)",
            "BDV_StopChannel(uint32_t channel)",
            "BDV_RenderAll()",
            "BDV_GetStatusEx(uint32_t channel, BdvStatus* status)",
            "BDV_GetLastErrorEx(uint32_t channel, char* buffer, uint32_t capacity)",
        ):
            self.assertIn(declaration, header)

    def test_legacy_operations_target_player_channel(self) -> None:
        source = (VIDEO / "BeiDouVideo.cpp").read_text(encoding="utf-8")
        self.assertIn(
            "return BDV_PlayFileEx(BDV_CHANNEL_PLAYER_SKILL, path);", source
        )
        self.assertIn("BDV_StopChannel(BDV_CHANNEL_PLAYER_SKILL);", source)
        self.assertIn(
            "return BDV_GetStatusEx(BDV_CHANNEL_PLAYER_SKILL, status);", source
        )
        self.assertIn(
            "BDV_GetLastErrorEx(BDV_CHANNEL_PLAYER_SKILL, buffer, capacity);", source
        )

    def test_render_order_puts_player_skill_above_boss_scene(self) -> None:
        source = (VIDEO / "BeiDouVideo.cpp").read_text(encoding="utf-8")
        boss = source.index("BDV_CHANNEL_BOSS_SCENE", source.index("renderOrder[]"))
        player = source.index("BDV_CHANNEL_PLAYER_SKILL", boss)
        self.assertLess(boss, player)

    def test_channel_lookup_rejects_out_of_range_values(self) -> None:
        source = (VIDEO / "BeiDouVideo.cpp").read_text(encoding="utf-8")
        self.assertIn(
            "return channel < BDV_CHANNEL_COUNT ? gPlayers[channel] : nullptr;",
            source,
        )
        self.assertIn("Player* player = GetPlayer(channel);", source)

    def test_each_player_stops_and_cleans_up_only_its_own_playback(self) -> None:
        source = (VIDEO / "BeiDouVideo.cpp").read_text(encoding="utf-8")
        play = source[source.index("bool Play(const char* path)") :]
        play = play[: play.index("void Stop()")]
        self.assertEqual(2, play.count("Stop();"))
        self.assertNotIn("gPlayers", play)

    def test_harness_can_start_and_monitor_both_channels(self) -> None:
        source = (VIDEO / "VideoHarness.cpp").read_text(encoding="utf-8")
        self.assertIn('LoadFunction<PlayFileExFn>(gVideoModule, "BDV_PlayFileEx")', source)
        self.assertIn("bossVideoPath = TrimArgument(bossVideoPath);", source)
        self.assertIn("playFileEx(BDV_CHANNEL_BOSS_SCENE, bossVideoPath)", source)
        self.assertIn(
            "gGetStatusEx(BDV_CHANNEL_BOSS_SCENE, &bossStatus)", source
        )

    def test_karing_spawn_markers_are_detectable_and_routed(self) -> None:
        source = COMPAT.read_text(encoding="utf-8")
        self.assertEqual(2, source.count("code >= 1 && code <= 14"))
        self.assertIn("pixels[3] != 0xFCDD", source)
        self.assertNotIn("0xFCDE", source)
        self.assertIn('{13, "Data\\\\Video\\\\karing-p2-regen.mcv"', source)
        self.assertIn('{14, "Data\\\\Video\\\\karing-p3-regen.mcv"', source)

    def test_only_karing_dark_pulse_uses_the_ground_anchor_offset(self) -> None:
        source = (VIDEO / "export_karing_boss_mcvs.py").read_text(encoding="utf-8")
        self.assertIn("anchor_offset_y: int = 0", source)
        self.assertIn("TMS_VIEWPORT_HEIGHT = 768", source)
        self.assertIn("TMS_DARK_PULSE_GROUND_Y = 699", source)
        self.assertIn("return target_anchor_y - HEIGHT // 2", source)
        self.assertIn("anchor_offset_y=projected_ground_offset_y()", source)
        self.assertNotIn("anchor_offset_y=64", source)
        self.assertIn(
            "top = HEIGHT // 2 + anchor_offset_y - origin_y", source
        )

    def test_karing_compat_chains_existing_device_hooks(self) -> None:
        source = COMPAT.read_text(encoding="utf-8")
        self.assertIn('LoadFunction<GetAttachedDeviceFn>(module, "BDV_GetAttachedDevice")', source)
        self.assertIn("gNextPresent = FunctionFromPointer<PresentFn>(original);", source)
        self.assertIn("return gNextSetTexture(device, stage, texture);", source)
        self.assertNotIn('LoadLibraryA("DawnWarriorSkillCompat.dll")', source)

    def test_karing_compat_load_waits_for_a_karing_map(self) -> None:
        source = WZ_LOGGER.read_text(encoding="utf-8")
        for map_id in range(410007100, 410007301, 20):
            self.assertIn(f'L"{map_id}.img"', source)
        self.assertIn("DetectKaringMapOpen(fileName);", source)
        self.assertIn("DetectKaringMapOpen(widePath);", source)
        load_condition = source[source.index("if (sawClientWindow") :]
        load_condition = load_condition[: load_condition.index("HMODULE karingCompat")]
        self.assertIn("g_karingMapDetected", load_condition)
        self.assertIn('GetModuleHandleA("BeiDouVideo.dll")', load_condition)

    def test_wz_logger_holds_modules_while_patching_imports(self) -> None:
        source = WZ_LOGGER.read_text(encoding="utf-8")
        patch_module = source[source.index("static int PatchModule(") :]
        patch_module = patch_module[: patch_module.index("static void PatchAllModules()")]
        self.assertIn("GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS", patch_module)
        self.assertIn("heldModule != module", patch_module)
        self.assertEqual(3, patch_module.count("FreeLibrary(heldModule);"))
        self.assertLess(
            patch_module.index("GetModuleHandleExW("),
            patch_module.index("PatchImport(module"),
        )

    def test_karing_markers_cannot_restart_or_render_twice_while_playing(self) -> None:
        source = COMPAT.read_text(encoding="utf-8")
        consume = source[source.index("bool ConsumeMarkerDraw()") :]
        consume = consume[: consume.index("HRESULT WINAPI HookSetTexture")]
        render = source[source.index("void RenderScene()") :]
        render = render[: render.index("bool ConsumeMarkerDraw()")]
        self.assertIn("if (!gScenePlaying)", consume)
        self.assertNotIn("gBoundMarkerCode !=", consume)
        self.assertIn("gRenderedThisFrame", render)
        self.assertIn("gMarkerStarted[kMarkerCodeCount]", source)
        self.assertIn("gFramesWithoutMarker[kMarkerCodeCount]", source)
        self.assertIn("gSawMarkerThisFrame[markerCode] = false;", source)
        self.assertIn("gPendingMarkerCode = gBoundMarkerCode;", source)
        self.assertIn("StartScene(pendingMarkerCode);", source)


if __name__ == "__main__":
    unittest.main()
