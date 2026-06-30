#!/usr/bin/env python3
"""Set Character/Weapon info/limitBreak to Integer.MAX_VALUE.

Both client .img files and server .img.xml files are handled. The client
side is parsed through tool/wz-python and re-serialized as WZ IMG data.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzIntProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


LIMIT_BREAK = 2_147_483_647


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def set_client_limit_break(path: Path, dry_run: bool) -> str:
    data = path.read_bytes()
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    info = root.child("info")
    if info is None:
        return "missing-info"

    existing = info.child("limitBreak")
    if isinstance(existing, WzIntProperty) and int(existing.value) == LIMIT_BREAK:
        return "ok"

    prop = WzIntProperty("limitBreak", LIMIT_BREAK, info)
    info._children["limitBreak"] = prop
    if dry_run:
        return "would-update" if existing is not None else "would-add"

    out = encode_image_body(image, image.wz_file.reader)
    atomic_write_bytes(path, out)
    return "updated" if existing is not None else "added"


def render_xml(tree: ET.ElementTree) -> str:
    ET.indent(tree, space="  ")
    body = ET.tostring(tree.getroot(), encoding="unicode", short_empty_elements=True)
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + body + "\n"


def set_server_xml_limit_break(path: Path, dry_run: bool) -> str:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(path, parser=parser)
    root = tree.getroot()
    info = None
    for child in root:
        if child.tag == "imgdir" and child.get("name") == "info":
            info = child
            break
    if info is None:
        return "missing-info"

    existing = None
    for child in info:
        if child.tag == "int" and child.get("name") == "limitBreak":
            existing = child
            break

    if existing is not None and existing.get("value") == str(LIMIT_BREAK):
        return "ok"

    if dry_run:
        return "would-update" if existing is not None else "would-add"

    if existing is None:
        existing = ET.Element("int", {"name": "limitBreak", "value": str(LIMIT_BREAK)})
        info.append(existing)
        status = "added"
    else:
        existing.set("value", str(LIMIT_BREAK))
        status = "updated"
    atomic_write_text(path, render_xml(tree))
    return status


def walk_files(path: Path, suffix: str) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob(f"*{suffix}") if p.is_file())


def count_statuses(statuses: list[str]) -> str:
    counts: dict[str, int] = {}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def patch_group(label: str, files: list[Path], func, dry_run: bool) -> list[str]:
    statuses: list[str] = []
    total = len(files)
    for index, path in enumerate(files, 1):
        status = func(path, dry_run)
        statuses.append(status)
        if index == total or index % 500 == 0:
            print(f"{label}: {index}/{total} ({count_statuses(statuses)})")
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--client-dir",
        type=Path,
        default=ROOT / "clien" / "Data" / "Character" / "Weapon",
    )
    parser.add_argument(
        "--server-dir",
        type=Path,
        default=ROOT / "gms-server" / "wz" / "Character.wz" / "Weapon",
    )
    parser.add_argument("--client-only", action="store_true")
    parser.add_argument("--server-only", action="store_true")
    args = parser.parse_args()

    if args.client_only and args.server_only:
        raise SystemExit("--client-only and --server-only cannot be used together")

    if not args.server_only:
        client_files = walk_files(args.client_dir, ".img")
        client_statuses = patch_group("client", client_files, set_client_limit_break, args.dry_run)
        print(f"client summary: {count_statuses(client_statuses)}")

    if not args.client_only:
        server_files = walk_files(args.server_dir, ".img.xml")
        server_statuses = patch_group("server", server_files, set_server_xml_limit_break, args.dry_run)
        print(f"server summary: {count_statuses(server_statuses)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
