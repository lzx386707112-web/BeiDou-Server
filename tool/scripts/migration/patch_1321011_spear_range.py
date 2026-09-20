#!/usr/bin/env python3
"""Project 1321011 hit box onto TMS 400011004 forward spear travel, not a two-sided screen."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from migrate_arcane_river_expansion import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    raw_record_state,
)
from wzpy.crypto import WzKey  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.wz_image import WzImage  # noqa: E402

CLIENT_132 = ROOT / "clien" / "Data" / "Skill" / "132.img"
SERVER_XML = ROOT / "gms-server" / "wz" / "Skill.wz" / "132.img.xml"
# TMS 400011004 shootobj p2 travels x=-1000; bodyWH height 220.
LT = (-1000, -110)
RB = (40, 110)


def clone_tree(source, parent=None):
    if isinstance(source, WzVectorProperty):
        if source.name == "lt":
            return WzVectorProperty(source.name, LT[0], LT[1], parent)
        if source.name == "rb":
            return WzVectorProperty(source.name, RB[0], RB[1], parent)
        return WzVectorProperty(source.name, int(source.x), int(source.y), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(source.name, int(source.value), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(source.name, str(source.value), parent)
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(source.name, parent)
        for child in source.children():
            output.add(clone_tree(child, output))
        return output
    raise TypeError(type(source))


def verify_scope(before: bytes, after: bytes) -> None:
    before_records, before_orders = raw_record_state(before)
    after_records, after_orders = raw_record_state(after)
    root = ("skill", "1321011", "level")
    if before_orders[("skill",)] != after_orders[("skill",)]:
        raise SystemExit("skill sibling order changed")
    if before_orders[("skill", "1321011")] != after_orders[("skill", "1321011")]:
        raise SystemExit("1321011 sibling order changed")
    for path, raw in before_records.items():
        affected = path[: len(root)] == root or root[: len(path)] == path
        if not affected and after_records.get(path) != raw:
            raise SystemExit(f"protected record changed: {'/'.join(path)}")


def patch_client() -> bytes:
    before = CLIENT_132.read_bytes()
    image = WzImage.from_bytes(before, key=WzKey.for_region("GMS"))
    image.parse()
    if image.truncated or image.parse_warnings:
        raise SystemExit(image.parse_warnings)
    source = image.root.get("skill/1321011/level")
    if source is None:
        raise SystemExit("missing 1321011/level")
    replacement = clone_tree(source)
    result = replace_img_record(before, ("skill", "1321011", "level"), replacement, region="GMS")
    verify_scope(before, result.data)
    parsed = WzImage.from_bytes(result.data, key=WzKey.for_region("GMS"))
    parsed.parse()
    if parsed.truncated or parsed.parse_warnings:
        raise SystemExit(parsed.parse_warnings)
    lv30 = parsed.root.get("skill/1321011/level/30")
    lt, rb = lv30.child("lt"), lv30.child("rb")
    if (int(lt.x), int(lt.y)) != LT or (int(rb.x), int(rb.y)) != RB:
        raise SystemExit(f"lv30 box {(lt.x, lt.y)} {(rb.x, rb.y)}")
    print("client 1321011 level delta", result.byte_delta)
    return result.data


def patch_xml() -> None:
    text = SERVER_XML.read_text(encoding="utf-8")
    pattern = r'(  <imgdir name="1321011">.*?\n  </imgdir>\n)(  <imgdir name="1321015">)'
    match = re.search(pattern, text, flags=re.S)
    if match is None:
        raise SystemExit("1321011 xml block not found")
    block = match.group(1)
    updated = block.replace(
        '<vector name="lt" x="-700" y="-450" />',
        f'<vector name="lt" x="{LT[0]}" y="{LT[1]}" />',
    ).replace(
        '<vector name="rb" x="700" y="250" />',
        f'<vector name="rb" x="{RB[0]}" y="{RB[1]}" />',
    )
    if updated.count(f'x="{LT[0]}"') < 30:
        raise SystemExit("did not rewrite all 1321011 lt vectors")
    if "-700" in updated or 'x="700" y="250"' in updated:
        raise SystemExit("old fullscreen box still in 1321011")
    text = text[: match.start(1)] + updated + text[match.start(2) :]
    atomic_write_text(SERVER_XML, text)


def main() -> int:
    first = patch_client()
    atomic_write_bytes(CLIENT_132, first)
    first_hash = hashlib.sha256(first).hexdigest()
    second = patch_client()
    if hashlib.sha256(second).hexdigest() != first_hash:
        raise SystemExit("not idempotent")
    atomic_write_bytes(CLIENT_132, second)
    patch_xml()
    print("client 132.img", first_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
