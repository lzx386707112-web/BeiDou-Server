#!/usr/bin/env python3
"""Create Bishop dragon-copy summon skills and patch BeiDou.exe for them."""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzIntProperty,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.writer import encode_image_body  # noqa: E402
from PIL import Image  # noqa: E402


SOURCE_ID = "2321003"
OLD_ID = 2321003
NEW_MIN = 2321010
NEW_MAX = 2321018
TARGETS = [
    (2321010, 22171081, "2217.img", "dragonSwift"),
    (2321011, 22141012, "2217.img", "dragonDive"),
    (2321012, 22171063, "2217.img", "dragonBreath"),
    (2321013, 22140014, "2218.img", "dragonSwiftThunder"),
    (2321014, 22170067, "2218.img", "dragonDiveEarth"),
    (2321015, 22170066, "2218.img", "dragonBreathWind"),
    (2321016, 22201003, "2220.img", "6thDragonSwift"),
    (2321017, 22201007, "2220.img", "6thDragonDive"),
    (2321018, 22201011, "2220.img", "6thDragonBreath"),
]

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "232.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "232.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
DRAGON_CANVAS = Path("/Users/lizixian/Documents/mxd/273/sanjindao/Data/Skill/Dragon/_Canvas")
DRAGON_STRING = Path("/Users/lizixian/Documents/mxd/273/sanjindao/Data/String/Skill.img")
EXE = ROOT / "clien" / "BeiDou.exe"

IMAGE_BASE = 0x400000

HOOK1_VA = 0x7A5227
HOOK1_OFFSET = HOOK1_VA - IMAGE_BASE
HOOK1_ORIGINAL = bytes.fromhex("81bbb40000006b6a23008945e8750b")
HOOK1_CAVE_VA = 0xAEF620
HOOK1_CAVE_OFFSET = HOOK1_CAVE_VA - IMAGE_BASE
HOOK1_EQUAL_VA = 0x7A5236
HOOK1_NOT_EQUAL_VA = 0x7A5241

HOOK2_VA = 0x7AD4F8
HOOK2_OFFSET = HOOK2_VA - IMAGE_BASE
HOOK2_ORIGINAL = bytes.fromhex("3d6b6a2300741c")
HOOK2_CAVE_VA = 0xAEF650
HOOK2_CAVE_OFFSET = HOOK2_CAVE_VA - IMAGE_BASE
HOOK2_EQUAL_VA = 0x7AD51B
HOOK2_RETURN_VA = 0x7AD4FF

HOOK3_VA = 0x967EE6
HOOK3_OFFSET = HOOK3_VA - IMAGE_BASE
HOOK3_ORIGINAL = bytes.fromhex("b84c512f003bf07f590f848e090000")
HOOK3_CAVE_VA = 0xAEF680
HOOK3_CAVE_OFFSET = HOOK3_CAVE_VA - IMAGE_BASE
HOOK3_TARGET_VA = 0x9689DF
HOOK3_GREATER_VA = 0x967F48
HOOK3_EQUAL_VA = 0x968883
HOOK3_RETURN_VA = 0x967EF5


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def backup(path: Path, suffix: str, dry_run: bool) -> None:
    backup_path = path.with_name(path.name + suffix)
    if backup_path.exists():
        return
    if dry_run:
        print(f"[dry-run] would create backup: {backup_path}")
        return
    shutil.copy2(path, backup_path)
    print(f"backup: {backup_path}")


def clone_property(prop, name: str | None = None, parent=None):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        out = WzCanvasProperty(new_name, parent)
        out.width = prop.width
        out.height = prop.height
        out.format = prop.format
        out.format2 = prop.format2
        out._png_offset = prop._png_offset
        out._png_length = prop._png_length
        out._png_data = prop._png_data
        out._wz_image = prop._wz_image
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        return out
    if isinstance(prop, WzVectorProperty):
        return WzVectorProperty(new_name, int(prop.x), int(prop.y), parent)
    if isinstance(prop, WzStringProperty):
        return WzStringProperty(new_name, str(prop.value), parent)
    if isinstance(prop, WzIntProperty):
        return WzIntProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzShortProperty):
        return WzShortProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzLongProperty):
        return WzLongProperty(new_name, int(prop.value), parent)
    if isinstance(prop, WzFloatProperty):
        return WzFloatProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzDoubleProperty):
        return WzDoubleProperty(new_name, float(prop.value), parent)
    if isinstance(prop, WzNullProperty):
        return WzNullProperty(new_name, parent)
    if isinstance(prop, WzUolProperty):
        return WzUolProperty(new_name, prop.value, parent)
    if isinstance(prop, WzConvexProperty):
        out = WzConvexProperty(new_name, parent)
        out.points = [clone_property(point, parent=out) for point in prop.points]
        return out
    if isinstance(prop, WzSoundProperty):
        out = WzSoundProperty(new_name, parent)
        out.length_ms = prop.length_ms
        out.header = prop.header
        out._data_offset = prop._data_offset
        out._data_length = prop._data_length
        out._wz_image = prop._wz_image
        out._data = prop._data
        return out
    raise TypeError(f"unsupported WZ property: {type(prop).__name__}")


def put_child_after(parent: WzSubProperty, after_name: str, prop) -> None:
    prop.parent = parent
    items = []
    inserted = False
    for key, value in parent._children.items():
        if key == prop.name:
            continue
        items.append((key, value))
        if key == after_name:
            items.append((prop.name, prop))
            inserted = True
    if not inserted:
        items.append((prop.name, prop))
    parent._children = dict(items)


def replace_child(parent: WzSubProperty, prop) -> None:
    prop.parent = parent
    parent._children[prop.name] = prop


def mark_invisible(prop: WzSubProperty) -> None:
    replace_child(prop, WzIntProperty("invisible", 1, prop))


def make_canvas_from_source(src: WzCanvasProperty, name: str, parent, target_key: WzKey, *, origin_ratio: tuple[float, float], delay: int, copy_box=None) -> WzCanvasProperty:
    image = decode_canvas(src, region="BMS")
    out = WzCanvasProperty(name, parent)
    out.width = src.width
    out.height = src.height
    out.format = 2
    out.format2 = 0
    out._png_data = encode_canvas_payload(image, 2, src.width, src.height, key=target_key, listwz=False)
    out._png_length = len(out._png_data)
    out.add(WzVectorProperty("origin", int(round(src.width * origin_ratio[0])), int(round(src.height * origin_ratio[1])), out))
    out.add(WzIntProperty("delay", delay, out))
    if copy_box is not None:
        lt, rb = copy_box
        out.add(WzVectorProperty("lt", int(lt.x), int(lt.y), out))
        out.add(WzVectorProperty("rb", int(rb.x), int(rb.y), out))
    return out


def make_icon_from_source(src: WzCanvasProperty, name: str, parent, target_key: WzKey) -> WzCanvasProperty:
    image = decode_canvas(src, region="BMS").convert("RGBA")
    bbox = image.getbbox()
    if bbox is not None:
        image = image.crop(bbox)
    image.thumbnail((32, 32), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    icon.paste(image, ((32 - image.width) // 2, (32 - image.height) // 2), image)

    out = WzCanvasProperty(name, parent)
    out.width = 32
    out.height = 32
    out.format = 2
    out.format2 = 0
    out._png_data = encode_canvas_payload(icon, 2, 32, 32, key=target_key, listwz=False)
    out._png_length = len(out._png_data)
    out.add(WzVectorProperty("origin", 0, 32, out))
    out.add(WzIntProperty("z", 0, out))
    return out


def first_canvas(source_group: WzSubProperty) -> WzCanvasProperty:
    frames = [child for child in source_group.children() if isinstance(child, WzCanvasProperty)]
    if not frames:
        raise RuntimeError(f"source group has no canvas frames: {source_group.name}")
    return frames[len(frames) // 2]


def replace_icons(skill: WzSubProperty, source_group: WzSubProperty, target_key: WzKey) -> None:
    frame = first_canvas(source_group)
    replace_child(skill, make_icon_from_source(frame, "icon", skill, target_key))
    replace_child(skill, make_icon_from_source(frame, "iconMouseOver", skill, target_key))
    replace_child(skill, make_icon_from_source(frame, "iconDisabled", skill, target_key))


def make_frame_group(name: str, source_group: WzSubProperty, parent, target_key: WzKey, *, origin_ratio: tuple[float, float], delay: int, copy_box=None, info=None) -> WzSubProperty:
    out = WzSubProperty(name, parent)
    if info is not None:
        out.add(clone_property(info, parent=out))
    frame_no = 0
    for child in source_group.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        out.add(make_canvas_from_source(child, str(frame_no), out, target_key, origin_ratio=origin_ratio, delay=delay, copy_box=copy_box))
        frame_no += 1
    if frame_no == 0:
        raise RuntimeError(f"source group has no canvas frames: {source_group.name}")
    return out


def load_dragon_groups():
    cache = {}

    def get(img_name: str, node_name: str) -> WzSubProperty:
        if img_name not in cache:
            path = DRAGON_CANVAS / img_name
            image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("BMS"), name=img_name)
            cache[img_name] = image.parse()
        node = cache[img_name].get(node_name)
        if node is None:
            raise RuntimeError(f"missing dragon node: {img_name}/{node_name}")
        return node

    return get


def load_dragon_strings():
    image = WzImage.from_bytes(DRAGON_STRING.read_bytes(), key=WzKey.for_region("BMS"), name=DRAGON_STRING.name)
    root = image.parse()

    def get(source_string_id: int) -> WzSubProperty:
        node = root.get(str(source_string_id))
        if node is None:
            raise RuntimeError(f"missing Dragon String/Skill.img node: {source_string_id}")
        return node

    return get


def get_string_value(node: WzSubProperty, child_name: str) -> str | None:
    child = node.get(child_name)
    if isinstance(child, WzStringProperty):
        return str(child.value)
    return None


def source_string_name(get_dragon_string, source_string_id: int) -> str:
    node = get_dragon_string(source_string_id)
    return get_string_value(node, "name") or str(source_string_id)


def patch_client_skill(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    skill_root = root.get("skill")
    source = root.get(f"skill/{SOURCE_ID}")
    if skill_root is None or source is None:
        raise RuntimeError(f"missing client skill/{SOURCE_ID}")

    get_dragon = load_dragon_groups()
    stand = get_dragon("2217.img", "stand")
    move = get_dragon("2217.img", "move")
    back = get_dragon("2217.img", "dragonBack")
    base_stand0 = source.get("summon/stand/0")
    base_fly0 = source.get("summon/fly/0")
    base_attack0 = source.get("summon/attack1/0")
    copy_box = (base_stand0.child("lt"), base_stand0.child("rb")) if base_stand0 else None
    target_key = image.wz_file.reader.key
    after_name = SOURCE_ID

    for skill_id, _source_string_id, img_name, attack_node in TARGETS:
        clone = clone_property(source, str(skill_id))
        mark_invisible(clone)
        summon = clone.get("summon")
        attack_group = get_dragon(img_name, attack_node)
        attack_info = source.get("summon/attack1/info")
        replace_icons(clone, attack_group, target_key)
        replace_child(summon, make_frame_group("summoned", stand, summon, target_key, origin_ratio=(0.365, 0.854), delay=120, copy_box=copy_box))
        replace_child(summon, make_frame_group("stand", stand, summon, target_key, origin_ratio=(0.365, 0.854), delay=150, copy_box=copy_box))
        replace_child(summon, make_frame_group("fly", move, summon, target_key, origin_ratio=(0.36, 0.82), delay=120, copy_box=None))
        replace_child(summon, make_frame_group("die", back, summon, target_key, origin_ratio=(0.5, 0.8), delay=120, copy_box=None))
        replace_child(summon, make_frame_group("attack1", attack_group, summon, target_key, origin_ratio=(0.711, 0.642), delay=90, copy_box=None, info=attack_info))
        put_child_after(skill_root, after_name, clone)
        after_name = str(skill_id)

    if dry_run:
        print(f"[dry-run] would patch client dragon skills {NEW_MIN}-{NEW_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-skills", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"patched client dragon skills {NEW_MIN}-{NEW_MAX}: {path}")


def patch_client_string(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    get_dragon_string = load_dragon_strings()
    after_name = SOURCE_ID
    for skill_id, source_string_id, _img_name, _attack_node in TARGETS:
        source = get_dragon_string(source_string_id)
        clone = clone_property(source, str(skill_id))
        put_child_after(root, after_name, clone)
        after_name = str(skill_id)
    if dry_run:
        print(f"[dry-run] would patch client dragon strings {NEW_MIN}-{NEW_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-skills", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"patched client dragon strings {NEW_MIN}-{NEW_MAX}: {path}")


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    token = f'<imgdir name="{node_name}">'
    start = text.find(token)
    if start < 0:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    depth = 0
    for match in re.finditer(r"</?imgdir\b[^>]*>", text[start:]):
        tag = match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, start + match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def build_string_xml_block(skill_id: int, source: WzSubProperty) -> str:
    lines = [f'<imgdir name="{skill_id}">']
    for child in source.children():
        if isinstance(child, WzStringProperty):
            lines.append(f'<string name="{escape(child.name)}" value="{escape(str(child.value or ""))}"/>')
    lines.append("</imgdir>")
    return "".join(lines)


def patch_skill_xml(path: Path, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    src_start, src_end = find_imgdir_block(text, SOURCE_ID)
    source = text[src_start:src_end]
    for skill_id, _source_string_id, _img_name, _attack_node in TARGETS:
        try:
            tgt_start, tgt_end = find_imgdir_block(text, str(skill_id))
            text = text[:tgt_start] + text[tgt_end:]
        except RuntimeError:
            pass
        clone = source.replace(f'<imgdir name="{SOURCE_ID}">', f'<imgdir name="{skill_id}">', 1)
        clone = clone.replace(f'<imgdir name="{skill_id}">', f'<imgdir name="{skill_id}"><int name="invisible" value="1"/>', 1)
        insert_at = find_imgdir_block(text, SOURCE_ID)[1]
        text = text[:insert_at] + clone + text[insert_at:]
    if dry_run:
        print(f"[dry-run] would patch XML dragon skills {NEW_MIN}-{NEW_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-skills", dry_run=False)
    atomic_write_text(path, text)
    print(f"patched XML dragon skills {NEW_MIN}-{NEW_MAX}: {path}")


def patch_string_xml(path: Path, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    get_dragon_string = load_dragon_strings()
    insert_after = SOURCE_ID
    for skill_id, source_string_id, _img_name, _attack_node in TARGETS:
        try:
            tgt_start, tgt_end = find_imgdir_block(text, str(skill_id))
            text = text[:tgt_start] + text[tgt_end:]
        except RuntimeError:
            pass
        insert_at = find_imgdir_block(text, insert_after)[1]
        text = text[:insert_at] + build_string_xml_block(skill_id, get_dragon_string(source_string_id)) + text[insert_at:]
        insert_after = str(skill_id)
    if dry_run:
        print(f"[dry-run] would patch XML dragon strings {NEW_MIN}-{NEW_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-skills", dry_run=False)
    atomic_write_text(path, text)
    print(f"patched XML dragon strings {NEW_MIN}-{NEW_MAX}: {path}")


def rel32(from_va: int, to_va: int) -> bytes:
    return struct.pack("<i", to_va - (from_va + 5))


def jmp(from_va: int, to_va: int) -> bytes:
    return b"\xE9" + rel32(from_va, to_va)


def je(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x84" + struct.pack("<i", to_va - (from_va + 6))


def jl(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x8C" + struct.pack("<i", to_va - (from_va + 6))


def jle(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x8E" + struct.pack("<i", to_va - (from_va + 6))


def jbe(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x86" + struct.pack("<i", to_va - (from_va + 6))


def jg(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x8F" + struct.pack("<i", to_va - (from_va + 6))


def cmp_reg_imm(op: bytes, value: int) -> bytes:
    return op + struct.pack("<I", value)


def build_cave1() -> bytes:
    chunks = []
    va = HOOK1_CAVE_VA
    chunks.append(bytes.fromhex("8945e8"))  # mov [ebp-0x18], eax
    va += 3
    chunks.append(bytes.fromhex("8b93b4000000"))  # mov edx, [ebx+0xb4]
    va += 6
    chunks.append(cmp_reg_imm(bytes.fromhex("81fa"), OLD_ID))
    va += 6
    chunks.append(je(va, HOOK1_EQUAL_VA))
    va += 6
    chunks.append(cmp_reg_imm(bytes.fromhex("81ea"), NEW_MIN))  # sub edx, min
    va += 6
    chunks.append(bytes.fromhex("83fa") + bytes([NEW_MAX - NEW_MIN]))  # cmp edx, range width
    va += 3
    chunks.append(jbe(va, HOOK1_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK1_NOT_EQUAL_VA))
    return b"".join(chunks)


def build_cave2() -> bytes:
    chunks = []
    va = HOOK2_CAVE_VA
    chunks.append(bytes.fromhex("8bd0"))  # mov edx, eax
    va += 2
    chunks.append(cmp_reg_imm(bytes.fromhex("81fa"), OLD_ID))
    va += 6
    chunks.append(je(va, HOOK2_EQUAL_VA))
    va += 6
    chunks.append(cmp_reg_imm(bytes.fromhex("81ea"), NEW_MIN))  # sub edx, min
    va += 6
    chunks.append(bytes.fromhex("83fa") + bytes([NEW_MAX - NEW_MIN]))
    va += 3
    chunks.append(jbe(va, HOOK2_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK2_RETURN_VA))
    return b"".join(chunks)


def build_cave3() -> bytes:
    chunks = []
    va = HOOK3_CAVE_VA
    chunks.append(bytes.fromhex("8bd6"))  # mov edx, esi
    va += 2
    chunks.append(cmp_reg_imm(bytes.fromhex("81ea"), NEW_MIN))  # sub edx, min
    va += 6
    chunks.append(bytes.fromhex("83fa") + bytes([NEW_MAX - NEW_MIN]))
    va += 3
    chunks.append(jbe(va, HOOK3_TARGET_VA))
    va += 6
    chunks.append(b"\xB8" + struct.pack("<I", 0x2F514C))
    va += 5
    chunks.append(bytes.fromhex("3bf0"))
    va += 2
    chunks.append(jg(va, HOOK3_GREATER_VA))
    va += 6
    chunks.append(je(va, HOOK3_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK3_RETURN_VA))
    return b"".join(chunks)


def patch_exe(path: Path, dry_run: bool) -> None:
    data = bytearray(path.read_bytes())
    hook1_patch = jmp(HOOK1_VA, HOOK1_CAVE_VA) + b"\x90" * (len(HOOK1_ORIGINAL) - 5)
    hook2_patch = jmp(HOOK2_VA, HOOK2_CAVE_VA) + b"\x90" * (len(HOOK2_ORIGINAL) - 5)
    hook3_patch = jmp(HOOK3_VA, HOOK3_CAVE_VA) + b"\x90" * (len(HOOK3_ORIGINAL) - 5)
    cave1 = build_cave1()
    cave2 = build_cave2()
    cave3 = build_cave3()
    if len(cave1) > HOOK2_CAVE_OFFSET - HOOK1_CAVE_OFFSET:
        raise RuntimeError("hook1 cave overlaps hook2 cave")
    if len(cave2) > HOOK3_CAVE_OFFSET - HOOK2_CAVE_OFFSET:
        raise RuntimeError("hook2 cave overlaps hook3 cave")

    current_hook1 = bytes(data[HOOK1_OFFSET:HOOK1_OFFSET + len(HOOK1_ORIGINAL)])
    current_hook2 = bytes(data[HOOK2_OFFSET:HOOK2_OFFSET + len(HOOK2_ORIGINAL)])
    current_hook3 = bytes(data[HOOK3_OFFSET:HOOK3_OFFSET + len(HOOK3_ORIGINAL)])
    if current_hook1 not in (HOOK1_ORIGINAL, hook1_patch):
        raise RuntimeError(f"unexpected hook1 bytes: {current_hook1.hex()}")
    if current_hook2 not in (HOOK2_ORIGINAL, hook2_patch):
        raise RuntimeError(f"unexpected hook2 bytes: {current_hook2.hex()}")
    if current_hook3 not in (HOOK3_ORIGINAL, hook3_patch):
        raise RuntimeError(f"unexpected hook3 bytes: {current_hook3.hex()}")

    if dry_run:
        print(f"[dry-run] would patch BeiDou.exe dragon range {NEW_MIN}-{NEW_MAX}")
        return
    backup(path, ".bak-bishop-dragon-skills", dry_run=False)
    data[HOOK1_OFFSET:HOOK1_OFFSET + len(hook1_patch)] = hook1_patch
    data[HOOK2_OFFSET:HOOK2_OFFSET + len(hook2_patch)] = hook2_patch
    data[HOOK3_OFFSET:HOOK3_OFFSET + len(hook3_patch)] = hook3_patch
    data[HOOK1_CAVE_OFFSET:HOOK1_CAVE_OFFSET + len(cave1)] = cave1
    data[HOOK2_CAVE_OFFSET:HOOK2_CAVE_OFFSET + len(cave2)] = cave2
    data[HOOK3_CAVE_OFFSET:HOOK3_CAVE_OFFSET + len(cave3)] = cave3
    atomic_write_bytes(path, bytes(data))
    print(f"patched BeiDou.exe dragon range {NEW_MIN}-{NEW_MAX}: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch_client_skill(CLIENT_SKILL, args.dry_run)
    patch_client_string(CLIENT_STRING, args.dry_run)
    patch_skill_xml(SERVER_SKILL, args.dry_run)
    patch_string_xml(SERVER_STRING, args.dry_run)
    patch_exe(EXE, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
