#!/usr/bin/env python3
"""Project TMS 8880102 vortex and Etc/BossDemian swords onto new v83 fly mobs.

Do not spawn 8880102 (old client Flash crash). 8880113 inlines TMS
8880102 move/regen/die1 onto the 8880165 fly contract. 8880114 inlines
Etc/BossDemian flyingSword stand/move. firstAttack=0 so they patrol instead
of shooting Lucid balls. New standalone IMGs may use encode_image_body.
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

ANALOGUE_ID = 8880165
VORTEX_ID = 8880113
SWORD_ID = 8880114
TMS_VORTEX = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Mob/_Canvas/8880102.img")
TMS_SWORD = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Etc/_Canvas/BossDemian.img")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canvas_frames(image: WzImage, path: str) -> list[WzCanvasProperty]:
    node = image.root.get(path)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing {path}")
    frames = [
        child
        for child in node.children()
        if isinstance(child, WzCanvasProperty) and child.name.isdigit() and int(child.width) > 4
    ]
    frames.sort(key=lambda canvas: int(canvas.name))
    if len(frames) < 4:
        raise RuntimeError(f"{path} has too few visible frames")
    return frames


def vortex_sets() -> dict[str, list[WzCanvasProperty]]:
    image = arc.load_image(TMS_VORTEX, arc.BMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"8880102 canvas parse failed: {image.parse_warnings}")
    move = canvas_frames(image, "move")
    return {
        "fly": move,
        "regen": canvas_frames(image, "regen"),
        "die1": canvas_frames(image, "die1"),
        "hit1": move[:1],
        "attack1": move,
    }


def sword_sets() -> dict[str, list[WzCanvasProperty]]:
    image = arc.load_image(TMS_SWORD, arc.BMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"BossDemian canvas parse failed: {image.parse_warnings}")
    move = canvas_frames(image, "flyingSword/move")
    stand = canvas_frames(image, "flyingSword/stand")
    return {
        "fly": move,
        "regen": stand,
        "die1": stand[:4],
        "hit1": stand[:1],
        "attack1": move,
    }


def gms_canvas(name: str, parent, source: WzCanvasProperty, rotate_cw: bool = False) -> WzCanvasProperty:
    bitmap = decode_canvas(source, region="BMS").convert("RGBA")
    if bitmap.getbbox() is None:
        raise RuntimeError(f"{source.name} decoded empty")
    if rotate_cw:
        rotated = bitmap.rotate(-90, expand=True)
        bitmap.close()
        bitmap = rotated
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


def pick(frames: list[WzCanvasProperty], name: str) -> WzCanvasProperty:
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


def use_visual(path: tuple[str, ...]) -> str | None:
    if not path:
        return None
    if path[0] in {"fly", "regen", "die1", "hit1"}:
        return path[0]
    if path[0] == "attack1" and len(path) >= 2 and path[1].isdigit():
        return "attack1"
    if path[:3] == ("attack1", "info", "hit") and len(path) >= 4 and path[3].isdigit():
        return "hit1"
    return None


def rebuild(source, parent, path: tuple[str, ...], sets: dict[str, list[WzCanvasProperty]], speed: int, rotate_cw: bool, first_attack: int, body_attack: int):
    if isinstance(source, WzCanvasProperty):
        key = use_visual(path)
        if key is None:
            raise RuntimeError(f"unexpected analogue canvas at {'/'.join(path)}")
        return gms_canvas(source.name, parent, pick(sets[key], source.name), rotate_cw=rotate_cw)
    if not isinstance(source, WzSubProperty):
        return clone_leaf(source, parent)
    output = WzSubProperty(source.name, parent)
    for child in source.children():
        if path == ("attack1", "info") and child.name in {"ball", "type", "bulletSpeed", "disease", "level"}:
            continue
        output.add(rebuild(child, output, (*path, child.name), sets, speed, rotate_cw, first_attack, body_attack))
    if path == ("info",):
        arc.set_int(output, "firstAttack", first_attack)
        arc.set_int(output, "bodyAttack", body_attack)
        arc.set_int(output, "hideName", 1)
        arc.set_int(output, "speed", speed)
        arc.set_int(output, "boss", 0)
        arc.set_int(output, "removeAfter", 0)
    if path == ("attack1", "info"):
        arc.remove_child(output, "disease")
        arc.remove_child(output, "level")
        arc.remove_child(output, "type")
        arc.remove_child(output, "bulletSpeed")
        arc.remove_child(output, "ball")
    return output


def build_image(sets: dict[str, list[WzCanvasProperty]], speed: int, rotate_cw: bool, first_attack: int, body_attack: int) -> WzImage:
    analogue = arc.load_image(demian.client_mob_path(ANALOGUE_ID), arc.GMS_KEY)
    if analogue.truncated or analogue.parse_warnings:
        raise RuntimeError(f"{ANALOGUE_ID} parse failed")
    analogue._root = rebuild(analogue.root, None, (), sets, speed, rotate_cw, first_attack, body_attack)
    analogue._parsed = True
    return analogue


def attach_jump(image: WzImage) -> None:
    fly = image.root.child("fly")
    if not isinstance(fly, WzSubProperty):
        raise RuntimeError("sword image missing fly")
    if image.root.child("jump") is not None:
        return
    jump = WzSubProperty("jump", image.root)
    for child in fly.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        bitmap = decode_canvas(child, region="GMS").convert("RGBA")
        rotated = bitmap.rotate(45, expand=True, resample=Image.BICUBIC)
        bitmap.close()
        output = WzCanvasProperty(child.name, jump)
        output.width, output.height = rotated.size
        output.format, output.format2 = 1, 0
        output._png_data = encode_canvas_payload(
            rotated, 1, rotated.width, rotated.height, key=arc.GMS_KEY, listwz=False, zlib_level=6
        )
        output._png_length = len(output._png_data)
        output._png_offset = 0
        output.add(WzVectorProperty("origin", rotated.width // 2, rotated.height // 2, output))
        output.add(WzIntProperty("z", 0, output))
        delay = child.child("delay")
        output.add(WzIntProperty("delay", int(delay.value) if delay is not None else 90, output))
        jump.add(output)
        rotated.close()
    image.root.add(jump)


def install_one(
    mob_id: int,
    sets: dict[str, list[WzCanvasProperty]],
    speed: int,
    label: str,
    rotate_cw: bool,
    first_attack: int,
    body_attack: int,
    add_jump: bool = False,
) -> dict[str, str]:
    image = build_image(sets, speed, rotate_cw, first_attack, body_attack)
    if add_jump:
        attach_jump(image)
    client = demian.client_mob_path(mob_id)
    server = demian.server_mob_path(mob_id)
    data = arc.verified_image_bytes(arc.encode_image_body(image, arc.gms_reader()), f"{mob_id}.img")
    parsed = WzImage.from_bytes(data, key=arc.GMS_KEY, name=f"{mob_id}.img")
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise RuntimeError(f"{mob_id} parse failed {parsed.parse_warnings}")
    fly0 = parsed.root.get("fly/0")
    if not isinstance(fly0, WzCanvasProperty) or fly0.width <= 4:
        raise RuntimeError(f"{mob_id} fly/0 is empty")
    if (int(fly0.format), int(fly0.format2)) != (1, 0):
        raise RuntimeError(f"{mob_id} fly is not ARGB4444")
    decoded = decode_canvas(fly0, region="GMS").convert("RGBA")
    if decoded.getbbox() is None:
        raise RuntimeError(f"{mob_id} fly decoded empty")
    decoded.close()
    if add_jump:
        jump0 = parsed.root.get("jump/0")
        if not isinstance(jump0, WzCanvasProperty) or jump0.width <= 4:
            raise RuntimeError(f"{mob_id} jump/0 is empty")
        if (int(jump0.format), int(jump0.format2)) != (1, 0):
            raise RuntimeError(f"{mob_id} jump is not ARGB4444")
    xml = arc.image_to_xml(parsed, f"{mob_id}.img")
    if f'name="firstAttack" value="{first_attack}"' not in xml:
        raise RuntimeError(f"{mob_id} firstAttack must be {first_attack}")
    if 'name="removeAfter" value="0"' not in xml:
        raise RuntimeError(f"{mob_id} must not despawn after 15s")
    if "8880102" in xml or "8880169" in xml:
        raise RuntimeError(f"{mob_id} XML still names crash/butterfly IDs")
    if 'name="type" value="2"' in xml:
        raise RuntimeError(f"{mob_id} must not keep a type=2 ball")
    arc.atomic_write_bytes(client, data)
    arc.atomic_write_text(server, xml)
    print(f"{label} -> {mob_id}")
    return {str(client): sha256_bytes(data), str(server): sha256_bytes(xml.encode("utf-8"))}


def main() -> int:
    first = install_one(SWORD_ID, sword_sets(), -30, "BossDemian flyingSword", True, 1, 1, True)
    second = install_one(SWORD_ID, sword_sets(), -30, "BossDemian flyingSword", True, 1, 1, True)
    if first != second:
        raise RuntimeError(f"not idempotent: {first} vs {second}")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
