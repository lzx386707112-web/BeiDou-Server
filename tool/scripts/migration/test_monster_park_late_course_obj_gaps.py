#!/usr/bin/env python3
"""Contract for modern obj/connect projection and numeric gap fill."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/repair_monster_park_late_course_obj_gaps.py"
SPEC = importlib.util.spec_from_file_location("park_obj_gaps", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def main() -> int:
    errors: list[str] = []
    sample_ids = (
        270010100,
        273030200,
        953020000,
        954100000,
        954102000,
        450007170,
        450009000,
        450011660,
        951000300,
    )
    for map_id in sample_ids:
        if not repair.client_map_path(map_id).is_file():
            errors.append(f"missing client map {map_id}")
            continue
        data = repair.client_map_path(map_id).read_bytes()
        leftover = repair.leftover_gaps_from_bytes(data, map_id)
        if leftover:
            errors.append(f"{map_id} still has numeric gaps {leftover}")
        modern = repair.leftover_modern(data, map_id)
        if modern:
            errors.append(f"{map_id} still has modern/connect nodes {modern}")
        image = repair.load_client(data, f"{map_id}.img")
        if image.truncated or image.parse_warnings:
            errors.append(f"{map_id} parse failed")

    if 953020000 not in sample_ids:
        errors.append("auto-guard sample missing")
    auto = repair.load_client(repair.client_map_path(953020000).read_bytes(), "953020000.img")
    for layer in [child for child in auto.root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if objects is None:
            continue
        for entry in objects.children():
            if str(repair.arc.child_value(entry, "oS") or "") != "connect":
                continue
            if str(repair.arc.child_value(entry, "l1") or "") != "0":
                errors.append(
                    f"953020000 {layer.name}/obj/{entry.name} connect l1="
                    f"{repair.arc.child_value(entry, 'l1')}"
                )

    if errors:
        print("FAIL")
        for item in errors:
            print(item)
        return 1
    print("modern obj/connect/gap contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
