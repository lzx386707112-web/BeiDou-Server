#!/usr/bin/env python3
"""Install custom Etc item 4000695 and grant 2 from quest 3411 completion."""

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


ITEM_ID = 4000695
ITEM_NODE = f"0{ITEM_ID}"
STRING_NODE = str(ITEM_ID)
ITEM_ANCHOR = "04000828"
STRING_ANCHOR = "4000828"
ITEM_NAME = "外星人炸弹之核"
ITEM_DESC = "外星人使用的炸弹之核。拥有可以点燃强大火药的力量。"
SOURCE_ICON = Path(__file__).resolve().parent / "assets/4000695.png"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0400.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
CLIENT_ACT = ROOT / "clien/Data/Quest/Act.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
SERVER_ACTS = (
    ROOT / "gms-server/wz/Quest.wz/Act.img.xml",
    ROOT / "gms-server/wz-zh-CN/Quest.wz/Act.img.xml",
)
ICON_SIZE = (28, 29)
ICON_ORIGIN = (-2, 29)
QUEST_ID = "3411"
REWARD_SLOT = "2"
REWARD_COUNT = 2
PREVIOUS_QUEST_ID = "3404"


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


def make_reward_node() -> WzSubProperty:
    node = WzSubProperty(REWARD_SLOT)
    node.add(WzIntProperty("count", REWARD_COUNT, node))
    node.add(WzIntProperty("id", ITEM_ID, node))
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


def insert_or_keep_reward(original: bytes, node: WzSubProperty) -> bytes:
    records, _ = arc.raw_record_state(original)
    reward_root = (QUEST_ID, "1", "item", REWARD_SLOT)
    if reward_root in records:
        return original
    updated = arc.append_property_record(original, (QUEST_ID, "1", "item"), node)
    arc.verify_raw_record_insert_scope(original, updated, {reward_root})
    load_client_bytes(updated, CLIENT_ACT.name)
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
    before_name: str | None,
) -> str:
    if xml_has_path(original, (*parent_path, node.name)):
        return original
    if before_name is None:
        updated = arc.append_xml_properties(original, parent_path, [node])
    else:
        updated = arc.insert_xml_properties_before(
            original, parent_path, [node], before_name
        )
    ET.fromstring(updated)
    return updated


def validate_item(item_data: bytes) -> None:
    item = load_client_bytes(item_data, CLIENT_ITEM.name)
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
    if int(arc.child_value(record.get("info"), "slotMax")) != 200:
        raise RuntimeError("unexpected slotMax")


def validate_string(string_data: bytes) -> None:
    strings = load_client_bytes(string_data, CLIENT_STRING.name)
    text = strings.root.get(f"Etc/{STRING_NODE}")
    if not isinstance(text, WzSubProperty):
        raise RuntimeError(f"client String/Etc {ITEM_ID} missing")
    if str(arc.child_value(text, "name")) != ITEM_NAME:
        raise RuntimeError(f"unexpected item name: {ITEM_ID}")
    if str(arc.child_value(text, "desc")) != ITEM_DESC:
        raise RuntimeError(f"unexpected item desc: {ITEM_ID}")


def _item_rows(act: WzImage, quest_id: str) -> dict[str, WzSubProperty]:
    items = act.root.get(f"{quest_id}/1/item")
    if not isinstance(items, WzSubProperty):
        return {}
    return {
        child.name: child
        for child in items.children()
        if isinstance(child, WzSubProperty)
    }


def validate_reward(act_data: bytes) -> None:
    act = load_client_bytes(act_data, CLIENT_ACT.name)
    rows = _item_rows(act, QUEST_ID)
    consume = rows.get("0")
    existing = rows.get("1")
    reward = rows.get(REWARD_SLOT)
    if not isinstance(consume, WzSubProperty) or not isinstance(existing, WzSubProperty):
        raise RuntimeError("quest 3411 completion items are incomplete")
    if int(arc.child_value(consume, "id")) != 4000125:
        raise RuntimeError("quest 3411 consume item changed")
    if int(arc.child_value(existing, "id")) != 2020008:
        raise RuntimeError("quest 3411 existing reward changed")
    if not isinstance(reward, WzSubProperty):
        raise RuntimeError("quest 3411 missing 4000695 reward")
    if int(arc.child_value(reward, "id")) != ITEM_ID:
        raise RuntimeError("quest 3411 reward id mismatch")
    if int(arc.child_value(reward, "count")) != REWARD_COUNT:
        raise RuntimeError("quest 3411 reward count mismatch")
    previous = _item_rows(act, PREVIOUS_QUEST_ID)
    if any(int(arc.child_value(row, "id") or 0) == ITEM_ID for row in previous.values()):
        raise RuntimeError("quest 3404 still grants 4000695")


def validate_xml(item_xml: str, string_xmls: dict[Path, str], act_xmls: dict[Path, str]) -> None:
    item_root = ET.fromstring(item_xml)
    item_node = next(
        (child for child in item_root if child.attrib.get("name") == ITEM_NODE),
        None,
    )
    if item_node is None:
        raise RuntimeError("server Item XML missing 4000695")
    for path, text in string_xmls.items():
        root = ET.fromstring(text)
        etc = next(child for child in root if child.attrib.get("name") == "Etc")
        node = next(
            (child for child in etc if child.attrib.get("name") == STRING_NODE),
            None,
        )
        if node is None:
            raise RuntimeError(f"{path.name} missing 4000695")
        values = {child.attrib["name"]: child.attrib.get("value") for child in node}
        if values.get("name") != ITEM_NAME or values.get("desc") != ITEM_DESC:
            raise RuntimeError(f"{path.name} string mismatch")
    for path, text in act_xmls.items():
        root = ET.fromstring(text)
        quest = next(child for child in root if child.attrib.get("name") == QUEST_ID)
        complete = next(child for child in quest if child.attrib.get("name") == "1")
        items = next(child for child in complete if child.attrib.get("name") == "item")
        rows = {child.attrib.get("name"): child for child in items}
        reward = rows.get(REWARD_SLOT)
        if reward is None:
            raise RuntimeError(f"{path} missing quest 3411 reward")
        fields = {child.attrib["name"]: child.attrib.get("value") for child in reward}
        if fields.get("id") != str(ITEM_ID) or fields.get("count") != str(REWARD_COUNT):
            raise RuntimeError(f"{path} quest 3411 reward mismatch")
        consume = rows.get("0")
        existing = rows.get("1")
        consume_fields = {child.attrib["name"]: child.attrib.get("value") for child in consume}
        existing_fields = {child.attrib["name"]: child.attrib.get("value") for child in existing}
        if consume_fields.get("id") != "4000125":
            raise RuntimeError(f"{path} quest 3411 consume item changed")
        if existing_fields.get("id") != "2020008":
            raise RuntimeError(f"{path} quest 3411 existing reward changed")
        previous = next(child for child in root if child.attrib.get("name") == PREVIOUS_QUEST_ID)
        previous_complete = next(child for child in previous if child.attrib.get("name") == "1")
        previous_items = next(
            (child for child in previous_complete if child.attrib.get("name") == "item"),
            None,
        )
        if previous_items is not None:
            for row in previous_items:
                values = {child.attrib["name"]: child.attrib.get("value") for child in row}
                if values.get("id") == str(ITEM_ID):
                    raise RuntimeError(f"{path} quest 3404 still grants 4000695")


def build() -> dict[Path, bytes]:
    pixels = source_pixels()
    item_node = make_item_node(pixels)
    string_node = make_string_node()
    reward_node = make_reward_node()
    payloads = {
        CLIENT_ITEM: insert_or_keep_item(CLIENT_ITEM.read_bytes(), item_node),
        CLIENT_STRING: insert_or_keep_string(CLIENT_STRING.read_bytes(), string_node),
        CLIENT_ACT: insert_or_keep_reward(CLIENT_ACT.read_bytes(), reward_node),
        SERVER_ITEM: insert_or_keep_xml(
            SERVER_ITEM.read_text(encoding="utf-8"), (), item_node, ITEM_ANCHOR
        ).encode("utf-8"),
    }
    for path in SERVER_STRINGS:
        payloads[path] = insert_or_keep_xml(
            path.read_text(encoding="utf-8"), ("Etc",), string_node, STRING_ANCHOR
        ).encode("utf-8")
    for path in SERVER_ACTS:
        payloads[path] = insert_or_keep_xml(
            path.read_text(encoding="utf-8"),
            (QUEST_ID, "1", "item"),
            reward_node,
            None,
        ).encode("utf-8")
    validate_item(payloads[CLIENT_ITEM])
    validate_string(payloads[CLIENT_STRING])
    validate_reward(payloads[CLIENT_ACT])
    validate_xml(
        payloads[SERVER_ITEM].decode("utf-8"),
        {path: payloads[path].decode("utf-8") for path in SERVER_STRINGS},
        {path: payloads[path].decode("utf-8") for path in SERVER_ACTS},
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
        raise RuntimeError(f"item 4000695 insert is not idempotent: {first} vs {second}")
    print("item 4000695 quest 3411 reward ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
