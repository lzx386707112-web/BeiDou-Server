#!/usr/bin/env python3
"""Materialize Root Abyss boss gauge icon aliases for the legacy client."""

from __future__ import annotations

import hashlib
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402

from migrate_root_abyss_maps import clone_property, remove_child  # noqa: E402


CLIENT_UI = ROOT / "clien/Data/UI/UIWindow.img"
KEY = WzKey.for_region("GMS")
TARGET_PATH = ("MobGage", "Mob")
ALIASES = {
    "8900100": "8900000",
    "8910100": "8910000",
    "8920101": "8920000",
    "8920001": "8920000",
    "8930100": "8930000",
}


def load_image(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=KEY, name=CLIENT_UI.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed {CLIENT_UI}: {image.parse_warnings}")
    return image


def skip_record_body(reader, tag: int) -> None:
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
        raise RuntimeError(f"unexpected property tag: {tag}")


def read_property_records(reader, block_end: int):
    if reader.read_string_block(0) != "Property":
        raise RuntimeError("target block is not a Property")
    reader.skip(2)
    count = reader.read_compressed_int()
    names = []
    spans = []
    size_offsets = {}
    block_sizes = {}
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag == 9:
            size_offsets[name] = reader.position
            block_size = reader.read_u32()
            block_sizes[name] = block_size
            reader.seek(reader.position + block_size)
        else:
            skip_record_body(reader, tag)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != block_end:
        raise RuntimeError("property records do not fill their block")
    return tuple(names), tuple(spans), size_offsets, block_sizes


def locate_mob_gauge_records(image: WzImage, data: bytes):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported UIWindow.img header")
    reader.skip(2)
    root_count = reader.read_compressed_int()
    root_names = []
    root_spans = []
    mob_gage_size_offset = None
    mob_gage_block_size = None
    mob_gage_block_start = None
    mob_gage_block_end = None
    for _ in range(root_count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root record type: {name}/{tag}")
        size_offset = reader.position
        block_size = reader.read_u32()
        block_start = reader.position
        block_end = block_start + block_size
        reader.seek(block_end)
        root_names.append(name)
        root_spans.append((start, reader.position))
        if name == TARGET_PATH[0]:
            mob_gage_size_offset = size_offset
            mob_gage_block_size = block_size
            mob_gage_block_start = block_start
            mob_gage_block_end = block_end
    if reader.position != len(data):
        raise RuntimeError("UIWindow.img root records do not fill the file")
    if mob_gage_block_start is None:
        raise RuntimeError("missing MobGage")

    reader.seek(mob_gage_block_start)
    mob_gage_names, mob_gage_spans, mob_gage_size_offsets, mob_gage_block_sizes = read_property_records(
        reader, mob_gage_block_end
    )
    if TARGET_PATH[1] not in mob_gage_size_offsets:
        raise RuntimeError("missing MobGage/Mob")
    mob_size_offset = mob_gage_size_offsets[TARGET_PATH[1]]
    mob_block_size = mob_gage_block_sizes[TARGET_PATH[1]]
    mob_index = mob_gage_names.index(TARGET_PATH[1])
    mob_record_start, mob_record_end = mob_gage_spans[mob_index]
    mob_block_start = mob_size_offset + 4
    mob_block_end = mob_block_start + mob_block_size

    reader.seek(mob_block_start)
    mob_names, mob_spans, _, _ = read_property_records(reader, mob_block_end)
    return {
        "root_names": tuple(root_names),
        "root_spans": tuple(root_spans),
        "mob_gage_size_offset": mob_gage_size_offset,
        "mob_gage_block_size": mob_gage_block_size,
        "mob_gage_names": mob_gage_names,
        "mob_gage_spans": mob_gage_spans,
        "mob_record_span": (mob_record_start, mob_record_end),
        "mob_size_offset": mob_size_offset,
        "mob_block_size": mob_block_size,
        "mob_names": mob_names,
        "mob_spans": mob_spans,
    }


def encode_record(node, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected property record prefix")
    return encoded[len(prefix):]


def materialize_icons(image: WzImage) -> bool:
    mob_root = image.root.get("/".join(TARGET_PATH))
    if mob_root is None:
        raise RuntimeError("missing MobGage/Mob")
    changed = False
    for alias, target in ALIASES.items():
        template = mob_root.child(target)
        if not isinstance(template, WzCanvasProperty) or not template.has_pixels():
            raise RuntimeError(f"invalid boss gauge template {target}")
        clone = clone_property(template, alias, mob_root)
        remove_child(clone, "_inlink")
        remove_child(clone, "_outlink")
        mob_root._children[alias] = clone
        changed = True
    return changed


def patch(data: bytes) -> bytes:
    image = load_image(data)
    before = locate_mob_gauge_records(image, data)
    if not all(name in before["mob_names"] for name in ALIASES):
        missing = sorted(set(ALIASES) - set(before["mob_names"]))
        raise RuntimeError(f"missing MobGage aliases: {missing}")

    materialize_icons(image)
    mob_root = image.root.get("/".join(TARGET_PATH))
    replacements = {name: encode_record(mob_root.child(name), image) for name in ALIASES}

    rebuilt = bytearray()
    cursor = 0
    delta = 0
    for name, span in zip(before["mob_names"], before["mob_spans"]):
        start, end = span
        rebuilt += data[cursor:start]
        if name in replacements:
            replacement = replacements[name]
            rebuilt += replacement
            delta += len(replacement) - (end - start)
        else:
            rebuilt += data[start:end]
        cursor = end
    rebuilt += data[cursor:]
    if delta == 0:
        return data

    updated = bytearray(rebuilt)
    struct.pack_into("<I", updated, before["mob_size_offset"], before["mob_block_size"] + delta)
    struct.pack_into(
        "<I",
        updated,
        before["mob_gage_size_offset"],
        before["mob_gage_block_size"] + delta,
    )
    updated = bytes(updated)

    verified = load_image(updated)
    after = locate_mob_gauge_records(verified, updated)
    if after["root_names"] != before["root_names"]:
        raise RuntimeError("UIWindow root order changed")
    if after["mob_gage_names"] != before["mob_gage_names"]:
        raise RuntimeError("MobGage child order changed")
    if after["mob_names"] != before["mob_names"]:
        raise RuntimeError("MobGage/Mob child order changed")

    for name, old_span, new_span in zip(before["root_names"], before["root_spans"], after["root_spans"]):
        if name != TARGET_PATH[0] and data[slice(*old_span)] != updated[slice(*new_span)]:
            raise RuntimeError(f"unapproved root record changed: {name}")
    for name, old_span, new_span in zip(
        before["mob_gage_names"], before["mob_gage_spans"], after["mob_gage_spans"]
    ):
        if name != TARGET_PATH[1] and data[slice(*old_span)] != updated[slice(*new_span)]:
            raise RuntimeError(f"unapproved MobGage record changed: {name}")
    for name, old_span, new_span in zip(before["mob_names"], before["mob_spans"], after["mob_spans"]):
        if name not in ALIASES and data[slice(*old_span)] != updated[slice(*new_span)]:
            raise RuntimeError(f"unapproved MobGage/Mob record changed: {name}")

    for alias in ALIASES:
        node = verified.root.get(f"MobGage/Mob/{alias}")
        if not isinstance(node, WzCanvasProperty) or (node.format, node.format2) != (1, 0):
            raise RuntimeError(f"{alias}: not an ARGB4444 Canvas")
        if node.child("_inlink") is not None or node.child("_outlink") is not None:
            raise RuntimeError(f"{alias}: still uses a Canvas link")
        if decode_canvas(node, region="GMS").getbbox() is None:
            raise RuntimeError(f"{alias}: icon is transparent")
    return updated


def main() -> None:
    original = CLIENT_UI.read_bytes()
    updated = patch(original)
    if updated != original:
        with tempfile.NamedTemporaryFile("wb", dir=CLIENT_UI.parent, delete=False) as handle:
            handle.write(updated)
            temporary = Path(handle.name)
        temporary.replace(CLIENT_UI)
    print(f"Root Abyss boss gauge icons ready: bytes={len(updated)} sha256={hashlib.sha256(updated).hexdigest()}")


if __name__ == "__main__":
    main()
