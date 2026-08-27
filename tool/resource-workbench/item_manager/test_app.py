from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from item_manager import app as item_module
from wzpy import WzIntProperty, WzKey, WzStringProperty, WzSubProperty
from wzpy.incremental_img import scan_img
from wzpy.reader import WzBinaryReader
from wzpy.writer import _encode_property_list, encode_image_type_string


def encode_img(nodes, region: str) -> bytes:
    reader = WzBinaryReader(io.BytesIO(), WzKey.for_region(region))
    return encode_image_type_string(reader, "Property") + b"\x00\x00" + _encode_property_list(tuple(nodes), reader)


def item_node(name: str, price: int = 1) -> WzSubProperty:
    node = WzSubProperty(name)
    info = WzSubProperty("info", node); node.add(info)
    info.add(WzIntProperty("price", price, info)); info.add(WzIntProperty("slotMax", 100, info))
    return node


def string_parent(item_id: str, name: str) -> WzSubProperty:
    root = WzSubProperty("Etc")
    node = WzSubProperty(item_id, root); root.add(node)
    node.add(WzStringProperty("name", name, node)); node.add(WzStringProperty("desc", f"{name}描述", node))
    return root


def record_bytes(data: bytes, name: str, region: str = "GMS") -> bytes:
    record = next(row for row in scan_img(data, region=region).root.records if row.name == name)
    return data[record.start:record.end]


class TemporaryItemWorkspace:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.tms = self.root / "TMS" / "Data"; self.client_item = self.root / "clien" / "Data" / "Item"
        self.server_item = self.root / "gms-server" / "wz" / "Item.wz"
        self.client_string = self.root / "clien" / "Data" / "String"
        self.server_string = self.root / "gms-server" / "wz" / "String.wz"
        self.zh_string = self.root / "gms-server" / "wz-zh-CN" / "String.wz"
        for path in (
            self.tms / "Item" / "Etc", self.tms / "String", self.client_item / "Etc",
            self.server_item / "Etc", self.client_string, self.server_string, self.zh_string,
        ):
            path.mkdir(parents=True, exist_ok=True)
        (self.client_item / "Etc" / "0400.img").write_bytes(encode_img([item_node("04000000", 7)], "GMS"))
        (self.tms / "Item" / "Etc" / "0400.img").write_bytes(encode_img([item_node("04000999", 15)], "BMS"))
        (self.client_string / "Etc.img").write_bytes(encode_img([string_parent("4000000", "旧物品")], "GMS"))
        (self.tms / "String" / "Etc.img").write_bytes(encode_img([string_parent("4000999", "TMS物品")], "BMS"))
        item_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="0400.img">\n  <imgdir name="04000000"><imgdir name="info"><int name="price" value="7"/><int name="slotMax" value="100"/></imgdir></imgdir>\n</imgdir>\n'
        string_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="Etc.img"><imgdir name="Etc"><imgdir name="4000000"><string name="name" value="旧物品"/><string name="desc" value="旧物品描述"/></imgdir></imgdir></imgdir>\n'
        (self.server_item / "Etc" / "0400.img.xml").write_text(item_xml)
        for base in (self.server_string, self.zh_string):
            (base / "Etc.img.xml").write_text(string_xml)
        replacements = {
            "ROOT": self.root, "TMS_DATA": self.tms, "CLIENT_ITEM": self.client_item,
            "SERVER_ITEM": self.server_item, "CLIENT_STRING": self.client_string,
            "SERVER_STRING": self.server_string, "ZH_STRING": self.zh_string,
            "BACKUP_ROOT": self.root / "backups",
        }
        self.patches = [mock.patch.object(item_module, name, value) for name, value in replacements.items()]
        self.patches.append(mock.patch.object(item_module.arc, "SOURCE", self.tms))
        for patcher in self.patches:
            patcher.start()
        item_module._local_catalog.cache_clear(); item_module._tms_catalog.cache_clear(); item_module._legacy_schema.cache_clear(); item_module._record_names.cache_clear()
        return self

    def __exit__(self, exc_type, exc, traceback):
        item_module._local_catalog.cache_clear(); item_module._tms_catalog.cache_clear(); item_module._legacy_schema.cache_clear(); item_module._record_names.cache_clear()
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()


class ItemManagerTests(unittest.TestCase):
    def test_reuses_record_scan_for_items_in_the_same_img(self):
        with TemporaryItemWorkspace():
            category = item_module.CATEGORIES["etc"]
            with mock.patch.object(item_module, "scan_img", wraps=item_module.scan_img) as scanner:
                self.assertTrue(item_module._item_exists(category, 4000000, "local"))
                self.assertFalse(item_module._item_exists(category, 4000001, "local"))
            self.assertEqual(scanner.call_count, 1)

    def test_copy_edit_metadata_delete_are_incremental_and_idempotent(self):
        with TemporaryItemWorkspace() as workspace:
            client = item_module.app.test_client(); item_path = workspace.client_item / "Etc" / "0400.img"
            old_item_record = record_bytes(item_path.read_bytes(), "04000000")
            old_xml_record = '<imgdir name="04000000"><imgdir name="info"><int name="price" value="7"/><int name="slotMax" value="100"/></imgdir></imgdir>'

            source = client.get("/api/item/tms/etc/4000999")
            self.assertEqual(source.status_code, 200, source.get_json())
            self.assertTrue(source.get_json()["compatibility"]["safe"])
            self.assertEqual(
                next(row for row in source.get_json()["projection"]["nodes"] if row["path"] == "info/price")["value"],
                15,
            )
            migration = {
                "category": "etc", "id": "4000999",
                "changes": [{"operation": "edit", "path": "info/price", "values": {"value": 33}}],
                "metadata": {"name": "迁移名称", "desc": "迁移描述"},
            }
            copied = client.post("/api/item/copy", json=migration)
            self.assertEqual(copied.status_code, 200, copied.get_json())
            self.assertEqual(next(row for row in copied.get_json()["item"]["nodes"] if row["path"] == "info/price")["value"], 33)
            self.assertEqual(copied.get_json()["item"]["name"], "迁移名称")
            first = {path: path.read_bytes() for path in (
                item_path, workspace.server_item / "Etc" / "0400.img.xml", workspace.client_string / "Etc.img",
                workspace.server_string / "Etc.img.xml", workspace.zh_string / "Etc.img.xml",
            )}
            self.assertEqual(record_bytes(item_path.read_bytes(), "04000000"), old_item_record)
            self.assertIn(old_xml_record.encode(), (workspace.server_item / "Etc" / "0400.img.xml").read_bytes())
            self.assertIsNotNone(next((row for row in scan_img(item_path.read_bytes(), region="GMS").root.records if row.name == "04000999"), None))

            repeated = client.post("/api/item/copy", json={**migration, "overwrite": True, "confirm": "4000999"})
            self.assertEqual(repeated.status_code, 200, repeated.get_json())
            self.assertEqual(first, {path: path.read_bytes() for path in first})

            edited = client.post("/api/item/node", json={
                "category": "etc", "id": "4000999", "operation": "edit", "path": "info/price", "values": {"value": 99},
            })
            self.assertEqual(edited.status_code, 200, edited.get_json())
            self.assertEqual(next(row for row in edited.get_json()["item"]["nodes"] if row["path"] == "info/price")["value"], 99)
            self.assertEqual(record_bytes(item_path.read_bytes(), "04000000"), old_item_record)

            metadata = client.post("/api/item/metadata", json={"category": "etc", "id": "4000999", "name": "新名称", "desc": "新描述"})
            self.assertEqual(metadata.status_code, 200, metadata.get_json())
            self.assertEqual(metadata.get_json()["item"]["name"], "新名称")

            rejected = client.post("/api/item/delete", json={"category": "etc", "id": "4000999", "confirm": "wrong"})
            self.assertEqual(rejected.status_code, 400)
            deleted = client.post("/api/item/delete", json={"category": "etc", "id": "4000999", "confirm": "4000999"})
            self.assertEqual(deleted.status_code, 200, deleted.get_json())
            self.assertFalse(any(row.name == "04000999" for row in scan_img(item_path.read_bytes(), region="GMS").root.records))
            self.assertEqual(record_bytes(item_path.read_bytes(), "04000000"), old_item_record)

    def test_unified_catalog_identifies_tms_only_items(self):
        with TemporaryItemWorkspace():
            response = item_module.app.test_client().get("/api/catalog?availability=missing&category=etc")
            self.assertEqual(response.status_code, 200, response.get_json())
            payload = response.get_json()
            self.assertEqual([row["id"] for row in payload["items"]], ["4000999"])
            self.assertFalse(payload["items"][0]["local"])
            self.assertTrue(payload["items"][0]["tms"])
            self.assertEqual(payload["items"][0]["status"], "missing")
            self.assertEqual(payload["counts"], {"all": 2, "both": 0, "local": 1, "missing": 1})

    def test_rejects_equipment_id(self):
        with TemporaryItemWorkspace():
            response = item_module.app.test_client().post("/api/item/copy", json={"category": "etc", "id": "1002000"})
            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
