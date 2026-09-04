#!/usr/bin/env python3
"""Add Star Force safeguard scrolls with incremental legacy IMG inserts."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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


SOURCE_ICON = Path(__file__).resolve().parent / "assets/star_force_safeguard.png"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0426.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0426.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)
STRING_ANCHOR = "4260020"
ICON_SIZE = (32, 32)
ICON_ORIGIN = (0, 32)


@dataclass(frozen=True)
class ScrollSpec:
    item_id: int
    reduction: int

    @property
    def item_node(self) -> str:
        return f"0{self.item_id}"

    @property
    def name(self) -> str:
        return f"星之力防爆卷{self.reduction}%"

    @property
    def description(self) -> str:
        return f"星之力强化时使用，使本次强化的爆装率降低{self.reduction}个百分点。"


SCROLLS = tuple(
    ScrollSpec(4260011 + index, reduction)
    for index, reduction in enumerate(range(2, 18, 2), start=1)
)
TARGET_ITEM_NODES = frozenset(spec.item_node for spec in SCROLLS)
TARGET_STRING_NODES = frozenset(str(spec.item_id) for spec in SCROLLS)


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
        ((ICON_SIZE[0] - source.width) // 2, (ICON_SIZE[1] - source.height) // 2),
    )
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


def make_item_node(spec: ScrollSpec, pixels: Image.Image) -> WzSubProperty:
    item = WzSubProperty(spec.item_node)
    info = WzSubProperty("info", item)
    item.add(info)
    info.add(make_canvas("icon", info, pixels))
    info.add(make_canvas("iconRaw", info, pixels))
    info.add(WzIntProperty("price", 1, info))
    info.add(WzIntProperty("slotMax", 500, info))
    return item


def make_string_node(spec: ScrollSpec) -> WzSubProperty:
    node = WzSubProperty(str(spec.item_id))
    node.add(WzStringProperty("desc", spec.description, node))
    node.add(WzStringProperty("name", spec.name, node))
    return node


def build_client_items(nodes: list[WzSubProperty]) -> bytes:
    original = CLIENT_ITEM.read_bytes()
    records, _ = arc.raw_record_state(original)
    missing = [node for node in nodes if (node.name,) not in records]
    if not missing:
        return original
    updated = original
    for node in missing:
        updated = arc.append_property_record(updated, (), node)
    approved = {(node.name,) for node in missing}
    arc.verify_raw_record_insert_scope(original, updated, approved)
    load_client_bytes(updated, CLIENT_ITEM.name)
    return updated


def build_client_strings(nodes: list[WzSubProperty]) -> bytes:
    original = CLIENT_STRING.read_bytes()
    records, _ = arc.raw_record_state(original)
    missing = [node for node in nodes if ("Etc", node.name) not in records]
    if not missing:
        return original
    updated = arc.insert_property_records_before(
        original, ("Etc",), missing, STRING_ANCHOR
    )
    approved = {("Etc", node.name) for node in missing}
    arc.verify_raw_record_insert_scope(original, updated, approved)
    load_client_bytes(updated, CLIENT_STRING.name)
    return updated


def xml_parent(root: ET.Element, parent_path: tuple[str, ...], path: Path) -> ET.Element:
    parent = root
    for part in parent_path:
        parent = next(
            (child for child in parent if child.tag == "imgdir" and child.get("name") == part),
            None,
        )
        if parent is None:
            raise RuntimeError(f"missing XML parent {'/'.join(parent_path)} in {path}")
    return parent


def build_server_items(nodes: list[WzSubProperty]) -> str:
    original = SERVER_ITEM.read_text(encoding="utf-8")
    parent = xml_parent(ET.fromstring(original), (), SERVER_ITEM)
    existing = {child.get("name") for child in parent if child.tag == "imgdir"}
    missing = [node for node in nodes if node.name not in existing]
    if not missing:
        return original
    updated = arc.append_xml_properties(original, (), missing)
    ET.fromstring(updated)
    return updated


def build_server_strings(path: Path, nodes: list[WzSubProperty]) -> str:
    original = path.read_text(encoding="utf-8")
    parent_path = ("Etc",)
    parent = xml_parent(ET.fromstring(original), parent_path, path)
    existing = {child.get("name") for child in parent if child.tag == "imgdir"}
    missing = [node for node in nodes if node.name not in existing]
    if not missing:
        return original
    specs = {str(spec.item_id): spec for spec in SCROLLS}
    marker = f'<imgdir name="{STRING_ANCHOR}">'
    if original.count(marker) != 1:
        raise RuntimeError(f"String XML anchor is not unique in {path}: {STRING_ANCHOR}")
    block = "".join(
        f'<imgdir name="{node.name}">'
        f'<string name="desc" value={quoteattr(specs[node.name].description)} />'
        f'<string name="name" value={quoteattr(specs[node.name].name)} />'
        '</imgdir>'
        for node in missing
    )
    updated = original.replace(marker, block + marker, 1)
    ET.fromstring(updated)
    return updated


def verify_resources(
    expected_pixels: Image.Image,
    client_item_data: bytes,
    client_string_data: bytes,
    server_item_text: str,
    server_string_texts: dict[Path, str],
) -> None:
    item = load_client_bytes(client_item_data, CLIENT_ITEM.name)
    strings = load_client_bytes(client_string_data, CLIENT_STRING.name)
    for spec in SCROLLS:
        for canvas_name in ("icon", "iconRaw"):
            canvas = item.get(f"{spec.item_node}/info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"missing Canvas {spec.item_node}/{canvas_name}")
            if (canvas.width, canvas.height, canvas.format, canvas.format2) != (32, 32, 1, 0):
                raise RuntimeError(f"incompatible Canvas {spec.item_node}/{canvas_name}")
            decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
            if decoded.getchannel("A").getbbox() is None:
                raise RuntimeError(f"transparent Canvas {spec.item_node}/{canvas_name}")
            if decoded.size != expected_pixels.size:
                raise RuntimeError(f"Canvas size mismatch {spec.item_node}/{canvas_name}")
        if strings.get(f"Etc/{spec.item_id}/name").value != spec.name:
            raise RuntimeError(f"client name mismatch: {spec.item_id}")
        if strings.get(f"Etc/{spec.item_id}/desc").value != spec.description:
            raise RuntimeError(f"client description mismatch: {spec.item_id}")

    item_root = ET.fromstring(server_item_text)
    item_names = {child.get("name") for child in item_root if child.tag == "imgdir"}
    if not TARGET_ITEM_NODES.issubset(item_names):
        raise RuntimeError("server item XML is missing safeguard scrolls")
    for path in SERVER_STRINGS:
        root = ET.fromstring(server_string_texts[path])
        parent = xml_parent(root, ("Etc",), path)
        values = {child.get("name"): child for child in parent if child.tag == "imgdir"}
        for spec in SCROLLS:
            node = values.get(str(spec.item_id))
            fields = (
                {child.get("name"): child.get("value") for child in node}
                if node is not None
                else {}
            )
            if fields.get("name") != spec.name or fields.get("desc") != spec.description:
                raise RuntimeError(f"server string mismatch {path}: {spec.item_id}")


def main() -> int:
    pixels = source_pixels()
    item_nodes = [make_item_node(spec, pixels) for spec in SCROLLS]
    string_nodes = [make_string_node(spec) for spec in SCROLLS]

    client_item_data = build_client_items(item_nodes)
    client_string_data = build_client_strings(string_nodes)
    server_item_text = build_server_items(item_nodes)
    server_string_texts = {
        path: build_server_strings(path, string_nodes) for path in SERVER_STRINGS
    }
    verify_resources(
        pixels,
        client_item_data,
        client_string_data,
        server_item_text,
        server_string_texts,
    )

    outputs: list[tuple[Path, bytes | str]] = [
        (CLIENT_ITEM, client_item_data),
        (CLIENT_STRING, client_string_data),
        (SERVER_ITEM, server_item_text),
        *server_string_texts.items(),
    ]
    changed: list[Path] = []
    for path, output in outputs:
        current = path.read_bytes() if isinstance(output, bytes) else path.read_text(encoding="utf-8")
        if current == output:
            continue
        if isinstance(output, bytes):
            arc.atomic_write_bytes(path, output)
        else:
            arc.atomic_write_text(path, output)
        changed.append(path)

    print(f"Star Force safeguard scrolls ready: count={len(SCROLLS)} changed={len(changed)}")
    for path in changed:
        print(f"{path.relative_to(ROOT)} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
