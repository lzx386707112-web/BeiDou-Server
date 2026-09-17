#!/usr/bin/env python3
"""Rewrite Damien P1 skill2 hold-loop UOLs for the old client.

TMS skill2/31–79 are same-folder UOLs (value="23") that keep the airborne
pose 23–30. The old client resolves those as missing and falls back to stand,
so the boss flickers between the sky canvas and the ground body.

Proven analogue: skill2/0–9 already use ../skill1/N. Point 31–79 at
../skill2/N instead. Incremental record replace only; do not full-serialize.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "tool/wz-python"),
    str(ROOT / "tool/scripts/migration"),
    str(ROOT / "tool/resource-workbench"),
]

import migrate_arcane_river_expansion as arc  # noqa: E402
from map_mob import app as workbench  # noqa: E402
from wzpy import WzImage, WzUolProperty  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402

CLIENT = ROOT / "clien/Data/Mob/8880110.img"
SERVER = ROOT / "gms-server/wz/Mob.wz/8880110.img.xml"
HOLD_FRAMES = range(31, 80)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wanted_uol(current: str) -> str:
    target = current.strip().replace("\\", "/")
    if target.startswith("../skill2/"):
        return target
    if not target.isdigit():
        raise RuntimeError(f"skill2 hold UOL is not a same-folder loop: {current!r}")
    return f"../skill2/{target}"


def patch_client(data: bytes) -> bytes:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name="8880110.img")
    image.parse()
    skill2 = image.root.get("skill2")
    if skill2 is None:
        raise RuntimeError("8880110 missing skill2")
    for index in HOLD_FRAMES:
        node = skill2.child(str(index))
        if not isinstance(node, WzUolProperty):
            raise RuntimeError(f"skill2/{index} is not a UOL")
        wanted = wanted_uol(str(node.value))
        if str(node.value) == wanted:
            continue
        result = replace_img_record(
            data, ("skill2", str(index)), WzUolProperty(str(index), wanted), region="GMS",
        )
        data = result.data
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name="8880110.img")
        image.parse()
        skill2 = image.root.get("skill2")
    return data


def verify_client(data: bytes, original: bytes) -> None:
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name="8880110.img")
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"parse failed: {image.parse_warnings}")
    skill2 = image.root.get("skill2")
    for index in HOLD_FRAMES:
        node = skill2.child(str(index))
        if not isinstance(node, WzUolProperty):
            raise RuntimeError(f"skill2/{index} lost UOL")
        value = str(node.value)
        if not value.startswith("../skill2/"):
            raise RuntimeError(f"skill2/{index} still {value}")
        frame = int(value.rsplit("/", 1)[-1])
        if frame < 23 or frame > 30:
            raise RuntimeError(f"skill2/{index} points at {frame}, expected 23–30")
        target = skill2.child(str(frame))
        if target is None:
            raise RuntimeError(f"missing loop source skill2/{frame}")
    before, _ = arc.raw_record_state(original)
    after, _ = arc.raw_record_state(data)
    for path, payload in before.items():
        if path[0] != "skill2" and after.get(path) != payload:
            raise RuntimeError(f"protected record changed: {'/'.join(path)}")
    for path in after:
        if path[0] != "skill2" and path not in before:
            raise RuntimeError(f"unexpected record added: {'/'.join(path)}")
    for index in list(range(0, 31)) + list(range(80, 105)):
        key = ("skill2", str(index))
        if before.get(key) != after.get(key):
            raise RuntimeError(f"skill2/{index} was not supposed to change")


def patch_server() -> None:
    original = SERVER.read_bytes()
    for index in HOLD_FRAMES:
        path = f"skill2/{index}"
        current = workbench.index_xml(SERVER.read_bytes())[path]
        value = current.attrs.get("value", "")
        wanted = wanted_uol(value)
        if value == wanted:
            continue
        workbench.patch_xml_value(SERVER, path, wanted, dry_run=False, backup=False)
    if original == SERVER.read_bytes():
        return
    import xml.etree.ElementTree as ET
    ET.parse(SERVER)


def main() -> int:
    original = CLIENT.read_bytes()
    first = patch_client(original)
    verify_client(first, original)
    second = patch_client(first)
    if sha256(first) != sha256(second):
        raise RuntimeError("skill2 hold UOL patcher is not idempotent")
    arc.atomic_write_bytes(CLIENT, first)
    patch_server()
    print("damien skill2 hold UOLs ok", sha256(first))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
