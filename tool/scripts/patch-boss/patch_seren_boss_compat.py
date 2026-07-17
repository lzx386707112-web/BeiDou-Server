#!/usr/bin/env python3
"""Build a mobile-safe five-stage Boss-only Chosen Seren chain."""

from __future__ import annotations

import io
import re
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty, WzUolProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_body,
    _tag_for,
    encode_compressed_int,
    encode_image_body,
    encode_string_block,
)

from patch_dusk_boss_compat import convert_canvas_tree_to_argb4444  # noqa: E402
from patch_lucid_boss_compat import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    gms_reader,
    img_to_xml,
    replace_child,
    set_int,
    set_revive,
    set_string,
    source_img,
)


SOURCE_IDS = (8880600, 8880603, 8880607, 8880609, 8880612)
TARGET_IDS = (8880340, 8880341, 8880342, 8880343, 8880344)
SOURCE_BY_TARGET = dict(zip(TARGET_IDS, SOURCE_IDS))
SERVER_STAGE_HP = 5_000_000_000
CLIENT_STAGE_HP = 2_000_000_000
REVIVE = dict(zip(TARGET_IDS[:-1], TARGET_IDS[1:]))
NAMES = {mob_id: "神选者塞伦" for mob_id in TARGET_IDS}

# Preserve every source skill that already has a complete old-client and old-server level.
SKILLS = {
    8880340: ((140, 6, 1), (145, 1, 2), (128, 1, 3), (141, 11, 4)),
    8880341: ((140, 6, 1), (145, 1, 2)),
    8880342: (
        (140, 6, 1),
        (145, 1, 2),
    ),
    8880343: ((140, 6, 1), (145, 1, 2), (128, 1, 3)),
    8880344: ((140, 6, 1), (145, 1, 2), (128, 1, 3)),
}

# Source action names are inconsistent (skill/Skill) and several stages omit
# skill actions completely. Reuse the closest native visual without copying pixels.
VISUALS = {
    8880340: {1: "skill1", 2: "Skill2", 3: "Skill3", 4: "attack2"},
    8880341: {1: "attack1", 2: "attack2", 3: "attack1", 4: "attack2"},
    8880342: {1: "attack1", 2: "attack2", 3: "attack3", 4: "attack2"},
    8880343: {1: "skill1", 2: "attack1", 3: "attack2", 4: "attack2"},
    8880344: {1: "skill1", 2: "attack1", 3: "attack2", 4: "attack2"},
}


def make_skill_action(root: WzSubProperty, action: int, source_name: str) -> None:
    target_name = f"skill{action}"
    source = root.child(source_name)
    if source is None:
        raise ValueError(f"{root.name}: missing {source_name}")
    frames = [child for child in source.children() if child.name.isdigit()]
    if not frames:
        raise ValueError(f"{root.name}: {source_name} has no animation frames")
    if source_name == target_name:
        return

    skill = WzSubProperty(target_name, root)
    for frame in frames:
        skill.add(WzUolProperty(frame.name, f"../{source_name}/{frame.name}", skill))
    replace_child(root, skill)


def set_skills(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")

    for action, source_name in VISUALS[mob_id].items():
        make_skill_action(root, action, source_name)

    skill_root = WzSubProperty("skill", info)
    for index, (skill_id, level, action) in enumerate(SKILLS[mob_id]):
        entry = WzSubProperty(str(index), skill_root)
        entry.add(WzIntProperty("skill", skill_id, entry))
        entry.add(WzIntProperty("level", level, entry))
        entry.add(WzIntProperty("action", action, entry))
        skill_root.add(entry)
    replace_child(info, skill_root)


def sanitize_root(root: WzSubProperty, mob_id: int, server: bool) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")
    if server:
        set_string(info, "maxHP", str(SERVER_STAGE_HP))
    else:
        set_int(info, "maxHP", CLIENT_STAGE_HP)
    set_int(info, "PDRate", 50)
    set_int(info, "MDRate", 50)
    set_revive(info, REVIVE.get(mob_id))
    set_skills(root, mob_id)


def patch_client_mob(mob_id: int) -> None:
    source_id = SOURCE_BY_TARGET[mob_id]
    img = source_img(ROOT.parent / "神说/Data" / f"Mob/{source_id}.img")
    sanitize_root(img.root, mob_id, server=False)
    convert_canvas_tree_to_argb4444(img.root)
    atomic_write_bytes(
        ROOT / f"clien/Data/Mob/{mob_id}.img",
        encode_image_body(img, gms_reader()),
    )


def patch_server_mob(mob_id: int) -> None:
    source_id = SOURCE_BY_TARGET[mob_id]
    img = source_img(ROOT.parent / "神说/Data" / f"Mob/{source_id}.img")
    sanitize_root(img.root, mob_id, server=True)
    atomic_write_text(
        ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
        img_to_xml(img, root_name=f"{mob_id}.img"),
    )


def patch_client_strings() -> None:
    path = ROOT / "clien/Data/String/Mob.img"
    data = path.read_bytes()
    img = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    img.parse()
    missing = [(mob_id, name) for mob_id, name in NAMES.items() if img.root.get(f"{mob_id}/name") is None]
    if not missing:
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
    count_bytes = encode_compressed_int(count + len(missing))
    if len(count_bytes) != count_len:
        raise ValueError(f"{path}: root count width would change")

    encoder = gms_reader()
    append = bytearray()
    for mob_id, name in missing:
        entry = WzSubProperty(str(mob_id))
        entry.add(WzStringProperty("name", name, entry))
        append += encode_string_block(encoder, entry.name)
        append += bytes([_tag_for(entry)])
        append += _encode_property_body(entry, encoder)

    patched = bytearray(data)
    patched[count_offset:count_offset + count_len] = count_bytes
    patched += append
    atomic_write_bytes(path, bytes(patched))


def patch_server_strings(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for mob_id, name in NAMES.items():
        replacement = f'<imgdir name="{mob_id}"><string name="name" value="{name}"/></imgdir>'
        pattern = rf'<imgdir name="{mob_id}">.*?</imgdir>'
        if re.search(pattern, text, flags=re.DOTALL):
            text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
        else:
            root_close = text.rfind("</imgdir>")
            if root_close < 0:
                raise ValueError(f"{path}: missing root closing imgdir")
            text = text[:root_close] + replacement + text[root_close:]
    atomic_write_text(path, text)


def main() -> int:
    for mob_id in TARGET_IDS:
        patch_client_mob(mob_id)
        patch_server_mob(mob_id)
    patch_client_strings()
    patch_server_strings(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_strings(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
