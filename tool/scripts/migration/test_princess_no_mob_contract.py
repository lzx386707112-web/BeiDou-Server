#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "nohime_migration",
    ROOT / "tool/scripts/migration/migrate_nohime_odium_shangrila_commerci.py",
)
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = migration
spec.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


MOB_ID = 9450037
ATTACK_INFO_PATH = "attack1/info"
SCENE_MOB_ID = 9450040
SOURCE_SCENE_SKILLS = (
    {"action": 1, "skill": 170, "level": 55, "effectAfter": 0,
     "afterAttack": 4, "afterAttackCount": 1},
    {"action": 2, "skill": 201, "level": 111, "skillAfter": 960},
)
CLIENT_SCENE_SKILLS = (
    {"action": 1, "skill": 200, "level": 235, "effectAfter": 0,
     "afterAttack": 4, "afterAttackCount": 1},
    {"action": 2, "skill": 200, "level": 236, "skillAfter": 960},
)
SOURCE_SCENE_LEVELS = {
    (170, 55): (("x", 1), ("interval", 30)),
    (201, 111): (
        ("interval", 300), ("hp", 100), ("limit", 10),
        ("0", 9450021), ("1", 9450047), ("2", 9450048),
        ("3", 9450049), ("4", 9450050),
        ("summonEffect", 6), ("exchangeAttack", 1),
    ),
}
CLIENT_SCENE_LEVELS = {
    235: SOURCE_SCENE_LEVELS[(170, 55)],
    236: SOURCE_SCENE_LEVELS[(201, 111)],
}
SCENE_SUMMON_MOBS = {9450021: 35, 9450047: 35, 9450048: 35, 9450049: 35, 9450050: 31}
SCENE_SUMMON_NAME = "織田軍陰陽師"


def assert_source_contract() -> None:
    source = migration.arc.extract_mob(MOB_ID)
    image = migration.arc.load_image(source, migration.arc.BMS_KEY)
    modern = image.root.get("info/attack/0")
    assert isinstance(modern, WzSubProperty)
    assert migration.child_value(modern, "action") == 1
    assert migration.child_value(modern, "type") == 2
    assert migration.child_value(modern, "bulletSpeed") == 140


def assert_client_contract() -> None:
    path = ROOT / f"clien/Data/Mob/{MOB_ID}.img"
    image = migration.arc.load_image(path, migration.arc.GMS_KEY)
    assert not image.truncated
    assert not image.parse_warnings

    info = image.root.get(ATTACK_INFO_PATH)
    assert isinstance(info, WzSubProperty)
    assert tuple(child.name for child in info.children()) == (
        "range", "ball", "hit", "type", "attackAfter", "bulletSpeed"
    )
    assert migration.child_value(info, "type") == 2
    assert migration.child_value(info, "bulletSpeed") == 140
    assert migration.child_value(info.child("hit"), "attach") == 1

    canvas_count = 0
    stack = [image.root]
    while stack:
        node = stack.pop()
        if isinstance(node, WzCanvasProperty):
            canvas_count += 1
            assert (node.format, node.format2) == (1, 0)
            assert decode_canvas(node, region="GMS").convert("RGBA").getbbox() is not None
        if isinstance(node, WzSubProperty):
            stack.extend(node.children())
    assert canvas_count == 88


def assert_server_contract() -> None:
    path = ROOT / f"gms-server/wz/Mob.wz/{MOB_ID}.img.xml"
    root = ET.parse(path).getroot()
    info = root.find('./imgdir[@name="attack1"]/imgdir[@name="info"]')
    assert info is not None
    assert info.find('./imgdir[@name="ball"]') is not None
    assert info.find('./int[@name="hit"]') is None
    assert info.find('./imgdir[@name="hit"]/int[@name="attach"]').get("value") == "1"
    assert info.find('./int[@name="type"]').get("value") == "2"
    assert info.find('./int[@name="bulletSpeed"]').get("value") == "140"


def skill_values(skills: WzSubProperty) -> tuple[dict[str, int], ...]:
    return tuple(
        {field.name: int(migration.child_value(entry, field.name)) for field in entry.children()}
        for entry in skills.children()
    )


def assert_scene_source_contract() -> None:
    source = migration.arc.extract_mob(SCENE_MOB_ID)
    image = migration.arc.load_image(source, migration.arc.BMS_KEY)
    skills = image.root.get("info/skill")
    assert isinstance(skills, WzSubProperty)
    assert skill_values(skills) == SOURCE_SCENE_SKILLS
    for (skill_id, level), expected in SOURCE_SCENE_LEVELS.items():
        source = migration.arc.load_image(
            migration.extract_nohime_mob_skill(skill_id), migration.arc.BMS_KEY
        )
        node = source.root.get(f"level/{level}")
        assert isinstance(node, WzSubProperty)
        assert migration.scalar_level_values(node) == expected


def assert_scene_client_contract() -> None:
    mob = migration.arc.load_image(
        ROOT / f"clien/Data/Mob/{SCENE_MOB_ID}.img", migration.arc.GMS_KEY
    )
    assert not mob.truncated
    assert not mob.parse_warnings
    skills = mob.root.get("info/skill")
    assert isinstance(skills, WzSubProperty)
    assert skill_values(skills) == CLIENT_SCENE_SKILLS
    assert isinstance(mob.root.child("skill1"), WzSubProperty)
    assert isinstance(mob.root.child("skillAfter1"), WzSubProperty)
    assert isinstance(mob.root.child("skill2"), WzSubProperty)

    visible = 0
    placeholders = []
    stack = [(mob.root, "")]
    while stack:
        node, parent_path = stack.pop()
        path = f"{parent_path}/{node.name}" if parent_path else node.name
        if isinstance(node, WzCanvasProperty):
            assert (node.format, node.format2) == (1, 0)
            if decode_canvas(node, region="GMS").convert("RGBA").getbbox() is None:
                placeholders.append(path)
            else:
                visible += 1
        if isinstance(node, WzSubProperty):
            stack.extend((child, path) for child in node.children())
    assert visible == 300
    assert sorted(placeholders) == [
        "9450040.img/attack6/info/screenCenter/0",
        "9450040.img/skillAfter1/0",
    ]

    mob_skills = migration.arc.load_image(
        ROOT / "clien/Data/Skill/MobSkill.img", migration.arc.GMS_KEY
    )
    assert not mob_skills.truncated
    assert not mob_skills.parse_warnings
    levels = mob_skills.root.get("200/level")
    assert isinstance(levels, WzSubProperty)
    assert [child.name for child in levels.children()][-2:] == ["235", "236"]
    for level, expected in CLIENT_SCENE_LEVELS.items():
        node = levels.child(str(level))
        assert isinstance(node, WzSubProperty)
        assert migration.scalar_level_values(node) == expected

    for mob_id, expected_canvases in SCENE_SUMMON_MOBS.items():
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        summon = migration.arc.load_image(path, migration.arc.GMS_KEY)
        assert not summon.truncated
        assert not summon.parse_warnings
        canvas_count = 0
        visible_count = 0
        stack = [summon.root]
        while stack:
            node = stack.pop()
            if isinstance(node, WzCanvasProperty):
                canvas_count += 1
                assert (node.format, node.format2) == (1, 0)
                if decode_canvas(node, region="GMS").convert("RGBA").getbbox() is not None:
                    visible_count += 1
            if isinstance(node, WzSubProperty):
                stack.extend(node.children())
        assert canvas_count == expected_canvases
        assert visible_count > 0

    strings = migration.arc.load_image(
        ROOT / "clien/Data/String/Mob.img", migration.arc.GMS_KEY
    )
    for mob_id in SCENE_SUMMON_MOBS:
        entry = strings.root.child(str(mob_id))
        assert isinstance(entry, WzSubProperty)
        assert migration.child_value(entry, "name") == SCENE_SUMMON_NAME


def assert_scene_server_contract() -> None:
    mob_root = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{SCENE_MOB_ID}.img.xml").getroot()
    skills = mob_root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    assert skills is not None
    actual = tuple(
        {field.get("name"): int(field.get("value")) for field in entry}
        for entry in skills
    )
    assert actual == CLIENT_SCENE_SKILLS

    root = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    levels = root.find('./imgdir[@name="200"]/imgdir[@name="level"]')
    assert levels is not None
    assert [child.get("name") for child in levels][-2:] == ["235", "236"]
    for level, expected in CLIENT_SCENE_LEVELS.items():
        node = levels.find(f'./imgdir[@name="{level}"]')
        assert node is not None
        assert tuple((child.get("name"), int(child.get("value"))) for child in node) == expected

    for mob_id in SCENE_SUMMON_MOBS:
        summon = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        assert summon.get("name") == f"{mob_id}.img"
    for tree in ("wz", "wz-zh-CN"):
        strings = ET.parse(ROOT / f"gms-server/{tree}/String.wz/Mob.img.xml").getroot()
        for mob_id in SCENE_SUMMON_MOBS:
            name = strings.find(f'./imgdir[@name="{mob_id}"]/string[@name="name"]')
            assert name is not None
            assert name.get("value") == SCENE_SUMMON_NAME


assert_source_contract()
assert_client_contract()
assert_server_contract()
assert_scene_source_contract()
assert_scene_client_contract()
assert_scene_server_contract()
print("Princess No mob ballistic and scene skill contract checks passed")
