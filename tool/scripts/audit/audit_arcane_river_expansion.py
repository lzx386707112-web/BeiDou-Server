#!/usr/bin/env python3
"""Audit the Reverse City, Sellas, and non-boss Tenebris migration."""

from __future__ import annotations

import importlib.util
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzSoundProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.writer import _read_sound_payload  # noqa: E402


EXPECTED = {"maps": 132, "assets": 29, "mobs": 53, "npcs": 114, "bgms": 17, "marks": 7}
ACTUAL_BOSS_MOBS = {
    8645009, 8645039, 8645045, 8645046, 8645047, 8645048, 8645049,
    8645050, 8645064, 8645065, 8645066, 8645067, 8645068,
    *range(8880500, 8880550),
}
ALLOWED_STORY_BOSS_FLAG_MOBS = {8645051, 8645053, 8645057, 8645058}


def direct_xml_child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node if child.get("name") == name), None)


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.canvas_count = 0
        self.dependencies = {
            "assets": defaultdict(set), "mobs": set(), "npcs": set(),
            "bgms": set(), "marks": set(),
        }
        self._images = {}
        self._xml = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def image(self, path: Path):
        if path not in self._images:
            if not path.is_file():
                self.error(f"missing IMG: {path.relative_to(ROOT)}")
                self._images[path] = None
            else:
                try:
                    image = migration.load_image(path, migration.GMS_KEY)
                    if image.truncated or image.parse_warnings:
                        self.error(
                            f"malformed IMG {path.relative_to(ROOT)}: "
                            f"{image.truncated=} {image.parse_warnings=}"
                        )
                    self._images[path] = image
                except Exception as exc:
                    self.error(f"cannot parse IMG {path.relative_to(ROOT)}: {exc}")
                    self._images[path] = None
        return self._images[path]

    def xml(self, path: Path) -> ET.Element | None:
        if path not in self._xml:
            try:
                self._xml[path] = ET.parse(path).getroot()
            except Exception as exc:
                self.error(f"cannot parse XML {path.relative_to(ROOT)}: {exc}")
                self._xml[path] = None
        return self._xml[path]

    def check_canvas(
        self, canvas: WzCanvasProperty, label: str, require_materialized: bool
    ) -> None:
        self.canvas_count += 1
        if require_materialized and (
            canvas.child("_outlink") is not None or canvas.child("_inlink") is not None
        ):
            self.error(f"unmaterialized Canvas link: {label}")
        if (int(canvas.format), int(canvas.format2)) != (1, 0):
            self.error(
                f"non-ARGB4444 Canvas {label}: "
                f"{int(canvas.format)}/{int(canvas.format2)}"
            )
        try:
            decoded = decode_canvas(canvas, region="GMS")
            if decoded.size != (int(canvas.width), int(canvas.height)):
                self.error(f"decoded Canvas size mismatch: {label}")
        except Exception as exc:
            self.error(f"cannot decode Canvas {label}: {exc}")

    def check_tree(self, node, label: str, require_materialized: bool = True) -> None:
        for child, path in migration.walk(node):
            if isinstance(child, WzCanvasProperty):
                self.check_canvas(child, f"{label}/{path}", require_materialized)

    def check_string(self, img_name: str, item_id: int, category: str | None = None) -> None:
        client = self.image(ROOT / f"clien/Data/String/{img_name}.img")
        path = f"{category}/{item_id}" if category else str(item_id)
        if client is None or client.root.get(path) is None:
            self.error(f"missing client String/{img_name}.img/{path}")
        for tree in ("wz", "wz-zh-CN"):
            root = self.xml(ROOT / f"gms-server/{tree}/String.wz/{img_name}.img.xml")
            parent = direct_xml_child(root, category) if category else root
            if direct_xml_child(parent, str(item_id)) is None:
                self.error(f"missing {tree} String/{img_name}.img/{path}")

    def check_map(self, map_id: int) -> None:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = self.image(path)
        if image is None:
            return
        roots = {child.name for child in image.root.children()}
        extra = roots - migration.MAP_ROOTS
        if extra:
            self.error(f"{map_id}: unsupported roots {sorted(extra)}")
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            self.error(f"{map_id}: missing info")
        else:
            modern = {name for name in migration.MAP_INFO_UNSUPPORTED if info.child(name) is not None}
            if modern:
                self.error(f"{map_id}: unsupported info fields {sorted(modern)}")
        portal = image.root.child("portal")
        if isinstance(portal, WzSubProperty):
            by_name = {}
            for entry in portal.children():
                name = str(migration.child_value(entry, "pn") or "")
                by_name[name] = entry
                script = migration.child_value(entry, "script")
                portal_type = int(migration.child_value(entry, "pt") or 0)
                target = migration.child_value(entry, "tm")
                if script:
                    self.error(f"{map_id}/{name}: retained portal script {script}")
                if portal_type > 6:
                    self.error(f"{map_id}/{name}: unsupported portal type {portal_type}")
                if isinstance(target, int) and target not in (
                    {999999999} | migration.MAP_ID_SET | migration.INSTALLED_ROUTE_MAP_IDS
                ):
                    self.error(f"{map_id}/{name}: target outside installed closure {target}")
            for name, (target, target_name) in migration.LEGACY_CAVE_ROUTE_PORTALS.get(
                map_id, {}
            ).items():
                entry = by_name.get(name)
                actual = (
                    migration.child_value(entry, "pt"),
                    migration.child_value(entry, "tm"),
                    migration.child_value(entry, "tn"),
                ) if entry is not None else None
                if actual != (2, target, target_name):
                    self.error(f"{map_id}/{name}: route projection is {actual}")
        migration.merge_dependency_sets(self.dependencies, migration.collect_dependencies(image))
        self.check_tree(image.root, f"Map/Map4/{map_id}.img")
        server_path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        if self.xml(server_path) is not None:
            expected = migration.image_to_xml(image, f"{map_id}.img")
            if server_path.read_text(encoding="utf-8") != expected:
                self.error(f"{map_id}: client/server map semantic XML mismatch")
        self.check_string("Map", map_id, "grandis")

    def check_assets(self) -> None:
        checked = set()
        for (kind, name), branches in sorted(self.dependencies["assets"].items()):
            image = self.image(ROOT / f"clien/Data/Map/{kind}/{name}.img")
            if image is None:
                continue
            for branch in sorted(branches):
                node = image.root.get(branch)
                if node is None:
                    self.error(f"missing map asset branch: {kind}/{name}.img/{branch}")
                elif (kind, name, branch) not in checked:
                    self.check_tree(
                        node,
                        f"Map/{kind}/{name}.img/{branch}",
                        require_materialized=(kind, name) in migration.NEW_STANDALONE_ASSETS,
                    )
                    checked.add((kind, name, branch))
        helper = self.image(ROOT / "clien/Data/Map/MapHelper.img")
        if helper is not None:
            for mark in sorted(self.dependencies["marks"]):
                node = helper.root.get(f"mark/{mark}")
                if node is None:
                    self.error(f"missing MapHelper mark/{mark}")
                else:
                    self.check_tree(node, f"MapHelper.img/mark/{mark}")

    def check_mobs(self) -> None:
        if self.dependencies["mobs"] & ACTUAL_BOSS_MOBS:
            self.error(f"boss mobs entered dependency closure: {sorted(self.dependencies['mobs'] & ACTUAL_BOSS_MOBS)}")
        for mob_id in sorted(self.dependencies["mobs"]):
            image = self.image(ROOT / f"clien/Data/Mob/{mob_id}.img")
            server = self.xml(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml")
            if image is None:
                continue
            info = image.root.child("info")
            if not isinstance(info, WzSubProperty):
                self.error(f"{mob_id}: missing info")
            else:
                if migration.child_value(info, "eva") != 100:
                    self.error(f"{mob_id}: legacy eva is not 100")
                if migration.child_value(info, "boss") and mob_id not in ALLOWED_STORY_BOSS_FLAG_MOBS:
                    self.error(f"{mob_id}: unexpected boss flag in normal-map dependency")
            xml_info = direct_xml_child(server, "info")
            xml_eva = direct_xml_child(xml_info, "eva")
            if xml_eva is None or xml_eva.get("value") != "100":
                self.error(f"{mob_id}: server eva is not 100")
            has_canvas = any(
                isinstance(node, WzCanvasProperty) for node, _ in migration.walk(image.root)
            )
            link = migration.child_value(info, "link") if info is not None else None
            if not has_canvas and str(link) not in {str(value) for value in self.dependencies["mobs"]}:
                self.error(f"{mob_id}: has neither action Canvas nor installed info/link")
            self.check_tree(
                image.root,
                f"Mob/{mob_id}.img",
                require_materialized=mob_id not in migration.REUSED_MOB_IDS,
            )
            self.check_string("Mob", mob_id)
        projectile = self.image(ROOT / "clien/Data/Mob/8644709.img")
        projectile_info = projectile.root.get("attack1/info") if projectile is not None else None
        if migration.child_value(projectile_info, "type") != 2:
            self.error("8644709: missing legacy projectile type=2")
        if projectile_info is not None and projectile_info.child("bulletSpeed") is not None:
            self.error("8644709: invented bulletSpeed not present in TMS source")

    def check_npcs(self) -> None:
        for npc_id in sorted(self.dependencies["npcs"]):
            image = self.image(ROOT / f"clien/Data/Npc/{npc_id}.img")
            self.xml(ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml")
            if image is not None:
                self.check_tree(image.root, f"Npc/{npc_id}.img")
            self.check_string("Npc", npc_id)

    def check_bgms(self) -> None:
        for reference in sorted(self.dependencies["bgms"]):
            pack, name = reference.split("/", 1)
            image = self.image(ROOT / f"clien/Data/Sound/{pack}.img")
            sound = image.root.child(name) if image is not None else None
            if not isinstance(sound, WzSoundProperty):
                self.error(f"missing BGM {reference}")
                continue
            payload = _read_sound_payload(sound)
            decoded = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-f", "mp3", "-i", "pipe:0", "-f", "null", "-",
                ],
                input=payload, capture_output=True, check=False,
            )
            if decoded.returncode != 0:
                self.error(f"undecodable MP3 payload: {reference}")
            if pack != "Bgm49" and not migration.is_legacy_mp3_payload(payload):
                self.error(f"non-legacy MP3 payload: {reference}")

    def check_raw_binary_scope(self) -> None:
        checks = {
            "clien/Data/Map/MapHelper.img": {
                ("mark", mark) for mark in self.dependencies["marks"]
            },
            "clien/Data/Map/Tile/allInvisibleTile.img": {
                (branch.split("/", 1)[0],)
                for branch in self.dependencies["assets"][("Tile", "allInvisibleTile")]
            },
            "clien/Data/Sound/Bgm48.img": {("Outpost",)},
            "clien/Data/Sound/Bgm54.img": {
                (reference.split("/", 1)[1],)
                for reference in self.dependencies["bgms"]
                if reference.startswith("Bgm54/")
            },
            "clien/Data/String/Map.img": {
                ("grandis", str(map_id)) for map_id in migration.MAP_IDS
            },
            "clien/Data/String/Mob.img": {
                (str(mob_id),) for mob_id in self.dependencies["mobs"]
            },
            "clien/Data/String/Npc.img": {
                (str(npc_id),)
                for npc_id in self.dependencies["npcs"]
                if str(npc_id).startswith("300")
            },
        }
        for mob_id in migration.REUSED_MOB_IDS:
            checks[f"clien/Data/Mob/{mob_id}.img"] = {("info", "eva")}
        for relative, approved in checks.items():
            baseline = migration.BACKUP_ROOT / relative
            current = migration.ROOT / relative
            if not baseline.is_file():
                self.error(f"missing raw-record baseline: {baseline}")
                continue
            try:
                migration.verify_raw_record_scope(
                    baseline.read_bytes(),
                    current.read_bytes(),
                    approved,
                    allow_additions=not relative.startswith("clien/Data/Mob/864501"),
                )
            except Exception as exc:
                self.error(f"raw-record scope failed for {relative}: {exc}")

    def run(self) -> int:
        try:
            migration.verify_preserved_files()
            migration.verify_shared_file_states(require_final=True)
        except Exception as exc:
            self.error(str(exc))
        for map_id in migration.MAP_IDS:
            self.check_map(map_id)
        actual = {
            "maps": len(migration.MAP_IDS),
            "assets": len(self.dependencies["assets"]),
            "mobs": len(self.dependencies["mobs"]),
            "npcs": len(self.dependencies["npcs"]),
            "bgms": len(self.dependencies["bgms"]),
            "marks": len(self.dependencies["marks"]),
        }
        if actual != EXPECTED:
            self.error(f"dependency counts changed: {actual}, expected {EXPECTED}")
        self.check_assets()
        self.check_mobs()
        self.check_npcs()
        self.check_bgms()
        self.check_raw_binary_scope()
        print(f"audited {actual} canvases={self.canvas_count}")
        for message in self.errors:
            print(f"ERROR: {message}")
        print(f"result: errors={len(self.errors)}")
        return 1 if self.errors else 0


if __name__ == "__main__":
    raise SystemExit(Audit().run())
