#!/usr/bin/env python3
"""Contract: Monster Park commemorative coin and Laku shop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))
sys.path.insert(0, str(ROOT / "tool/wz-python"))

import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

ITEM_ID = 4310020
ITEM_NODE = f"0{ITEM_ID}"
ITEM_NAME = "怪物公园纪念币"
ITEM_DESC = "祝賀拜訪怪物公園的紀念貨幣，拿給怪物公園的休菲凱曼就可以交換成特別的道具。"


def load(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path.name}: truncated={image.truncated} warnings={image.parse_warnings}")
    return image


def main() -> int:
    errors: list[str] = []
    item = load(ROOT / "clien/Data/Item/Etc/0431.img")
    record = item.root.child(ITEM_NODE)
    if not isinstance(record, WzSubProperty):
        errors.append("client Etc/0431.img missing 04310020")
    else:
        for canvas_name in ("icon", "iconRaw"):
            canvas = record.get(f"info/{canvas_name}")
            if not isinstance(canvas, WzCanvasProperty):
                errors.append(f"missing {canvas_name}")
                continue
            if (int(canvas.format), int(canvas.format2 or 0)) != (1, 0):
                errors.append(f"{canvas_name} is not format=1/0")
            decoded = decode_canvas(canvas, region="GMS")
            if decoded.getbbox() is None:
                errors.append(f"{canvas_name} has no visible pixels")
    strings = load(ROOT / "clien/Data/String/Etc.img")
    text = strings.root.get(f"Etc/{ITEM_ID}")
    if not isinstance(text, WzSubProperty):
        errors.append("client String/Etc.img missing 4310020")
    else:
        if str(arc.child_value(text, "name")) != ITEM_NAME:
            errors.append("coin name mismatch")
        if str(arc.child_value(text, "desc")) != ITEM_DESC:
            errors.append("coin desc mismatch")
    xml_item = (ROOT / "gms-server/wz/Item.wz/Etc/0431.img.xml").read_text(encoding="utf-8")
    if ITEM_NODE not in xml_item:
        errors.append("server Item XML missing 04310020")
    for tree in ("wz", "wz-zh-CN"):
        xml = (ROOT / f"gms-server/{tree}/String.wz/Etc.img.xml").read_text(encoding="utf-8")
        if f'<imgdir name="{ITEM_ID}">' not in xml or ITEM_NAME not in xml:
            errors.append(f"{tree} String XML missing coin")
    shop = (ROOT / "gms-server/scripts/npc/9071001.js").read_text(encoding="utf-8")
    for token in ("4310020", "2000002", "4007000", "1152000", "1672000", "1190000", "1182000", "1342119"):
        if token not in shop:
            errors.append(f"9071001 is missing shop item {token}")
    alias = (ROOT / "gms-server/scripts/npc/mParkShop.js").read_text(encoding="utf-8")
    if "4007000" not in alias or "1152108" not in alias:
        errors.append("mParkShop alias is out of date")
    final = (ROOT / "gms-server/scripts/portal/mPark_final.js").read_text(encoding="utf-8")
    if "MPARK_BASIC" not in final or "return 20" not in final:
        errors.append("mPark_final is missing per-door coin rewards")
    extreme = (ROOT / "gms-server/scripts/portal/Extreme_out.js").read_text(encoding="utf-8")
    if "gainItem(4310020, 50)" not in extreme:
        errors.append("Extreme_out is missing the 50-coin reward")
    eqp = load(ROOT / "clien/Data/String/Eqp.img")
    tiger = eqp.root.get("Eqp/Accessory/1152000")
    if not isinstance(tiger, WzSubProperty) or str(arc.child_value(tiger, "name")) != "虎爪":
        errors.append("client Eqp.img missing TMS 1152000 虎爪")
    blade = eqp.root.get("Eqp/Weapon/1342002")
    if not isinstance(blade, WzSubProperty) or str(arc.child_value(blade, "name")) != "倚天刀":
        errors.append("client Eqp.img missing TMS 1342002 倚天刀")
    if "[4007000, 90]" not in shop:
        errors.append("9071001 cube prices were not tripled")
    welcome = (ROOT / "gms-server/scripts/npc/9071000.js").read_text(encoding="utf-8")
    if "DAILY_LIMIT = 2" not in welcome:
        errors.append("9071000 is not limited to 2 entries per region")
    event = (ROOT / "gms-server/scripts/event/MonsterPark.js").read_text(encoding="utf-8")
    if "parkRegion" not in event:
        errors.append("MonsterPark event does not store parkRegion")
    if errors:
        print("FAIL")
        for item_error in errors:
            print(item_error)
        return 1
    print("monster park coin contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
