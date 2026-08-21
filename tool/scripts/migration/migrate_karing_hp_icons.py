#!/usr/bin/env python3
"""Incrementally add the five Karing boss gauge icons to UIWindow.img."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_CANVAS = Path(
    "/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/UI/_Canvas/UIWindow2.img"
)
CLIENT_UI = ROOT / "clien/Data/UI/UIWindow.img"
ICON_IDS = ("8880830", "8880831", "8880832", "8880837", "8880842")
TARGET_PARENT = ("MobGage", "Mob")

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402

import migrate_karing_p1_maps as p1  # noqa: E402
from migrate_karing_later_stages import insert_raw_record  # noqa: E402


def build_icon(source: WzImage, mob_id: str) -> WzCanvasProperty:
    source_node = source.root.get(f"MobGage/Mob/{mob_id}")
    if not isinstance(source_node, WzCanvasProperty) or not source_node.has_pixels():
        raise RuntimeError(f"{SOURCE_CANVAS}: missing visible icon {mob_id}")

    holder = WzSubProperty("Mob")
    materializer = p1.CanvasMaterializer()
    icon = p1.clone_property(
        source_node,
        holder,
        source,
        SOURCE_CANVAS,
        materializer,
        mob_id,
    )
    if not isinstance(icon, WzCanvasProperty):
        raise RuntimeError(f"{mob_id}: cloned icon is not a Canvas")
    holder.add(icon)
    p1.remove_child(icon, "_inlink")
    p1.remove_child(icon, "_outlink")
    p1.remove_child(icon, "delay")
    p1.remove_child(icon, "origin")
    icon.add(WzIntProperty("delay", 500, icon))
    icon.add(WzVectorProperty("origin", 0, 0, icon))
    return icon


def verify_icons() -> None:
    image = WzImage.from_bytes(
        CLIENT_UI.read_bytes(), key=p1.GMS_KEY, name=CLIENT_UI.name
    )
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{CLIENT_UI}: malformed result {image.parse_warnings}")

    for mob_id in ICON_IDS:
        icon = image.root.get(f"{'/'.join(TARGET_PARENT)}/{mob_id}")
        if not isinstance(icon, WzCanvasProperty):
            raise RuntimeError(f"{mob_id}: boss gauge icon is not a Canvas")
        if (icon.width, icon.height, icon.format, icon.format2) != (25, 25, 1, 0):
            raise RuntimeError(
                f"{mob_id}: unexpected Canvas contract "
                f"{icon.width}x{icon.height} format={icon.format}/{icon.format2}"
            )
        if icon.child("_inlink") is not None or icon.child("_outlink") is not None:
            raise RuntimeError(f"{mob_id}: legacy icon still contains a Canvas link")
        delay = icon.child("delay")
        origin = icon.child("origin")
        if getattr(delay, "value", None) != 500:
            raise RuntimeError(f"{mob_id}: missing legacy delay=500")
        if not isinstance(origin, WzVectorProperty) or (origin.x, origin.y) != (0, 0):
            raise RuntimeError(f"{mob_id}: missing legacy origin=(0,0)")
        if decode_canvas(icon, region="GMS").getbbox() is None:
            raise RuntimeError(f"{mob_id}: boss gauge icon is transparent")


def main() -> None:
    source = p1.load_image(SOURCE_CANVAS, p1.BMS_KEY)
    if source.truncated or source.parse_warnings:
        raise RuntimeError(f"{SOURCE_CANVAS}: malformed source {source.parse_warnings}")

    inserted = 0
    for mob_id in ICON_IDS:
        inserted += int(insert_raw_record(CLIENT_UI, TARGET_PARENT, build_icon(source, mob_id)))
    verify_icons()
    payload = CLIENT_UI.read_bytes()
    print(
        f"Karing boss gauge icons ready: inserted={inserted} "
        f"bytes={len(payload)} sha256={hashlib.sha256(payload).hexdigest()}"
    )


if __name__ == "__main__":
    main()
