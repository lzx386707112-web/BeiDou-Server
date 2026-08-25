#!/usr/bin/env python3
"""Incrementally rebuild the compatible object projection for Morass town."""

from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import quoteattr


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool/wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _count_edit,
    _find_list,
    _record_bytes,
    _reference_edits,
    _size_edits,
    scan_img,
)
from wzpy.incremental_xml import scan_xml  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402


MAP_ID = 450006130
SOURCE = Path(
    "/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Map/Map/Map4/450006130.img"
)
CLIENT = ROOT / "clien/Data/Map/Map/Map4/450006130.img"
SERVER = ROOT / "gms-server/wz/Map.wz/Map/Map4/450006130.img.xml"
MORASS_ASSET = ROOT / "clien/Data/Map/Obj/morass.img"

SOURCE_SHA256 = "e8c1b0f3bb17238e55083b1e2f79b3449bf799acceb550f2f852f9629facb453"
BASELINE_CLIENT_SHA256 = "18e6c6394cc53a833b0bb90af8ccd0f91577ca7d7411bea0425942023ee79827"
BASELINE_SERVER_SHA256 = "6a068f9005b3833c3986b57f7994c0ec15faf2484f94202a6dc63e515997ec24"
FINAL_CLIENT_SHA256 = "4681c0b7ab7e539e903cda1e666f3b5f685d9832d0a58d58dc7ce3a455c3d8e3"
FINAL_SERVER_SHA256 = "b09bd11b3e64d64d87324b35bbc3ec32ff6297d16a502fe44822e3ad884bc9c8"
MORASS_ASSET_SHA256 = "5af8decae63f54e7ecba5fefce8335c2096f19b43080ee8b14adee449dc19f3e"

# Round seven isolated this group from foothold_Bridge, whose individual
# instances were later proven to trigger legacy-client high load.  Plain
# acc/bridge objects also remain excluded because their combined test failed.
SAFE_GROUPS = {"foothold_Bridge2", "foothold_Castle", "stone"}
EXPECTED_GROUP_COUNTS = Counter(
    {"foothold_Bridge2": 11, "foothold_Castle": 4, "stone": 1}
)
REMOVE_ENTRY_IF_PRESENT = {"questex", "tags", "timeScale", "spineAni"}
REMOVE_FIELDS = {
    "SN0",
    "SN_count",
    "dynamic",
    "move",
    "name",
    "piece",
    "questex",
    "tags",
    "timeScale",
    "cantThrough",
    "fadeName",
    "fadeType",
    "groupName",
    "quest",
    "sideType",
}

GMS_KEY = WzKey.for_region("GMS")
BMS_KEY = WzKey.for_region("BMS")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image(data: bytes, key: WzKey, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=key, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def clone_scalar(source, parent):
    name = source.name
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(name, parent)
        for child in source.children():
            if child.name not in REMOVE_FIELDS:
                output.add(clone_scalar(child, output))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(name, int(source.value), parent)
    if isinstance(source, WzLongProperty):
        return WzLongProperty(name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(name, float(source.value), parent)
    if isinstance(source, WzDoubleProperty):
        return WzDoubleProperty(name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(name, str(source.value), parent)
    if isinstance(source, WzNullProperty):
        return WzNullProperty(name, parent)
    raise TypeError(f"unsupported map object property: {type(source).__name__}")


def source_objects(source: WzImage) -> list[tuple[str, WzSubProperty]]:
    selected: list[tuple[str, WzSubProperty]] = []
    for layer in [node for node in source.root.children() if node.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if child_value(entry, "oS") != "morass":
                continue
            if child_value(entry, "l1") not in SAFE_GROUPS:
                continue
            fields = {child.name for child in entry.children()}
            if fields & REMOVE_ENTRY_IF_PRESENT:
                continue
            selected.append((layer.name, clone_scalar(entry, None)))
    counts = Counter(str(child_value(entry, "l1")) for _, entry in selected)
    if counts != EXPECTED_GROUP_COUNTS:
        raise RuntimeError(f"unexpected TMS compatible-object set: {counts}")
    return selected


def append_property(data: bytes, parent_path: tuple[str, ...], prop) -> bytes:
    layout = scan_img(data, region="GMS")
    prop_list, ancestors = _find_list(layout.root, parent_path)
    if any(record.name == prop.name for record in prop_list.records):
        raise FileExistsError("/".join((*parent_path, prop.name)))
    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    record = _record_bytes(prop, reader)
    count_edit = _count_edit(prop_list, prop_list.count + 1)
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(record) + count_delta
    edits = [
        (prop_list.end, prop_list.end, record),
        count_edit,
        *_size_edits(ancestors, delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    result = _apply_edits(data, edits)
    scan_img(result, region="GMS")
    load_image(result, GMS_KEY, CLIENT.name)
    return result


def xml_property(prop, indent: str) -> str:
    name = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzSubProperty):
        children = "\n".join(xml_property(child, indent + "  ") for child in prop.children())
        return f"{indent}<imgdir {name}>\n{children}\n{indent}</imgdir>"
    if isinstance(prop, WzVectorProperty):
        return f'{indent}<vector {name} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzNullProperty):
        return f"{indent}<null {name}/>"
    tags = {
        WzShortProperty: "short",
        WzIntProperty: "int",
        WzLongProperty: "long",
        WzFloatProperty: "float",
        WzDoubleProperty: "double",
        WzStringProperty: "string",
        WzUolProperty: "uol",
    }
    tag = next((value for kind, value in tags.items() if isinstance(prop, kind)), None)
    if tag is None:
        raise TypeError(f"unsupported map XML property: {type(prop).__name__}")
    return f"{indent}<{tag} {name} value={quoteattr(str(prop.value))}/>"


def find_xml_node(root, path: tuple[str, ...]):
    current = root
    for part in path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(path)}")
        current = matches[0]
    return current


def append_xml_property(text: str, parent_path: tuple[str, ...], prop) -> str:
    root = scan_xml(text)
    parent = find_xml_node(root, parent_path)
    if any(child.name == prop.name for child in parent.children):
        raise FileExistsError("/".join((*parent_path, prop.name)))
    line_start = text.rfind("\n", 0, parent.start) + 1
    parent_indent = text[line_start:parent.start]
    if parent_indent.strip():
        raise RuntimeError("cannot determine XML indentation")
    block = xml_property(prop, parent_indent + "  ") + "\n"
    if not text[parent.start_end:parent.end_start].strip():
        insert_at = parent.end_start
        insertion = "\n" + block + parent_indent
    else:
        close_line_start = text.rfind("\n", 0, parent.end_start) + 1
        insert_at = close_line_start
        insertion = block
    result = text[:insert_at] + insertion + text[insert_at:]
    scan_xml(result)
    return result


def record_projection(entry: WzSubProperty) -> tuple[tuple[str, object], ...]:
    values = []
    for child in entry.children():
        if isinstance(child, WzVectorProperty):
            values.append((child.name, (int(child.x), int(child.y))))
        else:
            values.append((child.name, getattr(child, "value", None)))
    return tuple(values)


def object_projection(image: WzImage) -> dict[tuple[str, str], tuple[tuple[str, object], ...]]:
    result = {}
    for layer in [node for node in image.root.children() if node.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in objects.children():
            if child_value(entry, "oS") == "morass":
                result[(layer.name, entry.name)] = record_projection(entry)
    return result


def walk(node, path: str = ""):
    if not hasattr(node, "children"):
        return
    for child in node.children():
        child_path = f"{path}/{child.name}" if path else child.name
        yield child, child_path
        yield from walk(child, child_path)


def verify_canvases(root: WzSubProperty, label: str) -> int:
    count = 0
    for node, path in walk(root):
        if node.name in {"_outlink", "_inlink"}:
            raise RuntimeError(f"{label}/{path} retains a modern Canvas link")
        if not isinstance(node, WzCanvasProperty):
            continue
        count += 1
        if (int(node.format), int(node.format2)) != (1, 0):
            raise RuntimeError(f"{label}/{path} is not GMS ARGB4444")
        if min(int(node.width), int(node.height)) <= 0 or max(int(node.width), int(node.height)) > 2048:
            raise RuntimeError(f"{label}/{path} has unsafe dimensions")
        decoded = decode_canvas(node, region="GMS").convert("RGBA")
        if decoded.getchannel("A").getbbox() is None:
            raise RuntimeError(f"{label}/{path} has no visible pixels")
    return count


def verify_dependencies(image: WzImage) -> None:
    if sha256_bytes(MORASS_ASSET.read_bytes()) != MORASS_ASSET_SHA256:
        raise RuntimeError("installed morass.img is not the tested compatibility resource")
    asset = load_image(MORASS_ASSET.read_bytes(), GMS_KEY, MORASS_ASSET.name)
    if verify_canvases(image.root, f"Map/{CLIENT.name}") != 1:
        raise RuntimeError("map should contain exactly one visible miniMap Canvas")
    branches = {
        "/".join(str(child_value(entry, name)) for name in ("l0", "l1", "l2"))
        for layer in image.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
        if child_value(entry, "oS") == "morass"
    }
    if len(branches) != 8:
        raise RuntimeError(f"expected 8 Morass resource branches, got {len(branches)}")
    for branch in sorted(branches):
        node = asset.root.get(branch)
        if node is None:
            raise RuntimeError(f"missing Morass resource branch: {branch}")
        if verify_canvases(node, f"Obj/morass.img/{branch}") != 1:
            raise RuntimeError(f"unexpected Canvas count in Morass branch: {branch}")


def xml_object_projection(text: str) -> dict[tuple[str, str], tuple[tuple[str, object], ...]]:
    root = ET.fromstring(text)
    result = {}
    for layer in root:
        if not (layer.tag == "imgdir" and str(layer.get("name", "")).isdigit()):
            continue
        objects = next(
            (child for child in layer if child.tag == "imgdir" and child.get("name") == "obj"),
            None,
        )
        for entry in objects if objects is not None else ():
            fields = []
            for child in entry:
                value = child.get("value")
                if child.tag in {"int", "short", "long"}:
                    value = int(value)
                elif child.tag in {"float", "double"}:
                    value = float(value)
                elif child.tag == "vector":
                    value = (int(child.get("x")), int(child.get("y")))
                fields.append((child.get("name"), value))
            if dict(fields).get("oS") == "morass":
                result[(layer.get("name"), entry.get("name"))] = tuple(fields)
    return result


def protected_records(data: bytes) -> dict[tuple[str, ...], bytes]:
    layout = scan_img(data, region="GMS")
    protected = {}
    for record in layout.root.records:
        if record.name not in {"2", "4"}:
            protected[(record.name,)] = data[record.start:record.end]
            continue
        if record.children is None:
            raise RuntimeError(f"layer {record.name} is not a container")
        for child in record.children.records:
            if child.name != "obj":
                protected[(record.name, child.name)] = data[child.start:child.end]
    return protected


def verify(client_data: bytes, server_text: str, expected) -> None:
    image = load_image(client_data, GMS_KEY, CLIENT.name)
    actual = object_projection(image)
    wanted = {(layer, entry.name): record_projection(entry) for layer, entry in expected}
    if actual != wanted:
        raise RuntimeError(f"client object projection differs: actual={len(actual)} expected={len(wanted)}")
    if xml_object_projection(server_text) != wanted:
        raise RuntimeError("server XML object projection differs from client")
    groups = Counter(dict(fields).get("l1") for fields in actual.values())
    if groups != EXPECTED_GROUP_COUNTS:
        raise RuntimeError(f"generated group counts differ: {groups}")
    if any(set(dict(fields)) & REMOVE_FIELDS for fields in actual.values()):
        raise RuntimeError("generated objects retain modern fields")
    all_objects = sum(
        len(layer.child("obj").children())
        for layer in image.root.children()
        if layer.name.isdigit() and isinstance(layer.child("obj"), WzSubProperty)
    )
    if all_objects != 22:
        raise RuntimeError(f"expected 22 compatible objects, got {all_objects}")
    verify_dependencies(image)


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def build(check_only: bool) -> tuple[str, str, Path | None]:
    source_data = SOURCE.read_bytes()
    if sha256_bytes(source_data) != SOURCE_SHA256:
        raise RuntimeError("TMS 450006130 source hash changed; review before migrating")
    expected = source_objects(load_image(source_data, BMS_KEY, SOURCE.name))
    client_before = CLIENT.read_bytes()
    server_before = SERVER.read_text(encoding="utf-8-sig")
    current = load_image(client_before, GMS_KEY, CLIENT.name)
    current_morass = object_projection(current)
    if current_morass:
        verify(client_before, server_before, expected)
        if sha256_bytes(client_before) != FINAL_CLIENT_SHA256:
            raise RuntimeError("final client map hash changed")
        if sha256_bytes(SERVER.read_bytes()) != FINAL_SERVER_SHA256:
            raise RuntimeError("final server map XML hash changed")
        return sha256_bytes(client_before), sha256_bytes(SERVER.read_bytes()), None
    if sha256_bytes(client_before) != BASELINE_CLIENT_SHA256:
        raise RuntimeError("client map is not the known stable baseline")
    if sha256_bytes(SERVER.read_bytes()) != BASELINE_SERVER_SHA256:
        raise RuntimeError("server map XML is not the known stable baseline")

    protected = protected_records(client_before)
    client_after = client_before
    server_after = server_before
    for layer, entry in expected:
        client_after = append_property(client_after, (layer, "obj"), entry)
        server_after = append_xml_property(server_after, (layer, "obj"), entry)
    verify(client_after, server_after, expected)
    if protected_records(client_after) != protected:
        raise RuntimeError("a protected raw IMG record changed")
    if check_only:
        return sha256_bytes(client_after), sha256_bytes(server_after.encode()), None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path(f"/private/tmp/morass-{MAP_ID}-before-remigration-{timestamp}")
    for path in (CLIENT, SERVER):
        destination = backup / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    atomic_write(CLIENT, client_after)
    atomic_write(SERVER, server_after.encode("utf-8"))
    verify(CLIENT.read_bytes(), SERVER.read_text(encoding="utf-8-sig"), expected)
    return sha256_bytes(CLIENT.read_bytes()), sha256_bytes(SERVER.read_bytes()), backup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="generate and verify without writing")
    args = parser.parse_args()
    client_hash, server_hash, backup = build(args.check)
    print(
        f"450006130 compatible projection: client={client_hash} server={server_hash} "
        f"backup={backup or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
