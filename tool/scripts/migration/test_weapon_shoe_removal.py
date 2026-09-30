#!/usr/bin/env python3
"""Post-removal checks for the approved equipment deletion boundary."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_weapon_shoe_removal as migration
from wzpy.properties import WzCanvasProperty


def baseline(path):
    return subprocess.check_output(["rtk", "proxy", "git", "cat-file", "blob", f"HEAD:{path.relative_to(migration.ROOT)}"],
                                   cwd=migration.ROOT)


class RemovalContract(unittest.TestCase):
    def test_frozen_decision(self):
        ids = migration.delete_ids()
        self.assertEqual(315, len(ids))
        self.assertEqual(24, sum(migration.audit_tool.category(i) == "Shoes" for i in ids))
        self.assertTrue(ids.isdisjoint(migration.KEEP_IDS))

    def test_removed_files_absent_and_keep_files_exact(self):
        for item_id in migration.delete_ids():
            for path in migration.audit_tool.equipment_paths(item_id):
                self.assertFalse(path.exists(), path)
        result = json.loads(migration.RESULT.read_text(encoding="utf-8"))
        self.assertEqual(630, len(result["removed_files"]))
        for relative, expected in result["protected_sha256"].items():
            self.assertEqual(expected, migration.digest((migration.ROOT / relative).read_bytes()), relative)

    def test_client_strings_raw_scope_and_parse(self):
        ids = migration.delete_ids()
        paths = [("Eqp", migration.audit_tool.category(i), str(i)) for i in sorted(ids)]
        data = migration.CLIENT_EQP.read_bytes()
        migration.verify_scope(baseline(migration.CLIENT_EQP), data, paths)
        migration.verify_img(data, "GMS")
        layout = migration.scan_img(data, region="GMS")
        for path in paths:
            with self.assertRaises(KeyError):
                migration._find_record(layout.root, path)
        for item_id in migration.KEEP_IDS:
            migration._find_record(layout.root, ("Eqp", migration.audit_tool.category(item_id), str(item_id)))
        image = migration.WzImage.from_bytes(data, key=migration.WzKey.for_region("GMS"))
        def canvases(node):
            return int(isinstance(node, WzCanvasProperty)) + sum(canvases(child) for child in node.children())
        self.assertEqual(0, canvases(image.parse()), "Name-only IMG must not modify Canvas payloads")

    def test_xml_strings_exact_scope(self):
        paths = [("Eqp", migration.audit_tool.category(i), str(i)) for i in sorted(migration.delete_ids())]
        for path in migration.SERVER_EQP:
            text = path.read_text(encoding="utf-8")
            migration.verify_scope(baseline(path).decode("utf-8"), text, paths, xml=True)
            tree = migration.scan_xml(text)
            for target in paths:
                with self.assertRaises(KeyError):
                    migration._find_node(tree, target)

    def test_catalog_and_handbook_scope(self):
        ids = migration.delete_ids()
        old = json.loads(baseline(migration.CATALOG))
        new = json.loads(migration.CATALOG.read_text(encoding="utf-8"))
        old["items"] = [item for item in old["items"] if int(item["id"]) not in ids]
        for category in ("Weapon", "Shoes"):
            items = [item for item in old["items"] if item.get("category") == category]
            old["atlases"][category]["count"] = len(items)
            old["atlases"][category]["icons"] = sum(bool(item.get("icon")) for item in items)
            path = migration.ROOT / "gms-server/handbook/Equip" / f"{category}.txt"
            expected = "".join(line for line in baseline(path).decode("utf-8").splitlines(keepends=True)
                               if not (line[:7].isdigit() and int(line[:7]) in ids))
            self.assertEqual(expected, path.read_text(encoding="utf-8"))
        self.assertEqual(old, new)

    def test_cleanup_sql_only_approved_ids(self):
        text = migration.SQL.read_text(encoding="utf-8")
        values = text.split("VALUES\n", 1)[1].split(";", 1)[0]
        sql_ids = re.findall(r"\((\d{7})\)", values)
        self.assertEqual(315, len(sql_ids))
        self.assertEqual(migration.delete_ids(), set(map(int, sql_ids)))
        self.assertEqual(migration.sql_text(migration.delete_ids()), text)
        self.assertLess(text.index("FROM `inventoryequipment`"), text.index("FROM `inventoryitems` AS target"))

    def test_apply_is_idempotent(self):
        writes, deletes, _checks = migration.plan(migration.delete_ids())
        self.assertEqual({}, writes)
        self.assertEqual([], deletes)

    def test_delete_manifest_matches_exact_paths(self):
        manifest = json.loads(migration.DELETE_MANIFEST.read_text(encoding="utf-8"))
        expected = {str(path.relative_to(migration.ROOT)) for i in migration.delete_ids()
                    for path in migration.audit_tool.equipment_paths(i)}
        self.assertEqual(expected, {item["path"] for item in manifest["files"]})
        self.assertEqual(sorted(migration.KEEP_IDS), manifest["keep_ids"])


if __name__ == "__main__":
    unittest.main()
