#!/usr/bin/env python3
"""Project Chu Chu Village's modern skyWhale lift onto legacy portals."""

from __future__ import annotations

import argparse
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import migrate_arcane_river_fields as migration  # noqa: E402
from repair_arcane_river_cave_portals import (  # noqa: E402
    find_node_span,
    load_image,
    locate_extended_children,
    locate_root,
    patch_client,
    patch_server,
    record_bytes,
    sha256,
)
from wzpy.writer import encode_compressed_int  # noqa: E402


MAP_ID = 450002000
CLIENT = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
OBSOLETE_PORTALS = {
    "skyWhaleLift": (3, 2475, -421, 450002000, "skyWhaleTop"),
    "skyWhaleTop": (0, 2475, -925, 999999999, ""),
}


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


def remove_obsolete_client_portal(data: bytes, portal_name: str) -> bytes:
    image = load_image(data, f"{MAP_ID}.img")
    portal = image.root.get("portal")
    entry = next(
        (node for node in portal.children() if migration.child_value(node, "pn") == portal_name),
        None,
    )
    if entry is None:
        return data
    expected = OBSOLETE_PORTALS[portal_name]
    actual = tuple(
        migration.child_value(entry, name) for name in ("pt", "x", "y", "tm", "tn")
    )
    if actual != expected:
        return data

    roots = locate_root(data)
    portal_record = next(record for record in roots.records if record.name == "portal")
    entries = locate_extended_children(data, portal_record)
    record = next(node for node in entries.records if node.name == entry.name)
    removed_length = record.end - record.start
    updated = bytearray(data[:record.start] + data[record.end:])
    encoded_count = encode_compressed_int(entries.count - 1)
    if len(encoded_count) != entries.count_length:
        raise RuntimeError(f"{MAP_ID}: portal count encoding width changed")
    updated[entries.count_offset:entries.count_offset + entries.count_length] = encoded_count
    if portal_record.size_offset is None or portal_record.block_size is None:
        raise RuntimeError(f"{MAP_ID}: portal block size is missing")
    struct.pack_into(
        "<I", updated, portal_record.size_offset, portal_record.block_size - removed_length
    )
    result = bytes(updated)

    verified = load_image(result, f"{MAP_ID}.img")
    if any(
        migration.child_value(node, "pn") == portal_name
        for node in verified.root.get("portal").children()
    ):
        raise RuntimeError(f"{MAP_ID}: obsolete portal survived: {portal_name}")
    after_roots = locate_root(result)
    after_portal = next(record for record in after_roots.records if record.name == "portal")
    after_entries = locate_extended_children(result, after_portal)
    before_root_raw = record_bytes(data, roots.records)
    after_root_raw = record_bytes(result, after_roots.records)
    for name, raw in before_root_raw.items():
        if name != "portal" and after_root_raw[name] != raw:
            raise RuntimeError(f"{MAP_ID}: unapproved root record changed: {name}")
    after_entry_raw = record_bytes(result, after_entries.records)
    for name, raw in record_bytes(data, entries.records).items():
        if name != record.name and after_entry_raw[name] != raw:
            raise RuntimeError(f"{MAP_ID}: unapproved portal entry changed: {name}")
    return result


def remove_obsolete_server_portal(text: str, portal_name: str) -> str:
    root = ET.fromstring(text)
    portal = root.find('./imgdir[@name="portal"]')
    entry = next(
        (
            node for node in portal.findall("./imgdir")
            if node.find('./string[@name="pn"]') is not None
            and node.find('./string[@name="pn"]').get("value") == portal_name
        ),
        None,
    )
    if entry is None:
        return text
    values = {node.get("name"): node.get("value") for node in entry}
    expected = OBSOLETE_PORTALS[portal_name]
    actual = tuple(values[name] for name in ("pt", "x", "y", "tm", "tn"))
    if actual != tuple(str(value) for value in expected):
        return text

    portal_start, portal_end = find_node_span(text, "imgdir", "portal", 0, len(text))
    start, end = find_node_span(text, "imgdir", entry.get("name"), portal_start, portal_end)
    line_start = text.rfind("\n", 0, start) + 1
    if not text[line_start:start].strip():
        start = line_start
    if end < len(text) and text[end:end + 1] == "\n":
        end += 1
    result = text[:start] + text[end:]
    ET.fromstring(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    client_before = CLIENT.read_bytes()
    server_before = SERVER.read_text(encoding="utf-8")
    client_after = client_before
    server_after = server_before
    for portal_name in OBSOLETE_PORTALS:
        client_after = remove_obsolete_client_portal(client_after, portal_name)
        server_after = remove_obsolete_server_portal(server_after, portal_name)
    for portal_name, values in migration.LEGACY_CHUCHU_SKY_WHALE_PORTALS[MAP_ID].items():
        _, portal_type, _, _, target_map, target_name = values
        client_after = patch_client(
            client_after, MAP_ID, portal_name, target_map, target_name, portal_type
        )
        server_after = patch_server(
            server_after, MAP_ID, portal_name, target_map, target_name, portal_type
        )

    changed = client_after != client_before or server_after != server_before
    if args.check and changed:
        raise SystemExit("450002000 skyWhale lift needs repair")
    if not args.check:
        if client_after != client_before:
            atomic_write(CLIENT, client_after)
        if server_after != server_before:
            atomic_write(SERVER, server_after)
    print(f"Chu Chu skyWhale lift ok: changed={changed} sha256={sha256(client_after)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
