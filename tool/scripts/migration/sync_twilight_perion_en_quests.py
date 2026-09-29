#!/usr/bin/env python3
"""Mirror the newly imported 黃昏的勇士之村 quests into the English server tree.

``import_twilight_perion_quest_chain.py`` only writes ``wz-zh-CN/Quest.wz``.
The two trees are normally kept in sync, so copy the freshly added blocks
(31930..31944) across to ``wz/Quest.wz`` as well.  Idempotent: entries that
already exist are skipped.

Run:  /opt/homebrew/bin/python3 tool/scripts/migration/sync_twilight_perion_en_quests.py
"""

from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "gms-server/wz-zh-CN/Quest.wz"
DST = ROOT / "gms-server/wz/Quest.wz"
BACKUP_ROOT = Path("/private/tmp/twilight-perion-en-quests-backup")

FILES = ("QuestInfo", "Check", "Act", "Say")
QUEST_IDS = [str(i) for i in range(31930, 31945)]


def backup(path: Path) -> None:
    target = BACKUP_ROOT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def extract_block(text: str, qid: str) -> str | None:
    m = re.search(
        r'^  <imgdir name="%s">.*?^  </imgdir>' % re.escape(qid), text, re.S | re.M
    )
    return m.group(0) if m else None


def insert_block(path: Path, qid: str, block: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if f'<imgdir name="{qid}">' in text:
        return False
    positions = [
        (int(m.group(1)), m.start())
        for m in re.finditer(r'^  <imgdir name="(\d+)">', text, re.M)
    ]
    target = None
    for value, offset in positions:
        if value > int(qid):
            target = offset
            break
    if target is None:
        target = text.rfind("</imgdir>")
    result = text[:target] + block + "\n" + text[target:]
    ET.fromstring(result)  # validate before writing
    backup(path)
    path.write_text(result, encoding="utf-8")
    return True


def main() -> int:
    total = 0
    for name in FILES:
        src, dst = SRC / f"{name}.img.xml", DST / f"{name}.img.xml"
        if not dst.exists():
            print(f"  {name}: English tree missing, skip")
            continue
        src_text = src.read_text(encoding="utf-8")
        added = 0
        for qid in QUEST_IDS:
            block = extract_block(src_text, qid)
            if block is None:
                print(f"  {name}/{qid}: not in zh-CN tree, skip")
                continue
            if insert_block(dst, qid, block):
                added += 1
        print(f"  {name}.img.xml: +{added}")
        total += added
    print(f"\ndone: {total} blocks copied to wz/Quest.wz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
