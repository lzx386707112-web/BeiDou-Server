from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .app import create_app
from wzpy.crypto import WzKey
from wzpy.incremental_img import mutate_img, scan_img
from wzpy.incremental_xml import mutate_xml, scan_xml
from wzpy.properties import WzIntProperty, WzStringProperty, WzSubProperty
from wzpy.reader import WzBinaryReader
from wzpy.writer import _encode_property_list, encode_image_type_string


XML = """<?xml version="1.0" encoding="UTF-8"?>
<imgdir name="sample.img">
  <imgdir name="info">
    <int name="level" value="10"/>
    <string name="name" value="old"/>
  </imgdir>
  <int name="tail" value="7"/>
</imgdir>
"""


def _sample_img() -> bytes:
    info = WzSubProperty("info")
    info.add(WzIntProperty("level", 10, info))
    info.add(WzStringProperty("name", "old", info))
    reader = WzBinaryReader(io.BytesIO(), WzKey.for_region("GMS"))
    return (
        encode_image_type_string(reader, "Property")
        + b"\x00\x00"
        + _encode_property_list((info, WzIntProperty("tail", 7)), reader)
    )


def _record(data: bytes, path):
    prop_list = scan_img(data, region="GMS").root
    found = None
    for part in path:
        found = next(item for item in prop_list.records if item.name == part)
        if part != path[-1]:
            prop_list = found.children
    return found


class IncrementalMutationTests(unittest.TestCase):
    def test_file_picker_api_returns_selected_path(self):
        app = create_app()
        with patch("img_editor.app._pick_file", return_value="/tmp/sample.img"):
            response = app.test_client().post("/api/pick-file", json={
                "kind": "img",
                "current": "",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["path"], "/tmp/sample.img")

    def test_nested_resize_preserves_unrelated_records(self):
        original = _sample_img()
        old_tail = _record(original, ["tail"])
        old_level = _record(original, ["info", "level"])
        tail_bytes = original[old_tail.start:old_tail.end]
        level_bytes = original[old_level.start:old_level.end]

        changed = mutate_img(
            original,
            "edit",
            ["info", "name"],
            values={"value": "a much longer value"},
            region="GMS",
        ).data
        new_tail = _record(changed, ["tail"])
        new_level = _record(changed, ["info", "level"])
        self.assertEqual(tail_bytes, changed[new_tail.start:new_tail.end])
        self.assertEqual(level_bytes, changed[new_level.start:new_level.end])

    def test_add_then_remove_restores_img_exactly(self):
        original = _sample_img()
        added = mutate_img(
            original,
            "add",
            ["info"],
            name="origin",
            kind="Vector",
            values={"x": -3, "y": 8},
            region="GMS",
        ).data
        removed = mutate_img(
            added,
            "remove",
            ["info", "origin"],
            region="GMS",
        ).data
        self.assertEqual(original, removed)

    def test_xml_and_api_transaction(self):
        edited_xml = mutate_xml(
            XML,
            "edit",
            ["info", "name"],
            values={"value": "new & safe"},
        )
        scan_xml(edited_xml)
        self.assertIn('value="new &amp; safe"', edited_xml)

        with tempfile.TemporaryDirectory() as raw_dir:
            directory = Path(raw_dir)
            img_path = directory / "sample.img"
            xml_path = directory / "sample.img.xml"
            original = _sample_img()
            img_path.write_bytes(original)
            xml_path.write_text(XML, encoding="utf-8")
            img_path.chmod(0o640)
            client = create_app().test_client()
            self.assertEqual(client.post("/api/open", json={
                "img_path": str(img_path),
                "xml_path": str(xml_path),
                "region": "GMS",
            }).status_code, 200)
            response = client.post("/api/mutate", json={
                "operation": "edit",
                "path": ["info", "name"],
                "values": {"value": "updated"},
            })
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertIn('value="updated"', xml_path.read_text(encoding="utf-8"))
            self.assertEqual(img_path.stat().st_mode & 0o777, 0o640)
            self.assertEqual(
                img_path.with_name("sample.img.web-editor.bak").read_bytes(),
                original,
            )

    def test_xml_type_mismatch_is_rejected(self):
        mismatched = XML.replace(
            '<string name="name" value="old"/>',
            '<int name="name" value="1"/>',
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            mutate_xml(
                mismatched,
                "edit",
                ["info", "name"],
                kind="String",
                values={"value": "new"},
            )


if __name__ == "__main__":
    unittest.main()
