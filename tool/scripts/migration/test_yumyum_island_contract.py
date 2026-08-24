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

import migrate_arcane_river_fields as arcane  # noqa: E402
import migrate_yumyum_island_maps as migration  # noqa: E402
from migrate_karing_later_stages import locate_records  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


CLIENT = ROOT / "clien/Data"


def load(path: Path, data: bytes | None = None) -> WzImage:
    payload = path.read_bytes() if data is None else data
    image = WzImage.from_bytes(payload, key=arcane.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"malformed IMG {path}: {image.parse_warnings}")
    return image


def visible_canvas_count(root) -> tuple[int, int]:
    canvases = visible = 0
    for node, path in arcane.walk(root):
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases += 1
        if (int(node.format), int(node.format2)) != (1, 0):
            raise AssertionError((path, node.format, node.format2))
        bitmap = decode_canvas(node, region="GMS")
        if bitmap.size != (int(node.width), int(node.height)):
            raise AssertionError(path)
        visible += bitmap.getbbox() is not None
    return canvases, visible


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def raw_records(path: Path, data: bytes, parent: tuple[str, ...]):
    image = load(path, data)
    _, _, _, names, spans, _ = locate_records(image, data, parent)
    return names, {
        name: data[start:end]
        for name, (start, end) in zip(names, spans, strict=True)
    }


class YumYumIslandContract(unittest.TestCase):
    def test_maps_are_legacy_safe_and_routes_close(self):
        maps = {}
        for map_id in (*migration.MAP_IDS, 450002025):
            path = CLIENT / f"Map/Map/Map4/{map_id}.img"
            maps[map_id] = load(path)

        portal_names = {}
        for map_id, image in maps.items():
            portal = image.root.child("portal")
            self.assertIsInstance(portal, WzSubProperty, map_id)
            portal_names[map_id] = {
                str(arcane.child_value(entry, "pn")) for entry in portal.children()
            }

        for map_id in migration.MAP_IDS:
            image = maps[map_id]
            self.assertLessEqual(
                {child.name for child in image.root.children()}, migration.story.MAP_ROOTS
            )
            info = image.root.child("info")
            self.assertIsInstance(info, WzSubProperty)
            for name in migration.story.MAP_INFO_UNSUPPORTED:
                self.assertIsNone(info.child(name), (map_id, name))
            portal = image.root.child("portal")
            for entry in portal.children():
                self.assertNotEqual(10, arcane.child_value(entry, "pt"), map_id)
                self.assertIsNone(entry.child("script"), map_id)
                target = arcane.child_value(entry, "tm")
                target_name = str(arcane.child_value(entry, "tn") or "")
                if target in portal_names and target_name:
                    self.assertIn(target_name, portal_names[target], (map_id, target, target_name))
            for layer in [child for child in image.root.children() if child.name.isdigit()]:
                objects = layer.child("obj")
                if not isinstance(objects, WzSubProperty):
                    continue
                entries = list(objects.children())
                connect_count = sum(
                    arcane.child_value(entry, "oS") == "connect" for entry in entries
                )
                self.assertTrue(
                    all(
                        arcane.child_value(entry, "oS") == "connect"
                        for entry in entries[:connect_count]
                    )
                )
                for entry in entries:
                    self.assertFalse(
                        set(child.name for child in entry.children())
                        & migration.story.OBJ_UNSUPPORTED
                    )
            ET.parse(
                ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
            )

        story_exit = maps[450002025].root.child("portal")
        out = next(
            entry
            for entry in story_exit.children()
            if arcane.child_value(entry, "pn") == "out00"
        )
        self.assertEqual((2, 450015020, "west00"), (
            arcane.child_value(out, "pt"),
            arcane.child_value(out, "tm"),
            arcane.child_value(out, "tn"),
        ))

    def test_dependency_closure_and_resource_payloads(self):
        dependencies = migration.collect_dependencies()
        for (kind, name), branches in dependencies["assets"].items():
            asset_path = CLIENT / f"Map/{kind}/{name}.img"
            asset = load(asset_path)
            for branch in branches:
                self.assertIsNotNone(asset.root.get(branch), (kind, name, branch))
            if (kind, name) in migration.NEW_ASSETS:
                canvases, visible = visible_canvas_count(asset.root)
                self.assertGreater(canvases, 0, (kind, name))
                self.assertGreater(visible, 0, (kind, name))

        for mob_id in sorted(dependencies["mobs"]):
            mob = load(CLIENT / f"Mob/{mob_id:07d}.img")
            self.assertEqual(100, arcane.child_value(mob.root.child("info"), "eva"))
            self.assertIsNotNone(mob.root.get("info/maxHP"), mob_id)
            canvases, visible = visible_canvas_count(mob.root)
            link = arcane.child_value(mob.root.child("info"), "link")
            if canvases == 0:
                self.assertIsInstance(link, str, mob_id)
                linked_id = int(link)
                self.assertIn(linked_id, dependencies["mobs"])
                linked = load(CLIENT / f"Mob/{linked_id:07d}.img")
                linked_canvases, linked_visible = visible_canvas_count(linked.root)
                self.assertGreater(linked_canvases, 0, (mob_id, linked_id))
                self.assertGreater(linked_visible, 0, (mob_id, linked_id))
            else:
                self.assertGreater(visible, 0, mob_id)
            ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml")

        for npc_id in sorted(value for value in dependencies["npcs"] if str(value).startswith("300")):
            npc = load(CLIENT / f"Npc/{npc_id:07d}.img")
            canvases, visible = visible_canvas_count(npc.root)
            self.assertGreater(canvases, 0, npc_id)
            self.assertGreater(visible, 0, npc_id)
            ET.parse(ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml")

        bgm = load(CLIENT / "Sound/Bgm54.img")
        for reference in migration.EXPECTED_BGMS:
            self.assertIsNotNone(bgm.root.get(reference.split("/", 1)[1]))

    def test_strings_mark_and_raw_preservation(self):
        map_strings = load(CLIENT / "String/Map.img")
        mob_strings = load(CLIENT / "String/Mob.img")
        npc_strings = load(CLIENT / "String/Npc.img")
        for map_id in migration.MAP_IDS:
            self.assertIsNotNone(map_strings.root.get(f"grandis/{map_id}"))
        for mob_id in migration.EXPECTED_MOBS:
            self.assertIsNotNone(mob_strings.root.get(str(mob_id)))
        for npc_id in migration.EXPECTED_NPCS:
            self.assertIsNotNone(npc_strings.root.get(str(npc_id)))

        helper_path = CLIENT / "Map/MapHelper.img"
        helper = load(helper_path)
        mark = helper.root.get("mark/YumYum")
        self.assertIsInstance(mark, WzCanvasProperty)
        self.assertEqual((1, 0), (int(mark.format), int(mark.format2)))
        self.assertIsNotNone(decode_canvas(mark, region="GMS").getbbox())
        old_names, old_raw = raw_records(helper_path, git_baseline(helper_path), ("mark",))
        new_names, new_raw = raw_records(helper_path, helper_path.read_bytes(), ("mark",))
        self.assertEqual((*old_names, "YumYum"), new_names)
        for name, record in old_raw.items():
            self.assertEqual(record, new_raw[name], name)

        specs = (
            (
                CLIENT / "String/Map.img",
                ("grandis",),
                tuple(str(value) for value in (*migration.story.MAP_IDS, *migration.MAP_IDS)),
            ),
            (
                CLIENT / "String/Mob.img",
                (),
                tuple(str(value) for value in sorted(migration.EXPECTED_MOBS)),
            ),
            (
                CLIENT / "String/Npc.img",
                (),
                tuple(
                    str(value)
                    for value in (
                        *migration.story.NPC_IDS,
                        *sorted(migration.EXPECTED_NPCS),
                    )
                ),
            ),
        )
        for path, parent, insertion_order in specs:
            old_names, old_raw = raw_records(path, git_baseline(path), parent)
            new_names, new_raw = raw_records(path, path.read_bytes(), parent)
            expected_names = list(old_names)
            expected_names.extend(name for name in insertion_order if name not in expected_names)
            self.assertEqual(tuple(expected_names), new_names, path.name)
            allowed = set(insertion_order)
            for name, record in old_raw.items():
                if name not in allowed:
                    self.assertEqual(record, new_raw[name], f"{path.name}/{name}")

    def test_generator_keeps_shared_imgs_incremental(self):
        source = Path(migration.__file__).read_text(encoding="utf-8")
        self.assertIn("insert_raw_record", source)
        self.assertNotIn("save_as(", source)


if __name__ == "__main__":
    unittest.main()
