#!/usr/bin/env python3
"""Align Damien attackAfter with visible impact. Do not rewrite the IMG."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from wzpy import WzImage  # noqa: E402

# attack1 slash ends ~1800ms; attack3 areaWarning peaks ~2970ms.
# Leftover 2730/8700 were MCV/ground-burst clocks and miss the pose.
TIMING = {
    8880110: {
        ("attack1", "info", "attackAfter"): 1800,
        ("attack3", "info", "attackAfter"): 2970,
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_client(mob_id: int, edits: dict[tuple[str, ...], int]) -> str:
    path = demian.client_mob_path(mob_id)
    data = path.read_bytes()
    for record, value in edits.items():
        image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
        image.parse()
        node = image.root.get("/".join(record))
        if node is None:
            raise RuntimeError(f"{mob_id} missing {'/'.join(record)}")
        if int(node.value) == value:
            continue
        patched = arc.mutate_img(data, "edit", record, values={"value": value}, region="GMS").data
        arc.verify_raw_record_scope(data, patched, {record}, allow_additions=False)
        checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{mob_id} parse failed after {'/'.join(record)}")
        data = patched
    image = WzImage.from_bytes(data, key=arc.GMS_KEY, name=path.name)
    image.parse()
    for record, value in edits.items():
        node = image.root.get("/".join(record))
        if node is None or int(node.value) != value:
            raise RuntimeError(f"{mob_id} {'/'.join(record)} is not {value}")
    arc.atomic_write_bytes(path, data)
    return sha256_bytes(data)


def patch_xml(mob_id: int, edits: dict[tuple[str, ...], int]) -> str:
    path = demian.server_mob_path(mob_id)
    text = path.read_text(encoding="utf-8")
    replacements = {
        8880110: (
            ('<int name="attackAfter" value="2730"/>', '<int name="attackAfter" value="1800"/>', 1),
            ('<int name="attackAfter" value="8700"/>', '<int name="attackAfter" value="2970"/>', 1),
        ),
    }
    for old, new, count in replacements[mob_id]:
        if text.count(old) != count and text.count(new) != count:
            raise RuntimeError(f"{mob_id} XML unexpected attackAfter ({old})")
        text = text.replace(old, new, count)
    for record, value in edits.items():
        needle = f'<int name="{record[-1]}" value="{value}"/>'
        if needle not in text:
            raise RuntimeError(f"{mob_id} XML missing {needle}")
    arc.atomic_write_text(path, text)
    return sha256_bytes(text.encode("utf-8"))


def install() -> dict[str, str]:
    hashes = {}
    for mob_id, edits in TIMING.items():
        hashes[str(demian.client_mob_path(mob_id))] = patch_client(mob_id, edits)
        hashes[str(demian.server_mob_path(mob_id))] = patch_xml(mob_id, edits)
    return hashes


def main() -> int:
    first = install()
    second = install()
    if first != second:
        raise RuntimeError(f"hit timing generator is not idempotent: {first} vs {second}")
    print("damien hit timing")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
