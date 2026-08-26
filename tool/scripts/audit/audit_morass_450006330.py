#!/usr/bin/env python3
"""Static compatibility audit for the Morass 450006330 migration."""

from __future__ import annotations

import argparse
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "tool/scripts/migration/migrate_morass_450006330.py"
SPEC = importlib.util.spec_from_file_location("morass_450006330", MIGRATION)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MIGRATION}")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)
arc = migration.arc

from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


class Audit:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.errors: list[str] = []
        self.canvases = 0

    def error(self, message: str) -> None:
        self.errors.append(message)

    def image(self, path: Path):
        try:
            image = arc.load_image(path, arc.GMS_KEY)
            if image.truncated or image.parse_warnings:
                self.error(f"malformed IMG {path}: {image.parse_warnings}")
            return image
        except Exception as exc:
            self.error(f"cannot parse {path}: {exc}")
            return None

    def check_canvases(self, node, label: str) -> None:
        for child, path in arc.walk(node):
            if not isinstance(child, WzCanvasProperty):
                continue
            self.canvases += 1
            if (int(child.format), int(child.format2)) != (1, 0):
                self.error(f"non-ARGB4444 Canvas {label}/{path}")
            if child.child("_outlink") is not None or child.child("_inlink") is not None:
                self.error(f"unmaterialized Canvas link {label}/{path}")
            try:
                decoded = decode_canvas(child, region="GMS")
                if decoded.size != (int(child.width), int(child.height)):
                    self.error(f"decoded size mismatch {label}/{path}")
            except Exception as exc:
                self.error(f"Canvas decode failed {label}/{path}: {exc}")

    def check_map(self):
        client_path = self.root / "clien/Data/Map/Map/Map4/450006330.img"
        image = self.image(client_path)
        if image is None:
            return None
        if {child.name for child in image.root.children()} - arc.MAP_ROOTS:
            self.error("450006330 retains unsupported root nodes")
        info = image.root.child("info")
        if isinstance(info, WzSubProperty):
            modern = [name for name in arc.MAP_INFO_UNSUPPORTED if info.child(name) is not None]
            if modern:
                self.error(f"450006330 retains modern info fields: {sorted(modern)}")
        dependencies = arc.collect_dependencies(image)
        if dependencies != migration.expected_dependencies():
            self.error(f"dependency closure changed: {dependencies}")
        portal = image.root.child("portal")
        actual = [
            (
                arc.child_value(entry, "pn"), arc.child_value(entry, "pt"),
                arc.child_value(entry, "tm"), arc.child_value(entry, "tn"),
                arc.child_value(entry, "script"),
            )
            for entry in portal.children()
        ] if isinstance(portal, WzSubProperty) else []
        expected = [
            ("sp", 0, 999999999, "", None),
            ("inv_00", 1, 999999999, "", None),
            ("door00", 1, 999999999, "", None),
            ("west00", 2, 450006320, "east00", None),
        ]
        if actual != expected:
            self.error(f"450006330 portal projection changed: {actual}")
        self.check_canvases(image.root, "Map/450006330.img")
        server = self.root / "gms-server/wz/Map.wz/Map/Map4/450006330.img.xml"
        try:
            ET.parse(server)
            if server.read_text(encoding="utf-8") != arc.image_to_xml(image, "450006330.img"):
                self.error("450006330 client/server XML mismatch")
        except Exception as exc:
            self.error(f"cannot parse server 450006330 XML: {exc}")
        return dependencies

    def check_dependencies(self, dependencies) -> None:
        if dependencies is None:
            return
        for kind, name in dependencies["assets"]:
            image = self.image(self.root / f"clien/Data/Map/{kind}/{name}.img")
            if image is None:
                continue
            for branch in sorted(dependencies["assets"][(kind, name)]):
                node = image.root.get(branch)
                if node is None:
                    self.error(f"missing map asset {kind}/{name}.img/{branch}")
                elif branch in {"closedArea/gate/0", "closedArea/gate/1"}:
                    self.check_canvases(node, f"Map/{kind}/{name}.img/{branch}")
        for npc_id in sorted(dependencies["npcs"]):
            image = self.image(self.root / f"clien/Data/Npc/{npc_id}.img")
            if image is None:
                continue
            self.check_canvases(image.root, f"Npc/{npc_id}.img")
            server = self.root / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
            try:
                ET.parse(server)
                if server.read_text(encoding="utf-8") != arc.image_to_xml(image, f"{npc_id}.img"):
                    self.error(f"NPC {npc_id} client/server XML mismatch")
            except Exception as exc:
                self.error(f"cannot parse server NPC {npc_id}: {exc}")

    def check_strings(self) -> None:
        checks = (("Map", "grandis", {450006330}), ("Npc", None, migration.VISIBLE_NPCS))
        for img_name, category, ids in checks:
            image = self.image(self.root / f"clien/Data/String/{img_name}.img")
            for item_id in sorted(ids):
                path = f"{category}/{item_id}" if category else str(item_id)
                if image is None or image.root.get(path) is None:
                    self.error(f"missing client String/{img_name}.img/{path}")
            for tree in ("wz", "wz-zh-CN"):
                root = ET.parse(self.root / f"gms-server/{tree}/String.wz/{img_name}.img.xml").getroot()
                parent = root if category is None else next(
                    (child for child in root if child.get("name") == category), None
                )
                for item_id in sorted(ids):
                    if parent is None or not any(child.get("name") == str(item_id) for child in parent):
                        self.error(f"missing {tree} String/{img_name}.img/{item_id}")

    def check_raw_scope(self) -> None:
        checks = {
            "clien/Data/Map/Obj/morass.img": {
                ("closedArea", "gate"),
            },
            "clien/Data/String/Map.img": {("grandis", "450006330")},
            "clien/Data/String/Npc.img": {
                ("3003540",), ("3003577",), ("3003578",)
            },
        }
        for relative, approved in checks.items():
            baseline = arc.BACKUP_ROOT / relative
            current = self.root / relative
            if not baseline.is_file():
                self.error(f"missing raw-record baseline: {baseline}")
                continue
            try:
                arc.verify_raw_record_scope(
                    baseline.read_bytes(), current.read_bytes(), approved,
                    allow_additions=True,
                )
            except Exception as exc:
                self.error(f"raw-record scope failed for {relative}: {exc}")

    def check_xml_scope(self) -> None:
        checks = (("Map", "grandis", {450006330}), ("Npc", None, migration.VISIBLE_NPCS))
        for tree in ("wz", "wz-zh-CN"):
            for img_name, category, ids in checks:
                relative = f"gms-server/{tree}/String.wz/{img_name}.img.xml"
                baseline = arc.BACKUP_ROOT / relative
                current = self.root / relative
                if not baseline.is_file():
                    self.error(f"missing XML baseline: {baseline}")
                    continue
                source_path = arc.SOURCE / f"String/{img_name}.img"
                source = arc.load_image(source_path, arc.BMS_KEY)
                additions = []
                for item_id in sorted(ids):
                    node = (
                        arc.source_map_string(source, item_id)
                        if img_name == "Map"
                        else source.root.get(str(item_id))
                    )
                    if node is None:
                        self.error(f"missing source String/{img_name}.img/{item_id}")
                    else:
                        additions.append(node)
                try:
                    expected = arc.append_xml_properties(
                        baseline.read_text(encoding="utf-8"),
                        (category,) if category else (), additions,
                    )
                    if current.read_text(encoding="utf-8") != expected:
                        self.error(f"XML changed outside approved additions: {relative}")
                except Exception as exc:
                    self.error(f"XML scope check failed for {relative}: {exc}")

    def run(self) -> int:
        migration.configure(self.root)
        try:
            migration.verify_source()
            migration.verify_known_states(self.root, require_final=True)
        except Exception as exc:
            self.error(str(exc))
        dependencies = self.check_map()
        self.check_dependencies(dependencies)
        self.check_strings()
        self.check_raw_scope()
        self.check_xml_scope()
        print(f"audited map=450006330 npcs=3 canvases={self.canvases}")
        for message in self.errors:
            print(f"ERROR: {message}")
        print(f"result: errors={len(self.errors)}")
        return 1 if self.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    return Audit(args.root.resolve()).run()


if __name__ == "__main__":
    raise SystemExit(main())
