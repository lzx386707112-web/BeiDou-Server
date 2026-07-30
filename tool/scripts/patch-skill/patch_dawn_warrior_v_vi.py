#!/usr/bin/env python3
"""Migrate TMS Dawn Warrior V/VI active attacks into the empty 1112 skill book.

Compatibility policy:
- remap retained source skills to 11121005..11121012;
- encode every client canvas as ARGB4444 (WZ format 1);
- fit oversized canvases inside 1280x720 and never exceed 2048x2048;
- reshape character effects into Brandish-compatible effect/0 and effect/1;
- move modern screen animations to Map/Effect field effects;
- keep server Skill.wz free of visual payloads (only action/level metadata).
"""

from __future__ import annotations

import argparse
import configparser
import copy
import gc
import hashlib
import html
import io
import os
import posixpath
import re
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
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
    WzUolProperty,
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
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/DawnWarrior")
SOURCE_1114 = TMS_ROOT / "Skill" / "_Canvas" / "1114.img"
SOURCE_40001 = TMS_ROOT / "Skill" / "_Canvas" / "40001.img"
SOURCE_STRING = TMS_ROOT / "String" / "Skill.img"

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1112.img"
STAGING_IMAGE_TEMPLATE = ROOT / "clien" / "Data" / "Skill" / "1412.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
CLIENT_CONFIG = ROOT / "clien" / "config.ini"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"

CANVAS_FORMAT = 1
MAX_SCREEN_WIDTH = 1280
MAX_SCREEN_HEIGHT = 720
TEXTURE_LIMIT = 2048
DEFAULT_FRAME_DELAY = 30
MASTER_LEVEL = 30
FIELD_EFFECT_ROOT = "customSkill/dawnWarrior"
CUSTOM_SKILL_IDS = range(11121000, 11121013)
SOUL_ECLIPSE_REFERENCE_WIDTH = 1368
SOUL_ECLIPSE_REFERENCE_HEIGHT = 768
GALAXY_STAR_BURST_VIDEO_SAMPLE_STEP = 1
GALAXY_STAR_BURST_SCREEN_SCALE = 1.0
GALAXY_STAR_BURST_DURATION_MS = 7140
SOUL_ECLIPSE_SAMPLE_STEP = 1
SOUL_ECLIPSE_DURATION_MS = 20000
VIDEO_MARKER_WIDTH = 7
VIDEO_MARKER_HEIGHT = 5
VIDEO_MARKER_DURATION_MS = 30000
VIDEO_FIELD_MARKERS = (
    "galaxyStarBurstVideoLayer",
    "eclipseForceVideoLayer",
    "soulEclipseVideoLayer",
)


def configured_screen_size() -> tuple[int, int]:
    config = configparser.ConfigParser()
    config.read(CLIENT_CONFIG, encoding="utf-8")
    width = config.getint("general", "width", fallback=MAX_SCREEN_WIDTH)
    height = config.getint("general", "height", fallback=MAX_SCREEN_HEIGHT)
    return min(MAX_SCREEN_WIDTH, max(1, width)), min(MAX_SCREEN_HEIGHT, max(1, height))


SCREEN_WIDTH, SCREEN_HEIGHT = configured_screen_size()


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
    hit_source_group: str = "1114"
    field_effect: str | None = None
    effect_node: str = "effect"
    effect0_node: str = "effect0"
    lt: tuple[int, int] = (-1200, -800)
    rb: tuple[int, int] = (1200, 800)
    duration_seconds: int | None = None


@dataclass
class MsMetadata:
    roots: dict[int, ET.Element]
    paths: dict[int, str]
    index: dict[str, ET.Element]

    @classmethod
    def load(cls) -> "MsMetadata":
        roots: dict[int, ET.Element] = {}
        paths: dict[int, str] = {}
        index: dict[str, ET.Element] = {}
        for spec in SKILLS:
            if spec.source_id in roots:
                continue
            path = MS_EXPORT_ROOT / f"{spec.source_id}.xml"
            if not path.is_file():
                raise RuntimeError(f"missing MS export: {path}")
            root = ET.parse(path).getroot()
            if root.tag != "skill" or int(root.attrib.get("id", 0)) != spec.source_id:
                raise RuntimeError(f"invalid MS skill export: {path}")
            roots[spec.source_id] = root

            def visit(element: ET.Element, node_path: str) -> None:
                paths[id(element)] = node_path
                index[node_path] = element
                for child in element:
                    name = child.attrib.get("name")
                    if name is not None:
                        visit(child, f"{node_path}/{name}")

            visit(root, f"skill/{spec.source_id}")
        return cls(roots, paths, index)

    def child(self, node: ET.Element | None, name: str) -> ET.Element | None:
        if node is None:
            return None
        return next((child for child in node if child.attrib.get("name") == name), None)

    def resolve(self, node: ET.Element) -> ET.Element:
        seen: set[str] = set()
        while node.tag == "uol":
            current = self.paths[id(node)]
            value = node.attrib["value"]
            target = posixpath.normpath(posixpath.join(posixpath.dirname(current), value))
            if target in seen or target not in self.index:
                raise RuntimeError(f"unresolved MS UOL: {current} -> {value}")
            seen.add(target)
            node = self.index[target]
        return node


SKILLS = (
    SkillSpec(11121005, 11141500, "1114", "银河星爆", "斩开空间并引发远古爆炸。主演出由MS视频逐帧兼容。", 900, 15, 15, 500, 10, ("genesis",), field_effect="galaxyStarBurst"),
    SkillSpec(11121006, 11141503, "1114", "全蚀之力", "与元素共鸣，释放灵魂之力斩杀敌人。两阶段在旧端合并演出。", 850, 15, 15, 400, 10, ("sanctuary",), hit_source_id=11141504),
    SkillSpec(11121007, 11141504, "1114", "全蚀之力：魂斩", "全蚀之力的内部第二阶段。", 900, 15, 15, 0, 0, ("brandish1", "brandish2"), hidden=True),
    SkillSpec(11121008, 400011088, "40001", "灵魂蚀日", "体现日月重叠的日蚀，并以日月分裂结束演出。", 635, 7, 15, 1000, 120, ("genesis",), field_effect="soulEclipse", lt=(-700, -600), rb=(700, 200), duration_seconds=20),
    SkillSpec(11121009, 400011089, "40001", "日月分裂", "灵魂蚀日的内部终结阶段。", 900, 15, 15, 0, 0, ("brandish1", "brandish2"), hidden=True, field_effect="sunMoonDivide", lt=(-700, -600), rb=(700, 200)),
    SkillSpec(11121011, 400011056, "40001", "冥河破", "以灵魂之力发动黄泉十字斩击。", 750, 5, 15, 100, 0, ("brandish1", "brandish2"), lt=(-600, -480), rb=(10, 40)),
    SkillSpec(11121012, 400011142, "40001", "宇宙之花", "展开完整银河，在15秒内持续攻击周围敌人。", 700, 15, 12, 350, 10, ("sanctuary",), effect_node="special", effect0_node="special2", lt=(-380, -340), rb=(380, 80)),
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


def load_sources() -> tuple[dict[str, WzSubProperty], WzSubProperty, MsMetadata]:
    groups: dict[str, WzSubProperty] = {}
    for name, path in (("1114", SOURCE_1114), ("40001", SOURCE_40001)):
        image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("BMS"), name=path.name)
        groups[name] = image.parse()
    string_image = WzImage.from_bytes(SOURCE_STRING.read_bytes(), key=WzKey.for_region("BMS"), name=SOURCE_STRING.name)
    return groups, string_image.parse(), MsMetadata.load()


def ms_children(node: ET.Element | None) -> list[ET.Element]:
    return list(node) if node is not None else []


def ms_int(node: ET.Element | None, name: str, default: int | None = None) -> int | None:
    if node is not None:
        child = next((item for item in node if item.attrib.get("name") == name and item.tag in {"int", "short", "long"}), None)
        if child is not None:
            return int(child.attrib["value"])
    return default


def ms_vector(node: ET.Element | None, name: str) -> tuple[int, int] | None:
    if node is None:
        return None
    child = next((item for item in node if item.attrib.get("name") == name and item.tag == "vector"), None)
    if child is None:
        return None
    return int(child.attrib["x"]), int(child.attrib["y"])


def ms_numeric_frames(node: ET.Element | None, metadata: MsMetadata) -> list[ET.Element]:
    if node is None:
        return []
    frames = [child for child in node if child.attrib.get("name", "").isdigit() and child.tag in {"canvas", "uol"}]
    frames.sort(key=lambda child: int(child.attrib["name"]))
    return [metadata.resolve(frame) for frame in frames]


def resolve_ms_canvas(meta: ET.Element, groups: dict[str, WzSubProperty], metadata: MsMetadata) -> WzCanvasProperty | None:
    outlink = next((child for child in meta if child.tag == "string" and child.attrib.get("name") == "_outlink"), None)
    if outlink is not None:
        match = re.fullmatch(r"Skill/_Canvas/(\d+)\.img/(.+)", outlink.attrib["value"])
        if not match:
            return None
        group = groups.get(match.group(1))
        source = group.get(match.group(2)) if group is not None else None
    else:
        path = metadata.paths[id(meta)]
        match = re.match(r"skill/(\d+)/(.*)", path)
        if not match:
            return None
        source_id = int(match.group(1))
        group_name = next((spec.source_group for spec in SKILLS if spec.source_id == source_id), None)
        group = groups.get(group_name) if group_name is not None else None
        source = group.get(path) if group is not None else None
    return source if isinstance(source, WzCanvasProperty) else None


def paired_numeric_canvases(
    source: WzSubProperty | None,
    meta: ET.Element | None,
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
) -> list[tuple[WzCanvasProperty, ET.Element | None]]:
    meta_frames = ms_numeric_frames(meta, metadata)
    if meta_frames:
        result = []
        pending_delay = 0
        for frame in meta_frames:
            canvas = resolve_ms_canvas(frame, groups, metadata)
            if canvas is None:
                pending_delay += ms_int(frame, "delay", 0) or 0
                continue
            if pending_delay:
                frame = copy.deepcopy(frame)
                delay = next((child for child in frame if child.attrib.get("name") == "delay"), None)
                if delay is None:
                    delay = ET.SubElement(frame, "int", {"name": "delay", "value": "0"})
                delay.attrib["value"] = str(int(delay.attrib["value"]) + pending_delay)
                pending_delay = 0
            result.append((canvas, frame))
        if result:
            return result
    return [(canvas, None) for canvas in numeric_canvases(source)]


def numeric_canvases(node) -> list[WzCanvasProperty]:
    if not isinstance(node, WzSubProperty):
        return []
    frames = [child for child in node.children() if isinstance(child, WzCanvasProperty) and child.name.isdigit()]
    return sorted(frames, key=lambda frame: int(frame.name))


def frame_delay(canvas: WzCanvasProperty, meta: ET.Element | None = None) -> int:
    delay = ms_int(meta, "delay")
    if delay is not None:
        return max(1, delay)
    delay = canvas.child("delay")
    return max(1, int(delay.value)) if isinstance(delay, WzIntProperty) else DEFAULT_FRAME_DELAY


def canvas_origin(canvas: WzCanvasProperty, meta: ET.Element | None = None) -> tuple[int, int]:
    meta_origin = ms_vector(meta, "origin")
    if meta_origin is not None:
        return meta_origin
    origin = canvas.child("origin")
    if isinstance(origin, WzVectorProperty):
        return int(origin.x), int(origin.y)
    return int(canvas.width) // 2, int(canvas.height) // 2


def fit_size(width: int, height: int, allow_upscale: bool = False) -> tuple[int, int, float]:
    limit_w = min(SCREEN_WIDTH, TEXTURE_LIMIT)
    limit_h = min(SCREEN_HEIGHT, TEXTURE_LIMIT)
    scale = min(limit_w / max(1, width), limit_h / max(1, height))
    if not allow_upscale:
        scale = min(1.0, scale)
    return max(1, round(width * scale)), max(1, round(height * scale)), scale


def clean_rgba(image: Image.Image) -> Image.Image:
    return image.convert("RGBA")


def alpha_union(boxes: list[tuple[int, int, int, int] | None]) -> tuple[int, int, int, int] | None:
    visible = [box for box in boxes if box is not None]
    if not visible:
        return None
    return (
        min(box[0] for box in visible),
        min(box[1] for box in visible),
        max(box[2] for box in visible),
        max(box[3] for box in visible),
    )


def cover_size(
    image: Image.Image,
    crop_box: tuple[int, int, int, int] | None,
    target_width: int,
    target_height: int,
) -> Image.Image:
    if crop_box is not None:
        left, top, right, bottom = crop_box
        left = max(0, min(left, image.width - 1))
        top = max(0, min(top, image.height - 1))
        right = max(left + 1, min(right, image.width))
        bottom = max(top + 1, min(bottom, image.height))
        cropped = image.crop((left, top, right, bottom))
        image.close()
        image = cropped
    scale = max(target_width / image.width, target_height / image.height)
    width = max(target_width, round(image.width * scale))
    height = max(target_height, round(image.height * scale))
    if (width, height) != image.size:
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        image.close()
        image = resized
    left = (width - target_width) // 2
    top = (height - target_height) // 2
    result = image.crop((left, top, left + target_width, top + target_height))
    image.close()
    return result


def cover_screen(image: Image.Image, crop_box: tuple[int, int, int, int] | None) -> Image.Image:
    return cover_size(image, crop_box, SCREEN_WIDTH, SCREEN_HEIGHT)


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
    meta: ET.Element | None = None,
    screen_crop: tuple[int, int, int, int] | None = None,
) -> WzCanvasProperty:
    image = clean_rgba(decode_source_canvas(src))
    if force_screen:
        image = cover_screen(image, screen_crop)
        width, height = image.size
        scale = 1.0
    else:
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
    ox, oy = canvas_origin(src, meta)
    if force_screen:
        ox, oy = width // 2, height // 2
    else:
        ox, oy = round(ox * scale), round(oy * scale)
    set_vector(out, "origin", (ox, oy))
    set_int(out, "delay", frame_delay(src, meta) * delay_multiplier)
    if meta is not None:
        for child in meta:
            name = child.attrib.get("name")
            if not name or name in {"_outlink", "origin", "delay"}:
                continue
            if child.tag in {"int", "short", "long"}:
                set_int(out, name, int(child.attrib["value"]))
            elif child.tag == "string":
                set_string(out, name, child.attrib["value"])
            elif child.tag == "vector":
                set_vector(out, name, (int(child.attrib["x"]), int(child.attrib["y"])))
    else:
        z = src.child("z")
        if isinstance(z, WzIntProperty):
            set_int(out, "z", int(z.value))
    return out


def compose_frames(
    first: tuple[WzCanvasProperty, ET.Element | None],
    second: tuple[WzCanvasProperty, ET.Element | None],
    name: str,
    parent,
    target_key: WzKey,
) -> WzCanvasProperty:
    canvases = [first[0], second[0]]
    metas = [first[1], second[1]]
    images = [clean_rgba(decode_source_canvas(canvas)) for canvas in canvases]
    origins = [canvas_origin(canvas, meta) for canvas, meta in zip(canvases, metas)]
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
    set_int(out, "delay", max(frame_delay(canvases[0], metas[0]), frame_delay(canvases[1], metas[1])))
    for child in ms_children(metas[0]):
        name = child.attrib.get("name")
        if name in {"a0", "a1", "z", "rotate", "flip"} and child.tag in {"int", "short", "long"}:
            set_int(out, name, int(child.attrib["value"]))
    return out


def merge_tracks(
    primary: list[tuple[WzCanvasProperty, ET.Element | None]],
    secondary: list[tuple[WzCanvasProperty, ET.Element | None]],
    parent: WzSubProperty,
    target_key: WzKey,
    start_index: int = 0,
) -> None:
    total = max(len(primary), len(secondary))
    for index in range(total):
        first = primary[min(index, len(primary) - 1)] if primary else None
        second = secondary[min(index, len(secondary) - 1)] if secondary else None
        frame_name = str(start_index + index)
        if first is not None and second is not None:
            frame = compose_frames(first, second, frame_name, parent, target_key)
        else:
            canvas, meta = first or second
            frame = encode_target_canvas(canvas, frame_name, parent, target_key, meta=meta)
        parent.add(frame)


def metadata_value(node: ET.Element | None, name: str) -> int:
    child = next((item for item in ms_children(node) if item.attrib.get("name") == name), None)
    if child is None or "value" not in child.attrib:
        raise RuntimeError(f"missing MS value: {name}")
    return int(child.attrib["value"])


def build_cosmos_effect(
    meta_source: ET.Element,
    primary_variants: list[list[tuple[WzCanvasProperty, ET.Element | None]]],
    secondary_variants: list[list[tuple[WzCanvasProperty, ET.Element | None]]],
    target: WzSubProperty,
    target_key: WzKey,
    metadata: MsMetadata,
) -> WzSubProperty:
    if len(primary_variants) < 2 or len(secondary_variants) < 2:
        raise RuntimeError("Cosmos requires create/loop and closing variants")
    meta_effect = metadata.child(meta_source, "special")
    meta_effect0 = metadata.child(meta_source, "special2")
    meta_primary_loop = metadata.child(meta_effect, "0")
    meta_secondary_loop = metadata.child(meta_effect0, "0")
    primary_repeat = metadata_value(meta_primary_loop, "repeat")
    secondary_repeat = metadata_value(meta_secondary_loop, "repeat")
    if primary_repeat != secondary_repeat:
        raise RuntimeError("Cosmos special/special2 repeat indices differ")

    common = metadata.child(meta_source, "common")
    duration_ms = metadata_value(common, "time")
    result = WzSubProperty("effect", target)
    main = WzSubProperty("0", result)
    merge_tracks(primary_variants[0], secondary_variants[0], main, target_key)
    base_frames = sorted(
        (child for child in main.children() if isinstance(child, WzCanvasProperty) and child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    if not 0 <= primary_repeat < len(base_frames):
        raise RuntimeError("Cosmos repeat index is outside the base animation")
    elapsed = sum(frame_delay(frame) for frame in base_frames)
    output_index = len(base_frames)
    loop_index = primary_repeat
    while elapsed < duration_ms:
        source_frame = base_frames[loop_index]
        delay = frame_delay(source_frame)
        if elapsed + delay > duration_ms:
            raise RuntimeError("Cosmos loop frames do not align with common/time")
        main.add(WzUolProperty(str(output_index), source_frame.name, main))
        elapsed += delay
        output_index += 1
        loop_index += 1
        if loop_index >= len(base_frames):
            loop_index = primary_repeat

    merge_tracks(
        primary_variants[1],
        secondary_variants[1],
        main,
        target_key,
        start_index=output_index,
    )
    set_int(main, "z", -1)
    result.add(main)

    alternate = WzSubProperty("1", result)
    frame_count = output_index + max(len(primary_variants[1]), len(secondary_variants[1]))
    for index in range(frame_count):
        alternate.add(WzUolProperty(str(index), f"../0/{index}", alternate))
    set_int(alternate, "z", -1)
    result.add(alternate)
    return result


def effect_tracks(
    source: WzSubProperty | None,
    meta: ET.Element | None,
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
) -> list[list[tuple[WzCanvasProperty, ET.Element | None]]]:
    direct = paired_numeric_canvases(source, meta, groups, metadata)
    if direct:
        return [direct]
    result = []
    meta_variants = [child for child in ms_children(meta) if child.attrib.get("name", "").isdigit()]
    meta_variants.sort(key=lambda child: int(child.attrib["name"]))
    if meta_variants:
        for meta_variant in meta_variants:
            source_variant = source.child(meta_variant.attrib["name"]) if isinstance(source, WzSubProperty) else None
            frames = paired_numeric_canvases(source_variant, meta_variant, groups, metadata)
            if frames:
                result.append(frames)
        return result
    if isinstance(source, WzSubProperty):
        for child in sorted(source.children(), key=lambda item: int(item.name) if item.name.isdigit() else 9999):
            frames = paired_numeric_canvases(child if isinstance(child, WzSubProperty) else None, None, groups, metadata)
            if frames:
                result.append(frames)
    return result


def effect_variants(
    spec: SkillSpec,
    source: WzSubProperty,
    meta_source: ET.Element,
    target: WzSubProperty,
    target_key: WzKey,
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
) -> WzSubProperty:
    effect = source.child(spec.effect_node)
    effect0 = source.child(spec.effect0_node)
    meta_effect = metadata.child(meta_source, spec.effect_node)
    meta_effect0 = metadata.child(meta_source, spec.effect0_node)
    primary_variants = effect_tracks(
        effect if isinstance(effect, WzSubProperty) else None, meta_effect, groups, metadata
    )

    secondary_variants = effect_tracks(
        effect0 if isinstance(effect0, WzSubProperty) else None, meta_effect0, groups, metadata
    )
    if spec.target_id == 11121012:
        return build_cosmos_effect(
            meta_source,
            primary_variants,
            secondary_variants,
            target,
            target_key,
            metadata,
        )
    result = WzSubProperty("effect", target)
    for variant_index in range(2):
        frames = primary_variants[min(variant_index, len(primary_variants) - 1)] if primary_variants else []
        secondary = (
            secondary_variants[min(variant_index, len(secondary_variants) - 1)]
            if secondary_variants
            else []
        )
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
        set_vector(node, "lt", spec.lt)
        set_int(node, "mobCount", min(15, spec.mob_count))
        set_int(node, "mpCon", spec.mp_con)
        set_vector(node, "rb", spec.rb)
        if spec.duration_seconds is not None:
            set_int(node, "time", spec.duration_seconds)
        levels.add(node)
    return levels


def build_skill(
    spec: SkillSpec,
    source: WzSubProperty,
    hit_source: WzSubProperty | None,
    parent: WzSubProperty,
    key: WzKey,
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
) -> WzSubProperty:
    target = WzSubProperty(str(spec.target_id), parent)
    for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
        icon = source.child(icon_name)
        if not isinstance(icon, WzCanvasProperty) and hit_source is not None:
            icon = hit_source.child(icon_name)
        if isinstance(icon, WzCanvasProperty):
            target.add(make_icon(icon, icon_name, target, key))
    target.add(effect_variants(spec, source, metadata.roots[spec.source_id], target, key, groups, metadata))
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


def patch_client_skill(groups: dict[str, WzSubProperty], metadata: MsMetadata, dry_run: bool) -> None:
    image = WzImage.from_bytes(CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name)
    root = image.parse()
    skill_root = ensure_path(root, "skill")
    key = image.wz_file.reader.key
    for skill_id in CUSTOM_SKILL_IDS:
        skill_root._children.pop(str(skill_id), None)
    for spec in SKILLS:
        source = source_node(groups, spec.source_group, spec.source_id)
        hit_source = source_node(groups, spec.hit_source_group, spec.hit_source_id) if spec.hit_source_id else None
        replace_child(skill_root, build_skill(spec, source, hit_source, skill_root, key, groups, metadata))
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
    for skill_id in CUSTOM_SKILL_IDS:
        root._children.pop(str(skill_id), None)
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


def append_video_frames(
    effect: WzSubProperty,
    video: ET.Element,
    key: WzKey,
    output_index: int,
    sample_step: int = 6,
    screen_scale: float = 1.0,
    cover_alpha_to_screen: bool = False,
) -> int:
    frames = [child for child in video if child.tag == "frame"]
    boxes = []
    for frame in frames:
        with Image.open(MS_EXPORT_ROOT / frame.attrib["file"]) as source_image:
            rgba = source_image.convert("RGBA")
            alpha = rgba.getchannel("A")
            boxes.append(alpha.getbbox())
            alpha.close()
            rgba.close()
    crop_box = alpha_union(boxes)
    for frame_index in range(0, len(frames), sample_step):
        sampled = frames[frame_index : frame_index + sample_step]
        image_path = MS_EXPORT_ROOT / sampled[0].attrib["file"]
        with Image.open(image_path) as source_image:
            image = clean_rgba(source_image)
        if cover_alpha_to_screen:
            image = cover_screen(image, crop_box)
            width, height = image.size
            origin = (width // 2, height // 2)
        else:
            source_width, source_height = image.size
            scale = min(
                1.0,
                SCREEN_WIDTH / max(1, source_width),
                SCREEN_HEIGHT / max(1, source_height),
            ) * screen_scale
            scaled_width = max(1, round(source_width * scale))
            scaled_height = max(1, round(source_height * scale))
            if (scaled_width, scaled_height) != image.size:
                resized = image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
                image.close()
                image = resized
            if crop_box is None:
                left, top, right, bottom = 0, 0, scaled_width, scaled_height
            else:
                left = max(0, min(scaled_width - 1, round(crop_box[0] * scale)))
                top = max(0, min(scaled_height - 1, round(crop_box[1] * scale)))
                right = max(left + 1, min(scaled_width, round(crop_box[2] * scale)))
                bottom = max(top + 1, min(scaled_height, round(crop_box[3] * scale)))
            cropped = image.crop((left, top, right, bottom))
            image.close()
            image = cropped
            width, height = image.size
            origin = (scaled_width // 2 - left, scaled_height // 2 - top)
        frame = WzCanvasProperty(str(output_index), effect)
        frame.width = width
        frame.height = height
        frame.format = CANVAS_FORMAT
        frame.format2 = 0
        frame._png_data = encode_canvas_payload(image, CANVAS_FORMAT, width, height, key=key, listwz=False, zlib_level=9)
        frame._png_length = len(frame._png_data)
        set_vector(frame, "origin", origin)
        set_int(frame, "delay", sum(max(1, int(item.attrib["delay"])) for item in sampled))
        effect.add(frame)
        image.close()
        output_index += 1
    return output_index


def build_field_effect(
    spec: SkillSpec,
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
    parent: WzSubProperty,
    key: WzKey,
) -> WzSubProperty:
    effect = WzSubProperty(spec.field_effect or str(spec.target_id), parent)
    output_index = 0
    if spec.target_id == 11121005:
        screen = metadata.child(metadata.roots[11141500], "screen")
        video = next((child for child in ms_children(screen) if child.tag == "video"), None)
        if video is None:
            raise RuntimeError("missing MS video: 11141500/screen/video")
        output_index = append_video_frames(
            effect,
            video,
            key,
            output_index,
            sample_step=GALAXY_STAR_BURST_VIDEO_SAMPLE_STEP,
            screen_scale=GALAXY_STAR_BURST_SCREEN_SCALE,
            cover_alpha_to_screen=True,
        )
    elif spec.target_id == 11121008:
        return build_soul_eclipse_field_effect(groups, metadata, parent, key)
    if output_index == 0:
        raise RuntimeError(f"no field-effect frames for {spec.target_id}")
    return effect


def encode_rgba_canvas(
    image: Image.Image,
    name: str,
    parent: WzSubProperty,
    key: WzKey,
    delay: int,
    z: int = 0,
    origin: tuple[int, int] | None = None,
) -> WzCanvasProperty:
    image = clean_rgba(image)
    frame = WzCanvasProperty(name, parent)
    frame.width = image.width
    frame.height = image.height
    frame.format = CANVAS_FORMAT
    frame.format2 = 0
    frame._png_data = encode_canvas_payload(
        image,
        CANVAS_FORMAT,
        image.width,
        image.height,
        key=key,
        listwz=False,
        zlib_level=9,
    )
    frame._png_length = len(frame._png_data)
    set_vector(frame, "origin", origin or (image.width // 2, image.height // 2))
    set_int(frame, "delay", max(1, delay))
    set_int(frame, "z", z)
    return frame


def source_screen_track(
    source_id: int,
    group: str,
    branch_name: str,
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
) -> list[tuple[WzCanvasProperty, ET.Element | None]]:
    source = source_node(groups, group, source_id)
    branch = source.child(branch_name)
    meta_branch = metadata.child(metadata.roots[source_id], branch_name)
    return paired_numeric_canvases(
        branch if isinstance(branch, WzSubProperty) else None,
        meta_branch,
        groups,
        metadata,
    )


def screen_anchored_image(
    canvas: WzCanvasProperty,
    meta: ET.Element | None,
    source_scale: float = 1.0,
) -> Image.Image:
    image = clean_rgba(decode_source_canvas(canvas))
    origin_x, origin_y = canvas_origin(canvas, meta)
    if source_scale != 1.0:
        resized = image.resize(
            (round(image.width * source_scale), round(image.height * source_scale)),
            Image.Resampling.LANCZOS,
        )
        image.close()
        image = resized
        origin_x = round(origin_x * source_scale)
        origin_y = round(origin_y * source_scale)
    reference = Image.new(
        "RGBA",
        (SOUL_ECLIPSE_REFERENCE_WIDTH, SOUL_ECLIPSE_REFERENCE_HEIGHT),
        (0, 0, 0, 0),
    )
    reference.alpha_composite(
        image,
        (
            SOUL_ECLIPSE_REFERENCE_WIDTH // 2 - origin_x,
            SOUL_ECLIPSE_REFERENCE_HEIGHT // 2 - origin_y,
        ),
    )
    result = cover_screen(reference, (0, 0, reference.width, reference.height))
    image.close()
    reference.close()
    return result


def append_soul_eclipse_track(
    effect: WzSubProperty,
    track: list[tuple[WzCanvasProperty, ET.Element | None]],
    key: WzKey,
    output_index: int,
    source_scale: float,
) -> int:
    for frame_index in range(0, len(track), SOUL_ECLIPSE_SAMPLE_STEP):
        canvas, meta = track[frame_index]
        sampled = track[frame_index : frame_index + SOUL_ECLIPSE_SAMPLE_STEP]
        image = screen_anchored_image(canvas, meta, source_scale)
        box = image.getbbox()
        if box is None:
            raise RuntimeError(f"transparent Soul Eclipse frame: {frame_index}")
        left, top, right, bottom = box
        image = image.crop(box)
        effect.add(
            encode_rgba_canvas(
                image,
                str(output_index),
                effect,
                key,
                sum(frame_delay(item[0], item[1]) for item in sampled),
                origin=(SCREEN_WIDTH // 2 - left, SCREEN_HEIGHT // 2 - top),
            )
        )
        image.close()
        output_index += 1
    return output_index


def build_soul_eclipse_field_effect(
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
    parent: WzSubProperty,
    key: WzKey,
) -> WzSubProperty:
    specs = (
        (400011088, "screen0", 1.0),
        (400011088, "screen1", 2.0),
        (400011088, "screen", 2.0),
        (400011088, "screen2", 1.0),
        (400011088, "screen4", 1.0),
        (400011088, "screen5", 1.0),
        (400011089, "screen", 2.0),
        (400011089, "screen0", 2.0),
        (400011089, "screen1", 1.0),
    )
    effect = WzSubProperty("soulEclipse", parent)
    output_index = 0
    for source_id, branch_name, source_scale in specs:
        track = source_screen_track(source_id, "40001", branch_name, groups, metadata)
        if not track:
            raise RuntimeError(f"missing Soul Eclipse track: {source_id}/{branch_name}")
        output_index = append_soul_eclipse_track(
            effect,
            track,
            key,
            output_index,
            source_scale,
        )
    return effect


def build_video_field_effect(
    name: str,
    sequences: tuple[tuple[int, tuple[str, ...], int, bool], ...],
    metadata: MsMetadata,
    parent: WzSubProperty,
    key: WzKey,
) -> WzSubProperty:
    effect = WzSubProperty(name, parent)
    output_index = 0
    for skill_id, path, sample_step, cover_alpha_to_screen in sequences:
        node = metadata.roots[skill_id]
        for segment in path:
            node = metadata.child(node, segment)
            if node is None:
                raise RuntimeError(f"missing MS video branch: {skill_id}/{'/'.join(path)}")
        video = next((child for child in node if child.tag == "video"), None)
        if video is None:
            raise RuntimeError(f"missing MS video: {skill_id}/{'/'.join(path)}/video")
        output_index = append_video_frames(
            effect,
            video,
            key,
            output_index,
            sample_step=sample_step,
            cover_alpha_to_screen=cover_alpha_to_screen,
        )
    return effect


def build_static_field_background(
    name: str,
    duration: int,
    color: tuple[int, int, int, int],
    parent: WzSubProperty,
    key: WzKey,
) -> WzSubProperty:
    effect = WzSubProperty(name, parent)
    effect.add(
        encode_rgba_canvas(
            Image.new("RGBA", (SCREEN_WIDTH, SCREEN_HEIGHT), color),
            "0",
            effect,
            key,
            duration,
        )
    )
    return effect


def build_video_field_marker(
    name: str,
    parent: WzSubProperty,
    key: WzKey,
) -> WzSubProperty:
    effect = WzSubProperty(name, parent)
    image = Image.new("RGBA", (VIDEO_MARKER_WIDTH, VIDEO_MARKER_HEIGHT), (0, 0, 0, 0))
    image.putdata(
        [
            (17, 34, 51, 255),
            (68, 85, 102, 255),
            (119, 136, 153, 255),
            (170, 187, 204, 255),
        ]
        + [(0, 0, 0, 0)] * (VIDEO_MARKER_WIDTH * VIDEO_MARKER_HEIGHT - 4)
    )
    effect.add(
        encode_rgba_canvas(
            image,
            "0",
            effect,
            key,
            VIDEO_MARKER_DURATION_MS,
            origin=(VIDEO_MARKER_WIDTH // 2, VIDEO_MARKER_HEIGHT // 2),
        )
    )
    image.close()
    return effect


def write_soul_eclipse_stage(
    groups: dict[str, WzSubProperty],
    metadata: MsMetadata,
    staged_path: Path,
) -> None:
    soul_eclipse = next(spec for spec in SKILLS if spec.target_id == 11121008)
    staging_image = WzImage.from_bytes(
        STAGING_IMAGE_TEMPLATE.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=staged_path.name,
    )
    staging_root = staging_image.parse()
    staging_root._children.clear()
    staged_effect = build_field_effect(
        soul_eclipse,
        groups,
        metadata,
        staging_root,
        staging_image.wz_file.reader.key,
    )
    replace_child(staging_root, staged_effect)
    atomic_write_bytes(
        staged_path,
        encode_image_body(staging_image, staging_image.wz_file.reader),
    )


def install_map_effect_stage(staged_path: Path, metadata: MsMetadata, dry_run: bool) -> None:
    try:
        image = WzImage.from_bytes(
            CLIENT_MAP_EFFECT.read_bytes(),
            key=WzKey.for_region("GMS"),
            name=CLIENT_MAP_EFFECT.name,
        )
        root = image.parse()
        parent = ensure_path(root, FIELD_EFFECT_ROOT)
        key = image.wz_file.reader.key
        for child_name in list(parent._children):
            if re.fullmatch(r"soulEclipse\d+", child_name) or child_name.startswith("soulEclipse") or child_name.startswith("sunMoonDivide"):
                parent._children.pop(child_name)
        staged_image = WzImage.from_bytes(
            staged_path.read_bytes(),
            key=WzKey.for_region("GMS"),
            name=staged_path.name,
        )
        staged_effect = staged_image.parse().get("soulEclipse")
        if not isinstance(staged_effect, WzSubProperty):
            raise RuntimeError("missing staged Soul Eclipse field effect")
        replace_child(parent, staged_effect)

        for spec in SKILLS:
            if not spec.field_effect or spec.target_id in {11121008, 11121009}:
                continue
            effect = build_field_effect(spec, {}, metadata, parent, key)
            replace_child(parent, effect)
            print(f"field effect: {FIELD_EFFECT_ROOT}/{spec.field_effect}")
        full_eclipse_effects = (
            (
                "fullEclipseMale",
                ((11141503, ("screen",), 6, False), (11141504, ("screen",), 1, True)),
            ),
            (
                "fullEclipseFemale",
                ((11141503, ("screen2",), 6, False), (11141504, ("screen",), 1, True)),
            ),
        )
        for name, sequences in full_eclipse_effects:
            replace_child(parent, build_video_field_effect(name, sequences, metadata, parent, key))
            print(f"field effect: {FIELD_EFFECT_ROOT}/{name}")
        parent._children.pop("soulEclipseBackground", None)
        backgrounds = (
            ("galaxyStarBurstBackground", GALAXY_STAR_BURST_DURATION_MS, (4, 0, 16, 220)),
        )
        for name, duration, color in backgrounds:
            replace_child(parent, build_static_field_background(name, duration, color, parent, key))
            print(f"field effect: {FIELD_EFFECT_ROOT}/{name}")
        for name in VIDEO_FIELD_MARKERS:
            replace_child(parent, build_video_field_marker(name, parent, key))
            print(f"field effect marker: {FIELD_EFFECT_ROOT}/{name}")
        if dry_run:
            return
        backup(CLIENT_MAP_EFFECT)
        atomic_write_bytes(CLIENT_MAP_EFFECT, encode_image_body(image, image.wz_file.reader))
    finally:
        staged_path.unlink(missing_ok=True)


def patch_map_effect(groups: dict[str, WzSubProperty], metadata: MsMetadata, dry_run: bool) -> None:
    with tempfile.NamedTemporaryFile(
        prefix=".soul-eclipse-stage.",
        suffix=".img",
        dir=CLIENT_MAP_EFFECT.parent,
        delete=False,
    ) as staged_file:
        staged_path = Path(staged_file.name)
    try:
        write_soul_eclipse_stage(groups, metadata, staged_path)
        print(f"field effect: {FIELD_EFFECT_ROOT}/soulEclipse")
    except BaseException:
        staged_path.unlink(missing_ok=True)
        raise
    arguments = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--install-map-stage",
        str(staged_path),
    ]
    if dry_run:
        arguments.append("--dry-run")
    os.execv(sys.executable, arguments)


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
                f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
                f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
                f'        <int name="mpCon" value="{spec.mp_con}"/>',
                f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
                *(
                    [f'        <int name="time" value="{spec.duration_seconds}"/>']
                    if spec.duration_seconds is not None
                    else []
                ),
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
        line_start = text.rfind("\n", 0, start) + 1
        if not text[line_start:start].strip():
            start = line_start
        return text[:start] + block + text[end:]
    except RuntimeError:
        closing = text.rfind("</imgdir>")
        if closing < 0:
            raise RuntimeError("missing String.wz root closing imgdir")
        return text[:closing] + block + "\n" + text[closing:]


def remove_xml_block(text: str, node_name: str) -> str:
    try:
        start, end = find_imgdir_block(text, node_name)
    except RuntimeError:
        return text
    line_start = text.rfind("\n", 0, start) + 1
    if not text[line_start:start].strip():
        start = line_start
    return text[:start] + text[end:]


def patch_server_string(strings: WzSubProperty, dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    for skill_id in CUSTOM_SKILL_IDS:
        text = remove_xml_block(text, str(skill_id))
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
            if decode_canvas(node, region="GMS").getbbox() is None:
                raise RuntimeError(f"transparent canvas: {node.name}")
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
    for variant in ("0", "1"):
        cosmos_effect = root.get(f"skill/11121012/effect/{variant}")
        cosmos_z = cosmos_effect.child("z") if isinstance(cosmos_effect, WzSubProperty) else None
        if not isinstance(cosmos_z, WzIntProperty) or int(cosmos_z.value) != -1:
            raise RuntimeError(f"Cosmos effect/{variant} is not behind the character")
    print(f"validated client skills: canvases={count}, max={max_size[0]}x{max_size[1]}, ARGB4444 raw={raw / 1024 / 1024:.1f} MiB")

    map_image = WzImage.from_bytes(CLIENT_MAP_EFFECT.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name)
    map_root = map_image.parse()
    field_parent = map_root.get(FIELD_EFFECT_ROOT)
    if not isinstance(field_parent, WzSubProperty):
        raise RuntimeError(f"missing field-effect root: {FIELD_EFFECT_ROOT}")
    field_names = (
        "galaxyStarBurst",
        "galaxyStarBurstBackground",
        "fullEclipseMale",
        "fullEclipseFemale",
        "soulEclipse",
        *VIDEO_FIELD_MARKERS,
    )
    field_count = 0
    field_raw = 0
    field_frames: dict[str, list[WzCanvasProperty]] = {}
    for field_name in field_names:
        node = map_root.get(f"{FIELD_EFFECT_ROOT}/{field_name}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing field effect: {FIELD_EFFECT_ROOT}/{field_name}")
        frames = numeric_canvases(node)
        if not frames:
            raise RuntimeError(f"empty field effect: {FIELD_EFFECT_ROOT}/{field_name}")
        field_frames[field_name] = frames
        duration = 0
        for frame in frames:
            if int(frame.format) != CANVAS_FORMAT or int(frame.format2) != 0:
                raise RuntimeError(f"non-ARGB4444 field canvas: {field_name}/{frame.name}")
            if int(frame.width) > SCREEN_WIDTH or int(frame.height) > SCREEN_HEIGHT:
                raise RuntimeError(f"oversized field canvas: {field_name}/{frame.name} {frame.width}x{frame.height}")
            if decode_canvas(frame, region="GMS").getbbox() is None:
                raise RuntimeError(f"transparent field canvas: {field_name}/{frame.name}")
            duration += frame_delay(frame)
            field_raw += int(frame.width) * int(frame.height) * 2
        field_count += len(frames)
        print(f"validated field effect: {field_name}, frames={len(frames)}, duration={duration}ms")
    galaxy_frames = field_frames["galaxyStarBurst"]
    if any((int(frame.width), int(frame.height)) != (SCREEN_WIDTH, SCREEN_HEIGHT) for frame in galaxy_frames):
        raise RuntimeError("Galaxy Star Burst does not cover the configured screen")
    for field_name in ("fullEclipseMale", "fullEclipseFemale"):
        frames = field_frames[field_name]
        if len(frames) != 52 or any(frame_delay(frame) != 60 for frame in frames[8:]):
            raise RuntimeError(f"{field_name} finisher is not the complete 44-frame source video")
        if any((int(frame.width), int(frame.height)) != (SCREEN_WIDTH, SCREEN_HEIGHT) for frame in frames[8:]):
            raise RuntimeError(f"{field_name} finisher does not cover the configured screen")
    if map_root.get(f"{FIELD_EFFECT_ROOT}/soulEclipseBackground") is not None:
        raise RuntimeError("obsolete Soul Eclipse blackout is still installed")
    print(f"validated field effects: canvases={field_count}, ARGB4444 raw={field_raw / 1024 / 1024:.1f} MiB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--install-map-stage", type=Path)
    args = parser.parse_args()
    if args.install_map_stage is not None:
        install_map_effect_stage(args.install_map_stage, MsMetadata.load(), args.dry_run)
        return 0
    if args.validate_only:
        validate_client_outputs()
        return 0
    groups, strings, metadata = load_sources()
    patch_client_skill(groups, metadata, args.dry_run)
    patch_client_string(strings, args.dry_run)
    patch_server_skill(args.dry_run)
    patch_server_string(strings, args.dry_run)
    del strings
    gc.collect()
    patch_map_effect(groups, metadata, args.dry_run)
    if not args.dry_run:
        validate_client_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
