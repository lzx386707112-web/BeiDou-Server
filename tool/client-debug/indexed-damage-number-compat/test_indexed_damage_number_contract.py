#!/usr/bin/env python3
"""Static contracts for the indexed DAMAGE_MONSTER client hook."""

from pathlib import Path
import re
import struct
import unittest


SOURCE = Path(__file__).with_name("IndexedDamageNumberCompat.cpp")
ROOT = SOURCE.resolve().parents[3]


class IndexedDamageNumberContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_hook_is_bounded_to_the_verified_damage_monster_decoder(self) -> None:
        self.assertIn("kDamageMonsterHookAddress = 0x0066C6CB", self.source)
        self.assertIn('"push 0x0066C6E9', self.source)
        original = re.search(
            r"kDamageMonsterOriginal\[\] = \{(?P<body>.*?)\};",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(original)
        self.assertEqual(30, len(re.findall(r"0x[0-9A-F]{2}", original.group("body"))))
        self.assertIn("BytesEqual(target, kDamageMonsterOriginal", self.source)

    def test_hook_bytes_match_the_repository_client_executable(self) -> None:
        original = re.search(
            r"kDamageMonsterOriginal\[\] = \{(?P<body>.*?)\};",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(original)
        expected = bytes(
            int(value, 16)
            for value in re.findall(r"0x([0-9A-F]{2})", original.group("body"))
        )
        executable = (ROOT / "clien/BeiDou.exe").read_bytes()
        file_offset = 0x26C6CB
        self.assertEqual(expected, executable[file_offset : file_offset + len(expected)])

    def test_only_reserved_markers_become_native_hit_indices(self) -> None:
        hook = self.source[
            self.source.index("void HookDamageMonsterNumber") :
            self.source.index("bool InstallHook")
        ]
        self.assertIn('"cmp edx, 0x80', hook)
        self.assertIn('"cmp edx, 0x8E', hook)
        self.assertIn('"and edx, 0x0F', hook)
        self.assertIn('"damage_number_unmarked:\\n"\n        "xor edx, edx', hook)

    def test_hook_reuses_native_number_layout_without_player_attack_routing(self) -> None:
        self.assertIn('"mov eax, 0x006691D3', self.source)
        self.assertNotIn("0x009803AB", self.source)
        self.assertNotIn("CUserLocal", self.source)
        self.assertNotIn("CUserRemote", self.source)

    def test_diagnostics_watchdog_loads_module_before_its_first_sleep(self) -> None:
        logger = (
            ROOT / "tool/client-debug/wz_file_logger/WzFileLogger.cpp"
        ).read_text(encoding="utf-8")
        watchdog = logger[logger.index("static DWORD WINAPI WatchdogThreadProc") :]
        load = watchdog.index('RealLoadLibraryA("IndexedDamageNumberCompat.dll")')
        first_sleep = watchdog.index("Sleep(g_healthIntervalMs)")
        self.assertLess(load, first_sleep)

    def test_server_packet_and_cosmos_use_the_indexed_protocol(self) -> None:
        packet_creator = (
            ROOT / "gms-server/src/main/java/org/gms/util/PacketCreator.java"
        ).read_text(encoding="utf-8")
        indexed_packet = packet_creator[
            packet_creator.index("public static Packet indexedDamageMonsterNumber") :
            packet_creator.index("public static Packet healMonster")
        ]
        self.assertIn("p.writeByte(INDEXED_DAMAGE_NUMBER_MARKER | hitIndex);", indexed_packet)
        self.assertIn("hitIndex >= MAX_INDEXED_DAMAGE_NUMBER_HITS", indexed_packet)

        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        cosmos = close_handler[
            close_handler.index("private void scheduleCosmosAttacks") :
            close_handler.index("void scheduleTrackingCloseAttacks", close_handler.index("private void scheduleCosmosAttacks"))
        ]
        self.assertIn("showCapturedIndexedDamageNumbers", cosmos)
        self.assertIn("LocalDamageNumberMode.INDEXED", cosmos)

    def test_server_stages_indexed_hits_at_the_native_brandish_interval(self) -> None:
        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/AbstractDealDamageHandler.java"
        ).read_text(encoding="utf-8")
        indexed_helper = handler[
            handler.index("protected static void showIndexedDamageNumbers") :
            handler.index("public static class AttackInfo")
        ]
        self.assertIn("INDEXED_DAMAGE_NUMBER_HIT_INTERVAL_MS = 120", handler)
        self.assertIn("damageByMonster,\n                INDEXED_DAMAGE_NUMBER_HIT_INTERVAL_MS", indexed_helper)
        self.assertIn("TimerManager.getInstance().schedule", indexed_helper)
        self.assertIn("hitIndex * hitIntervalMs", indexed_helper)
        self.assertIn("if (hitIndex == 0)", indexed_helper)
        self.assertIn("chr.getMap() != expectedMap", indexed_helper)

    def test_dawn_warrior_animated_skills_use_indexed_replay_numbers(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        scheduler = close_handler[
            close_handler.index("private void scheduleAnimatedAttacks") :
            close_handler.index("@Override", close_handler.index("private void scheduleAnimatedAttacks"))
        ]
        self.assertIn("LocalDamageNumberMode damageNumberMode", scheduler)
        self.assertIn("damageNumberHitIntervalMs", scheduler)
        self.assertIn("showCapturedIndexedDamageNumbers(", scheduler)
        self.assertIn("repeatCapturedAttack(", scheduler)
        self.assertIn("damageNumberMode", scheduler)
        self.assertNotIn("createFallbackCloseDamageTemplate(", scheduler)
        for skill in ("GALAXY_STAR_BURST", "ECLIPSE_FORCE", "SOUL_ECLIPSE"):
            branch_start = close_handler.index(f"attack.skill == DawnWarrior.{skill}")
            branch_end = close_handler.index("} else if", branch_start)
            branch = close_handler[branch_start:branch_end]
            self.assertIn("scheduleAnimatedAttacks(", branch)
            self.assertIn("LocalDamageNumberMode.INDEXED", branch)
            expected_interval = (
                "GALAXY_STAR_BURST_DAMAGE_NUMBER_HIT_INTERVAL_MS"
                if skill == "GALAXY_STAR_BURST"
                else "INDEXED_DAMAGE_NUMBER_HIT_INTERVAL_MS"
            )
            self.assertIn(expected_interval, branch)

    def test_animated_replay_keeps_one_damage_settlement_per_target(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        replay = close_handler[
            close_handler.index("private static int repeatCapturedAttack") :
            close_handler.index("private static void showCapturedDamageNumbers")
        ]
        self.assertIn("chr, expectedMap, liveDamage, damageNumberHitIntervalMs", replay)
        self.assertEqual(1, replay.count("expectedMap.damageMonster(chr, monster, damage);"))
        self.assertEqual(1, replay.count("monster.aggroMonsterDamage(chr, damage);"))
        self.assertIn("damageNumberMode == LocalDamageNumberMode.TOTAL", replay)

    def test_empty_cast_defers_fallback_damage_until_a_later_tick_has_targets(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        fallback = close_handler[
            close_handler.index("private static List<Integer> createFallbackCloseDamageTemplate") :
            close_handler.index("private static List<Integer> adaptDamageTemplate")
        ]
        self.assertIn("DawnWarrior.SWORD_MASTERY", fallback)
        self.assertIn("Randomizer.rand(minimumDamage, maximumDamage)", fallback)
        self.assertIn("new ArrayList<>(attackCount)", fallback)
        cosmos = close_handler[
            close_handler.index("private void scheduleCosmosAttacks") :
            close_handler.index("void scheduleTrackingCloseAttacks", close_handler.index("private void scheduleCosmosAttacks"))
        ]
        self.assertNotIn("createFallbackCloseDamageTemplate(", cosmos)
        self.assertNotIn("Collections.singletonList", cosmos)

        scheduled_tracking = close_handler[
            close_handler.index("void scheduleTrackingCloseAttacks", close_handler.index("private void scheduleCosmosAttacks")) :
            close_handler.index("private static void repeatLightningSpearThunder")
        ]
        self.assertNotIn("calculateFallbackCloseDamage(", scheduled_tracking)
        self.assertNotIn("Collections.singletonList", scheduled_tracking)

        tracking = close_handler[
            close_handler.index("private static void repeatTrackingCloseAttack") :
            close_handler.index("void scheduleTrackingCloseAttacks", close_handler.index("private static void repeatTrackingCloseAttack"))
        ]
        no_targets = tracking.index("if (damage.isEmpty())")
        lazy_fallback = tracking.index("if (damageTemplate.isEmpty())", no_targets)
        packet = tracking.index("Packet packet =", lazy_fallback)
        self.assertLess(no_targets, lazy_fallback)
        self.assertLess(lazy_fallback, packet)
        self.assertIn("createFallbackCloseDamageTemplate(", tracking)
        self.assertIn("damage.replaceAll(", tracking)

        animated = close_handler[
            close_handler.index("private static int repeatCapturedAttack") :
            close_handler.index("private static void showCapturedDamageNumbers")
        ]
        no_targets = animated.index("if (liveDamage.isEmpty())")
        lazy_fallback = animated.index("if (damageTemplate.isEmpty())", no_targets)
        packet = animated.index("Packet repeatedAttack =", lazy_fallback)
        self.assertLess(no_targets, lazy_fallback)
        self.assertLess(lazy_fallback, packet)
        self.assertIn("liveDamage.replaceAll(", animated)

        tracking_collector = close_handler[
            close_handler.index("private static Map<Integer, List<Integer>> collectTrackingCloseTargets") :
            close_handler.index("private static void repeatTrackingCloseAttack")
        ]
        self.assertNotIn("if (damageTemplate.isEmpty())", tracking_collector)

    def test_full_eclipse_keeps_all_source_frames_at_60ms(self) -> None:
        exporter = (
            ROOT / "tool/client-video/export_dawn_warrior_mcvs.py"
        ).read_text(encoding="utf-8")
        self.assertIn('full_eclipse_track(ms_source, 11141503, "screen")', exporter)
        self.assertIn('full_eclipse_track(ms_source, 11141504, "screen")', exporter)
        self.assertIn("len(opening) != 43 or len(finishing) != 44", exporter)
        self.assertIn("delays != [60] * 87", exporter)

        data = (ROOT / "clien/Data/Video/eclipse-force.mcv").read_bytes()
        header = struct.unpack_from("<4sHHIHHIB3xQI", data, 0)
        signature, _, header_size, _, width, height, frame_count, flags, _, _ = header
        self.assertEqual(b"MCV0", signature)
        self.assertEqual((1280, 720, 87), (width, height, frame_count))
        self.assertEqual(0x03, flags)
        delay_offset = header_size + frame_count * 8 * 2
        delays = struct.unpack_from(f"<{frame_count}I", data, delay_offset)
        self.assertEqual((60,) * 87, delays)


if __name__ == "__main__":
    unittest.main()
