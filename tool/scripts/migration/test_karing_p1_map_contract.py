#!/usr/bin/env python3
"""Contract checks for Karing P1 maps, map assets, and guide NPCs."""

from __future__ import annotations

import importlib.util
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_karing_p1_maps.py"
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def load_migration_module():
    spec = importlib.util.spec_from_file_location("migrate_karing_p1_maps", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def walk(node):
    yield node
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk(child)


def test_karing_p1_maps_are_present_and_legacy_safe():
    migration = load_migration_module()
    for map_id in migration.MAP_IDS:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
        image.parse()
        assert not image.truncated
        assert image.parse_warnings == []
        assert image.root.child("particle") is None

        info = image.root.child("info")
        assert isinstance(info, WzSubProperty)
        assert info.child("bgm") is None
        assert info.child("mapMark") is None
        assert info.child("fieldType") is None
        expected_field_limit = migration.LEGACY_FIELD_LIMIT_OVERRIDES.get(map_id)
        if expected_field_limit is not None:
            assert migration.child_value(info, "fieldLimit") == expected_field_limit
        assert migration.child_value(info, "returnMap") == migration.RETURN_MAP
        assert migration.child_value(info, "forcedReturn") == migration.RETURN_MAP
        expected_script = migration.ON_FIRST_USER_ENTER_OVERRIDES.get(map_id)
        if expected_script is not None:
            assert migration.child_value(info, "onFirstUserEnter") == expected_script

        portal = image.root.child("portal")
        assert isinstance(portal, WzSubProperty)
        portal_names = {
            migration.child_value(entry, "pn") for entry in portal.children()
        }
        assert portal_names.isdisjoint(
            migration.P1_INTER_BOSS_PORTALS.get(map_id, set())
        )
        hidden_target = migration.HIDDEN_PORTAL_TARGET_OVERRIDES.get(map_id)
        if hidden_target is not None:
            for entry in portal.children():
                if str(migration.child_value(entry, "pn") or "").startswith("hd"):
                    assert migration.child_value(entry, "tm") == hidden_target

        for node in walk(image.root):
            if not isinstance(node, WzCanvasProperty):
                continue
            assert node.child("_outlink") is None
            assert node.child("_inlink") is None
            assert int(node.format) == 1
            assert int(node.format2) == 0
            assert int(node.width) <= migration.MAX_CANVAS_EDGE
            assert int(node.height) <= migration.MAX_CANVAS_EDGE
            decode_canvas(node, region="GMS")

        ET.parse(ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml")


def test_karing_p1_asset_and_npc_dependencies_exist():
    migration = load_migration_module()
    migration.verify()


def test_karing_p1_back_animations_are_legacy_bounded():
    migration = load_migration_module()
    path = ROOT / "clien/Data/Map/Back/dowonkyungDark.img"
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
    )
    image.parse()
    for index in range(6):
        animation = image.root.get(f"ani/{index}")
        assert isinstance(animation, WzSubProperty)
        frames = [child for child in animation.children() if child.name.isdigit()]
        assert [frame.name for frame in frames] == ["0"]


def test_karing_p1_reactors_match_server_and_exist():
    migration = load_migration_module()
    for map_id in migration.MAP_IDS:
        client_path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = WzImage.from_bytes(
            client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
        )
        image.parse()
        server_root = ET.parse(
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        ).getroot()
        client_reactors = migration.reactor_ids_from_client(image)
        server_reactors = migration.reactor_ids_from_server(server_root)
        assert client_reactors == server_reactors
        for reactor_id in client_reactors:
            assert (ROOT / f"clien/Data/Reactor/{reactor_id}.img").is_file()
            assert (ROOT / f"gms-server/wz/Reactor.wz/{reactor_id}.img.xml").is_file()


def test_karing_boss_maps_have_no_optional_immediate_load_dependencies():
    migration = load_migration_module()
    for map_id, base_map_id in migration.MAP_STRUCTURE_BASE_IDS.items():
        target_root = ET.parse(
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        ).getroot()
        base_root = ET.parse(
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{base_map_id}.img.xml"
        ).getroot()
        for root_name in ("info", "foothold", "ladderRope", "miniMap", "portal"):
            target_node = next(
                child for child in target_root if child.get("name") == root_name
            )
            base_node = next(
                child for child in base_root if child.get("name") == root_name
            )
            comparable_target = copy.deepcopy(target_node)
            if root_name == "info":
                target_script = next(
                    child
                    for child in comparable_target
                    if child.get("name") == "onFirstUserEnter"
                )
                base_script = next(
                    child
                    for child in base_node
                    if child.get("name") == "onFirstUserEnter"
                )
                target_script.set("value", base_script.get("value"))
            elif root_name == "portal":
                base_entries = {entry.get("name"): entry for entry in base_node}
                for target_entry in comparable_target:
                    base_entry = base_entries[target_entry.get("name")]
                    target_tm = next(
                        (child for child in target_entry if child.get("name") == "tm"),
                        None,
                    )
                    base_tm = next(
                        (child for child in base_entry if child.get("name") == "tm"),
                        None,
                    )
                    if target_tm is not None and base_tm is not None:
                        target_tm.set("value", base_tm.get("value"))
            assert ET.tostring(comparable_target) == ET.tostring(base_node)

    for map_id in sorted(migration.MAP_LOAD_SAFE_PROJECTION_IDS):
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        image.parse()

        info = image.root.child("info")
        assert isinstance(info, WzSubProperty)
        assert info.child("abilityPresetBlock") is None

        life = image.root.child("life")
        reactor = image.root.child("reactor")
        assert isinstance(life, WzSubProperty) and list(life.children()) == []
        assert isinstance(reactor, WzSubProperty) and list(reactor.children()) == []

        portal = image.root.child("portal")
        assert isinstance(portal, WzSubProperty)
        assert {
            migration.child_value(entry, "pn") for entry in portal.children()
        } == {"sp", "ptKaringOut"}
        visible_script_portals = {
            migration.child_value(entry, "pn"): migration.child_value(entry, "pt")
            for entry in portal.children()
            if migration.child_value(entry, "pn")
            in migration.LEGACY_VISIBLE_SCRIPT_PORTALS[map_id]
        }
        assert visible_script_portals == {
            name: 7 for name in migration.LEGACY_VISIBLE_SCRIPT_PORTALS[map_id]
        }

        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            objects = layer.child("obj")
            if not isinstance(objects, WzSubProperty):
                continue
            for entry in objects.children():
                assert migration.child_value(entry, "oS") != "BossKaring"

        generated = migration.image_to_xml(image, f"{map_id}.img")
        server = (
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        ).read_text()
        assert generated == server


def test_karing_dool_map_keeps_blue_background_with_legacy_safe_objects():
    migration = load_migration_module()
    path = ROOT / "clien/Data/Map/Map/Map4/410007180.img"
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
    )
    image.parse()

    back = image.root.child("back")
    assert isinstance(back, WzSubProperty)
    assert any(
        migration.child_value(entry, "bS") == "BossKaring"
        for entry in back.children()
    )

    object_branches = set()
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        object_branches.update(
            tuple(
                str(migration.child_value(entry, name))
                for name in ("oS", "l0", "l1")
            )
            for entry in objects.children()
        )
    assert ("dowonkyung", "foothold", "upFootholdDarkSummer") not in object_branches
    assert ("dowonkyung", "foothold", "upFootholdDarkSpring") in object_branches


def test_karing_p1_map_scripts_match_wz_entry_folders():
    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        for name in ("first_goongipre", "first_doolpre", "first_hondonpre"):
            assert (ROOT / tree / "map/onFirstUserEnter" / f"{name}.js").is_file()
        for name in ("karing_first", "goongi_direction", "dool_direction", "hondon_direction", "first_dool2"):
            assert (ROOT / tree / "map/onUserEnter" / f"{name}.js").is_file()


def test_karing_boss_spawns_are_delayed_until_after_map_entry():
    advanced = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/新高级boss传送.js").read_text()
    assert "var skipBossSpawn" not in advanced
    assert "cm.scheduleMonsterOnGroundBelowIfMissing" in advanced
    assert "8880831, -1, 568, 106" in advanced
    assert "410007260, 500000" in advanced
    assert "8880837, -1, 568, 106" in advanced
    assert "410007300, 500000" in advanced
    assert "8880842, -1, -545, 399" in advanced
    assert "!isGM && isKaringBoss(bossMaps[i][3])" in advanced
    assert "bossId == 8880837 || bossId == 8880842" in advanced

    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        for script in (ROOT / tree / "portal").glob("karing*Portal.js"):
            text = script.read_text()
            assert "pi.warp(mapId, 0);" in text
            assert text.index("pi.warp(mapId, 0);") < text.index(
                "pi.scheduleMonsterOnGroundBelowIfMissing"
            )
            assert "pi.scheduleMonsterOnGroundBelowIfMissing(map, bossId, x, y, 2000);" in text
            if "ToDoolPortal" in script.name:
                assert "410007180, 8880831, 568, 106" in text
