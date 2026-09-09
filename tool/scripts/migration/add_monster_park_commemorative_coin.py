#!/usr/bin/env python3
"""Insert Monster Park commemorative coin 4310020 with the user icon."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

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


ITEM_ID = 4310020
ITEM_NODE = f"0{ITEM_ID}"
STRING_NODE = str(ITEM_ID)
STRING_ANCHOR = "4310059"
ITEM_NAME = "怪物公园纪念币"
ITEM_DESC = "祝賀拜訪怪物公園的紀念貨幣，拿給怪物公園的休菲凱曼就可以交換成特別的道具。"
SOURCE_ICON = Path(__file__).resolve().parent / "assets/monster_park_commemorative_coin.png"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0431.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0431.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
ICON_SIZE = (32, 32)
ICON_ORIGIN = (-3, 30)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_client_bytes(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe IMG {name}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def source_pixels() -> Image.Image:
    if not SOURCE_ICON.is_file():
        raise RuntimeError(f"missing source icon: {SOURCE_ICON}")
    source = Image.open(SOURCE_ICON).convert("RGBA")
    if source.getchannel("A").getbbox() is None:
        raise RuntimeError("source icon is fully transparent")
    source.thumbnail(ICON_SIZE, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
    output.alpha_composite(
        source,
        ((ICON_SIZE[0] - source.width) // 2, ICON_SIZE[1] - source.height),
    )
    if output.getbbox() is None:
        raise RuntimeError("projected icon has no visible pixels")
    return output


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


def make_item_node(pixels: Image.Image) -> WzSubProperty:
    item = WzSubProperty(ITEM_NODE)
    info = WzSubProperty("info", item)
    item.add(info)
    info.add(make_canvas("icon", info, pixels))
    info.add(make_canvas("iconRaw", info, pixels))
    info.add(WzIntProperty("notSale", 1, info))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 1000, info))
    info.add(WzIntProperty("tradeBlock", 1, info))
    return item


def make_string_node() -> WzSubProperty:
    node = WzSubProperty(STRING_NODE)
    node.add(WzStringProperty("desc", ITEM_DESC, node))
    node.add(WzStringProperty("name", ITEM_NAME, node))
    return node


def build_client_item(node: WzSubProperty) -> bytes:
    original = CLIENT_ITEM.read_bytes()
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        return original
    updated = arc.append_property_record(original, (), node)
    arc.verify_raw_record_insert_scope(original, updated, {(node.name,)})
    load_client_bytes(updated, CLIENT_ITEM.name)
    return updated


def build_client_string(node: WzSubProperty) -> bytes:
    original = CLIENT_STRING.read_bytes()
    records, _ = arc.raw_record_state(original)
    if ("Etc", node.name) in records:
        return original
    updated = arc.insert_property_records_before(original, ("Etc",), [node], STRING_ANCHOR)
    arc.verify_raw_record_insert_scope(original, updated, {("Etc", node.name)})
    load_client_bytes(updated, CLIENT_STRING.name)
    return updated


def build_server_item(node: WzSubProperty) -> str:
    original = SERVER_ITEM.read_text(encoding="utf-8")
    if f'<imgdir name="{ITEM_NODE}">' in original:
        return original
    updated = arc.append_xml_properties(original, (), [node])
    ET = __import__("xml.etree.ElementTree", fromlist=["fromstring"]).fromstring
    ET(updated)
    return updated


def build_server_string(path: Path) -> str:
    original = path.read_text(encoding="utf-8")
    if f'<imgdir name="{STRING_NODE}">' in original:
        return original
    marker = f'<imgdir name="{STRING_ANCHOR}">'
    if original.count(marker) != 1:
        raise RuntimeError(f"String XML anchor is not unique in {path}")
    block = (
        f'<imgdir name="{STRING_NODE}">'
        f"<string name=\"desc\" value={quoteattr(ITEM_DESC)} />"
        f"<string name=\"name\" value={quoteattr(ITEM_NAME)} />"
        "</imgdir>"
    )
    updated = original.replace(marker, block + marker, 1)
    ET = __import__("xml.etree.ElementTree", fromlist=["fromstring"]).fromstring
    ET(updated)
    return updated


def verify(pixels: Image.Image, item_data: bytes, string_data: bytes, item_xml: str, string_xmls: dict[Path, str]) -> None:
    item = load_client_bytes(item_data, CLIENT_ITEM.name)
    record = item.root.child(ITEM_NODE)
    if not isinstance(record, WzSubProperty):
        raise RuntimeError("client item 4310020 missing after insert")
    for canvas_name in ("icon", "iconRaw"):
        canvas = record.get(f"info/{canvas_name}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing {canvas_name}")
        if (int(canvas.format), int(canvas.format2 or 0)) != (1, 0):
            raise RuntimeError(f"{canvas_name} is not GMS ARGB4444")
        decoded = decode_canvas(canvas, region="GMS")
        if decoded.size != ICON_SIZE or decoded.getbbox() is None:
            raise RuntimeError(f"{canvas_name} decode failed")
    strings = load_client_bytes(string_data, CLIENT_STRING.name)
    text = strings.root.get(f"Etc/{STRING_NODE}")
    if not isinstance(text, WzSubProperty):
        raise RuntimeError("client String/Etc 4310020 missing")
    if str(arc.child_value(text, "name")) != ITEM_NAME:
        raise RuntimeError("coin name mismatch")
    if str(arc.child_value(text, "desc")) != ITEM_DESC:
        raise RuntimeError("coin desc mismatch")
    if ITEM_NODE not in item_xml or STRING_NODE not in next(iter(string_xmls.values())):
        raise RuntimeError("server XML missing 4310020")


def apply() -> dict[str, str]:
    pixels = source_pixels()
    item_node = make_item_node(pixels)
    string_node = make_string_node()
    item_data = build_client_item(item_node)
    string_data = build_client_string(string_node)
    item_xml = build_server_item(item_node)
    string_xmls = {path: build_server_string(path) for path in SERVER_STRINGS}
    verify(pixels, item_data, string_data, item_xml, string_xmls)
    hashes = {
        "client_item": sha256_bytes(item_data),
        "client_string": sha256_bytes(string_data),
        "server_item": sha256_bytes(item_xml.encode("utf-8")),
    }
    if item_data != CLIENT_ITEM.read_bytes():
        arc.atomic_write_bytes(CLIENT_ITEM, item_data)
    if string_data != CLIENT_STRING.read_bytes():
        arc.atomic_write_bytes(CLIENT_STRING, string_data)
    if item_xml != SERVER_ITEM.read_text(encoding="utf-8"):
        arc.atomic_write_text(SERVER_ITEM, item_xml)
    for path, text in string_xmls.items():
        if text != path.read_text(encoding="utf-8"):
            arc.atomic_write_text(path, text)
        hashes[path.name] = sha256_bytes(text.encode("utf-8"))
    return hashes


def main() -> int:
    first = apply()
    second = apply()
    if first != second:
        raise RuntimeError(f"coin insert is not idempotent: {first} vs {second}")
    print("monster park coin 4310020 ok", first["client_item"][:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
