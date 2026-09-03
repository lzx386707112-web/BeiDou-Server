#!/usr/bin/env python3
"""Install per-character damage-cap stones without reserializing legacy IMG files."""

from __future__ import annotations

import hashlib
import io
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402


SOURCE_ICON = Path("/Users/lizixian/Downloads/2614088.png")
CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0243.img"
CLIENT_STRING = ROOT / "clien/Data/String/Consume.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Consume/0243.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Consume.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Consume.img.xml",
)
CLIENT_DLL = ROOT / "clien/ijl15.dll"
ITEM_ANCHOR = "02436037"
STRING_ANCHOR = "2029006"
ITEM_DESCRIPTION = "使用后可以突破伤害上限的神秘宝石。"
SCRIPT_NAME = "damage_cap_breakthrough"
ICON_SIZE = (32, 32)
ICON_ORIGIN = (0, 32)


@dataclass(frozen=True)
class StoneSpec:
    item_id: int
    name: str
    increment: int

    @property
    def item_node(self) -> str:
        return f"0{self.item_id}"


STONES = (
    StoneSpec(2431152, "突破石30万 50%", 300_000),
    StoneSpec(2431153, "突破石50万 50%", 500_000),
    StoneSpec(2431154, "突破石200万 50%", 2_000_000),
    StoneSpec(2431155, "突破石1000万 50%", 10_000_000),
    StoneSpec(2431156, "突破石1亿 50%", 100_000_000),
    StoneSpec(2431157, "突破石5亿 50%", 500_000_000),
)
TARGET_ITEM_NODES = frozenset(spec.item_node for spec in STONES)
TARGET_STRING_NODES = frozenset(str(spec.item_id) for spec in STONES)


def load_client(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed IMG {path}: {image.parse_warnings}")
    return image


def source_pixels() -> Image.Image:
    if not SOURCE_ICON.is_file():
        raise RuntimeError(f"missing source icon: {SOURCE_ICON}")
    pixels = Image.open(SOURCE_ICON).convert("RGBA")
    if pixels.size != ICON_SIZE:
        raise RuntimeError(f"expected a 32x32 icon, got {pixels.size}")
    if pixels.getchannel("A").getbbox() is None:
        raise RuntimeError("source icon is fully transparent")
    return pixels


def make_canvas(name: str, parent: WzSubProperty, pixels: Image.Image) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = ICON_SIZE
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        pixels, 1, *ICON_SIZE, key=arc.GMS_KEY, listwz=False, zlib_level=9
    )
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", *ICON_ORIGIN, canvas))
    return canvas


def make_item_node(spec: StoneSpec, pixels: Image.Image) -> WzSubProperty:
    item = WzSubProperty(spec.item_node)
    info = WzSubProperty("info", item)
    item.add(info)
    info.add(make_canvas("icon", info, pixels))
    info.add(make_canvas("iconRaw", info, pixels))
    info.add(WzIntProperty("notSale", 1, info))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 100, info))
    info.add(WzIntProperty("tradeBlock", 1, info))
    spec_node = WzSubProperty("spec", item)
    item.add(spec_node)
    spec_node.add(WzIntProperty("npc", 9900001, spec_node))
    spec_node.add(WzStringProperty("script", SCRIPT_NAME, spec_node))
    return item


def make_string_node(spec: StoneSpec) -> WzSubProperty:
    node = WzSubProperty(str(spec.item_id))
    node.add(WzStringProperty("name", spec.name, node))
    node.add(WzStringProperty("desc", ITEM_DESCRIPTION, node))
    return node


def insert_client_records(
    path: Path,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
    anchor: str,
) -> bool:
    original = path.read_bytes()
    records, _ = arc.raw_record_state(original)
    missing = [node for node in nodes if (*parent_path, node.name) not in records]
    if not missing:
        return False
    updated = arc.insert_property_records_before(original, parent_path, missing, anchor)
    arc.verify_raw_record_insert_scope(
        original, updated, {(*parent_path, node.name) for node in missing}
    )
    arc.atomic_write_bytes(path, updated)
    return True


def insert_server_records(
    path: Path,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
    anchor: str,
) -> bool:
    original = path.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    parent = root
    for part in parent_path:
        parent = next(
            (child for child in parent if child.tag == "imgdir" and child.get("name") == part),
            None,
        )
        if parent is None:
            raise RuntimeError(f"missing XML parent {'/'.join(parent_path)} in {path}")
    existing = {child.get("name") for child in parent}
    missing = [node for node in nodes if node.name not in existing]
    if not missing:
        return False
    updated = arc.insert_xml_properties_before(original, parent_path, missing, anchor)
    ET.fromstring(updated)
    arc.atomic_write_text(path, updated)
    return True


def patch_client_dll() -> bool:
    original = CLIENT_DLL.read_bytes()
    updated = bytearray(original)
    patches = (
        (0x3416C, struct.pack("<i", 19_999_999), struct.pack("<i", 2_147_483_647)),
        (0x34170, struct.pack("<i", 19_999_999), struct.pack("<i", 2_147_483_647)),
        (0x34180, struct.pack("<d", 19_999_999.0), struct.pack("<d", 2_147_483_647.0)),
    )
    for offset, old, new in patches:
        current = bytes(updated[offset:offset + len(old)])
        if current == old:
            updated[offset:offset + len(old)] = new
        elif current != new:
            raise RuntimeError(f"unexpected ijl15.dll bytes at {offset:#x}: {current.hex()}")
    result = bytes(updated)
    if struct.pack("<i", 19_999_999) in result or struct.pack("<d", 19_999_999.0) in result:
        raise RuntimeError("legacy 19,999,999 cap remains in ijl15.dll")
    if result == original:
        return False
    arc.atomic_write_bytes(CLIENT_DLL, result)
    return True


def verify_resources() -> None:
    item = load_client(CLIENT_ITEM)
    strings = load_client(CLIENT_STRING)
    for spec in STONES:
        for canvas_name in ("icon", "iconRaw"):
            canvas = item.get(f"{spec.item_node}/info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"missing Canvas {spec.item_node}/{canvas_name}")
            if (canvas.width, canvas.height, canvas.format, canvas.format2) != (32, 32, 1, 0):
                raise RuntimeError(f"incompatible Canvas {spec.item_node}/{canvas_name}")
            decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
            if decoded.getchannel("A").getbbox() is None:
                raise RuntimeError(f"transparent Canvas {spec.item_node}/{canvas_name}")
        if item.get(f"{spec.item_node}/info/tradeBlock").value != 1:
            raise RuntimeError(f"tradeBlock missing for {spec.item_id}")
        if item.get(f"{spec.item_node}/spec/script").value != SCRIPT_NAME:
            raise RuntimeError(f"script mismatch for {spec.item_id}")
        if strings.get(f"{spec.item_id}/name").value != spec.name:
            raise RuntimeError(f"name mismatch for {spec.item_id}")
        if strings.get(f"{spec.item_id}/desc").value != ITEM_DESCRIPTION:
            raise RuntimeError(f"description mismatch for {spec.item_id}")

def main() -> int:
    pixels = source_pixels()
    item_nodes = [make_item_node(spec, pixels) for spec in STONES]
    string_nodes = [make_string_node(spec) for spec in STONES]
    changed: list[Path] = []
    if insert_client_records(CLIENT_ITEM, (), item_nodes, ITEM_ANCHOR):
        changed.append(CLIENT_ITEM)
    if insert_client_records(CLIENT_STRING, (), string_nodes, STRING_ANCHOR):
        changed.append(CLIENT_STRING)
    if insert_server_records(SERVER_ITEM, (), item_nodes, ITEM_ANCHOR):
        changed.append(SERVER_ITEM)
    for path in SERVER_STRINGS:
        if insert_server_records(path, (), string_nodes, STRING_ANCHOR):
            changed.append(path)
    if patch_client_dll():
        changed.append(CLIENT_DLL)
    verify_resources()

    print(f"damage-cap breakthrough resources ready: stones={len(STONES)} changed={len(changed)}")
    for path in changed:
        print(f"{path.relative_to(ROOT)} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
