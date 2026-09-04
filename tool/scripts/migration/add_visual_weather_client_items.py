#!/usr/bin/env python3
"""Append the five visual-weather art pointers without rewriting 0512.img."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402

CLIENT_ITEM = ROOT / "clien/Data/Item/Cash/0512.img"
GMS_KEY = WzKey.for_region("GMS")
ITEMS = {
    "05120995": ("Effect/WeatherParticles.img/snowFall", 3),
    "05120996": ("Effect/WeatherParticles.img/sandGrit", 6),
    "05120997": ("Effect/WeatherParticles.img/blizzardSnow", 4),
    "05120998": ("Effect/WeatherParticles.img/leafMix", 2),
    "05120999": ("Effect/WeatherParticles.img/blossomMix", 2),
}


def reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def make_node(name: str, path: str, speed: int) -> WzSubProperty:
    node = WzSubProperty(name)
    info = WzSubProperty("info", node)
    node.add(info)
    info.add(WzStringProperty("path", path, info))
    info.add(WzIntProperty("type", 2, info))
    info.add(WzIntProperty("speed", speed, info))
    info.add(WzIntProperty("cash", 1, info))
    return node


def encode_record(node: WzSubProperty) -> bytes:
    encoded = _encode_property_list((node,), reader())
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected property-list prefix")
    return encoded[len(prefix):]


def root_layout(data: bytes):
    image = WzImage.from_bytes(data, key=GMS_KEY, name=CLIENT_ITEM.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed IMG: {image.parse_warnings}")
    source = image.wz_file.reader
    source.seek(0)
    if source.read_byte() != 0x73 or source.read_string() != "Property":
        raise RuntimeError("unsupported IMG header")
    source.skip(2)
    count_offset = source.position
    count = source.read_compressed_int()
    count_end = source.position
    names = []
    spans = []
    for _ in range(count):
        start = source.position
        name = source.read_string_block(0)
        tag = source.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root record {name}/{tag}")
        size = source.read_u32()
        source.seek(source.position + size)
        names.append(name)
        spans.append((start, source.position))
    if source.position != len(data):
        raise RuntimeError("root records do not fill IMG")
    return count_offset, count_end, count, tuple(names), tuple(spans)


def patch(data: bytes) -> bytes:
    count_offset, count_end, count, names, spans = root_layout(data)
    existing = {name: data[start:end] for name, (start, end) in zip(names, spans)}
    additions = {name: encode_record(make_node(name, path, speed))
                 for name, (path, speed) in ITEMS.items()}
    new_names = list(names)
    for name in ITEMS:
        if name not in existing:
            new_names.append(name)
    records = [additions[name] if name in ITEMS else existing[name]
               for name in new_names]
    record_start = spans[0][0] if spans else count_end
    record_end = spans[-1][1] if spans else count_end
    result = (data[:count_offset] + encode_compressed_int(len(new_names))
              + data[count_end:record_start] + b"".join(records) + data[record_end:])

    _, _, verified_count, verified_names, verified_spans = root_layout(result)
    verified = {name: result[start:end]
                for name, (start, end) in zip(verified_names, verified_spans)}
    if verified_count != count + sum(name not in existing for name in ITEMS):
        raise RuntimeError("root record count mismatch")
    if verified_names != tuple(new_names):
        raise RuntimeError("root property order changed")
    for name, raw in existing.items():
        if name not in ITEMS and verified[name] != raw:
            raise RuntimeError(f"protected record changed: {name}")
    for name, expected in additions.items():
        if verified[name] != expected:
            raise RuntimeError(f"weather record mismatch: {name}")
    return result


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    original = CLIENT_ITEM.read_bytes()
    updated = patch(original)
    if updated != original:
        atomic_write(CLIENT_ITEM, updated)
    print("visual weather art pointers verified: 05120995..05120999")


if __name__ == "__main__":
    main()
