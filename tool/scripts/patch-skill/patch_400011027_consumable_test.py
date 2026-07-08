#!/usr/bin/env python3
"""Install a consumable-triggered Death Fault visual test.

The consumable still calls a server-side script token. For this test, skill
2321010 is used as a temporary client-recognized visual shell so attack packets
can reference a known skill id and exercise the source effect/special/hit nodes.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzIntProperty, WzStringProperty, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from patch_1121001_sword_illusion import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    backup,
    clone_property,
    find_imgdir_block,
    remove_child,
    replace_child,
    set_int,
    set_string,
    xml_escape_attr,
)


TEST_ITEM_ID = "2430125"
TEST_ITEM_NODE = "02430125"
TEST_ITEM_SCRIPT = "400011027"
FIELD_EFFECT_PATH = "customSkill/deathFault/screen"
DEFAULT_FIELD_EFFECT_CANVAS_WIDTH = 1280
DEFAULT_FIELD_EFFECT_CANVAS_HEIGHT = 700
SOURCE_FRAME_UNIT_DELAY = 30
SOURCE_273_REGION = "BMS"
TARGET_KEY = WzKey.for_region("GMS")

CLIENT_CONFIG = ROOT / "clien" / "config.ini"
CLIENT_ITEM = ROOT / "clien" / "Data" / "Item" / "Consume" / "0243.img"
CLIENT_CONSUME_STRING = ROOT / "clien" / "Data" / "String" / "Consume.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "232.img"
CLIENT_SKILL_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_ITEM = ROOT / "gms-server" / "wz" / "Item.wz" / "Consume" / "0243.img.xml"
SERVER_CONSUME_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Consume.img.xml"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "232.img.xml"
SERVER_SKILL_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
SOURCE_SKILL_CANVAS = Path("/Users/lizixian/Documents/mxd/skill-273-export/img/_Canvas/40001.img")
VISUAL_SKILL_ID = "2321010"
SOURCE_SKILL_ID = "400011027"

ITEM_NAME = "斗气死亡断层测试触发器"
ITEM_DESC = "放到键位上使用，触发斗气死亡断层全屏动画测试。"
SKILL_NAME = "斗气死亡断层"
SKILL_DESC = "用剑分割空间。"

field_effect_canvas_width = DEFAULT_FIELD_EFFECT_CANVAS_WIDTH
field_effect_canvas_height = DEFAULT_FIELD_EFFECT_CANVAS_HEIGHT


def read_client_resolution(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    width_match = re.search(r"(?m)^\s*width\s*=\s*(\d+)\s*$", text)
    height_match = re.search(r"(?m)^\s*height\s*=\s*(\d+)\s*$", text)
    if not width_match or not height_match:
        return None
    width = int(width_match.group(1))
    height = int(height_match.group(1))
    if width <= 0 or height <= 0:
        return None
    return width, height


def configure_field_effect_canvas(width: int, height: int) -> None:
    global field_effect_canvas_width, field_effect_canvas_height
    field_effect_canvas_width = width
    field_effect_canvas_height = height


def set_string_child(parent: WzSubProperty, name: str, value: str) -> None:
    child = parent.child(name)
    if isinstance(child, WzStringProperty):
        child._value = value
    else:
        replace_child(parent, WzStringProperty(name, value, parent))


def property_signature(prop):
    if prop is None:
        return None
    if isinstance(prop, WzCanvasProperty):
        return (type(prop).__name__, prop.name, prop.width, prop.height, tuple(property_signature(child) for child in prop.children()))
    if isinstance(prop, WzSubProperty):
        return (type(prop).__name__, prop.name, tuple(property_signature(child) for child in prop.children()))
    return (type(prop).__name__, prop.name, getattr(prop, "value", None), getattr(prop, "x", None), getattr(prop, "y", None))


def ensure_wz_sub_path(root: WzSubProperty, path: str) -> WzSubProperty:
    node = root
    for name in path.split("/"):
        child = node.child(name)
        if not isinstance(child, WzSubProperty):
            child = WzSubProperty(name, node)
            node.add(child)
        node = child
    return node


def copy_visual_property(prop, name: str | None, parent, target_key: WzKey):
    new_name = prop.name if name is None else name
    if isinstance(prop, WzCanvasProperty):
        image = decode_canvas(prop, region=SOURCE_273_REGION).convert("RGBA")
        width = int(prop.width or image.width or 1)
        height = int(prop.height or image.height or 1)
        out = WzCanvasProperty(new_name, parent)
        out.width = width
        out.height = height
        out.format = 2
        out.format2 = 0
        out._png_data = encode_canvas_payload(image, 2, width, height, key=target_key, listwz=False)
        out._png_length = len(out._png_data)
        for child in prop.children():
            out.add(clone_property(child, parent=out))
        if out.child("origin") is None:
            out.add(WzVectorProperty("origin", width // 2, height // 2, out))
        if out.child("delay") is None:
            out.add(WzIntProperty("delay", SOURCE_FRAME_UNIT_DELAY, out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(new_name, parent)
        for child in prop.children():
            out.add(copy_visual_property(child, child.name, out, target_key))
        return out
    return clone_property(prop, new_name, parent)


def copy_icon_property(source: WzSubProperty, child_name: str, target_name: str, parent: WzSubProperty):
    source_child = source.child(child_name)
    if source_child is None:
        return None
    out = copy_visual_property(source_child, target_name, parent, TARGET_KEY)
    if isinstance(out, WzCanvasProperty):
        remove_child(out, "delay")
    return out


def load_source_skill() -> WzSubProperty:
    if not SOURCE_SKILL_CANVAS.exists():
        raise RuntimeError(f"missing source canvas {SOURCE_SKILL_CANVAS}")
    image = WzImage.from_bytes(SOURCE_SKILL_CANVAS.read_bytes(), key=WzKey.for_region(SOURCE_273_REGION), name=SOURCE_SKILL_CANVAS.name)
    root = image.parse()
    source = root.get(f"skill/{SOURCE_SKILL_ID}")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError(f"{SOURCE_SKILL_CANVAS} missing skill/{SOURCE_SKILL_ID}")
    return source


def create_field_canvas(name: str, parent: WzSubProperty, image: Image.Image, delay: int) -> WzCanvasProperty:
    width = field_effect_canvas_width
    height = field_effect_canvas_height
    out = WzCanvasProperty(name, parent)
    out.width = width
    out.height = height
    out.format = 2
    out.format2 = 0
    out._png_data = encode_canvas_payload(image, 2, width, height, key=TARGET_KEY, listwz=False)
    out._png_length = len(out._png_data)
    origin_x = width // 2
    origin_y = height // 2
    out.add(WzVectorProperty("origin", origin_x, origin_y, out))
    out.add(WzVectorProperty("head", -1, -min(80, origin_y), out))
    out.add(WzVectorProperty("lt", -origin_x, -origin_y, out))
    out.add(WzVectorProperty("rb", width - origin_x, height - origin_y, out))
    out.add(WzIntProperty("delay", delay, out))
    return out


def transparent_field_canvas(name: str, parent: WzSubProperty, delay: int) -> WzCanvasProperty:
    image = Image.new("RGBA", (field_effect_canvas_width, field_effect_canvas_height), (0, 0, 0, 0))
    return create_field_canvas(name, parent, image, delay)


def clone_canvas_to_target(prop: WzCanvasProperty, name: str, parent: WzSubProperty, scale: float, delay: int) -> WzCanvasProperty:
    source_image = decode_canvas(prop, region=SOURCE_273_REGION).convert("RGBA")
    scaled_width = max(1, round(source_image.width * scale))
    scaled_height = max(1, round(source_image.height * scale))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    scaled_image = source_image.resize((scaled_width, scaled_height), resample)
    image = Image.new("RGBA", (field_effect_canvas_width, field_effect_canvas_height), (0, 0, 0, 0))
    paste_x = (field_effect_canvas_width - scaled_width) // 2
    paste_y = (field_effect_canvas_height - scaled_height) // 2
    image.paste(scaled_image, (paste_x, paste_y), scaled_image)
    return create_field_canvas(name, parent, image, delay)


def build_death_fault_field_effect(parent: WzSubProperty) -> WzSubProperty:
    screen = load_source_skill().child("screen")
    if not isinstance(screen, WzSubProperty):
        raise RuntimeError(f"{SOURCE_SKILL_CANVAS} missing skill/{SOURCE_SKILL_ID}/screen")
    effect = WzSubProperty(parent.name, parent.parent)
    frames = [child for child in screen.children() if isinstance(child, WzCanvasProperty)]
    frames.sort(key=lambda child: int(child.name) if child.name.isdigit() else 0)
    max_width = max(int(child.width or 1) for child in frames)
    max_height = max(int(child.height or 1) for child in frames)
    scale = min(field_effect_canvas_width / max_width, field_effect_canvas_height / max_height)
    frame_indices = [int(child.name) for child in frames]
    leading_delay = frame_indices[0] * SOURCE_FRAME_UNIT_DELAY
    name_offset = 0
    if leading_delay > 0:
        effect.add(transparent_field_canvas("0", effect, leading_delay))
        name_offset = 1
    for idx, child in enumerate(frames):
        current_frame = frame_indices[idx]
        next_frame = frame_indices[idx + 1] if idx + 1 < len(frame_indices) else current_frame + 1
        delay = max(SOURCE_FRAME_UNIT_DELAY, (next_frame - current_frame) * SOURCE_FRAME_UNIT_DELAY)
        effect.add(clone_canvas_to_target(child, str(name_offset + idx), effect, scale, delay))
    return effect


def patch_client_map_effect(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    root = image.parse()
    parent_path, effect_name = FIELD_EFFECT_PATH.rsplit("/", 1)
    parent = ensure_wz_sub_path(root, parent_path)
    existing = parent.child(effect_name)
    new_effect = build_death_fault_field_effect(WzSubProperty(effect_name, parent))
    if property_signature(existing) == property_signature(new_effect):
        return 0
    replace_child(parent, new_effect)
    if dry_run:
        print(f"[dry-run] would update client map effect {FIELD_EFFECT_PATH}: {path}")
        return 1
    backup(path, ".bak-death-fault-field-effect", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"updated client map effect {FIELD_EFFECT_PATH}: {path}")
    return 1


def patch_client_visual_skill(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    root = image.parse()
    skill_root = root.get("skill")
    target = root.get(f"skill/{VISUAL_SKILL_ID}")
    if not isinstance(skill_root, WzSubProperty) or not isinstance(target, WzSubProperty):
        raise RuntimeError(f"missing client visual skill {VISUAL_SKILL_ID}: {path}")

    source = load_source_skill()
    for child_name in ("effect", "special", "hit", "icon", "iconMouseOver", "iconDisabled"):
        source_child = source.child(child_name)
        if source_child is not None:
            replace_child(target, copy_visual_property(source_child, child_name, target, TARGET_KEY))

    level = WzSubProperty("level", target)
    level1 = WzSubProperty("1", level)
    level1.add(WzIntProperty("damage", 416, level1))
    level1.add(WzIntProperty("attackCount", 14, level1))
    level1.add(WzIntProperty("mobCount", 15, level1))
    level1.add(WzIntProperty("mpCon", 500, level1))
    level1.add(WzVectorProperty("lt", -3000, -2000, level1))
    level1.add(WzVectorProperty("rb", 3000, 2000, level1))
    level.add(level1)
    replace_child(target, level)
    replace_child(target, WzIntProperty("invisible", 1, target))

    if dry_run:
        print(f"[dry-run] would update client visual skill {VISUAL_SKILL_ID}: {path}")
        return 1
    backup(path, ".bak-death-fault-visual-skill", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"updated client visual skill {VISUAL_SKILL_ID}: {path}")
    return 1


def patch_client_skill_string(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    root = image.parse()
    target = root.child(VISUAL_SKILL_ID)
    if not isinstance(target, WzSubProperty):
        target = WzSubProperty(VISUAL_SKILL_ID, root)
        root.add(target)
    set_string_child(target, "name", SKILL_NAME)
    set_string_child(target, "desc", SKILL_DESC)
    set_string_child(
        target,
        "h1",
        "MP消耗500，以416%的伤害最多攻击15名敌人14次，施展动作中无敌\\n冷却时间5秒",
    )
    if dry_run:
        print(f"[dry-run] would update client skill string {VISUAL_SKILL_ID}: {path}")
        return 1
    backup(path, ".bak-death-fault-visual-skill", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"updated client skill string {VISUAL_SKILL_ID}: {path}")
    return 1


def patch_client_item(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    source = root.child("02430033") or root.child("02430681")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError("missing item template 02430033/02430681")

    target = clone_property(source, TEST_ITEM_NODE, root)
    remove_child(target, "spec")
    spec = WzSubProperty("spec", target)
    spec.add(WzIntProperty("hp", 0, spec))
    target.add(spec)

    info = target.child("info")
    if isinstance(info, WzSubProperty):
        set_int(info, "notSale", 1)
        set_int(info, "slotMax", 1)
        remove_child(info, "notConsume")
        source_skill = load_source_skill()
        icon = copy_icon_property(source_skill, "icon", "icon", info)
        icon_raw = copy_icon_property(source_skill, "icon", "iconRaw", info)
        if icon is not None:
            replace_child(info, icon)
        if icon_raw is not None:
            replace_child(info, icon_raw)

    replace_child(root, target)
    if dry_run:
        print(f"[dry-run] would update client item {TEST_ITEM_ID}: {path}")
        return 1
    backup(path, ".bak-death-fault-field-effect", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"updated client item {TEST_ITEM_ID}: {path}")
    return 1


def patch_client_string(path: Path, dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    target = root.child(TEST_ITEM_ID)
    if not isinstance(target, WzSubProperty):
        target = WzSubProperty(TEST_ITEM_ID, root)
        root.add(target)
    set_string_child(target, "name", ITEM_NAME)
    set_string_child(target, "desc", ITEM_DESC)

    if dry_run:
        print(f"[dry-run] would update client consume string {TEST_ITEM_ID}: {path}")
        return 1
    backup(path, ".bak-death-fault-field-effect", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"updated client consume string {TEST_ITEM_ID}: {path}")
    return 1


def item_xml_block() -> str:
    return f'''<imgdir name="{TEST_ITEM_NODE}">
  <imgdir name="info">
    <canvas name="icon" width="35" height="32">
      <vector name="origin" x="1" y="32"/>
      <string name="_outlink" value="Item/Consume/_Canvas/0243.img/02432343/info/icon"/>
    </canvas>
    <canvas name="iconRaw" width="35" height="31">
      <vector name="origin" x="1" y="32"/>
      <string name="_outlink" value="Item/Consume/_Canvas/0243.img/02432343/info/iconRaw"/>
    </canvas>
    <int name="notSale" value="1"/>
    <int name="price" value="1"/>
    <int name="slotMax" value="1"/>
  </imgdir>
  <imgdir name="spec">
    <int name="hp" value="0"/>
  </imgdir>
</imgdir>'''


def string_xml_block() -> str:
    return (
        f'  <imgdir name="{TEST_ITEM_ID}">\n'
        f'    <string name="desc" value={xml_escape_attr(ITEM_DESC)}/>\n'
        f'    <string name="name" value={xml_escape_attr(ITEM_NAME)}/>\n'
        f'  </imgdir>'
    )


def replace_or_append_imgdir(text: str, node_name: str, block: str) -> str:
    token = f'<imgdir name="{node_name}">'
    if token in text:
        start, end = find_imgdir_block(text, node_name)
        return text[:start] + block + text[end:]
    insert_at = text.rfind("</imgdir>")
    if insert_at < 0:
        raise RuntimeError("missing root closing imgdir")
    return text[:insert_at] + block + "\n" + text[insert_at:]


def patch_server_item(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    new_text = replace_or_append_imgdir(text, TEST_ITEM_NODE, item_xml_block())
    if dry_run:
        print(f"[dry-run] would update server item {TEST_ITEM_ID}: {path}")
        return 1
    if new_text != text:
        backup(path, ".bak-death-fault-field-effect", dry_run=False)
        atomic_write_text(path, new_text)
        print(f"updated server item {TEST_ITEM_ID}: {path}")
        return 1
    return 0


def patch_server_string(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    new_text = replace_or_append_imgdir(text, TEST_ITEM_ID, string_xml_block())
    if dry_run:
        print(f"[dry-run] would update server consume string {TEST_ITEM_ID}: {path}")
        return 1
    if new_text != text:
        backup(path, ".bak-death-fault-field-effect", dry_run=False)
        atomic_write_text(path, new_text)
        print(f"updated server consume string {TEST_ITEM_ID}: {path}")
        return 1
    return 0


def visual_skill_xml_block() -> str:
    return f'''<imgdir name="{VISUAL_SKILL_ID}">
  <imgdir name="level">
    <imgdir name="1">
      <string name="hs" value="h1"/>
      <int name="damage" value="416"/>
      <int name="attackCount" value="14"/>
      <int name="mobCount" value="15"/>
      <int name="mpCon" value="500"/>
      <int name="cooltime" value="5"/>
      <vector name="lt" x="-3000" y="-2000"/>
      <vector name="rb" x="3000" y="2000"/>
    </imgdir>
  </imgdir>
  <imgdir name="action">
    <string name="0" value="alert3"/>
  </imgdir>
  <int name="invisible" value="1"/>
</imgdir>'''


def skill_string_xml_block() -> str:
    return (
        f'  <imgdir name="{VISUAL_SKILL_ID}">\n'
        f'    <string name="desc" value={xml_escape_attr(SKILL_DESC)}/>\n'
        f'    <string name="h1" value={xml_escape_attr("MP消耗500，以416%的伤害最多攻击15名敌人14次，施展动作中无敌\\n冷却时间5秒")}/>\n'
        f'    <string name="name" value={xml_escape_attr(SKILL_NAME)}/>\n'
        f'  </imgdir>'
    )


def patch_server_visual_skill(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{VISUAL_SKILL_ID}">' not in text:
        raise RuntimeError(f"server visual shell {VISUAL_SKILL_ID} missing: {path}")
    new_text = replace_or_append_imgdir(text, VISUAL_SKILL_ID, visual_skill_xml_block())
    if dry_run:
        print(f"[dry-run] would update server visual skill {VISUAL_SKILL_ID}: {path}")
        return 1
    if new_text != text:
        backup(path, ".bak-death-fault-visual-skill", dry_run=False)
        atomic_write_text(path, new_text)
        print(f"updated server visual skill {VISUAL_SKILL_ID}: {path}")
        return 1
    return 0


def patch_server_skill_string(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    new_text = replace_or_append_imgdir(text, VISUAL_SKILL_ID, skill_string_xml_block())
    if dry_run:
        print(f"[dry-run] would update server skill string {VISUAL_SKILL_ID}: {path}")
        return 1
    if new_text != text:
        backup(path, ".bak-death-fault-visual-skill", dry_run=False)
        atomic_write_text(path, new_text)
        print(f"updated server skill string {VISUAL_SKILL_ID}: {path}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--canvas-width", type=int, help="field-effect canvas width; defaults to clien/config.ini width")
    parser.add_argument("--canvas-height", type=int, help="field-effect canvas height; defaults to clien/config.ini height")
    args = parser.parse_args()

    config_resolution = read_client_resolution(CLIENT_CONFIG)
    width = args.canvas_width or (config_resolution[0] if config_resolution else DEFAULT_FIELD_EFFECT_CANVAS_WIDTH)
    height = args.canvas_height or (config_resolution[1] if config_resolution else DEFAULT_FIELD_EFFECT_CANVAS_HEIGHT)
    configure_field_effect_canvas(width, height)
    print(f"field-effect canvas: {field_effect_canvas_width}x{field_effect_canvas_height}")

    patch_client_item(CLIENT_ITEM, args.dry_run)
    patch_client_string(CLIENT_CONSUME_STRING, args.dry_run)
    patch_client_map_effect(CLIENT_MAP_EFFECT, args.dry_run)
    patch_client_visual_skill(CLIENT_SKILL, args.dry_run)
    patch_client_skill_string(CLIENT_SKILL_STRING, args.dry_run)
    patch_server_item(SERVER_ITEM, args.dry_run)
    patch_server_string(SERVER_CONSUME_STRING, args.dry_run)
    patch_server_visual_skill(SERVER_SKILL, args.dry_run)
    patch_server_skill_string(SERVER_SKILL_STRING, args.dry_run)
    print(
        f"{TEST_ITEM_ID}: death-fault visual test prepared as a normal use item, visualSkill={VISUAL_SKILL_ID}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
