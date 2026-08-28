#!/usr/bin/env python3
"""Incrementally install Lacheln item 2436037 and its missing NPC resources."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


ITEM_ID = 2436037
ITEM_NAME = f"0{ITEM_ID}"
NEW_NPC_IDS = (3003200, 3003208, 9000159, 9010100)
NPC_IDS = (*NEW_NPC_IDS, 3006902)
ITEM_STRING_NAME = "神祕的核心寶石"
NPC_NAMES = {
    3003200: "露希妲",
    3003208: "防毒面具",
    9000159: "楓之谷管理者",
    9010100: "夢中的破布娃娃",
    3006902: "平靜的池水邊",
}
NPC_CANVAS_COUNTS = {3003200: 15, 3003208: 1, 9000159: 4, 9010100: 12}

CLIENT_ITEM = ROOT / "clien/Data/Item/Consume/0243.img"
CLIENT_ITEM_STRING = ROOT / "clien/Data/String/Consume.img"
CLIENT_NPC_STRING = ROOT / "clien/Data/String/Npc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Consume/0243.img.xml"
SERVER_ITEM_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Consume.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Consume.img.xml",
)
SERVER_NPC_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Npc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Npc.img.xml",
)
CLIENT_NPCS = {
    npc_id: ROOT / f"clien/Data/Npc/{npc_id}.img" for npc_id in NEW_NPC_IDS
}
SERVER_NPCS = {
    npc_id: ROOT / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
    for npc_id in NEW_NPC_IDS
}
PREVIOUS_SHA256 = {
    CLIENT_NPC_STRING: "5fcd78b784a317c33bc649d2e2748d27d1cf10ef81733dba89358d05ddbfd7ba",
    SERVER_NPC_STRINGS[0]: "a9262f599184a0bbcfaa4266deaf08369487ce7424d72d4a2af5c91bb042b70e",
    SERVER_NPC_STRINGS[1]: "9a66035d63d848ca7339e6786a48e52023be00fbbb7b2ab05ccbc61c0b62d007",
}
TRANSITION_SHA256 = {
    SERVER_NPC_STRINGS[1]: "453be136038ebe2e8e1534a943ec3827d6d9812070938efb0352f0ae3fc8ad4d",
}


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


def checked_image(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"unsafe IMG {name}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return image


def visible_canvases(root) -> list[tuple[str, WzCanvasProperty]]:
    canvases = []
    for node, path in arc.walk(root):
        if not isinstance(node, WzCanvasProperty):
            continue
        if (node.format, node.format2) != (1, 0):
            raise RuntimeError(f"incompatible Canvas {path}: {node.format}/{node.format2}")
        if not decode_canvas(node, region="GMS").getbbox():
            raise RuntimeError(f"empty Canvas: {path}")
        canvases.append((path, node))
    return canvases


def build_item_nodes() -> tuple[WzSubProperty, WzSubProperty]:
    item_path = SOURCE / "Item/Consume/0243.img"
    string_path = SOURCE / "String/Consume.img"
    item_image = arc.load_image(item_path, arc.BMS_KEY)
    string_image = arc.load_image(string_path, arc.BMS_KEY)
    source_item = item_image.root.get(ITEM_NAME)
    source_string = string_image.root.get(str(ITEM_ID))
    if not isinstance(source_item, WzSubProperty) or not isinstance(
        source_string, WzSubProperty
    ):
        raise RuntimeError(f"TMS item resource is missing: {ITEM_ID}")

    item = arc.clone_property(
        source_item, None, item_image, item_path, arc.CanvasMaterializer(), ITEM_NAME
    )
    string = arc.clone_property(
        source_string,
        None,
        string_image,
        string_path,
        arc.CanvasMaterializer(),
        str(ITEM_ID),
    )
    canvases = visible_canvases(item)
    dimensions = {path: (canvas.width, canvas.height) for path, canvas in canvases}
    if dimensions != {"info/icon": (38, 38), "info/iconRaw": (38, 38)}:
        raise RuntimeError(f"unexpected item Canvas contract: {dimensions}")
    if string.get("name").value != ITEM_STRING_NAME:
        raise RuntimeError(f"unexpected item name: {string.get('name').value}")
    return item, string


def build_npc_resources() -> tuple[dict[int, bytes], dict[int, bytes], dict[int, WzSubProperty]]:
    client: dict[int, bytes] = {}
    server: dict[int, bytes] = {}
    for npc_id in NEW_NPC_IDS:
        image, materializer = arc.clone_image(
            SOURCE / f"Npc/{npc_id}.img", arc.sanitize_npc
        )
        roots = [child.name for child in image.root.children()]
        if any(name.startswith("condition") for name in roots):
            raise RuntimeError(f"unsupported NPC condition root remains: {npc_id}")
        canvases = visible_canvases(image.root)
        if len(canvases) != NPC_CANVAS_COUNTS[npc_id]:
            raise RuntimeError(f"unexpected NPC Canvas count: {npc_id}/{len(canvases)}")
        if materializer.canvases != len(canvases):
            raise RuntimeError(f"NPC Canvas materialization mismatch: {npc_id}")
        data = arc.encode_image_body(image, arc.gms_reader())
        checked_image(data, f"{npc_id}.img")
        client[npc_id] = data
        server[npc_id] = arc.image_to_xml(image, f"{npc_id}.img").encode("utf-8")
        ET.fromstring(server[npc_id])

    source_path = SOURCE / "String/Npc.img"
    source = arc.load_image(source_path, arc.BMS_KEY)
    strings: dict[int, WzSubProperty] = {}
    for npc_id in NPC_IDS:
        node = source.root.get(str(npc_id))
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"TMS NPC String is missing: {npc_id}")
        strings[npc_id] = arc.clone_property(
            node,
            None,
            source,
            source_path,
            arc.CanvasMaterializer(),
            str(npc_id),
        )
        if strings[npc_id].get("name").value != NPC_NAMES[npc_id]:
            raise RuntimeError(f"unexpected NPC name: {npc_id}")
    return client, server, strings


def insert_binary_records(
    baseline: bytes, nodes: dict[int, WzSubProperty], anchors: dict[int, str]
) -> bytes:
    result = baseline
    for record_id, anchor in anchors.items():
        result = arc.insert_property_record_before(result, (), nodes[record_id], anchor)
    arc.verify_raw_record_insert_scope(
        baseline, result, {(str(record_id),) for record_id in anchors}
    )
    return result


def insert_xml_records(
    baseline: bytes, nodes: dict[int, WzSubProperty], anchors: dict[int, str]
) -> bytes:
    result = baseline.decode("utf-8")
    for record_id, anchor in anchors.items():
        result = arc.insert_xml_properties_before(result, (), [nodes[record_id]], anchor)
    ET.fromstring(result)
    return result.encode("utf-8")


def build_expected() -> dict[Path, tuple[bytes | None, bytes]]:
    item, item_string = build_item_nodes()
    npc_client, npc_server, npc_strings = build_npc_resources()
    output: dict[Path, tuple[bytes | None, bytes]] = {}

    baseline = git_baseline(CLIENT_ITEM)
    result = arc.append_property_record(baseline, (), item)
    arc.verify_raw_record_insert_scope(baseline, result, {(ITEM_NAME,)})
    output[CLIENT_ITEM] = (baseline, result)

    baseline = git_baseline(CLIENT_ITEM_STRING)
    result = arc.insert_property_record_before(baseline, (), item_string, "2440000")
    arc.verify_raw_record_insert_scope(baseline, result, {(str(ITEM_ID),)})
    output[CLIENT_ITEM_STRING] = (baseline, result)

    prior_main_npcs = {
        3003208: "3003209",
        9000159: "9000174",
        9010100: "9020000",
    }
    prior_zh_npcs = {
        3003208: "3003300",
        3006902: "3007007",
        9000159: "9000174",
        9010100: "9020000",
    }

    head_baseline = git_baseline(CLIENT_NPC_STRING)
    baseline = insert_binary_records(head_baseline, npc_strings, prior_main_npcs)
    if sha256(baseline) != PREVIOUS_SHA256[CLIENT_NPC_STRING]:
        raise RuntimeError("previous client NPC String baseline hash mismatch")
    result = arc.insert_property_record_before(
        baseline, (), npc_strings[3003200], "3003201"
    )
    arc.verify_raw_record_insert_scope(baseline, result, {("3003200",)})
    output[CLIENT_NPC_STRING] = (baseline, result)

    baseline = git_baseline(SERVER_ITEM)
    output[SERVER_ITEM] = (
        baseline,
        arc.append_xml_properties(baseline.decode("utf-8"), (), [item]).encode("utf-8"),
    )
    for path in SERVER_ITEM_STRINGS:
        baseline = git_baseline(path)
        result = arc.insert_xml_properties_before(
            baseline.decode("utf-8"), (), [item_string], "2440000"
        ).encode("utf-8")
        output[path] = (baseline, result)

    for path, prior_anchors, new_anchor in (
        (SERVER_NPC_STRINGS[0], prior_main_npcs, "3003201"),
        (SERVER_NPC_STRINGS[1], prior_zh_npcs, "3003208"),
    ):
        head_baseline = git_baseline(path)
        baseline = insert_xml_records(head_baseline, npc_strings, prior_anchors)
        if sha256(baseline) != PREVIOUS_SHA256[path]:
            raise RuntimeError(f"previous server NPC String baseline hash mismatch: {path}")
        result = arc.insert_xml_properties_before(
            baseline.decode("utf-8"), (), [npc_strings[3003200]], new_anchor
        ).encode("utf-8")
        output[path] = (baseline, result)

    for npc_id in NEW_NPC_IDS:
        output[CLIENT_NPCS[npc_id]] = (None, npc_client[npc_id])
        output[SERVER_NPCS[npc_id]] = (None, npc_server[npc_id])

    validate_expected(output)
    return output


def validate_expected(expected: dict[Path, tuple[bytes | None, bytes]]) -> None:
    for path in (CLIENT_ITEM, CLIENT_ITEM_STRING, CLIENT_NPC_STRING, *CLIENT_NPCS.values()):
        image = checked_image(expected[path][1], path.name)
        if path in CLIENT_NPCS.values():
            visible_canvases(image.root)

    item = checked_image(expected[CLIENT_ITEM][1], CLIENT_ITEM.name).root.get(ITEM_NAME)
    if not isinstance(item, WzSubProperty):
        raise RuntimeError(f"generated client item is missing: {ITEM_ID}")
    visible_canvases(item)

    for path, (_baseline, result) in expected.items():
        if path.suffix == ".xml":
            ET.fromstring(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    expected = build_expected()
    changed: list[Path] = []
    for path, (baseline, result) in expected.items():
        current = path.read_bytes() if path.exists() else None
        if current == result:
            continue
        transition_hash = TRANSITION_SHA256.get(path)
        known_transition = current is not None and (
            transition_hash is not None and sha256(current) == transition_hash
        )
        if current != baseline and not known_transition:
            raise RuntimeError(f"refusing unknown resource state: {path}")
        if args.check:
            raise SystemExit(f"{path} needs Lacheln resources")
        arc.atomic_write_bytes(path, result)
        changed.append(path)

    print(f"Lacheln item/NPC resources ok: changed={len(changed)}")
    for path, (_baseline, result) in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
