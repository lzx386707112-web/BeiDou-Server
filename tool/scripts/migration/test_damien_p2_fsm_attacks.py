#!/usr/bin/env python3
"""8880111 attack2/4/5/6 use phase-one onlyFsm projection: stand UOLs, no 1x1."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import patch_damien_p2_fsm_attacks as patcher  # noqa: E402
from wzpy import WzCanvasProperty, WzSubProperty, WzUolProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def errors() -> list[str]:
    found: list[str] = []
    if not patcher.img_is_clean(patcher.client_path().read_bytes()):
        found.append("8880111 attack2/4/5/6 still have empty onlyFsm poses")
    if not patcher.xml_is_clean(patcher.server_path().read_text(encoding="utf-8")):
        found.append("8880111 XML attack2/4/5/6 still have empty onlyFsm poses")
    image = arc.load_image(patcher.client_path(), arc.GMS_KEY)
    analogue = arc.load_image(ROOT / "clien/Data/Mob/8880110.img", arc.GMS_KEY)
    p1 = analogue.root.child("attack2")
    if not isinstance(p1, WzSubProperty) or not patcher.pose_is_clean(p1):
        found.append("phase-one attack2 analogue is not stand UOLs")
    for name in patcher.ATTACKS:
        action = image.root.child(name)
        if not isinstance(action, WzSubProperty):
            found.append(f"missing {name}")
            continue
        if action.child("info") is not None and action.child("info").child("onlyFsm") is not None:
            found.append(f"{name} kept onlyFsm")
        for child in action.children():
            if child.name.isdigit() and isinstance(child, WzCanvasProperty):
                found.append(f"{name}/{child.name} is still a canvas")
            if isinstance(child, WzUolProperty) and not str(child.value).startswith("../stand/"):
                found.append(f"{name}/{child.name} UOL {child.value}")
        knives = image.root.get("attack3/info/ball")
        if knives is None:
            found.append("protected attack3 ball was removed")
    if image.root.get("attack3/info/type") is None:
        found.append("protected attack3 type was removed")
    return found


def main() -> int:
    found = errors()
    if found:
        print("FAILED")
        for item in found:
            print(item)
        return 1
    print("ok")
    print(f"8880111.img sha256={sha256(patcher.client_path())}")
    print(f"8880111.img.xml sha256={sha256(patcher.server_path())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
