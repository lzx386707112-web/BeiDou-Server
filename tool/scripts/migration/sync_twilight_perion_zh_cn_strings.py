#!/usr/bin/env python3
"""Mirror the 黃昏的勇士之村 String entries into the zh-CN server WZ tree.

The earlier migration scripts wrote mob/item display names into
``gms-server/wz/String.wz`` (the English tree).  The server runs with
``gms.service.language: zh-CN`` and ``WZFiles.getFile()`` prefers
``wz-zh-CN/<file>`` whenever it exists -- so those names would never be seen.

This script copies the exact entries this task added into the zh-CN tree:

* ``wz-zh-CN/String.wz/Mob.img.xml``  <- 8620012, 9100043
* ``wz-zh-CN/String.wz/Etc.img.xml``  <- 4033730/4033731/4033750..4033754

Both trees are edited idempotently (existing entries are skipped) and every
result is re-parsed with ElementTree before being written.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/sync_twilight_perion_zh_cn_strings.py
"""

from __future__ import annotations

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[3]
SERVER_EN = ROOT / "gms-server/wz"
SERVER_ZH = ROOT / "gms-server/wz-zh-CN"
BACKUP_ROOT = Path("/private/tmp/twilight-perion-zhcn-strings-backup")

MOB_IDS = ("8620012", "9100043")
ETC_IDS = (
    "4033730",
    "4033731",
    "4033750",
    "4033751",
    "4033752",
    "4033753",
    "4033754",
)


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def read_entry(text: str, entry_id: str) -> tuple[str, str] | None:
    """Pull (name, desc) for ``entry_id`` out of a String XML blob."""
    m = re.search(
        r'<imgdir name="%s">(.*?)</imgdir>' % re.escape(entry_id), text, re.S
    )
    if not m:
        return None
    inner = m.group(1)
    name = re.search(r'<string name="name" value="([^"]*)"', inner)
    desc = re.search(r'<string name="desc" value="([^"]*)"', inner)
    return (
        name.group(1) if name else "",
        desc.group(1) if desc else "",
    )


def insert_sorted_block(path: Path, entry_id: str, block: str) -> bool:
    """Insert ``block`` into a 2-space indented imgdir list, keeping id order."""
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{entry_id}">' in text:
        print(f"    {path.name}: {entry_id} already present, skip")
        return False
    positions = [
        (int(m.group(1)), m.start())
        for m in re.finditer(r'^  <imgdir name="(\d+)">', text, re.M)
    ]
    target = None
    for value, offset in positions:
        if value > int(entry_id):
            target = offset
            break
    if target is None:
        target = text.rfind("</imgdir>")
    result = text[:target] + block + "\n" + text[target:]
    ET.fromstring(result)  # validate before writing
    backup(path)
    path.write_text(result, encoding="utf-8")
    print(f"    {path.name}: + {entry_id}")
    return True


def sync_mobs() -> int:
    src = SERVER_EN / "String.wz/Mob.img.xml"
    dst = SERVER_ZH / "String.wz/Mob.img.xml"
    if not dst.exists():
        print("  zh-CN Mob.img.xml missing, skip")
        return 0
    src_text = src.read_text(encoding="utf-8")
    n = 0
    for mob_id in MOB_IDS:
        entry = read_entry(src_text, mob_id)
        if entry is None:
            print(f"  {mob_id}: not found in English tree, skip")
            continue
        name, _ = entry
        block = (
            f'  <imgdir name="{mob_id}">\n'
            f'    <string name="name" value={quoteattr(name)} />\n'
            f"  </imgdir>"
        )
        if insert_sorted_block(dst, mob_id, block):
            n += 1
    return n


def _etc_container_end(text: str) -> int:
    """Offset just past the closing tag of the top-level ``Etc`` container.

    zh-CN ``String.wz/Etc.img.xml`` is a single line shaped like::

        <imgdir name="Etc.img"><imgdir name="Etc">...entries...</imgdir>
        <imgdir name="4033080">...</imgdir>...</imgdir>

    i.e. every real entry lives *inside* the ``Etc`` container; a handful of
    stray ids sit at top level after it.  Appending at the end of the file
    would put new entries outside the container the server reads.
    """
    start = text.find('<imgdir name="Etc">')
    if start < 0:
        raise RuntimeError("zh-CN Etc.img.xml has no Etc container")
    # Walk the tags and stop where the container's depth returns to zero.
    depth = 0
    pos = start
    open_re = re.compile(r"<imgdir\b[^>]*>")
    close_re = re.compile(r"</imgdir>")
    while True:
        open_m = open_re.search(text, pos)
        close_m = close_re.search(text, pos)
        if close_m is None:
            raise RuntimeError("unbalanced imgdir tags after Etc container")
        if open_m is not None and open_m.start() < close_m.start():
            # Only count real containers: a self-closing <imgdir ... /> has no depth.
            if not open_m.group(0).endswith("/>"):
                depth += 1
            pos = open_m.end()
            continue
        depth -= 1
        pos = close_m.end()
        if depth == 0:
            # Insert *before* the container's closing tag, i.e. inside it.
            return close_m.start()


def sync_etc() -> int:
    src = SERVER_EN / "String.wz/Etc.img.xml"
    dst = SERVER_ZH / "String.wz/Etc.img.xml"
    if not dst.exists():
        print("  zh-CN Etc.img.xml missing, skip")
        return 0
    src_text = src.read_text(encoding="utf-8")
    n = 0
    for item_id in ETC_IDS:
        entry = read_entry(src_text, item_id)
        if entry is None:
            print(f"  {item_id}: not found in English tree, skip")
            continue
        name, desc = entry
        block = (
            f'<imgdir name="{item_id}">'
            f'<string name="desc" value={quoteattr(desc)} />'
            f'<string name="name" value={quoteattr(name)} />'
            f"</imgdir>"
        )
        text = dst.read_text(encoding="utf-8")
        if f'<imgdir name="{item_id}">' in text:
            # present but maybe at the wrong level -- verify via ElementTree
            root = ET.fromstring(text)
            if any(
                c.get("name") == item_id
                for c in root.find('./imgdir[@name="Etc"]')
            ):
                print(f"    {dst.name}: {item_id} already in Etc, skip")
                continue
            raise RuntimeError(
                f"{dst.name}: {item_id} exists outside the Etc container; "
                f"restore from {BACKUP_ROOT} and re-run"
            )
        anchor = _etc_container_end(text)
        result = text[:anchor] + block + text[anchor:]
        ET.fromstring(result)  # validate
        backup(dst)
        dst.write_text(result, encoding="utf-8")
        print(f"    {dst.name}: + {item_id} (inside Etc)")
        n += 1
    return n


def main() -> int:
    print("== mob names ==")
    a = sync_mobs()
    print("== etc item names ==")
    b = sync_etc()
    print(f"\ndone: mob +{a}, etc +{b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
