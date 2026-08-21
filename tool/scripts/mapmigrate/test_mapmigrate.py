#!/usr/bin/env python3
"""Targeted contracts for the read-only map/Boss migration workbench."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import web_app  # noqa: E402
import compat  # noqa: E402
from wzpy.properties import WzLongProperty  # noqa: E402


class MapMigrateComparisonTest(unittest.TestCase):
    def test_flip_children_expose_modern_node_and_resource_tags(self):
        nodes = [
            {"name": "flip", "path": "flip", "type": "imgdir", "status": "review",
             "reason": "根级 flip 动作容器在现代 Boss 中常见。"},
            {"name": "effect", "path": "flip/effect", "type": "imgdir", "status": "ok", "reason": ""},
            {"name": "3", "path": "flip/effect/3", "type": "canvas", "status": "incompatible",
             "reason": "Canvas 格式不兼容。", "format": 2050, "format2": 0},
        ]
        web_app.annotate_modern_tags(nodes)
        self.assertEqual(nodes[1]["modernTags"], [
            {"kind": "node", "label": "flip", "path": "flip"},
        ])
        self.assertEqual(nodes[2]["modernTags"], [
            {"kind": "node", "label": "flip", "path": "flip"},
            {"kind": "resource", "label": "纹理 2050/0", "path": "flip/effect/3"},
        ])

    def test_texture_metrics_detect_limit_and_project_origin(self):
        metrics = web_app.texture_metrics({
            "width": 4096,
            "height": 1024,
            "payloadBytes": 12345,
            "origin": {"x": 2000, "y": 512},
        })
        self.assertTrue(metrics["overLimit"])
        self.assertEqual((metrics["suggestedWidth"], metrics["suggestedHeight"]), (2048, 512))
        self.assertEqual(metrics["suggestedOrigin"], {"x": 1000, "y": 256})
        self.assertEqual(metrics["argb4444Bytes"], 4096 * 1024 * 2)
        self.assertEqual(metrics["rgbaBytes"], 4096 * 1024 * 4)
        self.assertEqual((metrics["potWidth"], metrics["potHeight"]), (4096, 1024))

    def test_field_limit_uses_evidence_values_not_an_incorrect_threshold(self):
        known_modern = {"name": "fieldLimit", "parent_name": "info", "path": "info/fieldLimit", "type": "int", "value": 1_048_576}
        proven_karing = {**known_modern, "value": 1_909_496}
        self.assertEqual(compat.evaluate(known_modern, "map").status, "modern")
        self.assertIsNone(compat.action_for(compat.evaluate(known_modern, "map"), known_modern))
        self.assertEqual(compat.evaluate(proven_karing, "map").status, "ok")

    def test_modern_projection_rules_cover_links_canvas_and_extended_fields(self):
        outlink = {"name": "_outlink", "parent_name": "0", "path": "stand/0/_outlink", "type": "string", "value": "Mob/_Canvas/1.img/stand/0"}
        canvas = {"name": "0", "parent_name": "stand", "path": "stand/0", "type": "canvas", "format": 4098, "format2": 0, "width": 32, "height": 32}
        portal = {"name": "hRange", "parent_name": "0", "path": "portal/0/hRange", "type": "int", "value": 80}
        attack = {"name": "attack", "parent_name": "info", "path": "info/attack", "type": "imgdir"}
        spine = {"name": "spineAnchors", "parent_name": "0", "path": "0/obj/0/spineAnchors", "type": "imgdir"}
        self.assertEqual(compat.evaluate(outlink, "boss").status, "incompatible")
        self.assertEqual(compat.evaluate(canvas, "boss").status, "incompatible")
        self.assertEqual(compat.evaluate(portal, "map").status, "modern")
        self.assertEqual(compat.evaluate(attack, "boss").status, "incompatible")
        self.assertEqual(compat.evaluate(spine, "map").status, "incompatible")
        self.assertIsNone(compat.action_for(compat.evaluate(attack, "boss"), attack))

    def test_identical_boss_keeps_full_details_and_canvas_digest(self):
        mob = ROOT / "clien/Data/Mob/0100100.img"
        result = web_app.analyze(mob, "boss", mob)

        self.assertEqual(result["comparison"]["changed"], 0)
        self.assertEqual(result["comparison"]["source_only"], 0)
        self.assertEqual(result["comparison"]["reference_only"], 0)
        self.assertEqual(result["comparison"]["same"], result["comparison"]["total"])

        canvas = next(node for node in result["flat"] if node["type"] == "canvas")
        self.assertEqual(canvas["compareStatus"], "same")
        self.assertEqual(len(canvas["pixelSha256"]), 64)
        self.assertEqual(canvas["sourceNode"]["pixelSha256"], canvas["referenceNode"]["pixelSha256"])
        self.assertEqual(canvas["sourceNode"]["status"], "ok")
        self.assertEqual(canvas["referenceNode"]["status"], "ok")
        self.assertIn("format", canvas["sourceNode"])
        self.assertIn("origin", canvas["referenceNode"])

    def test_different_maps_return_changed_and_one_sided_nodes(self):
        source = ROOT / "clien/Data/Map/Map/Map0/000000000.img"
        reference = ROOT / "clien/Data/Map/Map/Map0/000000001.img"
        result = web_app.analyze(source, "map", reference)

        comparison = result["comparison"]
        self.assertGreater(comparison["changed"], 0)
        self.assertGreater(comparison["source_only"], 0)
        self.assertGreater(comparison["reference_only"], 0)
        changed = next(node for node in result["flat"] if node["compareStatus"] == "changed")
        self.assertIsNotNone(changed["sourceNode"])
        self.assertIsNotNone(changed["referenceNode"])
        reference_only = next(node for node in result["flat"] if node["compareStatus"] == "reference_only")
        self.assertIsNone(reference_only["sourceNode"])
        self.assertIsNotNone(reference_only["referenceNode"])

    def test_long_values_are_visible_to_compatibility_rules(self):
        self.assertEqual(web_app.meta_of(WzLongProperty("maxHP", 3_000_000_000)), {
            "type": "int",
            "value": 3_000_000_000,
        })

    def test_full_tree_rewrite_is_disabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PermissionError, "整树序列化"):
                web_app.require_full_rewrite_enabled()

    def test_missing_reference_is_reported_instead_of_silently_ignored(self):
        client = web_app.app.test_client()
        response = client.get(
            "/api/load",
            query_string={
                "mode": "map",
                "img_path": "clien/Data/Map/Map/Map0/000000000.img",
                "reference_img_path": "clien/Data/Map/Map/Map0/not-present.img",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("找不到对照", response.get_json()["reason"])

    def test_json_report_contains_the_same_two_sided_comparison(self):
        client = web_app.app.test_client()
        response = client.post("/api/report", json={
            "mode": "boss",
            "img_path": "clien/Data/Mob/0100100.img",
            "reference_img_path": "clien/Data/Mob/0100101.img",
            "format": "json",
        })
        self.assertEqual(response.status_code, 200)
        report = response.get_json()["report"]
        self.assertIn('"comparisonNodes"', report)
        self.assertIn('"sourceNode"', report)
        self.assertIn('"referenceNode"', report)
        self.assertIn('"textureSummary"', report)
        self.assertIn('"textures"', report)

    @unittest.skipUnless(
        (web_app.MS_IMG_DATA_DIR / "Map/Map/Map5/555003400.img").is_file()
        and (web_app.MS_IMG_DATA_DIR / "Map/Map/Map5/_Canvas/555003400.img").is_file(),
        "real TMS loose Map and _Canvas corpus are unavailable",
    )
    def test_real_loose_map_resolves_sibling_canvas(self):
        source = web_app.MS_IMG_DATA_DIR / "Map/Map/Map5/555003400.img"
        client = web_app.app.test_client()
        response = client.get("/api/load", query_string={
            "mode": "map",
            "img_path": str(source),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            Path(payload["canvasPath"]),
            source.parent / "_Canvas" / source.name,
        )
        canvas = next(node for node in payload["flat"] if node["path"] == "miniMap/canvas")
        self.assertEqual((canvas["width"], canvas["height"]), (1, 1))
        self.assertGreater(canvas["resolvedCanvas"]["width"], 1)
        self.assertGreater(canvas["resolvedCanvas"]["height"], 1)
        textures = payload["summary"]["textures"]
        self.assertEqual(textures["count"], 1)
        self.assertEqual(textures["overLimit"], 0)
        self.assertEqual((textures["maxWidth"], textures["maxHeight"]), (90, 56))
        self.assertEqual(textures["argb4444Bytes"], 90 * 56 * 2)
        report_response = client.post("/api/report", json={
            "mode": "map",
            "img_path": str(source),
            "canvas_img_path": payload["canvasPath"],
            "format": "json",
        })
        report = json.loads(report_response.get_json()["report"])
        self.assertEqual((report["textureSummary"]["maxWidth"], report["textureSummary"]["maxHeight"]), (90, 56))
        self.assertEqual(report["textures"][0]["sourceEntry"], "Map/Map/Map5/_Canvas/555003400.img")

    @unittest.skipUnless(
        web_app.MSPROBE_DLL.is_file()
        and Path(web_app.DOTNET_BIN).exists()
        and (web_app.MSPACKS_DIR / "Mob_00000.ms").is_file()
        and (web_app.MS_IMG_DATA_DIR / "Mob/_Canvas/0100100.img").is_file(),
        "real TMS MS metadata and _Canvas corpus are unavailable",
    )
    def test_real_ms_metadata_resolves_loose_canvas_and_decodes_preview(self):
        client = web_app.app.test_client()
        response = client.get("/api/load", query_string={
            "mode": "boss",
            "ms_pack": str(web_app.MSPACKS_DIR / "Mob_00000.ms"),
            "ms_entry": "Mob/0100100.img",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(
            Path(payload["msCanvasPath"]),
            web_app.MS_IMG_DATA_DIR / "Mob/_Canvas/0100100.img",
        )
        outlink = next(node for node in payload["flat"] if node["path"] == "move/0/_outlink")
        self.assertEqual(outlink["status"], "incompatible")
        canvas = next(node for node in payload["flat"] if node["path"] == "move/0")
        self.assertEqual((canvas["width"], canvas["height"]), (1, 1))
        self.assertGreater(canvas["resolvedCanvas"]["width"], 1)
        self.assertGreater(canvas["resolvedCanvas"]["height"], 1)
        self.assertEqual(canvas["resolvedCanvas"]["status"], "ok")
        paths = {node["path"] for node in payload["flat"]}
        linked_canvases = sum(
            node["type"] == "canvas" and f'{node["path"]}/_outlink' in paths
            for node in payload["flat"]
        )
        self.assertEqual(payload["resolvedCanvases"], linked_canvases)
        preview = client.get("/api/canvas.png", query_string={
            "img_path": payload["imgPath"],
            "canvas_img_path": payload["msCanvasPath"],
            "path": "move/0",
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data[:8], b"\x89PNG\r\n\x1a\n")
        scaled = client.get("/api/canvas.png", query_string={
            "img_path": payload["imgPath"],
            "canvas_img_path": payload["msCanvasPath"],
            "path": "move/0",
            "max_texture": 16,
        })
        self.assertEqual(scaled.status_code, 200)
        width = int.from_bytes(scaled.data[16:20], "big")
        height = int.from_bytes(scaled.data[20:24], "big")
        self.assertEqual(max(width, height), 16)
        self.assertEqual(scaled.headers["X-Canvas-Original-Size"], "37x26")
        self.assertEqual(scaled.headers["X-Canvas-Preview-Size"], f"{width}x{height}")
        self.assertEqual(scaled.headers["X-Canvas-Preview-Only"], "1")


if __name__ == "__main__":
    unittest.main()
