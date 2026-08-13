#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
CLIENT_VIDEO = ROOT / "tool" / "client-video"
WZPY = ROOT / "tool" / "wz-python"
sys.path[:0] = [str(PATCH_SKILL), str(CLIENT_VIDEO), str(WZPY)]

import patch_explorer_other_v_vi as migration  # noqa: E402
from export_thunder_breaker_mcvs import (  # noqa: E402
    output_alpha_union_bounds,
    parse_mcv,
    start_decoder,
)
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty, WzUolProperty  # noqa: E402


CLASS_FILES = {
    "fpArchMage": "FPArchMage.java",
    "ilArchMage": "ILArchMage.java",
    "bishop": "Bishop.java",
    "bowmaster": "Bowmaster.java",
    "marksman": "Marksman.java",
    "nightLord": "NightLord.java",
    "shadower": "Shadower.java",
    "buccaneer": "Buccaneer.java",
    "corsair": "Corsair.java",
}

DISPATCH_RANGES = {
    212: (2121009, 2121036, "explorer_magic_active"),
    222: (2221009, 2221031, "explorer_magic_active"),
    232: (2321020, 2321043, "explorer_bishop_magic_active"),
    312: (3121010, 3121033, "explorer_ranged_active"),
    322: (3221009, 3221035, "explorer_ranged_active"),
    412: (4121010, 4121029, "explorer_ranged_active"),
    422: (4221009, 4221029, "explorer_melee_active"),
    512: (5121011, 5121036, "explorer_melee_active"),
    522: (5221011, 5221035, "explorer_ranged_active"),
}

MCV_DURATIONS_MS = {
    2121032: 6660, 2121035: 4860,
    2221027: 5520, 2221030: 2520,
    2321037: 4380, 2321042: 3870,
    3121029: 4560, 3121031: 1560,
    3221032: 7980, 3221034: 3000,
    4121026: 3780, 4121028: 2760,
    4221023: 3360, 4221027: 960,
    5121015: 4890, 5121029: 5100, 5121035: 2340,
    5221012: 1780, 5221032: 4740, 5221034: 2460,
}


class ExplorerOtherPatchContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = migration.build_runtime_jobs()

    def test_active_attack_arrays_match_generated_resources(self):
        constants = ROOT / "gms-server/src/main/java/org/gms/constants/skills"
        for job in self.jobs:
            text = (constants / CLASS_FILES[job.config.key]).read_text(encoding="utf-8")
            block = re.search(r"V_VI_ACTIVE_ATTACKS\s*=\s*\{([^}]*)}", text, re.S)
            self.assertIsNotNone(block, job.config.key)
            actual = [int(value) for value in re.findall(r"\d+", block.group(1))]
            expected = [spec.target_id for spec in job.skills if not spec.hidden]
            self.assertEqual(expected, actual, job.config.key)

    def test_server_level_30_parameters_match_specs(self):
        for job in self.jobs:
            root = ET.parse(
                ROOT / f"gms-server/wz/Skill.wz/{job.config.book}.img.xml"
            ).getroot()
            skills = root.find("./imgdir[@name='skill']")
            for spec in job.skills:
                node = skills.find(f"./imgdir[@name='{spec.target_id}']")
                self.assertIsNotNone(node, spec.target_id)
                level = node.find("./imgdir[@name='level']/imgdir[@name='30']")
                values = {child.get("name"): child for child in level}
                self.assertEqual(spec.damage, int(values["damage"].get("value")))
                self.assertEqual(spec.attack_count, int(values["attackCount"].get("value")))
                self.assertEqual(spec.mob_count, int(values["mobCount"].get("value")))
                self.assertEqual(spec.mp_con, int(values["mpCon"].get("value")))
                self.assertEqual(spec.cooldown, int(values["cooltime"].get("value")))
                actual_duration = (int(values["time"].get("value"))
                                   if "time" in values else None)
                self.assertEqual(spec.duration_seconds, actual_duration, spec.target_id)

    def test_renderable_source_hits_survive_client_conversion(self):
        for job in self.jobs:
            path = ROOT / f"clien/Data/Skill/{job.config.book}.img"
            image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
            root = image.parse()
            for spec in job.skills:
                node = root.get(f"skill/{spec.target_id}")
                self.assertIsInstance(node, WzSubProperty)
                if spec.include_hit:
                    frames = migration.engine.base.numeric_canvases(node.get("hit/0"))
                    self.assertTrue(frames, spec.target_id)

    def test_actions_and_all_copied_canvases_are_renderable(self):
        for job in self.jobs:
            path = ROOT / f"clien/Data/Skill/{job.config.book}.img"
            image = WzImage.from_bytes(
                path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
            )
            root = image.parse()
            for spec in job.skills:
                node = root.get(f"skill/{spec.target_id}")
                self.assertEqual(migration.legacy_action(job, spec), node.get("action/0").value)
                canvas_count = 0
                decoded_representative = False
                stack = [node]
                while stack:
                    current = stack.pop()
                    if isinstance(current, WzCanvasProperty):
                        canvas_count += 1
                        self.assertLessEqual(current.width, 1280, spec.target_id)
                        self.assertLessEqual(current.height, 720, spec.target_id)
                        if not decoded_representative:
                            decoded_representative = (
                                decode_canvas(current, region="GMS").getbbox() is not None
                            )
                    if hasattr(current, "children"):
                        stack.extend(current.children())
                self.assertGreater(canvas_count, 0, spec.target_id)
                self.assertTrue(decoded_representative, spec.target_id)

    def test_dll_dispatches_every_migrated_node_by_attack_type(self):
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        start = cpp.index("void HookActiveSkillDispatch()")
        end = cpp.index("\n}\n", start)
        dispatch = cpp[start:end]
        for job in self.jobs:
            first, last, branch = DISPATCH_RANGES[job.config.book]
            self.assertIn(f'cmp esi, {first}\\n', dispatch)
            self.assertIn(f'cmp esi, {last}\\n', dispatch)
            self.assertRegex(
                dispatch,
                rf'cmp esi, {last}\\n"\s*"jbe {branch}\\n',
                job.config.key,
            )
        for branch, address in {
            "explorer_melee_active": "0x009690AE",
            "explorer_magic_active": "0x0096928B",
            "explorer_ranged_active": "0x009690E9",
        }.items():
            branch_start = dispatch.index(f'"{branch}:\\n"')
            block = dispatch[branch_start:branch_start + 320]
            self.assertIn('call _StartVideoSkill\\n', block)
            self.assertIn(f'push {address}\\n', block)

    def test_dll_ranged_target_limits_match_active_specs(self):
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for job in self.jobs:
            if job.config.book not in (312, 322, 412, 522):
                continue
            first, last, _ = DISPATCH_RANGES[job.config.book]
            self.assertIn(f"skillId >= {first} && skillId <= {last}", cpp)
            for spec in job.skills:
                if not spec.hidden:
                    self.assertIn(
                        f"case {spec.target_id}: return {spec.mob_count};", cpp
                    )

    def test_flash_mirage_uses_native_per_projectile_targets(self):
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        arm_start = cpp.index("void ArmNightWalkerProjectiles(int skillId)")
        arm_end = cpp.index("\n}\n", arm_start)
        arm = cpp[arm_start:arm_end]
        self.assertRegex(
            arm,
            r"case 13121003:\s+case 3121026:[\s\S]*?"
            r"gNativeRangedProjectileWindowEnd = GetTickCount\(\) \+ 1200;",
        )

        dispatch_start = cpp.index("void HookActiveSkillDispatch()")
        dispatch_end = cpp.index("\n}\n", dispatch_start)
        dispatch = cpp[dispatch_start:dispatch_end]
        self.assertIn('cmp esi, 3121026\\n"\n        "je explorer_bowmaster_flash_mirage_active\\n', dispatch)
        branch_start = dispatch.index('"explorer_bowmaster_flash_mirage_active:\\n"')
        branch_end = dispatch.index('"explorer_ranged_active:\\n"', branch_start)
        branch = dispatch[branch_start:branch_end]
        self.assertIn('call _ArmNightWalkerProjectiles\\n', branch)
        generic = dispatch[branch_end:]
        self.assertNotIn('call _ArmNightWalkerProjectiles\\n', generic)

    def test_overloaded_tms_time_fields_use_legacy_seconds(self):
        expected = {
            2221014: 40,
            5221012: None,
            5221013: None,
        }
        specs = {spec.target_id: spec for job in self.jobs for spec in job.skills}
        for skill_id, duration in expected.items():
            self.assertEqual(duration, specs[skill_id].duration_seconds, skill_id)

    def test_retired_bowmaster_skills_are_absent_without_shifting_later_ids(self):
        job = next(job for job in self.jobs if job.config.key == "bowmaster")
        self.assertTrue(migration.BOWMASTER_RETIRED_SOURCE_IDS.isdisjoint(job.target_by_source))
        self.assertEqual(3140010, job.source_by_target[3121018])
        self.assertEqual(3141002, job.source_by_target[3121022])
        self.assertEqual(3141012, job.source_by_target[3121025])
        self.assertEqual(3141500, job.source_by_target[3121029])
        self.assertEqual(400031002, job.source_by_target[3121033])
        self.assertTrue(next(
            spec.hidden for spec in job.skills if spec.target_id == 3121033
        ))
        self.assertNotIn(400031028, job.target_by_source)
        self.assertNotIn(400031029, job.target_by_source)

        client_path = ROOT / "clien/Data/Skill/312.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            string_path.read_bytes(), key=WzKey.for_region("GMS"), name=string_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/312.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        for skill_id in migration.BOWMASTER_RETIRED_SKILL_IDS:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)

        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for skill_id in migration.BOWMASTER_RETIRED_SKILL_IDS:
            self.assertIn(
                f'cmp esi, {skill_id}\\n"\n        "je explorer_bowmaster_active_next',
                cpp,
            )
        self.assertIn("&& !retiredBowmasterSkill", cpp)

    def test_removed_night_lord_skills_are_retired_without_shifting_later_ids(self):
        job = next(job for job in self.jobs if job.config.key == "nightLord")
        self.assertTrue(
            migration.NIGHT_LORD_RETIRED_SOURCE_IDS.isdisjoint(job.target_by_source)
        )
        self.assertEqual(400041038, job.source_by_target[4121012])
        self.assertEqual(4141000, job.source_by_target[4121016])
        self.assertEqual(4141001, job.source_by_target[4121017])

        client_path = ROOT / "clien/Data/Skill/412.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            string_path.read_bytes(), key=WzKey.for_region("GMS"), name=string_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/412.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        for skill_id in migration.NIGHT_LORD_RETIRED_SKILL_IDS:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)

    def test_night_lord_origin_mcvs_and_damage_replays_match_tms(self):
        job = next(job for job in self.jobs if job.config.key == "nightLord")
        specs = {spec.target_id: spec for spec in job.skills}
        expected = {
            4121026: (4141500, 1180, 7, 15, 1200, 360),
            4121027: (4141501, 1158, 7, 15, 0, 0),
            4121028: (4141503, 7325, 13, 15, 1000, 240),
            4121029: (4141504, 8167, 15, 15, 0, 0),
        }
        for skill_id, values in expected.items():
            spec = specs[skill_id]
            self.assertEqual(
                values,
                (
                    spec.source_id,
                    spec.damage,
                    spec.attack_count,
                    spec.mob_count,
                    spec.mp_con,
                    spec.cooldown,
                ),
                skill_id,
            )

        client_path = ROOT / "clien/Data/Skill/412.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/412.img.xml").getroot()
        for skill_id, (_, damage, attack_count, mob_count, mp_con, cooldown) in expected.items():
            client_level = client.get(f"skill/{skill_id}/level/30")
            server_level = server.find(
                f"./imgdir[@name='skill']/imgdir[@name='{skill_id}']"
                "/imgdir[@name='level']/imgdir[@name='30']"
            )
            for name, value in (
                ("damage", damage),
                ("attackCount", attack_count),
                ("mobCount", mob_count),
                ("mpCon", mp_con),
                ("cooltime", cooldown),
            ):
                self.assertEqual(value, int(client_level.get(name).value), (skill_id, name))
                self.assertEqual(
                    value,
                    int(server_level.find(f"./int[@name='{name}']").get("value")),
                    (skill_id, name),
                )

        self.assertEqual(
            {
                4121026: (
                    *range(1440, 2010, 30),
                    *range(2310, 2550, 30),
                    2580, 2610, 2640, 2760, 2880, 3000,
                )
            },
            migration.multi_attack_schedule(job, specs[4121026]),
        )
        self.assertEqual(
            {
                4121028: tuple(range(420, 720, 30)),
                4121029: tuple(range(1860, 2220, 30)),
            },
            migration.multi_attack_schedule(job, specs[4121028]),
        )

        for source_id, video_count in ((4141500, 1), (4141503, 3)):
            source = ET.parse(migration.MS_EXPORT_ROOT / f"{source_id}.xml").getroot()
            self.assertEqual(video_count, len(list(source.iter("video"))), source_id)
        for skill_id, frame_count, duration in (
            (4121026, 63, 3780),
            (4121028, 46, 2760),
        ):
            track = parse_mcv(
                (ROOT / f"clien/Data/Video/explorer-{skill_id}.mcv").read_bytes()
            )
            self.assertEqual((1280, 720), (track.width, track.height), skill_id)
            self.assertEqual(frame_count, len(track.delays), skill_id)
            self.assertEqual(duration, sum(track.delays), skill_id)

        handler = (ROOT / (
            "gms-server/src/main/java/org/gms/net/server/channel/handlers/"
            "RangedAttackHandler.java"
        )).read_text(encoding="utf-8")
        compat = (ROOT / (
            "gms-server/src/main/java/org/gms/constants/skills/"
            "ExplorerOtherSkillCompat.java"
        )).read_text(encoding="utf-8")
        cpp = (ROOT / (
            "tool/client-debug/dawn-warrior-skill-compat/"
            "DawnWarriorSkillCompat.cpp"
        )).read_text(encoding="utf-8")
        effect_path = ROOT / "clien/Data/Map/Effect.img"
        effect_image = WzImage.from_bytes(
            effect_path.read_bytes(), key=WzKey.for_region("GMS"), name=effect_path.name
        )
        effect = effect_image.parse()
        self.assertFalse(effect_image.truncated)
        self.assertFalse(effect_image.parse_warnings)
        for skill_id in (4121026, 4121028):
            self.assertIsNotNone(effect.get(f"customSkill/nightLord/video{skill_id}"))
            self.assertIn(
                f'{{{skill_id}, "Data\\\\Video\\\\explorer-{skill_id}.mcv"',
                cpp,
            )
        self.assertIn(
            'case 4121026, 4121028 -> "customSkill/nightLord/video" + skillId;',
            compat,
        )
        self.assertIn("chr.sendPacket(PacketCreator.showEffect(explorerVideoLayer));", handler)
        replay = handler[
            handler.index("private static void repeatTrackingAttack("):
            handler.index("private static boolean replayTargetedAttack(")
        ]
        self.assertIn("chr.sendPacket(packet);", replay)
        self.assertIn("expectedMap.broadcastMessage(chr, packet, false, true);", replay)
        self.assertIn("chr.sendPacket(PacketCreator.damageMonster(", replay)
        self.assertIn("ExplorerOtherSkillCompat.multiAttacks(skillId) != null", handler)
        self.assertIn("applyAttackCostOnly(attack, chr, bulletCount);", handler)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MCV pixel checks")
    def test_night_lord_origin_mcvs_cover_the_full_screen(self):
        ffmpeg = shutil.which("ffmpeg")
        for skill_id in (4121026, 4121028):
            path = ROOT / f"clien/Data/Video/explorer-{skill_id}.mcv"
            self.assertEqual(
                (0, 0, 1280, 720),
                output_alpha_union_bounds(path, ffmpeg),
                skill_id,
            )

        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for skill_id in migration.NIGHT_LORD_RETIRED_SKILL_IDS:
            self.assertIn(
                f'cmp esi, {skill_id}\\n"\n        "je explorer_night_lord_active_next',
                cpp,
            )
        self.assertIn("&& !retiredNightLordSkill", cpp)

    def test_night_lord_all_levels_match_tms_parameters(self):
        job = next(job for job in self.jobs if job.config.key == "nightLord")
        migration.configure(job)
        client_path = ROOT / "clien/Data/Skill/412.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"),
            name=client_path.name,
        ).parse()
        server_skills = ET.parse(
            ROOT / "gms-server/wz/Skill.wz/412.img.xml"
        ).getroot().find("./imgdir[@name='skill']")
        for spec in job.skills:
            for level in range(1, migration.MASTER_LEVEL + 1):
                expected = migration.level_parameters(spec, level)
                client_level = client.get(
                    f"skill/{spec.target_id}/level/{level}"
                )
                server_level = server_skills.find(
                    f"./imgdir[@name='{spec.target_id}']"
                    f"/imgdir[@name='level']/imgdir[@name='{level}']"
                )
                for name in (
                    "damage", "attackCount", "mobCount", "mpCon", "cooltime"
                ):
                    self.assertEqual(
                        expected[name], int(client_level.get(name).value),
                        (spec.target_id, level, name, "client"),
                    )
                    self.assertEqual(
                        expected[name],
                        int(server_level.find(f"./int[@name='{name}']").get("value")),
                        (spec.target_id, level, name, "server"),
                    )

    def test_night_lord_projectiles_hits_and_summons_match_tms_projection(self):
        job = next(job for job in self.jobs if job.config.key == "nightLord")
        migration.configure(job)
        client_path = ROOT / "clien/Data/Skill/412.img"
        image = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"),
            name=client_path.name,
        )
        client = image.parse()
        self.assertFalse(image.truncated)
        self.assertFalse(image.parse_warnings)

        for skill_id in migration.NIGHT_LORD_CLIENT_REPLACEMENT_IDS:
            skill = client.get(f"skill/{skill_id}")
            for property_name in ("weapon", "weapon2", "subWeapon"):
                self.assertIsNone(
                    skill.get(property_name),
                    (skill_id, property_name, "wrong client weapon restriction"),
                )

        expected_projectiles = {
            4121016: 16,
            4121017: 16,
            4121019: 7,
            4121020: 7,
            4121026: 6,
            4121027: 6,
        }
        for skill_id, frame_count in expected_projectiles.items():
            ball = client.get(f"skill/{skill_id}/ball")
            frames = migration.engine.base.numeric_canvases(ball)
            self.assertEqual(frame_count, len(frames), skill_id)
            for frame in frames:
                self.assertEqual((1, 0), (frame.format, frame.format2), skill_id)
                self.assertIsNotNone(
                    decode_canvas(frame, region="GMS").getchannel("A").getbbox(),
                    (skill_id, frame.name),
                )

            for level in range(1, migration.MASTER_LEVEL + 1):
                link = client.get(f"skill/{skill_id}/level/{level}/ball")
                self.assertIsInstance(link, WzUolProperty, (skill_id, level))
                self.assertEqual("../../ball", link.value, (skill_id, level))

        fuma = client.get("skill/4121011")
        effect = migration.engine.base.numeric_canvases(fuma.get("effect"))
        self.assertEqual(13, len(effect))
        self.assertEqual([60] * 13, [
            migration.engine.base.frame_delay(frame) for frame in effect
        ])
        self.assertEqual(780, sum(
            migration.engine.base.frame_delay(frame) for frame in effect
        ))
        ball = fuma.get("ball")
        ball_frames = sorted(
            (child for child in ball.children() if child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        self.assertEqual(6, len(ball_frames))
        self.assertEqual([60] * 6, [
            migration.engine.base.frame_delay(frame) for frame in ball_frames
        ])
        self.assertEqual(360, sum(
            migration.engine.base.frame_delay(frame) for frame in ball_frames
        ))
        hold = fuma.get("fumaHold")
        logical_frames = sorted(
            (child for child in hold.children() if child.name.isdigit()),
            key=lambda child: int(child.name),
        )
        self.assertEqual(68, len(logical_frames))
        logical_delays = []
        for frame in logical_frames:
            source = frame
            if isinstance(frame, WzUolProperty):
                source = hold.child(str(frame.value))
            self.assertIsInstance(source, WzCanvasProperty, frame.name)
            logical_delays.append(migration.engine.base.frame_delay(source))
        self.assertEqual([40] * 50, logical_delays[:50])
        self.assertEqual([60] * 18, logical_delays[50:])
        self.assertEqual(3080, sum(logical_delays))
        for frame in (
            *migration.engine.base.numeric_canvases(ball),
            *migration.engine.base.numeric_canvases(hold),
        ):
            self.assertEqual((1, 0), (frame.format, frame.format2), frame.name)
            self.assertIsNotNone(
                decode_canvas(frame, region="GMS").getchannel("A").getbbox(),
                (frame.name, "transparent Fuma projectile frame"),
            )
        for level in range(1, migration.MASTER_LEVEL + 1):
            link = fuma.get(f"level/{level}/ball")
            self.assertIsInstance(link, WzUolProperty, level)
            self.assertEqual("../../ball", link.value, level)

        groups, _, metadata = migration.engine.load_sources()
        tms_track = migration.engine.tracks(
            groups, metadata, 4141001, "shootobj/layerList/b1"
        )[0]
        self.assertEqual(16, len(tms_track))
        expected_geometry = [
            (
                frame.width,
                frame.height,
                migration.engine.base.canvas_origin(frame, meta),
                migration.engine.base.frame_delay(frame, meta),
            )
            for frame, meta in tms_track
        ]
        for skill_id in (4121016, 4121017):
            frames = migration.engine.base.numeric_canvases(
                client.get(f"skill/{skill_id}/ball")
            )
            actual_geometry = [
                (
                    frame.width,
                    frame.height,
                    migration.engine.base.canvas_origin(frame),
                    migration.engine.base.frame_delay(frame),
                )
                for frame in frames
            ]
            self.assertEqual(expected_geometry, actual_geometry, skill_id)
            self.assertEqual([60] * 16, [value[3] for value in actual_geometry])
            self.assertEqual(960, sum(value[3] for value in actual_geometry))

        hit_metadata = {
            4121011: {"randomHitOrigin": 25},
            4121016: {"randomHitOrigin": 30, "useZ": 1, "z": 1},
            4121019: {"onlyOnce": 1, "randomHitOrigin": 30, "useZ": 1, "z": 1},
            4121020: {"randomHitOrigin": 30, "randomHitAngle": 1, "useZ": 1, "z": 1},
            4121022: {"randomHitOrigin": 30, "randomHitAngle": 1, "useZ": 1, "z": 1},
            4121026: {"randomHitOrigin": 60, "onCoverFieldDamage": 2001, "hitSoundProb": 60},
            4121028: {"randomHitOrigin": 60, "onCoverFieldDamage": 2001, "hitSoundProb": 50},
            4121029: {"randomHitOrigin": 70, "onCoverFieldDamage": 2001, "hitSoundProb": 60},
        }
        for skill_id, expected in hit_metadata.items():
            hit = client.get(f"skill/{skill_id}/hit/0")
            for name, value in expected.items():
                self.assertEqual(value, int(hit.get(name).value), (skill_id, name))

        summon_contracts = {
            4121012: {"summoned": 17, "stand": 10, "attack1": 23, "die": 23},
        }
        for skill_id, actions in summon_contracts.items():
            summon = client.get(f"skill/{skill_id}/summon")
            self.assertEqual(tuple(actions), tuple(child.name for child in summon.children()))
            for action, frame_count in actions.items():
                node = summon.child(action)
                frames = [child for child in node.children() if child.name.isdigit()]
                self.assertEqual(frame_count, len(frames), (skill_id, action))
            info = summon.get("attack1/info")
            self.assertIsNotNone(info, skill_id)
            self.assertIsNotNone(info.get("range/lt"), skill_id)
            self.assertIsNotNone(info.get("range/rb"), skill_id)

        cpp = (ROOT / (
            "tool/client-debug/dawn-warrior-skill-compat/"
            "DawnWarriorSkillCompat.cpp"
        )).read_text(encoding="utf-8")
        for skill_id in (4121011, 4121016, 4121019, 4121026):
            self.assertIn(f"case {skill_id}:", cpp)
        for skill_id in (4121012,):
            self.assertIn(
                f'cmp esi, {skill_id}\\n"\n'
                '        "je explorer_night_lord_summon_active',
                cpp,
            )
            self.assertIn(
                f'cmp dword ptr [ebx + 0xB4], {skill_id}\\n"', cpp
            )
            self.assertIn(f'cmp eax, {skill_id}\\n"', cpp)
        for skill_id in (4121010, 4121015, 4121021):
            self.assertNotIn(f"case {skill_id}:", cpp)
            self.assertNotIn(
                f'cmp dword ptr [ebx + 0xB4], {skill_id}\\n"', cpp
            )
            self.assertNotIn(f'cmp eax, {skill_id}\\n"', cpp)
        self.assertIn("case 14121004:", cpp)
        self.assertIn("kProjectileProfileRapidThrow", cpp)
        self.assertIn("kProjectileProfileFumaShuriken", cpp)
        self.assertIn("kFumaShurikenTravelMilliseconds", cpp)
        self.assertIn("kFumaShurikenHoldMilliseconds", cpp)
        self.assertIn("kFumaShurikenFadeMilliseconds", cpp)

        stat_effect = (ROOT / (
            "gms-server/src/main/java/org/gms/server/StatEffect.java"
        )).read_text(encoding="utf-8")
        summon_handler = (ROOT / (
            "gms-server/src/main/java/org/gms/net/server/channel/handlers/"
            "SummonDamageHandler.java"
        )).read_text(encoding="utf-8")
        self.assertIn("case NightLord.DARK_LORDS_SECRET_SCROLL:", stat_effect)
        self.assertIn("add(NightLord.DARK_LORDS_SECRET_SCROLL);", summon_handler)
        self.assertNotIn("DARK_FLARE_VI", stat_effect)
        self.assertNotIn("DARK_FLARE_VI", summon_handler)

    def test_night_lord_four_seasons_rain_vi_visuals_match_tms(self):
        client_path = ROOT / "clien/Data/Skill/412.img"
        image = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"),
            name=client_path.name,
        )
        client = image.parse()
        self.assertFalse(image.truncated)
        self.assertFalse(image.parse_warnings)
        four_seasons_visuals = {
            4121023: (37, 8, 20),
            4121024: (43, 9, 25),
            4121025: (0, 9, 30),
        }
        for skill_id, (effect_count, hit_count, random_origin) in four_seasons_visuals.items():
            skill = client.get(f"skill/{skill_id}")
            self.assertIsNone(skill.get("ball"), (skill_id, "unexpected legacy projectile"))
            self.assertIsNone(skill.get("shootobj"), (skill_id, "unexpected modern projectile"))
            effect = migration.engine.base.numeric_canvases(skill.get("effect"))
            self.assertEqual(effect_count, len(effect), (skill_id, "effect"))
            hit = skill.get("hit/0")
            hit_frames = migration.engine.base.numeric_canvases(hit)
            self.assertEqual(hit_count, len(hit_frames), (skill_id, "hit"))
            for frame in (*effect, *hit_frames):
                self.assertEqual(60, int(frame.child("delay").value), (skill_id, frame.name))
                self.assertEqual((1, 0), (frame.format, frame.format2), (skill_id, frame.name))
                self.assertIsNotNone(
                    decode_canvas(frame, region="GMS").getchannel("A").getbbox(),
                    (skill_id, frame.name, "transparent frame"),
                )
            self.assertEqual(random_origin, int(hit.child("randomHitOrigin").value))
            self.assertEqual(1, int(hit.child("randomHitAngle").value))
            self.assertEqual(1, int(hit.child("useZ").value))
            self.assertEqual(1, int(hit.child("z").value))

    def test_night_lord_four_seasons_rain_vi_uses_tms_frenzy_timeline(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            compat,
            r"Map\.entry\(4121024,\s*replays\(\s*"
            r"replay\(4121024, points\(0\)\),\s*"
            r"replay\(4121025, points\(180, 240, 300, 360, 420, 480\)\)\s*"
            r"\)\)",
        )
        self.assertIn(
            "return skillId == 4121011 || skillId >= 4121023 && skillId <= 4121025;",
            compat,
        )

        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("hasFourSeasonsRainFrenzy(chr, attack)", handler)
        self.assertIn("consumeFourSeasonsRainFrenzy(chr, attack)", handler)
        self.assertIn("markFourSeasonsRainHit(chr, attack)", handler)
        self.assertIn("ExplorerOtherSkillCompat.multiAttacks(4121024)", handler)
        self.assertIn("ExplorerOtherSkillCompat.hidesNativeProjectile(attack.skill)", handler)
        self.assertIn("skillId == 4121023", handler)

    def test_night_lord_fuma_shuriken_uses_tms_timing_contract(self):
        compat = (ROOT / (
            "gms-server/src/main/java/org/gms/constants/skills/"
            "ExplorerOtherSkillCompat.java"
        )).read_text(encoding="utf-8")
        self.assertRegex(
            compat,
            r"Map\.entry\(4121011,\s*replays\(replay\(4121011,\s*concat\(\s*"
            r"range\(420, 100, 720\),\s*range\(780, 180, 2760\)\s*"
            r"\)\)\)\)",
        )
        handler = (ROOT / (
            "gms-server/src/main/java/org/gms/net/server/channel/handlers/"
            "RangedAttackHandler.java"
        )).read_text(encoding="utf-8")
        self.assertIn("skillId == 4121011", handler)

        client = WzImage.from_bytes(
            (ROOT / "clien/Data/Skill/412.img").read_bytes(),
            key=WzKey.for_region("GMS"), name="412.img",
        ).parse()
        level = client.get("skill/4121011/level/30")
        self.assertEqual(615, int(level.get("damage").value))
        self.assertEqual(7, int(level.get("attackCount").value))
        self.assertEqual(6, int(level.get("mobCount").value))
        self.assertEqual(800, int(level.get("mpCon").value))
        self.assertEqual(25, int(level.get("cooltime").value))
        self.assertEqual((-920, -198), (
            int(level.get("lt").x), int(level.get("lt").y)
        ))
        self.assertEqual((-40, 82), (
            int(level.get("rb").x), int(level.get("rb").y)
        ))

        ball = client.get("skill/4121011/ball")
        self.assertEqual([str(value) for value in range(6)], list(ball._children))
        self.assertEqual(360, sum(
            int(ball.get(str(value)).get("delay").value) for value in range(6)
        ))
        hold = client.get("skill/4121011/fumaHold")
        self.assertEqual([str(value) for value in range(68)], list(hold._children))
        hold_delays = []
        for value in range(68):
            frame = hold.get(str(value))
            if isinstance(frame, WzUolProperty):
                frame = hold.get(str(frame.value))
            hold_delays.append(int(frame.get("delay").value))
        self.assertEqual(3080, sum(hold_delays))

        cpp = (ROOT / (
            "tool/client-debug/dawn-warrior-skill-compat/"
            "DawnWarriorSkillCompat.cpp"
        )).read_text(encoding="utf-8")
        self.assertIn(
            'case 4121011: return L"Skill/412.img/skill/4121011/fumaHold";',
            cpp,
        )
        self.assertIn("? 4121011", cpp)
        self.assertIn("duration = kFumaShurikenTravelMilliseconds;", cpp)
        self.assertIn("const float travelT = Clamp01(rawT);", cpp)
        self.assertIn('WideContains(path, L"/fumaHold")', cpp)

    def test_night_lord_patch_changes_only_approved_raw_records(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Skill/412.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Skill/412.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> tuple[tuple[str, ...], dict[str, bytes]]:
            with tempfile.TemporaryDirectory(prefix="night-lord-record-contract-") as name:
                path = Path(name) / filename
                path.write_bytes(data)
                image = WzImage.from_bytes(
                    data, key=WzKey.for_region("GMS"), name=filename
                )
                _, _, _, _, names, spans = migration.locate_client_skill_records(
                    image, path
                )
                return tuple(names), {
                    skill_id: data[start:end]
                    for skill_id, (start, end) in zip(names, spans)
                }

        baseline_order, baseline_records = records(baseline, "baseline-412.img")
        current_order, current_records = records(current, "412.img")
        retired = {str(value) for value in migration.NIGHT_LORD_RETIRED_SKILL_IDS}
        self.assertEqual(
            tuple(value for value in baseline_order if value not in retired),
            current_order,
        )
        allowed = {
            str(value) for value in migration.NIGHT_LORD_CLIENT_REPLACEMENT_IDS
        }
        changed = {
            key for key, value in current_records.items()
            if baseline_records.get(key) != value
        }
        self.assertTrue(changed.issubset(allowed))
        self.assertEqual(allowed, changed)
        for key, value in current_records.items():
            if key not in allowed:
                self.assertEqual(baseline_records[key], value, key)

    def test_bowmaster_retirement_preserves_every_retained_raw_record(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Skill/312.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Skill/312.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> dict[str, bytes]:
            with tempfile.TemporaryDirectory(prefix="bowmaster-record-contract-") as name:
                path = Path(name) / filename
                path.write_bytes(data)
                image = WzImage.from_bytes(
                    data, key=WzKey.for_region("GMS"), name=filename
                )
                _, _, _, _, names, spans = migration.locate_client_skill_records(image, path)
                return {
                    skill_id: data[start:end]
                    for skill_id, (start, end) in zip(names, spans)
                }

        baseline_records = records(baseline, "baseline-312.img")
        current_records = records(current, "312.img")
        retired = {str(skill_id) for skill_id in migration.BOWMASTER_RETIRED_SKILL_IDS}
        expected_order = tuple(
            skill_id for skill_id in baseline_records if skill_id not in retired
        )
        replay_id = str(migration.BOWMASTER_ARROW_RAIN_TICK_ID)
        if replay_id not in baseline_records:
            expected_order = (*expected_order, replay_id)
        self.assertEqual(expected_order, tuple(current_records))
        changed = {
            skill_id for skill_id, record in current_records.items()
            if skill_id in baseline_records and baseline_records[skill_id] != record
        }
        allowed_changed = {
            str(skill_id)
            for skill_id in (
                *migration.BOWMASTER_CLIENT_REPLACEMENT_IDS,
                *migration.BOWMASTER_CLIENT_ADDITIONS,
            )
        }
        self.assertTrue(changed.issubset(allowed_changed))
        self.assertIn(replay_id, current_records)
        for skill_id, record in current_records.items():
            if skill_id not in changed and skill_id in baseline_records:
                self.assertEqual(baseline_records[skill_id], record, skill_id)

        baseline_string = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/String/Skill.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_string_path = ROOT / "clien/Data/String/Skill.img"
        current_string = current_string_path.read_bytes()
        self.assertEqual(len(baseline_string), len(current_string))
        with tempfile.TemporaryDirectory(prefix="bowmaster-string-contract-") as name:
            baseline_path = Path(name) / "Skill.img"
            baseline_path.write_bytes(baseline_string)
            _, locations = migration.top_level_name_locations(baseline_path)
        allowed_spans = [
            (locations[str(skill_id)][0], locations[str(skill_id)][1])
            for skill_id in (
                *migration.BOWMASTER_RETIRED_SKILL_IDS,
                *migration.MARKSMAN_RETIRED_SKILL_IDS,
            )
            if str(skill_id) in locations
        ]
        changed_offsets = {
            offset
            for offset, (before, after) in enumerate(zip(baseline_string, current_string))
            if before != after
        }
        self.assertTrue(changed_offsets)
        self.assertTrue(all(
            any(start <= offset < start + length for start, length in allowed_spans)
            for offset in changed_offsets
        ))

        for relative_path, parent_name in (
            ("gms-server/wz/Skill.wz/522.img.xml", "skill"),
            ("gms-server/wz/String.wz/Skill.img.xml", None),
        ):
            baseline_xml = subprocess.run(
                ["git", "cat-file", "blob", f"HEAD:{relative_path}"],
                cwd=ROOT, check=True, stdout=subprocess.PIPE,
            ).stdout.decode("utf-8")
            current_xml = (ROOT / relative_path).read_text(encoding="utf-8")
            baseline_root = ET.fromstring(baseline_xml)
            current_root = ET.fromstring(current_xml)
            if parent_name is not None:
                baseline_root = baseline_root.find(
                    f"./imgdir[@name='{parent_name}']"
                )
                current_root = current_root.find(
                    f"./imgdir[@name='{parent_name}']"
                )
            baseline_names = [
                node.get("name") for node in baseline_root if node.tag == "imgdir"
            ]
            current_names = [
                node.get("name") for node in current_root if node.tag == "imgdir"
            ]
            retired_names = {
                str(skill_id) for skill_id in migration.CORSAIR_RETIRED_SKILL_IDS
            }
            self.assertEqual(
                [name for name in baseline_names if name not in retired_names],
                current_names,
                relative_path,
            )
            for skill_id in current_names:
                baseline_start, baseline_end = migration.engine.find_imgdir_block(
                    baseline_xml, skill_id
                )
                current_start, current_end = migration.engine.find_imgdir_block(
                    current_xml, skill_id
                )
                self.assertEqual(
                    baseline_xml[baseline_start:baseline_end],
                    current_xml[current_start:current_end],
                    (relative_path, skill_id),
                )

    def test_bowmaster_flash_mirage_has_legacy_projectile_and_hit_effects(self):
        path = ROOT / "clien/Data/Skill/312.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        root = image.parse()
        self.assertFalse(image.truncated)
        self.assertFalse(image.parse_warnings)

        for skill_id in migration.BOWMASTER_FLASH_MIRAGE_IDS:
            ball = root.get(f"skill/{skill_id}/ball")
            frames = migration.engine.base.numeric_canvases(ball)
            self.assertEqual(12, len(frames), skill_id)
            for frame in frames:
                self.assertEqual((160, 48), (frame.width, frame.height), skill_id)
                origin = frame.get("origin")
                self.assertEqual((70, 22), (int(origin.x), int(origin.y)), skill_id)
                self.assertEqual(60, int(frame.get("delay").value), skill_id)
                self.assertEqual(0, int(frame.get("z").value), skill_id)
                self.assertEqual((1, 0), (int(frame.format), int(frame.format2)), skill_id)
                decoded = decode_canvas(frame, region="GMS")
                self.assertIsNotNone(decoded.getchannel("A").getbbox(), skill_id)
                decoded.close()
            for level in range(1, migration.MASTER_LEVEL + 1):
                level_ball = root.get(f"skill/{skill_id}/level/{level}/ball")
                self.assertIsInstance(level_ball, WzUolProperty)
                self.assertEqual("../../ball", level_ball.value)

        active = root.get("skill/3121026")
        hit = active.get("hit/0")
        hit_frames = migration.engine.base.numeric_canvases(hit)
        self.assertEqual(12, len(hit_frames))
        self.assertEqual(720, sum(
            int(frame.get("delay").value) for frame in hit_frames
        ))
        for name, expected in {
            "randomHitOrigin": 35,
            "randomHitAngle": 1,
            "useZ": 1,
            "z": 1,
        }.items():
            self.assertEqual(expected, int(hit.get(name).value), name)
        for frame in hit_frames:
            self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
            decoded = decode_canvas(frame, region="GMS")
            self.assertIsNotNone(decoded.getchannel("A").getbbox())
            decoded.close()

        effect = migration.engine.base.numeric_canvases(active.get("effect"))
        self.assertEqual(20, len(effect))
        self.assertEqual(1200, sum(int(frame.get("delay").value) for frame in effect))
        for frame in effect:
            self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
            decoded = decode_canvas(frame, region="GMS")
            self.assertIsNotNone(decoded.getchannel("A").getbbox())
            decoded.close()
        for name in ("special", "special1", "special2", "special3"):
            frames = migration.engine.base.numeric_canvases(active.get(f"{name}/0"))
            self.assertEqual(20, len(frames), name)
            self.assertEqual(
                1200, sum(int(frame.get("delay").value) for frame in frames), name
            )

    def test_bowmaster_arrow_rain_and_phoenix_use_legacy_playback_shapes(self):
        path = ROOT / "clien/Data/Skill/312.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        root = image.parse()
        self.assertFalse(image.truncated)
        self.assertFalse(image.parse_warnings)

        arrow_effect = root.get("skill/3121010/effect")
        self.assertIsInstance(arrow_effect, WzSubProperty)
        self.assertEqual(71, len(arrow_effect.children()))
        duration = 0
        for frame in arrow_effect.children():
            if isinstance(frame, WzUolProperty):
                frame = arrow_effect.get(frame.value)
            self.assertIsInstance(frame, WzCanvasProperty)
            duration += migration.engine.base.frame_delay(frame)
        self.assertEqual(2_500, duration)
        arrow_canvases = migration.engine.base.numeric_canvases(arrow_effect)
        self.assertEqual(24, len(arrow_canvases))
        for frame in arrow_canvases:
            self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
            decoded = decode_canvas(frame, region="GMS")
            self.assertIsNotNone(decoded.getchannel("A").getbbox())
            decoded.close()

        tick = root.get(f"skill/{migration.BOWMASTER_ARROW_RAIN_TICK_ID}")
        self.assertEqual(1, int(tick.get("invisible").value))
        tick_effect = migration.engine.base.numeric_canvases(tick.get("effect"))
        self.assertEqual(8, len(tick_effect))
        self.assertEqual(240, sum(
            migration.engine.base.frame_delay(frame) for frame in tick_effect
        ))
        special = tick.get("special")
        for name, value in {
            "x": 85,
            "y": 230,
            "fall": 150,
            "start": 0,
            "interval": 90,
            "count": 8,
            "duration": 500,
        }.items():
            self.assertEqual(value, int(special.get(name).value), name)
        tick_canvases = [
            *tick_effect,
            *migration.engine.base.numeric_canvases(special.get("0")),
            *migration.engine.base.numeric_canvases(tick.get("hit/0")),
        ]
        self.assertEqual(12, len(tick_canvases))
        for frame in tick_canvases:
            self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
            decoded = decode_canvas(frame, region="GMS")
            self.assertIsNotNone(decoded.getchannel("A").getbbox())
            decoded.close()

        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/312.img.xml").getroot()
        for skill_id, mp_con, duration in (
            (3121010, 1000, 70),
            (migration.BOWMASTER_ARROW_RAIN_TICK_ID, 0, None),
        ):
            level = server.find(
                f"./imgdir[@name='skill']/imgdir[@name='{skill_id}']"
                "/imgdir[@name='level']/imgdir[@name='30']"
            )
            self.assertEqual(1650, int(level.find("./int[@name='damage']").get("value")))
            self.assertEqual(7, int(level.find("./int[@name='attackCount']").get("value")))
            self.assertEqual(10, int(level.find("./int[@name='mobCount']").get("value")))
            self.assertEqual(mp_con, int(level.find("./int[@name='mpCon']").get("value")))
            time = level.find("./int[@name='time']")
            self.assertEqual(duration, None if time is None else int(time.get("value")))

        constants = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/Bowmaster.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("public static final int ARROW_RAIN = 3121010;", constants)
        self.assertIn("public static final int ARROW_RAIN_FIELD_ATTACK = 3121033;", constants)
        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java").read_text(
            encoding="utf-8"
        )
        for marker in (
            "ARROW_RAIN_DURATION_MS = 70000",
            "ARROW_RAIN_FIELD_COOLDOWN_MS = 5000",
            "intervalTimes(0, 240, 2400)",
            "triggerArrowRainField(attack, chr);",
            "Bowmaster.ARROW_RAIN_FIELD_ATTACK",
        ):
            self.assertIn(marker, handler)
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("case 3121033: return 10;", cpp)
        self.assertIn("skillId <= 3121033", cpp)

        phoenix = root.get("skill/3121025")
        self.assertEqual("alert2", phoenix.get("action/0").value)
        self.assertEqual("f", phoenix.get("elemAttr").value)
        self.assertEqual(45, int(phoenix.get("weapon").value))
        expected = {
            "summoned": (14, 1260),
            "fly": (12, 1080),
            "stand": (12, 1440),
            "attack1": (19, 1710),
            "die": (13, 1170),
        }
        summon = phoenix.get("summon")
        self.assertEqual(expected.keys(), {child.name for child in summon.children()})
        for name, (count, action_duration) in expected.items():
            frames = migration.engine.base.numeric_canvases(summon.get(name))
            self.assertEqual(count, len(frames), name)
            self.assertEqual(
                action_duration,
                sum(migration.engine.base.frame_delay(frame) for frame in frames),
                name,
            )
            for frame in frames:
                self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
                decoded = decode_canvas(frame, region="GMS")
                self.assertIsNotNone(decoded.getchannel("A").getbbox(), name)
                decoded.close()
        info = summon.get("attack1/info")
        lt = info.get("range/lt")
        rb = info.get("range/rb")
        self.assertEqual((-560, -200), (int(lt.x), int(lt.y)))
        self.assertEqual((100, 50), (int(rb.x), int(rb.y)))
        for name, value in {
            "type": 0,
            "attackAfter": 720,
            "mobCount": 6,
        }.items():
            self.assertEqual(value, int(info.get(name).value), name)
        self.assertEqual(3, len(
            migration.engine.base.numeric_canvases(phoenix.get("mob"))
        ))
        self.assertEqual(8, len(
            migration.engine.base.numeric_canvases(phoenix.get("hit/0"))
        ))
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/312.img.xml").getroot()
        for level in range(1, migration.MASTER_LEVEL + 1):
            server_level = server.find(
                f"./imgdir[@name='skill']/imgdir[@name='3121025']"
                f"/imgdir[@name='level']/imgdir[@name='{level}']"
            )
            damage = int(server_level.find("./int[@name='damage']").get("value"))
            pad = int(server_level.find("./int[@name='pad']").get("value"))
            self.assertEqual(damage, pad, level)

    def test_bowmaster_phoenix_runtime_is_wired_as_a_summon(self):
        constants = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/Bowmaster.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("public static final int PHOENIX_VI = 3121025;", constants)
        effect = (ROOT / "gms-server/src/main/java/org/gms/server/StatEffect.java").read_text(
            encoding="utf-8"
        )
        self.assertEqual(2, effect.count("case Bowmaster.PHOENIX_VI:"))
        summon_handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/SummonDamageHandler.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("add(Bowmaster.PHOENIX_VI);", summon_handler)

        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        dispatch_start = cpp.index("void HookActiveSkillDispatch()")
        dispatch_end = cpp.index("\n}\n", dispatch_start)
        dispatch = cpp[dispatch_start:dispatch_end]
        self.assertIn(
            'cmp esi, 3121025\\n"\n        "je explorer_bowmaster_summon_active\\n',
            dispatch,
        )
        branch_start = dispatch.index('"explorer_bowmaster_summon_active:\\n"')
        branch = dispatch[branch_start:branch_start + 120]
        self.assertIn('push 0x009689DF\\n', branch)
        for function in (
            "HookSummonBehaviorClassifier",
            "HookSummonAttackClassifier",
        ):
            start = cpp.index(f"void {function}()")
            end = cpp.index("\n}\n", start)
            self.assertIn("3121025", cpp[start:end], function)

    def test_retired_marksman_skills_are_absent_without_shifting_later_ids(self):
        job = next(job for job in self.jobs if job.config.key == "marksman")
        self.assertTrue(migration.MARKSMAN_RETIRED_SOURCE_IDS.isdisjoint(job.target_by_source))
        self.assertEqual(400031006, job.source_by_target[3221009])
        self.assertEqual(400031010, job.source_by_target[3221010])
        self.assertEqual(400031025, job.source_by_target[3221013])
        self.assertEqual(3241012, job.source_by_target[3221029])
        self.assertEqual(3241500, job.source_by_target[3221032])

        client_path = ROOT / "clien/Data/Skill/322.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        client_string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            client_string_path.read_bytes(),
            key=WzKey.for_region("GMS"),
            name=client_string_path.name,
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/322.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        for skill_id in migration.MARKSMAN_RETIRED_SKILL_IDS:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)

        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for skill_id in migration.MARKSMAN_RETIRED_SKILL_IDS:
            self.assertIn(
                f'cmp esi, {skill_id}\\n"\n        "je explorer_marksman_active_next',
                cpp,
            )
        self.assertIn("&& !retiredMarksmanSkill", cpp)

    def test_marksman_retirement_preserves_every_retained_raw_record(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Skill/322.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Skill/322.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> dict[str, bytes]:
            with tempfile.TemporaryDirectory(prefix="marksman-record-contract-") as name:
                path = Path(name) / filename
                path.write_bytes(data)
                image = WzImage.from_bytes(
                    data, key=WzKey.for_region("GMS"), name=filename
                )
                _, _, _, _, names, spans = migration.locate_client_skill_records(image, path)
                return {
                    skill_id: data[start:end]
                    for skill_id, (start, end) in zip(names, spans)
                }

        baseline_records = records(baseline, "baseline-322.img")
        current_records = records(current, "322.img")
        retired = {str(skill_id) for skill_id in migration.MARKSMAN_RETIRED_SKILL_IDS}
        self.assertEqual(
            tuple(skill_id for skill_id in baseline_records if skill_id not in retired),
            tuple(current_records),
        )
        changed = {
            skill_id for skill_id, record in current_records.items()
            if baseline_records[skill_id] != record
        }
        approved = {
            str(skill_id) for skill_id in (
                *migration.MARKSMAN_TRUE_SNIPING_IDS,
                *migration.MARKSMAN_CLIENT_REPLACEMENT_IDS,
            )
        }
        self.assertEqual(
            approved,
            changed,
        )
        for skill_id, record in current_records.items():
            if skill_id not in changed:
                self.assertEqual(baseline_records[skill_id], record, skill_id)

        baseline_server = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:gms-server/wz/Skill.wz/322.img.xml"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout.decode("utf-8")
        current_server = (ROOT / "gms-server/wz/Skill.wz/322.img.xml").read_text(
            encoding="utf-8"
        )

        def server_blocks(text: str) -> dict[str, str]:
            root = ET.fromstring(text)
            skills = root.find("./imgdir[@name='skill']")
            result = {}
            for child in skills:
                skill_id = child.get("name")
                start, end = migration.engine.find_imgdir_block(text, skill_id)
                result[skill_id] = text[start:end]
            return result

        baseline_server_blocks = server_blocks(baseline_server)
        current_server_blocks = server_blocks(current_server)
        self.assertEqual(
            tuple(skill_id for skill_id in baseline_server_blocks if skill_id not in retired),
            tuple(current_server_blocks),
        )
        changed_server = {
            skill_id for skill_id, block in current_server_blocks.items()
            if baseline_server_blocks[skill_id] != block
        }
        self.assertEqual(
            approved,
            changed_server,
        )

    def test_true_sniping_uses_target_markers_and_six_impact_replays(self):
        path = ROOT / "clien/Data/Skill/322.img"
        root = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        ).parse()
        main = root.get("skill/3221009")
        hidden = root.get("skill/3221010")
        self.assertIsNone(main.get("special"))
        marker = migration.engine.base.numeric_canvases(main.get("hit/0"))
        impacts = migration.engine.base.numeric_canvases(hidden.get("hit/0"))
        self.assertEqual(7, len(marker))
        self.assertEqual([30] * 7, [migration.engine.base.frame_delay(frame) for frame in marker])
        self.assertEqual(6, len(impacts))
        self.assertEqual([60] * 6, [migration.engine.base.frame_delay(frame) for frame in impacts])
        for skill_id in migration.MARKSMAN_TRUE_SNIPING_IDS:
            level = root.get(f"skill/{skill_id}/level/30")
            self.assertEqual((-700, -400), (level.get("lt").x, level.get("lt").y))
            self.assertEqual((700, 400), (level.get("rb").x, level.get("rb").y))

        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            compat,
            r"Map\.entry\(3221009, replays\(replay\(\s*3221010, "
            r"points\(90, 150, 240, 300, 360, 420\)\s*\)\)\)",
        )
        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("skillId == Marksman.TRUE_SNIPING", handler)
        self.assertIn("if (!hasPositiveDamageTemplate(sourceDamageTemplate))", handler)

    def test_marksman_projectiles_and_hit_metadata_use_legacy_shapes(self):
        path = ROOT / "clien/Data/Skill/322.img"
        root = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        ).parse()
        for skill_id, frame_count in {3221013: 10}.items():
            ball = root.get(f"skill/{skill_id}/ball")
            self.assertEqual(
                frame_count, len(migration.engine.base.numeric_canvases(ball)), skill_id
            )
            for level in (1, 15, 30):
                link = root.get(f"skill/{skill_id}/level/{level}/ball")
                self.assertIsInstance(link, WzUolProperty, (skill_id, level))
                self.assertEqual("../../ball", link.value, (skill_id, level))

        self.assertIsNone(root.get("skill/3221030/ball"))
        self.assertIsNone(root.get("skill/3221030/level/30/ball"))

        for skill_id, (variant_count, random_origin) in {
            3221031: (4, 15),
        }.items():
            hit = root.get(f"skill/{skill_id}/hit")
            self.assertEqual(1, int(hit.get("randomHit").value), skill_id)
            variants = [
                child for child in hit.children()
                if isinstance(child, WzSubProperty) and child.name.isdigit()
            ]
            self.assertEqual(variant_count, len(variants), skill_id)
            metadata_variants = variants[:3] if skill_id == 3221031 else variants
            for variant in metadata_variants:
                self.assertEqual(
                    random_origin, int(variant.get("randomHitOrigin").value),
                    (skill_id, variant.name),
                )
            if skill_id == 3221031:
                self.assertIsNone(root.get("skill/3221031/hit2"))
                self.assertEqual(15, int(variants[3].get("repeat").value))
                for variant in variants[:3]:
                    self.assertEqual(1, int(variant.get("useZ").value))
                    self.assertEqual(1, int(variant.get("z").value))

    def test_frost_prey_vi_uses_legacy_summon_contract(self):
        path = ROOT / "clien/Data/Skill/322.img"
        root = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        ).parse()
        summon = root.get("skill/3221029/summon")
        self.assertEqual(
            {"summoned", "fly", "stand", "attack1", "die"},
            {child.name for child in summon.children()},
        )
        for action in summon.children():
            self.assertTrue(
                migration.engine.base.numeric_canvases(action), action.name
            )
        info = summon.get("attack1/info")
        expected = migration.MARKSMAN_FROST_PREY_SUMMON_INFO
        self.assertEqual(expected[0], (info.get("range/lt").x, info.get("range/lt").y))
        self.assertEqual(expected[1], (info.get("range/rb").x, info.get("range/rb").y))
        self.assertEqual(expected[2], int(info.get("type").value))
        self.assertEqual(expected[3], int(info.get("attackAfter").value))
        self.assertEqual(expected[4], int(info.get("mobCount").value))
        self.assertEqual("i", root.get("skill/3221029/elemAttr").value)
        self.assertEqual(46, int(root.get("skill/3221029/weapon").value))
        level = root.get("skill/3221029/level/30")
        self.assertEqual(int(level.get("damage").value), int(level.get("pad").value))
        self.assertEqual(3, int(level.get("x").value))

        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/322.img.xml").getroot()
        server_skill = server.find(
            "./imgdir[@name='skill']/imgdir[@name='3221029']"
        )
        server_level = server_skill.find("./imgdir[@name='level']/imgdir[@name='30']")
        values = {child.get("name"): child.get("value") for child in server_level}
        self.assertEqual(values["damage"], values["pad"])
        self.assertEqual("3", values["x"])
        self.assertEqual(
            "i", server_skill.find("./string[@name='elemAttr']").get("value")
        )

        stat_effect = (ROOT / "gms-server/src/main/java/org/gms/server/StatEffect.java").read_text(
            encoding="utf-8"
        )
        summon_handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/SummonDamageHandler.java").read_text(
            encoding="utf-8"
        )
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(stat_effect.count("Marksman.FROST_PREY_VI"), 2)
        self.assertIn("add(Marksman.FROST_PREY_VI)", summon_handler)
        self.assertIn(
            'cmp esi, 3221029\\n"\n        "je explorer_marksman_summon_active', cpp
        )
        for function in ("HookSummonBehaviorClassifier", "HookSummonAttackClassifier"):
            start = cpp.index(f"void {function}()")
            end = cpp.index("\n}\n", start)
            self.assertIn("3221029", cpp[start:end], function)

    def test_marksman_runtime_stages_match_tms_contract(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "Map.entry(3221013, replays(replay(3221013, points(0, 100))))",
            compat,
        )
        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java").read_text(
            encoding="utf-8"
        )
        for retired_reference in (
            "Marksman.SPLIT_ARROW",
            "Marksman.SPLIT_ARROW_HIT",
            "Marksman.PIERCING_ARROW_VI",
            "PIERCING_ARROW_CAST_COUNTS",
        ):
            self.assertNotIn(retired_reference, handler)

        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        arm_start = cpp.index("void ArmNightWalkerProjectiles(int skillId)")
        arm_end = cpp.index("\n}\n", arm_start)
        arm = cpp[arm_start:arm_end]
        for skill_id in (3221013, 3221030, 3221031):
            self.assertIn(f"case {skill_id}:", arm)
        self.assertIn("gNativeRangedProjectileWindowEnd = GetTickCount() + 1200", arm)
        self.assertNotIn("case 3221022:", arm)
        self.assertIn("Attack Skill Compat v63", cpp)
        dispatch_start = cpp.index('"explorer_ranged_active:\\n"')
        dispatch_end = cpp.index('"ret\\n"', dispatch_start)
        self.assertIn("call _ArmNightWalkerProjectiles", cpp[dispatch_start:dispatch_end])

    def test_removed_il_vi_skills_are_absent_without_shifting_later_ids(self):
        job = next(job for job in self.jobs if job.config.key == "ilArchMage")
        self.assertTrue(migration.IL_EXCLUDED_VI_IDS.isdisjoint(job.target_by_source))
        self.assertEqual(2241003, job.source_by_target[2221020])
        self.assertEqual(2241005, job.source_by_target[2221022])
        self.assertEqual(2241500, job.source_by_target[2221027])
        self.assertEqual(2241505, job.source_by_target[2221030])

        removed_ids = (2221019, 2221023, 2221024, 2221025)
        client_path = ROOT / "clien/Data/Skill/222.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        client_string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            client_string_path.read_bytes(),
            key=WzKey.for_region("GMS"),
            name=client_string_path.name,
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/222.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        for skill_id in removed_ids:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)

    def test_il_internal_vi_nodes_are_hidden_from_active_skill_grants(self):
        job = next(job for job in self.jobs if job.config.key == "ilArchMage")
        specs = {spec.target_id: spec for spec in job.skills}
        self.assertEqual(2240006, specs[2221016].source_id)
        self.assertEqual(2241001, specs[2221018].source_id)
        for skill_id in (2221016, 2221018):
            self.assertTrue(specs[skill_id].hidden, skill_id)

        client_path = ROOT / "clien/Data/Skill/222.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/222.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        for skill_id in (2221016, 2221018):
            self.assertEqual(1, client.get(f"skill/{skill_id}/invisible").value, skill_id)
            invisible = server_skills.find(
                f"./imgdir[@name='{skill_id}']/int[@name='invisible']"
            )
            self.assertIsNotNone(invisible, skill_id)
            self.assertEqual("1", invisible.get("value"), skill_id)

        constants = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ILArchMage.java").read_text(
            encoding="utf-8"
        )
        block = re.search(r"V_VI_ACTIVE_ATTACKS\s*=\s*\{([^}]*)}", constants, re.S)
        active_ids = {int(value) for value in re.findall(r"\d+", block.group(1))}
        self.assertTrue({2221016, 2221018}.isdisjoint(active_ids))

    def test_mcv_headers_alpha_and_dll_mappings(self):
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        video_specs = []
        for job in self.jobs:
            for spec in job.skills:
                metadata = migration.MS_EXPORT_ROOT / f"{spec.source_id}.xml"
                if (not spec.hidden
                        and (spec.target_id in (5121015, 5221012)
                             or "<video " in metadata.read_text(encoding="utf-8"))):
                    video_specs.append(spec)
        self.assertEqual(20, len(video_specs))
        marker_capacity = re.search(r"kMaxVideoMarkerTextures\s*=\s*(\d+)", cpp)
        self.assertIsNotNone(marker_capacity)
        self.assertGreaterEqual(int(marker_capacity.group(1)), len(video_specs) + 5)
        for spec in video_specs:
            path = ROOT / f"clien/Data/Video/explorer-{spec.target_id}.mcv"
            track = parse_mcv(path.read_bytes())
            self.assertEqual((1280, 720), (track.width, track.height), spec.target_id)
            self.assertEqual(len(track.color_packets), len(track.alpha_packets), spec.target_id)
            self.assertEqual(len(track.delays), len(track.color_packets), spec.target_id)
            self.assertEqual(MCV_DURATIONS_MS[spec.target_id], sum(track.delays), spec.target_id)
            self.assertIn(f'{{{spec.target_id}, "Data\\\\Video\\\\explorer-{spec.target_id}.mcv"', cpp)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MCV pixel checks")
    def test_howling_fist_mcv_starts_after_charge_and_preserves_screen_layers(self):
        path = ROOT / "clien/Data/Video/explorer-5121015.mcv"
        track = parse_mcv(path.read_bytes())
        self.assertEqual((1280, 720), (track.width, track.height))
        self.assertEqual(4890, sum(track.delays))
        self.assertEqual(1920, track.delays[0])
        boxes = []
        bright_pixels = []
        with tempfile.TemporaryDirectory(prefix="howling-fist-mcv-contract-") as name:
            decoder = start_decoder(shutil.which("ffmpeg"), track, Path(name), 0)
            for frame_index in range(len(track.delays)):
                frame = decoder.read_frame(frame_index)
                boxes.append(frame.getchannel("A").getbbox())
                bright_pixels.append(sum(
                    1 for red, green, blue, alpha in frame.getdata()
                    if alpha >= 128 and max(red, green, blue) >= 220
                ))
                frame.close()
            decoder.close()
        self.assertIsNone(boxes[0])
        self.assertIsNotNone(boxes[1])
        self.assertGreaterEqual(
            max(box[2] - box[0] for box in boxes if box is not None), 1200
        )
        self.assertEqual([0, 0], bright_pixels[-2:])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MCV pixel checks")
    def test_death_eye_mcv_restores_the_complete_screen_track(self):
        path = ROOT / "clien/Data/Video/explorer-5221012.mcv"
        track = parse_mcv(path.read_bytes())
        self.assertEqual((1280, 720), (track.width, track.height))
        self.assertEqual(15, len(track.delays))
        self.assertEqual(1780, sum(track.delays))
        self.assertEqual(240, track.delays[0])
        boxes = []
        with tempfile.TemporaryDirectory(prefix="death-eye-mcv-contract-") as name:
            decoder = start_decoder(shutil.which("ffmpeg"), track, Path(name), 0)
            for frame_index in range(len(track.delays)):
                frame = decoder.read_frame(frame_index)
                boxes.append(frame.getchannel("A").getbbox())
                frame.close()
            decoder.close()
        self.assertIsNone(boxes[0])
        self.assertTrue(all(box is not None for box in boxes[1:]))
        self.assertEqual(
            (0, 0, 1280, 673),
            (
                min(box[0] for box in boxes[1:]),
                min(box[1] for box in boxes[1:]),
                max(box[2] for box in boxes[1:]),
                max(box[3] for box in boxes[1:]),
            ),
        )

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MCV pixel checks")
    def test_fatal_trigger_mcv_preserves_all_timed_layers(self):
        path = ROOT / "clien/Data/Video/explorer-3221034.mcv"
        track = parse_mcv(path.read_bytes())
        self.assertEqual((1280, 720), (track.width, track.height))
        self.assertEqual(46, len(track.delays))
        self.assertEqual(3000, sum(track.delays))
        self.assertEqual(300, track.delays[0])
        boxes = []
        with tempfile.TemporaryDirectory(prefix="fatal-trigger-mcv-contract-") as name:
            decoder = start_decoder(shutil.which("ffmpeg"), track, Path(name), 0)
            for frame_index in range(len(track.delays)):
                frame = decoder.read_frame(frame_index)
                boxes.append(frame.getchannel("A").getbbox())
                frame.close()
            decoder.close()
        self.assertIsNone(boxes[0])
        self.assertEqual((34, 59, 1216, 679), boxes[-1])
        visible = [box for box in boxes if box is not None]
        self.assertEqual(
            (0, 0, 1280, 720),
            (
                min(box[0] for box in visible),
                min(box[1] for box in visible),
                max(box[2] for box in visible),
                max(box[3] for box in visible),
            ),
        )

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MCV pixel checks")
    def test_split_space_mcv_and_player_cover_the_full_render_target(self):
        path = ROOT / "clien/Data/Video/explorer-3221032.mcv"
        track = parse_mcv(path.read_bytes())
        self.assertEqual((1280, 720), (track.width, track.height))
        self.assertEqual(133, len(track.delays))
        boxes = []
        with tempfile.TemporaryDirectory(prefix="split-space-mcv-contract-") as name:
            decoder = start_decoder(shutil.which("ffmpeg"), track, Path(name), 0)
            for frame_index in range(len(track.delays)):
                frame = decoder.read_frame(frame_index)
                boxes.append(frame.getchannel("A").getbbox())
                frame.close()
            decoder.close()
        visible = [box for box in boxes if box is not None]
        self.assertGreaterEqual(
            sum(1 for box in visible if box[0] <= 10 and box[2] >= 1270),
            132,
        )
        self.assertEqual(
            (0, 0, 1280, 720),
            (
                min(box[0] for box in visible),
                min(box[1] for box in visible),
                max(box[2] for box in visible),
                max(box[3] for box in visible),
            ),
        )
        player = (ROOT / "tool/client-video/BeiDouVideo.cpp").read_text(
            encoding="utf-8"
        )
        for expected in (
            "renderTarget->GetDesc(&renderTargetDescription)",
            "fullViewport.Width = renderTargetDescription.Width",
            "fullViewport.Height = renderTargetDescription.Height",
            "device_->SetViewport(&fullViewport)",
        ):
            self.assertIn(expected, player)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MCV pixel checks")
    def test_bishop_mcv_tracks_preserve_source_timing_and_visible_tail(self):
        ffmpeg = shutil.which("ffmpeg")
        expected_frames = {2321037: 87, 2321042: 106}
        attack_times = {
            2321037: (
                30, 60, 90, 810,
                *range(930, 1171, 120),
                *range(1260, 1441, 90),
                *range(1500, 1681, 60),
                *range(1710, 2011, 30),
                *range(2040, 3061, 30),
            ),
            2321042: (
                *range(660, 1441, 60),
                *range(1860, 2221, 30),
            ),
        }
        self.assertEqual(60, len(attack_times[2321037]))
        self.assertEqual(27, len(attack_times[2321042]))
        for skill_id in (2321037, 2321042):
            path = ROOT / f"clien/Data/Video/explorer-{skill_id}.mcv"
            track = parse_mcv(path.read_bytes())
            self.assertEqual(expected_frames[skill_id], len(track.delays), skill_id)
            self.assertIn(30, track.delays, skill_id)
            boxes = []
            with tempfile.TemporaryDirectory(prefix=f"bishop-{skill_id}-contract-") as name:
                decoder = start_decoder(ffmpeg, track, Path(name), 0)
                for frame_index in range(len(track.delays)):
                    frame = decoder.read_frame(frame_index)
                    boxes.append(frame.getchannel("A").getbbox())
                    frame.close()
                decoder.close()
            frame_starts = []
            elapsed = 0
            for delay in track.delays:
                frame_starts.append(elapsed)
                elapsed += delay
            for attack_time in attack_times[skill_id]:
                frame_index = max(
                    index
                    for index, frame_start in enumerate(frame_starts)
                    if frame_start <= attack_time
                )
                self.assertIsNotNone(
                    boxes[frame_index], (skill_id, attack_time, frame_index)
                )
            self.assertIsNotNone(boxes[-1], skill_id)
            if skill_id == 2321042:
                self.assertEqual(30, track.delays[0])
                self.assertIsNone(boxes[0])
                self.assertIsNotNone(boxes[1])

    def test_all_video_field_markers_exist(self):
        path = ROOT / "clien/Data/Map/Effect.img"
        image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
        root = image.parse()
        for job in self.jobs:
            migration.configure(job)
            for marker in migration.engine.VIDEO_MARKERS:
                frame = root.get(f"customSkill/{job.config.key}/{marker}/0")
                self.assertIsInstance(frame, WzCanvasProperty)
                self.assertEqual((7, 5), (frame.width, frame.height))

    def test_howling_fist_marker_append_preserves_existing_buccaneer_records(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Map/Effect.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Map/Effect.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> tuple[tuple[str, ...], dict[str, bytes]]:
            image = WzImage.from_bytes(
                data, key=WzKey.for_region("GMS"), name=filename
            )
            _, _, _, names, spans, _ = migration.locate_nested_property_records(
                image, data, ("customSkill", "buccaneer")
            )
            return names, {
                name: data[start:end]
                for name, (start, end) in zip(names, spans)
            }

        baseline_names, baseline_records = records(baseline, "baseline-Effect.img")
        current_names, current_records = records(current, "Effect.img")
        marker = migration.BUCCANEER_HOWLING_FIST_VIDEO_MARKER
        expected_names = baseline_names if marker in baseline_names else (*baseline_names, marker)
        self.assertEqual(expected_names, current_names)
        for name, record in baseline_records.items():
            self.assertEqual(record, current_records[name], name)

    def test_death_eye_marker_append_preserves_existing_corsair_records(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Map/Effect.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Map/Effect.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> tuple[tuple[str, ...], dict[str, bytes]]:
            image = WzImage.from_bytes(
                data, key=WzKey.for_region("GMS"), name=filename
            )
            _, _, _, names, spans, _ = migration.locate_nested_property_records(
                image, data, ("customSkill", "corsair")
            )
            return names, {
                name: data[start:end]
                for name, (start, end) in zip(names, spans)
            }

        baseline_names, baseline_records = records(baseline, "baseline-Effect.img")
        current_names, current_records = records(current, "Effect.img")
        marker = migration.CORSAIR_DEATH_EYE_VIDEO_MARKER
        expected_names = baseline_names if marker in baseline_names else (*baseline_names, marker)
        self.assertEqual(expected_names, current_names)
        for name, record in baseline_records.items():
            self.assertEqual(record, current_records[name], name)

    def test_tms_multi_attack_timelines_are_wired(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        source_count = 0
        for job in self.jobs:
            for spec in job.skills:
                if spec.hidden:
                    continue
                schedule = migration.multi_attack_schedule(job, spec)
                if not schedule:
                    continue
                source_count += 1
                self.assertIn(f"Map.entry({spec.target_id},", compat)
                for replay_id, times in schedule.items():
                    self.assertRegex(compat, rf"replay\s*\(\s*{replay_id}\s*,")
                    self.assertEqual(list(times), sorted(times))
        self.assertEqual(20, source_count)

    def test_il_v_levels_follow_tms_formulas(self):
        job = next(job for job in self.jobs if job.config.key == "ilArchMage")
        client_path = ROOT / "clien/Data/Skill/222.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/222.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        for spec in job.skills:
            if spec.source_id not in migration.IL_LEGACY_ACTIONS:
                continue
            for level in (1, 15, 30):
                expected = migration.level_parameters(spec, level)
                client_level = client.get(f"skill/{spec.target_id}/level/{level}")
                server_level = server_skills.find(
                    f"./imgdir[@name='{spec.target_id}']/imgdir[@name='level']"
                    f"/imgdir[@name='{level}']"
                )
                server_values = {child.get("name"): child.get("value") for child in server_level}
                for name in ("damage", "attackCount", "mobCount", "mpCon", "cooltime"):
                    self.assertEqual(expected[name], int(client_level.get(name).value), (spec.target_id, level, name))
                    self.assertEqual(expected[name], int(server_values[name]), (spec.target_id, level, name))
                client_time = client_level.get("time")
                self.assertEqual(expected["time"], None if client_time is None else int(client_time.value))
                self.assertEqual(expected["time"], int(server_values["time"]) if "time" in server_values else None)

    def test_il_v_legacy_visual_nodes_are_recognizable(self):
        path = ROOT / "clien/Data/Skill/222.img"
        root = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        ).parse()
        expected_actions = {
            2221009: "blizzard",
            2221010: "chainlightning",
            2221013: "alert2",
            2221014: "chainlightning",
        }
        for skill_id, action in expected_actions.items():
            self.assertEqual(action, root.get(f"skill/{skill_id}/action/0").value)
        self.assertTrue(migration.engine.base.numeric_canvases(root.get("skill/2221010/hit/0")))
        for skill_id in (2221009, 2221013, 2221014):
            summon = root.get(f"skill/{skill_id}/summon")
            self.assertIsInstance(summon, WzSubProperty)
            self.assertEqual(
                {"summoned", "stand", "attack1", "die"},
                {child.name for child in summon.children()},
            )
            for action in summon.children():
                direct_canvas = (
                    skill_id == 2221013
                    or (skill_id == 2221009 and action.name != "attack1")
                    or action.name in {"summoned", "die"}
                )
                if direct_canvas:
                    self.assertTrue(migration.engine.base.numeric_canvases(action), (skill_id, action.name))
                    continue
                frames = action.children()
                self.assertTrue(frames, (skill_id, action.name))
                for frame in frames:
                    self.assertIsInstance(frame, WzUolProperty, (skill_id, action.name, frame.name))
                    resolved = frame.parent.get(frame.value)
                    self.assertIsInstance(resolved, WzCanvasProperty, (skill_id, action.name, frame.value))

    def test_il_nodes_use_only_legacy_shapes(self):
        path = ROOT / "clien/Data/Skill/222.img"
        root = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        ).parse()
        for skill_id, branch in (
            (2221009, "special2"),
            (2221009, "special3"),
            (2221013, "hit2"),
        ):
            self.assertIsNone(root.get(f"skill/{skill_id}/{branch}"), (skill_id, branch))

        merged_hit = root.get("skill/2221013/hit")
        self.assertGreaterEqual(len(merged_hit.children()), 6)
        for skill_id in (2221016, 2221017):
            mob = root.get(f"skill/{skill_id}/mob")
            self.assertTrue(migration.engine.base.numeric_canvases(mob), skill_id)
            self.assertTrue(all(
                isinstance(child, WzCanvasProperty)
                for child in mob.children()
            ), skill_id)

        for skill_id in (2221009, 2221014):
            summon = root.get(f"skill/{skill_id}/summon")
            for action_name in ("summoned", "die"):
                action = summon.get(action_name)
                self.assertTrue(migration.engine.base.numeric_canvases(action))
                self.assertTrue(all(
                    isinstance(child, WzCanvasProperty)
                    for child in action.children()
                ), (skill_id, action_name))

    def test_il_v_runtime_compatibility_is_wired(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("Map.entry(2221010,", compat)
        self.assertIn("replay(2221011, points(0, 600, 1200, 1800))", compat)
        self.assertIn("replay(2221012, points(300, 900, 1500, 2100))", compat)
        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MagicDamageHandler.java").read_text(
            encoding="utf-8"
        )
        for name, duration in {
            "ICE_AGE": "20_000",
            "SPIRIT_OF_SNOW": "30_000",
            "JUPITER_THUNDER": "40_000",
        }.items():
            self.assertIn(f"{name}_DURATION_MS = {duration}", handler)
            self.assertIn(f"attack.skill == ILArchMage.{name}", handler)
        self.assertIn("intervalTimes(3400, 3400, 37400)", handler)
        self.assertIn("ILArchMage.JUPITER_THUNDER_EXPLOSION, false", handler)

    def test_bishop_parameters_and_legacy_visual_nodes_are_complete(self):
        job = next(job for job in self.jobs if job.config.key == "bishop")
        specs = {spec.target_id: spec for spec in job.skills}
        balance = specs[2321020]
        self.assertEqual((1100, 10, 12), (
            balance.damage, balance.attack_count, balance.mob_count,
        ))
        self.assertEqual(2, specs[2321024].cooldown)

        path = ROOT / "clien/Data/Skill/232.img"
        root = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        ).parse()
        expected_summon_actions = {
            2321020: {"summoned", "stand", "fly", "attack1", "die"},
            2321031: {"summoned", "stand", "attack1", "die"},
        }
        for skill_id, expected in expected_summon_actions.items():
            summon = root.get(f"skill/{skill_id}/summon")
            self.assertIsInstance(summon, WzSubProperty, skill_id)
            self.assertEqual(expected, {child.name for child in summon.children()}, skill_id)
            for action in summon.children():
                self.assertTrue(
                    migration.engine.base.numeric_canvases(action),
                    (skill_id, action.name),
                )
        expected_summon_info = {
            2321020: ((-640, -210), (0, 30), 0, 660, 6),
            2321031: ((-290, -300), (290, 110), 0, 2000, 8),
        }
        for skill_id, (lt, rb, attack_type, attack_after, mob_count) in expected_summon_info.items():
            info = root.get(f"skill/{skill_id}/summon/attack1/info")
            self.assertIsInstance(info, WzSubProperty, skill_id)
            self.assertEqual(lt, (int(info.get("range/lt").x), int(info.get("range/lt").y)))
            self.assertEqual(rb, (int(info.get("range/rb").x), int(info.get("range/rb").y)))
            self.assertEqual(attack_type, int(info.get("type").value))
            self.assertEqual(attack_after, int(info.get("attackAfter").value))
            self.assertEqual(mob_count, int(info.get("mobCount").value))

        balance_level = root.get("skill/2321020/level/30")
        self.assertEqual(1100, int(balance_level.get("damage").value))
        self.assertEqual(11000, int(balance_level.get("mad").value))
        self.assertEqual(1, int(balance_level.get("attackCount").value))
        self.assertEqual(12, int(balance_level.get("mobCount").value))

        touch = root.get("skill/2321032/level/30")
        self.assertEqual(-44, int(touch.get("x").value))
        self.assertEqual(100, int(touch.get("prop").value))
        door_effect = root.get("skill/2321035/effect")
        self.assertIsInstance(door_effect, WzSubProperty)
        self.assertEqual(18, len(door_effect.children()))
        self.assertIsNone(root.get("skill/2321035/effect0"))
        door_special = root.get("skill/2321035/special")
        self.assertIsInstance(door_special, WzSubProperty)
        self.assertEqual(30, len(door_special.children()))
        self.assertIsNone(root.get("skill/2321035/special0"))
        self.assertEqual("chainlightning", root.get("skill/2321033/action/0").value)
        self.assertEqual("chainlightning", root.get("skill/2321035/action/0").value)
        for frame in door_special.children():
            self.assertIsInstance(frame, WzCanvasProperty)
            self.assertEqual(60, int(frame.get("delay").value))
            image = decode_canvas(frame)
            self.assertIsNotNone(image.getchannel("A").getbbox())
            image.close()
        punishment = root.get("skill/2321024/effect")
        punishment_duration = 0
        for frame in punishment.children():
            resolved = frame if isinstance(frame, WzCanvasProperty) else punishment.get(frame.value)
            self.assertIsInstance(resolved, WzCanvasProperty)
            delay = resolved.get("delay")
            punishment_duration += int(delay.value) if delay is not None else 100
        self.assertEqual(102, len(punishment.children()))
        self.assertEqual(6120, punishment_duration)
        for skill_id in range(2321020, 2321045):
            node = root.get(f"skill/{skill_id}")
            if node is None:
                continue
            stack = [node]
            while stack:
                current = stack.pop()
                if isinstance(current, WzCanvasProperty):
                    self.assertEqual((1, 0), (int(current.format), int(current.format2)), skill_id)
                if hasattr(current, "children"):
                    stack.extend(current.children())

    def test_bishop_client_patch_preserves_every_unmodified_raw_record(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Skill/232.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Skill/232.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> dict[str, bytes]:
            with tempfile.TemporaryDirectory(prefix="bishop-record-contract-") as name:
                path = Path(name) / filename
                path.write_bytes(data)
                image = WzImage.from_bytes(
                    data, key=WzKey.for_region("GMS"), name=filename
                )
                _, _, _, _, names, spans = migration.locate_client_skill_records(image, path)
                return {
                    skill_id: data[start:end]
                    for skill_id, (start, end) in zip(names, spans)
                }

        baseline_records = records(baseline, "baseline-232.img")
        current_records = records(current, "232.img")
        retired = {
            str(skill_id) for skill_id in (
                2321022, 2321023, 2321025, 2321026, 2321027, 2321028, 2321036,
            )
        }
        self.assertEqual(
            (*tuple(skill_id for skill_id in baseline_records if skill_id not in retired),
             str(migration.BISHOP_DIVINE_PUNISHMENT_REPLAY_ID)),
            tuple(current_records),
        )
        changed = {
            int(skill_id) for skill_id in baseline_records
            if skill_id not in retired
            and baseline_records[skill_id] != current_records[skill_id]
        }
        self.assertEqual(set(migration.BISHOP_CLIENT_REPLACEMENTS), changed)
        replay = current_records[str(migration.BISHOP_DIVINE_PUNISHMENT_REPLAY_ID)]
        self.assertTrue(replay)

        baseline_string = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/String/Skill.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        self.assertEqual(
            len(baseline_string),
            (ROOT / "clien/Data/String/Skill.img").stat().st_size,
        )

    def test_retired_bishop_skills_are_absent_without_shifting_retained_ids(self):
        job = next(job for job in self.jobs if job.config.key == "bishop")
        retired_sources = {
            400021070, 400021077, 2341000, 2341001, 2341002, 2341003, 2341013,
        }
        self.assertTrue(retired_sources.isdisjoint(job.target_by_source))
        self.assertEqual(2341006, job.source_by_target[2321031])
        self.assertEqual(2341007, job.source_by_target[2321032])
        self.assertEqual(2341009, job.source_by_target[2321033])
        self.assertEqual(2341011, job.source_by_target[2321035])
        self.assertEqual(2341500, job.source_by_target[2321037])
        self.assertEqual(2341507, job.source_by_target[2321042])

        retired_ids = (
            2321022, 2321023, 2321025, 2321026, 2321027, 2321028, 2321036,
        )
        client_path = ROOT / "clien/Data/Skill/232.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            string_path.read_bytes(), key=WzKey.for_region("GMS"), name=string_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/232.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        for skill_id in retired_ids:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)

        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for skill_id in retired_ids:
            self.assertIn(f'cmp esi, {skill_id}\\n"\n        "je explorer_bishop_active_next', cpp)

    def test_bishop_server_compatibility_is_wired(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("replay(2321044, range(240, 240, 4800))", compat)

        stat_effect = (ROOT / "gms-server/src/main/java/org/gms/server/StatEffect.java").read_text(
            encoding="utf-8"
        )
        for constant in ("ANGEL_OF_BALANCE", "FOUNTAIN_FOR_ANGEL_VI"):
            self.assertIn(f"case Bishop.{constant}:", stat_effect)
        self.assertIn("case Bishop.ANGELIC_TOUCH_VI:", stat_effect)
        self.assertIn("monsterStatus.put(MonsterStatus.WDEF, ret.x);", stat_effect)

        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MagicDamageHandler.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("points(30, 60, 90, 810)", compat)
        self.assertIn("replay(2321041, range(2040, 30, 3060))", compat)
        self.assertIn("replay(2321042, range(660, 60, 1440))", compat)
        self.assertIn("replay(2321043, range(1860, 30, 2220))", compat)
        self.assertIn("Bishop.isVViSummonSkill(attack.skill)", handler)
        self.assertIn("intervalTimes(2000, 2000, 60000)", handler)
        self.assertIn("scheduleFountainForAngelViAttacks", handler)
        self.assertIn("private static void showDamageNumbers(", handler)
        self.assertIn("chr.sendPacket(PacketCreator.damageMonster(", handler)
        self.assertNotIn("needsServerTargetExpansion", handler)
        self.assertNotIn("replaceAttackTargets(attack", handler)
        self.assertIn("new ArrayList<>(expectedMap.getAllMonsters())", handler)
        self.assertIn("thenComparingInt(Monster::getObjectId)", handler)
        self.assertIn("chr.getMap().broadcastMessage(chr, packet, false, true);", handler)

        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/232.img.xml").getroot()
        balance = server.find("./imgdir[@name='skill']/imgdir[@name='2321020']/imgdir[@name='level']/imgdir[@name='30']")
        self.assertEqual("10", balance.find("./int[@name='attackCount']").get("value"))
        self.assertEqual("1100", balance.find("./int[@name='damage']").get("value"))
        self.assertEqual("1100", balance.find("./int[@name='mad']").get("value"))
        self.assertEqual("12", balance.find("./int[@name='mobCount']").get("value"))

        summon_handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/SummonDamageHandler.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("summon.getSkill() == Bishop.ANGEL_OF_BALANCE", summon_handler)
        self.assertIn("summonEffect.getAttackCount()", summon_handler)
        self.assertIn("if (attack.skill == Bishop.HEAVENS_DOOR_VI) {", handler)
        self.assertIn("PacketCreator.showOwnBuffEffect(attack.skill, 2)", handler)
        self.assertIn("PacketCreator.showBuffEffect(chr.getId(), attack.skill, 2)", handler)

        bishop = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/Bishop.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("DIVINE_PUNISHMENT_HIT = 2321044", bishop)
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn('call _QueueVideoSkill\\n"', cpp[cpp.index("explorer_bishop_magic_active:"):])
        self.assertIn('cmp esi, 2321044\\n"\n        "jbe explorer_bishop_magic_active', cpp)
        self.assertIn('je explorer_bishop_summon_active\\n"', cpp)
        self.assertIn('push 0x009689DF\\n"', cpp)
        self.assertIn("Angel of Balance summon behavior", cpp)
        self.assertIn("Angel of Balance summon attack", cpp)
        self.assertIn("cmp dword ptr [ebx + 0xB4], 2321020", cpp)
        self.assertIn("cmp eax, 2321020", cpp)
        for skill_id in (2321024, 2321044, 2321032, 2321033, 2321035, 2321037, 2321042):
            self.assertIn(f'cmp eax, {skill_id}\\n"', cpp)
        self.assertIn("Bishop magic AoE classifier", cpp)

        self.assertIn("PacketCreator.magicAttack(", handler)
        self.assertIn("showDamageNumbers(chr, expectedMap, damage)", handler)
        self.assertNotIn("cosmosReplay.scheduleTrackingCloseAttacks(", handler)
        high_visual = cpp[cpp.index("void HookHighSkillVisualBranch()"):cpp.index("void HookBrandishActionType()")]
        self.assertNotIn("2321044", high_visual)
        brandish_hooks = cpp[cpp.index("void HookBrandishActionType()"):cpp.index("const unsigned char kKeyboardDispatchOriginal")]
        self.assertNotIn("2321044", brandish_hooks)

        client_path = ROOT / "clien/Data/Skill/232.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        replay = client.get("skill/2321044")
        self.assertIsInstance(replay, WzSubProperty)
        self.assertIsNone(replay.get("effect"))
        self.assertIsNotNone(replay.get("hit/0"))
        self.assertEqual(1, int(replay.get("invisible").value))
        active_block = re.search(r"V_VI_ACTIVE_ATTACKS\s*=\s*\{([^}]*)}", bishop, re.S)
        self.assertNotIn("2321044", active_block.group(1))
        string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            string_path.read_bytes(), key=WzKey.for_region("GMS"), name=string_path.name
        ).parse()
        self.assertIsNone(client_string.get("2321044"))

    def test_buccaneer_retired_skills_are_absent_without_shifting_ids(self):
        job = next(job for job in self.jobs if job.config.key == "buccaneer")
        self.assertTrue(
            migration.BUCCANEER_RETIRED_SOURCE_IDS.isdisjoint(job.target_by_source)
        )
        self.assertEqual(400051042, job.source_by_target[5121014])
        self.assertEqual(400051070, job.source_by_target[5121015])
        self.assertEqual(5140004, job.source_by_target[5121017])
        self.assertEqual(5141009, job.source_by_target[5121024])
        self.assertEqual(5141011, job.source_by_target[5121025])

        client_path = ROOT / "clien/Data/Skill/512.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            string_path.read_bytes(), key=WzKey.for_region("GMS"), name=string_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/512.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for skill_id in migration.BUCCANEER_RETIRED_SKILL_IDS:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIn(
                f'cmp esi, {skill_id}\\n"\n        "je explorer_buccaneer_active_next',
                cpp,
            )

    def test_buccaneer_retirement_preserves_unmanaged_raw_records(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Skill/512.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Skill/512.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> dict[int, bytes]:
            with tempfile.TemporaryDirectory(prefix="buccaneer-record-contract-") as name:
                path = Path(name) / filename
                path.write_bytes(data)
                image = WzImage.from_bytes(
                    data, key=WzKey.for_region("GMS"), name=filename
                )
                _, _, _, _, names, spans = migration.locate_client_skill_records(
                    image, path
                )
                return {
                    int(skill_id): data[start:end]
                    for skill_id, (start, end) in zip(names, spans)
                }

        baseline_records = records(baseline, "baseline-512.img")
        current_records = records(current, "512.img")
        retired = set(migration.BUCCANEER_RETIRED_SKILL_IDS)
        self.assertEqual(
            tuple(skill_id for skill_id in baseline_records if skill_id not in retired),
            tuple(current_records),
        )
        changed = {
            skill_id for skill_id in current_records
            if baseline_records[skill_id] != current_records[skill_id]
        }
        managed = set(migration.BUCCANEER_CLIENT_REPLACEMENT_IDS)
        self.assertTrue(changed.issubset(managed), changed - managed)
        self.assertIn(migration.BUCCANEER_SEA_DRAGON_CHARGE_ID, changed)
        for skill_id in current_records.keys() - changed:
            self.assertEqual(baseline_records[skill_id], current_records[skill_id])

    def test_corsair_retired_skills_are_absent_without_shifting_ids(self):
        job = next(job for job in self.jobs if job.config.key == "corsair")
        self.assertTrue(
            migration.CORSAIR_RETIRED_SOURCE_IDS.isdisjoint(job.target_by_source)
        )
        self.assertEqual(5241005, job.source_by_target[5221022])
        self.assertEqual(5241018, job.source_by_target[5221030])
        self.assertEqual(5241500, job.source_by_target[5221032])
        self.assertEqual(5241503, job.source_by_target[5221034])
        corsair = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/Corsair.java").read_text(
            encoding="utf-8"
        )
        active = re.search(r"V_VI_ACTIVE_ATTACKS\s*=\s*\{([^}]*)}", corsair, re.S)
        self.assertIsNotNone(active)
        self.assertEqual(
            [spec.target_id for spec in job.skills if not spec.hidden],
            [int(value) for value in re.findall(r"\d+", active.group(1))],
        )

        client_path = ROOT / "clien/Data/Skill/522.img"
        client = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        ).parse()
        string_path = ROOT / "clien/Data/String/Skill.img"
        client_string = WzImage.from_bytes(
            string_path.read_bytes(), key=WzKey.for_region("GMS"), name=string_path.name
        ).parse()
        server = ET.parse(ROOT / "gms-server/wz/Skill.wz/522.img.xml").getroot()
        server_skills = server.find("./imgdir[@name='skill']")
        server_string = ET.parse(ROOT / "gms-server/wz/String.wz/Skill.img.xml").getroot()
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        for skill_id in migration.CORSAIR_RETIRED_SKILL_IDS:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(client_string.get(str(skill_id)), skill_id)
            self.assertIsNone(server_skills.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(server_string.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIn(
                f'cmp esi, {skill_id}\\n"\n        "je explorer_corsair_active_next',
                cpp,
            )
            target_limit = cpp[cpp.index("LONG CustomRangedTargetLimit"):
                               cpp.index("bool IsExplorerRangedSkill")]
            self.assertNotIn(f"case {skill_id}:", target_limit)
        self.assertIn("&& !retiredCorsairSkill", cpp)

        grant = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/冒险家五六转攻击技能.js").read_text(
            encoding="utf-8"
        )
        retired = ", ".join(str(value) for value in migration.CORSAIR_RETIRED_SKILL_IDS)
        self.assertIn(f"retiredBindings: [{retired}]", grant)
        self.assertIn(f"retiredSkills: [{retired}]", grant)

    def test_corsair_retirement_preserves_every_retained_raw_record(self):
        baseline = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/Skill/522.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_path = ROOT / "clien/Data/Skill/522.img"
        current = current_path.read_bytes()

        def records(data: bytes, filename: str) -> dict[int, bytes]:
            with tempfile.TemporaryDirectory(prefix="corsair-record-contract-") as name:
                path = Path(name) / filename
                path.write_bytes(data)
                image = WzImage.from_bytes(
                    data, key=WzKey.for_region("GMS"), name=filename
                )
                _, _, _, _, names, spans = migration.locate_client_skill_records(
                    image, path
                )
                return {
                    int(skill_id): data[start:end]
                    for skill_id, (start, end) in zip(names, spans)
                }

        baseline_records = records(baseline, "baseline-522.img")
        current_records = records(current, "522.img")
        retired = set(migration.CORSAIR_RETIRED_SKILL_IDS)
        self.assertEqual(
            tuple(skill_id for skill_id in baseline_records if skill_id not in retired),
            tuple(current_records),
        )
        for skill_id, record in current_records.items():
            self.assertEqual(baseline_records[skill_id], record, skill_id)

        baseline_string = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:clien/Data/String/Skill.img"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        current_string = (ROOT / "clien/Data/String/Skill.img").read_bytes()
        self.assertEqual(len(baseline_string), len(current_string))
        with tempfile.TemporaryDirectory(prefix="corsair-string-contract-") as name:
            baseline_path = Path(name) / "Skill.img"
            baseline_path.write_bytes(baseline_string)
            _, locations = migration.top_level_name_locations(baseline_path)
        allowed_spans = [
            (locations[str(skill_id)][0], locations[str(skill_id)][1])
            for skill_id in migration.CORSAIR_RETIRED_SKILL_IDS
        ]
        changed_offsets = {
            offset
            for offset, (before, after) in enumerate(zip(baseline_string, current_string))
            if before != after
        }
        self.assertTrue(changed_offsets)
        self.assertTrue(all(
            any(start <= offset < start + length for start, length in allowed_spans)
            for offset in changed_offsets
        ))

    def test_corsair_nautilus_schedule_and_death_eye_effects_are_complete(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("Map.entry(5221013, replays(", compat)
        self.assertIn("replay(5221014, range(990, 120, 1710))", compat)
        self.assertIn("replay(5221015, range(3420, 100, 6920))", compat)
        self.assertIn(
            'case 5221012, 5221032, 5221034 -> "customSkill/corsair/video" + skillId;',
            compat,
        )
        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("ExplorerOtherSkillCompat.multiAttacks(skillId) != null", handler)
        self.assertIn("applyAttackCostOnly(attack, chr, bulletCount);", handler)
        self.assertIn("new Point(chr.getPosition())", handler)
        self.assertIn("canContinueTrackingAttack(chr, expectedMap)", handler)

        path = ROOT / "clien/Data/Skill/522.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        root = image.parse()
        self.assertFalse(image.truncated)
        self.assertFalse(image.parse_warnings)
        expected = {
            "skill/5221012/effect": 13,
            "skill/5221012/mob/0": 43,
            "skill/5221012/hit/0": 10,
        }
        for node_path, frame_count in expected.items():
            frames = migration.engine.base.numeric_canvases(root.get(node_path))
            self.assertEqual(frame_count, len(frames), node_path)
            for frame in frames:
                self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
                decoded = decode_canvas(frame, region="GMS")
                self.assertIsNotNone(decoded.getchannel("A").getbbox(), node_path)
                decoded.close()
        self.assertIsNone(root.get("skill/5221012/screen"))

    def test_buccaneer_repaired_effects_are_complete(self):
        path = ROOT / "clien/Data/Skill/512.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        root = image.parse()
        self.assertFalse(image.truncated)
        self.assertFalse(image.parse_warnings)
        for skill_id in migration.BUCCANEER_CLIENT_REPLACEMENT_IDS:
            self.assertIsNone(root.get(f"skill/{skill_id}/weapon"), skill_id)
            self.assertIsNone(root.get(f"skill/{skill_id}/weapon2"), skill_id)

        expected = {
            "skill/5121015/effect": (32, 1920),
            "skill/5121016/special/0": (38, 4770),
            "skill/5121017/effect": (17, 1080),
            "skill/5121017/hit/0": (12, 720),
            "skill/5121025/effect": (16, 960),
            "skill/5121025/special/0": (11, 660),
            "skill/5121026/effect": (19, 1710),
            "skill/5121026/hit/0": (7, 420),
            "skill/5121027/effect": (12, 720),
            "skill/5121027/ball": (12, 720),
            "skill/5121027/hit/0": (7, 630),
        }
        for node_path, (frame_count, duration) in expected.items():
            frames = migration.engine.base.numeric_canvases(root.get(node_path))
            self.assertEqual(frame_count, len(frames), node_path)
            self.assertEqual(
                duration,
                sum(int(frame.get("delay").value) for frame in frames),
                node_path,
            )
            for frame in frames:
                self.assertEqual((1, 0), (int(frame.format), int(frame.format2)))
                decoded = decode_canvas(frame, region="GMS")
                self.assertIsNotNone(decoded.getchannel("A").getbbox(), node_path)
                decoded.close()

        for property_name, expected_value in (
                migration.BUCCANEER_SERPENT_ASSAULT_HIT_METADATA.items()):
            value = root.get(f"skill/5121026/hit/0/{property_name}")
            self.assertIsNotNone(value, property_name)
            self.assertEqual(expected_value, int(value.value), property_name)
        self.assertEqual("rush2", root.get("skill/5121014/action/0").value)
        self.assertEqual("swingO1", root.get("skill/5121025/action/0").value)

        finish = migration.engine.base.numeric_canvases(
            root.get("skill/5121016/special/0")
        )
        self.assertTrue(all(frame.width == 1280 for frame in finish))
        self.assertIsNone(root.get("skill/5121016/effect"))

    def test_buccaneer_server_timelines_and_grants_are_wired(self):
        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("Map.entry(5121015, replays(", compat)
        self.assertIn("replay(5121015, points(1920))", compat)
        self.assertIn("2040, 2760, 3000, 3180", compat)
        self.assertIn("Map.entry(5121025, replays(", compat)
        for value in (
            "replay(5121025, points(0))",
            "replay(5121026, points(240))",
            "replay(5121027, points(1080))",
        ):
            self.assertIn(value, compat)

        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java").read_text(
            encoding="utf-8"
        )
        cpp = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("attack.skill == Buccaneer.SEA_DRAGON_FIST", handler)
        self.assertIn("Buccaneer.SEA_DRAGON_FIST_FINISH", handler)
        self.assertNotIn("showBuccaneerSpecialEffect", handler)
        self.assertNotIn("BUCCANEER_HOWLING_FIST_FINISH_DELAY_MS", handler)
        self.assertIn(
            "replay.skillId() == Buccaneer.SEA_DRAGON_FIST_FINISH", handler
        )
        self.assertIn("showLocalDamageNumbers", handler)
        self.assertIn("BUCCANEER_SERPENT_TRACE schedule", handler)
        self.assertIn("BUCCANEER_SERPENT_TRACE stage={}", handler)
        self.assertIn("effectContext=type1", handler)
        self.assertIn(
            "replaySkillId == Buccaneer.SEA_DRAGON_ASSAULT_VI", handler
        )
        self.assertIn("showBuccaneerSerpentAssaultEffect(chr);", handler)
        self.assertIn("packet=CLOSE_RANGE_ATTACK", handler)
        self.assertIn("appliedTargets={}", handler)
        self.assertIn(
            "replaySkillId == Buccaneer.SEA_DRAGON_FIST_FINISH", handler
        )
        self.assertIn("attackOrigin.x - 1000", handler)
        self.assertIn("Howling Fist finish skill={} targets={} bounds={}", handler)
        self.assertIn(
            "kBuccaneerSeaDragonChargeRushClassifierAddress = 0x00952E0D", cpp
        )
        self.assertIn("cmp dword ptr [ebp - 0x10], 5121014", cpp)
        self.assertNotIn("cmp dword ptr [ebp - 0x10], 5121025", cpp)
        self.assertIn("push 0x00952E14", cpp)
        self.assertIn("push 0x00952E2C", cpp)
        self.assertIn(
            "kBuccaneerSeaDragonChargeRushOriginal[] = {0x81, 0x7D, 0xF0, 0xEE, 0x1A, 0x11, 0x00}",
            cpp,
        )
        self.assertIn(
            'case 5121015, 5121029, 5121035 -> "customSkill/buccaneer/video" + skillId;',
            compat,
        )

        grant = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/冒险家五六转攻击技能.js").read_text(
            encoding="utf-8"
        )
        retired = ", ".join(str(value) for value in migration.BUCCANEER_RETIRED_SKILL_IDS)
        self.assertIn(f"retiredBindings: [{retired}]", grant)
        self.assertIn(f"retiredSkills: [{retired}]", grant)


if __name__ == "__main__":
    unittest.main()
