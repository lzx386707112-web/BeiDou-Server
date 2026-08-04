#!/usr/bin/env python3
"""Regression contracts for the Explorer warrior V/VI attack migration."""

from __future__ import annotations

import re
import shutil
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tool/client-video"))

import patch_explorer_warrior_v_vi as patch  # noqa: E402
import export_explorer_warrior_mcvs as video  # noqa: E402
import export_thunder_breaker_mcvs as mcv  # noqa: E402


HANDLER = (
    ROOT
    / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
)
RANGED_HANDLER = (
    ROOT
    / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java"
)
SUMMON_HANDLER = (
    ROOT
    / "gms-server/src/main/java/org/gms/net/server/channel/handlers/SummonDamageHandler.java"
)
HERO_CONSTANTS = ROOT / "gms-server/src/main/java/org/gms/constants/skills/Hero.java"
PALADIN_CONSTANTS = ROOT / "gms-server/src/main/java/org/gms/constants/skills/Paladin.java"
DLL = ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"
GRANT_SCRIPT = (
    ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/冒险家五六转攻击技能.js"
)


def source_multi_attack_times(skill_id: int) -> dict[int, list[int]]:
    root = ET.parse(patch.MS_EXPORT_ROOT / f"{skill_id}.xml").getroot()
    multi = next((node for node in root if node.get("name") == "multiAttackInfo"), None)
    if multi is None:
        raise RuntimeError(f"missing TMS multiAttackInfo: {skill_id}")
    elapsed = 0
    result: dict[int, list[int]] = {}
    entries = sorted(
        (node for node in multi if node.tag == "imgdir"),
        key=lambda node: int(node.get("name")),
    )
    for entry in entries:
        values = {node.get("name"): node for node in entry}
        elapsed += int(values["attackTime"].get("value"))
        stage = int(values.get("x", ET.Element("int", {"value": str(skill_id)})).get("value"))
        result.setdefault(stage, []).append(elapsed)
    return result


def java_int_array(source: str, name: str) -> list[int]:
    match = re.search(
        rf"private static final int\[\] {re.escape(name)}\s*=\s*\{{(.*?)\}};",
        source,
        re.DOTALL,
    )
    if match is None:
        raise RuntimeError(f"missing server attack timeline: {name}")
    return [int(value) for value in re.findall(r"\d+", match.group(1))]


class ExplorerWarriorPatchContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = HANDLER.read_text(encoding="utf-8")

    def test_only_attack_entries_are_visible_and_script_granted(self) -> None:
        expected = {
            "hero": {1121012, 1121013, 1121014, 1121020,
                     1121023, 1121025, 1121030},
            "paladin": {1221015, 1221016, 1221020, 1221027, 1221030},
            "darkKnight": {1321011, 1321015, 1321018, 1321020,
                           1321022, 1321025},
        }
        for job in patch.JOBS:
            with self.subTest(job=job.key):
                self.assertEqual(
                    expected[job.key],
                    {spec.target_id for spec in job.skills if not spec.hidden},
                )

        script = GRANT_SCRIPT.read_text(encoding="utf-8")
        for class_name in ("Hero", "Paladin", "DarkKnight"):
            self.assertIn(f"{class_name}\").V_VI_ACTIVE_ATTACKS", script)
        self.assertIn(
            "retiredBindings: [1121001, 1121016, 1121017, 1121018, 1121019, "
            "1121026, 1121027, 1121028, 1121029]",
            script,
        )
        self.assertIn("retiredSkills: [1121001]", script)
        self.assertIn(
            "retiredBindings: [1221013, 1221015, 1221016, 1221018, 1221020, "
            "1221023, 1221025, 1221027, 1221030]",
            script,
        )
        self.assertIn(
            "retiredSkills: [1221013, 1221014, 1221018, 1221019, 1221023, "
            "1221024, 1221025, 1221026]",
            script,
        )
        self.assertIn(
            "retiredBindings: [1321011, 1321012, 1321014, 1321015, 1321017, "
            "1321018, 1321020, 1321022, 1321023, 1321024, 1321025]",
            script,
        )
        self.assertIn(
            "retiredSkills: [1321012, 1321013, 1321014, 1321017, 1321023, 1321024]",
            script,
        )

    def test_tms_parameters_and_generated_resources_match(self) -> None:
        for job in patch.JOBS:
            with self.subTest(job=job.key):
                patch.configure(job)
                patch.validate_source_parameters()
                patch.validate_generated()

    def test_server_multi_attack_timelines_match_tms(self) -> None:
        mappings = {
            "SWORD_ILLUSION_SLASH_TIMES_MS": (400011125, 400011125),
            "SWORD_ILLUSION_EXPLOSION_TIMES_MS": (400011126, 400011126),
            "RAGE_UPRISING_VI_TIMES_MS": (1141002, 1141002),
            "SPIRIT_CALIBER_TIMES_MS": (1141500, 1141500),
            "SPIRIT_CALIBER_FINISH_TIMES_MS": (1141500, 1141501),
            "HEAVENS_HAMMER_VI_TIMES_MS": (1241007, 1241007),
            "SACRED_BASTION_TIMES_MS": (1241500, 1241500),
            "SACRED_BASTION_FINISH_TIMES_MS": (1241500, 1241503),
            "DOMINUS_OBRION_TIMES_MS": (1241504, 1241504),
            "DOMINUS_OBRION_FINISH_TIMES_MS": (1241504, 1241505),
            "DEAD_SPACE_TIMES_MS": (1341500, 1341500),
            "DEAD_SPACE_FINISH_TIMES_MS": (1341500, 1341501),
            "DARK_HALIDOM_TIMES_MS": (1341502, 1341502),
            "DARK_HALIDOM_FINISH_TIMES_MS": (1341502, 1341503),
        }
        for name, (skill_id, stage_id) in mappings.items():
            with self.subTest(name=name):
                self.assertEqual(
                    source_multi_attack_times(skill_id)[stage_id],
                    java_int_array(self.handler, name),
                )

        cyclone = source_multi_attack_times(400011069)[400011069]
        self.assertEqual(
            [4000 + time for time in cyclone],
            java_int_array(self.handler, "CALAMITOUS_CYCLONE_FINISH_TIMES_MS"),
        )

    def test_server_interval_timelines_use_tms_values(self) -> None:
        expected_calls = (
            "BURNING_SOUL_BLADE_TIMES_MS = intervalTimes(0, 1000, 19000)",
            "GRAND_GUARDIAN_TIMES_MS = intervalTimes(900, 150, 4800)",
            "SACRED_BASTION_FIELD_TIMES_MS = intervalTimes(420, 300, 29820)",
            "CALAMITOUS_CYCLONE_TIMES_MS = intervalTimes(0, 140, 3920)",
        )
        for expected in expected_calls:
            self.assertIn(expected, self.handler)
        self.assertEqual(
            [1170], java_int_array(self.handler, "MIGHTY_MJOLNIR_EXPLOSION_TIMES_MS")
        )
        self.assertEqual(
            [960, 1080, 1200, 1320],
            java_int_array(self.handler, "RISING_JUSTICE_TIMES_MS"),
        )

    def test_tracking_close_replays_only_use_stacked_attack_damage_numbers(self) -> None:
        repeat_start = self.handler.index("private static void repeatTrackingCloseAttack(")
        repeat_end = self.handler.index("\n    private void scheduleTrackingCloseAttacks(", repeat_start)
        repeat_block = self.handler[repeat_start:repeat_end]
        self.assertIn("PacketCreator.closeRangeAttack(", repeat_block)
        self.assertNotIn("PacketCreator.damageMonster(", repeat_block)

        schedule_start = repeat_end
        schedule_end = self.handler.index("\n    private static void repeatLightningSpearThunder(", schedule_start)
        schedule_block = self.handler[schedule_start:schedule_end]
        self.assertIn("applyAttack(attack, chr, originalEffect.getAttackCount())", schedule_block)
        self.assertNotIn("showCapturedDamageNumbers(attack, chr, expectedMap)", schedule_block)

    def test_hero_removed_swordsman_idea_and_uses_free_melee_id(self) -> None:
        hero = next(job for job in patch.JOBS if job.key == "hero")
        target_ids = {spec.target_id for spec in hero.skills}
        self.assertIn(1121020, target_ids)
        self.assertNotIn(1121028, target_ids)
        self.assertNotIn(1121029, target_ids)

        constants = HERO_CONSTANTS.read_text(encoding="utf-8")
        self.assertIn("SWORD_ILLUSION = 1121020", constants)
        self.assertNotIn("VALHALLA_VI", constants)
        self.assertNotIn("VALHALLA_VI_TIMES_MS", self.handler)

        patch.configure(hero)
        client = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        retired = (1121016, 1121017, 1121018, 1121019, 1121026, 1121027, 1121028, 1121029)
        for skill_id in retired:
            with self.subTest(skill_id=skill_id):
                self.assertIsNone(client.get(f"skill/{skill_id}"))
        server = patch.engine.SERVER_SKILL.read_text(encoding="utf-8")
        for skill_id in retired:
            with self.subTest(skill_id=skill_id):
                self.assertNotIn(f'<imgdir name="{skill_id}">', server)

        client_strings = patch.engine.WzImage.from_bytes(
            patch.CLIENT_STRING.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.CLIENT_STRING.name,
        ).parse()
        server_strings = patch.SERVER_STRING.read_text(encoding="utf-8")
        for skill_id in retired:
            with self.subTest(skill_id=skill_id, resource="string"):
                self.assertIsNone(client_strings.get(str(skill_id)))
                self.assertNotIn(f'<imgdir name="{skill_id}">', server_strings)

    def test_hero_visuals_are_flat_and_sword_illusion_starts_smoothly(self) -> None:
        hero = next(job for job in patch.JOBS if job.key == "hero")
        patch.configure(hero)
        image = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        )
        root = image.parse()
        for path in (
            "skill/1121015/effect",
            "skill/1121015/hit/0",
        ):
            with self.subTest(path=path):
                self.assertTrue(patch.engine.base.numeric_canvases(root.get(path)))

        sword_effect = root.get("skill/1121020/effect")
        frames = patch.engine.base.numeric_canvases(sword_effect)
        self.assertTrue(frames)
        self.assertLessEqual(patch.engine.base.frame_delay(frames[0]), 60)

        original_magnet = root.get("skill/1121001")
        self.assertIsNotNone(original_magnet.get("prepare"))
        self.assertIsNone(original_magnet.get("action"))

    def test_sword_illusion_long_sword_light_matches_tms(self) -> None:
        source = ET.parse(patch.MS_EXPORT_ROOT / "400011124.xml").getroot()
        effect0 = next(node for node in source if node.get("name") == "effect0")
        first_frame = next(node for node in effect0 if node.get("name") == "0")
        delay = next(node for node in first_frame if node.get("name") == "delay")
        self.assertEqual(1320, int(delay.get("value")))
        self.assertEqual(
            1320,
            source_multi_attack_times(400011125)[400011125][0],
        )
        hero = next(job for job in patch.JOBS if job.key == "hero")
        patch.configure(hero)
        root = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        first = patch.engine.base.numeric_canvases(root.get("skill/1121020/effect"))[0]
        self.assertLess(int(first.width), 800)

    def test_burning_soul_blade_uses_legacy_summon_states(self) -> None:
        hero = next(job for job in patch.JOBS if job.key == "hero")
        patch.configure(hero)
        root = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        skill = root.get("skill/1121014")
        for state in ("summoned", "stand", "attack1", "die"):
            with self.subTest(state=state):
                self.assertTrue(
                    patch.engine.base.numeric_canvases(skill.get(f"summon/{state}"))
                )
        self.assertTrue(patch.engine.base.numeric_canvases(skill.get("hit/0")))
        self.assertEqual(270, int(skill.get("summon/attack1/info/attackAfter").value))
        self.assertEqual(8, int(skill.get("summon/attack1/info/mobCount").value))

        self.assertIn("spawnTimedSummon(", self.handler)
        self.assertIn("Hero.BURNING_SOUL_BLADE,", self.handler)
        self.assertIn("SummonMovementType.STATIONARY,", self.handler)
        summon_handler = SUMMON_HANDLER.read_text(encoding="utf-8")
        self.assertIn("summon.getSkill() == Hero.BURNING_SOUL_BLADE", summon_handler)

    def test_dark_knight_retired_skills_are_removed(self) -> None:
        patch.configure(next(job for job in patch.JOBS if job.key == "darkKnight"))
        root = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        server = patch.engine.SERVER_SKILL.read_text(encoding="utf-8")
        client_strings = patch.engine.WzImage.from_bytes(
            patch.CLIENT_STRING.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.CLIENT_STRING.name,
        ).parse()
        server_strings = patch.SERVER_STRING.read_text(encoding="utf-8")
        for skill_id in (1321012, 1321013, 1321014, 1321017, 1321023, 1321024):
            with self.subTest(skill_id=skill_id):
                self.assertIsNone(root.get(f"skill/{skill_id}"))
                self.assertNotIn(f'<imgdir name="{skill_id}">', server)
                self.assertIsNone(client_strings.get(str(skill_id)))
                self.assertNotIn(f'<imgdir name="{skill_id}">', server_strings)

        constants = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/DarkKnight.java").read_text(
            encoding="utf-8"
        )
        for name in (
            "DARKNESS_AURA", "BEHOLDER_IMPACT", "GUNGNIRS_DESCENT_VI",
            "BEHOLDER_SHOCK_VI", "BEHOLDER_SHOCK_VI_PROJECTILE",
        ):
            self.assertNotIn(name, constants)
        self.assertNotIn("DARKNESS_AURA_TIMES_MS", self.handler)
        self.assertNotIn("BEHOLDER_IMPACT_TIMES_MS", self.handler)
        self.assertNotIn("BEHOLDER_SHOCK_VI_TIMES_MS", self.handler)
        self.assertNotIn("BEHOLDER_SHOCK_VI_PROJECTILE_TIMES_MS", self.handler)

    def test_dark_knight_problem_visuals_match_tms(self) -> None:
        patch.configure(next(job for job in patch.JOBS if job.key == "darkKnight"))
        root = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()

        self.assertIsNone(root.get("skill/1321011/ball"))
        self.assertTrue(
            patch.engine.base.numeric_canvases(root.get("skill/1321011/effect"))
        )

        spear = patch.engine.base.numeric_canvases(root.get("skill/1321011/effect"))
        self.assertEqual(
            1410,
            sum(patch.engine.base.frame_delay(frame) for frame in spear),
        )
        self.assertTrue(any(int(frame.width) > 1200 for frame in spear))

        synthesis = patch.engine.base.numeric_canvases(
            root.get("skill/1321022/effect")
        )
        self.assertTrue(any(int(frame.height) == 720 for frame in synthesis))

        halidom = patch.engine.base.numeric_canvases(
            root.get("skill/1321025/effect")
        )
        self.assertEqual(
            2460,
            sum(patch.engine.base.frame_delay(frame) for frame in halidom),
        )
        for skill_id in (1321011, 1321022, 1321025):
            frames = patch.engine.base.numeric_canvases(
                root.get(f"skill/{skill_id}/effect")
            )
            self.assertTrue(all(int(frame.width) <= 1280 for frame in frames))
            self.assertTrue(all(int(frame.height) <= 720 for frame in frames))

    def test_paladin_problem_visuals_match_tms_and_legacy_nodes(self) -> None:
        patch.configure(next(job for job in patch.JOBS if job.key == "paladin"))
        root = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()

        expected_effects = {
            1221015: (None, 5860),
            1221016: (32, 1290),
            1221029: (18, 1080),
            1221030: (40, 2760),
        }
        for skill_id, (frame_count, duration) in expected_effects.items():
            with self.subTest(skill_id=skill_id, visual="effect_timeline"):
                frames = patch.engine.base.numeric_canvases(
                    root.get(f"skill/{skill_id}/effect")
                )
                if frame_count is not None:
                    self.assertEqual(frame_count, len(frames))
                self.assertEqual(
                    duration,
                    sum(patch.engine.base.frame_delay(frame) for frame in frames),
                )

        for skill_id in (1221029,):
            with self.subTest(skill_id=skill_id, visual="legacy_projectile"):
                self.assertIsNone(root.get(f"skill/{skill_id}/ball"))

        for skill_id in (1221016, 1221030):
            with self.subTest(skill_id=skill_id, visual="baked_special"):
                self.assertIsNone(root.get(f"skill/{skill_id}/special"))

        grand_hit = patch.engine.base.numeric_canvases(root.get("skill/1221015/hit/0"))
        self.assertEqual(8, len(grand_hit))
        self.assertEqual(
            480,
            sum(patch.engine.base.frame_delay(frame) for frame in grand_hit),
        )
        repeated_hit = patch.engine.base.numeric_canvases(root.get("skill/1221032/hit/0"))
        self.assertEqual(8, len(repeated_hit))
        self.assertIsNone(root.get("skill/1221032/effect"))

        self.assertIsNone(root.get("skill/1221016/ball"))
        self.assertIsNone(root.get("skill/1221016/level/30/bulletCount"))
        self.assertIsNone(root.get("skill/1221016/level/30/ball"))
        self.assertIsNone(root.get("skill/1221017/effect"))
        self.assertTrue(
            patch.engine.base.numeric_canvases(root.get("skill/1221017/hit/0"))
        )
        expected_mjolnir_states = {
            "summoned": (16, 1170),
            "stand": (1, 60),
            "die": (17, 1020),
        }
        for state, (count, duration) in expected_mjolnir_states.items():
            frames = patch.engine.base.numeric_canvases(
                root.get(f"skill/1221016/summon/{state}")
            )
            self.assertEqual(count, len(frames))
            self.assertEqual(
                duration,
                sum(patch.engine.base.frame_delay(frame) for frame in frames),
            )

    def test_paladin_retired_skills_are_removed(self) -> None:
        patch.configure(next(job for job in patch.JOBS if job.key == "paladin"))
        root = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        server = patch.engine.SERVER_SKILL.read_text(encoding="utf-8")
        client_strings = patch.engine.WzImage.from_bytes(
            patch.CLIENT_STRING.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.CLIENT_STRING.name,
        ).parse()
        server_strings = patch.SERVER_STRING.read_text(encoding="utf-8")
        retired = (
            1221013, 1221014, 1221018, 1221019,
            1221023, 1221024, 1221025, 1221026,
        )
        for skill_id in retired:
            with self.subTest(skill_id=skill_id):
                self.assertIsNone(root.get(f"skill/{skill_id}"))
                self.assertNotIn(f'<imgdir name="{skill_id}">', server)
                self.assertIsNone(client_strings.get(str(skill_id)))
                self.assertNotIn(f'<imgdir name="{skill_id}">', server_strings)

        constants = PALADIN_CONSTANTS.read_text(encoding="utf-8")
        self.assertNotIn("HAMMERS_OF_THE_RIGHTEOUS", constants)
        self.assertNotIn("HAMMERS_OF_THE_RIGHTEOUS", self.handler)
        for name in (
            "BLAST_VI", "DIVINE_JUDGMENT_VI", "DIVINE_CHARGE_VI",
            "DIVINE_BRAND_VI", "JUSTICE_JUDGMENT", "JUSTICE_JUDGMENT_HIT",
        ):
            self.assertNotIn(name, constants)

    def test_paladin_cooldowns_match_requested_values(self) -> None:
        job = next(job for job in patch.JOBS if job.key == "paladin")
        patch.configure(job)
        client = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        server = ET.parse(patch.engine.SERVER_SKILL).getroot()
        for spec in job.skills:
            expected = 10 if spec.target_id in {1221020, 1221030} else 0
            with self.subTest(skill_id=spec.target_id):
                self.assertEqual(expected, spec.cooldown)
                self.assertEqual(
                    expected,
                    int(client.get(f"skill/{spec.target_id}/level/30/cooltime").value),
                )
                server_value = server.find(
                    f"./imgdir[@name='skill']/imgdir[@name='{spec.target_id}']/"
                    "imgdir[@name='level']/imgdir[@name='30']/int[@name='cooltime']"
                )
                self.assertEqual(expected, int(server_value.get("value")))

    def test_dark_knight_cooldowns_match_requested_values(self) -> None:
        job = next(job for job in patch.JOBS if job.key == "darkKnight")
        patch.configure(job)
        client = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        ).parse()
        server = ET.parse(patch.engine.SERVER_SKILL).getroot()
        for spec in job.skills:
            expected = 10 if spec.target_id in {1321018, 1321025} else 0
            with self.subTest(skill_id=spec.target_id):
                self.assertEqual(expected, spec.cooldown)
                self.assertEqual(
                    expected,
                    int(client.get(f"skill/{spec.target_id}/level/30/cooltime").value),
                )
                server_value = server.find(
                    f"./imgdir[@name='skill']/imgdir[@name='{spec.target_id}']/"
                    "imgdir[@name='level']/imgdir[@name='30']/int[@name='cooltime']"
                )
                self.assertEqual(expected, int(server_value.get("value")))

    def test_mcv_outputs_match_source_timeline_and_have_alpha(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg)
        for spec in video.EFFECTS:
            with self.subTest(effect=spec.key):
                tracks = video.load_tracks(spec, video.DEFAULT_SOURCE)
                segments = video.timeline(tracks)
                output = ROOT / "clien/Data/Video" / spec.output
                parsed = mcv.parse_mcv(output.read_bytes())
                self.assertEqual((video.WIDTH, video.HEIGHT), (parsed.width, parsed.height))
                self.assertEqual(len(segments), len(parsed.delays))
                self.assertEqual(segments[-1][1], sum(parsed.delays))
                self.assertEqual(len(parsed.color_packets), len(parsed.alpha_packets))
                left, top, right, bottom = mcv.output_alpha_union_bounds(output, ffmpeg)
                self.assertGreater(right, left)
                self.assertGreater(bottom, top)
                if spec.cover_field:
                    self.assertLessEqual(left, 2)
                    self.assertLessEqual(top, 2)
                    self.assertGreaterEqual(right, 1278)
                    self.assertGreaterEqual(bottom, 718)

    def test_dll_maps_every_origin_to_its_mcv(self) -> None:
        source = DLL.read_text(encoding="utf-8")
        mappings = {
            1121023: "spirit-caliber.mcv",
            1221020: "sacred-bastion.mcv",
            1221030: "dominus-obrion.mcv",
            1321018: "dead-space.mcv",
            1321025: "dark-halidom.mcv",
        }
        for skill_id, filename in mappings.items():
            self.assertIn(f'{{{skill_id}, "Data\\\\Video\\\\{filename}"', source)

    def test_dll_routes_all_migrated_hero_stages_as_brandish(self) -> None:
        source = DLL.read_text(encoding="utf-8")
        functions = {
            "HookActiveSkillDispatch": "esi",
            "HookHighSkillVisualBranch": "esi",
            "HookBrandishActionType": "eax",
            "HookBrandishVisualOffset": "eax",
            "HookBrandishStateSwitch": "esi",
            "HookBrandishHit": "ebx",
        }
        for name, register in functions.items():
            with self.subTest(hook=name):
                start = source.index(f"void {name}()")
                end = source.index("\n}\n", start)
                block = source[start:end]
                self.assertIn(f'cmp {register}, 1121012\\n', block)
                self.assertIn(f'cmp {register}, 1121030\\n', block)

    def test_dll_routes_paladin_and_dark_knight_stages_as_melee(self) -> None:
        source = DLL.read_text(encoding="utf-8")
        start = source.index("void HookActiveSkillDispatch()")
        end = source.index("\n}\n", start)
        block = source[start:end]
        for first, last in ((1221015, 1221032), (1321011, 1321026)):
            self.assertIn(f'cmp esi, {first}\\n', block)
            self.assertRegex(
                block,
                rf'cmp esi, {last}\\n"\s*"jbe explorer_melee_active\\n',
            )

        visual_start = source.index("void HookHighSkillVisualBranch()")
        visual_end = source.index("\n}\n", visual_start)
        visual = source[visual_start:visual_end]
        self.assertIn('cmp esi, 1221015\\n', visual)
        self.assertNotIn('cmp esi, 1221013\\n', visual)
        self.assertIn('cmp esi, 1221032\\n', visual)

        self.assertNotIn('cmp esi, 1221016\\n', block)
        self.assertNotIn("case 1221016: return 4;", source)
        self.assertNotRegex(
            source,
            r"(?s)case 1221016:\s+gNightWalkerProjectileProfile",
        )

        ranged = RANGED_HANDLER.read_text(encoding="utf-8")
        self.assertNotIn("Paladin.MIGHTY_MJOLNIR", ranged)
        self.assertNotIn("Paladin.MIGHTY_MJOLNIR_EXPLOSION", ranged)
        self.assertIn("spawnMightyMjolnirProjectiles(attack, chr)", self.handler)
        self.assertIn("projectileCount >= 4", self.handler)

    def test_hero_cooldown_overrides_match_client_and_server(self) -> None:
        expected = {
            1121012: 0,
            1121013: 0,
            1121014: 0,
            1121020: 0,
            1121023: 10,
            1121025: 0,
            1121030: 0,
        }
        hero = next(job for job in patch.JOBS if job.key == "hero")
        patch.configure(hero)
        image = patch.engine.WzImage.from_bytes(
            patch.engine.CLIENT_SKILL.read_bytes(),
            key=patch.engine.WzKey.for_region("GMS"),
            name=patch.engine.CLIENT_SKILL.name,
        )
        client = image.parse()
        server = ET.parse(
            ROOT / "gms-server/wz/Skill.wz/112.img.xml"
        ).getroot()
        for skill_id, cooldown in expected.items():
            with self.subTest(skill_id=skill_id):
                client_value = client.get(f"skill/{skill_id}/level/30/cooltime")
                self.assertEqual(cooldown, int(client_value.value))
                server_value = server.find(
                    f"./imgdir[@name='skill']/imgdir[@name='{skill_id}']/"
                    "imgdir[@name='level']/imgdir[@name='30']/int[@name='cooltime']"
                )
                self.assertIsNotNone(server_value)
                self.assertEqual(cooldown, int(server_value.get("value")))


if __name__ == "__main__":
    unittest.main()
