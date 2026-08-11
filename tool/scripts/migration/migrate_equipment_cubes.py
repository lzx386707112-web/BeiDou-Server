#!/usr/bin/env python3
"""Project selected TMS cube icons onto the legacy magic-powder item IDs."""

from __future__ import annotations

import io
import re
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool/wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402


TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
TMS_ITEM = TMS_DATA / "Item/Cash/0506.img"
TMS_CANVAS = TMS_DATA / "Item/Cash/_Canvas/0506.img"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0400.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
GMS_KEY = WzKey.for_region("GMS")
BMS_KEY = WzKey.for_region("BMS")
ICON_SIZE = (31, 31)
ICON_ORIGIN = (-1, 31)


@dataclass(frozen=True)
class CubeSpec:
    item_id: int
    source_id: int
    name: str
    max_grade: str
    rare_rate: int
    unique_rate: int
    legendary_rate: int
    can_keep_old: bool = False

    @property
    def item_node(self) -> str:
        return f"0{self.item_id}"

    @property
    def description(self) -> str:
        choice = "使用后可以在原词条和新词条中选择。\\n" if self.can_keep_old else ""
        return (
            f"在装备中心使用的{self.name}。每次都会重新生成魔方词条，最高可达到{self.max_grade}强度。\\n"
            f"特殊/稀有/罕见升阶率：{self.rare_rate}%/{self.unique_rate}%/{self.legendary_rate}%。\\n"
            f"{choice}不影响卷轴、星级和装备升级属性。"
        )


CUBES = (
    CubeSpec(4007000, 5062000, "奇幻魔方", "罕见", 12, 6, 0),
    CubeSpec(4007001, 5062006, "白金奇幻魔方", "传说", 20, 10, 3),
    CubeSpec(4007002, 5062001, "超级奇幻魔方", "罕见", 18, 8, 0),
    CubeSpec(4007003, 5062004, "星星魔方", "罕见", 20, 10, 0),
    CubeSpec(4007004, 5062013, "太阳魔方", "传说", 25, 12, 4),
    CubeSpec(4007005, 5062002, "传说魔方", "传说", 18, 8, 2),
    CubeSpec(4007006, 5062009, "红色魔方", "传说", 15, 6, 1),
    CubeSpec(4007007, 5062010, "黑色魔方", "传说", 20, 8, 2, True),
)
TARGET_ITEM_NODES = frozenset(spec.item_node for spec in CUBES)
TARGET_STRING_NODES = frozenset(str(spec.item_id) for spec in CUBES)


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed IMG {path}: {image.parse_warnings}")
    return image


def atomic_write(path: Path, data: bytes | str) -> None:
    mode = "wb" if isinstance(data, bytes) else "w"
    kwargs = {} if isinstance(data, bytes) else {"encoding": "utf-8"}
    with tempfile.NamedTemporaryFile(mode, dir=path.parent, delete=False, **kwargs) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def encode_record(node: WzSubProperty, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected property record prefix")
    return encoded[len(prefix):]


def locate_root_records(image: WzImage, data: bytes):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported IMG header: {image.name}")
    reader.skip(2)
    count = reader.read_compressed_int()
    names = []
    spans = []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root record {name}/{tag}")
        size = reader.read_u32()
        reader.seek(reader.position + size)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != len(data):
        raise RuntimeError(f"root records do not fill {image.name}")
    return tuple(names), tuple(spans)


def locate_child_records(image: WzImage, data: bytes, parent_name: str):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported IMG header: {image.name}")
    reader.skip(2)
    root_count = reader.read_compressed_int()
    for _ in range(root_count):
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root record {name}/{tag}")
        size_offset = reader.position
        block_size = reader.read_u32()
        block_end = reader.position + block_size
        if name != parent_name:
            reader.seek(block_end)
            continue
        if reader.read_string_block(0) != "Property":
            raise RuntimeError(f"{parent_name} is not a Property")
        reader.skip(2)
        count = reader.read_compressed_int()
        names = []
        spans = []
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected {parent_name} record {child_name}/{child_tag}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            names.append(child_name)
            spans.append((start, reader.position))
        if reader.position != block_end:
            raise RuntimeError(f"{parent_name} records do not fill their block")
        return size_offset, block_size, tuple(names), tuple(spans)
    raise RuntimeError(f"missing parent {parent_name}")


def source_pixels(metadata: WzImage, canvases: WzImage, source_id: int, name: str) -> Image.Image:
    proxy = metadata.get(f"0{source_id}/info/{name}")
    if not isinstance(proxy, WzCanvasProperty):
        raise RuntimeError(f"missing TMS cube Canvas {source_id}/{name}")
    outlink = proxy.child("_outlink")
    if not isinstance(outlink, WzStringProperty):
        source = proxy
    else:
        marker = "0506.img/"
        value = str(outlink.value)
        if marker not in value:
            raise RuntimeError(f"unexpected TMS cube outlink: {value}")
        source = canvases.get(value.split(marker, 1)[1])
    if not isinstance(source, WzCanvasProperty) or not source.has_pixels():
        raise RuntimeError(f"unresolved TMS cube Canvas {source_id}/{name}")
    pixels = decode_canvas(source, region="BMS").convert("RGBA")
    pixels.thumbnail(ICON_SIZE, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
    output.alpha_composite(
        pixels,
        ((ICON_SIZE[0] - pixels.width) // 2, (ICON_SIZE[1] - pixels.height) // 2),
    )
    if output.getchannel("A").getbbox() is None:
        raise RuntimeError(f"TMS cube icon is transparent: {source_id}/{name}")
    return output


def make_canvas(name: str, parent: WzSubProperty, pixels: Image.Image) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = ICON_SIZE
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        pixels, 1, *ICON_SIZE, key=GMS_KEY, listwz=False, zlib_level=9
    )
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", *ICON_ORIGIN, canvas))
    return canvas


def make_item_node(spec: CubeSpec, metadata: WzImage, canvases: WzImage) -> WzSubProperty:
    item = WzSubProperty(spec.item_node)
    info = WzSubProperty("info", item)
    item.add(info)
    info.add(make_canvas("icon", info, source_pixels(metadata, canvases, spec.source_id, "icon")))
    info.add(make_canvas("iconRaw", info, source_pixels(metadata, canvases, spec.source_id, "iconRaw")))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 100, info))
    return item


def make_string_node(spec: CubeSpec) -> WzSubProperty:
    node = WzSubProperty(str(spec.item_id))
    node.add(WzStringProperty("desc", spec.description, node))
    node.add(WzStringProperty("name", spec.name, node))
    return node


def patch_client_items(nodes: dict[str, WzSubProperty]) -> None:
    original = CLIENT_ITEM.read_bytes()
    image = load_image(CLIENT_ITEM, GMS_KEY)
    names, spans = locate_root_records(image, original)
    raw = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    if not TARGET_ITEM_NODES.issubset(raw):
        raise RuntimeError("legacy client is missing one or more magic-powder records")
    replacements = {name: encode_record(node, image) for name, node in nodes.items()}
    rebuilt = b"".join(replacements.get(name, raw[name]) for name in names)
    start, end = spans[0][0], spans[-1][1]
    updated = original[:start] + rebuilt + original[end:]
    verified = load_image_bytes(updated, CLIENT_ITEM.name)
    new_names, new_spans = locate_root_records(verified, updated)
    new_raw = {name: updated[a:b] for name, (a, b) in zip(new_names, new_spans)}
    if new_names != names:
        raise RuntimeError("client item record order changed")
    for name in names:
        if name not in TARGET_ITEM_NODES and raw[name] != new_raw[name]:
            raise RuntimeError(f"unapproved client item record changed: {name}")
    atomic_write(CLIENT_ITEM, updated)


def patch_client_strings(nodes: dict[str, WzSubProperty]) -> None:
    original = CLIENT_STRING.read_bytes()
    image = load_image(CLIENT_STRING, GMS_KEY)
    size_offset, old_size, names, spans = locate_child_records(image, original, "Etc")
    raw = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    if not TARGET_STRING_NODES.issubset(raw):
        raise RuntimeError("legacy client is missing one or more magic-powder strings")
    replacements = {name: encode_record(node, image) for name, node in nodes.items()}
    rebuilt = b"".join(replacements.get(name, raw[name]) for name in names)
    start, end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:start] + rebuilt + original[end:])
    struct.pack_into("<I", updated, size_offset, old_size + len(updated) - len(original))
    result = bytes(updated)
    verified = load_image_bytes(result, CLIENT_STRING.name)
    _, _, new_names, new_spans = locate_child_records(verified, result, "Etc")
    new_raw = {name: result[a:b] for name, (a, b) in zip(new_names, new_spans)}
    if new_names != names:
        raise RuntimeError("client string record order changed")
    for name in names:
        if name not in TARGET_STRING_NODES and raw[name] != new_raw[name]:
            raise RuntimeError(f"unapproved client string record changed: {name}")
    atomic_write(CLIENT_STRING, result)


def load_image_bytes(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"generated malformed IMG {name}: {image.parse_warnings}")
    return image


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    match = re.search(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>', text)
    if match is None:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    start = match.start()
    depth = 0
    for tag_match in re.finditer(r"</?imgdir\b[^>]*>", text[start:]):
        tag = tag_match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, start + tag_match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def replace_xml_blocks(path: Path, blocks: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    spans = []
    for name, block in blocks.items():
        start, end = find_imgdir_block(text, name)
        spans.append((start, end, block))
    for start, end, block in sorted(spans, reverse=True):
        text = text[:start] + block + text[end:]
    atomic_write(path, text)


def item_xml(spec: CubeSpec) -> str:
    node = spec.item_node
    return (
        f'<imgdir name="{node}">\n'
        '    <imgdir name="info">\n'
        f'      <canvas name="icon" width="{ICON_SIZE[0]}" height="{ICON_SIZE[1]}" format="1">\n'
        f'        <vector name="origin" x="{ICON_ORIGIN[0]}" y="{ICON_ORIGIN[1]}"/>\n'
        '      </canvas>\n'
        f'      <canvas name="iconRaw" width="{ICON_SIZE[0]}" height="{ICON_SIZE[1]}" format="1">\n'
        f'        <vector name="origin" x="{ICON_ORIGIN[0]}" y="{ICON_ORIGIN[1]}"/>\n'
        '      </canvas>\n'
        '      <int name="price" value="1"/>\n'
        '      <int name="slotMax" value="100"/>\n'
        '    </imgdir>\n'
        '  </imgdir>'
    )


def string_xml(spec: CubeSpec) -> str:
    return (
        f'<imgdir name="{spec.item_id}">'
        f'<string name="desc" value={quoteattr(spec.description)}/>'
        f'<string name="name" value={quoteattr(spec.name)}/>'
        '</imgdir>'
    )


def verify(pixels: dict[tuple[int, str], Image.Image]) -> None:
    item = load_image(CLIENT_ITEM, GMS_KEY)
    strings = load_image(CLIENT_STRING, GMS_KEY)
    for spec in CUBES:
        for name in ("icon", "iconRaw"):
            canvas = item.get(f"{spec.item_node}/info/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"missing generated Canvas {spec.item_id}/{name}")
            if (canvas.width, canvas.height, canvas.format, canvas.format2) != (*ICON_SIZE, 1, 0):
                raise RuntimeError(f"incompatible generated Canvas {spec.item_id}/{name}")
            decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
            if decoded.getchannel("A").getbbox() is None:
                raise RuntimeError(f"transparent generated Canvas {spec.item_id}/{name}")
            expected = pixels[(spec.item_id, name)]
            if decoded.size != expected.size:
                raise RuntimeError(f"generated Canvas size mismatch {spec.item_id}/{name}")
        if strings.get(f"Etc/{spec.item_id}/name").value != spec.name:
            raise RuntimeError(f"client cube name mismatch: {spec.item_id}")
        if strings.get(f"Etc/{spec.item_id}/desc").value != spec.description:
            raise RuntimeError(f"client cube description mismatch: {spec.item_id}")


def main() -> None:
    metadata = load_image(TMS_ITEM, BMS_KEY)
    canvases = load_image(TMS_CANVAS, BMS_KEY)
    item_nodes = {spec.item_node: make_item_node(spec, metadata, canvases) for spec in CUBES}
    string_nodes = {str(spec.item_id): make_string_node(spec) for spec in CUBES}
    expected_pixels = {
        (spec.item_id, name): source_pixels(metadata, canvases, spec.source_id, name)
        for spec in CUBES
        for name in ("icon", "iconRaw")
    }

    patch_client_items(item_nodes)
    patch_client_strings(string_nodes)
    replace_xml_blocks(SERVER_ITEM, {spec.item_node: item_xml(spec) for spec in CUBES})
    blocks = {str(spec.item_id): string_xml(spec) for spec in CUBES}
    for path in SERVER_STRINGS:
        replace_xml_blocks(path, blocks)
    verify(expected_pixels)
    print("migrated 8 TMS cube icons onto 4007000-4007007 with raw-record preservation")


if __name__ == "__main__":
    main()
