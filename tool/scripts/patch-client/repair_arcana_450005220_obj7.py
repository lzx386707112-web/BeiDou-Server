#!/usr/bin/env python3
"""Restore the omitted legacy-safe 1/obj/7 record in Arcana map 450005220."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


MAP_ID = 450005220
CLIENT = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
SERVER = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
TMS_MAP = ROOT.parent / f"TMS/MapleStory-IMG/Data/Map/Map/Map4/{MAP_ID}.img"
CLIENT_OBJ = ROOT / "clien/Data/Map/Obj/arcana.img"
PARENT_PATH = ("1", "obj")
INSERT_NAME = "7"
BEFORE_ORDER = (
    "0", "2", "3", "4", "6", "8", "9", "1", "10", "11",
    "12", "13", "14", "15", "5", "16", "17", "18", "19",
)
AFTER_ORDER = (*BEFORE_ORDER, INSERT_NAME)
LEGACY_FIELDS = ("oS", "l0", "l1", "l2", "x", "y", "z", "f", "zM", "r")
EXPECTED_SOURCE = (
    ("oS", "String", "arcana"),
    ("l0", "String", "deepForest"),
    ("l1", "String", "acc"),
    ("l2", "String", "3"),
    ("x", "Int", -1296),
    ("y", "Int", 62),
    ("z", "Int", 14),
    ("f", "Int", 0),
    ("zM", "Int", 0),
    ("r", "Int", 0),
    ("move", "Int", 0),
    ("dynamic", "Int", 0),
    ("piece", "Int", 7),
    ("timeScale", "Int", 0),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_baseline(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def property_signature(node: WzSubProperty) -> tuple[tuple[str, str, object], ...]:
    return tuple((child.name, child.type_name, child.value) for child in node.children())


def projected_node() -> WzSubProperty:
    if not TMS_MAP.is_file():
        raise FileNotFoundError(TMS_MAP)
    source = arc.load_image(TMS_MAP, arc.BMS_KEY)
    if source.truncated or source.parse_warnings:
        raise RuntimeError(
            f"malformed TMS map: truncated={source.truncated} warnings={source.parse_warnings}"
        )
    source_node = source.root.get(f"1/obj/{INSERT_NAME}")
    if not isinstance(source_node, WzSubProperty):
        raise RuntimeError(f"missing TMS object: 1/obj/{INSERT_NAME}")
    actual = property_signature(source_node)
    if actual != EXPECTED_SOURCE:
        raise RuntimeError(f"TMS object contract changed: 1/obj/{INSERT_NAME}: {actual}")

    projected = WzSubProperty(INSERT_NAME)
    for field_name in LEGACY_FIELDS:
        child = source_node.child(field_name)
        if isinstance(child, WzStringProperty):
            projected.add(WzStringProperty(field_name, str(child.value), projected))
        elif isinstance(child, WzIntProperty):
            projected.add(WzIntProperty(field_name, int(child.value), projected))
        else:
            raise RuntimeError(f"unsupported projected field: {INSERT_NAME}/{field_name}")
    return projected


def load_client(data: bytes) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=CLIENT.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed client map: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    return image


def client_state(data: bytes, expected: WzSubProperty) -> str:
    image = load_client(data)
    objects = image.root.get("1/obj")
    if not isinstance(objects, WzSubProperty):
        raise RuntimeError("client map is missing 1/obj")
    order = tuple(child.name for child in objects.children())
    if order == BEFORE_ORDER:
        return "original"
    if order != AFTER_ORDER:
        raise RuntimeError(f"unexpected client 1/obj order: {order}")
    actual = objects.child(INSERT_NAME)
    if not isinstance(actual, WzSubProperty) or property_signature(actual) != property_signature(expected):
        raise RuntimeError(f"client object mismatch: 1/obj/{INSERT_NAME}")
    numbers = {int(child.name) for child in objects.children()}
    if numbers != set(range(20)):
        raise RuntimeError(f"client 1/obj numbering is not complete: {sorted(numbers)}")
    return "repaired"


def xml_signature(node: ET.Element) -> tuple[tuple[str, str, object], ...]:
    output = []
    for child in node:
        type_name = "String" if child.tag == "string" else "Int"
        value: object = child.get("value", "")
        if type_name == "Int":
            value = int(str(value))
        output.append((child.get("name", ""), type_name, value))
    return tuple(output)


def server_state(text: str, expected: WzSubProperty) -> str:
    root = ET.fromstring(text)
    layer = next((child for child in root if child.get("name") == "1"), None)
    layer_children = layer if layer is not None else ()
    objects = next(
        (child for child in layer_children if child.get("name") == "obj"),
        None,
    )
    if objects is None:
        raise RuntimeError("server map is missing 1/obj")
    order = tuple(child.get("name", "") for child in objects)
    if order == BEFORE_ORDER:
        return "original"
    if order != AFTER_ORDER:
        raise RuntimeError(f"unexpected server 1/obj order: {order}")
    actual = next((child for child in objects if child.get("name") == INSERT_NAME), None)
    if actual is None or xml_signature(actual) != property_signature(expected):
        raise RuntimeError(f"server object mismatch: 1/obj/{INSERT_NAME}")
    return "repaired"


def validate_resource_canvas() -> None:
    image = arc.load_image(CLIENT_OBJ, arc.GMS_KEY)
    path = "deepForest/acc/3/0"
    canvas = image.root.get(path)
    if canvas is None or canvas.type_name != "Canvas":
        raise RuntimeError(f"missing client object Canvas: {path}")
    if (int(canvas.format), int(canvas.format2)) != (1, 0):
        raise RuntimeError(f"incompatible Canvas format: {path} {canvas.format}/{canvas.format2}")
    if decode_canvas(canvas, region="GMS").getbbox() is None:
        raise RuntimeError(f"client object Canvas is transparent: {path}")


def build_expected() -> dict[Path, tuple[bytes, bytes]]:
    node = projected_node()
    client_baseline = git_baseline(CLIENT)
    if client_state(client_baseline, node) != "original":
        raise RuntimeError("HEAD client baseline is not the reviewed obj/7 gap")
    client_result = arc.append_property_record(client_baseline, PARENT_PATH, node)
    approved = {(*PARENT_PATH, INSERT_NAME)}
    arc.verify_raw_record_insert_scope(client_baseline, client_result, approved)
    if client_state(client_result, node) != "repaired":
        raise RuntimeError("client repair validation failed")

    server_baseline = git_baseline(SERVER)
    server_text = server_baseline.decode("utf-8")
    if server_state(server_text, node) != "original":
        raise RuntimeError("HEAD server baseline is not the reviewed obj/7 gap")
    server_result_text = arc.append_xml_properties(server_text, PARENT_PATH, [node])
    if server_state(server_result_text, node) != "repaired":
        raise RuntimeError("server repair validation failed")

    validate_resource_canvas()
    return {
        CLIENT: (client_baseline, client_result),
        SERVER: (server_baseline, server_result_text.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    expected = build_expected()
    states = []
    for path, (baseline, result) in expected.items():
        current = path.read_bytes()
        if current == result:
            states.append("repaired")
        elif current == baseline:
            states.append("original")
        else:
            raise RuntimeError(f"refusing unknown target state: {path}")
    if len(set(states)) != 1:
        raise RuntimeError(f"client/server current state differs: {states}")
    if args.check and states[0] != "repaired":
        raise SystemExit(f"{MAP_ID} needs obj/7 repair")

    changed = 0
    if not args.check:
        for path, (_, result) in expected.items():
            if path.read_bytes() == result:
                continue
            if path == CLIENT:
                arc.atomic_write_bytes(path, result)
            else:
                arc.atomic_write_text(path, result.decode("utf-8"))
            changed += 1

    print(f"Arcana {MAP_ID} obj/7 ok: changed={changed}")
    for path, (_, result) in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
