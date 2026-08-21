#!/usr/bin/env python3
"""Add the mentorship EXP potion to legacy client IMG files incrementally."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

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
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402


SOURCE_ICON = Path("/Users/lizixian/Downloads/2003609.png")
CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0200.img"
CLIENT_STRING = ROOT / "clien/Data/String/Consume.img"
ITEM_NODE = "02003609"
STRING_NODE = "2003609"
ITEM_NAME = "经验秘药"
ITEM_DESC = "集成了炼金术技术的神秘药水。使用后获得经验100万。"
ICON_SIZE = (32, 32)
ICON_ORIGIN = (-1, 31)
GMS_KEY = WzKey.for_region("GMS")


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def load_image(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed IMG {path}: {image.parse_warnings}")
    return image


def encode_record(node: WzSubProperty) -> bytes:
    encoded = _encode_property_list((node,), gms_reader())
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected encoded property list prefix")
    return encoded[len(prefix):]


def locate_root_records(image: WzImage, data: bytes):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported IMG header: {image.name}")
    reader.skip(2)
    count_offset = reader.position
    count = reader.read_compressed_int()
    count_end = reader.position

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
    return count_offset, count_end, count, tuple(names), tuple(spans)


def upsert_root_record(path: Path, node: WzSubProperty) -> None:
    original = path.read_bytes()
    image = load_image(path)
    count_offset, count_end, count, names, spans = locate_root_records(image, original)
    raw = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    new_record = encode_record(node)
    new_count = count if node.name in raw else count + 1
    new_count_bytes = encode_compressed_int(new_count)

    rebuilt = bytearray()
    for name in names:
        rebuilt += new_record if name == node.name else raw[name]
    if node.name not in raw:
        rebuilt += new_record

    record_start = spans[0][0] if spans else count_end
    record_end = spans[-1][1] if spans else count_end
    updated = (
        original[:count_offset]
        + new_count_bytes
        + original[count_end:record_start]
        + bytes(rebuilt)
        + original[record_end:]
    )

    verified = WzImage.from_bytes(updated, key=GMS_KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"generated malformed IMG {path}: {verified.parse_warnings}")
    _, _, verified_count, verified_names, verified_spans = locate_root_records(verified, updated)
    if verified_count != new_count:
        raise RuntimeError(f"root count mismatch in {path}")
    expected_names = tuple(names) if node.name in raw else tuple(names) + (node.name,)
    if verified_names != expected_names:
        raise RuntimeError(f"root record order changed unexpectedly in {path}")

    verified_raw = {
        name: updated[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name in names:
        if name != node.name and raw[name] != verified_raw[name]:
            raise RuntimeError(f"unapproved root record changed in {path}: {name}")
    if verified_raw[node.name] != new_record:
        raise RuntimeError(f"new record mismatch in {path}: {node.name}")

    if updated != original:
        atomic_write(path, updated)


def source_pixels() -> Image.Image:
    if not SOURCE_ICON.exists():
        raise RuntimeError(f"missing source icon: {SOURCE_ICON}")
    pixels = Image.open(SOURCE_ICON).convert("RGBA")
    if pixels.size != ICON_SIZE:
        raise RuntimeError(f"expected {ICON_SIZE[0]}x{ICON_SIZE[1]} icon, got {pixels.size}")
    if pixels.getchannel("A").getbbox() is None:
        raise RuntimeError("source icon is fully transparent")
    return pixels


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


def make_item_node(pixels: Image.Image) -> WzSubProperty:
    item = WzSubProperty(ITEM_NODE)
    info = WzSubProperty("info", item)
    spec = WzSubProperty("spec", item)
    item.add(info)
    item.add(spec)
    info.add(make_canvas("icon", info, pixels))
    info.add(make_canvas("iconRaw", info, pixels))
    info.add(WzIntProperty("notSale", 1, info))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 100, info))
    spec.add(WzIntProperty("exp", 1000000, spec))
    return item


def make_string_node() -> WzSubProperty:
    node = WzSubProperty(STRING_NODE)
    node.add(WzStringProperty("name", ITEM_NAME, node))
    node.add(WzStringProperty("desc", ITEM_DESC, node))
    return node


def verify_client(pixels: Image.Image) -> None:
    item_image = load_image(CLIENT_ITEM)
    string_image = load_image(CLIENT_STRING)

    if item_image.get(f"{ITEM_NODE}/spec/exp").value != 1000000:
        raise RuntimeError("invalid client potion exp")
    for name in ("icon", "iconRaw"):
        canvas = item_image.get(f"{ITEM_NODE}/info/{name}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing client Canvas {ITEM_NODE}/{name}")
        if (canvas.width, canvas.height, canvas.format, canvas.format2) != (*ICON_SIZE, 1, 0):
            raise RuntimeError(f"incompatible client Canvas {ITEM_NODE}/{name}")
        decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
        if decoded.getchannel("A").getbbox() is None:
            raise RuntimeError(f"transparent client Canvas {ITEM_NODE}/{name}")

    if string_image.get(f"{STRING_NODE}/name").value != ITEM_NAME:
        raise RuntimeError("invalid client potion name")
    if string_image.get(f"{STRING_NODE}/desc").value != ITEM_DESC:
        raise RuntimeError("invalid client potion description")


def main() -> None:
    pixels = source_pixels()
    upsert_root_record(CLIENT_ITEM, make_item_node(pixels))
    upsert_root_record(CLIENT_STRING, make_string_node())
    verify_client(pixels)
    print("added client mentorship EXP potion 2003609 with raw-record preservation")


if __name__ == "__main__":
    main()
