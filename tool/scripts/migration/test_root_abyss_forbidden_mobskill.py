#!/usr/bin/env python3
"""Pierre, Von Bon, and Vellum must only reference client-present MobSkills."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/patch_root_abyss_forbidden_mobskill.py"
SPEC = importlib.util.spec_from_file_location("patch_root_abyss_forbidden_mobskill", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def main() -> int:
    errors: list[str] = []
    present, levels = patch.mobskill_catalog()
    expected = {
        8900000: [("0", 200, 40)],
        8910000: [
            ("0", 200, 1),
            ("1", 184, 1),
            ("2", 200, 11),
            ("3", 200, 1),
            ("4", 200, 2),
            ("5", 200, 14),
        ],
        8930000: [("0", 200, 13), ("1", 200, 49)],
    }
    for mob_id in patch.MOB_IDS:
        image = patch.load_checked(patch.client_mob_path(mob_id), patch.arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            errors.append(f"unsafe {mob_id}")
        rows = patch.skill_slots(image.root.child("info"))
        leftover = patch.problems_for(rows, present, levels)
        if leftover:
            errors.extend(f"{mob_id} {item}" for item in leftover)
        if rows != expected[mob_id]:
            errors.append(f"{mob_id} projection {rows} != {expected[mob_id]}")
        xml_path = patch.server_mob_path("wz", mob_id)
        root = ET.parse(xml_path).getroot()
        xml_rows = []
        for child in root.find('./imgdir[@name="info"]/imgdir[@name="skill"]'):
            if not (child.get("name") or "").isdigit():
                continue
            skill_node = child.find('./int[@name="skill"]')
            level_node = child.find('./int[@name="level"]')
            xml_rows.append(
                (
                    child.get("name"),
                    int(skill_node.get("value") or 0),
                    int(level_node.get("value") or 0),
                )
            )
        if xml_rows != expected[mob_id]:
            errors.append(f"server {mob_id} {xml_rows} != {expected[mob_id]}")
    if errors:
        print("\n".join(errors))
        return 1
    print("root abyss forbidden mobskill projection ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
