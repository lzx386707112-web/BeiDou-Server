#!/usr/bin/env python3
"""Build the mob-only A test variant for Arcana map 450005131."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450005131
SOURCE_MOB_ID = "8644001"
TARGET_MOB_ID = "8644002"
EXPECTED_REPLACEMENTS = 13
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/450005131_A_仅8644002")

sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzStringProperty, WzSubProperty  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def life_snapshot(life: WzSubProperty) -> list[tuple[str, tuple[tuple[str, object], ...]]]:
    return [
        (
            entry.name,
            tuple(
                (child.name, getattr(child, "value", None))
                for child in entry.children()
                if child.name != "id"
            ),
        )
        for entry in life.children()
    ]


def mob_counts(life: WzSubProperty) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in life.children():
        if migration.child_value(entry, "type") != "m":
            continue
        mob_id = str(migration.child_value(entry, "id"))
        counts[mob_id] = counts.get(mob_id, 0) + 1
    return counts


def main() -> int:
    source = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    source_hash = sha256(source)
    image = migration.load_image(source, migration.GMS_KEY)
    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("map has no life node")

    before_snapshot = life_snapshot(life)
    before_counts = mob_counts(life)
    if before_counts.get(SOURCE_MOB_ID) != EXPECTED_REPLACEMENTS:
        raise RuntimeError(
            f"expected {EXPECTED_REPLACEMENTS} mobs {SOURCE_MOB_ID}, got {before_counts}"
        )

    replaced = 0
    for entry in life.children():
        if (
            migration.child_value(entry, "type") == "m"
            and migration.child_value(entry, "id") == SOURCE_MOB_ID
        ):
            mob_id = entry.child("id")
            if not isinstance(mob_id, WzStringProperty):
                raise RuntimeError(f"life/{entry.name}/id is not a string")
            entry._children["id"] = WzStringProperty("id", TARGET_MOB_ID, entry)
            replaced += 1

    client = DESTINATION / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = DESTINATION / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    written_life = written.root.child("life")
    if not isinstance(written_life, WzSubProperty):
        raise RuntimeError("written map has no life node")
    if life_snapshot(written_life) != before_snapshot:
        raise RuntimeError("life data other than mob id changed")
    after_counts = mob_counts(written_life)
    if after_counts.get(SOURCE_MOB_ID, 0) != 0 or after_counts != {TARGET_MOB_ID: 31}:
        raise RuntimeError(f"unexpected written mob counts: {after_counts}")
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError("server XML differs from the client map tree")
    if sha256(source) != source_hash:
        raise RuntimeError("source client map was modified")

    readme = f"""# 450005131 A 版测试

本版本仅将地图 life 中的 `{SOURCE_MOB_ID}` 替换为上一张正常地图使用的
`{TARGET_MOB_ID}`。共替换 {replaced} 个刷怪项；坐标、foothold、对象、背景、
Portal、小地图和其他字段均保持不变。

- 客户端 IMG SHA256：`{sha256(client)}`
- 服务端 XML SHA256：`{sha256(server)}`
- 原图 SHA256：`{source_hash}`

测试时同时替换 Client 与 Server 文件，重新打包 Map.wz 并重启服务端。
若本版不再黑屏，根因位于 `8644001` 与 `8644002` 同图加载的兼容路径；
若仍然黑屏，下一步检查第 6 层 `connect/rope` 对象。
"""
    migration.atomic_write_text(DESTINATION / "README_测试说明.md", readme)
    print(
        f"map={MAP_ID} replaced={replaced} life={len(written_life.children())} "
        f"mobs={after_counts} client_sha256={sha256(client)}"
    )
    print(f"output={DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
