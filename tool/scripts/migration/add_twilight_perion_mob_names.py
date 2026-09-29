#!/usr/bin/env python3
"""Add the display names of the two migrated 黃昏的勇士之村 mobs.

8620012 (變形樹妖王) already existed in the repo but was never spawned, and
9100043 (驅夢者的手下) was migrated from TMS; neither has a String entry, so the
name plate above them renders empty.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/add_twilight_perion_mob_names.py
"""

from __future__ import annotations

import importlib.util
import io
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import (  # noqa: E402
    WzImage,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    detect_region_from_img,
)
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _record_bytes,
    _reference_edits,
    _size_edits,
    scan_img,
)
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_compressed_int  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "arc", ROOT / "tool/scripts/migration/migrate_arcane_river_expansion.py"
)
arc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arc)

TMS = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
BACKUP_ROOT = Path("/private/tmp/twilight-perion-mob-names-backup")
MOBS = ("8620012", "9100043")


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def tms_name(mob_id: str):
    data = (TMS / "String/Mob.img").read_bytes()
    root = WzImage.from_bytes(data, key=arc.BMS_KEY).parse()
    container = root
    if len(root.children()) == 1 and root.children()[0].children():
        container = root.children()[0]
    for child in container.children():
        if child.name == mob_id:
            node = child.child("name")
            return node.value if node is not None else None
    return None


def insert_server(path: Path, mob_id: str, name: str) -> None:
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{mob_id}">' in text:
        print(f"    {path.name}: {mob_id} already present, skip")
        return
    block = (
        f'  <imgdir name="{mob_id}">\n'
        f'    <string name="name" value={quoteattr(name)}/>\n'
        f'  </imgdir>'
    )
    positions = [
        (int(m.group(1)), m.start())
        for m in re.finditer(r'^  <imgdir name="(\d+)">', text, re.M)
    ]
    target = None
    for value, offset in positions:
        if value > int(mob_id):
            target = offset
            break
    if target is None:
        target = text.rfind("</imgdir>")
    result = text[:target] + block + "\n" + text[target:]
    ET.fromstring(result)
    backup(path)
    path.write_text(result, encoding="utf-8")


def insert_client(path: Path, mob_id: str, name: str) -> None:
    data = path.read_bytes()
    layout = scan_img(data, region="GMS")
    if any(record.name == mob_id for record in layout.root.records):
        print(f"    {path.name}: {mob_id} already present, skip")
        return
    node = WzSubProperty(mob_id)
    node.add(WzStringProperty("name", name))
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region("GMS"))
    payload = _record_bytes(node, reader)
    count_bytes = encode_compressed_int(layout.root.count + 1)
    count_delta = len(count_bytes) - (layout.root.count_end - layout.root.count_offset)
    delta = len(payload) + count_delta
    edits = [
        (layout.root.end, layout.root.end, payload),
        (layout.root.count_offset, layout.root.count_end, count_bytes),
        *_size_edits([], delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    patched = _apply_edits(data, edits)
    image = WzImage.from_bytes(patched, key=WzKey.for_region("GMS"))
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{path.name}: patched IMG invalid: {image.parse_warnings}")
    backup(path)
    path.write_bytes(patched)


def main() -> int:
    server = ROOT / "gms-server/wz/String.wz/Mob.img.xml"
    client = ROOT / "clien/Data/String/Mob.img"
    for mob_id in MOBS:
        name = tms_name(mob_id)
        if name is None:
            print(f"  {mob_id}: no TMS name, skip")
            continue
        print(f"  {mob_id}: {name}")
        insert_server(server, mob_id, str(name))
        insert_client(client, mob_id, str(name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
