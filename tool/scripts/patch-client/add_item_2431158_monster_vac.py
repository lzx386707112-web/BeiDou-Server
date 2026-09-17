#!/usr/bin/env python3
"""Incrementally install consume item 2431158 (怪物吸星大法)."""

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


ITEM_ID = 2431158
ITEM_NODE = f"0{ITEM_ID}"
STRING_NODE = str(ITEM_ID)
ITEM_ANCHOR = "02436037"
STRING_ANCHOR = "2029006"
PREVIOUS_ITEM = "02431157"
PREVIOUS_STRING = "2431157"
ITEM_NAME = "怪物吸星大法"
ITEM_DESC = "一切怪物在此大法面前众生平等。"
SOURCE_ICON = Path(__file__).resolve().parent / "assets/2431158.png"
CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0243.img"
CLIENT_STRING = ROOT / "clien/Data/String/Consume.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Consume/0243.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Consume.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Consume.img.xml",
)
ICON_SIZE = (32, 32)
ICON_ORIGIN = (0, 32)
SPEC_TIME = 600000
SPEC_PDD = 1


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
    if source.getbbox() is None:
        raise RuntimeError("source icon is fully transparent")
    fitted = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
    source.thumbnail(ICON_SIZE, Image.Resampling.LANCZOS)
    offset = ((ICON_SIZE[0] - source.width) // 2, ICON_SIZE[1] - source.height)
    fitted.paste(source, offset, source)
    if fitted.getbbox() is None:
        raise RuntimeError("fitted icon is fully transparent")
    return fitted


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
    spec = WzSubProperty("spec", item)
    item.add(info)
    item.add(spec)
    info.add(make_canvas("icon", info, pixels))
    info.add(make_canvas("iconRaw", info, pixels))
    info.add(WzIntProperty("notSale", 1, info))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 100, info))
    info.add(WzIntProperty("tradeBlock", 1, info))
    spec.add(WzIntProperty("npc", 9900001, spec))
    spec.add(WzIntProperty("pdd", SPEC_PDD, spec))
    spec.add(WzIntProperty("time", SPEC_TIME, spec))
    spec.add(WzStringProperty("script", "consume_2431158", spec))
    return item


def make_string_node() -> WzSubProperty:
    node = WzSubProperty(STRING_NODE)
    node.add(WzStringProperty("desc", ITEM_DESC, node))
    node.add(WzStringProperty("name", ITEM_NAME, node))
    return node


def insert_or_keep_item(original: bytes, node: WzSubProperty) -> bytes:
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        return ensure_item_spec_buff(original)
    updated = arc.insert_property_record_before(original, (), node, ITEM_ANCHOR)
    arc.verify_raw_record_insert_scope(original, updated, {(node.name,)})
    load_client_bytes(updated, CLIENT_ITEM.name)
    return updated


def ensure_item_spec_buff(original: bytes) -> bytes:
    records, _ = arc.raw_record_state(original)
    updated = original
    spec_parent = (ITEM_NODE, "spec")
    if (*spec_parent, "time") not in records:
        updated = arc.insert_property_record_before(
            updated, spec_parent, WzIntProperty("time", SPEC_TIME), "script"
        )
    records, _ = arc.raw_record_state(updated)
    if (*spec_parent, "pdd") not in records:
        updated = arc.insert_property_record_before(
            updated, spec_parent, WzIntProperty("pdd", SPEC_PDD), "script"
        )
    if updated != original:
        load_client_bytes(updated, CLIENT_ITEM.name)
    return updated


def insert_or_keep_string(original: bytes, node: WzSubProperty) -> bytes:
    records, _ = arc.raw_record_state(original)
    if (node.name,) in records:
        return original
    updated = arc.insert_property_record_before(original, (), node, STRING_ANCHOR)
    arc.verify_raw_record_insert_scope(original, updated, {(node.name,)})
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


def ensure_xml_spec_buff(original: str) -> str:
    updated = original
    spec_path = (ITEM_NODE, "spec")
    if not xml_has_path(updated, (*spec_path, "time")):
        updated = arc.insert_xml_properties_before(
            updated, spec_path, [WzIntProperty("time", SPEC_TIME)], "script"
        )
    if not xml_has_path(updated, (*spec_path, "pdd")):
        updated = arc.insert_xml_properties_before(
            updated, spec_path, [WzIntProperty("pdd", SPEC_PDD)], "script"
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
    if PREVIOUS_ITEM not in names:
        raise RuntimeError("previous consume 2431157 is missing")
    if names.index(ITEM_NODE) != names.index(PREVIOUS_ITEM) + 1:
        raise RuntimeError("2431158 is not immediately after 2431157")
    if names[names.index(ITEM_NODE) + 1] != ITEM_ANCHOR:
        raise RuntimeError("2431158 is not immediately before 02436037")
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
    info = record.get("info")
    spec = record.get("spec")
    if int(arc.child_value(info, "slotMax")) != 100:
        raise RuntimeError("unexpected slotMax")
    if int(arc.child_value(info, "notSale")) != 1:
        raise RuntimeError("unexpected notSale")
    if int(arc.child_value(spec, "npc")) != 9900001:
        raise RuntimeError("unexpected spec npc")
    if int(arc.child_value(spec, "time")) != SPEC_TIME:
        raise RuntimeError("unexpected spec time")
    if int(arc.child_value(spec, "pdd")) != SPEC_PDD:
        raise RuntimeError("unexpected spec pdd")
    if str(arc.child_value(spec, "script")) != "consume_2431158":
        raise RuntimeError("unexpected spec script")


def validate_string(string_data: bytes) -> None:
    strings = load_client_bytes(string_data, CLIENT_STRING.name)
    names = sibling_names(strings, ())
    if names.index(STRING_NODE) != names.index(PREVIOUS_STRING) + 1:
        raise RuntimeError("string 2431158 is not immediately after 2431157")
    if names[names.index(STRING_NODE) + 1] != STRING_ANCHOR:
        raise RuntimeError("string 2431158 is not immediately before 2029006")
    text = strings.root.get(STRING_NODE)
    if not isinstance(text, WzSubProperty):
        raise RuntimeError(f"client String/Consume {ITEM_ID} missing")
    if str(arc.child_value(text, "name")) != ITEM_NAME:
        raise RuntimeError(f"unexpected item name: {ITEM_ID}")
    if str(arc.child_value(text, "desc")) != ITEM_DESC:
        raise RuntimeError(f"unexpected item desc: {ITEM_ID}")


def validate_xml(item_xml: str, string_xmls: dict[Path, str]) -> None:
    item_root = ET.fromstring(item_xml)
    item_names = [child.attrib.get("name") for child in item_root]
    if item_names.index(ITEM_NODE) != item_names.index(PREVIOUS_ITEM) + 1:
        raise RuntimeError("server Item XML order mismatch for 2431158")
    item_node = next(child for child in item_root if child.attrib.get("name") == ITEM_NODE)
    info = next(child for child in item_node if child.attrib.get("name") == "info")
    spec = next(child for child in item_node if child.attrib.get("name") == "spec")
    fields = {
        child.attrib["name"]: child.attrib.get("value")
        for child in info
        if child.tag == "int"
    }
    if fields.get("notSale") != "1" or fields.get("price") != "1" or fields.get("slotMax") != "100":
        raise RuntimeError("server Item XML info mismatch")
    spec_values = {child.attrib["name"]: child.attrib.get("value") for child in spec}
    if spec_values.get("script") != "consume_2431158" or spec_values.get("npc") != "9900001":
        raise RuntimeError("server Item XML spec mismatch")
    if spec_values.get("time") != str(SPEC_TIME) or spec_values.get("pdd") != str(SPEC_PDD):
        raise RuntimeError("server Item XML buff spec mismatch")
    for path, text in string_xmls.items():
        root = ET.fromstring(text)
        names = [child.attrib.get("name") for child in root]
        if names.index(STRING_NODE) != names.index(PREVIOUS_STRING) + 1:
            raise RuntimeError(f"{path.name} string order mismatch")
        node = next(child for child in root if child.attrib.get("name") == STRING_NODE)
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
        SERVER_ITEM: ensure_xml_spec_buff(
            insert_or_keep_xml(
                SERVER_ITEM.read_text(encoding="utf-8"), (), item_node, ITEM_ANCHOR
            )
        ).encode("utf-8"),
    }
    for path in SERVER_STRINGS:
        payloads[path] = insert_or_keep_xml(
            path.read_text(encoding="utf-8"), (), string_node, STRING_ANCHOR
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
        raise RuntimeError(f"item 2431158 insert is not idempotent: {first} vs {second}")
    print("item 2431158 怪物吸星大法 ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
