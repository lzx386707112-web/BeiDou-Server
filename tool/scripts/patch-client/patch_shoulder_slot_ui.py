#!/usr/bin/env python3
"""Add legacy-styled extended equipment slots to UIWindow.img/Equip/backgrnd."""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402


CLIENT_UI = ROOT / "clien/Data/UI/UIWindow.img"
KEY = WzKey.for_region("GMS")
TARGET_PARENT = "Equip"
TARGET_RECORD = "backgrnd"
TARGET_PATH = "Equip/backgrnd"
SLOT_SPECS = (
    ((137, 101, 169, 133), "肩饰"),
    ((104, 197, 136, 229), "副手"),
    ((71, 230, 103, 262), "心脏"),
    ((104, 230, 136, 262), "徽章"),
    ((137, 230, 169, 262), "纹章"),
)
TEMPLATE_RECT = (5, 133, 37, 165)
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
)


def load_image(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=KEY, name=CLIENT_UI.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed {CLIENT_UI}: {image.parse_warnings}")
    return image


def locate_root_records(image: WzImage, data: bytes):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported UIWindow.img header")
    reader.skip(2)
    count = reader.read_compressed_int()
    names = []
    spans = []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        if reader.read_byte() != 9:
            raise RuntimeError(f"unexpected root record type: {name}")
        size = reader.read_u32()
        reader.seek(reader.position + size)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != len(data):
        raise RuntimeError("UIWindow.img root records do not fill the file")
    return tuple(names), tuple(spans)


def locate_child_records(image: WzImage, data: bytes):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported UIWindow.img header")
    reader.skip(2)
    count = reader.read_compressed_int()
    for _ in range(count):
        name = reader.read_string_block(0)
        if reader.read_byte() != 9:
            raise RuntimeError(f"unexpected root record type: {name}")
        size_offset = reader.position
        block_size = reader.read_u32()
        block_end = reader.position + block_size
        if name != TARGET_PARENT:
            reader.seek(block_end)
            continue
        if reader.read_string_block(0) != "Property":
            raise RuntimeError(f"{TARGET_PARENT} is not a Property")
        reader.skip(2)
        child_count = reader.read_compressed_int()
        names = []
        spans = []
        for _ in range(child_count):
            start = reader.position
            child_name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag == 9:
                size = reader.read_u32()
                reader.seek(reader.position + size)
            elif tag == 0:
                pass
            elif tag in (2, 11):
                reader.skip(2)
            elif tag == 3:
                reader.read_compressed_int()
            elif tag == 20:
                reader.read_compressed_long()
            elif tag == 4:
                marker = reader.read_byte()
                if marker == 0x80:
                    reader.skip(4)
            elif tag == 5:
                reader.skip(8)
            elif tag == 8:
                reader.read_string_block(0)
            else:
                raise RuntimeError(f"unexpected {TARGET_PARENT} child {child_name}/{tag}")
            names.append(child_name)
            spans.append((start, reader.position))
        if reader.position != block_end:
            raise RuntimeError(f"{TARGET_PARENT} children do not fill their block")
        return size_offset, block_size, tuple(names), tuple(spans)
    raise RuntimeError(f"missing parent {TARGET_PARENT}")


def encode_record(node, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected property record prefix")
    return encoded[len(prefix):]


def native_slot_tile(pixels: Image.Image) -> Image.Image:
    tile = pixels.crop(TEMPLATE_RECT)
    pattern = tile.crop((12, 22, 16, 26))
    for y in range(1, 31, 4):
        for x in range(1, 31, 4):
            tile.paste(pattern, (x, y))
    return tile


def draw_label(tile: Image.Image, text: str) -> None:
    font_path = next((path for path in FONT_CANDIDATES if path.is_file()), None)
    if font_path is None:
        raise RuntimeError("no compatible Chinese UI font found")
    font = ImageFont.truetype(str(font_path), 11)
    draw = ImageDraw.Draw(tile)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
    x = (32 - (box[2] - box[0])) // 2 - box[0]
    draw.text(
        (x, 6), text, font=font, fill=(101, 135, 161, 255),
        stroke_width=1, stroke_fill=(239, 246, 250, 255),
    )


def expected_slot(pixels: Image.Image, text: str) -> Image.Image:
    tile = native_slot_tile(pixels)
    draw_label(tile, text)
    return tile.point(lambda value: (value >> 4) * 17)


def slots_are_present(pixels: Image.Image) -> bool:
    return all(pixels.crop(rect).tobytes() == expected_slot(pixels, text).tobytes()
               for rect, text in SLOT_SPECS)


def patch(data: bytes) -> bytes:
    image = load_image(data)
    canvas = image.root.get(TARGET_PATH)
    if not isinstance(canvas, WzCanvasProperty) or not canvas.has_pixels():
        raise RuntimeError(f"missing Canvas {TARGET_PATH}")
    if (canvas.format, canvas.format2) != (1, 0):
        raise RuntimeError(f"unsupported Canvas format: {(canvas.format, canvas.format2)}")
    pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
    if slots_are_present(pixels):
        return data
    for rect, text in SLOT_SPECS:
        pixels.paste(expected_slot(pixels, text), rect[:2])
    canvas._png_data = encode_canvas_payload(
        pixels, 1, canvas.width, canvas.height, key=KEY, listwz=False, zlib_level=9
    )
    canvas._png_length = len(canvas._png_data)

    size_offset, block_size, names, spans = locate_child_records(image, data)
    index = names.index(TARGET_RECORD)
    start, end = spans[index]
    replacement = encode_record(canvas, image)
    updated = bytearray(data[:start] + replacement + data[end:])
    delta = len(updated) - len(data)
    import struct
    struct.pack_into("<I", updated, size_offset, block_size + delta)
    updated = bytes(updated)

    verified = load_image(updated)
    _, _, new_names, new_spans = locate_child_records(verified, updated)
    if new_names != names:
        raise RuntimeError("UIWindow.img Equip child order changed")
    for name, old_span, new_span in zip(names, spans, new_spans):
        if name != TARGET_RECORD and data[slice(*old_span)] != updated[slice(*new_span)]:
            raise RuntimeError(f"unapproved Equip child record changed: {name}")
    old_root_names, old_root_spans = locate_root_records(image, data)
    new_root_names, new_root_spans = locate_root_records(verified, updated)
    if new_root_names != old_root_names:
        raise RuntimeError("UIWindow.img root record order changed")
    for name, old_span, new_span in zip(old_root_names, old_root_spans, new_root_spans):
        if name != TARGET_PARENT and data[slice(*old_span)] != updated[slice(*new_span)]:
            raise RuntimeError(f"unapproved root record changed: {name}")
    result = verified.root.get(TARGET_PATH)
    decoded = decode_canvas(result, region="GMS").convert("RGBA")
    if not slots_are_present(decoded):
        raise RuntimeError("generated extended equipment slots do not match")
    return updated


def main() -> None:
    original = CLIENT_UI.read_bytes()
    updated = patch(original)
    if updated != original:
        with tempfile.NamedTemporaryFile("wb", dir=CLIENT_UI.parent, delete=False) as handle:
            handle.write(updated)
            temporary = Path(handle.name)
        temporary.replace(CLIENT_UI)
    print(
        f"extended equipment UI ready: bytes={len(updated)} "
        f"sha256={hashlib.sha256(updated).hexdigest()}"
    )


if __name__ == "__main__":
    main()
