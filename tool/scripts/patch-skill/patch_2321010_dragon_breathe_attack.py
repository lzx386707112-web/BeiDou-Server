#!/usr/bin/env python3
"""Convert 2321010 from a Bahamut-style summon clone to a Dragon breath attack."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzIntProperty, WzStringProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

import patch_bishop_dragon_skills as dragon_patch  # noqa: E402


SKILL_ID = 2321010
SKILL_ID_TEXT = str(SKILL_ID)
DRAGON_CANVAS = Path("/Users/lizixian/Documents/mxd/273/sanjindao/Data/Skill/Dragon/_Canvas/2217.img")
DRAGON_ACTION = "dragonImperialBreathe"
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "232.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "232.img.xml"
EXE = ROOT / "clien" / "BeiDou.exe"

ATTACK_COUNT = 2
MOB_COUNT = 6
LT = (-640, -365)
RB = (65, 220)
ACTION = "genesis"

IMAGE_BASE = 0x400000

SUMMON_MIN = 2321011
SUMMON_MAX = 2321018
BAHAMUT_ID = 2321003

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
HOOK3_ATTACK_VA = 0x96928B
HOOK3_SUMMON_VA = 0x9689DF
HOOK3_GREATER_VA = 0x967F48
HOOK3_EQUAL_VA = 0x968883
HOOK3_RETURN_VA = 0x967EF5

AOE_HOOK_VA = 0x955D0E
AOE_HOOK_OFFSET = AOE_HOOK_VA - IMAGE_BASE
AOE_ORIGINAL = bytes.fromhex("3dad9521000f8459060000")
AOE_OLD_CAVE_VA = 0xAEF602
AOE_NEW_CAVE_VA = 0xAEF6B0
AOE_NEW_CAVE_OFFSET = AOE_NEW_CAVE_VA - IMAGE_BASE
AOE_BRANCH_VA = 0x956372
AOE_RETURN_VA = 0x955D19


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


def replace_child(parent: WzSubProperty, prop) -> None:
    prop.parent = parent
    parent._children[prop.name] = prop


def remove_child(parent: WzSubProperty, name: str) -> None:
    parent._children.pop(name, None)


def set_int(parent: WzSubProperty, name: str, value: int) -> None:
    replace_child(parent, WzIntProperty(name, value, parent))


def set_vector(parent: WzSubProperty, name: str, xy: tuple[int, int]) -> None:
    replace_child(parent, WzVectorProperty(name, xy[0], xy[1], parent))


def set_action(skill: WzSubProperty) -> None:
    action = WzSubProperty("action", skill)
    action.add(WzStringProperty("0", ACTION, action))
    replace_child(skill, action)


def read_server_level_values(path: Path) -> dict[int, dict[str, int]]:
    text = path.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, SKILL_ID_TEXT)
    block = text[start:end]
    values: dict[int, dict[str, int]] = {}
    for level in range(1, 31):
        level_start, level_end = find_imgdir_block(block, str(level))
        level_block = block[level_start:level_end]
        values[level] = {}
        for name in ("mpCon", "time", "mastery", "mad"):
            match = re.search(rf'<int name="{name}" value="(-?\d+)"/>', level_block)
            if match:
                values[level][name] = int(match.group(1))
    return values


def patch_client_skill(path: Path, server_values: dict[int, dict[str, int]], dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    skill = root.get(f"skill/{SKILL_ID_TEXT}")
    if skill is None:
        raise RuntimeError(f"missing client skill/{SKILL_ID_TEXT}")

    dragon_image = WzImage.from_bytes(DRAGON_CANVAS.read_bytes(), key=WzKey.for_region("BMS"), name=DRAGON_CANVAS.name)
    dragon_root = dragon_image.parse()
    breath = dragon_root.get(DRAGON_ACTION)
    if breath is None:
        raise RuntimeError(f"missing dragon action: {DRAGON_ACTION}")

    target_key = image.wz_file.reader.key
    remove_child(skill, "summon")
    remove_child(skill, "req")
    set_action(skill)
    dragon_patch.replace_icons(skill, breath, target_key)
    replace_child(skill, dragon_patch.make_frame_group("effect", breath, skill, target_key, origin_ratio=(0.35, 0.78), delay=90))

    level_root = skill.get("level")
    if level_root is None:
        raise RuntimeError(f"missing client skill/{SKILL_ID_TEXT}/level")
    for level in range(1, 31):
        level_node = level_root.get(str(level))
        if level_node is None:
            raise RuntimeError(f"missing client skill/{SKILL_ID_TEXT}/level/{level}")
        values = server_values.get(level, {})
        for name in ("mpCon", "time", "mastery", "mad"):
            if name in values:
                set_int(level_node, name, values[name])
        mad = values.get("mad")
        if mad is None:
            mad_node = level_node.get("mad")
            mad = int(mad_node.value) if mad_node is not None else 100
        set_int(level_node, "damage", mad)
        set_int(level_node, "attackCount", ATTACK_COUNT)
        set_int(level_node, "mobCount", MOB_COUNT)
        set_vector(level_node, "lt", LT)
        set_vector(level_node, "rb", RB)

    if dry_run:
        print(f"[dry-run] would convert client {SKILL_ID_TEXT} to {DRAGON_ACTION}: {path}")
        return
    backup(path, ".bak-2321010-dragon-breathe-attack", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"converted client {SKILL_ID_TEXT} to {DRAGON_ACTION}: {path}")


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


def set_or_insert_int(block: str, name: str, value: int) -> str:
    repl = f'<int name="{name}" value="{value}"/>'
    pattern = rf'<int name="{re.escape(name)}" value="-?\d+"\s*/>'
    if re.search(pattern, block):
        return re.sub(pattern, repl, block, count=1)
    for anchor in ("mad", "mastery", "mpCon"):
        anchor_pattern = rf'(<int name="{anchor}" value="-?\d+"\s*/>)'
        if re.search(anchor_pattern, block):
            return re.sub(anchor_pattern, rf"\1{repl}", block, count=1)
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1)


def set_or_insert_vector(block: str, name: str, xy: tuple[int, int]) -> str:
    repl = f'<vector name="{name}" x="{xy[0]}" y="{xy[1]}"/>'
    pattern = rf'<vector name="{re.escape(name)}" x="-?\d+" y="-?\d+"\s*/>'
    if re.search(pattern, block):
        return re.sub(pattern, repl, block, count=1)
    if name == "lt":
        return re.sub(r'(<imgdir name="\d+">)', rf"\1{repl}", block, count=1)
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1)


def int_value(block: str, name: str, default: int) -> int:
    match = re.search(rf'<int name="{re.escape(name)}" value="(-?\d+)"/>', block)
    return int(match.group(1)) if match else default


def patch_xml_level(level_block: str) -> str:
    mad = int_value(level_block, "mad", 100)
    level_block = set_or_insert_vector(level_block, "lt", LT)
    level_block = set_or_insert_int(level_block, "damage", mad)
    level_block = set_or_insert_int(level_block, "attackCount", ATTACK_COUNT)
    level_block = set_or_insert_int(level_block, "mobCount", MOB_COUNT)
    level_block = set_or_insert_vector(level_block, "rb", RB)
    return level_block


def patch_server_xml(path: Path, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, SKILL_ID_TEXT)
    block = text[start:end]

    try:
        action_start, action_end = find_imgdir_block(block, "action")
        action_block = f'<imgdir name="action"><string name="0" value="{ACTION}"/></imgdir>'
        block = block[:action_start] + action_block + block[action_end:]
    except RuntimeError:
        insert_at = block.find('<imgdir name="level">')
        if insert_at < 0:
            raise RuntimeError(f"missing XML level block for {SKILL_ID_TEXT}")
        block = block[:insert_at] + f'<imgdir name="action"><string name="0" value="{ACTION}"/></imgdir>' + block[insert_at:]

    for child_name in ("summon", "req"):
        try:
            child_start, child_end = find_imgdir_block(block, child_name)
            block = block[:child_start] + block[child_end:]
        except RuntimeError:
            pass

    for level in range(1, 31):
        level_start, level_end = find_imgdir_block(block, str(level))
        level_block = patch_xml_level(block[level_start:level_end])
        block = block[:level_start] + level_block + block[level_end:]
    if block == text[start:end]:
        print(f"server XML {SKILL_ID_TEXT} already converted")
        return
    if dry_run:
        print(f"[dry-run] would convert server XML {SKILL_ID_TEXT}: {path}")
        return
    backup(path, ".bak-2321010-dragon-breathe-attack", dry_run=False)
    atomic_write_text(path, text[:start] + block + text[end:])
    print(f"converted server XML {SKILL_ID_TEXT}: {path}")


def rel32(from_va: int, to_va: int) -> bytes:
    return struct.pack("<i", to_va - (from_va + 5))


def jmp(from_va: int, to_va: int) -> bytes:
    return b"\xE9" + rel32(from_va, to_va)


def je(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x84" + struct.pack("<i", to_va - (from_va + 6))


def jbe(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x86" + struct.pack("<i", to_va - (from_va + 6))


def jg(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x8F" + struct.pack("<i", to_va - (from_va + 6))


def cmp_eax(value: int) -> bytes:
    return b"\x3D" + struct.pack("<I", value)


def cmp_edx(value: int) -> bytes:
    return bytes.fromhex("81fa") + struct.pack("<I", value)


def sub_edx(value: int) -> bytes:
    return bytes.fromhex("81ea") + struct.pack("<I", value)


def build_summon_cave1() -> bytes:
    chunks = []
    va = HOOK1_CAVE_VA
    chunks.append(bytes.fromhex("8945e8"))
    va += 3
    chunks.append(bytes.fromhex("8b93b4000000"))
    va += 6
    chunks.append(cmp_edx(BAHAMUT_ID))
    va += 6
    chunks.append(je(va, HOOK1_EQUAL_VA))
    va += 6
    chunks.append(sub_edx(SUMMON_MIN))
    va += 6
    chunks.append(bytes.fromhex("83fa") + bytes([SUMMON_MAX - SUMMON_MIN]))
    va += 3
    chunks.append(jbe(va, HOOK1_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK1_NOT_EQUAL_VA))
    return b"".join(chunks)


def build_summon_cave2() -> bytes:
    chunks = []
    va = HOOK2_CAVE_VA
    chunks.append(bytes.fromhex("8bd0"))
    va += 2
    chunks.append(cmp_edx(BAHAMUT_ID))
    va += 6
    chunks.append(je(va, HOOK2_EQUAL_VA))
    va += 6
    chunks.append(sub_edx(SUMMON_MIN))
    va += 6
    chunks.append(bytes.fromhex("83fa") + bytes([SUMMON_MAX - SUMMON_MIN]))
    va += 3
    chunks.append(jbe(va, HOOK2_EQUAL_VA))
    va += 6
    chunks.append(jmp(va, HOOK2_RETURN_VA))
    return b"".join(chunks)


def build_summon_cave3() -> bytes:
    chunks = []
    va = HOOK3_CAVE_VA
    chunks.append(bytes.fromhex("8bd6"))
    va += 2
    chunks.append(sub_edx(SKILL_ID))
    va += 6
    chunks.append(je(va, HOOK3_ATTACK_VA))
    va += 6
    chunks.append(bytes.fromhex("4a"))
    va += 1
    chunks.append(bytes.fromhex("83fa") + bytes([SUMMON_MAX - SUMMON_MIN]))
    va += 3
    chunks.append(jbe(va, HOOK3_SUMMON_VA))
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


def build_aoe_cave() -> bytes:
    chunks = []
    va = AOE_NEW_CAVE_VA
    for skill_id in (2121006, 2201005, SKILL_ID):
        chunks.append(cmp_eax(skill_id))
        va += 5
        chunks.append(je(va, AOE_BRANCH_VA))
        va += 6
    chunks.append(jmp(va, AOE_RETURN_VA))
    return b"".join(chunks)


def patch_exe(path: Path, dry_run: bool) -> None:
    data = bytearray(path.read_bytes())
    hook1_patch = jmp(HOOK1_VA, HOOK1_CAVE_VA) + b"\x90" * (len(HOOK1_ORIGINAL) - 5)
    hook2_patch = jmp(HOOK2_VA, HOOK2_CAVE_VA) + b"\x90" * (len(HOOK2_ORIGINAL) - 5)
    hook3_patch = jmp(HOOK3_VA, HOOK3_CAVE_VA) + b"\x90" * (len(HOOK3_ORIGINAL) - 5)
    aoe_hook_patch = jmp(AOE_HOOK_VA, AOE_NEW_CAVE_VA) + b"\x90" * (len(AOE_ORIGINAL) - 5)
    old_aoe_hook_patch = jmp(AOE_HOOK_VA, AOE_OLD_CAVE_VA) + b"\x90" * (len(AOE_ORIGINAL) - 5)

    cave1 = build_summon_cave1()
    cave2 = build_summon_cave2()
    cave3 = build_summon_cave3()
    aoe_cave = build_aoe_cave()

    if len(cave1) > HOOK2_CAVE_OFFSET - HOOK1_CAVE_OFFSET:
        raise RuntimeError("hook1 cave overlaps hook2 cave")
    if len(cave2) > HOOK3_CAVE_OFFSET - HOOK2_CAVE_OFFSET:
        raise RuntimeError("hook2 cave overlaps hook3 cave")
    if any(data[AOE_NEW_CAVE_OFFSET + i] not in (0, aoe_cave[i]) for i in range(len(aoe_cave))):
        raise RuntimeError(f"new AoE code cave is not empty at VA 0x{AOE_NEW_CAVE_VA:x}")

    current_aoe_hook = bytes(data[AOE_HOOK_OFFSET:AOE_HOOK_OFFSET + len(AOE_ORIGINAL)])
    if current_aoe_hook not in (AOE_ORIGINAL, old_aoe_hook_patch, aoe_hook_patch):
        raise RuntimeError(f"unexpected AoE hook bytes: {current_aoe_hook.hex()}")
    for name, offset, original, patch in (
        ("hook1", HOOK1_OFFSET, HOOK1_ORIGINAL, hook1_patch),
        ("hook2", HOOK2_OFFSET, HOOK2_ORIGINAL, hook2_patch),
        ("hook3", HOOK3_OFFSET, HOOK3_ORIGINAL, hook3_patch),
    ):
        current = bytes(data[offset:offset + len(original)])
        if current not in (original, patch):
            raise RuntimeError(f"unexpected {name} bytes: {current.hex()}")

    if dry_run:
        print(f"[dry-run] would patch BeiDou.exe: {SKILL_ID_TEXT} attack, {SUMMON_MIN}-{SUMMON_MAX} summon")
        return
    backup(path, ".bak-2321010-dragon-breathe-attack", dry_run=False)
    data[HOOK1_OFFSET:HOOK1_OFFSET + len(hook1_patch)] = hook1_patch
    data[HOOK2_OFFSET:HOOK2_OFFSET + len(hook2_patch)] = hook2_patch
    data[HOOK3_OFFSET:HOOK3_OFFSET + len(hook3_patch)] = hook3_patch
    data[HOOK1_CAVE_OFFSET:HOOK1_CAVE_OFFSET + len(cave1)] = cave1
    data[HOOK2_CAVE_OFFSET:HOOK2_CAVE_OFFSET + len(cave2)] = cave2
    data[HOOK3_CAVE_OFFSET:HOOK3_CAVE_OFFSET + len(cave3)] = cave3
    data[AOE_HOOK_OFFSET:AOE_HOOK_OFFSET + len(aoe_hook_patch)] = aoe_hook_patch
    data[AOE_NEW_CAVE_OFFSET:AOE_NEW_CAVE_OFFSET + len(aoe_cave)] = aoe_cave
    atomic_write_bytes(path, bytes(data))
    print(f"patched BeiDou.exe for {SKILL_ID_TEXT} Dragon breath attack: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    server_values = read_server_level_values(SERVER_SKILL)
    patch_client_skill(CLIENT_SKILL, server_values, args.dry_run)
    patch_server_xml(SERVER_SKILL, args.dry_run)
    patch_exe(EXE, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
