#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/resource-workbench"))
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from map_mob import app  # noqa: E402
from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

import migrate_root_abyss_boss_contracts as migration  # noqa: E402
import activate_vellum_skill_actions as vellum  # noqa: E402


EXISTING_MOBS = tuple(migration.MOB_INFO)
NEW_MOBS = (8900003, 8920006)
ALLOWED_TOP_LEVEL = {
    8900001: {"info", "skillAfter1"},
    8910000: {"info", "skillAfter1", "skillAfter3", "skillAfter6"},
}


def scalar(node: WzSubProperty, name: str) -> int:
    return int(node.child(name).value)


def skill_rows(node: WzSubProperty) -> tuple[dict[str, int], ...]:
    return tuple(
        {field.name: int(field.value) for field in row.children()}
        for row in node.children()
    )


def assert_client_mobs() -> None:
    for mob_id, expected in migration.MOB_INFO.items():
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        image = app.load_image(path)
        assert not image.truncated and not image.parse_warnings
        info = image.root.get("info")
        assert isinstance(info, WzSubProperty)
        for name, value in expected.items():
            assert scalar(info, name) == value, (mob_id, name)
        if mob_id in migration.CLIENT_SKILLS and mob_id != 8930000:
            assert skill_rows(info.child("skill")) == migration.CLIENT_SKILLS[mob_id]
        if mob_id == 8920000:
            assert info.child("revive") is None
        if mob_id == 8930000:
            actions = tuple(
                child.name for child in image.root.children()
                if child.name.startswith("attack")
            )
            assert actions == tuple(f"attack{index}" for index in range(1, 9))
            for name in ("skill1", "skill2", "skill3"):
                assert isinstance(image.root.get(name), WzSubProperty), (mob_id, name)

    for mob_id, actions in migration.MISSING_ACTIONS.items():
        image = app.load_image(ROOT / f"clien/Data/Mob/{mob_id}.img")
        for action in actions:
            assert isinstance(image.root.get(action), WzSubProperty), (mob_id, action)


def assert_server_mobs() -> None:
    for mob_id, expected in migration.MOB_INFO.items():
        root = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml").getroot()
        info = root.find('./imgdir[@name="info"]')
        assert info is not None
        for name, value in expected.items():
            node = info.find(f'./*[@name="{name}"]')
            assert node is not None and int(node.get("value")) == value, (mob_id, name)
        if mob_id in migration.SERVER_SKILLS and mob_id != 8930000:
            table = info.find('./imgdir[@name="skill"]')
            rows = tuple(
                {field.get("name"): int(field.get("value")) for field in row}
                for row in table.findall("./imgdir")
            )
            assert rows == migration.SERVER_SKILLS[mob_id], mob_id
        if mob_id == 8920000:
            assert info.find('./imgdir[@name="revive"]') is None


def assert_mob_skills() -> None:
    client = app.load_image(ROOT / "clien/Data/Skill/MobSkill.img")
    levels = client.root.get("200/level")
    for level, expected in migration.PROJECTED_MOB_SKILLS.items():
        node = levels.child(str(level))
        assert isinstance(node, WzSubProperty), level
        for name, value in expected.items():
            actual = node.child(name)
            assert actual is not None, (level, name)
            if isinstance(value, tuple):
                assert tuple(actual.value) == value, (level, name)
            elif isinstance(value, str) and not value.lstrip("-").isdigit():
                assert str(actual.value) == value, (level, name)
            else:
                assert int(actual.value) == int(value), (level, name)

    server = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    for (skill_id, level), expected in migration.SERVER_MOB_SKILL_LEVELS.items():
        node = server.find(
            f'./imgdir[@name="{skill_id}"]/imgdir[@name="level"]/imgdir[@name="{level}"]'
        )
        assert node is not None, (skill_id, level)
        values = {child.get("name"): child for child in node}
        for name, value in expected.items():
            child = values[name]
            if isinstance(value, tuple):
                assert (int(child.get("x")), int(child.get("y"))) == value
            elif isinstance(value, str) and not value.lstrip("-").isdigit():
                assert child.get("value") == value
            else:
                assert int(child.get("value")) == int(value)


def assert_new_mobs_and_canvases() -> None:
    for mob_id in (*EXISTING_MOBS, *NEW_MOBS):
        image = app.load_image(ROOT / f"clien/Data/Mob/{mob_id}.img")
        canvases = 0
        visible = 0
        stack = [image.root]
        while stack:
            node = stack.pop()
            if isinstance(node, WzCanvasProperty):
                canvases += 1
                assert (node.format, node.format2) == (1, 0), (mob_id, node.name)
                if decode_canvas(node, region="GMS").convert("RGBA").getbbox():
                    visible += 1
            if isinstance(node, WzSubProperty):
                stack.extend(node.children())
        assert canvases and visible, mob_id
        ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml")


def assert_raw_scope() -> None:
    for mob_id in EXISTING_MOBS:
        rel = f"clien/Data/Mob/{mob_id}.img"
        if mob_id == 8930000:
            # The activation generator audits every insertion against the
            # working artifact.
            assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == (
                "fb630d477f95e549fa775be5ca5ea30678b567cc043c55ca9ccb54bae9cb812e"
            )
            continue
        before = subprocess.run(
            ["git", "cat-file", "blob", f"HEAD:{rel}"], cwd=ROOT,
            check=True, capture_output=True,
        ).stdout
        after = (ROOT / rel).read_bytes()
        before_records, before_orders = app.arc.raw_record_state(before)
        after_records, after_orders = app.arc.raw_record_state(after)
        allowed = ALLOWED_TOP_LEVEL.get(mob_id, {"info"})
        for path, raw in before_records.items():
            if path and path[0] in allowed:
                continue
            assert after_records.get(path) == raw, (mob_id, path)
        for parent, names in before_orders.items():
            if parent and parent[0] in allowed:
                continue
            current = after_orders[parent]
            assert tuple(name for name in current if name in names) == names, (mob_id, parent)

    rel = "clien/Data/Skill/MobSkill.img"
    before = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{rel}"], cwd=ROOT,
        check=True, capture_output=True,
    ).stdout
    after = (ROOT / rel).read_bytes()
    before_records, _ = app.arc.raw_record_state(before)
    after_records, _ = app.arc.raw_record_state(after)
    targets = {("200", "level", str(level)) for level in migration.PROJECTED_MOB_SKILLS}
    targets.add(("100", "level", "30"))
    for path, raw in before_records.items():
        if any(path[:len(target)] == target or target[:len(path)] == path for target in targets):
            continue
        assert after_records.get(path) == raw, path


def main() -> None:
    assert_client_mobs()
    assert_server_mobs()
    assert_mob_skills()
    assert_new_mobs_and_canvases()
    assert_raw_scope()
    vellum.validate_mob(vellum.MOB_IMG.read_bytes())
    vellum.validate_mob_xml(vellum.MOB_XML.read_bytes())
    vellum.validate_skill(vellum.SKILL_IMG.read_bytes())
    vellum.validate_skill_xml(vellum.SKILL_XML.read_bytes())
    print("Root Abyss boss contracts: OK")


if __name__ == "__main__":
    main()
