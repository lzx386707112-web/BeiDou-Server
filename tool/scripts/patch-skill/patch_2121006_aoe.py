#!/usr/bin/env python3
"""Patch FP ArchMage Paralyze (2121006) to hit multiple monsters.

The client .img and server .img.xml both need the skill metadata. Without
mobCount the server defaults to 1 target, and without lt/rb some client
selection paths do not have an attack rectangle to collect targets from.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzIntProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


SKILL_ID = "2121006"
LEVELS = range(1, 31)
MOB_COUNT = 6
LT = (-640, -365)
RB = (65, 220)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def backup(path: Path, suffix: str, dry_run: bool) -> None:
    backup_path = path.with_name(path.name + suffix)
    if backup_path.exists():
        return
    if dry_run:
        print(f"[dry-run] would create backup: {backup_path}")
        return
    shutil.copy2(path, backup_path)
    print(f"backup: {backup_path}")


def set_child(parent, prop) -> bool:
    existing = parent.child(prop.name)
    if existing is not None:
        if isinstance(existing, WzIntProperty) and isinstance(prop, WzIntProperty):
            if int(existing.value) == int(prop.value):
                return False
        if isinstance(existing, WzVectorProperty) and isinstance(prop, WzVectorProperty):
            if (int(existing.x), int(existing.y)) == (int(prop.x), int(prop.y)):
                return False
        prop.parent = parent
        parent._children[prop.name] = prop
        return True

    parent.add(prop)
    return True


def patch_client_img(path: Path, dry_run: bool) -> int:
    data = path.read_bytes()
    key = WzKey.for_region("GMS")
    image = WzImage.from_bytes(data, key=key, name=path.name)
    root = image.parse()
    level_root = root.get(f"skill/{SKILL_ID}/level")
    if level_root is None:
        raise RuntimeError(f"missing client node skill/{SKILL_ID}/level")

    changes = 0
    for level in LEVELS:
        level_node = level_root.child(str(level))
        if level_node is None:
            raise RuntimeError(f"missing client node skill/{SKILL_ID}/level/{level}")
        if set_child(level_node, WzVectorProperty("lt", LT[0], LT[1], level_node)):
            changes += 1
        if set_child(level_node, WzIntProperty("mobCount", MOB_COUNT, level_node)):
            changes += 1
        if set_child(level_node, WzVectorProperty("rb", RB[0], RB[1], level_node)):
            changes += 1

    if changes == 0:
        return 0
    if dry_run:
        print(f"[dry-run] would update {changes} client IMG fields: {path}")
        return changes

    backup(path, ".bak-2121006-aoe", dry_run=False)
    out = encode_image_body(image, image.wz_file.reader)
    atomic_write_bytes(path, out)
    print(f"updated {changes} client IMG fields: {path}")
    return changes


def set_or_insert_int(block: str, name: str, value: int) -> tuple[str, bool]:
    pattern = rf'<int name="{re.escape(name)}" value="-?\d+"\s*/>'
    repl = f'<int name="{name}" value="{value}"/>'
    if re.search(pattern, block):
        new_block = re.sub(pattern, repl, block, count=1)
        return new_block, new_block != block

    for anchor in (r'(<int name="mastery" value="-?\d+"\s*/>)', r'(<int name="attackCount" value="-?\d+"\s*/>)'):
        if re.search(anchor, block):
            return re.sub(anchor, rf'\1{repl}', block, count=1), True
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1), True


def set_or_insert_vector(block: str, name: str, x: int, y: int) -> tuple[str, bool]:
    pattern = rf'<vector name="{re.escape(name)}" x="-?\d+" y="-?\d+"\s*/>'
    repl = f'<vector name="{name}" x="{x}" y="{y}"/>'
    if re.search(pattern, block):
        new_block = re.sub(pattern, repl, block, count=1)
        return new_block, new_block != block

    if name == "lt":
        return re.sub(r'(<imgdir name="\d+">)', rf'\1{repl}', block, count=1), True
    return block.replace("</imgdir>", f"{repl}</imgdir>", 1), True


def patch_xml_level(block: str) -> tuple[str, int]:
    changes = 0
    block, changed = set_or_insert_vector(block, "lt", LT[0], LT[1])
    changes += int(changed)
    block, changed = set_or_insert_int(block, "mobCount", MOB_COUNT)
    changes += int(changed)
    block, changed = set_or_insert_vector(block, "rb", RB[0], RB[1])
    changes += int(changed)
    return block, changes


def patch_server_xml(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    start = text.find(f'<imgdir name="{SKILL_ID}">')
    if start < 0:
        raise RuntimeError(f"missing server XML skill {SKILL_ID}")
    end = text.find('<imgdir name="2121007">', start)
    if end < 0:
        raise RuntimeError("missing server XML skill 2121007 boundary")

    skill_block = text[start:end]
    changes = 0
    for level in LEVELS:
        pattern = re.compile(rf'<imgdir name="{level}">.*?</imgdir>')

        def repl(match):
            nonlocal changes
            new_block, level_changes = patch_xml_level(match.group(0))
            changes += level_changes
            return new_block

        skill_block, count = pattern.subn(repl, skill_block, count=1)
        if count != 1:
            raise RuntimeError(f"missing server XML level {level}")

    if changes == 0:
        return 0
    new_text = text[:start] + skill_block + text[end:]
    if dry_run:
        print(f"[dry-run] would update {changes} server XML fields: {path}")
        return changes

    backup(path, ".bak-2121006-aoe", dry_run=False)
    atomic_write_text(path, new_text)
    print(f"updated {changes} server XML fields: {path}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--client-img", default=str(ROOT / "clien" / "Data" / "Skill" / "212.img"))
    parser.add_argument("--server-xml", default=str(ROOT / "gms-server" / "wz" / "Skill.wz" / "212.img.xml"))
    args = parser.parse_args()

    client_changes = patch_client_img(Path(args.client_img), args.dry_run)
    server_changes = patch_server_xml(Path(args.server_xml), args.dry_run)
    print(
        f"{SKILL_ID}: mobCount={MOB_COUNT}, "
        f"lt=({LT[0]},{LT[1]}), rb=({RB[0]},{RB[1]}), "
        f"clientChanges={client_changes}, serverChanges={server_changes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
