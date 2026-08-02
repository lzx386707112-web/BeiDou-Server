#!/usr/bin/env python3
"""Add the legacy-safe Arcane River core gemstone item and strings."""

from __future__ import annotations

import io
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ICON = Path("/Users/lizixian/Downloads/2637755.png")
CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0243.img"
CLIENT_STRING = ROOT / "clien/Data/String/Consume.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Consume/0243.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Consume.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Consume.img.xml",
)
ITEM_SCRIPTS = (
    ROOT / "gms-server/scripts/item/core_gemstone_inert.js",
    ROOT / "gms-server/scripts-zh-CN/item/core_gemstone_inert.js",
)
ITEM_NODE_NAME = "02435719"
STRING_NODE_NAME = "2435719"
SCRIPT_NAME = "core_gemstone_inert"
ICON_SIZE = (32, 32)

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_arcane_river_fields import (  # noqa: E402
    GMS_KEY,
    atomic_write_bytes,
    atomic_write_text,
    property_to_xml,
)
from migrate_arcane_river_quests import find_imgdir_block  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def load_client_image(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=GMS_KEY, name=path.name)
    image.parse()
    return image


def add_int(parent: WzSubProperty, name: str, value: int) -> None:
    parent.add(WzIntProperty(name, value, parent))


def add_string(parent: WzSubProperty, name: str, value: str) -> None:
    parent.add(WzStringProperty(name, value, parent))


def resized_icon() -> Image.Image:
    if not SOURCE_ICON.exists():
        raise RuntimeError(f"missing source icon: {SOURCE_ICON}")
    source = Image.open(SOURCE_ICON).convert("RGBA")
    if source.size != (38, 38):
        raise RuntimeError(f"expected 38x38 source icon, got {source.size}")
    return source.resize(ICON_SIZE, Image.Resampling.LANCZOS)


def make_canvas(name: str, parent: WzSubProperty, pixels: Image.Image) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = ICON_SIZE
    canvas.format = 2
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        pixels, 2, ICON_SIZE[0], ICON_SIZE[1], key=GMS_KEY, listwz=False
    )
    canvas._png_length = len(canvas._png_data)
    # Official 38x38 origin (3, 36), scaled to the requested 32x32 icon.
    canvas.add(WzVectorProperty("origin", 3, 30, canvas))
    return canvas


def make_item_node(pixels: Image.Image) -> WzSubProperty:
    item = WzSubProperty(ITEM_NODE_NAME)
    info = WzSubProperty("info", item)
    spec = WzSubProperty("spec", item)
    item.add(info)
    item.add(spec)

    info.add(make_canvas("icon", info, pixels))
    info.add(make_canvas("iconRaw", info, pixels))
    add_int(info, "price", 1)
    add_int(info, "notSale", 1)
    add_int(info, "slotMax", 9999)
    add_int(info, "notConsume", 1)
    add_int(info, "tradeBlock", 1)

    add_string(spec, "script", SCRIPT_NAME)
    add_int(spec, "npc", 0)
    return item


def make_string_node() -> WzSubProperty:
    item_string = WzSubProperty(STRING_NODE_NAME)
    add_string(item_string, "name", "核心宝石")
    add_string(item_string, "desc", "这是什么垃圾玩意！")
    return item_string


def write_client_node(path: Path, node: WzSubProperty) -> None:
    image = load_client_image(path)
    image.root._children.pop(node.name, None)
    image.root.add(node)
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def upsert_xml_node(path: Path, parent_name: str, node: WzSubProperty) -> None:
    text = path.read_text(encoding="utf-8-sig")
    parent_start, parent_end = find_imgdir_block(text, parent_name)
    parent = text[parent_start:parent_end]
    try:
        child_start, child_end = find_imgdir_block(parent, node.name)
        line_start = parent.rfind("\n", 0, child_start) + 1
        if not parent[line_start:child_start].strip():
            child_start = line_start
        if child_start > 0 and parent[child_start - 1] == "\n":
            child_start -= 1
        if child_end < len(parent) and parent[child_end] == "\n":
            child_end += 1
        parent = parent[:child_start] + parent[child_end:]
    except RuntimeError:
        pass

    insert_at = parent.rfind("</imgdir>")
    prefix = parent[:insert_at].rstrip()
    block = property_to_xml(node, 1)
    parent = prefix + "\n" + block + "\n" + parent[insert_at:]
    atomic_write_text(path, text[:parent_start] + parent + text[parent_end:])


def verify_client(pixels: Image.Image) -> None:
    item_image = load_client_image(CLIENT_ITEM)
    expected_values = {
        "price": 1,
        "notSale": 1,
        "slotMax": 9999,
        "notConsume": 1,
        "tradeBlock": 1,
    }
    for name, expected in expected_values.items():
        node = item_image.get(f"{ITEM_NODE_NAME}/info/{name}")
        if node is None or node.value != expected:
            raise RuntimeError(f"invalid {ITEM_NODE_NAME}/info/{name}")
    for name in ("icon", "iconRaw"):
        canvas = item_image.get(f"{ITEM_NODE_NAME}/info/{name}")
        decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
        if decoded.size != ICON_SIZE or decoded.tobytes() != pixels.tobytes():
            raise RuntimeError(f"client {name} does not match resized source pixels")

    string_image = load_client_image(CLIENT_STRING)
    if string_image.get(f"{STRING_NODE_NAME}/name").value != "核心宝石":
        raise RuntimeError("invalid core gemstone name")
    if string_image.get(f"{STRING_NODE_NAME}/desc").value != "这是什么垃圾玩意！":
        raise RuntimeError("invalid core gemstone description")


def xml_child(parent: ET.Element, tag: str, name: str) -> ET.Element:
    child = next((entry for entry in parent if entry.tag == tag and entry.get("name") == name), None)
    if child is None:
        raise RuntimeError(f"missing XML {tag} node {name}")
    return child


def verify_server() -> None:
    item = xml_child(ET.parse(SERVER_ITEM).getroot(), "imgdir", ITEM_NODE_NAME)
    info = xml_child(item, "imgdir", "info")
    spec = xml_child(item, "imgdir", "spec")
    expected_values = {
        "price": "1",
        "notSale": "1",
        "slotMax": "9999",
        "notConsume": "1",
        "tradeBlock": "1",
    }
    for name, expected in expected_values.items():
        if xml_child(info, "int", name).get("value") != expected:
            raise RuntimeError(f"invalid server info/{name}")
    for name in ("icon", "iconRaw"):
        canvas = xml_child(info, "canvas", name)
        if (canvas.get("width"), canvas.get("height")) != ("32", "32"):
            raise RuntimeError(f"invalid server {name} size")
    if xml_child(spec, "string", "script").get("value") != SCRIPT_NAME:
        raise RuntimeError("invalid server item script")
    if xml_child(spec, "int", "npc").get("value") != "0":
        raise RuntimeError("invalid server item NPC")

    for path in SERVER_STRINGS:
        node = xml_child(ET.parse(path).getroot(), "imgdir", STRING_NODE_NAME)
        if xml_child(node, "string", "name").get("value") != "核心宝石":
            raise RuntimeError(f"invalid core gemstone name in {path}")
        if xml_child(node, "string", "desc").get("value") != "这是什么垃圾玩意！":
            raise RuntimeError(f"invalid core gemstone description in {path}")

    for path in ITEM_SCRIPTS:
        script = path.read_text(encoding="utf-8")
        if "im.dispose()" not in script or "gainItem" in script:
            raise RuntimeError(f"item script is not inert: {path}")


def main() -> None:
    pixels = resized_icon()
    item_node = make_item_node(pixels)
    string_node = make_string_node()

    write_client_node(CLIENT_ITEM, item_node)
    write_client_node(CLIENT_STRING, string_node)
    upsert_xml_node(SERVER_ITEM, "0243.img", item_node)
    for path in SERVER_STRINGS:
        upsert_xml_node(path, "Consume.img", string_node)

    verify_client(pixels)
    verify_server()
    print("added core gemstone 2435719 with 32x32 icon")


if __name__ == "__main__":
    main()
