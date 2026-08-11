#!/usr/bin/env python3
"""Contract checks for the legacy equipment cube system."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_equipment_cubes import (  # noqa: E402
    CLIENT_ITEM,
    CLIENT_STRING,
    CUBES,
    GMS_KEY,
    SERVER_ITEM,
    SERVER_STRINGS,
    TARGET_ITEM_NODES,
    TARGET_STRING_NODES,
    load_image_bytes,
    locate_child_records,
    locate_root_records,
)
from wzpy import WzCanvasProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git_blob(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def raw_root_records(data: bytes, name: str):
    image = load_image_bytes(data, name)
    names, spans = locate_root_records(image, data)
    return names, {entry: data[start:end] for entry, (start, end) in zip(names, spans)}


def raw_child_records(data: bytes, name: str, parent: str):
    image = load_image_bytes(data, name)
    _, _, names, spans = locate_child_records(image, data, parent)
    return names, {entry: data[start:end] for entry, (start, end) in zip(names, spans)}


def check_client_binary_scope() -> None:
    baseline = git_blob(CLIENT_ITEM)
    current = CLIENT_ITEM.read_bytes()
    old_names, old_records = raw_root_records(baseline, CLIENT_ITEM.name)
    new_names, new_records = raw_root_records(current, CLIENT_ITEM.name)
    require(old_names == new_names, "client item order changed")
    changed = {name for name in old_names if old_records[name] != new_records[name]}
    require(changed == TARGET_ITEM_NODES, f"unexpected client item changes: {changed}")

    baseline = git_blob(CLIENT_STRING)
    current = CLIENT_STRING.read_bytes()
    old_names, old_records = raw_child_records(baseline, CLIENT_STRING.name, "Etc")
    new_names, new_records = raw_child_records(current, CLIENT_STRING.name, "Etc")
    require(old_names == new_names, "client string item order changed")
    changed = {name for name in old_names if old_records[name] != new_records[name]}
    require(changed == TARGET_STRING_NODES, f"unexpected client string changes: {changed}")


def check_client_semantics() -> None:
    item_data = CLIENT_ITEM.read_bytes()
    item = load_image_bytes(item_data, CLIENT_ITEM.name)
    strings = load_image_bytes(CLIENT_STRING.read_bytes(), CLIENT_STRING.name)
    for spec in CUBES:
        require(strings.get(f"Etc/{spec.item_id}/name").value == spec.name,
                f"wrong client name {spec.item_id}")
        require(strings.get(f"Etc/{spec.item_id}/desc").value == spec.description,
                f"wrong client description {spec.item_id}")
        for name in ("icon", "iconRaw"):
            canvas = item.get(f"{spec.item_node}/info/{name}")
            require(isinstance(canvas, WzCanvasProperty), f"missing Canvas {spec.item_id}/{name}")
            require((canvas.format, canvas.format2) == (1, 0),
                    f"non-ARGB4444 Canvas {spec.item_id}/{name}")
            decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
            require(decoded.size == (31, 31), f"wrong Canvas size {spec.item_id}/{name}")
            require(decoded.getchannel("A").getbbox() is not None,
                    f"transparent Canvas {spec.item_id}/{name}")


def find_child(parent: ET.Element, tag: str, name: str) -> ET.Element:
    result = next((child for child in parent if child.tag == tag and child.get("name") == name), None)
    if result is None:
        raise AssertionError(f"missing XML {tag} {name}")
    return result


def check_server_resources() -> None:
    item_root = ET.parse(SERVER_ITEM).getroot()
    for spec in CUBES:
        item = find_child(item_root, "imgdir", spec.item_node)
        info = find_child(item, "imgdir", "info")
        for name in ("icon", "iconRaw"):
            canvas = find_child(info, "canvas", name)
            require(canvas.get("format") == "1", f"wrong server Canvas format {spec.item_id}/{name}")
        for path in SERVER_STRINGS:
            root = ET.parse(path).getroot()
            parent = find_child(root, "imgdir", "Etc")
            node = find_child(parent, "imgdir", str(spec.item_id))
            require(find_child(node, "string", "name").get("value") == spec.name,
                    f"wrong server cube name {path}/{spec.item_id}")
            require(find_child(node, "string", "desc").get("value") == spec.description,
                    f"wrong server cube description {path}/{spec.item_id}")


def check_source_contract() -> None:
    manager = (ROOT / "gms-server/src/main/java/org/gms/server/EquipmentCubeManager.java").read_text()
    npc = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/魔方洗练.js").read_text()
    center = (ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/装备中心.js").read_text()
    equip = (ROOT / "gms-server/src/main/java/org/gms/client/inventory/Equip.java").read_text()
    for spec in CUBES:
        require(str(spec.item_id) in manager and str(spec.item_id) in npc,
                f"cube id missing from server contract: {spec.item_id}")
    require("expandAttribute4" in manager, "cube data is not persisted in expandAttribute4")
    require("EquipmentCubeManager.inherit(oldItem, this)" in equip,
            "replaceData does not inherit cube data")
    require('openNpc("魔方洗练")' in center, "equipment center has no cube entry")
    require("EquipmentCubeManager.roll" in npc, "cube roll is not server-authoritative")
    require("pendingRoll.canKeepOld()" in npc, "black cube keep-old behavior is missing")
    require("升阶失败时保持当前强度" in npc, "potential rank failure behavior is missing")
    require("forceUpdateItem(current)" in npc, "cube result is not sent to the client")


def main() -> None:
    check_client_binary_scope()
    check_client_semantics()
    check_server_resources()
    check_source_contract()
    print("equipment cube contract passed: 8 cubes, exact IMG scope, visible ARGB4444 icons")


if __name__ == "__main__":
    main()
