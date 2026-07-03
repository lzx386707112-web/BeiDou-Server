#!/usr/bin/env python3
"""Strip redundant hair canvas _outlink fields for old-client compatibility."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzStringProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from migrate_hair_new_only import (  # noqa: E402
    CLIENT_HAIR,
    SERVER_HAIR,
    atomic_write_bytes,
    atomic_write_text,
    backup,
    gms_reader,
    image_to_xml,
)

KEY = WzKey.for_region("GMS")


def strip_outlinks(node) -> tuple[int, int]:
    removed = 0
    missing_pixels = 0
    if isinstance(node, WzCanvasProperty):
        outlink = node.child("_outlink")
        if isinstance(outlink, WzStringProperty):
            if not node.has_pixels():
                missing_pixels += 1
            else:
                del node._children["_outlink"]
                removed += 1
    if hasattr(node, "children"):
        for child in node.children():
            child_removed, child_missing = strip_outlinks(child)
            removed += child_removed
            missing_pixels += child_missing
    return removed, missing_pixels


def patch_one(path: Path, dry_run: bool) -> tuple[int, int]:
    image = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    root = image.parse()
    removed, missing_pixels = strip_outlinks(root)
    if missing_pixels:
        raise RuntimeError(f"{path.name}: {missing_pixels} _outlink canvas nodes have no pixels")
    if removed and not dry_run:
        backup(path)
        atomic_write_bytes(path, encode_image_body(image, gms_reader()))
        xml_path = SERVER_HAIR / f"{path.name}.xml"
        if xml_path.exists():
            backup(xml_path)
            atomic_write_text(xml_path, image_to_xml(path))
    return removed, missing_pixels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("ids", nargs="*", type=int, help="optional hair ids to patch")
    args = parser.parse_args()

    if args.ids:
        paths = [CLIENT_HAIR / f"{hair_id:08d}.img" for hair_id in args.ids]
    else:
        paths = sorted(CLIENT_HAIR.glob("*.img"))
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing hair files: {missing[:5]}")

    changed_files = 0
    removed_total = 0
    for path in paths:
        removed, _ = patch_one(path, args.dry_run)
        if removed:
            changed_files += 1
            removed_total += removed
            print(f"{path.name}: removed {removed} _outlink nodes")
    print(f"changed files: {changed_files}")
    print(f"removed _outlink nodes: {removed_total}")
    if args.dry_run:
        print("dry-run only; no files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
