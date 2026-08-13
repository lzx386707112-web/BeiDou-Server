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
import patch_shadower_dual_blade_skin as lower_job_migration  # noqa: E402
from patch_shadower_dual_blade_skin import locate_root_records  # noqa: E402
from export_thunder_breaker_mcvs import parse_mcv  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402


BASELINE = Path("/tmp/beidou-dual-v-vi-baseline.lEtAmh")
CLIENT_SKILL = ROOT / "clien/Data/Skill/422.img"
CLIENT_STRING = ROOT / "clien/Data/String/Skill.img"
SERVER_SKILL = ROOT / "gms-server/wz/Skill.wz/422.img.xml"
SERVER_STRING = ROOT / "gms-server/wz/String.wz/Skill.img.xml"
JAVA_SKILLS = ROOT / "gms-server/src/main/java/org/gms/constants/skills/Shadower.java"
JAVA_HANDLER = ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
DLL_SOURCE = ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"

SOURCE_TO_TARGET = {
    source_id: target_id for target_id, source_id in enumerate(
        migration.SHADOWER_DUAL_BLADE_SOURCE_IDS, start=4221009
    )
}
ACTIVE_IDS = (4221009, 4221010, 4221011, 4221018, 4221019,
              4221020, 4221022, 4221023, 4221027)
MANAGED = set(range(4221009, 4221030))
RETIRED = set(range(4221030, 4221041))
RESTORED_AUXILIARY = set(lower_job_migration.LEGACY_AUXILIARY_SKILLS)
LOWER_JOB_ATTACKS = {spec.target_id for spec in lower_job_migration.ATTACK_SPECS}
FOURTH_JOB_ATTACKS = {
    skill_id for skill_id in LOWER_JOB_ATTACKS if skill_id // 10000 == 422
}
EXPECTED_RANGES = {
    4221011: ((-270, -450), (285, 45)),
    4221012: ((-650, -370), (100, 0)),
    4221018: ((-550, -370), (210, 160)),
    4221020: ((-350, -270), (380, 105)),
}


def parse_image(path: Path):
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError((image.truncated, image.parse_warnings))
    return image, root


def skill_records(path: Path):
    data = path.read_bytes()
    image, _ = parse_image(path)
    *_, names, spans = migration.locate_client_skill_records(image, path)
    return tuple(map(int, names)), {
        int(name): data[start:end]
        for name, (start, end) in zip(names, spans)
    }


def string_records(path: Path):
    data = path.read_bytes()
    image, _ = parse_image(path)
    _, _, names, spans = locate_root_records(image, data, path)
    return names, {
        name: data[start:end] for name, (start, end) in zip(names, spans)
    }


def root_record(path: Path, wanted: str) -> bytes:
    data = path.read_bytes()
    image, _ = parse_image(path)
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise AssertionError("invalid root")
    reader.skip(2)
    for _ in range(reader.read_compressed_int()):
        start = reader.position
        name = reader.read_string_block(0)
        if reader.read_byte() != 9:
            raise AssertionError(name)
        size = reader.read_u32()
        reader.seek(reader.position + size)
        if name == wanted:
            return data[start:reader.position]
    raise AssertionError(wanted)


class ShadowerDualBladeVVIContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BASELINE.is_dir():
            raise unittest.SkipTest(f"task baseline missing: {BASELINE}")
        cls.job = next(
            job for job in migration.build_runtime_jobs()
            if job.config.key == "shadower"
        )

    def test_fixed_source_mapping_and_public_entry_array(self):
        self.assertEqual(SOURCE_TO_TARGET, self.job.target_by_source)
        self.assertEqual(ACTIVE_IDS, tuple(
            spec.target_id for spec in self.job.skills if not spec.hidden
        ))
        text = JAVA_SKILLS.read_text(encoding="utf-8")
        block = re.search(r"V_VI_ACTIVE_ATTACKS\s*=\s*\{([^}]*)}", text, re.S)
        self.assertIsNotNone(block)
        self.assertEqual(ACTIVE_IDS, tuple(map(int, re.findall(r"\d+", block.group(1)))))

    def test_client_skill_raw_record_contract(self):
        before_order, before = skill_records(BASELINE / "422.img")
        after_order, after = skill_records(CLIENT_SKILL)
        self.assertEqual(tuple(i for i in before_order if i not in RETIRED), after_order)
        self.assertEqual(
            MANAGED | FOURTH_JOB_ATTACKS,
            {i for i in after if before[i] != after[i]},
        )
        self.assertEqual(RETIRED, set(before) - set(after))
        for skill_id in set(after) - MANAGED - FOURTH_JOB_ATTACKS:
            self.assertEqual(before[skill_id], after[skill_id], skill_id)
        with self.assertRaises(AssertionError):
            root_record(CLIENT_SKILL, "dualBladeSkin")

    def test_client_string_only_approved_records_change_without_shifting(self):
        before_path = BASELINE / "Skill.img"
        self.assertEqual(before_path.stat().st_size, CLIENT_STRING.stat().st_size)
        before_order, before = string_records(before_path)
        after_order, after = string_records(CLIENT_STRING)
        self.assertEqual(before_order, after_order)
        changed = {int(name) for name in after if before[name] != after[name]}
        self.assertEqual(
            MANAGED | RETIRED | RESTORED_AUXILIARY | LOWER_JOB_ATTACKS,
            changed,
        )

    def test_all_v_vi_skills_have_no_weapon_restriction(self):
        _, root = parse_image(CLIENT_SKILL)
        for skill_id in MANAGED:
            node = root.get(f"skill/{skill_id}")
            for name in ("weapon", "weapon2", "subWeapon"):
                self.assertIsNone(node.get(name), (skill_id, name))

        server = ET.parse(SERVER_SKILL).getroot().find("./imgdir[@name='skill']")
        for skill_id in MANAGED:
            node = server.find(f"./imgdir[@name='{skill_id}']")
            for name in ("weapon", "weapon2", "subWeapon"):
                self.assertIsNone(node.find(f"./*[@name='{name}']"), (skill_id, name))

    def test_corrected_damage_ranges_match_client_and_server(self):
        _, client = parse_image(CLIENT_SKILL)
        server = ET.parse(SERVER_SKILL).getroot().find("./imgdir[@name='skill']")
        for skill_id, expected in EXPECTED_RANGES.items():
            client_skill = client.get(f"skill/{skill_id}")
            server_skill = server.find(f"./imgdir[@name='{skill_id}']")
            for level in (1, 30):
                client_level = client_skill.get(f"level/{level}")
                client_range = tuple(
                    (int(client_level.get(name).x), int(client_level.get(name).y))
                    for name in ("lt", "rb")
                )
                server_level = server_skill.find(f"./imgdir[@name='level']/imgdir[@name='{level}']")
                server_range = tuple(
                    (int(server_level.find(f"./vector[@name='{name}']").get("x")),
                     int(server_level.find(f"./vector[@name='{name}']").get("y")))
                    for name in ("lt", "rb")
                )
                self.assertEqual(expected, client_range, (skill_id, level, "client"))
                self.assertEqual(expected, server_range, (skill_id, level, "server"))

    def test_shadower_physical_levels_have_no_magic_or_bullet_fields(self):
        _, client = parse_image(CLIENT_SKILL)
        for skill_id in MANAGED:
            for level in range(1, migration.MASTER_LEVEL + 1):
                node = client.get(f"skill/{skill_id}/level/{level}")
                self.assertIsNone(node.get("mad"), (skill_id, level, "mad"))
                self.assertIsNone(
                    node.get("bulletCount"), (skill_id, level, "bulletCount")
                )

    def test_karma_fury_parameters_and_effect_contract(self):
        _, client = parse_image(CLIENT_SKILL)
        skill = client.get("skill/4221010")
        for level, damage in ((1, 416), (30, 880)):
            node = skill.get(f"level/{level}")
            self.assertEqual(damage, int(node.get("damage").value))
            self.assertEqual(7, int(node.get("attackCount").value))
            self.assertEqual(12, int(node.get("mobCount").value))
            self.assertEqual(500, int(node.get("mpCon").value))
            self.assertEqual(10, int(node.get("cooltime").value))
            self.assertEqual((-460, -530), (int(node.get("lt").x), int(node.get("lt").y)))
            self.assertEqual((460, 60), (int(node.get("rb").x), int(node.get("rb").y)))

        effect = migration.engine.base.numeric_canvases(skill.get("effect"))
        hit_canvases = [
            node for variant in skill.get("hit").children()
            for node in migration.engine.base.numeric_canvases(variant)
        ]
        self.assertEqual(26, len(effect))
        self.assertEqual(1650, sum(int(frame.get("delay").value) for frame in effect))
        self.assertEqual(14, len(hit_canvases))

        compat = (ROOT / "gms-server/src/main/java/org/gms/constants/skills/ExplorerOtherSkillCompat.java").read_text(encoding="utf-8")
        replay = re.search(r"Map\.entry\(4221010, replays\(replay\(\s*4221010, points\(([^)]*)\)", compat)
        self.assertIsNotNone(replay)
        self.assertEqual((0, 180, 360, 540, 720), tuple(map(int, re.findall(r"\d+", replay.group(1)))))

    def test_retired_slots_are_absent_from_runtime_resources(self):
        _, client = parse_image(CLIENT_SKILL)
        server = ET.parse(SERVER_SKILL).getroot().find("./imgdir[@name='skill']")
        strings = ET.parse(SERVER_STRING).getroot()
        for skill_id in RETIRED:
            self.assertIsNone(client.get(f"skill/{skill_id}"), skill_id)
            self.assertIsNone(server.find(f"./imgdir[@name='{skill_id}']"), skill_id)
            self.assertIsNone(strings.find(f"./imgdir[@name='{skill_id}']"), skill_id)

    def test_all_migrated_canvases_are_visible_gms_argb4444(self):
        _, root = parse_image(CLIENT_SKILL)
        canvases = []
        for skill_id in MANAGED:
            stack = [root.get(f"skill/{skill_id}")]
            while stack:
                node = stack.pop()
                if isinstance(node, WzCanvasProperty):
                    canvases.append((skill_id, node))
                if hasattr(node, "children"):
                    stack.extend(node.children())
        self.assertEqual(575, len(canvases))
        for skill_id, canvas in canvases:
            self.assertEqual((1, 0), (int(canvas.format), int(canvas.format2)))
            decoded = decode_canvas(canvas, region="GMS")
            self.assertIsNotNone(decoded.getbbox(), skill_id)
            decoded.close()

    def test_mcv_and_dll_video_routes(self):
        for skill_id, duration, frames in ((4221023, 3360, 56), (4221027, 960, 16)):
            data = (ROOT / f"clien/Data/Video/explorer-{skill_id}.mcv").read_bytes()
            track = parse_mcv(data)
            self.assertEqual((1280, 720, frames, duration), (
                track.width, track.height, len(track.delays), sum(track.delays)
            ))
        dll = DLL_SOURCE.read_text(encoding="utf-8")
        self.assertIn("4221023", dll)
        self.assertIn("4221027", dll)

    def test_hidden_follow_ups_are_not_granted_and_use_tms_triggers(self):
        handler = JAVA_HANDLER.read_text(encoding="utf-8")
        self.assertIn("attack.skill == Shadower.BLADE_FURY_VI", handler)
        self.assertIn("attack.skill == Shadower.PHANTOM_BLOW_VI", handler)
        self.assertIn("SUDDEN_RAID_TRIGGER_HITS = 15", handler)
        self.assertIn("SUDDEN_RAID_MAX_STORED_HITS = 60", handler)
        script = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/冒险家五六转攻击技能.js").read_text(encoding="utf-8")
        for skill_id in MANAGED - set(ACTIVE_IDS):
            self.assertNotRegex(script, rf"\b{skill_id}\b.*changeSkillLevel")


if __name__ == "__main__":
    unittest.main()
