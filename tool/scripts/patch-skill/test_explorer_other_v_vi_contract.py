#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
CLIENT_VIDEO = ROOT / "tool" / "client-video"
WZPY = ROOT / "tool" / "wz-python"
sys.path[:0] = [str(PATCH_SKILL), str(CLIENT_VIDEO), str(WZPY)]

import patch_explorer_other_v_vi as migration  # noqa: E402
from export_thunder_breaker_mcvs import parse_mcv  # noqa: E402
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
    232: (2321020, 2321043, "explorer_magic_active"),
    312: (3121010, 3121032, "explorer_ranged_active"),
    322: (3221009, 3221035, "explorer_ranged_active"),
    412: (4121010, 4121029, "explorer_ranged_active"),
    422: (4221009, 4221040, "explorer_melee_active"),
    512: (5121011, 5121036, "explorer_melee_active"),
    522: (5221011, 5221035, "explorer_ranged_active"),
}

MCV_DURATIONS_MS = {
    2121032: 6660, 2121035: 4860,
    2221027: 5520, 2221030: 2520,
    2321037: 4380, 2321042: 3240,
    3121029: 4560, 3121031: 1560,
    3221032: 7980, 3221034: 1740,
    4121026: 3780, 4121028: 2760,
    4221036: 5100, 4221039: 2400,
    5121029: 5100, 5121035: 2340,
    5221032: 4740, 5221034: 2460,
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

    def test_overloaded_tms_time_fields_use_legacy_seconds(self):
        expected = {
            2221014: 40,
            3121012: None,
            3121024: 60,
            3221017: None,
            3221018: None,
            3221020: None,
            5121019: 10,
            5121020: None,
            5221012: None,
            5221013: None,
        }
        specs = {spec.target_id: spec for job in self.jobs for spec in job.skills}
        for skill_id, duration in expected.items():
            self.assertEqual(duration, specs[skill_id].duration_seconds, skill_id)

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
                if not spec.hidden and "<video " in metadata.read_text(encoding="utf-8"):
                    video_specs.append(spec)
        self.assertEqual(18, len(video_specs))
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


if __name__ == "__main__":
    unittest.main()
