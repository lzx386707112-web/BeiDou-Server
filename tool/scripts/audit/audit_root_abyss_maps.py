#!/usr/bin/env python3
"""Audit TMS Root Abyss map migration resources.

This checks the map-only migration boundary: TMS 1052 maps, map assets, NPCs,
reactors, scripts, and old-client ARGB4444 canvas compatibility.
"""

from __future__ import annotations

import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzStringProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


CLIENT = ROOT / "clien" / "Data"
SRC_CLIENT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
SERVER_WZ = ROOT / "gms-server" / "wz"
DROP_MIGRATION = ROOT / "gms-server/src/main/resources/db/migration/V2.1.23__add_root_abyss_normal_mob_drops.sql"
BOSS_DROP_MIGRATION = ROOT / "gms-server/src/main/resources/db/migration/V2.1.24__add_root_abyss_boss_drops.sql"
SOURCE_MAP_IDS = sorted(int(p.stem) for p in (SRC_CLIENT / "Map/Map/Map1").glob("1052*.img"))
MAP_IDS = sorted(int(p.stem) for p in (CLIENT / "Map/Map/Map1").glob("1052*.img"))
NORTH_GARDEN_MAP_IDS = {105200400, 105200800}
NORMAL_MOBS = {7120110, 7120111, 7120112, 7120113, 7120114, 7120115, 9834610}
NORMAL_BOSS_MOBS = {
    8900100,
    8910100,
    8920101,
    8930100,
}
ROOT_ABYSS_BOSS_ROOM_SPAWNS = {
    105200110: (8910100, 489, 454),
    105200210: (8900100, -131, 550),
    105200310: (8920101, 60, 134),
    105200410: (8930100, -192, 442),
    105200510: (8910000, 489, 454),
    105200610: (8900000, -131, 550),
    105200710: (8920000, 60, 134),
    105200810: (8930000, -192, 442),
}
DIRECT_BOSS_MOBS = {mob_id for mob_id, _x, _y in ROOT_ABYSS_BOSS_ROOM_SPAWNS.values()}
ADVANCED_BOSS_MOBS = {
    8900000,
    8910000,
    8920000, 8920001,
    8930000,
}
BOSS_GAUGE_MOBS = {
    8900000, 8900100,
    8910000, 8910100,
    8920000, 8920001, 8920101,
    8930000, 8930100,
}
VELLUM_COMPAT_MOBS = {8930000, 8930100}
VELLUM_MAX_ATTACK_FRAME_WIDTH = 960
VELLUM_MAX_ATTACK_FRAME_HEIGHT = 720
ADVANCED_BOSS_DROP_MOBS = {8900000, 8910000, 8920000, 8930000}
NORMAL_BOSS_DROP_MOBS = {8900100, 8910100, 8920101, 8930100}
OLD_SERVER_REQUIRED_BOSS_INFO_FIELDS = {"PADamage", "PDDamage", "MADamage", "MDDamage", "level"}
ROOT_ABYSS_SECOND_PHASE_BOSS_HP = {
    8920001: 3_000_000_000,
}
SUPPORTED_ROOT_ABYSS_BOSS_SKILLS = {
    (110, 5),
    (120, 3), (120, 5), (120, 8),
    (121, 4),
    (122, 10),
    (123, 1),
    (127, 2),
    (128, 1), (128, 3), (128, 16),
    (131, 3), (131, 12), (131, 13),
    (134, 2),
    (141, 4),
    (142, 1),
    (145, 1), (145, 2),
    (170, 11), (170, 13), (170, 14),
    (184, 1),
    (186, 1),
    (191, 1), (191, 2),
    (201, 40), (201, 47), (201, 48), (201, 49), (201, 51), (201, 52), (201, 53),
    (203, 1),
}
SERVER_DRIVEN_ROOT_ABYSS_BOSS_SKILLS = {
    (170, 11), (170, 13), (170, 14),
    (184, 1),
    (186, 1),
    (191, 1), (191, 2),
    (201, 40), (201, 47), (201, 48), (201, 49), (201, 51), (201, 52), (201, 53),
    (203, 1),
}
NPCS = {
    1064002, 1064003, 1064005, 1064006, 1064007, 1064008,
    1064009,
    1064012, 1064013, 1064014, 1064015, 1064032,
    3007007, 3007008, 9091004, 9091021, 9091023,
}
STRING_ONLY_NPCS = {1064031}
ROOT_ABYSS_QUESTS = {30000, *range(30002, 30023), 30027}
ROOT_ABYSS_ITEMS = {4001755, 4001756}
REMOVED_LIFE_FIELDS = {"forcedZPage", "forcedZMass", "limitedname"}
REACTORS = {
    1058016, 1058017, 1058018, 1058019, 1058020, 1058021, 1058022, 1058023,
    1058024, 1058025, 1058026, 1058027, 1058028, 1058029,
}
ALLOWED_MAP_MARKS = {"None"}
SCRIPT_PORTAL_TARGETS = {
    "rootabyssGardenOut": (105200000, "sp"),
    "rootabyssOUT": (105040300, "sp"),
    "rootaNext1": (105200210, "sp"),
    "rootaNext2": (105200310, "sp"),
    "outrootaBoss": (105200000, "sp"),
    "rootaNext": (105200110, "sp"),
}
DOOR_SELECT_SCRIPTS = {
    "rootafirstDoor": ("rootaFirstDoorSelect", 105200100, 105200500),
    "rootasecondDoor": ("rootaSecondDoorSelect", 105200200, 105200600),
    "rootathirdDoor": ("rootaThirdDoorSelect", 105200300, 105200700),
    "rootaforthDoor": ("rootaFourthDoorSelect", 105200400, 105200800),
}
REMOVED_INFO_FIELDS = {
    "standAlone", "partyStandAlone", "noMapCmd", "fieldScript",
    "onFirstUserEnter", "onUserEnter",
    "AmbientBGM", "AmbientBGMv", "ableMapleAuction", "abilityPresetBlock",
    "fieldLimit2", "limitUpgradeItem", "noBackOverlapped", "noChair",
    "qrLimitState", "qrLimitState2",
    "ReviveCurFieldOfNoTransfer", "ReviveCurFieldOfNoTransferPoint",
    "ReviveCurFieldOfNoTransferNotDamaged",
}
REMOVED_OBJ_FIELDS = {"hide", "reactor", "flow"}
REMOVED_PORTAL_FIELDS = {"delay", "hideTooltip", "onlyOnce"}


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.cache: dict[Path, WzImage] = {}
        self.source_cache: dict[Path, WzImage] = {}
        self.canvas_count = 0

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def client_img(self, rel: str | Path) -> WzImage | None:
        path = CLIENT / rel
        if not path.exists():
            self.error(f"missing client IMG: {path.relative_to(ROOT)}")
            return None
        if path not in self.cache:
            try:
                img = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
                img.parse()
            except Exception as exc:  # noqa: BLE001
                self.error(f"client IMG parse failed: {path.relative_to(ROOT)}: {exc}")
                return None
            self.cache[path] = img
        return self.cache[path]

    def source_img(self, rel: str | Path) -> WzImage | None:
        path = SRC_CLIENT / rel
        if not path.exists():
            self.error(f"missing source IMG: {path}")
            return None
        if path not in self.source_cache:
            try:
                img = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("BMS"), name=path.name)
                img.parse()
            except Exception as exc:  # noqa: BLE001
                self.error(f"source IMG parse failed: {path}: {exc}")
                return None
            self.source_cache[path] = img
        return self.source_cache[path]

    def server_xml(self, rel: str | Path) -> ET.Element | None:
        path = SERVER_WZ / rel
        if not path.exists():
            self.error(f"missing server XML: {path.relative_to(ROOT)}")
            return None
        try:
            return ET.parse(path).getroot()
        except Exception as exc:  # noqa: BLE001
            self.error(f"server XML parse failed: {path.relative_to(ROOT)}: {exc}")
            return None

    def child_value(self, node, name: str):
        child = node.child(name) if node is not None else None
        return getattr(child, "value", None)

    def xml_int_children(self, node: ET.Element) -> dict[str, int]:
        values: dict[str, int] = {}
        for child in node:
            if child.tag == "int" and child.get("name") and child.get("value") is not None:
                values[child.get("name")] = int(child.get("value"))
        return values

    def has_foothold_below(self, root: ET.Element, x: int, y: int) -> bool:
        start_y = y - 1
        for node in root.iter("imgdir"):
            values = self.xml_int_children(node)
            if {"x1", "y1", "x2", "y2"} <= values.keys():
                x1, y1, x2, y2 = values["x1"], values["y1"], values["x2"], values["y2"]
                if min(x1, x2) <= x <= max(x1, x2):
                    floor_y = y1 if x1 == x2 else y1 + ((y2 - y1) * (x - x1) / (x2 - x1))
                    if floor_y >= start_y:
                        return True
        return False

    def has_server_string(self, img_name: str, item_id: int) -> bool:
        root = self.server_xml(f"String.wz/{img_name}.img.xml")
        return root is not None and any(child.get("name") == str(item_id) for child in root)

    def decode_canvases(self, rel: str | Path) -> None:
        img = self.client_img(rel)
        if img is None:
            return
        self.decode_canvas_tree(rel, img.root)

    def decode_canvas_tree(self, label: str | Path, root) -> None:
        def walk(node, path: str) -> None:
            if isinstance(node, WzStringProperty) and node.name in {"_outlink", "_inlink"}:
                self.error(f"modern canvas link remains: {label}:{path} -> {node.value}")
            if isinstance(node, WzCanvasProperty) and node.has_pixels():
                canvas_format = int(node.format) + int(node.format2)
                if canvas_format != 1 or int(node.format2) != 0:
                    self.error(f"canvas is not ARGB4444: {label}:{path} format={canvas_format} format2={node.format2}")
                try:
                    decode_canvas(node, region="GMS")
                    self.canvas_count += 1
                except Exception as exc:  # noqa: BLE001
                    self.error(f"canvas decode failed: {label}:{path}: {exc}")
            if hasattr(node, "children"):
                for child in node.children():
                    walk(child, f"{path}/{child.name}" if path else child.name)

        walk(root, "")

    def check_no_transparent_canvas_regressions(self, rel: str | Path) -> None:
        target = self.client_img(rel)
        source = self.source_img(rel)
        if target is None or source is None:
            return

        def target_is_placeholder(node: WzCanvasProperty) -> bool:
            try:
                image = decode_canvas(node, region="GMS")
            except Exception:
                return False
            return image.size == (1, 1) and image.getbbox() is None

        def source_is_visible(node: WzCanvasProperty) -> bool:
            try:
                image = decode_canvas(node, region="BMS")
            except Exception:
                return False
            return image.size != (1, 1) and image.getbbox() is not None

        def walk(node, path: str) -> None:
            if isinstance(node, WzCanvasProperty) and node.has_pixels() and target_is_placeholder(node):
                source_node = source.get(path)
                if isinstance(source_node, WzCanvasProperty) and source_node.has_pixels() and source_is_visible(source_node):
                    self.error(f"transparent 1x1 regression: {rel}:{path}")
            if hasattr(node, "children"):
                for child in node.children():
                    walk(child, f"{path}/{child.name}" if path else child.name)

        walk(target.root, "")

    def check_map_counts(self) -> None:
        server_maps = sorted(int(p.stem.split(".")[0]) for p in (SERVER_WZ / "Map.wz/Map/Map1").glob("1052*.img.xml"))
        if MAP_IDS != SOURCE_MAP_IDS:
            self.error(f"client 1052 map list must match TMS source: source={len(SOURCE_MAP_IDS)} client={len(MAP_IDS)}")
        if server_maps != MAP_IDS:
            self.error(f"server/client 1052 map list mismatch: client={len(MAP_IDS)} server={len(server_maps)}")

    def check_map(self, map_id: int) -> None:
        rel = Path(f"Map/Map/Map1/{map_id}.img")
        img = self.client_img(rel)
        self.server_xml(f"Map.wz/Map/Map1/{map_id}.img.xml")
        if img is None:
            return

        bgm = self.child_value(img.get("info"), "bgm")
        if isinstance(bgm, str) and "/" in bgm:
            pack, name = bgm.split("/", 1)
            sound = self.client_img(Path("Sound") / f"{pack}.img")
            if sound is None or sound.get(name) is None:
                self.error(f"{map_id}: missing BGM {bgm}")

        mark = self.child_value(img.get("info"), "mapMark")
        if mark and mark not in ALLOWED_MAP_MARKS:
            helper = self.client_img("Map/MapHelper.img")
            if helper is None or helper.get(f"mark/{mark}") is None:
                self.error(f"{map_id}: missing mapMark mark/{mark}")

        info = img.get("info")
        if info is not None:
            for field in REMOVED_INFO_FIELDS:
                if field == "onUserEnter" and map_id in ROOT_ABYSS_BOSS_ROOM_SPAWNS:
                    continue
                if info.child(field) is not None:
                    self.error(f"{map_id}: high-version info field remains: {field}")
            on_user_enter = self.child_value(info, "onUserEnter")
            if map_id in ROOT_ABYSS_BOSS_ROOM_SPAWNS and on_user_enter not in (None, "rootaBossEnter"):
                self.error(f"{map_id}: boss room has unexpected onUserEnter script {on_user_enter}")
            forced_return = self.child_value(info, "forcedReturn")
            if forced_return == 910000000:
                self.error(f"{map_id}: forcedReturn still points to Free Market")

        root = self.server_xml(f"Map.wz/Map/Map1/{map_id}.img.xml")
        if map_id in ROOT_ABYSS_BOSS_ROOM_SPAWNS and root is not None:
            info_xml = root.find("./imgdir[@name='info']")
            on_enter_xml = info_xml.find("./string[@name='onUserEnter']") if info_xml is not None else None
            if on_enter_xml is not None and on_enter_xml.get("value") != "rootaBossEnter":
                self.error(f"{map_id}: server XML boss room has unexpected onUserEnter {on_enter_xml.get('value')}")
            mob_id, x, y = ROOT_ABYSS_BOSS_ROOM_SPAWNS[map_id]
            if not self.has_foothold_below(root, x, y):
                self.error(f"{map_id}: boss spawn {mob_id} at ({x}, {y}) has no foothold below")
            for script_dir in ("scripts/map/onUserEnter", "scripts-zh-CN/map/onUserEnter"):
                path = ROOT / "gms-server" / script_dir / "rootaBossEnter.js"
                if not path.exists():
                    self.error(f"{map_id}: missing boss room onUserEnter script {path.relative_to(ROOT)}")
                    continue
                script = path.read_text()
                if "spawnMonsterOnGroundBelow" not in script:
                    self.error(f"{map_id}: {path.relative_to(ROOT)} must auto-spawn boss on map enter")
                if "ms.spawnMonster(" in script:
                    self.error(f"{map_id}: {path.relative_to(ROOT)} must not use raw ms.spawnMonster for boss rooms")

        self.check_back_refs(map_id, img)
        self.check_tile_obj_refs(map_id, img)
        self.check_life_refs(map_id, img)
        self.check_reactor_refs(map_id, img)
        self.check_portal_refs(map_id, img)

    def check_back_refs(self, map_id: int, img: WzImage) -> None:
        idx = 0
        while True:
            back = img.get(f"back/{idx}")
            if back is None:
                break
            bS = self.child_value(back, "bS")
            no = self.child_value(back, "no")
            if bS:
                asset = self.client_img(Path("Map/Back") / f"{bS}.img")
                self.server_xml(f"Map.wz/Back/{bS}.img.xml")
                if asset is not None and no is not None and asset.get(f"back/{no}") is None:
                    self.error(f"{map_id}: missing back {bS}/back/{no}")
            idx += 1

    def check_tile_obj_refs(self, map_id: int, img: WzImage) -> None:
        for layer in range(8):
            tile_set = self.child_value(img.get(f"{layer}/info"), "tS")
            if tile_set:
                self.client_img(Path("Map/Tile") / f"{tile_set}.img")
                self.server_xml(f"Map.wz/Tile/{tile_set}.img.xml")

            obj_root = img.get(f"{layer}/obj")
            if obj_root is None:
                continue
            for obj in obj_root.children():
                for field in REMOVED_OBJ_FIELDS:
                    if obj.child(field) is not None:
                        self.error(f"{map_id}: high-version obj field remains: {layer}/obj/{obj.name}/{field}")
                obj_set = self.child_value(obj, "oS")
                l0 = self.child_value(obj, "l0")
                l1 = self.child_value(obj, "l1")
                l2 = self.child_value(obj, "l2")
                if (
                    map_id in NORTH_GARDEN_MAP_IDS
                    and obj_set == "rootabyss"
                    and l0 == "garden"
                    and l1 == "foot"
                    and layer != 0
                ):
                    self.error(f"{map_id}: north garden foot obj must render behind characters in layer 0: {layer}/obj/{obj.name}")
                if obj_set:
                    asset = self.client_img(Path("Map/Obj") / f"{obj_set}.img")
                    if obj_set not in {"connect", "effect"}:
                        self.server_xml(f"Map.wz/Obj/{obj_set}.img.xml")
                    if asset is not None and asset.get(f"{l0}/{l1}/{l2}") is None:
                        self.error(f"{map_id}: missing obj {obj_set}/{l0}/{l1}/{l2}")

    def check_life_refs(self, map_id: int, img: WzImage) -> None:
        life_root = img.get("life")
        if life_root is None:
            return
        for life in life_root.children():
            life_type = self.child_value(life, "type")
            raw_id = self.child_value(life, "id")
            if raw_id is None:
                self.error(f"{map_id}: life/{life.name} missing id")
                continue
            life_id = int(raw_id)
            if life_type == "n":
                self.client_img(f"Npc/{life_id}.img")
                self.server_xml(f"Npc.wz/{life_id}.img.xml")
                if not self.has_server_string("Npc", life_id):
                    self.error(f"{map_id}: missing server String/Npc {life_id}")
                if self.child_value(life, "hide") != 1:
                    for script_dir in ("scripts/npc", "scripts-zh-CN/npc"):
                        path = ROOT / "gms-server" / script_dir / f"{life_id}.js"
                        if not path.exists():
                            self.error(f"{map_id}: missing visible NPC script {path.relative_to(ROOT)}")
            elif life_type == "m":
                if life_id not in NORMAL_MOBS:
                    self.error(f"{map_id}: non-Root-Abyss mob life remains: {life_id}")
                self.client_img(f"Mob/{life_id}.img")
                self.server_xml(f"Mob.wz/{life_id}.img.xml")
                if not self.has_server_string("Mob", life_id):
                    self.error(f"{map_id}: missing server String/Mob {life_id}")
                for field in REMOVED_LIFE_FIELDS:
                    if life.child(field) is not None:
                        self.error(f"{map_id}: high-version life field remains: life/{life.name}/{field}")
            else:
                self.warn(f"{map_id}: unhandled life type {life_type} at life/{life.name}")

    def check_reactor_refs(self, map_id: int, img: WzImage) -> None:
        reactor_root = img.get("reactor")
        if reactor_root is None:
            return
        for reactor in reactor_root.children():
            raw_id = self.child_value(reactor, "id")
            if raw_id is None:
                self.error(f"{map_id}: reactor/{reactor.name} missing id")
                continue
            reactor_id = int(raw_id)
            self.client_img(f"Reactor/{reactor_id}.img")
            self.server_xml(f"Reactor.wz/{reactor_id}.img.xml")
            for script_dir in ("scripts/reactor", "scripts-zh-CN/reactor"):
                path = ROOT / "gms-server" / script_dir / f"{reactor_id}.js"
                if not path.exists():
                    self.error(f"{map_id}: missing reactor script {path.relative_to(ROOT)}")

    def check_portal_refs(self, map_id: int, img: WzImage) -> None:
        portal_root = img.get("portal")
        if portal_root is None:
            return
        for portal in portal_root.children():
            for field in REMOVED_PORTAL_FIELDS:
                if portal.child(field) is not None:
                    self.error(f"{map_id}: high-version portal field remains: portal/{portal.name}/{field}")
            script = self.child_value(portal, "script")
            if script:
                if script == "rootabyssOut":
                    self.error(f"{map_id}: portal/{portal.name} uses case-colliding legacy script rootabyssOut")
                for script_dir in ("scripts/portal", "scripts-zh-CN/portal"):
                    path = ROOT / "gms-server" / script_dir / f"{script}.js"
                    if not path.exists():
                        self.error(f"{map_id}: missing portal script {path.relative_to(ROOT)}")
                script_target = SCRIPT_PORTAL_TARGETS.get(script)
                if script == "rootaNext":
                    next_targets = {
                        105200100: 105200110,
                        105200200: 105200210,
                        105200300: 105200310,
                        105200400: 105200410,
                        105200500: 105200510,
                        105200600: 105200610,
                        105200700: 105200710,
                        105200800: 105200810,
                    }
                    target_map = next_targets.get(map_id)
                    script_target = (target_map, "sp") if target_map is not None else None
                door_select = DOOR_SELECT_SCRIPTS.get(script)
                if door_select is not None:
                    npc_script, normal_map, advanced_map = door_select
                    for script_dir in ("scripts/npc", "scripts-zh-CN/npc"):
                        npc_path = ROOT / "gms-server" / script_dir / f"{npc_script}.js"
                        if not npc_path.exists():
                            self.error(f"{map_id}: missing door select script {npc_path.relative_to(ROOT)}")
                            continue
                        text = npc_path.read_text(encoding="utf-8-sig")
                        if str(normal_map) not in text or str(advanced_map) not in text:
                            self.error(
                                f"{map_id}: {npc_path.relative_to(ROOT)} does not expose both {normal_map} and {advanced_map}"
                            )
                    self.check_target_portal(map_id, f"portal/{portal.name} script {script} normal", normal_map, "sp")
                    self.check_target_portal(map_id, f"portal/{portal.name} script {script} advanced", advanced_map, "sp")
                if script_target is not None:
                    self.check_target_portal(map_id, f"portal/{portal.name} script {script}", *script_target)
            target = self.child_value(portal, "tm")
            if isinstance(target, int) and target != 999999999:
                if target == 910000000:
                    self.error(f"{map_id}: portal/{portal.name} still points to Free Market")
                target_name = self.child_value(portal, "tn")
                self.check_target_portal(map_id, f"portal/{portal.name}", target, target_name)

    def check_target_portal(self, source_map_id: int, label: str, target: int, target_name: str | None) -> None:
        target_rel = Path(f"Map/Map/Map{target // 100000000}/{target}.img")
        target_path = CLIENT / target_rel
        if not target_path.exists():
            self.error(f"{source_map_id}: {label} target client map missing: {target}")
            return
        if target_name:
            target_img = self.client_img(target_rel)
            target_portals = target_img.get("portal") if target_img is not None else None
            if target_portals is None or not any(self.child_value(p, "pn") == target_name for p in target_portals.children()):
                self.error(f"{source_map_id}: {label} target portal missing: {target}/{target_name}")

    def check_known_sets(self) -> None:
        for script_dir in ("scripts/portal", "scripts-zh-CN/portal"):
            path = ROOT / "gms-server" / script_dir / "rootabyssGardenOut.js"
            if path.exists() and 'getSavedLocation("EVENT")' in path.read_text(encoding="utf-8"):
                self.error(f"rootabyssGardenOut garden exit must not read EVENT saved location: {path.relative_to(ROOT)}")

        for script_dir in ("scripts/portal", "scripts-zh-CN/portal"):
            path = ROOT / "gms-server" / script_dir / "rootabyssOUT.js"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if "returnMap < 100000000" not in text or "returnMap == 910000000" not in text:
                self.error(f"rootabyssOUT must reject stale Maple Island/FM EVENT returns: {path.relative_to(ROOT)}")

        for mob_id in NORMAL_MOBS:
            self.client_img(f"Mob/{mob_id}.img")
            self.server_xml(f"Mob.wz/{mob_id}.img.xml")
            if not self.has_server_string("Mob", mob_id):
                self.error(f"missing String/Mob {mob_id}")
        for mob_id in sorted(NORMAL_BOSS_MOBS | ADVANCED_BOSS_MOBS):
            self.check_root_abyss_boss_mob(mob_id)
        for npc_id in NPCS:
            self.client_img(f"Npc/{npc_id}.img")
            self.server_xml(f"Npc.wz/{npc_id}.img.xml")
            if not self.has_server_string("Npc", npc_id):
                self.error(f"missing String/Npc {npc_id}")
        for npc_id in STRING_ONLY_NPCS:
            if not self.has_server_string("Npc", npc_id):
                self.error(f"missing String/Npc {npc_id}")
        for reactor_id in REACTORS:
            self.client_img(f"Reactor/{reactor_id}.img")
            self.server_xml(f"Reactor.wz/{reactor_id}.img.xml")
        self.check_quest_data()
        self.check_root_abyss_items()

    def check_root_abyss_boss_mob(self, mob_id: int) -> None:
        img = self.client_img(f"Mob/{mob_id}.img")
        root = self.server_xml(f"Mob.wz/{mob_id}.img.xml")
        if not self.has_server_string("Mob", mob_id):
            self.error(f"missing String/Mob {mob_id}")
        if img is None:
            return

        info = img.get("info")
        if info is None:
            self.error(f"{mob_id}: missing mob info")
            return
        client_hp = self.child_value(info, "maxHP")
        if mob_id in ROOT_ABYSS_SECOND_PHASE_BOSS_HP:
            try:
                client_hp_value = int(client_hp)
            except (TypeError, ValueError):
                client_hp_value = 0
            if client_hp_value > 2_147_483_647:
                self.error(f"{mob_id}: client maxHP must stay int-safe; long HP belongs only in server XML")
        if self.child_value(info, "mobType") != 1:
            self.error(f"{mob_id}: mobType must be old-client integer 1")
        for field in OLD_SERVER_REQUIRED_BOSS_INFO_FIELDS:
            if self.child_value(info, field) is None:
                self.error(f"{mob_id}: missing old-server required mob info field {field}")
        boss_flag = self.child_value(info, "boss")
        if mob_id not in BOSS_GAUGE_MOBS and boss_flag:
            self.error(f"{mob_id}: helper mob must not request missing boss gauge")
        if mob_id in BOSS_GAUGE_MOBS:
            ui = self.client_img("UI/UIWindow.img")
            gauge = ui.get(f"MobGage/Mob/{mob_id}") if ui is not None else None
            if gauge is None:
                self.error(f"{mob_id}: missing boss HP gauge UI")
            elif not isinstance(gauge, WzCanvasProperty):
                self.error(f"{mob_id}: boss HP gauge UI must be a Canvas")
            else:
                if gauge.child("_inlink") is not None or gauge.child("_outlink") is not None:
                    self.error(f"{mob_id}: boss HP gauge UI must be materialized, not a Canvas link")
                if (gauge.format, gauge.format2) != (1, 0):
                    self.error(f"{mob_id}: boss HP gauge UI must be ARGB4444")
                elif decode_canvas(gauge, region="GMS").getbbox() is None:
                    self.error(f"{mob_id}: boss HP gauge UI is transparent")

        if mob_id in VELLUM_COMPAT_MOBS:
            for action in img.children():
                if not action.name.startswith("attack"):
                    continue
                for frame in action.children():
                    if (
                        isinstance(frame, WzCanvasProperty)
                        and (frame.width > VELLUM_MAX_ATTACK_FRAME_WIDTH
                             or frame.height > VELLUM_MAX_ATTACK_FRAME_HEIGHT)
                    ):
                        self.error(
                            f"{mob_id}: {action.name}/{frame.name} exceeds old-client Vellum attack frame limit "
                            f"{VELLUM_MAX_ATTACK_FRAME_WIDTH}x{VELLUM_MAX_ATTACK_FRAME_HEIGHT}: "
                            f"{frame.width}x{frame.height}"
                        )

        skill_root = img.get("info/skill")
        if skill_root is not None:
            for expected_idx, skill in enumerate(skill_root.children()):
                if skill.name != str(expected_idx):
                    self.error(f"{mob_id}: boss skill entries must be compact, got {skill.name} expected {expected_idx}")
                skill_id = self.child_value(skill, "skill")
                level = self.child_value(skill, "level")
                action = self.child_value(skill, "action") or expected_idx + 1
                if (skill_id, level) not in SUPPORTED_ROOT_ABYSS_BOSS_SKILLS:
                    self.error(f"{mob_id}: unsupported boss MobSkill {skill_id}/{level}")
                if img.get(f"skill{action}") is None:
                    self.error(f"{mob_id}: boss MobSkill {skill_id}/{level} points to missing skill{action}")
                mob_skill = self.client_img("Skill/MobSkill.img")
                if mob_skill is not None:
                    client_skill_level = mob_skill.get(f"{skill_id}/level/{level}")
                    if client_skill_level is None and (skill_id, level) not in SERVER_DRIVEN_ROOT_ABYSS_BOSS_SKILLS:
                        self.error(f"{mob_id}: missing client MobSkill {skill_id}/{level}")
                server_skill = self.server_xml("Skill.wz/MobSkill.img.xml")
                if server_skill is not None:
                    xpath = f"./imgdir[@name='{skill_id}']/imgdir[@name='level']/imgdir[@name='{level}']"
                    server_skill_level = server_skill.find(xpath)
                    if server_skill_level is None:
                        self.error(f"{mob_id}: missing server MobSkill {skill_id}/{level}")

        if mob_id in DIRECT_BOSS_MOBS:
            self.check_direct_boss_foot_alignment(mob_id, img)

        if root is not None:
            server_info = root.find("./imgdir[@name='info']")
            if server_info is not None:
                for field in OLD_SERVER_REQUIRED_BOSS_INFO_FIELDS:
                    if server_info.find(f"./int[@name='{field}']") is None:
                        self.error(f"{mob_id}: server XML missing old-server required mob info field {field}")
                expected_hp = ROOT_ABYSS_SECOND_PHASE_BOSS_HP.get(mob_id)
                if expected_hp is not None:
                    hp_node = server_info.find("./string[@name='maxHP']")
                    if hp_node is None or hp_node.get("value") != str(expected_hp):
                        self.error(f"{mob_id}: server XML second-phase maxHP must be string {expected_hp}")
            server_skills = root.find("./imgdir[@name='info']/imgdir[@name='skill']")
            if server_skills is not None:
                for expected_idx, skill in enumerate(server_skills):
                    if skill.get("name") != str(expected_idx):
                        self.error(f"{mob_id}: server boss skill entries must be compact")

    def check_direct_boss_foot_alignment(self, mob_id: int, img: WzImage) -> None:
        for action_name in ("stand", "move"):
            action = img.get(action_name)
            if action is None or not hasattr(action, "children"):
                continue
            for frame in action.children():
                if not frame.name.isdigit() or not isinstance(frame, WzCanvasProperty) or not frame.has_pixels():
                    continue
                origin = frame.child("origin")
                if not isinstance(origin, WzVectorProperty):
                    self.error(f"{mob_id}: {action_name}/{frame.name} missing origin")
                    continue
                try:
                    image = decode_canvas(frame, region="GMS")
                except Exception as exc:  # noqa: BLE001
                    self.error(f"{mob_id}: {action_name}/{frame.name} decode failed during foot audit: {exc}")
                    continue
                bbox = image.getbbox()
                if bbox is None:
                    continue
                visible_bottom_delta = int(bbox[3]) - int(origin.y)
                if visible_bottom_delta > 0:
                    self.error(f"{mob_id}: {action_name}/{frame.name} visible foot below origin by {visible_bottom_delta}px")

    def check_drop_data(self) -> None:
        if NORMAL_MOBS:
            self.check_drop_migration(DROP_MIGRATION, NORMAL_MOBS, "Root Abyss normal mob")
        if ADVANCED_BOSS_DROP_MOBS:
            self.check_drop_migration(BOSS_DROP_MIGRATION, ADVANCED_BOSS_DROP_MOBS, "Root Abyss advanced boss")
        self.check_any_drop_rows(NORMAL_BOSS_DROP_MOBS, "Root Abyss normal boss")

    def check_any_drop_rows(self, mob_ids: set[int], label: str) -> None:
        sql_paths = sorted((ROOT / "gms-server/src/main/resources/db/migration").glob("V*.sql"))
        pattern = re.compile(r"\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)")
        drops: dict[int, list[tuple[int, int, int, int, int]]] = {mob_id: [] for mob_id in mob_ids}
        for path in sql_paths:
            text = path.read_text(encoding="utf-8")
            for dropper, item, minimum, maximum, quest, chance in pattern.findall(text):
                dropper_id = int(dropper)
                if dropper_id in drops:
                    drops[dropper_id].append((int(item), int(minimum), int(maximum), int(quest), int(chance)))
        for mob_id in sorted(mob_ids):
            mob_drops = drops[mob_id]
            if not mob_drops:
                self.error(f"{mob_id}: missing {label} drop rows")
            elif not any(item_id > 0 for item_id, *_ in mob_drops):
                self.error(f"{mob_id}: missing {label} item drop rows")

    def check_drop_migration(self, path: Path, mob_ids: set[int], label: str) -> None:
        if not path.exists():
            self.error(f"missing {label} drop migration: {path.relative_to(ROOT)}")
            return
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(r"\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)")
        drops: dict[int, list[tuple[int, int, int, int, int]]] = {mob_id: [] for mob_id in mob_ids}
        for dropper, item, minimum, maximum, quest, chance in pattern.findall(text):
            dropper_id = int(dropper)
            if dropper_id in drops:
                drops[dropper_id].append((int(item), int(minimum), int(maximum), int(quest), int(chance)))

        for mob_id in sorted(mob_ids):
            mob_drops = drops[mob_id]
            if not mob_drops:
                self.error(f"{mob_id}: missing {label} drop rows")
                continue
            if not any(item_id == 0 for item_id, *_ in mob_drops):
                self.error(f"{mob_id}: missing meso drop row")
            if not any(item_id > 0 for item_id, *_ in mob_drops):
                self.error(f"{mob_id}: missing item drop rows")
            for item_id, minimum, maximum, _quest, chance in mob_drops:
                if minimum <= 0 or maximum < minimum or chance < 0:
                    self.error(f"{mob_id}: invalid drop row item={item_id} min={minimum} max={maximum} chance={chance}")
                if item_id > 0:
                    self.check_drop_item_resource(mob_id, item_id)

    def check_drop_item_resource(self, mob_id: int, item_id: int) -> None:
        if 2000000 <= item_id < 3000000:
            folder = "Consume"
        elif 4000000 <= item_id < 5000000:
            folder = "Etc"
        else:
            folder = "Equip"
        img_name = f"{item_id // 10000:04d}.img"
        node_name = f"0{item_id}"

        client_rel = Path("Item") / folder / img_name
        item_img = self.client_img(client_rel)
        if item_img is not None and item_img.get(node_name) is None and item_img.get(str(item_id)) is None:
            self.error(f"{mob_id}: drop item client node missing: {item_id} in {client_rel}")

        server_root = self.server_xml(Path("Item.wz") / folder / f"{img_name}.xml")
        if server_root is not None and not any(child.get("name") in {node_name, str(item_id)} for child in server_root):
            self.error(f"{mob_id}: drop item server XML node missing: {item_id} in Item.wz/{folder}/{img_name}.xml")

    def check_quest_data(self) -> None:
        for file_name in ("QuestInfo", "Check", "Act", "Say"):
            client_img = self.client_img(f"Quest/{file_name}.img")
            server_root = self.server_xml(f"Quest.wz/{file_name}.img.xml")
            zh_path = ROOT / "gms-server/wz-zh-CN/Quest.wz" / f"{file_name}.img.xml"
            zh_root = None
            if zh_path.exists():
                try:
                    zh_root = ET.parse(zh_path).getroot()
                except Exception as exc:  # noqa: BLE001
                    self.error(f"server zh-CN Quest XML parse failed: {zh_path.relative_to(ROOT)}: {exc}")
            for quest_id in ROOT_ABYSS_QUESTS:
                if client_img is not None and client_img.get(str(quest_id)) is None:
                    self.error(f"missing client Quest/{file_name}.img {quest_id}")
                if server_root is not None and server_root.find(f"./imgdir[@name='{quest_id}']") is None:
                    self.error(f"missing server Quest.wz/{file_name}.img.xml {quest_id}")
                if zh_root is not None and zh_root.find(f"./imgdir[@name='{quest_id}']") is None:
                    self.error(f"missing server wz-zh-CN Quest.wz/{file_name}.img.xml {quest_id}")
        for script_root in ("scripts", "scripts-zh-CN"):
            for quest_id in range(30014, 30023):
                path = ROOT / "gms-server" / script_root / "quest" / f"{quest_id}.js"
                if not path.exists():
                    self.error(f"missing daily Root Abyss quest script: {path.relative_to(ROOT)}")

    def check_root_abyss_items(self) -> None:
        etc = self.client_img("Item/Etc/0400.img")
        string_etc = self.client_img("String/Etc.img")
        server_etc = self.server_xml("Item.wz/Etc/0400.img.xml")
        server_string = self.server_xml("String.wz/Etc.img.xml")
        for item_id in ROOT_ABYSS_ITEMS:
            node_name = f"0{item_id}"
            if etc is not None and etc.get(node_name) is None:
                self.error(f"missing client Root Abyss item {node_name}")
            if string_etc is not None and string_etc.get(f"Etc/{item_id}") is None:
                self.error(f"missing client String/Etc {item_id}")
            if server_etc is not None and server_etc.find(f"./imgdir[@name='{node_name}']") is None:
                self.error(f"missing server Item.wz/Etc/0400.img.xml {node_name}")
            if server_string is not None:
                etc_root = server_string.find("./imgdir[@name='Etc']")
                if etc_root is None or etc_root.find(f"./imgdir[@name='{item_id}']") is None:
                    self.error(f"missing server String/Etc {item_id}")
            if etc is not None:
                item_node = etc.get(node_name)
                if item_node is not None:
                    self.decode_canvas_tree(f"Item/Etc/0400.img:{node_name}", item_node)

    def check_canvas_decode(self) -> None:
        paths: list[Path] = []
        paths.extend(Path("Map/Map/Map1") / f"{mid}.img" for mid in MAP_IDS)
        paths.extend(Path("Map/Back") / p.name for p in (CLIENT / "Map/Back").glob("rootabyss*.img"))
        paths.extend([
            Path("Map/Obj/rootabyss.img"),
            Path("Map/Obj/gran_helisium.img"),
            Path("Map/Obj/connect.img"),
            Path("Map/Obj/effect.img"),
            Path("Map/Tile/rootabyssBan.img"),
            Path("Map/Tile/rootabyssBanInside.img"),
            Path("Map/Tile/rootabyssBellum.img"),
            Path("Map/Tile/rootabyssQueen.img"),
            Path("Sound/Bgm29.img"),
        ])
        paths.extend(Path("Mob") / f"{mob_id}.img" for mob_id in sorted(NORMAL_MOBS))
        paths.extend(Path("Mob") / f"{mob_id}.img" for mob_id in sorted(NORMAL_BOSS_MOBS | ADVANCED_BOSS_MOBS))
        paths.extend(Path("Npc") / f"{npc_id}.img" for npc_id in sorted(NPCS))
        paths.extend(Path("Reactor") / f"{reactor_id}.img" for reactor_id in sorted(REACTORS))
        for rel in paths:
            self.decode_canvases(rel)

    def check_visual_regressions(self) -> None:
        paths: list[Path] = [
            Path("Map/Obj/rootabyss.img"),
            Path("Map/Obj/gran_helisium.img"),
        ]
        paths.extend(Path("Map/Back") / p.name for p in (CLIENT / "Map/Back").glob("rootabyss*.img"))
        paths.extend(Path("Map/Tile") / p.name for p in (CLIENT / "Map/Tile").glob("rootabyss*.img"))
        for rel in paths:
            self.check_no_transparent_canvas_regressions(rel)

    def run(self) -> int:
        self.check_map_counts()
        for map_id in MAP_IDS:
            self.check_map(map_id)
        self.check_known_sets()
        self.check_drop_data()
        self.check_canvas_decode()
        self.check_visual_regressions()

        print(f"root_abyss_maps={len(MAP_IDS)}")
        print(f"decoded_canvases={self.canvas_count}")
        print(f"warnings={len(self.warnings)}")
        print(f"errors={len(self.errors)}")
        for warning in self.warnings[:50]:
            print(f"WARN {warning}")
        for error in self.errors[:100]:
            print(f"ERROR {error}")
        return 1 if self.errors else 0


if __name__ == "__main__":
    raise SystemExit(Audit().run())
