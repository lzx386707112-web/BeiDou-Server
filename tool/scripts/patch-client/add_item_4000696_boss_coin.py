#!/usr/bin/env python3
"""Incrementally install custom Etc item 4000696 (Boss币)."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(ROOT / "tool/scripts/migration")]

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


ITEM_ID = 4000696
ITEM_NODE = f"0{ITEM_ID}"
STRING_NODE = str(ITEM_ID)
ITEM_ANCHOR = "04000828"
STRING_ANCHOR = "4000828"
PREVIOUS_CUSTOM = "04000695"
PREVIOUS_STRING = "4000695"
ITEM_NAME = "Boss币"
ITEM_DESC = "由Boss的钱包掉出来的不知名硬币。"
SOURCE_ICON = Path(__file__).resolve().parent / "assets/4000696.png"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0400.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
ICON_SIZE = (30, 31)
ICON_ORIGIN = (-1, 31)


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
    if source.size != ICON_SIZE:
        raise RuntimeError(f"unexpected icon size: {source.size}")
    if source.getbbox() is None:
        raise RuntimeError("source icon is fully transparent")
    return source


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
    info.add(WzIntProperty("slotMax", 200, info))
    return item


def make_string_node() -> WzSubProperty:
    node = WzSubProperty(STRING_NODE)
    node.add(WzStringProperty("desc", ITEM_DESC, node))
    node.add(WzStringProperty("name", ITEM_NAME, node))
    return node


def insert_or_keep_item(original: bytes, node: WzSubProperty) -> bytes:
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        return original
    updated = arc.insert_property_record_before(original, (), node, ITEM_ANCHOR)
    arc.verify_raw_record_insert_scope(original, updated, {(node.name,)})
    load_client_bytes(updated, CLIENT_ITEM.name)
    return updated


def insert_or_keep_string(original: bytes, node: WzSubProperty) -> bytes:
    records, _ = arc.raw_record_state(original)
    if ("Etc", node.name) in records:
        return original
    updated = arc.insert_property_record_before(original, ("Etc",), node, STRING_ANCHOR)
    arc.verify_raw_record_insert_scope(original, updated, {("Etc", node.name)})
    load_client_bytes(updated, CLIENT_STRING.name)
    return updated


def xml_has_path(text: str, path: tuple[str, ...]) -> bool:
    current = arc.scan_xml(text)
    for part in path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            return False
        current = matches[0]
    return True


def insert_or_keep_xml(
    original: str,
    parent_path: tuple[str, ...],
    node: WzSubProperty,
    before_name: str,
) -> str:
    if xml_has_path(original, (*parent_path, node.name)):
        return original
    updated = arc.insert_xml_properties_before(
        original, parent_path, [node], before_name
    )
    ET.fromstring(updated)
    return updated


def sibling_names(image: WzImage, parent: tuple[str, ...]) -> list[str]:
    node = image.root
    for part in parent:
        node = node.child(part)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing parent {'/'.join(parent)}")
    return [child.name for child in node.children()]


def validate_item(item_data: bytes) -> None:
    item = load_client_bytes(item_data, CLIENT_ITEM.name)
    names = sibling_names(item, ())
    if PREVIOUS_CUSTOM not in names:
        raise RuntimeError("previous custom Etc 4000695 is missing")
    if names.index(ITEM_NODE) != names.index(PREVIOUS_CUSTOM) + 1:
        raise RuntimeError("4000696 is not immediately after 4000695")
    next_item = names[names.index(ITEM_NODE) + 1]
    if next_item not in {ITEM_ANCHOR, "04000697"}:
        raise RuntimeError("4000696 is not immediately before 04000828 or 4000697")
    record = item.root.child(ITEM_NODE)
    if not isinstance(record, WzSubProperty):
        raise RuntimeError(f"client item {ITEM_ID} missing after insert")
    for canvas_name in ("icon", "iconRaw"):
        canvas = record.get(f"info/{canvas_name}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing {canvas_name}")
        if (int(canvas.format), int(canvas.format2 or 0)) != (1, 0):
            raise RuntimeError(f"{canvas_name} is not GMS ARGB4444")
        decoded = decode_canvas(canvas, region="GMS")
        if decoded.size != ICON_SIZE or decoded.getbbox() is None:
            raise RuntimeError(f"{canvas_name} decode failed")
        origin = canvas.get("origin")
        if origin.x != ICON_ORIGIN[0] or origin.y != ICON_ORIGIN[1]:
            raise RuntimeError(f"{canvas_name} origin mismatch")
    if int(arc.child_value(record.get("info"), "slotMax")) != 200:
        raise RuntimeError("unexpected slotMax")
    if int(arc.child_value(record.get("info"), "notSale")) != 1:
        raise RuntimeError("unexpected notSale")


def validate_string(string_data: bytes) -> None:
    strings = load_client_bytes(string_data, CLIENT_STRING.name)
    names = sibling_names(strings, ("Etc",))
    if names.index(STRING_NODE) != names.index(PREVIOUS_STRING) + 1:
        raise RuntimeError("string 4000696 is not immediately after 4000695")
    next_string = names[names.index(STRING_NODE) + 1]
    if next_string not in {STRING_ANCHOR, "4000697"}:
        raise RuntimeError("string 4000696 is not immediately before 4000828 or 4000697")
    text = strings.root.get(f"Etc/{STRING_NODE}")
    if not isinstance(text, WzSubProperty):
        raise RuntimeError(f"client String/Etc {ITEM_ID} missing")
    if str(arc.child_value(text, "name")) != ITEM_NAME:
        raise RuntimeError(f"unexpected item name: {ITEM_ID}")
    if str(arc.child_value(text, "desc")) != ITEM_DESC:
        raise RuntimeError(f"unexpected item desc: {ITEM_ID}")


def validate_xml(item_xml: str, string_xmls: dict[Path, str]) -> None:
    item_root = ET.fromstring(item_xml)
    item_names = [child.attrib.get("name") for child in item_root]
    if item_names.index(ITEM_NODE) != item_names.index(PREVIOUS_CUSTOM) + 1:
        raise RuntimeError("server Item XML order mismatch for 4000696")
    item_node = next(child for child in item_root if child.attrib.get("name") == ITEM_NODE)
    fields = {
        child.attrib["name"]: child.attrib.get("value")
        for child in item_node.find("imgdir")
        if child.tag == "int"
    }
    if fields.get("notSale") != "1" or fields.get("price") != "1" or fields.get("slotMax") != "200":
        raise RuntimeError("server Item XML info mismatch")
    for path, text in string_xmls.items():
        root = ET.fromstring(text)
        etc = next(child for child in root if child.attrib.get("name") == "Etc")
        names = [child.attrib.get("name") for child in etc]
        if names.index(STRING_NODE) != names.index(PREVIOUS_STRING) + 1:
            raise RuntimeError(f"{path.name} string order mismatch")
        node = next(child for child in etc if child.attrib.get("name") == STRING_NODE)
        values = {child.attrib["name"]: child.attrib.get("value") for child in node}
        if values.get("name") != ITEM_NAME or values.get("desc") != ITEM_DESC:
            raise RuntimeError(f"{path.name} string mismatch")


def build() -> dict[Path, bytes]:
    pixels = source_pixels()
    item_node = make_item_node(pixels)
    string_node = make_string_node()
    payloads = {
        CLIENT_ITEM: insert_or_keep_item(CLIENT_ITEM.read_bytes(), item_node),
        CLIENT_STRING: insert_or_keep_string(CLIENT_STRING.read_bytes(), string_node),
        SERVER_ITEM: insert_or_keep_xml(
            SERVER_ITEM.read_text(encoding="utf-8"), (), item_node, ITEM_ANCHOR
        ).encode("utf-8"),
    }
    for path in SERVER_STRINGS:
        payloads[path] = insert_or_keep_xml(
            path.read_text(encoding="utf-8"), ("Etc",), string_node, STRING_ANCHOR
        ).encode("utf-8")
    validate_item(payloads[CLIENT_ITEM])
    validate_string(payloads[CLIENT_STRING])
    validate_xml(
        payloads[SERVER_ITEM].decode("utf-8"),
        {path: payloads[path].decode("utf-8") for path in SERVER_STRINGS},
    )
    return payloads


def apply(payloads: dict[Path, bytes]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path, data in payloads.items():
        current = path.read_bytes()
        if current != data:
            if path.suffix == ".xml":
                arc.atomic_write_text(path, data.decode("utf-8"))
            else:
                arc.atomic_write_bytes(path, data)
        hashes[str(path.relative_to(ROOT))] = sha256_bytes(data)
    return hashes


def main() -> int:
    first = apply(build())
    second = apply(build())
    if first != second:
        raise RuntimeError(f"item 4000696 insert is not idempotent: {first} vs {second}")
    print("item 4000696 Boss币 ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
