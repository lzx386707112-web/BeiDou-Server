#!/usr/bin/env python3
"""Extract skill icons from client Skill IMG files into a catalog atlas."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill"
OUT_DIR = ROOT / "gms-server" / "src" / "main" / "resources" / "skill-catalog"
WZPYTHON = ROOT / "tool" / "wz-python"
CELL = 40

sys.path.insert(0, str(WZPYTHON))
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.crypto import WzKey, detect_region_from_img  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.wz_image import WzImage  # noqa: E402


def resolve_node(node: WzProperty | None) -> WzProperty | None:
    seen: set[int] = set()
    cur = node
    for _ in range(16):
        if cur is None or not isinstance(cur, WzUolProperty):
            return cur
        if id(cur) in seen or cur.parent is None:
            return None
        seen.add(id(cur))
        target = cur.value
        if not target:
            return None
        cur = cur.parent.get(str(target))
    return None


def canvas_of(skill: WzProperty) -> WzCanvasProperty | None:
    for name in ("icon", "iconRaw", "iconMouseOver"):
        node = resolve_node(skill.get(name) if hasattr(skill, "get") else None)
        if isinstance(node, WzCanvasProperty):
            return node
    return None


def job_files() -> list[Path]:
    files = []
    for path in sorted(CLIENT_SKILL.glob("*.img")):
        stem = path.name[:-4]
        if stem.isdigit():
            files.append(path)
    return files


def extract_icons() -> dict[int, Image.Image]:
    icons: dict[int, Image.Image] = {}
    for path in job_files():
        data = path.read_bytes()
        region = detect_region_from_img(data)
        if region is None:
            print(f"skip {path.name}: unknown region")
            continue
        image = WzImage.from_bytes(data, key=WzKey.for_region(region), name=path.name)
        root = image.parse_partial(only=frozenset({"skill"}))
        skill_root = root.get("skill")
        if not isinstance(skill_root, WzSubProperty):
            continue
        decoded = 0
        for child in skill_root.children():
            if not child.name.isdigit():
                continue
            skill_id = int(child.name)
            icon = canvas_of(child)
            if icon is None:
                continue
            try:
                bitmap = decode_canvas(icon, region=region)
            except Exception as exc:
                print(f"  {path.name}/{child.name}: {exc}")
                continue
            if bitmap.mode != "RGBA":
                bitmap = bitmap.convert("RGBA")
            icons[skill_id] = bitmap
            decoded += 1
        print(f"{path.name}: {decoded} icons")
    return icons


def build_atlas(icons: dict[int, Image.Image]) -> tuple[Image.Image, dict[str, dict[str, int]]]:
    ids = sorted(icons)
    cols = max(1, math.ceil(math.sqrt(len(ids))))
    rows = max(1, math.ceil(len(ids) / cols))
    atlas = Image.new("RGBA", (cols * CELL, rows * CELL), (0, 0, 0, 0))
    coords: dict[str, dict[str, int]] = {}
    for index, skill_id in enumerate(ids):
        x = (index % cols) * CELL
        y = (index // cols) * CELL
        src = icons[skill_id]
        cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
        ox = max(0, (CELL - src.width) // 2)
        oy = max(0, (CELL - src.height) // 2)
        cell.paste(src, (ox, oy), src)
        atlas.paste(cell, (x, y), cell)
        coords[str(skill_id)] = {"x": x, "y": y}
    return atlas, coords


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    icons = extract_icons()
    atlas, coords = build_atlas(icons)
    atlas_path = OUT_DIR / "atlas.png"
    atlas.save(atlas_path, "PNG")
    manifest = {
        "cellSize": CELL,
        "count": len(coords),
        "icons": coords,
    }
    (OUT_DIR / "icons.json").write_text(
        json.dumps(manifest, separators=(",", ":")), encoding="utf-8"
    )
    print(f"wrote {len(coords)} icons -> {atlas_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
