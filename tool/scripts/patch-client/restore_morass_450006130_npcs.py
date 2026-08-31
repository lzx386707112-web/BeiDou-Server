#!/usr/bin/env python3
"""Restore the five TMS NPC resources referenced by Morass map 450006130."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ARC_SCRIPT = ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arc)

sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


MAP_ID = 450006130
NPC_IDS = (9000123, 9000124, 9010109, 9010112, 9010113)
NPC_NAMES = {
    9000123: "大頭沃爾德",
    9000124: "塑膠洛伊",
    9010109: "副官MR.潘喬",
    9010112: "皇家騎士SIR.漢姆斯洛特",
    9010113: "城鎮傳送點",
}
NPC_CANVASES = {
    9000123: 1,
    9000124: 1,
    9010109: 6,
    9010112: 36,
    9010113: 83,
}
SOURCE_SHA256 = {
    "Npc/9000123.img": "6bbb81e7185adf47971d556a1865168677bf8f44597ee0d9449cbaf580f84125",
    "Npc/9000124.img": "0a78d88da2ebaaff0b0810b8c87e188d115da669ab2075572b1343490afec49a",
    "Npc/9010109.img": "faa8af3b03a14107fb5507412db1a15f417fefa5434b05a3e9888bf99ac10701",
    "Npc/9010112.img": "ce11e60b8b09214d57c245c2b850ba841ddd6c2972086be21d1a23e5efec0d0f",
    "Npc/9010113.img": "ad58bea8aa92799e5c2428c031c96de1745b12f7cef802fb3e777dd83e24285c",
    "Npc/_Canvas/9010113.img": "7d9c771c85d5d9d2702d9461c4748e8c979009716d69d6923f03e1e6c817da85",
    "String/Npc.img": "4406787fac0f5d1c5aafb45b803a9138dbfcfc5b1fae3445adc426b9d2aca2ec",
}
FINAL_NPC_SHA256 = {
    9000123: "da3c1b4fc929a23d5aac9b8060351d2c6ceba958f547d83d3d4828dfec5c0f03",
    9000124: "11ae13efdcce8cef189babd4ed4e5d814b1495b6fbb1d9722ee84d0e29aaeaf9",
    9010109: "49c06b7a17c94cf336fa014b32650b335fe23b93c6bcd5d1c3d9dec449c9366d",
    9010112: "7fef6a318cd98fff9b4bdec8c7f73391339d5112af72606d4839b80e7f1daad9",
    9010113: "47546c86c35ccdba80011c3836f6d1c63d61a7081c52534550fa3b56ff52164e",
}

MAP_CLIENT = f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
MAP_SERVER = f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
STRING_CLIENT = "clien/Data/String/Npc.img"
STRING_SERVERS = (
    "gms-server/wz/String.wz/Npc.img.xml",
    "gms-server/wz-zh-CN/String.wz/Npc.img.xml",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_client(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return image


def xml_signature(node: ET.Element):
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        tuple(xml_signature(child) for child in node),
    )


def property_signature(node) -> tuple:
    return xml_signature(ET.fromstring(arc.property_to_xml(node, 0)))


def verify_sources() -> None:
    for relative, expected in SOURCE_SHA256.items():
        path = arc.SOURCE / relative
        if not path.is_file() or sha256_path(path) != expected:
            raise RuntimeError(f"TMS source changed or is missing: {path}")


def verify_existing_npcs(root: Path) -> None:
    for npc_id in NPC_IDS:
        client = root / f"clien/Data/Npc/{npc_id}.img"
        server = root / f"gms-server/wz/Npc.wz/{npc_id}.img.xml"
        if client.exists() and sha256_path(client) != FINAL_NPC_SHA256[npc_id]:
            raise RuntimeError(f"unknown existing client NPC state: {client}")
        if server.exists():
            if not client.exists():
                raise RuntimeError(f"server NPC exists without client NPC: {server}")
            expected = ET.fromstring(
                arc.image_to_xml(
                    load_client(client.read_bytes(), client.name), client.name
                )
            )
            if xml_signature(ET.parse(server).getroot()) != xml_signature(expected):
                raise RuntimeError(f"existing client/server NPC differs: {npc_id}")


def build_npc(npc_id: int) -> tuple[bytes, bytes, int]:
    source = arc.SOURCE / f"Npc/{npc_id}.img"
    image, materializer = arc.clone_image(source, arc.sanitize_npc)
    data = arc.encode_image_body(image, arc.gms_reader())
    if sha256_bytes(data) != FINAL_NPC_SHA256[npc_id]:
        raise RuntimeError(f"generated NPC hash changed: {npc_id}")
    parsed = load_client(data, f"{npc_id}.img")
    canvases = []
    for node, path in arc.walk(parsed.root):
        if node.name in {"_outlink", "_inlink"}:
            raise RuntimeError(f"{npc_id} retained Canvas link at {path}")
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases.append(node)
        if (int(node.format), int(node.format2)) != (1, 0):
            raise RuntimeError(f"{npc_id} contains a non-ARGB4444 Canvas at {path}")
        decoded = decode_canvas(node, region="GMS").convert("RGBA")
        if decoded.size != (int(node.width), int(node.height)):
            raise RuntimeError(f"{npc_id} Canvas decode size mismatch at {path}")
        if decoded.getchannel("A").getbbox() is None:
            raise RuntimeError(f"{npc_id} Canvas has no visible pixels at {path}")
    expected = NPC_CANVASES[npc_id]
    if len(canvases) != expected or materializer.canvases != expected:
        raise RuntimeError(
            f"{npc_id} Canvas count changed: {len(canvases)}/{materializer.canvases}"
        )
    if any(parsed.root.child(f"condition{index}") is not None for index in range(10)):
        raise RuntimeError(f"{npc_id} retained a modern condition action")
    server = arc.image_to_xml(parsed, f"{npc_id}.img").encode("utf-8")
    return data, server, len(canvases)


def source_string_nodes() -> tuple[WzImage, dict[int, WzSubProperty]]:
    source = arc.load_image(arc.SOURCE / "String/Npc.img", arc.BMS_KEY)
    result = {}
    for npc_id in NPC_IDS:
        node = source.root.get(str(npc_id))
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"TMS String/Npc.img has no {npc_id} record")
        name = node.child("name")
        if not isinstance(name, WzStringProperty) or name.value != NPC_NAMES[npc_id]:
            raise RuntimeError(f"unexpected TMS NPC name: {npc_id}")
        result[npc_id] = node
    return source, result


def build_client_strings(
    data: bytes,
    source_image: WzImage,
    source_nodes: dict[int, WzSubProperty],
) -> bytes:
    target = load_client(data, Path(STRING_CLIENT).name)
    result = data
    additions = set()
    for npc_id in NPC_IDS:
        source = source_nodes[npc_id]
        existing = target.root.child(str(npc_id))
        if existing is not None:
            if property_signature(existing) != property_signature(source):
                raise RuntimeError(f"existing client NPC string conflicts: {npc_id}")
            continue
        cloned = arc.clone_property(
            source,
            None,
            source_image,
            arc.SOURCE / "String/Npc.img",
            arc.CanvasMaterializer(),
            str(npc_id),
        )
        result = arc.append_property_record(result, (), cloned)
        additions.add((str(npc_id),))
        target = load_client(result, Path(STRING_CLIENT).name)
    if additions:
        arc.verify_raw_record_scope(data, result, additions, allow_additions=True)
    return result


def build_server_strings(
    data: bytes, source_nodes: dict[int, WzSubProperty]
) -> bytes:
    text = data.decode("utf-8")
    root = ET.fromstring(text)
    additions = []
    for npc_id in NPC_IDS:
        source = source_nodes[npc_id]
        existing = next(
            (child for child in root if child.get("name") == str(npc_id)), None
        )
        if existing is not None:
            if xml_signature(existing) != property_signature(source):
                raise RuntimeError(f"existing server NPC string conflicts: {npc_id}")
            continue
        additions.append(source)
    if additions:
        text = arc.append_xml_properties(text, (), additions)
        ET.fromstring(text)
    return text.encode("utf-8")


def verify_map_contract(root: Path) -> None:
    client = load_client((root / MAP_CLIENT).read_bytes(), Path(MAP_CLIENT).name)
    life = client.root.child("life")
    client_ids = {
        int(arc.child_value(entry, "id"))
        for entry in life.children()
        if arc.child_value(entry, "type") == "n"
    }
    server = ET.parse(root / MAP_SERVER).getroot()
    server_life = server.find('./imgdir[@name="life"]')
    server_ids = {
        int(next(child for child in entry if child.get("name") == "id").get("value"))
        for entry in server_life
        if next(child for child in entry if child.get("name") == "type").get("value") == "n"
    }
    missing_client = set(NPC_IDS) - client_ids
    missing_server = set(NPC_IDS) - server_ids
    if missing_client or missing_server:
        raise RuntimeError(
            f"450006130 life contract missing: client={sorted(missing_client)} "
            f"server={sorted(missing_server)}"
        )


def build_outputs(root: Path) -> tuple[dict[str, bytes], int]:
    verify_sources()
    verify_existing_npcs(root)
    verify_map_contract(root)
    source_image, source_nodes = source_string_nodes()
    outputs = {}
    canvases = 0
    for npc_id in NPC_IDS:
        client, server, count = build_npc(npc_id)
        outputs[f"clien/Data/Npc/{npc_id}.img"] = client
        outputs[f"gms-server/wz/Npc.wz/{npc_id}.img.xml"] = server
        canvases += count
    outputs[STRING_CLIENT] = build_client_strings(
        (root / STRING_CLIENT).read_bytes(), source_image, source_nodes
    )
    for relative in STRING_SERVERS:
        outputs[relative] = build_server_strings(
            (root / relative).read_bytes(), source_nodes
        )
    return outputs, canvases


def write_outputs(root: Path, outputs: dict[str, bytes], *, no_backup: bool) -> None:
    arc.ROOT = root
    arc.BACKUP_ROOT = Path("/private/tmp/morass-450006130-npc-backup")
    for relative, data in outputs.items():
        path = root / relative
        if path.exists() and path.read_bytes() == data:
            continue
        if path.exists() and not no_backup:
            arc.backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arc.atomic_write_bytes(path, data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()
    outputs, canvases = build_outputs(ROOT)
    if not args.check:
        write_outputs(ROOT, outputs, no_backup=args.no_backup)
    print(f"check={args.check} map={MAP_ID} npcs={len(NPC_IDS)} canvases={canvases}")
    for relative, data in outputs.items():
        print(f"{relative} {sha256_bytes(data)} {len(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
