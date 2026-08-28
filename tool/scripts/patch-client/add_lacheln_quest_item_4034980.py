#!/usr/bin/env python3
"""Incrementally install the missing Lacheln quest item 4034980."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


ITEM_ID = 4034980
ITEM_NAME = f"0{ITEM_ID}"
CLIENT_ITEM = ROOT / "clien/Data/Item/Etc/0403.img"
CLIENT_STRING = ROOT / "clien/Data/String/Etc.img"
SERVER_ITEM = ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml"
SERVER_STRINGS = (
    ROOT / "gms-server/wz/String.wz/Etc.img.xml",
    ROOT / "gms-server/wz-zh-CN/String.wz/Etc.img.xml",
)


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


def build_nodes() -> tuple[WzSubProperty, WzSubProperty]:
    item_source_path = SOURCE / "Item/Etc/0403.img"
    string_source_path = SOURCE / "String/Etc.img"
    item_source = arc.load_image(item_source_path, arc.BMS_KEY)
    string_source = arc.load_image(string_source_path, arc.BMS_KEY)
    source_item = item_source.root.get(ITEM_NAME)
    source_string = string_source.root.get(f"Etc/{ITEM_ID}")
    if not isinstance(source_item, WzSubProperty) or not isinstance(
        source_string, WzSubProperty
    ):
        raise RuntimeError(f"TMS quest item resource is missing: {ITEM_ID}")

    item_node = arc.clone_property(
        source_item,
        None,
        item_source,
        item_source_path,
        arc.CanvasMaterializer(),
        ITEM_NAME,
    )
    string_node = arc.clone_property(
        source_string,
        None,
        string_source,
        string_source_path,
        arc.CanvasMaterializer(),
        str(ITEM_ID),
    )
    validate_item_node(item_node)
    return item_node, string_node


def validate_item_node(item_node: WzSubProperty) -> None:
    for canvas_name, dimensions in (("icon", (33, 31)), ("iconRaw", (33, 30))):
        canvas = item_node.get(f"info/{canvas_name}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing item Canvas: {ITEM_ID}/{canvas_name}")
        if (canvas.format, canvas.format2) != (1, 0):
            raise RuntimeError(f"incompatible item Canvas: {ITEM_ID}/{canvas_name}")
        if (canvas.width, canvas.height) != dimensions:
            raise RuntimeError(f"unexpected item dimensions: {ITEM_ID}/{canvas_name}")
        bitmap = decode_canvas(canvas, region="GMS")
        if not bitmap.getbbox():
            raise RuntimeError(f"empty item Canvas: {ITEM_ID}/{canvas_name}")


def build_expected() -> dict[Path, tuple[bytes, bytes]]:
    item_node, string_node = build_nodes()
    output: dict[Path, tuple[bytes, bytes]] = {}

    item_baseline = git_baseline(CLIENT_ITEM)
    item_result = arc.insert_property_record_before(
        item_baseline, (), item_node, "04034981"
    )
    arc.verify_raw_record_insert_scope(
        item_baseline, item_result, {(ITEM_NAME,)}
    )
    output[CLIENT_ITEM] = (item_baseline, item_result)

    string_baseline = git_baseline(CLIENT_STRING)
    string_result = arc.insert_property_record_before(
        string_baseline, ("Etc",), string_node, "4034981"
    )
    arc.verify_raw_record_insert_scope(
        string_baseline, string_result, {("Etc", str(ITEM_ID))}
    )
    output[CLIENT_STRING] = (string_baseline, string_result)

    for path, parent_path, node, anchor in (
        (SERVER_ITEM, (), item_node, "04034981"),
        *((path, ("Etc",), string_node, "4034981") for path in SERVER_STRINGS),
    ):
        baseline = git_baseline(path)
        result = arc.insert_xml_properties_before(
            baseline.decode("utf-8"), parent_path, [node], anchor
        ).encode("utf-8")
        output[path] = (baseline, result)
    validate_expected(output)
    return output


def validate_expected(expected: dict[Path, tuple[bytes, bytes]]) -> None:
    item = WzImage.from_bytes(
        expected[CLIENT_ITEM][1], key=arc.GMS_KEY, name=CLIENT_ITEM.name
    )
    string = WzImage.from_bytes(
        expected[CLIENT_STRING][1], key=arc.GMS_KEY, name=CLIENT_STRING.name
    )
    for image in (item, string):
        image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"generated IMG failed validation: {image.name}")
    item_node = item.root.get(ITEM_NAME)
    string_node = string.root.get(f"Etc/{ITEM_ID}")
    if not isinstance(item_node, WzSubProperty) or not isinstance(
        string_node, WzSubProperty
    ):
        raise RuntimeError(f"generated item contract is incomplete: {ITEM_ID}")
    validate_item_node(item_node)
    if string_node.get("name").value != "華麗面具材料":
        raise RuntimeError(f"unexpected item name: {ITEM_ID}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    expected = build_expected()
    changed: list[Path] = []
    for path, (baseline, result) in expected.items():
        current = path.read_bytes()
        if current not in (baseline, result):
            raise RuntimeError(f"refusing unknown item resource state: {path}")
        if current == result:
            continue
        if args.check:
            raise SystemExit(f"{path} needs item {ITEM_ID}")
        arc.atomic_write_bytes(path, result)
        changed.append(path)

    print(f"Lacheln item {ITEM_ID} ok: changed={len(changed)}")
    for path, (_baseline, result) in expected.items():
        print(f"{path.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
