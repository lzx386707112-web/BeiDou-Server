#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import add_npc_3003104_daily_items as migration  # noqa: E402
import add_npc_3003104_reverse_city_quests as reverse_migration  # noqa: E402
import add_reverse_city_story_quests as story_migration  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402
import repair_reverse_city_client_record_order as repair  # noqa: E402
from wzpy import WzCanvasProperty, WzImage  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


COLLECTION_QUESTS = {
    -31397: (4034922, 50),
    -31396: (4034923, 50),
    -31395: (4034924, 50),
    -31394: (4034925, 50),
    -31393: (4034926, 50),
    -31392: (4034927, 50),
    -31391: (4034928, 50),
    -31390: (4034929, 50),
    -31389: (4034930, 33),
    -31388: (4034934, 30),
    -31387: (4034935, 30),
    -31386: (4034936, 30),
    -26473: (4036709, 50),
}
KILL_QUESTS = {
    -31406: (8641000, 200),
    -31405: (8641001, 200),
    -31404: (8641002, 200),
    -31403: (9101085, 200),
    -31402: (8641004, 200),
    -31401: (8641005, 200),
    -31400: (9101086, 200),
    -31399: (8641007, 200),
    -31398: (8641008, 130),
    -26481: (8641051, 200),
    -26480: (8641052, 200),
    -26479: (8641053, 200),
    -26478: (8641054, 200),
    -26477: (8641055, 200),
    -26476: (8641056, 200),
    -26475: (8641057, 200),
    -26474: (8641058, 200),
}
ALL_QUESTS = set(range(-31408, -31385)) | set(range(-26481, -26472))
DROP_ROWS = {
    (8641000, 4034922, -31397),
    (8641001, 4034923, -31396),
    (8641002, 4034924, -31395),
    (8641003, 4034925, -31394),
    (8641004, 4034926, -31393),
    (8641005, 4034927, -31392),
    (8641006, 4034928, -31391),
    (8641007, 4034929, -31390),
    *((mob_id, 4034934, -31388) for mob_id in range(8641000, 8641004)),
    *((mob_id, 4034935, -31387) for mob_id in range(8641004, 8641007)),
    (8641007, 4034936, -31386),
    *((mob_id, 4036709, -26473) for mob_id in range(8641051, 8641059)),
}


def load_client(path: Path) -> tuple[WzImage, bytes]:
    data = path.read_bytes()
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"malformed IMG {path}: {image.parse_warnings}")
    return image, data


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    ref = "HEAD^" if path in reverse_migration.CLIENT_QUESTS.values() else "HEAD"
    return subprocess.run(
        ["git", "cat-file", "blob", f"{ref}:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def direct_imgdirs(path: Path, parent_name: str | None = None) -> dict[str, ET.Element]:
    parent = ET.parse(path).getroot()
    if parent_name is not None:
        parent = parent.find(f"./imgdir[@name='{parent_name}']")
        if parent is None:
            raise AssertionError(f"missing XML parent {parent_name} in {path}")
    return {child.get("name", ""): child for child in parent if child.tag == "imgdir"}


class Npc3003104DailyContract(unittest.TestCase):
    def test_client_item_and_string_records_are_incremental(self):
        cases = (
            (
                migration.CLIENT_ITEM,
                (),
                {f"0{item_id}" for item_id in migration.ITEM_IDS + story_migration.ITEM_IDS},
            ),
            (
                migration.CLIENT_STRING,
                ("Etc",),
                {str(item_id) for item_id in migration.ITEM_IDS + story_migration.ITEM_IDS},
            ),
        )
        for path, parent, allowed in cases:
            baseline = git_baseline(path)
            current = path.read_bytes()
            before_records, before_order = arc.raw_record_state(baseline)
            after_records, after_order = arc.raw_record_state(current)
            approved_paths = {(*parent, name) for name in allowed}
            self.assertEqual(
                before_order[parent],
                tuple(name for name in after_order[parent] if name not in allowed),
            )
            self.assertEqual(allowed - set(before_order[parent]), set(after_order[parent]) - set(before_order[parent]))
            for record_path, raw in before_records.items():
                is_parent_of_addition = any(
                    approved[: len(record_path)] == record_path for approved in approved_paths
                )
                if not is_parent_of_addition:
                    self.assertEqual(raw, after_records[record_path], "/".join(record_path))

    def test_all_item_resources_and_visible_argb4444_canvases_exist(self):
        item_image, _ = load_client(migration.CLIENT_ITEM)
        string_image, _ = load_client(migration.CLIENT_STRING)
        server_items = direct_imgdirs(migration.SERVER_ITEM)
        server_strings = [direct_imgdirs(path, "Etc") for path in migration.SERVER_STRINGS]
        for item_id in migration.ITEM_IDS:
            item_name = f"0{item_id}"
            self.assertIn(item_name, server_items)
            self.assertIsNotNone(string_image.root.get(f"Etc/{item_id}/name"))
            for strings in server_strings:
                self.assertIn(str(item_id), strings)
            for canvas_name in ("icon", "iconRaw"):
                canvas = item_image.root.get(f"{item_name}/info/{canvas_name}")
                self.assertIsInstance(canvas, WzCanvasProperty)
                self.assertEqual((1, 0), (canvas.format, canvas.format2))
                bitmap = decode_canvas(canvas, region="GMS")
                self.assertGreater(bitmap.width * bitmap.height, 1)
                self.assertIsNotNone(bitmap.getbbox())

    def test_collection_checks_and_removals_match_tms(self):
        checks = direct_imgdirs(ROOT / "gms-server/wz/Quest.wz/Check.img.xml")
        acts = direct_imgdirs(ROOT / "gms-server/wz/Quest.wz/Act.img.xml")
        for quest_id, (item_id, count) in COLLECTION_QUESTS.items():
            check_item = checks[str(quest_id)].find("./imgdir[@name='1']/imgdir[@name='item']/imgdir[@name='0']")
            act_item = acts[str(quest_id)].find("./imgdir[@name='1']/imgdir[@name='item']/imgdir[@name='1']")
            self.assertIsNotNone(check_item, quest_id)
            self.assertIsNotNone(act_item, quest_id)
            self.assertEqual(str(item_id), check_item.find("./int[@name='id']").get("value"))
            self.assertEqual(str(count), check_item.find("./int[@name='count']").get("value"))
            self.assertEqual(str(item_id), act_item.find("./int[@name='id']").get("value"))
            self.assertEqual(str(-count), act_item.find("./int[@name='count']").get("value"))

    def test_every_quest_record_reward_script_and_kill_target_exist(self):
        quest_files = {
            name: direct_imgdirs(ROOT / f"gms-server/wz/Quest.wz/{name}.img.xml")
            for name in ("Act", "Check", "QuestInfo", "Say")
        }
        for quest_id in ALL_QUESTS:
            for name, records in quest_files.items():
                self.assertIn(str(quest_id), records, f"{name}/{quest_id}")
            self.assertTrue(
                ROOT.joinpath(f"gms-server/scripts-zh-CN/quest/{quest_id}.js").is_file(),
                quest_id,
            )
            if quest_id != -31408:
                reward = quest_files["Act"][str(quest_id)].find(
                    "./imgdir[@name='1']/imgdir[@name='item']/imgdir[@name='0']"
                )
                self.assertIsNotNone(reward, quest_id)
                self.assertEqual("1712001", reward.find("./int[@name='id']").get("value"))
                self.assertEqual("2", reward.find("./int[@name='count']").get("value"))

        checks = quest_files["Check"]
        for quest_id, (mob_id, count) in KILL_QUESTS.items():
            mob = checks[str(quest_id)].find(
                "./imgdir[@name='1']/imgdir[@name='mob']/imgdir[@name='0']"
            )
            self.assertIsNotNone(mob, quest_id)
            self.assertEqual(str(mob_id), mob.find("./int[@name='id']").get("value"))
            self.assertEqual(str(count), mob.find("./int[@name='count']").get("value"))

    def test_reverse_city_client_quest_records_are_incremental_and_complete(self):
        additions = {
            str(quest_id)
            for quest_id in reverse_migration.TMS_QUEST_IDS
            + story_migration.TMS_QUEST_IDS
        }
        replacements = set(map(str, repair.WORKBENCH_CLIENT_QUEST_IDS))
        images = {}
        for name, path in reverse_migration.CLIENT_QUESTS.items():
            baseline = git_baseline(path)
            current = path.read_bytes()
            before_records, before_order = arc.raw_record_state(baseline)
            after_records, after_order = arc.raw_record_state(current)
            self.assertEqual(
                before_order[()],
                tuple(name for name in after_order[()] if name not in additions),
            )
            self.assertEqual(
                additions - set(before_order[()]),
                set(after_order[()]) - set(before_order[()]),
            )
            for record_path, raw in before_records.items():
                if record_path[0] not in replacements:
                    self.assertEqual(
                        raw, after_records[record_path], "/".join(record_path)
                    )
            images[name], _ = load_client(path)

        descriptions = reverse_migration.tms_descriptions()
        server_infos = direct_imgdirs(reverse_migration.SERVER_QUESTS["QuestInfo"])
        for quest_id, signed_id in zip(
            reverse_migration.TMS_QUEST_IDS,
            reverse_migration.SIGNED_QUEST_IDS,
        ):
            quest_name = str(quest_id)
            for image in images.values():
                self.assertIsNotNone(image.root.child(quest_name), quest_id)

            if quest_id != 34128:
                reward = images["Act"].root.get(f"{quest_name}/1/item/0")
                self.assertEqual(1712001, reward.child("id").value)
                self.assertEqual(2, reward.child("count").value)
            info = images["QuestInfo"].root.child(quest_name)
            self.assertEqual(272, info.child("area").value)
            for expected in descriptions[str(signed_id)]:
                self.assertEqual(expected.value, info.child(expected.name).value)
                server_field = server_infos[str(signed_id)].find(
                    f"./string[@name='{expected.name}']"
                )
                self.assertIsNotNone(server_field, f"{signed_id}/{expected.name}")
                self.assertEqual(expected.value, server_field.get("value"))

        for quest_id, (mob_id, count) in KILL_QUESTS.items():
            if quest_id > -26473 or quest_id < -26481:
                continue
            client_id = quest_id + 65536
            mob = images["Check"].root.get(f"{client_id}/1/mob/0")
            self.assertEqual(mob_id, mob.child("id").value)
            self.assertEqual(count, mob.child("count").value)
        item = images["Check"].root.get("39063/1/item/0")
        self.assertEqual(4036709, item.child("id").value)
        self.assertEqual(50, item.child("count").value)

    def test_reverse_city_monsters_have_resources_and_map_spawns(self):
        map_root = ROOT / "gms-server/wz/Map.wz/Map/Map4"
        map_text = "".join(path.read_text(encoding="utf-8") for path in map_root.glob("450014*.img.xml"))
        strings = [
            direct_imgdirs(ROOT / f"gms-server/{tree}/String.wz/Mob.img.xml")
            for tree in ("wz", "wz-zh-CN")
        ]
        for mob_id in range(8641051, 8641059):
            mob_name = f"{mob_id:07d}"
            self.assertTrue(ROOT.joinpath(f"clien/Data/Mob/{mob_name}.img").is_file())
            self.assertTrue(ROOT.joinpath(f"gms-server/wz/Mob.wz/{mob_name}.img.xml").is_file())
            for records in strings:
                self.assertIn(str(mob_id), records)
            self.assertIn(f'name="id" value="{mob_id}"', map_text)

    def test_drop_rows_are_complete_and_quest_limited(self):
        sql = (
            ROOT
            / "gms-server/src/main/resources/db/migration/V2.1.63__add_npc_3003104_daily_quest_drops.sql"
        ).read_text(encoding="utf-8")
        self.assertEqual(24, len(DROP_ROWS))
        for mob_id, item_id, quest_id in DROP_ROWS:
            self.assertIn(f"({mob_id}, {item_id}, 1, 1, {quest_id}, 500000)", sql)
        self.assertNotIn("4034930, 1, 1", sql)

    def test_virtual_tms_kill_ids_are_counted(self):
        mob_ids = (ROOT / "gms-server/src/main/java/org/gms/constants/id/MobId.java").read_text()
        character = (ROOT / "gms-server/src/main/java/org/gms/client/Character.java").read_text()
        for name, actual, virtual in (
            ("JOYFUL_ERDA", 8641003, 9101085),
            ("RAGING_ERDA", 8641006, 9101086),
        ):
            self.assertIn(f"{name} = {actual}", mob_ids)
            self.assertIn(f"{name}_QUEST = {virtual}", mob_ids)
            self.assertIn(f"id == MobId.{name}", character)
            self.assertIn(f"raiseQuestMobCount(MobId.{name}_QUEST)", character)

    def test_unspawned_lantern_tasks_are_not_offered(self):
        npc = migration.ROOT.joinpath("gms-server/scripts-zh-CN/npc/3003104.js").read_text()
        offered = {
            int(quest_id)
            for quest_id in re.findall(r"(?:\d+:\s*\[|promptDailyQuest\()(-\d+)", npc)
        }
        expected = (set(KILL_QUESTS) | set(COLLECTION_QUESTS)) - {-31398, -31389}
        self.assertEqual(expected, offered)
        self.assertNotIn("擊退130隻艾爾達斯的燈火", npc)
        self.assertNotIn("#L18#", npc)
        self.assertNotIn("8: [-31398", npc)
        self.assertNotIn("18: [-31389", npc)

    def test_generator_forbids_full_img_serialization(self):
        for module in (migration, reverse_migration, story_migration):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn("encode_image_body", source)
            self.assertNotIn("save_as(", source)
            self.assertIn("insert_property_record_before", source)
            self.assertIn("verify_raw_record_insert_scope", source)


if __name__ == "__main__":
    unittest.main()
