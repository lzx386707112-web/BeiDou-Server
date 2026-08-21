#!/usr/bin/env python3
"""Incrementally migrate the five-piece TMS Endless Radiance boss set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

import migrate_destiny_eternal_equipment as equipment  # noqa: E402


SET_ID = 1055
SOURCE_SET_NAME = "光輝Boss套裝"
ITEM_SPECS = (
    equipment.ItemSpec(1113341, "Ring", 0, 4, target_level=220),
    equipment.ItemSpec(1122447, "Accessory", 0, 7, target_level=220),
    equipment.ItemSpec(1143471, "Accessory", 0, 0, target_level=220),
    equipment.ItemSpec(1113360, "Ring", 0, 4, target_level=220),
    equipment.ItemSpec(1012911, "Accessory", 0, 7, target_level=220),
)
EXPECTED_NAMES = {
    1113341: "根源的耳語",
    1122447: "死亡之誓",
    1143471: "不朽的遺產",
    1113360: "恍惚的惡夢",
    1012911: "傲慢的原罪",
}
EXPECTED_CANVASES = 11
EXPECTED_OUTLINKS = 11
ITEM_DESCRIPTION = "无尽辉耀套装装备，集齐套装部件可激活套装属性。"


def source_set_contract() -> tuple[int, ...]:
    source = equipment.load_image(
        equipment.TMS_DATA / "Etc/SetItemInfo.img", equipment.BMS_KEY
    )
    node = source.root.child(str(SET_ID))
    name = node.child("setItemName") if isinstance(node, WzSubProperty) else None
    item_root = node.child("ItemID") if isinstance(node, WzSubProperty) else None
    if not isinstance(name, WzStringProperty) or str(name.value) != SOURCE_SET_NAME:
        raise RuntimeError(f"unexpected TMS set {SET_ID} name")
    if not isinstance(item_root, WzSubProperty):
        raise RuntimeError(f"TMS set {SET_ID} has no ItemID contract")
    item_ids = tuple(int(child.value) for child in item_root.children())
    expected = tuple(spec.item_id for spec in ITEM_SPECS)
    if item_ids != expected:
        raise RuntimeError(f"TMS set {SET_ID} items changed: {item_ids}")
    return item_ids


def source_strings() -> dict[equipment.ItemSpec, tuple[tuple[str, str], ...]]:
    source = equipment.load_image(equipment.SOURCE_STRING, equipment.BMS_KEY)
    result = {}
    for spec in ITEM_SPECS:
        node = source.root.get(f"Eqp/{spec.category}/{spec.item_id}")
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing source string for {spec.item_id}")
        values = tuple(
            (child.name, str(child.value))
            for child in node.children()
            if isinstance(child, WzStringProperty)
        )
        names = [value for name, value in values if name == "name"]
        if names != [EXPECTED_NAMES[spec.item_id]]:
            raise RuntimeError(f"unexpected source name for {spec.item_id}: {names}")
        result[spec] = equipment.complete_string_values(values, ITEM_DESCRIPTION)
    return result


def build_items():
    materializer = equipment.CanvasMaterializer()
    outputs = {}
    for spec in ITEM_SPECS:
        source = equipment.load_image(spec.source_path, equipment.BMS_KEY)
        root = WzSubProperty(source.root.name)
        for child in source.root.children():
            root.add(equipment.clone_property(child, root, materializer))
        equipment.patch_info(root, spec)
        image = WzImage.from_bytes(b"", key=equipment.GMS_KEY, name=spec.file_name)
        image._root = root
        image._parsed = True
        outputs[spec] = (
            encode_image_body(image, equipment.gms_reader()),
            equipment.image_xml(spec.file_name, root),
        )
    if materializer.canvases != EXPECTED_CANVASES:
        raise RuntimeError(
            f"expected {EXPECTED_CANVASES} canvases, got {materializer.canvases}"
        )
    if materializer.outlinks != EXPECTED_OUTLINKS:
        raise RuntimeError(
            f"expected {EXPECTED_OUTLINKS} outlinks, got {materializer.outlinks}"
        )
    return outputs, materializer


def verify(names) -> None:
    source_set_contract()
    total_canvases = 0
    for spec in ITEM_SPECS:
        canvases, _ = equipment.verify_item(spec)
        total_canvases += canvases
        image = equipment.load_image(spec.client_path, equipment.GMS_KEY)
        icon = image.root.get("info/icon")
        icon_raw = image.root.get("info/iconRaw")
        for canvas in (icon, icon_raw):
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"{spec.item_id}: missing item icon")
            if decode_canvas(canvas, region="GMS").convert("RGBA").getbbox() is None:
                raise RuntimeError(f"{spec.item_id}: transparent item icon")
    if total_canvases != EXPECTED_CANVASES:
        raise RuntimeError(f"written Canvas count mismatch: {total_canvases}")
    equipment.verify_strings(names)


def apply() -> None:
    source_set_contract()
    names = source_strings()
    outputs, materializer = build_items()
    touched = [equipment.CLIENT_STRING, *equipment.SERVER_STRINGS]
    touched += [spec.client_path for spec in ITEM_SPECS]
    touched += [spec.server_path for spec in ITEM_SPECS]
    backup = equipment.backup_paths(touched)
    for spec, (client_data, server_data) in outputs.items():
        equipment.atomic_write(spec.client_path, client_data)
        equipment.atomic_write(spec.server_path, server_data)

    client_records = equipment.upsert_client_string_records(names)
    server_records = sum(
        equipment.upsert_server_string_records(path, names)
        for path in equipment.SERVER_STRINGS
    )
    verify(names)
    print(
        f"items={len(outputs)} canvases={materializer.canvases} "
        f"outlinks={materializer.outlinks} clientStrings={client_records} "
        f"serverStrings={server_records} backup={backup}"
    )


def apply_strings() -> None:
    names = source_strings()
    client_records, server_records, backup = (
        equipment.apply_string_records_incrementally(names)
    )
    print(
        f"strings={len(names)} clientStrings={client_records} "
        f"serverStrings={server_records} backup={backup}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--apply-strings", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply()
        return 0
    if args.apply_strings:
        apply_strings()
        return 0
    if args.verify:
        verify(source_strings())
        print("verification passed: set=1055 items=5 canvases=11")
        return 0
    outputs, materializer = build_items()
    source_set_contract()
    source_strings()
    print(
        f"dry-run: items={len(outputs)} canvases={materializer.canvases} "
        f"outlinks={materializer.outlinks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
