#!/usr/bin/env python3
"""Repair the legacy-client attack contract on Arcane River mob 8641002."""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import _read_canvas_bytes, decode_canvas  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402


CLIENT = ROOT / "clien/Data/Mob/8641002.img"
SERVER = ROOT / "gms-server/wz/Mob.wz/8641002.img.xml"
BACKUP_ROOT = Path("/private/tmp/beidou-450001014-attack-gap-backup")
KEY = WzKey.for_region("GMS")
EXPECTED_ROOTS = ("info", "stand", "move", "attack1", "hit1", "die1")
EXPECTED_ATTACK_CHILDREN = ("info", *(str(index) for index in range(16)))
EXPECTED_ATTACK_INFO_CHILDREN = (
    "range", "ball", "hit", "type", "attackAfter", "bulletSpeed"
)
EXPECTED_ATTACK_INFO_VALUES = {"type": 2, "bulletSpeed": 300}


@dataclass(frozen=True)
class Record:
    name: str
    start: int
    end: int
    tag: int
    size_offset: int | None = None
    block_start: int | None = None
    block_size: int | None = None


@dataclass(frozen=True)
class PropertyList:
    count_offset: int
    count_length: int
    count: int
    records: tuple[Record, ...]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes | str) -> None:
    mode = "wb" if isinstance(data, bytes) else "w"
    kwargs = {} if isinstance(data, bytes) else {"encoding": "utf-8"}
    with tempfile.NamedTemporaryFile(
        mode, prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False, **kwargs
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def backup(path: Path) -> None:
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def load_image(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=KEY, name=CLIENT.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {CLIENT}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def skip_record_body(reader: WzBinaryReader, tag: int) -> None:
    if tag == 0:
        return
    if tag in (2, 11):
        reader.skip(2)
        return
    if tag in (3, 19):
        reader.read_compressed_int()
        return
    if tag == 20:
        reader.read_compressed_long()
        return
    if tag == 4:
        if reader.read_byte() == 0x80:
            reader.skip(4)
        return
    if tag == 5:
        reader.skip(8)
        return
    if tag == 8:
        reader.read_string_block(0)
        return
    raise RuntimeError(f"unsupported property tag {tag} at 0x{reader.position - 1:X}")


def read_property_list(reader: WzBinaryReader, block_end: int) -> PropertyList:
    count_offset = reader.position
    count = reader.read_compressed_int()
    count_length = reader.position - count_offset
    records: list[Record] = []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag == 9:
            size_offset = reader.position
            block_size = reader.read_u32()
            block_start = reader.position
            reader.seek(block_start + block_size)
            records.append(
                Record(name, start, reader.position, tag, size_offset, block_start, block_size)
            )
        else:
            skip_record_body(reader, tag)
            records.append(Record(name, start, reader.position, tag))
    if reader.position != block_end:
        raise RuntimeError(
            f"property list ends at 0x{reader.position:X}, expected 0x{block_end:X}"
        )
    return PropertyList(count_offset, count_length, count, tuple(records))


def locate_lists(data: bytes) -> tuple[PropertyList, Record, PropertyList]:
    reader = WzBinaryReader(io.BytesIO(data), KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported IMG header: {CLIENT}")
    reader.skip(2)
    roots = read_property_list(reader, len(data))
    if tuple(record.name for record in roots.records) != EXPECTED_ROOTS:
        raise RuntimeError(f"unexpected root order: {[record.name for record in roots.records]}")
    attack = next(record for record in roots.records if record.name == "attack1")
    if attack.tag != 9 or attack.block_start is None or attack.block_size is None:
        raise RuntimeError("attack1 is not an extended Property block")
    reader.seek(attack.block_start)
    if reader.read_string_block(0) != "Property":
        raise RuntimeError("attack1 body is not a Property block")
    reader.skip(2)
    children = read_property_list(reader, attack.block_start + attack.block_size)
    return roots, attack, children


def locate_attack_info_list(data: bytes) -> tuple[Record, Record, PropertyList]:
    _, attack, attack_children = locate_lists(data)
    info = next(record for record in attack_children.records if record.name == "info")
    if info.tag != 9 or info.block_start is None or info.block_size is None:
        raise RuntimeError("attack1/info is not an extended Property block")
    reader = WzBinaryReader(io.BytesIO(data), KEY)
    reader.seek(info.block_start)
    if reader.read_string_block(0) != "Property":
        raise RuntimeError("attack1/info body is not a Property block")
    reader.skip(2)
    children = read_property_list(reader, info.block_start + info.block_size)
    return attack, info, children


def clone_property(source, name: str, parent):
    if isinstance(source, WzCanvasProperty):
        clone = WzCanvasProperty(name, parent)
        clone.width, clone.height = int(source.width), int(source.height)
        clone.format, clone.format2 = int(source.format), int(source.format2)
        clone._png_data = bytes(_read_canvas_bytes(source))
        clone._png_length = len(clone._png_data)
        for child in source.children():
            clone.add(clone_property(child, child.name, clone))
        return clone
    if isinstance(source, WzSubProperty):
        clone = WzSubProperty(name, parent)
        for child in source.children():
            clone.add(clone_property(child, child.name, clone))
        return clone
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(name, int(source.value), parent)
    if isinstance(source, WzLongProperty):
        return WzLongProperty(name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(name, float(source.value), parent)
    if isinstance(source, WzDoubleProperty):
        return WzDoubleProperty(name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(name, str(source.value), parent)
    if isinstance(source, WzNullProperty):
        return WzNullProperty(name, parent)
    raise RuntimeError(f"unsupported frame metadata type: {type(source).__name__}")


def encode_frame10(image: WzImage) -> bytes:
    attack = image.root.child("attack1")
    frame9 = attack.child("9") if isinstance(attack, WzSubProperty) else None
    if not isinstance(frame9, WzCanvasProperty):
        raise RuntimeError("missing attack1/9 Canvas template")
    frame10 = clone_property(frame9, "10", attack)
    encoded = _encode_property_list((frame10,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected encoded frame record prefix")
    return encoded[len(prefix):]


def encode_int_record(image: WzImage, name: str, value: int, parent) -> bytes:
    encoded = _encode_property_list(
        (WzIntProperty(name, value, parent),), image.wz_file.reader
    )
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"unexpected encoded {name} record prefix")
    return encoded[len(prefix):]


def patch_attack_info(data: bytes) -> tuple[bytes, str]:
    image = load_image(data)
    attack, info, children = locate_attack_info_list(data)
    names = tuple(record.name for record in children.records)
    for name in EXPECTED_ATTACK_INFO_VALUES:
        if names.count(name) > 1:
            raise RuntimeError(f"duplicate attack1/info/{name}: {names}")
    existing_base = tuple(
        name for name in names if name not in EXPECTED_ATTACK_INFO_VALUES
    )
    expected_base = tuple(
        name for name in EXPECTED_ATTACK_INFO_CHILDREN
        if name not in EXPECTED_ATTACK_INFO_VALUES
    )
    if existing_base != expected_base:
        raise RuntimeError(f"unexpected attack1/info order: {names}")
    for name, value in EXPECTED_ATTACK_INFO_VALUES.items():
        current = image.root.get(f"attack1/info/{name}")
        if current is not None and (
            not isinstance(current, WzIntProperty) or int(current.value) != value
        ):
            raise RuntimeError(f"unexpected attack1/info/{name}={current.value}")
    if names == EXPECTED_ATTACK_INFO_CHILDREN:
        return data, "metadata-present"

    parent = image.root.get("attack1/info")
    raw = {record.name: data[record.start:record.end] for record in children.records}
    for name, value in EXPECTED_ATTACK_INFO_VALUES.items():
        if name not in raw:
            raw[name] = encode_int_record(image, name, value, parent)
    rebuilt = b"".join(raw[name] for name in EXPECTED_ATTACK_INFO_CHILDREN)
    records_start = children.records[0].start
    records_end = children.records[-1].end
    updated = bytearray(data[:records_start] + rebuilt + data[records_end:])
    delta = len(updated) - len(data)
    new_count = encode_compressed_int(len(EXPECTED_ATTACK_INFO_CHILDREN))
    if len(new_count) != children.count_length:
        raise RuntimeError("attack1/info child-count encoding width changed")
    updated[children.count_offset:children.count_offset + children.count_length] = new_count
    if info.size_offset is None or info.block_size is None:
        raise AssertionError("attack1/info span lost its size field")
    if attack.size_offset is None or attack.block_size is None:
        raise AssertionError("attack1 span lost its size field")
    struct.pack_into("<I", updated, info.size_offset, info.block_size + delta)
    struct.pack_into("<I", updated, attack.size_offset, attack.block_size + delta)
    return bytes(updated), "metadata-inserted"


def patch_attach(data: bytes) -> bytes:
    image = load_image(data)
    attach = image.root.get("attack1/info/hit/attach")
    if not isinstance(attach, WzIntProperty):
        raise RuntimeError("missing attack1/info/hit/attach")
    if int(attach.value) == 1:
        return data
    if int(attach.value) != 0 or attach._value_offset is None or attach._value_length != 1:
        raise RuntimeError(f"cannot restore attack1/info/hit/attach={attach.value} in place")
    updated = bytearray(data)
    updated[attach._value_offset] = 1
    return bytes(updated)


def frame_signature(image: WzImage, name: str) -> tuple:
    frame = image.root.get(f"attack1/{name}")
    if not isinstance(frame, WzCanvasProperty):
        raise RuntimeError(f"attack1/{name} is not a Canvas")
    metadata = tuple(
        (child.name, child.type_name, getattr(child, "x", None), getattr(child, "y", None), child.value)
        for child in frame.children()
    )
    pixels = decode_canvas(frame, region="GMS").convert("RGBA")
    return (
        int(frame.width),
        int(frame.height),
        int(frame.format),
        int(frame.format2),
        metadata,
        sha256(_read_canvas_bytes(frame)),
        sha256(pixels.tobytes()),
    )


def patch_client(data: bytes) -> tuple[bytes, str]:
    before_roots, _, _ = locate_lists(data)
    result, metadata_action = patch_attack_info(data)
    working_image = load_image(result)
    _, attack, children = locate_lists(result)
    names = tuple(record.name for record in children.records)
    if names.count("10") > 1:
        raise RuntimeError(f"duplicate attack1/10 records: {names}")
    without10 = tuple(name for name in names if name != "10")
    expected_without10 = tuple(name for name in EXPECTED_ATTACK_CHILDREN if name != "10")
    if without10 != expected_without10:
        raise RuntimeError(f"unexpected attack1 order: {names}")

    raw = {record.name: result[record.start:record.end] for record in children.records}
    action = "already-ordered"
    if names != EXPECTED_ATTACK_CHILDREN:
        if "10" not in raw:
            raw["10"] = encode_frame10(working_image)
            action = "inserted-frame10"
        else:
            action = "moved-frame10"
        rebuilt = b"".join(raw[name] for name in EXPECTED_ATTACK_CHILDREN)
        records_start = children.records[0].start
        records_end = children.records[-1].end
        updated = bytearray(result[:records_start] + rebuilt + result[records_end:])
        delta = len(updated) - len(result)
        new_count = encode_compressed_int(len(EXPECTED_ATTACK_CHILDREN))
        if len(new_count) != children.count_length:
            raise RuntimeError("attack1 child-count encoding width changed")
        updated[children.count_offset:children.count_offset + children.count_length] = new_count
        if attack.size_offset is None or attack.block_size is None:
            raise AssertionError("attack1 span lost its size field")
        struct.pack_into("<I", updated, attack.size_offset, attack.block_size + delta)
        result = bytes(updated)

    result = patch_attach(result)
    after_image = load_image(result)
    after_roots, _, after_children = locate_lists(result)
    if tuple(record.name for record in after_children.records) != EXPECTED_ATTACK_CHILDREN:
        raise RuntimeError("attack1 frame order is not legacy-contiguous after repair")
    if frame_signature(after_image, "9") != frame_signature(after_image, "10"):
        raise RuntimeError("attack1/10 is not an exact visual clone of attack1/9")
    attach = after_image.root.get("attack1/info/hit/attach")
    if not isinstance(attach, WzIntProperty) or int(attach.value) != 1:
        raise RuntimeError("attack1/info/hit/attach was not restored to 1")
    info = after_image.root.get("attack1/info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError("attack1/info is missing after repair")
    if tuple(child.name for child in info.children()) != EXPECTED_ATTACK_INFO_CHILDREN:
        raise RuntimeError("attack1/info metadata order remains invalid")
    for name, value in EXPECTED_ATTACK_INFO_VALUES.items():
        node = info.child(name)
        if not isinstance(node, WzIntProperty) or int(node.value) != value:
            raise RuntimeError(f"attack1/info/{name} was not restored to {value}")

    before_root_raw = {
        record.name: data[record.start:record.end] for record in before_roots.records
    }
    after_root_raw = {
        record.name: result[record.start:record.end] for record in after_roots.records
    }
    for name in EXPECTED_ROOTS:
        if name != "attack1" and before_root_raw[name] != after_root_raw[name]:
            raise RuntimeError(f"unapproved client root record changed: {name}")
    return result, f"{metadata_action},{action}"


def find_node_span(text: str, tag: str, name: str, start: int, limit: int) -> tuple[int, int]:
    marker = re.compile(rf'<{tag}\b[^>]*\bname="{re.escape(name)}"[^>]*>')
    match = marker.search(text, start, limit)
    if match is None:
        raise RuntimeError(f"missing XML node {tag}/{name}")
    node_start = match.start()
    depth = 0
    token = re.compile(rf'</?{tag}\b[^>]*>')
    for candidate in token.finditer(text, node_start, limit):
        value = candidate.group(0)
        if value.startswith("</"):
            depth -= 1
            if depth == 0:
                return node_start, candidate.end()
        elif not value.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML node {tag}/{name}")


def patch_server(text: str) -> tuple[str, str]:
    root = ET.fromstring(text)
    attack = root.find('./imgdir[@name="attack1"]')
    if attack is None:
        raise RuntimeError("server XML is missing attack1")
    names = tuple(child.get("name") for child in attack)
    if names.count("10") > 1:
        raise RuntimeError(f"server XML has duplicate attack1/10: {names}")
    without10 = tuple(name for name in names if name != "10")
    expected_without10 = tuple(name for name in EXPECTED_ATTACK_CHILDREN if name != "10")
    if without10 != expected_without10:
        raise RuntimeError(f"unexpected server attack1 order: {names}")
    xml_info = attack.find('./imgdir[@name="info"]')
    if xml_info is None:
        raise RuntimeError("server XML is missing attack1/info")
    for name, value in EXPECTED_ATTACK_INFO_VALUES.items():
        node = xml_info.find(f'./int[@name="{name}"]')
        if node is not None and node.get("value") != str(value):
            raise RuntimeError(f"unexpected server attack1/info/{name}={node.get('value')}")

    attack_start, attack_end = find_node_span(text, "imgdir", "attack1", 0, len(text))
    info_start, info_end = find_node_span(text, "imgdir", "info", attack_start, attack_end)
    info_text = text[info_start:info_end]
    if '<int name="attach" value="0"/>' in info_text:
        info_text = info_text.replace(
            '<int name="attach" value="0"/>', '<int name="attach" value="1"/>', 1
        )
        text = text[:info_start] + info_text + text[info_end:]
    elif '<int name="attach" value="1"/>' not in info_text:
        raise RuntimeError("server XML attack1/info/hit/attach is not 0 or 1")

    metadata_action = "metadata-present"
    attack_start, attack_end = find_node_span(text, "imgdir", "attack1", 0, len(text))
    info_start, info_end = find_node_span(text, "imgdir", "info", attack_start, attack_end)
    info_text = text[info_start:info_end]
    if '<int name="type" value="2"/>' not in info_text:
        _, hit_end = find_node_span(info_text, "imgdir", "hit", 0, len(info_text))
        info_text = (
            info_text[:hit_end]
            + '\n      <int name="type" value="2"/>'
            + info_text[hit_end:]
        )
        metadata_action = "metadata-inserted"
    if '<int name="bulletSpeed" value="300"/>' not in info_text:
        marker = '<int name="attackAfter" value="1260"/>'
        if marker not in info_text:
            raise RuntimeError("server XML has unexpected attack1/info/attackAfter")
        info_text = info_text.replace(
            marker, marker + '\n      <int name="bulletSpeed" value="300"/>', 1
        )
        metadata_action = "metadata-inserted"
    text = text[:info_start] + info_text + text[info_end:]

    attack_start, attack_end = find_node_span(text, "imgdir", "attack1", 0, len(text))
    _, info_end = find_node_span(text, "imgdir", "info", attack_start, attack_end)
    frame_spans = {
        name: find_node_span(text, "canvas", name, info_end, attack_end)
        for name in names
        if name != "info"
    }
    action = "already-ordered"
    if names != EXPECTED_ATTACK_CHILDREN:
        if "10" in frame_spans:
            frame_start, frame_end = frame_spans["10"]
            frame10 = text[frame_start:frame_end]
            text = text[:frame_start] + text[frame_end:]
            action = "moved-frame10"
        else:
            frame9_start, frame9_end = frame_spans["9"]
            frame10 = text[frame9_start:frame9_end].replace(
                '<canvas name="9"', '<canvas name="10"', 1
            )
            action = "inserted-frame10"
        attack_start, attack_end = find_node_span(text, "imgdir", "attack1", 0, len(text))
        _, info_end = find_node_span(text, "imgdir", "info", attack_start, attack_end)
        frame9_start, frame9_end = find_node_span(text, "canvas", "9", info_end, attack_end)
        text = text[:frame9_end] + "\n    " + frame10 + text[frame9_end:]

    verified = ET.fromstring(text)
    verified_attack = verified.find('./imgdir[@name="attack1"]')
    verified_names = (
        tuple(child.get("name") for child in verified_attack)
        if verified_attack is not None
        else ()
    )
    if verified_names != EXPECTED_ATTACK_CHILDREN:
        raise RuntimeError(f"server XML attack1 order remains invalid: {verified_names}")
    attach = verified.find(
        './imgdir[@name="attack1"]/imgdir[@name="info"]/imgdir[@name="hit"]/'
        'int[@name="attach"]'
    )
    if attach is None or attach.get("value") != "1":
        raise RuntimeError("server XML attack1/info/hit/attach was not restored to 1")
    verified_info = verified.find('./imgdir[@name="attack1"]/imgdir[@name="info"]')
    verified_info_names = (
        tuple(child.get("name") for child in verified_info)
        if verified_info is not None
        else ()
    )
    if verified_info_names != EXPECTED_ATTACK_INFO_CHILDREN:
        raise RuntimeError(f"server XML attack1/info order remains invalid: {verified_info_names}")
    for name, value in EXPECTED_ATTACK_INFO_VALUES.items():
        node = verified_info.find(f'./int[@name="{name}"]')
        if node is None or node.get("value") != str(value):
            raise RuntimeError(f"server XML attack1/info/{name} was not restored")
    frame9 = verified_attack.find('./canvas[@name="9"]')
    frame10 = verified_attack.find('./canvas[@name="10"]')
    if frame9 is None or frame10 is None:
        raise RuntimeError("server XML is missing attack1/9 or attack1/10")
    frame9_signature = (
        tuple(sorted((name, value) for name, value in frame9.attrib.items() if name != "name")),
        tuple(ET.tostring(child, encoding="unicode") for child in frame9),
    )
    frame10_signature = (
        tuple(sorted((name, value) for name, value in frame10.attrib.items() if name != "name")),
        tuple(ET.tostring(child, encoding="unicode") for child in frame10),
    )
    if frame9_signature != frame10_signature:
        raise RuntimeError("server XML attack1/10 is not an exact clone of attack1/9")
    return text, f"{metadata_action},{action}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    client_before = CLIENT.read_bytes()
    server_before = SERVER.read_text(encoding="utf-8")
    client_after, client_action = patch_client(client_before)
    server_after, server_action = patch_server(server_before)
    changed = client_after != client_before or server_after != server_before
    if args.check and changed:
        raise SystemExit("8641002 legacy attack contract is not fully repaired")
    if not args.check and changed:
        backup(CLIENT)
        backup(SERVER)
        atomic_write(CLIENT, client_after)
        atomic_write(SERVER, server_after)
    print(
        f"8641002 legacy attack contract ok: client={client_action} server={server_action} "
        f"changed={changed} client_sha256={sha256(client_after)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
