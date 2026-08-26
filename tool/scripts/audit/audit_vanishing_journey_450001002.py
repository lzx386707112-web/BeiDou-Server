#!/usr/bin/env python3
"""Static audit for the legacy 450001002 map migration."""

from __future__ import annotations

import argparse
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "tool/scripts/migration/migrate_vanishing_journey_450001002.py"
SPEC = importlib.util.spec_from_file_location("vanishing_journey_450001002", MIGRATION)
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
        image = self.image(self.root / "clien/Data/Map/Map/Map4/450001002.img")
        if image is None:
            return None
        extra = {child.name for child in image.root.children()} - arc.MAP_ROOTS
        if extra:
            self.error(f"unsupported roots: {sorted(extra)}")
        info = image.root.child("info")
        if isinstance(info, WzSubProperty):
            modern = [name for name in arc.MAP_INFO_UNSUPPORTED if info.child(name) is not None]
            if modern:
                self.error(f"modern info fields remain: {sorted(modern)}")
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
            ("west00", 2, 450001000, "north00", None),
        ]
        if actual != expected:
            self.error(f"portal projection changed: {actual}")
        self.check_canvases(image.root, "Map/450001002.img")
        server = self.root / "gms-server/wz/Map.wz/Map/Map4/450001002.img.xml"
        try:
            ET.parse(server)
            if server.read_text(encoding="utf-8") != arc.image_to_xml(image, "450001002.img"):
                self.error("client/server map XML mismatch")
        except Exception as exc:
            self.error(f"cannot parse server map XML: {exc}")
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
                    self.error(f"missing asset {kind}/{name}.img/{branch}")
                elif (kind, name, branch) == ("Obj", "ReverseCity", "subway/obj/0"):
                    self.check_canvases(node, "Map/Obj/ReverseCity.img/subway/obj/0")

    def check_strings(self) -> None:
        image = self.image(self.root / "clien/Data/String/Map.img")
        if image is None or image.root.get("grandis/450001002") is None:
            self.error("missing client map string 450001002")
        for tree in ("wz", "wz-zh-CN"):
            root = ET.parse(
                self.root / f"gms-server/{tree}/String.wz/Map.img.xml"
            ).getroot()
            grandis = next((child for child in root if child.get("name") == "grandis"), None)
            if grandis is None or not any(child.get("name") == "450001002" for child in grandis):
                self.error(f"missing {tree} map string 450001002")

    def check_incremental_scope(self) -> None:
        checks = {
            "clien/Data/Map/Obj/ReverseCity.img": {("subway", "obj", "0")},
            "clien/Data/String/Map.img": {("grandis", "450001002")},
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

        source = arc.load_image(arc.SOURCE / "String/Map.img", arc.BMS_KEY)
        node = arc.source_map_string(source, migration.MAP_ID)
        if node is None:
            self.error("missing source map string 450001002")
            return
        for tree in ("wz", "wz-zh-CN"):
            relative = f"gms-server/{tree}/String.wz/Map.img.xml"
            baseline = arc.BACKUP_ROOT / relative
            if not baseline.is_file():
                self.error(f"missing XML baseline: {baseline}")
                continue
            expected = arc.append_xml_properties(
                baseline.read_text(encoding="utf-8"), ("grandis",), [node]
            )
            if (self.root / relative).read_text(encoding="utf-8") != expected:
                self.error(f"XML changed outside approved map string: {relative}")

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
        self.check_incremental_scope()
        print(f"audited map=450001002 canvases={self.canvases}")
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
