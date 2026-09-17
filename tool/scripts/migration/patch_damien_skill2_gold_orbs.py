#!/usr/bin/env python3
"""Project TMS 8880101 attack3/info/ball onto the v83 8880112 shooter.

v83 cannot spawn projectiles from Damien's skill pose. 8880112 keeps the Lucid
8880165 attack1/info type=2 contract. Projectile pixels come from TMS
8880101/attack3/info/ball (already a ~70px sphere). Do not spawn 8880101 or
8880102. Do not rewrite 8880110 or 8880165.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402

ORB_ID = 8880112
ANALOGUE_ID = 8880165
BALL_SOURCE_ID = 8880101
TMS_BALL = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Mob/_Canvas/8880101.img")
BALL_PATH = "attack3/info/ball"
# Native 8880101 balls are ~70x77. Cap only if a source frame is huge.
BALL_MAX_SIDE = 96
HIT_MAX_SIDE = 160
BODY_MAX_SIDE = 96


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ball_sources() -> list[WzCanvasProperty]:
    if not TMS_BALL.is_file():
        raise FileNotFoundError(TMS_BALL)
    image = arc.load_image(TMS_BALL, arc.BMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{BALL_SOURCE_ID} canvas parse failed: {image.parse_warnings}")
    node = image.root.get(BALL_PATH)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"{BALL_SOURCE_ID} missing {BALL_PATH}")
    frames = []
    for child in node.children():
        if not isinstance(child, WzCanvasProperty) or not child.name.isdigit():
            continue
        if int(child.width) <= 4 or int(child.height) <= 4:
            raise RuntimeError(f"{BALL_SOURCE_ID} {BALL_PATH}/{child.name} is a placeholder")
        frames.append(child)
    if len(frames) < 4:
        raise RuntimeError(f"{BALL_SOURCE_ID} {BALL_PATH} has too few frames: {len(frames)}")
    frames.sort(key=lambda canvas: int(canvas.name))
    return frames


def scaled_size(width: int, height: int, max_side: int = BALL_MAX_SIDE) -> tuple[int, int]:
    longest = max(width, height)
    if longest <= max_side:
        return width, height
    scale = max_side / longest
    return max(1, round(width * scale)), max(1, round(height * scale))


def scale_bitmap(bitmap: Image.Image, max_side: int) -> Image.Image:
    size = scaled_size(*bitmap.size, max_side)
    if size == bitmap.size:
        return bitmap
    sized = bitmap.resize(size, Image.Resampling.LANCZOS)
    bitmap.close()
    return sized.convert("RGBA")


def canvas_max_side(path: tuple[str, ...]) -> int:
    if path[:3] == ("attack1", "info", "ball"):
        return BALL_MAX_SIDE
    if path[:3] == ("attack1", "info", "hit"):
        return HIT_MAX_SIDE
    return BODY_MAX_SIDE


def orb_canvas(name: str, parent, source: WzCanvasProperty, max_side: int) -> WzCanvasProperty:
    bitmap = scale_bitmap(decode_canvas(source, region="BMS").convert("RGBA"), max_side)
    if bitmap.getbbox() is None:
        raise RuntimeError(f"8880101 ball {source.name} decoded empty")
    output = WzCanvasProperty(name, parent)
    output.width, output.height = bitmap.size
    output.format, output.format2 = 1, 0
    output._png_data = encode_canvas_payload(
        bitmap, 1, bitmap.width, bitmap.height, key=arc.GMS_KEY, listwz=False, zlib_level=6
    )
    output._png_length = len(output._png_data)
    output._png_offset = 0
    delay = source.child("delay")
    output.add(WzVectorProperty("origin", bitmap.width // 2, bitmap.height // 2, output))
    output.add(WzIntProperty("z", 0, output))
    output.add(WzIntProperty("delay", int(delay.value) if delay is not None else 90, output))
    bitmap.close()
    return output


def pick_ball(frames: list[WzCanvasProperty], name: str) -> WzCanvasProperty:
    if name.isdigit():
        return frames[int(name) % len(frames)]
    return frames[0]


def clone_leaf(source, parent):
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(source.name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(source.name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(source.name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(source.name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(source.name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(source.name, str(source.value), parent)
    raise TypeError(f"unsupported leaf {type(source).__name__} {source.name}")


def use_ball(path: tuple[str, ...]) -> bool:
    if not path:
        return False
    if path[0] in {"fly", "regen", "die1", "hit1"}:
        return True
    if path[0] == "attack1" and len(path) >= 2 and path[1].isdigit():
        return True
    if path[:3] == ("attack1", "info", "ball"):
        return True
    if path[:3] == ("attack1", "info", "hit") and len(path) >= 4 and path[3].isdigit():
        return True
    return False


def rebuild(source, parent, path: tuple[str, ...], frames: list[WzCanvasProperty]):
    if isinstance(source, WzCanvasProperty):
        if use_ball(path):
            return orb_canvas(
                source.name, parent, pick_ball(frames, source.name), canvas_max_side(path)
            )
        raise RuntimeError(f"unexpected analogue canvas at {'/'.join(path)}")
    if not isinstance(source, WzSubProperty):
        return clone_leaf(source, parent)
    output = WzSubProperty(source.name, parent)
    for child in source.children():
        output.add(rebuild(child, output, (*path, child.name), frames))
    if path == ("info",):
        if output.child("hideName") is None:
            arc.set_int(output, "hideName", 1)
        if int(arc.child_value(output, "firstAttack") or 0) != 1:
            raise RuntimeError("analogue lost firstAttack=1")
    if path == ("attack1", "info"):
        if int(arc.child_value(output, "type") or 0) != 2:
            raise RuntimeError("8880112 attack1/info type must stay 2")
        if output.child("bulletSpeed") is None:
            raise RuntimeError("8880112 attack1/info missing bulletSpeed")
        attach = output.get("hit/attach")
        if attach is None or int(attach.value) != 1:
            raise RuntimeError("8880112 attack1/info/hit must keep attach=1")
        arc.remove_child(output, "disease")
        arc.remove_child(output, "level")
        arc.set_int(output, "fixDamR", 20)
    return output


def build_image() -> arc.WzImage:
    analogue_path = demian.client_mob_path(ANALOGUE_ID)
    analogue = arc.load_image(analogue_path, arc.GMS_KEY)
    if analogue.truncated or analogue.parse_warnings:
        raise RuntimeError(f"{ANALOGUE_ID} parse failed")
    frames = ball_sources()
    analogue._root = rebuild(analogue.root, None, (), frames)
    analogue._parsed = True
    return analogue


def install() -> dict[str, str]:
    image = build_image()
    client = demian.client_mob_path(ORB_ID)
    server = demian.server_mob_path(ORB_ID)
    client.parent.mkdir(parents=True, exist_ok=True)
    server.parent.mkdir(parents=True, exist_ok=True)
    data = arc.verified_image_bytes(arc.encode_image_body(image, arc.gms_reader()), f"{ORB_ID}.img")
    parsed = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{ORB_ID}.img")
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise RuntimeError(f"{ORB_ID} generated parse failed {parsed.parse_warnings}")
    ball = parsed.root.get("attack1/info/ball/0")
    source = ball_sources()[0]
    expected = scaled_size(int(source.width), int(source.height))
    if not isinstance(ball, WzCanvasProperty) or (int(ball.width), int(ball.height)) != expected:
        raise RuntimeError("8880112 ball is not the 8880101 attack3 ball canvas")
    if ball.child("_outlink") is not None:
        raise RuntimeError("8880112 must inline 8880101 ball pixels, not outlinks")
    decoded = decode_canvas(ball, region="GMS").convert("RGBA")
    if decoded.getbbox() is None:
        raise RuntimeError("8880112 ball decoded empty")
    decoded.close()
    xml = arc.image_to_xml(parsed, f"{ORB_ID}.img")
    if 'name="type" value="2"' not in xml or "bulletSpeed" not in xml:
        raise RuntimeError("8880112 XML lost ballistic fields")
    if "8880169" in xml or "8880102" in xml:
        raise RuntimeError("8880112 XML still points at butterfly/shadow IDs")
    if 'name="disease"' in xml:
        raise RuntimeError("8880112 must not seduce via leftover Lucid disease")
    if 'name="fixDamR" value="20"' not in xml:
        raise RuntimeError("8880112 XML missing fixDamR=20")
    arc.atomic_write_bytes(client, data)
    arc.atomic_write_text(server, xml)
    return {str(client): sha256_bytes(data), str(server): sha256_bytes(xml.encode("utf-8"))}


def main() -> int:
    first = install()
    second = install()
    if first != second:
        raise RuntimeError(f"8880112 generator is not idempotent: {first} vs {second}")
    print("damien skill2 orbs -> 8880112 from 8880101 attack3/ball")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
