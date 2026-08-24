#!/usr/bin/env python3
"""Audit the Arcane River field migration as a closed, old-client-safe pack."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSoundProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.writer import _read_sound_payload  # noqa: E402

import migrate_arcane_river_fields as migration  # noqa: E402


CLIENT = ROOT / "clien" / "Data"
REQUIRED_MOB_INFO = set(migration.OLD_MOB_FIELDS)


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.images: dict[Path, WzImage] = {}
        self.xml: dict[Path, ET.Element] = {}
        self.canvas_count = 0
        self.dependencies = {
            "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
        }

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def image(self, path: Path) -> WzImage | None:
        if not path.exists():
            self.error(f"missing client IMG: {path.relative_to(ROOT)}")
            return None
        if path not in self.images:
            try:
                image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
                image.parse()
                self.images[path] = image
            except Exception as exc:  # noqa: BLE001
                self.error(f"client IMG parse failed: {path.relative_to(ROOT)}: {exc}")
                return None
        return self.images[path]

    def server_xml(self, path: Path) -> ET.Element | None:
        if not path.exists():
            self.error(f"missing server XML: {path.relative_to(ROOT)}")
            return None
        if path not in self.xml:
            try:
                self.xml[path] = ET.parse(path).getroot()
            except Exception as exc:  # noqa: BLE001
                self.error(f"server XML parse failed: {path.relative_to(ROOT)}: {exc}")
                return None
        return self.xml[path]

    def check_canvas_tree(self, image: WzImage, label: str) -> None:
        self.check_property_tree(image.root, label)

    def check_property_tree(self, root, label: str) -> None:
        for node, prop_path in migration.walk(root):
            if node.name in {"_outlink", "_inlink"}:
                self.error(f"linked canvas metadata remains: {label}:{prop_path}")
            if not isinstance(node, WzCanvasProperty):
                continue
            if not node.has_pixels():
                self.error(f"canvas has no pixels: {label}:{prop_path}")
                continue
            width, height = int(node.width), int(node.height)
            if int(node.format) + int(node.format2) != 1:
                self.error(f"non-ARGB4444 canvas: {label}:{prop_path}")
            if width <= 0 or height <= 0 or max(width, height) > migration.MAX_CANVAS_EDGE:
                self.error(f"invalid canvas dimensions {width}x{height}: {label}:{prop_path}")
            try:
                decode_canvas(node, region="GMS")
                self.canvas_count += 1
            except Exception as exc:  # noqa: BLE001
                self.error(f"canvas decode failed: {label}:{prop_path}: {exc}")

    @staticmethod
    def child_value(node, name: str):
        return migration.child_value(node, name)

    def merge_dependencies(self, found: dict[str, object]) -> None:
        migration.merge_dependency_sets(self.dependencies, found)

    def check_map(self, map_id: int) -> None:
        path = CLIENT / f"Map/Map/Map4/{map_id}.img"
        image = self.image(path)
        trees = ["wz"]
        if (ROOT / "gms-server/wz-zh-CN/Map.wz").exists():
            trees.append("wz-zh-CN")
        for tree in trees:
            self.server_xml(ROOT / f"gms-server/{tree}/Map.wz/Map/Map4/{map_id}.img.xml")
        if image is None:
            return
        expected_sha = migration.PINNED_CLIENT_MAP_SHA256.get(map_id)
        if expected_sha and hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            self.error(f"{map_id}: pinned client IMG SHA-256 changed")
        unexpected = {child.name for child in image.root.children()} - migration.MAP_ROOTS
        if unexpected:
            self.error(f"{map_id}: unsupported map roots {sorted(unexpected)}")
        info = image.root.child("info")
        if map_id in migration.LEGACY_MEDIA_DISABLED_MAPS and info is not None:
            for name in ("bgm", "mapMark"):
                if info.child(name) is not None:
                    self.error(f"{map_id}: legacy-stable map retains info/{name}")
        for name in migration.MAP_INFO_UNSUPPORTED:
            if info is not None and info.child(name) is not None:
                self.error(f"{map_id}: unsupported info/{name}")
        for node, prop_path in migration.walk(image.root):
            value = str(getattr(node, "value", ""))
            if "2025MysticBloom" in value:
                self.error(f"{map_id}: seasonal resource remains at {prop_path}")
        back = image.root.child("back")
        if isinstance(back, WzSubProperty):
            for entry in back.children():
                for name in migration.BACK_UNSUPPORTED:
                    if entry.child(name) is not None:
                        self.error(f"{map_id}: unsupported back field {entry.name}/{name}")
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if isinstance(objects, WzSubProperty):
                if map_id in migration.LEGACY_CONNECT_FIRST_MAPS:
                    entries = list(objects.children())
                    connect_count = sum(
                        self.child_value(entry, "oS") == "connect" for entry in entries
                    )
                    if connect_count and (
                        any(
                            self.child_value(entry, "oS") != "connect"
                            for entry in entries[:connect_count]
                        )
                        or [entry.name for entry in entries]
                        != [str(index) for index in range(len(entries))]
                    ):
                        self.error(f"{map_id}: unstable legacy connect order in layer {layer.name}")
                for entry in objects.children():
                    for name in migration.OBJ_UNSUPPORTED:
                        if entry.child(name) is not None:
                            self.error(f"{map_id}: unsupported obj field {layer.name}/{entry.name}/{name}")
                    if self.child_value(entry, "oS") == "connect" and str(
                        self.child_value(entry, "l1")
                    ) != "0":
                        self.error(
                            f"{map_id}: non-legacy connect style "
                            f"{layer.name}/{entry.name}/"
                            f"{self.child_value(entry, 'l0')}/{self.child_value(entry, 'l1')}"
                        )
        ladder_rope = image.root.child("ladderRope")
        if isinstance(ladder_rope, WzSubProperty):
            for entry in ladder_rope.children():
                if entry.child("piece") is not None:
                    self.error(f"{map_id}: unsupported ladderRope/{entry.name}/piece")
        life = image.root.child("life")
        if isinstance(life, WzSubProperty):
            for entry in life.children():
                unsupported = migration.LIFE_UNSUPPORTED | migration.LIFE_UNSUPPORTED_BY_MAP.get(
                    map_id, set()
                )
                for name in unsupported:
                    if entry.child(name) is not None:
                        self.error(f"{map_id}: unsupported life field {entry.name}/{name}")
                if self.child_value(entry, "type") == "n":
                    npc_id = int(self.child_value(entry, "id"))
                    if npc_id in migration.REMOVED_NPCS:
                        self.error(f"{map_id}: removed activity NPC {npc_id} remains")
        if map_id in migration.LEGACY_ZERO_FIELD_LIMIT_MAPS and self.child_value(
            image.root.child("info"), "fieldLimit"
        ) != 0:
            self.error(f"{map_id}: fieldLimit is not legacy-safe 0")
        foothold = image.root.child("foothold")
        if foothold is not None:
            for node, path in migration.walk(foothold):
                for name in migration.FOOTHOLD_UNSUPPORTED_BY_MAP.get(map_id, set()):
                    if node.child(name) is not None:
                        self.error(f"{map_id}: unsupported foothold field {path}/{name}")
        portal = image.root.child("portal")
        if isinstance(portal, WzSubProperty):
            for entry in portal.children():
                if int(self.child_value(entry, "pt") or 0) == 10:
                    self.error(f"{map_id}: unsupported portal type 10 at {entry.name}")
                for name in migration.PORTAL_UNSUPPORTED | {"script"}:
                    if entry.child(name) is not None:
                        self.error(f"{map_id}: unsupported portal field {entry.name}/{name}")
                target = self.child_value(entry, "tm")
                target_name = str(self.child_value(entry, "tn") or "")
                if isinstance(target, int) and target != 999999999:
                    if target not in migration.MAP_ID_SET:
                        self.error(f"{map_id}: portal {entry.name} targets absent map {target}")
                    elif target_name and target_name not in self.portal_names(target):
                        self.error(
                            f"{map_id}: portal {entry.name} targets missing portal {target}/{target_name}"
                        )
            cave_portals = [
                (name, 2, target_map, target_name)
                for name, (target_map, target_name) in migration.LEGACY_CAVE_ROUTE_PORTALS.get(
                    map_id, {}
                ).items()
            ] + [
                (name, 3, target_map, target_name)
                for name, (target_map, target_name) in migration.LEGACY_CAVE_COLLISION_PORTALS.get(
                    map_id, {}
                ).items()
            ]
            for portal_name, portal_type, target_map, target_name in cave_portals:
                entry = next(
                    (
                        node for node in portal.children()
                        if self.child_value(node, "pn") == portal_name
                    ),
                    None,
                )
                expected = {"pt": portal_type, "tm": target_map, "tn": target_name}
                actual = {
                    name: self.child_value(entry, name) if entry is not None else None
                    for name in expected
                }
                if actual != expected:
                    self.error(
                        f"{map_id}: incompatible cave portal {portal_name}: {actual}"
                    )
                xml = self.server_xml(
                    ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
                )
                xml_portal = self.xml_direct_child(xml, "portal")
                xml_entry = next(
                    (
                        node for node in xml_portal if xml_portal is not None
                        if self.xml_direct_child(node, "pn") is not None
                        and self.xml_direct_child(node, "pn").get("value") == portal_name
                    ),
                    None,
                )
                xml_actual = {
                    name: (
                        self.xml_direct_child(xml_entry, name).get("value")
                        if self.xml_direct_child(xml_entry, name) is not None
                        else None
                    )
                    for name in expected
                }
                xml_expected = {name: str(value) for name, value in expected.items()}
                if xml_actual != xml_expected:
                    self.error(
                        f"{map_id}: incompatible server cave portal {portal_name}: {xml_actual}"
                    )
        self.merge_dependencies(migration.collect_dependencies(image))
        self.check_canvas_tree(image, f"Map/{map_id}.img")

    def portal_names(self, map_id: int) -> set[str]:
        image = self.image(CLIENT / f"Map/Map/Map4/{map_id}.img")
        portal = image.root.child("portal") if image else None
        if not isinstance(portal, WzSubProperty):
            return set()
        return {
            str(self.child_value(entry, "pn"))
            for entry in portal.children()
            if self.child_value(entry, "pn") is not None
        }

    def check_assets(self) -> None:
        checked: set[tuple[Path, str]] = set()
        for (kind, name), branches in sorted(self.dependencies["assets"].items()):
            path = CLIENT / f"Map/{kind}/{name}.img"
            image = self.image(path)
            if image is None:
                continue
            for error in migration.legacy_asset_structure_errors(image, kind, name):
                self.error(f"non-contiguous legacy asset node: {error}")
            for branch in branches:
                node = image.root.get(branch)
                if node is None:
                    self.error(f"missing map asset branch: Map/{kind}/{name}.img/{branch}")
                elif (path, branch) not in checked:
                    self.check_property_tree(node, f"Map/{kind}/{name}.img/{branch}")
                    checked.add((path, branch))
        helper = self.image(CLIENT / "Map/MapHelper.img")
        if helper:
            for mark in self.dependencies["marks"]:
                node = helper.root.get(f"mark/{mark}")
                if node is None:
                    self.error(f"missing MapHelper mark/{mark}")
                else:
                    self.check_property_tree(node, f"Map/MapHelper.img/mark/{mark}")

    def check_bgms(self) -> None:
        packs: dict[str, WzImage | None] = {}
        legacy = self.image(CLIENT / "Sound/Bgm12.img")
        legacy_sound = legacy.root.get("AquaCave") if legacy else None
        for reference in sorted(self.dependencies["bgms"]):
            pack, name = reference.split("/", 1)
            if pack not in packs:
                packs[pack] = self.image(CLIENT / f"Sound/{pack}.img")
            image = packs[pack]
            sound = image.root.get(name) if image else None
            if not isinstance(sound, WzSoundProperty):
                self.error(f"missing BGM track: {reference}")
                continue
            if isinstance(legacy_sound, WzSoundProperty) and sound.header != legacy_sound.header:
                self.error(f"non-legacy Sound_DX8 header: {reference}")
            payload = _read_sound_payload(sound)
            if not migration.is_legacy_mp3_payload(payload):
                self.error(f"non-MPEG2 22.05kHz stereo 64kbps BGM payload: {reference}")

    def xml_direct_child(self, node: ET.Element | None, name: str) -> ET.Element | None:
        if node is None:
            return None
        return next((child for child in node if child.get("name") == name), None)

    def check_string(self, tree: str, img: str, item_id: int, category=None) -> None:
        root = self.server_xml(ROOT / f"gms-server/{tree}/String.wz/{img}.img.xml")
        parent = self.xml_direct_child(root, category) if category else root
        if self.xml_direct_child(parent, str(item_id)) is None:
            self.error(f"missing {tree} String/{img}: {category + '/' if category else ''}{item_id}")

    def check_client_string(self, img: str, item_id: int, category=None) -> None:
        image = self.image(CLIENT / f"String/{img}.img")
        path = f"{category}/{item_id}" if category else str(item_id)
        if image is None or image.root.get(path) is None:
            self.error(f"missing client String/{img}: {path}")

    def check_mob(self, mob_id: int) -> None:
        image = self.image(CLIENT / f"Mob/{mob_id:07d}.img")
        xml = self.server_xml(ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml")
        if image is None:
            return
        info = image.root.child("info")
        if not isinstance(info, WzSubProperty):
            self.error(f"{mob_id}: missing client info")
        else:
            missing = REQUIRED_MOB_INFO - {child.name for child in info.children()}
            if missing:
                self.error(f"{mob_id}: missing required mob info {sorted(missing)}")
            max_hp = self.child_value(info, "maxHP")
            if max_hp is None or int(max_hp) > 2_147_483_647:
                self.error(f"{mob_id}: invalid client maxHP {max_hp}")
            for name in migration.MOB_INFO_UNSUPPORTED:
                if info.child(name) is not None:
                    self.error(f"{mob_id}: unsupported mob info/{name}")
        if not any(isinstance(node, WzCanvasProperty) for node, _ in migration.walk(image.root)):
            self.error(f"{mob_id}: no materialized action frames")
        if mob_id == 8641002:
            attack = image.root.child("attack1")
            names = tuple(child.name for child in attack.children()) if attack is not None else ()
            expected = ("info", *(str(index) for index in range(16)))
            if names != expected:
                self.error(f"8641002: non-contiguous attack1 frames {names}")
        ballistic = migration.LEGACY_BALLISTIC_ATTACKS.get(mob_id)
        if ballistic is not None:
            attack_number, bullet_speed = ballistic
            attack_info = image.root.get(f"attack{attack_number}/info")
            info_names = (
                tuple(child.name for child in attack_info.children())
                if isinstance(attack_info, WzSubProperty)
                else ()
            )
            expected_info = (
                "range", "ball", "hit", "type", "attackAfter", "bulletSpeed"
            )
            if info_names != expected_info:
                self.error(f"{mob_id}: incompatible attack{attack_number}/info nodes {info_names}")
            if self.child_value(attack_info, "type") != 2:
                self.error(f"{mob_id}: attack{attack_number}/info/type is not 2")
            if self.child_value(attack_info, "bulletSpeed") != bullet_speed:
                self.error(
                    f"{mob_id}: attack{attack_number}/info/bulletSpeed is not {bullet_speed}"
                )
        xml_info = self.xml_direct_child(xml, "info")
        xml_fields = {child.get("name") for child in xml_info} if xml_info is not None else set()
        if REQUIRED_MOB_INFO - xml_fields:
            self.error(f"{mob_id}: server mob missing {sorted(REQUIRED_MOB_INFO - xml_fields)}")
        if ballistic is not None:
            attack_number, bullet_speed = ballistic
            xml_attack = self.xml_direct_child(xml, f"attack{attack_number}")
            xml_attack_info = self.xml_direct_child(xml_attack, "info")
            xml_info_names = (
                tuple(child.get("name") for child in xml_attack_info)
                if xml_attack_info is not None
                else ()
            )
            expected_info = (
                "range", "ball", "hit", "type", "attackAfter", "bulletSpeed"
            )
            if xml_info_names != expected_info:
                self.error(
                    f"{mob_id}: server attack{attack_number}/info nodes {xml_info_names}"
                )
            xml_type = self.xml_direct_child(xml_attack_info, "type")
            xml_bullet_speed = self.xml_direct_child(xml_attack_info, "bulletSpeed")
            if xml_type is None or xml_type.get("value") != "2":
                self.error(f"{mob_id}: server attack{attack_number}/info/type is not 2")
            if xml_bullet_speed is None or xml_bullet_speed.get("value") != str(bullet_speed):
                self.error(
                    f"{mob_id}: server attack{attack_number}/info/bulletSpeed is not {bullet_speed}"
                )
        self.check_canvas_tree(image, f"Mob/{mob_id:07d}.img")
        self.check_client_string("Mob", mob_id)
        for tree in ("wz", "wz-zh-CN"):
            self.check_string(tree, "Mob", mob_id)

    def check_npc(self, npc_id: int) -> None:
        image = self.image(CLIENT / f"Npc/{npc_id:07d}.img")
        if image is None:
            return
        info = image.root.child("info")
        if isinstance(info, WzSubProperty):
            for name in migration.NPC_INFO_UNSUPPORTED:
                if info.child(name) is not None:
                    self.error(f"{npc_id}: unsupported NPC info/{name}")
        for child in image.root.children():
            suffix = child.name.removeprefix(migration.NPC_ROOT_UNSUPPORTED_PREFIX)
            if child.name.startswith(migration.NPC_ROOT_UNSUPPORTED_PREFIX) and suffix.isdigit():
                self.error(f"{npc_id}: unsupported NPC root/{child.name}")
        if str(npc_id).startswith("300"):
            self.server_xml(ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml")
            self.check_canvas_tree(image, f"Npc/{npc_id:07d}.img")
            self.check_client_string("Npc", npc_id)
            self.check_string("wz", "Npc", npc_id)

    def run(self) -> int:
        if len(migration.MAP_IDS) != 155:
            self.error(f"migration whitelist changed: {len(migration.MAP_IDS)} maps")
        for map_id in migration.MAP_IDS:
            self.check_map(map_id)
            self.check_client_string("Map", map_id, "grandis")
            for tree in ("wz", "wz-zh-CN"):
                self.check_string(tree, "Map", map_id, "grandis")
        if len(self.dependencies["mobs"]) != 84:
            self.error(f"expected 84 mobs, found {len(self.dependencies['mobs'])}")
        if len(self.dependencies["npcs"]) > 186:
            self.error(f"expected at most 186 retained NPCs, found {len(self.dependencies['npcs'])}")
        if len(self.dependencies["bgms"]) != 16:
            self.error(f"expected 16 BGM tracks, found {len(self.dependencies['bgms'])}")
        self.check_assets()
        self.check_bgms()
        for mob_id in sorted(self.dependencies["mobs"]):
            self.check_mob(mob_id)
        for npc_id in sorted(self.dependencies["npcs"]):
            self.check_npc(npc_id)
        print(
            f"audited maps={len(migration.MAP_IDS)} mobs={len(self.dependencies['mobs'])} "
            f"npcs={len(self.dependencies['npcs'])} bgms={len(self.dependencies['bgms'])} "
            f"asset_files={len(self.dependencies['assets'])} canvases={self.canvas_count}"
        )
        for warning in self.warnings:
            print(f"WARN: {warning}")
        for error in self.errors:
            print(f"ERROR: {error}")
        print(f"result: errors={len(self.errors)} warnings={len(self.warnings)}")
        return 1 if self.errors else 0


if __name__ == "__main__":
    raise SystemExit(Audit().run())
