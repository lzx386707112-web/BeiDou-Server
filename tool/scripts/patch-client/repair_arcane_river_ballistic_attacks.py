#!/usr/bin/env python3
"""Restore legacy projectile metadata on Arcane River ballistic mob attacks."""

from __future__ import annotations

import argparse
import io
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzIntProperty, WzKey, WzSubProperty  # noqa: E402
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


CLIENT_ROOT = ROOT / "clien/Data/Mob"
SERVER_ROOT = ROOT / "gms-server/wz/Mob.wz"
BACKUP_ROOT = Path("/private/tmp/beidou-arcane-river-ballistic-attack-backup")
KEY = WzKey.for_region("GMS")


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


def locate_action_list(
    data: bytes, action_name: str
) -> tuple[PropertyList, Record, PropertyList]:
    reader = WzBinaryReader(io.BytesIO(data), KEY)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported IMG header")
    reader.skip(2)
    roots = read_property_list(reader, len(data))
    action = next((record for record in roots.records if record.name == action_name), None)
    if action is None or action.tag != 9 or action.block_start is None or action.block_size is None:
        raise RuntimeError(f"missing extended action {action_name}")
    reader.seek(action.block_start)
    if reader.read_string_block(0) != "Property":
        raise RuntimeError(f"{action_name} body is not a Property block")
    reader.skip(2)
    children = read_property_list(reader, action.block_start + action.block_size)
    return roots, action, children


def locate_info_list(data: bytes, action_name: str) -> tuple[Record, Record, PropertyList]:
    _, action, action_children = locate_action_list(data, action_name)
    info = next((record for record in action_children.records if record.name == "info"), None)
    if info is None or info.tag != 9 or info.block_start is None or info.block_size is None:
        raise RuntimeError(f"{action_name}/info is not an extended Property block")
    reader = WzBinaryReader(io.BytesIO(data), KEY)
    reader.seek(info.block_start)
    if reader.read_string_block(0) != "Property":
        raise RuntimeError(f"{action_name}/info body is not a Property block")
    reader.skip(2)
    children = read_property_list(reader, info.block_start + info.block_size)
    return action, info, children


def target_order(names: tuple[str, ...]) -> tuple[str, ...]:
    base = tuple(name for name in names if name not in {"type", "bulletSpeed"})
    if "ball" not in base or "attackAfter" not in base:
        raise RuntimeError(f"not a legacy ballistic info block: {names}")
    ordered: list[str] = []
    for name in base:
        if name == "attackAfter":
            ordered.extend(("type", "attackAfter", "bulletSpeed"))
        else:
            ordered.append(name)
    return tuple(ordered)


def encode_int_record(image: WzImage, name: str, value: int, parent) -> bytes:
    encoded = _encode_property_list(
        (WzIntProperty(name, value, parent),), image.wz_file.reader
    )
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError(f"unexpected encoded {name} record prefix")
    return encoded[len(prefix):]


def record_bytes(data: bytes, records: tuple[Record, ...]) -> dict[str, bytes]:
    return {record.name: data[record.start:record.end] for record in records}


def patch_client(data: bytes, mob_id: int, attack_number: int, speed: int) -> bytes:
    action_name = f"attack{attack_number}"
    image = load_image(data, f"{mob_id}.img")
    before_roots, _, before_action_children = locate_action_list(data, action_name)
    action, info, children = locate_info_list(data, action_name)
    names = tuple(record.name for record in children.records)
    expected_order = target_order(names)
    if names.count("type") > 1 or names.count("bulletSpeed") > 1:
        raise RuntimeError(f"{mob_id}: duplicate ballistic metadata {names}")
    expected_values = {"type": 2, "bulletSpeed": speed}
    for name, value in expected_values.items():
        current = image.root.get(f"{action_name}/info/{name}")
        if current is not None and (
            not isinstance(current, WzIntProperty) or int(current.value) != value
        ):
            raise RuntimeError(f"{mob_id}: conflicting {action_name}/info/{name}")
    if names == expected_order:
        return data

    parent = image.root.get(f"{action_name}/info")
    raw = record_bytes(data, children.records)
    for name, value in expected_values.items():
        if name not in raw:
            raw[name] = encode_int_record(image, name, value, parent)
    rebuilt = b"".join(raw[name] for name in expected_order)
    records_start, records_end = children.records[0].start, children.records[-1].end
    updated = bytearray(data[:records_start] + rebuilt + data[records_end:])
    delta = len(updated) - len(data)
    new_count = encode_compressed_int(len(expected_order))
    if len(new_count) != children.count_length:
        raise RuntimeError(f"{mob_id}: info child-count encoding width changed")
    updated[children.count_offset:children.count_offset + children.count_length] = new_count
    if info.size_offset is None or info.block_size is None:
        raise AssertionError("info block size field missing")
    if action.size_offset is None or action.block_size is None:
        raise AssertionError("action block size field missing")
    struct.pack_into("<I", updated, info.size_offset, info.block_size + delta)
    struct.pack_into("<I", updated, action.size_offset, action.block_size + delta)
    result = bytes(updated)

    after_image = load_image(result, f"{mob_id}.img")
    after_roots, _, after_action_children = locate_action_list(result, action_name)
    after_info = after_image.root.get(f"{action_name}/info")
    if not isinstance(after_info, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing repaired {action_name}/info")
    if tuple(child.name for child in after_info.children()) != expected_order:
        raise RuntimeError(f"{mob_id}: ballistic metadata order remains invalid")
    for name, value in expected_values.items():
        node = after_info.child(name)
        if not isinstance(node, WzIntProperty) or int(node.value) != value:
            raise RuntimeError(f"{mob_id}: {action_name}/info/{name} was not restored")

    before_root_raw = record_bytes(data, before_roots.records)
    after_root_raw = record_bytes(result, after_roots.records)
    for name in before_root_raw:
        if name != action_name and before_root_raw[name] != after_root_raw[name]:
            raise RuntimeError(f"{mob_id}: unapproved root record changed: {name}")
    before_action_raw = record_bytes(data, before_action_children.records)
    after_action_raw = record_bytes(result, after_action_children.records)
    for name in before_action_raw:
        if name != "info" and before_action_raw[name] != after_action_raw[name]:
            raise RuntimeError(f"{mob_id}: unapproved {action_name} record changed: {name}")
    return result


def patch_server(text: str, mob_id: int, attack_number: int, speed: int) -> str:
    action_name = f"attack{attack_number}"
    root = ET.fromstring(text)
    info = root.find(f'./imgdir[@name="{action_name}"]/imgdir[@name="info"]')
    if info is None:
        raise RuntimeError(f"{mob_id}: server XML is missing {action_name}/info")
    names = tuple(child.get("name") for child in info)
    expected_order = target_order(names)
    for name, value in {"type": 2, "bulletSpeed": speed}.items():
        node = info.find(f'./int[@name="{name}"]')
        if node is not None and node.get("value") != str(value):
            raise RuntimeError(f"{mob_id}: conflicting server {action_name}/info/{name}")
    if names == expected_order:
        return text

    action_start, action_end = find_node_span(text, "imgdir", action_name, 0, len(text))
    info_start, info_end = find_node_span(text, "imgdir", "info", action_start, action_end)
    info_text = text[info_start:info_end]
    if '<int name="type" value="2"/>' not in info_text:
        _, hit_end = find_node_span(info_text, "imgdir", "hit", 0, len(info_text))
        info_text = info_text[:hit_end] + '\n      <int name="type" value="2"/>' + info_text[hit_end:]
    if f'<int name="bulletSpeed" value="{speed}"/>' not in info_text:
        attack_after = info.find('./int[@name="attackAfter"]')
        if attack_after is None:
            raise RuntimeError(f"{mob_id}: server ballistic attack has no attackAfter")
        marker = f'<int name="attackAfter" value="{attack_after.get("value")}"/>'
        info_text = info_text.replace(
            marker, marker + f'\n      <int name="bulletSpeed" value="{speed}"/>', 1
        )
    result = text[:info_start] + info_text + text[info_end:]
    verified = ET.fromstring(result)
    verified_info = verified.find(
        f'./imgdir[@name="{action_name}"]/imgdir[@name="info"]'
    )
    verified_names = (
        tuple(child.get("name") for child in verified_info)
        if verified_info is not None else ()
    )
    if verified_names != expected_order:
        raise RuntimeError(f"{mob_id}: server ballistic metadata order remains invalid")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()
    changed: list[int] = []
    hashes: list[str] = []
    pending: list[tuple[Path, bytes | str]] = []
    for mob_id, (attack_number, speed) in migration.LEGACY_BALLISTIC_ATTACKS.items():
        client = CLIENT_ROOT / f"{mob_id}.img"
        server = SERVER_ROOT / f"{mob_id}.img.xml"
        client_before = client.read_bytes()
        server_before = server.read_text(encoding="utf-8")
        client_after = patch_client(client_before, mob_id, attack_number, speed)
        server_after = patch_server(server_before, mob_id, attack_number, speed)
        if client_after != client_before or server_after != server_before:
            changed.append(mob_id)
            pending.extend(((client, client_after), (server, server_after)))
        hashes.append(f"{mob_id}:{sha256(client_after)}")
    if args.check and changed:
        raise SystemExit(f"ballistic attack contracts need repair: {changed}")
    if not args.check:
        for path, data in pending:
            backup(path)
            atomic_write(path, data)
    print(
        f"Arcane River ballistic attack contracts ok: mobs={len(hashes)} "
        f"changed={changed or False} hashes={' '.join(hashes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
