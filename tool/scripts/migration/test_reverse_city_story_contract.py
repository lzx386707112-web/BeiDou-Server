#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import add_npc_3003104_daily_items as daily_items  # noqa: E402
import add_npc_3003104_reverse_city_quests as daily_quests  # noqa: E402
import add_reverse_city_story_quests as migration  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402
import repair_reverse_city_client_record_order as repair  # noqa: E402
from wzpy import WzCanvasProperty, WzImage  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


START_NPCS = (
    3003111,
    3004603,
    3004603,
    3004609,
    3004609,
    3004610,
    3004611,
    3004612,
    3004612,
    3004613,
    3004601,
    3004615,
    3004615,
    3004616,
    3004617,
    3004617,
    3004618,
    3004619,
    3004620,
    3004602,
)
END_NPCS = (
    3004603,
    3004603,
    3004609,
    3004609,
    3004610,
    3004610,
    3004612,
    3004612,
    3004613,
    3004613,
    3004614,
    3004615,
    3004616,
    3004616,
    3004617,
    3004618,
    3004618,
    3004651,
    3004651,
    3004602,
)


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    ref = "HEAD^" if path in migration.CLIENT_QUESTS.values() else "HEAD"
    return subprocess.run(
        ["git", "cat-file", "blob", f"{ref}:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def assert_xml_additions_only(
    testcase: unittest.TestCase,
    path: Path,
    parent_path: tuple[str, ...],
    allowed: set[str],
) -> None:
    before = ET.fromstring(git_baseline(path))
    after = ET.parse(path).getroot()
    for part in parent_path:
        before = before.find(f"./imgdir[@name='{part}']")
        after = after.find(f"./imgdir[@name='{part}']")
        if before is None or after is None:
            raise AssertionError(f"missing XML parent {'/'.join(parent_path)} in {path}")
    before_nodes = {child.get("name", ""): child for child in before}
    after_nodes = {child.get("name", ""): child for child in after}
    testcase.assertEqual(allowed - set(before_nodes), set(after_nodes) - set(before_nodes))
    for name, node in before_nodes.items():
        before_tail = node.tail
        after_tail = after_nodes[name].tail
        node.tail = None
        after_nodes[name].tail = None
        testcase.assertEqual(
            ET.tostring(node, encoding="unicode"),
            ET.tostring(after_nodes[name], encoding="unicode"),
            f"{path}/{name}",
        )
        node.tail = before_tail
        after_nodes[name].tail = after_tail


def load_client(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"malformed IMG {path}: {image.parse_warnings}")
    return image


def direct_imgdirs(path: Path, parent_name: str | None = None) -> dict[str, ET.Element]:
    parent = ET.parse(path).getroot()
    if parent_name is not None:
        parent = parent.find(f"./imgdir[@name='{parent_name}']")
        if parent is None:
            raise AssertionError(f"missing XML parent {parent_name} in {path}")
    return {child.get("name", ""): child for child in parent if child.tag == "imgdir"}


def int_value(parent: ET.Element, name: str) -> int:
    field = parent.find(f"./int[@name='{name}']")
    if field is None:
        raise AssertionError(f"missing int {name}")
    return int(field.get("value", "0"))


class ReverseCityStoryContract(unittest.TestCase):
    def test_client_quest_records_are_incremental(self):
        additions = {
            str(quest_id)
            for quest_id in daily_quests.TMS_QUEST_IDS + migration.TMS_QUEST_IDS
        }
        replacements = set(map(str, repair.WORKBENCH_CLIENT_QUEST_IDS))
        for path in migration.CLIENT_QUESTS.values():
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
            order = after_order[()]
            story_names = tuple(map(str, migration.TMS_QUEST_IDS))
            vanishing_names = tuple(map(str, daily_quests.VANISHING_QUEST_IDS))
            daily_names = tuple(map(str, daily_quests.REVERSE_CITY_QUEST_IDS))
            story_anchor = order.index("37701")
            vanishing_anchor = order.index("34200")
            daily_anchor = order.index("39064")
            self.assertEqual(
                story_names,
                order[story_anchor - len(story_names):story_anchor],
            )
            self.assertEqual(
                vanishing_names,
                order[vanishing_anchor - len(vanishing_names):vanishing_anchor],
            )
            self.assertEqual(
                daily_names,
                order[daily_anchor - len(daily_names):daily_anchor],
            )
            load_client(path)

    def test_all_twenty_quests_form_the_projected_npc_chain(self):
        checks = direct_imgdirs(migration.SERVER_QUESTS["Check"])
        acts = direct_imgdirs(migration.SERVER_QUESTS["Act"])
        infos = direct_imgdirs(migration.SERVER_QUESTS["QuestInfo"])
        says = direct_imgdirs(migration.SERVER_QUESTS["Say"])
        for offset, quest_id in enumerate(migration.TMS_QUEST_IDS):
            signed_id = migration.signed_quest_id(quest_id)
            name = str(signed_id)
            self.assertIn(name, checks)
            self.assertIn(name, acts)
            self.assertIn(name, infos)
            self.assertIn(name, says)
            self.assertTrue((migration.QUEST_SCRIPT_ROOT / f"{name}.js").is_file())

            start = checks[name].find("./imgdir[@name='0']")
            end = checks[name].find("./imgdir[@name='1']")
            self.assertIsNotNone(start)
            self.assertIsNotNone(end)
            self.assertEqual(205, int_value(start, "lvmin"))
            self.assertEqual(START_NPCS[offset], int_value(start, "npc"))
            self.assertEqual(END_NPCS[offset], int_value(end, "npc"))
            self.assertEqual(
                f"q{quest_id}s",
                start.find("./string[@name='startscript']").get("value"),
            )
            self.assertEqual(
                f"q{quest_id}e",
                end.find("./string[@name='endscript']").get("value"),
            )
            self.assertIsNone(end.find("./int[@name='infoNumber']"))
            self.assertIsNone(end.find("./imgdir[@name='infoex']"))

            prereqs = start.findall("./imgdir[@name='quest']/imgdir")
            if quest_id == 37601:
                self.assertEqual(
                    [(1465, 2), (-31416, 2)],
                    [(int_value(entry, "id"), int_value(entry, "state")) for entry in prereqs],
                )
            else:
                self.assertEqual(1, len(prereqs))
                self.assertEqual(signed_id - 1, int_value(prereqs[0], "id"))
                self.assertEqual(2, int_value(prereqs[0], "state"))

            self.assertEqual(273, int_value(infos[name], "area"))
            title = infos[name].find("./string[@name='name']")
            self.assertIsNotNone(title)
            self.assertIn("反轉城市", title.get("value", ""))

    def test_server_xml_changes_are_limited_to_approved_records(self):
        quest_ids = {
            str(quest_id)
            for quest_id in daily_quests.SIGNED_QUEST_IDS + migration.SIGNED_QUEST_IDS
        } | {str(quest_id) for quest_id in range(-31408, -31385)}
        for path in migration.SERVER_QUESTS.values():
            assert_xml_additions_only(self, path, (), quest_ids)

        item_ids = daily_items.ITEM_IDS + migration.ITEM_IDS
        assert_xml_additions_only(
            self,
            migration.SERVER_ITEM,
            (),
            {f"0{item_id}" for item_id in item_ids},
        )
        for path in migration.SERVER_ETC_STRINGS:
            assert_xml_additions_only(
                self, path, ("Etc",), {str(item_id) for item_id in item_ids}
            )
        for path in migration.SERVER_NPC_STRINGS:
            assert_xml_additions_only(self, path, (), {str(migration.NPC_ID)})
        for path in migration.SERVER_MOB_STRINGS:
            assert_xml_additions_only(self, path, (), {str(migration.MOB_ID)})

        before_map = ET.fromstring(git_baseline(migration.SERVER_MAP))
        after_map = ET.parse(migration.SERVER_MAP).getroot()
        for before_child in before_map:
            after_child = after_map.find(
                f"./{before_child.tag}[@name='{before_child.get('name')}']"
            )
            self.assertIsNotNone(after_child)
            if before_child.get("name") != "life":
                self.assertEqual(
                    ET.tostring(before_child, encoding="unicode"),
                    ET.tostring(after_child, encoding="unicode"),
                )
        assert_xml_additions_only(self, migration.SERVER_MAP, ("life",), {"1", "2"})

    def test_collection_and_kill_objectives_match_tms(self):
        checks = direct_imgdirs(migration.SERVER_QUESTS["Check"])
        acts = direct_imgdirs(migration.SERVER_QUESTS["Act"])
        for quest_id, (item_id, count, _) in migration.COLLECTION_QUESTS.items():
            name = str(migration.signed_quest_id(quest_id))
            check_item = checks[name].find(
                "./imgdir[@name='1']/imgdir[@name='item']/imgdir[@name='0']"
            )
            act_item = acts[name].find(
                "./imgdir[@name='1']/imgdir[@name='item']/imgdir[@name='0']"
            )
            self.assertIsNotNone(check_item)
            self.assertIsNotNone(act_item)
            self.assertEqual((item_id, count), (int_value(check_item, "id"), int_value(check_item, "count")))
            self.assertEqual((item_id, -count), (int_value(act_item, "id"), int_value(act_item, "count")))
            script = (migration.QUEST_SCRIPT_ROOT / f"{name}.js").read_text(encoding="utf-8")
            self.assertIn(f"qm.haveItem({item_id}, {count})", script)
            self.assertIn(f"qm.gainItem({item_id}, -{count})", script)

        for quest_id, (mob_id, count) in migration.KILL_QUESTS.items():
            name = str(migration.signed_quest_id(quest_id))
            mob = checks[name].find(
                "./imgdir[@name='1']/imgdir[@name='mob']/imgdir[@name='0']"
            )
            self.assertIsNotNone(mob)
            self.assertEqual((mob_id, count), (int_value(mob, "id"), int_value(mob, "count")))
        final = checks[str(migration.signed_quest_id(37619))]
        final_mob = final.find(
            "./imgdir[@name='1']/imgdir[@name='mob']/imgdir[@name='0']"
        )
        self.assertIsNotNone(final_mob)
        self.assertEqual(
            (migration.MOB_ID, 1),
            (int_value(final_mob, "id"), int_value(final_mob, "count")),
        )
        final_info = direct_imgdirs(migration.SERVER_QUESTS["QuestInfo"])[
            str(migration.signed_quest_id(37619))
        ]
        self.assertIn("8641059", ET.tostring(final_info, encoding="unicode"))

    def test_story_items_and_strings_are_incremental_and_visible(self):
        cases = (
            (
                migration.CLIENT_ITEM,
                (),
                {f"0{item_id}" for item_id in daily_items.ITEM_IDS + migration.ITEM_IDS},
            ),
            (
                migration.CLIENT_ETC_STRING,
                ("Etc",),
                {str(item_id) for item_id in daily_items.ITEM_IDS + migration.ITEM_IDS},
            ),
        )
        for path, parent, allowed in cases:
            before_records, before_order = arc.raw_record_state(git_baseline(path))
            after_records, after_order = arc.raw_record_state(path.read_bytes())
            self.assertEqual(
                before_order[parent],
                tuple(name for name in after_order[parent] if name not in allowed),
            )
            self.assertEqual(allowed - set(before_order[parent]), set(after_order[parent]) - set(before_order[parent]))
            for record_path, raw in before_records.items():
                is_parent = any(
                    (*parent, name)[: len(record_path)] == record_path for name in allowed
                )
                if not is_parent:
                    self.assertEqual(raw, after_records[record_path], "/".join(record_path))

        items = load_client(migration.CLIENT_ITEM)
        strings = load_client(migration.CLIENT_ETC_STRING)
        server_items = direct_imgdirs(migration.SERVER_ITEM)
        server_strings = [direct_imgdirs(path, "Etc") for path in migration.SERVER_ETC_STRINGS]
        for item_id in migration.ITEM_IDS:
            item_name = f"0{item_id}"
            self.assertIn(item_name, server_items)
            self.assertIsNotNone(strings.root.get(f"Etc/{item_id}/name"))
            for records in server_strings:
                self.assertIn(str(item_id), records)
            for canvas_name in ("icon", "iconRaw"):
                canvas = items.root.get(f"{item_name}/info/{canvas_name}")
                self.assertIsInstance(canvas, WzCanvasProperty)
                self.assertEqual((1, 0), (canvas.format, canvas.format2))
                bitmap = decode_canvas(canvas, region="GMS")
                self.assertGreater(bitmap.width * bitmap.height, 1)
                self.assertIsNotNone(bitmap.getbbox())

    def test_missing_npc_mob_strings_and_tower_spawns_exist(self):
        for path, allowed in (
            (migration.CLIENT_NPC_STRING, {str(migration.NPC_ID)}),
            (migration.CLIENT_MOB_STRING, {str(migration.MOB_ID)}),
        ):
            before_records, before_order = arc.raw_record_state(git_baseline(path))
            after_records, after_order = arc.raw_record_state(path.read_bytes())
            self.assertEqual(
                before_order[()],
                tuple(name for name in after_order[()] if name not in allowed),
            )
            self.assertEqual(
                allowed - set(before_order[()]),
                set(after_order[()]) - set(before_order[()]),
            )
            for record_path, raw in before_records.items():
                self.assertEqual(raw, after_records[record_path], "/".join(record_path))

        for path in (migration.CLIENT_NPC, migration.CLIENT_MOB):
            image = load_client(path)
            canvases: list[WzCanvasProperty] = []

            def visit(parent) -> None:
                for child in parent.children():
                    if isinstance(child, WzCanvasProperty):
                        canvases.append(child)
                    if child.children():
                        visit(child)

            visit(image.root)
            self.assertTrue(canvases)
            visible = 0
            for canvas in canvases:
                self.assertEqual((1, 0), (canvas.format, canvas.format2))
                bitmap = decode_canvas(canvas, region="GMS")
                visible += int(
                    bitmap.width * bitmap.height > 1 and bitmap.getbbox() is not None
                )
            self.assertGreater(visible, 0)

        self.assertTrue(migration.SERVER_NPC.is_file())
        self.assertTrue(migration.SERVER_MOB.is_file())
        npc_strings = load_client(migration.CLIENT_NPC_STRING)
        mob_strings = load_client(migration.CLIENT_MOB_STRING)
        self.assertEqual(
            "倍爾", npc_strings.root.get(f"{migration.NPC_ID}/name").value
        )
        self.assertEqual(
            "黑洞產生器", mob_strings.root.get(f"{migration.MOB_ID}/name").value
        )
        for path in migration.SERVER_NPC_STRINGS:
            self.assertIn(str(migration.NPC_ID), direct_imgdirs(path))
        for path in migration.SERVER_MOB_STRINGS:
            self.assertIn(str(migration.MOB_ID), direct_imgdirs(path))

        map_image = load_client(migration.CLIENT_MAP)
        self.assertEqual(str(migration.NPC_ID), map_image.root.get("life/1/id").value)
        self.assertEqual(str(migration.MOB_ID), map_image.root.get("life/2/id").value)
        baseline_records, baseline_order = arc.raw_record_state(git_baseline(migration.CLIENT_MAP))
        current_records, current_order = arc.raw_record_state(migration.CLIENT_MAP.read_bytes())
        self.assertEqual(baseline_order[("life",)], current_order[("life",)][: len(baseline_order[("life",)])])
        self.assertEqual(
            {"1", "2"},
            set(current_order[("life",)]) - set(baseline_order[("life",)]),
        )
        for record_path, raw in baseline_records.items():
            is_life_parent = record_path in {(), ("life",)}
            if not is_life_parent:
                self.assertEqual(raw, current_records[record_path], "/".join(record_path))

        server_life = direct_imgdirs(migration.SERVER_MAP, "life")
        self.assertEqual(
            str(migration.NPC_ID),
            server_life["1"].find("./string[@name='id']").get("value"),
        )
        self.assertEqual(
            str(migration.MOB_ID),
            server_life["2"].find("./string[@name='id']").get("value"),
        )
        for name in ("1", "2"):
            self.assertEqual(1, int_value(server_life[name], "fh"))
            self.assertEqual(-33, int_value(server_life[name], "cy"))

    def test_drop_rows_are_quest_limited(self):
        sql = migration.DROP_MIGRATION.read_text(encoding="utf-8")
        for quest_id, (item_id, _, mob_id) in migration.COLLECTION_QUESTS.items():
            signed_id = migration.signed_quest_id(quest_id)
            self.assertIn(f"({mob_id}, {item_id}, 1, 1, {signed_id}, 500000)", sql)

    def test_generator_uses_incremental_writes_for_existing_imgs(self):
        source = Path(migration.__file__).read_text(encoding="utf-8")
        self.assertNotIn("encode_image_body", source)
        self.assertNotIn("save_as(", source)
        self.assertIn("insert_property_record_before", source)
        self.assertIn("verify_raw_record_insert_scope", source)


if __name__ == "__main__":
    unittest.main()
