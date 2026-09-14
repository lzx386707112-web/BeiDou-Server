#!/usr/bin/env python3
"""Project Pierre, Von Bon, and Vellum MobSkills onto client-present IDs/levels.

Queen already uses 200. Same crash class: missing Skill/MobSkill.img IDs
201/191/203, or 170 levels other than 1.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzImage, WzSubProperty  # noqa: E402


MOB_IDS = (8900000, 8910000, 8930000)
FALLBACK_SKILL = 200
MISSING_IDS = {188, 191, 201, 202, 203}


def client_mob_path(mob_id: int) -> Path:
    return ROOT / f"clien/Data/Mob/{mob_id}.img"


def server_mob_path(tree: str, mob_id: int) -> Path:
    return ROOT / f"gms-server/{tree}/Mob.wz/{mob_id}.img.xml"


def mobskill_catalog() -> tuple[set[int], dict[int, set[int]]]:
    image = load_checked(ROOT / "clien/Data/Skill/MobSkill.img", arc.GMS_KEY)
    present: set[int] = set()
    levels: dict[int, set[int]] = {}
    for child in image.root.children():
        if not child.name.isdigit():
            continue
        skill_id = int(child.name)
        present.add(skill_id)
        level_root = child.child("level")
        if isinstance(level_root, WzSubProperty):
            levels[skill_id] = {
                int(node.name) for node in level_root.children() if node.name.isdigit()
            }
    return present, levels


def skill_slots(info: WzSubProperty) -> list[tuple[str, int, int]]:
    skill = info.child("skill")
    if not isinstance(skill, WzSubProperty):
        raise RuntimeError("missing info/skill")
    rows = []
    for child in skill.children():
        if not child.name.isdigit():
            continue
        rows.append(
            (
                child.name,
                int(arc.child_value(child, "skill") or 0),
                int(arc.child_value(child, "level") or 0),
            )
        )
    return rows


def project_skill(
    skill_id: int,
    level: int,
    present: set[int],
    levels: dict[int, set[int]],
) -> tuple[int, int]:
    available = levels.get(skill_id, set())
    if skill_id in present and level in available:
        return skill_id, level
    fallback_levels = levels.get(FALLBACK_SKILL, set())
    if skill_id not in present:
        return FALLBACK_SKILL, level if level in fallback_levels else 1
    if level in fallback_levels:
        return FALLBACK_SKILL, level
    if available:
        return skill_id, max(available)
    return FALLBACK_SKILL, 1


def problems_for(rows: list[tuple[str, int, int]], present: set[int], levels: dict[int, set[int]]) -> list[str]:
    found = []
    for slot, skill_id, level in rows:
        if skill_id not in present:
            found.append(f"{slot}:{skill_id}/{level} missing id")
        elif level not in levels.get(skill_id, set()):
            found.append(f"{slot}:{skill_id}/{level} missing level")
    return found


def parse_img(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name} parse failed")
    return image


def patch_client(mob_id: int, present: set[int], levels: dict[int, set[int]]) -> bool:
    path = client_mob_path(mob_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id} missing info")
    patched = original
    approved: set[tuple[str, ...]] = set()
    for slot, skill_id, level in skill_slots(info):
        new_id, new_level = project_skill(skill_id, level, present, levels)
        if new_id != skill_id:
            target = ("info", "skill", slot, "skill")
            patched = arc.mutate_img(
                patched, "edit", target, values={"value": new_id}, region="GMS"
            ).data
            approved.add(target)
        if new_level != level:
            target = ("info", "skill", slot, "level")
            patched = arc.mutate_img(
                patched, "edit", target, values={"value": new_level}, region="GMS"
            ).data
            approved.add(target)
    if patched == original:
        return False
    arc.verify_raw_record_scope(original, patched, approved, allow_additions=False)
    checked = parse_img(patched, path.name)
    leftover = problems_for(skill_slots(checked.root.child("info")), present, levels)
    if leftover:
        raise RuntimeError(f"{mob_id} still broken: {leftover}")
    arc.atomic_write_bytes(path, patched)
    return True


def patch_server(mob_id: int, present: set[int], levels: dict[int, set[int]]) -> bool:
    changed = False
    for tree in ("wz", "wz-zh-CN"):
        path = server_mob_path(tree, mob_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        root = ET.fromstring(text)
        skill = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
        if skill is None:
            continue
        for child in list(skill):
            slot = child.get("name")
            if not slot or not slot.isdigit():
                continue
            skill_node = child.find('./int[@name="skill"]')
            level_node = child.find('./int[@name="level"]')
            if skill_node is None or level_node is None:
                continue
            skill_id = int(skill_node.get("value") or 0)
            level = int(level_node.get("value") or 0)
            new_id, new_level = project_skill(skill_id, level, present, levels)
            if new_id != skill_id:
                text = arc.mutate_xml(
                    text,
                    "edit",
                    ("info", "skill", slot, "skill"),
                    kind="Int",
                    values={"value": new_id},
                )
            if new_level != level:
                text = arc.mutate_xml(
                    text,
                    "edit",
                    ("info", "skill", slot, "level"),
                    kind="Int",
                    values={"value": new_level},
                )
        if text == original:
            continue
        root = ET.fromstring(text)
        rows = []
        for child in root.find('./imgdir[@name="info"]/imgdir[@name="skill"]'):
            if not (child.get("name") or "").isdigit():
                continue
            skill_node = child.find('./int[@name="skill"]')
            level_node = child.find('./int[@name="level"]')
            rows.append(
                (
                    child.get("name"),
                    int(skill_node.get("value") or 0) if skill_node is not None else 0,
                    int(level_node.get("value") or 0) if level_node is not None else 0,
                )
            )
        leftover = problems_for(rows, present, levels)
        if leftover:
            raise RuntimeError(f"{path} still broken: {leftover}")
        arc.atomic_write_text(path, text)
        changed = True
    return changed


def main() -> int:
    present, levels = mobskill_catalog()
    for mob_id in MOB_IDS:
        client_changed = patch_client(mob_id, present, levels)
        server_changed = patch_server(mob_id, present, levels)
        image = load_checked(client_mob_path(mob_id), arc.GMS_KEY)
        print(
            f"{mob_id} client={client_changed} server={server_changed} "
            f"skills={skill_slots(image.root.child('info'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
