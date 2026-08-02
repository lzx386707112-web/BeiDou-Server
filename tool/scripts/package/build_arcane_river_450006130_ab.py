#!/usr/bin/env python3
"""Build two single-variable crash-isolation variants for map 450006130."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_arcane_river_fields as migration  # noqa: E402
from wzpy import WzSubProperty  # noqa: E402


UNIQUE_OBJECT_BRANCHES = {
    ("morass", "castle_Outside", "acc", "5"),
    ("morass", "castle_Outside", "acc", "7"),
    ("morass", "castle_Outside", "foothold_Castle", "2"),
    ("morass", "castle_Outside", "foothold_Castle", "6"),
    ("morass", "castle_Outside", "stone", "7"),
}


def object_branch(entry) -> tuple[str, str, str, str]:
    return tuple(
        str(migration.child_value(entry, name) or "") for name in ("oS", "l0", "l1", "l2")
    )


def write_variant(name: str, mutate) -> tuple[int, int, str, str]:
    source = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    image = migration.load_image(source, migration.GMS_KEY)
    mutate(image)

    root = DESTINATION / name
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    asset = root / "Client/Data/Map/Obj/morass.img"
    migration.atomic_write_bytes(
        client,
        migration.encode_image_body(image, migration.gms_reader()),
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))
    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "clien/Data/Map/Obj/morass.img", asset)

    written = migration.load_image(client, migration.GMS_KEY)
    life = written.root.child("life")
    life_count = len(life.children()) if isinstance(life, WzSubProperty) else 0
    object_count = sum(
        len(objects.children())
        for layer in written.root.children()
        if layer.name.isdigit()
        and isinstance((objects := layer.child("obj")), WzSubProperty)
    )
    client_hash = hashlib.sha256(client.read_bytes()).hexdigest()
    server_hash = hashlib.sha256(server.read_bytes()).hexdigest()
    return life_count, object_count, client_hash, server_hash


def without_life(image) -> None:
    life = image.root.child("life")
    if not isinstance(life, WzSubProperty):
        raise RuntimeError("map has no life node")
    life._children.clear()


def without_unique_objects(image) -> None:
    removed = []
    for layer in image.root.children():
        objects = layer.child("obj") if layer.name.isdigit() else None
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if object_branch(entry) in UNIQUE_OBJECT_BRANCHES:
                removed.append((layer.name, entry.name, object_branch(entry)))
                migration.remove_child(objects, entry.name)
    if len(removed) != len(UNIQUE_OBJECT_BRANCHES):
        raise RuntimeError(f"expected 5 unique objects, removed {removed}")


def write_readme(results: dict[str, tuple[int, int, str, str]]) -> None:
    a = results["A_无NPC"]
    b = results["B_去独占对象"]
    text = f"""# 450006130 崩溃 AB 测试

两个版本都基于当前项目地图生成，并同时提供客户端 IMG、`Obj/morass.img`
与服务端 XML。
每次测试都必须同时替换对应目录中的 Client 和 Server 文件，再重新打 Map.wz。

## A_无NPC

- life 数量：{a[0]}
- 对象数量：{a[1]}
- 仅清空 life；对象、背景、碰撞、传送点、小地图和 BGM 保持不变。
- Client SHA256：`{a[2]}`
- Server SHA256：`{a[3]}`

## B_去独占对象

- life 数量：{b[0]}
- 对象数量：{b[1]}
- 保留全部 NPC，仅移除本图独占使用的 5 个 morass 对象分支引用。
- Client SHA256：`{b[2]}`
- Server SHA256：`{b[3]}`

## 结果判断

- A 正常、B 崩溃：问题在 NPC/life。
- A 崩溃、B 正常：问题在 5 个独占对象分支。
- A、B 都崩溃：继续检查 back、miniMap、BGM 或地图核心节点。
- A、B 都正常：NPC 与独占对象之间存在组合问题，下一轮再二分。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def main() -> int:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    results = {
        "A_无NPC": write_variant("A_无NPC", without_life),
        "B_去独占对象": write_variant("B_去独占对象", without_unique_objects),
    }
    write_readme(results)
    for name, values in results.items():
        print(f"{name}: life={values[0]} objects={values[1]} client_sha256={values[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
