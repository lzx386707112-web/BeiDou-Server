#!/usr/bin/env python3
"""Focused safety tests for Map & Mob Workbench."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from map_mob import app as workbench


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

    def test_add_cloned_node_inserts_inside_inline_empty_imgdir(self) -> None:
        source = b'<imgdir name="1.img">\n  <imgdir name="1"><imgdir name="obj"></imgdir></imgdir>\n</imgdir>\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "1.img.xml"
            path.write_bytes(source)
            child = workbench.WzSubProperty("0")
            child.add(workbench.WzIntProperty("x", 12))
            workbench.xml_add_cloned_node(path, "1/obj", child, dry_run=False)
            workbench.ET.parse(path)
            nodes, _ = workbench.flatten_xml(path)
            self.assertEqual(nodes["1/obj/0/x"]["value"], 12)
            self.assertTrue(path.read_bytes().startswith(b'<imgdir name="1.img">'))


class ImgPatchTests(unittest.TestCase):
    def test_empty_gms_img_is_parseable_and_has_no_nodes(self) -> None:
        data = workbench.empty_gms_img_bytes()
        image = workbench._verified_img_from_bytes(Path("empty.img"), data)
        self.assertEqual(image.root.children(), [])
        self.assertEqual(data, workbench.empty_gms_img_bytes())

    def test_missing_main_source_is_reported_without_flatten_failure(self) -> None:
        missing = workbench._ROOT / "clien/Data/Map/Map/Map9/__missing_workbench_test__.img"
        self.assertFalse(missing.exists())
        nodes, info = workbench.flatten_optional_source(missing)
        self.assertEqual(nodes, {})
        self.assertEqual(info["format"], "img")
        self.assertFalse(info["exists"])

    def test_resource_status_is_attached_to_the_referencing_life_node(self) -> None:
        rows = [{"path": "life/8"}, {"path": "life/8/id"}]
        resources = [{
            "kind": "npc", "name": "9000123", "status": "missingFile",
            "clientPath": "clien/Data/Npc/9000123.img", "nodes": ["life/8"],
            "autoCopy": True, "contract": {"issues": ["客户端 IMG 缺失"]},
        }]
        workbench.attach_resource_statuses(rows, resources)
        self.assertEqual(rows[0]["resources"][0]["name"], "9000123")
        self.assertEqual(rows[0]["resources"][0]["issues"], ["客户端 IMG 缺失"])
        self.assertNotIn("resources", rows[1])

    def test_reverse_city_marks_only_missing_branch_and_accepts_projected_connect_rope(self) -> None:
        left = workbench._ROOT / "clien/Data/Map/Map/Map4/450014200.img"
        right = workbench._TMS_DATA / "Map/Map/Map4/450014200.img"
        if not left.is_file() or not right.is_file():
            self.skipTest("Reverse City map samples are unavailable")
        resources = workbench.audit_map_resources(left, right)
        by_key = {(item["kind"], item["name"]): item for item in resources}
        reverse_city = by_key[("obj", "ReverseCity")]
        connect = by_key[("obj", "connect")]
        self.assertEqual(reverse_city["status"], "missingCanvas")
        self.assertEqual(reverse_city["issueNodes"], ["3/obj/24"])
        self.assertIn("mtower/ani/3/0", reverse_city["contract"]["issues"][0])
        self.assertEqual(connect["status"], "ready")
        self.assertTrue(connect["projected"])
        rows = [{"path": "3/obj/10"}, {"path": "3/obj/24"}, {"path": "7/obj/3"}]
        workbench.attach_resource_statuses(rows, resources)
        self.assertNotIn("resources", rows[0])
        self.assertEqual(rows[1]["resources"][0]["name"], "ReverseCity")
        self.assertEqual(rows[2]["resources"][0]["status"], "ready")

    def test_mob_default_path_prefers_tms_canvas_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_tms_data = workbench._TMS_DATA
            workbench._TMS_DATA = Path(directory)
            canvas = workbench._TMS_DATA / "Mob/_Canvas/8642050.img"
            canvas.parent.mkdir(parents=True)
            canvas.write_bytes(b"test")
            try:
                _, right = workbench.default_paths("mob", "8642050")
            finally:
                workbench._TMS_DATA = original_tms_data
            self.assertEqual(right, canvas)

    def test_create_empty_main_creates_parseable_client_and_server_pair(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-create-test-", dir=workbench._HERE) as directory:
            client = Path(directory) / "999999999.img"
            server = Path(directory) / "999999999.img.xml"
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.create_empty_main_files(client)
            finally:
                workbench.server_xml_for_client = original_resolver
            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            self.assertEqual(image.root.children(), [])
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(set(server_nodes), {""})
            self.assertTrue(result["createdClient"])
            self.assertTrue(result["createdServer"])

    def test_client_paths_resolve_to_primary_server_xml(self) -> None:
        map_client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        mob_client = workbench._ROOT / "clien/Data/Mob/8641002.img"
        self.assertEqual(
            workbench.server_xml_for_client(map_client),
            workbench._ROOT / "gms-server/wz/Map.wz/Map/Map4/450002011.img.xml",
        )
        self.assertEqual(
            workbench.server_xml_for_client(mob_client),
            workbench._ROOT / "gms-server/wz/Mob.wz/8641002.img.xml",
        )

    def test_map_scalar_sync_dry_run_preflights_client_and_server_without_writes(self) -> None:
        client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        server = workbench._ROOT / "gms-server/wz/Map.wz/Map/Map4/450002011.img.xml"
        if not client.is_file() or not server.is_file():
            self.skipTest("repository map sync samples are unavailable")
        client_before = client.read_bytes()
        server_before = server.read_bytes()
        result = workbench.patch_with_server_sync(client, "info/swim", 0, dry_run=True, backup=False)
        self.assertEqual(client.read_bytes(), client_before)
        self.assertEqual(server.read_bytes(), server_before)
        self.assertEqual(result["clientPath"], "clien/Data/Map/Map/Map4/450002011.img")
        self.assertEqual(result["serverPath"], "gms-server/wz/Map.wz/Map/Map4/450002011.img.xml")
        self.assertIn("client", result)
        self.assertIn("server", result)

    def test_real_mob_scalar_dry_run_is_bounded(self) -> None:
        path = workbench._ROOT / "clien" / "Data" / "Mob" / "8641002.img"
        if not path.is_file():
            self.skipTest("repository sample Mob IMG is unavailable")
        before = path.read_bytes()
        result = workbench.patch_img(path, "info/level", 202, dry_run=True, backup=False)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(result["slots"][0]["length"], 5)

    def test_raw_record_add_delete_builds_swim_area_and_exactly_restores_img(self) -> None:
        source = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        if not source.is_file():
            self.skipTest("repository map IMG sample is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / source.name
            shutil.copy2(source, path)
            original = path.read_bytes()
            steps = (
                ("", "__swimArea_test__", "imgdir", None),
                ("__swimArea_test__", "swim01", "imgdir", None),
                ("__swimArea_test__/swim01", "x1", "int", -819),
                ("__swimArea_test__/swim01", "y1", "int", 206),
                ("__swimArea_test__/swim01", "x2", "int", 5000),
                ("__swimArea_test__/swim01", "y2", "int", 474),
            )
            for parent, name, node_type, value in steps:
                workbench.patch_img_add(
                    path, parent, name, node_type, value, dry_run=False, backup=False,
                )
            image = workbench._verified_img_from_bytes(path, path.read_bytes())
            self.assertEqual(image.root.get("__swimArea_test__/swim01/x1").value, -819)
            self.assertEqual(image.root.get("__swimArea_test__/swim01/y1").value, 206)
            self.assertEqual(image.root.get("__swimArea_test__/swim01/x2").value, 5000)
            self.assertEqual(image.root.get("__swimArea_test__/swim01/y2").value, 474)
            workbench.patch_img_delete(path, "__swimArea_test__", dry_run=False, backup=False)
            self.assertEqual(path.read_bytes(), original)

    def test_scalar_edit_replaces_record_when_compressed_length_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "length-change.img"
            path.write_bytes(workbench.empty_gms_img_bytes())
            steps = (
                ("", "swimArea", "imgdir", None),
                ("swimArea", "swim01", "imgdir", None),
                ("swimArea/swim01", "x1", "int", -819),
                ("swimArea/swim01", "y1", "int", 206),
                ("swimArea/swim01", "x2", "int", 5000),
                ("swimArea/swim01", "y2", "int", 474),
            )
            for parent, name, node_type, value in steps:
                workbench.patch_img_add(
                    path, parent, name, node_type, value, dry_run=False, backup=False,
                )
            before = path.read_bytes()
            before_image = workbench._verified_img_from_bytes(path, before)
            _, _, _, names, spans, _ = workbench.locate_img_records(
                before_image, before, ("swimArea", "swim01"),
            )
            sibling_records = {
                name: before[start:end]
                for name, (start, end) in zip(names, spans) if name != "x1"
            }

            result = workbench.patch_img(
                path, "swimArea/swim01/x1", -1, dry_run=False, backup=False,
            )

            after = path.read_bytes()
            after_image = workbench._verified_img_from_bytes(path, after)
            self.assertEqual(after_image.root.get("swimArea/swim01/x1").value, -1)
            _, _, _, new_names, new_spans, _ = workbench.locate_img_records(
                after_image, after, ("swimArea", "swim01"),
            )
            self.assertEqual(new_names, names)
            self.assertEqual(
                {
                    name: after[start:end]
                    for name, (start, end) in zip(new_names, new_spans) if name != "x1"
                },
                sibling_records,
            )
            self.assertEqual(result["mode"], "record-replacement")
            self.assertEqual(result["sizeDelta"], -4)

    def test_length_changing_scalar_edit_syncs_client_and_server(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / "length-change.img"
            server = Path(directory) / "length-change.img.xml"
            client.write_bytes(workbench.empty_gms_img_bytes())
            for parent, name, node_type, value in (
                ("", "swimArea", "imgdir", None),
                ("swimArea", "swim01", "imgdir", None),
                ("swimArea/swim01", "x1", "int", -819),
            ):
                workbench.patch_img_add(
                    client, parent, name, node_type, value, dry_run=False, backup=False,
                )
            server.write_bytes(b'''<?xml version="1.0" encoding="UTF-8"?>
<imgdir name="length-change.img">
  <imgdir name="swimArea">
    <imgdir name="swim01">
      <int name="x1" value="-819"/>
    </imgdir>
  </imgdir>
</imgdir>
''')
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.patch_with_server_sync(
                    client, "swimArea/swim01/x1", -1, dry_run=False, backup=False,
                )
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(image.root.get("swimArea/swim01/x1").value, -1)
            self.assertEqual(server_nodes["swimArea/swim01/x1"]["value"], -1)
            self.assertEqual(result["client"]["mode"], "record-replacement")

    def test_add_delete_server_sync_preflights_and_restores_both_files(self) -> None:
        client_source = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        server_source = workbench._ROOT / "gms-server/wz/Map.wz/Map/Map4/450002011.img.xml"
        if not client_source.is_file() or not server_source.is_file():
            self.skipTest("repository map sync samples are unavailable")
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / client_source.name
            server = Path(directory) / server_source.name
            shutil.copy2(client_source, client)
            shutil.copy2(server_source, server)
            client_original = client.read_bytes()
            server_original = server.read_bytes()
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                add_result = workbench.add_with_server_sync(
                    client, "", "__swimArea_sync_test__", "imgdir", None, dry_run=True, backup=False,
                )
                self.assertIn("client", add_result)
                self.assertIn("server", add_result)
                self.assertEqual(client.read_bytes(), client_original)
                self.assertEqual(server.read_bytes(), server_original)
                workbench.add_with_server_sync(
                    client, "", "__swimArea_sync_test__", "imgdir", None, dry_run=False, backup=False,
                )
                workbench.delete_with_server_sync(
                    client, "__swimArea_sync_test__", dry_run=False, backup=False,
                )
                self.assertEqual(client.read_bytes(), client_original)
                self.assertEqual(server.read_bytes(), server_original)
            finally:
                workbench.server_xml_for_client = original_resolver

    def test_copy_tms_subtree_adds_same_client_and_server_nodes(self) -> None:
        client_source = workbench._ROOT / "clien/Data/Map/Map/Map1/100040000.img"
        server_source = workbench._ROOT / "gms-server/wz/Map.wz/Map/Map1/100040000.img.xml"
        tms_source = workbench._TMS_DATA / "Map/Map/Map1/100040000.img"
        if not all(path.is_file() for path in (client_source, server_source, tms_source)):
            self.skipTest("repository and TMS map samples are unavailable")
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-test-", dir=workbench._HERE) as directory:
            client = Path(directory) / client_source.name
            server = Path(directory) / server_source.name
            shutil.copy2(client_source, client)
            shutil.copy2(server_source, server)
            original_resolver = workbench.server_xml_for_client
            original_atomic_write = workbench.atomic_write
            workbench.server_xml_for_client = lambda _path: server
            workbench.atomic_write = lambda path, data, *, backup=True: original_atomic_write(path, data, backup=False)
            try:
                result = workbench.copy_tms_node_with_server_sync(client, tms_source, "0/info/tS")
            finally:
                workbench.server_xml_for_client = original_resolver
                workbench.atomic_write = original_atomic_write
            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            self.assertEqual(image.root.get("0/info/tS").value, "grassySoil")
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(server_nodes["0/info/tS"]["value"], "grassySoil")
            self.assertEqual(result["path"], "0/info/tS")

    def test_copy_tms_leaf_creates_missing_main_files_and_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-missing-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "999999997.img"
            server = root / "999999997.img.xml"
            source = root / "source.img"
            source.write_bytes(workbench.empty_gms_img_bytes())
            for parent, name, node_type, value in (
                ("", "0", "imgdir", None),
                ("0", "info", "imgdir", None),
                ("0/info", "tS", "string", "grassySoil"),
            ):
                workbench.patch_img_add(
                    source, parent, name, node_type, value, dry_run=False, backup=False,
                )
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "0/info/tS")

                client_before = client.read_bytes()
                server_before = server.read_bytes()
                client_mtime = client.stat().st_mtime_ns
                server_mtime = server.stat().st_mtime_ns
                with self.assertRaisesRegex(ValueError, "同名节点已存在且不是空目录"):
                    workbench.copy_tms_node_with_server_sync(client, source, "0/info/tS")
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(image.root.get("0/info/tS").value, "grassySoil")
            self.assertEqual(server_nodes["0/info/tS"]["value"], "grassySoil")
            self.assertTrue(result["createdClient"])
            self.assertTrue(result["createdServer"])
            self.assertEqual(result["createdAncestors"], ["0", "0/info"])
            self.assertEqual(client.read_bytes(), client_before)
            self.assertEqual(server.read_bytes(), server_before)
            self.assertEqual(client.stat().st_mtime_ns, client_mtime)
            self.assertEqual(server.stat().st_mtime_ns, server_mtime)

    def test_copy_tms_leaf_populates_empty_main_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-empty-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "999999996.img"
            server = root / "999999996.img.xml"
            source = root / "source.img"
            client.write_bytes(workbench.empty_gms_img_bytes())
            workbench.patch_img_add(
                client, "", "life", "imgdir", None, dry_run=False, backup=False,
            )
            server.write_bytes(b'<imgdir name="999999996.img">\n  <imgdir name="life">\n  </imgdir>\n</imgdir>\n')
            source.write_bytes(workbench.empty_gms_img_bytes())
            for parent, name, node_type, value in (
                ("", "life", "imgdir", None),
                ("life", "0", "imgdir", None),
                ("life/0", "id", "string", "9001000"),
                ("life/0", "type", "string", "m"),
            ):
                workbench.patch_img_add(
                    source, parent, name, node_type, value, dry_run=False, backup=False,
                )
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "life")
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(image.root.get("life/0/id").value, "9001000")
            self.assertEqual(image.root.get("life/0/type").value, "m")
            self.assertEqual(server_nodes["life/0/id"]["value"], "9001000")
            self.assertFalse(result["createdClient"])
            self.assertFalse(result["createdServer"])
            self.assertEqual(result["createdAncestors"], [])

    def test_copy_rejects_known_modern_map_node(self) -> None:
        client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        tms_source = workbench._TMS_DATA / "Map/Map/Map4/450002011.img"
        if not client.is_file() or not tms_source.is_file():
            self.skipTest("repository and TMS map samples are unavailable")
        with self.assertRaisesRegex(ValueError, "不能直接复制"):
            workbench.copy_tms_node_with_server_sync(client, tms_source, "rapidStream")

    def test_copy_tms_top_level_node_projects_complete_compatible_subtree(self) -> None:
        tms_source = workbench._TMS_DATA / "Map/Map/Map4/450002011.img"
        if not tms_source.is_file():
            self.skipTest("TMS map sample is unavailable")
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-root-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "999999995.img"
            server = root / "999999995.img.xml"
            client.write_bytes(workbench.empty_gms_img_bytes())
            server.write_bytes(b'<imgdir name="999999995.img">\n</imgdir>\n')
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(client, tms_source, "4")
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertIsNotNone(image.root.get("4/obj/0/x"))
            self.assertIsNone(image.root.get("4/obj/0/dynamic"))
            self.assertIn("4/obj/0/dynamic", result["skippedPaths"])
            self.assertIn("4/obj/0/x", server_nodes)
            self.assertNotIn("4/obj/0/dynamic", server_nodes)

    def test_copy_tms_root_populates_empty_client_and_single_xml_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-file-root-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "999999994.img"
            server = root / "999999994.img.xml"
            source = root / "source.img"
            client.write_bytes(workbench.empty_gms_img_bytes())
            server.write_bytes(b'<imgdir name="999999994.img">\n</imgdir>\n')
            source.write_bytes(workbench.empty_gms_img_bytes())
            workbench.patch_img_add(
                source, "", "info", "imgdir", None, dry_run=False, backup=False,
            )
            workbench.patch_img_add(
                source, "info", "fieldLimit", "int", 1, dry_run=False, backup=False,
            )
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "")
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(image.root.get("info/fieldLimit").value, 1)
            self.assertEqual(server_nodes["info/fieldLimit"]["value"], 1)
            self.assertEqual(result["path"], "")
            workbench.ET.parse(server)

    def test_copy_empty_tms_root_keeps_empty_client_and_valid_xml(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-empty-root-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "999999993.img"
            server = root / "999999993.img.xml"
            source = root / "source.img"
            client.write_bytes(workbench.empty_gms_img_bytes())
            server.write_bytes(b'<imgdir name="999999993.img">\n</imgdir>\n')
            source.write_bytes(workbench.empty_gms_img_bytes())
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "")
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            self.assertEqual(image.root.children(), [])
            self.assertEqual(result["client"], [])
            self.assertEqual(result["server"], [])
            workbench.ET.parse(server)

    def test_copy_empty_tms_directory_into_existing_empty_directory_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-empty-directory-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "999999991.img"
            server = root / "999999991.img.xml"
            source = root / "source.img"
            client.write_bytes(workbench.empty_gms_img_bytes())
            source.write_bytes(workbench.empty_gms_img_bytes())
            workbench.patch_img_add(client, "", "reactor", "imgdir", None, dry_run=False, backup=False)
            workbench.patch_img_add(source, "", "reactor", "imgdir", None, dry_run=False, backup=False)
            server.write_bytes(b'<imgdir name="999999991.img">\n  <imgdir name="reactor"></imgdir>\n</imgdir>\n')
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "reactor")
            finally:
                workbench.server_xml_for_client = original_resolver

            self.assertEqual(result["client"], [])
            self.assertEqual(result["server"], [])
            workbench.ET.parse(server)

    def test_missing_npc_resource_migration_is_complete_and_idempotent(self) -> None:
        npc_id = "9010106"
        source = workbench.tms_entity_source("npc", npc_id)
        source_string = workbench._TMS_DATA / "String/Npc.img"
        if not source.is_file() or not source_string.is_file():
            self.skipTest("TMS NPC migration samples are unavailable")
        with tempfile.TemporaryDirectory(prefix=".map-mob-npc-resource-test-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            string_client = repo / "clien/Data/String/Npc.img"
            string_client.parent.mkdir(parents=True)
            string_client.write_bytes(workbench.empty_gms_img_bytes())
            for tree in ("wz", "wz-zh-CN"):
                string_server = repo / f"gms-server/{tree}/String.wz/Npc.img.xml"
                string_server.parent.mkdir(parents=True)
                string_server.write_bytes(b'<imgdir name="Npc.img">\n</imgdir>\n')

            references = [{"kind": "npc", "name": npc_id}]
            result = workbench.migrate_missing_entity_resources(
                references, repo_root=repo, tms_data=workbench._TMS_DATA,
            )
            client = repo / f"clien/Data/Npc/{npc_id}.img"
            server = repo / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
            audit = workbench._audit_canvas_payloads(client)
            self.assertEqual(audit["errors"], [])
            self.assertGreater(audit["visible"], 0)
            workbench.ET.parse(server)
            self.assertIsNotNone(workbench.load_image(string_client).root.get(npc_id))
            for tree in ("wz", "wz-zh-CN"):
                self.assertTrue(workbench.xml_has_root_child(
                    repo / f"gms-server/{tree}/String.wz/Npc.img.xml", npc_id,
                ))
            self.assertEqual(result["migrated"][0]["id"], npc_id)
            self.assertEqual(len(result["files"]), 5)

            files = [path for path in repo.rglob("*") if path.is_file()]
            before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            second = workbench.migrate_missing_entity_resources(
                references, repo_root=repo, tms_data=workbench._TMS_DATA,
            )
            after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            self.assertEqual(second, {"migrated": [], "unresolved": [], "files": []})
            self.assertEqual(after, before)

    def test_missing_map_object_branch_is_materialized_with_gms_canvas(self) -> None:
        source = workbench._TMS_DATA / "Map/Obj/morass.img"
        if not source.is_file():
            self.skipTest("TMS map object sample is unavailable")
        reference = {
            "kind": "obj", "name": "morass", "branch": "castle_Outside/acc/11",
            "canvasPath": "castle_Outside/acc/11/0", "nodes": ["4/obj/1"],
        }
        with tempfile.TemporaryDirectory(prefix=".map-mob-object-resource-test-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            result = workbench.migrate_missing_entity_resources(
                [reference], repo_root=repo, tms_data=workbench._TMS_DATA,
            )
            target = repo / "clien/Data/Map/Obj/morass.img"
            descriptor = workbench.canvas_descriptor(target, reference["canvasPath"])
            self.assertIsNotNone(descriptor)
            audit = workbench._audit_canvas_payloads(target)
            self.assertEqual(audit["errors"], [])
            self.assertGreater(audit["visible"], 0)
            self.assertEqual(result["migrated"][0]["branches"], [reference["branch"]])
            self.assertEqual(result["unresolved"], [])

    def test_copy_map_life_subtree_forwards_referenced_npc_for_resource_migration(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-copy-resource-integration-", dir=workbench._HERE) as directory:
            root = Path(directory)
            source = root / "Data/Map/Map/Map9/source.img"
            source.parent.mkdir(parents=True)
            source.write_bytes(workbench.empty_gms_img_bytes())
            for parent, name, node_type, value in (
                ("", "life", "imgdir", None),
                ("life", "0", "imgdir", None),
                ("life/0", "id", "string", "9010106"),
                ("life/0", "type", "string", "n"),
            ):
                workbench.patch_img_add(
                    source, parent, name, node_type, value, dry_run=False, backup=False,
                )
            client = root / "999999990.img"
            server = root / "999999990.img.xml"
            client.write_bytes(workbench.empty_gms_img_bytes())
            server.write_bytes(b'<imgdir name="999999990.img">\n</imgdir>\n')
            captured = []
            original_resolver = workbench.server_xml_for_client
            original_migrator = workbench.migrate_missing_entity_resources
            workbench.server_xml_for_client = lambda _path: server
            workbench.migrate_missing_entity_resources = lambda references: (
                captured.extend(references) or {
                    "migrated": [{"kind": "npc", "id": "9010106"}],
                    "files": ["clien/Data/Npc/9010106.img"],
                }
            )
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "life")
            finally:
                workbench.server_xml_for_client = original_resolver
                workbench.migrate_missing_entity_resources = original_migrator

            self.assertEqual([(item["kind"], item["name"]) for item in captured], [("npc", "9010106")])
            self.assertEqual(result["resources"]["migrated"][0]["id"], "9010106")
            self.assertEqual(
                result["modifiedFiles"],
                [
                    workbench.relative_path(client), workbench.relative_path(server),
                    "clien/Data/Npc/9010106.img",
                ],
            )

    def test_existing_map_life_node_can_repair_incomplete_npc_without_rewriting_map(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".map-mob-repair-resource-integration-", dir=workbench._HERE) as directory:
            root = Path(directory)
            source = root / "Data/Map/Map/Map9/source.img"
            source.parent.mkdir(parents=True)
            source.write_bytes(workbench.empty_gms_img_bytes())
            client = root / "999999989.img"
            client.write_bytes(workbench.empty_gms_img_bytes())
            for target in (source, client):
                for parent, name, node_type, value in (
                    ("", "life", "imgdir", None),
                    ("life", "0", "imgdir", None),
                    ("life/0", "id", "string", "9010106"),
                    ("life/0", "type", "string", "n"),
                ):
                    workbench.patch_img_add(
                        target, parent, name, node_type, value, dry_run=False, backup=False,
                    )
            server = root / "999999989.img.xml"
            server.write_bytes(b'<imgdir name="999999989.img">\n</imgdir>\n')
            client_before = client.read_bytes()
            server_before = server.read_bytes()
            captured = []
            original_resolver = workbench.server_xml_for_client
            original_migrator = workbench.migrate_missing_entity_resources
            workbench.server_xml_for_client = lambda _path: server
            workbench.migrate_missing_entity_resources = lambda references: (
                captured.extend(references) or {
                    "migrated": [{"kind": "npc", "id": "9010106"}],
                    "unresolved": [],
                    "files": ["gms-server/wz/String.wz/Npc.img.xml"],
                }
            )
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "life/0")
            finally:
                workbench.server_xml_for_client = original_resolver
                workbench.migrate_missing_entity_resources = original_migrator

            self.assertTrue(result["resourceOnly"])
            self.assertEqual([(item["kind"], item["name"]) for item in captured], [("npc", "9010106")])
            self.assertEqual(client.read_bytes(), client_before)
            self.assertEqual(server.read_bytes(), server_before)
            self.assertEqual(result["modifiedFiles"], ["gms-server/wz/String.wz/Npc.img.xml"])

    def test_copy_rejects_canvas_subtree(self) -> None:
        root = workbench.WzSubProperty("modern")
        root.add(workbench.WzCanvasProperty("0"))
        with self.assertRaisesRegex(ValueError, "Canvas"):
            workbench.clone_supported_node(root)

    def test_compare_api_loads_tms_nodes_when_main_file_is_missing(self) -> None:
        tms_source = workbench._TMS_DATA / "Map/Map/Map4/450002011.img"
        if not tms_source.is_file():
            self.skipTest("TMS map sample is unavailable")
        missing = "clien/Data/Map/Map/Map9/__missing_workbench_api_test__.img"
        response = workbench.app.test_client().post("/api/compare", json={
            "kind": "map", "leftPath": missing, "rightPath": str(tms_source),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["leftInfo"]["exists"])
        self.assertTrue(payload["nodes"])
        self.assertTrue(all(row["status"] == "rightOnly" for row in payload["nodes"]))
        self.assertGreater(payload["compatibility"]["addedRootCount"], 0)

    def test_compare_api_loads_local_map_when_tms_file_is_missing(self) -> None:
        left = "clien/Data/Map/Map/Map4/450006130.img"
        missing = str(workbench._TMS_DATA / "Map/Map/Map4/__missing_workbench_test__.img")
        if not (workbench._ROOT / left).is_file():
            self.skipTest("repository map sample is unavailable")
        response = workbench.app.test_client().post("/api/compare", json={
            "kind": "map", "leftPath": left, "rightPath": missing,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["leftInfo"]["exists"])
        self.assertFalse(payload["rightInfo"]["exists"])
        self.assertTrue(payload["nodes"])
        self.assertTrue(all(row["status"] == "leftOnly" for row in payload["nodes"]))
        self.assertTrue(payload["compatibility"]["leftAvailable"])
        self.assertFalse(payload["compatibility"]["rightAvailable"])
        self.assertEqual(payload["compatibility"]["resources"], [])

    def test_compare_api_rejects_when_both_files_are_missing(self) -> None:
        response = workbench.app.test_client().post("/api/compare", json={
            "kind": "map",
            "leftPath": "clien/Data/Map/Map/Map9/__missing_workbench_left__.img",
            "rightPath": str(workbench._TMS_DATA / "Map/Map/Map9/__missing_workbench_right__.img"),
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("A 与 B 文件都不存在", response.get_json()["reason"])

    def test_compare_api_keeps_mob_main_loaded_when_tms_file_is_missing(self) -> None:
        left = "clien/Data/Mob/8642050.img"
        missing = str(workbench._TMS_DATA / "Mob/_Canvas/__missing_workbench_test__.img")
        if not (workbench._ROOT / left).is_file():
            self.skipTest("repository mob sample is unavailable")
        response = workbench.app.test_client().post("/api/compare", json={
            "kind": "mob", "leftPath": left, "rightPath": missing,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["leftInfo"]["exists"])
        self.assertFalse(payload["rightInfo"]["exists"])
        self.assertGreater(len(payload["nodes"]), 0)

    def test_export_preserves_repo_paths_and_hashes_client_and_server(self) -> None:
        client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        server = workbench._ROOT / "gms-server/wz/Map.wz/Map/Map4/450002011.img.xml"
        additional = [
            workbench._ROOT / "clien/Data/Map/Obj/login.img",
            workbench._ROOT / "clien/Data/String/Npc.img",
            workbench._ROOT / "gms-server/wz/Npc.wz/9330045.img.xml",
            workbench._ROOT / "gms-server/wz/String.wz/Npc.img.xml",
            workbench._ROOT / "gms-server/wz-zh-CN/String.wz/Npc.img.xml",
        ]
        downloads = Path.home() / "Downloads"
        if not client.is_file() or not server.is_file() or not all(path.is_file() for path in additional) or not downloads.is_dir():
            self.skipTest("repository export samples or Downloads directory are unavailable")
        with tempfile.TemporaryDirectory(prefix=".map-mob-export-test-", dir=downloads) as directory:
            destination = Path(directory)
            result = workbench.export_current_files(
                client,
                str(destination),
                include_server=True,
                additional_sources=[server, *additional, additional[0]],
            )
            expected = [client, server, *additional]
            for source in expected:
                target = destination / source.relative_to(workbench._ROOT)
                self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(len(result["files"]), len(expected))
            self.assertTrue(all(len(item["sha256"]) == 64 for item in result["files"]))

    def test_export_without_server_filters_all_related_server_files(self) -> None:
        client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        client_resource = workbench._ROOT / "clien/Data/Map/Obj/login.img"
        server_resources = [
            workbench._ROOT / "gms-server/wz/Map.wz/Map/Map4/450002011.img.xml",
            workbench._ROOT / "gms-server/wz/String.wz/Npc.img.xml",
        ]
        downloads = Path.home() / "Downloads"
        if not all(path.is_file() for path in [client, client_resource, *server_resources]) or not downloads.is_dir():
            self.skipTest("repository export samples or Downloads directory are unavailable")
        with tempfile.TemporaryDirectory(prefix=".map-mob-export-client-test-", dir=downloads) as directory:
            destination = Path(directory)
            result = workbench.export_current_files(
                client,
                str(destination),
                include_server=False,
                additional_sources=[client_resource, *server_resources],
            )
            self.assertEqual(
                [item["source"] for item in result["files"]],
                [workbench.relative_path(client), workbench.relative_path(client_resource)],
            )
            self.assertFalse((destination / server_resources[0].relative_to(workbench._ROOT)).exists())
            self.assertFalse((destination / server_resources[1].relative_to(workbench._ROOT)).exists())

    def test_export_rejects_missing_related_file(self) -> None:
        client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        downloads = Path.home() / "Downloads"
        if not client.is_file() or not downloads.is_dir():
            self.skipTest("repository map IMG sample or Downloads directory is unavailable")
        missing = workbench._ROOT / "clien/Data/Npc/__missing_export_resource__.img"
        with tempfile.TemporaryDirectory(prefix=".map-mob-export-missing-test-", dir=downloads) as directory:
            with self.assertRaisesRegex(ValueError, "关联修改文件不存在"):
                workbench.export_current_files(
                    client,
                    directory,
                    include_server=False,
                    additional_sources=[missing],
                )

    def test_export_rejects_destination_outside_downloads(self) -> None:
        client = workbench._ROOT / "clien/Data/Map/Map/Map4/450002011.img"
        if not client.is_file():
            self.skipTest("repository map IMG sample is unavailable")
        with self.assertRaisesRegex(ValueError, "Downloads"):
            workbench.export_current_files(client, "/tmp/map-mob-export", include_server=False)


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

    def test_chew_chew_swim_nodes_explain_legacy_local_area_projection(self) -> None:
        left_path = workbench._ROOT / "clien" / "Data" / "Map" / "Map" / "Map4" / "450002011.img"
        right_path = workbench._TMS_DATA / "Map" / "Map" / "Map4" / "450002011.img"
        if not left_path.is_file() or not right_path.is_file():
            self.skipTest("Chew Chew map samples are unavailable")
        left, _ = workbench.flatten_source(left_path)
        right, _ = workbench.flatten_source(right_path)
        rows, _ = workbench.merge_sources(left, right)
        workbench.annotate_rows(rows, "map", "450002011")
        swim = next(row for row in rows if row["path"] == "info/swim")
        self.assertEqual(swim["left"]["value"], 0)
        self.assertEqual(swim["right"]["value"], 0)
        self.assertIn("是否可游泳", swim["left"]["meaning"])
        self.assertIn("整张地图", swim["left"]["scope"])
        self.assertIn("swimArea/swim01", swim["left"]["migration"])
        self.assertIn("info/swim=0", swim["left"]["migration"])
        self.assertIn("根节点", swim["left"]["placement"])
        self.assertIn("└─ swimArea", swim["left"]["structure"])
        self.assertIn("y1 = 206", swim["left"]["structure"])
        self.assertEqual(swim["left"]["compatibility"]["status"], "ok")
        self.assertEqual(swim["right"]["compatibility"]["status"], "ok")
        rapid_y1 = next(row for row in rows if row["path"] == "rapidStream/swim01/y1")
        self.assertIn("水面高度", rapid_y1["right"]["meaning"])
        self.assertIn("x=-819..5000", rapid_y1["right"]["migration"])
        self.assertIn("根节点新建 swimArea", rapid_y1["right"]["placement"])
        self.assertEqual(rapid_y1["right"]["compatibility"]["status"], "modern")
        area_force = next(row for row in rows if row["path"] == "areaCtrl/swim01/forceX")
        self.assertIn("水平基础作用力", area_force["right"]["meaning"])
        self.assertIn("不决定矩形边界", area_force["right"]["scope"])

    def test_nautilus_swim_area_is_a_proven_legacy_local_water_contract(self) -> None:
        path = workbench._ROOT / "clien" / "Data" / "Map" / "Map" / "Map1" / "120000000.img"
        if not path.is_file():
            self.skipTest("Nautilus map sample is unavailable")
        nodes, _ = workbench.flatten_source(path)
        self.assertEqual(nodes["info/swim"]["value"], 0)
        self.assertEqual(nodes["swimArea/nt/x1"]["value"], -606)
        annotated = workbench.annotate_meta("swimArea/nt/y1", nodes["swimArea/nt/y1"], "map", "120000000")
        self.assertIn("水面高度", annotated["meaning"])
        self.assertIn("旧端已验证", annotated["migration"])
        self.assertEqual(annotated["compatibility"]["status"], "ok")

    def test_map_preview_exposes_normalized_water_area_rectangles(self) -> None:
        path = workbench._ROOT / "clien" / "Data" / "Map" / "Map" / "Map1" / "120000000.img"
        if not path.is_file():
            self.skipTest("Nautilus map sample is unavailable")
        preview = workbench.map_preview(path)
        area = next(item for item in preview["waterAreas"] if item["path"] == "swimArea/nt")
        self.assertEqual(area, {
            "path": "swimArea/nt", "kind": "swimArea",
            "x1": -606, "y1": 207, "x2": 5318, "y2": 302,
        })
        self.assertEqual(preview["summary"]["waterAreas"], 1)


class CrashDiagnosticTests(unittest.TestCase):
    def test_arcana_two_case_control_reports_exclusive_nodes_and_working_counterexamples(self) -> None:
        path = workbench._ROOT / "clien/Data/Map/Map/Map4/450005220.img"
        peer = workbench._ROOT / "clien/Data/Map/Map/Map4/450005242.img"
        if not path.is_file() or not peer.is_file():
            self.skipTest("Arcana two-case regression data is unavailable")
        report = workbench.diagnose_map_crash(path, "map_load", ["450005242"])
        comparison = report["caseControl"]
        self.assertTrue(comparison["enabled"])
        self.assertEqual(comparison["caseMaps"], ["450005220", "450005242"])
        self.assertEqual(comparison["parsedControlCount"], 29)
        self.assertTrue(any(item["mapPath"] == "miniMap/canvas" for item in comparison["exclusive"]))
        life_schema = next(
            item for item in comparison["exclusive"]
            if item["category"] == "schema" and item["mapPath"] == "life"
        )
        self.assertIn("life/31", life_schema["casePaths"]["450005220"])
        self.assertIn("life/31", life_schema["casePaths"]["450005242"])
        forced = next(item for item in comparison["counterexamples"] if "forcedZPage" in item["title"])
        self.assertIn("450005240", forced["controlMaps"])
        forced_finding = next(item for item in report["findings"] if item["mapPath"].endswith("/forcedZPage"))
        self.assertIn("不要据此删除", forced_finding["action"])
        self.assertIn("450005240", forced_finding["evidence"][0])
        self.assertIn("session-*.log", report["isolation"][0])

    def test_arcana_baseline_prioritizes_exclusive_materialized_background_on_map_load(self) -> None:
        repository_path = workbench._ROOT / "clien/Data/Map/Map/Map4/450005220.img"
        tms_map = workbench._TMS_DATA / "Map/Map/Map4/450005220.img"
        if not repository_path.is_file() or not tms_map.is_file():
            self.skipTest("Arcana crash regression data is unavailable")
        try:
            baseline = subprocess.check_output([
                "git", "cat-file", "blob", "HEAD:clien/Data/Map/Map/Map4/450005220.img",
            ], cwd=workbench._ROOT)
        except subprocess.CalledProcessError:
            self.skipTest("Arcana Git baseline is unavailable")
        parent = workbench._ROOT / "clien/Data/Map/Map/Map4"
        with tempfile.TemporaryDirectory(prefix=".crash-diagnostic-test-", dir=parent) as directory:
            path = Path(directory) / "450005220.img"
            path.write_bytes(baseline)
            report = workbench.diagnose_map_crash(path, "map_load")
        suspect = next(
            item for item in report["sceneResources"]["suspects"]
            if item["mapPath"] == "back/18"
        )
        self.assertEqual(suspect["name"], "arcana2")
        self.assertEqual(suspect["canvasPath"], "back/74")
        self.assertEqual((suspect["sourceWidth"], suspect["sourceHeight"]), (1, 1))
        self.assertEqual(suspect["sourceLinkType"], "_outlink")
        self.assertEqual(suspect["sourceLinkPath"], "Map/Back/_Canvas/arcana2.img/back/74")
        self.assertEqual((suspect["clientWidth"], suspect["clientHeight"]), (970, 824))
        self.assertEqual(suspect["regionalUsageCount"], 1)
        self.assertTrue(suspect["exclusive"])
        self.assertEqual(report["phase"], "map_load")
        self.assertEqual(report["conclusion"], "更偏向地图结构或场景资源问题")
        self.assertGreater(report["scores"]["resource"], report["scores"]["entity"])
        finding = next(item for item in report["findings"] if item["mapPath"] == "back/18")
        self.assertIn("1x1", finding["detail"])
        self.assertIn("970x824", finding["detail"])
        self.assertIn("只同步移除 back/18", finding["action"])
        mob_type = next(item for item in report["findings"] if "info/mobType" in item["title"])
        self.assertEqual(mob_type["confidence"], "low")

        from wzpy.incremental_img import mutate_img

        gapped = mutate_img(baseline, "remove", ("back", "18"), region="GMS").data
        with tempfile.TemporaryDirectory(prefix=".crash-diagnostic-gap-test-", dir=parent) as directory:
            path = Path(directory) / "450005220.img"
            path.write_bytes(gapped)
            gap_report = workbench.diagnose_map_crash(path, "map_load")
        gap_finding = next(item for item in gap_report["findings"] if item["mapPath"] == "back")
        self.assertIn("缺少 18", gap_finding["detail"])
        self.assertIn("A/B 结果无效", gap_finding["title"])

    def test_yumyum_crash_diagnostic_separates_map_and_mob_evidence(self) -> None:
        path = workbench._ROOT / "clien/Data/Map/Map/Map4/450015030.img"
        if not path.is_file():
            self.skipTest("YumYum crash sample is unavailable")
        report = workbench.diagnose_map_crash(path)
        self.assertEqual(report["mapId"], "450015030")
        self.assertEqual(report["conclusion"], "更偏向怪物/NPC 资源问题")
        self.assertEqual(report["confidence"], "中")
        mob = next(item for item in report["entities"] if item["id"] == "8642050")
        self.assertEqual(mob["spawns"], 27)
        self.assertGreater(mob["canvases"], 0)
        self.assertEqual(mob["canvases"], mob["visible"])
        mob_type = next(item for item in report["findings"] if "info/mobType" in item["title"])
        self.assertEqual(mob_type["domain"], "entity")
        self.assertEqual(mob_type["severity"], "warn")
        self.assertEqual(mob_type["confidence"], "medium")
        self.assertIn("单凭该字段不能证明必崩", mob_type["detail"])
        self.assertTrue(any("地图 IMG 可完整解析" in item for item in report["verified"]))

    def test_diagnose_map_api_is_read_only_and_returns_isolation_steps(self) -> None:
        path = workbench._ROOT / "clien/Data/Map/Map/Map4/450015030.img"
        if not path.is_file():
            self.skipTest("YumYum crash sample is unavailable")
        before = path.read_bytes()
        response = workbench.app.test_client().post(
            "/api/diagnose-map", json={"sourcePath": str(path), "phase": "entity_appear"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["phase"], "entity_appear")
        self.assertGreaterEqual(len(payload["isolation"]), 3)
        self.assertEqual(path.read_bytes(), before)


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
