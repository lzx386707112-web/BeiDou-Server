#!/usr/bin/env python3
"""Set the 83 installed Arcane River mobs to legacy-safe EVA 100."""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKUP_ROOT = Path("/private/tmp/arcane-river-eva100-backup")
TARGET_EVA = 100
REGION_PREFIXES = {"450001", "450002", "450003", "450005", "450006", "450007"}

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_arcane_river_fields import GMS_KEY, atomic_write_bytes, gms_reader, load_image  # noqa: E402
from wzpy import WzIntProperty, WzSubProperty  # noqa: E402
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


def installed_mob_ids() -> set[int]:
    mob_ids: set[int] = set()
    map_root = ROOT / "gms-server/wz/Map.wz/Map/Map4"
    for path in map_root.glob("450*.img.xml"):
        map_id = int(path.name.split(".")[0])
        if str(map_id)[:6] not in REGION_PREFIXES:
            continue
        root = ET.parse(path).getroot()
        life = next(
            (child for child in root if child.tag == "imgdir" and child.get("name") == "life"),
            None,
        )
        if life is None:
            continue
        for entry in life:
            values = {child.get("name"): child.get("value") for child in entry}
            if values.get("type") == "m" and (values.get("id") or "").isdigit():
                mob_ids.add(int(values["id"]))
    if len(mob_ids) != 83:
        raise RuntimeError(f"expected 83 installed Arcane River mobs, found {len(mob_ids)}")
    return mob_ids


def patch_client(mob_id: int) -> None:
    path = ROOT / f"clien/Data/Mob/{mob_id}.img"
    image = load_image(path, GMS_KEY)
    info = image.root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{path}: missing info")
    eva = info.child("eva")
    if not isinstance(eva, WzIntProperty):
        raise RuntimeError(f"{path}: missing integer eva")
    if int(eva.value) == TARGET_EVA:
        return
    eva._value = TARGET_EVA
    backup(path)
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def patch_server(mob_id: int) -> None:
    path = ROOT / f"gms-server/wz/Mob.wz/{mob_id}.img.xml"
    text = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r'(<int\s+name="eva"\s+value=")[^"]+("\s*/>)')
    output, replacements = pattern.subn(rf"\g<1>{TARGET_EVA}\g<2>", text, count=1)
    if replacements != 1:
        raise RuntimeError(f"{path}: expected one eva node, found {replacements}")
    if output == text:
        return
    backup(path)
    atomic_write_text(path, output)


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    mob_ids = installed_mob_ids()
    for mob_id in sorted(mob_ids):
        patch_client(mob_id)
        patch_server(mob_id)
    print(f"Arcane River mob EVA normalized: mobs={len(mob_ids)}, eva={TARGET_EVA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
