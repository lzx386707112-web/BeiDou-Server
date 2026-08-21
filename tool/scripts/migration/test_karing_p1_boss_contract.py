#!/usr/bin/env python3
"""Contract checks for the Karing P1 beast boss migration."""

from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_karing_p1_bosses.py"
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzKey,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402


def load_migration_module():
    spec = importlib.util.spec_from_file_location("migrate_karing_p1_bosses", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_karing_p1_client_mobs_are_legacy_canvas_safe():
    migration = load_migration_module()
    for mob_id in migration.MOB_IDS:
        assert migration.LEGACY_CANVAS_SCALE[mob_id] == 1.0
        image_path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        source = migration.extract_source(mob_id)
        source_image = WzImage.from_bytes(
            source.read_bytes(), key=WzKey.for_region("BMS"), name=source.name
        )
        source_image.parse()
        expected_actions = migration.projected_action_frame_counts(
            mob_id, migration.action_frame_counts(source_image)
        )
        source_attack_root = source_image.root.get("info/attack")
        source_fsm_actions = {
            f"attack{migration.child_value(entry, 'action')}"
            for entry in source_attack_root.children()
            if migration.child_value(entry, "onlyFsm") == 1
        }
        blocked_fsm_actions = migration.LEGACY_FSM_ONLY_ACTIONS.get(mob_id, set())
        assert blocked_fsm_actions <= source_fsm_actions

        image = WzImage.from_bytes(
            image_path.read_bytes(), key=WzKey.for_region("GMS"), name=image_path.name
        )
        image.parse()
        assert not image.truncated
        assert image.parse_warnings == []
        assert migration.action_frame_counts(image) == expected_actions
        if mob_id in migration.FULL_DEATH_ACTIONS:
            expected_frames, expected_duration = migration.FULL_DEATH_ACTIONS[mob_id]
            die1 = image.root.child("die1")
            frames = sorted(
                (child for child in die1.children() if child.name.isdigit()),
                key=lambda child: int(child.name),
            )
            assert len(frames) == expected_frames
            assert sum(migration.action_frame_delay(die1, frame) for frame in frames) == expected_duration
        assert image.root.child("flip") is None
        assert all(image.root.child(action) is not None for action in blocked_fsm_actions)

        attack_numbers = sorted(
            int(child.name.removeprefix("attack"))
            for child in image.root.children()
            if child.name.startswith("attack")
        )
        assert attack_numbers == list(range(1, len(attack_numbers) + 1))

        for action_name, (target_name, selected_frames) in (
            migration.LEGACY_ACTION_FRAME_UOLS.get(mob_id, {}).items()
        ):
            action = image.root.child(action_name)
            target = image.root.child(target_name)
            assert isinstance(action, WzSubProperty)
            assert isinstance(target, WzSubProperty)
            target_frames = tuple(
                child.name for child in target.children() if child.name.isdigit()
            )
            frame_names = target_frames if selected_frames is None else selected_frames
            frames = tuple(child for child in action.children() if child.name.isdigit())
            assert len(frames) == len(frame_names)
            resolved = []
            for index, (frame, target_frame) in enumerate(zip(frames, frame_names)):
                assert isinstance(frame, WzUolProperty)
                assert frame.name == str(index)
                assert frame.value == f"../{target_name}/{target_frame}"
                resolved.append(frame.parent.get(str(frame.value)))
            assert all(isinstance(frame, WzCanvasProperty) for frame in resolved)
            assert any(
                decode_canvas(frame, region="GMS").convert("RGBA").getbbox() is not None
                for frame in resolved
            )

        canvases = []
        texture_bytes = 0
        missing_origins = set()
        for node, node_path in migration.walk(image.root):
            if isinstance(node, WzCanvasProperty):
                canvases.append(node)
                assert int(node.format) == 1
                assert int(node.format2) == 0
                assert int(node.width) <= migration.LEGACY_MAX_CANVAS_EDGE
                assert int(node.height) <= migration.LEGACY_MAX_CANVAS_EDGE
                assert node.child("_outlink") is None
                assert node.child("_inlink") is None
                if node.child("origin") is None:
                    missing_origins.add(node_path)
                texture_bytes += (
                    migration.next_power_of_two(int(node.width))
                    * migration.next_power_of_two(int(node.height))
                    * 2
                )
        assert canvases
        largest = max(canvases, key=lambda canvas: int(canvas.width) * int(canvas.height))
        assert decode_canvas(largest, region="GMS").convert("RGBA").getbbox() is not None

        assert texture_bytes > 0
        assert missing_origins == migration.LEGACY_MISSING_ORIGIN_PATHS[mob_id]
        for path, expected in migration.LEGACY_SYNTHESIZED_ORIGINS.get(
            mob_id, {}
        ).items():
            origin = image.root.get(path).child("origin")
            assert isinstance(origin, WzVectorProperty)
            assert (origin.x, origin.y) == expected

        for action in image.root.children():
            if not action.name.startswith("attack"):
                continue
            action_info = action.child("info")
            if not isinstance(action_info, WzSubProperty):
                continue
            assert action_info.child("areaAttack") is None
            assert all(
                action_info.child(name) is None
                for name in migration.LEGACY_ACTION_INFO_UNSUPPORTED
            )

        for (range_mob_id, action_name), (expected_lt, expected_rb) in (
            migration.LEGACY_AREA_RANGES.items()
        ):
            if range_mob_id != mob_id:
                continue
            legacy_range = image.root.get(f"{action_name}/info/range")
            assert isinstance(legacy_range, WzSubProperty)
            lt = legacy_range.child("lt")
            rb = legacy_range.child("rb")
            assert isinstance(lt, WzVectorProperty)
            assert isinstance(rb, WzVectorProperty)
            assert (lt.x, lt.y) == expected_lt
            assert (rb.x, rb.y) == expected_rb

        if mob_id == 8880830:
            assert image.root.get("attack4/info/hit") is None

        info = image.root.child("info")
        assert migration.child_value(info, "eva") == migration.LEGACY_EVASION
        assert migration.child_value(info, "maxHP") == migration.CLIENT_MAX_HP
        skill_root = info.child("skill")
        actual_skills = [] if skill_root is None else [
            (
                migration.child_value(entry, "skill"),
                migration.child_value(entry, "level"),
                migration.child_value(entry, "action"),
            )
            for entry in skill_root.children()
        ]
        assert actual_skills == list(migration.LEGACY_MOB_SKILLS[mob_id])

        for attack_number, (disease, level) in migration.LEGACY_ATTACK_DISEASES.get(
            mob_id, {}
        ).items():
            attack_info = image.root.get(f"attack{attack_number}/info")
            assert migration.child_value(attack_info, "disease") == disease
            assert migration.child_value(attack_info, "level") == level


def test_karing_p1_server_xml_has_no_modern_auto_skill_fields():
    migration = load_migration_module()
    for mob_id in migration.MOB_IDS:
        path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        root = ET.parse(path).getroot()
        assert root.get("name") == f"{mob_id}.img"
        assert all(child.get("name") != "flip" for child in root)
        blocked_fsm_actions = migration.LEGACY_FSM_ONLY_ACTIONS.get(mob_id, set())
        root_names = {entry.get("name") for entry in root}
        assert blocked_fsm_actions <= root_names
        attack_names = [
            child.get("name") for child in root if child.get("name", "").startswith("attack")
        ]
        assert attack_names == [f"attack{index}" for index in range(1, len(attack_names) + 1)]
        info = next(child for child in root if child.get("name") == "info")
        names = {child.get("name") for child in info}
        assert names.isdisjoint(migration.KARING_INFO_UNSUPPORTED)
        assert {"boss", "mobType", "PDDamage", "MDDamage"} <= names
        eva = next(child for child in info if child.get("name") == "eva")
        assert int(eva.get("value")) == migration.LEGACY_EVASION
        max_hp = next(child for child in info if child.get("name") == "maxHP")
        assert max_hp.tag == "string"
        assert int(max_hp.get("value")) == migration.TMS_NORMAL_HP[mob_id]

        for property_path, expected in migration.LEGACY_SYNTHESIZED_ORIGINS.get(
            mob_id, {}
        ).items():
            node = root
            for part in property_path.split("/"):
                node = next(child for child in node if child.get("name") == part)
            origin = next(child for child in node if child.get("name") == "origin")
            assert (int(origin.get("x")), int(origin.get("y"))) == expected

        skill_root = next(
            (child for child in info if child.get("name") == "skill"), None
        )
        actual_skills = []
        if skill_root is not None:
            for entry in skill_root:
                values = {child.get("name"): int(child.get("value")) for child in entry}
                actual_skills.append((values["skill"], values["level"], values["action"]))
        assert actual_skills == list(migration.LEGACY_MOB_SKILLS[mob_id])

        for action_name, (target_name, selected_frames) in (
            migration.LEGACY_ACTION_FRAME_UOLS.get(mob_id, {}).items()
        ):
            action = next(child for child in root if child.get("name") == action_name)
            uols = [child for child in action if child.tag == "uol" and child.get("name", "").isdigit()]
            if selected_frames is None:
                target = next(child for child in root if child.get("name") == target_name)
                selected_frames = tuple(
                    child.get("name") for child in target if child.get("name", "").isdigit()
                )
            assert [entry.get("name") for entry in uols] == [
                str(index) for index in range(len(selected_frames))
            ]
            assert [entry.get("value") for entry in uols] == [
                f"../{target_name}/{frame_name}" for frame_name in selected_frames
            ]

        for action in root:
            if not action.get("name", "").startswith("attack"):
                continue
            action_info = next(
                (child for child in action if child.get("name") == "info"), None
            )
            if action_info is None:
                continue
            names = {child.get("name") for child in action_info}
            assert "areaAttack" not in names
            assert names.isdisjoint(migration.LEGACY_ACTION_INFO_UNSUPPORTED)

        for (range_mob_id, action_name), (expected_lt, expected_rb) in (
            migration.LEGACY_AREA_RANGES.items()
        ):
            if range_mob_id != mob_id:
                continue
            action = next(child for child in root if child.get("name") == action_name)
            action_info = next(child for child in action if child.get("name") == "info")
            legacy_range = next(child for child in action_info if child.get("name") == "range")
            lt = next(child for child in legacy_range if child.get("name") == "lt")
            rb = next(child for child in legacy_range if child.get("name") == "rb")
            assert (int(lt.get("x")), int(lt.get("y"))) == expected_lt
            assert (int(rb.get("x")), int(rb.get("y"))) == expected_rb

        if mob_id == 8880830:
            attack4 = next(child for child in root if child.get("name") == "attack4")
            attack4_info = next(child for child in attack4 if child.get("name") == "info")
            assert all(child.get("name") != "hit" for child in attack4_info)

        for attack_number, (disease, level) in migration.LEGACY_ATTACK_DISEASES.get(
            mob_id, {}
        ).items():
            attack = next(child for child in root if child.get("name") == f"attack{attack_number}")
            attack_info = next(child for child in attack if child.get("name") == "info")
            values = {
                child.get("name"): int(child.get("value"))
                for child in attack_info
                if child.get("value") is not None
            }
            assert values["disease"] == disease
            assert values["level"] == level


def test_karing_p1_projected_mob_skills_exist_in_client_and_server():
    migration = load_migration_module()
    client_path = ROOT / "clien/Data/Skill/MobSkill.img"
    client = WzImage.from_bytes(
        client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
    )
    client.parse()
    assert not client.truncated
    assert client.parse_warnings == []

    server = ET.parse(ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml").getroot()
    server_skills = {child.get("name"): child for child in server}
    for projected in migration.LEGACY_MOB_SKILLS.values():
        for skill_id, level, _action in projected:
            assert client.root.get(f"{skill_id}/level/{level}") is not None
            level_root = next(
                child
                for child in server_skills[str(skill_id)]
                if child.get("name") == "level"
            )
            assert any(child.get("name") == str(level) for child in level_root)


def test_karing_p1_mob_names_exist_in_client_and_server_strings():
    migration = load_migration_module()
    client_path = ROOT / "clien/Data/String/Mob.img"
    client = WzImage.from_bytes(
        client_path.read_bytes(), key=WzKey.for_region("GMS"), name=client_path.name
    )
    client.parse()
    assert not client.truncated
    assert client.parse_warnings == []

    for mob_id, expected_name in migration.MOB_NAMES.items():
        node = client.root.child(str(mob_id))
        assert isinstance(node, WzSubProperty)
        assert migration.child_value(node, "name") == expected_name

    for path in (
        ROOT / "gms-server/wz/String.wz/Mob.img.xml",
        ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
    ):
        root = ET.parse(path).getroot()
        strings = {child.get("name"): child for child in root}
        for mob_id, expected_name in migration.MOB_NAMES.items():
            entry = strings[str(mob_id)]
            name_node = next(child for child in entry if child.get("name") == "name")
            assert name_node.get("value") == expected_name
