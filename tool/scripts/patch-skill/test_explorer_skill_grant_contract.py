#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzKey  # noqa: E402

CONSTANTS = ROOT / "gms-server/src/main/java/org/gms/constants/skills"
CHARACTER = ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/冒险家五六转攻击技能.js"
SKILL_CENTER = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/技能中心.js"
FIFTH_JOB_GODDESS = ROOT / "gms-server/scripts-zh-CN/npc/9900008.js"
SERVER_CONSUME = ROOT / "gms-server/wz/Item.wz/Consume/0202.img.xml"
SERVER_CONSUME_STRING = ROOT / "gms-server/wz/String.wz/Consume.img.xml"

EXPLORER_CLASSES = {
    112: "Hero",
    122: "Paladin",
    132: "DarkKnight",
    212: "FPArchMage",
    222: "ILArchMage",
    232: "Bishop",
    312: "Bowmaster",
    322: "Marksman",
    412: "NightLord",
    422: "Shadower",
    512: "Buccaneer",
    522: "Corsair",
}
KNIGHT_CLASSES = ("DawnWarrior", "BlazeWizard", "WindArcher", "ThunderBreaker")
A_TO_Z_KEY_CODES = [
    30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50,
    49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44,
]


def active_ids(class_name: str) -> list[int]:
    text = (CONSTANTS / f"{class_name}.java").read_text(encoding="utf-8")
    block = re.search(r"V_VI_ACTIVE_ATTACKS\s*=\s*\{([^}]*)}", text, re.S)
    if block is None:
        raise AssertionError(f"missing active attack array: {class_name}")
    constants = {
        name: int(value)
        for name, value in re.findall(
            r"public static final int\s+([A-Z0-9_]+)\s*=\s*(\d+);", text
        )
    }
    values = []
    for token in re.findall(r"[A-Z][A-Z0-9_]*|\d+", block.group(1)):
        values.append(int(token) if token.isdigit() else constants[token])
    return values


class ExplorerSkillGrantContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        character = CHARACTER.read_text(encoding="utf-8")
        cls.character = character
        cls.masteries = character[character.index("public void setMasteries"):
                                   character.index("private void broadcastChangeJob")]

    def test_script_only_maps_supported_explorer_jobs(self):
        mapped = {
            int(job): class_name
            for job, class_name in re.findall(
                r'(\d+):\s*\{[^}]*?skills:\s*Java\.type\('
                r'"org\.gms\.constants\.skills\.([A-Za-z]+)"\)\.V_VI_ACTIVE_ATTACKS[^}]*}',
                self.script,
                re.S,
            )
        }
        self.assertEqual(EXPLORER_CLASSES, mapped)
        for class_name in KNIGHT_CLASSES:
            self.assertNotIn(class_name, self.script)

    def test_every_active_array_fits_a_to_z(self):
        for class_name in EXPLORER_CLASSES.values():
            skills = active_ids(class_name)
            self.assertTrue(skills, class_name)
            self.assertLessEqual(len(skills), len(A_TO_Z_KEY_CODES), class_name)

    def test_keyboard_codes_are_a_to_z_order(self):
        block = re.search(r"KEY_CODES\s*=\s*\[([^]]*)]", self.script, re.S)
        self.assertIsNotNone(block)
        actual = [int(value) for value in re.findall(r"\d+", block.group(1))]
        self.assertEqual(A_TO_Z_KEY_CODES, actual)
        self.assertIn('KEY_NAMES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"', self.script)

    def test_script_grants_full_level_and_sends_one_keymap(self):
        self.assertIn(
            "cm.teachSkill(skillId, SKILL_LEVEL, SKILL_LEVEL, -1, true)",
            self.script,
        )
        self.assertIn("player.removeBySkillId(skillId)", self.script)
        self.assertIn("player.changeKeybinding(KEY_CODES[index]", self.script)
        self.assertIn("player.removeSkillById(retiredSkills[skillIndex])", self.script)
        self.assertEqual(1, self.script.count("player.sendKeymap()"))

    def test_removed_skill_ids_can_be_deleted_after_wz_cleanup(self):
        self.assertIn("public void removeSkillById(int skillId)", self.character)
        self.assertIn("SkillsDO.builder().skillid(skillId)", self.character)

    def test_fp_retired_skills_and_bindings_are_removed_on_claim(self):
        block = re.search(r"212:\s*\{(.*?)\},\s*222:", self.script, re.S)
        self.assertIsNotNone(block)
        expected = [
            2121009, 2121010, 2121011, 2121013, 2121014, 2121015,
            2121016, 2121023, 2121024, 2121025, 2121026, 2121027,
            2121029, 2121030, 2121031, 2121037,
        ]
        for field in ("retiredBindings", "retiredSkills"):
            values = re.search(rf"{field}:\s*\[([^]]*)]", block.group(1))
            self.assertIsNotNone(values, field)
            self.assertEqual(expected, [int(value) for value in re.findall(r"\d+", values.group(1))])

    def test_bishop_retired_skills_and_bindings_are_removed_on_claim(self):
        block = re.search(r"232:\s*\{(.*?)\},\s*312:", self.script, re.S)
        self.assertIsNotNone(block)
        expected = [
            2321022, 2321023, 2321025, 2321026, 2321027, 2321028, 2321036,
        ]
        for field in ("retiredBindings", "retiredSkills"):
            values = re.search(rf"{field}:\s*\[([^]]*)]", block.group(1))
            self.assertIsNotNone(values, field)
            actual = [int(value) for value in re.findall(r"\d+", values.group(1))]
            self.assertEqual(expected, actual, field)

    def test_bowmaster_retired_skills_and_bindings_are_removed_on_claim(self):
        block = re.search(r"312:\s*\{(.*?)\},\s*322:", self.script, re.S)
        self.assertIsNotNone(block)
        expected = [
            3121011, 3121012, 3121013, 3121014, 3121015, 3121016,
            3121020, 3121021, 3121024,
        ]
        for field in ("retiredBindings", "retiredSkills"):
            values = re.search(rf"{field}:\s*\[([^]]*)]", block.group(1))
            self.assertIsNotNone(values, field)
            actual = [int(value) for value in re.findall(r"\d+", values.group(1))]
            self.assertEqual(expected, actual, field)

    def test_marksman_retired_skills_and_bindings_are_removed_on_claim(self):
        block = re.search(r"322:\s*\{(.*?)\},\s*412:", self.script, re.S)
        self.assertIsNotNone(block)
        expected = [3221011, 3221012, *range(3221014, 3221029)]
        for field in ("retiredBindings", "retiredSkills"):
            values = re.search(rf"{field}:\s*\[([^]]*)]", block.group(1))
            self.assertIsNotNone(values, field)
            actual = [int(value) for value in re.findall(r"\d+", values.group(1))]
            self.assertEqual(expected, actual, field)

    def test_corsair_retired_skills_and_bindings_are_removed_on_claim(self):
        block = re.search(r"522:\s*\{(.*?)\}\s*\n\};", self.script, re.S)
        self.assertIsNotNone(block)
        expected = [
            5221016, 5221017, 5221018, 5221019,
            5221020, 5221021, 5221028, 5221029,
        ]
        for field in ("retiredBindings", "retiredSkills"):
            values = re.search(rf"{field}:\s*\[([^]]*)]", block.group(1))
            self.assertIsNotNone(values, field)
            actual = [int(value) for value in re.findall(r"\d+", values.group(1))]
            self.assertEqual(expected, actual, field)

    def test_night_lord_retired_skills_and_bindings_are_removed_on_claim(self):
        block = re.search(r"412:\s*\{(.*?)\},\s*422:", self.script, re.S)
        self.assertIsNotNone(block)
        for field in ("retiredBindings", "retiredSkills"):
            values = re.search(rf"{field}:\s*\[([^]]*)]", block.group(1))
            self.assertIsNotNone(values, field)
            self.assertEqual(
                [4121010, 4121012, 4121013, 4121014, 4121015, 4121021],
                [int(value) for value in re.findall(r"\d+", values.group(1))],
                field,
            )
        self.assertNotIn(4121013, active_ids("NightLord"))
        self.assertNotIn(4121012, active_ids("NightLord"))

    def test_explorers_are_not_auto_granted_or_mastered(self):
        for class_name in EXPLORER_CLASSES.values():
            self.assertNotIn(f"{class_name}.V_VI_ACTIVE_ATTACKS", self.masteries)
        self.assertNotIn("Hero.MONSTER_MAGNET", self.masteries)
        self.assertNotIn("Hero.RAGING_BLOW_VI", self.masteries)

    def test_knight_auto_grant_branches_remain(self):
        for class_name in KNIGHT_CLASSES:
            self.assertIn(f"{class_name}.V_VI_ACTIVE_ATTACKS", self.masteries)
        self.assertIn("Job.THUNDERBREAKER3", self.masteries)
        self.assertIn("Job.THUNDERBREAKER4", self.masteries)

    def test_explorer_script_is_only_opened_by_fifth_job_item(self):
        center = SKILL_CENTER.read_text(encoding="utf-8")
        self.assertNotIn("冒险家五、六转攻击技能", center)
        self.assertNotIn('openNpc("冒险家五六转攻击技能")', center)
        consume = SERVER_CONSUME.read_text(encoding="utf-8")
        self.assertIn('<imgdir name="02029006">', consume)
        self.assertIn('<int name="npc" value="9900001"/>', consume)
        self.assertIn('<string name="script" value="冒险家五六转攻击技能"/>', consume)
        self.assertIn('<int name="remove" value="0"/>', consume)
        strings = SERVER_CONSUME_STRING.read_text(encoding="utf-8")
        self.assertIn('<imgdir name="2029006">', strings)
        self.assertIn('<string name="name" value="5转技能"/>', strings)

    def test_fifth_job_goddess_grants_item_to_supported_explorers(self):
        goddess = FIFTH_JOB_GODDESS.read_text(encoding="utf-8")
        self.assertNotIn("等全部做好再开放好了", goddess)
        jobs = re.search(r"EXPLORER_FOURTH_JOBS\s*=\s*\{([^}]*)}", goddess, re.S)
        self.assertIsNotNone(jobs)
        actual = {int(value) for value in re.findall(r"(\d+)\s*:\s*true", jobs.group(1))}
        self.assertEqual(set(EXPLORER_CLASSES), actual)
        self.assertIn("cm.getPlayer().getLevel() < ADVANCEMENT_LEVEL", goddess)
        self.assertIn("cm.haveItem(EXPLORER_FIFTH_JOB_ITEM_ID, 1)", goddess)
        self.assertIn("cm.canHold(EXPLORER_FIFTH_JOB_ITEM_ID, 1)", goddess)
        self.assertIn("cm.gainItem(EXPLORER_FIFTH_JOB_ITEM_ID, 1)", goddess)

    def test_public_v_vi_attacks_are_hidden_only_from_legacy_skill_window(self):
        for job_id, class_name in EXPLORER_CLASSES.items():
            expected = active_ids(class_name)
            client_path = ROOT / f"clien/Data/Skill/{job_id}.img"
            client = WzImage.from_bytes(
                client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
            )
            client.parse()
            self.assertFalse(client.truncated, job_id)
            self.assertFalse(client.parse_warnings, job_id)
            server = ET.parse(ROOT / f"gms-server/wz/Skill.wz/{job_id}.img.xml").getroot()
            skills = server.find("./imgdir[@name='skill']")
            for skill_id in expected:
                invisible = client.root.get(f"skill/{skill_id}/invisible")
                self.assertIsNotNone(invisible, skill_id)
                self.assertEqual(1, int(invisible.value), skill_id)
                server_invisible = skills.find(
                    f"./imgdir[@name='{skill_id}']/int[@name='invisible']"
                )
                self.assertIsNotNone(server_invisible, skill_id)
                self.assertEqual("1", server_invisible.get("value"), skill_id)


if __name__ == "__main__":
    unittest.main()
