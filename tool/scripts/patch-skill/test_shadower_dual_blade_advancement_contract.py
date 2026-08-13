#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool/scripts/patch-skill"
WZPY = ROOT / "tool/wz-python"
sys.path[:0] = [str(PATCH_SKILL), str(WZPY)]

import patch_explorer_other_v_vi as migration  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzSubProperty, WzVectorProperty  # noqa: E402


QUICK_JOB = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/快速转职.js"
MAX_SKILLS = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/技能全满.js"
FOURTH_JOB_NPC = ROOT / "gms-server/scripts-zh-CN/npc/2081400.js"
CHARACTER = ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
SHADOWER = ROOT / "gms-server/src/main/java/org/gms/constants/skills/Shadower.java"

FIRST_JOB_HASH = "bb230c5ef1364bc2d7ac0eb7cfa59d0bbd6548f616365894ae06fc12e2a0ef75"
FOURTH_JOB_ATTACKS = (4221001, 4221003, 4221004, 4221007)
PUBLIC_V_VI = (4221009, 4221010, 4221011, 4221018, 4221019,
               4221020, 4221022, 4221023, 4221027)


def parse_img(path: Path):
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError((path, image.truncated, image.parse_warnings))
    return root


def parse_img_bytes(data: bytes, name: str):
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=name)
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError((name, image.truncated, image.parse_warnings))
    return root


def property_signature(node):
    if isinstance(node, WzSubProperty):
        return tuple(property_signature(child) for child in node.children())
    if isinstance(node, WzVectorProperty):
        return node.name, int(node.x), int(node.y)
    return node.name, node.value


def values(node) -> dict[str, str]:
    return {child.get("name"): child.get("value") for child in node}


class ShadowerDualBladeAdvancementContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_string = parse_img(ROOT / "clien/Data/String/Skill.img")
        cls.consume_string = parse_img(ROOT / "clien/Data/String/Consume.img")
        cls.quick_job = QUICK_JOB.read_text(encoding="utf-8")
        cls.max_skills = MAX_SKILLS.read_text(encoding="utf-8")
        cls.npc = FOURTH_JOB_NPC.read_text(encoding="utf-8")
        cls.character = CHARACTER.read_text(encoding="utf-8")
        cls.shadower = SHADOWER.read_text(encoding="utf-8")

    def test_first_job_resource_and_job_ids_remain_unchanged(self):
        first_job = (ROOT / "clien/Data/Skill/400.img").read_bytes()
        self.assertEqual(FIRST_JOB_HASH, hashlib.sha256(first_job).hexdigest())
        for marker in (
            '{job_id: 420, name: "侠客"',
            '{job_id: 421, name: "独行客"',
            '{job_id: 422, name: "侠盗"',
        ):
            self.assertIn(marker, self.quick_job)

    def test_second_through_fourth_job_strings_remain_at_legacy_baseline(self):
        baseline = parse_img_bytes(
            migration.git_blob(
                migration.SHADOWER_LEGACY_BASELINE,
                "clien/Data/String/Skill.img",
            ),
            "baseline-Skill.img",
        )
        for skill_id in migration.SHADOWER_LOWER_JOB_STRING_IDS:
            self.assertEqual(
                property_signature(baseline.child(str(skill_id))),
                property_signature(self.skill_string.child(str(skill_id))),
                skill_id,
            )

    def test_fourth_job_skill_and_mastery_book_bindings_keep_legacy_ids(self):
        client_228 = parse_img(ROOT / "clien/Data/Item/Consume/0228.img")
        client_229 = parse_img(ROOT / "clien/Data/Item/Consume/0229.img")
        expected = {
            2280003: {4221000},
            2280006: {4121003, 4221003},
            2290080: {4121003, 4221003},
            2290081: {4121003, 4221003},
            2290082: {4121004, 4221004},
            2290083: {4121004, 4221004},
            2290090: {4221007},
            2290091: {4221007},
            2290092: {4221001},
            2290093: {4221001},
        }
        for item_id, skill_ids in expected.items():
            root = client_228 if item_id // 1000 == 2280 else client_229
            node = root.get(f"0{item_id}/info/skill")
            actual = {int(child.value) for child in node.children()}
            if item_id == 2280003:
                self.assertIn(4221000, actual, item_id)
            else:
                self.assertEqual(skill_ids, actual, item_id)

    def test_skill_book_text_remains_at_legacy_baseline(self):
        baseline = parse_img_bytes(
            migration.git_blob(
                migration.SHADOWER_LEGACY_BASELINE,
                "clien/Data/String/Consume.img",
            ),
            "baseline-Consume.img",
        )
        for item_id in migration.SHADOWER_SKILL_BOOK_STRING_IDS:
            self.assertEqual(
                property_signature(baseline.child(str(item_id))),
                property_signature(self.consume_string.child(str(item_id))),
                item_id,
            )

    def test_normal_fourth_job_npc_keeps_original_skill_book_grants(self):
        self.assertIn("cm.gainItem(2280003, 1)", self.npc)
        self.assertIn("cm.teachSkill(4221007, 0, 10, -1)", self.npc)
        self.assertIn("cm.teachSkill(4221004, 0, 10, -1)", self.npc)
        self.assertIn("cm.teachSkill(4221001, 0, 10, -1)", self.npc)
        self.assertNotIn("cm.gainItem(2280006, 1)", self.npc)

    def test_quick_fourth_job_restores_original_master_levels(self):
        block = re.search(r"421:\s*\[(.*?)\n\s*\],\n\s*430:", self.quick_job, re.S)
        self.assertIsNotNone(block)
        entries = {
            int(skill_id): int(master)
            for skill_id, master in re.findall(
                r"\{id:\s*(422\d+),\s*max_Level:\s*(\d+)\}", block.group(1)
            )
        }
        self.assertEqual(
            {
                4220002: 30, 4220005: 30, 4221000: 30, 4221001: 30,
                4221003: 30, 4221004: 30, 4221006: 30, 4221007: 30,
                4221008: 5,
            },
            entries,
        )

    def test_full_skill_script_keeps_first_job_and_maxes_replaced_slots(self):
        block = re.search(r"case 422:(.*?)break;", self.max_skills, re.S)
        self.assertIsNotNone(block)
        for skill_id in (4000000, 4000001, 4001002, 4001003, 4001334, 4001344):
            self.assertRegex(block.group(1), rf"teachSkill\({skill_id},")
        for skill_id in FOURTH_JOB_ATTACKS:
            self.assertIn(f"teachSkill({skill_id}, 30, 30, -1)", block.group(1))
        for skill_id in PUBLIC_V_VI:
            self.assertNotIn(str(skill_id), block.group(1))

    def test_java_mastery_uses_original_boomerang_step_slot(self):
        mastery = self.character[
            self.character.index("public void setMasteries"):
            self.character.index("private void broadcastChangeJob")
        ]
        self.assertIn("skills[2] = Shadower.BOOMERANG_STEP;", mastery)
        self.assertNotIn("SHORT_DAGGER_GUARD", self.shadower)
        for skill_id in PUBLIC_V_VI:
            self.assertNotIn(str(skill_id), mastery)


if __name__ == "__main__":
    unittest.main()
