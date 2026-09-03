#!/usr/bin/env python3
"""Incrementally copy server quest -27916 into the zh-CN Quest XML tree."""

from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
QUEST_FILES = ("Check.img.xml", "Act.img.xml", "QuestInfo.img.xml", "Say.img.xml")
NODE_NAME = "-27916"
ANCHOR_NAME = "-27917"


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    pattern = re.compile(rf'<imgdir\s+name="{re.escape(node_name)}"(?:\s[^>]*)?>')
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"missing imgdir {node_name}")

    depth = 0
    for tag in re.finditer(r"<imgdir\b[^>]*>|</imgdir>", text[match.start():]):
        token = tag.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return match.start(), match.start() + tag.end()
        elif not token.endswith("/>"):
            depth += 1
    raise ValueError(f"unterminated imgdir {node_name}")


def atomic_write_text(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except Exception:
        os.unlink(temp_name)
        raise


def sync_file(file_name: str) -> bool:
    source_path = ROOT / "gms-server" / "wz" / "Quest.wz" / file_name
    target_path = ROOT / "gms-server" / "wz-zh-CN" / "Quest.wz" / file_name
    source = source_path.read_text(encoding="utf-8")
    target = target_path.read_text(encoding="utf-8")

    try:
        existing_start, existing_end = find_imgdir_block(target, NODE_NAME)
    except ValueError:
        existing_start = existing_end = -1

    source_start, source_end = find_imgdir_block(source, NODE_NAME)
    source_block = source[source_start:source_end]
    if existing_start >= 0:
        if target[existing_start:existing_end] != source_block:
            raise ValueError(f"{target_path}: existing {NODE_NAME} differs from source")
        return False

    anchor_start, _ = find_imgdir_block(target, ANCHOR_NAME)
    updated = target[:anchor_start] + source_block + "\n  " + target[anchor_start:]
    if updated.replace(source_block + "\n  ", "", 1) != target:
        raise AssertionError(f"{target_path}: bytes outside inserted block changed")
    ET.fromstring(updated)
    atomic_write_text(target_path, updated)
    return True


def main() -> None:
    changed = [file_name for file_name in QUEST_FILES if sync_file(file_name)]
    print("updated: " + (", ".join(changed) if changed else "none"))


if __name__ == "__main__":
    main()
