#!/usr/bin/env python3
"""Clone Hero skill 1121011 to 1121012 and name it 测试."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(PATCH_SKILL))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzStringProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from patch_2321010_skill import clone_property, find_imgdir_block, put_child_after  # noqa: E402


SOURCE_ID = "1121011"
TARGET_ID = "1121012"
TARGET_NAME = "测试"

CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"


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


def patch_client_skill(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    skill_root = root.get("skill")
    source = root.get(f"skill/{SOURCE_ID}")
    if skill_root is None or source is None:
        raise RuntimeError(f"missing client skill/{SOURCE_ID}: {path}")

    clone = clone_property(source, TARGET_ID)
    put_child_after(skill_root, SOURCE_ID, clone)
    if dry_run:
        print(f"[dry-run] would clone client skill {SOURCE_ID} -> {TARGET_ID}: {path}")
        return
    backup(path, ".bak-1121012-test-skill", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"cloned client skill {SOURCE_ID} -> {TARGET_ID}: {path}")


def patch_client_string(path: Path, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    source = root.get(SOURCE_ID)
    if source is None:
        raise RuntimeError(f"missing client string {SOURCE_ID}: {path}")

    clone = clone_property(source, TARGET_ID)
    name = clone.child("name")
    if isinstance(name, WzStringProperty):
        name._value = TARGET_NAME
    else:
        clone.add(WzStringProperty("name", TARGET_NAME, clone))
    put_child_after(root, SOURCE_ID, clone)
    if dry_run:
        print(f"[dry-run] would clone client string {SOURCE_ID} -> {TARGET_ID}: {path}")
        return
    backup(path, ".bak-1121012-test-skill", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"cloned client string {SOURCE_ID} -> {TARGET_ID}: {path}")


def clone_xml_block(text: str, rename_string: bool) -> str:
    source_start, source_end = find_imgdir_block(text, SOURCE_ID)
    source = text[source_start:source_end]
    clone = source.replace(f'<imgdir name="{SOURCE_ID}">', f'<imgdir name="{TARGET_ID}">', 1)
    if rename_string:
        clone = re.sub(
            r'<string name="name" value="[^"]*"\s*/>',
            f'<string name="name" value="{TARGET_NAME}"/>',
            clone,
            count=1,
        )

    try:
        target_start, target_end = find_imgdir_block(text, TARGET_ID)
        text = text[:target_start] + text[target_end:]
    except RuntimeError:
        pass

    insert_at = find_imgdir_block(text, SOURCE_ID)[1]
    return text[:insert_at] + clone + text[insert_at:]


def patch_server_xml(path: Path, dry_run: bool, rename_string: bool) -> None:
    text = path.read_text(encoding="utf-8")
    new_text = clone_xml_block(text, rename_string=rename_string)
    if new_text == text:
        print(f"server XML already contains {TARGET_ID}: {path}")
        return
    if dry_run:
        print(f"[dry-run] would clone server XML {SOURCE_ID} -> {TARGET_ID}: {path}")
        return
    backup(path, ".bak-1121012-test-skill", dry_run=False)
    atomic_write_text(path, new_text)
    print(f"cloned server XML {SOURCE_ID} -> {TARGET_ID}: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    patch_client_skill(CLIENT_SKILL, args.dry_run)
    patch_client_string(CLIENT_STRING, args.dry_run)
    patch_server_xml(SERVER_SKILL, args.dry_run, rename_string=False)
    patch_server_xml(SERVER_STRING, args.dry_run, rename_string=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
