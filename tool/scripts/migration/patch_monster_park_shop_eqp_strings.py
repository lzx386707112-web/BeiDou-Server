#!/usr/bin/env python3
"""Insert/fix Laku shop equip names from TMS String/Eqp.img without rewriting Eqp.img."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(ROOT / "tool/wz-python"))

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_frenzy_totem_resources as frenzy  # noqa: E402
from wzpy import WzImage, WzSubProperty  # noqa: E402

TMS_EQP = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/String/Eqp.img")
CLIENT_EQP = ROOT / "clien/Data/String/Eqp.img"
SERVER_EQP = (
    ROOT / "gms-server/wz/String.wz/Eqp.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Eqp.img.xml",
)

ACCESSORY_IDS = (
    1152000,
    1152010,
    1152018,
    1152022,
    1152030,
    1152038,
    1152108,
    1152174,
    1152191,
)
WEAPON_IDS = (1342002, 1342004, 1342006, 1342008, 1342011)
ACCESSORY_ANCHOR = "1152212"
WEAPON_ANCHOR = "1342053"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clone_eqp(source: WzImage, folder: str, item_id: int) -> WzSubProperty:
    record = source.root.get(f"Eqp/{folder}/{item_id}")
    if not isinstance(record, WzSubProperty):
        raise RuntimeError(f"TMS Eqp/{folder}/{item_id} missing")
    cloned = arc.clone_property(
        record,
        None,
        source,
        TMS_EQP,
        arc.CanvasMaterializer(),
        str(item_id),
    )
    if not isinstance(cloned, WzSubProperty):
        raise RuntimeError(f"invalid clone Eqp/{folder}/{item_id}")
    return cloned


def insert_missing_client(
    data: bytes,
    parent: tuple[str, ...],
    nodes: list[WzSubProperty],
    anchor: str,
) -> bytes:
    records, _orders = arc.raw_record_state(data)
    missing = [node for node in nodes if (*parent, node.name) not in records]
    if not missing:
        return data
    return arc.insert_property_records_before(data, parent, missing, anchor)


def patch_server_xml(text: str, parent: tuple[str, ...], nodes: list[WzSubProperty], anchor: str) -> str:
    existing = {
        child.get("name")
        for child in __import__("xml.etree.ElementTree", fromlist=["ET"]).fromstring(text).findall(
            "./imgdir[@name='Eqp']/imgdir[@name='%s']/imgdir" % parent[-1]
        )
    }
    updated = text
    to_insert: list[WzSubProperty] = []
    for node in nodes:
        if node.name in existing:
            updated = frenzy.ensure_xml_record(updated, parent, node)
        else:
            to_insert.append(node)
    if to_insert:
        updated = arc.insert_xml_properties_before(updated, parent, to_insert, anchor)
    return updated


def expected_name(node: WzSubProperty) -> str:
    value = arc.child_value(node, "name")
    if not value:
        raise RuntimeError(f"{node.name} has no name")
    return str(value)


def verify_client(data: bytes, accessory: list[WzSubProperty], weapons: list[WzSubProperty]) -> None:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name="Eqp.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"Eqp.img truncated={image.truncated} warnings={image.parse_warnings}")
    for node in accessory:
        got = image.root.get(f"Eqp/Accessory/{node.name}")
        if str(arc.child_value(got, "name")) != expected_name(node):
            raise RuntimeError(f"client Accessory/{node.name} name mismatch")
    for node in weapons:
        got = image.root.get(f"Eqp/Weapon/{node.name}")
        if str(arc.child_value(got, "name")) != expected_name(node):
            raise RuntimeError(f"client Weapon/{node.name} name mismatch")


def main() -> int:
    source = arc.load_image(TMS_EQP, arc.BMS_KEY)
    source.parse()
    accessory = [clone_eqp(source, "Accessory", item_id) for item_id in ACCESSORY_IDS]
    weapons = [clone_eqp(source, "Weapon", item_id) for item_id in WEAPON_IDS]

    original = CLIENT_EQP.read_bytes()
    data = insert_missing_client(original, ("Eqp", "Accessory"), accessory, ACCESSORY_ANCHOR)
    data = insert_missing_client(data, ("Eqp", "Weapon"), weapons, WEAPON_ANCHOR)
    verify_client(data, accessory, weapons)
    if data != original:
        arc.atomic_write_bytes(CLIENT_EQP, data)

    for path in SERVER_EQP:
        original_text = path.read_text(encoding="utf-8")
        updated = patch_server_xml(original_text, ("Eqp", "Accessory"), accessory, ACCESSORY_ANCHOR)
        updated = patch_server_xml(updated, ("Eqp", "Weapon"), weapons, WEAPON_ANCHOR)
        if updated != original_text:
            arc.atomic_write_text(path, updated)

    print("eqp", sha256(CLIENT_EQP.read_bytes()))
    for path in SERVER_EQP:
        print(path.name, sha256(path.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
