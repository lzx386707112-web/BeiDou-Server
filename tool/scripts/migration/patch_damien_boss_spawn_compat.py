#!/usr/bin/env python3
"""Remove modern Damien action records that crash the legacy client on spawn."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from wzpy import WzImage  # noqa: E402


REMOVE_TOP_LEVEL = {
    8880110: (
        "attack2", "attack3", "attack4", "attack5", "attack6",
        "skillAfter1", "skillAfter3", "skillAfter4",
        "directionAct1",
    ),
    8880111: (
        "attack2", "attack3", "attack4", "attack5", "attack6", "attack7",
        "skillAfter1", "skillAfter2", "skillAfter3",
        "skillAfter4", "skill6", "skillAfter6", "skill7",
        "skill8", "skill9", "skillAfter9", "skill10",
    ),
}
REMOVE_ATTACK_INFO = {
    8880110: (
        ("attack1", "info", "range", "start"),
        ("attack1", "info", "range", "areaCount"),
        ("attack1", "info", "range", "attackCount"),
        ("attack1", "info", "areaWarning"),
        ("attack1", "info", "effectAfter"),
        ("attack1", "info", "delay"),
        ("attack1", "info", "onlyFsm"),
    ),
    8880111: (
        ("attack1", "info", "hit", "attach"),
        ("attack1", "info", "effect"),
        ("attack1", "info", "onlyFsm"),
    ),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_tree_removal(before: bytes, after: bytes, root: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    expected_removed = {path for path in before_records if path[:len(root)] == root}
    removed = set(before_records) - set(after_records)
    if removed != expected_removed:
        raise RuntimeError(f"unexpected removals for {'/'.join(root)}: {sorted(removed)}")
    if set(after_records) - set(before_records):
        raise RuntimeError(f"record added while removing {'/'.join(root)}")
    parent = root[:-1]
    expected_order = tuple(name for name in before_orders[parent] if name != root[-1])
    if after_orders.get(parent) != expected_order:
        raise RuntimeError(f"sibling order changed at {'/'.join(parent)}")
    for path, raw in before_records.items():
        affected = path[:len(root)] == root or root[:len(path)] == path
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {'/'.join(path)}")


def remove_img_path(data: bytes, path: tuple[str, ...]) -> bytes:
    records, _ = arc.raw_record_state(data)
    if path not in records:
        return data
    updated = arc.mutate_img(data, "remove", path, region="GMS").data
    verify_tree_removal(data, updated, path)
    return updated


def xml_has_path(text: str, path: tuple[str, ...]) -> bool:
    current = arc.scan_xml(text)
    for part in path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            return False
        current = matches[0]
    return True


def approved_paths(mob_id: int) -> tuple[tuple[str, ...], ...]:
    return (
        *REMOVE_ATTACK_INFO[mob_id],
        ("info", "firstAttack"),
        *((name,) for name in REMOVE_TOP_LEVEL[mob_id]),
    )


def patch_mob(mob_id: int) -> None:
    client = demian.client_mob_path(mob_id)
    original = client.read_bytes()
    patched = original
    for path in approved_paths(mob_id):
        patched = remove_img_path(patched, path)
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=client.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{client.name} parse failed after spawn projection")
    root_names = tuple(child.name for child in checked.root.children())
    allowed_orders = {
        demian.SPAWN_SAFE_BASE_TOP_LEVEL,
        demian.LEGACY_BOSS_TOP_LEVEL_BY_MOB[mob_id],
    }
    if root_names not in allowed_orders:
        raise RuntimeError(f"{client.name} root projection mismatch: {root_names}")
    if patched != original:
        arc.atomic_write_bytes(client, patched)

    server = demian.server_mob_path("wz", mob_id)
    text = server.read_text(encoding="utf-8")
    updated = text
    for path in approved_paths(mob_id):
        if xml_has_path(updated, path):
            updated = arc.mutate_xml(updated, "remove", path)
    xml_root = ET.fromstring(updated)
    xml_root_names = tuple(
        child.get("name") for child in xml_root if child.tag == "imgdir"
    )
    if xml_root_names not in allowed_orders:
        raise RuntimeError(f"{server.name} root projection mismatch: {xml_root_names}")
    if updated != text:
        arc.atomic_write_text(server, updated)


def main() -> int:
    targets = []
    for mob_id in demian.BOSS_IDS:
        targets.extend((demian.client_mob_path(mob_id), demian.server_mob_path("wz", mob_id)))
        patch_mob(mob_id)
    first = {str(path.relative_to(ROOT)): sha256_file(path) for path in targets}
    for mob_id in demian.BOSS_IDS:
        patch_mob(mob_id)
    second = {str(path.relative_to(ROOT)): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError("Damien boss spawn patch is not idempotent")
    print("damien boss spawn compatibility patch ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
