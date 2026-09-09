#!/usr/bin/env python3
"""Contract: Arcane River ballistic attacks match the 8641002 type=2 analogue."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(ROOT / "tool/wz-python"))

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_twilight_perion_monster_park as twilight  # noqa: E402
from wzpy import WzIntProperty, WzSubProperty  # noqa: E402


def main() -> int:
    errors: list[str] = []
    leftover = twilight.iter_incomplete_ballistic_attacks(twilight.arcane_river_mob_ids())
    if leftover:
        errors.append(f"864* ball attacks still incomplete: {leftover}")

    image = twilight.load_checked(twilight.client_mob_path(8644412), arc.GMS_KEY)
    info = image.root.get("attack1/info")
    if not isinstance(info, WzSubProperty) or info.child("ball") is None:
        errors.append("8644412 missing attack1/info/ball")
    elif int(arc.child_value(info, "type") or 0) != 2:
        errors.append("8644412 attack1 type is not 2")
    elif int(arc.child_value(info, "bulletSpeed") or 0) != 300:
        errors.append("8644412 attack1 bulletSpeed is not 300")
    hit = info.child("hit") if info is not None else None
    if not isinstance(hit, WzSubProperty) or not isinstance(hit.child("attach"), WzIntProperty):
        errors.append("8644412 attack1/info/hit/attach is missing")

    analogue = twilight.load_checked(twilight.client_mob_path(8641002), arc.GMS_KEY)
    analogue_info = analogue.root.get("attack1/info")
    if int(arc.child_value(analogue_info, "type") or 0) != 2:
        errors.append("analogue 8641002 lost type=2")

    if errors:
        print("FAIL")
        for item in errors:
            print(item)
        return 1
    print("arcane river ballistic contract ok: 864* ball attacks type=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
