#!/usr/bin/env python3
"""Patch Hero skill 1121012 with 400011027 Death Fault resources."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

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
    ensure_canvas_animation_metadata,
    find_imgdir_block,
    property_to_xml,
    renumber_direct_animation_frames,
    remove_child,
    remove_child_xml,
    replace_child,
    replace_or_append_child_xml,
    set_int,
    set_string,
    set_vector,
)
from patch_1121012_test_skill import atomic_write_bytes, atomic_write_text, backup  # noqa: E402


SOURCE_SKILL_ID = "400011027"
SOURCE_REGION = "BMS"
TARGET_SKILL_ID = "1121012"
TARGET_NAME = "斗气死亡断层"
TARGET_DESC = "用剑分割空间。"
FIELD_EFFECT_PATH = "customSkill/deathFault/full"

LEVELS = range(1, 31)
MP_CON = 500
DAMAGE = 416
ATTACK_COUNT = 14
MOB_COUNT = 15
COOLTIME = 5
LT = (-3000, -2000)
RB = (3000, 2000)
MASTER_LEVEL = 30
ACTION_NAMES = ("brandish1", "brandish2")
SCREEN_EFFECT_SLOT = "90"
DEFAULT_SCREEN_EFFECT_SIZE = (1024, 768)
SCREEN_SCALE_MODE = "cover"
SCREEN_LEADING_FRAME_UNIT_DELAY = 30
SCREEN_VISIBLE_FRAME_UNIT_DELAY = 90
FIELD_EFFECT_CANVAS_FORMAT = 2
FIELD_EFFECT_FRAME_STEP = 1
FIELD_EFFECT_SCREEN_SCALE_MODE = "cover"
BRANDISH_EFFECT_VARIANTS = ("0", "1")
EFFECT_VARIANT_X_OFFSETS = {
    "0": 200,
    "1": -160,
}

SOURCE_SKILL = Path("/Users/lizixian/Documents/mxd/skill-273-export/img/_Canvas/40001.img")
CLIENT_CONFIG = ROOT / "clien" / "config.ini"
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"

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


def load_source_skill() -> WzSubProperty:
    image = WzImage.from_bytes(SOURCE_SKILL.read_bytes(), key=WzKey.for_region(SOURCE_REGION), name=SOURCE_SKILL.name)
    skill = image.parse().get(f"skill/{SOURCE_SKILL_ID}")
    if not isinstance(skill, WzSubProperty):
        raise RuntimeError(f"missing source skill/{SOURCE_SKILL_ID}: {SOURCE_SKILL}")
    return skill


def source_visual_children(source: WzSubProperty):
    return [child for child in source.children() if child.name in VISUAL_CHILDREN]


def ensure_wz_sub_path(root: WzSubProperty, path: str) -> WzSubProperty:
    node = root
    for name in path.split("/"):
        child = node.child(name)
        if not isinstance(child, WzSubProperty):
            child = WzSubProperty(name, node)
            node.add(child)
        node = child
    return node


def property_signature(prop):
    if prop is None:
        return None
    if isinstance(prop, WzCanvasProperty):
        try:
            pixel_hash = hashlib.sha256(decode_canvas(prop, region="GMS").convert("RGBA").tobytes()).hexdigest()
        except Exception:
            pixel_hash = None
        return (
            type(prop).__name__,
            prop.name,
            prop.width,
            prop.height,
            prop.format,
            prop.format2,
            getattr(prop, "_png_length", 0) or len(getattr(prop, "_png_data", b"") or b""),
            pixel_hash,
            tuple(property_signature(child) for child in prop.children()),
        )
    if isinstance(prop, WzSubProperty):
        return (
            type(prop).__name__,
            prop.name,
            tuple(property_signature(child) for child in prop.children()),
        )
    return (
        type(prop).__name__,
        prop.name,
        getattr(prop, "value", None),
        getattr(prop, "x", None),
        getattr(prop, "y", None),
    )


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
        set_int(node, "damage", DAMAGE)
        set_string(node, "hs", f"h{level}")
        set_vector(node, "lt", LT)
        set_int(node, "mobCount", MOB_COUNT)
        set_int(node, "mpCon", MP_CON)
        set_vector(node, "rb", RB)
        level_root.add(node)
    return level_root


def read_client_resolution(path: Path) -> tuple[int, int]:
    width = height = None
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = re.match(r"\s*(width|height)\s*=\s*(\d+)\s*$", line, re.IGNORECASE)
            if not match:
                continue
            if match.group(1).lower() == "width":
                width = int(match.group(2))
            else:
                height = int(match.group(2))
    if width and height:
        return width, height
    return DEFAULT_SCREEN_EFFECT_SIZE


def paste_centered(base: Image.Image, image: Image.Image, x: int, y: int) -> None:
    dest_x0 = max(0, x)
    dest_y0 = max(0, y)
    dest_x1 = min(base.width, x + image.width)
    dest_y1 = min(base.height, y + image.height)
    if dest_x1 <= dest_x0 or dest_y1 <= dest_y0:
        return
    src_x0 = dest_x0 - x
    src_y0 = dest_y0 - y
    src_x1 = src_x0 + (dest_x1 - dest_x0)
    src_y1 = src_y0 + (dest_y1 - dest_y0)
    cropped = image.crop((src_x0, src_y0, src_x1, src_y1))
    base.alpha_composite(cropped, (dest_x0, dest_y0))


def screen_scale(frames: list[WzCanvasProperty], screen_size: tuple[int, int]) -> float:
    if SCREEN_SCALE_MODE == "none" or not frames:
        return 1.0
    max_width = max(frame.width for frame in frames)
    max_height = max(frame.height for frame in frames)
    if max_width <= 0 or max_height <= 0:
        return 1.0
    canvas_width, canvas_height = screen_size
    scale_width = canvas_width / max_width
    scale_height = canvas_height / max_height
    if SCREEN_SCALE_MODE == "fit":
        return min(scale_width, scale_height)
    return max(scale_width, scale_height)


def field_effect_scale_for_image(image: Image.Image, screen_size: tuple[int, int], scale_mode: str) -> float:
    if scale_mode == "none":
        return 1.0
    source_width = max(1, image.width)
    source_height = max(1, image.height)
    canvas_width, canvas_height = screen_size
    scale_width = canvas_width / source_width
    scale_height = canvas_height / source_height
    if scale_mode == "cover":
        return max(scale_width, scale_height)
    return min(scale_width, scale_height)


def make_transparent_screen_canvas(
    name: str,
    parent,
    target_key: WzKey | None,
    screen_size: tuple[int, int],
    delay: int,
) -> WzCanvasProperty:
    width, height = screen_size
    out = WzCanvasProperty(name, parent)
    out.width = width
    out.height = height
    out.format = FIELD_EFFECT_CANVAS_FORMAT
    out.format2 = 0
    if target_key is not None:
        image = Image.new("RGBA", screen_size, (0, 0, 0, 0))
        out._png_data = encode_canvas_payload(image, 2, width, height, key=target_key, listwz=False)
        out._png_length = len(out._png_data)
    set_vector(out, "origin", (width // 2, height // 2))
    set_int(out, "delay", delay)
    return out


def make_fullscreen_canvas(
    src: WzCanvasProperty,
    name: str,
    parent,
    target_key: WzKey | None,
    screen_size: tuple[int, int],
    scale: float,
    delay: int,
) -> WzCanvasProperty:
    width, height = screen_size
    out = WzCanvasProperty(name, parent)
    out.width = width
    out.height = height
    out.format = 2
    out.format2 = 0

    if target_key is not None:
        image = decode_canvas(src, region="GMS")
        image = image.convert("RGBA")
        if scale != 1.0:
            resampling = getattr(Image, "Resampling", Image)
            resample = getattr(resampling, "LANCZOS", Image.LANCZOS)
            image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), resample)
        composed = Image.new("RGBA", screen_size, (0, 0, 0, 0))
        x = (width - image.width) // 2
        y = (height - image.height) // 2
        paste_centered(composed, image, x, y)
        out._png_data = encode_canvas_payload(composed, 2, width, height, key=target_key, listwz=False)
        out._png_length = len(out._png_data)

    set_vector(out, "origin", (width // 2, height // 2))
    set_int(out, "delay", delay)
    return out


def screen_timeline(source_screen: WzSubProperty) -> tuple[int, list[int]]:
    frames = [frame for frame in sorted_numeric_children(source_screen) if isinstance(frame, WzCanvasProperty)]
    frame_indices = [int(frame.name) for frame in frames]
    if not frame_indices:
        return 0, []

    leading_delay = frame_indices[0] * SCREEN_LEADING_FRAME_UNIT_DELAY
    delays: list[int] = []
    for index, current_frame in enumerate(frame_indices):
        next_frame = frame_indices[index + 1] if index + 1 < len(frame_indices) else current_frame + 1
        frame_gap = max(1, next_frame - current_frame)
        delays.append(frame_gap * SCREEN_VISIBLE_FRAME_UNIT_DELAY)
    return leading_delay, delays


def make_fullscreen_screen_effect(
    screen: WzSubProperty,
    parent,
    target_key: WzKey | None,
    screen_size: tuple[int, int],
    timeline: tuple[int, list[int]],
) -> WzSubProperty:
    fullscreen = WzSubProperty(SCREEN_EFFECT_SLOT, parent)
    frames = [frame for frame in sorted_numeric_children(screen) if isinstance(frame, WzCanvasProperty)]
    scale = screen_scale(frames, screen_size)
    leading_delay, delays = timeline
    name_offset = 0
    if leading_delay > 0:
        fullscreen.add(make_transparent_screen_canvas("0", fullscreen, target_key, screen_size, leading_delay))
        name_offset = 1
    for frame in frames:
        index = int(frame.name)
        delay = delays[index] if index < len(delays) else SCREEN_VISIBLE_FRAME_UNIT_DELAY
        fullscreen.add(make_fullscreen_canvas(frame, str(index + name_offset), fullscreen, target_key, screen_size, scale, delay))
    return fullscreen


def mirror_screen_to_effect_slot(
    skill: WzSubProperty,
    target_key: WzKey | None,
    screen_size: tuple[int, int],
    timeline: tuple[int, list[int]],
) -> int:
    effect = skill.child("effect")
    screen = skill.child("screen")
    if not isinstance(effect, WzSubProperty) or not isinstance(screen, WzSubProperty):
        return 0
    replace_child(effect, make_fullscreen_screen_effect(screen, effect, target_key, screen_size, timeline))
    return 1


def make_field_effect_canvas(
    src: WzCanvasProperty | None,
    name: str,
    parent,
    target_key: WzKey,
    screen_size: tuple[int, int],
    scale_mode: str,
    crop_to_alpha: bool,
    delay: int,
) -> WzCanvasProperty:
    width, height = screen_size
    out = WzCanvasProperty(name, parent)
    out.width = width
    out.height = height
    out.format = 2
    out.format2 = 0

    composed = Image.new("RGBA", screen_size, (0, 0, 0, 0))
    if src is not None:
        image = decode_canvas(src, region=SOURCE_REGION).convert("RGBA")
        bbox = image.getchannel("A").getbbox() if crop_to_alpha else None
        if crop_to_alpha and bbox:
            image = image.crop(bbox)
        scale = field_effect_scale_for_image(image, screen_size, scale_mode)
        if scale != 1.0:
            resampling = getattr(Image, "Resampling", Image)
            resample = getattr(resampling, "LANCZOS", Image.LANCZOS)
            image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), resample)
        paste_centered(composed, image, (width - image.width) // 2, (height - image.height) // 2)
    out._png_data = encode_canvas_payload(composed, FIELD_EFFECT_CANVAS_FORMAT, width, height, key=target_key, listwz=False)
    out._png_length = len(out._png_data)

    origin_x = width // 2
    origin_y = height // 2
    set_vector(out, "origin", (origin_x, origin_y))
    set_vector(out, "head", (-1, -min(80, origin_y)))
    set_vector(out, "lt", (-origin_x, -origin_y))
    set_vector(out, "rb", (width - origin_x, height - origin_y))
    set_int(out, "delay", delay)
    return out


def make_death_fault_field_effect(parent, screen_size: tuple[int, int]) -> WzSubProperty:
    source = load_source_skill()
    source_screen = source.child("screen")
    if not isinstance(source_screen, WzSubProperty):
        raise RuntimeError(f"missing source skill/{SOURCE_SKILL_ID}/screen: {SOURCE_SKILL}")

    screen_frames = [frame for frame in sorted_numeric_children(source_screen) if isinstance(frame, WzCanvasProperty)]
    leading_delay, screen_delays = screen_timeline(source_screen)
    effect = WzSubProperty(parent.name, parent.parent)
    output_index = 0
    if leading_delay > 0:
        effect.add(
            make_field_effect_canvas(
                None,
                str(output_index),
                effect,
                WzKey.for_region("GMS"),
                screen_size,
                "none",
                False,
                leading_delay,
            )
        )
        output_index += 1
    for index in range(0, len(screen_frames), FIELD_EFFECT_FRAME_STEP):
        frame = screen_frames[index]
        next_index = min(index + FIELD_EFFECT_FRAME_STEP, len(screen_frames))
        delay = sum(screen_delays[index:next_index]) if index < len(screen_delays) else SCREEN_VISIBLE_FRAME_UNIT_DELAY
        effect.add(
            make_field_effect_canvas(
                frame,
                str(output_index),
                effect,
                WzKey.for_region("GMS"),
                screen_size,
                FIELD_EFFECT_SCREEN_SCALE_MODE,
                True,
                delay,
            )
        )
        output_index += 1
    return effect


def patch_client_map_effect(path: Path, dry_run: bool, screen_size: tuple[int, int]) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    parent_path, effect_name = FIELD_EFFECT_PATH.rsplit("/", 1)
    parent = ensure_wz_sub_path(root, parent_path)
    existing = parent.child(effect_name)
    new_effect = make_death_fault_field_effect(WzSubProperty(effect_name, parent), screen_size)
    if property_signature(existing) == property_signature(new_effect):
        return 0
    replace_child(parent, new_effect)
    if dry_run:
        print(f"[dry-run] would patch client map effect {FIELD_EFFECT_PATH}: {screen_size[0]}x{screen_size[1]}")
        return 1
    backup(path, ".bak-1121012-death-fault-field-effect", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"patched client map effect {FIELD_EFFECT_PATH}: {screen_size[0]}x{screen_size[1]}")
    return 1


def normalize_visual_frames(prop) -> int:
    changed = renumber_direct_animation_frames(prop)
    if isinstance(prop, WzSubProperty):
        for child in prop.children():
            changed += normalize_visual_frames(child)
    return changed


def ensure_skill_icon_metadata(prop) -> int:
    if not isinstance(prop, WzCanvasProperty):
        return 0
    changed = 0
    origin = prop.child("origin")
    if not isinstance(origin, WzVectorProperty) or (int(origin.x), int(origin.y)) != (0, int(prop.height)):
        set_vector(prop, "origin", (0, int(prop.height)))
        changed += 1
    z = prop.child("z")
    if not isinstance(z, WzIntProperty) or int(z.value) != 0:
        set_int(prop, "z", 0)
        changed += 1
    return changed


def ensure_death_fault_effect_metadata(prop) -> int:
    changed = 0
    if isinstance(prop, WzCanvasProperty):
        delay = prop.child("delay")
        if delay is None or int(delay.value) != 30:
            set_int(prop, "delay", 30)
            changed += 1
        return changed
    if isinstance(prop, WzSubProperty):
        for child in prop.children():
            changed += ensure_death_fault_effect_metadata(child)
    return changed


def make_brandish_effect_variants(prop: WzSubProperty) -> int:
    frames = list(prop.children())
    if not frames or any(not isinstance(child, WzCanvasProperty) for child in frames):
        return 0

    prop._children = {}
    for variant_name in BRANDISH_EFFECT_VARIANTS:
        variant = WzSubProperty(variant_name, prop)
        for frame in frames:
            variant.add(clone_property(frame, frame.name, variant))
        prop.add(variant)
    return len(frames) * len(BRANDISH_EFFECT_VARIANTS)


def apply_effect_variant_offsets(prop: WzSubProperty) -> int:
    changed = 0
    for variant_name, x_offset in EFFECT_VARIANT_X_OFFSETS.items():
        variant = prop.child(variant_name)
        if not isinstance(variant, WzSubProperty):
            continue
        for frame in variant.children():
            if not isinstance(frame, WzCanvasProperty):
                continue
            expected_origin = (int(frame.width) // 2 - x_offset, int(frame.height) // 2)
            origin = frame.child("origin")
            if not isinstance(origin, WzVectorProperty) or (int(origin.x), int(origin.y)) != expected_origin:
                set_vector(frame, "origin", expected_origin)
                changed += 1
    return changed


def sorted_numeric_children(prop: WzSubProperty):
    return sorted(
        [child for child in prop.children() if child.name.isdigit()],
        key=lambda child: int(child.name),
    )


def merge_animation_groups(first: WzSubProperty, second: WzSubProperty, name: str, parent: WzSubProperty) -> WzSubProperty:
    merged = WzSubProperty(name, parent)
    frame_index = 0
    for group in (first, second):
        for frame in sorted_numeric_children(group):
            merged.add(clone_property(frame, str(frame_index), merged))
            frame_index += 1
    return merged


def add_special_hit_compat(skill: WzSubProperty) -> int:
    hit = skill.child("hit")
    special = skill.child("special")
    if not isinstance(hit, WzSubProperty) or not isinstance(special, WzSubProperty):
        return 0
    base_hit = hit.child("0")
    if not isinstance(base_hit, WzSubProperty):
        return 0

    changed = 0
    base_hit_copy = clone_property(base_hit, "0", None)
    for special_group in sorted_numeric_children(special):
        if not isinstance(special_group, WzSubProperty):
            continue
        merged = merge_animation_groups(special_group, base_hit_copy, special_group.name, hit)
        replace_child(hit, merged)
        changed += 1
    return changed


def level_text() -> str:
    return (
        f"MP消耗{MP_CON}，以{DAMAGE}%的伤害最多攻击{MOB_COUNT}名敌人{ATTACK_COUNT}次，"
        f"冷却时间{COOLTIME}秒                    "
    )


def patch_client_skill(path: Path, dry_run: bool, screen_size: tuple[int, int]) -> int:
    source = load_source_skill()
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target = root.get(f"skill/{TARGET_SKILL_ID}")
    if not isinstance(target, WzSubProperty):
        raise RuntimeError(f"missing client skill/{TARGET_SKILL_ID}: {path}")

    source_children = source_visual_children(source)
    source_names = {child.name for child in source_children}
    source_screen = source.child("screen")
    screen_timing = screen_timeline(source_screen) if isinstance(source_screen, WzSubProperty) else (0, [])
    removed: list[str] = []
    for child in list(target.children()):
        if child.name in VISUAL_CHILDREN and child.name not in source_names:
            remove_child(target, child.name)
            removed.append(child.name)
    for stale in ("invisible", "req"):
        if target.child(stale) is not None:
            remove_child(target, stale)
            removed.append(stale)

    target_key = image.wz_file.reader.key
    copied: list[str] = []
    metadata_patches = 0
    icon_metadata_patches = 0
    renumbered_frames = 0
    for child in source_children:
        copied_child = copy_visual_property(child, child.name, target, target_key)
        if child.name == "effect":
            metadata_patches += ensure_death_fault_effect_metadata(copied_child)
            renumbered_frames += make_brandish_effect_variants(copied_child)
            metadata_patches += apply_effect_variant_offsets(copied_child)
        elif child.name in {"screen", "special", "hit"}:
            metadata_patches += ensure_canvas_animation_metadata(copied_child)
        if child.name in {"icon", "iconMouseOver", "iconDisabled"}:
            icon_metadata_patches += ensure_skill_icon_metadata(copied_child)
        if child.name in {"screen", "special", "hit"}:
            renumbered_frames += normalize_visual_frames(copied_child)
        replace_child(target, copied_child)
        copied.append(child.name)
    mirrored_screen = 0
    special_hit_compat = add_special_hit_compat(target)

    replace_child(target, make_action_node(target))
    replace_child(target, make_level_node(target))
    replace_child(target, WzIntProperty("masterLevel", MASTER_LEVEL, target))

    if dry_run:
        print(
            f"[dry-run] would patch client {TARGET_SKILL_ID}: "
            f"copy {','.join(copied)}, remove {','.join(removed) or '-'}, "
            f"metadata {metadata_patches}, icon metadata {icon_metadata_patches}, "
            f"renumber {renumbered_frames}, "
            f"effect-slot screen mirror {mirrored_screen}, special-hit compat {special_hit_compat}, "
            f"field canvas {screen_size[0]}x{screen_size[1]}, "
            f"screen timeline {screen_timing[0]}+{sum(screen_timing[1])}ms, levels {len(list(LEVELS))}"
        )
        return 1

    backup(path, ".bak-1121012-death-fault", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(
        f"patched client {TARGET_SKILL_ID}: copied {','.join(copied)}, "
        f"removed {','.join(removed) or '-'}, metadata {metadata_patches}, "
        f"icon metadata {icon_metadata_patches}, "
        f"renumbered {renumbered_frames}, effect-slot screen mirror {mirrored_screen}, "
        f"special-hit compat {special_hit_compat}, field canvas {screen_size[0]}x{screen_size[1]}, "
        f"screen timeline {screen_timing[0]}+{sum(screen_timing[1])}ms"
    )
    return 1


def patch_client_string(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target = root.get(TARGET_SKILL_ID)
    if not isinstance(target, WzSubProperty):
        raise RuntimeError(f"missing client string {TARGET_SKILL_ID}: {path}")

    replacements = {"name": TARGET_NAME, "desc": TARGET_DESC}
    for level in LEVELS:
        replacements[f"h{level}"] = level_text()
    for name, value in replacements.items():
        existing = target.child(name)
        if isinstance(existing, WzStringProperty):
            existing._value = value
        else:
            target.add(WzStringProperty(name, value, target))

    if dry_run:
        print(f"[dry-run] would patch client string {TARGET_SKILL_ID}: {path}")
        return 1

    backup(path, ".bak-1121012-death-fault", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"patched client string {TARGET_SKILL_ID}: {path}")
    return 1


def remove_target_xml_children(block: str, source_names: set[str]) -> tuple[str, list[str]]:
    removed: list[str] = []
    for name in sorted(VISUAL_CHILDREN - source_names):
        block, did_remove = remove_child_xml(block, name)
        if did_remove:
            removed.append(name)
    for stale in ("invisible", "req"):
        pattern = rf'<(?:int|imgdir) name="{re.escape(stale)}"[^>]*/?>'
        new_block, count = re.subn(pattern, "", block, count=1)
        if count:
            block = new_block
            removed.append(stale)
    return block, removed


def set_top_level_int_xml(block: str, name: str, value: int) -> str:
    block = re.sub(rf'<int name="{re.escape(name)}" value="-?\d+"\s*/>', "", block)
    insert_at = block.rfind("</imgdir>")
    if insert_at < 0:
        raise RuntimeError("missing skill closing imgdir")
    return block[:insert_at] + f'  <int name="{name}" value="{value}"/>\n' + block[insert_at:]


def patch_server_skill(path: Path, dry_run: bool, screen_size: tuple[int, int]) -> int:
    source = load_source_skill()
    text = path.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, TARGET_SKILL_ID)
    block = text[start:end]

    source_children = source_visual_children(source)
    source_names = {child.name for child in source_children}
    source_screen = source.child("screen")
    screen_timing = screen_timeline(source_screen) if isinstance(source_screen, WzSubProperty) else (0, [])
    block, removed = remove_target_xml_children(block, source_names)

    copied: list[str] = []
    metadata_patches = 0
    icon_metadata_patches = 0
    renumbered_frames = 0
    prepared_skill = WzSubProperty(TARGET_SKILL_ID, None)
    for child in source_children:
        xml_child = copy_visual_property(child, child.name, prepared_skill, WzKey.for_region("GMS"))
        if child.name == "effect":
            metadata_patches += ensure_death_fault_effect_metadata(xml_child)
            renumbered_frames += make_brandish_effect_variants(xml_child)
            metadata_patches += apply_effect_variant_offsets(xml_child)
        elif child.name in {"screen", "special", "hit"}:
            metadata_patches += ensure_canvas_animation_metadata(xml_child)
        if child.name in {"icon", "iconMouseOver", "iconDisabled"}:
            icon_metadata_patches += ensure_skill_icon_metadata(xml_child)
        if child.name in {"screen", "special", "hit"}:
            renumbered_frames += normalize_visual_frames(xml_child)
        prepared_skill.add(xml_child)
        copied.append(child.name)
    mirrored_screen = 0
    special_hit_compat = add_special_hit_compat(prepared_skill)
    for xml_child in prepared_skill.children():
        block = replace_or_append_child_xml(block, xml_child.name, property_to_xml(xml_child, 2))

    action_xml = property_to_xml(make_action_node(WzSubProperty(TARGET_SKILL_ID, None)), 2)
    level_xml = property_to_xml(make_level_node(WzSubProperty(TARGET_SKILL_ID, None)), 2)
    block = replace_or_append_child_xml(block, "action", action_xml)
    block = replace_or_append_child_xml(block, "level", level_xml)
    block = set_top_level_int_xml(block, "masterLevel", MASTER_LEVEL)

    new_text = text[:start] + block + text[end:]
    if dry_run:
        print(
            f"[dry-run] would patch server {TARGET_SKILL_ID}: "
            f"copy {','.join(copied)}, remove {','.join(removed) or '-'}, "
            f"metadata {metadata_patches}, icon metadata {icon_metadata_patches}, "
            f"renumber {renumbered_frames}, "
            f"effect-slot screen mirror {mirrored_screen}, special-hit compat {special_hit_compat}, "
            f"field canvas {screen_size[0]}x{screen_size[1]}, "
            f"screen timeline {screen_timing[0]}+{sum(screen_timing[1])}ms"
        )
        return 1
    if new_text != text:
        backup(path, ".bak-1121012-death-fault", dry_run=False)
        atomic_write_text(path, new_text)
        print(
            f"patched server {TARGET_SKILL_ID}: copied {','.join(copied)}, "
            f"removed {','.join(removed) or '-'}, metadata {metadata_patches}, "
            f"icon metadata {icon_metadata_patches}, "
            f"renumbered {renumbered_frames}, effect-slot screen mirror {mirrored_screen}, "
            f"special-hit compat {special_hit_compat}, field canvas {screen_size[0]}x{screen_size[1]}, "
            f"screen timeline {screen_timing[0]}+{sum(screen_timing[1])}ms"
        )
        return 1
    return 0


def set_or_insert_string_xml(block: str, name: str, value: str) -> str:
    from xml.sax.saxutils import quoteattr

    repl = f'<string name="{name}" value={quoteattr(value)}/>'
    pattern = rf'<string name="{re.escape(name)}" value="[^"]*"\s*/>'
    if re.search(pattern, block):
        return re.sub(pattern, repl, block, count=1)
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1)


def patch_server_string(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, TARGET_SKILL_ID)
    block = text[start:end]
    replacements = {"name": TARGET_NAME, "desc": TARGET_DESC}
    for level in LEVELS:
        replacements[f"h{level}"] = level_text()
    for name, value in replacements.items():
        block = set_or_insert_string_xml(block, name, value)
    new_text = text[:start] + block + text[end:]
    if dry_run:
        print(f"[dry-run] would patch server string {TARGET_SKILL_ID}: {path}")
        return 1
    if new_text != text:
        backup(path, ".bak-1121012-death-fault", dry_run=False)
        atomic_write_text(path, new_text)
        print(f"patched server string {TARGET_SKILL_ID}: {path}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--canvas-width", type=int, help="screen mirror canvas width; defaults to clien/config.ini width")
    parser.add_argument("--canvas-height", type=int, help="screen mirror canvas height; defaults to clien/config.ini height")
    args = parser.parse_args()

    config_width, config_height = read_client_resolution(CLIENT_CONFIG)
    screen_size = (args.canvas_width or config_width, args.canvas_height or config_height)
    if screen_size[0] <= 0 or screen_size[1] <= 0:
        parser.error("field canvas width and height must be positive")

    patch_client_skill(CLIENT_SKILL, args.dry_run, screen_size)
    patch_client_string(CLIENT_STRING, args.dry_run)
    patch_client_map_effect(CLIENT_MAP_EFFECT, args.dry_run, screen_size)
    patch_server_skill(SERVER_SKILL, args.dry_run, screen_size)
    patch_server_string(SERVER_STRING, args.dry_run)
    print(f"{TARGET_SKILL_ID}: {TARGET_NAME} patched from {SOURCE_SKILL_ID}; field canvas {screen_size[0]}x{screen_size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
