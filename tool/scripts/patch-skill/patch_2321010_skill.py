#!/usr/bin/env python3
"""Add Bishop test skill 2321010 by cloning 2321003 and patching BeiDou.exe."""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
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


SOURCE_ID = "2321003"
TARGET_ID = "2321010"
TARGET_NAME = "新技能测试"

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "232.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "232.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
EXE = ROOT / "clien" / "BeiDou.exe"

IMAGE_BASE = 0x400000
OLD_ID = 2321003
NEW_ID = 2321010

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
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as tmp:
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


def patch_client_skill(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    skill_root = root.get("skill")
    source = root.get(f"skill/{SOURCE_ID}")
    if skill_root is None or source is None:
        raise RuntimeError(f"missing client skill/{SOURCE_ID}")

    clone = clone_property(source, TARGET_ID)
    put_child_after(skill_root, SOURCE_ID, clone)
    if dry_run:
        print(f"[dry-run] would clone client skill {SOURCE_ID} -> {TARGET_ID}: {path}")
        return
    backup(path, ".bak-2321010-skill", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"cloned client skill {SOURCE_ID} -> {TARGET_ID}: {path}")


def patch_client_string(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    source = root.get(SOURCE_ID)
    if source is None:
        raise RuntimeError(f"missing client string {SOURCE_ID}")

    clone = clone_property(source, TARGET_ID)
    name_node = clone.child("name")
    if not isinstance(name_node, WzStringProperty):
        clone.add(WzStringProperty("name", TARGET_NAME, clone))
    else:
        name_node._value = TARGET_NAME
    put_child_after(root, SOURCE_ID, clone)
    if dry_run:
        print(f"[dry-run] would clone client string {SOURCE_ID} -> {TARGET_ID}: {path}")
        return
    backup(path, ".bak-2321010-skill", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"cloned client string {SOURCE_ID} -> {TARGET_ID}: {path}")


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


def clone_xml_block(text: str, *, rename_string: bool) -> str:
    src_start, src_end = find_imgdir_block(text, SOURCE_ID)
    source = text[src_start:src_end]
    clone = source.replace(f'<imgdir name="{SOURCE_ID}">', f'<imgdir name="{TARGET_ID}">', 1)
    if rename_string:
        clone = re.sub(
            r'<string name="name" value="[^"]*"\s*/>',
            f'<string name="name" value="{TARGET_NAME}"/>',
            clone,
            count=1,
        )

    try:
        tgt_start, tgt_end = find_imgdir_block(text, TARGET_ID)
        text = text[:tgt_start] + text[tgt_end:]
        if tgt_start < src_end:
            src_start, src_end = find_imgdir_block(text, SOURCE_ID)
    except RuntimeError:
        pass

    insert_at = find_imgdir_block(text, SOURCE_ID)[1]
    return text[:insert_at] + clone + text[insert_at:]


def patch_server_xml(path: Path, dry_run: bool, *, rename_string: bool) -> None:
    text = path.read_text(encoding="utf-8")
    new_text = clone_xml_block(text, rename_string=rename_string)
    if new_text == text:
        print(f"server XML already contains {TARGET_ID}: {path}")
        return
    if dry_run:
        print(f"[dry-run] would clone server XML {SOURCE_ID} -> {TARGET_ID}: {path}")
        return
    backup(path, ".bak-2321010-skill", dry_run=False)
    atomic_write_text(path, new_text)
    print(f"cloned server XML {SOURCE_ID} -> {TARGET_ID}: {path}")


def rel32(from_va: int, to_va: int) -> bytes:
    return struct.pack("<i", to_va - (from_va + 5))


def jmp(from_va: int, to_va: int) -> bytes:
    return b"\xE9" + rel32(from_va, to_va)


def je(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x84" + struct.pack("<i", to_va - (from_va + 6))


def cmp_eax_imm(value: int) -> bytes:
    return b"\x3D" + struct.pack("<I", value)


def cmp_esi_imm(value: int) -> bytes:
    return b"\x81\xFE" + struct.pack("<I", value)


def cmp_ebx_b4_imm(value: int) -> bytes:
    return bytes.fromhex("81bbb4000000") + struct.pack("<I", value)


def build_cave1() -> bytes:
    chunks = []
    va = HOOK1_CAVE_VA
    chunks.append(bytes.fromhex("8945e8"))  # mov dword ptr [ebp - 0x18], eax
    va += 3
    chunks.append(cmp_ebx_b4_imm(NEW_ID))
    va += 10
    chunks.append(je(va, HOOK1_EQUAL_VA))
    va += 6
    chunks.append(cmp_ebx_b4_imm(OLD_ID))
    va += 10
    chunks.append(je(va, HOOK1_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK1_NOT_EQUAL_VA))
    return b"".join(chunks)


def build_cave2() -> bytes:
    chunks = []
    va = HOOK2_CAVE_VA
    chunks.append(cmp_eax_imm(NEW_ID))
    va += 5
    chunks.append(je(va, HOOK2_EQUAL_VA))
    va += 6
    chunks.append(cmp_eax_imm(OLD_ID))
    va += 5
    chunks.append(je(va, HOOK2_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK2_RETURN_VA))
    return b"".join(chunks)


def build_cave3() -> bytes:
    chunks = []
    va = HOOK3_CAVE_VA
    chunks.append(cmp_esi_imm(NEW_ID))
    va += 6
    chunks.append(je(va, HOOK3_TARGET_VA))
    va += 6
    chunks.append(b"\xB8" + struct.pack("<I", 0x2F514C))  # mov eax, 0x2f514c
    va += 5
    chunks.append(bytes.fromhex("3bf0"))  # cmp esi, eax
    va += 2
    chunks.append(bytes.fromhex("0f8f") + struct.pack("<i", HOOK3_GREATER_VA - (va + 6)))
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

    current_hook1 = bytes(data[HOOK1_OFFSET:HOOK1_OFFSET + len(HOOK1_ORIGINAL)])
    current_hook2 = bytes(data[HOOK2_OFFSET:HOOK2_OFFSET + len(HOOK2_ORIGINAL)])
    current_hook3 = bytes(data[HOOK3_OFFSET:HOOK3_OFFSET + len(HOOK3_ORIGINAL)])
    current_cave1 = bytes(data[HOOK1_CAVE_OFFSET:HOOK1_CAVE_OFFSET + len(cave1)])
    current_cave2 = bytes(data[HOOK2_CAVE_OFFSET:HOOK2_CAVE_OFFSET + len(cave2)])
    current_cave3 = bytes(data[HOOK3_CAVE_OFFSET:HOOK3_CAVE_OFFSET + len(cave3)])

    already = (
        current_hook1 == hook1_patch
        and current_hook2 == hook2_patch
        and current_hook3 == hook3_patch
        and current_cave1 == cave1
        and current_cave2 == cave2
        and current_cave3 == cave3
    )
    if already:
        print("BeiDou.exe already has the 2321010 hooks.")
        return
    if current_hook1 not in (HOOK1_ORIGINAL, hook1_patch):
        raise RuntimeError(f"unexpected hook1 bytes: {current_hook1.hex()}")
    if current_hook2 not in (HOOK2_ORIGINAL, hook2_patch):
        raise RuntimeError(f"unexpected hook2 bytes: {current_hook2.hex()}")
    if current_hook3 not in (HOOK3_ORIGINAL, hook3_patch):
        raise RuntimeError(f"unexpected hook3 bytes: {current_hook3.hex()}")
    if current_cave1 != cave1 and not all(v == 0 for v in current_cave1):
        raise RuntimeError(f"hook1 cave is not empty: {current_cave1.hex()}")
    if current_cave2 != cave2 and not all(v == 0 for v in current_cave2):
        raise RuntimeError(f"hook2 cave is not empty: {current_cave2.hex()}")
    if current_cave3 != cave3 and not all(v == 0 for v in current_cave3):
        raise RuntimeError(f"hook3 cave is not empty: {current_cave3.hex()}")

    print(f"2321010 hook1 cave bytes ({len(cave1)}): {cave1.hex()}")
    print(f"2321010 hook2 cave bytes ({len(cave2)}): {cave2.hex()}")
    print(f"2321010 hook3 cave bytes ({len(cave3)}): {cave3.hex()}")
    if dry_run:
        print(f"[dry-run] would patch BeiDou.exe: {path}")
        return

    backup(path, ".bak-2321010-skill", dry_run=False)
    data[HOOK1_OFFSET:HOOK1_OFFSET + len(hook1_patch)] = hook1_patch
    data[HOOK2_OFFSET:HOOK2_OFFSET + len(hook2_patch)] = hook2_patch
    data[HOOK3_OFFSET:HOOK3_OFFSET + len(hook3_patch)] = hook3_patch
    data[HOOK1_CAVE_OFFSET:HOOK1_CAVE_OFFSET + len(cave1)] = cave1
    data[HOOK2_CAVE_OFFSET:HOOK2_CAVE_OFFSET + len(cave2)] = cave2
    data[HOOK3_CAVE_OFFSET:HOOK3_CAVE_OFFSET + len(cave3)] = cave3
    atomic_write_bytes(path, bytes(data))
    print(f"patched BeiDou.exe for {TARGET_ID}: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    patch_client_skill(CLIENT_SKILL, args.dry_run)
    patch_client_string(CLIENT_STRING, args.dry_run)
    patch_server_xml(SERVER_SKILL, args.dry_run, rename_string=False)
    patch_server_xml(SERVER_STRING, args.dry_run, rename_string=True)
    patch_exe(EXE, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
