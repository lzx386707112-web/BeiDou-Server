#!/usr/bin/env python3
"""Convert Bishop Dragon attack clones 2321011-2321018 to manual attack skills."""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzFile, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzIntProperty, WzStringProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

import patch_bishop_dragon_skills as dragon_patch  # noqa: E402


SOURCE_TARGETS = [
    (2321011, "2214.img", 22141012, "2217.img", "dragonDive"),
    (2321012, "2217.img", 22171063, "2217.img", "dragonBreath"),
    (2321013, "2214.img", 22140014, "2218.img", "dragonSwiftThunder"),
    (2321014, "2217.img", 22170067, "2218.img", "dragonDiveEarth"),
    (2321015, "2217.img", 22170066, "2218.img", "dragonBreathWind"),
    (2321016, "2220.img", 22201003, "2220.img", "6thDragonSwift"),
    (2321017, "2220.img", 22201007, "2220.img", "6thDragonDive"),
    (2321018, "2220.img", 22201011, "2220.img", "6thDragonBreath"),
]
TARGET_SKILL_IDS = [skill_id for skill_id, *_ in SOURCE_TARGETS]

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "232.img"
CLIENT_SKILL_TAB = ROOT / "clien" / "Data" / "Skill" / "233.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_UI = ROOT / "clien" / "Data" / "UI" / "UIWindow.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "232.img.xml"
SERVER_SKILL_TAB = ROOT / "gms-server" / "wz" / "Skill.wz" / "233.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
V095_SKILL_WZ = Path("/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095客户端/Skill.wz")
V095_STRING_WZ = Path("/Users/lizixian/Documents/mxd/怀旧岛V095仿官版/怀旧岛V095客户端/String.wz")
MODERN_SKILL_DIR = Path("/Users/lizixian/Documents/mxd/273/sanjindao/Data/Skill/_Canvas")
MODERN_DRAGON_DIR = Path("/Users/lizixian/Documents/mxd/273/sanjindao/Data/Skill/Dragon/_Canvas")
MODERN_STRING = Path("/Users/lizixian/Documents/mxd/273/sanjindao/Data/String/Skill.img")
EXE = ROOT / "clien" / "BeiDou.exe"

ATTACK_COUNT = 2
MOB_COUNT = 6
LT = (-640, -365)
RB = (65, 220)
IMAGE_BASE = 0x400000
BAHAMUT_ID = 2321003
SUMMON_ID = 2321010
DISPLAY_SUMMON_ID = 2331010
ATTACK_MIN = min(TARGET_SKILL_IDS)
ATTACK_MAX = max(TARGET_SKILL_IDS)
DISPLAY_OFFSET = 10000
DISPLAY_SKILL_IDS = [SUMMON_ID + DISPLAY_OFFSET, *[skill_id + DISPLAY_OFFSET for skill_id in TARGET_SKILL_IDS]]
V095_VISUAL_CHILDREN = (
    "icon",
    "iconMouseOver",
    "iconDisabled",
    "elemAttr",
    "prepare",
    "effect",
    "hit",
    "ball",
    "mob",
    "action",
)
ACTION_BY_SKILL = {
    2321011: "paralyze",
    2321012: "paralyze",
    2321013: "paralyze",
    2321014: "paralyze",
    2321015: "paralyze",
    2321016: "paralyze",
    2321017: "paralyze",
    2321018: "paralyze",
}

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
HOOK2_CAVE_OFFSET = HOOK2_VA - IMAGE_BASE + (0xAEF650 - 0x7AD4F8)
HOOK2_EQUAL_VA = 0x7AD51B
HOOK2_RETURN_VA = 0x7AD4FF

HOOK3_VA = 0x967EE6
HOOK3_OFFSET = HOOK3_VA - IMAGE_BASE
HOOK3_ORIGINAL = bytes.fromhex("b84c512f003bf07f590f848e090000")
HOOK3_CAVE_VA = 0xAEF680
HOOK3_CAVE_OFFSET = HOOK3_CAVE_VA - IMAGE_BASE
HOOK3_SUMMON_VA = 0x9689DF
HOOK3_ATTACK_VA = 0x96928B
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

EVAN_STAGE_HOOK_VA = 0x4FEEC5
EVAN_STAGE_HOOK_OFFSET = EVAN_STAGE_HOOK_VA - IMAGE_BASE
EVAN_STAGE_ORIGINAL = bytes.fromhex("8b4424043d98080000750333c0c33da20800007c113daa0800007f0a996a0a59f7f98bc240c383c8ffc3")
EVAN_STAGE_CAVE_VA = 0xAEF740
EVAN_STAGE_CAVE_OFFSET = EVAN_STAGE_CAVE_VA - IMAGE_BASE

SKILL_JOB_HOOK_VA = 0x4F0751
SKILL_JOB_HOOK_OFFSET = SKILL_JOB_HOOK_VA - IMAGE_BASE
SKILL_JOB_ORIGINAL = bytes.fromhex("3de8000000751c")
SKILL_JOB_OLD_CAVE_VA = 0xAEF790
SKILL_JOB_CAVE_VA = 0xAEF9E0
SKILL_JOB_CAVE_OFFSET = SKILL_JOB_CAVE_VA - IMAGE_BASE
SKILL_JOB_BRANCH_VA = 0x4F0758
SKILL_JOB_RETURN_VA = 0x4F0774

HOOK1_RELOC_CAVE_VA = 0xAEF7C0
HOOK1_RELOC_CAVE_OFFSET = HOOK1_RELOC_CAVE_VA - IMAGE_BASE
HOOK3_RELOC_CAVE_VA = 0xAEF820
HOOK3_RELOC_CAVE_OFFSET = HOOK3_RELOC_CAVE_VA - IMAGE_BASE
AOE_RELOC_CAVE_VA = 0xAEF8A0
AOE_RELOC_CAVE_OFFSET = AOE_RELOC_CAVE_VA - IMAGE_BASE

BISHOP_ADD_HOOK_VA = 0xA0A3D6
BISHOP_ADD_HOOK_OFFSET = BISHOP_ADD_HOOK_VA - IMAGE_BASE
BISHOP_ADD_ORIGINAL = bytes.fromhex("3de80000000f85ba000000")
BISHOP_ADD_CAVE_VA = 0xAEF980
BISHOP_ADD_CAVE_OFFSET = BISHOP_ADD_CAVE_VA - IMAGE_BASE
BISHOP_ADD_CONTINUE_VA = 0xA0A3E1
BISHOP_ADD_REJECT_VA = 0xA0A49B

TAB_LOOP_CMP_VA = 0x4E6679
TAB_LOOP_CMP_OFFSET = TAB_LOOP_CMP_VA - IMAGE_BASE
TAB_LOOP_CMP_ORIGINAL = bytes.fromhex("83ff05")
TAB_LOOP_CMP_PATCH = bytes.fromhex("83ff06")

TAB_SLOT_CMP_VA = 0x4B071E
TAB_SLOT_CMP_OFFSET = TAB_SLOT_CMP_VA - IMAGE_BASE
TAB_SLOT_CMP_ORIGINAL = bytes.fromhex("83f805")
TAB_SLOT_CMP_PATCH = bytes.fromhex("83f806")

TAB6_SWITCH_HOOK_VA = 0x4EFDE8
TAB6_SWITCH_HOOK_OFFSET = TAB6_SWITCH_HOOK_VA - IMAGE_BASE
TAB6_SWITCH_ORIGINAL = bytes.fromhex("0f855effffff")
TAB6_SWITCH_CAVE_VA = 0xAEF9B0
TAB6_SWITCH_CAVE_OFFSET = TAB6_SWITCH_CAVE_VA - IMAGE_BASE
TAB6_SWITCH_FOURTH_VA = 0x4EFDEE
TAB6_SWITCH_FIFTH_VA = 0x4F0732
TAB6_SWITCH_REJECT_VA = 0x4EFD4C


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
    if not path.exists():
        return
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


def ensure_icon_anchor(skill: WzSubProperty) -> None:
    for child_name in ICON_CHILDREN:
        icon = skill.get(child_name)
        if icon is None:
            continue
        replace_child(icon, WzVectorProperty("origin", 0, 32, icon))
        replace_child(icon, WzIntProperty("z", 0, icon))


def set_action(skill: WzSubProperty, action_name: str) -> None:
    action = WzSubProperty("action", skill)
    action.add(WzStringProperty("0", action_name, action))
    replace_child(skill, action)


def copy_canvas_for_target(src: WzCanvasProperty, name: str, parent, target_key: WzKey, source_region: str) -> WzCanvasProperty:
    image = decode_canvas(src, region=source_region)
    out = WzCanvasProperty(name, parent)
    out.width = src.width
    out.height = src.height
    out.format = 2
    out.format2 = 0
    out._png_data = encode_canvas_payload(
        image,
        2,
        src.width,
        src.height,
        key=target_key,
        listwz=False,
    )
    out._png_length = len(out._png_data)
    for child in src.children():
        out.add(copy_visual_property(child, child.name, out, target_key, source_region))
    return out


def copy_visual_property(prop, name: str | None, parent, target_key: WzKey, source_region: str):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        return copy_canvas_for_target(prop, new_name, parent, target_key, source_region)
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(copy_visual_property(child, child.name, out, target_key, source_region))
        return out
    return dragon_patch.clone_property(prop, new_name, parent)


def replace_source_visuals(target_skill: WzSubProperty, source_skill: WzSubProperty, target_key: WzKey, source_region: str) -> None:
    remove_child(target_skill, "summon")
    remove_child(target_skill, "req")
    for child_name in V095_VISUAL_CHILDREN:
        source_child = source_skill.get(child_name)
        if source_child is not None:
            replace_child(target_skill, copy_visual_property(source_child, child_name, target_skill, target_key, source_region))
        elif child_name not in ("icon", "iconMouseOver", "iconDisabled"):
            remove_child(target_skill, child_name)
    ensure_icon_anchor(target_skill)


def replace_effect_from_dragon_action(target_skill: WzSubProperty, dragon_group: WzSubProperty, target_key: WzKey) -> None:
    effect = WzSubProperty("effect", target_skill)
    frame_no = 0
    for child in dragon_group.children():
        if not isinstance(child, WzCanvasProperty):
            continue
        effect.add(dragon_patch.make_canvas_from_source(
            child,
            str(frame_no),
            effect,
            target_key,
            origin_ratio=(0.711, 0.642),
            delay=90,
        ))
        frame_no += 1
    if frame_no == 0:
        raise RuntimeError(f"dragon action has no canvas frames: {dragon_group.name}")
    replace_child(target_skill, effect)
    remove_child(target_skill, "effect0")


def read_server_level_values(path: Path) -> dict[int, dict[int, dict[str, int]]]:
    text = path.read_text(encoding="utf-8")
    out: dict[int, dict[int, dict[str, int]]] = {}
    for skill_id in TARGET_SKILL_IDS:
        start, end = find_imgdir_block(text, str(skill_id))
        block = text[start:end]
        out[skill_id] = {}
        for level in range(1, 31):
            level_start, level_end = find_imgdir_block(block, str(level))
            level_block = block[level_start:level_end]
            values = {}
            for name in ("mpCon", "time", "mastery", "mad"):
                match = re.search(rf'<int name="{name}" value="(-?\d+)"/>', level_block)
                if match:
                    values[name] = int(match.group(1))
            out[skill_id][level] = values
    return out


def patch_client_skill(path: Path, server_values: dict[int, dict[int, dict[str, int]]], dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target_key = image.wz_file.reader.key
    v095_wz = WzFile.open(str(V095_SKILL_WZ), region="EMS", version=95)
    v095_cache = {}
    modern_cache = {}
    dragon_cache = {}

    def source_skill(img_name: str, source_skill_id: int) -> tuple[WzSubProperty, str, str]:
        if img_name not in v095_cache:
            source_image = v095_wz.root.get(img_name)
            v095_cache[img_name] = source_image.parse() if source_image is not None else None
        if v095_cache[img_name] is not None:
            source = v095_cache[img_name].get(f"skill/{source_skill_id}")
            if source is not None:
                return source, "EMS", "095"

        if img_name not in modern_cache:
            img_path = MODERN_SKILL_DIR / img_name
            if not img_path.exists():
                raise RuntimeError(f"missing modern skill image {img_path}")
            modern_image = WzImage.from_bytes(img_path.read_bytes(), key=WzKey.for_region("BMS"), name=img_name)
            modern_cache[img_name] = modern_image.parse()
        source = modern_cache[img_name].get(f"skill/{source_skill_id}")
        if source is None:
            raise RuntimeError(f"missing skill/{source_skill_id} in both 095 and modern {img_name}")
        return source, "BMS", "273"

    def dragon_action(img_name: str, action_name: str) -> WzSubProperty:
        if img_name not in dragon_cache:
            img_path = MODERN_DRAGON_DIR / img_name
            if not img_path.exists():
                raise RuntimeError(f"missing modern Dragon canvas image {img_path}")
            dragon_image = WzImage.from_bytes(img_path.read_bytes(), key=WzKey.for_region("BMS"), name=img_name)
            dragon_cache[img_name] = dragon_image.parse()
        group = dragon_cache[img_name].get(action_name)
        if group is None:
            raise RuntimeError(f"missing Dragon action {img_name}/{action_name}")
        return group

    for skill_id, img_name, source_skill_id, dragon_img, action_name in SOURCE_TARGETS:
        skill = root.get(f"skill/{skill_id}")
        if skill is None:
            raise RuntimeError(f"missing client skill/{skill_id}")
        source, source_region, _source_label = source_skill(img_name, source_skill_id)
        dragon_group = dragon_action(dragon_img, action_name)
        replace_source_visuals(skill, source, target_key, source_region)
        replace_effect_from_dragon_action(skill, dragon_group, target_key)
        set_action(skill, ACTION_BY_SKILL[skill_id])

        level_root = skill.get("level")
        if level_root is None:
            raise RuntimeError(f"missing client skill/{skill_id}/level")
        for level in range(1, 31):
            level_node = level_root.get(str(level))
            if level_node is None:
                raise RuntimeError(f"missing client skill/{skill_id}/level/{level}")
            values = server_values.get(skill_id, {}).get(level, {})
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

    v095_wz.close()

    if dry_run:
        print(f"[dry-run] would convert client manual Dragon attacks {ATTACK_MIN}-{ATTACK_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-manual-attacks", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"converted client manual Dragon attacks {ATTACK_MIN}-{ATTACK_MAX}: {path}")


def patch_client_display_skill(src_path: Path, dst_path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(src_path.read_bytes(), key=WzKey.for_region("GMS"), name=dst_path.name)
    root = image.parse()
    skill_root = root.get("skill")
    if skill_root is None:
        raise RuntimeError(f"missing client skill root: {src_path}")

    cloned = {}
    for source_id in [SUMMON_ID, *TARGET_SKILL_IDS]:
        source = skill_root.get(str(source_id))
        if source is None:
            raise RuntimeError(f"missing source display skill/{source_id}")
        cloned[str(source_id + DISPLAY_OFFSET)] = dragon_patch.clone_property(source, str(source_id + DISPLAY_OFFSET), skill_root)
    skill_root._children = cloned

    if dry_run:
        print(f"[dry-run] would create client fifth-tab Dragon skills {DISPLAY_SKILL_IDS[0]}-{DISPLAY_SKILL_IDS[-1]}: {dst_path}")
        return
    backup(dst_path, ".bak-bishop-dragon-fifth-tab", dry_run=False)
    atomic_write_bytes(dst_path, encode_image_body(image, image.wz_file.reader))
    print(f"created client fifth-tab Dragon skills {DISPLAY_SKILL_IDS[0]}-{DISPLAY_SKILL_IDS[-1]}: {dst_path}")


def patch_client_string(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    v095_wz = WzFile.open(str(V095_STRING_WZ), region="EMS", version=95)
    v095_root = v095_wz.root.get("Skill.img").parse()
    modern_root = WzImage.from_bytes(MODERN_STRING.read_bytes(), key=WzKey.for_region("BMS"), name=MODERN_STRING.name).parse()

    for skill_id, _img_name, source_skill_id, _dragon_img, _action_name in SOURCE_TARGETS:
        source = v095_root.get(str(source_skill_id))
        if source is None:
            source = modern_root.get(str(source_skill_id))
        if source is None:
            raise RuntimeError(f"missing String/Skill.img node {source_skill_id} in both 095 and modern")
        replace_child(root, dragon_patch.clone_property(source, str(skill_id), root))
        replace_child(root, dragon_patch.clone_property(source, str(skill_id + DISPLAY_OFFSET), root))

    summon_source = root.get(str(SUMMON_ID))
    if summon_source is not None:
        replace_child(root, dragon_patch.clone_property(summon_source, str(DISPLAY_SUMMON_ID), root))

    v095_wz.close()

    if dry_run:
        print(f"[dry-run] would sync client manual Dragon strings {ATTACK_MIN}-{ATTACK_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-manual-attacks", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"synced client manual Dragon strings {ATTACK_MIN}-{ATTACK_MAX}: {path}")


def make_tab_canvas(name: str, parent: WzSubProperty, target_key: WzKey, color: tuple[int, int, int, int]) -> WzCanvasProperty:
    img = Image.new("RGBA", (15, 12), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((4, -1), "V", fill=color)
    out = WzCanvasProperty(name, parent)
    out.width = img.width
    out.height = img.height
    out.format = 2
    out.format2 = 0
    out._png_data = encode_canvas_payload(img, 2, img.width, img.height, key=target_key, listwz=False)
    out._png_length = len(out._png_data)
    out.add(WzVectorProperty("origin", 0, 0, out))
    return out


def patch_client_skill_tab_ui(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target_key = image.wz_file.reader.key
    for state, color in (("enabled", (35, 35, 35, 255)), ("disabled", (110, 110, 110, 255))):
        parent = root.get(f"Skill/Tab/{state}")
        if parent is None:
            raise RuntimeError(f"missing UI Skill/Tab/{state}")
        replace_child(parent, make_tab_canvas("5", parent, target_key, color))

    if dry_run:
        print(f"[dry-run] would add Skill/Tab/5 V resource: {path}")
        return
    backup(path, ".bak-bishop-dragon-fifth-tab", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"added Skill/Tab/5 V resource: {path}")


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
    level_block = set_or_insert_int(level_block, "attackCount", ATTACK_COUNT)
    level_block = set_or_insert_int(level_block, "damage", mad)
    level_block = set_or_insert_int(level_block, "mobCount", MOB_COUNT)
    level_block = set_or_insert_vector(level_block, "rb", RB)
    return level_block


def remove_imgdir_child(block: str, child_name: str) -> str:
    try:
        child_start, child_end = find_imgdir_block(block, child_name)
        return block[:child_start] + block[child_end:]
    except RuntimeError:
        return block


def set_xml_action(block: str, action: str) -> str:
    action_block = f'<imgdir name="action"><string name="0" value="{action}"/></imgdir>'
    try:
        action_start, action_end = find_imgdir_block(block, "action")
        return block[:action_start] + action_block + block[action_end:]
    except RuntimeError:
        level_start = block.find('<imgdir name="level">')
        if level_start < 0:
            raise RuntimeError("missing level block")
        return block[:level_start] + action_block + block[level_start:]


def build_string_xml_block(skill_id: int, source: WzSubProperty) -> str:
    lines = [f'<imgdir name="{skill_id}">']
    for child in source.children():
        if isinstance(child, WzStringProperty):
            lines.append(f'<string name="{escape(child.name)}" value="{escape(str(child.value or ""))}"/>')
    lines.append("</imgdir>")
    return "".join(lines)


def patch_server_xml(path: Path, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    for skill_id in TARGET_SKILL_IDS:
        start, end = find_imgdir_block(text, str(skill_id))
        block = text[start:end]
        block = set_xml_action(block, ACTION_BY_SKILL[skill_id])
        block = remove_imgdir_child(block, "summon")
        block = remove_imgdir_child(block, "req")
        for level in range(1, 31):
            level_start, level_end = find_imgdir_block(block, str(level))
            block = block[:level_start] + patch_xml_level(block[level_start:level_end]) + block[level_end:]
        text = text[:start] + block + text[end:]

    if dry_run:
        print(f"[dry-run] would convert server XML manual Dragon attacks {ATTACK_MIN}-{ATTACK_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-manual-attacks", dry_run=False)
    atomic_write_text(path, text)
    print(f"converted server XML manual Dragon attacks {ATTACK_MIN}-{ATTACK_MAX}: {path}")


def patch_server_display_skill_xml(src_path: Path, dst_path: Path, dry_run: bool) -> None:
    text = src_path.read_text(encoding="utf-8")
    blocks = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><imgdir name="233.img"><imgdir name="skill">']
    for source_id in [SUMMON_ID, *TARGET_SKILL_IDS]:
        start, end = find_imgdir_block(text, str(source_id))
        block = text[start:end].replace(f'<imgdir name="{source_id}">', f'<imgdir name="{source_id + DISPLAY_OFFSET}">', 1)
        blocks.append(block)
    blocks.append("</imgdir></imgdir>")
    out = "".join(blocks)

    if dry_run:
        print(f"[dry-run] would create server fifth-tab Dragon XML {DISPLAY_SKILL_IDS[0]}-{DISPLAY_SKILL_IDS[-1]}: {dst_path}")
        return
    backup(dst_path, ".bak-bishop-dragon-fifth-tab", dry_run=False)
    atomic_write_text(dst_path, out)
    print(f"created server fifth-tab Dragon XML {DISPLAY_SKILL_IDS[0]}-{DISPLAY_SKILL_IDS[-1]}: {dst_path}")


def patch_server_string_xml(path: Path, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    v095_wz = WzFile.open(str(V095_STRING_WZ), region="EMS", version=95)
    v095_root = v095_wz.root.get("Skill.img").parse()
    modern_root = WzImage.from_bytes(MODERN_STRING.read_bytes(), key=WzKey.for_region("BMS"), name=MODERN_STRING.name).parse()

    for skill_id, _img_name, source_skill_id, _dragon_img, _action_name in SOURCE_TARGETS:
        source = v095_root.get(str(source_skill_id))
        if source is None:
            source = modern_root.get(str(source_skill_id))
        if source is None:
            raise RuntimeError(f"missing String/Skill.img node {source_skill_id} in both 095 and modern")
        try:
            start, end = find_imgdir_block(text, str(skill_id))
            text = text[:start] + build_string_xml_block(skill_id, source) + text[end:]
        except RuntimeError:
            insert_at = find_imgdir_block(text, str(SUMMON_ID))[1]
            text = text[:insert_at] + build_string_xml_block(skill_id, source) + text[insert_at:]
        try:
            start, end = find_imgdir_block(text, str(skill_id + DISPLAY_OFFSET))
            text = text[:start] + build_string_xml_block(skill_id + DISPLAY_OFFSET, source) + text[end:]
        except RuntimeError:
            insert_at = find_imgdir_block(text, str(skill_id))[1]
            text = text[:insert_at] + build_string_xml_block(skill_id + DISPLAY_OFFSET, source) + text[insert_at:]

    summon_source = None
    try:
        start, end = find_imgdir_block(text, str(SUMMON_ID))
        summon_source = text[start:end].replace(f'<imgdir name="{SUMMON_ID}">', f'<imgdir name="{DISPLAY_SUMMON_ID}">', 1)
    except RuntimeError:
        pass
    if summon_source is not None:
        try:
            start, end = find_imgdir_block(text, str(DISPLAY_SUMMON_ID))
            text = text[:start] + summon_source + text[end:]
        except RuntimeError:
            insert_at = find_imgdir_block(text, str(SUMMON_ID))[1]
            text = text[:insert_at] + summon_source + text[insert_at:]

    v095_wz.close()

    if dry_run:
        print(f"[dry-run] would sync server XML manual Dragon strings {ATTACK_MIN}-{ATTACK_MAX}: {path}")
        return
    backup(path, ".bak-bishop-dragon-manual-attacks", dry_run=False)
    atomic_write_text(path, text)
    print(f"synced server XML manual Dragon strings {ATTACK_MIN}-{ATTACK_MAX}: {path}")


def rel32(from_va: int, to_va: int) -> bytes:
    return struct.pack("<i", to_va - (from_va + 5))


def jmp(from_va: int, to_va: int) -> bytes:
    return b"\xE9" + rel32(from_va, to_va)


def je(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x84" + struct.pack("<i", to_va - (from_va + 6))


def jne(from_va: int, to_va: int) -> bytes:
    return b"\x0F\x85" + struct.pack("<i", to_va - (from_va + 6))


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
    va = HOOK1_RELOC_CAVE_VA
    chunks.append(bytes.fromhex("8945e8"))
    va += 3
    chunks.append(bytes.fromhex("8b93b4000000"))
    va += 6
    for skill_id in (BAHAMUT_ID, SUMMON_ID, DISPLAY_SUMMON_ID):
        chunks.append(cmp_edx(skill_id))
        va += 6
        chunks.append(je(va, HOOK1_EQUAL_VA))
        va += 6
    chunks.append(jmp(va, HOOK1_NOT_EQUAL_VA))
    return b"".join(chunks)


def build_summon_cave2() -> bytes:
    chunks = []
    va = HOOK2_CAVE_VA
    chunks.append(bytes.fromhex("8bd0"))
    va += 2
    for skill_id in (BAHAMUT_ID, SUMMON_ID, DISPLAY_SUMMON_ID):
        chunks.append(cmp_edx(skill_id))
        va += 6
        chunks.append(je(va, HOOK2_EQUAL_VA))
        va += 6
    chunks.append(jmp(va, HOOK2_RETURN_VA))
    return b"".join(chunks)


def build_release_cave3() -> bytes:
    chunks = []
    va = HOOK3_RELOC_CAVE_VA
    for summon_id in (SUMMON_ID, DISPLAY_SUMMON_ID):
        chunks.append(bytes.fromhex("8bd6"))
        va += 2
        chunks.append(sub_edx(summon_id))
        va += 6
        chunks.append(je(va, HOOK3_SUMMON_VA))
        va += 6
    for attack_min in (ATTACK_MIN, ATTACK_MIN + DISPLAY_OFFSET):
        chunks.append(bytes.fromhex("8bd6"))
        va += 2
        chunks.append(sub_edx(attack_min))
        va += 6
        chunks.append(bytes.fromhex("83fa") + bytes([ATTACK_MAX - ATTACK_MIN]))
        va += 3
        chunks.append(jbe(va, HOOK3_ATTACK_VA))
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
    va = AOE_RELOC_CAVE_VA
    for skill_id in (2121006, 2201005, *range(ATTACK_MIN, ATTACK_MAX + 1), *range(ATTACK_MIN + DISPLAY_OFFSET, ATTACK_MAX + DISPLAY_OFFSET + 1)):
        chunks.append(cmp_eax(skill_id))
        va += 5
        chunks.append(je(va, AOE_BRANCH_VA))
        va += 6
    chunks.append(jmp(va, AOE_RETURN_VA))
    return b"".join(chunks)


def build_evan_stage_cave() -> bytes:
    chunks = []
    va = EVAN_STAGE_CAVE_VA
    chunks.append(bytes.fromhex("8b442404"))
    va += 4
    chunks.append(cmp_eax(232))
    va += 5
    chunks.append(jne(va, va + 6 + 6))
    va += 6
    chunks.append(b"\xB8" + struct.pack("<I", 9))
    va += 5
    chunks.append(b"\xC3")
    va += 1
    chunks.append(cmp_eax(2200))
    va += 5
    chunks.append(bytes.fromhex("7503"))
    va += 2
    chunks.append(bytes.fromhex("33c0c3"))
    va += 3
    chunks.append(cmp_eax(2210))
    va += 5
    chunks.append(bytes.fromhex("7c11"))
    va += 2
    chunks.append(cmp_eax(2218))
    va += 5
    chunks.append(bytes.fromhex("7f0a"))
    va += 2
    chunks.append(bytes.fromhex("996a0a59f7f98bc240c383c8ffc3"))
    return b"".join(chunks)


def build_skill_job_cave() -> bytes:
    chunks = []
    va = SKILL_JOB_CAVE_VA
    chunks.append(bytes.fromhex("8b4de8"))  # original skill window object saved at [ebp-18h]
    va += 3
    chunks.append(cmp_eax(232))
    va += 5
    check_233_va = va + 6 + 4 + 6 + 5
    chunks.append(jne(va, check_233_va))
    va += 6
    chunks.append(bytes.fromhex("83791805"))  # selected tab 5: fourth job
    va += 4
    chunks.append(je(va, SKILL_JOB_BRANCH_VA))
    va += 6
    chunks.append(jmp(va, SKILL_JOB_RETURN_VA))
    va += 5
    chunks.append(cmp_eax(233))
    va += 5
    chunks.append(jne(va, SKILL_JOB_RETURN_VA))
    va += 6
    chunks.append(bytes.fromhex("83791806"))  # selected tab 6: V tab
    va += 4
    chunks.append(je(va, SKILL_JOB_BRANCH_VA))
    va += 6
    chunks.append(jmp(va, SKILL_JOB_RETURN_VA))
    return b"".join(chunks)


def build_tab6_switch_cave() -> bytes:
    chunks = []
    va = TAB6_SWITCH_CAVE_VA
    chunks.append(bytes.fromhex("85c0"))
    va += 2
    chunks.append(je(va, TAB6_SWITCH_FOURTH_VA))
    va += 6
    chunks.append(bytes.fromhex("83f801"))
    va += 3
    chunks.append(je(va, TAB6_SWITCH_FIFTH_VA))
    va += 6
    chunks.append(jmp(va, TAB6_SWITCH_REJECT_VA))
    return b"".join(chunks)


def build_bishop_add_cave() -> bytes:
    chunks = []
    va = BISHOP_ADD_CAVE_VA
    for job_id in (232, 233):
        chunks.append(cmp_eax(job_id))
        va += 5
        chunks.append(je(va, BISHOP_ADD_CONTINUE_VA))
        va += 6
    chunks.append(jmp(va, BISHOP_ADD_REJECT_VA))
    return b"".join(chunks)


def patch_exe(path: Path, dry_run: bool) -> None:
    data = bytearray(path.read_bytes())
    hook1_patch = jmp(HOOK1_VA, HOOK1_RELOC_CAVE_VA) + b"\x90" * (len(HOOK1_ORIGINAL) - 5)
    old_hook1_patch = jmp(HOOK1_VA, HOOK1_CAVE_VA) + b"\x90" * (len(HOOK1_ORIGINAL) - 5)
    hook2_patch = jmp(HOOK2_VA, HOOK2_CAVE_VA) + b"\x90" * (len(HOOK2_ORIGINAL) - 5)
    hook3_patch = jmp(HOOK3_VA, HOOK3_RELOC_CAVE_VA) + b"\x90" * (len(HOOK3_ORIGINAL) - 5)
    old_hook3_patch = jmp(HOOK3_VA, HOOK3_CAVE_VA) + b"\x90" * (len(HOOK3_ORIGINAL) - 5)
    aoe_hook_patch = jmp(AOE_HOOK_VA, AOE_RELOC_CAVE_VA) + b"\x90" * (len(AOE_ORIGINAL) - 5)
    mid_aoe_hook_patch = jmp(AOE_HOOK_VA, AOE_NEW_CAVE_VA) + b"\x90" * (len(AOE_ORIGINAL) - 5)
    old_aoe_hook_patch = jmp(AOE_HOOK_VA, AOE_OLD_CAVE_VA) + b"\x90" * (len(AOE_ORIGINAL) - 5)
    evan_stage_hook_patch = jmp(EVAN_STAGE_HOOK_VA, EVAN_STAGE_CAVE_VA) + b"\x90" * (len(EVAN_STAGE_ORIGINAL) - 5)
    skill_job_hook_patch = jmp(SKILL_JOB_HOOK_VA, SKILL_JOB_CAVE_VA) + b"\x90" * (len(SKILL_JOB_ORIGINAL) - 5)
    old_skill_job_hook_patch = jmp(SKILL_JOB_HOOK_VA, SKILL_JOB_OLD_CAVE_VA) + b"\x90" * (len(SKILL_JOB_ORIGINAL) - 5)
    bishop_add_hook_patch = jmp(BISHOP_ADD_HOOK_VA, BISHOP_ADD_CAVE_VA) + b"\x90" * (len(BISHOP_ADD_ORIGINAL) - 5)
    tab6_switch_hook_patch = jmp(TAB6_SWITCH_HOOK_VA, TAB6_SWITCH_CAVE_VA) + b"\x90"

    cave1 = build_summon_cave1()
    cave2 = build_summon_cave2()
    cave3 = build_release_cave3()
    aoe_cave = build_aoe_cave()
    evan_stage_cave = build_evan_stage_cave()
    skill_job_cave = build_skill_job_cave()
    tab6_switch_cave = build_tab6_switch_cave()
    bishop_add_cave = build_bishop_add_cave()

    if len(cave2) > HOOK3_CAVE_OFFSET - HOOK2_CAVE_OFFSET:
        raise RuntimeError("hook2 cave overlaps hook3 cave")
    if len(evan_stage_cave) > HOOK1_RELOC_CAVE_OFFSET - EVAN_STAGE_CAVE_OFFSET:
        raise RuntimeError("Evan stage cave overlaps relocated hook1 cave")
    if len(cave1) > HOOK3_RELOC_CAVE_OFFSET - HOOK1_RELOC_CAVE_OFFSET:
        raise RuntimeError("relocated hook1 cave overlaps relocated hook3 cave")
    if len(cave3) > AOE_RELOC_CAVE_OFFSET - HOOK3_RELOC_CAVE_OFFSET:
        raise RuntimeError("relocated hook3 cave overlaps relocated AoE cave")
    if len(aoe_cave) > BISHOP_ADD_CAVE_OFFSET - AOE_RELOC_CAVE_OFFSET:
        raise RuntimeError("relocated AoE cave overlaps Bishop add cave")
    if len(bishop_add_cave) > TAB6_SWITCH_CAVE_OFFSET - BISHOP_ADD_CAVE_OFFSET:
        raise RuntimeError("Bishop add cave overlaps tab6 switch cave")
    if len(tab6_switch_cave) > SKILL_JOB_CAVE_OFFSET - TAB6_SWITCH_CAVE_OFFSET:
        raise RuntimeError("tab6 switch cave overlaps skill job cave")

    for name, offset, original, patch in (
        ("hook1", HOOK1_OFFSET, HOOK1_ORIGINAL, hook1_patch),
        ("hook2", HOOK2_OFFSET, HOOK2_ORIGINAL, hook2_patch),
        ("hook3", HOOK3_OFFSET, HOOK3_ORIGINAL, hook3_patch),
    ):
        current = bytes(data[offset:offset + len(original)])
        old_patch = old_hook1_patch if name == "hook1" else old_hook3_patch if name == "hook3" else patch
        if current not in (original, patch, old_patch):
            raise RuntimeError(f"unexpected {name} bytes: {current.hex()}")

    current_aoe_hook = bytes(data[AOE_HOOK_OFFSET:AOE_HOOK_OFFSET + len(AOE_ORIGINAL)])
    if current_aoe_hook not in (AOE_ORIGINAL, old_aoe_hook_patch, mid_aoe_hook_patch, aoe_hook_patch):
        raise RuntimeError(f"unexpected AoE hook bytes: {current_aoe_hook.hex()}")

    current_evan_stage_hook = bytes(data[EVAN_STAGE_HOOK_OFFSET:EVAN_STAGE_HOOK_OFFSET + len(EVAN_STAGE_ORIGINAL)])
    if current_evan_stage_hook not in (EVAN_STAGE_ORIGINAL, evan_stage_hook_patch):
        raise RuntimeError(f"unexpected Evan stage hook bytes: {current_evan_stage_hook.hex()}")

    current_skill_job_hook = bytes(data[SKILL_JOB_HOOK_OFFSET:SKILL_JOB_HOOK_OFFSET + len(SKILL_JOB_ORIGINAL)])
    if current_skill_job_hook not in (SKILL_JOB_ORIGINAL, old_skill_job_hook_patch, skill_job_hook_patch):
        raise RuntimeError(f"unexpected skill job hook bytes: {current_skill_job_hook.hex()}")

    current_bishop_add_hook = bytes(data[BISHOP_ADD_HOOK_OFFSET:BISHOP_ADD_HOOK_OFFSET + len(BISHOP_ADD_ORIGINAL)])
    if current_bishop_add_hook not in (BISHOP_ADD_ORIGINAL, bishop_add_hook_patch):
        raise RuntimeError(f"unexpected Bishop add hook bytes: {current_bishop_add_hook.hex()}")

    current_tab_loop_cmp = bytes(data[TAB_LOOP_CMP_OFFSET:TAB_LOOP_CMP_OFFSET + len(TAB_LOOP_CMP_ORIGINAL)])
    if current_tab_loop_cmp not in (TAB_LOOP_CMP_ORIGINAL, TAB_LOOP_CMP_PATCH):
        raise RuntimeError(f"unexpected tab loop cmp bytes: {current_tab_loop_cmp.hex()}")

    current_tab_slot_cmp = bytes(data[TAB_SLOT_CMP_OFFSET:TAB_SLOT_CMP_OFFSET + len(TAB_SLOT_CMP_ORIGINAL)])
    if current_tab_slot_cmp not in (TAB_SLOT_CMP_ORIGINAL, TAB_SLOT_CMP_PATCH):
        raise RuntimeError(f"unexpected tab slot cmp bytes: {current_tab_slot_cmp.hex()}")

    current_tab6_switch = bytes(data[TAB6_SWITCH_HOOK_OFFSET:TAB6_SWITCH_HOOK_OFFSET + len(TAB6_SWITCH_ORIGINAL)])
    if current_tab6_switch not in (TAB6_SWITCH_ORIGINAL, tab6_switch_hook_patch):
        raise RuntimeError(f"unexpected tab6 switch bytes: {current_tab6_switch.hex()}")

    if dry_run:
        print(f"[dry-run] would patch BeiDou.exe: {SUMMON_ID} summon, {ATTACK_MIN}-{ATTACK_MAX} manual attacks")
        return
    backup(path, ".bak-bishop-dragon-manual-attacks", dry_run=False)
    data[HOOK1_OFFSET:HOOK1_OFFSET + len(hook1_patch)] = hook1_patch
    data[HOOK2_OFFSET:HOOK2_OFFSET + len(hook2_patch)] = hook2_patch
    data[HOOK3_OFFSET:HOOK3_OFFSET + len(hook3_patch)] = hook3_patch
    data[HOOK1_RELOC_CAVE_OFFSET:HOOK1_RELOC_CAVE_OFFSET + len(cave1)] = cave1
    data[HOOK2_CAVE_OFFSET:HOOK2_CAVE_OFFSET + len(cave2)] = cave2
    data[HOOK3_RELOC_CAVE_OFFSET:HOOK3_RELOC_CAVE_OFFSET + len(cave3)] = cave3
    data[AOE_HOOK_OFFSET:AOE_HOOK_OFFSET + len(aoe_hook_patch)] = aoe_hook_patch
    data[AOE_RELOC_CAVE_OFFSET:AOE_RELOC_CAVE_OFFSET + len(aoe_cave)] = aoe_cave
    data[EVAN_STAGE_HOOK_OFFSET:EVAN_STAGE_HOOK_OFFSET + len(evan_stage_hook_patch)] = evan_stage_hook_patch
    data[EVAN_STAGE_CAVE_OFFSET:EVAN_STAGE_CAVE_OFFSET + len(evan_stage_cave)] = evan_stage_cave
    data[SKILL_JOB_HOOK_OFFSET:SKILL_JOB_HOOK_OFFSET + len(skill_job_hook_patch)] = skill_job_hook_patch
    data[SKILL_JOB_CAVE_OFFSET:SKILL_JOB_CAVE_OFFSET + len(skill_job_cave)] = skill_job_cave
    data[BISHOP_ADD_HOOK_OFFSET:BISHOP_ADD_HOOK_OFFSET + len(bishop_add_hook_patch)] = bishop_add_hook_patch
    data[BISHOP_ADD_CAVE_OFFSET:BISHOP_ADD_CAVE_OFFSET + len(bishop_add_cave)] = bishop_add_cave
    data[TAB_LOOP_CMP_OFFSET:TAB_LOOP_CMP_OFFSET + len(TAB_LOOP_CMP_PATCH)] = TAB_LOOP_CMP_PATCH
    data[TAB_SLOT_CMP_OFFSET:TAB_SLOT_CMP_OFFSET + len(TAB_SLOT_CMP_PATCH)] = TAB_SLOT_CMP_PATCH
    data[TAB6_SWITCH_HOOK_OFFSET:TAB6_SWITCH_HOOK_OFFSET + len(tab6_switch_hook_patch)] = tab6_switch_hook_patch
    data[TAB6_SWITCH_CAVE_OFFSET:TAB6_SWITCH_CAVE_OFFSET + len(tab6_switch_cave)] = tab6_switch_cave
    atomic_write_bytes(path, bytes(data))
    print(f"patched BeiDou.exe: {SUMMON_ID} summon, {ATTACK_MIN}-{ATTACK_MAX} manual attacks")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    server_values = read_server_level_values(SERVER_SKILL)
    patch_client_skill(CLIENT_SKILL, server_values, args.dry_run)
    patch_client_display_skill(CLIENT_SKILL, CLIENT_SKILL_TAB, args.dry_run)
    patch_client_string(CLIENT_STRING, args.dry_run)
    patch_client_skill_tab_ui(CLIENT_UI, args.dry_run)
    patch_server_xml(SERVER_SKILL, args.dry_run)
    patch_server_display_skill_xml(SERVER_SKILL, SERVER_SKILL_TAB, args.dry_run)
    patch_server_string_xml(SERVER_STRING, args.dry_run)
    patch_exe(EXE, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
