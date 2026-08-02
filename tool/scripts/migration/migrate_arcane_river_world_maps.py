#!/usr/bin/env python3
"""Migrate the legacy-safe Arcane River world maps from TMS."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
)

from migrate_arcane_river_fields import (  # noqa: E402
    BMS_KEY,
    CanvasMaterializer,
    GMS_KEY,
    MAP_ID_SET,
    SOURCE,
    atomic_write_text,
    backup,
    child_value,
    clone_image,
    clone_property,
    image_to_xml,
    load_image,
    property_to_xml,
    remove_child,
    set_int,
    write_client_image,
    write_server_image,
)


WORLD_MAPS = (
    "WorldMap082",
    "WorldMap0821",
    "WorldMap0822",
    "WorldMap0823",
    "WorldMap0824",
    "WorldMap0825",
    "WorldMap0826",
)
BRIDGE_WORLD_MAP = "WorldMap080"
REGION_MAPS = frozenset(WORLD_MAPS[1:])
LEGACY_MAP_LIST_FIELDS = frozenset({"spot", "type", "mapNo", "title", "desc"})
# TMS 28/29 are the modern equivalents of the legacy field/town markers.
LEGACY_TYPE_BY_TMS_TYPE = {28: 1, 29: 0}
# Seven of the 152 migrated fields are hidden or instance maps not shown by TMS.
EXPECTED_LISTED_MAPS = 145


def renumber(parent: WzSubProperty) -> None:
    children = list(parent.children())
    parent._children.clear()
    for index, child in enumerate(children):
        child.name = str(index)
        parent.add(child)


def filter_map_numbers(entry: WzSubProperty) -> int:
    map_numbers = entry.child("mapNo")
    if not isinstance(map_numbers, WzSubProperty):
        raise RuntimeError(f"MapList/{entry.name} has no mapNo list")
    values = [
        int(child.value)
        for child in map_numbers.children()
        if int(child.value) in MAP_ID_SET
    ]
    map_numbers._children.clear()
    for index, map_id in enumerate(values):
        map_numbers.add(WzIntProperty(str(index), map_id, map_numbers))
    return len(values)


def sanitize_map_list(root: WzSubProperty) -> None:
    map_list = root.child("MapList")
    if not isinstance(map_list, WzSubProperty):
        raise RuntimeError("world map has no MapList")
    for entry in list(map_list.children()):
        if filter_map_numbers(entry) == 0:
            remove_child(map_list, entry.name)
            continue
        source_type = int(child_value(entry, "type"))
        legacy_type = LEGACY_TYPE_BY_TMS_TYPE.get(source_type)
        if legacy_type is None:
            raise RuntimeError(f"unsupported TMS world-map type {source_type}")
        set_int(entry, "type", legacy_type)
        for child in list(entry.children()):
            if child.name not in LEGACY_MAP_LIST_FIELDS:
                remove_child(entry, child.name)
    renumber(map_list)


def sanitize_map_links(root: WzSubProperty, name: str) -> None:
    map_links = root.child("MapLink")
    if name != WORLD_MAPS[0]:
        if map_links is not None:
            remove_child(root, "MapLink")
        return
    if not isinstance(map_links, WzSubProperty):
        raise RuntimeError("Arcane River overview has no MapLink")
    for entry in list(map_links.children()):
        link_map = child_value(entry.child("link"), "linkMap")
        if link_map not in REGION_MAPS:
            remove_child(map_links, entry.name)
    renumber(map_links)


def sanitize_world_map(root: WzSubProperty, name: str) -> None:
    for child in list(root.children()):
        if child.name not in {"info", "BaseImg", "MapList", "MapLink"}:
            remove_child(root, child.name)
    sanitize_map_list(root)
    sanitize_map_links(root, name)


def build_bridge_world_map() -> tuple[WzImage, CanvasMaterializer]:
    source_path = SOURCE / f"Map/WorldMap/{BRIDGE_WORLD_MAP}.img"
    source = load_image(source_path, BMS_KEY)
    target = load_image(
        ROOT / f"clien/Data/Map/WorldMap/{BRIDGE_WORLD_MAP}.img", GMS_KEY
    )
    map_links = target.root.child("MapLink")
    if not isinstance(map_links, WzSubProperty):
        map_links = WzSubProperty("MapLink", target.root)
        target.root.add(map_links)
    for entry in list(map_links.children()):
        if child_value(entry.child("link"), "linkMap") == WORLD_MAPS[0]:
            remove_child(map_links, entry.name)
    renumber(map_links)

    source_entry = source.get("MapLink/1")
    if not isinstance(source_entry, WzSubProperty):
        raise RuntimeError("TMS WorldMap080 has no Arcane River bridge")
    materializer = CanvasMaterializer()
    map_links.add(
        clone_property(
            source_entry,
            map_links,
            source,
            source_path,
            materializer,
            str(len(map_links.children())),
        )
    )
    return target, materializer


def write_bridge_server_xml(image: WzImage) -> None:
    path = ROOT / f"gms-server/wz/Map.wz/WorldMap/{BRIDGE_WORLD_MAP}.img.xml"
    root = ET.parse(path).getroot()
    map_links = next(
        (child for child in root if child.get("name") == "MapLink"), None
    )
    if map_links is None:
        map_links = ET.Element("imgdir", {"name": "MapLink"})
        if len(root):
            root[-1].tail = "\n  "
        map_links.text = "\n    "
        map_links.tail = "\n"
        root.append(map_links)
    for entry in list(map_links):
        link_map = entry.find("./imgdir[@name='link']/string[@name='linkMap']")
        if link_map is not None and link_map.get("value") == WORLD_MAPS[0]:
            map_links.remove(entry)
    for index, entry in enumerate(map_links):
        entry.set("name", str(index))
        entry.tail = "\n    "

    bridge = image.get("MapLink/0")
    if not isinstance(bridge, WzSubProperty):
        raise RuntimeError("WorldMap080: generated bridge is missing")
    entry = ET.fromstring(property_to_xml(bridge, 0))
    entry.set("name", str(len(map_links)))
    ET.indent(entry, space="  ", level=2)
    entry.tail = "\n  "
    map_links.append(entry)

    backup(path)
    xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    atomic_write_text(
        path,
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + xml.replace(" />", "/>")
        + "\n",
    )


def scalar_map_ids(image: WzImage) -> set[int]:
    result: set[int] = set()
    map_list = image.get("MapList")
    if not isinstance(map_list, WzSubProperty):
        return result
    for entry in map_list.children():
        map_numbers = entry.child("mapNo")
        if isinstance(map_numbers, WzSubProperty):
            result.update(int(child.value) for child in map_numbers.children())
    return result


def walk(node):
    yield node
    for child in node.children():
        yield from walk(child)


def audit_image(image: WzImage, name: str) -> dict[str, int]:
    map_list = image.get("MapList")
    if not isinstance(map_list, WzSubProperty):
        raise RuntimeError(f"{name}: missing MapList")
    if [child.name for child in map_list.children()] != [
        str(index) for index in range(len(map_list.children()))
    ]:
        raise RuntimeError(f"{name}: MapList indices are not dense")
    for entry in map_list.children():
        if set(child.name for child in entry.children()) - LEGACY_MAP_LIST_FIELDS:
            raise RuntimeError(f"{name}: unsupported MapList fields remain")
        if int(child_value(entry, "type")) not in {0, 1, 2, 3}:
            raise RuntimeError(f"{name}: non-legacy MapList type remains")
        map_numbers = entry.child("mapNo")
        if not isinstance(map_numbers, WzSubProperty):
            raise RuntimeError(f"{name}: missing mapNo")
        if [child.name for child in map_numbers.children()] != [
            str(index) for index in range(len(map_numbers.children()))
        ]:
            raise RuntimeError(f"{name}: mapNo indices are not dense")
    canvases = 0
    for node in walk(image.root):
        if isinstance(node, WzStringProperty) and node.name in {"_outlink", "_inlink"}:
            raise RuntimeError(f"{name}: unresolved canvas link remains")
        if isinstance(node, WzCanvasProperty):
            canvases += 1
            if (int(node.format), int(node.format2)) != (1, 0):
                raise RuntimeError(f"{name}: unsupported canvas format")
            if int(node.width) > 2048 or int(node.height) > 2048:
                raise RuntimeError(f"{name}: oversized canvas")
    if name == WORLD_MAPS[0]:
        map_links = image.get("MapLink")
        links = {
            child_value(entry.child("link"), "linkMap")
            for entry in map_links.children()
        } if isinstance(map_links, WzSubProperty) else set()
        if links != REGION_MAPS:
            raise RuntimeError(f"{name}: unexpected region links {sorted(links)}")
    return {"map_entries": len(map_list.children()), "canvases": canvases}


def audit_bridge(image: WzImage) -> None:
    map_links = image.get("MapLink")
    if not isinstance(map_links, WzSubProperty):
        raise RuntimeError("WorldMap080: missing MapLink")
    bridges = [
        entry
        for entry in map_links.children()
        if child_value(entry.child("link"), "linkMap") == WORLD_MAPS[0]
    ]
    if len(bridges) != 1:
        raise RuntimeError(f"WorldMap080: expected one Arcane River bridge, got {len(bridges)}")
    canvas = bridges[0].get("link/linkImg")
    if not isinstance(canvas, WzCanvasProperty):
        raise RuntimeError("WorldMap080: bridge has no link image")
    if (int(canvas.format), int(canvas.format2)) != (1, 0):
        raise RuntimeError("WorldMap080: bridge canvas is not legacy ARGB4444")
    if canvas.child("_outlink") is not None or canvas.child("_inlink") is not None:
        raise RuntimeError("WorldMap080: unresolved bridge canvas link remains")


def verify_written(expected: dict[str, WzImage]) -> None:
    listed: set[int] = set()
    for name, source in expected.items():
        client_path = ROOT / f"clien/Data/Map/WorldMap/{name}.img"
        written = WzImage.from_file(str(client_path), key=GMS_KEY)
        audit_image(written, name)
        if image_to_xml(written, f"{name}.img") != image_to_xml(source, f"{name}.img"):
            raise RuntimeError(f"{name}: client IMG round-trip mismatch")
        server_path = ROOT / f"gms-server/wz/Map.wz/WorldMap/{name}.img.xml"
        if server_path.read_text(encoding="utf-8") != image_to_xml(source, f"{name}.img"):
            raise RuntimeError(f"{name}: server XML mismatch")
        if name != WORLD_MAPS[0]:
            listed.update(scalar_map_ids(written))
    if len(listed) != EXPECTED_LISTED_MAPS or not listed <= MAP_ID_SET:
        raise RuntimeError(
            f"world-map coverage mismatch: {len(listed)} listed, "
            f"{len(listed - MAP_ID_SET)} unavailable"
        )


def verify_bridge_written(expected: WzImage) -> None:
    name = BRIDGE_WORLD_MAP
    client_path = ROOT / f"clien/Data/Map/WorldMap/{name}.img"
    written = WzImage.from_file(str(client_path), key=GMS_KEY)
    audit_bridge(written)
    expected_xml = image_to_xml(expected, f"{name}.img")
    if image_to_xml(written, f"{name}.img") != expected_xml:
        raise RuntimeError(f"{name}: client IMG round-trip mismatch")
    server_path = ROOT / f"gms-server/wz/Map.wz/WorldMap/{name}.img.xml"
    server_root = ET.parse(server_path).getroot()
    server_links = next(
        (child for child in server_root if child.get("name") == "MapLink"), None
    )
    bridges = [] if server_links is None else [
        entry
        for entry in server_links
        if (
            entry.find("./imgdir[@name='link']/string[@name='linkMap']") is not None
            and entry.find("./imgdir[@name='link']/string[@name='linkMap']").get("value")
            == WORLD_MAPS[0]
        )
    ]
    if len(bridges) != 1:
        raise RuntimeError(f"{name}: server XML bridge mismatch")


def main() -> int:
    outputs: dict[str, WzImage] = {}
    totals = {"files": 0, "map_entries": 0, "canvases": 0, "links": 0}
    bridge, bridge_materializer = build_bridge_world_map()
    audit_bridge(bridge)
    write_client_image(
        ROOT / f"clien/Data/Map/WorldMap/{BRIDGE_WORLD_MAP}.img", bridge
    )
    write_bridge_server_xml(bridge)
    totals["files"] += 1
    totals["canvases"] += 1
    totals["links"] += bridge_materializer.links
    for name in WORLD_MAPS:
        source_path = SOURCE / f"Map/WorldMap/{name}.img"
        image, materializer = clone_image(
            source_path, lambda root, value=name: sanitize_world_map(root, value)
        )
        stats = audit_image(image, name)
        write_client_image(ROOT / f"clien/Data/Map/WorldMap/{name}.img", image)
        write_server_image(
            ROOT / f"gms-server/wz/Map.wz/WorldMap/{name}.img.xml",
            image,
            f"{name}.img",
        )
        outputs[name] = image
        totals["files"] += 1
        totals["map_entries"] += stats["map_entries"]
        totals["canvases"] += stats["canvases"]
        totals["links"] += materializer.links
    verify_bridge_written(bridge)
    verify_written(outputs)
    print("Arcane River world maps", totals)
    print(f"listed maps={EXPECTED_LISTED_MAPS}, unavailable references=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
