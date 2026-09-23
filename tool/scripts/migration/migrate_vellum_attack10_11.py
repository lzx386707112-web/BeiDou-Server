#!/usr/bin/env python3
"""Incrementally migrate Vellum attack10/11 without modern screen canvases."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Mob/_Canvas/8930000.img")
CLIENT = ROOT / "clien/Data/Mob/8930000.img"
SERVER = ROOT / "gms-server/wz/Mob.wz/8930000.img.xml"
ACTIONS = ("attack10", "attack11")
ANCHOR = "attack12"

sys.path.insert(0, str(ROOT / "tool/resource-workbench"))

from map_mob import app  # noqa: E402
from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402


EXPECTED_RANGES = {
    "attack10": ((-7000, -1300), (-635, 70)),
    "attack11": ((-7727, -1225), (-588, -23)),
}
EXPECTED_FRAMES = {"attack10": 12, "attack11": 7}


def _ordered_children(node: WzSubProperty, names: list[str]) -> None:
    children = {child.name: child for child in node.children()}
    ordered = [children[name] for name in names if name in children]
    ordered.extend(child for child in node.children() if child.name not in names)
    node._children = {child.name: child for child in ordered}
    for child in ordered:
        child.parent = node


def _restore_hit_uols(info: WzSubProperty) -> None:
    hit = WzSubProperty("hit", info)
    for index in range(9):
        hit.add(WzUolProperty(
            str(index), f"../../../attack3/info/hit/{index}", hit,
        ))
    if info.child("hit") is None:
        info.add(hit)
    else:
        info._children["hit"] = hit


def build_action(
    action_name: str,
    source_image,
    client_image,
) -> WzSubProperty:
    source_action = source_image.root.get(action_name)
    if not isinstance(source_action, WzSubProperty):
        raise RuntimeError(f"missing TMS canvas action: {action_name}")
    action, _materializer, _stats = app.clone_compatible_mob_node(
        source_action,
        source_image,
        SOURCE,
        client_image=client_image,
        copied_root=action_name,
        dest_mob_id="8930000",
    )
    if not isinstance(action, WzSubProperty):
        raise RuntimeError(f"projected action is not a directory: {action_name}")
    info = action.child("info")
    if not isinstance(info, WzSubProperty) or info.child("screen") is None:
        raise RuntimeError(f"missing TMS screen node: {action_name}/info/screen")
    info._children.pop("screen")
    _restore_hit_uols(info)
    _ordered_children(info, ["hit", "range"])

    logical = app.companion_logical_node(SOURCE, action_name)
    if not isinstance(logical, WzSubProperty):
        raise RuntimeError(f"missing TMS logical action: {action_name}")
    _ordered_children(
        action,
        [child.name for child in logical.children()],
    )
    return action


def _vector(node: WzSubProperty, name: str) -> tuple[int, int]:
    value = node.child(name)
    if not isinstance(value, WzVectorProperty):
        raise RuntimeError(f"missing vector: {node.name}/{name}")
    return int(value.x), int(value.y)


def validate_action(action: WzSubProperty, action_name: str) -> None:
    info = action.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"missing action info: {action_name}")
    if info.child("screen") is not None:
        raise RuntimeError(f"modern screen leaked into client action: {action_name}")
    hit = info.child("hit")
    if not isinstance(hit, WzSubProperty):
        raise RuntimeError(f"missing hit table: {action_name}")
    for index in range(9):
        node = hit.child(str(index))
        expected = f"../../../attack3/info/hit/{index}"
        if not isinstance(node, WzUolProperty) or str(node.value) != expected:
            raise RuntimeError(f"invalid hit UOL: {action_name}/info/hit/{index}")
    attack_range = info.child("range")
    if not isinstance(attack_range, WzSubProperty):
        raise RuntimeError(f"missing range: {action_name}")
    expected_lt, expected_rb = EXPECTED_RANGES[action_name]
    if _vector(attack_range, "lt") != expected_lt or _vector(attack_range, "rb") != expected_rb:
        raise RuntimeError(f"range mismatch: {action_name}")

    frames = [
        child for child in action.children()
        if isinstance(child, WzCanvasProperty) and child.name.isdigit()
    ]
    if [int(frame.name) for frame in frames] != list(range(EXPECTED_FRAMES[action_name])):
        raise RuntimeError(f"frame sequence mismatch: {action_name}")
    for frame in frames:
        if (int(frame.format), int(frame.format2)) != (1, 0):
            raise RuntimeError(f"non-ARGB4444 frame: {action_name}/{frame.name}")
        bitmap = decode_canvas(frame, region="GMS").convert("RGBA")
        try:
            if not bitmap.getchannel("A").getbbox():
                raise RuntimeError(f"blank action frame: {action_name}/{frame.name}")
        finally:
            bitmap.close()
    if action_name == "attack10":
        repeat = action.child("repeatFrameTime")
        if repeat is None or int(repeat.value) != 4210:
            raise RuntimeError("attack10/repeatFrameTime mismatch")


def validate_xml(data: bytes) -> None:
    root = ET.fromstring(data)
    names = [child.get("name") for child in root]
    expected = [*ACTIONS, ANCHOR]
    start = names.index(ACTIONS[0])
    if names[start:start + len(expected)] != expected:
        raise RuntimeError("server XML action order mismatch")
    for action_name in ACTIONS:
        node = root.find(f'./imgdir[@name="{action_name}"]')
        if node is None:
            raise RuntimeError(f"server XML action missing: {action_name}")
        if node.find('./imgdir[@name="info"]/imgdir[@name="screen"]') is not None:
            raise RuntimeError(f"server XML contains modern screen: {action_name}")


def migrate() -> dict[str, object]:
    original_client = CLIENT.read_bytes()
    original_server = SERVER.read_bytes()
    client_image = app._verified_img_from_bytes(CLIENT, original_client)
    compacted_actions = tuple(
        child.name for child in client_image.root.children()
        if child.name.startswith("attack")
    )
    if compacted_actions in (
        tuple(f"attack{index}" for index in range(1, 11)),
        tuple(f"attack{index}" for index in range(1, 9)),
    ):
        server_root = ET.fromstring(original_server)
        server_actions = tuple(
            child.get("name") for child in server_root
            if child.tag == "imgdir" and str(child.get("name", "")).startswith("attack")
        )
        if server_actions != compacted_actions:
            raise RuntimeError("compacted client/server Vellum action tables disagree")
        if len(compacted_actions) == 8:
            for name in ("skill2", "skill3"):
                if client_image.root.get(name) is None or server_root.find(f'./imgdir[@name="{name}"]') is None:
                    raise RuntimeError(f"missing projected Vellum {name}")
        return {
            "inserted": [],
            "clientSha256": hashlib.sha256(original_client).hexdigest(),
            "serverSha256": hashlib.sha256(original_server).hexdigest(),
        }
    source_image = app.load_image(SOURCE)
    expected = {
        name: build_action(name, source_image, client_image)
        for name in ACTIONS
    }

    existing = {name for name in ACTIONS if client_image.root.get(name) is not None}
    for name in existing:
        current = client_image.root.get(name)
        if not isinstance(current, WzSubProperty):
            raise RuntimeError(f"existing client action is not a directory: {name}")
        validate_action(current, name)
    missing = [expected[name] for name in ACTIONS if name not in existing]
    client_data = original_client
    if missing:
        client_data = app.arc.insert_property_records_before(
            client_data, (), missing, ANCHOR,
        )
        app.arc.verify_raw_record_insert_scope(
            original_client,
            client_data,
            {(node.name,) for node in missing},
        )

    verified = app._verified_img_from_bytes(CLIENT, client_data)
    names = [child.name for child in verified.root.children()]
    start = names.index(ACTIONS[0])
    if names[start:start + 3] != [*ACTIONS, ANCHOR]:
        raise RuntimeError("client action order mismatch")
    for name in ACTIONS:
        action = verified.root.get(name)
        if not isinstance(action, WzSubProperty):
            raise RuntimeError(f"client action missing after migration: {name}")
        validate_action(action, name)

    server_root = ET.fromstring(original_server)
    server_names = {child.get("name") for child in server_root}
    server_missing = [expected[name] for name in ACTIONS if name not in server_names]
    server_data = original_server
    if server_missing:
        server_data = app.arc.insert_xml_properties_before(
            original_server.decode("utf-8"), (), server_missing, ANCHOR,
        ).encode("utf-8")
    validate_xml(server_data)

    written: list[tuple[Path, bytes]] = []
    try:
        if client_data != original_client:
            app.atomic_write(CLIENT, client_data, backup=False)
            written.append((CLIENT, original_client))
        if server_data != original_server:
            app.atomic_write(SERVER, server_data, backup=False)
            written.append((SERVER, original_server))
        app._load_image_cached.cache_clear()
        app._verified_img_from_bytes(CLIENT, CLIENT.read_bytes())
        ET.parse(SERVER)
    except Exception:
        for path, data in reversed(written):
            app.atomic_write(path, data, backup=False)
        app._load_image_cached.cache_clear()
        raise

    return {
        "inserted": [node.name for node in missing],
        "clientSha256": hashlib.sha256(client_data).hexdigest(),
        "serverSha256": hashlib.sha256(server_data).hexdigest(),
    }


def main() -> None:
    result = migrate()
    print(
        f"inserted={','.join(result['inserted']) or 'none'} "
        f"client={result['clientSha256']} server={result['serverSha256']}"
    )


if __name__ == "__main__":
    main()
