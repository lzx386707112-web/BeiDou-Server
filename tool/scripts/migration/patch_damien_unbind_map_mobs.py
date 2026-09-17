#!/usr/bin/env python3
"""Stop Damien maps from naming boss/shadow-sword mobs in info.

The old client treats info/shadowzone and info/boss as map-owned spawn
hooks. Encounter already creates 8880102 from Java; keep that path and
drop the map WZ binding.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzImage  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402

MAPS = (350160240, 350160280)
UNBIND = ("shadowzone", "boss")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_remove_scope(before: bytes, after: bytes, root: tuple[str, ...]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    if before_orders.get(()) != after_orders.get(()):
        raise RuntimeError("top-level sibling order changed")
    gone = set(before_records) - set(after_records)
    expected_gone = {path for path in before_records if path[: len(root)] == root}
    if gone != expected_gone:
        raise RuntimeError(f"unexpected removals: {sorted(gone)}")
    added = set(after_records) - set(before_records)
    if added:
        raise RuntimeError(f"unexpected additions: {sorted(added)}")
    for path, raw in before_records.items():
        affected = path[: len(root)] == root or root[: len(path)] == path
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for parent, names in before_orders.items():
        if parent[: len(root)] == root:
            continue
        if parent == root[:-1]:
            expected = tuple(name for name in names if name != root[-1])
            if after_orders.get(parent) != expected:
                raise RuntimeError(f"sibling order changed: {parent}")
            continue
        if after_orders.get(parent) != names:
            raise RuntimeError(f"sibling order changed: {parent}")


def strip_client(map_id: int) -> None:
    path = demian.client_map_path(map_id)
    image = load_checked(path, arc.GMS_KEY)
    info = image.root.child("info")
    for name in UNBIND:
        if info is None or info.child(name) is None:
            continue
        original = path.read_bytes()
        patched = mutate_img(original, "remove", ("info", name), region="GMS").data
        verify_remove_scope(original, patched, ("info", name))
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{path.name} parse failed after removing {name}")
        if checked.root.get(f"info/{name}") is not None:
            raise RuntimeError(f"{path.name} still has info/{name}")
        if demian.numeric_gaps(checked.root.child("back")):
            raise RuntimeError(f"{path.name} back gaps after removing {name}")
        arc.atomic_write_bytes(path, patched)


def strip_xml(map_id: int) -> None:
    path = demian.server_map_path(map_id)
    text = path.read_text(encoding="utf-8")
    updated = text
    for name in UNBIND:
        updated = updated.replace(f'    <int name="{name}" value="8880111"/>\n', "")
        updated = updated.replace(f'    <int name="{name}" value="8880102"/>\n', "")
    if updated != text:
        arc.atomic_write_text(path, updated)


def verify() -> None:
    for map_id in MAPS:
        image = load_checked(demian.client_map_path(map_id), arc.GMS_KEY)
        for name in UNBIND:
            if image.root.get(f"info/{name}") is not None:
                raise RuntimeError(f"{map_id} client still has info/{name}")
        xml = demian.server_map_path(map_id).read_text(encoding="utf-8")
        if 'name="shadowzone"' in xml or 'name="boss"' in xml:
            raise RuntimeError(f"{map_id} XML still binds boss/shadowzone")


def patch_once() -> None:
    for map_id in MAPS:
        strip_client(map_id)
        strip_xml(map_id)
    verify()


def main() -> int:
    targets = []
    for map_id in MAPS:
        targets.extend((demian.client_map_path(map_id), demian.server_map_path(map_id)))
    patch_once()
    first = {str(path): sha256_file(path) for path in targets}
    patch_once()
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"unbind patcher is not idempotent: {first} vs {second}")
    print("damien map-mob unbind ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
