#!/usr/bin/env python3
"""Project Bloody Queen 201 MobSkills onto client-present summon 200.

Crash evidence (session-20260910-175106-pid32):
  first_chance_av eip=0066E88F eax=0 target=4 ecx=0x34
  0x34 == Queen info/skill/2 level 52. Client Skill/MobSkill.img has no 201.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


SOURCE_SKILL = 201
TARGET_SKILL = 200
MOB_IDS = (8920000, 8920001)
FORBIDDEN = {188, 191, 201, 202, 203}


def client_mob_path(mob_id: int) -> Path:
    return ROOT / f"clien/Data/Mob/{mob_id}.img"


def server_mob_path(tree: str, mob_id: int) -> Path:
    return ROOT / f"gms-server/{tree}/Mob.wz/{mob_id}.img.xml"


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


def patch_client(mob_id: int) -> bool:
    path = client_mob_path(mob_id)
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{mob_id} missing info")
    patched = original
    approved: set[tuple[str, ...]] = set()
    for slot, skill_id, _level in skill_slots(info):
        if skill_id != SOURCE_SKILL:
            continue
        target = ("info", "skill", slot, "skill")
        patched = arc.mutate_img(
            patched, "edit", target, values={"value": TARGET_SKILL}, region="GMS"
        ).data
        approved.add(target)
    if patched == original:
        return False
    arc.verify_raw_record_scope(original, patched, approved, allow_additions=False)
    from wzpy import WzImage

    checked_image = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    checked_image.parse()
    if checked_image.truncated or checked_image.parse_warnings:
        raise RuntimeError(f"{mob_id} parse failed after skill projection")
    leftover = [
        skill_id
        for _slot, skill_id, _level in skill_slots(checked_image.root.child("info"))
        if skill_id in FORBIDDEN
    ]
    if leftover:
        raise RuntimeError(f"{mob_id} still has forbidden skills {leftover}")
    arc.atomic_write_bytes(path, patched)
    return True


def patch_server(mob_id: int) -> bool:
    changed = False
    for tree in ("wz", "wz-zh-CN"):
        path = server_mob_path(tree, mob_id)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        from xml.etree import ElementTree as ET

        root = ET.fromstring(text)
        skill = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
        if skill is None:
            continue
        for child in list(skill):
            if child.get("name") is None or not str(child.get("name")).isdigit():
                continue
            node = child.find('./int[@name="skill"]')
            if node is None or node.get("value") != str(SOURCE_SKILL):
                continue
            text = arc.mutate_xml(
                text,
                "edit",
                ("info", "skill", child.get("name"), "skill"),
                kind="Int",
                values={"value": TARGET_SKILL},
            )
        if text == original:
            continue
        root = ET.fromstring(text)
        leftover = [
            int(node.get("value") or 0)
            for child in root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
            for node in [child.find('./int[@name="skill"]')]
            if node is not None and int(node.get("value") or 0) in FORBIDDEN
        ]
        if leftover:
            raise RuntimeError(f"{path} still has forbidden skills {leftover}")
        arc.atomic_write_text(path, text)
        changed = True
    return changed


def main() -> int:
    for mob_id in MOB_IDS:
        client_changed = patch_client(mob_id)
        server_changed = patch_server(mob_id)
        print(f"{mob_id} client={client_changed} server={server_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
