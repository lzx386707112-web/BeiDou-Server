#!/usr/bin/env python3
"""Contract: Damien maps no longer place lava mountains on Back layers."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import patch_damien_lava_backs as lava  # noqa: E402
from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def errors() -> list[str]:
    found: list[str] = []
    if not lava.back_is_clean(lava.CLIENT_BACK.read_bytes()):
        found.append("BossDemian still has lava canvases or extra back/17-19")
    back = arc.load_image(lava.CLIENT_BACK, arc.GMS_KEY)
    if back.root.child("spine") is not None:
        found.append("BossDemian still has spine")
    folder = back.root.child("back")
    if not isinstance(folder, WzSubProperty):
        found.append("BossDemian missing back")
        return found
    names = [child.name for child in folder.children()]
    if names != [str(index) for index in range(17)]:
        found.append(f"BossDemian back names {names}")
    for name, size in lava.HEAD_BACK_SIZES.items():
        canvas = folder.child(name)
        if not isinstance(canvas, WzCanvasProperty):
            found.append(f"missing restored back/{name}")
            continue
        if (int(canvas.width), int(canvas.height)) != size:
            found.append(f"back/{name} still lava-sized {canvas.width}x{canvas.height}")
        if (int(canvas.format), int(canvas.format2)) != (1, 0):
            found.append(f"back/{name} not ARGB4444")
    for map_id in lava.MAP_IDS:
        client = lava.client_map_path(map_id)
        server = lava.server_map_path(map_id)
        if not lava.map_is_clean(client.read_bytes(), client.name):
            found.append(f"{map_id} still has lava back 9-11")
        if not lava.xml_is_clean(server.read_text(encoding="utf-8"), server.name):
            found.append(f"{map_id} XML still has lava back 9-11")
        image = arc.load_image(client, arc.GMS_KEY)
        back_node = image.root.child("back")
        if not isinstance(back_node, WzSubProperty):
            found.append(f"{map_id} missing back")
            continue
        names = {child.name for child in back_node.children() if child.name.isdigit()}
        if names != {str(index) for index in range(9)}:
            found.append(f"{map_id} unexpected back names {sorted(names, key=int)}")
        zh = ROOT / f"gms-server/wz-zh-CN/Map.wz/Map/Map{str(map_id)[0]}/{map_id}.img.xml"
        if zh.exists():
            found.append(f"wz-zh-CN Map overlay {zh}")
    return found


def main() -> int:
    found = errors()
    if found:
        print("FAILED")
        for item in found:
            print(item)
        return 1
    print("ok")
    print(f"Back/BossDemian.img sha256={sha256(lava.CLIENT_BACK)}")
    for map_id in lava.MAP_IDS:
        print(f"{map_id} sha256={sha256(lava.client_map_path(map_id))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
