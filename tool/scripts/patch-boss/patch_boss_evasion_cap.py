#!/usr/bin/env python3
"""Cap selected boss evasion values at 200 in client IMG and server XML data."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzIntProperty, WzKey  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


CAP = 200
BOSS_IDS = (
    8850011,  # Cygnus
    8860000,  # Arkarium
    8880340, 8880342,  # Seren
    8880140, 8880141,  # Lucid
    8644630,  # Dusk
    8880504, 8880505, 8880506, 8880507, 8880511,  # Black Mage
)
KEY = WzKey.for_region("GMS")
EVA_PATTERN = re.compile(r'(<int name="eva" value=")(-?\d+)("\s*/>)')


def atomic_write(path: Path, data: bytes) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temp_name, path)
    except BaseException:
        os.unlink(temp_name)
        raise


def patch_img(path: Path) -> tuple[int, int]:
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    info = img.root.child("info")
    eva = info.child("eva") if info is not None else None
    if eva is None:
        raise ValueError(f"{path}: missing info/eva")
    old = int(eva.value)
    if old <= CAP:
        return old, old
    replacement = WzIntProperty("eva", CAP, parent=info)
    info._children["eva"] = replacement
    atomic_write(path, encode_image_body(img, img.wz_file.reader))
    return old, CAP


def patch_xml(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    match = EVA_PATTERN.search(text)
    if match is None:
        raise ValueError(f"{path}: missing info/eva")
    old = int(match.group(2))
    if old <= CAP:
        return old, old
    updated = EVA_PATTERN.sub(rf"\g<1>{CAP}\g<3>", text, count=1)
    atomic_write(path, updated.encode("utf-8"))
    return old, CAP


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-dir",
        action="append",
        type=Path,
        default=[],
        help="Mob IMG directory; may be supplied more than once",
    )
    args = parser.parse_args()

    client_dirs = args.client_dir or [ROOT / "clien/Data/Mob"]
    server_dir = ROOT / "gms-server/wz/Mob.wz"
    for mob_id in BOSS_IDS:
        for client_dir in client_dirs:
            path = client_dir / f"{mob_id}.img"
            old, new = patch_img(path)
            print(f"IMG {path}: {old} -> {new}")
        path = server_dir / f"{mob_id}.img.xml"
        old, new = patch_xml(path)
        print(f"XML {path}: {old} -> {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
