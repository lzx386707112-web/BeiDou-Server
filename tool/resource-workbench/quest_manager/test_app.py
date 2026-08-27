from __future__ import annotations

import copy
import io
import importlib
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from quest_manager.app import _basic_payload, _item_drop_audit, _item_icon, _mob_preview, _npc_map_details, _npc_preview, _property_from_xml, _replace_xml_record, _validate_id
from wzpy.crypto import WzKey
from wzpy.incremental_img import mutate_img, replace_img_record, scan_img
from wzpy.properties import WzIntProperty, WzStringProperty, WzSubProperty
from wzpy.reader import WzBinaryReader
from wzpy.writer import _encode_property_list, encode_image_type_string

quest_module = importlib.import_module("quest_manager.app")


def sample_img() -> bytes:
    quest = WzSubProperty("1000")
    quest.add(WzStringProperty("name", "before", quest))
    tail = WzSubProperty("2000")
    tail.add(WzIntProperty("value", 7, tail))
    reader = WzBinaryReader(io.BytesIO(), WzKey.for_region("GMS"))
    return encode_image_type_string(reader, "Property") + b"\x00\x00" + _encode_property_list((quest, tail), reader)


def record(data: bytes, name: str):
    return next(item for item in scan_img(data, region="GMS").root.records if item.name == name)


def quest_xml(name: str) -> bytes:
    records = {
        "QuestInfo": '<imgdir name="1000"><string name="name" value="before" /><int name="custom" value="9" /></imgdir>',
        "Check": '<imgdir name="1000"><imgdir name="0"><int name="npc" value="2101" /></imgdir><imgdir name="1"><int name="npc" value="2100" /></imgdir></imgdir>',
        "Act": '<imgdir name="1000"><imgdir name="0" /><imgdir name="1" /></imgdir>',
        "Say": '<imgdir name="1000"><imgdir name="0" /><imgdir name="1" /></imgdir>',
    }
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<imgdir name="{name}.img">\n  '
            f'{records[name]}\n  <imgdir name="2000"><int name="value" value="7" /></imgdir>\n</imgdir>\n').encode()


class TemporaryQuestWorkspace:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = self.root / "client"
        self.server = self.root / "server"
        self.zh = self.root / "zh"
        self.backups = self.root / "backups"
        self.scripts = {"main": self.root / "scripts", "zh": self.root / "scripts-zh-CN"}
        for directory in (self.client, self.server, self.zh):
            directory.mkdir(parents=True)
        for name in quest_module.QUEST_FILES:
            (self.client / f"{name}.img").write_bytes(sample_img())
            (self.server / f"{name}.img.xml").write_bytes(quest_xml(name))
            (self.zh / f"{name}.img.xml").write_bytes(quest_xml(name))
        self.patches = [
            mock.patch.object(quest_module, "ROOT", self.root),
            mock.patch.object(quest_module, "CLIENT_QUEST", self.client),
            mock.patch.object(quest_module, "SERVER_QUEST", self.server),
            mock.patch.object(quest_module, "ZH_QUEST", self.zh),
            mock.patch.object(quest_module, "BACKUP_ROOT", self.backups),
            mock.patch.object(quest_module, "SCRIPT_ROOTS", self.scripts),
            mock.patch.object(quest_module, "_npc_names", return_value={"2100": "莎丽", "2101": "希娜"}),
        ]
        for patcher in self.patches:
            patcher.start()
        for cached in (quest_module._catalog, quest_module._map_metadata, quest_module._npc_map_ids,
                       quest_module._npc_locations, quest_module._npc_map_details):
            cached.cache_clear()
        return self

    def __exit__(self, exc_type, exc, traceback):
        for cached in (quest_module._catalog, quest_module._map_metadata, quest_module._npc_map_ids,
                       quest_module._npc_locations, quest_module._npc_map_details):
            cached.cache_clear()
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def runtime_paths(self):
        for name in quest_module.QUEST_FILES:
            yield self.client / f"{name}.img"
            yield self.server / f"{name}.img.xml"
            yield self.zh / f"{name}.img.xml"

    def install_signed_quest(self, quest_id: str) -> str:
        client_id = str(int(quest_id) + 65536)
        for name in quest_module.QUEST_FILES:
            source = ET.parse(self.server / f"{name}.img.xml").getroot().find("./imgdir[@name='1000']")
            self.assert_source(source, name)
            server_node = copy.deepcopy(source)
            server_node.set("name", quest_id)
            for base in (self.server, self.zh):
                path = base / f"{name}.img.xml"
                path.write_bytes(quest_module._replace_xml_record(path.read_bytes(), quest_id, server_node))
            client_node = copy.deepcopy(source)
            client_node.set("name", client_id)
            path = self.client / f"{name}.img"
            path.write_bytes(quest_module._replace_img_record(path.read_bytes(), client_id, client_node))
        return client_id

    @staticmethod
    def assert_source(source, name: str) -> None:
        if source is None:
            raise AssertionError(f"missing source quest node for {name}")


class QuestManagerTests(unittest.TestCase):
    def test_negative_quest_id_is_valid(self):
        self.assertEqual(_validate_id("-31436", "任务 ID"), "-31436")

    def test_seven_digit_item_icon_uses_significant_category_digit(self):
        icon = _item_icon(4031003)
        self.assertIsNotNone(icon)
        self.assertGreater(icon.width, 1)
        self.assertGreater(icon.height, 1)

    def test_pet_icon_uses_standalone_img(self):
        icon = _item_icon(5000411)
        self.assertIsNotNone(icon)
        self.assertGreater(icon.width, 1)
        self.assertGreater(icon.height, 1)

    def test_npc_preview_uses_padded_client_img(self):
        preview = _npc_preview(2101)
        self.assertIsNotNone(preview)
        self.assertGreater(preview.width, 1)
        self.assertGreater(preview.height, 1)

    def test_mob_preview_uses_padded_client_img(self):
        preview = _mob_preview(100100)
        self.assertIsNotNone(preview)
        self.assertGreater(preview.width, 1)
        self.assertGreater(preview.height, 1)

    def test_npc_map_details_include_map_name_and_id(self):
        maps = _npc_map_details().get("9010010", [])
        self.assertTrue(maps)
        self.assertTrue(all(row["id"].isdigit() for row in maps))
        self.assertTrue(any(row["name"] != "(未知地图)" for row in maps))

    def test_item_drop_audit_distinguishes_current_other_and_missing(self):
        output = "\n".join((
            "mob\t100100\t4030001\t1\t1\t1000\t500000",
            "mob\t100101\t4030002\t1\t2\t2000\t250000",
            "mob\t8641000\t4030004\t1\t1\t34102\t500000",
        ))
        completed = mock.Mock(stdout=output)
        with mock.patch.object(quest_module, "_database_settings", return_value={
            "host": "localhost", "port": 3306, "database": "beidou", "username": "root", "password": "root",
        }), mock.patch.object(quest_module.shutil, "which", return_value="/usr/bin/mysql"), \
                mock.patch.object(quest_module.subprocess, "run", return_value=completed), \
                mock.patch.object(quest_module, "_mob_names", return_value={"100100": "蜗牛", "100101": "蓝蜗牛"}):
            audit = _item_drop_audit([4030001, 4030002, 4030003, 4030004], "1000")
            signed = _item_drop_audit([4030004], "-31434")
        self.assertTrue(audit["available"])
        self.assertEqual(audit["items"]["4030001"]["status"], "available")
        self.assertEqual(audit["items"]["4030001"]["drops"][0]["dropperName"], "蜗牛")
        self.assertEqual(audit["items"]["4030002"]["status"], "otherQuest")
        self.assertEqual(audit["items"]["4030003"]["status"], "missing")
        self.assertEqual(signed["items"]["4030004"]["status"], "available")
        self.assertEqual(signed["items"]["4030004"]["drops"][0]["questId"], -31434)
        self.assertEqual(signed["items"]["4030004"]["drops"][0]["databaseQuestId"], 34102)

    def test_xml_record_replacement_preserves_siblings(self):
        source = b'''<?xml version="1.0" encoding="UTF-8"?>\n<imgdir name="QuestInfo.img">\n  <imgdir name="1000"><string name="name" value="before" /></imgdir>\n  <imgdir name="2000"><int name="value" value="7" /></imgdir>\n</imgdir>\n'''
        node = ET.fromstring('<imgdir name="1000"><string name="name" value="after" /></imgdir>')
        changed = _replace_xml_record(source, "1000", node)
        self.assertIn(b'value="after"', changed)
        self.assertIn(b'<imgdir name="2000"><int name="value" value="7" /></imgdir>', changed)
        self.assertEqual(changed, _replace_xml_record(changed, "1000", ET.fromstring(quest_module._node_fragment(node))))

    def test_xml_property_replacement_preserves_img_sibling_record(self):
        original = sample_img()
        tail = record(original, "2000")
        tail_bytes = original[tail.start:tail.end]
        node = ET.fromstring('<imgdir name="1000"><string name="name" value="after and longer" /></imgdir>')
        changed = replace_img_record(original, ("1000",), _property_from_xml(node), region="GMS").data
        new_tail = record(changed, "2000")
        self.assertEqual(tail_bytes, changed[new_tail.start:new_tail.end])

    def test_signed_quest_save_and_delete_use_unsigned_client_record(self):
        with TemporaryQuestWorkspace() as workspace:
            quest_id = "-27835"
            client_id = workspace.install_signed_quest(quest_id)
            client = quest_module.app.test_client()
            unchanged_records = {}
            for path in workspace.client.glob("*.img"):
                data = path.read_bytes()
                unchanged_records[path] = {
                    name: data[record(data, name).start:record(data, name).end]
                    for name in ("1000", "2000")
                }
            body = {
                "questId": quest_id, "name": "signed update", "startNpc": 2101,
                "endNpc": 2100, "items": {},
            }
            saved = client.post("/api/quest/save", json=body)
            self.assertEqual(saved.status_code, 200, saved.get_json())
            self.assertEqual(saved.get_json()["quest"]["name"], "signed update")
            first_save = {path: path.read_bytes() for path in workspace.runtime_paths()}
            saved_again = client.post("/api/quest/save", json=body)
            self.assertEqual(saved_again.status_code, 200, saved_again.get_json())
            self.assertEqual(first_save, {path: path.read_bytes() for path in workspace.runtime_paths()})
            for name in quest_module.QUEST_FILES:
                path = workspace.client / f"{name}.img"
                data = path.read_bytes()
                names = {row.name for row in scan_img(data, region="GMS").root.records}
                self.assertIn(client_id, names)
                self.assertNotIn(quest_id, names)
                for unchanged_name, unchanged_bytes in unchanged_records[path].items():
                    current = record(data, unchanged_name)
                    self.assertEqual(unchanged_bytes, data[current.start:current.end])

            deleted = client.post("/api/quest/delete", json={"questId": quest_id, "confirm": quest_id})
            self.assertEqual(deleted.status_code, 200, deleted.get_json())
            for name in quest_module.QUEST_FILES:
                path = workspace.client / f"{name}.img"
                data = path.read_bytes()
                names = {row.name for row in scan_img(data, region="GMS").root.records}
                self.assertNotIn(client_id, names)
                self.assertIsNone(ET.parse(workspace.server / f"{name}.img.xml").getroot().find(f"./imgdir[@name='{quest_id}']"))
                for unchanged_name, unchanged_bytes in unchanged_records[path].items():
                    current = record(data, unchanged_name)
                    self.assertEqual(unchanged_bytes, data[current.start:current.end])

    def test_signed_quest_create_uses_unsigned_client_record(self):
        with TemporaryQuestWorkspace() as workspace:
            quest_id = "-27835"
            client_id = "37701"
            client = quest_module.app.test_client()
            created = client.post("/api/quest/create", json={
                "questId": quest_id, "name": "signed quest", "startNpc": 2101,
                "endNpc": 2100, "items": {},
            })
            self.assertEqual(created.status_code, 200, created.get_json())
            for name in quest_module.QUEST_FILES:
                names = {row.name for row in scan_img((workspace.client / f"{name}.img").read_bytes(), region="GMS").root.records}
                self.assertIn(client_id, names)
                self.assertNotIn(quest_id, names)
                self.assertIsNotNone(ET.parse(workspace.server / f"{name}.img.xml").getroot().find(f"./imgdir[@name='{quest_id}']"))

    def test_signed_and_unsigned_client_records_are_rejected_as_collision(self):
        quest_id = "-27835"
        node = ET.fromstring(f'<imgdir name="{quest_id}"><string name="name" value="collision" /></imgdir>')
        data = quest_module._replace_img_record(sample_img(), quest_id, node)
        data = mutate_img(data, "add", (), name=quest_id, kind="SubProperty", region="GMS").data
        data = replace_img_record(data, (quest_id,), _property_from_xml(node), region="GMS").data
        with self.assertRaisesRegex(ValueError, "客户端任务 ID 冲突"):
            quest_module._replace_img_record(data, quest_id, node)

    def test_basic_save_keeps_unknown_fields(self):
        nodes = {
            "QuestInfo": ET.fromstring('<imgdir name="1000"><int name="custom" value="9" /></imgdir>'),
            "Check": ET.fromstring('<imgdir name="1000"><imgdir name="0"><int name="customCheck" value="3" /><imgdir name="quest"><imgdir name="0"><int name="id" value="1000" /><int name="state" value="2" /></imgdir></imgdir><imgdir name="mob"><imgdir name="0"><int name="count" value="5" /><int name="id" value="100100" /></imgdir></imgdir><int name="customAfter" value="5" /></imgdir><imgdir name="1" /></imgdir>'),
            "Act": ET.fromstring('<imgdir name="1000"><imgdir name="0" /><imgdir name="1"><int name="customAct" value="4" /></imgdir></imgdir>'),
            "Say": ET.fromstring('<imgdir name="1000"><imgdir name="0" /><imgdir name="1" /></imgdir>'),
        }
        result = _basic_payload(nodes, {"questId": "1000", "name": "updated", "items": {},
                                        "requirements": [{"id": "2000", "state": 1}],
                                        "mobs": {"checkStart": [{"id": "100101", "count": 8}]}})
        self.assertEqual(result["QuestInfo"].find("./int[@name='custom']").get("value"), "9")
        self.assertEqual(result["Check"].find("./imgdir/int[@name='customCheck']").get("value"), "3")
        self.assertEqual(result["Check"].find("./imgdir/imgdir[@name='quest']/imgdir/int[@name='id']").get("value"), "2000")
        self.assertEqual(result["Check"].find("./imgdir/imgdir[@name='quest']/imgdir/int[@name='state']").get("value"), "1")
        self.assertEqual(result["Check"].find("./imgdir/imgdir[@name='mob']/imgdir/int[@name='id']").get("value"), "100101")
        self.assertEqual(result["Check"].find("./imgdir/imgdir[@name='mob']/imgdir/int[@name='count']").get("value"), "8")
        self.assertEqual([node.get("name") for node in result["Check"].find("./imgdir")],
                         ["customCheck", "quest", "mob", "customAfter"])
        self.assertEqual(result["Act"].find("./imgdir[@name='1']/int[@name='customAct']").get("value"), "4")

    def test_complete_quest_and_script_workflow_uses_incremental_files(self):
        with TemporaryQuestWorkspace() as workspace:
            client = quest_module.app.test_client()
            original_siblings = {
                path: path.read_bytes()[record(path.read_bytes(), "2000").start:record(path.read_bytes(), "2000").end]
                for path in workspace.client.glob("*.img")
            }
            xml_siblings = {
                path: quest_module._node_fragment(ET.parse(path).getroot().find("./imgdir[@name='2000']"))
                for base in (workspace.server, workspace.zh) for path in base.glob("*.img.xml")
            }
            body = {
                "questId": "1000", "name": "after", "area": 20,
                "startNpc": 2101, "endNpc": 2100, "levelMin": 12,
                "contentStart": "start", "contentProgress": "progress", "contentComplete": "done",
                "dialogStart": "hello", "dialogComplete": "thanks",
                "items": {"checkStart": [{"values": {"id": 4031003, "count": 2}}]},
                "mobs": {"checkStart": [], "checkComplete": [{"id": "100100", "count": 10}]},
            }
            first = client.post("/api/quest/save", json=body)
            self.assertEqual(first.status_code, 200, first.get_json())
            first_hashes = {path: path.read_bytes() for path in workspace.runtime_paths()}
            second = client.post("/api/quest/save", json=body)
            self.assertEqual(second.status_code, 200, second.get_json())
            self.assertEqual(first_hashes, {path: path.read_bytes() for path in workspace.runtime_paths()})
            self.assertEqual(second.get_json()["quest"]["items"]["checkStart"][0]["values"]["id"], 4031003)
            self.assertEqual(second.get_json()["quest"]["mobs"]["checkComplete"][0]["id"], "100100")
            self.assertEqual(second.get_json()["quest"]["mobs"]["checkComplete"][0]["count"], 10)

            raw = second.get_json()["quest"]["raw"]
            raw_info = ET.fromstring(raw["QuestInfo"])
            raw_info.find("./string[@name='name']").set("value", "raw after")
            raw["QuestInfo"] = ET.tostring(raw_info, encoding="unicode")
            raw_saved = client.post("/api/quest/raw", json={"questId": "1000", "raw": raw})
            self.assertEqual(raw_saved.status_code, 200, raw_saved.get_json())
            self.assertEqual(raw_saved.get_json()["quest"]["name"], "raw after")
            before_invalid_raw = {path: path.read_bytes() for path in workspace.runtime_paths()}
            invalid_raw = dict(raw)
            invalid_raw["QuestInfo"] = invalid_raw["QuestInfo"].replace('name="1000"', 'name="9999"', 1)
            rejected_raw = client.post("/api/quest/raw", json={"questId": "1000", "raw": invalid_raw})
            self.assertEqual(rejected_raw.status_code, 400)
            self.assertEqual(before_invalid_raw, {path: path.read_bytes() for path in workspace.runtime_paths()})

            for path, sibling in original_siblings.items():
                changed = path.read_bytes()
                changed_record = record(changed, "2000")
                self.assertEqual(sibling, changed[changed_record.start:changed_record.end])
            for path, sibling in xml_siblings.items():
                current = ET.parse(path).getroot().find("./imgdir[@name='2000']")
                self.assertEqual(sibling, quest_module._node_fragment(current))

            existing_img_records = {}
            for path in workspace.client.glob("*.img"):
                data = path.read_bytes()
                existing_img_records[path] = {name: data[record(data, name).start:record(data, name).end] for name in ("1000", "2000")}
            existing_xml_records = {
                path: {name: quest_module._node_fragment(ET.parse(path).getroot().find(f"./imgdir[@name='{name}']")) for name in ("1000", "2000")}
                for base in (workspace.server, workspace.zh) for path in base.glob("*.img.xml")
            }
            created = client.post("/api/quest/create", json={
                "questId": "3000", "name": "new quest", "startNpc": 2101, "endNpc": 2100, "items": {},
            })
            self.assertEqual(created.status_code, 200, created.get_json())
            created_quest = created.get_json()["quest"]
            self.assertEqual(created_quest["questScript"]["id"], "3000")
            self.assertEqual([row["id"] for row in created_quest["npcScripts"]], ["2101", "2100"])
            for name in quest_module.QUEST_FILES:
                path = workspace.client / f"{name}.img"
                data = path.read_bytes()
                self.assertIsNotNone(record(data, "3000"))
                for old_name, old_bytes in existing_img_records[path].items():
                    current = record(data, old_name)
                    self.assertEqual(old_bytes, data[current.start:current.end])
                for base in (workspace.server, workspace.zh):
                    path = base / f"{name}.img.xml"
                    root = ET.parse(path).getroot()
                    self.assertIsNotNone(root.find("./imgdir[@name='3000']"))
                    for old_name, old_fragment in existing_xml_records[path].items():
                        self.assertEqual(old_fragment, quest_module._node_fragment(root.find(f"./imgdir[@name='{old_name}']")))

            script_body = {"kind": "quest", "id": "3000", "locale": "main", "content": "function start() {}\n"}
            saved_script = client.post("/api/script", json=script_body)
            self.assertEqual(saved_script.status_code, 200, saved_script.get_json())
            script_path = workspace.scripts["main"] / "quest" / "3000.js"
            self.assertEqual(script_path.read_text(), script_body["content"])
            edited_script = client.post("/api/script", json={**script_body, "content": "function end() {}\n"})
            self.assertEqual(edited_script.status_code, 200, edited_script.get_json())
            self.assertEqual(script_path.read_text(), "function end() {}\n")
            npc_script_body = {"kind": "npc", "id": "2101", "locale": "zh", "content": "function action() {}\n"}
            saved_npc_script = client.post("/api/script", json=npc_script_body)
            self.assertEqual(saved_npc_script.status_code, 200, saved_npc_script.get_json())
            npc_script_path = workspace.scripts["zh"] / "npc" / "2101.js"
            self.assertEqual(npc_script_path.read_text(), npc_script_body["content"])

            before_rejected_delete = {path: path.read_bytes() for path in workspace.runtime_paths()}
            rejected_delete = client.post("/api/quest/delete", json={"questId": "3000", "confirm": "wrong"})
            self.assertEqual(rejected_delete.status_code, 400)
            self.assertEqual(before_rejected_delete, {path: path.read_bytes() for path in workspace.runtime_paths()})
            deleted = client.post("/api/quest/delete", json={"questId": "3000", "confirm": "3000"})
            self.assertEqual(deleted.status_code, 200, deleted.get_json())
            self.assertTrue(script_path.is_file())
            self.assertTrue(npc_script_path.is_file())
            for name in quest_module.QUEST_FILES:
                path = workspace.client / f"{name}.img"
                data = path.read_bytes()
                self.assertFalse(any(row.name == "3000" for row in scan_img(data, region="GMS").root.records))
                for old_name, old_bytes in existing_img_records[path].items():
                    current = record(data, old_name)
                    self.assertEqual(old_bytes, data[current.start:current.end])
                for base in (workspace.server, workspace.zh):
                    path = base / f"{name}.img.xml"
                    root = ET.parse(path).getroot()
                    self.assertIsNone(root.find("./imgdir[@name='3000']"))
                    for old_name, old_fragment in existing_xml_records[path].items():
                        self.assertEqual(old_fragment, quest_module._node_fragment(root.find(f"./imgdir[@name='{old_name}']")))

            rejected = client.post("/api/script", json={**script_body, "delete": True, "confirm": "wrong"})
            self.assertEqual(rejected.status_code, 400)
            self.assertTrue(script_path.is_file())
            removed = client.post("/api/script", json={**script_body, "delete": True, "confirm": "3000"})
            self.assertEqual(removed.status_code, 200, removed.get_json())
            self.assertFalse(script_path.exists())


if __name__ == "__main__":
    unittest.main()
