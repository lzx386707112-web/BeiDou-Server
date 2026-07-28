#!/usr/bin/env python3
"""Migrate TMS Dawn Warrior V/VI active attacks into the empty 1112 skill book.

Compatibility policy:
- remap source skills to 11121000..11121009;
- encode every client canvas as ARGB4444 (WZ format 1);
- fit oversized canvases inside 1280x720 and never exceed 2048x2048;
- reshape character effects into Brandish-compatible effect/0 and effect/1;
- move modern screen animations to Map/Effect field effects;
- keep server Skill.wz free of visual payloads (only action/level metadata).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import re
import shutil
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(PATCH_SKILL))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import _decompress, decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.writer import encode_image_body  # noqa: E402

from patch_1121001_sword_illusion import (  # noqa: E402
    clone_property,
    find_imgdir_block,
    set_int,
    set_string,
    set_vector,
)


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
SOURCE_1114 = TMS_ROOT / "Skill" / "_Canvas" / "1114.img"
SOURCE_40001 = TMS_ROOT / "Skill" / "_Canvas" / "40001.img"
SOURCE_STRING = TMS_ROOT / "String" / "Skill.img"

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"

CANVAS_FORMAT = 1
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
TEXTURE_LIMIT = 2048
DEFAULT_FRAME_DELAY = 30
MASTER_LEVEL = 30
FIELD_EFFECT_ROOT = "customSkill/dawnWarrior"


@dataclass(frozen=True)
class SkillSpec:
    target_id: int
    source_id: int
    source_group: str
    name: str
    description: str
    damage: int
    attack_count: int
    mob_count: int
    mp_con: int
    cooldown: int
    action: tuple[str, ...]
    hidden: bool = False
    hit_source_id: int | None = None
    field_effect: str | None = None


SKILLS = (
    SkillSpec(11121000, 11141100, "1114", "月光分裂VI", "和月亮一起斩击前方的敌人。", 620, 8, 15, 80, 0, ("brandish1", "brandish2")),
    SkillSpec(11121001, 11141200, "1114", "烈日狂斩VI", "借助太阳之力攻击前方的敌人。", 620, 8, 15, 80, 0, ("brandish1", "brandish2")),
    SkillSpec(11121002, 11141002, "1114", "宇宙轰炸VI", "召唤流星雨轰炸周围敌人。旧端兼容为一次完整攻击演出。", 700, 12, 15, 120, 12, ("sanctuary",)),
    SkillSpec(11121003, 11141004, "1114", "宇宙爆裂VI", "释放宇宙宝珠追击前方敌人。", 760, 10, 15, 100, 5, ("brandish1", "brandish2")),
    SkillSpec(11121004, 11141005, "1114", "双重狂斩VI", "突进并连续挥砍敌人。", 680, 10, 15, 70, 5, ("rush", "rush2")),
    SkillSpec(11121005, 11141500, "1114", "银河星爆", "斩开空间并引发远古爆炸。主视频暂以日月分裂场景帧兼容。", 900, 15, 15, 500, 180, ("genesis",), field_effect="galaxyStarBurst"),
    SkillSpec(11121006, 11141503, "1114", "全蚀之力", "与元素共鸣，释放灵魂之力斩杀敌人。两阶段在旧端合并演出。", 850, 15, 15, 400, 180, ("sanctuary",), hit_source_id=11141504),
    SkillSpec(11121007, 11141504, "1114", "全蚀之力：魂斩", "全蚀之力的内部第二阶段。", 900, 15, 15, 0, 0, ("brandish1", "brandish2"), hidden=True),
    SkillSpec(11121008, 400011088, "40001", "灵魂蚀日", "体现日月重叠的日蚀，并以日月分裂结束演出。", 820, 15, 15, 450, 120, ("genesis",), field_effect="soulEclipse"),
    SkillSpec(11121009, 400011089, "40001", "日月分裂", "灵魂蚀日的内部终结阶段。", 900, 15, 15, 0, 0, ("brandish1", "brandish2"), hidden=True, field_effect="sunMoonDivide"),
)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        temp = Path(tmp.name)
    temp.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        temp = Path(tmp.name)
    temp.replace(path)


def backup(path: Path) -> None:
    target = path.with_name(path.name + ".bak-dawn-warrior-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def replace_child(parent: WzSubProperty, prop) -> None:
    prop.parent = parent
    parent._children[prop.name] = prop


def ensure_path(root: WzSubProperty, path: str) -> WzSubProperty:
    node = root
    for name in path.split("/"):
        child = node.child(name)
        if not isinstance(child, WzSubProperty):
            child = WzSubProperty(name, node)
            replace_child(node, child)
        node = child
    return node


def load_sources() -> tuple[dict[str, WzSubProperty], WzSubProperty]:
    groups: dict[str, WzSubProperty] = {}
    for name, path in (("1114", SOURCE_1114), ("40001", SOURCE_40001)):
        image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("BMS"), name=path.name)
        groups[name] = image.parse()
    string_image = WzImage.from_bytes(SOURCE_STRING.read_bytes(), key=WzKey.for_region("BMS"), name=SOURCE_STRING.name)
    return groups, string_image.parse()


def numeric_canvases(node) -> list[WzCanvasProperty]:
    if not isinstance(node, WzSubProperty):
        return []
    frames = [child for child in node.children() if isinstance(child, WzCanvasProperty) and child.name.isdigit()]
    return sorted(frames, key=lambda frame: int(frame.name))


def frame_delay(canvas: WzCanvasProperty) -> int:
    delay = canvas.child("delay")
    return max(1, int(delay.value)) if isinstance(delay, WzIntProperty) else DEFAULT_FRAME_DELAY


def canvas_origin(canvas: WzCanvasProperty) -> tuple[int, int]:
    origin = canvas.child("origin")
    if isinstance(origin, WzVectorProperty):
        return int(origin.x), int(origin.y)
    return int(canvas.width) // 2, int(canvas.height) // 2


def fit_size(width: int, height: int) -> tuple[int, int, float]:
    limit_w = min(SCREEN_WIDTH, TEXTURE_LIMIT)
    limit_h = min(SCREEN_HEIGHT, TEXTURE_LIMIT)
    scale = min(1.0, limit_w / max(1, width), limit_h / max(1, height))
    return max(1, round(width * scale)), max(1, round(height * scale)), scale


def clean_rgba(image: Image.Image) -> Image.Image:
    return image.convert("RGBA")


def decode_source_canvas(canvas: WzCanvasProperty) -> Image.Image:
    fmt = int(canvas.format) + int(canvas.format2)
    if fmt != 4098:
        return decode_canvas(canvas, region="BMS")

    # Modern TMS uses BC7 for some Origin/hit frames. Pillow's DDS-DX10
    # decoder handles BC7 reliably once the decompressed WZ blocks receive a
    # standard container header. The result is immediately converted to the
    # old client's ARGB4444 format by encode_target_canvas().
    raw = _decompress(canvas, WzKey.for_region("BMS"))
    linear_size = ((int(canvas.width) + 3) // 4) * ((int(canvas.height) + 3) // 4) * 16
    if len(raw) < linear_size:
        raise RuntimeError(f"short BC7 payload: {len(raw)} < {linear_size}")
    header = struct.pack(
        "<I6I11I",
        124,
        0x00081007,
        int(canvas.height),
        int(canvas.width),
        linear_size,
        0,
        0,
        *([0] * 11),
    )
    pixel_format = struct.pack("<II4s5I", 32, 4, b"DX10", 0, 0, 0, 0, 0)
    caps = struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    dx10 = struct.pack("<5I", 98, 3, 0, 1, 0)  # DXGI_FORMAT_BC7_UNORM, TEXTURE2D
    dds = b"DDS " + header + pixel_format + caps + dx10 + raw[:linear_size]
    with Image.open(io.BytesIO(dds)) as decoded:
        return decoded.convert("RGBA")


def encode_target_canvas(
    src: WzCanvasProperty,
    name: str,
    parent,
    target_key: WzKey,
    force_screen: bool = False,
    delay_multiplier: int = 1,
) -> WzCanvasProperty:
    image = clean_rgba(decode_source_canvas(src))
    width, height, scale = fit_size(image.width, image.height)
    if (width, height) != image.size:
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    out = WzCanvasProperty(name, parent)
    out.width = width
    out.height = height
    out.format = CANVAS_FORMAT
    out.format2 = 0
    out._png_data = encode_canvas_payload(image, CANVAS_FORMAT, width, height, key=target_key, listwz=False, zlib_level=9)
    out._png_length = len(out._png_data)
    ox, oy = canvas_origin(src)
    if force_screen:
        ox, oy = width // 2, height // 2
    else:
        ox, oy = round(ox * scale), round(oy * scale)
    set_vector(out, "origin", (ox, oy))
    set_int(out, "delay", frame_delay(src) * delay_multiplier)
    z = src.child("z")
    if isinstance(z, WzIntProperty):
        set_int(out, "z", int(z.value))
    return out


def compose_frames(
    first: WzCanvasProperty,
    second: WzCanvasProperty,
    name: str,
    parent,
    target_key: WzKey,
) -> WzCanvasProperty:
    images = [clean_rgba(decode_source_canvas(first)), clean_rgba(decode_source_canvas(second))]
    origins = [canvas_origin(first), canvas_origin(second)]
    left = min(-origin[0] for origin in origins)
    top = min(-origin[1] for origin in origins)
    right = max(image.width - origin[0] for image, origin in zip(images, origins))
    bottom = max(image.height - origin[1] for image, origin in zip(images, origins))
    merged = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)), (0, 0, 0, 0))
    for image, origin in zip(images, origins):
        merged.alpha_composite(image, (-origin[0] - left, -origin[1] - top))
    width, height, scale = fit_size(merged.width, merged.height)
    if (width, height) != merged.size:
        merged = merged.resize((width, height), Image.Resampling.LANCZOS)
    out = WzCanvasProperty(name, parent)
    out.width = width
    out.height = height
    out.format = CANVAS_FORMAT
    out.format2 = 0
    out._png_data = encode_canvas_payload(merged, CANVAS_FORMAT, width, height, key=target_key, listwz=False, zlib_level=9)
    out._png_length = len(out._png_data)
    set_vector(out, "origin", (round(-left * scale), round(-top * scale)))
    set_int(out, "delay", max(frame_delay(first), frame_delay(second)))
    return out


def merge_tracks(
    primary: list[WzCanvasProperty],
    secondary: list[WzCanvasProperty],
    parent: WzSubProperty,
    target_key: WzKey,
) -> None:
    total = max(len(primary), len(secondary))
    for index in range(total):
        first = primary[min(index, len(primary) - 1)] if primary else None
        second = secondary[min(index, len(secondary) - 1)] if secondary else None
        if first is not None and second is not None:
            frame = compose_frames(first, second, str(index), parent, target_key)
        else:
            frame = encode_target_canvas(first or second, str(index), parent, target_key)
        parent.add(frame)


def effect_variants(source: WzSubProperty, target: WzSubProperty, target_key: WzKey) -> WzSubProperty:
    effect = source.child("effect")
    effect0 = source.child("effect0")
    primary_variants: list[list[WzCanvasProperty]] = []
    if isinstance(effect, WzSubProperty):
        direct = numeric_canvases(effect)
        if direct:
            primary_variants = [direct]
        else:
            for child in sorted(effect.children(), key=lambda item: int(item.name) if item.name.isdigit() else 9999):
                frames = numeric_canvases(child)
                if frames:
                    primary_variants.append(frames)

    if not primary_variants:
        screen = source.child("screen")
        if isinstance(screen, WzSubProperty) and numeric_canvases(screen):
            primary_variants = [numeric_canvases(screen)[:12]]
        else:
            hit = source.child("hit")
            base_hit = hit.child("0") if isinstance(hit, WzSubProperty) else None
            if isinstance(base_hit, WzSubProperty):
                primary_variants = [numeric_canvases(base_hit)]

    secondary = numeric_canvases(effect0) if isinstance(effect0, WzSubProperty) else []
    result = WzSubProperty("effect", target)
    for variant_index in range(2):
        frames = primary_variants[min(variant_index, len(primary_variants) - 1)] if primary_variants else []
        variant = WzSubProperty(str(variant_index), result)
        merge_tracks(frames, secondary, variant, target_key)
        result.add(variant)
    return result


def copy_tree_argb4444(prop, name: str, parent, target_key: WzKey):
    if isinstance(prop, WzCanvasProperty):
        return encode_target_canvas(prop, name, parent, target_key)
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(name, parent)
        children = list(prop.children())
        numeric = children and all(child.name.isdigit() for child in children)
        if numeric:
            children.sort(key=lambda child: int(child.name))
        for index, child in enumerate(children):
            child_name = str(index) if numeric else child.name
            out.add(copy_tree_argb4444(child, child_name, out, target_key))
        return out
    return clone_property(prop, name, parent)


def make_icon(src: WzCanvasProperty, name: str, parent, target_key: WzKey) -> WzCanvasProperty:
    out = encode_target_canvas(src, name, parent, target_key)
    set_vector(out, "origin", (0, int(out.height)))
    set_int(out, "z", 0)
    return out


def make_action(spec: SkillSpec, parent: WzSubProperty) -> WzSubProperty:
    action = WzSubProperty("action", parent)
    for index, value in enumerate(spec.action):
        set_string(action, str(index), value)
    return action


def make_levels(spec: SkillSpec, parent: WzSubProperty) -> WzSubProperty:
    levels = WzSubProperty("level", parent)
    for level in range(1, MASTER_LEVEL + 1):
        node = WzSubProperty(str(level), levels)
        set_int(node, "attackCount", min(15, spec.attack_count))
        set_int(node, "cooltime", spec.cooldown)
        set_int(node, "damage", spec.damage)
        set_string(node, "hs", f"h{level}")
        set_vector(node, "lt", (-1280, -720))
        set_int(node, "mobCount", min(15, spec.mob_count))
        set_int(node, "mpCon", spec.mp_con)
        set_vector(node, "rb", (1280, 720))
        levels.add(node)
    return levels


def build_skill(spec: SkillSpec, source: WzSubProperty, hit_source: WzSubProperty | None, parent: WzSubProperty, key: WzKey) -> WzSubProperty:
    target = WzSubProperty(str(spec.target_id), parent)
    for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
        icon = source.child(icon_name)
        if not isinstance(icon, WzCanvasProperty) and hit_source is not None:
            icon = hit_source.child(icon_name)
        if isinstance(icon, WzCanvasProperty):
            target.add(make_icon(icon, icon_name, target, key))
    target.add(effect_variants(source, target, key))
    hit_owner = hit_source or source
    hit = hit_owner.child("hit")
    if isinstance(hit, WzSubProperty):
        target.add(copy_tree_argb4444(hit, "hit", target, key))
    target.add(make_action(spec, target))
    target.add(make_levels(spec, target))
    set_int(target, "masterLevel", MASTER_LEVEL)
    if spec.hidden:
        set_int(target, "invisible", 1)
    return target


def source_node(groups: dict[str, WzSubProperty], group: str, skill_id: int) -> WzSubProperty:
    node = groups[group].get(f"skill/{skill_id}")
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing source skill/{skill_id} in {group}.img")
    return node


def patch_client_skill(groups: dict[str, WzSubProperty], dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name)
    root = image.parse()
    skill_root = ensure_path(root, "skill")
    key = image.wz_file.reader.key
    for spec in SKILLS:
        source = source_node(groups, spec.source_group, spec.source_id)
        hit_source = source_node(groups, "1114", spec.hit_source_id) if spec.hit_source_id else None
        replace_child(skill_root, build_skill(spec, source, hit_source, skill_root, key))
        print(f"client skill: {spec.source_id} -> {spec.target_id}")
    if dry_run:
        return
    backup(CLIENT_SKILL)
    atomic_write_bytes(CLIENT_SKILL, encode_image_body(image, image.wz_file.reader))


def source_string_values(strings: WzSubProperty, skill_id: int) -> dict[str, str]:
    node = strings.get(str(skill_id))
    if not isinstance(node, WzSubProperty):
        return {}
    return {child.name: str(child.value) for child in node.children() if isinstance(child, WzStringProperty)}


def level_text(spec: SkillSpec) -> str:
    cooldown = f"，冷却时间{spec.cooldown}秒" if spec.cooldown else ""
    return f"消耗MP {spec.mp_con}，最多攻击{spec.mob_count}名敌人，以{spec.damage}%伤害攻击{spec.attack_count}次{cooldown}                    "


def patch_client_string(strings: WzSubProperty, dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_STRING.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_STRING.name)
    root = image.parse()
    for spec in SKILLS:
        source_values = source_string_values(strings, spec.source_id)
        node = WzSubProperty(str(spec.target_id), root)
        set_string(node, "name", spec.name)
        set_string(node, "desc", source_values.get("desc", spec.description))
        for level in range(1, MASTER_LEVEL + 1):
            set_string(node, f"h{level}", level_text(spec))
        replace_child(root, node)
    if dry_run:
        return
    backup(CLIENT_STRING)
    atomic_write_bytes(CLIENT_STRING, encode_image_body(image, image.wz_file.reader))


def selected_screen_tracks(spec: SkillSpec, groups: dict[str, WzSubProperty]) -> list[list[WzCanvasProperty]]:
    source = source_node(groups, spec.source_group, spec.source_id)
    tracks: list[list[WzCanvasProperty]] = []
    if spec.target_id == 11121005:
        fallback = source_node(groups, "40001", 400011089)
        for name in ("screen", "screen0", "screen1"):
            frames = numeric_canvases(fallback.child(name))
            if frames:
                tracks.append(frames)
    elif spec.target_id == 11121008:
        for name in ("screen0", "screen1", "screen", "screen2", "screen4", "screen5"):
            frames = numeric_canvases(source.child(name))
            if frames:
                tracks.append(frames)
        divide = source_node(groups, "40001", 400011089)
        for name in ("screen", "screen0", "screen1"):
            frames = numeric_canvases(divide.child(name))
            if frames:
                tracks.append(frames)
    elif spec.target_id == 11121009:
        for name in ("screen", "screen0", "screen1"):
            frames = numeric_canvases(source.child(name))
            if frames:
                tracks.append(frames)
    return tracks


def build_field_effect(spec: SkillSpec, groups: dict[str, WzSubProperty], parent: WzSubProperty, key: WzKey) -> WzSubProperty:
    effect = WzSubProperty(spec.field_effect or str(spec.target_id), parent)
    output_index = 0
    for track in selected_screen_tracks(spec, groups):
        # Heavy full-screen sequences are sampled at half rate; delay is retained.
        for frame_index in range(0, len(track), 2):
            frame = encode_target_canvas(track[frame_index], str(output_index), effect, key, force_screen=True, delay_multiplier=2)
            effect.add(frame)
            output_index += 1
    if output_index == 0:
        raise RuntimeError(f"no field-effect frames for {spec.target_id}")
    return effect


def patch_map_effect(groups: dict[str, WzSubProperty], dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_MAP_EFFECT.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    root = image.parse()
    parent = ensure_path(root, FIELD_EFFECT_ROOT)
    key = image.wz_file.reader.key
    for spec in SKILLS:
        if not spec.field_effect:
            continue
        replace_child(parent, build_field_effect(spec, groups, parent, key))
        print(f"field effect: {FIELD_EFFECT_ROOT}/{spec.field_effect}")
    if dry_run:
        return
    backup(CLIENT_MAP_EFFECT)
    atomic_write_bytes(CLIENT_MAP_EFFECT, encode_image_body(image, image.wz_file.reader))


def xml_escape(value: str) -> str:
    return html.escape(value, quote=True)


def server_skill_block(spec: SkillSpec) -> str:
    lines = [f'  <imgdir name="{spec.target_id}">']
    lines.append('    <imgdir name="action">')
    for index, action in enumerate(spec.action):
        lines.append(f'      <string name="{index}" value="{xml_escape(action)}"/>')
    lines.append("    </imgdir>")
    lines.append('    <imgdir name="level">')
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend(
            [
                f'      <imgdir name="{level}">',
                f'        <int name="attackCount" value="{min(15, spec.attack_count)}"/>',
                f'        <int name="cooltime" value="{spec.cooldown}"/>',
                f'        <int name="damage" value="{spec.damage}"/>',
                f'        <string name="hs" value="h{level}"/>',
                '        <vector name="lt" x="-1280" y="-720"/>',
                f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
                f'        <int name="mpCon" value="{spec.mp_con}"/>',
                '        <vector name="rb" x="1280" y="720"/>',
                "      </imgdir>",
            ]
        )
    lines.append("    </imgdir>")
    lines.append(f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>')
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_skill(dry_run: bool) -> None:
    text = SERVER_SKILL.read_text(encoding="utf-8")
    info_start, info_end = find_imgdir_block(text, "info")
    info = text[info_start:info_end]
    blocks = "\n".join(server_skill_block(spec) for spec in SKILLS)
    new_text = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<imgdir name="1112.img">\n{info}\n<imgdir name="skill">\n{blocks}\n</imgdir>\n</imgdir>\n'
    if dry_run:
        return
    backup(SERVER_SKILL)
    atomic_write_text(SERVER_SKILL, new_text)


def server_string_block(spec: SkillSpec, source_values: dict[str, str]) -> str:
    lines = [f'  <imgdir name="{spec.target_id}">']
    lines.append(f'    <string name="name" value="{xml_escape(spec.name)}"/>')
    lines.append(f'    <string name="desc" value="{xml_escape(source_values.get("desc", spec.description))}"/>')
    for level in range(1, MASTER_LEVEL + 1):
        lines.append(f'    <string name="h{level}" value="{xml_escape(level_text(spec))}"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def replace_or_insert_xml_block(text: str, node_name: str, block: str) -> str:
    try:
        start, end = find_imgdir_block(text, node_name)
        return text[:start] + block + text[end:]
    except RuntimeError:
        closing = text.rfind("</imgdir>")
        if closing < 0:
            raise RuntimeError("missing String.wz root closing imgdir")
        return text[:closing] + block + "\n" + text[closing:]


def patch_server_string(strings: WzSubProperty, dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    for spec in SKILLS:
        block = server_string_block(spec, source_string_values(strings, spec.source_id))
        text = replace_or_insert_xml_block(text, str(spec.target_id), block)
    if dry_run:
        return
    backup(SERVER_STRING)
    atomic_write_text(SERVER_STRING, text)


def validate_client_outputs() -> None:
    image = WzImage.from_bytes(CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name)
    root = image.parse()
    count = 0
    max_size = (0, 0)
    raw = 0

    def walk(node):
        nonlocal count, max_size, raw
        if isinstance(node, WzCanvasProperty):
            count += 1
            if int(node.format) != CANVAS_FORMAT or int(node.format2) != 0:
                raise RuntimeError(f"non-ARGB4444 canvas: {node.name} format={node.format}+{node.format2}")
            if int(node.width) > SCREEN_WIDTH or int(node.height) > SCREEN_HEIGHT:
                raise RuntimeError(f"oversized canvas: {node.width}x{node.height}")
            max_size = max(max_size, (int(node.width), int(node.height)), key=lambda value: value[0] * value[1])
            raw += int(node.width) * int(node.height) * 2
        if hasattr(node, "children"):
            for child in node.children():
                walk(child)

    for spec in SKILLS:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing migrated client skill {spec.target_id}")
        walk(node)
    print(f"validated client skills: canvases={count}, max={max_size[0]}x{max_size[1]}, ARGB4444 raw={raw / 1024 / 1024:.1f} MiB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate_client_outputs()
        return 0
    groups, strings = load_sources()
    patch_client_skill(groups, args.dry_run)
    patch_client_string(strings, args.dry_run)
    patch_map_effect(groups, args.dry_run)
    patch_server_skill(args.dry_run)
    patch_server_string(strings, args.dry_run)
    if not args.dry_run:
        validate_client_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
