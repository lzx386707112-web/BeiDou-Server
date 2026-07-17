#!/usr/bin/env python3
"""Build a mobile-safe Boss-only Dusk from the available weakened body."""

from __future__ import annotations

import io
import re
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_body,
    _tag_for,
    encode_compressed_int,
    encode_image_body,
    encode_string_block,
)

from patch_lucid_boss_compat import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    gms_reader,
    img_to_xml,
    remove_child,
    replace_child,
    set_int,
    set_string,
    source_img,
)


SOURCE_ID = 8644611
TARGET_ID = 8644630
SERVER_HP = 5_000_000_000
CLIENT_HP = 2_000_000_000
DUSK_NAME = "戴斯克"
SKILLS = (
    (120, 4, 1),
    (132, 2, 2),
    (114, 37, 3),
)


def convert_canvas_tree_to_argb4444(prop, source_region: str = "EMS") -> None:
    if isinstance(prop, WzCanvasProperty) and prop.has_pixels():
        image = decode_canvas(prop, region=source_region)
        prop.format = 1
        prop.format2 = 0
        prop._png_data = encode_canvas_payload(
            image,
            1,
            int(prop.width),
            int(prop.height),
            key=WzKey.for_region("GMS"),
            listwz=False,
        )
        prop._png_length = len(prop._png_data)
    if hasattr(prop, "children"):
        for child in prop.children():
            convert_canvas_tree_to_argb4444(child, source_region)


def normalize_canvas_origins(prop) -> None:
    if isinstance(prop, WzCanvasProperty):
        origin = prop.child("origin")
        if origin is not None and int(origin.y) > int(prop.height):
            origin.y = int(prop.height)
    if hasattr(prop, "children"):
        for child in prop.children():
            normalize_canvas_origins(child)


def make_skill_action(root: WzSubProperty, action: int) -> None:
    attack_name = f"attack{action}"
    source = root.child(attack_name)
    if source is None:
        raise ValueError(f"{SOURCE_ID}: missing {attack_name}")

    skill = WzSubProperty(f"skill{action}", root)
    for child in source.children():
        if child.name.isdigit():
            skill.add(WzUolProperty(child.name, f"../{attack_name}/{child.name}", skill))
    replace_child(root, skill)


def set_skills(root: WzSubProperty) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{SOURCE_ID}: missing info")

    skills = WzSubProperty("skill", info)
    for index, (skill_id, level, action) in enumerate(SKILLS):
        make_skill_action(root, action)
        entry = WzSubProperty(str(index), skills)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", action, entry))
        skills.add(entry)
    replace_child(info, skills)


def sanitize_root(root: WzSubProperty, server: bool) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{SOURCE_ID}: missing info")
    if server:
        set_string(info, "maxHP", str(SERVER_HP))
    else:
        set_int(info, "maxHP", CLIENT_HP)
    remove_child(info, "revive")
    set_int(info, "speed", 0)
    set_int(info, "fixed", 1)
    set_skills(root)
    normalize_canvas_origins(root)


def patch_client_mob() -> None:
    img = source_img(ROOT.parent / "神说/Data" / f"Mob/{SOURCE_ID}.img")
    sanitize_root(img.root, server=False)
    convert_canvas_tree_to_argb4444(img.root)
    atomic_write_bytes(
        ROOT / f"clien/Data/Mob/{TARGET_ID}.img",
        encode_image_body(img, gms_reader()),
    )


def patch_server_mob() -> None:
    img = source_img(ROOT.parent / "神说/Data" / f"Mob/{SOURCE_ID}.img")
    sanitize_root(img.root, server=True)
    atomic_write_text(
        ROOT / f"gms-server/wz/Mob.wz/{TARGET_ID}.img.xml",
        img_to_xml(img, root_name=f"{TARGET_ID}.img"),
    )


def find_imgdir(text: str, name: str, start: int = 0) -> tuple[int, int]:
    marker = f'<imgdir name="{name}">'
    block_start = text.find(marker, start)
    if block_start < 0:
        raise ValueError(f"missing {marker}")
    pos = block_start
    depth = 0
    while pos < len(text):
        next_open = text.find("<imgdir ", pos)
        next_close = text.find("</imgdir>", pos)
        if next_close < 0:
            break
        if 0 <= next_open < next_close:
            depth += 1
            pos = next_open + 8
        else:
            depth -= 1
            pos = next_close + len("</imgdir>")
            if depth == 0:
                return block_start, pos
    raise ValueError(f"unterminated {marker}")


def patch_server_heal_skill() -> None:
    path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    text = path.read_text(encoding="utf-8")
    skill_start, skill_end = find_imgdir(text, "114")
    skill_block = text[skill_start:skill_end]
    if '<imgdir name="37">' in skill_block:
        return

    level_start, level_end = find_imgdir(skill_block, "level")
    level_block = skill_block[level_start:level_end]
    insert_at = level_block.rfind("</imgdir>")
    level_37 = (
        '<imgdir name="37">'
        '<int name="x" value="300000"/>'
        '<int name="y" value="50000"/>'
        '<int name="hp" value="90"/>'
        '<int name="mpCon" value="10"/>'
        '<int name="interval" value="60"/>'
        '<int name="time" value="1"/>'
        '<vector name="lt" x="-400" y="-350"/>'
        '<vector name="rb" x="400" y="250"/>'
        '</imgdir>'
    )
    level_block = level_block[:insert_at] + level_37 + level_block[insert_at:]
    skill_block = skill_block[:level_start] + level_block + skill_block[level_end:]
    text = text[:skill_start] + skill_block + text[skill_end:]
    atomic_write_text(path, text)


def patch_client_string() -> None:
    path = ROOT / "clien/Data/String/Mob.img"
    data = path.read_bytes()
    img = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    img.parse()
    if img.root.get(f"{TARGET_ID}/name") is not None:
        return

    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region("GMS"))
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError(f"{path}: unexpected String/Mob.img header")
    reader.skip(2)
    count_offset = reader.position
    if data[count_offset] == 0x80:
        count_len = 5
        count = struct.unpack("<i", data[count_offset + 1:count_offset + 5])[0]
    else:
        count_len = 1
        count = struct.unpack("<b", data[count_offset:count_offset + 1])[0]
    count_bytes = encode_compressed_int(count + 1)
    if len(count_bytes) != count_len:
        raise ValueError(f"{path}: root count width would change")

    entry = WzSubProperty(str(TARGET_ID))
    entry.add(WzStringProperty("name", DUSK_NAME, entry))
    encoder = gms_reader()
    append = bytearray()
    append += encode_string_block(encoder, entry.name)
    append += bytes([_tag_for(entry)])
    append += _encode_property_body(entry, encoder)

    patched = bytearray(data)
    patched[count_offset:count_offset + count_len] = count_bytes
    patched += append
    atomic_write_bytes(path, bytes(patched))


def patch_server_string(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    replacement = f'<imgdir name="{TARGET_ID}"><string name="name" value="{DUSK_NAME}"/></imgdir>'
    pattern = rf'<imgdir name="{TARGET_ID}">.*?</imgdir>'
    if re.search(pattern, text, flags=re.DOTALL):
        text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
    else:
        root_close = text.rfind("</imgdir>")
        if root_close < 0:
            raise ValueError(f"{path}: missing root closing imgdir")
        text = text[:root_close] + replacement + text[root_close:]
    atomic_write_text(path, text)


def main() -> int:
    patch_client_mob()
    patch_server_mob()
    patch_server_heal_skill()
    patch_client_string()
    patch_server_string(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_string(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
