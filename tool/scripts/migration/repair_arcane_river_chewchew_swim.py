#!/usr/bin/env python3
"""Enable legacy underwater movement on Chew Chew's left field."""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450002011
BACKUP_ROOT = Path("/private/tmp/arcane-river-chewchew-swim-backup")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_arcane_river_fields import GMS_KEY, atomic_write_bytes, gms_reader, load_image  # noqa: E402
from wzpy import WzIntProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


def backup(path: Path) -> None:
    destination = BACKUP_ROOT / path.relative_to(ROOT)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def atomic_write_text(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def patch_client() -> None:
    path = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    image = load_image(path, GMS_KEY)
    swim = image.root.get("info/swim")
    if not isinstance(swim, WzIntProperty):
        raise RuntimeError(f"{path}: missing integer info/swim")
    if int(swim.value) == 1:
        return
    swim._value = 1
    backup(path)
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def patch_server() -> None:
    path = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    text = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r'(<int\s+name="swim"\s+value=")[^"]+("\s*/>)')
    output, replacements = pattern.subn(r"\g<1>1\g<2>", text, count=1)
    if replacements != 1:
        raise RuntimeError(f"{path}: expected one info/swim node, found {replacements}")
    if output == text:
        return
    backup(path)
    atomic_write_text(path, output)


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    patch_client()
    patch_server()
    print(f"Chew Chew legacy swim enabled: map={MAP_ID}, swim=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
