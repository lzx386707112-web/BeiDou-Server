#!/usr/bin/env python3
"""Repair Tenebris maps 450009301 and 450011990 for the legacy client."""

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


NPC_ID = 3003907
MAP_301_CLIENT = "clien/Data/Map/Map/Map4/450009301.img"
MAP_301_SERVER = "gms-server/wz/Map.wz/Map/Map4/450009301.img.xml"
MAP_990_CLIENT = "clien/Data/Map/Map/Map4/450011990.img"
MAP_990_SERVER = "gms-server/wz/Map.wz/Map/Map4/450011990.img.xml"
NPC_CLIENT = f"clien/Data/Npc/{NPC_ID}.img"
NPC_SERVER = f"gms-server/wz/Npc.wz/{NPC_ID}.img.xml"
NPC_STRING_CLIENT = "clien/Data/String/Npc.img"
NPC_STRING_SERVERS = (
    "gms-server/wz/String.wz/Npc.img.xml",
    "gms-server/wz-zh-CN/String.wz/Npc.img.xml",
)

MAP_301_SERVER_BLOCKS = ("foothold", "info", "portal")
MAP_990_REMOVALS = (
    ("info", "AmbientBGM"),
    ("info", "AmbientBGMv"),
    ("info", "lvLimit"),
    ("info", "noChair"),
    ("info", "qrLimit"),
    ("info", "quarterView"),
    ("portal", "0", "horizontalImpact"),
)

SOURCE_SHA256 = {
    "Npc/3003907.img": "d2bee2b6bb1a9729a903fe64f696af482af111417f10d6d8e2e7b384fb1e503d",
    "Npc/_Canvas/3003907.img": "f4ffbf93c30c29f6253fca01121213a640badc5316d32bf462681cc32c96e91e",
    "String/Npc.img": "4406787fac0f5d1c5aafb45b803a9138dbfcfc5b1fae3445adc426b9d2aca2ec",
}

BASELINE_SHA256 = {
    MAP_301_SERVER: "6d839dee18a7fd93b6a287fc62dd2d80555d62240539976512a1e63bb250a7d4",
    MAP_990_CLIENT: "2602dea0efadaa8e47d80d40c2c6124647c19ba526534a1eca54e0b37601556a",
    NPC_STRING_CLIENT: "3f3cbf940bcd005fd6a5b3df431bc3f7729f15941cd7aeb01c4c65f3ff13c97e",
    NPC_STRING_SERVERS[0]: "3360a7d1088aa59dd09113d0ce372ea64f533d755ce3d854681ffe5e7bd57b77",
    NPC_STRING_SERVERS[1]: "ecbfd61236b04875b98cbf547b1040543ab72c5d2717f0590e48950eb50cec3f",
}

FINAL_SHA256 = {
    MAP_301_SERVER: "9c42ab56bfe8b3551a136ce83735d329d9f762827a0bd46455363e9f96047202",
    MAP_990_CLIENT: "cb298f56bb437775e2cfbf30e75bedfe9f94d9bc42c3c0ec198abbbccd4c16d2",
    NPC_CLIENT: "2158f9f53e0d31cb4322263fe4b70e06615d8647b488546899bb09d01fb20fad",
    NPC_SERVER: "f19eaecd2dce39d0bc2afed7132728dda82c3ea46e0d1f220759321f6deb340e",
    NPC_STRING_CLIENT: "a5415d3332ee85c122876ccf0cbc9cc2db253200604aaab672b706be3ccdca68",
    NPC_STRING_SERVERS[0]: "0f4ccb1a3bd1413503eb7e0dd91aee6acb1e1e2c52589fc4cc31b7f065b0c88e",
    NPC_STRING_SERVERS[1]: "6b5951d688e1dd93d32128e24d8b5ded69f2e079081b210414fbefbdc462c6f5",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def walk(node):
    yield node
    if hasattr(node, "children"):
        for child in node.children():
            yield from walk(child)


def load_client(data: bytes, name: str) -> WzImage:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed {name}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return image


def verify_sources() -> None:
    for relative, expected in SOURCE_SHA256.items():
        path = arc.SOURCE / relative
        if not path.is_file() or sha256_path(path) != expected:
            raise RuntimeError(f"TMS source changed or is missing: {path}")


def verify_known_states(root: Path) -> None:
    for relative, baseline in BASELINE_SHA256.items():
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"missing baseline file: {relative}")
        allowed = {baseline}
        if relative in FINAL_SHA256:
            allowed.add(FINAL_SHA256[relative])
        actual = sha256_path(path)
        if actual not in allowed:
            raise RuntimeError(f"unknown repair state: {relative} {actual}")
    for relative in (NPC_CLIENT, NPC_SERVER):
        path = root / relative
        if path.exists() and sha256_path(path) != FINAL_SHA256.get(relative):
            raise RuntimeError(f"unknown existing generated artifact: {relative}")


def verify_raw_removals(before: bytes, after: bytes) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    removed = set(before_records) - set(after_records)
    expected_removed = set(MAP_990_REMOVALS)
    if removed != expected_removed:
        raise RuntimeError(f"unexpected removed IMG records: {sorted(removed)}")
    added = set(after_records) - set(before_records)
    if added:
        raise RuntimeError(f"unexpected added IMG records: {sorted(added)}")

    for parent, names in before_orders.items():
        if parent in removed:
            continue
        expected = tuple(
            name for name in names if (*parent, name) not in expected_removed
        )
        if after_orders.get(parent) != expected:
            raise RuntimeError(f"IMG sibling order changed at {parent}")

    for path, raw in before_records.items():
        if path in removed:
            continue
        ancestor = any(target[: len(path)] == path for target in expected_removed)
        if not ancestor and after_records.get(path) != raw:
            raise RuntimeError(f"protected IMG record changed: {path}")


def repair_map_990(data: bytes) -> bytes:
    image = load_client(data, Path(MAP_990_CLIENT).name)
    states = [image.root.get("/".join(path)) is not None for path in MAP_990_REMOVALS]
    if any(states) and not all(states):
        raise RuntimeError("450011990 has a partial legacy-field repair")
    if not any(states):
        return data
    result = data
    for path in MAP_990_REMOVALS:
        result = arc.mutate_img(result, "remove", path, region="GMS").data
    verify_raw_removals(data, result)
    repaired = load_client(result, Path(MAP_990_CLIENT).name)
    if any(repaired.root.get("/".join(path)) is not None for path in MAP_990_REMOVALS):
        raise RuntimeError("450011990 retained a removed legacy field")
    return result


def xml_span_with_indent(text: str, node) -> tuple[int, int]:
    start = node.start
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip() == "":
        start = line_start
    end = node.end
    if end < len(text) and text[end] == "\n":
        end += 1
    return start, end


def replace_direct_xml_block(text: str, name: str, replacement: str) -> str:
    root = arc.scan_xml(text)
    matches = [child for child in root.children if child.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"server XML block is not unique: {name}")
    start, end = xml_span_with_indent(text, matches[0])
    result = text[:start] + replacement + "\n" + text[end:]
    arc.scan_xml(result)
    return result


def masked_xml(text: str, names: tuple[str, ...]) -> str:
    root = arc.scan_xml(text)
    spans = []
    for name in names:
        matches = [child for child in root.children if child.name == name]
        if len(matches) != 1:
            raise RuntimeError(f"server XML block is not unique: {name}")
        spans.append((*xml_span_with_indent(text, matches[0]), name))
    result = text
    for start, end, name in sorted(spans, reverse=True):
        result = result[:start] + f"@@{name}@@\n" + result[end:]
    return result


def xml_signature(node: ET.Element):
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        tuple(xml_signature(child) for child in node),
    )


def repair_map_301_server(client_data: bytes, server_data: bytes) -> bytes:
    image = load_client(client_data, Path(MAP_301_CLIENT).name)
    before = server_data.decode("utf-8")
    after = before
    for name in MAP_301_SERVER_BLOCKS:
        node = image.root.child(name)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"450009301 client map has no {name} block")
        after = replace_direct_xml_block(after, name, arc.property_to_xml(node, 1))
    if masked_xml(before, MAP_301_SERVER_BLOCKS) != masked_xml(
        after, MAP_301_SERVER_BLOCKS
    ):
        raise RuntimeError("450009301 XML changed outside approved blocks")

    server_root = ET.fromstring(after)
    for name in MAP_301_SERVER_BLOCKS:
        actual = next(child for child in server_root if child.get("name") == name)
        expected = ET.fromstring(arc.property_to_xml(image.root.child(name), 0))
        if xml_signature(actual) != xml_signature(expected):
            raise RuntimeError(f"450009301 server block differs from client: {name}")
    return after.encode("utf-8")


def build_npc() -> tuple[bytes, bytes, int]:
    source = arc.SOURCE / f"Npc/{NPC_ID}.img"
    image, materializer = arc.clone_image(source, arc.sanitize_npc)
    data = arc.encode_image_body(image, arc.gms_reader())
    parsed = load_client(data, f"{NPC_ID}.img")
    canvases = 0
    for node in walk(parsed.root):
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases += 1
        if node.child("_outlink") is not None or node.child("_inlink") is not None:
            raise RuntimeError("3003907 retained a Canvas link")
        if (int(node.format), int(node.format2)) != (1, 0):
            raise RuntimeError("3003907 contains a non-ARGB4444 Canvas")
        decoded = decode_canvas(node, region="GMS")
        if decoded.size != (int(node.width), int(node.height)):
            raise RuntimeError("3003907 Canvas decode size mismatch")
    if canvases != materializer.canvases or canvases != 91:
        raise RuntimeError(
            f"3003907 Canvas count changed: {canvases}/{materializer.canvases}"
        )
    return data, arc.image_to_xml(parsed, f"{NPC_ID}.img").encode("utf-8"), canvases


def build_client_npc_string(data: bytes) -> bytes:
    target = load_client(data, Path(NPC_STRING_CLIENT).name)
    existing = target.root.child(str(NPC_ID))
    if existing is not None:
        name = existing.child("name")
        if not isinstance(name, WzStringProperty) or name.value != "墮落勇士":
            raise RuntimeError("existing client NPC string conflicts with TMS")
        return data

    source_path = arc.SOURCE / "String/Npc.img"
    source = arc.load_image(source_path, arc.BMS_KEY)
    node = source.root.get(str(NPC_ID))
    if not isinstance(node, WzSubProperty):
        raise RuntimeError("TMS String/Npc.img has no 3003907 record")
    cloned = arc.clone_property(
        node, None, source, source_path, arc.CanvasMaterializer(), str(NPC_ID)
    )
    result = arc.append_property_record(data, (), cloned)
    arc.verify_raw_record_scope(
        data, result, {(str(NPC_ID),)}, allow_additions=True
    )
    return result


def build_server_npc_string(data: bytes) -> bytes:
    text = data.decode("utf-8")
    root = ET.fromstring(text)
    existing = next((child for child in root if child.get("name") == str(NPC_ID)), None)
    if existing is not None:
        name = next((child for child in existing if child.get("name") == "name"), None)
        if name is None or name.get("value") != "墮落勇士":
            raise RuntimeError("existing server NPC string conflicts with TMS")
        return data

    source = arc.load_image(arc.SOURCE / "String/Npc.img", arc.BMS_KEY)
    node = source.root.get(str(NPC_ID))
    if not isinstance(node, WzSubProperty):
        raise RuntimeError("TMS String/Npc.img has no 3003907 record")
    result = arc.append_xml_properties(text, (), [node])
    ET.fromstring(result)
    return result.encode("utf-8")


def verify_map_990_contract(root: Path, client_data: bytes) -> None:
    image = load_client(client_data, Path(MAP_990_CLIENT).name)
    life = image.root.get("life/0")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("450011990 has no life/0")
    npc_id = arc.child_value(life, "id")
    npc_type = arc.child_value(life, "type")
    if (npc_id, npc_type) != (str(NPC_ID), "n"):
        raise RuntimeError(f"450011990 life contract changed: {npc_id}/{npc_type}")
    server = ET.parse(root / MAP_990_SERVER).getroot()
    server_life = server.find('./imgdir[@name="life"]/imgdir[@name="0"]')
    if server_life is None:
        raise RuntimeError("server 450011990 has no life/0")
    values = {child.get("name"): child.get("value") for child in server_life}
    if (values.get("id"), values.get("type")) != (str(NPC_ID), "n"):
        raise RuntimeError("server 450011990 life contract changed")
    client_life = ET.fromstring(arc.property_to_xml(life, 0))
    if xml_signature(client_life) != xml_signature(server_life):
        raise RuntimeError("450011990 client/server life/0 differs")


def build_outputs(root: Path) -> tuple[dict[str, bytes], int]:
    verify_sources()
    verify_known_states(root)
    before = {
        relative: (root / relative).read_bytes()
        for relative in (
            MAP_301_CLIENT,
            MAP_301_SERVER,
            MAP_990_CLIENT,
            NPC_STRING_CLIENT,
            *NPC_STRING_SERVERS,
        )
    }
    npc_client, npc_server, canvases = build_npc()
    outputs = {
        MAP_301_SERVER: repair_map_301_server(
            before[MAP_301_CLIENT], before[MAP_301_SERVER]
        ),
        MAP_990_CLIENT: repair_map_990(before[MAP_990_CLIENT]),
        NPC_CLIENT: npc_client,
        NPC_SERVER: npc_server,
        NPC_STRING_CLIENT: build_client_npc_string(before[NPC_STRING_CLIENT]),
        NPC_STRING_SERVERS[0]: build_server_npc_string(before[NPC_STRING_SERVERS[0]]),
        NPC_STRING_SERVERS[1]: build_server_npc_string(before[NPC_STRING_SERVERS[1]]),
    }
    verify_map_990_contract(root, outputs[MAP_990_CLIENT])
    return outputs, canvases


def write_outputs(root: Path, outputs: dict[str, bytes], *, no_backup: bool) -> None:
    arc.ROOT = root
    arc.BACKUP_ROOT = Path("/private/tmp/tenebris-crash-map-repair-backup")
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
    print(f"check={args.check} npc={NPC_ID} canvases={canvases}")
    for relative, data in outputs.items():
        print(f"{relative} {sha256_bytes(data)} {len(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
