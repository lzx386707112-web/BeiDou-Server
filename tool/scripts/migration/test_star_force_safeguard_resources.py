from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(MIGRATION_DIR)]

import add_star_force_safeguard_scrolls as migration  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


ITEM_IDS = tuple(range(4260012, 4260020))
ITEM_NODES = tuple(f"0{item_id}" for item_id in ITEM_IDS)
APPROVED_ITEM_ROOTS = {(node,) for node in ITEM_NODES}
APPROVED_STRING_ROOTS = {("Etc", str(item_id)) for item_id in ITEM_IDS}


def git_blob(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def xml_parent(root: ET.Element, path: tuple[str, ...]) -> ET.Element:
    parent = root
    for part in path:
        found = next(
            (child for child in parent if child.tag == "imgdir" and child.get("name") == part),
            None,
        )
        if found is None:
            raise AssertionError(f"missing XML parent: {'/'.join(path)}")
        parent = found
    return parent


def xml_node_bytes(node: ET.Element) -> bytes:
    tail = node.tail
    node.tail = None
    try:
        return ET.tostring(node)
    finally:
        node.tail = tail


class StarForceSafeguardResourceTest(unittest.TestCase):
    def test_ids_names_and_reductions(self) -> None:
        self.assertEqual(tuple(spec.item_id for spec in migration.SCROLLS), ITEM_IDS)
        self.assertEqual(tuple(spec.reduction for spec in migration.SCROLLS), tuple(range(2, 18, 2)))
        for spec in migration.SCROLLS:
            self.assertEqual(spec.name, f"星之力防爆卷{spec.reduction}%")
            self.assertIn(f"降低{spec.reduction}个百分点", spec.description)

    def test_source_icon_is_the_supplied_asset(self) -> None:
        self.assertEqual(
            hashlib.sha256(migration.SOURCE_ICON.read_bytes()).hexdigest(),
            "ee3c08f8436c30870371f010f24b8069f79d400fd5cc2d41e8311f699a2a6ece",
        )

    def test_client_item_insert_scope_and_order(self) -> None:
        baseline = git_blob(migration.CLIENT_ITEM)
        current = migration.CLIENT_ITEM.read_bytes()
        arc.verify_raw_record_insert_scope(baseline, current, APPROVED_ITEM_ROOTS)
        _, before_orders = arc.raw_record_state(baseline)
        _, after_orders = arc.raw_record_state(current)
        self.assertEqual(after_orders[()][-8:], ITEM_NODES)
        self.assertEqual(tuple(name for name in after_orders[()] if name not in ITEM_NODES), before_orders[()])

    def test_client_string_insert_scope_and_order(self) -> None:
        baseline = git_blob(migration.CLIENT_STRING)
        current = migration.CLIENT_STRING.read_bytes()
        arc.verify_raw_record_insert_scope(baseline, current, APPROVED_STRING_ROOTS)
        _, before_orders = arc.raw_record_state(baseline)
        _, after_orders = arc.raw_record_state(current)
        order = after_orders[("Etc",)]
        anchor = order.index(migration.STRING_ANCHOR)
        self.assertEqual(order[anchor - 8:anchor], tuple(str(item_id) for item_id in ITEM_IDS))
        self.assertEqual(
            tuple(name for name in order if name not in {str(item_id) for item_id in ITEM_IDS}),
            before_orders[("Etc",)],
        )

    def test_client_canvases_decode_and_match(self) -> None:
        item = migration.load_client_bytes(
            migration.CLIENT_ITEM.read_bytes(), migration.CLIENT_ITEM.name
        )
        canvas_hashes: dict[str, set[str]] = {"icon": set(), "iconRaw": set()}
        for node in ITEM_NODES:
            for name in canvas_hashes:
                canvas = item.get(f"{node}/info/{name}")
                self.assertIsInstance(canvas, WzCanvasProperty)
                self.assertEqual((canvas.width, canvas.height, canvas.format, canvas.format2), (32, 32, 1, 0))
                pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
                self.assertIsNotNone(pixels.getchannel("A").getbbox())
                canvas_hashes[name].add(hashlib.sha256(pixels.tobytes()).hexdigest())
        self.assertEqual({name: len(values) for name, values in canvas_hashes.items()}, {"icon": 1, "iconRaw": 1})

    def test_client_strings(self) -> None:
        strings = migration.load_client_bytes(
            migration.CLIENT_STRING.read_bytes(), migration.CLIENT_STRING.name
        )
        for spec in migration.SCROLLS:
            self.assertEqual(strings.get(f"Etc/{spec.item_id}/name").value, spec.name)
            self.assertEqual(strings.get(f"Etc/{spec.item_id}/desc").value, spec.description)

    def test_server_xml_additions_are_exact(self) -> None:
        targets = [
            (migration.SERVER_ITEM, (), set(ITEM_NODES)),
            *[(path, ("Etc",), {str(item_id) for item_id in ITEM_IDS}) for path in migration.SERVER_STRINGS],
        ]
        for path, parent_path, expected_additions in targets:
            before = xml_parent(ET.fromstring(git_blob(path)), parent_path)
            after = xml_parent(ET.parse(path).getroot(), parent_path)
            before_nodes = {child.get("name"): xml_node_bytes(child) for child in before if child.tag == "imgdir"}
            after_nodes = {child.get("name"): xml_node_bytes(child) for child in after if child.tag == "imgdir"}
            self.assertEqual(set(after_nodes) - set(before_nodes), expected_additions)
            self.assertEqual(set(before_nodes) - set(after_nodes), set())
            for name, raw in before_nodes.items():
                self.assertEqual(after_nodes[name], raw, f"legacy XML node changed: {path}:{name}")

    def test_generator_uses_incremental_atomic_writes(self) -> None:
        source = Path(migration.__file__).read_text(encoding="utf-8")
        self.assertIn("arc.append_property_record", source)
        self.assertIn("arc.insert_property_records_before", source)
        self.assertIn("arc.verify_raw_record_insert_scope", source)
        self.assertIn("arc.atomic_write_bytes", source)
        self.assertIn("arc.atomic_write_text", source)
        self.assertNotIn("encode_image_body", source)
        self.assertNotIn("save_as(", source)


if __name__ == "__main__":
    unittest.main()
