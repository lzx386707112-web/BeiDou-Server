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

import migrate_chewchew_quests as migration  # noqa: E402
from migrate_arcane_river_fields import GMS_KEY  # noqa: E402
from migrate_karing_later_stages import locate_records  # noqa: E402
from wzpy import WzCanvasProperty, WzImage  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def load(path: Path, data: bytes | None = None) -> tuple[WzImage, bytes]:
    payload = path.read_bytes() if data is None else data
    image = WzImage.from_bytes(payload, key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"malformed IMG {path}: {image.parse_warnings}")
    return image, payload


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def raw_records(path: Path, data: bytes, parent: tuple[str, ...] = ()):
    image, _ = load(path, data)
    _, _, _, names, spans, _ = locate_records(image, data, parent)
    return names, {
        name: data[start:end]
        for name, (start, end) in zip(names, spans, strict=True)
    }


def direct_children(path: Path, parent_name: str) -> dict[str, ET.Element]:
    root = ET.parse(path).getroot()
    if root.get("name") != parent_name:
        root = root.find(f"./imgdir[@name='{parent_name}']")
    if root is None:
        raise AssertionError((path, parent_name))
    return {child.get("name", ""): child for child in root if child.tag == "imgdir"}


def child_value(node: ET.Element | None, name: str):
    if node is None:
        return None
    child = node.find(f"./*[@name='{name}']")
    if child is None:
        return None
    raw = child.get("value")
    return int(raw) if child.tag in {"int", "short", "long"} and raw is not None else raw


class ChewChewYumYumQuestContract(unittest.TestCase):
    def test_signed_ids_are_bit_identical(self):
        for quest_id in migration.QUEST_IDS:
            runtime_id = migration.signed_quest_id(quest_id)
            self.assertEqual(quest_id & 0xFFFF, runtime_id & 0xFFFF)
            self.assertLess(runtime_id, 0)

    def test_client_records_are_incremental_and_positive(self):
        approved = {str(value) for value in migration.QUEST_IDS}
        retired = {str(migration.signed_quest_id(value)) for value in migration.QUEST_IDS}
        append_order = tuple(str(value) for value in migration.QUEST_IDS)
        for image_name in migration.QUEST_IMAGE_NAMES:
            path = ROOT / f"clien/Data/Quest/{image_name}.img"
            old_names, old_raw = raw_records(path, git_baseline(path))
            new_names, new_raw = raw_records(path, path.read_bytes())
            expected = [name for name in old_names if name not in retired]
            expected.extend(name for name in append_order if name not in expected)
            self.assertEqual(tuple(expected), new_names, image_name)
            for name, record in old_raw.items():
                if name not in approved and name not in retired:
                    self.assertEqual(record, new_raw[name], f"{image_name}/{name}")
            self.assertTrue(approved <= new_raw.keys())
            self.assertFalse(retired & new_raw.keys())

    def test_client_and_server_quest_semantics(self):
        client = {
            name: load(ROOT / f"clien/Data/Quest/{name}.img")[0]
            for name in migration.QUEST_IMAGE_NAMES
        }
        for quest_id in migration.QUEST_IDS:
            for image_name, image in client.items():
                self.assertIsNotNone(image.root.get(str(quest_id)), (image_name, quest_id))
            self.assertIsInstance(client["Check"].root.get(f"{quest_id}/0/npc").value, int)
            self.assertIsInstance(client["Check"].root.get(f"{quest_id}/1/npc").value, int)
        for quest_id in migration.DAILY_IDS:
            self.assertEqual(1440, client["Check"].root.get(f"{quest_id}/0/interval").value)

        for tree in ("wz", "wz-zh-CN"):
            roots = {
                name: direct_children(
                    ROOT / f"gms-server/{tree}/Quest.wz/{name}.img.xml",
                    f"{name}.img",
                )
                for name in migration.QUEST_IMAGE_NAMES
            }
            for quest_id in migration.QUEST_IDS:
                runtime_id = str(migration.signed_quest_id(quest_id))
                for image_name, nodes in roots.items():
                    self.assertIn(runtime_id, nodes, (tree, image_name, runtime_id))
                    self.assertNotIn(str(quest_id), nodes, (tree, image_name, quest_id))
            for quest_id in migration.DAILY_IDS:
                runtime_id = str(migration.signed_quest_id(quest_id))
                start = roots["Check"][runtime_id].find("./imgdir[@name='0']")
                self.assertEqual(1440, child_value(start, "interval"))

    def test_server_xml_changes_only_direct_quest_records(self):
        positive = {str(value) for value in migration.QUEST_IDS}
        negative_order = tuple(
            str(migration.signed_quest_id(value)) for value in migration.QUEST_IDS
        )
        for tree in ("wz", "wz-zh-CN"):
            for image_name in migration.QUEST_IMAGE_NAMES:
                path = ROOT / f"gms-server/{tree}/Quest.wz/{image_name}.img.xml"
                baseline = git_baseline(path).decode("utf-8-sig")
                current = path.read_text(encoding="utf-8-sig")
                _, old_spans = migration.direct_imgdir_spans(
                    baseline, f"{image_name}.img"
                )
                _, new_spans = migration.direct_imgdir_spans(
                    current, f"{image_name}.img"
                )
                old_names = tuple(old_spans)
                expected_names = [name for name in old_names if name not in positive]
                expected_names.extend(
                    name for name in negative_order if name not in expected_names
                )
                self.assertEqual(tuple(expected_names), tuple(new_spans), (tree, image_name))
                for name, (start, end) in old_spans.items():
                    if name not in positive:
                        new_start, new_end = new_spans[name]
                        self.assertEqual(
                            baseline[start:end],
                            current[new_start:new_end],
                            f"{tree}/{image_name}/{name}",
                        )

    def test_npc_mob_and_item_closure(self):
        _, records = migration.build_all_nodes(signed_ids=True)
        npcs, mobs = migration.installed_life_ids()
        self.assertFalse({record.start_npc for record in records} - npcs)
        self.assertFalse({record.end_npc for record in records} - npcs)
        self.assertFalse({mob for record in records for mob, _ in record.mobs} - mobs)

        item_path = ROOT / "clien/Data/Item/Etc/0403.img"
        item, item_data = load(item_path)
        string_path = ROOT / "clien/Data/String/Etc.img"
        strings, string_data = load(string_path)
        old_item_names, old_item_raw = raw_records(item_path, git_baseline(item_path))
        new_item_names, new_item_raw = raw_records(item_path, item_data)
        self.assertTrue(set(old_item_names) <= set(new_item_names))
        allowed_items = {f"0{item_id}" for item_id in migration.QUEST_ITEMS}
        for name, record in old_item_raw.items():
            if name not in allowed_items:
                self.assertEqual(record, new_item_raw[name], f"Item/0403/{name}")
        old_string_names, old_string_raw = raw_records(
            string_path, git_baseline(string_path), ("Etc",)
        )
        new_string_names, new_string_raw = raw_records(
            string_path, string_data, ("Etc",)
        )
        self.assertTrue(set(old_string_names) <= set(new_string_names))
        allowed_strings = {str(item_id) for item_id in migration.QUEST_ITEMS}
        for name, record in old_string_raw.items():
            if name not in allowed_strings:
                self.assertEqual(record, new_string_raw[name], f"String/Etc/{name}")
        for item_id in migration.QUEST_ITEMS:
            node_name = f"0{item_id}"
            self.assertIsNotNone(item.root.get(node_name))
            self.assertIsNotNone(strings.root.get(f"Etc/{item_id}/name"))
            for canvas_name in ("icon", "iconRaw"):
                canvas = item.root.get(f"{node_name}/info/{canvas_name}")
                self.assertIsInstance(canvas, WzCanvasProperty)
                self.assertEqual((1, 0), (int(canvas.format), int(canvas.format2)))
                self.assertIsNotNone(decode_canvas(canvas, region="GMS").getbbox())

        item_xml = direct_children(
            ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml", "0403.img"
        )
        for item_id in migration.QUEST_ITEMS:
            self.assertIn(f"0{item_id}", item_xml)
            for tree in ("wz", "wz-zh-CN"):
                strings_xml = direct_children(
                    ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml", "Etc"
                )
                self.assertIn(str(item_id), strings_xml)

    def test_drop_migration_uses_runtime_ids(self):
        sql = (
            ROOT
            / "gms-server/src/main/resources/db/migration/"
            "V2.1.62__add_yumyum_mob_and_quest_drops.sql"
        ).read_text(encoding="utf-8")
        for mob_id in (8642050, 8642051, 8642052, 8642053, 8642054, 8642055,
                       8642060, 8642061, 8642062, 8642063, 8642064, 8642065):
            self.assertIn(str(mob_id), sql)
        expected = {
            (8642000, 4034942, -31333),
            (8642001, 4034943, -31329),
            (8642015, 4034958, -31321),
        }
        for mob_id, item_id, quest_id in expected:
            self.assertIn(f"({mob_id}, {item_id}, 1, 1, {quest_id}, 500000)", sql)
        self.assertIn("4036571, 1, 1, -26503", sql)
        self.assertIn("4036710, 1, 1, -26466", sql)

    def test_generator_never_serializes_existing_imgs(self):
        source = Path(migration.__file__).read_text(encoding="utf-8")
        self.assertIn("patch_raw_records", source)
        self.assertNotIn("encode_image_body", source)
        self.assertNotIn("save_as(", source)


if __name__ == "__main__":
    unittest.main()
