#!/usr/bin/env python3
"""Bisect the 30 remaining Morass foothold objects in the full map."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAP_ID = 450006130
DESTINATION = Path("/Users/lizixian/Downloads/神秘河/AB测试_450006130_第七轮")
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import build_arcane_river_450006130_ab3 as round3  # noqa: E402
import migrate_arcane_river_fields as migration  # noqa: E402


GROUP_A = {"foothold_Bridge"}
GROUP_B = {"foothold_Bridge2", "foothold_Castle", "stone"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep_morass_groups(image, groups: set[str]) -> None:
    for layer in image.root.children():
        if not layer.name.isdigit():
            continue
        objects = layer.child("obj")
        for entry in list(objects.children()):
            resource = migration.child_value(entry, "oS")
            if resource == "morass" and migration.child_value(entry, "l1") not in groups:
                migration.remove_child(objects, entry.name)


def write_variant(name: str, groups: set[str], expected_objects: int) -> dict[str, object]:
    image = round3.full_morass_image()
    keep_morass_groups(image, groups)
    root = DESTINATION / name
    client = root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img"
    server = root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    migration.atomic_write_bytes(
        client, migration.encode_image_body(image, migration.gms_reader())
    )
    migration.atomic_write_text(server, migration.image_to_xml(image, f"{MAP_ID}.img"))

    written = migration.load_image(client, migration.GMS_KEY)
    objects = [
        entry
        for layer in written.root.children()
        if layer.name.isdigit()
        for entry in layer.child("obj").children()
    ]
    morass_groups = {
        migration.child_value(entry, "l1")
        for entry in objects
        if migration.child_value(entry, "oS") == "morass"
    }
    if len(objects) != expected_objects or morass_groups != groups:
        raise RuntimeError(
            f"{name}: expected {expected_objects} objects and {groups}, "
            f"got {len(objects)} and {morass_groups}"
        )
    expected_xml = migration.image_to_xml(written, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"{name}: client and server trees differ")
    return {
        "client": sha256(client),
        "server": sha256(server),
        "objects": len(objects),
        "morass_groups": sorted(morass_groups),
    }


def output_paths(name: str) -> tuple[Path, Path]:
    root = DESTINATION / name
    return (
        root / f"Client/Data/Map/Map/Map4/{MAP_ID}.img",
        root / f"Server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml",
    )


def install(name: str) -> Path:
    generated_client, generated_server = output_paths(name)
    if not generated_client.exists() or not generated_server.exists():
        raise RuntimeError("seventh-round package is missing; generate it before installing")
    client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
    server = ROOT / f"gms-server/wz/Map.wz/Map/Map4/{MAP_ID}.img.xml"
    label = "A" if name.startswith("A_") else "B"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(f"/private/tmp/arcane-river-{MAP_ID}-before-AB7-{label}-{timestamp}")
    for path in (client, server):
        backup = backup_root / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    migration.atomic_write_bytes(client, generated_client.read_bytes())
    migration.atomic_write_text(server, generated_server.read_text(encoding="utf-8-sig"))
    if sha256(client) != sha256(generated_client):
        raise RuntimeError(f"installed seventh-round {label} client differs from package")
    image = migration.load_image(client, migration.GMS_KEY)
    expected_xml = migration.image_to_xml(image, f"{MAP_ID}.img")
    if server.read_text(encoding="utf-8-sig") != expected_xml:
        raise RuntimeError(f"installed seventh-round {label} server differs from client")
    return backup_root


def write_readme(a: dict[str, object], b: dict[str, object]) -> None:
    text = f"""# 450006130 崩溃 AB 测试（第七轮）

完整地图排除全部 Morass 对象后实机正常，因此问题锁定在 30 个带 foothold
元数据的 Morass 对象。本轮保留完整背景、NPC、life、小地图和 BGM，只拆对象。

## A_仅foothold_Bridge

- 6 个 connect + 14 个 `foothold_Bridge`，共 20 个对象。
- Client SHA256：`{a['client']}`
- Server SHA256：`{a['server']}`

## B_其余foothold对象

- 6 个 connect + 11 个 `foothold_Bridge2` + 4 个 `foothold_Castle`
  + 1 个 `stone`，共 22 个对象。
- Client SHA256：`{b['client']}`
- Server SHA256：`{b['server']}`

## 结果判断

- A 崩、B 正常：问题在 `foothold_Bridge`。
- A 正常、B 崩：问题在 Bridge2/Castle/stone 组。
- A、B 都正常：两组存在组合触发条件。
- A、B 都崩：两组各自含有问题分支。
"""
    migration.atomic_write_text(DESTINATION / "README_测试顺序.md", text)


def build() -> tuple[dict[str, object], dict[str, object]]:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    a = write_variant("A_仅foothold_Bridge", GROUP_A, 20)
    b = write_variant("B_其余foothold对象", GROUP_B, 22)
    write_readme(a, b)
    return a, b


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-a", action="store_true")
    parser.add_argument("--install-b", action="store_true")
    args = parser.parse_args()
    if args.install_a and args.install_b:
        parser.error("--install-a and --install-b are mutually exclusive")
    if args.install_a or args.install_b:
        name = "A_仅foothold_Bridge" if args.install_a else "B_其余foothold对象"
        backup = install(name)
        client = ROOT / f"clien/Data/Map/Map/Map4/{MAP_ID}.img"
        print(f"installed {name}: sha256={sha256(client)} backup={backup}")
        return 0
    a, b = build()
    print(f"A: {a}")
    print(f"B: {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
