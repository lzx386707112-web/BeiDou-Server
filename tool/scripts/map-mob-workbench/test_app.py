#!/usr/bin/env python3
"""Focused safety tests for Map & Mob Workbench."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_APP_PATH = Path(__file__).with_name("app.py")
_SPEC = importlib.util.spec_from_file_location("map_mob_workbench_app", _APP_PATH)
assert _SPEC and _SPEC.loader
workbench = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = workbench
_SPEC.loader.exec_module(workbench)


class XmlPatchTests(unittest.TestCase):
    SOURCE = b'''<?xml version="1.0" encoding="UTF-8"?>
<imgdir name="1.img">
  <imgdir name="info">
    <int name="level" value="10"/>
    <vector name="pos" x="1" y="2"/>
  </imgdir>
</imgdir>
'''

    def test_edit_add_delete_preserve_surrounding_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "1.img.xml"
            path.write_bytes(self.SOURCE)
            workbench.patch_xml_value(path, "info/level", 12, dry_run=False, backup=False)
            workbench.xml_add_node(path, "info", "speed", "int", -5, dry_run=False, backup=False)
            workbench.xml_delete_node(path, "info/pos", dry_run=False, backup=False)
            self.assertEqual(
                path.read_bytes(),
                self.SOURCE.replace(b'value="10"', b'value="12"').replace(
                    b'    <vector name="pos" x="1" y="2"/>\n',
                    b'    <int name="speed" value="-5"/>\n',
                ),
            )

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "1.img.xml"
            path.write_bytes(self.SOURCE)
            workbench.patch_xml_value(path, "info/level", 99, dry_run=True, backup=False)
            self.assertEqual(path.read_bytes(), self.SOURCE)


class ImgPatchTests(unittest.TestCase):
    def test_real_mob_scalar_dry_run_is_bounded(self) -> None:
        path = workbench._ROOT / "clien" / "Data" / "Mob" / "8641002.img"
        if not path.is_file():
            self.skipTest("repository sample Mob IMG is unavailable")
        before = path.read_bytes()
        result = workbench.patch_img(path, "info/level", 202, dry_run=True, backup=False)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(result["slots"][0]["length"], 5)


class MapPreviewTests(unittest.TestCase):
    def test_map_preview_distinguishes_mobs_npcs_and_portals(self) -> None:
        path = workbench._ROOT / "clien" / "Data" / "Map" / "Map" / "Map1" / "100040000.img"
        if not path.is_file():
            self.skipTest("repository sample Map IMG is unavailable")
        preview = workbench.map_preview(path)
        mobs = [point for point in preview["life"] if point["kind"] == "mob"]
        npcs = [point for point in preview["life"] if point["kind"] == "npc"]
        self.assertTrue(mobs)
        self.assertTrue(npcs)
        self.assertTrue(preview["portals"])
        self.assertTrue(all("sprite" in point for point in mobs + npcs + preview["portals"]))
        self.assertTrue(all(point["path"].startswith("life/") for point in mobs + npcs))
        self.assertTrue(all(point["path"].startswith("portal/") for point in preview["portals"]))
        self.assertTrue(all(element["path"] for element in preview["elements"]))
        self.assertTrue(all(line["path"].startswith("foothold/") for line in preview["footholds"]))

    def test_tms_map_is_default_comparison_and_resolves_split_canvas(self) -> None:
        map_path = workbench._TMS_DATA / "Map" / "Map" / "Map1" / "100040000.img"
        tile_path = workbench._TMS_DATA / "Map" / "Tile" / "grassySoil.img"
        if not map_path.is_file() or not tile_path.is_file():
            self.skipTest("TMS IMG dataset is unavailable")
        self.assertEqual(workbench.default_paths("map", "100040000")[1], map_path)
        flattened, info = workbench.flatten_source(map_path)
        self.assertEqual(info["format"], "img")
        self.assertIn("life/0/id", flattened)
        preview = workbench.map_preview(map_path)
        mobs = [point for point in preview["life"] if point["kind"] == "mob"]
        self.assertTrue(mobs)
        self.assertTrue(all("sprite" in point for point in mobs))
        image = workbench.load_image(tile_path)
        _, canvas, resolved_path = workbench.resolve_canvas_node(image, "slRU/0", tile_path)
        self.assertIn("_Canvas", resolved_path.parts)
        self.assertGreater(canvas.width, 1)
        descriptor = workbench.canvas_descriptor(tile_path, "slRU/0")
        self.assertEqual(descriptor["origin"], {"x": 0, "y": 96})
        stat = resolved_path.stat()
        decoded = workbench.decode_canvas(
            canvas,
            region=workbench.canvas_region(str(resolved_path), stat.st_mtime_ns, stat.st_size),
        )
        self.assertEqual(decoded.size, (canvas.width, canvas.height))

    def test_tms_compatibility_report_identifies_added_nodes_and_resources(self) -> None:
        left_path = workbench._ROOT / "clien" / "Data" / "Map" / "Map" / "Map1" / "100040000.img"
        right_path = workbench._TMS_DATA / "Map" / "Map" / "Map1" / "100040000.img"
        if not left_path.is_file() or not right_path.is_file():
            self.skipTest("map comparison samples are unavailable")
        left, _ = workbench.flatten_source(left_path)
        right, _ = workbench.flatten_source(right_path)
        report = workbench.compatibility_analysis(left, right, left_path, right_path)
        self.assertGreater(report["rightOnlyCount"], 0)
        self.assertTrue(report["addedRoots"])
        self.assertTrue(report["categories"])
        self.assertTrue(report["resources"])
        self.assertTrue(all(item["status"] in {"ready", "missingFile", "missingCanvas"} for item in report["resources"]))

    def test_chew_chew_swim_node_explains_legacy_whole_map_projection(self) -> None:
        left_path = workbench._ROOT / "clien" / "Data" / "Map" / "Map" / "Map4" / "450002011.img"
        right_path = workbench._TMS_DATA / "Map" / "Map" / "Map4" / "450002011.img"
        if not left_path.is_file() or not right_path.is_file():
            self.skipTest("Chew Chew map samples are unavailable")
        left, _ = workbench.flatten_source(left_path)
        right, _ = workbench.flatten_source(right_path)
        rows, _ = workbench.merge_sources(left, right)
        workbench.annotate_rows(rows, "map", "450002011")
        swim = next(row for row in rows if row["path"] == "info/swim")
        self.assertEqual(swim["left"]["value"], 1)
        self.assertEqual(swim["right"]["value"], 0)
        self.assertIn("是否可游泳", swim["left"]["meaning"])
        self.assertIn("整张地图", swim["left"]["scope"])
        self.assertIn("保留 A", swim["left"]["migration"])
        self.assertIn("foothold", swim["left"]["migration"])


class FileBrowserTests(unittest.TestCase):
    def test_lists_supported_files_and_directories(self) -> None:
        result = workbench.browse_directory("gms-server/wz/Map.wz/Map/Map1")
        names = {item["name"] for item in result["items"]}
        self.assertIn("100000000.img.xml", names)
        self.assertTrue(all(item["type"] == "directory" or item["name"].lower().endswith(workbench._ALLOWED_SUFFIXES) for item in result["items"]))

    def test_rejects_directory_outside_home(self) -> None:
        with self.assertRaisesRegex(ValueError, "用户目录"):
            workbench.browse_directory("/tmp")


if __name__ == "__main__":
    unittest.main()
