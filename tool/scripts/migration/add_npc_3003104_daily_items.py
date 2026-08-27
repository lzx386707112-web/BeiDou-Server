#!/usr/bin/env python3
"""Install the missing item resources used by NPC 3003104 daily quests."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


ITEM_IDS = (
    4034922,
    4034923,
    4034924,
    4034925,
    4034926,
    4034927,
    4034928,
    4034929,
    4034930,
    4034934,
    4034935,
    4034936,
    4036709,
)
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0403.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)


def load_checked(path: Path, key) -> WzImage:
    image = arc.load_image(path, key)
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe IMG {path}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def build_nodes() -> tuple[list[WzSubProperty], list[WzSubProperty]]:
    item_source_path = SOURCE / "Item/Etc/0403.img"
    string_source_path = SOURCE / "String/Etc.img"
    item_source = load_checked(item_source_path, arc.BMS_KEY)
    string_source = load_checked(string_source_path, arc.BMS_KEY)
    string_parent = string_source.root.get("Etc")
    if not isinstance(string_parent, WzSubProperty):
        raise RuntimeError("TMS String/Etc.img has no Etc parent")

    materializer = arc.CanvasMaterializer()
    item_nodes: list[WzSubProperty] = []
    string_nodes: list[WzSubProperty] = []
    for item_id in ITEM_IDS:
        item_name = f"0{item_id}"
        source_item = item_source.root.get(item_name)
        source_string = string_parent.child(str(item_id))
        if not isinstance(source_item, WzSubProperty) or not isinstance(
            source_string, WzSubProperty
        ):
            raise RuntimeError(f"TMS quest item resource is missing: {item_id}")
        item_node = arc.clone_property(
            source_item,
            None,
            item_source,
            item_source_path,
            materializer,
            item_name,
        )
        for canvas_name in ("icon", "iconRaw"):
            canvas = item_node.get(f"info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"materialized item Canvas is missing: {item_id}/{canvas_name}")
            if (canvas.format, canvas.format2) != (1, 0):
                raise RuntimeError(f"incompatible item Canvas format: {item_id}/{canvas_name}")
            bitmap = decode_canvas(canvas, region="GMS")
            if bitmap.width * bitmap.height <= 1 or not bitmap.getbbox():
                raise RuntimeError(f"empty item Canvas: {item_id}/{canvas_name}")
        item_nodes.append(item_node)
        string_nodes.append(
            arc.clone_property(
                source_string,
                None,
                string_source,
                string_source_path,
                arc.CanvasMaterializer(),
                str(item_id),
            )
        )
    return item_nodes, string_nodes


def append_client_records(
    path: Path, parent_path: tuple[str, ...], nodes: list[WzSubProperty]
) -> bool:
    original = path.read_bytes()
    data = original
    approved = {(*parent_path, node.name) for node in nodes}
    for node in nodes:
        records, _ = arc.raw_record_state(data)
        if (*parent_path, node.name) not in records:
            prefix = "0" if parent_path == () else ""
            before_name = (
                f"{prefix}4034937"
                if int(node.name) < 4036000
                else f"{prefix}4036710"
            )
            data = arc.insert_property_record_before(
                data, parent_path, node, before_name
            )
    arc.verify_raw_record_insert_scope(original, data, approved)
    load_checked_bytes = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    load_checked_bytes.parse()
    if load_checked_bytes.truncated or load_checked_bytes.parse_warnings:
        raise RuntimeError(f"generated IMG failed validation: {path}")
    if data == original:
        return False
    arc.atomic_write_bytes(path, data)
    return True


def append_server_records(
    path: Path, parent_path: tuple[str, ...], nodes: list[WzSubProperty]
) -> bool:
    original = path.read_text(encoding="utf-8")
    parent = ET.fromstring(original)
    for part in parent_path:
        parent = next(
            (child for child in parent if child.tag == "imgdir" and child.get("name") == part),
            None,
        )
        if parent is None:
            raise RuntimeError(f"missing XML parent {'/'.join(parent_path)} in {path}")
    existing = {child.get("name") for child in parent}
    additions = [node for node in nodes if node.name not in existing]
    if not additions:
        return False
    updated = arc.append_xml_properties(original, parent_path, additions)
    ET.fromstring(updated)
    arc.atomic_write_text(path, updated)
    return True


def main() -> int:
    item_nodes, string_nodes = build_nodes()
    changed: list[Path] = []
    if append_client_records(CLIENT_ITEM, (), item_nodes):
        changed.append(CLIENT_ITEM)
    if append_client_records(CLIENT_STRING, ("Etc",), string_nodes):
        changed.append(CLIENT_STRING)
    if append_server_records(SERVER_ITEM, (), item_nodes):
        changed.append(SERVER_ITEM)
    for path in SERVER_STRINGS:
        if append_server_records(path, ("Etc",), string_nodes):
            changed.append(path)

    print(f"NPC 3003104 daily items ready: items={len(ITEM_IDS)} changed={len(changed)}")
    for path in changed:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
