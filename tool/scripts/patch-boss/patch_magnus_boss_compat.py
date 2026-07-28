#!/usr/bin/env python3
"""Patch the single Boss-only Magnus with long server HP."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzIntProperty, WzKey, WzStringProperty, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402
from patch_lucid_boss_compat import convert_canvas_tree_to_argb4444  # noqa: E402


KEY = WzKey.for_region("GMS")
MAGNUS_ID = 8880000
REMOVED_IDS = (8880001, 8880002, 8880004, 8880005, 8880006, 8880007, 8880008, 8880009, 8880010, 8880011)


def set_int(info: WzSubProperty, name: str, value: int) -> None:
    node = info.child(name)
    if node is None:
        info.add(WzIntProperty(name, value, info))
    else:
        node._value = value


def patch_client_mob() -> None:
    path = ROOT / "clien/Data/Mob/8880000.img"
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    info = img.root.child("info")
    if info is None:
        raise ValueError("8880000: missing info")
    set_int(info, "maxHP", 2_000_000_000)
    set_int(info, "hpRecovery", 100_000_000)
    set_int(info, "speed", 50)
    set_int(info, "PDDamage", 30_000)
    set_int(info, "MDDamage", 30_000)
    info._children.pop("revive", None)
    convert_canvas_tree_to_argb4444(img.root, source_region="GMS")
    path.write_bytes(encode_image_body(img, img.wz_file.reader))


def replace_scalar(text: str, name: str, tag: str, value: int) -> str:
    pattern = rf'<(?:int|string) name="{re.escape(name)}" value="[^"]*"/>'
    replacement = f'<{tag} name="{name}" value="{value}"/>'
    new_text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"missing server info/{name}")
    return new_text


def patch_server_mob() -> None:
    path = ROOT / "gms-server/wz/Mob.wz/8880000.img.xml"
    text = path.read_text(encoding="utf-8")
    text = replace_scalar(text, "maxHP", "string", 5_000_000_000)
    if 'name="hpRecovery"' in text:
        text = replace_scalar(text, "hpRecovery", "int", 100_000_000)
    else:
        text = text.replace(
            '<int name="mpRecovery" value="10000"/>',
            '<int name="mpRecovery" value="10000"/>\n    <int name="hpRecovery" value="100000000"/>',
            1,
        )
    text = replace_scalar(text, "speed", "int", 50)
    path.write_text(text, encoding="utf-8")


def patch_client_strings() -> None:
    path = ROOT / "clien/Data/String/Mob.img"
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    for mob_id in REMOVED_IDS:
        img.root._children.pop(str(mob_id), None)
    entry = WzSubProperty(str(MAGNUS_ID))
    entry.add(WzStringProperty("name", "麦格纳斯"))
    img.root._children[str(MAGNUS_ID)] = entry
    path.write_bytes(encode_image_body(img, img.wz_file.reader))


def patch_server_strings(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for mob_id in REMOVED_IDS:
        text = re.sub(
            rf'<imgdir name="{mob_id}">.*?</imgdir>',
            "",
            text,
            count=1,
            flags=re.DOTALL,
        )
    if '<imgdir name="8880000">' not in text:
        root_close = text.rfind("</imgdir>")
        text = text[:root_close] + '<imgdir name="8880000"><string name="name" value="麦格纳斯"/></imgdir>' + text[root_close:]
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_client_mob()
    patch_server_mob()
    patch_client_strings()
    patch_server_strings(ROOT / "gms-server/wz/String.wz/Mob.img.xml")
    patch_server_strings(ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
