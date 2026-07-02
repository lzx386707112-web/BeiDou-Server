#!/usr/bin/env python3
"""Migrate only the item nodes required by v095 Cygnus/Future Gate quests."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from migrate_095_cygnus import (
    ROOT,
    SRC_CLIENT,
    SRC_SERVER,
    TARGET_KEY,
    WzFile,
    WzImage,
    atomic_write_bytes,
    atomic_write_text,
    backup,
    clone_property,
    gms_reader,
)
from wzpy.writer import encode_image_body


QUEST_ITEM_IDS = [
    2270021,
    4000642, 4000643, 4000644, 4000645, 4000646, 4000647, 4000648,
    4000649, 4000650, 4000651, 4000652, 4000653, 4000654, 4000655,
    4000656, 4000657, 4000658, 4000659,
    4020013,
    4032921, 4032922, 4032924, 4032925, 4032926, 4032927, 4032928,
    4032930, 4032940, 4032941,
]


def item_group(item_id: int) -> tuple[str, str]:
    text = f"{item_id:08d}"
    if 2000000 <= item_id < 3000000:
        return "Consume", text[:4]
    if 4000000 <= item_id < 5000000:
        return "Etc", text[:4]
    raise RuntimeError(f"unsupported quest item id {item_id}")


def find_imgdir_block_any(text: str, node_name: str, start: int = 0) -> tuple[int, int]:
    pattern = re.compile(rf'<imgdir\b[^>]*\bname="{re.escape(node_name)}"[^>]*>')
    match = pattern.search(text, start)
    if match is None:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    root_start = match.start()
    depth = 0
    for tag_match in re.finditer(r"</?imgdir\b[^>]*>", text[root_start:]):
        tag = tag_match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return root_start, root_start + tag_match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def insert_or_replace_root_child(text: str, root_name: str, child_name: str, child_block: str) -> str:
    root_start, root_end = find_imgdir_block_any(text, root_name)
    root_block = text[root_start:root_end]
    try:
        child_start, child_end = find_imgdir_block_any(root_block, child_name)
        root_block = root_block[:child_start] + root_block[child_end:]
    except RuntimeError:
        pass

    insert_at = root_block.rfind("</imgdir>")
    if insert_at < 0:
        raise RuntimeError(f"cannot insert into {root_name}")
    root_block = root_block[:insert_at] + child_block + root_block[insert_at:]
    return text[:root_start] + root_block + text[root_end:]


def patch_server_item_xml() -> None:
    by_image: dict[tuple[str, str], list[int]] = {}
    for item_id in QUEST_ITEM_IDS:
        by_image.setdefault(item_group(item_id), []).append(item_id)

    for (category, prefix), item_ids in sorted(by_image.items()):
        src_path = SRC_SERVER / "wz/Item.wz" / category / f"{prefix}.img.xml"
        dst_path = ROOT / "gms-server/wz/Item.wz" / category / f"{prefix}.img.xml"
        if not src_path.exists():
            raise RuntimeError(f"missing source item XML {src_path}")

        src_text = src_path.read_text(encoding="utf-8")
        dst_text = dst_path.read_text(encoding="utf-8") if dst_path.exists() else (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><imgdir name="{prefix}.img"></imgdir>'
        )
        root_name = ET.parse(dst_path).getroot().get("name") if dst_path.exists() else f"{prefix}.img"
        for item_id in item_ids:
            item_name = f"{item_id:08d}"
            try:
                source_start, source_end = find_imgdir_block_any(src_text, item_name)
            except RuntimeError as exc:
                raise RuntimeError(f"missing source item XML node {category}/{prefix}.img/{item_name}")
            dst_text = insert_or_replace_root_child(dst_text, root_name, item_name, src_text[source_start:source_end])

        backup(dst_path)
        atomic_write_text(dst_path, dst_text)


def patch_client_item_images() -> None:
    by_image: dict[tuple[str, str], list[int]] = {}
    for item_id in QUEST_ITEM_IDS:
        by_image.setdefault(item_group(item_id), []).append(item_id)

    with WzFile.open(str(SRC_CLIENT / "Item.wz"), region="EMS", version=95) as src_wz:
        for (category, prefix), item_ids in sorted(by_image.items()):
            src_img = src_wz.root.get(f"{category}/{prefix}.img")
            if src_img is None:
                raise RuntimeError(f"missing source client item image {category}/{prefix}.img")
            src_img.parse()

            dst_path = ROOT / "clien/Data/Item" / category / f"{prefix}.img"
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if dst_path.exists():
                dst_img = WzImage.from_bytes(dst_path.read_bytes(), key=TARGET_KEY, name=f"{prefix}.img")
                dst_img.parse()
            else:
                dst_img = WzImage(f"{prefix}.img")

            for item_id in item_ids:
                item_name = f"{item_id:08d}"
                source = src_img.get(item_name)
                if source is None:
                    raise RuntimeError(f"missing source client item node {category}/{prefix}.img/{item_name}")
                dst_img.root.add(clone_property(source, item_name, dst_img.root, source_region="EMS"))

            backup(dst_path)
            atomic_write_bytes(dst_path, encode_image_body(dst_img, gms_reader()))


def main() -> int:
    patch_server_item_xml()
    patch_client_item_images()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
