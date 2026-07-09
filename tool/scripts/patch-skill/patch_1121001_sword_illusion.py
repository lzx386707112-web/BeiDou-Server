#!/usr/bin/env python3
"""Patch Hero test skill 1121001 with Sword Illusion.

The official 5th-job skill is 400011124 (剑影分身). In this client, Hero's
test skill uses 1121001, already routed through Brandish-like attack logic.
The 273 export has the visual canvas tree for 400011124. The level values are
filled from the provided level-1 official text, scaling damage by +5 per level.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
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


SOURCE_SKILL_ID = "400011124"
TARGET_SKILL_ID = "1121001"
TARGET_NAME = "剑影分身"
TARGET_DESC = "爆发斗气之力，以肉眼不可见的速度向前方斩击无数次。剑影分身即使攻击反射状态的敌人也不会受到伤害。"
PROTECTED_TARGET_CHILDREN = {"action", "level", "masterLevel", "req"}
SYNCED_VISUAL_CHILDREN = {
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
    "summon",
    "tile",
}
LEVELS = range(1, 31)
MP_CON = 700
SLASH_COUNT = 12
BASE_SLASH_DAMAGE = 130
SLASH_ATTACK_COUNT = 4
MOB_COUNT = 8
EXPLOSION_COUNT = 5
BASE_EXPLOSION_DAMAGE = 260
EXPLOSION_ATTACK_COUNT = 5
DAMAGE_STEP = 5
COMBO_TIME = 8
COMBO_POINTS = 6
LT = (-40, -366)
RB = (700, 126)
DEFAULT_EFFECT_DELAY = 30
EFFECT0_START_DELAY = 1000
MERGED_EFFECT0_FORWARD_OFFSET = -40
MERGED_EFFECT0_UP_OFFSET = 120
BRANDISH_EFFECT_VARIANTS = ("0", "1")
EFFECT0_COMPAT_VARIANT = "2"
EFFECT0_COMPAT_ACTION = "brandish1"

SOURCE_SKILL = Path("/Users/lizixian/Documents/mxd/skill-273-export/img/_Canvas/40001.img")
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"


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


def replace_child(parent: WzSubProperty, prop) -> None:
    prop.parent = parent
    parent._children[prop.name] = prop


def remove_child(parent: WzSubProperty, name: str) -> None:
    parent._children.pop(name, None)


def set_int(parent: WzSubProperty, name: str, value: int) -> None:
    replace_child(parent, WzIntProperty(name, value, parent))


def set_string(parent: WzSubProperty, name: str, value: str) -> None:
    replace_child(parent, WzStringProperty(name, value, parent))


def set_vector(parent: WzSubProperty, name: str, xy: tuple[int, int]) -> None:
    replace_child(parent, WzVectorProperty(name, xy[0], xy[1], parent))


def slash_damage(level: int) -> int:
    return BASE_SLASH_DAMAGE + (level - 1) * DAMAGE_STEP


def explosion_damage(level: int) -> int:
    return BASE_EXPLOSION_DAMAGE + (level - 1) * DAMAGE_STEP


def level_text(level: int) -> str:
    return (
        f"MP消耗{MP_CON}，发动{SLASH_COUNT}次以{slash_damage(level)}%的伤害最多攻击{MOB_COUNT}名敌人"
        f"{SLASH_ATTACK_COUNT}次的斩击后，发动{EXPLOSION_COUNT}次以{explosion_damage(level)}%的伤害"
        f"攻击{EXPLOSION_ATTACK_COUNT}次的爆炸；斗气集中激活期间，在{COMBO_TIME}秒内，和增加"
        f"{COMBO_POINTS}个斗气点数的最终伤害相同数值的最终伤害增加，与斗气点数增加的最终伤害合计应用"
        "                    "
    )


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
        out.length_ms = int(prop.length_ms)
        out.header = bytes(prop.header)
        out._data_offset = prop._data_offset
        out._data_length = prop._data_length
        out._wz_image = prop._wz_image
        out._data = prop._data
        return out
    raise TypeError(f"unsupported WZ property: {type(prop).__name__}")


def copy_canvas_for_target(src: WzCanvasProperty, name: str, parent, target_key: WzKey) -> WzCanvasProperty:
    image = decode_canvas(src, region="BMS")
    out = WzCanvasProperty(name, parent)
    out.width = src.width
    out.height = src.height
    out.format = 2
    out.format2 = 0
    out._png_data = encode_canvas_payload(image, 2, src.width, src.height, key=target_key, listwz=False)
    out._png_length = len(out._png_data)
    for child in src.children():
        out.add(copy_visual_property(child, child.name, out, target_key))
    return out


def copy_visual_property(prop, name: str | None, parent, target_key: WzKey):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        return copy_canvas_for_target(prop, new_name, parent, target_key)
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(copy_visual_property(child, child.name, out, target_key))
        return out
    return clone_property(prop, new_name, parent)


def ensure_canvas_animation_metadata(prop) -> int:
    changed = 0
    if isinstance(prop, WzCanvasProperty):
        if prop.child("origin") is None:
            set_vector(prop, "origin", (int(prop.width) // 2, int(prop.height) // 2))
            changed += 1
        delay = prop.child("delay")
        if delay is None or int(delay.value) != DEFAULT_EFFECT_DELAY:
            set_int(prop, "delay", DEFAULT_EFFECT_DELAY)
            changed += 1
        return changed
    if isinstance(prop, WzSubProperty):
        for child in prop.children():
            changed += ensure_canvas_animation_metadata(child)
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


def renumber_direct_animation_frames(prop) -> int:
    if not isinstance(prop, WzSubProperty):
        return 0
    children = list(prop.children())
    if not children or any(not child.name.isdigit() for child in children):
        return 0
    ordered = sorted(children, key=lambda child: int(child.name))
    if [child.name for child in ordered] == [str(i) for i in range(len(ordered))]:
        return 0

    new_children = {}
    changed = 0
    for index, child in enumerate(ordered):
        new_name = str(index)
        if child.name != new_name:
            changed += 1
        clone = clone_property(child, new_name, prop)
        new_children[new_name] = clone
    prop._children = new_children
    return changed


def move_canvas_forward(prop, x_offset: int, y_offset: int) -> None:
    if not isinstance(prop, WzCanvasProperty):
        return
    origin = prop.child("origin")
    if origin is None:
        set_vector(prop, "origin", (-x_offset, int(prop.height) // 2 + y_offset))
        return
    set_vector(prop, "origin", (int(origin.x) - x_offset, int(origin.y) + y_offset))


def move_direct_animation_frames(prop, forward_offset: int = 0, up_offset: int = 0) -> int:
    if not isinstance(prop, WzSubProperty):
        return 0
    frames = list(prop.children())
    if (
        not frames
        or any(not child.name.isdigit() for child in frames)
        or not (forward_offset or up_offset)
    ):
        return 0

    moved = 0
    for frame in sorted(frames, key=lambda child: int(child.name)):
        move_canvas_forward(frame, forward_offset, up_offset)
        moved += 1
    return moved


def make_transparent_delay_canvas(name: str, parent, target_key: WzKey | None) -> WzCanvasProperty:
    out = WzCanvasProperty(name, parent)
    out.width = 1
    out.height = 1
    out.format = 2
    out.format2 = 0
    if target_key is not None:
        image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        out._png_data = encode_canvas_payload(image, 2, 1, 1, key=target_key, listwz=False)
        out._png_length = len(out._png_data)
    out.add(WzVectorProperty("origin", 0, 0, out))
    out.add(WzIntProperty("delay", EFFECT0_START_DELAY, out))
    return out


def prepend_effect0_start_delay(prop, target_key: WzKey | None = None) -> int:
    if not isinstance(prop, WzSubProperty):
        return 0
    frames = list(prop.children())
    if not frames or any(not isinstance(child, WzCanvasProperty) or not child.name.isdigit() for child in frames):
        return 0

    ordered = sorted(frames, key=lambda child: int(child.name))
    new_children = {"0": make_transparent_delay_canvas("0", prop, target_key)}
    for index, frame in enumerate(ordered, start=1):
        new_children[str(index)] = clone_property(frame, str(index), prop)
    prop._children = new_children
    return 1


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


def add_effect0_compat_variant(effect: WzSubProperty | None, effect0: WzSubProperty | None) -> int:
    if effect is None or effect0 is None:
        return 0
    if not isinstance(effect, WzSubProperty) or not isinstance(effect0, WzSubProperty):
        return 0
    variant = clone_property(effect0, EFFECT0_COMPAT_VARIANT, effect)
    replace_child(effect, variant)
    return len(list(variant.children()))


def ensure_effect0_compat_action(target: WzSubProperty) -> int:
    action = target.child("action")
    if not isinstance(action, WzSubProperty):
        action = WzSubProperty("action", target)
        replace_child(target, action)
    existing = action.child(EFFECT0_COMPAT_VARIANT)
    if isinstance(existing, WzStringProperty) and existing.value == EFFECT0_COMPAT_ACTION:
        return 0
    set_string(action, EFFECT0_COMPAT_VARIANT, EFFECT0_COMPAT_ACTION)
    return 1


def clone_visual_for_xml(prop):
    return clone_property(prop, prop.name, None)


def load_source_skill():
    image = WzImage.from_bytes(SOURCE_SKILL.read_bytes(), key=WzKey.for_region("BMS"), name=SOURCE_SKILL.name)
    source = image.parse().get(f"skill/{SOURCE_SKILL_ID}")
    if source is None:
        raise RuntimeError(f"missing source skill/{SOURCE_SKILL_ID}: {SOURCE_SKILL}")
    return source


def source_top_level_children(source: WzSubProperty):
    return [child for child in source.children() if child.name not in PROTECTED_TARGET_CHILDREN]


def remove_stale_visual_children(target: WzSubProperty, source_names: set[str]) -> list[str]:
    removed: list[str] = []
    for child in list(target.children()):
        if child.name in SYNCED_VISUAL_CHILDREN and child.name not in source_names:
            remove_child(target, child.name)
            removed.append(child.name)
    return removed


def patch_client_skill(path: Path, dry_run: bool) -> int:
    source = load_source_skill()
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target = root.get(f"skill/{TARGET_SKILL_ID}")
    if target is None:
        raise RuntimeError(f"missing client skill/{TARGET_SKILL_ID}: {path}")

    target_key = image.wz_file.reader.key
    source_children = source_top_level_children(source)
    source_names = {child.name for child in source_children}
    removed_children = remove_stale_visual_children(target, source_names)
    copied_children: list[str] = []
    renumbered_frames = 0
    moved_effect0_frames = 0
    for source_child in source_children:
        copied = copy_visual_property(source_child, source_child.name, target, target_key)
        if source_child.name == "effect":
            make_brandish_effect_variants(copied)
        if source_child.name == "effect0":
            renumbered_frames += renumber_direct_animation_frames(copied)
            moved_effect0_frames += move_direct_animation_frames(
                copied,
                MERGED_EFFECT0_FORWARD_OFFSET,
                MERGED_EFFECT0_UP_OFFSET,
            )
        replace_child(target, copied)
        copied_children.append(source_child.name)
    metadata_patches = 0
    icon_metadata_patches = 0
    for visual_name in ("effect", "effect0"):
        node = target.child(visual_name)
        if node is not None:
            metadata_patches += ensure_canvas_animation_metadata(node)
    for visual_name in ("icon", "iconMouseOver", "iconDisabled"):
        node = target.child(visual_name)
        icon_metadata_patches += ensure_skill_icon_metadata(node)
    delayed_effect0 = prepend_effect0_start_delay(target.child("effect0"), target_key)
    compat_frames = add_effect0_compat_variant(target.child("effect"), target.child("effect0"))
    compat_action = ensure_effect0_compat_action(target)

    level_root = target.get("level")
    if level_root is None:
        raise RuntimeError(f"missing client skill/{TARGET_SKILL_ID}/level: {path}")
    for level in LEVELS:
        level_node = level_root.get(str(level))
        if level_node is None:
            raise RuntimeError(f"missing client skill/{TARGET_SKILL_ID}/level/{level}: {path}")
        set_int(level_node, "attackCount", SLASH_ATTACK_COUNT)
        set_int(level_node, "damage", slash_damage(level))
        set_string(level_node, "hs", f"h{level}")
        set_vector(level_node, "lt", LT)
        set_int(level_node, "mobCount", MOB_COUNT)
        set_int(level_node, "mpCon", MP_CON)
        set_vector(level_node, "rb", RB)

    if dry_run:
        print(
            f"[dry-run] would copy source nodes {','.join(copied_children)} "
            f"remove stale nodes {','.join(removed_children) or '-'} "
            f"patch animation metadata {metadata_patches} "
            f"patch icon metadata {icon_metadata_patches} "
            f"renumber effect0 frames {renumbered_frames} "
            f"move effect0 frames {moved_effect0_frames} "
            f"prepend effect0 delay frames {delayed_effect0} "
            f"add effect/{EFFECT0_COMPAT_VARIANT} compat frames {compat_frames} "
            f"add action/{EFFECT0_COMPAT_VARIANT} compat {compat_action} "
            f"and update levels for client {TARGET_SKILL_ID}: {path}"
        )
        return 1

    backup(path, ".bak-1121001-sword-illusion", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(
        f"copied source nodes {','.join(copied_children)}, "
        f"removed stale nodes {','.join(removed_children) or '-'} "
        f"patched animation metadata {metadata_patches} "
        f"patched icon metadata {icon_metadata_patches} "
        f"renumbered effect0 frames {renumbered_frames} "
        f"moved effect0 frames {moved_effect0_frames} "
        f"prepended effect0 delay frames {delayed_effect0} "
        f"added effect/{EFFECT0_COMPAT_VARIANT} compat frames {compat_frames} "
        f"added action/{EFFECT0_COMPAT_VARIANT} compat {compat_action} "
        f"and updated levels for client {TARGET_SKILL_ID}: {path}"
    )
    return 1


def patch_client_string(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target = root.get(TARGET_SKILL_ID)
    if target is None:
        raise RuntimeError(f"missing client string {TARGET_SKILL_ID}: {path}")

    replacements = {"name": TARGET_NAME, "desc": TARGET_DESC}
    for level in LEVELS:
        replacements[f"h{level}"] = level_text(level)

    for name, value in replacements.items():
        node = target.child(name)
        if isinstance(node, WzStringProperty):
            node._value = value
        else:
            target.add(WzStringProperty(name, value, target))

    if dry_run:
        print(f"[dry-run] would update client string {TARGET_SKILL_ID}: {path}")
        return 1

    backup(path, ".bak-1121001-sword-illusion", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"updated client string {TARGET_SKILL_ID}: {path}")
    return 1


def xml_escape_attr(value: str) -> str:
    return quoteattr(value)


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name_attr = f"name={xml_escape_attr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name_attr}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name_attr} x="{prop.x}" y="{prop.y}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name_attr} width="{prop.width}" height="{prop.height}"'
        if int(prop.format) + int(prop.format2) != 0:
            attrs += f' format="{int(prop.format) + int(prop.format2)}"'
        children = list(prop.children())
        if not children:
            return f"{pad}<canvas {attrs}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in children)
        return f"{pad}<canvas {attrs}>\n{body}\n{pad}</canvas>"
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(f'{pad}  <vector name="{point.name}" x="{point.x}" y="{point.y}"/>' for point in prop.points)
        return f"{pad}<extended {name_attr}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name_attr} value={xml_escape_attr(str(prop.value))}/>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name_attr} length_ms="{int(prop.length_ms)}" bytes="{int(prop.value)}"/>'
    if isinstance(prop, WzSubProperty):
        if not prop.has_children():
            return f"{pad}<imgdir {name_attr}/>"
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<imgdir {name_attr}>\n{body}\n{pad}</imgdir>"
    value = getattr(prop, "value", "")
    if isinstance(prop, WzShortProperty):
        tag = "short"
    elif isinstance(prop, WzIntProperty):
        tag = "int"
    elif isinstance(prop, WzLongProperty):
        tag = "long"
    elif isinstance(prop, WzFloatProperty):
        tag = "float"
    elif isinstance(prop, WzDoubleProperty):
        tag = "double"
    elif isinstance(prop, WzStringProperty):
        tag = "string"
    else:
        tag = "string"
    return f"{pad}<{tag} {name_attr} value={xml_escape_attr(str(value))}/>"


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


def replace_or_append_child_xml(block: str, child_name: str, child_xml: str) -> str:
    token = f'<imgdir name="{child_name}"'
    start = block.find(token)
    if start >= 0:
        child_start, child_end = find_imgdir_block(block, child_name)
        return block[:child_start] + child_xml + block[child_end:]
    token = f'<canvas name="{child_name}"'
    start = block.find(token)
    if start >= 0:
        end = find_canvas_element_end(block, start)
        return block[:start] + child_xml + block[end:]
    insert_at = block.rfind("</imgdir>")
    if insert_at < 0:
        raise RuntimeError("missing target skill closing imgdir")
    return block[:insert_at] + child_xml + "\n" + block[insert_at:]


def ensure_effect0_compat_action_xml(block: str) -> tuple[str, int]:
    action_start, action_end = find_imgdir_block(block, "action")
    action_block = block[action_start:action_end]
    new_action_block = set_or_insert_string_xml(action_block, EFFECT0_COMPAT_VARIANT, EFFECT0_COMPAT_ACTION)
    return block[:action_start] + new_action_block + block[action_end:], int(new_action_block != action_block)


def find_canvas_element_end(block: str, start: int) -> int:
    open_end = block.find(">", start)
    if open_end < 0:
        raise RuntimeError("unterminated canvas XML")
    close = block.find("</canvas>", open_end)
    if block[open_end - 1] == "/":
        # Some earlier generated XML may have a self-closing canvas followed by
        # leftover child tags and a stale closing canvas. Replace that tail too.
        next_named_sibling = len(block)
        for token in ('<imgdir name="', '<canvas name="', '<int name="masterLevel"'):
            pos = block.find(token, open_end + 1)
            if pos >= 0:
                next_named_sibling = min(next_named_sibling, pos)
        if close >= 0 and close < next_named_sibling:
            return close + len("</canvas>")
        return open_end + 1
    if close < 0:
        raise RuntimeError(f"unterminated canvas XML {child_name}")
    return close + len("</canvas>")


def remove_child_xml(block: str, child_name: str) -> tuple[str, bool]:
    for tag in ("imgdir", "canvas"):
        token = f'<{tag} name="{child_name}"'
        start = block.find(token)
        if start < 0:
            continue
        if tag == "imgdir":
            child_start, child_end = find_imgdir_block(block, child_name)
            return block[:child_start] + block[child_end:], True
        child_end = find_canvas_element_end(block, start)
        return block[:start] + block[child_end:], True
    return block, False


def remove_stale_visual_children_xml(block: str, source_names: set[str]) -> tuple[str, list[str]]:
    removed: list[str] = []
    for child_name in sorted(SYNCED_VISUAL_CHILDREN - source_names):
        block, did_remove = remove_child_xml(block, child_name)
        if did_remove:
            removed.append(child_name)
    return block, removed


def set_or_insert_int_xml(block: str, name: str, value: int) -> str:
    repl = f'<int name="{name}" value="{value}"/>'
    pattern = rf'<int name="{re.escape(name)}" value="-?\d+"\s*/>'
    if re.search(pattern, block):
        return re.sub(pattern, repl, block, count=1)
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1)


def set_or_insert_string_xml(block: str, name: str, value: str) -> str:
    repl = f'<string name="{name}" value={xml_escape_attr(value)}/>'
    pattern = rf'<string name="{re.escape(name)}" value="[^"]*"\s*/>'
    if re.search(pattern, block):
        return re.sub(pattern, repl, block, count=1)
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1)


def set_or_insert_vector_xml(block: str, name: str, xy: tuple[int, int]) -> str:
    repl = f'<vector name="{name}" x="{xy[0]}" y="{xy[1]}"/>'
    pattern = rf'<vector name="{re.escape(name)}" x="-?\d+" y="-?\d+"\s*/>'
    if re.search(pattern, block):
        return re.sub(pattern, repl, block, count=1)
    if name == "lt":
        return re.sub(r'(<imgdir name="\d+">)', rf"\1{repl}", block, count=1)
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1)


def patch_level_xml(level_block: str, level: int) -> str:
    level_block = set_or_insert_int_xml(level_block, "attackCount", SLASH_ATTACK_COUNT)
    level_block = set_or_insert_int_xml(level_block, "damage", slash_damage(level))
    level_block = set_or_insert_string_xml(level_block, "hs", f"h{level}")
    level_block = set_or_insert_vector_xml(level_block, "lt", LT)
    level_block = set_or_insert_int_xml(level_block, "mobCount", MOB_COUNT)
    level_block = set_or_insert_int_xml(level_block, "mpCon", MP_CON)
    level_block = set_or_insert_vector_xml(level_block, "rb", RB)
    return level_block


def patch_level_root_xml(level_root: str) -> str:
    for level in LEVELS:
        level_start, level_end = find_imgdir_block(level_root, str(level))
        level_block = level_root[level_start:level_end]
        level_root = level_root[:level_start] + patch_level_xml(level_block, level) + level_root[level_end:]
    return level_root


def patch_server_skill(path: Path, dry_run: bool) -> int:
    source = load_source_skill()
    text = path.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, TARGET_SKILL_ID)
    block = text[start:end]

    source_children = source_top_level_children(source)
    source_names = {child.name for child in source_children}
    block, removed_children = remove_stale_visual_children_xml(block, source_names)

    copied_children: list[str] = []
    metadata_patches = 0
    icon_metadata_patches = 0
    renumbered_frames = 0
    moved_effect0_frames = 0
    delayed_effect0 = 0
    for source_child in source_children:
        xml_child = clone_visual_for_xml(source_child)
        if source_child.name == "effect":
            make_brandish_effect_variants(xml_child)
        if source_child.name == "effect0":
            renumbered_frames += renumber_direct_animation_frames(xml_child)
            moved_effect0_frames += move_direct_animation_frames(
                xml_child,
                MERGED_EFFECT0_FORWARD_OFFSET,
                MERGED_EFFECT0_UP_OFFSET,
            )
        if source_child.name in {"effect", "effect0"}:
            metadata_patches += ensure_canvas_animation_metadata(xml_child)
        if source_child.name in {"icon", "iconMouseOver", "iconDisabled"}:
            icon_metadata_patches += ensure_skill_icon_metadata(xml_child)
        if source_child.name == "effect0":
            delayed_effect0 += prepend_effect0_start_delay(xml_child)
        child_xml = property_to_xml(xml_child, 2)
        block = replace_or_append_child_xml(block, source_child.name, child_xml)
        copied_children.append(source_child.name)
    effect_node = None
    effect0_node = None
    for source_child in source_children:
        if source_child.name == "effect":
            effect_node = clone_visual_for_xml(source_child)
            make_brandish_effect_variants(effect_node)
        elif source_child.name == "effect0":
            effect0_node = clone_visual_for_xml(source_child)
            renumber_direct_animation_frames(effect0_node)
            move_direct_animation_frames(effect0_node, MERGED_EFFECT0_FORWARD_OFFSET, MERGED_EFFECT0_UP_OFFSET)
            ensure_canvas_animation_metadata(effect0_node)
            prepend_effect0_start_delay(effect0_node)
    compat_frames = add_effect0_compat_variant(effect_node, effect0_node)
    if effect_node is not None and compat_frames:
        block = replace_or_append_child_xml(block, "effect", property_to_xml(effect_node, 2))
    block, compat_action = ensure_effect0_compat_action_xml(block)

    level_start, level_end = find_imgdir_block(block, "level")
    level_root = block[level_start:level_end]
    block = block[:level_start] + patch_level_root_xml(level_root) + block[level_end:]

    new_text = text[:start] + block + text[end:]
    if dry_run:
        print(
            f"[dry-run] would copy source nodes {','.join(copied_children)}, "
            f"remove stale nodes {','.join(removed_children) or '-'} "
            f"patch animation metadata {metadata_patches} "
            f"patch icon metadata {icon_metadata_patches} "
            f"renumber effect0 frames {renumbered_frames} "
            f"move effect0 frames {moved_effect0_frames} "
            f"prepend effect0 delay frames {delayed_effect0} "
            f"add effect/{EFFECT0_COMPAT_VARIANT} compat frames {compat_frames} "
            f"add action/{EFFECT0_COMPAT_VARIANT} compat {compat_action} "
            f"to server skill XML {TARGET_SKILL_ID}: {path}"
        )
        return 1
    if new_text != text:
        backup(path, ".bak-1121001-sword-illusion", dry_run=False)
        atomic_write_text(path, new_text)
        print(
            f"copied source nodes {','.join(copied_children)}, "
            f"removed stale nodes {','.join(removed_children) or '-'} "
            f"patched animation metadata {metadata_patches} "
            f"patched icon metadata {icon_metadata_patches} "
            f"renumbered effect0 frames {renumbered_frames} "
            f"moved effect0 frames {moved_effect0_frames} "
            f"prepended effect0 delay frames {delayed_effect0} "
            f"added effect/{EFFECT0_COMPAT_VARIANT} compat frames {compat_frames} "
            f"added action/{EFFECT0_COMPAT_VARIANT} compat {compat_action} "
            f"to server skill XML {TARGET_SKILL_ID}: {path}"
        )
        return 1
    return 0


def patch_server_string(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    start, end = find_imgdir_block(text, TARGET_SKILL_ID)
    block = text[start:end]
    replacements = {
        "name": TARGET_NAME,
        "desc": TARGET_DESC,
    }
    for level in LEVELS:
        replacements[f"h{level}"] = level_text(level)
    for name, value in replacements.items():
        pattern = rf'<string name="{re.escape(name)}" value="[^"]*"\s*/>'
        repl = f'<string name="{name}" value={xml_escape_attr(value)}/>'
        if re.search(pattern, block):
            block = re.sub(pattern, repl, block, count=1)
        else:
            block = block.replace("</imgdir>", f"  {repl}\n</imgdir>", 1)
    new_text = text[:start] + block + text[end:]
    if dry_run:
        print(f"[dry-run] would update server string XML {TARGET_SKILL_ID}: {path}")
        return 1
    if new_text != text:
        backup(path, ".bak-1121001-sword-illusion", dry_run=False)
        atomic_write_text(path, new_text)
        print(f"updated server string XML {TARGET_SKILL_ID}: {path}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    patch_client_skill(CLIENT_SKILL, args.dry_run)
    patch_client_string(CLIENT_STRING, args.dry_run)
    patch_server_skill(SERVER_SKILL, args.dry_run)
    patch_server_string(SERVER_STRING, args.dry_run)
    print(f"{TARGET_SKILL_ID}: {TARGET_NAME} source nodes copied from {SOURCE_SKILL_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
