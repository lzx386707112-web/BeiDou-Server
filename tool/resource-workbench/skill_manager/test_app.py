from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skill_manager import app as skill_module
from PIL import Image
from wzpy import WzCanvasProperty, WzIntProperty, WzKey, WzStringProperty, WzSubProperty
from wzpy.canvas import encode_canvas_payload
from wzpy.incremental_img import scan_img
from wzpy.reader import WzBinaryReader
from wzpy.writer import _encode_property_list, encode_image_type_string


def encode_img(nodes, region: str) -> bytes:
    reader = WzBinaryReader(io.BytesIO(), WzKey.for_region(region))
    return encode_image_type_string(reader, "Property") + b"\x00\x00" + _encode_property_list(tuple(nodes), reader)


def make_icon(name: str, parent, size: int, color: tuple[int, int, int, int], outlink: str | None = None) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width = size
    canvas.height = size
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        Image.new("RGBA", (size, size), color), 1, size, size, key=WzKey.for_region("BMS"),
    )
    if outlink:
        canvas.add(WzStringProperty("_outlink", outlink, canvas))
    return canvas


def skill_book(*skills: tuple[str, int], icons: dict[str, WzCanvasProperty] | None = None, extra_ints: dict[str, list[tuple[str, int]]] | None = None) -> list[WzSubProperty]:
    root = WzSubProperty("skill")
    extra_ints = extra_ints or {}
    for skill_id, damage in skills:
        skill = WzSubProperty(skill_id, root)
        root.add(skill)
        levels = WzSubProperty("level", skill)
        skill.add(levels)
        level = WzSubProperty("1", levels)
        levels.add(level)
        level.add(WzIntProperty("damage", damage, level))
        for name, value in extra_ints.get(skill_id, []):
            skill.add(WzIntProperty(name, value, skill))
        if icons and skill_id in icons:
            icon = icons[skill_id]
            icon.parent = skill
            skill.add(icon)
    return [root]


def string_img(*rows: tuple[str, str]) -> list[WzSubProperty]:
    nodes = []
    for skill_id, name in rows:
        node = WzSubProperty(skill_id)
        node.add(WzStringProperty("name", name, node))
        nodes.append(node)
    return nodes


def record_bytes(data: bytes, name: str, region: str = "GMS") -> bytes:
    record = next(row for row in scan_img(data, region=region).root.records if row.name == name)
    return data[record.start:record.end]


class TemporarySkillWorkspace:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = self.root / "clien" / "Data" / "Skill"
        self.server = self.root / "gms-server" / "wz" / "Skill.wz"
        self.tms = self.root / "TMS" / "Data" / "Skill"
        self.canvas = self.tms / "_Canvas"
        self.packs = self.root / "TMS" / "Packs"
        self.ms_cache = self.root / "ms-extract"
        self.zh_string = self.root / "gms-server" / "wz-zh-CN" / "String.wz"
        self.server_string = self.root / "gms-server" / "wz" / "String.wz"
        self.tms_string = self.tms.parent / "String"
        for path in (self.client, self.server, self.canvas, self.packs, self.ms_cache, self.zh_string, self.server_string, self.tms_string):
            path.mkdir(parents=True, exist_ok=True)
        (self.client / "112.img").write_bytes(encode_img(skill_book(("1121008", 135), ("1121010", 11)), "GMS"))
        (self.tms / "112.img").write_bytes(encode_img(skill_book(("1121008", 280), ("1120010", 50), extra_ints={"1121008": [("cooltime", 5000)]}), "BMS"))
        linked = make_icon("icon", None, 1, (0, 0, 0, 0), "Skill/_Canvas/112.img/skill/1120010/icon")
        (self.ms_cache / "Skill_112.img").write_bytes(encode_img(
            skill_book(("1121008", 280), ("1120010", 50), icons={"1120010": linked}, extra_ints={"1121008": [("cooltime", 5000)]}),
            "BMS",
        ))
        real = make_icon("icon", None, 4, (255, 0, 0, 255))
        (self.canvas / "112.img").write_bytes(encode_img(skill_book(("1120010", 50), icons={"1120010": real}), "BMS"))
        (self.canvas / "999.img").write_bytes(encode_img(skill_book(("9990001", 1)), "BMS"))
        (self.ms_cache / "Skill_40001.img").write_bytes(encode_img(skill_book(("400011088", 635)), "BMS"))
        (self.tms_string / "Skill.img").write_bytes(encode_img(string_img(("1120010", "鬥氣爆發"), ("1121008", "狂暴攻擊")), "BMS"))
        (self.server / "112.img.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<imgdir name="112.img"><imgdir name="skill">'
            '<imgdir name="1121008"><imgdir name="level"><imgdir name="1"><int name="damage" value="135"/></imgdir></imgdir></imgdir>'
            '<imgdir name="1121010"><imgdir name="level"><imgdir name="1"><int name="damage" value="11"/></imgdir></imgdir></imgdir>'
            "</imgdir></imgdir>\n",
            encoding="utf-8",
        )
        string_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<imgdir name="Skill.img">'
            '<imgdir name="112"><string name="bookName" value="英雄"/></imgdir>'
            '<imgdir name="1121008"><string name="name" value="无双剑舞"/></imgdir>'
            '<imgdir name="400011088"><string name="name" value="灵魂蚀日"/></imgdir>'
            "</imgdir>\n"
        )
        (self.zh_string / "Skill.img.xml").write_text(string_xml, encoding="utf-8")
        replacements = {
            "ROOT": self.root,
            "TMS_DATA": self.tms.parent,
            "MS_PACKS": self.packs,
            "MS_PROBE": self.root / "missing-MSProbe.dll",
            "MS_CACHE_ROOT": self.ms_cache,
            "CLIENT_SKILL": self.client,
            "SERVER_SKILL": self.server,
            "ZH_STRING": self.zh_string / "Skill.img.xml",
            "SERVER_STRING": self.server_string / "Skill.img.xml",
            "BACKUP_ROOT": self.root / "backups",
        }
        self.patches = [mock.patch.object(skill_module, name, value) for name, value in replacements.items()]
        self.patches.append(mock.patch.object(skill_module, "ms_skill_index", return_value={
            "40001": self.packs / "Skill_00005.ms",
            "6100": self.packs / "Skill_00005.ms",
        }))
        self.patches.append(mock.patch.object(
            skill_module, "extract_ms_skill",
            side_effect=lambda book: (self.ms_cache / f"Skill_{book}.img", self.packs / "Skill_00005.ms")
            if (self.ms_cache / f"Skill_{book}.img").is_file() else None,
        ))
        for patcher in self.patches:
            patcher.start()
        skill_module._string_catalog.cache_clear()
        skill_module._tms_string_catalog.cache_clear()
        skill_module._cached_skill_ids.cache_clear()
        skill_module._cached_image.cache_clear()
        skill_module._ms_skill_index_cached.cache_clear()
        return self

    def __exit__(self, exc_type, exc, traceback):
        skill_module._string_catalog.cache_clear()
        skill_module._tms_string_catalog.cache_clear()
        skill_module._cached_skill_ids.cache_clear()
        skill_module._cached_image.cache_clear()
        skill_module._ms_skill_index_cached.cache_clear()
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()


class SkillManagerTests(unittest.TestCase):
    def test_jobs_and_skills_include_local_tms_and_ms_books(self):
        with TemporarySkillWorkspace():
            client = skill_module.app.test_client()
            jobs = client.get("/api/jobs").get_json()
            by_id = {row["id"]: row for row in jobs["jobs"]}
            self.assertEqual(by_id["112"]["name"], "英雄")
            self.assertTrue(by_id["112"]["local"])
            self.assertTrue(by_id["112"]["tms"])
            self.assertTrue(by_id["40001"]["ms"])
            skills = client.get("/api/skills?job=112").get_json()
            ids = [row["id"] for row in skills["items"]]
            self.assertEqual(ids, ["1120010", "1121008", "1121010"])
            self.assertEqual(next(row for row in skills["items"] if row["id"] == "1121008")["name"], "无双剑舞")
            tms_only = next(row for row in skills["items"] if row["id"] == "1120010")
            self.assertEqual(tms_only["name"], "鬥氣爆發")
            self.assertEqual(tms_only["status"], "missing")
            self.assertEqual(tms_only["iconSource"], "ms")
            icon = client.get("/api/skill/112/1120010/icon?source=ms")
            self.assertEqual(icon.status_code, 200, icon.get_data()[:80])
            self.assertEqual(Image.open(io.BytesIO(icon.get_data())).size, (4, 4))
            self.assertEqual(next(row for row in skills["items"] if row["id"] == "1121008")["status"], "both")
            self.assertEqual(next(row for row in skills["items"] if row["id"] == "1121010")["status"], "local")
            local_only = client.get("/api/skills?job=112&side=local").get_json()
            self.assertEqual([row["id"] for row in local_only["items"]], ["1121008", "1121010"])
            tms_only = client.get("/api/skills?job=112&side=tms").get_json()
            self.assertEqual([row["id"] for row in tms_only["items"]], ["1120010", "1121008"])
            local_jobs = {row["id"] for row in client.get("/api/jobs?side=local").get_json()["jobs"]}
            tms_jobs = {row["id"] for row in client.get("/api/jobs?side=tms").get_json()["jobs"]}
            self.assertIn("112", local_jobs)
            self.assertNotIn("40001", local_jobs)
            self.assertIn("40001", tms_jobs)
            self.assertIn("6100", tms_jobs)
            self.assertNotIn("999", tms_jobs)
            self.assertEqual(next(row["group"] for row in client.get("/api/jobs?side=tms").get_json()["jobs"] if row["id"] == "6100"), "超新星")
            ms_detail = client.get("/api/skill/40001/400011088").get_json()
            self.assertEqual(ms_detail["skill"]["name"], "灵魂蚀日")
            self.assertIsNone(ms_detail["local"])
            self.assertEqual(ms_detail["tmsSource"], "ms")
            self.assertEqual(next(row for row in ms_detail["tms"]["nodes"] if row["path"] == "level/1/damage")["value"], 635)

    def test_compare_and_incremental_node_edit_keep_sibling_skill_bytes(self):
        with TemporarySkillWorkspace() as workspace:
            client = skill_module.app.test_client()
            detail = client.get("/api/skill/112/1121008").get_json()
            self.assertEqual(detail["skill"]["name"], "无双剑舞")
            changed = next(row for row in detail["diff"] if row["path"] == "level/1/damage")
            self.assertEqual(changed["status"], "changed")
            self.assertEqual(changed["local"]["value"], 135)
            self.assertEqual(changed["tms"]["value"], 280)
            client_path = workspace.client / "112.img"
            before_sibling = record_bytes(client_path.read_bytes(), "skill")
            # Keep a copy of the untouched skill by editing a scalar inside 1121008 only.
            before = client_path.read_bytes()
            edited = client.post("/api/skill/node", json={
                "book": "112", "id": "1121008", "operation": "edit",
                "path": "level/1/damage", "values": {"value": 999},
            })
            self.assertEqual(edited.status_code, 200, edited.get_json())
            self.assertEqual(next(row for row in edited.get_json()["item"]["nodes"] if row["path"] == "level/1/damage")["value"], 999)
            xml = (workspace.server / "112.img.xml").read_text(encoding="utf-8")
            self.assertIn('<int name="damage" value="999"/>', xml)
            self.assertIn('<imgdir name="1121010">', xml)
            after = client_path.read_bytes()
            self.assertNotEqual(before, after)
            verified = skill_module._load_image(client_path, "GMS")
            self.assertFalse(verified.truncated)
            self.assertFalse(verified.parse_warnings)
            sibling = verified.root.get("skill/1121010/level/1/damage")
            self.assertEqual(int(sibling.value), 11)
            self.assertNotEqual(before_sibling, record_bytes(after, "skill"))
            repeated = client.post("/api/skill/node", json={
                "book": "112", "id": "1121008", "operation": "edit",
                "path": "level/1/damage", "values": {"value": 999},
            })
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(client_path.read_bytes(), after)
            copied = client.post("/api/skill/node", json={
                "book": "112", "id": "1121008", "operation": "copyFromTms",
                "path": "cooltime", "source": "tms", "recursive": False,
            })
            self.assertEqual(copied.status_code, 200, copied.get_json())
            self.assertEqual(copied.get_json()["copied"], 1)
            self.assertEqual(next(row for row in copied.get_json()["item"]["nodes"] if row["path"] == "cooltime")["value"], 5000)
            applied = client.post("/api/skill/node", json={
                "book": "112", "id": "1121008", "operation": "copyFromTms",
                "path": "level/1/damage", "source": "tms", "recursive": False,
            })
            self.assertEqual(applied.status_code, 200, applied.get_json())
            self.assertEqual(next(row for row in applied.get_json()["item"]["nodes"] if row["path"] == "level/1/damage")["value"], 280)
            xml = (workspace.server / "112.img.xml").read_text(encoding="utf-8")
            self.assertIn('<int name="cooltime" value="5000"/>', xml)
            self.assertIn('<int name="damage" value="280"/>', xml)
            sibling = skill_module._load_image(client_path, "GMS").root.get("skill/1121010/level/1/damage")
            self.assertEqual(int(sibling.value), 11)
            cross = client.post("/api/skill/node", json={
                "book": "112", "id": "1121010", "operation": "copyFromTms",
                "sourceBook": "112", "sourceId": "1121008", "source": "tms",
                "paths": ["cooltime", "level/1/damage"], "recursive": False,
            })
            self.assertEqual(cross.status_code, 200, cross.get_json())
            copied_nodes = {row["path"]: row["value"] for row in cross.get_json()["item"]["nodes"]}
            self.assertEqual(copied_nodes["cooltime"], 5000)
            self.assertEqual(copied_nodes["level/1/damage"], 280)
            original = skill_module._load_image(client_path, "GMS").root.get("skill/1121008/level/1/damage")
            self.assertEqual(int(original.value), 280)


if __name__ == "__main__":
    unittest.main()
