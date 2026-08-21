#!/usr/bin/env python3
"""Expose the existing legacy-compatible Genesis weapons as Eternal-set items."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402

import migrate_destiny_eternal_equipment as equipment  # noqa: E402


GENESIS_BY_SET = {
    886: (1302355, 1312213, 1322264, 1402268, 1412189, 1422197, 1432227, 1442285),
    887: (1372237, 1382274),
    888: (1452266, 1462252),
    889: (1332289, 1472275),
    890: (1482232, 1492245),
}
REQ_JOB_BY_SET = {886: 1, 887: 2, 888: 4, 889: 8, 890: 16}
ITEM_SPECS = tuple(
    equipment.ItemSpec(item_id, "Weapon", REQ_JOB_BY_SET[set_id], 8, True, 200)
    for set_id, item_ids in GENESIS_BY_SET.items()
    for item_id in item_ids
)
REQUIRED_SCALARS = (
    "reqLevel", "reqJob", "tuc", "incSTR", "incDEX", "incINT", "incLUK",
    "incPAD", "incMAD", "incPDD", "incMDD", "attackSpeed",
)
ITEM_DESCRIPTION = "创世武器，可参与对应职业的永恒套装效果。"


def source_contract() -> tuple[int, ...]:
    set_info = equipment.load_image(
        equipment.TMS_DATA / "Etc/SetItemInfo.img", equipment.BMS_KEY
    )
    found = []
    for set_id, expected_ids in GENESIS_BY_SET.items():
        node = set_info.root.child(str(set_id))
        item_root = node.child("ItemID") if isinstance(node, WzSubProperty) else None
        if not isinstance(item_root, WzSubProperty):
            raise RuntimeError(f"TMS Eternal set {set_id} has no ItemID contract")
        source_ids = {int(child.value) for child in item_root.children()}
        missing = set(expected_ids) - source_ids
        if missing:
            raise RuntimeError(f"TMS Eternal set {set_id} is missing Genesis IDs {missing}")
        for item_id in expected_ids:
            spec = next(spec for spec in ITEM_SPECS if spec.item_id == item_id)
            source = equipment.load_image(spec.source_path, equipment.BMS_KEY)
            info = source.root.child("info")
            if not isinstance(info, WzSubProperty):
                raise RuntimeError(f"{spec.source_path}: missing info")
            if equipment.int_value(info, "setItemID") != set_id:
                raise RuntimeError(f"{item_id}: unexpected TMS setItemID")
            if equipment.int_value(info, "jokerToSetItem") != 1:
                raise RuntimeError(f"{item_id}: not a TMS Eternal lucky weapon")
            found.append(item_id)
    return tuple(found)


def source_strings() -> dict[equipment.ItemSpec, tuple[tuple[str, str], ...]]:
    source = equipment.load_image(equipment.SOURCE_STRING, equipment.BMS_KEY)
    result = {}
    for spec in ITEM_SPECS:
        node = source.root.get(f"Eqp/Weapon/{spec.item_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing source string for {spec.item_id}")
        values = tuple(
            (child.name, str(child.value))
            for child in node.children()
            if isinstance(child, WzStringProperty)
        )
        names = [value for name, value in values if name == "name"]
        if len(names) != 1 or not names[0].startswith("創世"):
            raise RuntimeError(f"unexpected Genesis name for {spec.item_id}: {names}")
        result[spec] = equipment.complete_string_values(values, ITEM_DESCRIPTION)
    return result


def verify_items() -> None:
    for spec in ITEM_SPECS:
        source = equipment.load_image(spec.source_path, equipment.BMS_KEY)
        client = equipment.load_image(spec.client_path, equipment.GMS_KEY)
        source_info = source.root.child("info")
        client_info = client.root.child("info")
        if not isinstance(source_info, WzSubProperty) or not isinstance(client_info, WzSubProperty):
            raise RuntimeError(f"{spec.item_id}: missing info")
        for field in REQUIRED_SCALARS:
            expected = getattr(source_info.child(field), "value", None)
            actual = getattr(client_info.child(field), "value", None)
            if actual != expected:
                raise RuntimeError(f"{spec.item_id}: {field} mismatch {actual} != {expected}")
        for icon_name in ("icon", "iconRaw"):
            icon = client_info.child(icon_name)
            if not isinstance(icon, WzCanvasProperty):
                raise RuntimeError(f"{spec.item_id}: missing {icon_name}")
            if decode_canvas(icon, region="GMS").convert("RGBA").getbbox() is None:
                raise RuntimeError(f"{spec.item_id}: transparent {icon_name}")

        server_root = ET.parse(spec.server_path).getroot()
        server_info = equipment.direct_child(server_root, "info")
        if server_info is None:
            raise RuntimeError(f"{spec.server_path}: missing info")
        server_values = {child.get("name"): child.get("value") for child in server_info}
        for field in REQUIRED_SCALARS:
            expected = getattr(client_info.child(field), "value", None)
            actual = server_values.get(field)
            if (None if actual is None else str(actual)) != (None if expected is None else str(expected)):
                raise RuntimeError(f"{spec.item_id}: server {field} mismatch")


def verify() -> None:
    source_contract()
    names = source_strings()
    verify_items()
    equipment.verify_strings(names)


def apply() -> None:
    source_contract()
    names = source_strings()
    verify_items()
    client_records, server_records, backup = equipment.apply_string_records_incrementally(
        names
    )
    verify()
    print(
        f"items={len(ITEM_SPECS)} clientStrings={client_records} "
        f"serverStrings={server_records} backup={backup}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply()
    elif args.verify:
        verify()
        print("verification passed: Genesis weapons=16 Eternal sets=5")
    else:
        source_contract()
        source_strings()
        verify_items()
        print("dry-run passed: Genesis weapons=16 Eternal sets=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
