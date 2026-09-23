#!/usr/bin/env python3
"""Add custom reincarnation flames and boss fragments as untradeable Etc items."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[3]
DOWNLOADS = Path("/Users/lizixian/Downloads")
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "arcane_migration",
    ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py",
)
arc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = arc
spec.loader.exec_module(arc)

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402


CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0400.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
ITEM_ANCHOR = "04009996"
STRING_ANCHOR = "4009996"
FLAME_DESC = "来自仙界拥有未知力量的輪迴星火。"


@dataclass(frozen=True)
class ItemSpec:
    item_id: int
    name: str
    filename: str
    desc: str

    @property
    def item_record(self) -> str:
        return f"0{self.item_id}"


def fragment_desc(name: str) -> str:
    if not name.endswith("碎片"):
        raise ValueError(f"fragment name has no 碎片 suffix: {name}")
    return f"{name[:-2]}身上掉落的碎片，作用未知。"


def item(
    item_id: int,
    name: str,
    filename: str | None = None,
    description: str | None = None,
) -> ItemSpec:
    desc = description or (FLAME_DESC if "輪迴星火" in name else fragment_desc(name))
    return ItemSpec(item_id, name, filename or f"{name}.png", desc)


ITEMS = (
    item(4009818, "輪迴星火红色", " 輪迴星火红色.png"),
    item(4009819, "輪迴星火紫色", " 輪迴星火紫色.png"),
    item(4009820, "阿卡伊勒碎片"),
    item(4009821, "班·雷昂碎片"),
    item(4009822, "超越的輪迴星火"),
    item(4009823, "戴米安碎片"),
    item(4009824, "地狱輪迴星火"),
    item(4009825, "混沌碎片"),
    item(4009826, "觉醒希拉碎片"),
    item(4009827, "覺醒的暗黑輪迴星火"),
    item(4009828, "卡洛斯碎片"),
    item(4009829, "露希妲碎片"),
    item(4009830, "輪迴星火蓝色"),
    item(4009831, "輪迴星火绿色"),
    item(4009832, "扭曲輪迴星火"),
    item(4009833, "麦格纳斯碎片"),
    item(4009834, "亲卫队长顿凯尔碎片"),
    item(4009835, "窮奇碎片"),
    item(4009836, "塞伦碎片"),
    item(4009837, "守护天使绿水灵碎片"),
    item(4009838, "檮杌碎片"),
    item(4009839, "威尔碎片"),
    item(4009840, "希纳斯碎片"),
    item(4009841, "破滅的碎片", description="蘊含破滅力量的碎片，作用未知。"),
    item(4009842, "獅子王的獎牌", description="象徵獅子王力量的獎牌，作用未知。"),
)


def load_client_bytes(path: Path, data: bytes | None = None) -> WzImage:
    image = WzImage.from_bytes(
        data if data is not None else path.read_bytes(),
        key=arc.GMS_KEY,
        name=path.name,
    )
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {path}: truncated={image.truncated}, "
            f"warnings={image.parse_warnings}"
        )
    return image


def load_sources() -> dict[int, Image.Image]:
    result: dict[int, Image.Image] = {}
    existing_image: WzImage | None = None
    for spec in ITEMS:
        path = DOWNLOADS / spec.filename
        if path.is_file():
            with Image.open(path) as source:
                picture = source.convert("RGBA")
        else:
            if existing_image is None:
                existing_image = load_client_bytes(CLIENT_ITEM)
            canvas = existing_image.root.get(f"{spec.item_record}/info/icon")
            if not isinstance(canvas, WzCanvasProperty):
                raise FileNotFoundError(path)
            picture = decode_canvas(canvas, region="GMS")
        if picture.width <= 1 or picture.height <= 1:
            raise RuntimeError(f"invalid icon dimensions: {path}: {picture.size}")
        if picture.getchannel("A").getbbox() is None:
            raise RuntimeError(f"icon has no visible pixels: {path}")
        result[spec.item_id] = picture
    return result


def make_canvas(name: str, picture: Image.Image) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name)
    canvas.width, canvas.height = picture.size
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        picture,
        1,
        canvas.width,
        canvas.height,
        key=arc.GMS_KEY,
        listwz=False,
        zlib_level=9,
    )
    canvas._png_length = len(canvas._png_data)
    canvas.add(WzVectorProperty("origin", 0, canvas.height, canvas))
    return canvas


def make_item_record(spec: ItemSpec, picture: Image.Image) -> WzSubProperty:
    record = WzSubProperty(spec.item_record)
    info = WzSubProperty("info", record)
    record.add(info)
    info.add(make_canvas("icon", picture))
    info.add(make_canvas("iconRaw", picture))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("tradeBlock", 1, info))
    info.add(WzIntProperty("slotMax", 200, info))
    return record


def make_string_record(spec: ItemSpec) -> WzSubProperty:
    record = WzSubProperty(str(spec.item_id))
    record.add(WzStringProperty("desc", spec.desc, record))
    record.add(WzStringProperty("name", spec.name, record))
    return record


def stage_client(
    path: Path,
    parent: tuple[str, ...],
    records: tuple[WzSubProperty, ...],
    anchor: str,
) -> bytes:
    before = path.read_bytes()
    image = load_client_bytes(path, before)
    parent_node = image.root.get("/".join(parent)) if parent else image.root
    if not isinstance(parent_node, WzSubProperty):
        raise RuntimeError(f"missing client parent {path}: {'/'.join(parent)}")
    missing = tuple(record for record in records if parent_node.child(record.name) is None)
    if not missing:
        return before
    after = arc.insert_property_records_before(before, parent, missing, anchor)
    arc.verify_raw_record_insert_scope(
        before,
        after,
        {(*parent, record.name) for record in missing},
    )
    return after


def stage_xml(
    path: Path,
    parent_path: tuple[str, ...],
    records: tuple[WzSubProperty, ...],
    anchor: str,
) -> str:
    before = path.read_text(encoding="utf-8")
    root = ET.fromstring(before)
    parent = root
    for name in parent_path:
        parent = parent.find(f'./imgdir[@name="{name}"]')
        if parent is None:
            raise RuntimeError(f"missing XML parent {path}: {'/'.join(parent_path)}")
    existing = {child.get("name") for child in parent if child.tag == "imgdir"}
    missing = tuple(record for record in records if record.name not in existing)
    if not missing:
        if path not in SERVER_STRINGS:
            return before
        layout = arc.scan_xml(before)
        current = layout
        for name in parent_path:
            matches = [child for child in current.children if child.name == name]
            if len(matches) != 1:
                raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
            current = matches[0]
        names = [record.name for record in records]
        first = next(index for index, child in enumerate(current.children) if child.name == names[0])
        target_nodes = current.children[first:first + len(names)]
        if [node.name for node in target_nodes] != names:
            raise RuntimeError(f"target String records are not contiguous in {path}")
        if first == 0 or current.children[first + len(names)].name != anchor:
            raise RuntimeError(f"target String records are not directly before {anchor} in {path}")
        previous = current.children[first - 1]
        anchor_node = current.children[first + len(names)]
        canonical = "".join(arc.property_to_xml(record, 0) for record in records)
        after = before[:previous.end] + canonical + before[anchor_node.start:]
    elif path in SERVER_STRINGS:
        layout = arc.scan_xml(before)
        current = layout
        for name in parent_path:
            matches = [child for child in current.children if child.name == name]
            if len(matches) != 1:
                raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
            current = matches[0]
        anchors = [child for child in current.children if child.name == anchor]
        if len(anchors) != 1:
            raise RuntimeError(f"XML anchor is not unique: {anchor}")
        block = "".join(arc.property_to_xml(record, 0) for record in missing)
        after = before[:anchors[0].start] + block + before[anchors[0].start:]
    else:
        after = arc.insert_xml_properties_before(before, parent_path, list(missing), anchor)
    ET.fromstring(after)
    return after


def scalar(node, path: str) -> int | str | None:
    value = node.get(path)
    return getattr(value, "value", None)


def verify_client_item(data: bytes, sources: dict[int, Image.Image]) -> None:
    image = load_client_bytes(CLIENT_ITEM, data)
    for spec in ITEMS:
        record = image.root.child(spec.item_record)
        if not isinstance(record, WzSubProperty):
            raise RuntimeError(f"missing staged client item: {spec.item_id}")
        expected = {"price": 1, "tradeBlock": 1, "slotMax": 200}
        actual = {name: scalar(record, f"info/{name}") for name in expected}
        if actual != expected:
            raise RuntimeError(f"client item scalar mismatch {spec.item_id}: {actual}")
        source = sources[spec.item_id]
        expected_canvas = make_canvas("expected", source)
        expected_pixels = decode_canvas(expected_canvas, region="GMS")
        for name in ("icon", "iconRaw"):
            canvas = record.get(f"info/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"missing client Canvas {spec.item_id}/info/{name}")
            if (canvas.format, canvas.format2, canvas.width, canvas.height) != (
                1,
                0,
                source.width,
                source.height,
            ):
                raise RuntimeError(f"client Canvas metadata mismatch: {spec.item_id}/{name}")
            pixels = decode_canvas(canvas, region="GMS")
            if pixels.getchannel("A").getbbox() is None:
                raise RuntimeError(f"client Canvas is transparent: {spec.item_id}/{name}")
            if ImageChops.difference(pixels, expected_pixels).getbbox() is not None:
                raise RuntimeError(f"client Canvas pixels mismatch: {spec.item_id}/{name}")


def verify_client_strings(data: bytes) -> None:
    image = load_client_bytes(CLIENT_STRING, data)
    for spec in ITEMS:
        record = image.root.get(f"Etc/{spec.item_id}")
        if not isinstance(record, WzSubProperty):
            raise RuntimeError(f"missing staged client String: {spec.item_id}")
        actual = (scalar(record, "name"), scalar(record, "desc"))
        if actual != (spec.name, spec.desc):
            raise RuntimeError(f"client String mismatch {spec.item_id}: {actual}")


def xml_parent(path: Path, text: str, parent_path: tuple[str, ...]):
    current = ET.fromstring(text)
    for name in parent_path:
        current = current.find(f'./imgdir[@name="{name}"]')
        if current is None:
            raise RuntimeError(f"missing XML parent {path}: {'/'.join(parent_path)}")
    return current


def verify_server_item(text: str, sources: dict[int, Image.Image]) -> None:
    parent = xml_parent(SERVER_ITEM, text, ())
    for spec in ITEMS:
        record = parent.find(f'./imgdir[@name="{spec.item_record}"]')
        if record is None:
            raise RuntimeError(f"missing server item: {spec.item_id}")
        info = record.find('./imgdir[@name="info"]')
        if info is None:
            raise RuntimeError(f"missing server item info: {spec.item_id}")
        for name, expected in (("price", "1"), ("tradeBlock", "1"), ("slotMax", "200")):
            node = info.find(f'./int[@name="{name}"]')
            if node is None or node.get("value") != expected:
                raise RuntimeError(f"server item scalar mismatch: {spec.item_id}/{name}")
        source = sources[spec.item_id]
        for name in ("icon", "iconRaw"):
            node = info.find(f'./canvas[@name="{name}"]')
            if node is None or (node.get("width"), node.get("height")) != (
                str(source.width),
                str(source.height),
            ):
                raise RuntimeError(f"server item Canvas mismatch: {spec.item_id}/{name}")


def verify_server_strings(path: Path, text: str) -> None:
    parent = xml_parent(path, text, ("Etc",))
    for spec in ITEMS:
        record = parent.find(f'./imgdir[@name="{spec.item_id}"]')
        if record is None:
            raise RuntimeError(f"missing server String: {path}: {spec.item_id}")
        name = record.find('./string[@name="name"]')
        desc = record.find('./string[@name="desc"]')
        if name is None or desc is None:
            raise RuntimeError(f"incomplete server String: {path}: {spec.item_id}")
        if (name.get("value"), desc.get("value")) != (spec.name, spec.desc):
            raise RuntimeError(f"server String mismatch: {path}: {spec.item_id}")


def sha256(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    sources = load_sources()
    item_records = tuple(make_item_record(spec, sources[spec.item_id]) for spec in ITEMS)
    string_records = tuple(make_string_record(spec) for spec in ITEMS)

    client_outputs = {
        CLIENT_ITEM: stage_client(CLIENT_ITEM, (), item_records, ITEM_ANCHOR),
        CLIENT_STRING: stage_client(CLIENT_STRING, ("Etc",), string_records, STRING_ANCHOR),
    }
    xml_outputs = {
        SERVER_ITEM: stage_xml(SERVER_ITEM, (), item_records, ITEM_ANCHOR),
        **{
            path: stage_xml(path, ("Etc",), string_records, STRING_ANCHOR)
            for path in SERVER_STRINGS
        },
    }

    verify_client_item(client_outputs[CLIENT_ITEM], sources)
    verify_client_strings(client_outputs[CLIENT_STRING])
    verify_server_item(xml_outputs[SERVER_ITEM], sources)
    for path in SERVER_STRINGS:
        verify_server_strings(path, xml_outputs[path])

    changed = 0
    hashes: list[str] = []
    for path, data in client_outputs.items():
        hashes.append(f"{path.relative_to(ROOT)} {sha256(data)}")
        if data != path.read_bytes():
            arc.atomic_write_bytes(path, data)
            changed += 1
    for path, text in xml_outputs.items():
        hashes.append(f"{path.relative_to(ROOT)} {sha256(text)}")
        if text != path.read_text(encoding="utf-8"):
            arc.atomic_write_text(path, text)
            changed += 1

    print(f"custom Etc item migration complete: {changed} files changed")
    print("\n".join(hashes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
