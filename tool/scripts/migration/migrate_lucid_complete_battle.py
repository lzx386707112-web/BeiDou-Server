#!/usr/bin/env python3
"""Install legacy-safe Lucid summon resources used by LucidBossCompat."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ARC_SCRIPT = Path(__file__).with_name("migrate_arcane_river_expansion.py")
SPEC = importlib.util.spec_from_file_location("arcane_river_expansion", ARC_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {ARC_SCRIPT}")
arc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arc)


MUSHROOM_ID = 8880164
MUSHROOM_NAME = "噩梦毒蘑菇"
SOURCE_MOB = Path(
    "/Users/lizixian/Library/Caches/BeiDouMapMobWorkbench/"
    "ms/Mob_00000/Mob_8880164.img"
)
SOURCE_CANVAS = arc.SOURCE / "Mob/_Canvas/8880157.img"
SOURCE_SHA256 = {
    SOURCE_MOB: "4cfb0f0c378aaa5be005f3ba58b07f40a3eb866ee8b484b018f97fdeb93df9b3",
    SOURCE_CANVAS: "e1e9b6fef2ca41dbcdef52f9614e0e36717b586e7924ee30aacb29a516af4d0e",
}
CLIENT_MOB = ROOT / f"clien/Data/Mob/{MUSHROOM_ID}.img"
SERVER_MOB = ROOT / f"gms-server/wz/Mob.wz/{MUSHROOM_ID}.img.xml"
CLIENT_STRING = ROOT / "clien/Data/String/Mob.img"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Mob.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources() -> None:
    for path, expected in SOURCE_SHA256.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Lucid source changed: {path} {actual}")


def mushroom_string_record() -> arc.WzSubProperty:
    record = arc.WzSubProperty(str(MUSHROOM_ID))
    record.add(arc.WzStringProperty("name", MUSHROOM_NAME, record))
    return record


def generated_mushroom() -> tuple[bytes, str, int]:
    image, materializer = arc.clone_image(
        SOURCE_MOB,
        lambda root: arc.sanitize_mob(root, MUSHROOM_ID),
    )
    data = arc.encode_image_body(image, arc.gms_reader())
    arc.verified_image_bytes(data, CLIENT_MOB.name)
    xml = arc.image_to_xml(image, CLIENT_MOB.name)
    ET.fromstring(xml)
    return data, xml, materializer.canvases


def install_mob(data: bytes, xml: str) -> None:
    if CLIENT_MOB.exists() and CLIENT_MOB.read_bytes() != data:
        raise RuntimeError(f"existing Lucid mushroom differs: {CLIENT_MOB}")
    if SERVER_MOB.exists() and SERVER_MOB.read_text(encoding="utf-8") != xml:
        raise RuntimeError(f"existing Lucid mushroom XML differs: {SERVER_MOB}")
    if not CLIENT_MOB.exists():
        arc.atomic_write_bytes(CLIENT_MOB, data)
    if not SERVER_MOB.exists():
        arc.atomic_write_text(SERVER_MOB, xml)


def install_client_string() -> None:
    original = CLIENT_STRING.read_bytes()
    image = arc.load_image(CLIENT_STRING, arc.GMS_KEY)
    existing = image.root.get(f"{MUSHROOM_ID}/name")
    if existing is not None:
        if existing.value != MUSHROOM_NAME:
            raise RuntimeError(f"unexpected existing String/Mob name for {MUSHROOM_ID}")
        return
    record = mushroom_string_record()
    updated = arc.append_property_record(original, (), record)
    arc.verify_raw_record_insert_scope(original, updated, {(str(MUSHROOM_ID),)})
    arc.atomic_write_bytes(CLIENT_STRING, updated)


def install_server_strings() -> None:
    for path in SERVER_STRINGS:
        original = path.read_text(encoding="utf-8")
        root = ET.fromstring(original)
        record = root.find(f'./imgdir[@name="{MUSHROOM_ID}"]')
        if record is not None:
            name = record.find('./string[@name="name"]')
            if name is None or name.get("value") != MUSHROOM_NAME:
                raise RuntimeError(f"unexpected existing server String/Mob: {path}")
            continue
        updated = arc.append_xml_properties(original, (), [mushroom_string_record()])
        ET.fromstring(updated)
        arc.atomic_write_text(path, updated)


def verify_installed(expected_data: bytes, expected_xml: str, expected_canvases: int) -> None:
    if CLIENT_MOB.read_bytes() != expected_data:
        raise RuntimeError("Lucid mushroom client bytes are not deterministic")
    if SERVER_MOB.read_text(encoding="utf-8") != expected_xml:
        raise RuntimeError("Lucid mushroom server XML is not deterministic")
    image = arc.load_image(CLIENT_MOB, arc.GMS_KEY)
    if image.truncated or image.parse_warnings:
        raise RuntimeError("Lucid mushroom IMG did not parse cleanly")
    canvases = []
    visible = 0
    for node, path in arc.walk(image.root):
        if not isinstance(node, arc.WzCanvasProperty):
            continue
        canvases.append(path)
        if (int(node.format), int(node.format2)) != (1, 0):
            raise RuntimeError(f"non-ARGB4444 Lucid mushroom Canvas: {path}")
        decoded = arc.decode_canvas(node, region="GMS").convert("RGBA")
        if decoded.getbbox() is not None:
            visible += 1
        decoded.close()
    if len(canvases) != expected_canvases or visible == 0:
        raise RuntimeError(
            f"Lucid mushroom Canvas mismatch: total={len(canvases)} "
            f"expected={expected_canvases} visible={visible}"
        )
    for root_name in ("info", "regen", "stand", "move", "hit1", "die1"):
        if image.root.child(root_name) is None:
            raise RuntimeError(f"Lucid mushroom missing root: {root_name}")
    if image.root.get("info/skill") is not None:
        raise RuntimeError("modern mushroom MobSkill contract was not removed")
    name = arc.load_image(CLIENT_STRING, arc.GMS_KEY).root.get(f"{MUSHROOM_ID}/name")
    if name is None or name.value != MUSHROOM_NAME:
        raise RuntimeError("Lucid mushroom client string is missing")
    for path in SERVER_STRINGS:
        root = ET.parse(path).getroot()
        name = root.find(
            f'./imgdir[@name="{MUSHROOM_ID}"]/string[@name="name"]'
        )
        if name is None or name.get("value") != MUSHROOM_NAME:
            raise RuntimeError(f"Lucid mushroom server string is missing: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    verify_sources()
    data, xml, canvases = generated_mushroom()
    if not args.verify_only:
        install_mob(data, xml)
        install_client_string()
        install_server_strings()
    verify_installed(data, xml, canvases)
    print(
        f"Lucid complete battle resources ok: mushroom={MUSHROOM_ID} "
        f"canvas={canvases} client_sha256={sha256(CLIENT_MOB)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
