#!/usr/bin/env python3
"""Queen MobSkill 201 must be projected onto client-present 200."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/patch_queen_forbidden_mobskill.py"
SPEC = importlib.util.spec_from_file_location("patch_queen_forbidden_mobskill", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def main() -> int:
    errors: list[str] = []
    mob_skill = patch.load_checked(ROOT / "clien/Data/Skill/MobSkill.img", patch.arc.GMS_KEY)
    if mob_skill.root.child(str(patch.SOURCE_SKILL)) is not None:
        errors.append("client unexpectedly gained MobSkill 201")
    skill_200 = mob_skill.root.child(str(patch.TARGET_SKILL))
    if skill_200 is None or skill_200.child("level") is None:
        errors.append("client missing MobSkill 200")
    for mob_id in patch.MOB_IDS:
        image = patch.load_checked(patch.client_mob_path(mob_id), patch.arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            errors.append(f"unsafe {mob_id}")
        rows = patch.skill_slots(image.root.child("info"))
        for slot, skill_id, level in rows:
            if skill_id in patch.FORBIDDEN:
                errors.append(f"{mob_id} skill {slot} still {skill_id}")
            if skill_id == patch.TARGET_SKILL:
                level_node = skill_200.child("level").child(str(level)) if skill_200 else None
                if level_node is None:
                    errors.append(f"MobSkill 200 missing level {level} used by {mob_id}/{slot}")
        xml_path = patch.server_mob_path("wz", mob_id)
        root = ET.parse(xml_path).getroot()
        for child in root.find('./imgdir[@name="info"]/imgdir[@name="skill"]'):
            node = child.find('./int[@name="skill"]')
            if node is not None and int(node.get("value") or 0) in patch.FORBIDDEN:
                errors.append(f"server {mob_id} still has {node.get('value')}")
    if errors:
        print("\n".join(errors))
        return 1
    print("queen mobskill projection ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
