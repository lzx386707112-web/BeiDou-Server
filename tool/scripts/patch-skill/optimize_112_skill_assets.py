#!/usr/bin/env python3
"""Optimize heavy Hero 112 custom skill canvases.

The .img canvas payloads are raw WZ pixel formats compressed with zlib, not
normal PNG files.  This applies a TinyPNG-like palette quantization step before
re-encoding the selected new skill assets, and removes duplicate/obsolete
visual groups that are no longer used by the current client/server path.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "112.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
TARGET_SKILLS = ("1121001", "1121012", "1121013")
MAP_EFFECT_PATH = "customSkill/deathFault/full"
OBSOLETE_MAP_EFFECT_PATH = "customSkill/deathFault/screen"
OBSOLETE_1121013_GROUPS = ("effect0", "effect1")


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def backup(path: Path, suffix: str) -> None:
    backup_path = path.with_name(path.name + suffix)
    if backup_path.exists():
        return
    shutil.copy2(path, backup_path)
    print(f"backup: {backup_path}")


def walk_canvas(prop, path: str = ""):
    if isinstance(prop, WzCanvasProperty):
        yield path, prop
    if hasattr(prop, "children"):
        for child in prop.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk_canvas(child, child_path)


def payload_len(canvas: WzCanvasProperty) -> int:
    return int(getattr(canvas, "_png_length", 0) or len(getattr(canvas, "_png_data", b"") or b""))


def encoded_bytes_per_pixel(canvas: WzCanvasProperty) -> int:
    fmt = int(canvas.format) + int(canvas.format2)
    if fmt in {1, 257, 513}:
        return 2
    if fmt == 3:
        return 1
    if fmt == 517:
        return 1
    return 4


def canvas_totals(canvases: list[tuple[str, WzCanvasProperty]]) -> tuple[int, int]:
    payload = sum(payload_len(canvas) for _, canvas in canvases)
    encoded_raw = sum(int(canvas.width) * int(canvas.height) * encoded_bytes_per_pixel(canvas) for _, canvas in canvases)
    return payload, encoded_raw


def clean_transparent_rgb(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    arr = np.array(image, dtype=np.uint8)
    transparent = arr[:, :, 3] == 0
    if transparent.any():
        arr[transparent, 0:3] = 0
    return Image.fromarray(arr, "RGBA")


def quantize_rgba(image: Image.Image, colors: int) -> Image.Image:
    image = clean_transparent_rgb(image)
    return image.quantize(
        colors=colors,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    ).convert("RGBA")


def optimize_canvas(canvas: WzCanvasProperty, colors: int, zlib_level: int, canvas_format: int) -> tuple[int, int]:
    before = payload_len(canvas)
    image = decode_canvas(canvas, region="GMS")
    optimized = quantize_rgba(image, colors) if colors > 0 else clean_transparent_rgb(image)
    canvas.format = canvas_format
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        optimized,
        canvas_format,
        int(canvas.width),
        int(canvas.height),
        key=WzKey.for_region("GMS"),
        listwz=False,
        zlib_level=zlib_level,
    )
    canvas._png_length = len(canvas._png_data)
    return before, len(canvas._png_data)


def remove_child(parent: WzSubProperty, name: str) -> bool:
    if parent.child(name) is None:
        return False
    del parent._children[name]
    return True


def remove_path(root: WzSubProperty, path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return False
    parent = root.get("/".join(parts[:-1])) if len(parts) > 1 else root
    if not isinstance(parent, WzSubProperty):
        return False
    return remove_child(parent, parts[-1])


def short_hash(canvas: WzCanvasProperty) -> str:
    image = decode_canvas(canvas, region="GMS").convert("RGBA")
    return hashlib.sha256(image.tobytes()).hexdigest()


def report_duplicate_groups(canvases: list[tuple[str, WzCanvasProperty]], min_group: int = 2, limit: int = 20) -> int:
    groups: dict[tuple[int, int, str], list[str]] = {}
    for path, canvas in canvases:
        key = (int(canvas.width), int(canvas.height), short_hash(canvas))
        groups.setdefault(key, []).append(path)
    duplicate_groups = 0
    for (_width, _height, _hash), paths in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True):
        if len(paths) < min_group:
            continue
        duplicate_groups += 1
        if duplicate_groups <= limit:
            print(f"duplicate x{len(paths)}: {paths[0]}")
            for path in paths[1:5]:
                print(f"  same as: {path}")
            if len(paths) > 5:
                print(f"  ... {len(paths) - 5} more")
    if duplicate_groups > limit:
        print(f"duplicate groups omitted: {duplicate_groups - limit}")
    return duplicate_groups


def optimize_skill_img(path: Path, colors: int, zlib_level: int, canvas_format: int, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()

    removed = []
    raging = root.get("skill/1121013")
    if isinstance(raging, WzSubProperty):
        for group in OBSOLETE_1121013_GROUPS:
            if remove_child(raging, group):
                removed.append(f"skill/1121013/{group}")

    canvases: list[tuple[str, WzCanvasProperty]] = []
    for skill_id in TARGET_SKILLS:
        node = root.get(f"skill/{skill_id}")
        if node is not None:
            canvases.extend(list(walk_canvas(node, f"skill/{skill_id}")))

    before_payload, before_raw = canvas_totals(canvases)
    duplicate_groups = report_duplicate_groups(canvases)
    for _path, canvas in canvases:
        optimize_canvas(canvas, colors, zlib_level, canvas_format)

    after_payload, after_raw = canvas_totals(canvases)
    print(
        f"{path.name}: canvases={len(canvases)}, duplicates={duplicate_groups}, "
        f"removed={len(removed)}, payload {before_payload / 1024 / 1024:.2f}MB -> "
        f"{after_payload / 1024 / 1024:.2f}MB, encodedRaw {before_raw / 1024 / 1024:.1f}MB -> "
        f"{after_raw / 1024 / 1024:.1f}MB, format={canvas_format}"
    )
    for node_path in removed:
        print(f"removed obsolete duplicate node: {node_path}")

    if dry_run:
        return 1
    backup(path, ".bak-112-assets-optimize")
    atomic_write(path, encode_image_body(image, image.wz_file.reader))
    return 1


def optimize_map_effect_img(path: Path, colors: int, zlib_level: int, canvas_format: int, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()

    removed_obsolete = remove_path(root, OBSOLETE_MAP_EFFECT_PATH)
    node = root.get(MAP_EFFECT_PATH)
    if node is None:
        raise RuntimeError(f"missing {MAP_EFFECT_PATH}: {path}")

    canvases = list(walk_canvas(node, MAP_EFFECT_PATH))
    before_payload, before_raw = canvas_totals(canvases)
    duplicate_groups = report_duplicate_groups(canvases)
    for _path, canvas in canvases:
        optimize_canvas(canvas, colors, zlib_level, canvas_format)
    after_payload, after_raw = canvas_totals(canvases)
    print(
        f"{path.name}: canvases={len(canvases)}, duplicates={duplicate_groups}, "
        f"removed_obsolete_screen={int(removed_obsolete)}, payload "
        f"{before_payload / 1024 / 1024:.2f}MB -> {after_payload / 1024 / 1024:.2f}MB, "
        f"encodedRaw {before_raw / 1024 / 1024:.1f}MB -> {after_raw / 1024 / 1024:.1f}MB, "
        f"format={canvas_format}"
    )
    if removed_obsolete:
        print(f"removed obsolete map effect: {OBSOLETE_MAP_EFFECT_PATH}")

    if dry_run:
        return 1
    backup(path, ".bak-112-assets-optimize")
    atomic_write(path, encode_image_body(image, image.wz_file.reader))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--colors",
        type=int,
        default=None,
        help="palette size used for RGBA quantization; defaults to 256 for format 2 and disabled for format 1",
    )
    parser.add_argument("--canvas-format", type=int, default=2, choices=(1, 2), help="WZ canvas pixel format")
    parser.add_argument("--zlib-level", type=int, default=9, choices=range(1, 10), help="zlib compression level")
    parser.add_argument("--dry-run", action="store_true", help="report without writing files")
    args = parser.parse_args()
    colors = args.colors
    if colors is None:
        colors = 0 if args.canvas_format == 1 else 256

    changed = 0
    changed += optimize_skill_img(CLIENT_SKILL, colors, args.zlib_level, args.canvas_format, args.dry_run)
    changed += optimize_map_effect_img(CLIENT_MAP_EFFECT, colors, args.zlib_level, args.canvas_format, args.dry_run)
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
