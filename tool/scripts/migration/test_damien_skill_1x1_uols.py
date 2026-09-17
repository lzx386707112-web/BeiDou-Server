#!/usr/bin/env python3
"""Damien 1x1 skill/warning stubs must UOL to a real frame, not origin 0,0."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzUolProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def errors() -> list[str]:
    found: list[str] = []
    p1 = arc.load_image(ROOT / "clien/Data/Mob/8880110.img", arc.GMS_KEY)
    p2 = arc.load_image(ROOT / "clien/Data/Mob/8880111.img", arc.GMS_KEY)
    wanted = {
        (p1, "attack1/info/areaWarning/0", "../areaWarning/1"),
        (p1, "attack3/info/areaWarning/0", "../areaWarning/1"),
        (p2, "skill2/10", "../skill3/10"),
        (p2, "skill5/10", "../skill5/11"),
        (p2, "attack1/info/effect/0", "../effect/1"),
    }
    for image, path, value in wanted:
        node = image.root.get(path)
        if not isinstance(node, WzUolProperty) or str(node.value) != value:
            found.append(f"{image.name} {path} is {node}")
    names = [child.name for child in p1.root.child("skill4").children()]
    if names[:2] != ["0", "1"]:
        found.append(f"skill4 starts {names[:4]}")
    warning1 = p1.root.get("attack1/info/areaWarning/1")
    if not isinstance(warning1, WzCanvasProperty) or int(warning1.height) < 100:
        found.append("areaWarning/1 is not a head-high canvas")
    xml1 = (ROOT / "gms-server/wz/Mob.wz/8880110.img.xml").read_text(encoding="utf-8")
    if 'name="0" value="../areaWarning/1"' not in xml1:
        found.append("8880110 XML areaWarning/0 not UOL")
    xml2 = (ROOT / "gms-server/wz/Mob.wz/8880111.img.xml").read_text(encoding="utf-8")
    if 'name="10" value="../skill3/10"' not in xml2:
        found.append("8880111 XML skill2/10 not UOL")
    return found


def main() -> int:
    found = errors()
    if found:
        print("FAILED")
        for item in found:
            print(item)
        return 1
    print("ok")
    print(f"8880110 sha256={sha256(ROOT / 'clien/Data/Mob/8880110.img')}")
    print(f"8880111 sha256={sha256(ROOT / 'clien/Data/Mob/8880111.img')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
