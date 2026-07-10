#!/usr/bin/env python3
"""Add Hero skill 1121013 from 273 Canvas 1141002 resources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(PATCH_SKILL))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzIntProperty, WzStringProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from patch_1121001_sword_illusion import (  # noqa: E402
    clone_property,
    copy_visual_property,
    ensure_skill_icon_metadata,
    find_imgdir_block,
    property_to_xml,
    renumber_direct_animation_frames,
    set_int,
    set_string,
    set_vector,
)
from patch_1121012_test_skill import atomic_write_bytes, atomic_write_text, backup  # noqa: E402


SOURCE_SKILL_ID = "1141002"
SOURCE_REGION = "BMS"
SOURCE_SKILL = Path("/Users/lizixian/Documents/mxd/skill-273-export/img/_Canvas/114.img")

TARGET_SKILL_ID = "1121013"
TARGET_NAME = "狂怒连爆VI"
TARGET_DESC = "具象化古代战士的怒火，将前方的敌人化作焦土。"

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"

LEVELS = range(1, 31)
MASTER_LEVEL = 30
MP_CON = 201
DAMAGE = 196
DAMAGE_STEP = 5
SLASH_REPEAT = 4
MOB_COUNT = 10
ATTACK_COUNT = 8
COOLTIME = 10
PASSIVE_ULTIMATE_STRIKE_DAMAGE = 41
ACTION_NAMES = ("brandish1",)
INDEPENDENT_EFFECT_SLOTS = (
    ("90", "effect0"),
    ("91", "effect1"),
)
SKILL_EFFECT_DELAY = 100
VISUAL_SCALE = 0.70
EFFECT_VISIBLE_BOTTOM_DOWN_OFFSET = round(70 * VISUAL_SCALE)
LT = (round(-800 * VISUAL_SCALE), round(-350 * VISUAL_SCALE))
RB = (round(800 * VISUAL_SCALE), round(250 * VISUAL_SCALE))

VISUAL_CHILDREN = {
    "affected",
    "ball",
    "effect",
    "effect0",
    "effect1",
    "effect2",
    "effect3",
    "hit",
    "icon",
    "iconDisabled",
    "iconMouseOver",
    "keydown",
    "mob",
    "prepare",
    "screen",
    "screen0",
    "screen1",
    "screen2",
    "special",
    "summon",
    "tile",
}


def damage(level: int) -> int:
    return DAMAGE + (level - 1) * DAMAGE_STEP


def passive_damage(level: int) -> int:
    return PASSIVE_ULTIMATE_STRIKE_DAMAGE + (level - 1) * DAMAGE_STEP


def level_text(level: int) -> str:
    return (
        f"消耗{MP_CON}MP，发动{SLASH_REPEAT}次以{damage(level)}%的伤害攻击最多"
        f"{MOB_COUNT}个敌人{ATTACK_COUNT}次的斩击，冷却时间{COOLTIME}秒，"
        f"[被动效果：终极打击VI伤害增加{passive_damage(level)}%p]"
        "                    "
    )


def load_source_skill() -> WzSubProperty:
    image = WzImage.from_bytes(SOURCE_SKILL.read_bytes(), key=WzKey.for_region(SOURCE_REGION), name=SOURCE_SKILL.name)
    skill = image.parse().get(f"skill/{SOURCE_SKILL_ID}")
    if not isinstance(skill, WzSubProperty):
        raise RuntimeError(f"missing source skill/{SOURCE_SKILL_ID}: {SOURCE_SKILL}")
    return skill


def source_visual_children(source: WzSubProperty):
    return [child for child in source.children() if child.name in VISUAL_CHILDREN]


def make_action_node(parent: WzSubProperty) -> WzSubProperty:
    action = WzSubProperty("action", parent)
    for index, name in enumerate(ACTION_NAMES):
        action.add(WzStringProperty(str(index), name, action))
    return action


def make_level_node(parent: WzSubProperty) -> WzSubProperty:
    level_root = WzSubProperty("level", parent)
    for level in LEVELS:
        node = WzSubProperty(str(level), level_root)
        set_int(node, "attackCount", ATTACK_COUNT)
        set_int(node, "cooltime", COOLTIME)
        set_int(node, "damage", damage(level))
        set_string(node, "hs", f"h{level}")
        set_vector(node, "lt", LT)
        set_int(node, "mobCount", MOB_COUNT)
        set_int(node, "mpCon", MP_CON)
        set_vector(node, "rb", RB)
        set_int(node, "x", SLASH_REPEAT)
        set_int(node, "y", passive_damage(level))
        level_root.add(node)
    return level_root


def replace_child(parent: WzSubProperty, prop) -> None:
    prop.parent = parent
    parent._children[prop.name] = prop


def scale_xy(x: int, y: int, scale: float) -> tuple[int, int]:
    return round(int(x) * scale), round(int(y) * scale)


def scale_canvas_property(prop: WzCanvasProperty, region: str, target_key: WzKey | None, scale: float) -> int:
    image = decode_canvas(prop, region=region).convert("RGBA")
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    resampling = getattr(Image, "Resampling", Image)
    resample = getattr(resampling, "LANCZOS", Image.LANCZOS)
    image = image.resize((width, height), resample)

    prop.width = width
    prop.height = height
    prop.format = 2
    prop.format2 = 0
    prop._png_data = encode_canvas_payload(
        image,
        2,
        width,
        height,
        key=target_key or WzKey.for_region("GMS"),
        listwz=False,
    )
    prop._png_length = len(prop._png_data)

    changed = 1
    for child in prop.children():
        if isinstance(child, WzVectorProperty):
            expected = scale_xy(child.x, child.y, scale)
            if (int(child.x), int(child.y)) != expected:
                set_vector(prop, child.name, expected)
                changed += 1
    return changed


def scale_visual_canvases(prop, region: str, target_key: WzKey | None, scale: float = VISUAL_SCALE) -> int:
    if isinstance(prop, WzCanvasProperty):
        return scale_canvas_property(prop, region, target_key, scale)
    if isinstance(prop, WzSubProperty):
        changed = 0
        for child in prop.children():
            changed += scale_visual_canvases(child, region, target_key, scale)
        return changed
    return 0


def visible_bottom(prop: WzCanvasProperty, region: str) -> int:
    try:
        image = decode_canvas(prop, region=region).convert("RGBA")
        bbox = image.getchannel("A").getbbox()
    except Exception:
        bbox = None
    if bbox is None:
        return int(prop.height)
    return int(bbox[3])


def ensure_skill_effect_visible_bottom_origin(prop, region: str) -> int:
    changed = 0
    if isinstance(prop, WzCanvasProperty):
        expected_origin = (int(prop.width) // 2, visible_bottom(prop, region) - EFFECT_VISIBLE_BOTTOM_DOWN_OFFSET)
        origin = prop.child("origin")
        if origin is None or (int(origin.x), int(origin.y)) != expected_origin:
            set_vector(prop, "origin", expected_origin)
            changed += 1
        delay = prop.child("delay")
        if delay is None or int(delay.value) != SKILL_EFFECT_DELAY:
            set_int(prop, "delay", SKILL_EFFECT_DELAY)
            changed += 1
        return changed
    if isinstance(prop, WzSubProperty):
        for child in prop.children():
            changed += ensure_skill_effect_visible_bottom_origin(child, region)
    return changed


def ensure_skill_delay_without_origin(prop) -> int:
    changed = 0
    if isinstance(prop, WzCanvasProperty):
        if prop.child("origin") is not None:
            prop._children.pop("origin", None)
            changed += 1
        delay = prop.child("delay")
        if delay is None or int(delay.value) != SKILL_EFFECT_DELAY:
            set_int(prop, "delay", SKILL_EFFECT_DELAY)
            changed += 1
        return changed
    if isinstance(prop, WzSubProperty):
        for child in prop.children():
            changed += ensure_skill_delay_without_origin(child)
    return changed


def sorted_canvas_frames(prop: WzSubProperty) -> list[WzCanvasProperty]:
    frames = [child for child in prop.children() if isinstance(child, WzCanvasProperty) and child.name.isdigit()]
    return sorted(frames, key=lambda child: int(child.name))


def add_independent_effect_slots(skill: WzSubProperty) -> int:
    """Mirror extra top-level effects into effect/90..91 for independent playback."""

    effect = skill.child("effect")
    if not isinstance(effect, WzSubProperty):
        return 0

    total_frames = 0
    for slot_name, source_name in INDEPENDENT_EFFECT_SLOTS:
        source = skill.child(source_name)
        if not isinstance(source, WzSubProperty):
            continue
        frames = sorted_canvas_frames(source)
        if not frames:
            continue
        slot = WzSubProperty(slot_name, effect)
        for frame in frames:
            slot.add(clone_property(frame, frame.name, slot))
        replace_child(effect, slot)
        total_frames += len(frames)
    return total_frames


def make_skill_node(parent: WzSubProperty, target_key: WzKey | None) -> tuple[WzSubProperty, dict[str, int | str]]:
    source = load_source_skill()
    target = WzSubProperty(TARGET_SKILL_ID, parent)
    copied: list[str] = []
    metadata_patches = 0
    icon_metadata_patches = 0
    renumbered_frames = 0
    scaled_canvases = 0
    visual_region = "GMS" if target_key is not None else SOURCE_REGION

    for child in source_visual_children(source):
        copied_child = (
            copy_visual_property(child, child.name, target, target_key)
            if target_key is not None
            else clone_property(child, child.name, target)
        )
        if child.name in {"effect", "effect0", "effect1", "hit"}:
            scaled_canvases += scale_visual_canvases(copied_child, visual_region, target_key)
            renumbered_frames += renumber_direct_animation_frames(copied_child)
            if child.name == "hit":
                metadata_patches += ensure_skill_delay_without_origin(copied_child)
            else:
                metadata_patches += ensure_skill_effect_visible_bottom_origin(copied_child, visual_region)
        if child.name in {"icon", "iconMouseOver", "iconDisabled"}:
            icon_metadata_patches += ensure_skill_icon_metadata(copied_child)
        target.add(copied_child)
        copied.append(child.name)

    independent_effect_frames = add_independent_effect_slots(target)
    target.add(make_action_node(target))
    target.add(make_level_node(target))
    target.add(WzIntProperty("masterLevel", MASTER_LEVEL, target))

    return target, {
        "copied": ",".join(copied),
        "metadata": metadata_patches,
        "icon_metadata": icon_metadata_patches,
        "renumbered": renumbered_frames,
        "scaled_canvases": scaled_canvases,
        "independent_effect_frames": independent_effect_frames,
    }


def replace_xml_block(text: str, node_name: str, child_xml: str) -> str:
    start, end = find_imgdir_block(text, node_name)
    return text[:start] + child_xml + text[end:]


def patch_client_skill(path: Path, dry_run: bool, sync_existing: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    skill_root = root.get("skill")
    if not isinstance(skill_root, WzSubProperty):
        raise RuntimeError(f"missing skill root: {path}")
    if skill_root.child(TARGET_SKILL_ID) is not None and not sync_existing:
        raise RuntimeError(f"target client skill/{TARGET_SKILL_ID} already exists; not touching existing nodes")

    target, stats = make_skill_node(skill_root, image.wz_file.reader.key)
    replace_child(skill_root, target)
    if dry_run:
        print(
            f"[dry-run] would {'sync' if sync_existing else 'add'} client skill/{TARGET_SKILL_ID}: copied {stats['copied']}, "
            f"metadata {stats['metadata']}, icon metadata {stats['icon_metadata']}, "
            f"renumbered top-level effect frames {stats['renumbered']}, "
            f"scaled visual updates {stats['scaled_canvases']}, "
            f"independent effect slot frames {stats['independent_effect_frames']}"
        )
        return 1

    backup(path, ".bak-1121013-raging-blow-vi", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(
        f"{'synced' if sync_existing else 'added'} client skill/{TARGET_SKILL_ID}: copied {stats['copied']}, "
        f"metadata {stats['metadata']}, icon metadata {stats['icon_metadata']}, "
        f"renumbered top-level effect frames {stats['renumbered']}, "
        f"scaled visual updates {stats['scaled_canvases']}, "
        f"independent effect slot frames {stats['independent_effect_frames']}"
    )
    return 1


def make_string_node(parent: WzSubProperty) -> WzSubProperty:
    node = WzSubProperty(TARGET_SKILL_ID, parent)
    node.add(WzStringProperty("name", TARGET_NAME, node))
    node.add(WzStringProperty("desc", TARGET_DESC, node))
    for level in LEVELS:
        node.add(WzStringProperty(f"h{level}", level_text(level), node))
    return node


def patch_client_string(path: Path, dry_run: bool, sync_existing: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    if root.child(TARGET_SKILL_ID) is not None and not sync_existing:
        raise RuntimeError(f"target client string {TARGET_SKILL_ID} already exists; not touching existing nodes")
    replace_child(root, make_string_node(root))
    if dry_run:
        print(f"[dry-run] would {'sync' if sync_existing else 'add'} client string {TARGET_SKILL_ID}: {path}")
        return 1
    backup(path, ".bak-1121013-raging-blow-vi", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"{'synced' if sync_existing else 'added'} client string {TARGET_SKILL_ID}: {path}")
    return 1


def insert_xml_child(text: str, child_xml: str) -> str:
    insert_at = text.rfind("</imgdir>")
    if insert_at < 0:
        raise RuntimeError("missing XML root closing imgdir")
    return text[:insert_at] + child_xml + "\n" + text[insert_at:]


def insert_skill_xml_child(text: str, child_xml: str) -> str:
    skill_start, skill_end = find_imgdir_block(text, "skill")
    insert_at = text.rfind("</imgdir>", skill_start, skill_end)
    if insert_at < 0:
        raise RuntimeError("missing XML skill closing imgdir")
    return text[:insert_at] + child_xml + "\n" + text[insert_at:]


def patch_server_skill(path: Path, dry_run: bool, sync_existing: bool) -> int:
    text = path.read_text(encoding="utf-8")
    exists = True
    try:
        find_imgdir_block(text, TARGET_SKILL_ID)
    except RuntimeError:
        exists = False
    if exists and not sync_existing:
        raise RuntimeError(f"target server skill/{TARGET_SKILL_ID} already exists; not touching existing nodes")

    target, stats = make_skill_node(WzSubProperty("skill", None), None)
    skill_xml = property_to_xml(target, 2)
    new_text = replace_xml_block(text, TARGET_SKILL_ID, skill_xml) if exists else insert_skill_xml_child(text, skill_xml)
    if dry_run:
        print(
            f"[dry-run] would {'sync' if sync_existing else 'add'} server skill/{TARGET_SKILL_ID}: copied {stats['copied']}, "
            f"metadata {stats['metadata']}, icon metadata {stats['icon_metadata']}, "
            f"renumbered top-level effect frames {stats['renumbered']}, "
            f"scaled visual updates {stats['scaled_canvases']}, "
            f"independent effect slot frames {stats['independent_effect_frames']}"
        )
        return 1
    backup(path, ".bak-1121013-raging-blow-vi", dry_run=False)
    atomic_write_text(path, new_text)
    print(
        f"{'synced' if sync_existing else 'added'} server skill/{TARGET_SKILL_ID}: copied {stats['copied']}, "
        f"metadata {stats['metadata']}, icon metadata {stats['icon_metadata']}, "
        f"renumbered top-level effect frames {stats['renumbered']}, "
        f"scaled visual updates {stats['scaled_canvases']}, "
        f"independent effect slot frames {stats['independent_effect_frames']}"
    )
    return 1


def string_xml_block() -> str:
    lines = [f'  <imgdir name="{TARGET_SKILL_ID}">']
    lines.append(f'    <string name="name" value={quoteattr(TARGET_NAME)}/>')
    lines.append(f'    <string name="desc" value={quoteattr(TARGET_DESC)}/>')
    for level in LEVELS:
        lines.append(f'    <string name="h{level}" value={quoteattr(level_text(level))}/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_string(path: Path, dry_run: bool, sync_existing: bool) -> int:
    text = path.read_text(encoding="utf-8")
    exists = True
    try:
        find_imgdir_block(text, TARGET_SKILL_ID)
    except RuntimeError:
        exists = False
    if exists and not sync_existing:
        raise RuntimeError(f"target server string {TARGET_SKILL_ID} already exists; not touching existing nodes")
    new_text = replace_xml_block(text, TARGET_SKILL_ID, string_xml_block()) if exists else insert_xml_child(text, string_xml_block())
    if dry_run:
        print(f"[dry-run] would {'sync' if sync_existing else 'add'} server string {TARGET_SKILL_ID}: {path}")
        return 1
    backup(path, ".bak-1121013-raging-blow-vi", dry_run=False)
    atomic_write_text(path, new_text)
    print(f"{'synced' if sync_existing else 'added'} server string {TARGET_SKILL_ID}: {path}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync-existing", action="store_true", help="replace the generated 1121013 node in place")
    args = parser.parse_args()

    patch_client_skill(CLIENT_SKILL, args.dry_run, args.sync_existing)
    patch_client_string(CLIENT_STRING, args.dry_run, args.sync_existing)
    patch_server_skill(SERVER_SKILL, args.dry_run, args.sync_existing)
    patch_server_string(SERVER_STRING, args.dry_run, args.sync_existing)
    print(f"{TARGET_SKILL_ID}: {TARGET_NAME} added from {SOURCE_SKILL_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
