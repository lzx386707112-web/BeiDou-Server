#!/usr/bin/env python3
"""Project leftover modern map objects and fill numeric obj/back gaps.

Modern nodes—especially connect/rope with TMS l1 style folders—were stripped
or left in place. The old client walks 0..max by name, so those holes crash
or drop geometry. This repairs Arcane River, later Grandis, and Monster Park
fields without full-serializing existing IMGs.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import (  # noqa: E402
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
)

MODERN_OBJECT_FIELDS = ("spineAni", "questex", "tags", "timeScale")
OBJ_FIELDS = ("oS", "l0", "l1", "l2", "x", "y", "z", "f", "zM")
BACK_FIELDS = (
    "bS",
    "front",
    "ani",
    "no",
    "f",
    "x",
    "y",
    "rx",
    "ry",
    "type",
    "cx",
    "cy",
    "a",
)
CLIENT_GLOBS = (
    "clien/Data/Map/Map/Map2/27*.img",
    "clien/Data/Map/Map/Map4/450*.img",
    "clien/Data/Map/Map/Map4/410*.img",
    "clien/Data/Map/Map/Map9/951*.img",
    "clien/Data/Map/Map/Map9/952*.img",
    "clien/Data/Map/Map/Map9/9530*.img",
    "clien/Data/Map/Map/Map9/9540*.img",
    "clien/Data/Map/Map/Map9/9541*.img",
)


def map_folder(map_id: int) -> str:
    return f"Map{str(map_id)[0]}"


def client_map_path(map_id: int) -> Path:
    return ROOT / f"clien/Data/Map/Map/{map_folder(map_id)}/{map_id}.img"


def server_map_path(map_id: int) -> Path:
    return ROOT / f"gms-server/wz/Map.wz/Map/{map_folder(map_id)}/{map_id}.img.xml"


def iter_target_map_ids() -> tuple[int, ...]:
    found: list[int] = []
    for pattern in CLIENT_GLOBS:
        found.extend(int(path.stem) for path in sorted((ROOT / pattern).parent.glob(Path(pattern).name)))
    return tuple(dict.fromkeys(found))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_client(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{name}: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def numeric_gaps(parent: WzSubProperty | None) -> list[int]:
    if not isinstance(parent, WzSubProperty):
        return []
    names = [child.name for child in parent.children() if child.name.isdigit()]
    if not names:
        return []
    numbers = {int(name) for name in names}
    return [index for index in range(max(numbers) + 1) if index not in numbers]


def leftover_gaps_from_bytes(data: bytes, map_id: int) -> dict[str, list[int]]:
    image = load_client(data, f"{map_id}.img")
    leftover: dict[str, list[int]] = {}
    back = numeric_gaps(image.root.child("back"))
    if back:
        leftover["back"] = back
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        holes = numeric_gaps(layer.child("obj"))
        if holes:
            leftover[f"{layer.name}/obj"] = holes
    return leftover


def leftover_gaps(map_id: int) -> dict[str, list[int]]:
    return leftover_gaps_from_bytes(client_map_path(map_id).read_bytes(), map_id)


def legacy_piece(value: object) -> str:
    text = str(value or "1")
    if text.isdigit() and int(text) <= 4:
        return text
    return "1"


def project_entry(source: WzSubProperty, name: str, fields: tuple[str, ...]) -> WzSubProperty:
    projected = WzSubProperty(name)
    copied = 0
    for field in fields:
        child = source.child(field)
        if isinstance(child, WzStringProperty):
            projected.add(WzStringProperty(field, str(child.value), projected))
            copied += 1
        elif isinstance(child, WzIntProperty):
            projected.add(WzIntProperty(field, int(child.value), projected))
            copied += 1
        elif isinstance(child, WzFloatProperty):
            projected.add(WzFloatProperty(field, float(child.value), projected))
            copied += 1
    if copied == 0:
        raise RuntimeError(f"template {source.name} has no legacy fields {fields}")
    return projected


def template_for(parent: WzSubProperty, missing: int, next_existing: int) -> WzSubProperty:
    previous = parent.child(str(missing - 1))
    if isinstance(previous, WzSubProperty):
        return previous
    nxt = parent.child(str(next_existing))
    if isinstance(nxt, WzSubProperty):
        return nxt
    for child in parent.children():
        if isinstance(child, WzSubProperty) and child.name.isdigit():
            return child
    raise RuntimeError(f"no template sibling for missing {missing}")


def gap_batches(parent: WzSubProperty) -> list[tuple[list[int], int]]:
    missing = numeric_gaps(parent)
    if not missing:
        return []
    existing = {int(child.name) for child in parent.children() if child.name.isdigit()}
    batches: list[tuple[list[int], int]] = []
    remaining = list(missing)
    while remaining:
        first = remaining[0]
        next_existing = min(value for value in existing if value > first)
        run = [value for value in remaining if value < next_existing]
        batches.append((run, next_existing))
        remaining = remaining[len(run) :]
    return batches


def iter_gap_parents(image: WzImage) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    found: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    if numeric_gaps(image.root.child("back")):
        found.append((("back",), BACK_FIELDS))
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        if numeric_gaps(layer.child("obj")):
            found.append(((layer.name, "obj"), OBJ_FIELDS))
    return found


def collect_modern_object_ops(image: WzImage) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    remove_objects: list[tuple[str, ...]] = []
    remove_fields: list[tuple[str, ...]] = []
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            path = (layer.name, "obj", entry.name)
            if entry.child("spineAni") is not None:
                remove_objects.append(path)
                continue
            for field in MODERN_OBJECT_FIELDS:
                if entry.child(field) is not None:
                    remove_fields.append((*path, field))
    return remove_objects, remove_fields


def collect_connect_edits(image: WzImage) -> list[tuple[tuple[str, ...], str]]:
    edits: list[tuple[tuple[str, ...], str]] = []
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if str(arc.child_value(entry, "oS") or "") != "connect":
                continue
            path = (layer.name, "obj", entry.name)
            kind = str(arc.child_value(entry, "l0") or "")
            if kind not in {"rope", "ladder"}:
                edits.append(((*path, "l0"), "rope" if kind != "ladder" else "ladder"))
                kind = "rope"
            l1 = str(arc.child_value(entry, "l1") or "")
            if l1 not in {"0", "1", "2", "3", "4"}:
                edits.append(((*path, "l1"), "0"))
            l2 = legacy_piece(arc.child_value(entry, "l2"))
            if str(arc.child_value(entry, "l2") or "") != l2:
                edits.append(((*path, "l2"), l2))
    return edits


def apply_client_scalar_edits(data: bytes, edits: list[tuple[tuple[str, ...], str]]) -> bytes:
    for path, value in edits:
        data = arc.mutate_img(
            data, "edit", path, kind="String", values={"value": value}, region="GMS"
        ).data
    return data


def apply_client_removes(data: bytes, paths: list[tuple[str, ...]]) -> bytes:
    for path in reversed(paths):
        data = arc.mutate_img(data, "remove", path, region="GMS").data
    return data


def apply_xml_scalar_edits(text: str, edits: list[tuple[tuple[str, ...], str]]) -> str:
    for path, value in edits:
        text = arc.mutate_xml(text, "edit", path, kind="String", values={"value": value})
    return text


def apply_xml_removes(text: str, paths: list[tuple[str, ...]]) -> str:
    for path in reversed(paths):
        text = arc.mutate_xml(text, "remove", path)
    return text


def repair_client_gaps(data: bytes, map_id: int) -> tuple[bytes, int]:
    inserted = 0
    while True:
        image = load_client(data, f"{map_id}.img")
        parents = iter_gap_parents(image)
        if not parents:
            return data, inserted
        path, fields = parents[0]
        parent = image.root.get("/".join(path))
        batches = gap_batches(parent)
        if not batches:
            return data, inserted
        run, next_existing = batches[0]
        template = template_for(parent, run[0], next_existing)
        nodes = [project_entry(template, str(index), fields) for index in run]
        before = data
        data = arc.insert_property_records_before(data, path, nodes, str(next_existing))
        arc.verify_raw_record_insert_scope(
            before,
            data,
            {(*path, str(index)) for index in run},
        )
        inserted += len(run)


def repair_server_gaps(text: str) -> tuple[str, int]:
    from xml.etree import ElementTree as ET

    inserted = 0
    while True:
        root = ET.fromstring(text)
        parents = _xml_numeric_parents(root)
        if not parents:
            return text, inserted
        path, fields, names = parents[0]
        missing = [index for index in range(max(names) + 1) if index not in names]
        first = missing[0]
        next_existing = min(value for value in names if value > first)
        run = [value for value in missing if value < next_existing]
        template_name = str(first - 1) if (first - 1) in names else str(next_existing)
        template_xml = _xml_child(root, path, template_name)
        nodes = [_xml_to_projected(template_xml, str(index), fields) for index in run]
        text = arc.insert_xml_properties_before(text, path, nodes, str(next_existing))
        inserted += len(run)


def _xml_child(root, path: tuple[str, ...], name: str):
    current = root
    for part in path:
        current = next(child for child in current if child.get("name") == part)
    return next(child for child in current if child.get("name") == name)


def _xml_numeric_parents(root) -> list[tuple[tuple[str, ...], tuple[str, ...], set[int]]]:
    found = []
    back = next((child for child in root if child.get("name") == "back"), None)
    if back is not None:
        names = {int(child.get("name")) for child in back if (child.get("name") or "").isdigit()}
        if names and any(index not in names for index in range(max(names) + 1)):
            found.append((("back",), BACK_FIELDS, names))
    for layer in [child for child in root if (child.get("name") or "").isdigit()]:
        objects = next((child for child in layer if child.get("name") == "obj"), None)
        if objects is None:
            continue
        names = {int(child.get("name")) for child in objects if (child.get("name") or "").isdigit()}
        if names and any(index not in names for index in range(max(names) + 1)):
            found.append(((layer.get("name"), "obj"), OBJ_FIELDS, names))
    return found


def _xml_to_projected(node, name: str, fields: tuple[str, ...]) -> WzSubProperty:
    projected = WzSubProperty(name)
    by_name = {child.get("name"): child for child in node}
    copied = 0
    for field in fields:
        child = by_name.get(field)
        if child is None:
            continue
        if child.tag == "string":
            projected.add(WzStringProperty(field, str(child.get("value") or ""), projected))
            copied += 1
        elif child.tag in {"int", "short"}:
            projected.add(WzIntProperty(field, int(child.get("value") or 0), projected))
            copied += 1
        elif child.tag == "float":
            projected.add(WzFloatProperty(field, float(child.get("value") or 0), projected))
            copied += 1
    if copied == 0:
        raise RuntimeError(f"XML template {node.get('name')} has no legacy fields")
    return projected


def leftover_modern(data: bytes, map_id: int) -> dict[str, list[str]]:
    image = load_client(data, f"{map_id}.img")
    found: dict[str, list[str]] = {"modern": [], "connect": []}
    remove_objects, remove_fields = collect_modern_object_ops(image)
    found["modern"] = ["/".join(path) for path in (*remove_objects, *remove_fields)]
    found["connect"] = ["/".join(path) for path, _value in collect_connect_edits(image)]
    return {key: values for key, values in found.items() if values}


def repair_map(map_id: int) -> dict[str, object]:
    client = client_map_path(map_id)
    server = server_map_path(map_id)
    if not client.is_file() or not server.is_file():
        raise FileNotFoundError(map_id)
    client_before = client.read_bytes()
    server_before = server.read_text(encoding="utf-8")
    image = load_client(client_before, f"{map_id}.img")
    remove_objects, remove_fields = collect_modern_object_ops(image)
    connect_edits = collect_connect_edits(image)
    client_data = apply_client_removes(client_before, [*remove_fields, *remove_objects])
    client_data = apply_client_scalar_edits(client_data, connect_edits)
    client_data, client_inserted = repair_client_gaps(client_data, map_id)
    server_text = apply_xml_removes(server_before, [*remove_fields, *remove_objects])
    server_text = apply_xml_scalar_edits(server_text, connect_edits)
    server_text, server_inserted = repair_server_gaps(server_text)
    leftover = leftover_gaps_from_bytes(client_data, map_id)
    if leftover:
        raise RuntimeError(f"{map_id} still has gaps {leftover}")
    leftover_nodes = leftover_modern(client_data, map_id)
    if leftover_nodes:
        raise RuntimeError(f"{map_id} still has modern nodes {leftover_nodes}")
    repaired = load_client(client_data, f"{map_id}.img")
    if repaired.truncated or repaired.parse_warnings:
        raise RuntimeError(
            f"{map_id}: truncated={repaired.truncated} warnings={repaired.parse_warnings}"
        )
    if client_data != client_before:
        arc.atomic_write_bytes(client, client_data)
    if server_text != server_before:
        arc.atomic_write_text(server, server_text)
    return {
        "map_id": map_id,
        "client_inserted": client_inserted,
        "server_inserted": server_inserted,
        "connect_edits": len(connect_edits),
        "modern_removed": len(remove_objects) + len(remove_fields),
        "client_changed": client_data != client_before,
        "server_changed": server_text != server_before,
        "client_sha256": sha256_bytes(client_data),
        "server_sha256": sha256_bytes(server_text.encode("utf-8")),
    }


def maps_needing_repair() -> list[int]:
    needed = []
    for map_id in iter_target_map_ids():
        data = client_map_path(map_id).read_bytes()
        image = load_client(data, f"{map_id}.img")
        remove_objects, remove_fields = collect_modern_object_ops(image)
        if (
            remove_objects
            or remove_fields
            or collect_connect_edits(image)
            or leftover_gaps_from_bytes(data, map_id)
        ):
            needed.append(map_id)
    return needed


def repair_all(map_ids: tuple[int, ...] | None = None) -> list[dict[str, object]]:
    targets = list(map_ids) if map_ids is not None else maps_needing_repair()
    return [repair_map(map_id) for map_id in targets]


def main() -> int:
    results = repair_all()
    changed = [row for row in results if row["client_changed"] or row["server_changed"]]
    print(
        f"modern obj/connect/gap repair: inspected_need={len(results)} changed={len(changed)}"
    )
    for row in changed:
        print(
            f"  {row['map_id']} modern={row['modern_removed']} connect={row['connect_edits']} "
            f"insert client={row['client_inserted']} server={row['server_inserted']} "
            f"sha={row['client_sha256'][:16]}"
        )
    leftover = {}
    for map_id in iter_target_map_ids():
        holes = leftover_gaps(map_id)
        modern = leftover_modern(client_map_path(map_id).read_bytes(), map_id)
        if holes or modern:
            leftover[map_id] = {"gaps": holes, "modern": modern}
    if leftover:
        raise RuntimeError(f"repair leftover {leftover}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
