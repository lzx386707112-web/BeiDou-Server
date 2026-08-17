#!/usr/bin/env python3
"""Remove Chaos Pierre's fixed player-damage cap."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

from wzpy import WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402
from migrate_root_abyss_maps import gms_reader, remove_child  # noqa: E402


MOB_ID = 8900000
TARGET_KEY = WzKey.for_region("GMS")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def patch_client_mob() -> None:
    path = ROOT / f"clien/Data/Mob/{MOB_ID}.img"
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed {path}: {image.parse_warnings}")

    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"missing info in {path}")
    remove_child(info, "fixedDamage")

    atomic_write_bytes(path, encode_image_body(image, gms_reader()))

    verify = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    verify.parse()
    if verify.truncated or verify.parse_warnings:
        raise RuntimeError(f"malformed output {path}: {verify.parse_warnings}")
    if verify.root.get("info/fixedDamage") is not None:
        raise RuntimeError("fixedDamage still present")


def patch_server_xml() -> None:
    path = ROOT / f"gms-server/wz/Mob.wz/{MOB_ID}.img.xml"
    text = path.read_text(encoding="utf-8")
    if 'name="fixedDamage"' in text:
        raise RuntimeError(f"server XML still has fixedDamage: {path}")


def main() -> int:
    patch_client_mob()
    patch_server_xml()
    print(f"removed fixedDamage from {MOB_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
