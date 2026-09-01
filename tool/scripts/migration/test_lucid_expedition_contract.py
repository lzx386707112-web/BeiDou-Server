#!/usr/bin/env python3
"""Contract checks for the Lucid map and expedition migration."""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).with_name("migrate_lucid_expedition.py")
SPEC = importlib.util.spec_from_file_location("migrate_lucid_expedition", SCRIPT)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)
arc = migration.arc


def test_lucid_maps_are_present_and_legacy_safe():
    contracts = migration.expected_dependencies()
    for map_id in migration.MAP_IDS:
        path = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        image = arc.load_image(path, arc.GMS_KEY)
        assert not image.truncated
        assert image.parse_warnings == []
        assert arc.collect_dependencies(image) == contracts[map_id]

        info = image.root.child("info")
        assert arc.child_value(info, "returnMap") == migration.RETURN_MAP
        assert arc.child_value(info, "forcedReturn") == migration.RETURN_MAP
        assert arc.child_value(info, "fieldLimit") == 0
        assert arc.child_value(info, "bgm") == migration.MAP_BGM[map_id]
        assert info.child("fieldType") is None
        assert info.child("onFirstUserEnter") is None
        assert info.child("onUserEnter") is None
        assert image.root.child("mobTeleport") is None
        life = list(image.root.child("life").children())
        if map_id == migration.ENTRY_MAP:
            assert len(life) == 1
            npc = life[0]
            assert arc.child_value(npc, "id") == str(migration.ENTRY_NPC_ID)
            assert arc.child_value(npc, "type") == "n"
            for field, value in migration.ENTRY_NPC_POSITION.items():
                assert arc.child_value(npc, field) == value
            assert arc.child_value(npc, "hide") == 0
            assert arc.child_value(npc, "mobTime") == 0
        else:
            assert life == []
        assert list(image.root.child("reactor").children()) == []

        for node, _ in arc.walk(image.root):
            if not isinstance(node, arc.WzCanvasProperty):
                continue
            assert node.child("_outlink") is None
            assert node.child("_inlink") is None
            assert int(node.format) == 1
            assert int(node.format2) == 0
            arc.decode_canvas(node, region="GMS")

        expected_xml = arc.image_to_xml(image, f"{map_id}.img")
        actual_xml = (
            ROOT / f"gms-server/wz/Map.wz/Map/Map4/{map_id}.img.xml"
        ).read_text(encoding="utf-8")
        assert actual_xml == expected_xml


def test_lucid_portals_form_the_legacy_expedition_route():
    entry = arc.load_image(
        ROOT / "clien/Data/Map/Map/Map4/450004000.img", arc.GMS_KEY
    )
    recruit = migration.portal_by_name(entry.root, "pt02")
    assert arc.child_value(recruit, "pt") == 0
    assert arc.child_value(recruit, "script") == ""
    out = migration.portal_by_name(entry.root, "out00")
    assert arc.child_value(out, "tm") == migration.ROUTE_MAP
    assert arc.child_value(out, "tn") == "sp"

    for map_id in (450004150, 450004250):
        image = arc.load_image(
            ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img", arc.GMS_KEY
        )
        out = migration.portal_by_name(image.root, "pt00")
        assert arc.child_value(out, "pt") == 7
        assert arc.child_value(out, "script") == "lucid_exit"


def test_lucid_phase_one_spine_objects_are_projected_to_static_legacy_objects():
    migration.configure(ROOT)
    baseline_image, _ = arc.clone_image(
        arc.SOURCE / "Map/Map/Map4/450004150.img",
        lambda root: migration.sanitize_lucid_map(root, 450004150),
    )
    baseline = migration.encoded_image(baseline_image, "450004150.img")
    installed = (
        ROOT / "clien/Data/Map/Map/Map4/450004150.img"
    ).read_bytes()
    arc.verify_raw_record_insert_scope(
        baseline, installed,
        {("1", "obj", name) for name, *_ in migration.LEGACY_MAP_OBJECTS},
    )

    phase_one = arc.load_image(
        ROOT / "clien/Data/Map/Map/Map4/450004150.img", arc.GMS_KEY
    )
    objects = phase_one.root.get("1/obj")
    assert isinstance(objects, arc.WzSubProperty)
    assert [entry.name for entry in objects.children()] == ["0", "1"]
    for entry, expected in zip(objects.children(), migration.LEGACY_MAP_OBJECTS):
        name, branch, x, y = expected
        assert entry.name == name
        assert arc.child_value(entry, "oS") == migration.LEGACY_OBJ_ASSET
        assert arc.child_value(entry, "l0") == "Boss"
        assert arc.child_value(entry, "l1") == "obj"
        assert arc.child_value(entry, "l2") == branch
        assert arc.child_value(entry, "x") == x
        assert arc.child_value(entry, "y") == y
        assert arc.child_value(entry, "z") == 9
        assert arc.child_value(entry, "zM") == 5
        for unsupported in ("piece", "spineAni", "tags", "timeScale"):
            assert entry.child(unsupported) is None

    asset = arc.load_image(ROOT / migration.LEGACY_OBJ_PATH, arc.GMS_KEY)
    assert not asset.truncated
    assert asset.parse_warnings == []
    assert [entry.name for entry in asset.root.get("Boss/obj").children()] == ["9", "10"]
    for branch, spec in migration.LEGACY_OBJ_SPECS.items():
        canvas = asset.root.get(f"Boss/obj/{branch}/0")
        assert isinstance(canvas, arc.WzCanvasProperty)
        assert (int(canvas.width), int(canvas.height)) == spec["size"]
        assert (int(canvas.format), int(canvas.format2)) == (1, 0)
        origin = canvas.child("origin")
        assert isinstance(origin, arc.WzVectorProperty)
        assert (int(origin.x), int(origin.y)) == spec["origin"]
        assert arc.decode_canvas(canvas, region="GMS").convert("RGBA").getbbox() is not None


def test_lucid_asset_bgm_and_strings_exist():
    contracts = migration.expected_dependencies()
    branches = set().union(*(
        contract["assets"].get(("Back", "Lach_boss"), set())
        for contract in contracts.values()
    ))
    asset = arc.load_image(ROOT / "clien/Data/Map/Back/Lach_boss.img", arc.GMS_KEY)
    assert not asset.truncated
    assert asset.parse_warnings == []
    for branch in branches:
        assert asset.root.get(branch) is not None
    for node, _ in arc.walk(asset.root):
        if isinstance(node, arc.WzCanvasProperty):
            assert int(node.format) == 1
            assert int(node.format2) == 0
            arc.decode_canvas(node, region="GMS")

    sound = arc.load_image(ROOT / "clien/Data/Sound/Bgm46.img", arc.GMS_KEY)
    for reference in migration.MAP_BGM.values():
        assert isinstance(sound.root.child(reference.split("/", 1)[1]), arc.WzSoundProperty)

    strings = arc.load_image(ROOT / "clien/Data/String/Map.img", arc.GMS_KEY)
    for map_id in migration.MAP_IDS:
        assert strings.root.get(f"grandis/{map_id}/streetName") is not None
        assert strings.root.get(f"grandis/{map_id}/mapName") is not None
    for tree in ("wz", "wz-zh-CN"):
        root = ET.parse(ROOT / f"gms-server/{tree}/String.wz/Map.img.xml").getroot()
        grandis = next(child for child in root if child.get("name") == "grandis")
        assert {str(value) for value in migration.MAP_IDS}.issubset(
            {child.get("name") for child in grandis}
        )


def test_lucid_expedition_contract_is_wired_end_to_end():
    expedition_type = (
        ROOT / "gms-server/src/main/java/org/gms/server/expeditions/ExpeditionType.java"
    ).read_text(encoding="utf-8")
    boss_log = (
        ROOT / "gms-server/src/main/java/org/gms/server/expeditions/ExpeditionBossLog.java"
    ).read_text(encoding="utf-8")
    mob_ids = (
        ROOT / "gms-server/src/main/java/org/gms/constants/id/MobId.java"
    ).read_text(encoding="utf-8")
    expedition = (
        ROOT / "gms-server/src/main/java/org/gms/server/expeditions/Expedition.java"
    ).read_text(encoding="utf-8")
    assert "LUCID(1, 30, 220, 255, 5)" in expedition_type
    assert "LUCID(1, 1, false)" in boss_log
    for phase, mob_id in enumerate((8880140, 8880141, 8880142), start=1):
        constant = f"LUCID_PHASE_{phase}"
        assert f"{constant} = {mob_id}" in mob_ids
        assert f"MobId.{constant}" in expedition

    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        event = (ROOT / tree / "event/LucidBattle.js").read_text(encoding="utf-8")
        assert "var entryMap = 450004150" in event
        assert "var phaseTwoMap = 450004250" in event
        assert "LifeFactory.getMonster(8880140)" in event
        assert 'eim.schedule("advanceToPhaseTwo", 2500)' in event
        assert "phaseOneMap.killAllMonsters()" in event
        assert "LifeFactory.getMonster(8880141)" in event
        assert "mob.getId() == 8880142" in event
        assert "if (!hasKiller)" in event
        assert "var maxDeaths = 10" in event

    entrance = (
        ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/露希妲远征.js"
    ).read_text(encoding="utf-8")
    assert "ExpeditionType.LUCID" in entrance
    assert 'var eventName = "LucidBattle"' in entrance
    assert "em.startInstance(expedition)" in entrance

    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        npc = (ROOT / tree / "npc/3003208.js").read_text(encoding="utf-8")
        assert "cm.getMapId() == 450004000" in npc
        assert 'cm.openNpc(9900001, "露希妲远征")' in npc

    transport = (
        ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/新高级boss传送.js"
    ).read_text(encoding="utf-8")
    assert "梦中的路西德·远征入口" in transport
    assert "cm.warp(450004000, 0)" in transport

    migration_sql = (
        ROOT / "gms-server/src/main/resources/db/migration/"
        "V2.1.66__add_lucid_expedition_bosslog.sql"
    ).read_text(encoding="utf-8")
    assert migration_sql.count("'LUCID'") == 2


def test_lucid_tms_map_analysis_stays_documented():
    text = (ROOT / "docs/migrations/lucid-expedition.md").read_text(encoding="utf-8")
    assert "450004100 -> 450004150 -> 450004200 -> 450004250 -> 450004300" in text
    assert "450004400 -> 450004450 -> 450004500 -> 450004550 -> 450004600" in text
    assert "450004700 -> 450004750 -> 450004800 -> 450004850 -> 450004900" in text
    assert re.search(r"8880140.*8880141.*8880142", text, re.S)


def main() -> int:
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"Lucid expedition contract ok: tests={len(tests)} maps={len(migration.MAP_IDS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
