#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_vanishing_journey_quests as migration  # noqa: E402
from migrate_arcane_river_fields import GMS_KEY  # noqa: E402
from migrate_karing_later_stages import locate_records  # noqa: E402
from wzpy import WzCanvasProperty, WzImage  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


CLIENT_QUEST_IDS = tuple(range(34100, 34121))
SERVER_QUEST_IDS = tuple(range(-31436, -31415))
WORKING_POSITIVE_IDS = {"34102", "34103", "34104", "34105"}
ITEM_IDS = (4034914, 4034915, 4034916, 4034917, 4034918, 4034919, 4034920, 4034921, 4034937, 4034938)


def load_client(path: Path, data: bytes | None = None) -> tuple[WzImage, bytes]:
    payload = path.read_bytes() if data is None else data
    image = WzImage.from_bytes(payload, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"malformed IMG {path}: {image.parse_warnings}")
    return image, payload


def raw_records(path: Path, data: bytes, parent: tuple[str, ...] = ()):
    image, _ = load_client(path, data)
    _, _, _, names, spans, _ = locate_records(image, data, parent)
    return names, {name: data[start:end] for name, (start, end) in zip(names, spans)}


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def direct_children(path: Path, parent_name: str) -> dict[str, ET.Element]:
    root = ET.parse(path).getroot()
    parent = root if root.get("name") == parent_name else root.find(f"./imgdir[@name='{parent_name}']")
    if parent is None:
        raise AssertionError(f"missing parent {parent_name} in {path}")
    return {child.get("name", ""): child for child in parent if child.tag == "imgdir"}


def child_value(node: ET.Element, name: str) -> int | str | None:
    child = node.find(f"./*[@name='{name}']")
    if child is None:
        return None
    raw = child.get("value")
    if child.tag in {"int", "short", "long"} and raw is not None:
        return int(raw)
    return raw


class VanishingJourneyQuestContract(unittest.TestCase):
    def test_signed_id_projection_is_bit_identical(self):
        self.assertEqual(SERVER_QUEST_IDS, tuple(q - 65536 for q in CLIENT_QUEST_IDS))
        for source_id, legacy_id in zip(CLIENT_QUEST_IDS, SERVER_QUEST_IDS):
            self.assertEqual(source_id & 0xFFFF, legacy_id & 0xFFFF)

    def test_client_quest_records_and_raw_preservation(self):
        for image_name in migration.QUEST_IMAGE_NAMES:
            path = ROOT / f"clien/Data/Quest/{image_name}.img"
            baseline = git_baseline(path)
            current = path.read_bytes()
            old_names, old_raw = raw_records(path, baseline)
            new_names, new_raw = raw_records(path, current)
            expected_names = tuple(
                name for name in old_names if name not in WORKING_POSITIVE_IDS
            ) + tuple(str(q) for q in CLIENT_QUEST_IDS)
            self.assertEqual(expected_names, new_names, image_name)
            for name, record in old_raw.items():
                self.assertEqual(record, new_raw[name], f"{image_name}/{name}")
            for quest_id in CLIENT_QUEST_IDS:
                self.assertIn(str(quest_id), new_raw, f"{image_name}/{quest_id}")
            for quest_id in SERVER_QUEST_IDS:
                self.assertNotIn(str(quest_id), new_raw, f"{image_name}/{quest_id}")

    def test_client_quest_semantics(self):
        for image_name in migration.QUEST_IMAGE_NAMES:
            path = ROOT / f"clien/Data/Quest/{image_name}.img"
            image, _ = load_client(path)
            for quest_id in CLIENT_QUEST_IDS:
                self.assertIsNotNone(image.get(str(quest_id)), f"{image_name}/{quest_id}")

        check, _ = load_client(ROOT / "clien/Data/Quest/Check.img")
        for index, quest_id in enumerate(CLIENT_QUEST_IDS):
            self.assertEqual(200, check.get(f"{quest_id}/0/lvmin").value)
            if index and str(quest_id) not in WORKING_POSITIVE_IDS:
                self.assertEqual(CLIENT_QUEST_IDS[index - 1], check.get(f"{quest_id}/0/quest/0/id").value)
                self.assertEqual(2, check.get(f"{quest_id}/0/quest/0/state").value)
        self.assertEqual(8641012, check.get("34119/1/mob/0/id").value)
        self.assertEqual(30, check.get("34119/1/mob/0/count").value)

    def test_server_quest_trees_match_chain(self):
        for tree in ("wz", "wz-zh-CN"):
            roots = {
                name: direct_children(
                    ROOT / f"gms-server/{tree}/Quest.wz/{name}.img.xml",
                    f"{name}.img",
                )
                for name in migration.QUEST_IMAGE_NAMES
            }
            for quest_id in SERVER_QUEST_IDS:
                for image_name, nodes in roots.items():
                    self.assertIn(str(quest_id), nodes, f"{tree}/{image_name}/{quest_id}")
            for obsolete in WORKING_POSITIVE_IDS:
                for image_name, nodes in roots.items():
                    self.assertNotIn(obsolete, nodes, f"{tree}/{image_name}/{obsolete}")

            checks = roots["Check"]
            for index, quest_id in enumerate(SERVER_QUEST_IDS):
                start = checks[str(quest_id)].find("./imgdir[@name='0']")
                finish = checks[str(quest_id)].find("./imgdir[@name='1']")
                self.assertIsNotNone(start)
                self.assertIsNotNone(finish)
                self.assertIsInstance(child_value(start, "npc"), int)
                self.assertIsInstance(child_value(finish, "npc"), int)
                if index:
                    prerequisite = start.find("./imgdir[@name='quest']/imgdir[@name='0']")
                    self.assertEqual(SERVER_QUEST_IDS[index - 1], child_value(prerequisite, "id"))

    def test_npc_and_mob_closure(self):
        npcs, mobs = migration.installed_life_ids()
        records = []
        for order, source_id in enumerate(migration.SOURCE_QUEST_IDS, 1):
            _, record = migration.build_quest_nodes(source_id, order)
            records.append(record)
        self.assertFalse({r.start_npc for r in records} - npcs)
        self.assertFalse({r.end_npc for r in records} - npcs)
        self.assertFalse({mob for r in records for mob, _ in r.mobs} - mobs)

    def test_item_records_strings_and_canvas_payloads(self):
        item_path = ROOT / "clien/Data/Item/Etc/0403.img"
        item_image, item_data = load_client(item_path)
        old_names, old_raw = raw_records(item_path, git_baseline(item_path))
        new_names, new_raw = raw_records(item_path, item_data)
        self.assertEqual(tuple(name for name in old_names if name not in new_names), ())
        allowed = {f"0{item_id}" for item_id in ITEM_IDS}
        for name, record in old_raw.items():
            if name not in allowed:
                self.assertEqual(record, new_raw[name], f"Item/0403/{name}")
        for item_id in ITEM_IDS:
            node_name = f"0{item_id}"
            self.assertIn(node_name, new_raw)
            for canvas_name in ("icon", "iconRaw"):
                canvas = item_image.get(f"{node_name}/info/{canvas_name}")
                self.assertIsInstance(canvas, WzCanvasProperty)
                self.assertEqual((1, 0), (canvas.format, canvas.format2))
                decoded = decode_canvas(canvas, region="GMS")
                self.assertGreater(decoded.width * decoded.height, 1)

        string_path = ROOT / "clien/Data/String/Etc.img"
        string_image, _ = load_client(string_path)
        for item_id in ITEM_IDS:
            self.assertIsNotNone(string_image.get(f"Etc/{item_id}/name"))
            self.assertIsNotNone(
                ET.parse(ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml").getroot().find(
                    f"./imgdir[@name='0{item_id}']"
                )
            )
            for tree in ("wz", "wz-zh-CN"):
                strings = direct_children(ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml", "Etc")
                self.assertIn(str(item_id), strings)

    def test_signed_runtime_and_drop_contract(self):
        handler = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/QuestActionHandler.java").read_text()
        character = (ROOT / "gms-server/src/main/java/org/gms/client/Character.java").read_text()
        loot_manager = (ROOT / "gms-server/src/main/java/org/gms/server/loot/LootManager.java").read_text()
        self.assertIn("int questid = p.readShort();", handler)
        self.assertNotIn("Short.toUnsignedInt(p.readShort())", handler)
        self.assertIn("if (questid == 0)", character)
        self.assertIn("if (dropEntry.questid == 0)", loot_manager)
        self.assertIn("if (dropEntry.questid != 0)", loot_manager)

        migration_sql = (
            ROOT
            / "gms-server/src/main/resources/db/migration/V2.1.61__complete_vanishing_journey_quest_drops.sql"
        ).read_text()
        expected = {
            (8641000, 4034914, -31434),
            (8641001, 4034915, -31433),
            (8641002, 4034916, -31432),
            (8641003, 4034917, -31431),
            (8641004, 4034918, -31425),
            (8641005, 4034919, -31424),
            (8641006, 4034920, -31423),
            (8641007, 4034921, -31420),
            (8641007, 4034937, -31419),
            (8641007, 4034938, -31418),
        }
        for mob_id, item_id, quest_id in expected:
            self.assertIn(f"({mob_id}, {item_id}, 1, 1, {quest_id}, 500000)", migration_sql)

    def test_generator_uses_only_incremental_img_records(self):
        source = (ROOT / "tool/scripts/migration/migrate_vanishing_journey_quests.py").read_text()
        self.assertNotIn("encode_image_body", source)
        self.assertNotIn("save_as(", source)
        self.assertIn("patch_raw_records", source)


if __name__ == "__main__":
    unittest.main()
