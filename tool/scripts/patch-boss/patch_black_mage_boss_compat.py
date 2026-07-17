#!/usr/bin/env python3
"""Build a mobile-safe Boss-only Black Mage chain and sword spirits."""

from __future__ import annotations

import io
import re
import struct
import sys
import xml.etree.ElementTree as ET
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

from patch_dusk_boss_compat import convert_canvas_tree_to_argb4444  # noqa: E402
from patch_lucid_boss_compat import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    gms_reader,
    img_to_xml,
    remove_child,
    replace_child,
    set_int,
    set_revive,
    set_string,
    source_img,
)


SPIRIT_IDS = (8880500, 8880501)
MAIN_IDS = (8880502, 8880503, 8880504)
SUPPORT_IDS = (8880505, 8880506, 8880507, 8880511)
BLACK_MAGE_IDS = SPIRIT_IDS + MAIN_IDS + SUPPORT_IDS
SERVER_STAGE_HP = 20_000_000_000
SPIRIT_HP = 2_000_000_000
SUPPORT_HP = {8880505: 100_000_000, 8880506: 1, 8880507: 1, 8880511: 100_000_000}
CLIENT_HP = 2_000_000_000
REVIVE = {8880502: 8880503, 8880503: 8880504}
NAMES = {
    8880500: "创造之光明剑灵",
    8880501: "破坏之黑暗剑灵",
    8880502: "黑魔法师",
    8880503: "黑魔法师",
    8880504: "黑魔法师",
    8880505: "创造与破坏骑士",
    8880506: "红色闪电",
    8880507: "哭墙",
    8880511: "堕天使",
}

# Each tuple is (skill id, level, action). IDs 178-182 are append-only
# compatibility skills implemented by the old server without map scripts.
SKILLS = {
    8880500: ((128, 2, 1), (133, 1, 2)),
    8880501: ((126, 2, 1), (133, 1, 2)),
    8880502: (
        (178, 1, 3),
        (136, 1, 5),
        (179, 1, 2),
        (180, 1, 4),
        (181, 1, 1),
        (182, 1, 6),
    ),
    8880503: (
        (178, 1, 1),
        (179, 1, 2),
        (180, 1, 3),
        (181, 1, 1),
        (182, 1, 3),
    ),
    8880504: (
        (178, 1, 5),
        (179, 1, 2),
        (180, 1, 3),
        (181, 1, 1),
        (182, 1, 4),
    ),
}

VISUALS = {
    8880500: {1: "attack1", 2: "attack2"},
    8880501: {1: "skill1", 2: "attack2"},
    8880502: {1: "skill1", 2: "skill2", 3: "skill5", 4: "skill4", 5: "skill5", 6: "skill6"},
    8880503: {1: "attack3", 2: "attack2", 3: "attack1", 4: "attack1"},
    8880504: {1: "attack3", 2: "attack2", 3: "attack4", 4: "attack4", 5: "attack5"},
}

CUSTOM_SKILLS = {
    178: {"mpCon": 10, "interval": 30, "time": 0, "prop": 100, "x": 50},
    179: {"mpCon": 10, "interval": 15, "time": 0, "prop": 100, "x": 35},
    180: {"mpCon": 10, "interval": 20, "time": 0, "prop": 100, "x": 45},
    181: {"mpCon": 10, "interval": 25, "time": 0, "prop": 100, "x": 2},
    182: {"mpCon": 10, "interval": 30, "time": 0, "prop": 100, "x": 1},
}
FIELD_EFFECT_ROOT = "customBossBlackMage"
FIELD_EFFECT_NAME = "darkExplosion"


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
    for child in frames:
        skill.add(WzUolProperty(child.name, f"../{source_name}/{child.name}", skill))
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


def sanitize_zero_delay_actions(root: WzSubProperty, mob_id: int) -> None:
    for action in root.children():
        if not re.match(r"^(attack|skill|stand|move|regen)", action.name):
            continue
        frames = [frame for frame in action.children() if frame.name.isdigit()]
        if not frames:
            continue
        writable_frames = [frame for frame in frames if hasattr(frame, "add")]
        if not writable_frames:
            continue
        total_delay = sum(
            int(frame.child("delay").value) if frame.child("delay") is not None else 0
            for frame in writable_frames
        )
        if total_delay == 0:
            for frame in writable_frames:
                set_int(frame, "delay", 90)
    if mob_id == 8880505:
        attack = root.child("attack1")
        if attack is not None:
            for frame in attack.children():
                if frame.name.isdigit() and hasattr(frame, "add"):
                    set_int(frame, "delay", 1500)
    if mob_id == 8880507:
        stand = root.child("stand")
        if stand is not None and stand.child("0") is not None:
            set_int(stand.child("0"), "delay", 300)


def sanitize_root(root: WzSubProperty, mob_id: int, server: bool) -> None:
    info = root.child("info")
    if info is None:
        raise ValueError(f"{mob_id}: missing info")

    if mob_id in MAIN_IDS:
        hp = SERVER_STAGE_HP
    elif mob_id in SPIRIT_IDS:
        hp = SPIRIT_HP
    else:
        hp = SUPPORT_HP[mob_id]
    if server:
        set_string(info, "maxHP", str(hp))
    else:
        set_int(info, "maxHP", min(hp, CLIENT_HP))
    set_int(info, "PDRate", 50)
    set_int(info, "MDRate", 50)
    if mob_id in SPIRIT_IDS:
        set_int(info, "PDDamage", 1800)
        set_int(info, "MDDamage", 1800)
    elif mob_id in SUPPORT_IDS:
        set_int(info, "boss", 0)
        set_int(info, "exp", 0)
        remove_child(info, "hpTagColor")
        remove_child(info, "hpTagBgcolor")
    if mob_id == 8880502:
        remove_child(info, "buff")
    set_revive(info, REVIVE.get(mob_id))
    if mob_id in SKILLS:
        set_skills(root, mob_id)
    else:
        remove_child(info, "skill")
    sanitize_zero_delay_actions(root, mob_id)


def patch_client_mob(mob_id: int) -> None:
    img = source_img(ROOT.parent / "神说/Data" / f"Mob/{mob_id}.img")
    sanitize_root(img.root, mob_id, server=False)
    convert_canvas_tree_to_argb4444(img.root)
    atomic_write_bytes(
        ROOT / f"clien/Data/Mob/{mob_id}.img",
        encode_image_body(img, gms_reader()),
    )


def patch_server_mob(mob_id: int) -> None:
    img = source_img(ROOT.parent / "神说/Data" / f"Mob/{mob_id}.img")
    sanitize_root(img.root, mob_id, server=True)
    atomic_write_text(
        ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml",
        img_to_xml(img, root_name=f"{mob_id}.img"),
    )


def append_root_properties(path: Path, properties: list[WzSubProperty]) -> None:
    data = path.read_bytes()
    img = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    img.parse()
    missing = [prop for prop in properties if img.root.child(prop.name) is None]
    if not missing:
        return

    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region("GMS"))
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise ValueError(f"{path}: unexpected image header")
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
    for prop in missing:
        append += encode_string_block(encoder, prop.name)
        append += bytes([_tag_for(prop)])
        append += _encode_property_body(prop, encoder)
    patched = bytearray(data)
    patched[count_offset:count_offset + count_len] = count_bytes
    patched += append
    atomic_write_bytes(path, bytes(patched))


def build_custom_mobskill(skill_id: int) -> WzSubProperty:
    skill = WzSubProperty(str(skill_id))
    levels = WzSubProperty("level", skill)
    level = WzSubProperty("1", levels)
    for name, value in CUSTOM_SKILLS[skill_id].items():
        level.add(WzIntProperty(name, value, level))
    level.add(WzVectorProperty("lt", -2000, -1200, level))
    level.add(WzVectorProperty("rb", 2000, 500, level))
    levels.add(level)
    skill.add(levels)
    return skill


def patch_custom_mobskills() -> None:
    append_root_properties(
        ROOT / "clien/Data/Skill/MobSkill.img",
        [build_custom_mobskill(skill_id) for skill_id in CUSTOM_SKILLS],
    )

    path = ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml"
    root = ET.parse(path).getroot()
    existing = {child.attrib.get("name") for child in root.findall("imgdir")}
    missing = [skill_id for skill_id in CUSTOM_SKILLS if str(skill_id) not in existing]
    if not missing:
        return
    text = path.read_text(encoding="utf-8")
    insert_at = text.rfind("</imgdir>")
    if insert_at < 0:
        raise ValueError(f"{path}: missing root closing imgdir")
    append = []
    for skill_id in missing:
        values = CUSTOM_SKILLS[skill_id]
        body = "".join(f'<int name="{name}" value="{value}"/>' for name, value in values.items())
        body += '<vector name="lt" x="-2000" y="-1200"/><vector name="rb" x="2000" y="500"/>'
        append.append(f'<imgdir name="{skill_id}"><imgdir name="level"><imgdir name="1">{body}</imgdir></imgdir></imgdir>')
    atomic_write_text(path, text[:insert_at] + "".join(append) + text[insert_at:])


def build_dark_explosion_effect() -> WzSubProperty:
    source = source_img(ROOT.parent / "神说/Data/Mob/8880502.img")
    source_group = source.root.child("skill3")
    if source_group is None:
        raise ValueError("8880502: missing source skill3 for field effect")

    root = WzSubProperty(FIELD_EFFECT_ROOT)
    effect = WzSubProperty(FIELD_EFFECT_NAME, root)
    for frame in source_group.children():
        if not frame.name.isdigit() or not isinstance(frame, WzCanvasProperty):
            continue
        image = decode_canvas(frame, region="EMS")
        canvas = WzCanvasProperty(frame.name, effect)
        canvas.width = int(frame.width)
        canvas.height = int(frame.height)
        canvas.format = 1
        canvas.format2 = 0
        canvas._png_data = encode_canvas_payload(
            image,
            1,
            canvas.width,
            canvas.height,
            key=WzKey.for_region("GMS"),
            listwz=False,
        )
        canvas._png_length = len(canvas._png_data)
        origin_x = canvas.width // 2
        origin_y = max(0, canvas.height - 300)
        canvas.add(WzVectorProperty("origin", origin_x, origin_y, canvas))
        canvas.add(WzVectorProperty("head", -1, -min(80, origin_y), canvas))
        canvas.add(WzVectorProperty("lt", -origin_x, -origin_y, canvas))
        canvas.add(WzVectorProperty("rb", canvas.width - origin_x, canvas.height - origin_y, canvas))
        source_delay = frame.child("delay")
        delay = 90 if source_delay is None or int(source_delay.value) <= 0 else int(source_delay.value)
        canvas.add(WzIntProperty("delay", delay, canvas))
        effect.add(canvas)
    if not list(effect.children()):
        raise ValueError("8880502/skill3: no direct Canvas frames")
    root.add(effect)
    return root


def patch_dark_explosion_effect() -> None:
    append_root_properties(ROOT / "clien/Data/Map/Effect.img", [build_dark_explosion_effect()])


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
    patch_custom_mobskills()
    patch_dark_explosion_effect()
    for mob_id in BLACK_MAGE_IDS:
        patch_client_mob(mob_id)
        patch_server_mob(mob_id)
    patch_client_strings()
    patch_server_strings(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_strings(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
