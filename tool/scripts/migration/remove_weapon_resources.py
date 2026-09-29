#!/usr/bin/env python3
"""Incrementally remove the weapon IDs listed in remove_weapon_ids.txt."""

from __future__ import annotations

import argparse
import io
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy.crypto import WzKey  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _find_record,
    _reference_edits,
    mutate_img,
    scan_img,
)
from wzpy.incremental_xml import (  # noqa: E402
    _find_node,
    _remove_span_with_indent,
    _replace_attr,
    mutate_xml,
    scan_xml,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_compressed_int, encode_string_block  # noqa: E402
from wzpy.wz_image import WzImage  # noqa: E402


ID_FILE = Path(__file__).with_name("remove_weapon_ids.txt")
CLIENT_WEAPON = ROOT / "clien" / "Data" / "Character" / "Weapon"
SERVER_WEAPON = ROOT / "gms-server" / "wz" / "Character.wz" / "Weapon"
CLIENT_EQP = ROOT / "clien" / "Data" / "String" / "Eqp.img"
SERVER_EQP = (
    ROOT / "gms-server" / "wz" / "String.wz" / "Eqp.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Eqp.img.xml",
)
CLIENT_ACT = ROOT / "clien" / "Data" / "Quest" / "Act.img"
SERVER_ACT = (
    ROOT / "gms-server" / "wz" / "Quest.wz" / "Act.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz" / "Act.img.xml",
)
CLIENT_SAY = ROOT / "clien" / "Data" / "Quest" / "Say.img"
SERVER_SAY = (
    ROOT / "gms-server" / "wz" / "Quest.wz" / "Say.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz" / "Say.img.xml",
)
CLIENT_NPT = ROOT / "clien" / "Data" / "Etc" / "NPT_exception.img"
SERVER_NPT = (
    ROOT / "gms-server" / "wz" / "Etc.wz" / "NPT_exception.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Etc.wz" / "NPT_exception.img.xml",
)
CLIENT_COMMODITY = ROOT / "clien" / "Data" / "Etc" / "Commodity.img"
SERVER_COMMODITY = (
    ROOT / "gms-server" / "wz" / "Etc.wz" / "Commodity.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "Etc.wz" / "Commodity.img.xml",
)
CATALOG = ROOT / "gms-server" / "src" / "main" / "resources" / "equipment-catalog" / "catalog.json"
HANDBOOK = ROOT / "gms-server" / "handbook" / "Equip" / "Weapon.txt"
DEPENDENT_WEAPONS = (
    (
        ROOT / "clien" / "Data" / "Character" / "Weapon" / "01702934.img",
        ROOT / "gms-server" / "wz" / "Character.wz" / "Weapon" / "01702934.img.xml",
    ),
    (
        ROOT / "clien" / "Data" / "Character" / "Weapon" / "01705014.img",
        ROOT / "gms-server" / "wz" / "Character.wz" / "Weapon" / "01705014.img.xml",
    ),
)


def load_ids() -> tuple[int, ...]:
    tokens = re.findall(r"(?<!\d)\d{7}(?!\d)", ID_FILE.read_text(encoding="utf-8"))
    if len(tokens) != 480 or len(set(tokens)) != 480:
        raise ValueError(f"expected 480 unique weapon IDs, got {len(tokens)} / {len(set(tokens))}")
    ids = tuple(sorted(map(int, tokens)))
    if any(str(item_id)[:3] not in {str(value) for value in range(130, 150)} | {"170"} for item_id in ids):
        raise ValueError("manifest contains a non-weapon ID")
    return ids


def verify_img(data: bytes, region: str) -> None:
    layout = scan_img(data, region=region)
    image = WzImage.from_bytes(data, key=WzKey.for_region(region))
    image.parse()
    if image.truncated or image.parse_warnings:
        detail = "; ".join(image.parse_warnings or ["truncated"])
        raise ValueError(f"patched IMG failed verification: {detail}")
    if layout.root.count != len(layout.root.records):
        raise ValueError("patched IMG root property count mismatch")


def batch_remove_img(data: bytes, requested_paths: Iterable[Sequence[str]]) -> tuple[bytes, int]:
    layout = scan_img(data)
    targets = []
    seen = set()
    for requested in requested_paths:
        path = tuple(requested)
        try:
            parent, record, ancestors = _find_record(layout.root, path)
        except KeyError:
            continue
        if record.start in seen:
            continue
        seen.add(record.start)
        targets.append((parent, record, ancestors))
    if not targets:
        return data, 0

    edits = [(record.start, record.end, b"") for _parent, record, _ancestors in targets]
    by_parent: dict[int, list] = defaultdict(list)
    parent_objects = {}
    parent_ancestors = {}
    for parent, record, ancestors in targets:
        key = id(parent)
        by_parent[key].append(record)
        parent_objects[key] = parent
        parent_ancestors[key] = ancestors

    ancestor_deltas: dict[int, int] = defaultdict(int)
    ancestor_objects = {}
    for key, records in by_parent.items():
        parent = parent_objects[key]
        count_bytes = encode_compressed_int(parent.count - len(records))
        count_delta = len(count_bytes) - (parent.count_end - parent.count_offset)
        edits.append((parent.count_offset, parent.count_end, count_bytes))
        delta = count_delta - sum(record.end - record.start for record in records)
        for ancestor in parent_ancestors[key]:
            ancestor_deltas[id(ancestor)] += delta
            ancestor_objects[id(ancestor)] = ancestor

    for key, delta in ancestor_deltas.items():
        ancestor = ancestor_objects[key]
        if ancestor.size_offset is None or ancestor.block_size is None:
            raise ValueError(f"container {ancestor.name!r} has no size field")
        edits.append((
            ancestor.size_offset,
            ancestor.size_offset + 4,
            struct.pack("<I", ancestor.block_size + delta),
        ))

    edits.extend(_reference_edits(layout, edits))
    patched = _apply_edits(data, edits)
    verify_img(patched, layout.region)
    return patched, len(targets)


def batch_rename_img(data: bytes, renames: dict[tuple[str, ...], str]) -> tuple[bytes, int]:
    if not renames:
        return data, 0
    layout = scan_img(data)
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region(layout.region))
    edits = []
    ancestor_deltas: dict[int, int] = defaultdict(int)
    ancestor_objects = {}
    changed = 0
    for path, new_name in renames.items():
        try:
            _parent, record, ancestors = _find_record(layout.root, path)
        except KeyError:
            continue
        if record.name == new_name:
            continue
        replacement = encode_string_block(reader, new_name) + data[record.tag_offset:record.end]
        edits.append((record.start, record.end, replacement))
        delta = len(replacement) - (record.end - record.start)
        for ancestor in ancestors:
            ancestor_deltas[id(ancestor)] += delta
            ancestor_objects[id(ancestor)] = ancestor
        changed += 1
    if not edits:
        return data, 0
    for key, delta in ancestor_deltas.items():
        ancestor = ancestor_objects[key]
        if ancestor.size_offset is None or ancestor.block_size is None:
            raise ValueError(f"container {ancestor.name!r} has no size field")
        edits.append((
            ancestor.size_offset,
            ancestor.size_offset + 4,
            struct.pack("<I", ancestor.block_size + delta),
        ))
    edits.extend(_reference_edits(layout, edits))
    patched = _apply_edits(data, edits)
    verify_img(patched, layout.region)
    return patched, changed


def batch_remove_xml(text: str, paths: Iterable[Sequence[str]]) -> tuple[str, int]:
    root = scan_xml(text)
    spans = []
    seen = set()
    for requested in paths:
        try:
            node = _find_node(root, tuple(requested))
        except KeyError:
            continue
        span = _remove_span_with_indent(text, node)
        if span in seen:
            continue
        seen.add(span)
        spans.append(span)
    if not spans:
        return text, 0
    result = text
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + result[end:]
    scan_xml(result)
    return result, len(spans)


def batch_rename_xml(text: str, renames: dict[tuple[str, ...], str]) -> tuple[str, int]:
    if not renames:
        return text, 0
    root = scan_xml(text)
    edits = []
    for path, new_name in renames.items():
        try:
            node = _find_node(root, path)
        except KeyError:
            continue
        if node.name == new_name:
            continue
        token = text[node.start:node.start_end]
        edits.append((node.start, node.start_end, _replace_attr(token, "name", new_name)))
    result = text
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    scan_xml(result)
    return result, len(edits)


def walk_elements(root: ET.Element):
    def visit(node: ET.Element, path: tuple[str, ...]):
        for child in list(node):
            name = child.attrib.get("name")
            child_path = (*path, name) if name is not None else path
            yield child, child_path, node, path
            yield from visit(child, child_path)
    yield from visit(root, ())


def value_parent_paths(xml_text: str, field_name: str, ids: set[int]) -> set[tuple[str, ...]]:
    root = ET.fromstring(xml_text)
    result = set()
    for node, _path, _parent, parent_path in walk_elements(root):
        if node.attrib.get("name") != field_name:
            continue
        value = node.attrib.get("value", "")
        if value.isdigit() and int(value) in ids:
            result.add(parent_path)
    return result


def value_record_paths(xml_text: str, ids: set[int]) -> set[tuple[str, ...]]:
    root = ET.fromstring(xml_text)
    result = set()
    for node, path, _parent, _parent_path in walk_elements(root):
        value = node.attrib.get("value", "")
        if value.isdigit() and int(value) in ids:
            result.add(path)
    return result


def deleted_weapon_outlink_paths(xml_text: str, ids: set[int]) -> set[tuple[str, ...]]:
    root = ET.fromstring(xml_text)
    target = re.compile(r"^Character/Weapon/0(\d{7})\.img/")
    result = set()
    for node, path, _parent, _parent_path in walk_elements(root):
        if node.tag != "string" or node.attrib.get("name") != "_outlink":
            continue
        match = target.match(node.attrib.get("value", ""))
        if match and int(match.group(1)) in ids:
            result.add(path)
    return result


def quest_item_mutations(xml_text: str, ids: set[int]):
    root = ET.fromstring(xml_text)
    elements = {path: node for node, path, _parent, _parent_path in walk_elements(root)}
    remove_paths = value_parent_paths(xml_text, "id", ids)
    by_container: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for path in remove_paths:
        if path:
            by_container[path[:-1]].add(path[-1])

    renames = {}
    for container_path, removed_names in by_container.items():
        container = elements.get(container_path)
        if container is None:
            raise KeyError("/".join(container_path))
        children = [child for child in list(container) if child.tag == "imgdir"]
        names = [child.attrib.get("name", "") for child in children]
        if not all(name.isdigit() for name in names):
            raise ValueError(f"non-numeric quest item list at {'/'.join(container_path)}")
        kept = [name for name in names if name not in removed_names]
        for index, old_name in enumerate(kept):
            new_name = str(index)
            if old_name != new_name:
                renames[(*container_path, old_name)] = new_name
    return remove_paths, renames


def say_edits(xml_text: str, ids: set[int]) -> dict[tuple[str, ...], str]:
    root = ET.fromstring(xml_text)
    token = re.compile(r"#t(" + "|".join(map(str, sorted(ids))) + r")#")
    edits = {}
    for node, path, _parent, _parent_path in walk_elements(root):
        if node.tag != "string":
            continue
        value = node.attrib.get("value", "")
        replacement = token.sub("선물", value)
        if replacement != value:
            edits[path] = replacement
    return edits


def apply_img(path: Path, data: bytes, apply: bool) -> int:
    old = path.read_bytes()
    if old == data:
        return 0
    if apply:
        path.write_bytes(data)
    return len(old) - len(data)


def apply_text(path: Path, text: str, apply: bool) -> int:
    old = path.read_text(encoding="utf-8")
    if old == text:
        return 0
    if apply:
        path.write_text(text, encoding="utf-8")
    return len(old.encode("utf-8")) - len(text.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ids = load_ids()
    id_set = set(ids)
    mode = "apply" if args.apply else "check"
    print(f"mode={mode} ids={len(ids)}")

    client_files = {item_id: CLIENT_WEAPON / f"0{item_id}.img" for item_id in ids}
    server_files = {item_id: SERVER_WEAPON / f"0{item_id}.img.xml" for item_id in ids}
    mismatched = [item_id for item_id in ids if client_files[item_id].exists() != server_files[item_id].exists()]
    if mismatched:
        raise ValueError(f"client/server weapon file mismatch: {mismatched}")
    existing = [item_id for item_id in ids if client_files[item_id].exists()]
    removed_file_bytes = sum(
        client_files[item_id].stat().st_size + server_files[item_id].stat().st_size
        for item_id in existing
    )
    if args.apply:
        for item_id in existing:
            client_files[item_id].unlink()
            server_files[item_id].unlink()
    print(f"weapon_files={len(existing)} bytes={removed_file_bytes}")

    for client_path, server_path in DEPENDENT_WEAPONS:
        server_text = server_path.read_text(encoding="utf-8")
        outlink_paths = deleted_weapon_outlink_paths(server_text, id_set)
        client_data, client_count = batch_remove_img(client_path.read_bytes(), outlink_paths)
        client_saved = apply_img(client_path, client_data, args.apply)
        server_text, server_count = batch_remove_xml(server_text, outlink_paths)
        server_saved = apply_text(server_path, server_text, args.apply)
        print(
            f"dependent_weapon={client_path.name} client_outlinks={client_count} "
            f"client_bytes={client_saved} server_outlinks={server_count} "
            f"server_bytes={server_saved}"
        )

    eqp_paths = [("Eqp", "Weapon", str(item_id)) for item_id in ids]
    eqp_data, eqp_count = batch_remove_img(CLIENT_EQP.read_bytes(), eqp_paths)
    eqp_saved = apply_img(CLIENT_EQP, eqp_data, args.apply)
    print(f"client_eqp_records={eqp_count} bytes={eqp_saved}")
    for path in SERVER_EQP:
        text, count = batch_remove_xml(path.read_text(encoding="utf-8"), eqp_paths)
        saved = apply_text(path, text, args.apply)
        print(f"server_eqp={path.relative_to(ROOT)} records={count} bytes={saved}")

    canonical_npt = SERVER_NPT[0].read_text(encoding="utf-8")
    npt_paths = value_record_paths(canonical_npt, id_set)
    npt_data, npt_count = batch_remove_img(CLIENT_NPT.read_bytes(), npt_paths)
    npt_saved = apply_img(CLIENT_NPT, npt_data, args.apply)
    print(f"client_npt_records={npt_count} bytes={npt_saved}")
    for path in SERVER_NPT:
        text, count = batch_remove_xml(path.read_text(encoding="utf-8"), npt_paths)
        saved = apply_text(path, text, args.apply)
        print(f"server_npt={path.relative_to(ROOT)} records={count} bytes={saved}")

    canonical_commodity = SERVER_COMMODITY[0].read_text(encoding="utf-8")
    commodity_paths = value_parent_paths(canonical_commodity, "ItemId", id_set)
    commodity_data, commodity_count = batch_remove_img(CLIENT_COMMODITY.read_bytes(), commodity_paths)
    commodity_saved = apply_img(CLIENT_COMMODITY, commodity_data, args.apply)
    print(f"client_commodity_records={commodity_count} bytes={commodity_saved}")
    for path in SERVER_COMMODITY:
        text, count = batch_remove_xml(path.read_text(encoding="utf-8"), commodity_paths)
        saved = apply_text(path, text, args.apply)
        print(f"server_commodity={path.relative_to(ROOT)} records={count} bytes={saved}")

    canonical_act = SERVER_ACT[0].read_text(encoding="utf-8")
    act_remove, act_renames = quest_item_mutations(canonical_act, id_set)
    act_data, act_remove_count = batch_remove_img(CLIENT_ACT.read_bytes(), act_remove)
    act_data, act_rename_count = batch_rename_img(act_data, act_renames)
    act_saved = apply_img(CLIENT_ACT, act_data, args.apply)
    print(f"client_act_removed={act_remove_count} renamed={act_rename_count} bytes={act_saved}")
    for path in SERVER_ACT:
        text, remove_count = batch_remove_xml(path.read_text(encoding="utf-8"), act_remove)
        text, rename_count = batch_rename_xml(text, act_renames)
        saved = apply_text(path, text, args.apply)
        print(f"server_act={path.relative_to(ROOT)} removed={remove_count} renamed={rename_count} bytes={saved}")

    canonical_say = SERVER_SAY[0].read_text(encoding="utf-8")
    replacements = say_edits(canonical_say, id_set)
    say_data = CLIENT_SAY.read_bytes()
    client_say_count = 0
    for path, value in replacements.items():
        try:
            result = mutate_img(say_data, "edit", path, values={"value": value})
        except KeyError:
            continue
        say_data = result.data
        client_say_count += 1
    say_saved = apply_img(CLIENT_SAY, say_data, args.apply)
    print(f"client_say_strings={client_say_count} bytes={say_saved}")
    for path in SERVER_SAY:
        text = path.read_text(encoding="utf-8")
        count = 0
        for record_path, value in replacements.items():
            try:
                text = mutate_xml(text, "edit", record_path, values={"value": value})
            except KeyError:
                continue
            count += 1
        saved = apply_text(path, text, args.apply)
        print(f"server_say={path.relative_to(ROOT)} strings={count} bytes={saved}")

    catalog_text = CATALOG.read_text(encoding="utf-8")
    catalog = json.loads(catalog_text)
    before_items = catalog["items"]
    catalog["items"] = [item for item in before_items if int(item["id"]) not in id_set]
    removed_catalog = len(before_items) - len(catalog["items"])
    remaining_weapons = [item for item in catalog["items"] if item.get("category") == "Weapon"]
    weapon_atlas = catalog["atlases"]["Weapon"]
    weapon_atlas["count"] = len(remaining_weapons)
    weapon_atlas["icons"] = sum(bool(item.get("icon")) for item in remaining_weapons)
    new_catalog_text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    catalog_saved = apply_text(CATALOG, new_catalog_text, args.apply)
    print(f"catalog_items={removed_catalog} bytes={catalog_saved}")

    handbook_text = HANDBOOK.read_text(encoding="utf-8")
    handbook_lines = handbook_text.splitlines(keepends=True)
    kept_lines = [
        line for line in handbook_lines
        if not (line[:7].isdigit() and int(line[:7]) in id_set)
    ]
    new_handbook = "".join(kept_lines)
    handbook_count = len(handbook_lines) - len(kept_lines)
    handbook_saved = apply_text(HANDBOOK, new_handbook, args.apply)
    print(f"handbook_lines={handbook_count} bytes={handbook_saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
