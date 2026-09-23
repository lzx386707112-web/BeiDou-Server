#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

spec = importlib.util.spec_from_file_location(
    "enma_migration",
    ROOT / "tool/scripts/migration/add_enma_face_accessory.py",
)
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = migration
spec.loader.exec_module(migration)

from wzpy import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def child_value(node, name):
    child = node.child(name)
    return getattr(child, "value", None)


def canvas_pixels(image, region: str) -> dict[str, tuple[tuple[int, int], str]]:
    result = {}

    def visit(node, parent=""):
        for child in node.children():
            path = f"{parent}/{child.name}" if parent else child.name
            if isinstance(child, WzCanvasProperty):
                bitmap = decode_canvas(child, region=region).convert("RGBA")
                assert bitmap.getbbox() is not None
                result[path] = (
                    bitmap.size,
                    hashlib.sha256(bitmap.tobytes()).hexdigest(),
                )
            if hasattr(child, "children"):
                visit(child, path)

    visit(image.root)
    return result


def assert_client_equipment() -> None:
    assert migration.sha256(migration.LEGACY_BASELINE.read_bytes()) == (
        migration.LEGACY_BASELINE_SHA256
    )
    source = migration.load_image(
        migration.SOURCE_ATTACHMENT.read_bytes(), region="EMS", name=migration.SOURCE_NAME
    )
    target = migration.load_image(
        migration.CLIENT_TARGET.read_bytes(), region="GMS", name=migration.TARGET_NAME
    )
    source_pixels = canvas_pixels(source, "EMS")
    target_pixels = canvas_pixels(target, "GMS")
    assert source_pixels.keys() == target_pixels.keys()
    assert len(target_pixels) == 21
    for path in source_pixels.keys() - {"info/icon", "info/iconRaw"}:
        assert source_pixels[path] == target_pixels[path]

    info = target.root.child("info")
    assert isinstance(info, WzSubProperty)
    for name, value in migration.STATS.items():
        assert child_value(info, name) == value
    for icon_name in ("icon", "iconRaw"):
        icon = info.child(icon_name)
        assert isinstance(icon, WzCanvasProperty)
        assert (icon.format, icon.format2) == (1, 0)
        source_icon = source.root.get(f"info/{icon_name}")
        source_bitmap = decode_canvas(source_icon, region="EMS").convert("RGBA")
        target_bitmap = decode_canvas(icon, region="GMS").convert("RGBA")
        expected = bytes((channel >> 4) * 17 for channel in source_bitmap.tobytes())
        assert target_bitmap.tobytes() == expected


def assert_client_string() -> None:
    strings = migration.load_image(
        migration.CLIENT_STRING.read_bytes(), region="GMS", name=migration.CLIENT_STRING.name
    )
    record = strings.root.get(
        "/".join((*migration.STRING_PARENT, str(migration.TARGET_ID)))
    )
    assert isinstance(record, WzSubProperty)
    assert child_value(record, "name") == migration.ITEM_NAME
    assert child_value(record, "desc") == migration.ITEM_DESC


def assert_server_contract() -> None:
    equipment = ET.parse(migration.SERVER_TARGET).getroot()
    assert equipment.get("name") == migration.TARGET_NAME
    info = equipment.find('./imgdir[@name="info"]')
    assert info is not None
    for name, value in migration.STATS.items():
        node = info.find(f'./int[@name="{name}"]')
        assert node is not None and node.get("value") == str(value)
    for icon_name in ("icon", "iconRaw"):
        icon = info.find(f'./canvas[@name="{icon_name}"]')
        assert icon is not None and icon.get("format") == "1"

    for path in migration.SERVER_STRINGS:
        root = ET.parse(path).getroot()
        record = root.find(
            f'./imgdir[@name="Eqp"]/imgdir[@name="Accessory"]/'
            f'imgdir[@name="{migration.TARGET_ID}"]'
        )
        assert record is not None
        values = {child.get("name"): child.get("value") for child in record}
        assert values == {"desc": migration.ITEM_DESC, "name": migration.ITEM_NAME}


assert_client_equipment()
assert_client_string()
assert_server_contract()
print("Enma face accessory resource contract checks passed")
