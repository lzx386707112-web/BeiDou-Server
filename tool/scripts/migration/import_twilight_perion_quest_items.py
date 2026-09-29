#!/usr/bin/env python3
"""Import the 黃昏的勇士之村 quest ETC items that the repo never received.

31932-31940 (勇士之村戰士們的靈魂 / 緊缺的工料 / 勇士之村的名物 / 思念的孫女生日)
all require ETC items that exist in neither clien/Data/Item nor wz/Item.wz, so
those quests can never be completed.  4033732 and friends were imported long
ago; these seven were missed.

Everything is cloned from the TMS dump with the standard ARGB4444 projection and
inserted record by record, so no existing item moves.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/import_twilight_perion_quest_items.py
"""

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
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
BACKUP_ROOT = Path("/private/tmp/twilight-perion-item-import-backup")

ITEMS = ("04033730", "04033731", "04033750", "04033751", "04033752", "04033753", "04033754")
KEEP_INFO = ("icon", "iconRaw", "price", "quest")


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def load_tms(rel: str):
    data = (TMS / rel).read_bytes()
    return WzImage.from_bytes(data, key=arc.BMS_KEY).parse()


def clone_item(name: str):
    source = load_tms("Item/Etc/0403.img")
    node = None
    for child in source.children():
        if child.name == name:
            node = child
            break
    if node is None:
        raise RuntimeError(f"TMS has no item {name}")
    image = arc.load_image(TMS / "Item/Etc/0403.img", arc.BMS_KEY)
    materializer = arc.CanvasMaterializer()
    holder = WzSubProperty(name)
    cloned = arc.clone_property(
        node, holder, image, TMS / "Item/Etc/0403.img", materializer
    )
    info = cloned.child("info")
    for child in list(info.children()):
        if child.name not in KEEP_INFO:
            arc.remove_child(info, child.name)
    return cloned, materializer


# --------------------------------------------------------------------------- #
def insert_img(path: Path, prop) -> None:
    data = path.read_bytes()
    layout = scan_img(data, region="GMS")
    if any(record.name == prop.name for record in layout.root.records):
        print(f"    {path.name}: {prop.name} already present, skip")
        return
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region("GMS"))
    payload = _record_bytes(prop, reader)
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
        raise RuntimeError(
            f"{path.name}: patched IMG invalid: {image.parse_warnings or image.truncated}"
        )
    backup(path)
    path.write_bytes(patched)


def canvas_xml(canvas: WzCanvasProperty, indent: int) -> str:
    pad = "  " * indent
    origin = canvas.child("origin")
    ox = int(origin.x) if origin is not None else 0
    oy = int(origin.y) if origin is not None else 0
    return (
        f'{pad}<canvas name="{canvas.name}" width="{canvas.width}" '
        f'height="{canvas.height}" format="1">\n'
        f'{pad}  <vector name="origin" x="{ox}" y="{oy}"/>\n'
        f"{pad}</canvas>"
    )


def item_xml(name: str, prop) -> str:
    lines = [f'  <imgdir name="{name}">', '    <imgdir name="info">']
    info = prop.child("info")
    for child in info.children():
        if isinstance(child, WzCanvasProperty):
            lines.append(canvas_xml(child, 3))
        else:
            lines.append(f'      <int name="{child.name}" value="{child.value}"/>')
    lines.append("    </imgdir>")
    lines.append("  </imgdir>")
    return "\n".join(lines)


def insert_xml(path: Path, name: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{name}">' in text:
        print(f"    {path.name}: {name} already present, skip")
        return
    positions = [
        (int(m.group(1)), m.start())
        for m in __import__("re").finditer(r'^  <imgdir name="(\d+)">', text, __import__("re").M)
    ]
    target = None
    for value, offset in positions:
        if value > int(name):
            target = offset
            break
    if target is None:
        target = text.rfind("</imgdir>")
    result = text[:target] + block + "\n" + text[target:]
    ET.fromstring(result)
    backup(path)
    path.write_text(result, encoding="utf-8")


# --------------------------------------------------------------------------- #
def string_entry(rel: str, item_id: str):
    """Return (name, desc) from the TMS String dump, or None."""
    root = load_tms(rel)
    container = root
    if len(root.children()) == 1 and root.children()[0].children():
        container = root.children()[0]
    for child in container.children():
        if child.name == item_id:
            values = {c.name: c.value for c in child.children()}
            return values.get("name"), values.get("desc")
    return None


def add_string_server(path: Path, item_id: str, name, desc) -> None:
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{item_id}">' in text:
        print(f"    {path.name}: {item_id} already present, skip")
        return
    lines = [f'  <imgdir name="{item_id}">']
    if name is not None:
        lines.append(f'    <string name="name" value={quoteattr(str(name))}/>')
    if desc is not None:
        lines.append(f'    <string name="desc" value={quoteattr(str(desc))}/>')
    lines.append("  </imgdir>")
    block = "\n".join(lines)
    import re as _re

    positions = [
        (int(m.group(1)), m.start())
        for m in _re.finditer(r'^  <imgdir name="(\d+)">', text, _re.M)
    ]
    target = None
    for value, offset in positions:
        if value > int(item_id):
            target = offset
            break
    if target is None:
        target = text.rfind("</imgdir>")
    result = text[:target] + block + "\n" + text[target:]
    ET.fromstring(result)
    backup(path)
    path.write_text(result, encoding="utf-8")


def add_string_client(path: Path, item_id: str, name, desc) -> None:
    data = path.read_bytes()
    layout = scan_img(data, region="GMS")
    container, ancestors = None, []
    for record in layout.root.records:
        if record.children is not None and record.name in ("Etc",):
            container = record.children
            ancestors = [record]
            break
    if container is None:
        container = layout.root
        ancestors = []
    if any(record.name == item_id for record in container.records):
        print(f"    {path.name}: {item_id} already present, skip")
        return
    node = WzSubProperty(item_id)
    if name is not None:
        node.add(WzStringProperty("name", str(name)))
    if desc is not None:
        node.add(WzStringProperty("desc", str(desc)))
    reader = WzBinaryReader(io.BytesIO(data), WzKey.for_region("GMS"))
    payload = _record_bytes(node, reader)
    count_bytes = encode_compressed_int(container.count + 1)
    count_delta = len(count_bytes) - (container.count_end - container.count_offset)
    delta = len(payload) + count_delta
    edits = [
        (container.end, container.end, payload),
        (container.count_offset, container.count_end, count_bytes),
        *_size_edits(ancestors, delta),
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
    client_items = ROOT / "clien/Data/Item/Etc/0403.img"
    server_items = ROOT / "gms-server/wz/Item.wz/Etc/0403.img.xml"
    server_string = ROOT / "gms-server/wz/String.wz/Etc.img.xml"
    client_string = ROOT / "clien/Data/String/Etc.img"

    for name in ITEMS:
        prop, materializer = clone_item(name)
        item_id = str(int(name))
        print(f"  {item_id}: canvases={materializer.canvases} links={materializer.links}")
        insert_img(client_items, prop)
        insert_xml(server_items, name, item_xml(name, prop))
        name_text, desc_text = string_entry("String/Etc.img", item_id)
        print(f"      name={name_text} desc={str(desc_text)[:40]}")
        add_string_server(server_string, item_id, name_text, desc_text)
        add_string_client(client_string, item_id, name_text, desc_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
