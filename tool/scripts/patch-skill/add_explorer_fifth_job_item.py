#!/usr/bin/env python3
"""Add reusable item 2029006 for the Explorer V/VI skill NPC script."""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty, WzImage, WzIntProperty, WzKey, WzStringProperty,
    WzSubProperty, WzVectorProperty,
)
from wzpy.canvas import _read_canvas_bytes  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402


KEY = WzKey.for_region("GMS")
ITEM_ID = "2029006"
ITEM_RECORD = "02029006"
ICON_SOURCE_RECORD = "02022614"
CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0202.img"
CLIENT_STRING = ROOT / "clien/Data/String/Consume.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Consume/0202.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Consume.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Consume.img.xml",
)


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"unsafe IMG {path}: {image.parse_warnings}")
    return image


def clone_canvas(source: WzCanvasProperty, name: str, parent: WzSubProperty) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = source.width, source.height
    canvas.format, canvas.format2 = source.format, source.format2
    canvas._png_data = bytes(_read_canvas_bytes(source))
    canvas._png_length = source._png_length
    origin = source.child("origin")
    if isinstance(origin, WzVectorProperty):
        canvas.add(WzVectorProperty("origin", origin.x, origin.y, canvas))
    return canvas


def item_node(image: WzImage) -> WzSubProperty:
    source = image.get(f"{ICON_SOURCE_RECORD}/info")
    if not isinstance(source, WzSubProperty):
        raise RuntimeError("missing 2022614 icon source")
    node = WzSubProperty(ITEM_RECORD, image.root)
    info = WzSubProperty("info", node)
    for name in ("icon", "iconRaw"):
        canvas = source.child(name)
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing 2022614 {name}")
        info.add(clone_canvas(canvas, name, info))
    for name, value in (("price", 1), ("slotMax", 1), ("tradeBlock", 1), ("notSale", 1)):
        info.add(WzIntProperty(name, value, info))
    spec = WzSubProperty("spec", node)
    spec.add(WzIntProperty("npc", 9900001, spec))
    spec.add(WzStringProperty("script", "冒险家五六转攻击技能", spec))
    spec.add(WzIntProperty("remove", 0, spec))
    spec.add(WzIntProperty("isNpc", 1, spec))
    node.add(info)
    node.add(spec)
    return node


def string_node(image: WzImage) -> WzSubProperty:
    node = WzSubProperty(ITEM_ID, image.root)
    node.add(WzStringProperty("name", "5转技能", node))
    node.add(WzStringProperty("desc", "放在快捷键上使用，可打开冒险家五、六转攻击技能面板。", node))
    return node


def root_layout(image: WzImage, data: bytes):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported IMG header")
    reader.skip(2)
    count_start = reader.position
    count = reader.read_compressed_int()
    count_end = reader.position
    names, spans = [], []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root tag {name}/{tag}")
        size = reader.read_u32()
        reader.seek(reader.position + size)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != len(data):
        raise RuntimeError("root records do not fill IMG")
    return count_start, count_end, names, spans


def append_record(path: Path, factory) -> None:
    original = path.read_bytes()
    image = load(path)
    count_start, count_end, names, spans = root_layout(image, original)
    node = factory(image)
    if node.name in names:
        return
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected encoded record")
    count = len(names)
    new_count = encode_compressed_int(count + 1)
    if len(new_count) != count_end - count_start:
        raise RuntimeError("root count width would change")
    updated = original[:count_start] + new_count + original[count_end:] + encoded[len(prefix):]
    verified = WzImage.from_bytes(updated, key=KEY, name=path.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings or verified.get(node.name) is None:
        raise RuntimeError(f"generated IMG failed validation: {path}")
    _, _, new_names, new_spans = root_layout(verified, updated)
    if new_names != names + [node.name]:
        raise RuntimeError("root record order changed")
    for old_span, new_span in zip(spans, new_spans):
        if original[slice(*old_span)] != updated[slice(*new_span)]:
            raise RuntimeError("unapproved raw record changed")
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(updated)
        temporary = Path(handle.name)
    temporary.replace(path)


def insert_xml(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    token = f'<imgdir name="{ITEM_RECORD if "Item.wz" in str(path) else ITEM_ID}">'
    if token in text:
        return
    pos = text.rfind("</imgdir>")
    if pos < 0:
        raise RuntimeError(f"invalid XML {path}")
    updated = text[:pos] + block + "\n" + text[pos:]
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    append_record(CLIENT_ITEM, item_node)
    append_record(CLIENT_STRING, string_node)
    item_block = f'''  <imgdir name="{ITEM_RECORD}">
    <imgdir name="info">
      <int name="price" value="1"/><int name="slotMax" value="1"/>
      <int name="tradeBlock" value="1"/>
      <canvas name="icon" width="1" height="1"><string name="_outlink" value="Item/Consume/0202.img/{ICON_SOURCE_RECORD}/info/icon"/></canvas>
      <canvas name="iconRaw" width="1" height="1"><string name="_outlink" value="Item/Consume/0202.img/{ICON_SOURCE_RECORD}/info/iconRaw"/></canvas>
      <int name="notSale" value="1"/>
    </imgdir>
    <imgdir name="spec"><int name="npc" value="9900001"/><string name="script" value="冒险家五六转攻击技能"/><int name="remove" value="0"/><int name="isNpc" value="1"/></imgdir>
  </imgdir>'''
    insert_xml(SERVER_ITEM, item_block)
    string_block = f'  <imgdir name="{ITEM_ID}"><string name="name" value="5转技能"/><string name="desc" value="放在快捷键上使用，可打开冒险家五、六转攻击技能面板。"/></imgdir>'
    for path in SERVER_STRINGS:
        insert_xml(path, string_block)
    for path in (CLIENT_ITEM, CLIENT_STRING):
        print(f"{path.relative_to(ROOT)} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
