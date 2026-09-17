#!/usr/bin/env python3
"""8880113/8880114 are v83 projections of TMS 8880102 and Etc flyingSword."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import patch_damien_p2_field_mobs as patcher  # noqa: E402
from wzpy import WzCanvasProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def errors() -> list[str]:
    found: list[str] = []
    for mob_id, min_w in ((patcher.VORTEX_ID, 200), (patcher.SWORD_ID, 40)):
        path = ROOT / f"clien/Data/Mob/{mob_id}.img"
        xml = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        if not path.is_file() or not xml.is_file():
            found.append(f"missing {mob_id}")
            continue
        image = arc.load_image(path, arc.GMS_KEY)
        if image.truncated or image.parse_warnings:
            found.append(f"{mob_id} parse failed")
        fly0 = image.root.get("fly/0")
        if not isinstance(fly0, WzCanvasProperty) or fly0.width < min_w:
            found.append(f"{mob_id} fly/0 too small")
        elif (int(fly0.format), int(fly0.format2)) != (1, 0):
            found.append(f"{mob_id} fly not ARGB4444")
        else:
            decoded = decode_canvas(fly0, region="GMS").convert("RGBA")
            if decoded.getbbox() is None:
                found.append(f"{mob_id} fly empty")
            decoded.close()
        if mob_id == patcher.SWORD_ID:
            jump0 = image.root.get("jump/0")
            if not isinstance(jump0, WzCanvasProperty) or jump0.width < min_w:
                found.append("8880114 missing 45-degree jump pose")
        text = xml.read_text(encoding="utf-8")
        expected_first = "0" if mob_id == patcher.VORTEX_ID else "1"
        if f'name="firstAttack" value="{expected_first}"' not in text:
            found.append(f"{mob_id} firstAttack is not {expected_first}")
        if 'name="removeAfter" value="0"' not in text:
            found.append(f"{mob_id} removeAfter is not 0")
        if "8880102" in text or 'name="type" value="2"' in text:
            found.append(f"{mob_id} XML still ballistic or names 8880102")
    return found


def main() -> int:
    found = errors()
    if found:
        print("FAILED")
        for item in found:
            print(item)
        return 1
    print("ok")
    print(f"8880113 sha256={sha256(ROOT / 'clien/Data/Mob/8880113.img')}")
    print(f"8880114 sha256={sha256(ROOT / 'clien/Data/Mob/8880114.img')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
