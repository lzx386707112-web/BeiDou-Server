#!/usr/bin/env python3
"""Focused safety tests for Map & Mob Workbench."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_mob_default_path_keeps_canvas_directory_when_files_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_tms_data = workbench._TMS_DATA
            workbench._TMS_DATA = Path(directory)
            try:
                _, right = workbench.default_paths("mob", "8880110")
            finally:
                workbench._TMS_DATA = original_tms_data
            self.assertEqual(right, Path(directory) / "Mob/_Canvas/8880110.img")

    def test_mob_comparison_prefers_tms_directory_not_ms_cache(self) -> None:
        result = workbench.mob_source_options("8880100")
        canvas = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        self.assertEqual(result["comparisonPath"], workbench.relative_path(canvas))
        self.assertTrue(str(result["comparisonPath"]).startswith(str(workbench._TMS_DATA)))
        self.assertNotIn("Library/Caches", result["comparisonPath"])
        missing = workbench.mob_source_options("8880110")
        expected = workbench.relative_path(workbench._TMS_DATA / "Mob/_Canvas/8880110.img")
        self.assertEqual(missing["comparisonPath"], expected)
        self.assertIn("/_Canvas/", missing["comparisonPath"].replace("\\", "/"))

    def test_mob_canvas_store_tree_includes_sparse_attack_frames(self) -> None:
        canvas = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        if not canvas.is_file():
            self.skipTest("TMS Canvas 8880100 is unavailable")
        nodes, info = workbench.flatten_img(canvas)
        self.assertTrue(info.get("canvasStore"))
        for index in range(35):
            self.assertIn(f"attack1/{index}", nodes, f"attack1/{index} missing from canvas tree")
        self.assertTrue(nodes["attack1/12"].get("canvasStoreMissing"))
        self.assertIn("attack1", nodes)
        self.assertIn("attack2", nodes)
        self.assertIn("attack2/info/hit", nodes)
        self.assertNotIn("attack2/info/ball", nodes)
        self.assertNotIn("attack2/info/ball/0", nodes)
        self.assertIn("attack3", nodes)
        self.assertNotIn("attack4", nodes)
        self.assertNotIn("attack5", nodes)
        self.assertNotIn("attack6", nodes)

    def test_json_companion_does_not_invent_attack2_ball(self) -> None:
        canvas = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        json_dump = workbench._ROOT / "clien/Data/Mob/8880100.img.json"
        if not canvas.is_file() or not json_dump.is_file():
            self.skipTest("Damien 8880100 Canvas or JSON companion is unavailable")
        merged = workbench.merge_canvas_metadata_tables(canvas, allow_extract=True)
        self.assertNotIn("attack2/info/ball", merged)
        self.assertNotIn("attack2/info/ball/0", merged)
        self.assertIn("attack2/info/hit/0", merged)
        self.assertIn("attack1/0/origin", merged)

    def test_canvas_companion_uses_existing_extract_without_scanning_ms_packs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canvas = root / "Mob" / "_Canvas" / "1234567.img"
            extracted = root / "cache" / "Mob_1234567.img"
            canvas.parent.mkdir(parents=True)
            extracted.parent.mkdir(parents=True)
            canvas.touch()
            extracted.touch()
            original_find = workbench.find_extracted_ms_mob
            original_index = workbench.ms_mob_index
            try:
                workbench.find_extracted_ms_mob = lambda _item_id: extracted
                workbench.ms_mob_index = lambda: self.fail("read-only comparison must not scan MS packs")
                self.assertEqual(
                    workbench.canvas_metadata_companion_paths(canvas, allow_extract=False),
                    [extracted],
                )
            finally:
                workbench.find_extracted_ms_mob = original_find
                workbench.ms_mob_index = original_index

    def test_canvas_companion_copy_reuses_extract_without_scanning_ms_packs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            canvas = Path(directory) / "Mob" / "_Canvas" / "1234567.img"
            extracted = Path(directory) / "Mob_1234567.img"
            canvas.parent.mkdir(parents=True)
            canvas.touch()
            extracted.touch()
            with mock.patch.object(workbench, "find_extracted_ms_mob", return_value=extracted), \
                    mock.patch.object(workbench, "extract_ms_mob") as extract:
                self.assertEqual(
                    workbench.canvas_metadata_companion_paths(canvas, allow_extract=True),
                    [extracted],
                )
                extract.assert_not_called()

    def test_mob_scalar_copy_skips_canvas_metadata_and_subtree_loads_it_once(self) -> None:
        image = workbench._verified_img_from_bytes(Path("source.img"), workbench.empty_gms_img_bytes())
        source_path = Path("Mob/_Canvas/1234567.img")
        scalar = workbench.WzIntProperty("attackAfter", 630)
        subtree = workbench.WzSubProperty("info")
        subtree.add(workbench.WzIntProperty("level", 1, subtree))
        with mock.patch.object(workbench, "merge_canvas_metadata_tables", return_value={}) as metadata:
            clone, _, _ = workbench.clone_compatible_mob_node(scalar, image, source_path)
            self.assertEqual(clone.value, 630)
            metadata.assert_not_called()
            workbench.clone_compatible_mob_node(subtree, image, source_path)
            metadata.assert_called_once_with(source_path, allow_extract=True)

    def test_mob_attack8_keeps_self_contained_four_pixel_companion_frame(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8930000.img"
        companion = workbench.find_extracted_ms_mob("8930000")
        client = workbench._ROOT / "clien/Data/Mob/8930000.img"
        if not source.is_file() or companion is None or not client.is_file():
            self.skipTest("Magnus 8930000 Canvas, logical record, or client sample is unavailable")

        source_image = workbench.load_image(source)
        companion_image = workbench.load_image(companion)
        self.assertIsNone(source_image.root.get("attack8/12"))
        logical_frame = companion_image.root.get("attack8/12")
        self.assertIsInstance(logical_frame, workbench.WzCanvasProperty)
        self.assertEqual((int(logical_frame.width), int(logical_frame.height)), (4, 4))

        clone, _, _ = workbench.clone_compatible_mob_node(
            source_image.root.get("attack8"), source_image, source,
            client_image=workbench.load_image(client), copied_root="attack8", dest_mob_id="8930000",
        )
        names = sorted(int(child.name) for child in clone.children() if child.name.isdigit())
        self.assertEqual(names, list(range(32)))
        frame = clone.get("12")
        self.assertIsInstance(frame, workbench.WzCanvasProperty)
        self.assertEqual((int(frame.width), int(frame.height)), (4, 4))
        self.assertEqual((int(frame.format), int(frame.format2)), (1, 0))
        self.assertEqual(int(frame.child("delay").value), 1200)
        self.assertEqual(int(frame.child("hide").value), 1)
        bitmap = workbench.decode_canvas(frame, region="GMS").convert("RGBA")
        self.assertEqual(bitmap.getchannel("A").getbbox(), (0, 0, 1, 1))

    def test_ms_mob_index_resolves_lucid_id_to_exact_pack_entry(self) -> None:
        if not workbench._MS_PROBE.is_file() or not workbench.ms_pack_signature():
            self.skipTest("TMS MS packs or MSProbe are unavailable")
        index = workbench.ms_mob_index()
        self.assertIn("8880141", index)
        self.assertEqual(index["8880141"].name, "Mob_00000.ms")

    def test_mob_sources_extract_complete_ms_record_and_confirm_identity(self) -> None:
        if not workbench._MS_PROBE.is_file() or not workbench.ms_pack_signature():
            self.skipTest("TMS MS packs or MSProbe are unavailable")
        result = workbench.mob_source_options("8880141")
        self.assertEqual(result["name"], "夢中的露希妲")
        self.assertEqual(result["msEntry"], "Mob/8880141.img")
        source = next(item for item in result["sources"] if item["kind"] == "ms")
        self.assertEqual(source["pack"], "Mob_00000.ms")
        self.assertEqual(source["rootCount"], 14)
        self.assertIn("attack5", source["roots"])
        _, expected_right = workbench.default_paths("mob", "8880141")
        self.assertEqual(result["comparisonPath"], workbench.relative_path(expected_right))
        self.assertTrue(str(expected_right).startswith(str(workbench._TMS_DATA)))
        extracted = workbench.resolve_repo_path(source["path"])
        self.assertTrue(any(extracted.is_relative_to(root) for root in workbench._ms_extract_roots()))
        self.assertEqual(workbench.data_root_for(extracted), workbench._TMS_DATA)
        image = workbench.load_image(extracted)
        self.assertFalse(image.truncated)
        self.assertEqual(image.parse_warnings, [])

    def test_mob_catalog_can_search_tms_name_and_show_phase_candidates(self) -> None:
        if not workbench._MS_PROBE.is_file() or not workbench.ms_pack_signature():
            self.skipTest("TMS MS packs or MSProbe are unavailable")
        rows = workbench.catalog_rows("mob", "夢中的露希妲")
        by_id = {row["id"]: row for row in rows}
        self.assertTrue({"8880140", "8880141", "8880142"}.issubset(by_id))
        self.assertEqual(by_id["8880141"]["name"], "夢中的露希妲")
        self.assertIn("MS", by_id["8880141"]["sources"])

    def test_ms_mob_preview_contains_metadata_actions_missing_from_canvas_only_view(self) -> None:
        if not workbench._MS_PROBE.is_file() or not workbench.ms_pack_signature():
            self.skipTest("TMS MS packs or MSProbe are unavailable")
        source = workbench.mob_source_options("8880141")
        ms_path = next(item["path"] for item in source["sources"] if item["kind"] == "ms")
        preview = workbench.mob_preview(workbench.resolve_repo_path(ms_path))
        actions = {action["name"] for action in preview["actions"]}
        self.assertTrue({"stand", "skill5", "attack5"}.issubset(actions))
        self.assertGreaterEqual(len(actions), 13)

    def test_migrate_ms_mob_action_adds_replaces_and_is_idempotent(self) -> None:
        if not workbench._MS_PROBE.is_file() or not workbench.ms_pack_signature():
            self.skipTest("TMS MS packs or MSProbe are unavailable")
        project_client = workbench._ROOT / "clien/Data/Mob/8880141.img"
        project_server = workbench._ROOT / "gms-server/wz/Mob.wz/8880141.img.xml"
        if not project_client.is_file() or not project_server.is_file():
            self.skipTest("Lucid client/server baseline is unavailable")
        source_info = workbench.mob_source_options("8880141")
        source = workbench.resolve_repo_path(
            next(item["path"] for item in source_info["sources"] if item["kind"] == "ms")
        )

        with tempfile.TemporaryDirectory(prefix=".mob-action-migration-test-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            client = repo / "clien/Data/Mob/8880141.img"
            server = repo / "gms-server/wz/Mob.wz/8880141.img.xml"
            client.parent.mkdir(parents=True)
            server.parent.mkdir(parents=True)
            client.write_bytes(project_client.read_bytes())
            server.write_bytes(project_server.read_bytes())
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                before = client.read_bytes()
                before_records, before_orders = workbench.arc.raw_record_state(before)
                server_before = server.read_bytes()
                plan = workbench.migrate_mob_action_with_server_sync(
                    client, source, "stand", dry_run=True,
                )
                self.assertTrue(plan["dryRun"])
                self.assertTrue(plan["changed"])
                self.assertEqual(plan["modifiedFiles"], [])
                self.assertEqual(client.read_bytes(), before)
                self.assertEqual(server.read_bytes(), server_before)
                added = workbench.migrate_mob_action_with_server_sync(client, source, "stand")
                self.assertEqual(added["clientOperation"], "add")
                self.assertEqual(added["serverOperation"], "add")
                self.assertEqual(added["canvas"]["formats"], ["1/0"])
                self.assertEqual(added["canvas"]["canvases"], 8)
                self.assertEqual(added["canvas"]["visible"], 8)

                after_add = client.read_bytes()
                after_records, after_orders = workbench.arc.raw_record_state(after_add)
                self.assertEqual(after_orders[()][:-1], before_orders[()])
                self.assertEqual(after_orders[()][-1], "stand")
                for path, raw in before_records.items():
                    self.assertEqual(after_records[path], raw, "/".join(path))
                stand_xml = workbench.index_xml(server.read_bytes())["stand"]
                self.assertEqual(stand_xml.tag, "imgdir")
                stand_element = next(
                    child for child in workbench.ET.parse(server).getroot()
                    if child.tag == "imgdir" and child.get("name") == "stand"
                )
                stand_canvases = [child for child in stand_element if child.tag == "canvas"]
                self.assertEqual(len(stand_canvases), 8)
                self.assertTrue(all(canvas.get("format") == "1" for canvas in stand_canvases))

                first_hashes = (
                    hashlib.sha256(client.read_bytes()).hexdigest(),
                    hashlib.sha256(server.read_bytes()).hexdigest(),
                )
                repeated = workbench.migrate_mob_action_with_server_sync(client, source, "stand")
                second_hashes = (
                    hashlib.sha256(client.read_bytes()).hexdigest(),
                    hashlib.sha256(server.read_bytes()).hexdigest(),
                )
                self.assertFalse(repeated["changed"])
                self.assertEqual(repeated["modifiedFiles"], [])
                self.assertEqual(second_hashes, first_hashes)

                before_replace = client.read_bytes()
                replaced = workbench.migrate_mob_action_with_server_sync(client, source, "skill4")
                self.assertEqual(replaced["clientOperation"], "replace")
                self.assertEqual(replaced["serverOperation"], "replace")
                self.assertGreater(replaced["rawScope"]["protectedRecords"], 0)
                before_replace_records, _ = workbench.arc.raw_record_state(before_replace)
                after_replace_records, _ = workbench.arc.raw_record_state(client.read_bytes())
                for path, raw in before_replace_records.items():
                    if path[:1] != ("skill4",):
                        self.assertEqual(after_replace_records[path], raw, "/".join(path))
                workbench.ET.parse(server)

                blocked_client = client.read_bytes()
                blocked_server = server.read_bytes()
                with self.assertRaisesRegex(ValueError, "未授权记录"):
                    workbench.migrate_mob_action_with_server_sync(client, source, "hit1")
                self.assertEqual(client.read_bytes(), blocked_client)
                self.assertEqual(server.read_bytes(), blocked_server)
            finally:
                workbench._ROOT = original_root
                workbench._load_image_cached.cache_clear()

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
                with mock.patch.object(
                    workbench, "_verified_img_from_bytes", wraps=workbench._verified_img_from_bytes,
                ) as verify:
                    workbench.add_with_server_sync(
                        client, "", "__swimArea_sync_test__", "imgdir", None,
                        dry_run=False, backup=False,
                    )
                self.assertEqual(verify.call_count, 2)
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

    def test_mob_copy_batches_missing_ancestor_chain_with_leaf(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".mob-copy-branch-test-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "clien/Data/Mob/9999990.img"
            server = root / "gms-server/wz/Mob.wz/9999990.img.xml"
            source = root / "source/Mob/9999990.img"
            client.parent.mkdir(parents=True)
            server.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            client.write_bytes(workbench.empty_gms_img_bytes())
            server.write_bytes(b'<imgdir name="9999990.img">\n</imgdir>\n')
            source.write_bytes(workbench.empty_gms_img_bytes())
            for parent, name, node_type, value in (
                ("", "attack1", "imgdir", None),
                ("attack1", "info", "imgdir", None),
                ("attack1/info", "hit", "imgdir", None),
                ("attack1/info/hit", "0", "int", 7),
            ):
                workbench.patch_img_add(
                    source, parent, name, node_type, value, dry_run=False, backup=False,
                )
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                with mock.patch.object(
                    workbench, "patch_img_add", wraps=workbench.patch_img_add,
                ) as img_add, mock.patch.object(
                    workbench, "xml_add_cloned_node", wraps=workbench.xml_add_cloned_node,
                ) as xml_add:
                    result = workbench.copy_tms_node_with_server_sync(
                        client, source, "attack1/info/hit/0",
                    )
                self.assertEqual(img_add.call_count, 1)
                self.assertEqual(xml_add.call_count, 1)
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(image.root.get("attack1/info/hit/0").value, 7)
            self.assertEqual(server_nodes["attack1/info/hit/0"]["value"], 7)
            self.assertEqual(
                result["createdAncestors"], ["attack1", "attack1/info", "attack1/info/hit"],
            )
            self.assertEqual(result["client"]["insertedRoot"], "attack1")
            self.assertEqual(result["server"]["insertedRoot"], "attack1")

    def test_mob_copy_adds_missing_client_leaf_and_replaces_existing_server_leaf(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".mob-copy-server-replace-", dir=workbench._HERE) as directory:
            root = Path(directory)
            client = root / "clien/Data/Mob/9999989.img"
            server = root / "gms-server/wz/Mob.wz/9999989.img.xml"
            source = root / "source/Mob/9999989.img"
            client.parent.mkdir(parents=True)
            server.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            client.write_bytes(workbench.empty_gms_img_bytes())
            source.write_bytes(workbench.empty_gms_img_bytes())
            for path in (client, source):
                workbench.patch_img_add(
                    path, "", "attack4", "imgdir", None, dry_run=False, backup=False,
                )
            workbench.patch_img_add(
                source, "attack4", "12", "int", 12, dry_run=False, backup=False,
            )
            server.write_bytes(b'''<imgdir name="9999989.img">
  <imgdir name="attack4">
    <uol name="12" value="../attack1/32"/>
  </imgdir>
</imgdir>
''')
            original_resolver = workbench.server_xml_for_client
            workbench.server_xml_for_client = lambda _path: server
            try:
                result = workbench.copy_tms_node_with_server_sync(
                    client, source, "attack4/12",
                )
            finally:
                workbench.server_xml_for_client = original_resolver

            image = workbench._verified_img_from_bytes(client, client.read_bytes())
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertEqual(image.root.get("attack4/12").value, 12)
            self.assertEqual(server_nodes["attack4/12"]["type"], "int")
            self.assertEqual(server_nodes["attack4/12"]["value"], 12)
            self.assertEqual(result["server"]["operation"], "replace")

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

    def test_modern_spine_object_is_not_reported_as_a_missing_static_resource(self) -> None:
        root = workbench.WzSubProperty("root")
        layer = workbench.WzSubProperty("1")
        objects = workbench.WzSubProperty("obj")
        modern = workbench.WzSubProperty("0")
        for name, value in (
            ("oS", "Lacheln"), ("l0", "Boss"), ("l1", "obj"),
            ("l2", "9"), ("spineAni", "animation"), ("tags", "spine"),
        ):
            modern.add(workbench.WzStringProperty(name, value))
        objects.add(modern)
        layer.add(objects)
        root.add(layer)

        self.assertEqual(workbench.map_resource_references(root), [])
        projected, skipped = workbench.clone_compatible_map_node(
            objects, Path("clien/Data/Map/Map/Map4/450004150.img"),
        )
        self.assertIsNone(projected.child("0"))
        self.assertEqual(skipped, ["1/obj/0"])
        with self.assertRaisesRegex(ValueError, "现代 Spine/动态对象"):
            workbench.clone_compatible_map_node(
                modern, Path("clien/Data/Map/Map/Map4/450004150.img"),
            )

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

    def test_mob_area_warning_copy_projects_canvas_and_fills_numeric_gaps(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        project_client = workbench._ROOT / "clien/Data/Mob/8880110.img"
        project_server = workbench._ROOT / "gms-server/wz/Mob.wz/8880110.img.xml"
        if not source.is_file() or not project_client.is_file() or not project_server.is_file():
            self.skipTest("Damien 8880100 Canvas or 8880110 baseline is unavailable")
        image = workbench.load_image(source)
        warning = image.root.get("attack1/info/areaWarning")
        self.assertIsInstance(warning, workbench.WzSubProperty)
        source_names = sorted(int(child.name) for child in warning.children() if child.name.isdigit())
        self.assertNotEqual(source_names, list(range(source_names[0], source_names[-1] + 1)))
        clone, materializer = workbench.clone_compatible_mob_node(warning, image, source)[:2]
        names = [int(child.name) for child in clone.children() if child.name.isdigit()]
        self.assertEqual(names, list(range(len(source_names) + 1)))
        self.assertEqual(len(names), len(source_names) + 1)
        frame0 = clone.get("0")
        self.assertIsInstance(frame0, workbench.WzCanvasProperty)
        self.assertEqual((int(frame0.width), int(frame0.height)), (1, 1))
        frame1 = clone.get("1")
        self.assertIsInstance(frame1, workbench.WzCanvasProperty)
        self.assertGreater(int(frame1.width), 4)
        self.assertGreaterEqual(materializer.canvases, len(source_names))
        for child in clone.children():
            if isinstance(child, workbench.WzCanvasProperty):
                self.assertEqual((int(child.format), int(child.format2)), (1, 0))
                self.assertTrue(child._png_data)
                origin = child.child("origin")
                delay = child.child("delay")
                self.assertIsInstance(origin, workbench.WzVectorProperty)
                self.assertIsInstance(delay, workbench.WzIntProperty)
                self.assertGreaterEqual(int(delay.value), 16)

        with tempfile.TemporaryDirectory(prefix=".copy-area-warning-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            client = repo / "clien/Data/Mob/8880110.img"
            server = repo / "gms-server/wz/Mob.wz/8880110.img.xml"
            client.parent.mkdir(parents=True)
            server.parent.mkdir(parents=True)
            client.write_bytes(project_client.read_bytes())
            server.write_bytes(project_server.read_bytes())
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                result = workbench.copy_tms_node_with_server_sync(
                    client, source, "attack1/info/areaWarning",
                )
            finally:
                workbench._ROOT = original_root
            self.assertGreater(result["densifiedFrames"], 0)
            self.assertGreater(result["materialized"]["canvases"], 0)
            copied = workbench.load_image(client).root.get("attack1/info/areaWarning")
            copied_names = [int(child.name) for child in copied.children() if child.name.isdigit()]
            self.assertEqual(copied_names[0], 0)
            self.assertEqual((int(copied.get("0").width), int(copied.get("0").height)), (1, 1))
            self.assertGreater(int(copied.get("1").width), 4)
            server_nodes, _ = workbench.flatten_xml(server)
            self.assertIn("attack1/info/areaWarning/0", server_nodes)

    def test_mob_area_warning_frame0_copies_1x1_stub(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        if not source.is_file():
            self.skipTest("Damien 8880100 Canvas is unavailable")
        image = workbench.load_image(source)
        self.assertIsNone(image.root.get("attack1/info/areaWarning/0"))
        companion = workbench.companion_logical_node(source, "attack1/info/areaWarning/0")
        self.assertIsInstance(companion, workbench.WzCanvasProperty)
        self.assertEqual((int(companion.width), int(companion.height)), (1, 1))
        clone, _, _ = workbench.clone_compatible_mob_node(
            companion, image, source, copied_root="attack1/info/areaWarning/0",
        )
        self.assertIsInstance(clone, workbench.WzCanvasProperty)
        self.assertEqual(clone.name, "0")
        self.assertEqual((int(clone.width), int(clone.height)), (1, 1))
        self.assertEqual((int(clone.format), int(clone.format2)), (1, 0))
        self.assertTrue(clone._png_data)
        origin = clone.child("origin")
        self.assertIsInstance(origin, workbench.WzVectorProperty)
        self.assertEqual((int(origin.x), int(origin.y)), (0, 0))

    def test_mob_canvas_copy_keeps_origin_delay_from_companion(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        json_dump = workbench._ROOT / "clien/Data/Mob/8880100.img.json"
        if not source.is_file() or not json_dump.is_file():
            self.skipTest("Damien 8880100 Canvas or JSON companion is unavailable")
        image = workbench.load_image(source)
        attack1 = image.root.get("attack1/0")
        self.assertIsInstance(attack1, workbench.WzCanvasProperty)
        self.assertIsNone(attack1.child("origin"))
        clone, _materializer, stats = workbench.clone_compatible_mob_node(
            attack1, image, source, copied_root="attack1/0",
        )
        self.assertIsInstance(clone, workbench.WzCanvasProperty)
        origin = clone.child("origin")
        delay = clone.child("delay")
        self.assertIsInstance(origin, workbench.WzVectorProperty)
        self.assertEqual((int(origin.x), int(origin.y)), (45, 146))
        self.assertEqual(int(delay.value), 90)
        self.assertEqual((int(clone.child("head").x), int(clone.child("head").y)), (-3, -116))
        self.assertEqual((int(clone.child("lt").x), int(clone.child("lt").y)), (-38, -145))
        self.assertEqual((int(clone.child("rb").x), int(clone.child("rb").y)), (39, -11))
        self.assertEqual(int(clone.child("z").value), 0)
        self.assertGreater(stats["canvasMeta"], 0)

        cache = Path("/private/tmp/arcane-river-mob-cache/8880100/Mob_8880100.img")
        if cache.is_file():
            warning = image.root.get("attack1/info/areaWarning/1")
            self.assertIsInstance(warning, workbench.WzCanvasProperty)
            warning_clone, _, _ = workbench.clone_compatible_mob_node(
                warning, image, source, copied_root="attack1/info/areaWarning/1",
            )
            self.assertEqual(
                (int(warning_clone.child("origin").x), int(warning_clone.child("origin").y)),
                (59, 201),
            )
            skill2 = image.root.get("skill2")
            skill1 = workbench.WzSubProperty("skill1")
            for index in range(10):
                skill1.add(workbench._legacy_stub_canvas(str(index), skill1))
            stand = workbench.WzSubProperty("stand")
            for index in range(8):
                stand.add(workbench._legacy_stub_canvas(str(index), stand))
            client_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), stand)
            client_data = workbench.arc.append_property_record(client_data, (), skill1)
            client = workbench._verified_img_from_bytes(Path("8880110.img"), client_data)
            skill_clone, _, stats = workbench.clone_compatible_mob_node(
                skill2, image, source, client_image=client, copied_root="skill2",
            )
            names = sorted(int(child.name) for child in skill_clone.children() if child.name.isdigit())
            self.assertEqual(names, list(range(105)))
            self.assertIsInstance(skill_clone.get("0"), workbench.WzUolProperty)
            self.assertEqual(str(skill_clone.get("0").value), "../skill1/0")
            frame = skill_clone.get("10")
            self.assertIsInstance(frame, workbench.WzCanvasProperty)
            self.assertGreater(int(frame.width), 4)
            self.assertEqual((int(frame.child("origin").x), int(frame.child("origin").y)), (106, 653))
            self.assertEqual(str(skill_clone.get("31").value), "23")
            self.assertEqual(str(skill_clone.get("72").value), "23")
            self.assertEqual(str(skill_clone.get("97").value), "../stand/0")
            self.assertGreaterEqual(stats["uolsKept"], 59)
            return

        skill2 = image.root.get("skill2")
        with self.assertRaisesRegex(ValueError, "skill1"):
            workbench.clone_compatible_mob_node(skill2, image, source, copied_root="skill2")

    def test_mob_attack_copy_keeps_companion_children_and_skips_huge_gaps(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        project_client = workbench._ROOT / "clien/Data/Mob/8880110.img"
        if not source.is_file() or not project_client.is_file():
            self.skipTest("Damien Canvas or 8880110 baseline is unavailable")
        image = workbench.load_image(source)
        client_image = workbench.load_image(project_client)
        attack2 = image.root.get("attack2")
        clone, _materializer, stats = workbench.clone_compatible_mob_node(
            attack2, image, source, client_image=client_image, copied_root="attack2",
        )
        frame0 = clone.get("0")
        self.assertIsInstance(frame0, workbench.WzUolProperty)
        self.assertEqual(str(frame0.value), "../stand/0")
        stand_names = [
            child.name for child in client_image.root.get("stand").children() if child.name.isdigit()
        ]
        self.assertTrue(stand_names)
        last = str(max(int(name) for name in stand_names))
        self.assertIsInstance(clone.get(last), workbench.WzUolProperty)
        self.assertEqual(str(clone.get(last).value), f"../stand/{last}")
        self.assertGreaterEqual(stats["uolsKept"], len(stand_names))
        self.assertIsNone(clone.get("info/ball"))
        self.assertIsNone(clone.get("info/type"))
        self.assertIsNone(clone.get("info/bulletSpeed"))
        self.assertIsNotNone(clone.get("info/hit/0"))
        self.assertEqual(
            (int(clone.get("info/hit/0").width), int(clone.get("info/hit/0").height)),
            (107, 88),
        )
        extracted = workbench.find_extracted_ms_mob("8880100")
        if extracted is not None:
            self.assertIsNotNone(clone.get("info/range/lt"))
            self.assertEqual(int(clone.get("info/attackAfter").value), 30)
        hit0 = clone.get("info/hit/0")
        self.assertIsInstance(hit0.child("origin"), workbench.WzVectorProperty)
        self.assertEqual((int(hit0.child("origin").x), int(hit0.child("origin").y)), (50, 46))
        self.assertEqual(int(hit0.child("delay").value), 90)
        self.assertIsNone(clone.get("info/hit/attach"))

        attack1 = image.root.get("attack1")
        attack1_clone, _, _ = workbench.clone_compatible_mob_node(
            attack1, image, source, client_image=client_image, copied_root="attack1",
        )
        self.assertEqual(int(attack1_clone.get("info/type").value), 3)
        self.assertEqual(int(attack1_clone.get("info/effectAfter").value), 0)
        self.assertEqual(int(attack1_clone.get("info/range/areaCount").value), 9)
        self.assertEqual(int(attack1_clone.get("info/range/attackCount").value), 6)
        self.assertEqual(int(attack1_clone.get("info/range/start").value), -4)
        self.assertIsNone(attack1_clone.get("info/onlyFsm"))

        attack3 = image.root.get("attack3")
        attack3_clone, _, _ = workbench.clone_compatible_mob_node(
            attack3, image, source, client_image=client_image, copied_root="attack3",
        )
        self.assertEqual(int(attack3_clone.get("info/type").value), 3)
        self.assertIsNotNone(attack3_clone.get("info/hit/0"))
        self.assertGreater(int(attack3_clone.get("info/hit/0").width), 1)
        self.assertIsNone(attack3_clone.get("info/randDelayAttack"))
        self.assertEqual(int(attack3_clone.get("info/range/areaCount").value), 11)

        warning = image.root.get("attack3/info/areaWarning")
        source_names = sorted(int(child.name) for child in warning.children() if child.name.isdigit())
        warning_clone, _, warning_stats = workbench.clone_compatible_mob_node(
            warning, image, source, client_image=client_image, copied_root="attack3/info/areaWarning",
        )
        names = [int(child.name) for child in warning_clone.children() if child.name.isdigit()]
        self.assertEqual(names, list(range(len(source_names) + 1)))
        self.assertEqual(len(names), len(source_names) + 1)
        self.assertEqual((int(warning_clone.get("0").width), int(warning_clone.get("0").height)), (1, 1))
        self.assertGreater(int(warning_clone.get("1").width), 4)
        self.assertNotIn(53, names)
        self.assertGreater(warning_stats["densified"], 0)

    def test_mob_copy_info_from_canvas_uses_companion_and_projects_skills(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        if not source.is_file():
            self.skipTest("Damien 8880100 Canvas is unavailable")
        canvas = workbench.load_image(source)
        self.assertIsNone(canvas.root.get("info"))
        nodes, info = workbench.flatten_img(source)
        self.assertTrue(info.get("canvasStore"))
        self.assertIn("info", nodes)
        self.assertTrue(nodes["info"].get("logicalSource"))

        companion_info = workbench.companion_logical_node(source, "info")
        self.assertIsInstance(companion_info, workbench.WzSubProperty)
        clone, _, _ = workbench.clone_compatible_mob_node(
            companion_info, canvas, source,
            client_image=workbench._verified_img_from_bytes(
                Path("8880110.img"),
                subprocess.check_output(["git", "cat-file", "blob", "HEAD:clien/Data/Mob/8880110.img"]),
            ),
            copied_root="info",
            dest_mob_id="8880110",
        )
        self.assertEqual(int(clone.get("firstAttack").value), 1)
        self.assertIsNone(clone.get("publicReward"))
        self.assertEqual(int(clone.get("skill/0/skill").value), 100)
        self.assertEqual(int(clone.get("skill/1/skill").value), 101)
        self.assertEqual(int(clone.get("skill/2/skill").value), 123)
        self.assertEqual(int(clone.get("skill/3/skill").value), 128)
        self.assertEqual(int(clone.get("speed").value), 0)
        self.assertIsNone(clone.get("skill/0/skillForbid"))
        self.assertIsInstance(clone.get("maxHP"), workbench.WzIntProperty)
        self.assertIsNone(clone.get("attack"))
        self.assertIsNone(clone.get("firstAttackRange"))
        self.assertIsNone(clone.get("mobType"))
        self.assertIsInstance(clone.get("PDDamage"), workbench.WzIntProperty)
        self.assertIsInstance(clone.get("MDDamage"), workbench.WzIntProperty)

        empty = workbench._verified_img_from_bytes(Path("empty.img"), workbench.empty_gms_img_bytes())
        tms_info = workbench.WzSubProperty("info")
        tms_info.add(workbench.WzIntProperty("level", 210, tms_info))
        tms_info.add(workbench.WzIntProperty("maxHP", 1000, tms_info))
        tms_info.add(workbench.WzIntProperty("PADamage", 22000, tms_info))
        tms_info.add(workbench.WzIntProperty("MADamage", 24000, tms_info))
        tms_info.add(workbench.WzIntProperty("PDRate", 300, tms_info))
        source_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), tms_info)
        source_image = workbench._verified_img_from_bytes(Path("8880100.img"), source_data)
        filled, _, _ = workbench.clone_compatible_mob_node(
            source_image.root.get("info"), source_image, Path("TMS/Mob/8880100.img"),
            client_image=empty, copied_root="info", dest_mob_id="8880110",
        )
        self.assertEqual(int(filled.get("PDDamage").value), 0)
        self.assertEqual(int(filled.get("MDDamage").value), 0)

    def test_mob_info_placeholder_maxhp_falls_back_to_int_max(self) -> None:
        source_image = workbench._verified_img_from_bytes(
            Path("source.img"), workbench.empty_gms_img_bytes(),
        )
        source = workbench.WzSubProperty("info")
        source.add(workbench.WzStringProperty("maxHP", "??????", source))
        source.add(workbench.WzIntProperty("level", 200, source))
        empty = workbench._verified_img_from_bytes(Path("empty.img"), workbench.empty_gms_img_bytes())
        projected, _, _ = workbench.clone_compatible_mob_node(
            source, source_image, Path("TMS/Mob/9910004.img"), client_image=empty, copied_root="info",
        )
        self.assertEqual(int(projected.get("maxHP").value), workbench._CLIENT_MAXHP_INT)
        self.assertIsInstance(projected.get("maxHP"), workbench.WzIntProperty)

        existing = workbench.WzSubProperty("info")
        existing.add(workbench.WzIntProperty("maxHP", 10000, existing))
        existing_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), existing)
        target = workbench._verified_img_from_bytes(Path("target.img"), existing_data)
        inherited, _, _ = workbench.clone_compatible_mob_node(
            source, source_image, Path("TMS/Mob/9910004.img"), client_image=target, copied_root="info",
        )
        self.assertEqual(int(inherited.get("maxHP").value), 10000)

    def test_validate_copied_mob_info_allows_ballistic_attack_without_body_frames(self) -> None:
        info = workbench.WzSubProperty("info")
        info.add(workbench.WzIntProperty("maxHP", 50000, info))
        info.add(workbench.WzIntProperty("level", 100, info))
        for name in ("PADamage", "PDDamage", "MADamage", "MDDamage"):
            info.add(workbench.WzIntProperty(name, 0, info))
        attack2 = workbench.WzSubProperty("attack2")
        attack_info = workbench.WzSubProperty("info", attack2)
        attack_info.add(workbench.WzIntProperty("type", 2, attack_info))
        ball = workbench.WzSubProperty("ball", attack_info)
        ball.add(workbench.WzSubProperty("0", ball))
        attack_info.add(ball)
        attack2.add(attack_info)
        data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), info)
        data = workbench.arc.append_property_record(data, (), attack2)
        image = workbench._verified_img_from_bytes(Path("8880110.img"), data)
        workbench.validate_copied_mob_info(image)

        empty_attack = workbench.WzSubProperty("attack1")
        empty_attack.add(workbench.WzSubProperty("info", empty_attack))
        broken = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), info)
        broken = workbench.arc.append_property_record(broken, (), empty_attack)
        with self.assertRaisesRegex(ValueError, "attack1 没有动作帧"):
            workbench.validate_copied_mob_info(
                workbench._verified_img_from_bytes(Path("broken.img"), broken),
            )

    def test_fsm_only_attack_projects_stand_uols_not_origin_zero_stub(self) -> None:
        source_image = workbench._verified_img_from_bytes(
            Path("source.img"), workbench.empty_gms_img_bytes(),
        )
        attack = workbench.WzSubProperty("attack2")
        info = workbench.WzSubProperty("info", attack)
        info.add(workbench.WzIntProperty("onlyFsm", 1, info))
        info.add(workbench.WzIntProperty("attackAfter", 30, info))
        attack.add(info)
        attack.add(workbench._legacy_stub_canvas("0", attack))
        stand = workbench.WzSubProperty("stand")
        stand.add(workbench._legacy_stub_canvas("0", stand))
        stand.add(workbench._legacy_stub_canvas("1", stand))
        client = workbench._verified_img_from_bytes(
            Path("8880110.img"),
            workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), stand),
        )
        clone, _, stats = workbench.clone_compatible_mob_node(
            attack, source_image, Path("TMS/Mob/8880100.img"),
            client_image=client, copied_root="attack2",
        )
        self.assertIsInstance(clone.get("0"), workbench.WzUolProperty)
        self.assertEqual(str(clone.get("0").value), "../stand/0")
        self.assertEqual(str(clone.get("1").value), "../stand/1")
        self.assertIsNone(clone.get("info/onlyFsm"))
        self.assertGreaterEqual(stats["uolsKept"], 2)

    def test_ballistic_attack_without_body_keeps_stub_not_stand_uol(self) -> None:
        source_image = workbench._verified_img_from_bytes(
            Path("source.img"), workbench.empty_gms_img_bytes(),
        )
        attack = workbench.WzSubProperty("attack2")
        info = workbench.WzSubProperty("info", attack)
        ball = workbench.WzSubProperty("ball", info)
        ball.add(workbench._legacy_stub_canvas("0", ball))
        info.add(ball)
        attack.add(info)
        stand = workbench.WzSubProperty("stand")
        stand.add(workbench._legacy_stub_canvas("0", stand))
        client = workbench._verified_img_from_bytes(
            Path("8880110.img"),
            workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), stand),
        )
        clone, _, stats = workbench.clone_compatible_mob_node(
            attack, source_image, Path("TMS/Mob/8641002.img"),
            client_image=client, copied_root="attack2",
        )
        frame0 = clone.get("0")
        self.assertIsInstance(frame0, workbench.WzCanvasProperty)
        self.assertEqual((int(frame0.width), int(frame0.height)), (1, 1))
        self.assertEqual(int(clone.get("info/type").value), 2)
        self.assertEqual(stats["uolsKept"], 0)

    def test_fsm_only_attack_without_stand_raises(self) -> None:
        source_image = workbench._verified_img_from_bytes(
            Path("source.img"), workbench.empty_gms_img_bytes(),
        )
        attack = workbench.WzSubProperty("attack2")
        info = workbench.WzSubProperty("info", attack)
        info.add(workbench.WzIntProperty("onlyFsm", 1, info))
        attack.add(info)
        empty = workbench._verified_img_from_bytes(Path("empty.img"), workbench.empty_gms_img_bytes())
        with self.assertRaisesRegex(ValueError, "onlyFsm"):
            workbench.clone_compatible_mob_node(
                attack, source_image, Path("TMS/Mob/8880100.img"),
                client_image=empty, copied_root="attack2",
            )

    def test_skill2_copy_keeps_tms_timeline_uols(self) -> None:
        skill2 = workbench.WzSubProperty("skill2")
        skill2.add(workbench.WzUolProperty("0", "../skill1/0", skill2))
        skill2.add(workbench.WzUolProperty("1", "../skill1/1", skill2))
        for name, origin in (("2", (106, 653)), ("4", (111, 658))):
            frame = workbench._legacy_stub_canvas(name, skill2)
            frame._children.pop("origin", None)
            frame.add(workbench.WzVectorProperty("origin", origin[0], origin[1], frame))
            skill2.add(frame)
        skill2.add(workbench.WzUolProperty("3", "2", skill2))
        source_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), skill2)
        source_image = workbench._verified_img_from_bytes(Path("8880100.img"), source_data)
        stand = workbench.WzSubProperty("stand")
        stand.add(workbench._legacy_stub_canvas("0", stand))
        skill1 = workbench.WzSubProperty("skill1")
        skill1.add(workbench._legacy_stub_canvas("0", skill1))
        skill1.add(workbench._legacy_stub_canvas("1", skill1))
        client_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), stand)
        client_data = workbench.arc.append_property_record(client_data, (), skill1)
        client = workbench._verified_img_from_bytes(Path("8880110.img"), client_data)
        clone, _, stats = workbench.clone_compatible_mob_node(
            source_image.root.get("skill2"), source_image, Path("TMS/Mob/8880100.img"),
            client_image=client, copied_root="skill2",
        )
        self.assertEqual(
            sorted(int(child.name) for child in clone.children() if child.name.isdigit()),
            [0, 1, 2, 3, 4],
        )
        self.assertEqual(str(clone.get("0").value), "../skill1/0")
        self.assertIsInstance(clone.get("2"), workbench.WzCanvasProperty)
        self.assertEqual(str(clone.get("3").value), "../skill2/2")
        self.assertGreaterEqual(stats["uolsKept"], 3)

        empty = workbench._verified_img_from_bytes(Path("empty.img"), workbench.empty_gms_img_bytes())
        with self.assertRaisesRegex(ValueError, "skill1"):
            workbench.clone_compatible_mob_node(
                source_image.root.get("skill2"), source_image, Path("TMS/Mob/8880100.img"),
                client_image=empty, copied_root="skill2",
            )

        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        project_client = workbench._ROOT / "clien/Data/Mob/8880110.img"
        if source.is_file() and project_client.is_file():
            image = workbench.load_image(source)
            client_image = workbench.load_image(project_client)
            if client_image.root.get("skill1/9") is None:
                skill1 = workbench.WzSubProperty("skill1")
                for index in range(10):
                    skill1.add(workbench._legacy_stub_canvas(str(index), skill1))
                client_data = workbench.arc.append_property_record(project_client.read_bytes(), (), skill1)
                client_image = workbench._verified_img_from_bytes(Path("8880110.img"), client_data)
            tms_clone, _, stats = workbench.clone_compatible_mob_node(
                image.root.get("skill2"), image, source,
                client_image=client_image, copied_root="skill2",
            )
            names = sorted(int(child.name) for child in tms_clone.children() if child.name.isdigit())
            self.assertEqual(names, list(range(105)))
            self.assertEqual(str(tms_clone.get("0").value), "../skill1/0")
            self.assertGreater(int(tms_clone.get("10").width), 4)
            self.assertEqual(str(tms_clone.get("31").value), "../skill2/23")
            self.assertEqual(str(tms_clone.get("72").value), "../skill2/23")
            self.assertEqual(str(tms_clone.get("104").value), "../stand/7")
            self.assertGreaterEqual(stats["uolsKept"], 59)

    def test_skill4_copy_uses_skill3_outlink_not_skill1(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        if not source.is_file():
            self.skipTest("Damien 8880100 Canvas is unavailable")
        image = workbench.load_image(source)
        skill4 = image.root.get("skill4")
        self.assertIsNotNone(skill4)

        def client_with(*actions: workbench.WzSubProperty) -> workbench.WzImage:
            data = workbench.empty_gms_img_bytes()
            for action in actions:
                data = workbench.arc.append_property_record(data, (), action)
            return workbench._verified_img_from_bytes(Path("8880110.img"), data)

        skill1 = workbench.WzSubProperty("skill1")
        for index in range(10):
            skill1.add(workbench._legacy_stub_canvas(str(index), skill1))
        skill2 = workbench.WzSubProperty("skill2")
        for index in (87, 88):
            skill2.add(workbench._legacy_stub_canvas(str(index), skill2))
        skill3 = workbench.WzSubProperty("skill3")
        skill3.add(workbench._legacy_stub_canvas("0", skill3))
        skill3.add(workbench._legacy_stub_canvas("1", skill3))

        with self.assertRaisesRegex(ValueError, r"skill4/0.*skill3"):
            workbench.clone_compatible_mob_node(
                skill4, image, source, client_image=client_with(skill1, skill2), copied_root="skill4",
            )

        clone, _, stats = workbench.clone_compatible_mob_node(
            skill4, image, source,
            client_image=client_with(skill1, skill2, skill3), copied_root="skill4",
        )
        names = sorted(int(child.name) for child in clone.children() if child.name.isdigit())
        self.assertEqual(names, list(range(44)))
        self.assertEqual(str(clone.get("0").value), "../skill3/0")
        self.assertEqual(str(clone.get("1").value), "../skill3/1")
        self.assertIsInstance(clone.get("2"), workbench.WzCanvasProperty)
        self.assertEqual(str(clone.get("42").value), "../skill2/87")
        self.assertEqual(str(clone.get("43").value), "../skill2/88")
        self.assertIsNone(clone.get("44"))
        self.assertGreaterEqual(stats["uolsKept"], 4)

        project_client = workbench._ROOT / "clien/Data/Mob/8880110.img"
        if project_client.is_file():
            live = workbench.load_image(project_client)
            if live.root.get("skill3/1") is not None and live.root.get("skill2/87") is not None:
                live_clone, _, _ = workbench.clone_compatible_mob_node(
                    skill4, image, source, client_image=live, copied_root="skill4",
                )
                self.assertEqual(str(live_clone.get("0").value), "../skill3/0")
                self.assertEqual(
                    sorted(int(child.name) for child in live_clone.children() if child.name.isdigit()),
                    list(range(44)),
                )

    def test_mob_info_copy_is_generic_numeric_and_inserts_before_existing_actions(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".copy-mob-info-generic-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            client = repo / "clien/Data/Mob/9910001.img"
            server = repo / "gms-server/wz/Mob.wz/9910001.img.xml"
            source = repo / "TMS/Mob/9910001.img"
            for path in (client, server, source):
                path.parent.mkdir(parents=True, exist_ok=True)
            info = workbench.WzSubProperty("info")
            info.add(workbench.WzIntProperty("level", 100, info))
            info.add(workbench.WzStringProperty("maxHP", "12345", info))
            info.add(workbench.WzStringProperty("mobType", "7N", info))
            info.add(workbench.WzIntProperty("forcedSeperateSoul", 1, info))
            attack = workbench.WzSubProperty("attack", info)
            slot = workbench.WzSubProperty("0", attack)
            slot.add(workbench.WzIntProperty("action", 6, slot))
            attack.add(slot)
            info.add(attack)
            info.add(workbench.WzSubProperty("firstAttackRange", info))
            source.write_bytes(workbench.arc.append_property_record(
                workbench.empty_gms_img_bytes(), (), info,
            ))
            original = workbench.arc.append_property_record(
                workbench.empty_gms_img_bytes(), (), workbench.WzSubProperty("stand"),
            )
            client.write_bytes(original)
            server.write_bytes(b'<imgdir name="9910001.img">\n  <imgdir name="stand"/>\n</imgdir>\n')
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                workbench.copy_tms_node_with_server_sync(client, source, "info")
                first_hashes = (hashlib.sha256(client.read_bytes()).digest(), hashlib.sha256(server.read_bytes()).digest())
                workbench.copy_tms_node_with_server_sync(client, source, "info")
            finally:
                workbench._ROOT = original_root
            copied = workbench._verified_img_from_bytes(client, client.read_bytes())
            self.assertEqual([node.name for node in copied.root.children()], ["info", "stand"])
            self.assertEqual(int(copied.root.get("info/maxHP").value), 12345)
            self.assertIsInstance(copied.root.get("info/maxHP"), workbench.WzIntProperty)
            for forbidden in ("mobType", "attack", "firstAttackRange", "forcedSeperateSoul"):
                self.assertIsNone(copied.root.get("info/" + forbidden))
            before_records, _ = workbench.arc.raw_record_state(original)
            after_records, _ = workbench.arc.raw_record_state(client.read_bytes())
            self.assertEqual(before_records[("stand",)], after_records[("stand",)])
            self.assertEqual(
                [node.get("name") for node in workbench.ET.parse(server).getroot()],
                ["info", "stand"],
            )
            self.assertEqual(
                first_hashes,
                (hashlib.sha256(client.read_bytes()).digest(), hashlib.sha256(server.read_bytes()).digest()),
            )

    def test_mob_info_copy_rejects_existing_modern_profile_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".copy-mob-info-reject-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            client = repo / "clien/Data/Mob/9910002.img"
            server = repo / "gms-server/wz/Mob.wz/9910002.img.xml"
            source = repo / "TMS/Mob/9910002.img"
            for path in (client, server, source):
                path.parent.mkdir(parents=True, exist_ok=True)
            modern = workbench.WzSubProperty("info")
            modern.add(workbench.WzStringProperty("maxHP", "??????", modern))
            modern.add(workbench.WzSubProperty("attack", modern))
            old = workbench.arc.append_property_record(
                workbench.empty_gms_img_bytes(), (), workbench.WzSubProperty("stand"),
            )
            client.write_bytes(workbench.arc.append_property_record(old, (), modern))
            server.write_bytes(
                b'<imgdir name="9910002.img">\n  <imgdir name="stand"/>\n'
                + workbench.xml_snippet_for_node(modern, b"  ")
                + b'</imgdir>\n'
            )
            safe = workbench.WzSubProperty("info")
            safe.add(workbench.WzIntProperty("maxHP", 50000, safe))
            source.write_bytes(workbench.arc.append_property_record(
                workbench.empty_gms_img_bytes(), (), safe,
            ))
            before = (client.read_bytes(), server.read_bytes())
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                with self.assertRaisesRegex(ValueError, "info 不在首节点"):
                    workbench.copy_tms_node_with_server_sync(client, source, "info")
            finally:
                workbench._ROOT = original_root
            self.assertEqual((client.read_bytes(), server.read_bytes()), before)

    def test_mob_info_copy_never_invents_modern_skill_mapping(self) -> None:
        source_image = workbench._verified_img_from_bytes(
            Path("source.img"), workbench.empty_gms_img_bytes(),
        )
        source = workbench.WzSubProperty("info")
        source.add(workbench.WzIntProperty("maxHP", 50000, source))
        skills = workbench.WzSubProperty("skill", source)
        slot = workbench.WzSubProperty("0", skills)
        for name, value in (("skill", 170), ("level", 1), ("action", 1)):
            slot.add(workbench.WzIntProperty(name, value, slot))
        skills.add(slot)
        source.add(skills)
        empty = workbench._verified_img_from_bytes(Path("empty.img"), workbench.empty_gms_img_bytes())
        with self.assertRaisesRegex(ValueError, "目标没有可沿用"):
            workbench.clone_compatible_mob_node(
                source, source_image, Path("TMS/Mob/9910003.img"), client_image=empty, copied_root="info",
            )

        existing = workbench.WzSubProperty("info")
        existing.add(workbench.WzIntProperty("maxHP", 10000, existing))
        safe_skills = workbench.WzSubProperty("skill", existing)
        safe_slot = workbench.WzSubProperty("0", safe_skills)
        for name, value in (("skill", 120), ("level", 1), ("action", 1)):
            safe_slot.add(workbench.WzIntProperty(name, value, safe_slot))
        safe_skills.add(safe_slot)
        existing.add(safe_skills)
        existing_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), existing)
        target = workbench._verified_img_from_bytes(Path("target.img"), existing_data)
        projected, _, _ = workbench.clone_compatible_mob_node(
            source, source_image, Path("TMS/Mob/9910003.img"), client_image=target, copied_root="info",
        )
        self.assertEqual(int(projected.get("skill/0/skill").value), 120)
        self.assertEqual(int(projected.get("maxHP").value), 50000)

    def test_mob_info_damien_uses_projected_skill_table_when_target_has_none(self) -> None:
        source_image = workbench._verified_img_from_bytes(
            Path("source.img"), workbench.empty_gms_img_bytes(),
        )
        source = workbench.WzSubProperty("info")
        source.add(workbench.WzIntProperty("maxHP", 50000, source))
        skills = workbench.WzSubProperty("skill", source)
        slot = workbench.WzSubProperty("0", skills)
        for name, value in (("skill", 170), ("level", 44), ("action", 1)):
            slot.add(workbench.WzIntProperty(name, value, slot))
        skills.add(slot)
        source.add(skills)
        empty = workbench._verified_img_from_bytes(Path("empty.img"), workbench.empty_gms_img_bytes())
        projected, _, _ = workbench.clone_compatible_mob_node(
            source, source_image, Path("TMS/Mob/_Canvas/8880100.img"),
            client_image=empty, copied_root="info", dest_mob_id="8880110",
        )
        self.assertEqual(int(projected.get("skill/0/skill").value), 100)
        self.assertEqual(int(projected.get("skill/1/skill").value), 101)
        self.assertEqual(int(projected.get("skill/2/skill").value), 123)
        self.assertEqual(int(projected.get("skill/3/skill").value), 128)
        self.assertIsNone(projected.get("skill/0/skillForbid"))

        cygnus = workbench.WzSubProperty("info")
        cygnus.add(workbench.WzIntProperty("maxHP", 10000, cygnus))
        cygnus_skills = workbench.WzSubProperty("skill", cygnus)
        cygnus_slot = workbench.WzSubProperty("0", cygnus_skills)
        for name, value in (("skill", 200), ("level", 223), ("action", 2)):
            cygnus_slot.add(workbench.WzIntProperty(name, value, cygnus_slot))
        cygnus_skills.add(cygnus_slot)
        cygnus.add(cygnus_skills)
        cygnus_data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), cygnus)
        cygnus_target = workbench._verified_img_from_bytes(Path("8880110.img"), cygnus_data)
        replaced, _, _ = workbench.clone_compatible_mob_node(
            source, source_image, Path("TMS/Mob/_Canvas/8880100.img"),
            client_image=cygnus_target, copied_root="info", dest_mob_id="8880110",
        )
        self.assertEqual(int(replaced.get("skill/0/skill").value), 100)
        self.assertNotEqual(int(replaced.get("skill/0/skill").value), 200)
        self.assertEqual(int(replaced.get("PDDamage").value), 0)
        self.assertEqual(int(replaced.get("MDDamage").value), 0)

    def test_mob_info_copy_replaces_cygnus_skill_and_fills_pddamage(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".copy-mob-info-lifefactory-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            client = repo / "clien/Data/Mob/8880110.img"
            server = repo / "gms-server/wz/Mob.wz/8880110.img.xml"
            source = repo / "TMS/Mob/_Canvas/8880100.img"
            for path in (client, server, source):
                path.parent.mkdir(parents=True, exist_ok=True)
            info = workbench.WzSubProperty("info")
            info.add(workbench.WzIntProperty("level", 210, info))
            info.add(workbench.WzIntProperty("maxHP", 50000, info))
            info.add(workbench.WzIntProperty("PADamage", 22000, info))
            info.add(workbench.WzIntProperty("MADamage", 24000, info))
            info.add(workbench.WzIntProperty("PDRate", 300, info))
            info.add(workbench.WzIntProperty("MDRate", 300, info))
            skills = workbench.WzSubProperty("skill", info)
            slot = workbench.WzSubProperty("0", skills)
            for name, value in (("skill", 200), ("level", 223), ("action", 2)):
                slot.add(workbench.WzIntProperty(name, value, slot))
            skills.add(slot)
            info.add(skills)
            source.write_bytes(workbench.arc.append_property_record(
                workbench.empty_gms_img_bytes(), (), info,
            ))
            dest_info = workbench.WzSubProperty("info")
            dest_info.add(workbench.WzIntProperty("level", 190, dest_info))
            dest_info.add(workbench.WzIntProperty("maxHP", 10000, dest_info))
            dest_info.add(workbench.WzIntProperty("PADamage", 1, dest_info))
            dest_info.add(workbench.WzIntProperty("MADamage", 1, dest_info))
            dest_info.add(workbench.WzIntProperty("PDRate", 300, dest_info))
            dest_info.add(workbench.WzIntProperty("MDRate", 300, dest_info))
            dest_skills = workbench.WzSubProperty("skill", dest_info)
            dest_slot = workbench.WzSubProperty("0", dest_skills)
            for name, value in (("skill", 200), ("level", 223), ("action", 2)):
                dest_slot.add(workbench.WzIntProperty(name, value, dest_slot))
            dest_skills.add(dest_slot)
            dest_info.add(dest_skills)
            data = workbench.arc.append_property_record(workbench.empty_gms_img_bytes(), (), dest_info)
            stand = workbench.WzSubProperty("stand")
            stand.add(workbench._legacy_stub_canvas("0", stand))
            data = workbench.arc.append_property_record(data, (), stand)
            for name in ("skill1", "skill2"):
                action = workbench.WzSubProperty(name)
                action.add(workbench._legacy_stub_canvas("0", action))
                data = workbench.arc.append_property_record(data, (), action)
            client.write_bytes(data)
            server.write_bytes(
                b'<imgdir name="8880110.img">\n'
                + workbench.xml_snippet_for_node(dest_info, b"  ")
                + workbench.xml_snippet_for_node(stand, b"  ")
                + b'  <imgdir name="skill1"/>\n  <imgdir name="skill2"/>\n'
                + b'</imgdir>\n'
            )
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                workbench.copy_tms_node_with_server_sync(client, source, "info")
            finally:
                workbench._ROOT = original_root
            copied = workbench._verified_img_from_bytes(client, client.read_bytes())
            self.assertEqual(int(copied.root.get("info/PDDamage").value), 0)
            self.assertEqual(int(copied.root.get("info/MDDamage").value), 0)
            self.assertEqual(int(copied.root.get("info/skill/0/skill").value), 100)
            self.assertEqual(int(copied.root.get("info/skill/1/skill").value), 101)
            self.assertEqual(int(copied.root.get("info/PDRate").value), 0)
            self.assertEqual(int(copied.root.get("info/MDRate").value), 0)
            self.assertIsNone(copied.root.get("info/skill/2"))
            xml_root = workbench.ET.parse(server).getroot()
            xml_info = next(child for child in xml_root if child.get("name") == "info")
            xml_skill = next(child for child in xml_info if child.get("name") == "skill")
            self.assertEqual(
                [slot.find("int[@name='skill']").get("value") for slot in xml_skill],
                ["100", "101"],
            )

    def test_mob_copy_keeps_companion_uols_when_target_exists_in_a(self) -> None:
        source = workbench._TMS_DATA / "Mob/_Canvas/8880100.img"
        project_client = workbench._ROOT / "clien/Data/Mob/8880110.img"
        if not source.is_file() or not project_client.is_file():
            self.skipTest("Damien Canvas or 8880110 baseline is unavailable")
        image = workbench.load_image(source)
        client_image = workbench.load_image(project_client)
        self.assertIsNotNone(client_image.root.get("stand/0"))
        attack = image.root.get("attack1")
        clone, _materializer, stats = workbench.clone_compatible_mob_node(
            attack, image, source, client_image=client_image, copied_root="attack1",
        )
        self.assertGreaterEqual(stats["uolsKept"], 8)
        uols = [child for child in clone.children() if isinstance(child, workbench.WzUolProperty)]
        self.assertGreaterEqual(len(uols), 8)
        self.assertIn("../stand/0", [str(child.value).replace("\\", "/") for child in uols])
        self.assertTrue(all(child.name.isdigit() for child in clone.children() if child.name != "info"))
        digit_names = sorted(int(child.name) for child in clone.children() if child.name.isdigit())
        self.assertEqual(digit_names, list(range(len(digit_names))))
        self.assertNotIn("_outlink", [child.name for child in clone.get("0").children()] if clone.get("0") else [])

        synthetic = workbench.companion_uol_property(source, "attack1/35")
        self.assertIsInstance(synthetic, workbench.WzUolProperty)
        kept, _materializer, uol_stats = workbench.clone_compatible_mob_node(
            synthetic, image, source, client_image=client_image, copied_root="attack1/35",
        )
        self.assertIsInstance(kept, workbench.WzUolProperty)
        self.assertEqual(str(kept.value), "../stand/0")
        self.assertGreaterEqual(uol_stats["uolsKept"], 1)

        with tempfile.TemporaryDirectory(prefix=".copy-attack1-uol-", dir=workbench._HERE) as directory:
            repo = Path(directory)
            client = repo / "clien/Data/Mob/8880110.img"
            server = repo / "gms-server/wz/Mob.wz/8880110.img.xml"
            client.parent.mkdir(parents=True)
            server.parent.mkdir(parents=True)
            client.write_bytes(project_client.read_bytes())
            server.write_bytes((workbench._ROOT / "gms-server/wz/Mob.wz/8880110.img.xml").read_bytes())
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                result = workbench.copy_tms_node_with_server_sync(client, source, "attack1")
            finally:
                workbench._ROOT = original_root
            self.assertGreaterEqual(result["uolsKept"], 8)
            copied_attack = workbench.load_image(client).root.get("attack1")
            uols = [
                child for child in copied_attack.children()
                if isinstance(child, workbench.WzUolProperty)
            ]
            self.assertTrue(uols)
            self.assertIn("../stand/0", [str(child.value).replace("\\", "/") for child in uols])

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


class MobRealResourceTests(unittest.TestCase):
    """TMS 怪物帧多为 1×1 占位：必须能解析回真实资源，并对真实资源执行复制。

    样例固定用露希妲 8880141 —— 它是典型的跨怪引用：自身帧只有占位，
    真实像素全在 ``Mob/_Canvas/8880140.img`` 里。
    """

    MOB_ID = "8880141"
    CANVAS_STORE = ("Mob", "_Canvas", "8880140.img")

    def _comparison(self) -> Path:
        options = workbench.mob_source_options(self.MOB_ID)
        source = next((item for item in options["sources"] if item["kind"] == "ms"), None)
        if source is None:
            self.skipTest("TMS Lucid MS record is unavailable")
        path = workbench.resolve_repo_path(source["path"])
        if not path.is_file():
            self.skipTest("TMS Lucid comparison source is unavailable")
        return path

    def _canvas_store(self) -> Path:
        store = workbench._TMS_DATA.joinpath(*self.CANVAS_STORE)
        if not store.is_file():
            self.skipTest("TMS Canvas store for Lucid is unavailable")
        return store

    # ── 占位帧 → 真实资源 ─────────────────────────────────────────────

    def test_cross_mob_placeholder_resolves_to_the_real_canvas_store(self) -> None:
        source = self._comparison()
        report = workbench.describe_canvas_reference(
            workbench.load_image(source), "stand/0", source,
        )
        self.assertEqual(report["state"], "linked")
        self.assertTrue(report["placeholder"])
        self.assertTrue(report["recovered"])
        self.assertEqual((report["declaredWidth"], report["declaredHeight"]), (1, 1))
        self.assertEqual(report["linkKind"], "_outlink")
        resolved = report["resolved"]
        self.assertEqual(resolved["path"], "stand/0")
        self.assertEqual(resolved["absPath"], str(self._canvas_store().resolve()))
        self.assertEqual(resolved["mobId"], "8880140")
        self.assertTrue(resolved["visible"])
        self.assertGreater(resolved["width"], workbench._PLACEHOLDER_MAX_SIZE)
        self.assertGreater(resolved["height"], workbench._PLACEHOLDER_MAX_SIZE)
        # 声明尺寸是占位，真实像素尺寸来自被引用的库文件 —— 两者必须区分开
        self.assertNotEqual(
            (resolved["width"], resolved["height"]),
            (report["declaredWidth"], report["declaredHeight"]),
        )
        self.assertTrue(report["crossMob"])
        self.assertEqual(report["hops"][0]["path"], "stand/0")

    def test_linked_frame_summary_names_file_and_cross_mob(self) -> None:
        source = self._comparison()
        summary = workbench.canvas_reference_summary(
            workbench.describe_canvas_reference(
                workbench.load_image(source), "stand/0", source,
            )
        )
        self.assertIn("占位 →", summary)
        self.assertIn("_Canvas/8880140.img", summary)
        self.assertIn("跨怪引用", summary)

    def test_orphan_placeholder_reports_no_visible_pixel_source(self) -> None:
        source = self._comparison()
        report = workbench.describe_canvas_reference(
            workbench.load_image(source), "attack1/0", source,
        )
        self.assertEqual(report["state"], "orphan")
        self.assertEqual(report["linkKind"], "")
        self.assertFalse(report["crossMob"])
        self.assertFalse(report["recovered"])
        self.assertFalse(report["resolved"]["visible"])
        self.assertIn("空占位", workbench.canvas_reference_summary(report))

    def test_unresolvable_frame_reports_error_instead_of_raising(self) -> None:
        source = self._comparison()
        report = workbench.describe_canvas_reference(
            workbench.load_image(source), "move/0", source,
        )
        self.assertEqual(report["state"], "missing")
        self.assertIsNone(report["resolved"])
        self.assertIn("引用目标不存在", report["error"])

    # ── 真实资源清单 ──────────────────────────────────────────────────

    def test_manifest_aggregates_every_frame_onto_its_real_file(self) -> None:
        source = self._comparison()
        manifest = workbench.mob_resource_manifest(workbench.load_image(source), source)
        self.assertEqual(manifest["sourceMobId"], self.MOB_ID)
        self.assertGreater(manifest["frameCount"], 0)
        self.assertEqual(manifest["frameCount"], sum(manifest["stateCounts"].values()))
        self.assertEqual(manifest["brokenPaths"], [])
        self.assertEqual(len(manifest["crossMobFiles"]), 1)
        store = manifest["crossMobFiles"][0]
        self.assertEqual(store["label"], "TMS/Data/Mob/_Canvas/8880140.img")
        self.assertTrue(store["isCanvasStore"])
        self.assertTrue(store["crossMob"])
        self.assertFalse(store["inProject"])
        self.assertEqual(store["frameCount"], manifest["stateCounts"].get("linked"))
        # 清单的主来源必须指向跨怪库文件，而不是那只全是占位的源文件
        self.assertEqual(manifest["primaryFile"]["absPath"], store["absPath"])
        frame_paths = {frame["path"] for frame in manifest["frames"]}
        self.assertTrue(set(manifest["orphanPaths"]).issubset(frame_paths))
        by_path = {frame["path"]: frame for frame in manifest["frames"]}
        self.assertEqual(by_path["stand/0"]["resolved"]["mobId"], "8880140")
        self.assertEqual(by_path["attack1/0"]["state"], "orphan")

    def test_manifest_scope_limits_to_one_action(self) -> None:
        source = self._comparison()
        manifest = workbench.mob_resource_manifest(
            workbench.load_image(source), source, node_path="stand",
        )
        self.assertEqual(manifest["scope"], "stand")
        self.assertTrue(manifest["frames"])
        self.assertEqual({frame["action"] for frame in manifest["frames"]}, {"stand"})

    def test_frame_descriptor_reports_real_pixels_for_placeholder_frames(self) -> None:
        source = self._comparison()
        descriptor = workbench.mob_frame_descriptor(source, "stand/0")
        self.assertEqual(
            (descriptor["declaredWidth"], descriptor["declaredHeight"]), (1, 1),
        )
        self.assertEqual(descriptor["state"], "linked")
        self.assertTrue(descriptor["crossMob"])
        # 舞台按真实像素对齐，否则 1×1 占位会把整只怪的动画缩成一格
        self.assertEqual(
            (descriptor["width"], descriptor["height"]),
            (descriptor["resolved"]["width"], descriptor["resolved"]["height"]),
        )
        self.assertGreater(descriptor["width"], workbench._PLACEHOLDER_MAX_SIZE)
        self.assertIn("/api/canvas?", descriptor["url"])

    def test_canvas_reference_cache_follows_file_rewrites(self) -> None:
        source = self._comparison()
        first = workbench.canvas_reference(source, "stand/0")
        self.assertEqual(first["state"], "linked")
        workbench._canvas_reference_cached.cache_clear()
        os.utime(source, None)
        second = workbench.canvas_reference(source, "stand/0")
        self.assertEqual(second["resolved"]["absPath"], first["resolved"]["absPath"])

    # ── 只读 API ──────────────────────────────────────────────────────

    def test_canvas_reference_api_returns_resolved_source(self) -> None:
        source = self._comparison()
        response = workbench.app.test_client().post(
            "/api/canvas-reference",
            json={"sourcePath": str(source), "path": "stand/0"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "linked")
        self.assertTrue(payload["crossMob"])
        self.assertIn("_Canvas/8880140.img", payload["summary"])

    def test_mob_resource_manifest_api_lists_real_files(self) -> None:
        source = self._comparison()
        response = workbench.app.test_client().post(
            "/api/mob-resource-manifest", json={"sourcePath": str(source)},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertGreater(payload["frameCount"], 0)
        self.assertEqual(len(payload["crossMobFiles"]), 1)

    def test_mob_resource_manifest_api_rejects_non_img(self) -> None:
        xml = workbench._ROOT / "gms-server/wz/Mob.wz/8880141.img.xml"
        if not xml.is_file():
            self.skipTest("Lucid server XML is unavailable")
        response = workbench.app.test_client().post(
            "/api/mob-resource-manifest", json={"sourcePath": str(xml)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    # ── 变长改写限制 ──────────────────────────────────────────────────

    def test_reference_hazard_flags_only_the_first_large_action(self) -> None:
        client = workbench._ROOT / "clien/Data/Mob/8880141.img"
        if not client.is_file():
            self.skipTest("Lucid client baseline is unavailable")
        data = client.read_bytes()
        # attack1 是文件里第一个大动作，内部内联了共享属性名，变长替换会毁掉回指
        self.assertGreater(
            workbench.img_record_reference_hazard(data, ("attack1", "0")), 1000,
        )
        self.assertEqual(workbench.img_record_reference_hazard(data, ("die1", "0")), 0)
        message = workbench.img_length_change_blocked_message("attack1/0", 1449)
        self.assertIn("不能变长改写", message)
        self.assertIn("1449", message)
        self.assertIn("旧版 IMG", message)

    # ── 对真实资源的复制 ──────────────────────────────────────────────

    def _stage_lucid_repo(self, directory: str) -> tuple[Path, Path, Path]:
        """在系统临时目录里搭一个假仓库，返回 (repo, client, server)。

        repo 必须 resolve：`relative_path` 用 ``path.resolve().relative_to(_ROOT)``，
        而 macOS 的 /var 是 /private/var 的符号链接；_ROOT 不 resolve 会让匹配失败，
        路径退化成绝对路径。
        """
        repo = Path(directory).resolve()
        client = repo / "clien/Data/Mob/8880141.img"
        server = repo / "gms-server/wz/Mob.wz/8880141.img.xml"
        client.parent.mkdir(parents=True)
        server.parent.mkdir(parents=True)
        client.write_bytes((workbench._ROOT / "clien/Data/Mob/8880141.img").read_bytes())
        server.write_bytes(
            (workbench._ROOT / "gms-server/wz/Mob.wz/8880141.img.xml").read_bytes()
        )
        return repo, client, server

    def test_copy_frame_uses_placeholder_source_and_is_incremental(self) -> None:
        source = self._comparison()
        self._canvas_store()
        if not (workbench._ROOT / "clien/Data/Mob/8880141.img").is_file():
            self.skipTest("Lucid client baseline is unavailable")
        if not (workbench._ROOT / "gms-server/wz/Mob.wz/8880141.img.xml").is_file():
            self.skipTest("Lucid server baseline is unavailable")

        with tempfile.TemporaryDirectory(
            prefix="beidou-mob-frame-copy-test-",
        ) as directory:
            repo, client, server = self._stage_lucid_repo(directory)
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                before = client.read_bytes()
                server_before = server.read_bytes()
                plan = workbench.copy_mob_frame_with_server_sync(
                    client, source, "stand/0", "die1", 0, dry_run=True,
                )
                self.assertTrue(plan["dryRun"])
                self.assertTrue(plan["changed"])
                # dry run 不写盘：modifiedFiles 必须为空，将要改的文件走 plannedFiles
                self.assertEqual(plan["modifiedFiles"], [])
                self.assertEqual(
                    plan["plannedFiles"],
                    [
                        "clien/Data/Mob/8880141.img",
                        "gms-server/wz/Mob.wz/8880141.img.xml",
                    ],
                )
                # dry run 必须完全只读
                self.assertEqual(client.read_bytes(), before)
                self.assertEqual(server.read_bytes(), server_before)
                # 计划里已给出占位背后的真实资源与真实像素尺寸
                self.assertEqual(plan["sourceState"], "linked")
                self.assertTrue(plan["sourceCrossMob"])
                self.assertEqual((plan["declaredWidth"], plan["declaredHeight"]), (1, 1))
                self.assertEqual(plan["canvas"]["formats"], ["1/0"])
                self.assertGreater(plan["canvas"]["width"], workbench._PLACEHOLDER_MAX_SIZE)
                self.assertIn("跨怪引用", plan["sourceSummary"])

                written = workbench.copy_mob_frame_with_server_sync(
                    client, source, "stand/0", "die1", 0,
                )
                self.assertEqual(written["clientOperation"], "replace")
                self.assertEqual(written["serverOperation"], "replace")
                self.assertEqual(written["canvas"]["formats"], ["1/0"])
                self.assertEqual(written["canvas"]["visible"], 1)
                self.assertEqual(
                    written["modifiedFiles"],
                    [
                        "clien/Data/Mob/8880141.img",
                        "gms-server/wz/Mob.wz/8880141.img.xml",
                    ],
                )

                after = client.read_bytes()
                self.assertGreater(written["rawScope"]["protectedRecords"], 0)
                protected = workbench.verify_img_replace_scope(
                    before, after, ("die1", "0"), label="帧替换",
                )
                self.assertEqual(protected, written["rawScope"]["protectedRecords"])
                with self.assertRaises(ValueError) as guard:
                    workbench.verify_img_replace_scope(
                        before, after, ("skill4",), label="帧替换",
                    )
                self.assertIn("帧替换", str(guard.exception))
                self.assertIn("die1", str(guard.exception))

                # 只有 die1/0 子树与它的祖先跨度变化，其余记录逐字节不变
                before_records, _ = workbench.arc.raw_record_state(before)
                after_records, _ = workbench.arc.raw_record_state(after)
                changed = {
                    path for path in set(before_records) | set(after_records)
                    if before_records.get(path) != after_records.get(path)
                }
                self.assertTrue(changed)
                for path in changed:
                    self.assertTrue(
                        path[:2] == ("die1", "0") or path[:1] == ("die1",) or path == (),
                        "/".join(path),
                    )
                self.assertTrue(
                    any(path == ("die1", "0") for path in changed), sorted(changed),
                )

                # 服务端镜像同步同一帧
                server_nodes = workbench.flatten_xml(server)[0]
                self.assertIn("die1/0", server_nodes)

                # 重复执行必须无变化（幂等）
                first_hashes = (
                    hashlib.sha256(client.read_bytes()).hexdigest(),
                    hashlib.sha256(server.read_bytes()).hexdigest(),
                )
                repeated = workbench.copy_mob_frame_with_server_sync(
                    client, source, "stand/0", "die1", 0,
                )
                self.assertFalse(repeated["changed"])
                self.assertEqual(repeated["modifiedFiles"], [])
                self.assertEqual(
                    (
                        hashlib.sha256(client.read_bytes()).hexdigest(),
                        hashlib.sha256(server.read_bytes()).hexdigest(),
                    ),
                    first_hashes,
                )
            finally:
                workbench._ROOT = original_root
                workbench._load_image_cached.cache_clear()

    def test_copy_frame_rejects_actions_that_cannot_change_length(self) -> None:
        source = self._comparison()
        if not (workbench._ROOT / "clien/Data/Mob/8880141.img").is_file():
            self.skipTest("Lucid client baseline is unavailable")
        with tempfile.TemporaryDirectory(
            prefix="beidou-mob-frame-copy-blocked-test-",
        ) as directory:
            repo, client, _server = self._stage_lucid_repo(directory)
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                before = client.read_bytes()
                with self.assertRaisesRegex(ValueError, "不能变长改写"):
                    workbench.copy_mob_frame_with_server_sync(
                        client, source, "stand/0", "attack1", 0,
                    )
                self.assertEqual(client.read_bytes(), before)
            finally:
                workbench._ROOT = original_root
                workbench._load_image_cached.cache_clear()

    def test_copy_frame_rejects_empty_placeholder_source(self) -> None:
        source = self._comparison()
        if not (workbench._ROOT / "clien/Data/Mob/8880141.img").is_file():
            self.skipTest("Lucid client baseline is unavailable")
        with tempfile.TemporaryDirectory(
            prefix=".mob-frame-copy-orphan-test-", dir=workbench._HERE,
        ) as directory:
            repo, client, _server = self._stage_lucid_repo(directory)
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                before = client.read_bytes()
                with self.assertRaisesRegex(ValueError, "空占位"):
                    workbench.copy_mob_frame_with_server_sync(
                        client, source, "attack1/0", "die1", 0,
                    )
                self.assertEqual(client.read_bytes(), before)
            finally:
                workbench._ROOT = original_root
                workbench._load_image_cached.cache_clear()

    def test_copy_frame_points_to_action_migration_when_action_is_missing(self) -> None:
        source = self._comparison()
        if not (workbench._ROOT / "clien/Data/Mob/8880141.img").is_file():
            self.skipTest("Lucid client baseline is unavailable")
        with tempfile.TemporaryDirectory(
            prefix=".mob-frame-copy-noaction-test-", dir=workbench._HERE,
        ) as directory:
            repo, client, _server = self._stage_lucid_repo(directory)
            original_root = workbench._ROOT
            workbench._ROOT = repo
            try:
                with self.assertRaisesRegex(ValueError, "动作级迁移"):
                    workbench.copy_mob_frame_with_server_sync(
                        client, source, "stand/0", "notAnAction", 0,
                    )
            finally:
                workbench._ROOT = original_root
                workbench._load_image_cached.cache_clear()


class ServerControlHelpTests(unittest.TestCase):
    def test_skill2_uses_spawn_visual_template_and_lists_8880112(self) -> None:
        from map_mob import server_control_help

        rows = [
            {"path": "info/skill/1/skill", "left": {"value": 101}},
            {"path": "info/skill/1/action", "left": {"value": 2}},
            {"path": "info/skill/1/level", "left": {"value": 1}},
            {"path": "skill2", "left": {"type": "imgdir"}},
            {"path": "attack2/info/type", "left": {"value": 2}},
            {"path": "attack2/info/ball/0", "left": {"type": "canvas"}},
        ]
        help_data = server_control_help.help_for("skill2", rows, "8880110")
        self.assertEqual(help_data["template"]["id"], "spawn_visual")
        self.assertEqual(help_data["projectedSkill"], 101)
        self.assertTrue(any(item["name"] == "8880112" for item in help_data["related"]))
        self.assertGreaterEqual(len(help_data["howToStart"]), 4)
        ballistic = server_control_help.help_for("attack2", rows, "8880110")
        self.assertEqual(ballistic["template"]["id"], "ballistic")
        self.assertEqual(ballistic["attackIndex"], 1)
        self.assertEqual(help_data["mobSkill"]["skillId"], 101)
        self.assertEqual(help_data["mobSkill"]["nodePath"], "101/level/1")
        self.assertEqual(help_data["mobSkill"]["advice"]["verdict"], "keep")
        self.assertFalse(help_data["mobSkill"]["advice"]["edit"])

        fsm_rows = [
            {"path": "attack2/info/onlyFsm", "right": {"value": 1}},
            {"path": "attack2/info/hit/0", "right": {"type": "canvas"}},
        ]
        fsm = server_control_help.help_for("attack2", fsm_rows, "8880110")
        self.assertEqual(fsm["template"]["id"], "fsm_pose")
        self.assertFalse(any(item["kind"] == "ball" for item in fsm["related"]))
        skill2 = server_control_help.help_for("skill2", rows, "8880110")
        self.assertEqual(skill2["template"]["id"], "spawn_visual")
        self.assertTrue(skill2["timeline"])
        self.assertIn("0–9", skill2["timeline"][1])
        self.assertIn("23–30", server_control_help.action_frame_meaning("skill2", "31", value="23"))
        skill4 = server_control_help.help_for("skill4", rows, "8880110")
        self.assertTrue(skill4["timeline"])
        self.assertIn("skill3", skill4["timeline"][1])
        self.assertIn("skill3/0", server_control_help.action_frame_meaning("skill4", "0"))
        info_help = server_control_help.help_for("info", rows, "8880110")
        self.assertEqual(info_help["template"]["id"], "info_copy")
        self.assertIn("PDDamage", info_help["timeline"][0])


class MobSkillResolveTests(unittest.TestCase):
    def test_maps_id_to_v83_xml_and_tms_canvas_file(self) -> None:
        from map_mob import mob_skill_resolve

        card = mob_skill_resolve.mapping_card(176, 2, 2, tms_skill_id=142, intercept=True, mob_id="8880110")
        self.assertEqual(card["typeName"], "AKAYRUM_SCREEN_CRACK_VISUAL")
        self.assertTrue(card["serverHasLevel"])
        self.assertEqual(card["nodePath"], "176/level/2")
        self.assertFalse(card["advice"]["edit"])
        self.assertTrue(card["tmsCanvas"]["exists"])
        self.assertIn("142.img", card["tmsCanvas"]["path"])

    def test_modern_tms_id_is_not_copied_into_v83_table(self) -> None:
        from map_mob import mob_skill_resolve

        card = mob_skill_resolve.mapping_card(277, 1, 1)
        self.assertEqual(card["advice"]["verdict"], "forbidden")
        self.assertFalse(card["advice"]["edit"])

    def test_hard_skin_142_is_not_damien_fsm(self) -> None:
        from map_mob import mob_skill_resolve

        card = mob_skill_resolve.mapping_card(142, 1, 2)
        self.assertEqual(card["advice"]["verdict"], "skip")
        self.assertIn("硬皮", card["advice"]["reason"])

    def test_resolve_api_returns_mapping(self) -> None:
        client = workbench.app.test_client()
        response = client.get("/api/mob-skill-resolve?skillId=176&level=2&action=2&tmsSkillId=142&intercept=1&mobId=8880110")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["nodePath"], "176/level/2")
        self.assertEqual(payload["advice"]["verdict"], "java-owns")

    def test_help_api_returns_templates(self) -> None:
        client = workbench.app.test_client()
        response = client.get("/api/server-control-help?path=skill2&mobId=8880110")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["template"]["id"], "spawn_visual")
        self.assertIn("howToStart", payload)


class FileBrowserTests(unittest.TestCase):
    def test_lists_supported_files_and_directories(self) -> None:
        result = workbench.browse_directory("gms-server/wz/Map.wz/Map/Map1")
        names = {item["name"] for item in result["items"]}
        self.assertIn("100000000.img.xml", names)
        self.assertTrue(all(item["type"] == "directory" or item["name"].lower().endswith(workbench._ALLOWED_SUFFIXES) for item in result["items"]))

    def test_rejects_directory_outside_home(self) -> None:
        with self.assertRaisesRegex(ValueError, "用户目录"):
            workbench.browse_directory("/tmp")


class WorkbenchUiTests(unittest.TestCase):
    def test_node_detail_lives_in_overlay_not_inspector_column(self) -> None:
        html = (Path(__file__).resolve().parent / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="nodeDetailDialog"', html)
        self.assertIn('class="node-detail-overlay"', html)
        self.assertIn('id="dialogCopyBtn"', html)
        self.assertLess(html.index('id="inspectorPanel"'), html.index('id="nodeDetailDialog"'))
        self.assertGreater(html.index('id="inspector"'), html.index('id="nodeDetailDialog"'))
        inspector = html[html.index('id="inspectorPanel"'):html.index('id="nodeDetailDialog"')]
        self.assertNotIn('id="inspector"', inspector)
        self.assertIn("打开节点详情", inspector)

    def test_selecting_tree_node_does_not_open_detail_dialog(self) -> None:
        script = (Path(__file__).resolve().parent / "static" / "app.js").read_text(encoding="utf-8")
        select_node = script[script.index("function selectNode(path)"):script.index("function updateNodeActions()")]
        self.assertIn("updateNodeActions();", select_node)
        self.assertNotIn('setInspectorMode("node")', select_node)
        self.assertNotIn("openNodeDetailDialog()", select_node)

    def test_writes_do_not_use_secondary_confirmation_dialogs(self) -> None:
        script = (Path(__file__).resolve().parent / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("confirm(", script)
        self.assertNotIn("dryRun: true", script[script.index("async function writeMobFrame"):])


if __name__ == "__main__":
    unittest.main()
