#!/usr/bin/env python3
"""Restore legacy-visible Cave of Repose script portals incrementally."""

from __future__ import annotations

import argparse
import io
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402

import migrate_arcane_river_fields as migration  # noqa: E402
from repair_arcane_river_8641002_attack_gap import (  # noqa: E402
    PropertyList,
    Record,
    find_node_span,
    read_property_list,
    sha256,
)


CLIENT_ROOT = ROOT / "clien/Data/Map/Map/Map4"
SERVER_ROOT = ROOT / "gms-server/wz/Map.wz/Map/Map4"
BACKUP_ROOT = Path("/private/tmp/beidou-arcane-river-cave-portals-backup")
KEY = WzKey.for_region("GMS")
NEW_MAPS = {450001219, 450001230, 450001240, 450001250}
NEW_MOBS = {8641012}
NEW_NPCS = {3003140, 3003143}
STRING_INSERTIONS = (
    ("Map", 450001219, "grandis"),
    ("Map", 450001230, "grandis"),
    ("Map", 450001240, "grandis"),
    ("Map", 450001250, "grandis"),
    ("Mob", 8641012, None),
    ("Npc", 3003140, None),
    ("Npc", 3003143, None),
)


def atomic_write(path: Path, data: bytes | str) -> None:
    mode = "wb" if isinstance(data, bytes) else "w"
    kwargs = {} if isinstance(data, bytes) else {"encoding": "utf-8"}
    with tempfile.NamedTemporaryFile(
        mode, prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
        delete=False, **kwargs
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def backup(path: Path) -> None:
    if not path.exists():
        return
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def load_image(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def locate_root(data: bytes) -> PropertyList:
    reader = WzBinaryReader(io.BytesIO(data), KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported IMG header")
    reader.skip(2)
    return read_property_list(reader, len(data))


def locate_extended_children(data: bytes, parent: Record) -> PropertyList:
    if parent.tag != 9 or parent.block_start is None or parent.block_size is None:
        raise RuntimeError(f"{parent.name} is not an extended Property block")
    reader = WzBinaryReader(io.BytesIO(data), KEY)
    reader.seek(parent.block_start)
    if reader.read_string_block(0) != "Property":
        raise RuntimeError(f"{parent.name} body is not a Property block")
    reader.skip(2)
    return read_property_list(reader, parent.block_start + parent.block_size)


def locate_portal_entry(
    data: bytes, entry_name: str
) -> tuple[PropertyList, Record, PropertyList, Record, PropertyList]:
    roots = locate_root(data)
    portal = next((record for record in roots.records if record.name == "portal"), None)
    if portal is None:
        raise RuntimeError("missing portal root")
    entries = locate_extended_children(data, portal)
    entry = next((record for record in entries.records if record.name == entry_name), None)
    if entry is None:
        raise RuntimeError(f"missing portal entry {entry_name}")
    properties = locate_extended_children(data, entry)
    return roots, portal, entries, entry, properties


def encode_string_record(image: WzImage, name: str, value: str, parent) -> bytes:
    encoded = _encode_property_list(
        (WzStringProperty(name, value, parent),), image.wz_file.reader
    )
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"unexpected encoded {name} record prefix")
    return encoded[len(prefix):]


def encode_property_record(image: WzImage, prop) -> bytes:
    encoded = _encode_property_list((prop,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"unexpected encoded {prop.name} record prefix")
    return encoded[len(prefix):]


def record_bytes(data: bytes, records: tuple[Record, ...]) -> dict[str, bytes]:
    return {record.name: data[record.start:record.end] for record in records}


def insertion_offset(records: tuple[Record, ...], item_id: int, fallback: int) -> int:
    for record in records:
        if record.name.isdigit() and int(record.name) > item_id:
            return record.start
    return records[-1].end if records else fallback


def source_string_node(img_name: str, item_id: int):
    source = migration.load_image(
        migration.SOURCE / f"String/{img_name}.img", migration.BMS_KEY
    )
    node = (
        migration.source_map_string(source, item_id)
        if img_name == "Map"
        else source.root.get(str(item_id))
    )
    if node is None:
        raise RuntimeError(f"source String/{img_name}.img is missing {item_id}")
    return node


def insert_client_string(
    data: bytes, img_name: str, item_id: int, category_name: str | None
) -> bytes:
    image = load_image(data, f"String/{img_name}.img")
    path = f"{category_name}/{item_id}" if category_name else str(item_id)
    existing = image.root.get(path)
    source_node = source_string_node(img_name, item_id)
    expected_values = {
        child.name: getattr(child, "value", None) for child in source_node.children()
    }
    if existing is not None:
        actual_values = {
            child.name: getattr(child, "value", None) for child in existing.children()
        }
        if actual_values != expected_values:
            raise RuntimeError(f"conflicting client String/{img_name}.img/{path}")
        return data

    roots = locate_root(data)
    parent_record = None
    if category_name:
        parent_record = next(
            (record for record in roots.records if record.name == category_name), None
        )
        if parent_record is None:
            raise RuntimeError(f"missing client String/{img_name}.img/{category_name}")
        children = locate_extended_children(data, parent_record)
    else:
        children = roots
    encoded = encode_property_record(image, source_node)
    position = insertion_offset(
        children.records,
        item_id,
        children.count_offset + children.count_length,
    )
    updated = bytearray(data[:position] + encoded + data[position:])
    encoded_count = encode_compressed_int(children.count + 1)
    if len(encoded_count) != children.count_length:
        raise RuntimeError(f"String/{img_name}.img count encoding width changed")
    updated[children.count_offset:children.count_offset + children.count_length] = encoded_count
    if parent_record is not None:
        if parent_record.size_offset is None or parent_record.block_size is None:
            raise AssertionError(f"String/{img_name}.img parent size is missing")
        struct.pack_into(
            "<I", updated, parent_record.size_offset, parent_record.block_size + len(encoded)
        )
    result = bytes(updated)

    verified = load_image(result, f"String/{img_name}.img")
    verified_node = verified.root.get(path)
    actual_values = {
        child.name: getattr(child, "value", None) for child in verified_node.children()
    }
    if actual_values != expected_values:
        raise RuntimeError(f"client String/{img_name}.img/{path} insert failed")
    after_roots = locate_root(result)
    before_root_raw = record_bytes(data, roots.records)
    after_root_raw = record_bytes(result, after_roots.records)
    for name, raw in before_root_raw.items():
        if name != category_name and raw != after_root_raw[name]:
            raise RuntimeError(f"unapproved String/{img_name}.img root record changed: {name}")
    if parent_record is not None:
        after_parent = next(
            record for record in after_roots.records if record.name == category_name
        )
        after_children = locate_extended_children(result, after_parent)
        after_child_raw = record_bytes(result, after_children.records)
        for name, raw in record_bytes(data, children.records).items():
            if raw != after_child_raw[name]:
                raise RuntimeError(
                    f"unapproved String/{img_name}.img/{category_name} record changed: {name}"
                )
    return result


def insert_server_string(
    text: str, img_name: str, item_id: int, category_name: str | None
) -> str:
    root = ET.fromstring(text)
    parent = root.find(f'./imgdir[@name="{category_name}"]') if category_name else root
    if parent is None:
        raise RuntimeError(f"missing server String/{img_name}.img/{category_name}")
    source_node = source_string_node(img_name, item_id)
    expected_values = {
        child.name: str(getattr(child, "value", "")) for child in source_node.children()
    }
    existing = next((node for node in parent if node.get("name") == str(item_id)), None)
    if existing is not None:
        actual_values = {child.get("name"): child.get("value") for child in existing}
        if actual_values != expected_values:
            raise RuntimeError(f"conflicting server String/{img_name}.img/{item_id}")
        return text

    parent_start, parent_end = (0, len(text))
    if category_name:
        parent_start, parent_end = find_node_span(
            text, "imgdir", category_name, 0, len(text)
        )
    successors = sorted(
        int(node.get("name"))
        for node in parent
        if str(node.get("name", "")).isdigit() and int(node.get("name")) > item_id
    )
    if successors:
        position, _ = find_node_span(
            text, "imgdir", str(successors[0]), parent_start, parent_end
        )
    else:
        position = text.rfind("</imgdir>", parent_start, parent_end)
        if position < 0:
            raise RuntimeError(f"server String/{img_name}.img parent closing tag is missing")
    encoded = migration.property_to_xml(source_node, 0)
    result = text[:position] + encoded + text[position:]
    verified = ET.fromstring(result)
    verified_parent = (
        verified.find(f'./imgdir[@name="{category_name}"]')
        if category_name
        else verified
    )
    verified_node = next(
        node for node in verified_parent if node.get("name") == str(item_id)
    )
    actual_values = {child.get("name"): child.get("value") for child in verified_node}
    if actual_values != expected_values:
        raise RuntimeError(f"server String/{img_name}.img/{item_id} insert failed")
    if text[:position] != result[:position] or text[position:] != result[position + len(encoded):]:
        raise RuntimeError(f"server String/{img_name}.img changed outside inserted record")
    return result


def build_new_image(kind: str, item_id: int) -> tuple[bytes, str]:
    if kind == "Map":
        source = migration.SOURCE / f"Map/Map/Map4/{item_id}.img"
        sanitizer = lambda root: migration.sanitize_map(root, item_id)
    elif kind == "Npc":
        source = migration.SOURCE / f"Npc/{item_id}.img"
        sanitizer = migration.sanitize_npc
    elif kind == "Mob":
        source = migration.extract_mob(item_id)
        sanitizer = lambda root: migration.sanitize_mob(root, item_id)
    else:
        raise ValueError(kind)
    image, _ = migration.clone_image(source, sanitizer)
    client = migration.encode_image_body(image, migration.gms_reader())
    verified = load_image(client, f"{kind}/{item_id}.img")
    for node, path in migration.walk(verified.root):
        if not isinstance(node, migration.WzCanvasProperty):
            continue
        if (int(node.format), int(node.format2)) != (1, 0):
            raise RuntimeError(f"{kind}/{item_id}.img/{path} is not ARGB4444")
        migration.decode_canvas(node, region="GMS")
    server = migration.image_to_xml(image, f"{item_id}.img")
    ET.fromstring(server)
    return client, server


def locate_property_parent(
    data: bytes, parent_path: str
) -> tuple[PropertyList, tuple[Record, ...], PropertyList]:
    roots = locate_root(data)
    current = roots
    ancestors: list[Record] = []
    for name in parent_path.split("/"):
        record = next((node for node in current.records if node.name == name), None)
        if record is None:
            raise RuntimeError(f"missing property parent {parent_path} at {name}")
        ancestors.append(record)
        current = locate_extended_children(data, record)
    return roots, tuple(ancestors), current


def verify_ancestor_records_unchanged(
    before: bytes, after: bytes, parent_path: str
) -> None:
    before_roots, before_ancestors, before_children = locate_property_parent(
        before, parent_path
    )
    after_roots, after_ancestors, after_children = locate_property_parent(
        after, parent_path
    )
    before_lists = [before_roots]
    after_lists = [after_roots]
    for record in before_ancestors[:-1]:
        before_lists.append(locate_extended_children(before, record))
    for record in after_ancestors[:-1]:
        after_lists.append(locate_extended_children(after, record))
    path_names = parent_path.split("/")
    for depth, (before_list, after_list) in enumerate(zip(before_lists, after_lists)):
        before_raw = record_bytes(before, before_list.records)
        after_raw = record_bytes(after, after_list.records)
        nested_name = path_names[depth]
        for name, raw in before_raw.items():
            if name != nested_name and raw != after_raw[name]:
                raise RuntimeError(
                    f"unapproved asset sibling changed at {'/'.join(path_names[:depth])}/{name}"
                )
    after_child_raw = record_bytes(after, after_children.records)
    for name, raw in record_bytes(before, before_children.records).items():
        if raw != after_child_raw[name]:
            raise RuntimeError(f"existing asset record changed at {parent_path}/{name}")


def insert_asset_branch(
    data: bytes, kind: str, target_name: str, branch: str
) -> bytes:
    target = load_image(data, f"Map/{kind}/{target_name}.img")
    if target.root.get(branch) is not None:
        return data
    source_name = "extinction" if target_name == "extinctionLegacy" else target_name
    source_path = migration.SOURCE / f"Map/{kind}/{source_name}.img"
    source = migration.load_image(source_path, migration.BMS_KEY)
    insert_path = branch
    while "/" in insert_path and target.root.get(insert_path.rpartition("/")[0]) is None:
        insert_path = insert_path.rpartition("/")[0]
    source_node = source.root.get(insert_path)
    if source_node is None:
        raise RuntimeError(f"source asset is missing {kind}/{source_name}.img/{insert_path}")
    parent_path, _, leaf = insert_path.rpartition("/")
    semantic_parent = target.root.get(parent_path)
    if not isinstance(semantic_parent, WzSubProperty):
        raise RuntimeError(f"target asset parent is missing: {kind}/{target_name}/{parent_path}")
    materializer = migration.CanvasMaterializer()
    cloned = migration.clone_property(
        source_node,
        semantic_parent,
        source,
        source_path,
        materializer,
        leaf,
    )
    encoded = encode_property_record(target, cloned)
    _, ancestors, children = locate_property_parent(data, parent_path)
    source_parent = source.root.get(parent_path)
    source_order = [child.name for child in source_parent.children()]
    source_index = source_order.index(leaf)
    successors = set(source_order[source_index + 1:])
    position = next(
        (record.start for record in children.records if record.name in successors),
        children.records[-1].end
        if children.records
        else children.count_offset + children.count_length,
    )
    updated = bytearray(data[:position] + encoded + data[position:])
    encoded_count = encode_compressed_int(children.count + 1)
    if len(encoded_count) != children.count_length:
        raise RuntimeError(f"asset count encoding width changed: {kind}/{target_name}/{branch}")
    updated[children.count_offset:children.count_offset + children.count_length] = encoded_count
    for record in ancestors:
        if record.size_offset is None or record.block_size is None:
            raise RuntimeError(f"asset parent size is missing: {kind}/{target_name}/{record.name}")
        struct.pack_into(
            "<I", updated, record.size_offset, record.block_size + len(encoded)
        )
    result = bytes(updated)

    verified = load_image(result, f"Map/{kind}/{target_name}.img")
    node = verified.root.get(branch)
    if node is None:
        raise RuntimeError(f"asset branch insert failed: {kind}/{target_name}/{branch}")
    for child, path in migration.walk(node):
        if not isinstance(child, migration.WzCanvasProperty):
            continue
        if (int(child.format), int(child.format2)) != (1, 0):
            raise RuntimeError(f"non-ARGB4444 asset Canvas: {kind}/{target_name}/{branch}/{path}")
        migration.decode_canvas(child, region="GMS")
    verify_ancestor_records_unchanged(data, result, parent_path)
    return result


def required_new_map_assets() -> dict[tuple[str, str], set[str]]:
    dependencies = {
        "assets": defaultdict(set),
        "mobs": set(),
        "npcs": set(),
        "bgms": set(),
        "marks": set(),
    }
    for map_id in sorted(NEW_MAPS):
        image, _ = migration.clone_image(
            migration.SOURCE / f"Map/Map/Map4/{map_id}.img",
            lambda root, value=map_id: migration.sanitize_map(root, value),
        )
        migration.merge_dependency_sets(dependencies, migration.collect_dependencies(image))
    return dependencies["assets"]


def projected_source_portal(map_id: int, portal_name: str):
    source = migration.load_image(
        migration.SOURCE / f"Map/Map/Map4/{map_id}.img", migration.BMS_KEY
    )
    migration.sanitize_map(source.root, map_id)
    portal = source.root.child("portal")
    entry = next(
        (
            node for node in portal.children()
            if migration.child_value(node, "pn") == portal_name
        ),
        None,
    )
    if entry is None:
        raise RuntimeError(f"source {map_id}: missing projected portal {portal_name}")
    return entry


def insert_client_portal(
    data: bytes, map_id: int, portal_name: str, target_map: int, target_name: str,
    portal_type: int = 2,
) -> bytes:
    image = load_image(data, f"{map_id}.img")
    source_entry = projected_source_portal(map_id, portal_name)
    expected = {"pt": portal_type, "tm": target_map, "tn": target_name}
    if {
        name: migration.child_value(source_entry, name) for name in expected
    } != expected:
        raise RuntimeError(f"source {map_id}: projected {portal_name} target mismatch")

    roots = locate_root(data)
    portal_record = next(record for record in roots.records if record.name == "portal")
    entries = locate_extended_children(data, portal_record)
    encoded = encode_property_record(image, source_entry)
    position = insertion_offset(
        entries.records,
        int(source_entry.name),
        entries.count_offset + entries.count_length,
    )
    updated = bytearray(data[:position] + encoded + data[position:])
    encoded_count = encode_compressed_int(entries.count + 1)
    if len(encoded_count) != entries.count_length:
        raise RuntimeError(f"{map_id}: portal count encoding width changed")
    updated[entries.count_offset:entries.count_offset + entries.count_length] = encoded_count
    if portal_record.size_offset is None or portal_record.block_size is None:
        raise AssertionError(f"{map_id}: portal block size is missing")
    struct.pack_into(
        "<I", updated, portal_record.size_offset, portal_record.block_size + len(encoded)
    )
    result = bytes(updated)

    verified = load_image(result, f"{map_id}.img")
    verified_portal = verified.root.child("portal")
    verified_entry = next(
        node for node in verified_portal.children()
        if migration.child_value(node, "pn") == portal_name
    )
    actual = {
        name: migration.child_value(verified_entry, name) for name in expected
    }
    if actual != expected or verified_entry.child("script") is not None:
        raise RuntimeError(f"{map_id}: inserted {portal_name} is incompatible: {actual}")
    after_roots = locate_root(result)
    before_root_raw = record_bytes(data, roots.records)
    after_root_raw = record_bytes(result, after_roots.records)
    for name, raw in before_root_raw.items():
        if name != "portal" and raw != after_root_raw[name]:
            raise RuntimeError(f"{map_id}: unapproved root record changed: {name}")
    after_portal_record = next(
        record for record in after_roots.records if record.name == "portal"
    )
    after_entries = locate_extended_children(result, after_portal_record)
    after_entry_raw = record_bytes(result, after_entries.records)
    for name, raw in record_bytes(data, entries.records).items():
        if raw != after_entry_raw[name]:
            raise RuntimeError(f"{map_id}: existing portal entry changed: {name}")
    return result


def patch_client(
    data: bytes, map_id: int, portal_name: str, target_map: int, target_name: str,
    portal_type: int = 2,
) -> bytes:
    image = load_image(data, f"{map_id}.img")
    portal = image.root.get("portal")
    if not isinstance(portal, WzSubProperty):
        raise RuntimeError(f"{map_id}: missing portal root")
    semantic_entry = next(
        (entry for entry in portal.children() if entry.get("pn").value == portal_name), None
    )
    if not isinstance(semantic_entry, WzSubProperty):
        return insert_client_portal(
            data, map_id, portal_name, target_map, target_name, portal_type
        )
    expected = {"pt": portal_type, "tm": target_map, "tn": target_name}
    current = {name: semantic_entry.get(name).value for name in expected}
    if current == expected:
        return data
    allowed = {
        "pt": {0, 2, 3, 9}, "tm": {999999999, target_map}, "tn": {"", target_name}
    }
    if any(current[name] not in allowed[name] for name in expected):
        raise RuntimeError(f"{map_id}: conflicting {portal_name} values {current}")

    roots, portal_record, entries, entry_record, properties = locate_portal_entry(
        data, semantic_entry.name
    )
    property_records = {record.name: record for record in properties.records}
    updated = bytearray(data)
    for name, value in (("pt", portal_type), ("tm", target_map)):
        node = semantic_entry.get(name)
        encoded = encode_compressed_int(value)
        if not isinstance(node, WzIntProperty) or node._value_offset is None:
            raise RuntimeError(f"{map_id}: {portal_name}/{name} is not patchable")
        if len(encoded) != node._value_length:
            raise RuntimeError(f"{map_id}: {portal_name}/{name} encoding width changed")
        updated[node._value_offset:node._value_offset + node._value_length] = encoded

    delta = 0
    if current["tn"] != target_name:
        tn_record = property_records["tn"]
        encoded_tn = encode_string_record(image, "tn", target_name, semantic_entry)
        updated = bytearray(
            updated[:tn_record.start] + encoded_tn + updated[tn_record.end:]
        )
        delta = len(encoded_tn) - (tn_record.end - tn_record.start)
        if entry_record.size_offset is None or entry_record.block_size is None:
            raise AssertionError("portal entry block size field missing")
        if portal_record.size_offset is None or portal_record.block_size is None:
            raise AssertionError("portal root block size field missing")
        struct.pack_into(
            "<I", updated, entry_record.size_offset, entry_record.block_size + delta
        )
        struct.pack_into(
            "<I", updated, portal_record.size_offset, portal_record.block_size + delta
        )
    result = bytes(updated)

    after_image = load_image(result, f"{map_id}.img")
    after_entry = next(
        entry for entry in after_image.root.get("portal").children()
        if entry.get("pn").value == portal_name
    )
    if {name: after_entry.get(name).value for name in expected} != expected:
        raise RuntimeError(f"{map_id}: {portal_name} remains invalid")
    after_roots, _, after_entries, _, after_properties = locate_portal_entry(
        result, semantic_entry.name
    )
    before_root_raw = record_bytes(data, roots.records)
    after_root_raw = record_bytes(result, after_roots.records)
    for name in before_root_raw:
        if name != "portal" and before_root_raw[name] != after_root_raw[name]:
            raise RuntimeError(f"{map_id}: unapproved root record changed: {name}")
    before_entry_raw = record_bytes(data, entries.records)
    after_entry_raw = record_bytes(result, after_entries.records)
    for name in before_entry_raw:
        if name != semantic_entry.name and before_entry_raw[name] != after_entry_raw[name]:
            raise RuntimeError(f"{map_id}: unapproved portal entry changed: {name}")
    before_property_raw = record_bytes(data, properties.records)
    after_property_raw = record_bytes(result, after_properties.records)
    for name in before_property_raw:
        if name not in expected and before_property_raw[name] != after_property_raw[name]:
            raise RuntimeError(f"{map_id}: unapproved {portal_name} field changed: {name}")
    return result


def patch_server(
    text: str, map_id: int, portal_name: str, target_map: int, target_name: str,
    portal_type: int = 2,
) -> str:
    root = ET.fromstring(text)
    portal = root.find('./imgdir[@name="portal"]')
    if portal is None:
        raise RuntimeError(f"{map_id}: server XML is missing portal root")
    entry = next(
        (
            node for node in portal.findall("./imgdir")
            if (node.find('./string[@name="pn"]') is not None)
            and node.find('./string[@name="pn"]').get("value") == portal_name
        ),
        None,
    )
    if entry is None:
        source_entry = projected_source_portal(map_id, portal_name)
        portal_start, portal_end = find_node_span(
            text, "imgdir", "portal", 0, len(text)
        )
        successors = sorted(
            int(node.get("name"))
            for node in portal.findall("./imgdir")
            if str(node.get("name", "")).isdigit()
            and int(node.get("name")) > int(source_entry.name)
        )
        if successors:
            position, _ = find_node_span(
                text, "imgdir", str(successors[0]), portal_start, portal_end
            )
            line_start = text.rfind("\n", 0, position) + 1
            if not text[line_start:position].strip():
                position = line_start
        else:
            position = text.rfind("</imgdir>", portal_start, portal_end)
            if position < 0:
                raise RuntimeError(f"{map_id}: server portal closing tag is missing")
        encoded = migration.property_to_xml(source_entry, 2) + "\n"
        result = text[:position] + encoded + text[position:]
        verified = ET.fromstring(result)
        verified_portal = verified.find('./imgdir[@name="portal"]')
        verified_entry = next(
            node for node in verified_portal.findall("./imgdir")
            if node.find('./string[@name="pn"]') is not None
            and node.find('./string[@name="pn"]').get("value") == portal_name
        )
        expected = {"pt": str(portal_type), "tm": str(target_map), "tn": target_name}
        for name, value in expected.items():
            tag = "string" if name == "tn" else "int"
            node = verified_entry.find(f'./{tag}[@name="{name}"]')
            if node is None or node.get("value") != value:
                raise RuntimeError(f"{map_id}: server inserted {portal_name}/{name} invalid")
        if verified_entry.find('./string[@name="script"]') is not None:
            raise RuntimeError(f"{map_id}: server inserted {portal_name} retains script")
        if text[:position] != result[:position] or text[position:] != result[position + len(encoded):]:
            raise RuntimeError(f"{map_id}: server XML changed outside inserted portal")
        return result
    expected = {"pt": str(portal_type), "tm": str(target_map), "tn": target_name}
    current = {}
    for name in expected:
        tag = "string" if name == "tn" else "int"
        node = entry.find(f'./{tag}[@name="{name}"]')
        if node is None:
            raise RuntimeError(f"{map_id}: server {portal_name}/{name} is missing")
        current[name] = node.get("value")
    if current == expected:
        return text

    portal_start, portal_end = find_node_span(text, "imgdir", "portal", 0, len(text))
    entry_start, entry_end = find_node_span(
        text, "imgdir", entry.get("name"), portal_start, portal_end
    )
    entry_text = text[entry_start:entry_end]
    replacements = {
        f'<int name="pt" value="{current["pt"]}"/>': f'<int name="pt" value="{portal_type}"/>',
        f'<int name="tm" value="{current["tm"]}"/>': f'<int name="tm" value="{target_map}"/>',
        f'<string name="tn" value="{current["tn"]}"/>': f'<string name="tn" value="{target_name}"/>',
    }
    for old, new in replacements.items():
        if old not in entry_text:
            raise RuntimeError(f"{map_id}: expected server field not found: {old}")
        entry_text = entry_text.replace(old, new, 1)
    result = text[:entry_start] + entry_text + text[entry_end:]
    verified = ET.fromstring(result)
    verified_portal = verified.find('./imgdir[@name="portal"]')
    verified_entry = next(
        node for node in verified_portal.findall("./imgdir")
        if node.find('./string[@name="pn"]') is not None
        and node.find('./string[@name="pn"]').get("value") == portal_name
    )
    for name, value in expected.items():
        tag = "string" if name == "tn" else "int"
        if verified_entry.find(f'./{tag}[@name="{name}"]').get("value") != value:
            raise RuntimeError(f"{map_id}: server {portal_name}/{name} remains invalid")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()
    changed: list[str] = []
    pending: list[tuple[Path, bytes | str]] = []
    hashes: list[str] = []
    map_clients: dict[int, bytes] = {}
    map_servers: dict[int, str] = {}

    for (kind, name), branches in sorted(required_new_map_assets().items()):
        path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
        before = path.read_bytes()
        after = before
        for branch in sorted(branches):
            after = insert_asset_branch(after, kind, name, branch)
        if after != before:
            pending.append((path, after))
            changed.append(f"asset {kind}/{name}")

    for map_id in sorted(NEW_MAPS):
        client = CLIENT_ROOT / f"{map_id}.img"
        server = SERVER_ROOT / f"{map_id}.img.xml"
        client_expected, server_expected = build_new_image("Map", map_id)
        artifact_changed = False
        if client.exists():
            map_clients[map_id] = client.read_bytes()
            load_image(map_clients[map_id], client.name)
        else:
            map_clients[map_id] = client_expected
            artifact_changed = True
        if server.exists():
            map_servers[map_id] = server.read_text(encoding="utf-8")
            ET.parse(server)
        else:
            map_servers[map_id] = server_expected
            artifact_changed = True
        if artifact_changed:
            changed.append(f"map {map_id}")

    for npc_id in sorted(NEW_NPCS):
        client = ROOT / f"clien/Data/Npc/{npc_id}.img"
        server = ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
        client_expected, server_expected = build_new_image("Npc", npc_id)
        artifact_changed = False
        if client.exists():
            load_image(client.read_bytes(), client.name)
        else:
            pending.append((client, client_expected))
            artifact_changed = True
        if server.exists():
            ET.parse(server)
        else:
            pending.append((server, server_expected))
            artifact_changed = True
        if artifact_changed:
            changed.append(f"npc {npc_id}")

    for mob_id in sorted(NEW_MOBS):
        client = ROOT / f"clien/Data/Mob/{mob_id}.img"
        server = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
        client_expected, server_expected = build_new_image("Mob", mob_id)
        artifact_changed = False
        if client.exists():
            load_image(client.read_bytes(), client.name)
        else:
            pending.append((client, client_expected))
            artifact_changed = True
        if server.exists():
            ET.parse(server)
        else:
            pending.append((server, server_expected))
            artifact_changed = True
        if artifact_changed:
            changed.append(f"mob {mob_id}")

    by_string_image: dict[str, list[tuple[int, str | None]]] = defaultdict(list)
    for img_name, item_id, category_name in STRING_INSERTIONS:
        by_string_image[img_name].append((item_id, category_name))
    for img_name, insertions in by_string_image.items():
        client = ROOT / f"clien/Data/String/{img_name}.img"
        client_before = client.read_bytes()
        client_after = client_before
        for item_id, category_name in insertions:
            client_after = insert_client_string(
                client_after, img_name, item_id, category_name
            )
        if client_after != client_before:
            pending.append((client, client_after))
            changed.append(f"client String/{img_name}")
        for tree in ("wz", "wz-zh-CN"):
            server = ROOT / f"gms-server/{tree}/String.wz/{img_name}.img.xml"
            server_before = server.read_text(encoding="utf-8")
            server_after = server_before
            for item_id, category_name in insertions:
                server_after = insert_server_string(
                    server_after, img_name, item_id, category_name
                )
            if server_after != server_before:
                pending.append((server, server_after))
                changed.append(f"{tree} String/{img_name}")

    cave_portal_sets = (
        (2, migration.LEGACY_CAVE_ROUTE_PORTALS),
        (3, migration.LEGACY_CAVE_COLLISION_PORTALS),
    )
    for portal_type, portal_maps in cave_portal_sets:
        for map_id, portals in portal_maps.items():
            for portal_name, (target_map, target_name) in portals.items():
                client = CLIENT_ROOT / f"{map_id}.img"
                server = SERVER_ROOT / f"{map_id}.img.xml"
                if map_id not in map_clients:
                    map_clients[map_id] = client.read_bytes()
                if map_id not in map_servers:
                    map_servers[map_id] = server.read_text(encoding="utf-8")
                client_before = map_clients[map_id]
                server_before = map_servers[map_id]
                client_after = patch_client(
                    client_before, map_id, portal_name, target_map, target_name, portal_type
                )
                server_after = patch_server(
                    server_before, map_id, portal_name, target_map, target_name, portal_type
                )
                if client_after != client_before or server_after != server_before:
                    changed.append(f"portal {map_id}")
                map_clients[map_id] = client_after
                map_servers[map_id] = server_after
                hashes.append(f"{map_id}:{sha256(client_after)}")
    for map_id, data in map_clients.items():
        path = CLIENT_ROOT / f"{map_id}.img"
        if not path.exists() or data != path.read_bytes():
            pending.append((path, data))
    for map_id, text in map_servers.items():
        path = SERVER_ROOT / f"{map_id}.img.xml"
        if not path.exists() or text != path.read_text(encoding="utf-8"):
            pending.append((path, text))
    if args.check and changed:
        raise SystemExit(f"Cave of Repose portals need repair: {changed}")
    if not args.check:
        for path, data in pending:
            backup(path)
            atomic_write(path, data)
    print(
        f"Cave of Repose portals ok: changed={changed or False} "
        f"hashes={' '.join(hashes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
