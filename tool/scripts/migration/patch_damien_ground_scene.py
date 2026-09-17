#!/usr/bin/env python3
"""Project Damien skill2 ground-burst scene onto v83 Map/Effect FIELD_EFFECT.

The orange-red full-width band in the user's screenshot is not a map Back
layer. TMS plays it as a scene overlay while 8880110 is airborne (skill2).
The old client cannot run that fieldType/spine scene, and the 7x5
customBossDemian/groundBurst marker only existed for deleted MCV.

This replaces that marker with ARGB4444 frames: 8880110 attack1/info/areaWarning
fire, stretched across the current client resolution and parked on the lower
screen so it reads as a ground inferno line. Server broadcasts
customBossDemian/groundBurst at SKILL2_AIRBORNE_MS. Do not restore MCV.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(ROOT / "tool/scripts/migration")]

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

CLIENT_EFFECT = ROOT / "clien/Data/Map/Effect.img"
CLIENT_BOSS = ROOT / "clien/Data/Mob/8880110.img"
CONFIG = ROOT / "clien/config.ini"
WARNING_PATH = "attack1/info/areaWarning"
EFFECT_PATH = ("customBossDemian", "groundBurst")
BAND_TOP_RATIO = 0.52
BAND_HEIGHT_RATIO = 0.30
MIN_FRAMES = 8
MIN_ORANGE = 800


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def screen_size() -> tuple[int, int]:
    text = CONFIG.read_text(encoding="utf-8")
    width = int(re.search(r"^width=(\d+)", text, re.M).group(1))
    height = int(re.search(r"^height=(\d+)", text, re.M).group(1))
    return width, height


def orange_count(image: Image.Image) -> int:
    return sum(
        1
        for r, g, b, a in image.getdata()
        if a > 80 and r > 140 and g > 30 and b < 120 and r > g
    )


def warning_frames() -> list[WzCanvasProperty]:
    image = arc.load_image(CLIENT_BOSS, arc.GMS_KEY)
    node = image.root.get(WARNING_PATH)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError("8880110 missing attack1/info/areaWarning")
    frames = []
    for child in node.children():
        if not isinstance(child, WzCanvasProperty) or not child.name.isdigit():
            continue
        if child.width <= 1 or child.height <= 1:
            continue
        frames.append(child)
    if len(frames) < MIN_FRAMES:
        raise RuntimeError(f"areaWarning visible frames {len(frames)} < {MIN_FRAMES}")
    return frames


def scene_frame(name: str, parent: WzSubProperty, source: WzCanvasProperty, size: tuple[int, int]) -> WzCanvasProperty:
    width, height = size
    fire = decode_canvas(source, region="GMS").convert("RGBA")
    band_h = max(48, int(height * BAND_HEIGHT_RATIO))
    band = fire.resize((width, band_h), Image.Resampling.LANCZOS)
    fire.close()
    canvas_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    top = int(height * BAND_TOP_RATIO)
    canvas_img.paste(band, (0, top), band)
    band.close()
    output = WzCanvasProperty(name, parent)
    output.width, output.height = canvas_img.size
    output.format, output.format2 = 1, 0
    output._png_data = encode_canvas_payload(
        canvas_img, 1, width, height, key=arc.GMS_KEY, listwz=False, zlib_level=6
    )
    output._png_length = len(output._png_data)
    output._png_offset = 0
    output.add(WzVectorProperty("origin", width // 2, height // 2, output))
    delay = source.child("delay")
    output.add(WzIntProperty("delay", int(delay.value) if delay is not None else 90, output))
    output.add(WzIntProperty("z", 0, output))
    canvas_img.close()
    return output


def ground_burst_node() -> WzSubProperty:
    size = screen_size()
    root = WzSubProperty("groundBurst")
    for index, source in enumerate(warning_frames()):
        root.add(scene_frame(str(index), root, source, size))
    return root


def load_gms(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=CLIENT_EFFECT.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"Effect.img parse failed: {image.parse_warnings}")
    return image


def effect_has_scene(data: bytes) -> bool:
    image = load_gms(data)
    node = image.root.get("customBossDemian/groundBurst")
    if not isinstance(node, WzSubProperty):
        return False
    width, height = screen_size()
    frames = [
        child for child in node.children()
        if isinstance(child, WzCanvasProperty) and child.name.isdigit()
    ]
    if len(frames) < MIN_FRAMES:
        return False
    first = frames[0]
    if (first.width, first.height) != (width, height):
        return False
    if (int(first.format), int(first.format2)) != (1, 0):
        raise RuntimeError("groundBurst is not ARGB4444")
    decoded = decode_canvas(first, region="GMS").convert("RGBA")
    ok = decoded.getbbox() is not None
    decoded.close()
    lava = 0
    for frame in frames[-5:]:
        last_img = decode_canvas(frame, region="GMS").convert("RGBA")
        lava = max(lava, orange_count(last_img))
        last_img.close()
    return ok and lava >= MIN_ORANGE


def patch_effect(data: bytes) -> bytes:
    if effect_has_scene(data):
        return data
    replacement = ground_burst_node()
    result = replace_img_record(data, EFFECT_PATH, replacement, region="GMS").data
    arc.verify_raw_record_scope(
        data, result, {EFFECT_PATH}, allow_additions=True
    )
    image = load_gms(result)
    if image.root.child("customBossDemian").child("scene") is None:
        raise RuntimeError("protected customBossDemian/scene was removed")
    if not effect_has_scene(result):
        raise RuntimeError("groundBurst scene frames failed validation")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = patch_effect(CLIENT_EFFECT.read_bytes())
    if args.check:
        if CLIENT_EFFECT.read_bytes() != expected:
            raise SystemExit("needs Damien ground-burst scene patch")
        print("Damien ground-burst scene already applied")
        return 0
    if CLIENT_EFFECT.read_bytes() != expected:
        arc.atomic_write_bytes(CLIENT_EFFECT, expected)
    if patch_effect(CLIENT_EFFECT.read_bytes()) != expected:
        raise RuntimeError("generator not idempotent")
    print(f"Damien ground-burst scene ok sha256={sha256(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
