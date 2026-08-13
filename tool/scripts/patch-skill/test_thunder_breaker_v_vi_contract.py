#!/usr/bin/env python3
"""Regression contracts for the Thunder Breaker V/VI compatibility patch."""

from __future__ import annotations

import sys
import shutil
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import patch_thunder_breaker_v_vi as patch  # noqa: E402

CLIENT_VIDEO = ROOT / "tool/client-video"
sys.path.insert(0, str(CLIENT_VIDEO))

import export_thunder_breaker_mcvs as video  # noqa: E402

PATCH_CLIENT = ROOT / "tool/scripts/patch-client"
sys.path.insert(0, str(PATCH_CLIENT))

import patch_dawn_warrior_skill_dll_loader as dll_loader  # noqa: E402


class ThunderBreakerPatchContractTest(unittest.TestCase):
    def test_client_exe_loads_skill_compatibility_dll(self) -> None:
        exe = dll_loader.EXE.read_bytes()
        entry_patch = dll_loader.jump(
            dll_loader.ENTRY_VA, dll_loader.CAVE_VA
        )
        self.assertEqual(
            entry_patch,
            exe[
                dll_loader.ENTRY_OFFSET:
                dll_loader.ENTRY_OFFSET + len(entry_patch)
            ],
        )
        self.assertEqual(
            dll_loader.build_cave(),
            exe[
                dll_loader.CAVE_OFFSET:
                dll_loader.CAVE_OFFSET + dll_loader.CAVE_SIZE
            ],
        )

    def test_requested_skill_set_excludes_removed_skills(self) -> None:
        target_ids = {spec.target_id for spec in patch.SKILLS}

        self.assertNotIn(15121001, target_ids)
        self.assertNotIn(15121012, target_ids)
        constants = (
            ROOT
            / "gms-server/src/main/java/org/gms/constants/skills/ThunderBreaker.java"
        ).read_text(encoding="utf-8")
        self.assertNotIn("SHARK_TORPEDO", constants)
        self.assertNotIn("ANNIHILATE_VI", constants)

    def test_local_cooldown_policy(self) -> None:
        overrides = getattr(patch, "LOCAL_COOLDOWN_OVERRIDES", {})
        actual = {
            spec.target_id: overrides.get(spec.target_id, spec.cooldown)
            for spec in patch.SKILLS
        }
        expected = {
            spec.target_id: 10 if spec.target_id in {15121017, 15121019} else 0
            for spec in patch.SKILLS
        }

        self.assertEqual(expected, actual)

    def test_lightning_spear_replays_keep_visuals_and_main_range(self) -> None:
        generator = Path(patch.__file__).read_text(encoding="utf-8")
        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")

        self.assertIn("LIGHTNING_SPEAR_STAGE_IDS", generator)
        self.assertIn("targetingEffect", handler)
        self.assertIn("originalEffect : replayEffect", handler)
        self.assertIn("showThunderBreakerStandardEffect(chr, replaySkillId);", handler)

    def test_client_queues_full_screen_video_after_dispatch(self) -> None:
        source = (
            ROOT
            / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("QueueVideoSkill", source)
        self.assertIn("InterlockedExchange(&gPendingVideoSkillId", source)
        self.assertIn('call _QueueVideoSkill\\n', source)

    def test_origin_videos_cover_the_full_output_canvas(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg)

        for name in ("wave-riding-thunder.mcv", "swift-annihilation.mcv"):
            with self.subTest(name=name):
                actual = video.output_alpha_union_bounds(
                    ROOT / "clien/Data/Video" / name,
                    ffmpeg,
                )
                self.assertEqual((0, 0, video.WIDTH, video.HEIGHT), actual)

    def test_lightning_spear_replays_three_giant_thunders(self) -> None:
        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            [840, 1170, 1500],
            patch.java_int_array(handler, "LIGHTNING_SPEAR_GIANT_THUNDER_TIMES_MS"),
        )

    def test_lightning_spear_is_input_driven_for_twelve_presses(self) -> None:
        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")

        self.assertIn("LIGHTNING_SPEAR_MAX_PRESSES = 12", handler)
        self.assertIn("LIGHTNING_SPEAR_COMBO_WINDOW_MS = 60000", handler)
        self.assertIn("LIGHTNING_SPEAR_MIN_PRESS_INTERVAL_MS = 180", handler)
        self.assertIn("LIGHTNING_SPEAR_THUNDERS_PER_PRESS = 3", handler)
        self.assertEqual(
            [510],
            patch.java_int_array(handler, "LIGHTNING_SPEAR_FINISH_TIMES_MS"),
        )
        self.assertIn("advanceLightningSpearCombo", handler)
        self.assertIn("getCombatLifecycleGeneration()", handler)
        self.assertNotIn("scheduleLightningSpearMultistrike", handler)

        character = (
            ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(
            character.count("combatLifecycleGeneration.incrementAndGet();"),
            2,
        )

    def test_lightning_spear_has_one_server_only_visual_per_press(self) -> None:
        self.assertEqual(
            tuple(range(15121022, 15121034)),
            patch.LIGHTNING_SPEAR_COMBO_VISUAL_IDS,
        )

        constants = (
            ROOT
            / "gms-server/src/main/java/org/gms/constants/skills/ThunderBreaker.java"
        ).read_text(encoding="utf-8")
        self.assertIn("LIGHTNING_SPEAR_COMBO_VISUAL_FIRST = 15121022", constants)
        self.assertIn("LIGHTNING_SPEAR_COMBO_VISUAL_LAST = 15121033", constants)

        client = (
            ROOT
            / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("kThunderBreakerLastSkill = 15121033", client)
        keyboard_start = client.index("void HookKeyboardDispatch()")
        keyboard_end = client.index(
            "void HookActiveSkillDispatch()", keyboard_start
        )
        keyboard = client[keyboard_start:keyboard_end]
        self.assertIn('cmp ecx, 15121021\\n', keyboard)
        self.assertNotIn('cmp ecx, 15121033\\n', keyboard)
        active_start = client.index("void HookActiveSkillDispatch()")
        active_end = client.index(
            "void HookHighSkillVisualBranch()", active_start
        )
        active = client[active_start:active_end]
        self.assertIn('cmp esi, 15121033\\n', active)

    def test_lightning_spear_entry_effect_is_not_the_first_strike(self) -> None:
        self.assertNotIn(15121002, patch.COUNTER_EFFECT_IDS)
        generator = Path(patch.__file__).read_text(encoding="utf-8")
        self.assertIn("replace_lightning_spear_entry_effect", generator)

        image = patch.engine.WzImage.from_bytes(
            (ROOT / "clien/Data/Skill/1512.img").read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name="1512.img",
        )
        entry = image.parse().get("skill/15121002")
        frame = patch.engine.base.numeric_canvases(entry.get("effect"))[0]
        self.assertEqual((1, 1), (int(frame.width), int(frame.height)))
        self.assertIsNone(entry.get("hit"))

    def test_generated_combo_visuals_are_hidden_and_complete(self) -> None:
        image = patch.engine.WzImage.from_bytes(
            (ROOT / "clien/Data/Skill/1512.img").read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name="1512.img",
        )
        root = image.parse()
        for skill_id in patch.LIGHTNING_SPEAR_COMBO_VISUAL_IDS:
            with self.subTest(skill_id=skill_id):
                node = root.get(f"skill/{skill_id}")
                self.assertEqual(1, int(node.get("invisible").value))
                effect = patch.engine.base.numeric_canvases(node.get("effect"))
                self.assertTrue(effect)
                self.assertTrue(
                    any(int(frame.width) > 1 and int(frame.height) > 1
                        for frame in effect)
                )
                self.assertIsNotNone(node.get("hit"))

        for retired_id in (15121012, 15121013, 15121014):
            self.assertIsNone(root.get(f"skill/{retired_id}"))

        server_root = ET.parse(
            ROOT / "gms-server/wz/Skill.wz/1512.img.xml"
        ).getroot()
        for retired_id in (15121012, 15121013, 15121014):
            self.assertIsNone(
                server_root.find(
                    f"./imgdir[@name='skill']/imgdir[@name='{retired_id}']"
                )
            )

    def test_lightning_spear_explicitly_triggers_standard_effect(self) -> None:
        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        start = handler.index("private void advanceLightningSpearCombo(")
        end = handler.index(
            "private void scheduleAnimatedAttacks(", start
        )
        combo = handler[start:end]

        self.assertIn(
            "showThunderBreakerStandardEffect(chr, visualSkillId);", combo
        )
        helper_start = handler.index(
            "private static void showThunderBreakerStandardEffect("
        )
        helper_end = handler.index(
            "private static void showThunderBreakerSpecialEffect(", helper_start
        )
        helper = handler[helper_start:helper_end]
        self.assertIn("showOwnBuffEffect(skillId, 1)", helper)
        self.assertIn("showBuffEffect(chr.getId(), skillId, 1)", helper)

        thunder_start = handler.index(
            "private static void repeatLightningSpearThunder("
        )
        thunder_end = handler.index(
            "private void scheduleLightningSpearFinisher(", thunder_start
        )
        thunder = handler[thunder_start:thunder_end]
        self.assertIn(
            "showThunderBreakerStandardEffect(\n"
            "                    chr, ThunderBreaker.LIGHTNING_SPEAR_THUNDER\n"
            "            );",
            thunder,
        )
        self.assertNotIn("showThunderBreakerSpecialEffect", thunder)

        replay_start = handler.index(
            "private static void repeatTrackingCloseAttack("
        )
        replay_end = handler.index(
            "void scheduleTrackingCloseAttacks(", replay_start
        )
        replay = handler[replay_start:replay_end]
        self.assertIn(
            "showThunderBreakerStandardEffect(chr, replaySkillId);", replay
        )
        self.assertNotIn("showThunderBreakerSpecialEffect", replay)

    def test_lightning_spear_stage_visual_always_plays_before_target_check(self) -> None:
        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        start = handler.index("private static void repeatTrackingCloseAttack(")
        end = handler.index("void scheduleTrackingCloseAttacks(", start)
        replay = handler[start:end]

        visual = replay.index(
            "showThunderBreakerStandardEffect(chr, replaySkillId);"
        )
        empty_target = replay.index("if (damage.isEmpty())")
        return_after_empty = replay.index("return;", empty_target)
        attack_packet = replay.index("PacketCreator.closeRangeAttack(")

        self.assertLess(visual, empty_target)
        self.assertLess(empty_target, return_after_empty)
        self.assertLess(return_after_empty, attack_packet)
        self.assertIn("replaySkillId,", replay)

    def test_shark_torpedo_is_removed_and_native_shark_wave_is_restored(self) -> None:
        client_path = ROOT / "clien/Data/Skill/1512.img"
        image = patch.engine.WzImage.from_bytes(
            client_path.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=client_path.name,
        )
        self.assertIsNone(image.parse().get("skill/15121001"))

        server_root = ET.parse(
            ROOT / "gms-server/wz/Skill.wz/1512.img.xml"
        ).getroot()
        self.assertIsNone(
            server_root.find("./imgdir[@name='skill']/imgdir[@name='15121001']")
        )

        source = (
            ROOT
            / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"
        ).read_text(encoding="utf-8")
        self.assertNotIn("15121001", source)
        self.assertNotIn("Shark Torpedo", source)

        handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java"
        ).read_text(encoding="utf-8")
        self.assertNotIn("SHARK_TORPEDO", handler)
        self.assertNotIn("handleSharkTorpedoAttack", handler)

        character = (
            ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
        ).read_text(encoding="utf-8")
        self.assertNotIn("ThunderBreaker.V_VI_ACTIVE_ATTACKS.length + 1", character)
        self.assertNotIn("ThunderBreaker.SHARK_WAVE;", character)

        original = ROOT / "clien/Data/Skill/1511.img.bak-thunder-breaker-v-vi"
        self.assertTrue(original.exists())
        self.assertEqual(original.read_bytes(), patch.CLIENT_LEGACY_SKILL.read_bytes())

    def test_lightning_spear_uses_supported_idle_attack_action(self) -> None:
        image = patch.engine.WzImage.from_bytes(
            (ROOT / "clien/Data/Skill/1512.img").read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name="1512.img",
        )
        root = image.parse()
        ids = set(range(15121002, 15121012)) | set(
            patch.LIGHTNING_SPEAR_COMBO_VISUAL_IDS
        )
        for skill_id in sorted(ids):
            with self.subTest(skill_id=skill_id):
                self.assertEqual(
                    "alert5", root.get(f"skill/{skill_id}/action/0").value
                )


if __name__ == "__main__":
    unittest.main()
