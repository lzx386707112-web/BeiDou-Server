#!/usr/bin/env python3
"""Contract: custom consume item 2431158 怪物吸星大法."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "tool/wz-python"),
    str(ROOT / "tool/scripts/migration"),
    str(ROOT / "tool/scripts/patch-client"),
]

import add_item_2431158_monster_vac as patch  # noqa: E402


def main() -> int:
    payloads = patch.build()
    for path, data in payloads.items():
        if path.read_bytes() != data:
            raise RuntimeError(f"{path.relative_to(ROOT)} does not match generator output")
    print("item 2431158 怪物吸星大法 contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
