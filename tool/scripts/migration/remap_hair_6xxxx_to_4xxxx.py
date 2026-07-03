#!/usr/bin/env python3
"""Move migrated 6xxxx hair IDs into old-client-friendly 4xxxx ranges."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_hair_new_only import (  # noqa: E402
    CLIENT_EQP_STRING,
    CLIENT_HAIR,
    CLIENT_MAKE_CHAR,
    HANDBOOK_HAIR,
    SERVER_EQP_STRING,
    SERVER_HAIR,
    SERVER_MAKE_CHAR,
    atomic_write_text,
    backup,
    image_to_xml,
    patch_client_make_char,
    patch_server_make_char,
    replace_client_hair_strings,
    replace_hair_handbook,
    replace_server_hair_strings,
)

BASE_REMAP = {
    63110: 48700,
    63120: 48710,
    63130: 48720,
    63140: 48730,
    63160: 48740,
    64610: 48750,
    64650: 48760,
    64660: 48770,
    63150: 42200,
    63480: 42210,
    63490: 42220,
    64620: 42230,
    64630: 42240,
    64640: 42250,
    64910: 42260,
    64920: 42270,
}

ID_REMAP = {
    old_base + color: new_base + color
    for old_base, new_base in BASE_REMAP.items()
    for color in range(8)
}

TEXT_ROOTS = [
    ROOT / "gms-server/scripts",
    ROOT / "gms-server/scripts-zh-CN",
    ROOT / "gms-server/src/main/java",
    ROOT / "gms-server/src/main/resources/db/migration",
    ROOT / "gms-server/wz/String.wz",
    ROOT / "gms-server/wz/Etc.wz",
    ROOT / "gms-server/handbook",
]
TEXT_SUFFIXES = {".java", ".js", ".sql", ".xml", ".txt", ".py"}
DB_MIGRATION = ROOT / "gms-server/src/main/resources/db/migration/V2.1.22__remap_hair_6xxxx_to_4xxxx.sql"


def mapped_hair_ids() -> list[int]:
    return sorted(int(path.stem) for path in CLIENT_HAIR.glob("*.img"))


def remap_existing_ids(ids: list[int]) -> list[int]:
    return sorted(ID_REMAP.get(hair_id, hair_id) for hair_id in ids)


def move_file(src: Path, dst: Path, dry_run: bool) -> bool:
    if not src.exists():
        return False
    if dst.exists():
        raise FileExistsError(f"target already exists: {dst}")
    if not dry_run:
        backup(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return True


def remap_client_hair(dry_run: bool) -> int:
    moved = 0
    for old_id, new_id in sorted(ID_REMAP.items()):
        if move_file(CLIENT_HAIR / f"{old_id:08d}.img", CLIENT_HAIR / f"{new_id:08d}.img", dry_run):
            moved += 1
    return moved


def remap_server_hair(dry_run: bool) -> int:
    changed = 0
    for old_id, new_id in sorted(ID_REMAP.items()):
        old_xml = SERVER_HAIR / f"{old_id:08d}.img.xml"
        new_xml = SERVER_HAIR / f"{new_id:08d}.img.xml"
        new_img = CLIENT_HAIR / f"{new_id:08d}.img"
        if not old_xml.exists() and new_xml.exists():
            continue
        if not old_xml.exists() and not new_img.exists():
            continue
        if new_xml.exists() and old_xml.exists():
            raise FileExistsError(f"target already exists: {new_xml}")
        changed += 1
        if not dry_run:
            if old_xml.exists():
                backup(old_xml)
                old_xml.unlink()
            atomic_write_text(new_xml, image_to_xml(new_img))
    return changed


def text_files() -> list[Path]:
    files: list[Path] = []
    for root in TEXT_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return sorted(set(files))


def replace_text_ids(dry_run: bool) -> tuple[int, int]:
    pattern = re.compile(r"\b(" + "|".join(str(old) for old in sorted(ID_REMAP, reverse=True)) + r")\b")
    changed_files = 0
    replacements = 0
    for path in text_files():
        if path == DB_MIGRATION:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")

        def repl(match: re.Match[str]) -> str:
            nonlocal replacements
            replacements += 1
            return str(ID_REMAP[int(match.group(1))])

        updated = pattern.sub(repl, text)
        if updated != text:
            changed_files += 1
            if not dry_run:
                backup(path)
                atomic_write_text(path, updated)
    return changed_files, replacements


def write_db_remap(dry_run: bool) -> bool:
    cases = "\n".join(f"        WHEN {old_id} THEN {new_id}" for old_id, new_id in sorted(ID_REMAP.items()))
    old_ids = ", ".join(str(old_id) for old_id in sorted(ID_REMAP))
    data = f"""-- Move already-persisted migrated 6xxxx hair IDs into the 4xxxx compatibility range.

UPDATE `characters`
SET `hair` = CASE `hair`
{cases}
        ELSE `hair`
    END
WHERE `hair` IN ({old_ids});

UPDATE `playernpcs`
SET `hair` = CASE `hair`
{cases}
        ELSE `hair`
    END
WHERE `hair` IN ({old_ids});
"""
    old = DB_MIGRATION.read_text(encoding="utf-8") if DB_MIGRATION.exists() else ""
    if old == data:
        return False
    if not dry_run:
        backup(DB_MIGRATION)
        atomic_write_text(DB_MIGRATION, data)
    return True


def refresh_generated_tables(dry_run: bool) -> None:
    ids = mapped_hair_ids()
    male_defaults = [40070, 40080, 42100]
    female_defaults = [43270, 44440, 44450]
    replace_server_hair_strings(ids, dry_run)
    replace_client_hair_strings(ids, dry_run)
    replace_hair_handbook(ids, dry_run)
    patch_server_make_char(male_defaults, female_defaults, dry_run)
    patch_client_make_char(male_defaults, female_defaults, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    before_ids = mapped_hair_ids()
    target_ids = remap_existing_ids(before_ids)
    collisions = sorted(set(before_ids) & (set(target_ids) - set(before_ids)))
    if collisions:
        raise RuntimeError(f"remap target collisions: {collisions[:10]}")

    client_moved = remap_client_hair(args.dry_run)
    server_changed = remap_server_hair(args.dry_run)
    text_files_changed, text_replacements = replace_text_ids(args.dry_run)
    db_changed = write_db_remap(args.dry_run)
    if not args.dry_run:
        refresh_generated_tables(False)

    print(f"client Hair files moved: {client_moved}")
    print(f"server Hair XML files changed: {server_changed}")
    print(f"text files changed: {text_files_changed}, id replacements: {text_replacements}")
    print(f"db remap migration changed: {db_changed}")
    if args.dry_run:
        print("dry-run only; no files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
